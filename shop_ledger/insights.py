from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from typing import Any

import plotly.graph_objects as go


PALETTE = {
    "bg": "#080c12",
    "plot": "#0b1017",
    "panel": "#10151d",
    "grid": "rgba(157, 177, 154, 0.16)",
    "axis": "rgba(243, 244, 236, 0.58)",
    "ink": "#f3f4ec",
    "muted": "#a8b3a5",
    "green": "#8bdc8b",
    "gold": "#e6b450",
    "red": "#ff7a68",
    "blue": "#8ab4ff",
    "violet": "#b8a6ff",
}


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


def parse_row_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    if not text:
        return date.today()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%b %d", "%B %d"):
        try:
            parsed = datetime.strptime(text, fmt)
            if fmt in ("%b %d", "%B %d"):
                return parsed.replace(year=date.today().year).date()
            return parsed.date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        return date.today()


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
        variants = reply_variants(who, value, currency, item)
        queue.append(
            {
                "priority": "High" if value >= 5000 else "Normal",
                "counterparty": who,
                "amount": money(value, currency),
                "item": item,
                "next_action": reminder,
                "cadence": "Today, then every 2 days" if value >= 5000 else "Tomorrow",
                "script": variants["polite"],
                "polite_script": variants["polite"],
                "friendly_script": variants["friendly"],
                "firm_script": variants["firm"],
                "source_row": index,
            }
        )
    return sorted(queue, key=lambda row: (row["priority"] != "High", row["counterparty"]))


def reply_variants(who: str, value: float, currency: str, item: str) -> dict[str, str]:
    amount_text = money(value, currency)
    return {
        "polite": f"Hi {who}, just checking on {amount_text} for {item}. Can you confirm when it will be settled?",
        "friendly": f"Hi {who}, quick reminder from the shop ledger: {amount_text} is still open for {item}. Tell me what works for you.",
        "firm": f"Hi {who}, {amount_text} for {item} is still pending. Please settle it today or send a clear payment time.",
    }


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


