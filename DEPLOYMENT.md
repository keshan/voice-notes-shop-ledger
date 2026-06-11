# Deploying To Modal

This project serves a Gradio app through a Modal ASGI web endpoint. Modal keeps
the UI server separate from the model container so the llama.cpp model can stay
loaded between requests when the container is warm.

## 1. Authenticate Modal

```bash
pip install modal
modal setup
```

## 2. Choose A GGUF Model

Use a GGUF quantization of a <=32B model. For the hackathon target, use a Gemma
12B-class instruction model when a suitable GGUF is available.

The app does not hard-code a community quant because filenames change often.
Pass your chosen repo and filename when downloading:

```bash
modal run modal_app.py::download_model \
  --repo-id YOUR_GGUF_REPO \
  --filename YOUR_MODEL_FILE.gguf
```

Examples of the shape you want:

```text
repo-id:  your-name/gemma-4-12B-it-GGUF
filename: gemma-4-12B-it-Q4_K_M.gguf
```

If you are iterating before the GGUF is ready, skip the download and deploy in
mock mode. The UI and ledger workflow will still run.

## 3. Deploy The App

```bash
modal deploy modal_app.py
```

Modal will print a `.modal.run` URL for the Gradio app.

## 4. Runtime Configuration

`modal_app.py` sets `LEDGER_MODEL_MODE=llama` for the model container. If no GGUF
file is present in the Modal volume, the processor falls back to deterministic
heuristics so the demo remains usable.

To force mock mode for a quick UI-only deployment, edit `LEDGER_MODEL_MODE` in
`modal_app.py` or set the Modal app environment accordingly.

## 5. Notes For The Hackathon

- Keep the demo video focused on a real user's note becoming a ledger row.
- Mention the GGUF model name, parameter count, and quantization in the README
  or submission.
- Include the Modal URL for judges and a Hugging Face model/repo link for the
  model artifact if you publish a fine-tuned or quantized variant.
