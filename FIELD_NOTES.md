# Field Notes

## Person

TBD: name or role of the person this helps.

## Problem

They track small purchases, supplier payments, customer dues, and reminders in
messy notes or voice messages. The problem is not accounting complexity; it is
the daily friction of turning rough notes into something they can review later.

## What We Built

Tagline: Messy notes in. Clear books by closing time.

Small Shop Ledger turns a note like:

```text
paid Ravi 1200 for rice bags, customer Nimal owes 750 for tea packets, remind me Friday
```

into ledger rows, totals, and follow-up reminders.

It also accepts receipts, bills, note photos, and PDFs. PDFs are rendered into
page images locally, and Gemma reads the document visually through llama.cpp's
multimodal chat input.

The current version is organized as a Shop OS Cockpit:

- Net cash, cash in, cash out, due amount, open follow-ups, and average
  extraction confidence.
- A chart director that chooses the most useful graph for the current ledger:
  dues, expenses, cashflow, confidence review, or category mix.
- A Gemma-generated daily shop pulse that summarizes cash position, pressure,
  and the next follow-up from structured rows.
- Ask My Ledger for natural questions such as who owes the most or where cash
  went, grounded in the structured rows.
- Voice questions for Ask My Ledger, so the shopkeeper can speak a question
  after entering the day’s notes.
- A command palette for fast unpaid scans, WhatsApp follow-ups, risk checks,
  cash summaries, and QuickBooks-style export planning.
- People Memory cards that summarize trust, due balances, usual categories, and
  the next message per customer or supplier.
- Anomaly Lantern warnings for unusually large amounts, missing values,
  high-value dues, repeat unpaid parties, and low-confidence rows.
- A Shop Pulse Timeline that turns raw rows into the story of the day.
- A Daily Closing Ritual that turns the ledger into an end-of-day checklist.
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
3. Show the Shop Pulse center updating clean rows, totals, charts, and the
   timeline without leaving the cockpit.
4. Generate the daily shop pulse and read the short practical summary.
5. Ask "Who owes me most?" and show the answer.
6. Ask the same question by voice.
7. Run the command palette for unpaid rows or QuickBooks export planning.
8. Show the Action Inbox with follow-ups, review rows, and anomalies.
9. Open People and show a counterparty profile.
10. Open the Ledger Archive and show the raw table, closing checklist, and CSV
   export.
11. Point out the model badge showing the actual Gemma GGUF model label.
12. Export CSV.

## Lessons

TBD after real-user testing.
