from __future__ import annotations

import os
from pathlib import Path

from shop_ledger.heuristics import heuristic_extract
from shop_ledger.llama_backend import LlamaLedgerBackend
from shop_ledger.schema import LedgerResult


class LedgerProcessor:
    def __init__(self, mode: str = "mock", model_path: str | None = None) -> None:
        self.mode = mode
        self.backend = LlamaLedgerBackend(model_path=model_path)

    @classmethod
    def from_env(cls) -> "LedgerProcessor":
        mode = os.getenv("LEDGER_MODEL_MODE", "mock").strip().lower()
        return cls(mode=mode, model_path=os.getenv("LLAMA_GGUF_PATH"))

    def process(self, note: str, currency: str = "LKR") -> LedgerResult:
        if self.mode == "llama":
            if not self.backend.available:
                fallback = heuristic_extract(note, currency=currency)
                fallback.model_used = "heuristic fallback (missing GGUF model)"
                fallback.questions.append("No GGUF model was found, so heuristics were used.")
                return fallback
            try:
                return self.backend.extract(note, currency=currency)
            except Exception as exc:
                fallback = heuristic_extract(note, currency=currency)
                fallback.model_used = f"heuristic fallback ({type(exc).__name__})"
                fallback.questions.append(f"The llama.cpp model was unavailable, so heuristics were used: {exc}")
                return fallback
        result = heuristic_extract(note, currency=currency)
        result.model_used = "mock heuristic"
        return result


def transcribe_audio(audio_path: str | None) -> str:
    if not audio_path:
        return ""

    path = Path(audio_path)
    if not path.exists():
        return ""

    try:
        from faster_whisper import WhisperModel
    except Exception:
        return ""

    size = os.getenv("WHISPER_MODEL_SIZE", "tiny")
    model = WhisperModel(size, device="cpu", compute_type="int8")
    segments, _ = model.transcribe(str(path), beam_size=3)
    return " ".join(segment.text.strip() for segment in segments).strip()
