# Architecture

Voice Notes to Shop Ledger is a small-model Gradio app that turns messy shop
notes into structured ledger rows, insights, and follow-up actions.

## System Overview

```text
User text/audio/document
    |
    v
Gradio UI (`shop_ledger/ui.py`)
    |
    +--> local mode: `LedgerProcessor`
    |
    +--> Modal mode: `LedgerAgent().process.remote(...)`
              |
              v
       `LedgerProcessor`
              |
              +--> llama.cpp backend (`LlamaLedgerBackend`)
              |
              +--> heuristic fallback
              |
              v
       `LedgerResult`
              |
              v
Dashboard, ledger table, automation queue, CSV export
```

## Code Map

| File | Responsibility |
| --- | --- |
| `app.py` | Local Gradio entrypoint. |
| `modal_app.py` | Modal image, volume, GPU worker, ASGI app, model download, smoke tests. |
| `shop_ledger/ui.py` | Gradio Blocks UI, input selection, callbacks, CSV export. |
| `shop_ledger/schema.py` | Pydantic models for ledger entries and model results. |
| `shop_ledger/llama_backend.py` | llama.cpp prompt, model loading, JSON parsing. |
| `shop_ledger/processor.py` | Runtime mode selection and fallback handling. |
| `shop_ledger/heuristics.py` | Deterministic parser for mock/dev/fallback mode. |
| `shop_ledger/insights.py` | Dashboard metrics, risk flags, follow-up queue, breakdown tables. |
| `tests/` | Unit tests for extraction, processor fallback, input-choice behavior, and insights. |

## Data Flow

1. The user enters a written note, records/uploads a voice note, or uploads a
   receipt/bill image or PDF.
2. If multiple inputs are present and `Auto` is selected, the UI asks the user
   to choose which input to analyze.
3. Audio input is transcribed locally with `faster-whisper` when available.
4. Documents are prepared locally: PDFs are rendered into page images with
   PyMuPDF, uploaded images are resized with Pillow, and both become base64
   data URLs.
5. The chosen note text is sent to `LedgerProcessor`.
6. In Modal production, `LedgerProcessor` uses `LlamaLedgerBackend`.
7. `LlamaLedgerBackend` asks Gemma through llama.cpp to return strict JSON,
   using multimodal `image_url` message parts when document images are present.
8. The result is validated by `LedgerResult` and `LedgerEntry`.
9. Rows are appended to Gradio state.
10. The app recomputes:
   - ledger table
   - dashboard metrics
   - field intelligence
   - dynamic insight graph plan
   - daily shop-pulse brief
   - Plotly insight figures
   - automation queue
   - review queue
   - category and party tables
   - CSV export
11. The analyzed input is cleared so the next note starts cleanly.

## Model Contract

The model must return JSON shaped like:

```json
{
  "entries": [
    {
      "date": "YYYY-MM-DD or empty",
      "direction": "expense|income|transfer|unknown",
      "counterparty": "person or business",
      "item": "what changed hands",
      "quantity": "quantity if known",
      "amount": 0,
      "currency": "LKR",
      "category": "inventory|utilities|rent|wages|transport|maintenance|sales|general expense|uncategorized",
      "payment_status": "paid|due|partial|unknown",
      "due_date": "",
      "reminder": "short follow-up reminder or empty",
      "confidence": 0.0,
      "original_note": "source fragment"
    }
  ],
  "reminders": ["short reminders"],
  "questions": ["only ask if an amount, person, or due date is unclear"],
  "cleaned_note": "normalized note"
}
```

The schema intentionally tolerates `null` for text fields by converting it to an
empty string. This prevents valid model intent from failing because of minor
JSON style differences.

## Fallback Design

The app keeps a deterministic heuristic parser for three reasons:

1. Local UI development should work without downloading a 12B model.
2. The live demo should never go completely blank if model loading fails.
3. Tests can verify app behavior quickly.

Fallback is visible. If llama.cpp fails, `model_used` becomes something like:

```text
heuristic fallback (ValidationError)
```

The exception details are added to `questions` so the UI and smoke tests expose
the reason.

## Insights Engine

`shop_ledger/insights.py` is pure Python and deterministic. It computes:

- net cash
- paid income
- paid expenses
- due income
- due expenses
- open follow-ups
- average extraction confidence
- top categories
- top parties
- high-value due risk flags
- low-confidence risk flags
- chart plan selection
- daily brief generation with Gemma or local fallback
- Plotly figures for due radar, spend pressure, cashflow, confidence review,
  category mix, and party exposure
- follow-up queue with cadence and scripts
- reply studio variants for polite, friendly, and firm reminders
- review queue for low-confidence or incomplete rows
- daily field note

The chart planner is deterministic first. It asks what matters most right now:
unpaid money, expense pressure, cashflow timeline, review risk, or overall
category mix. Keeping insights separate from the Gradio UI makes the dashboard
testable and leaves room for a later local-LLM chart selector.

## UI Structure

The UI is a dark, custom-styled Gradio Blocks app.

Top area:

- written note
- voice note
- document upload
- input selector
- currency
- add/clear actions
- model and row status

Tabs:

- `Dashboard`: KPIs, chart director, dynamic Plotly graphs, field
  intelligence, Gemma daily brief, category and party breakdowns.
- `Automation Queue`: follow-up actions, reminder cadence, and reply studio
  message variants.
- `Review Desk`: low-confidence or incomplete rows with targeted correction
  questions.
- `Ledger`: raw ledger rows and CSV export.

## Modal Production Path

The live Modal path is:

```text
fastapi_app
  -> build_demo(process_fn=process_remote)
  -> LedgerAgent().process.remote(note, currency)
  -> LedgerProcessor.from_env()
  -> LlamaLedgerBackend(...)
  -> llama_cpp.Llama.create_chat_completion(...)
```

The model worker is configured with:

```text
gpu=A10
cpu=8
memory=32768
timeout=1800
LLAMA_N_GPU_LAYERS=-1
LLAMA_N_CTX=2048
```

## Testing Strategy

Current tests cover:

- heuristic parsing
- processor fallback behavior
- text/audio input-choice rules
- field-clearing callback behavior
- dashboard metrics
- chart-plan selection
- Plotly figure generation
- follow-up queue priority
- reply studio message variants
- review queue generation
- risk flags

Run:

```bash
python3 -m unittest discover -s tests
python3 -m compileall shop_ledger app.py modal_app.py tests
```

## Known Constraints

- Gradio state is session-local. This is enough for the hackathon demo but not a
  multi-user accounting product.
- CSV export is generated per session.
- Voice transcription uses local `faster-whisper` only when available.
- The app is not a replacement for accounting, tax, legal, or financial advice.
- The app should not store sensitive customer data without adding auth and
  persistence controls.
