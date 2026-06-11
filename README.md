# Voice Notes to Shop Ledger

A small-model Gradio app for turning messy shopkeeper notes into a clean ledger.

The app accepts pasted notes and optional voice notes, extracts expenses/income,
assigns categories, tracks due items, and drafts follow-up reminders. It is built
for the Build Small hackathon's Backyard AI trail: a specific, practical helper
for a real person who keeps money notes in scraps, voice messages, or memory.

## Why This Fits The Brief

- **Specific problem:** small shop owners and parents often record purchases,
  credit, supplier payments, and customer dues in unstructured notes.
- **Small-model fit:** extraction, categorization, and reminder drafting fit well
  inside a 12B-class instruction model.
- **No cloud inference APIs:** the language model runs through `llama.cpp` via
  `llama-cpp-python`.
- **Gradio canvas:** the whole interface is a Gradio app.
- **Modal deployment:** `modal_app.py` serves the Gradio UI as a Modal web app.

## Features

- Paste messy notes such as `paid Ravi 1200 for rice bags, remind me Friday`.
- Record or upload a voice note; optional local Whisper transcription handles it.
- Extract structured ledger rows with amount, party, item, category, status, and
  confidence.
- See totals by expense/income/due and category.
- Generate follow-up reminders for unpaid or ambiguous items.
- Export the ledger as CSV.
- Run with a heuristic dev fallback before downloading a large GGUF model.

## Project Layout

```text
app.py                 Local Gradio entrypoint
modal_app.py           Modal deployment entrypoint
shop_ledger/           App logic, UI, model backends
tests/                 Unit tests for parsing and processing
FIELD_NOTES.md         Hackathon report starter
DEPLOYMENT.md          Modal deployment notes
```

## Local Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

By default the app runs in `mock` mode. Set `LEDGER_MODEL_MODE=llama` and point
`LLAMA_GGUF_PATH` at a local GGUF file to use llama.cpp:

```bash
export LEDGER_MODEL_MODE=llama
export LLAMA_GGUF_PATH=/path/to/gemma-4-12b-it-q4_k_m.gguf
python app.py
```

## Modal Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md).

Short version:

```bash
pip install modal
modal setup
modal run modal_app.py::download_model \
  --repo-id YOUR_GGUF_REPO \
  --filename YOUR_MODEL_FILE.gguf
modal deploy modal_app.py
```

The app reads these environment variables:

| Variable | Purpose |
| --- | --- |
| `LEDGER_MODEL_MODE` | `mock` or `llama` |
| `LLAMA_GGUF_PATH` | Local path to a GGUF model |
| `GGUF_MODEL_REPO` | Hugging Face repo for Modal model download |
| `GGUF_MODEL_FILE` | GGUF filename inside that repo |
| `WHISPER_MODEL_SIZE` | Optional faster-whisper model size, defaults to `tiny` |

## Model Notes

The intended model family is a Gemma 12B-class instruction model quantized as
GGUF and run through llama.cpp. If using Gemma 4 12B, choose or publish a GGUF
quantization such as Q4_K_M/Q5_K_M and set `GGUF_MODEL_REPO` and
`GGUF_MODEL_FILE` accordingly.

The implementation deliberately avoids external LLM APIs so the demo can earn
the local-first/off-grid spirit of the hackathon. Modal is used for deployment,
not as a hosted inference API.
