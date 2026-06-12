# Roadmap And Feature Ideas

This app is strongest when it feels like a tiny night-shift co-pilot for a real
shopkeeper: practical, tactile, and a little magical. The ideas below keep that
theme while pushing the demo toward a more modern, world-class experience.

## Highest-Impact Next Features

### 1. Dynamic Insight Graphs

Status: shipped in the first enhancement sprint.

Generate charts based on the ledger rows and the current question the app thinks
is most important. The app now has a deterministic chart planner and Plotly
graphs for due radar, spend pressure, cashflow, confidence review, category mix,
and people exposure.

Examples:

- If dues are high: show a due-by-counterparty bar chart.
- If expenses dominate: show expense category breakdown.
- If many rows exist across dates: show cashflow over time.
- If confidence is low: show a review queue chart.

Implemented path:

- Added a chart planner in `shop_ledger/insights.py`.
- Let deterministic rules pick a chart first.
- Rendered charts with Gradio `Plot` and Plotly.

Future path:

- Optionally ask the local LLM to choose between safe chart specs.
- Add user-selectable chart questions such as "who owes me most?" or "what is
  eating cash?"

### 2. Ledger Command Center Layout

Status: shipped in the Shop OS Cockpit sprint.

Rearrange the UI into a more modern operational console:

- Left rail: input capture and session status.
- Center: active dashboard cards and chart.
- Right rail: follow-up queue and risk alerts.
- Bottom: raw ledger table.

The app now has a three-zone cockpit:

- Capture rail for text, audio, documents, currency, examples, and conflict
  handling.
- Shop Pulse center for KPIs, dynamic charts, timeline, and field intelligence.
- Ledger Assistant rail for daily brief, Ask My Ledger, voice questions,
  command palette, reminders, and closing ritual.

Supporting workflows are grouped into an Action Inbox plus People and Ledger
Archive workbenches instead of one tab per feature.

### 3. LLM-Generated Daily Brief

Status: shipped in the Daily Brief enhancement sprint.

After every few entries, generate a short "shopkeeper briefing":

```text
Today cash is negative because inventory spend is high. Nimal and Saman need
follow-up. Tea packets are the biggest open due item.
```

The dashboard now has a "Today's Shop Pulse" panel. It shows a local fallback
brief immediately and can call Gemma through the Modal llama.cpp worker for a
short practical summary from structured rows.

### 4. Voice Reply Studio

Status: shipped in the second enhancement sprint.

For every due item, generate three reply styles:

- polite
- firm
- friendly/local

The automation queue now generates polite, friendly, and firm scripts for each
due item. The user can copy the right tone into WhatsApp or SMS. This is very
demoable and directly useful.

### 5. Mistake Review Mode

Status: shipped in the third enhancement sprint.

Add a "Review low-confidence rows" panel:

- show rows below confidence threshold
- ask simple correction questions
- update the row in session state

The app now has a Review Desk tab that shows low-confidence or incomplete rows
and asks simple correction questions. A future version can make those questions
editable and write corrections back into session state.

## Futuristic But Still Practical

### 6. Shop Pulse Timeline

Status: shipped in the Pulse Timeline enhancement sprint.

Convert the ledger into a visual day timeline:

```text
09:20 inventory spend
10:45 sale logged
13:10 customer due
17:30 utility bill
```

The app now includes a Pulse Timeline tab with story cards, a Plotly pulse
chart, and a structured event table. This makes messy notes feel like a story
of the day.

### 7. Counterparty Memory Cards

Status: shipped in the memory-card enhancement sprint.

Create small profiles for each person or supplier:

- total paid
- total due
- last interaction
- usual category
- suggested next message

This is useful for small shops where trust and memory matter more than formal
accounting.

The app now includes People Memory cards and a counterparty table with trust
pulse, due amount, usual category, last item, and suggested next message.

### 8. What Changed Since Yesterday?

If persistence is added, the app can summarize:

- new dues
- cleared dues
- rising expense categories
- repeat late payers
- unusual entries

This becomes a daily habit rather than a one-off tool.

### 9. "Ask My Ledger"

Status: shipped in the Ask My Ledger enhancement sprint.

A local natural-language query box:

```text
Who owes me the most?
What did I spend on inventory?
What should I follow up today?
```

The dashboard now includes a question box. Common questions are answered
deterministically from structured rows, and Modal production can route the same
rows to Gemma for a concise local/off-grid answer.

### 10. Tiny Forecasts

Use simple local forecasting, not a big ML system:

- expected cash-in if dues are paid
- likely week-end cash position
- category spend trend

This adds value without leaving the small-model spirit.

## Additional Shipped Ideas

### Ledger Command Palette

Status: shipped.

The dashboard now has a command palette for unpaid rows, WhatsApp follow-ups,
risk scans, cash summaries, and QuickBooks-style export planning.

### AI Chart Composer

Status: shipped.

The chart wall now accepts plain-language chart questions. Modal production can
ask Gemma to choose from safe chart specs; local mode uses deterministic rules.

### Anomaly Lantern

Status: shipped.

The app now flags high-value dues, missing amounts, low-confidence rows,
unusually large entries, and repeat unpaid parties.

### Shopkeeper Voice Mode

Status: shipped.

Ask My Ledger now supports spoken questions using the same local transcription
path as voice notes.

### Daily Closing Ritual

Status: shipped.

The app now includes an end-of-day checklist and closing summary for cash,
dues, review items, anomalies, and export readiness.

## Hackathon Merit Badge Opportunities

### Off The Grid

Already aligned:

- no cloud LLM API
- llama.cpp runtime
- GGUF model

### Llama Champion

Already aligned:

- `llama-cpp-python`
- GGUF model
- Modal GPU worker

### Off-Brand

Aligned:

- custom dark UI
- Shop OS Cockpit layout
- persistent assistant rail
- action inbox
- themed Plotly graph wall
- People and Ledger Archive workbenches

Next step:

- richer CSS
- possible custom Gradio frontend layer if the installed Gradio version exposes
  the needed APIs in the future

### Field Notes

Already started:

- `FIELD_NOTES.md`

Next step:

- add real user interview notes
- add before/after screenshots
- add demo observations

## Recommended Next Sprint

Build these in order:

1. Dynamic charts in the Dashboard tab.
2. Right-side automation queue preview beside the note input.
3. LLM-generated daily brief.
4. Review mode for low-confidence rows.
5. Counterparty memory cards.

That gives the app an impressive demo arc:

```text
messy note -> clean ledger -> live dashboard -> smart chart -> follow-up script
-> daily brief -> CSV export
```
