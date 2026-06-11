from __future__ import annotations

import re
from datetime import date

from shop_ledger.schema import Direction, LedgerEntry, LedgerResult, PaymentStatus


AMOUNT_RE = re.compile(
    r"(?:(?:rs\.?|lkr|රු)\s*)?(\d[\d,]*(?:\.\d{1,2})?)", re.IGNORECASE
)
SPLIT_RE = re.compile(
    r"\s*(?:[.;\n]|,\s*(?=(?:paid|bought|sold|got|received|customer|supplier|owes|owe|due)\b))\s*",
    re.IGNORECASE,
)

CATEGORY_KEYWORDS = {
    "inventory": ("rice", "tea", "milk", "flour", "sugar", "packet", "bags", "stock", "goods"),
    "utilities": ("electric", "water", "wifi", "internet", "phone", "bill"),
    "rent": ("rent", "lease"),
    "wages": ("salary", "wage", "helper", "staff", "worker"),
    "transport": ("bus", "fuel", "petrol", "diesel", "delivery", "transport", "tuk"),
    "maintenance": ("repair", "fix", "paint", "clean", "replace"),
    "sales": ("sold", "sale", "customer", "received", "got"),
}

DUE_WORDS = ("owes", "owe", "due", "credit", "later", "unpaid", "balance")
PAID_WORDS = ("paid", "bought", "spent", "gave", "settled")
INCOME_WORDS = ("sold", "received", "got", "collected", "customer paid")


def heuristic_extract(note: str, currency: str = "LKR") -> LedgerResult:
    cleaned = " ".join(note.strip().split())
    if not cleaned:
        return LedgerResult(cleaned_note="", questions=["Add a note first."])

    parts = [part.strip(" ,") for part in SPLIT_RE.split(note) if part.strip(" ,")]
    entries: list[LedgerEntry] = []
    reminders: list[str] = []

    for part in parts:
        amount_match = AMOUNT_RE.search(part)
        amount = float(amount_match.group(1).replace(",", "")) if amount_match else 0.0
        lowered = part.lower()
        direction = infer_direction(lowered)
        status = infer_status(lowered, direction)
        counterparty = infer_counterparty(part)
        item = infer_item(part)
        category = infer_category(lowered, direction)
        reminder = infer_reminder(part, counterparty, amount, currency, status)

        if reminder:
            reminders.append(reminder)

        entries.append(
            LedgerEntry(
                date=date.today().isoformat(),
                direction=direction,
                counterparty=counterparty,
                item=item,
                amount=amount,
                currency=currency,
                category=category,
                payment_status=status,
                reminder=reminder,
                confidence=0.58 if amount else 0.34,
                original_note=part,
            )
        )

    questions = []
    if any(entry.amount == 0 for entry in entries):
        questions.append("Some rows have no amount. Ask the user to confirm the missing value.")
    if any(not entry.counterparty for entry in entries):
        questions.append("Some rows have no person or business name.")

    return LedgerResult(
        entries=entries,
        reminders=reminders,
        questions=questions,
        cleaned_note=cleaned,
        model_used="heuristic",
    )


def infer_direction(text: str) -> Direction:
    if any(word in text for word in INCOME_WORDS):
        return Direction.income
    if any(word in text for word in PAID_WORDS):
        return Direction.expense
    if any(word in text for word in DUE_WORDS):
        return Direction.income
    return Direction.unknown


def infer_status(text: str, direction: Direction) -> PaymentStatus:
    if any(word in text for word in DUE_WORDS):
        return PaymentStatus.due
    if direction in (Direction.expense, Direction.income):
        return PaymentStatus.paid
    return PaymentStatus.unknown


def infer_category(text: str, direction: Direction) -> str:
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            return category
    if direction == Direction.income:
        return "sales"
    if direction == Direction.expense:
        return "general expense"
    return "uncategorized"


def infer_counterparty(text: str) -> str:
    patterns = [
        r"\b(?:paid|gave|from|to|customer|supplier)\s+([A-Z][A-Za-z.'-]+)",
        r"\b([A-Z][A-Za-z.'-]+)\s+(?:owes|paid|gave|bought|sold)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()
    return ""


def infer_item(text: str) -> str:
    without_amount = AMOUNT_RE.sub("", text)
    match = re.search(r"\bfor\s+(.+)$", without_amount, re.IGNORECASE)
    if match:
        return cleanup_item(match.group(1))
    for phrase in ("bought", "sold", "paid", "received"):
        match = re.search(rf"\b{phrase}\b\s+(.+)$", without_amount, re.IGNORECASE)
        if match:
            return cleanup_item(match.group(1))
    return cleanup_item(without_amount)


def cleanup_item(text: str) -> str:
    cleaned = re.sub(r"\b(?:rs\.?|lkr|paid|gave|from|to|customer|supplier)\b", "", text, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,-")
    return cleaned[:80]


def infer_reminder(
    text: str,
    counterparty: str,
    amount: float,
    currency: str,
    status: PaymentStatus,
) -> str:
    if status != PaymentStatus.due:
        if "remind" not in text.lower():
            return ""

    who = counterparty or "the customer"
    amount_text = f"{currency} {amount:,.0f}" if amount else "the amount"
    return f"Follow up with {who} about {amount_text}."
