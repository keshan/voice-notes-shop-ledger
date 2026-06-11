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
4. Show a reminder generated from an unpaid item.
5. Export CSV.

## Lessons

TBD after real-user testing.
