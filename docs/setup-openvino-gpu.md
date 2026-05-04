# OpenVINO 2026.1 on Intel Arc Pro B-series (Linux)

Hands-on install + verify. Targets:
- **GPU**: Intel Arc Pro B70 (Battlemage G31, PCI ID `8086:e223`) — also covers
  B60 / B580 / B570 with the same NEO compute runtime.
- **OS**: Ubuntu 26.04 LTS. NEO 26.05+ in the archive supports Battlemage
  natively, so no third-party Intel graphics repo is needed. (For 22.04 / 24.04
  you do need the Intel APT repo — see "Older Ubuntu" at the bottom.)
- **Toolkit**: OpenVINO 2026.1.0 + OpenVINO GenAI + Optimum-Intel + transformers
  + sentence-transformers — installed via `uv` into a per-project venv, not
  system Python.

## 1. GPU compute runtime (system, one-time)

```bash
sudo apt install -y \
  ocl-icd-libopencl1 \
  intel-opencl-icd \
  libze-intel-gpu1 \
  libze1 \
  clinfo

# Add yourself to the render + video groups so non-root processes can use
# /dev/dri/render*. Takes effect on next login.
sudo usermod -a -G render,video "$USER"
```

Verify (works in any shell, no group membership needed for query):

```bash
$ clinfo -l
Platform #0: Intel(R) OpenCL Graphics
 `-- Device #0: Intel(R) Graphics [0xe223]
```

`0xe223` = Battlemage G31 = your B70.

> **Ubuntu 26.04 package renames**: in older docs you'll see
> `intel-level-zero-gpu` and `level-zero` — those are now
> `libze-intel-gpu1` and `libze1`. The compute runtime is the same; only
> the Debian package names changed.

## 2. uv project for the Python toolkit

The toolkit lives in a per-project venv to keep system Python clean and
let different services pin different OpenVINO versions.

```bash
mkdir -p /work/main/dev-tools/openvino-dev
cd /work/main/dev-tools/openvino-dev

uv init --no-readme --no-pin-python --python 3.12 --bare
uv add \
  openvino \
  openvino-genai \
  openvino-tokenizers \
  'optimum-intel[openvino,nncf]' \
  sentence-transformers \
  transformers \
  torch
```

Quick device check:

```bash
uv run python -c "
from openvino import Core
core = Core()
for d in core.available_devices:
    print(f'{d:8} {core.get_property(d, \"FULL_DEVICE_NAME\")}')"
```

Expected output on this machine:

```
CPU      AMD Ryzen 9 9950X 16-Core Processor
GPU      Intel(R) Graphics [0xe223] (dGPU)
```

## 3. End-to-end smoke test (GPU embeddings)

`scripts/smoke_embed.py`:

```python
"""Export a sentence-transformer to OpenVINO IR and embed on GPU vs CPU."""
from __future__ import annotations
import time
import numpy as np
from optimum.intel import OVModelForFeatureExtraction
from transformers import AutoTokenizer

MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"
SENTENCES = ["OpenVINO 2026.1 on Intel Arc Pro B70."] * 32


def mean_pool(last_hidden, mask):
    mask = mask[..., None].astype(last_hidden.dtype)
    return (last_hidden * mask).sum(1) / mask.sum(1).clip(min=1e-9)


def normalize(x):
    return x / np.linalg.norm(x, axis=1, keepdims=True).clip(min=1e-12)


tok = AutoTokenizer.from_pretrained(MODEL_ID)
results = {}
for device in ("CPU", "GPU"):
    model = OVModelForFeatureExtraction.from_pretrained(
        MODEL_ID, export=True, device=device,
    )
    enc = tok(SENTENCES, padding=True, truncation=True,
              return_tensors="pt", max_length=256)
    inputs = {k: v.numpy() for k, v in enc.items()}
    for _ in range(2):  # warmup
        model(**inputs)
    best = min(
        (time.perf_counter() - (t0 := time.perf_counter()) or model(**inputs))
        for _ in range(5)
    )
    # Real timing
    best = float("inf")
    for _ in range(5):
        t0 = time.perf_counter()
        out = model(**inputs)
        best = min(best, time.perf_counter() - t0)
    last = out.last_hidden_state
    last = last.numpy() if hasattr(last, "numpy") else last
    results[device] = normalize(mean_pool(last, inputs["attention_mask"]))
    print(f"{device:4s} best of 5: {best * 1000:6.1f} ms  shape={results[device].shape}")

