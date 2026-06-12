from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from shop_ledger.heuristics import heuristic_extract
from shop_ledger.schema import LedgerResult


SYSTEM_PROMPT = """You turn messy shopkeeper notes, receipts, bills, and ledger images into a clean ledger.
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
Use the user's currency. Do not invent amounts. Split multiple transactions into multiple entries.
For images, read visible receipt/bill/note text and infer only clear ledger facts."""


class LlamaLedgerBackend:
    def __init__(
        self,
        model_path: str | None = None,
        n_ctx: int | None = None,
        n_threads: int | None = None,
        n_gpu_layers: int | None = None,
    ) -> None:
        self.model_path = model_path or os.getenv("LLAMA_GGUF_PATH", "")
        self.model_label = os.getenv("LLAMA_MODEL_LABEL", "").strip() or self._default_model_label()
        self.n_ctx = n_ctx or int(os.getenv("LLAMA_N_CTX", "4096"))
        self.n_threads = n_threads or max(2, (os.cpu_count() or 4) - 1)
        self.n_gpu_layers = n_gpu_layers if n_gpu_layers is not None else int(os.getenv("LLAMA_N_GPU_LAYERS", "0"))
        self._llm: Any | None = None

    def _default_model_label(self) -> str:
        model_file = Path(self.model_path).name if self.model_path else "GGUF model"
        return f"llama.cpp / {model_file}"

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

    def extract(self, note: str, currency: str = "LKR", image_urls: list[str] | None = None) -> LedgerResult:
        if not self.available:
            return heuristic_extract(note, currency=currency)

        self.load()
        assert self._llm is not None
        image_urls = image_urls or []
        user_content: str | list[dict[str, Any]]
        prompt = f"Currency: {currency}\nNote or document context:\n{note or 'Read the uploaded document image(s).'}"
        if image_urls:
            user_content = [{"type": "text", "text": prompt}]
            user_content.extend({"type": "image_url", "image_url": {"url": image_url}} for image_url in image_urls)
        else:
            user_content = prompt

        response = self._llm.create_chat_completion(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            max_tokens=900,
            temperature=0.1,
            top_p=0.9,
        )
        text = response["choices"][0]["message"]["content"]
        data = parse_json_object(text)
        result = LedgerResult.model_validate(data)
        result.model_used = self.model_label
        return result

    def daily_brief(self, rows: list[dict[str, Any]], currency: str = "LKR") -> str:
        if not self.available:
            return ""

        self.load()
        assert self._llm is not None

        response = self._llm.create_chat_completion(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You write a short shopkeeper daily brief from structured ledger rows. "
                        "Be specific, practical, and under 80 words. Mention cash position, dues, "
                        "largest pressure, and the next follow-up when relevant."
                    ),
                },
                {"role": "user", "content": f"Currency: {currency}\nRows JSON:\n{json.dumps(rows, ensure_ascii=True)}"},
            ],
            max_tokens=180,
            temperature=0.3,
            top_p=0.9,
        )
        return str(response["choices"][0]["message"]["content"]).strip()

    def answer_ledger_question(self, rows: list[dict[str, Any]], question: str, currency: str = "LKR") -> str:
        if not self.available:
            return ""

        self.load()
        assert self._llm is not None

        response = self._llm.create_chat_completion(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Answer questions about a small shop ledger using only the provided structured rows. "
                        "Be concise, practical, and mention amounts/counterparties when relevant. "
                        "If the rows do not contain the answer, say what is missing."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Currency: {currency}\nQuestion: {question}\nRows JSON:\n"
                        f"{json.dumps(rows, ensure_ascii=True)}"
                    ),
                },
            ],
            max_tokens=220,
            temperature=0.2,
            top_p=0.9,
        )
        return str(response["choices"][0]["message"]["content"]).strip()

    def choose_chart_spec(self, rows: list[dict[str, Any]], question: str, allowed_charts: dict[str, str]) -> dict[str, str]:
        if not self.available:
            return {}

        self.load()
        assert self._llm is not None

        response = self._llm.create_chat_completion(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Choose the best chart for a small shop ledger question. "
                        "Return only JSON with keys chart and reason. "
                        f"Allowed chart ids: {', '.join(allowed_charts)}."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Question: {question}\nAllowed charts: {json.dumps(allowed_charts, ensure_ascii=True)}\n"
                        f"Rows JSON:\n{json.dumps(rows, ensure_ascii=True)}"
                    ),
                },
            ],
            max_tokens=160,
            temperature=0.1,
            top_p=0.9,
        )
        data = parse_json_object(str(response["choices"][0]["message"]["content"]))
        return {"chart": str(data.get("chart") or ""), "reason": str(data.get("reason") or "")}


def parse_json_object(text: str) -> dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        raise ValueError(f"Model did not return JSON: {text[:240]}")
    return json.loads(match.group(0))
