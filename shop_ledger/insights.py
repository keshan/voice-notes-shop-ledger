from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date
from typing import Any


def money(value: float, currency: str = "LKR") -> str:
    return f"{currency} {value:,.0f}"


def amount(row: dict[str, Any]) -> float:
    try:
        return float(row.get("amount") or 0)
    except (TypeError, ValueError):
        return 0.0


def primary_currency(rows: list[dict[str, Any]]) -> str:
    for row in rows:
        currency = row.get("currency")
        if currency:
            return str(currency)
    return "LKR"


def compute_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    currency = primary_currency(rows)
    paid_expense = sum(amount(row) for row in rows if row.get("direction") == "expense" and row.get("payment_status") == "paid")
    paid_income = sum(amount(row) for row in rows if row.get("direction") == "income" and row.get("payment_status") == "paid")
    due_income = sum(amount(row) for row in rows if row.get("direction") == "income" and row.get("payment_status") == "due")
    due_expense = sum(amount(row) for row in rows if row.get("direction") == "expense" and row.get("payment_status") == "due")
    reminders = [row for row in rows if row.get("reminder") or row.get("payment_status") == "due"]
    confidence_values = [float(row.get("confidence") or 0) for row in rows]

    return {
        "currency": currency,
        "row_count": len(rows),
        "paid_expense": paid_expense,
        "paid_income": paid_income,
        "net_cash": paid_income - paid_expense,
        "due_income": due_income,
        "due_expense": due_expense,
        "open_followups": len(reminders),
        "avg_confidence": sum(confidence_values) / len(confidence_values) if confidence_values else 0,
    }


def top_counter(rows: list[dict[str, Any]], key: str) -> tuple[str, float]:
    totals: dict[str, float] = defaultdict(float)
    for row in rows:
        value = str(row.get(key) or "").strip() or "uncategorized"
        totals[value] += amount(row)
    if not totals:
        return "none", 0.0
    return max(totals.items(), key=lambda item: item[1])


