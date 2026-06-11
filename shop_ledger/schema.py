from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class Direction(str, Enum):
    expense = "expense"
    income = "income"
    transfer = "transfer"
    unknown = "unknown"


class PaymentStatus(str, Enum):
    paid = "paid"
    due = "due"
    partial = "partial"
    unknown = "unknown"


class LedgerEntry(BaseModel):
    date: str = Field(default_factory=lambda: date.today().isoformat())
    direction: Direction = Direction.unknown
    counterparty: str = ""
    item: str = ""
    quantity: str = ""
    amount: float = 0.0
    currency: str = "LKR"
    category: str = "uncategorized"
    payment_status: PaymentStatus = PaymentStatus.unknown
    due_date: str = ""
    reminder: str = ""
    confidence: float = 0.5
    original_note: str = ""

    @field_validator(
        "date",
        "counterparty",
        "item",
        "quantity",
        "currency",
        "category",
        "due_date",
        "reminder",
        "original_note",
        mode="before",
    )
    @classmethod
    def parse_optional_text(cls, value: Any) -> str:
        if value is None:
            return ""
        return str(value)

    @field_validator("amount", mode="before")
    @classmethod
    def parse_amount(cls, value: Any) -> float:
        if value in (None, ""):
            return 0.0
        if isinstance(value, (int, float)):
            return float(value)
        cleaned = str(value).replace(",", "").strip()
        try:
            return float(cleaned)
        except ValueError:
            return 0.0

    @field_validator("confidence", mode="before")
    @classmethod
    def clamp_confidence(cls, value: Any) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return 0.5
        return max(0.0, min(1.0, number))


class LedgerResult(BaseModel):
    entries: list[LedgerEntry] = Field(default_factory=list)
    reminders: list[str] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)
    cleaned_note: str = ""
    model_used: str = "heuristic"

    def as_rows(self) -> list[dict[str, Any]]:
        return [entry.model_dump(mode="json") for entry in self.entries]
