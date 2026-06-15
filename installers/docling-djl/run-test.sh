#!/usr/bin/env bash
# run-test.sh — bring up standalone docling + DJL serving and verify, end to end:
#   1. docling parses a sample document into Markdown
#   2. DJL serves the TWO MiniLM models and returns sentence embeddings
#
# Usage:
#   ./run-test.sh gpu        # NVIDIA GPU path (default; needs container toolkit)
#   ./run-test.sh cpu        # CPU-only path
#   ./run-test.sh gpu --down # tear the stack down afterwards
#
# Exit 0 only if BOTH docling and DJL (both models) work.

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

MODE="${1:-gpu}"
DOWN=0
[ "${2:-}" = "--down" ] && DOWN=1
case "$MODE" in
  gpu) COMPOSE="docker-compose.gpu.yml" ;;
  cpu) COMPOSE="docker-compose.cpu.yml" ;;
  *) echo "usage: $0 [gpu|cpu] [--down]" >&2; exit 2 ;;
esac

DOCLING_URL="http://localhost:5001"
DJL_URL="http://localhost:8090"
SAMPLE="sample.html"

# serving-name : huggingface id  (the two models the embedder consumes)
MODELS=(
  "minilm:sentence-transformers/all-MiniLM-L6-v2"
  "paraphrase_MiniLM_L3_v2:sentence-transformers/paraphrase-MiniLM-L3-v2"
)

say() { echo "[docling-djl:$MODE] $*"; }
fail() { echo "[docling-djl:$MODE] FAIL: $*" >&2; exit 1; }

cleanup() {
  if [ "$DOWN" = 1 ]; then
    say "tearing down"
    docker compose -f "$COMPOSE" down -v >/dev/null 2>&1 || true
  fi
  return 0
}
trap cleanup EXIT

say "bringing up ($COMPOSE) ..."
docker compose -f "$COMPOSE" up -d

say "waiting for docling + djl to report healthy ..."
deadline=$(( $(date +%s) + 360 ))
while :; do
  d=$(docker compose -f "$COMPOSE" ps docling-serve --format '{{.Health}}' 2>/dev/null || true)
  j=$(docker compose -f "$COMPOSE" ps djl-serving   --format '{{.Health}}' 2>/dev/null || true)
  [ "$d" = "healthy" ] && [ "$j" = "healthy" ] && break
  [ "$(date +%s)" -ge "$deadline" ] && fail "services not healthy within 6 min (docling=$d djl=$j)"
  sleep 5
done
say "both healthy"

# ---- 1. docling: parse the sample document into Markdown ----------------------
say "parsing $SAMPLE via docling /v1/convert/file ..."
md=$(curl -fsS -X POST "$DOCLING_URL/v1/convert/file" -F "files=@$SAMPLE" \
      | python3 -c "import json,sys; print(json.load(sys.stdin)['document']['md_content'])")
[ -n "$md" ] || fail "docling returned empty markdown"
echo "----- docling markdown (first 5 lines) -----"
echo "$md" | sed '/^$/d' | head -5
echo "--------------------------------------------"
say "docling OK (${#md} chars of markdown)"

# ---- 2. DJL: register both models, then embed a sentence ---------------------
register_model() {
  local name="$1" hf="$2"
  if curl -fsS "$DJL_URL/models/$name" >/dev/null 2>&1; then
    say "model $name already registered"; return 0
  fi
  local url="djl://ai.djl.huggingface.pytorch/$hf"
  local enc; enc=$(python3 -c "from urllib.parse import quote;import sys;print(quote(sys.argv[1],safe=''))" "$url")
  say "registering $name (synchronous HF download — first run is slow) ..."
  curl -fsS -X POST "$DJL_URL/models?url=$enc&model_name=$name&engine=PyTorch&synchronous=true" >/dev/null \
    || fail "could not register $name"
}

embed() {
  # echoes the embedding dimension for a model, or fails
  local name="$1" text="$2"
  local vec; vec=$(curl -fsS -X POST "$DJL_URL/predictions/$name" \
      -H "Content-Type: application/json" -d "{\"inputs\":\"$text\"}")
  python3 -c "import json,sys; v=json.loads(sys.argv[1]); assert isinstance(v,list) and v and all(isinstance(x,(int,float)) for x in v), 'not a vector'; print(len(v))" "$vec" \
    || fail "model $name did not return a numeric embedding vector"
}

for entry in "${MODELS[@]}"; do
  register_model "${entry%%:*}" "${entry#*:}"
done

say "embedding a sentence with each model ..."
for entry in "${MODELS[@]}"; do
  name="${entry%%:*}"
  dim=$(embed "$name" "pipestream parses and embeds documents")
  say "DJL OK — model $name returned a ${dim}-dim embedding"
done

say "PASS — docling parsed the document AND DJL embedded with both models ($MODE)"