def biggest_transaction(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not rows:
        return None
    return max(rows, key=amount)


def followup_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    queue = []
    for index, row in enumerate(rows, start=1):
        if row.get("payment_status") != "due" and not row.get("reminder"):
            continue
        who = row.get("counterparty") or "Unknown"
        value = amount(row)
        currency = row.get("currency") or primary_currency(rows)
        item = row.get("item") or "ledger item"
        reminder = row.get("reminder") or f"Follow up with {who} about {money(value, currency)}."
        queue.append(
            {
                "priority": "High" if value >= 5000 else "Normal",
                "counterparty": who,
                "amount": money(value, currency),
                "item": item,
                "next_action": reminder,
                "cadence": "Today, then every 2 days" if value >= 5000 else "Tomorrow",
                "script": f"Hi {who}, just checking on {money(value, currency)} for {item}. Can you confirm when it will be settled?",
                "source_row": index,
            }
        )
    return sorted(queue, key=lambda row: (row["priority"] != "High", row["counterparty"]))


def category_breakdown(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    totals: dict[str, float] = defaultdict(float)
    currency = primary_currency(rows)
    for row in rows:
        totals[str(row.get("category") or "uncategorized")] += amount(row)
    return [
        {"category": category, "total": total, "display": money(total, currency)}
        for category, total in sorted(totals.items(), key=lambda item: item[1], reverse=True)
    ]


def party_breakdown(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    totals: dict[str, float] = defaultdict(float)
    due: dict[str, float] = defaultdict(float)
    currency = primary_currency(rows)
    for row in rows:
        party = str(row.get("counterparty") or "Unknown")
        totals[party] += amount(row)
        if row.get("payment_status") == "due":
            due[party] += amount(row)
    return [
        {"party": party, "total": money(total, currency), "due": money(due[party], currency)}
        for party, total in sorted(totals.items(), key=lambda item: item[1], reverse=True)
    ]


def build_dashboard_markdown(rows: list[dict[str, Any]]) -> str:
    metrics = compute_metrics(rows)
    currency = metrics["currency"]
    if not rows:
        return "### Tonight's Desk\nNo entries yet. Add one note to light up the dashboard."

    return (
        "### Tonight's Desk\n"
        f"<div class='metric-grid'>"
        f"<div class='metric-card'><span>Net cash</span><strong>{money(metrics['net_cash'], currency)}</strong></div>"
        f"<div class='metric-card'><span>Cash in</span><strong>{money(metrics['paid_income'], currency)}</strong></div>"
        f"<div class='metric-card'><span>Cash out</span><strong>{money(metrics['paid_expense'], currency)}</strong></div>"
        f"<div class='metric-card'><span>Still due</span><strong>{money(metrics['due_income'], currency)}</strong></div>"
        f"<div class='metric-card'><span>Follow-ups</span><strong>{metrics['open_followups']}</strong></div>"
        f"<div class='metric-card'><span>Avg confidence</span><strong>{metrics['avg_confidence']:.0%}</strong></div>"
        f"</div>"
    )


def build_insights_markdown(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "### Field Intelligence\nInsights appear after the first ledger entry."

    metrics = compute_metrics(rows)
    currency = metrics["currency"]
    top_category, top_category_total = top_counter(rows, "category")
    top_party, top_party_total = top_counter(rows, "counterparty")
    biggest = biggest_transaction(rows)
    risks = risk_flags(rows)
    risk_text = "\n".join(f"- {risk}" for risk in risks) if risks else "- No urgent risks detected."
    biggest_text = "none"
    if biggest:
        biggest_text = f"{money(amount(biggest), currency)} for {biggest.get('item') or 'unknown item'}"

    return (
        "### Field Intelligence\n"
        f"- Top category: **{top_category}** ({money(top_category_total, currency)})\n"
        f"- Most active party: **{top_party}** ({money(top_party_total, currency)})\n"
        f"- Biggest entry: **{biggest_text}**\n"
        f"- Open follow-up value: **{money(metrics['due_income'], currency)}**\n\n"
        "### Watch List\n"
        f"{risk_text}\n\n"
        "### Field Note\n"
        f"{daily_field_note(rows)}"
    )


def risk_flags(rows: list[dict[str, Any]]) -> list[str]:
    metrics = compute_metrics(rows)
    currency = metrics["currency"]
    flags = []
    if metrics["due_income"] > metrics["paid_income"] and metrics["due_income"] > 0:
        flags.append(f"Due income ({money(metrics['due_income'], currency)}) is higher than collected cash.")
    for row in rows:
        if row.get("payment_status") == "due" and amount(row) >= 5000:
            flags.append(f"High-value due item: {row.get('counterparty') or 'Unknown'} owes {money(amount(row), currency)}.")
    if metrics["avg_confidence"] and metrics["avg_confidence"] < 0.55:
        flags.append("Average extraction confidence is low. Review recent rows before using the CSV.")
    return flags[:5]


def daily_field_note(rows: list[dict[str, Any]]) -> str:
    metrics = compute_metrics(rows)
    currency = metrics["currency"]
    categories = [item["category"] for item in category_breakdown(rows)[:2]]
    category_text = " and ".join(categories) if categories else "general trade"
    return (
        f"{date.today().isoformat()}: {len(rows)} entries logged. "
        f"Money moved mostly through {category_text}. "
        f"Net cash is {money(metrics['net_cash'], currency)} with {metrics['open_followups']} follow-up(s) open."
    )


def build_reminder_markdown(rows: list[dict[str, Any]]) -> str:
    queue = followup_rows(rows)
    if not queue:
        return "### Automation Queue\nNo follow-ups waiting. The desk is clear."

    cards = ["### Automation Queue"]
    for item in queue[:8]:
        cards.append(
            "<div class='followup-card'>"
            f"<strong>{item['priority']} · {item['counterparty']} · {item['amount']}</strong>"
            f"<p>{item['next_action']}</p>"
            f"<small>Cadence: {item['cadence']}</small>"
            f"<code>{item['script']}</code>"
            "</div>"
        )
    return "\n".join(cards)


def build_tables(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    return category_breakdown(rows), party_breakdown(rows), followup_rows(rows)