def counterparty_memory_cards(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    currency = primary_currency(rows)
    profiles: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(rows, start=1):
        party = str(row.get("counterparty") or "Unknown").strip() or "Unknown"
        profile = profiles.setdefault(
            party,
            {
                "party": party,
                "total_moved": 0.0,
                "paid": 0.0,
                "due": 0.0,
                "row_count": 0,
                "last_row": index,
                "last_item": "",
                "categories": defaultdict(int),
                "items": defaultdict(int),
            },
        )
        value = amount(row)
        profile["total_moved"] += value
        profile["row_count"] += 1
        profile["last_row"] = index
        profile["last_item"] = row.get("item") or "ledger item"
        profile["categories"][str(row.get("category") or "uncategorized")] += 1
        profile["items"][str(row.get("item") or "ledger item")] += 1
        if row.get("payment_status") == "due":
            profile["due"] += value
        elif row.get("payment_status") == "paid":
            profile["paid"] += value

    cards = []
    for profile in profiles.values():
        category = max(profile["categories"].items(), key=lambda item: item[1])[0] if profile["categories"] else "uncategorized"
        usual_item = max(profile["items"].items(), key=lambda item: item[1])[0] if profile["items"] else "ledger item"
        trust = "Clear" if profile["due"] == 0 else "Watch" if profile["due"] < 5000 else "Collect first"
        next_message = (
            f"Thank {profile['party']} and keep trading."
            if profile["due"] == 0
            else f"Follow up with {profile['party']} about {money(profile['due'], currency)} before the next sale."
        )
        cards.append(
            {
                "party": profile["party"],
                "trust_pulse": trust,
                "total_moved": money(profile["total_moved"], currency),
                "paid": money(profile["paid"], currency),
                "due": money(profile["due"], currency),
                "usual_category": category,
                "usual_item": usual_item,
                "last_item": profile["last_item"],
                "row_count": profile["row_count"],
                "next_message": next_message,
            }
        )
    return sorted(cards, key=lambda card: (card["trust_pulse"] != "Collect first", card["trust_pulse"] != "Watch", card["party"]))


def build_counterparty_memory_markdown(rows: list[dict[str, Any]]) -> str:
    cards = counterparty_memory_cards(rows)
    if not cards:
        return "### Counterparty Memory\nPeople and supplier memory cards appear after the first ledger entry."

    blocks = ["### Counterparty Memory", "<div class='memory-grid'>"]
    for card in cards[:9]:
        tone = "risk" if card["trust_pulse"] == "Collect first" else "watch" if card["trust_pulse"] == "Watch" else "clear"
        blocks.append(
            f"<div class='memory-card {tone}'>"
            f"<strong>{card['party']}</strong>"
            f"<span>{card['trust_pulse']}</span>"
            f"<p>{card['total_moved']} moved · {card['due']} due</p>"
            f"<small>Usually: {card['usual_category']} / {card['usual_item']}</small>"
            f"<code>{card['next_message']}</code>"
            "</div>"
        )
    blocks.append("</div>")
    return "\n".join(blocks)


def review_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    review = []
    for index, row in enumerate(rows, start=1):
        confidence = float(row.get("confidence") or 0)
        missing = [
            label
            for label, value in {
                "counterparty": row.get("counterparty"),
                "item": row.get("item"),
                "amount": row.get("amount"),
                "payment status": row.get("payment_status"),
            }.items()
            if value in (None, "", 0)
        ]
        if confidence >= 0.6 and not missing:
            continue
        amount_text = money(amount(row), row.get("currency") or primary_currency(rows))
        issue = "Low confidence" if confidence < 0.6 else "Missing detail"
        if missing:
            issue += f": {', '.join(missing)}"
        review.append(
            {
                "source_row": index,
                "issue": issue,
                "confidence": f"{confidence:.0%}",
                "counterparty": row.get("counterparty") or "Unknown",
                "item": row.get("item") or "Unknown item",
                "amount": amount_text,
                "question": review_question(row, missing),
            }
        )
    return review


def review_question(row: dict[str, Any], missing: list[str]) -> str:
    who = row.get("counterparty") or "this person"
    item = row.get("item") or "this item"
    if missing:
        return f"Can you confirm the {', '.join(missing)} for {item}?"
    return f"Can you confirm {who}, {item}, and the amount before exporting?"


def build_dashboard_markdown(rows: list[dict[str, Any]]) -> str:
    metrics = compute_metrics(rows)
    currency = metrics["currency"]
    if not rows:
        return (
            "### Command Center\n"
            "No entries yet. Add one note to light up the cash desk, chart board, and follow-up radar."
        )

    return (
        "### Command Center\n"
        f"<div class='metric-grid'>"
        f"<div class='metric-card'><span>Net cash</span><strong>{money(metrics['net_cash'], currency)}</strong></div>"
        f"<div class='metric-card'><span>Cash in</span><strong>{money(metrics['paid_income'], currency)}</strong></div>"
        f"<div class='metric-card'><span>Cash out</span><strong>{money(metrics['paid_expense'], currency)}</strong></div>"
        f"<div class='metric-card'><span>Still due</span><strong>{money(metrics['due_income'], currency)}</strong></div>"
        f"<div class='metric-card'><span>Follow-ups</span><strong>{metrics['open_followups']}</strong></div>"
        f"<div class='metric-card'><span>Avg confidence</span><strong>{metrics['avg_confidence']:.0%}</strong></div>"
        f"</div>"
    )


def build_chart_plan(rows: list[dict[str, Any]]) -> dict[str, str]:
    if not rows:
        return {
            "chart": "empty",
            "title": "Waiting for ledger signal",
            "question": "What will the first note reveal?",
            "reason": "The graph board wakes up after the first extracted row.",
        }

    metrics = compute_metrics(rows)
    low_confidence = sum(1 for row in rows if float(row.get("confidence") or 0) < 0.6)
    dated_rows = {parse_row_date(row.get("date")) for row in rows}
    due_parties = {str(row.get("counterparty") or "Unknown") for row in rows if row.get("payment_status") == "due"}

    if metrics["due_income"] > 0 and len(due_parties) >= 1:
        return {
            "chart": "due_by_party",
            "title": "Who needs a follow-up first?",
            "question": "Where is unpaid money concentrated?",
            "reason": f"{money(metrics['due_income'], metrics['currency'])} is still due across {len(due_parties)} contact(s).",
        }
    if metrics["paid_expense"] > metrics["paid_income"] and metrics["paid_expense"] > 0:
        return {
            "chart": "expense_categories",
            "title": "What is pulling cash out?",
            "question": "Which spend category is dominating today?",
            "reason": "Paid expenses are currently higher than collected income.",
        }
    if len(dated_rows) > 1:
        return {
            "chart": "cashflow",
            "title": "How is cash moving over time?",
            "question": "Which days changed the cash position?",
            "reason": f"The ledger spans {len(dated_rows)} dates, so a timeline is now useful.",
        }
    if low_confidence > 0:
        return {
            "chart": "confidence_review",
            "title": "Which rows need human eyes?",
            "question": "Where might the extractor be uncertain?",
            "reason": f"{low_confidence} row(s) are below 60% confidence.",
        }
    return {
        "chart": "category_mix",
        "title": "What shape is today's trade?",
        "question": "Which categories are carrying the ledger?",
        "reason": "No urgent risk dominates, so the board shows category mix.",
    }


CHART_SPECS = {
    "due_by_party": "Due radar",
    "expense_categories": "Spend pressure",
    "cashflow": "Cashflow trail",
    "confidence_review": "Review queue",
    "category_mix": "Category mix",
    "party_exposure": "People ledger",
    "timeline": "Shop pulse timeline",
}


def chart_spec_from_question(rows: list[dict[str, Any]], question: str) -> dict[str, str]:
    text = question.strip().lower()
    if not rows:
        return {"chart": "empty", "reason": "Add ledger rows before composing charts.", "model_used": "local rules"}
    if any(word in text for word in ("owe", "due", "unpaid", "collect")):
        chart = "due_by_party"
        reason = "The question is about unpaid money and collections."
    elif any(word in text for word in ("spend", "spent", "expense", "cash go", "cash out")):
        chart = "expense_categories"
        reason = "The question is about where cash went."
    elif any(word in text for word in ("time", "trend", "flow", "day", "cash low")):
        chart = "cashflow"
        reason = "The question is about movement over time or cash position."
    elif any(word in text for word in ("confidence", "wrong", "review", "mistake", "uncertain")):
        chart = "confidence_review"
        reason = "The question is about extraction quality."
    elif any(word in text for word in ("person", "people", "supplier", "customer", "party")):
        chart = "party_exposure"
        reason = "The question is about people and suppliers."
    elif any(word in text for word in ("story", "timeline", "happened")):
        chart = "timeline"
        reason = "The question asks for the story of the day."
    else:
        plan = build_chart_plan(rows)
        chart = plan["chart"]
        reason = plan["reason"]
    return {"chart": chart, "reason": reason, "model_used": "local rules"}


def figure_for_chart_id(rows: list[dict[str, Any]], chart: str) -> go.Figure:
    builders = {
        "due_by_party": due_by_party_figure,
        "expense_categories": expense_category_figure,
        "cashflow": cashflow_figure,
        "confidence_review": confidence_review_figure,
        "category_mix": category_mix_figure,
        "party_exposure": party_exposure_figure,
        "timeline": timeline_figure,
    }
    return builders.get(chart, category_mix_figure)(rows) if rows else empty_figure()


def build_chart_composer_markdown(question: str, spec: dict[str, str]) -> str:
    chart = spec.get("chart", "category_mix")
    title = CHART_SPECS.get(chart, "Category mix")
    reason = spec.get("reason") or "The ledger shape makes this view useful."
    model_used = spec.get("model_used", "local rules")
    prompt = question.strip() or "Auto-compose from the ledger."
    return (
        "### AI Chart Composer\n"
        f"**Question:** {prompt}\n\n"
        f"**Chart:** {title}\n\n"
        f"**Why:** {reason}\n\n"
        f"<small>Composer: {model_used}</small>"
    )


def build_chart_markdown(rows: list[dict[str, Any]]) -> str:
    plan = build_chart_plan(rows)
    if not rows:
        return (
            "### Chart Director\n"
            f"**Question:** {plan['question']}\n\n"
            f"{plan['reason']}"
        )
    return (
        "### Chart Director\n"
        f"**Question:** {plan['question']}\n\n"
        f"**Graph chosen:** {plan['title']}\n\n"
        f"**Why now:** {plan['reason']}"
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


def build_daily_brief_markdown(rows: list[dict[str, Any]], brief: str | None = None, model_used: str = "local rules") -> str:
    if not rows:
        return "### Today's Shop Pulse\nAdd a few entries, then ask Gemma for the day's pulse."
    text = brief or daily_brief_fallback(rows)
    return f"### Today's Shop Pulse\n{text}\n\n<small>Brief: {model_used}</small>"


def daily_brief_fallback(rows: list[dict[str, Any]]) -> str:
    metrics = compute_metrics(rows)
    currency = metrics["currency"]
    top_category, top_category_total = top_counter(rows, "category")
    queue = followup_rows(rows)
    if queue:
        lead_followup = f"{queue[0]['counterparty']} needs the first follow-up for {queue[0]['amount']}."
    else:
        lead_followup = "No urgent follow-up is waiting."
    return (
        f"{len(rows)} row(s) logged today. Net cash is {money(metrics['net_cash'], currency)}. "
        f"Money moved most through {top_category} ({money(top_category_total, currency)}). "
        f"{lead_followup}"
    )


def answer_ledger_question(rows: list[dict[str, Any]], question: str) -> str:
    text = question.strip().lower()
    if not rows:
        return "No ledger rows yet. Add a note, voice memo, or document first."
    if not text:
        return "Ask something like: who owes me most, what should I follow up today, or where did cash go?"

    currency = primary_currency(rows)
    if any(phrase in text for phrase in ("owe", "owes", "due", "who owes")):
        due_by_party: dict[str, float] = defaultdict(float)
        for row in rows:
            if row.get("payment_status") == "due":
                due_by_party[str(row.get("counterparty") or "Unknown")] += amount(row)
        if not due_by_party:
            return "No due items are open right now."
        party, total = max(due_by_party.items(), key=lambda item: item[1])
        return f"{party} owes the most: {money(total, currency)}."

    if any(phrase in text for phrase in ("follow up", "followup", "remind", "today")):
        queue = followup_rows(rows)
        if not queue:
            return "No follow-ups are waiting right now."
        first = queue[0]
        return f"Follow up with {first['counterparty']} first about {first['amount']} for {first['item']}. Suggested cadence: {first['cadence']}."

    if any(phrase in text for phrase in ("cash go", "spent", "expense", "cash out", "where did cash")):
        expenses = [row for row in rows if row.get("direction") == "expense"]
        if not expenses:
            return "No paid expenses are logged yet."
        top_category, total = top_counter(expenses, "category")
        return f"Cash went mostly to {top_category}: {money(total, currency)}."

    metrics = compute_metrics(rows)
    return (
        f"Ledger snapshot: {len(rows)} row(s), net cash {money(metrics['net_cash'], currency)}, "
        f"{money(metrics['due_income'], currency)} due, and {metrics['open_followups']} follow-up(s) open."
    )


COMMAND_ACTIONS = [
    "Show unpaid",
    "Draft WhatsApp follow-ups",
    "Find risky rows",
    "Summarize cash",
    "Prepare QuickBooks export",
]


def run_ledger_command(rows: list[dict[str, Any]], command: str) -> str:
    if not rows:
        return "### Command Palette\nAdd ledger rows first, then run a command."

    action = (command or "").strip() or COMMAND_ACTIONS[0]
    currency = primary_currency(rows)
    if action == "Show unpaid":
        due_rows = [row for row in rows if row.get("payment_status") == "due"]
        if not due_rows:
            return "### Unpaid\nNo unpaid rows are open."
        lines = [
            f"- **{row.get('counterparty') or 'Unknown'}** owes {money(amount(row), currency)} for {row.get('item') or 'ledger item'}."
            for row in due_rows[:8]
        ]
        return "### Unpaid\n" + "\n".join(lines)

    if action == "Draft WhatsApp follow-ups":
        queue = followup_rows(rows)
        if not queue:
            return "### WhatsApp Follow-ups\nNo follow-up messages are waiting."
        lines = [f"- **{item['counterparty']}**: {item['friendly_script']}" for item in queue[:6]]
        return "### WhatsApp Follow-ups\n" + "\n".join(lines)

    if action == "Find risky rows":
        risks = risk_flags(rows)
        reviews = review_rows(rows)
        lines = [f"- {risk}" for risk in risks]
        lines.extend(f"- Row {item['source_row']}: {item['issue']}." for item in reviews[:5])
        return "### Risk Scan\n" + ("\n".join(lines) if lines else "No obvious risks found.")

    if action == "Prepare QuickBooks export":
        lines = [
            "- Map `income` rows to Sales Receipt or Invoice import.",
            "- Map `expense` rows to Expense import.",
            "- Use `counterparty` as Customer/Vendor.",
            "- Use `category` as Account/Category.",
            "- Use `item`, `amount`, `date`, and `payment_status` as transaction details.",
            f"- Rows ready for review: **{len(rows)}**.",
        ]
        return "### QuickBooks Export Plan\n" + "\n".join(lines)

    metrics = compute_metrics(rows)
    return (
        "### Cash Summary\n"
        f"- Net cash: **{money(metrics['net_cash'], currency)}**\n"
        f"- Cash in: **{money(metrics['paid_income'], currency)}**\n"
        f"- Cash out: **{money(metrics['paid_expense'], currency)}**\n"
        f"- Still due: **{money(metrics['due_income'], currency)}**"
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
            "<div class='reply-grid'>"
            f"<code><span>Polite</span>{item['polite_script']}</code>"
            f"<code><span>Friendly</span>{item['friendly_script']}</code>"
            f"<code><span>Firm</span>{item['firm_script']}</code>"
            "</div>"
            "</div>"
        )
    return "\n".join(cards)


def build_review_markdown(rows: list[dict[str, Any]]) -> str:
    queue = review_rows(rows)
    if not rows:
        return "### Review Desk\nRows that need a human check will appear here."
    if not queue:
        return "### Review Desk\nNo low-confidence rows waiting. Export still deserves a quick glance."

    cards = ["### Review Desk"]
    for item in queue[:8]:
        cards.append(
            "<div class='review-card'>"
            f"<strong>Row {item['source_row']} · {item['issue']} · {item['confidence']}</strong>"
            f"<p>{item['counterparty']} · {item['item']} · {item['amount']}</p>"
            f"<code>{item['question']}</code>"
            "</div>"
        )
    return "\n".join(cards)


def timeline_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    events = []
    currency = primary_currency(rows)
    for index, row in enumerate(rows, start=1):
        value = amount(row)
        direction = row.get("direction") or "unknown"
        status = row.get("payment_status") or "unknown"
        party = row.get("counterparty") or "Unknown"
        item = row.get("item") or "ledger item"
        signed = value
        if direction == "expense":
            signed = -value
        elif status == "due":
            signed = 0
        badge = "Cash in" if direction == "income" and status == "paid" else "Cash out" if direction == "expense" else "Due" if status == "due" else "Logged"
        story = f"{badge}: {party} · {item} · {money(value, currency)}"
        events.append(
            {
                "source_row": index,
                "date": str(row.get("date") or date.today().isoformat()),
                "badge": badge,
                "direction": direction,
                "counterparty": party,
                "item": item,
                "amount": money(value, currency),
                "signed_amount": signed,
                "status": status,
                "story": story,
            }
        )
    return sorted(events, key=lambda event: (parse_row_date(event["date"]), event["source_row"]))


def build_timeline_markdown(rows: list[dict[str, Any]]) -> str:
    events = timeline_rows(rows)
    if not events:
        return "### Shop Pulse Timeline\nThe day's story appears after the first ledger entry."

    cards = ["### Shop Pulse Timeline", "<div class='timeline-rail'>"]
    for event in events[:12]:
        tone = "income" if event["direction"] == "income" else "expense" if event["direction"] == "expense" else "due"
        cards.append(
            f"<div class='timeline-card {tone}'>"
            f"<strong>Row {event['source_row']} · {event['badge']} · {event['date']}</strong>"
            f"<p>{event['counterparty']} · {event['item']}</p>"
            f"<code>{event['amount']} · {event['status']}</code>"
            "</div>"
        )
    cards.append("</div>")
    return "\n".join(cards)


def timeline_figure(rows: list[dict[str, Any]]) -> go.Figure:
    events = timeline_rows(rows)
    figure = base_figure("Shop pulse timeline", "Rows become the story of the day")
    if not events:
        return empty_figure()

    labels = [f"Row {event['source_row']}" for event in events]
    values = [event["signed_amount"] for event in events]
    colors = [
        PALETTE["green"] if event["direction"] == "income" and event["status"] == "paid"
        else PALETTE["red"] if event["direction"] == "expense"
        else PALETTE["gold"] if event["status"] == "due"
        else PALETTE["blue"]
        for event in events
    ]
    hover = [event["story"] for event in events]
    figure.add_trace(
        go.Bar(
            x=labels,
            y=values,
            marker={"color": colors},
            marker_line={"color": "rgba(243, 244, 236, 0.28)", "width": 1},
            text=[event["badge"] for event in events],
            textposition="auto",
            hovertext=hover,
            hovertemplate="%{hovertext}<extra></extra>",
        )
    )
    figure.add_hline(y=0, line_color="rgba(243, 244, 236, 0.28)", line_width=1)
    return figure


def build_tables(
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    return category_breakdown(rows), party_breakdown(rows), followup_rows(rows), review_rows(rows)


def base_figure(title: str, subtitle: str = "") -> go.Figure:
    figure = go.Figure()
    figure.update_layout(
        title={
            "text": title if not subtitle else f"{title}<br><sup>{subtitle}</sup>",
            "x": 0.02,
            "xanchor": "left",
            "font": {"size": 17, "color": PALETTE["ink"]},
        },
        paper_bgcolor=PALETTE["bg"],
        plot_bgcolor=PALETTE["plot"],
        font={"color": PALETTE["ink"], "family": "Inter, ui-sans-serif, system-ui, sans-serif", "size": 12},
        margin={"l": 48, "r": 24, "t": 78, "b": 48},
        height=350,
        legend={
            "orientation": "h",
            "y": -0.22,
            "x": 0,
            "font": {"color": PALETTE["muted"], "size": 11},
            "bgcolor": "rgba(8, 12, 18, 0)",
        },
        hoverlabel={
            "bgcolor": "#10151d",
            "bordercolor": "rgba(157, 177, 154, 0.32)",
            "font": {"color": PALETTE["ink"], "size": 12},
        },
        bargap=0.34,
        transition={"duration": 240, "easing": "cubic-in-out"},
    )
    figure.update_xaxes(
        gridcolor=PALETTE["grid"],
        zerolinecolor=PALETTE["grid"],
        linecolor="rgba(157, 177, 154, 0.22)",
        tickfont={"color": PALETTE["axis"], "size": 11},
        title_font={"color": PALETTE["muted"], "size": 11},
        ticks="outside",
        tickcolor="rgba(157, 177, 154, 0.22)",
    )
    figure.update_yaxes(
        gridcolor=PALETTE["grid"],
        zerolinecolor=PALETTE["grid"],
        linecolor="rgba(157, 177, 154, 0.22)",
        tickfont={"color": PALETTE["axis"], "size": 11},
        title_font={"color": PALETTE["muted"], "size": 11},
        ticks="outside",
        tickcolor="rgba(157, 177, 154, 0.22)",
    )
    return figure


def empty_figure() -> go.Figure:
    figure = base_figure("Ledger signal board", "Add a note to generate the first graph")
    figure.add_annotation(
        text="No rows yet",
        x=0.5,
        y=0.5,
        showarrow=False,
        font={"size": 24, "color": PALETTE["muted"]},
        xref="paper",
        yref="paper",
    )
    figure.update_xaxes(visible=False)
    figure.update_yaxes(visible=False)
    return figure


def due_by_party_figure(rows: list[dict[str, Any]]) -> go.Figure:
    currency = primary_currency(rows)
    totals: dict[str, float] = defaultdict(float)
    for row in rows:
        if row.get("payment_status") == "due":
            totals[str(row.get("counterparty") or "Unknown")] += amount(row)
    items = sorted(totals.items(), key=lambda item: item[1], reverse=True)[:8]
    figure = base_figure("Due radar", "Highest-value follow-ups first")
    if not items:
        return empty_figure()
    parties, values = zip(*items)
    figure.add_trace(
        go.Bar(
            x=list(values),
            y=list(parties),
            orientation="h",
            marker={"color": PALETTE["gold"], "line": {"color": "rgba(243, 244, 236, 0.22)", "width": 1}},
            opacity=0.94,
            text=[money(value, currency) for value in values],
            textposition="auto",
            hovertemplate="%{y}<br>%{text}<extra></extra>",
        )
    )
    figure.update_yaxes(autorange="reversed")
    return figure


def expense_category_figure(rows: list[dict[str, Any]]) -> go.Figure:
    currency = primary_currency(rows)
    totals: dict[str, float] = defaultdict(float)
    for row in rows:
        if row.get("direction") == "expense":
            totals[str(row.get("category") or "uncategorized")] += amount(row)
    items = sorted(totals.items(), key=lambda item: item[1], reverse=True)[:8]
    figure = base_figure("Spend pressure", "Expense categories ranked by amount")
    if not items:
        return empty_figure()
    categories, values = zip(*items)
    figure.add_trace(
        go.Bar(
            x=list(categories),
            y=list(values),
            marker={
                "color": [PALETTE["red"], PALETTE["gold"], PALETTE["blue"], PALETTE["violet"]] * 2,
                "line": {"color": "rgba(243, 244, 236, 0.22)", "width": 1},
            },
            opacity=0.94,
            text=[money(value, currency) for value in values],
            textposition="auto",
            hovertemplate="%{x}<br>%{text}<extra></extra>",
        )
    )
    return figure


def cashflow_figure(rows: list[dict[str, Any]]) -> go.Figure:
    currency = primary_currency(rows)
    income: dict[date, float] = defaultdict(float)
    expense: dict[date, float] = defaultdict(float)
    for row in rows:
        day = parse_row_date(row.get("date"))
        if row.get("direction") == "income" and row.get("payment_status") == "paid":
            income[day] += amount(row)
        if row.get("direction") == "expense" and row.get("payment_status") == "paid":
            expense[day] += amount(row)
    days = sorted(set(income) | set(expense))
    figure = base_figure("Cashflow trail", "Paid income and expenses by date")
    if not days:
        return empty_figure()
    labels = [day.isoformat() for day in days]
    income_values = [income[day] for day in days]
    expense_values = [-expense[day] for day in days]
    net_values = [income[day] - expense[day] for day in days]
    figure.add_trace(
        go.Bar(
            name="Cash in",
            x=labels,
            y=income_values,
            marker={"color": PALETTE["green"], "line": {"color": "rgba(243, 244, 236, 0.18)", "width": 1}},
            opacity=0.92,
        )
    )
    figure.add_trace(
        go.Bar(
            name="Cash out",
            x=labels,
            y=expense_values,
            marker={"color": PALETTE["red"], "line": {"color": "rgba(243, 244, 236, 0.18)", "width": 1}},
            opacity=0.92,
        )
    )
    figure.add_trace(
        go.Scatter(
            name="Net",
            x=labels,
            y=net_values,
            mode="lines+markers",
            line={"color": PALETTE["blue"], "width": 3},
            marker={"size": 9, "color": PALETTE["blue"], "line": {"color": PALETTE["bg"], "width": 2}},
            hovertemplate=f"%{{x}}<br>{currency} %{{y:,.0f}}<extra></extra>",
        )
    )
    figure.update_layout(barmode="relative")
    return figure


def confidence_review_figure(rows: list[dict[str, Any]]) -> go.Figure:
    figure = base_figure("Review queue", "Lower bars deserve a quick check")
    labels = [f"Row {index}" for index, _ in enumerate(rows, start=1)]
    values = [float(row.get("confidence") or 0) for row in rows]
    colors = [PALETTE["red"] if value < 0.6 else PALETTE["green"] for value in values]
    figure.add_trace(
        go.Bar(
            x=labels,
            y=values,
            marker={"color": colors, "line": {"color": "rgba(243, 244, 236, 0.22)", "width": 1}},
            opacity=0.94,
            text=[f"{value:.0%}" for value in values],
            textposition="auto",
            hovertext=[row.get("item") or "ledger item" for row in rows],
            hovertemplate="%{x}<br>%{hovertext}<br>%{text}<extra></extra>",
        )
    )
    figure.update_yaxes(range=[0, 1], tickformat=".0%")
    return figure


def category_mix_figure(rows: list[dict[str, Any]]) -> go.Figure:
    breakdown = category_breakdown(rows)
    figure = base_figure("Category mix", "A quick map of where money moved")
    if not breakdown:
        return empty_figure()
    figure.add_trace(
        go.Pie(
            labels=[item["category"] for item in breakdown[:8]],
            values=[item["total"] for item in breakdown[:8]],
            hole=0.55,
            marker={
                "colors": [PALETTE["green"], PALETTE["gold"], PALETTE["blue"], PALETTE["red"], PALETTE["violet"]],
                "line": {"color": PALETTE["bg"], "width": 2},
            },
            textinfo="label+percent",
            textfont={"color": PALETTE["ink"], "size": 12},
            hovertemplate="%{label}<br>%{value:,.0f}<extra></extra>",
        )
    )
    figure.update_xaxes(visible=False)
    figure.update_yaxes(visible=False)
    return figure


def party_exposure_figure(rows: list[dict[str, Any]]) -> go.Figure:
    currency = primary_currency(rows)
    totals: dict[str, float] = defaultdict(float)
    due: dict[str, float] = defaultdict(float)
    for row in rows:
        party = str(row.get("counterparty") or "Unknown")
        totals[party] += amount(row)
        if row.get("payment_status") == "due":
            due[party] += amount(row)
    items = sorted(totals.items(), key=lambda item: item[1], reverse=True)[:8]
    figure = base_figure("People ledger", "Total movement vs unpaid exposure")
    if not items:
        return empty_figure()
    parties = [party for party, _ in items]
    figure.add_trace(
        go.Bar(
            name="Total",
            x=parties,
            y=[totals[party] for party in parties],
            marker={"color": PALETTE["blue"], "line": {"color": "rgba(243, 244, 236, 0.18)", "width": 1}},
            opacity=0.92,
            hovertemplate=f"%{{x}}<br>{currency} %{{y:,.0f}} total<extra></extra>",
        )
    )
    figure.add_trace(
        go.Bar(
            name="Due",
            x=parties,
            y=[due[party] for party in parties],
            marker={"color": PALETTE["gold"], "line": {"color": "rgba(243, 244, 236, 0.18)", "width": 1}},
            opacity=0.92,
            hovertemplate=f"%{{x}}<br>{currency} %{{y:,.0f}} due<extra></extra>",
        )
    )
    figure.update_layout(barmode="group")
    return figure


def build_insight_figures(rows: list[dict[str, Any]]) -> tuple[go.Figure, go.Figure, go.Figure]:
    if not rows:
        empty = empty_figure()
        return empty, empty_figure(), empty_figure()

    plan = build_chart_plan(rows)
    primary_builders = {
        "due_by_party": due_by_party_figure,
        "expense_categories": expense_category_figure,
        "cashflow": cashflow_figure,
        "confidence_review": confidence_review_figure,
        "category_mix": category_mix_figure,
    }
    primary = primary_builders.get(plan["chart"], category_mix_figure)(rows)
    return primary, cashflow_figure(rows), party_exposure_figure(rows)
