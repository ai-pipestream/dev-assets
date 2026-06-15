# docling + DJL serving — parse + embed smoke test

A self-contained installer + test that proves a machine can run the two
inference backends the platform's **parser** (docling) and **embedder** (DJL
Serving) depend on — on **GPU** and on **CPU**.

It does two things end to end:

1. **Parse** a sample document with **docling-serve** → Markdown.
2. **Embed** a sentence with **DJL Serving**, using the two MiniLM models the
   embedder consumes.

## Models

| Serving name | HuggingFace model | Dim |
|---|---|---|
| `minilm` | `sentence-transformers/all-MiniLM-L6-v2` | 384 |
| `paraphrase_MiniLM_L3_v2` | `sentence-transformers/paraphrase-MiniLM-L3-v2` | 384 |

## Usage

```bash
./run-test.sh gpu          # NVIDIA GPU path (default)
./run-test.sh cpu          # CPU-only path
./run-test.sh gpu --down   # also tear the stack down when done
```

Exit 0 only if docling returns Markdown **and** DJL returns embeddings from both
models. GPU and CPU use the same ports (docling `:5001`, DJL `:8090`), so run one
at a time — `--down`, or `docker compose -f docker-compose.<mode>.yml down`,
before switching.

## Requirements

- **GPU path**: NVIDIA driver + Container Toolkit + CDI. If missing, install with
  the platform's `nvidia-gpu-setup.sh`, or use the CPU path.
- **CPU path**: nothing GPU-specific. DJL uses the `cpu-full` image (PyTorch
  bundled — required for the sentence-transformer models). Markedly slower,
  especially first-run model download/load.

## Images

| | GPU | CPU |
|---|---|---|
| docling | `ghcr.io/docling-project/docling-serve-cu128:v1.14.3` | `ghcr.io/docling-project/docling-serve:v1.14.3` |
| DJL | `deepjavalibrary/djl-serving:0.36.0-pytorch-gpu` | `deepjavalibrary/djl-serving:0.36.0-cpu-full` |

## How it maps to the platform

- The **parser** module reaches docling at `quarkus.docling.base-url`
  (`http://docling-serve:5001` in the container network).
- The **embedder** module reaches DJL at `EMBEDDER_DJL_SERVING_URL`
  (`http://djl-serving:8080` in the container network) and health-gates on it
  being reachable with models loaded.

The platform compose stack wires these via `deploy/compose-stack/`'s
`docker-compose-nvidia.yaml` / `docker-compose-cpu.yaml` overlays; this installer
is the standalone proof that the inference layer works on the box first.

## API reference (what the test calls)

```bash
# docling: parse a file → Markdown
curl -X POST http://localhost:5001/v1/convert/file -F "files=@sample.html"
#   → .document.md_content

# DJL: register a model (synchronous load)
curl -X POST "http://localhost:8090/models?url=<urlencoded djl://ai.djl.huggingface.pytorch/<hf-id>>&model_name=minilm&engine=PyTorch&synchronous=true"

# DJL: embed a sentence
curl -X POST http://localhost:8090/predictions/minilm \
  -H "Content-Type: application/json" -d '{"inputs":"some text"}'
#   → [-0.0234, ...]  (384 floats)
```
