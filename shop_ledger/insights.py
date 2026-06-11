from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from typing import Any

import plotly.graph_objects as go


PALETTE = {
    "bg": "rgba(8, 12, 18, 0)",
    "grid": "rgba(157, 177, 154, 0.18)",
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


def build_tables(
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    return category_breakdown(rows), party_breakdown(rows), followup_rows(rows), review_rows(rows)


def base_figure(title: str, subtitle: str = "") -> go.Figure:
    figure = go.Figure()
    figure.update_layout(
        title={"text": title if not subtitle else f"{title}<br><sup>{subtitle}</sup>", "x": 0.02, "xanchor": "left"},
        paper_bgcolor=PALETTE["bg"],
        plot_bgcolor="rgba(11, 16, 23, 0.72)",
        font={"color": PALETTE["ink"], "family": "Inter, ui-sans-serif, system-ui, sans-serif"},
        margin={"l": 42, "r": 22, "t": 74, "b": 44},
        height=326,
        legend={"orientation": "h", "y": -0.24, "x": 0},
    )
    figure.update_xaxes(gridcolor=PALETTE["grid"], zerolinecolor=PALETTE["grid"])
    figure.update_yaxes(gridcolor=PALETTE["grid"], zerolinecolor=PALETTE["grid"])
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
            marker={"color": PALETTE["gold"]},
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
            marker={"color": [PALETTE["red"], PALETTE["gold"], PALETTE["blue"], PALETTE["violet"]] * 2},
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
    figure.add_trace(go.Bar(name="Cash in", x=labels, y=income_values, marker={"color": PALETTE["green"]}))
    figure.add_trace(go.Bar(name="Cash out", x=labels, y=expense_values, marker={"color": PALETTE["red"]}))
    figure.add_trace(
        go.Scatter(
            name="Net",
            x=labels,
            y=net_values,
            mode="lines+markers",
            line={"color": PALETTE["blue"], "width": 3},
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
            marker={"color": colors},
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
            marker={"colors": [PALETTE["green"], PALETTE["gold"], PALETTE["blue"], PALETTE["red"], PALETTE["violet"]]},
            textinfo="label+percent",
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
            marker={"color": PALETTE["blue"]},
            hovertemplate=f"%{{x}}<br>{currency} %{{y:,.0f}} total<extra></extra>",
        )
    )
    figure.add_trace(
        go.Bar(
            name="Due",
            x=parties,
            y=[due[party] for party in parties],
            marker={"color": PALETTE["gold"]},
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
