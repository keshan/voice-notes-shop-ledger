# UI Design And Layout System

Voice Notes to Shop Ledger is organized as a small-shop operating cockpit, not a
generic Gradio demo. The layout is designed for a shopkeeper who wants to move
from messy capture to concrete action without hunting through many equal tabs.

## Product Shape

The screen is split into four operating zones:

```text
Status strip
  Model status, row count, and session health

Shop OS Cockpit
  Capture rail | Shop Pulse center | Ledger Assistant rail

Action Inbox
  Follow-ups, review items, and anomaly signals

Workbenches
  People memory and ledger archive
```

This keeps the most common loop visible:

1. Capture a note, voice clip, or document.
2. Watch the ledger pulse update.
3. Ask the assistant what matters.
4. Clear actions before exporting.

## Cockpit Layout

### Capture Rail

The left rail owns all intake:

- written note
- voice note
- document upload
- input conflict selector
- currency
- add and clear controls
- example notes

The rail stays sticky on desktop because the user should always be able to add
the next note without scrolling back to the top. On mobile it becomes a normal
stack.

### Shop Pulse Center

The center column is the primary attention area:

- live KPI dashboard
- chart composer
- chart director
- main Plotly graph
- supporting signal graphs
- shop pulse timeline
- field intelligence

This is where the app turns ledger rows into a story. The chart composer lets
Gemma or the deterministic fallback pick a safe chart spec from a plain-language
question, while the timeline makes the day feel visible.

### Ledger Assistant Rail

The right rail is a persistent co-pilot:

- running totals and reminders
- LLM Daily Brief
- full Ask My Ledger chat
- voice question mode
- prompt suggestions
- command palette
- daily closing ritual

The assistant rail is sticky on desktop because questions and actions should be
available while the user scans charts, reminders, or the archive.

## Action Inbox

The Action Inbox merges three previously separate areas:

- follow-up automation
- review desk
- anomaly lantern

The user-facing cards appear first. The heavier operational tables are tucked
inside an accordion for demos and deeper inspection. This avoids making the app
look like a spreadsheet while preserving the export/review detail.

## Workbenches

The remaining tabs are intentionally few:

| Workbench | Purpose |
| --- | --- |
| People | Counterparty memory, trust pulse, and party totals. |
| Ledger Archive | Raw ledger rows, CSV export, categories, closing checklist, and event table. |

This replaces the older one-tab-per-feature structure. Features now live where
the user expects them rather than competing as top-level destinations.

## Styling Rules

- Dark theme is the default.
- Cards use an 8px radius and thin ledger-colored borders.
- The app avoids a single-hue palette: green means money/healthy, gold means
  attention, red means risk, and blue means insight.
- Plotly figures inherit the same background, grid, and hover label treatment.
- Raw data tables are secondary surfaces, not the first thing the user sees.
- Desktop uses a three-zone cockpit; mobile collapses into one column.

## Demo Flow

For the hackathon video, the recommended flow is:

1. Add a messy text note.
2. Upload a bill or receipt.
3. Point to the Shop Pulse center: KPIs, graph, and timeline update.
4. Ask "Who owes me most?" in the assistant rail.
5. Generate the daily brief.
6. Show the Action Inbox with follow-up/review/anomaly cards.
7. Open People to show memory cards.
8. Open Ledger Archive and export CSV.

## Implementation Map

The layout lives in `shop_ledger/ui.py`.

Important CSS hooks:

- `#cockpit-shell`
- `#input-dock`
- `#pulse-core`
- `#assistant-rail`
- `#action-inbox`
- `#action-grid`
- `#workbench-tabs`
- `#people-workbench`
- `#ledger-archive`

The insight content still comes from `shop_ledger/insights.py`, which keeps
layout and business logic separated.
