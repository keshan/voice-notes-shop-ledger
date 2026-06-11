from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from shop_ledger.heuristics import heuristic_extract
from shop_ledger.schema import LedgerResult


SYSTEM_PROMPT = """You turn messy shopkeeper notes into a clean ledger.
Return only valid JSON with this exact shape:
{
  "entries": [
    {
      "date": "YYYY-MM-DD or empty",
      "direction": "expense|income|transfer|unknown",
      "counterparty": "person or business",
      "item": "what changed hands",
      "quantity": "quantity if known",
      "amount": 0,
      "currency": "LKR",
      "category": "inventory|utilities|rent|wages|transport|maintenance|sales|general expense|uncategorized",
      "payment_status": "paid|due|partial|unknown",
      "due_date": "",
      "reminder": "short follow-up reminder or empty",
      "confidence": 0.0,
      "original_note": "source fragment"
    }
  ],
  "reminders": ["short reminders"],
  "questions": ["only ask if an amount, person, or due date is unclear"],
  "cleaned_note": "normalized note"
}
Use the user's currency. Do not invent amounts. Split multiple transactions into multiple entries."""


class LlamaLedgerBackend:
    def __init__(
        self,
        model_path: str | None = None,
        n_ctx: int = 4096,
        n_threads: int | None = None,
        n_gpu_layers: int = 0,
    ) -> None:
        self.model_path = model_path or os.getenv("LLAMA_GGUF_PATH", "")
        self.n_ctx = n_ctx
        self.n_threads = n_threads or max(2, (os.cpu_count() or 4) - 1)
        self.n_gpu_layers = n_gpu_layers
        self._llm: Any | None = None

    @property
    def available(self) -> bool:
        return bool(self.model_path and Path(self.model_path).exists())

    def load(self) -> None:
        if self._llm is not None:
            return
        if not self.available:
            raise FileNotFoundError(f"GGUF model not found: {self.model_path}")

        from llama_cpp import Llama

        self._llm = Llama(
            model_path=self.model_path,
            n_ctx=self.n_ctx,
            n_threads=self.n_threads,
            n_gpu_layers=self.n_gpu_layers,
            verbose=False,
        )

    def extract(self, note: str, currency: str = "LKR") -> LedgerResult:
        if not self.available:
            return heuristic_extract(note, currency=currency)

        self.load()
        assert self._llm is not None

        response = self._llm.create_chat_completion(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Currency: {currency}\nNote:\n{note}"},
            ],
            max_tokens=900,
            temperature=0.1,
            top_p=0.9,
        )
        text = response["choices"][0]["message"]["content"]
        data = parse_json_object(text)
        result = LedgerResult.model_validate(data)
        result.model_used = Path(self.model_path).name
        return result


def parse_json_object(text: str) -> dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        raise ValueError(f"Model did not return JSON: {text[:240]}")
    return json.loads(match.group(0))
