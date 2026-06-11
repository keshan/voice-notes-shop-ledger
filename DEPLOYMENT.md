# Deploying To Modal

This project serves a Gradio app through a Modal ASGI web endpoint. Modal keeps
the UI server separate from the model container so the llama.cpp model can stay
loaded between requests when the GPU container is warm.

## 1. Authenticate Modal

```bash
pip install modal
modal setup
```

## 2. Download The GGUF Model

The default Modal download uses:

- Repo: `unsloth/gemma-4-12b-it-GGUF`
- File: `gemma-4-12b-it-UD-Q4_K_XL.gguf`

```bash
modal run modal_app.py::download_model
```

To override the model, pass a different repo and filename:

```bash
modal run modal_app.py::download_model \
  --repo-id another/repo \
  --filename another-model.gguf
```

## 3. Deploy The App

```bash
modal app stop voice-notes-shop-ledger -y
modal deploy modal_app.py
```

Modal will print a `.modal.run` URL for the Gradio app.

## 4. Runtime Configuration

`modal_app.py` sets `LEDGER_MODEL_MODE=llama`, `LLAMA_N_GPU_LAYERS=-1`, and
`LLAMA_N_CTX=2048` for the model container. The `LedgerAgent` and smoke test run
on a Modal `A10` GPU. The image uses the prebuilt CUDA `llama-cpp-python` wheel
from the project wheel index instead of compiling llama.cpp during deployment.
If no GGUF file is present in the Modal volume, the processor falls back to
deterministic heuristics so the demo remains usable.

To force mock mode for a quick UI-only deployment, edit `LEDGER_MODEL_MODE` in
`modal_app.py` or set the Modal app environment accordingly.

## 5. Notes For The Hackathon

- Keep the demo video focused on a real user's note becoming a ledger row.
- Mention the GGUF model name, parameter count, and quantization in the README
  or submission.
- Include the Modal URL for judges and a Hugging Face model/repo link for the
  model artifact if you publish a fine-tuned or quantized variant.
