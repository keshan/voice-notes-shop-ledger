from __future__ import annotations

import csv
import tempfile
from collections.abc import Callable
from typing import Any

import gradio as gr
import pandas as pd

from shop_ledger.processor import LedgerProcessor, transcribe_audio


ProcessFn = Callable[[str, str], dict[str, Any]]

COLUMNS = [
    "date",
    "direction",
    "counterparty",
    "item",
    "quantity",
    "amount",
    "currency",
    "category",
    "payment_status",
    "due_date",
    "confidence",
    "reminder",
]

EXAMPLES = [
    "paid Ravi 1200 for rice bags, customer Nimal owes 750 for tea packets, remind me Friday",
    "bought milk packets 3600 cash from Sunil. sold biscuits 950 to school canteen",
    "electric bill 8400 due next Monday, paid helper Kamal 2500 salary",
]

CSS = """
:root {
  --ledger-bg: #090b0f;
  --ledger-panel: #10151d;
  --ledger-panel-2: #151b25;
  --ledger-line: rgba(157, 177, 154, 0.22);
  --ledger-ink: #f3f4ec;
  --ledger-muted: #a8b3a5;
  --ledger-green: #8bdc8b;
  --ledger-gold: #e6b450;
  --ledger-red: #ff7a68;
  --ledger-blue: #8ab4ff;
}

.gradio-container {
  background:
    radial-gradient(circle at 18% 0%, rgba(139, 220, 139, 0.16), transparent 28%),
    linear-gradient(180deg, #090b0f 0%, #11171f 54%, #0c1015 100%);
  color: var(--ledger-ink) !important;
}

.gradio-container .block,
.gradio-container .form,
.gradio-container .panel {
  background: var(--ledger-panel) !important;
  border-color: var(--ledger-line) !important;
}

.gradio-container textarea,
.gradio-container input,
.gradio-container select {
  background: #0b1017 !important;
  color: var(--ledger-ink) !important;
  border-color: var(--ledger-line) !important;
}

.gradio-container label,
.gradio-container .wrap,
.gradio-container .prose,
.gradio-container p,
.gradio-container span {
  color: var(--ledger-ink);
}

#hero {
  padding: 22px 0 8px;
}

#hero h1 {
  font-size: 38px;
  line-height: 1.08;
  margin-bottom: 8px;
  color: var(--ledger-ink);
}

#hero p {
  color: var(--ledger-muted);
  font-size: 16px;
  max-width: 760px;
}

#status-strip {
  border: 1px solid var(--ledger-line);
  background: rgba(16, 21, 29, 0.8);
  border-radius: 8px;
  padding: 8px 12px;
}

#input-dock,
#output-dock {
  border: 1px solid var(--ledger-line);
  background: rgba(16, 21, 29, 0.86);
  border-radius: 8px;
  padding: 14px;
}

#input-notice {
  min-height: 42px;
  border-left: 4px solid var(--ledger-gold);
  background: rgba(230, 180, 80, 0.1);
  border-radius: 6px;
  padding: 10px 12px;
}

.summary-card {
  border-left: 4px solid var(--ledger-green);
  background: rgba(139, 220, 139, 0.08);
  border-radius: 6px;
  padding: 12px;
}

.reminder-card {
  border-left: 4px solid var(--ledger-blue);
  background: rgba(138, 180, 255, 0.08);
  border-radius: 6px;
  padding: 12px;
}

button.primary {
  border-radius: 8px !important;
  background: linear-gradient(180deg, #92e693 0%, #5fbf73 100%) !important;
  color: #07100b !important;
  border: 0 !important;
  font-weight: 700 !important;
}

#ledger-table {
  border: 1px solid var(--ledger-line);
  border-radius: 8px;
}

#download-box {
  min-height: 70px;
}
"""


