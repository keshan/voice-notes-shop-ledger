# Field Notes

## Person

TBD: name or role of the person this helps.

## Problem

They track small purchases, supplier payments, customer dues, and reminders in
messy notes or voice messages. The problem is not accounting complexity; it is
the daily friction of turning rough notes into something they can review later.

## What We Built

Voice Notes to Shop Ledger turns a note like:

```text
paid Ravi 1200 for rice bags, customer Nimal owes 750 for tea packets, remind me Friday
```

into ledger rows, totals, and follow-up reminders.

It also accepts receipts, bills, note photos, and PDFs. PDFs are rendered into
page images locally, and Gemma reads the document visually through llama.cpp's
multimodal chat input.

The current version also adds a dashboard and automation queue:

- Net cash, cash in, cash out, due amount, open follow-ups, and average
  extraction confidence.
- A chart director that chooses the most useful graph for the current ledger:
  dues, expenses, cashflow, confidence review, or category mix.
- A Gemma-generated daily shop pulse that summarizes cash position, pressure,
  and the next follow-up from structured rows.
- Category and counterparty breakdowns.
- Risk flags for high-value dues and low-confidence extraction.
- Ready-to-send follow-up scripts with suggested cadence and three tones:
  polite, friendly, and firm.
- A Review Desk for low-confidence or incomplete rows, with simple questions
  the shopkeeper can answer before exporting.

## Small Model Fit

This is a structured extraction and rewriting task. A 12B-class model is enough
when the schema is narrow and the UI keeps the workflow grounded.

## What To Test With The User

- Can they enter a note faster than opening a spreadsheet?
- Do the extracted rows match what they meant?
- Are the categories useful?
- Do reminders feel helpful or annoying?
- Would they use the CSV export?

## Demo Video Beats

1. Show the messy note or voice note.
2. Click "Add to ledger".
3. Show clean rows and totals.
4. Open the dashboard and show due amount, the chosen graph, and risk flags.
5. Generate the daily shop pulse and read the short practical summary.
6. Open the automation queue and pick the right tone for a follow-up script.
7. Open the Review Desk and show that uncertainty becomes a clear correction
   task.
8. Export CSV.

## Lessons

TBD after real-user testing.
