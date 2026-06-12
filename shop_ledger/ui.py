from __future__ import annotations

import csv
import tempfile
from collections.abc import Callable
from typing import Any

import gradio as gr
import pandas as pd

from shop_ledger.insights import (
    build_chart_markdown,
    build_counterparty_memory_markdown,
    build_dashboard_markdown,
    build_daily_brief_markdown,
    build_insight_figures,
    build_insights_markdown,
    build_reminder_markdown,
    build_review_markdown,
    build_timeline_markdown,
    build_tables,
    counterparty_memory_cards,
    timeline_figure,
    timeline_rows,
)
from shop_ledger.processor import LedgerProcessor, prepare_document_input, transcribe_audio


ProcessFn = Callable[[str, str, list[str] | None], dict[str, Any]]
DailyBriefFn = Callable[[list[dict[str, Any]], str], dict[str, str]]
AskLedgerFn = Callable[[list[dict[str, Any]], str, str], dict[str, str]]
ChatHistory = list[dict[str, str]]

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

#status-strip .prose {
  margin: 0;
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

.metric-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin-top: 10px;
}

.metric-card {
  background: rgba(8, 12, 18, 0.88);
  border: 1px solid var(--ledger-line);
  border-radius: 8px;
  padding: 14px;
}

.metric-card span {
  display: block;
  color: var(--ledger-muted) !important;
  font-size: 12px;
  text-transform: uppercase;
}

.metric-card strong {
  display: block;
  color: var(--ledger-green);
  font-size: 22px;
  margin-top: 6px;
}

.dashboard-grid {
  display: grid;
  grid-template-columns: minmax(300px, 0.9fr) minmax(520px, 1.7fr);
  gap: 12px;
  align-items: start;
}

.ops-stack {
  display: grid;
  gap: 12px;
}

.ops-card,
.chat-panel {
  border: 1px solid var(--ledger-line);
  background: rgba(8, 12, 18, 0.88);
  border-radius: 8px;
  padding: 14px;
}

#chart-director,
#daily-brief-panel,
#ask-ledger-panel {
  min-height: 180px;
  border-left: 4px solid var(--ledger-blue);
}

#chart-wall {
  border: 1px solid var(--ledger-line);
  background:
    linear-gradient(180deg, rgba(16, 21, 29, 0.92), rgba(8, 12, 18, 0.88));
  border-radius: 8px;
  padding: 12px;
}

#chart-wall .block,
#signal-row .block {
  background: rgba(8, 12, 18, 0.34) !important;
  border-color: rgba(157, 177, 154, 0.18) !important;
  border-radius: 8px !important;
}

#signal-row {
  margin-top: 10px;
}

#ask-chat-panel {
  border-left: 4px solid var(--ledger-green);
}

#ask-chat-panel .wrap {
  background: transparent !important;
}

#ask-chatbot {
  min-height: 300px;
  border: 1px solid rgba(157, 177, 154, 0.18);
  border-radius: 8px;
  background: rgba(6, 10, 15, 0.72);
}

#ask-chatbot .message {
  border-radius: 8px !important;
}

#ask-chatbot .user {
  background: rgba(138, 180, 255, 0.14) !important;
  border: 1px solid rgba(138, 180, 255, 0.22) !important;
}

#ask-chatbot .bot {
  background: rgba(139, 220, 139, 0.12) !important;
  border: 1px solid rgba(139, 220, 139, 0.22) !important;
}

#ask-row {
  align-items: end;
}

.followup-card {
  background: rgba(8, 12, 18, 0.88);
  border: 1px solid var(--ledger-line);
  border-left: 4px solid var(--ledger-gold);
  border-radius: 8px;
  margin: 10px 0;
  padding: 12px;
}

.review-card {
  background: rgba(8, 12, 18, 0.88);
  border: 1px solid var(--ledger-line);
  border-left: 4px solid var(--ledger-red);
  border-radius: 8px;
  margin: 10px 0;
  padding: 12px;
}