def build_demo(process_fn: ProcessFn | None = None) -> gr.Blocks:
    processor = LedgerProcessor.from_env()

    def local_process(note: str, currency: str) -> dict[str, Any]:
        return processor.process(note, currency=currency).model_dump(mode="json")

    active_process = process_fn or local_process

    with gr.Blocks(
        css=CSS,
        title="Voice Notes to Shop Ledger",
        theme=gr.themes.Soft(primary_hue="green", secondary_hue="amber", neutral_hue="slate"),
    ) as demo:
        ledger_state = gr.State([])

        gr.Markdown(
            """
            # Voice Notes to Shop Ledger
            A midnight ledger desk for turning rough shop notes into rows, totals, and follow-ups.
            """,
            elem_id="hero",
        )

        with gr.Row(elem_id="status-strip"):
            model_badge = gr.Markdown("Model: not run yet")
            row_count = gr.Markdown("Rows: 0")

        with gr.Row():
            with gr.Column(scale=5, elem_id="input-dock"):
                note_box = gr.Textbox(
                    label="Written note",
                    placeholder="paid Ravi 1200 for rice bags, customer Nimal owes 750 for tea packets",
                    lines=6,
                )
                audio_box = gr.Audio(label="Voice note", sources=["microphone", "upload"], type="filepath")
                input_choice = gr.Radio(
                    label="Input to analyze",
                    choices=["Auto", "Text note", "Voice note"],
                    value="Auto",
                    interactive=True,
                )
                input_notice = gr.Markdown("Ready for one note.", elem_id="input-notice")
                with gr.Row():
                    currency = gr.Dropdown(
                        label="Currency",
                        choices=["LKR", "USD", "INR", "GBP", "EUR"],
                        value="LKR",
                        allow_custom_value=True,
                    )
                    add_button = gr.Button("Add to ledger", variant="primary")
                    clear_button = gr.Button("Clear")
            with gr.Column(scale=4, elem_id="output-dock"):
                summary = gr.Markdown("No ledger rows yet.", elem_classes=["summary-card"])
                reminders = gr.Markdown("No reminders yet.", elem_classes=["reminder-card"])

        ledger = gr.Dataframe(
            headers=COLUMNS,
            datatype=["str"] * len(COLUMNS),
            label="Ledger",
            interactive=False,
            wrap=True,
            elem_id="ledger-table",
        )
        download = gr.File(label="Download CSV", elem_id="download-box")

        gr.Examples(
            examples=EXAMPLES,
            inputs=note_box,
            label="Try a messy shop note",
        )

        add_button.click(
            fn=lambda note, audio, source_choice, currency_value, state: add_to_ledger(
                note,
                audio,
                source_choice,
                currency_value,
                state,
                active_process,
            ),
            inputs=[note_box, audio_box, input_choice, currency, ledger_state],
            outputs=[
                ledger,
                summary,
                reminders,
                model_badge,
                row_count,
                download,
                ledger_state,
                note_box,
                audio_box,
                input_choice,
                input_notice,
            ],
        )
        clear_button.click(
            fn=clear_ledger,
            outputs=[
                ledger,
                summary,
                reminders,
                model_badge,
                row_count,
                download,
                ledger_state,
                note_box,
                audio_box,
                input_choice,
                input_notice,
            ],
        )

    return demo


def add_to_ledger(
    note: str,
    audio_path: str | None,
    source_choice: str,
    currency: str,
    state: list[dict[str, Any]] | None,
    process_fn: ProcessFn,
) -> tuple[
    pd.DataFrame,
    str,
    str,
    str,
    str,
    str | None,
    list[dict[str, Any]],
    Any,
    Any,
    Any,
    str,
]:
    rows = state or []
    choice = choose_input(note, audio_path, source_choice)
    if choice["status"] != "ready":
        frame = pd.DataFrame(rows, columns=COLUMNS)
        return (
            frame,
            build_summary(rows, {}),
            build_reminders(rows, {}),
            "Model: waiting for input",
            f"Rows: {len(rows)}",
            write_csv(rows) if rows else None,
            rows,
            gr.update(),
            gr.update(),
            gr.update(),
            choice["notice"],
        )

    if choice["source"] == "audio":
        combined_note = transcribe_audio(audio_path)
        if not combined_note:
            frame = pd.DataFrame(rows, columns=COLUMNS)
            return (
                frame,
                build_summary(rows, {}),
                build_reminders(rows, {}),
                "Model: waiting for audio transcript",
                f"Rows: {len(rows)}",
                write_csv(rows) if rows else None,
                rows,
                gr.update(),
                gr.update(),
                gr.update(value="Voice note"),
                "I could not transcribe that voice note. Try another recording or paste the note.",
            )
    else:
        combined_note = (note or "").strip()

    result = process_fn(combined_note, currency or "LKR")
    rows = rows + compact_rows(result.get("entries", []))

    frame = pd.DataFrame(rows, columns=COLUMNS)
    summary = build_summary(rows, result)
    reminder_text = build_reminders(rows, result)
    csv_path = write_csv(rows) if rows else None
    model = result.get("model_used", "unknown")
    notice = f"Added {len(result.get('entries', []))} row(s) from the {choice['label'].lower()}."
    next_note = gr.update(value="") if choice["source"] == "text" else gr.update()
    next_audio = gr.update(value=None) if choice["source"] == "audio" else gr.update()

    return (
        frame,
        summary,
        reminder_text,
        f"Model: `{model}`",
        f"Rows: {len(rows)}",
        csv_path,
        rows,
        next_note,
        next_audio,
        gr.update(value="Auto"),
        notice,
    )


