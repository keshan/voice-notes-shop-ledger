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
- **Modal GPU deployment:** `modal_app.py` serves the Gradio UI and runs
  llama.cpp inference on a Modal `A10` GPU worker.

## Features

- Paste messy notes such as `paid Ravi 1200 for rice bags, remind me Friday`.
- Record or upload a voice note; optional local Whisper transcription handles it.
- Upload receipts, bills, note photos, or PDFs; PDFs are rendered to page
  images and Gemma reads the visual document content through llama.cpp.
- Extract structured ledger rows with amount, party, item, category, status, and
  confidence.
- See a live dashboard for net cash, cash in, cash out, due amount, follow-ups,
  and average extraction confidence.
- Let the app pick an insight graph based on the ledger state: unpaid dues,
  expense pressure, cashflow over time, confidence review, or category mix.
- Generate a Gemma-powered "today's shop pulse" from the structured ledger rows.
- Ask local ledger questions such as "Who owes me most?", "What should I follow
  up today?", and "Where did cash go?"
- Review field intelligence: top category, most active party, biggest entry,
  watch-list risks, and a daily field note.
- Use the automation queue to turn due items into follow-up actions, reminder
  cadence, and ready-to-send polite, friendly, or firm message scripts.
- Review low-confidence or incomplete rows in a dedicated Review Desk before
  exporting the CSV.
- Export the ledger as CSV.
- Run with a heuristic dev fallback before downloading a large GGUF model.

## Project Layout

```text
app.py                 Local Gradio entrypoint
modal_app.py           Modal deployment entrypoint
shop_ledger/           App logic, UI, model backends
tests/                 Unit tests for parsing and processing
ARCHITECTURE.md        System architecture and data flow
ROADMAP.md             Future feature ideas and next sprint options
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
export LLAMA_GGUF_PATH=/path/to/gemma-4-12b-it-UD-Q4_K_XL.gguf
python app.py
```

## Modal Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for the full Modal runbook.

Short version:

```bash
pip install modal
modal setup
modal run modal_app.py::download_model
modal deploy modal_app.py
```

The production Modal deployment uses a GPU worker for llama.cpp inference:

- GPU: Modal `A10`
- Runtime: `llama-cpp-python` CUDA wheel
- Model: `unsloth/gemma-4-12b-it-GGUF`
- Quant: `gemma-4-12b-it-UD-Q4_K_XL.gguf`

Smoke test the GPU model path:

```bash
modal run modal_app.py::smoke
```

Expected signal:

```text
model_used: model.gguf
gpu_type: A10
```

The app reads these environment variables:

| Variable | Purpose |
| --- | --- |
| `LEDGER_MODEL_MODE` | `mock` or `llama` |
| `LLAMA_GGUF_PATH` | Local path to a GGUF model |
| `LLAMA_N_GPU_LAYERS` | Number of llama.cpp layers to offload, `-1` on Modal |
| `LLAMA_N_CTX` | llama.cpp context window, `2048` on Modal |
| `WHISPER_MODEL_SIZE` | Optional faster-whisper model size, defaults to `tiny` |

The Gradio dashboard uses Plotly figures, so Modal installs `plotly>=6.0,<7`
inside the same image as the UI.

Document upload stays off-grid too: PDFs are rendered with PyMuPDF, images are
encoded as local data URLs, and Gemma 4 12B receives them through llama.cpp's
multimodal `image_url` chat message format.

## Model Notes

The configured Modal model is
[`unsloth/gemma-4-12b-it-GGUF`](https://huggingface.co/unsloth/gemma-4-12b-it-GGUF)
with `gemma-4-12b-it-UD-Q4_K_XL.gguf`. The model card lists Gemma 4 12B
Unified at 11.95B parameters, which is inside the hackathon's <=32B constraint.

The implementation deliberately avoids external LLM APIs so the demo can earn
the local-first/off-grid spirit of the hackathon. Modal is used for deployment,
not as a hosted inference API.

## Demo Flow

1. Add a messy text or voice note.
2. Upload a receipt/photo/PDF and show it entering the same ledger flow.
3. Open the dashboard and point to net cash, due amount, the chosen graph, and
   the generated daily brief.
4. Ask "Who owes me most?" and show the structured answer.
5. Open the automation queue and choose a polite, friendly, or firm follow-up
   script.
6. Open the Review Desk to show how uncertain rows are handled.
7. Export the CSV.

## More Docs

- [Architecture](ARCHITECTURE.md): code map, data flow, model contract,
  fallback behavior, and testing strategy.
- [Deployment](DEPLOYMENT.md): Modal GPU deployment, model volume, smoke tests,
  logs, and troubleshooting.
- [Roadmap](ROADMAP.md): dynamic graphs, modern dashboard layout, daily briefs,
  review mode, counterparty cards, and other future ideas.
- [Field Notes](FIELD_NOTES.md): hackathon report starter and demo beats.
