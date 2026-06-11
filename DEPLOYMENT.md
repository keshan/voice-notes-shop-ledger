# Deployment And Modal Runbook

This project runs as a Gradio web app on Modal. The UI is served by a lightweight
ASGI web function, while llama.cpp inference runs in a separate GPU worker that
keeps the GGUF model warm between requests.

## Production URLs

- Live app: <https://keshan--voice-notes-shop-ledger-fastapi-app.modal.run>
- Modal app name: `voice-notes-shop-ledger`
- Modal model volume: `voice-notes-shop-ledger-models`
- GitHub repo: <https://github.com/keshan/voice-notes-shop-ledger>

## Modal Architecture

`modal_app.py` defines four Modal objects:

| Object | Type | Purpose |
| --- | --- | --- |
| `download_model` | `@app.function` | Downloads the GGUF from Hugging Face into the persistent Modal volume. |
| `LedgerAgent` | `@app.cls` | GPU-backed llama.cpp worker used for extraction. |
| `smoke_test_model` | `@app.function` | Runs one extraction inside Modal and reports model/runtime metadata. |
| `fastapi_app` | `@app.function` + `@modal.asgi_app()` | Serves the Gradio UI and calls `LedgerAgent`. |

The web function and model worker are separated intentionally:

- The web layer stays responsive and cheap.
- The model worker gets GPU, CPU, and memory resources.
- The GGUF can stay loaded in a warm worker between Gradio requests.
- The UI can still render even if model inference is cold-starting.

## Runtime Choices

| Setting | Value | Why |
| --- | --- | --- |
| Base image | `nvidia/cuda:12.8.1-devel-ubuntu24.04` | CUDA-compatible runtime for llama.cpp GPU inference. |
| Python | `3.12` | Matches local development and Modal image setup. |
| GPU | Modal `A10` | Enough VRAM for a 12B-class quantized GGUF demo. |
| Model repo | `unsloth/gemma-4-12b-it-GGUF` | Gemma 4 12B GGUF distribution. |
| Model file | `gemma-4-12b-it-UD-Q4_K_XL.gguf` | Good quality/performance quant for the hackathon demo. |
| Runtime | `llama-cpp-python` CUDA wheel | Avoids source-building llama.cpp during deploy. |
| GPU layers | `LLAMA_N_GPU_LAYERS=-1` | Offload all possible layers to GPU. |
| Context | `LLAMA_N_CTX=2048` | Keeps ledger extraction responsive. |

The source-build path for CUDA llama.cpp was tested, but it failed during image
build because `libcuda.so.1` is only available on GPU runtime machines, not
during the Modal image build. The prebuilt CUDA wheel is therefore the reliable
deployment path for this app.

## First-Time Setup

Install and authenticate Modal:

```bash
pip install modal
modal setup
```

Download the model into the persistent Modal volume:

```bash
modal run modal_app.py::download_model
```

This downloads:

```text
repo: unsloth/gemma-4-12b-it-GGUF
file: gemma-4-12b-it-UD-Q4_K_XL.gguf
target: /models/model.gguf
```

You can confirm the volume contents:

```bash
modal volume ls voice-notes-shop-ledger-models
```

Expected files include:

```text
model.gguf
gemma-4-12b-it-UD-Q4_K_XL.gguf
```

## Deploy

Stop the currently deployed app when you want a clean redeploy:

```bash
modal app stop voice-notes-shop-ledger
```

Deploy the app:

```bash
modal deploy modal_app.py
```

Modal prints the live `.modal.run` URL after deployment.

## Smoke Test

Run the Modal smoke test:

```bash
modal run modal_app.py::smoke
```

A healthy run should print a result shaped like:

```text
{
  "model_used": "model.gguf",
  "entry_count": 2,
  "amounts": [1200.0, 750.0],
  "questions": [],
  "gpu_type": "A10"
}
```

If `model_used` starts with `heuristic fallback`, the app is not using the
llama.cpp model for that request. Check the `questions` field; fallback errors
are deliberately surfaced there.

## Logs

View app logs:

```bash
modal app logs voice-notes-shop-ledger
```

Useful signals:

- `llama_context` lines mean llama.cpp loaded the GGUF.
- `model_used: model.gguf` in smoke output means model extraction succeeded.
- `heuristic fallback (missing GGUF model)` means the volume does not contain
  `/models/model.gguf`.
- `heuristic fallback (ValidationError)` usually means the model returned JSON
  that did not match the schema.

## Local Development

Run without a model:

```bash
python app.py
```

This uses heuristic mode by default. It is useful for UI work and tests.

Run locally with a GGUF:

```bash
export LEDGER_MODEL_MODE=llama
export LLAMA_GGUF_PATH=/path/to/gemma-4-12b-it-UD-Q4_K_XL.gguf
export LLAMA_N_GPU_LAYERS=0
python app.py
```

On a laptop without GPU-compatible llama.cpp, keep `LLAMA_N_GPU_LAYERS=0`.

## Environment Variables

| Variable | Used by | Default on Modal | Purpose |
| --- | --- | --- | --- |
| `LEDGER_MODEL_MODE` | `LedgerProcessor` | `llama` | Selects `llama` or `mock` mode. |
| `LLAMA_GGUF_PATH` | `LlamaLedgerBackend` | `/models/model.gguf` | Path to the model file. |
| `LLAMA_N_GPU_LAYERS` | `LlamaLedgerBackend` | `-1` | Number of layers to offload to GPU. |
| `LLAMA_N_CTX` | `LlamaLedgerBackend` | `2048` | llama.cpp context window. |
| `WHISPER_MODEL_SIZE` | `transcribe_audio` | `tiny` | Local faster-whisper model size for voice notes. |

## Operational Notes

- The app intentionally does not call cloud LLM APIs.
- Modal is infrastructure only; inference happens inside the deployed
  llama.cpp worker.
- The `A10` worker may cold-start. The UI can load before the first model
  request finishes.
- The Gradio web function uses `max_containers=1` so the UI state and queue are
  easier to reason about during the demo.
- The model volume is persistent. Redeploying the app does not redownload the
  GGUF unless you run `download_model` again.

## Troubleshooting

### The app says heuristics were used

Run:

```bash
modal run modal_app.py::smoke
```

Then check:

- Is `model_used` equal to `model.gguf`?
- Does `modal volume ls voice-notes-shop-ledger-models` show `model.gguf`?
- Does the printed `questions` list include a schema or validation error?

### CPU inference is too slow

Make sure the deployed code has:

```python
gpu="A10"
```

on `LedgerAgent` and `smoke_test_model`, plus:

```text
LLAMA_N_GPU_LAYERS=-1
```

### CUDA wheel crashes

The deployed version currently uses the prebuilt CUDA `llama-cpp-python` wheel
from:

```text
https://abetlen.github.io/llama-cpp-python/whl/cu125
```

If that wheel becomes incompatible, the fallback plan is:

1. Try a different CUDA wheel index supported by `llama-cpp-python`.
2. Build from source inside an image with the CUDA driver stub library available
   at link time.
3. Temporarily use CPU mode only for UI demos while debugging.

## Hackathon Submission Checklist

- Live Modal URL works.
- GitHub repo is public.
- Demo video shows text or voice note -> ledger -> dashboard -> automation
  queue -> CSV export.
- Submission mentions:
  - Gemma 4 12B parameter count.
  - GGUF quantization.
  - llama.cpp runtime.
  - No external LLM API.
  - Modal GPU deployment.
