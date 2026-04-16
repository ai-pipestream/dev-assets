#!/usr/bin/env bash
#
# Start DJL Serving on macOS / Apple Silicon (M1/M2/M3/M4) and pre-load
# the 3 models the pipestream pipeline tests need.
#
# DJL Serving does not support Metal/CoreML acceleration in Docker, so
# this uses the aarch64 CPU variant of the image. Performance is fine
# for integration tests (MiniLM ~30ms/doc on M2 Pro in the p95
# measurements); don't use this for the multi-thousand-doc load runs.
#
# For ARM Linux (NVIDIA Jetson, AWS Graviton, etc.) this script also
# works — DJL's aarch64 image is Linux-aarch64 compatible and the script
# just cares about the architecture tag.
#
# Port: 18090 (same as the Linux GPU script; pick different via
# R3_DJL_PORT env var if you run both concurrently).
# Container name: r3-djl-arm.
#
set -euo pipefail

CONTAINER_NAME="${R3_DJL_CONTAINER_NAME:-r3-djl-arm}"
HOST_PORT="${R3_DJL_PORT:-18090}"
DJL_VERSION="${R3_DJL_VERSION:-0.36.0}"
DJL_IMAGE="deepjavalibrary/djl-serving:${DJL_VERSION}-aarch64"
DJL_URL="http://localhost:${HOST_PORT}"

log() { printf '[start-djl] %s\n' "$*"; }
die() { printf '[start-djl] FATAL: %s\n' "$*" >&2; exit 1; }

# ----- preflight ----------------------------------------------------------

command -v docker >/dev/null 2>&1 || die "docker CLI not on PATH (install Docker Desktop or colima)"
command -v curl >/dev/null 2>&1 || die "curl not on PATH"

ARCH=$(uname -m)
case "${ARCH}" in
    arm64|aarch64) log "arch: ${ARCH} (ok)" ;;
    *)             die "This script is for arm64 / aarch64 hosts. Detected ${ARCH} — use start-djl-linux-gpu.sh for x86_64 + NVIDIA or pick the CPU variant manually." ;;
esac

# macOS ships with BSD ss/netstat; lsof is more portable.
port_busy() {
    if command -v lsof >/dev/null 2>&1; then
        lsof -nP -iTCP:"${HOST_PORT}" -sTCP:LISTEN >/dev/null 2>&1
    elif command -v ss >/dev/null 2>&1; then
        ss -tln 2>/dev/null | grep -qE ":${HOST_PORT}\\b"
    else
        netstat -an 2>/dev/null | grep -qE "\\.?${HOST_PORT}[^0-9]+LISTEN"
    fi
}

if port_busy; then
    log "port ${HOST_PORT} already in use — checking if it's our container"
    if docker ps --filter "name=^${CONTAINER_NAME}\$" --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}\$"; then
        log "stopping existing ${CONTAINER_NAME} so we can restart fresh"
        docker stop "${CONTAINER_NAME}" >/dev/null
        sleep 2
    else
        die "port ${HOST_PORT} held by something else (not ${CONTAINER_NAME}). Free it or set R3_DJL_PORT=<other>."
    fi
fi

# ----- pull image ---------------------------------------------------------

if ! docker image inspect "${DJL_IMAGE}" >/dev/null 2>&1; then
    log "pulling ${DJL_IMAGE} (first run can take a few minutes over home broadband)"
    docker pull "${DJL_IMAGE}"
fi

# ----- start container ---------------------------------------------------

log "starting ${CONTAINER_NAME} on port ${HOST_PORT} (CPU-only, aarch64)"
# Heap lower than Linux-GPU — M-series Macs typically 16-24 GB total RAM.
docker run -d --rm \
    --name "${CONTAINER_NAME}" \
    -p "${HOST_PORT}:8080" \
    -e JAVA_OPTS="-Xmx6g -Xms2g -XX:+ExitOnOutOfMemoryError" \
    "${DJL_IMAGE}" >/dev/null

log "waiting for /ping (can take up to 30s on M-series first boot)"
for i in $(seq 1 90); do
    if curl -sf --max-time 1 "${DJL_URL}/ping" >/dev/null 2>&1; then
        log "DJL up after ${i}s"
        break
    fi
    sleep 1
    [ "$i" = "90" ] && die "DJL didn't respond on /ping within 90s — check 'docker logs ${CONTAINER_NAME}'"
done

# ----- register the 3 models ---------------------------------------------

# Same knobs as the Linux GPU script. max_worker=2 still helps on
# CPU because short-doc inference is IO-bound on tokenization (not ALU).
DJL_OPTS="batch_size=1&max_batch_delay=0&min_worker=1&max_worker=2&job_queue_size=1000&translatorFactory=ai.djl.huggingface.translator.TextEmbeddingTranslatorFactory&synchronous=true"

register_djl_pytorch() {
    local model_name="$1"
    local hf_id="$2"
    local url_encoded
    url_encoded=$(printf '%s' "djl://ai.djl.huggingface.pytorch/${hf_id}" | python3 -c 'import sys,urllib.parse;print(urllib.parse.quote(sys.stdin.read(),safe=""))')
    log "registering ${model_name} (PyTorch / djl://) — ${hf_id}"
    local resp
    resp=$(curl -sf --max-time 600 -X POST \
        "${DJL_URL}/models?url=${url_encoded}&model_name=${model_name}&engine=PyTorch&${DJL_OPTS}")
    case "${resp}" in
        *registered*) log "  ✓ ${model_name} READY" ;;
        *)            die "register ${model_name} failed: ${resp}" ;;
    esac
}