.review-card code {
  display: block;
  white-space: normal;
  margin-top: 8px;
  color: var(--ledger-ink);
  background: rgba(255, 122, 104, 0.08);
  border: 1px solid rgba(255, 122, 104, 0.22);
  border-radius: 6px;
  padding: 8px;
}

.timeline-rail {
  border-left: 1px solid var(--ledger-line);
  margin-left: 10px;
  padding-left: 14px;
}

.timeline-card {
  background: rgba(8, 12, 18, 0.88);
  border: 1px solid var(--ledger-line);
  border-left: 4px solid var(--ledger-blue);
  border-radius: 8px;
  margin: 10px 0;
  padding: 12px;
}

.timeline-card.income {
  border-left-color: var(--ledger-green);
}

.timeline-card.expense {
  border-left-color: var(--ledger-red);
}

.timeline-card.due {
  border-left-color: var(--ledger-gold);
}

.timeline-card code {
  color: var(--ledger-muted);
  background: rgba(157, 177, 154, 0.08);
  border-radius: 6px;
  padding: 5px 7px;
}

.memory-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.memory-card {
  background: rgba(8, 12, 18, 0.88);
  border: 1px solid var(--ledger-line);
  border-left: 4px solid var(--ledger-green);
  border-radius: 8px;
  padding: 12px;
}

.memory-card.watch {
  border-left-color: var(--ledger-gold);
}

.memory-card.risk {
  border-left-color: var(--ledger-red);
}

.memory-card strong,
.memory-card span {
  display: block;
}

.memory-card span {
  color: var(--ledger-gold) !important;
  font-size: 12px;
  margin-top: 4px;
  text-transform: uppercase;
}

.memory-card code {
  display: block;
  white-space: normal;
  margin-top: 8px;
  color: var(--ledger-green);
  background: rgba(139, 220, 139, 0.08);
  border: 1px solid rgba(139, 220, 139, 0.22);
  border-radius: 6px;
  padding: 8px;
}

.followup-card code {
  display: block;
  white-space: normal;
  color: var(--ledger-green);
  background: rgba(139, 220, 139, 0.08);
  border: 1px solid rgba(139, 220, 139, 0.22);
  border-radius: 6px;
  padding: 8px;
}

.reply-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  margin-top: 10px;
}

.reply-grid code span {
  display: block;
  color: var(--ledger-gold) !important;
  font-family: inherit;
  font-size: 11px;
  font-weight: 700;
  margin-bottom: 4px;
  text-transform: uppercase;
}

#dashboard-panel,
#automation-panel,
#review-panel,
#daily-brief-panel,
#ask-ledger-panel,
#timeline-panel,
#memory-panel,
#insight-panel {
  border: 1px solid var(--ledger-line);
  background: rgba(16, 21, 29, 0.86);
  border-radius: 8px;
  padding: 14px;
}