if {"CPU", "GPU"} <= results.keys():
    diff = float(np.abs(results["CPU"] - results["GPU"]).max())
    print(f"CPU vs GPU max abs diff: {diff:.2e}")
```

Run it:

```bash
uv run python scripts/smoke_embed.py
```

Reference numbers from this machine (Ryzen 9 9950X + Arc Pro B70, 32-sentence
batch, MiniLM-L6-v2):

| Device | Best of 5 | Notes |
|--------|-----------|-------|
| CPU    | ~4.5 ms   | AMD Zen 5, 16 cores |
| GPU    | ~0.7 ms   | Battlemage B70 — **6.4× CPU** |

Max abs diff between CPU and GPU embeddings: ~1e-3 (FP16 vs FP32 precision
during compile; numerically equivalent for retrieval).

## 4. What you've got

- **`openvino`** — runtime + Python API
- **`openvino-genai`** — pre-built pipelines for LLM text-gen, image gen,
  speech, semantic search; one-call `LLMPipeline`, `Text2ImagePipeline`, etc.
- **`openvino-tokenizers`** — packaged tokenizers compiled to OV IR (so the
  whole tokenize → embed pipeline runs in one OV graph if you want)
- **`optimum-intel[openvino,nncf]`** — HuggingFace bridge (`OVModelFor*`,
  `OVStableDiffusionPipeline`, etc.) plus NNCF for INT8/INT4 quantization
- **`sentence-transformers`** — for the model hub side; the OV runtime does
  the actual inference once you load via `OVModelForFeatureExtraction`
- **`transformers`** + **`torch`** — needed for export at first load; not on
  the inference hot path

## 5. Common patterns

**Quantize a model to INT8 once, reuse the saved IR forever:**

```python
from optimum.intel import OVModelForFeatureExtraction, OVWeightQuantizationConfig
m = OVModelForFeatureExtraction.from_pretrained(
    "sentence-transformers/all-mpnet-base-v2",
    export=True,
    quantization_config=OVWeightQuantizationConfig(bits=8),
)
m.save_pretrained("./mpnet-int8-ov")
# Later — no re-export, no torch dependency at load time:
m2 = OVModelForFeatureExtraction.from_pretrained("./mpnet-int8-ov", device="GPU")
```

**LLM text-gen via openvino-genai (no transformers at runtime):**

```python
import openvino_genai as ov_genai
pipe = ov_genai.LLMPipeline("./qwen3-1.5b-int4-ov", device="GPU")
print(pipe.generate("Explain BM25 in one sentence.", max_new_tokens=80))
```

(Export the model first via `optimum-cli export openvino --model <hf-id> --weight-format int4 ./out`.)

## 6. Older Ubuntu (22.04 / 24.04)

Archive NEO is too old for Battlemage. Add Intel's graphics repo:

```bash
curl https://repositories.intel.com/graphics/intel-graphics.key \
  | sudo gpg --dearmor --output /usr/share/keyrings/intel-graphics.gpg
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/intel-graphics.gpg] \
  https://repositories.intel.com/graphics/ubuntu jammy unified" \
  | sudo tee /etc/apt/sources.list.d/intel-graphics.list
sudo apt update
sudo apt install -y intel-opencl-icd intel-level-zero-gpu level-zero
```

(Substitute `noble` for 24.04. Package names there are still the older form.)

## 7. References

- OpenVINO 2026.1 Linux install: <https://docs.openvino.ai/2026/get-started/install-openvino/install-openvino-linux.html>
- GPU configuration guide: <https://docs.openvino.ai/2026/get-started/configurations/configurations-intel-gpu.html>
- OpenVINO GenAI: <https://github.com/openvinotoolkit/openvino.genai>
- Optimum-Intel: <https://github.com/huggingface/optimum-intel>