register_djl_pytorch "minilm"            "sentence-transformers/all-MiniLM-L6-v2"
register_djl_pytorch "paraphrase-minilm" "sentence-transformers/paraphrase-MiniLM-L3-v2"

# bge-m3: Python engine with a custom handler. Same reason as the Linux
# script — CVE-2025-32434 guard blocks torch.load of .bin weights.
log "preparing bge-m3 (Python engine + custom handler)"
docker exec "${CONTAINER_NAME}" mkdir -p /opt/ml/model/bge-m3

docker exec -i "${CONTAINER_NAME}" tee /opt/ml/model/bge-m3/serving.properties >/dev/null <<'PROPS'
engine=Python
option.model_id=BAAI/bge-m3
option.predict_timeout=240
PROPS

docker exec -i "${CONTAINER_NAME}" tee /opt/ml/model/bge-m3/requirements.txt >/dev/null <<'REQS'
transformers
sentencepiece
REQS

docker exec -i "${CONTAINER_NAME}" tee /opt/ml/model/bge-m3/model.py >/dev/null <<'PY'
"""Custom DJL handler for BAAI/bge-m3 dense embeddings via transformers."""
from djl_python import Input, Output
import torch

# torch < 2.6 blocks torch.load for pickle-format weights (CVE-2025-32434).
# BGE-M3 on HuggingFace only has pytorch_model.bin (no safetensors).
# Patch only when needed; torch >= 2.6 handles this natively.
if tuple(int(x) for x in torch.__version__.split("+")[0].split(".")[:2]) < (2, 6):
    import transformers.utils.import_utils as _tiu
    import transformers.modeling_utils as _mu
    _noop = lambda: None
    _tiu.check_torch_load_is_safe = _noop
    _mu.check_torch_load_is_safe = _noop

from transformers import AutoTokenizer, AutoModel

model = None
tokenizer = None


def get_model(properties):
    model_id = properties.get("model_id", "BAAI/bge-m3")
    # M-series Macs: no CUDA in Docker. DJL's aarch64 container runs CPU
    # torch; the "cuda" branch below is never taken. Keeping the check
    # identical to the Linux script for portability.
    device = "cuda" if torch.cuda.is_available() else "cpu"

    tok = AutoTokenizer.from_pretrained(model_id)
    mdl = AutoModel.from_pretrained(model_id).to(device)
    mdl.eval()
    if device == "cuda":
        mdl = mdl.half()

    return mdl, tok


def mean_pooling(model_output, attention_mask):
    token_embeddings = model_output[0]
    mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
    return torch.sum(token_embeddings * mask_expanded, 1) / torch.clamp(
        mask_expanded.sum(1), min=1e-9
    )


def handle(inputs: Input) -> Output:
    global model, tokenizer

    if not model:
        model, tokenizer = get_model(inputs.get_properties())

    if inputs.is_empty():
        return None

    data = inputs.get_as_json()

    if isinstance(data, list):
        sentences = data
    elif isinstance(data, dict):
        sentences = data.get("inputs", data.get("text", []))
    else:
        sentences = [str(data)]

    if isinstance(sentences, str):
        sentences = [sentences]

    device = next(model.parameters()).device

    max_len = int(inputs.get_properties().get("max_length", 512))
    encoded = tokenizer(
        sentences, padding=True, truncation=True, max_length=max_len, return_tensors="pt"
    ).to(device)

    with torch.no_grad():
        outputs = model(**encoded)

    embeddings = mean_pooling(outputs, encoded["attention_mask"])
    embeddings = torch.nn.functional.normalize(embeddings, p=2, dim=1)

    result = embeddings.float().cpu().tolist()

    return Output().add_as_json(result)
PY

# bge-m3 on CPU is ~3-5x slower than on the Linux GPU version — expect
# first embed to take 10-30s while the model loads + first inference
# warms the torch graph. Subsequent calls land in the 100-300ms range
# for typical sentence batches.
log "registering bge-m3 (Python engine — pip install + 2.3GB model download, ~3-10 min)"
resp=$(curl -sf --max-time 900 -X POST \
    "${DJL_URL}/models?url=/opt/ml/model/bge-m3&model_name=bge-m3&engine=Python&min_worker=1&max_worker=1&job_queue_size=1000&synchronous=true")
case "${resp}" in
    *registered*) log "  ✓ bge-m3 READY" ;;
    *)            die "register bge-m3 failed: ${resp}" ;;
esac

# ----- final report -------------------------------------------------------

log ""
log "============================================================"
log "DJL Serving READY at ${DJL_URL} (CPU / aarch64)"
log "Models loaded:"
curl -s "${DJL_URL}/models" | python3 -c "
import sys, json
d = json.load(sys.stdin)
for m in sorted(d['models'], key=lambda x: x['modelName']):
    print(f'  - {m[\"modelName\"]:24s} {m[\"status\"]}')
"
log ""
log "Smoke test:"
log "  curl -sX POST '${DJL_URL}/predictions/minilm' -H 'Content-Type: application/json' -d '{\"inputs\":[\"hello world\"]}' | head -c 100"
log ""
log "Stop with: docker stop ${CONTAINER_NAME}"
log "============================================================"