@media (max-width: 760px) {
  .metric-grid {
    grid-template-columns: 1fr;
  }

  .dashboard-grid {
    grid-template-columns: 1fr;
  }

  .reply-grid {
    grid-template-columns: 1fr;
  }

  .memory-grid {
    grid-template-columns: 1fr;
  }
}
"""


def build_demo(
    process_fn: ProcessFn | None = None,
    daily_brief_fn: DailyBriefFn | None = None,
    ask_ledger_fn: AskLedgerFn | None = None,
) -> gr.Blocks:
    processor = LedgerProcessor.from_env()

    def local_process(note: str, currency: str, image_urls: list[str] | None = None) -> dict[str, Any]:
        return processor.process(note, currency=currency, image_urls=image_urls).model_dump(mode="json")

    active_process = process_fn or local_process

    def local_daily_brief(rows: list[dict[str, Any]], currency: str) -> dict[str, str]:
        return processor.daily_brief(rows, currency=currency)

    active_daily_brief = daily_brief_fn or local_daily_brief

    def local_ask_ledger(rows: list[dict[str, Any]], question: str, currency: str) -> dict[str, str]:
        return processor.ask_ledger(rows, question, currency=currency)

    active_ask_ledger = ask_ledger_fn or local_ask_ledger

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
                document_box = gr.File(
                    label="Receipt, bill, or note image",
                    file_types=[".pdf", ".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp", ".txt", ".csv"],
                    type="filepath",
                )
                input_choice = gr.Radio(
                    label="Input to analyze",
                    choices=["Auto", "Text note", "Voice note", "Document"],
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

        with gr.Tabs():
            with gr.Tab("Dashboard"):
                with gr.Row(elem_id="dashboard-panel"):
                    dashboard = gr.Markdown(build_dashboard_markdown([]))
                with gr.Row(elem_classes=["dashboard-grid"]):
                    with gr.Column(elem_classes=["ops-stack"]):
                        with gr.Column(elem_id="chart-director", elem_classes=["ops-card"]):
                            chart_director = gr.Markdown(build_chart_markdown([]))
                        daily_brief = gr.Markdown(build_daily_brief_markdown([]), elem_id="daily-brief-panel")
                        daily_brief_button = gr.Button("Generate daily brief", variant="secondary")
                        insights = gr.Markdown(build_insights_markdown([]), elem_id="insight-panel")
                    with gr.Column(elem_id="chart-wall"):
                        primary_chart, secondary_chart, tertiary_chart = build_insight_figures([])
                        primary_plot = gr.Plot(value=primary_chart, label="Insight graph")
                        with gr.Row(elem_id="signal-row"):
                            secondary_plot = gr.Plot(value=secondary_chart, label="Cash trail")
                            tertiary_plot = gr.Plot(value=tertiary_chart, label="People ledger")
                with gr.Row(elem_id="ask-chat-panel", elem_classes=["chat-panel"]):
                    with gr.Column(scale=5):
                        ask_chatbot = gr.Chatbot(
                            value=initial_ask_chat(),
                            label="Ask My Ledger",
                            type="messages",
                            height=320,
                            elem_id="ask-chatbot",
                        )
                        with gr.Row(elem_id="ask-row"):
                            ask_question = gr.Textbox(
                                label="Ask my ledger",
                                placeholder="Who owes me most?",
                                lines=1,
                                scale=5,
                            )
                            ask_button = gr.Button("Ask", variant="primary", scale=1)
                            ask_clear = gr.Button("Reset chat", scale=1)
                    with gr.Column(scale=2):
                        gr.Markdown(
                            """
                            ### Good questions
                            - Who owes me most?
                            - What should I follow up today?
                            - Where did cash go?
                            - Give me the current ledger snapshot.
                            """,
                            elem_id="ask-ledger-panel",
                        )
                with gr.Row():
                    category_table = gr.Dataframe(
                        headers=["category", "total", "display"],
                        datatype=["str", "number", "str"],
                        label="Category heatmap",
                        interactive=False,
                        wrap=True,
                    )
                    party_table = gr.Dataframe(
                        headers=["party", "total", "due"],
                        datatype=["str", "str", "str"],
                        label="People and suppliers",
                        interactive=False,
                        wrap=True,
                    )
            with gr.Tab("Automation Queue"):
                automation = gr.Markdown(build_reminder_markdown([]), elem_id="automation-panel")
                automation_table = gr.Dataframe(
                    headers=[
                        "priority",
                        "counterparty",
                        "amount",
                        "item",
                        "next_action",
                        "cadence",
                        "polite_script",
                        "friendly_script",
                        "firm_script",
                        "source_row",
                    ],
                    datatype=["str", "str", "str", "str", "str", "str", "str", "str", "str", "number"],
                    label="Reply studio",
                    interactive=False,
                    wrap=True,
                )
            with gr.Tab("Review Desk"):
                review = gr.Markdown(build_review_markdown([]), elem_id="review-panel")
                review_table = gr.Dataframe(
                    headers=["source_row", "issue", "confidence", "counterparty", "item", "amount", "question"],
                    datatype=["number", "str", "str", "str", "str", "str", "str"],
                    label="Rows to verify",
                    interactive=False,
                    wrap=True,
                )
            with gr.Tab("Pulse Timeline"):
                timeline = gr.Markdown(build_timeline_markdown([]), elem_id="timeline-panel")
                timeline_plot = gr.Plot(value=timeline_figure([]), label="Shop pulse")
                timeline_table = gr.Dataframe(
                    headers=[
                        "source_row",
                        "date",
                        "badge",
                        "direction",
                        "counterparty",
                        "item",
                        "amount",
                        "signed_amount",
                        "status",
                        "story",
                    ],
                    datatype=["number", "str", "str", "str", "str", "str", "str", "number", "str", "str"],
                    label="Timeline events",
                    interactive=False,
                    wrap=True,
                )
            with gr.Tab("People Memory"):
                memory = gr.Markdown(build_counterparty_memory_markdown([]), elem_id="memory-panel")
                memory_table = gr.Dataframe(
                    headers=[
                        "party",
                        "trust_pulse",
                        "total_moved",
                        "paid",
                        "due",
                        "usual_category",
                        "usual_item",
                        "last_item",
                        "row_count",
                        "next_message",
                    ],
                    datatype=["str", "str", "str", "str", "str", "str", "str", "str", "number", "str"],
                    label="Counterparty memory",
                    interactive=False,
                    wrap=True,
                )
            with gr.Tab("Ledger"):
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
            fn=lambda note, audio, document, source_choice, currency_value, state: add_to_ledger(
                note,
                audio,
                document,
                source_choice,
                currency_value,
                state,
                active_process,
            ),
            inputs=[note_box, audio_box, document_box, input_choice, currency, ledger_state],
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
                document_box,
                input_choice,
                input_notice,
                dashboard,
                chart_director,
                daily_brief,
                primary_plot,
                secondary_plot,
                tertiary_plot,
                insights,
                automation,
                category_table,
                party_table,
                automation_table,
                review,
                review_table,
                timeline,
                timeline_plot,
                timeline_table,
                memory,
                memory_table,
            ],
        )
        clear_button.click(
            fn=lambda: (*clear_ledger(), initial_ask_chat(), ""),
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
                document_box,
                input_choice,
                input_notice,
                dashboard,
                chart_director,
                daily_brief,
                primary_plot,
                secondary_plot,
                tertiary_plot,
                insights,
                automation,
                category_table,
                party_table,
                automation_table,
                review,
                review_table,
                timeline,
                timeline_plot,
                timeline_table,
                memory,
                memory_table,
                ask_chatbot,
                ask_question,
            ],
        )
        daily_brief_button.click(
            fn=lambda state, currency_value: generate_daily_brief(state, currency_value, active_daily_brief),
            inputs=[ledger_state, currency],
            outputs=[daily_brief],
        )
        ask_button.click(
            fn=lambda state, question, history, currency_value: ask_ledger_chat(
                state,
                question,
                history,
                currency_value,
                active_ask_ledger,
            ),
            inputs=[ledger_state, ask_question, ask_chatbot, currency],
            outputs=[ask_chatbot, ask_question],
        )
        ask_question.submit(
            fn=lambda state, question, history, currency_value: ask_ledger_chat(
                state,
                question,
                history,
                currency_value,
                active_ask_ledger,
            ),
            inputs=[ledger_state, ask_question, ask_chatbot, currency],
            outputs=[ask_chatbot, ask_question],
        )
        ask_clear.click(
            fn=lambda: (initial_ask_chat(), ""),
            outputs=[ask_chatbot, ask_question],
        )

    return demo


def add_to_ledger(
    note: str,
    audio_path: str | None,
    document_path: Any,
    source_choice: str,
    currency: str,
    state: list[dict[str, Any]] | None,
    process_fn: ProcessFn,
) -> tuple[Any, ...]:
    rows = state or []
    choice = choose_input(note, audio_path, document_path, source_choice)
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
            gr.update(),
            choice["notice"],
            *render_intelligence(rows),
        )

    if choice["source"] == "audio":
        combined_note = transcribe_audio(audio_path)
        image_urls = None
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
                gr.update(),
                gr.update(value="Voice note"),
                "I could not transcribe that voice note. Try another recording or paste the note.",
                *render_intelligence(rows),
            )
    elif choice["source"] == "document":
        document = prepare_document_input(document_path)
        combined_note = build_document_prompt(document)
        image_urls = document.get("image_urls") or None
        if not combined_note and not image_urls:
            frame = pd.DataFrame(rows, columns=COLUMNS)
            return (
                frame,
                build_summary(rows, {}),
                build_reminders(rows, {}),
                "Model: waiting for document text",
                f"Rows: {len(rows)}",
                write_csv(rows) if rows else None,
                rows,
                gr.update(),
                gr.update(),
                gr.update(),
                gr.update(value="Document"),
                "I could not prepare that document. Try a PDF, receipt image, or pasted note.",
                *render_intelligence(rows),
            )
    else:
        combined_note = (note or "").strip()
        image_urls = None

    result = process_fn(combined_note, currency or "LKR", image_urls)
    rows = rows + compact_rows(result.get("entries", []))

    frame = pd.DataFrame(rows, columns=COLUMNS)
    summary = build_summary(rows, result)
    reminder_text = build_reminders(rows, result)
    csv_path = write_csv(rows) if rows else None
    model = result.get("model_used", "unknown")
    notice = f"Added {len(result.get('entries', []))} row(s) from the {choice['label'].lower()}."
    next_note = gr.update(value="") if choice["source"] == "text" else gr.update()
    next_audio = gr.update(value=None) if choice["source"] == "audio" else gr.update()
    next_document = gr.update(value=None) if choice["source"] == "document" else gr.update()

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
        next_document,
        gr.update(value="Auto"),
        notice,
        *render_intelligence(rows),
    )


def choose_input(note: str | None, audio_path: str | None, document_path: Any, source_choice: str | None) -> dict[str, str]:
    has_text = bool((note or "").strip())
    has_audio = bool(audio_path)
    has_document = bool(document_path)
    choice = source_choice or "Auto"
    present = [
        label
        for label, exists in (
            ("written note", has_text),
            ("voice note", has_audio),
            ("document", has_document),
        )
        if exists
    ]

    if len(present) > 1 and choice == "Auto":
        return {
            "status": "conflict",
            "notice": f"Multiple inputs are present ({', '.join(present)}). Choose Text note, Voice note, or Document, then add it to the ledger.",
        }
    if choice == "Text note" and not has_text:
        return {"status": "missing", "notice": "Text note is selected, but the written note is empty."}
    if choice == "Voice note" and not has_audio:
        return {"status": "missing", "notice": "Voice note is selected, but no audio is attached."}
    if choice == "Document" and not has_document:
        return {"status": "missing", "notice": "Document is selected, but no file is attached."}
    if not has_text and not has_audio and not has_document:
        return {"status": "missing", "notice": "Add a written note, record a voice note, or upload a document first."}
    if choice == "Voice note" or (choice == "Auto" and has_audio):
        return {"status": "ready", "source": "audio", "label": "Voice note"}
    if choice == "Document" or (choice == "Auto" and has_document):
        return {"status": "ready", "source": "document", "label": "Document"}
    return {"status": "ready", "source": "text", "label": "Text note"}


def build_document_prompt(document: dict[str, Any]) -> str:
    kind = document.get("kind") or "document"
    page_count = document.get("page_count") or 0
    text = str(document.get("text") or "").strip()
    parts = [
        f"Uploaded {kind} with {page_count} page/image(s).",
        "Extract shop ledger entries from the visible document content.",
    ]
    if text:
        parts.append(f"Text extracted from the document:\n{text}")
    return "\n".join(parts).strip()


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


def render_intelligence(rows: list[dict[str, Any]]) -> tuple[Any, ...]:
    categories, parties, followups, reviews = build_tables(rows)
    primary_chart, secondary_chart, tertiary_chart = build_insight_figures(rows)
    return (
        build_dashboard_markdown(rows),
        build_chart_markdown(rows),
        build_daily_brief_markdown(rows),
        primary_chart,
        secondary_chart,
        tertiary_chart,
        build_insights_markdown(rows),
        build_reminder_markdown(rows),
        pd.DataFrame(categories, columns=["category", "total", "display"]),
        pd.DataFrame(parties, columns=["party", "total", "due"]),
        pd.DataFrame(
            followups,
            columns=[
                "priority",
                "counterparty",
                "amount",
                "item",
                "next_action",
                "cadence",
                "polite_script",
                "friendly_script",
                "firm_script",
                "source_row",
            ],
        ),
        build_review_markdown(rows),
        pd.DataFrame(
            reviews,
            columns=["source_row", "issue", "confidence", "counterparty", "item", "amount", "question"],
        ),
        build_timeline_markdown(rows),
        timeline_figure(rows),
        pd.DataFrame(
            timeline_rows(rows),
            columns=[
                "source_row",
                "date",
                "badge",
                "direction",
                "counterparty",
                "item",
                "amount",
                "signed_amount",
                "status",
                "story",
            ],
        ),
        build_counterparty_memory_markdown(rows),
        pd.DataFrame(
            counterparty_memory_cards(rows),
            columns=[
                "party",
                "trust_pulse",
                "total_moved",
                "paid",
                "due",
                "usual_category",
                "usual_item",
                "last_item",
                "row_count",
                "next_message",
            ],
        ),
    )


def clear_ledger() -> tuple[Any, ...]:
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
        None,
        "Auto",
        "Ready for one note.",
        *render_intelligence([]),
    )


def generate_daily_brief(
    state: list[dict[str, Any]] | None,
    currency: str,
    daily_brief_fn: DailyBriefFn,
) -> str:
    rows = state or []
    result = daily_brief_fn(rows, currency or "LKR")
    return build_daily_brief_markdown(rows, result.get("brief"), result.get("model_used", "unknown"))


def ask_ledger(
    state: list[dict[str, Any]] | None,
    question: str,
    currency: str,
    ask_ledger_fn: AskLedgerFn,
) -> str:
    rows = state or []
    result = ask_ledger_fn(rows, question or "", currency or "LKR")
    answer = result.get("answer") or "No answer available."
    model_used = result.get("model_used", "unknown")
    return f"### Ask My Ledger\n{answer}\n\n<small>Answer: {model_used}</small>"


def initial_ask_chat() -> ChatHistory:
    return [
        {
            "role": "assistant",
            "content": "Ask me about dues, follow-ups, spending, or today’s cash position after you add ledger rows.",
        }
    ]


def ask_ledger_chat(
    state: list[dict[str, Any]] | None,
    question: str,
    history: ChatHistory | None,
    currency: str,
    ask_ledger_fn: AskLedgerFn,
) -> tuple[ChatHistory, str]:
    clean_question = (question or "").strip()
    next_history: ChatHistory = list(history or initial_ask_chat())
    if not clean_question:
        next_history.append({"role": "assistant", "content": "Ask a question first, then I’ll answer from the ledger rows."})
        return next_history, ""

    rows = state or []
    result = ask_ledger_fn(rows, clean_question, currency or "LKR")
    answer = result.get("answer") or "No answer available."
    model_used = result.get("model_used", "unknown")
    next_history.append({"role": "user", "content": clean_question})
    next_history.append({"role": "assistant", "content": f"{answer}\n\nAnswer source: {model_used}"})
    return next_history, ""
