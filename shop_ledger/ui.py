from __future__ import annotations

import csv
import tempfile
from collections.abc import Callable
from pathlib import Path
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
  --ledger-ink: #1f2933;
  --ledger-muted: #697386;
  --ledger-paper: #fffaf0;
  --ledger-green: #2f6f4e;
  --ledger-gold: #c9892b;
  --ledger-red: #a84632;
}

.gradio-container {
  background: linear-gradient(180deg, #f7f2e8 0%, #eef4ed 100%);
  color: var(--ledger-ink);
}

#hero {
  padding: 18px 0 4px;
}

#hero h1 {
  font-size: 34px;
  line-height: 1.08;
  margin-bottom: 8px;
}

#hero p {
  color: var(--ledger-muted);
  font-size: 16px;
  max-width: 760px;
}

#status-strip {
  border: 1px solid rgba(47, 111, 78, 0.22);
  background: rgba(255, 250, 240, 0.72);
  border-radius: 8px;
  padding: 10px 12px;
}

.summary-card {
  border-left: 4px solid var(--ledger-green);
}

button.primary {
  border-radius: 8px !important;
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
            Turn messy shop notes into ledger rows, totals, and reminders.
            """,
            elem_id="hero",
        )

        with gr.Row(elem_id="status-strip"):
            model_badge = gr.Markdown("Model: not run yet")
            row_count = gr.Markdown("Rows: 0")

        with gr.Row():
            with gr.Column(scale=5):
                note_box = gr.Textbox(
                    label="Paste a note",
                    placeholder="paid Ravi 1200 for rice bags, customer Nimal owes 750 for tea packets",
                    lines=6,
                )
                audio_box = gr.Audio(label="Or record/upload a voice note", sources=["microphone", "upload"], type="filepath")
                with gr.Row():
                    currency = gr.Dropdown(
                        label="Currency",
                        choices=["LKR", "USD", "INR", "GBP", "EUR"],
                        value="LKR",
                        allow_custom_value=True,
                    )
                    add_button = gr.Button("Add to ledger", variant="primary")
                    clear_button = gr.Button("Clear")
            with gr.Column(scale=4):
                summary = gr.Markdown("No ledger rows yet.", elem_classes=["summary-card"])
                reminders = gr.Markdown("No reminders yet.")

        ledger = gr.Dataframe(
            headers=COLUMNS,
            datatype=["str"] * len(COLUMNS),
            label="Ledger",
            interactive=False,
            wrap=True,
        )
        download = gr.File(label="Download CSV")

        gr.Examples(
            examples=EXAMPLES,
            inputs=note_box,
            label="Try a messy shop note",
        )

        add_button.click(
            fn=lambda note, audio, currency_value, state: add_to_ledger(
                note,
                audio,
                currency_value,
                state,
                active_process,
            ),
            inputs=[note_box, audio_box, currency, ledger_state],
            outputs=[ledger, summary, reminders, model_badge, row_count, download, ledger_state],
        )
        clear_button.click(
            fn=clear_ledger,
            outputs=[ledger, summary, reminders, model_badge, row_count, download, ledger_state],
        )

    return demo


def add_to_ledger(
    note: str,
    audio_path: str | None,
    currency: str,
    state: list[dict[str, Any]] | None,
    process_fn: ProcessFn,
) -> tuple[pd.DataFrame, str, str, str, str, str | None, list[dict[str, Any]]]:
    combined_note = note.strip() if note else ""
    transcript = transcribe_audio(audio_path)
    if transcript:
        combined_note = f"{combined_note}\n{transcript}".strip()

    result = process_fn(combined_note, currency or "LKR")
    rows = state or []
    rows = rows + compact_rows(result.get("entries", []))

    frame = pd.DataFrame(rows, columns=COLUMNS)
    summary = build_summary(rows, result)
    reminder_text = build_reminders(rows, result)
    csv_path = write_csv(rows) if rows else None
    model = result.get("model_used", "unknown")

    return (
        frame,
        summary,
        reminder_text,
        f"Model: `{model}`",
        f"Rows: {len(rows)}",
        csv_path,
        rows,
    )


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


def clear_ledger() -> tuple[pd.DataFrame, str, str, str, str, None, list[dict[str, Any]]]:
    return (
        pd.DataFrame([], columns=COLUMNS),
        "No ledger rows yet.",
        "No reminders yet.",
        "Model: not run yet",
        "Rows: 0",
        None,
        [],
    )