def choose_input(note: str | None, audio_path: str | None, source_choice: str | None) -> dict[str, str]:
    has_text = bool((note or "").strip())
    has_audio = bool(audio_path)
    choice = source_choice or "Auto"

    if has_text and has_audio and choice == "Auto":
        return {
            "status": "conflict",
            "notice": "Both a written note and a voice note are present. Choose Text note or Voice note, then add it to the ledger.",
        }
    if choice == "Text note" and not has_text:
        return {"status": "missing", "notice": "Text note is selected, but the written note is empty."}
    if choice == "Voice note" and not has_audio:
        return {"status": "missing", "notice": "Voice note is selected, but no audio is attached."}
    if not has_text and not has_audio:
        return {"status": "missing", "notice": "Add a written note or record a voice note first."}
    if choice == "Voice note" or (choice == "Auto" and has_audio):
        return {"status": "ready", "source": "audio", "label": "Voice note"}
    return {"status": "ready", "source": "text", "label": "Text note"}


def compact_rows(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for entry in entries:
        row = {column: entry.get(column, "") for column in COLUMNS}
        row["amount"] = float(row["amount"] or 0)
        row["confidence"] = round(float(row["confidence"] or 0), 2)
        rows.append(row)
    return rows


def build_summary(rows: list[dict[str, Any]], result: dict[str, Any]) -> str:
    if not rows:
        return "No ledger rows yet."

    expenses = sum_amount(rows, "expense", "paid")
    income = sum_amount(rows, "income", "paid")
    due = sum(float(row.get("amount") or 0) for row in rows if row.get("payment_status") == "due")
    categories = category_totals(rows)
    category_text = ", ".join(f"{name}: {amount:,.0f}" for name, amount in categories[:4])
    questions = result.get("questions") or []
    question_text = "\n".join(f"- {question}" for question in questions)

    summary = (
        f"### Totals\n"
        f"- Expenses paid: **{expenses:,.0f}**\n"
        f"- Income received: **{income:,.0f}**\n"
        f"- Still due: **{due:,.0f}**\n"
    )
    if category_text:
        summary += f"- Top categories: {category_text}\n"
    if question_text:
        summary += f"\n### Check With User\n{question_text}\n"
    return summary


def build_reminders(rows: list[dict[str, Any]], result: dict[str, Any]) -> str:
    reminders = list(result.get("reminders") or [])
    reminders.extend(row["reminder"] for row in rows if row.get("reminder"))
    unique = []
    for reminder in reminders:
        if reminder and reminder not in unique:
            unique.append(reminder)
    if not unique:
        return "No reminders yet."
    return "### Follow-ups\n" + "\n".join(f"- {reminder}" for reminder in unique[:8])


def sum_amount(rows: list[dict[str, Any]], direction: str, status: str) -> float:
    return sum(
        float(row.get("amount") or 0)
        for row in rows
        if row.get("direction") == direction and row.get("payment_status") == status
    )


def category_totals(rows: list[dict[str, Any]]) -> list[tuple[str, float]]:
    totals: dict[str, float] = {}
    for row in rows:
        category = row.get("category") or "uncategorized"
        totals[category] = totals.get(category, 0.0) + float(row.get("amount") or 0)
    return sorted(totals.items(), key=lambda item: item[1], reverse=True)


def write_csv(rows: list[dict[str, Any]]) -> str:
    handle = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, newline="")
    with handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return handle.name


def clear_ledger() -> tuple[
    pd.DataFrame,
    str,
    str,
    str,
    str,
    None,
    list[dict[str, Any]],
    str,
    None,
    str,
    str,
]:
    return (
        pd.DataFrame([], columns=COLUMNS),
        "No ledger rows yet.",
        "No reminders yet.",
        "Model: not run yet",
        "Rows: 0",
        None,
        [],
        "",
        None,
        "Auto",
        "Ready for one note.",
    )
