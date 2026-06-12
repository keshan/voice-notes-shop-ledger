from __future__ import annotations

import os
import base64
from io import BytesIO
from pathlib import Path
from typing import Any

from shop_ledger.heuristics import heuristic_extract
from shop_ledger.insights import CHART_SPECS, answer_ledger_question, chart_spec_from_question, daily_brief_fallback
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

    def process(self, note: str, currency: str = "LKR", image_urls: list[str] | None = None) -> LedgerResult:
        if self.mode == "llama":
            if not self.backend.available:
                fallback = heuristic_extract(note, currency=currency)
                fallback.model_used = "heuristic fallback (missing GGUF model)"
                fallback.questions.append("No GGUF model was found, so heuristics were used.")
                if image_urls:
                    fallback.questions.append("Document images need the multimodal GGUF model.")
                return fallback
            try:
                return self.backend.extract(note, currency=currency, image_urls=image_urls)
            except Exception as exc:
                fallback = heuristic_extract(note, currency=currency)
                fallback.model_used = f"heuristic fallback ({type(exc).__name__})"
                fallback.questions.append(f"The llama.cpp model was unavailable, so heuristics were used: {exc}")
                if image_urls:
                    fallback.questions.append("Document images were not analyzed because multimodal inference failed.")
                return fallback
        result = heuristic_extract(note, currency=currency)
        result.model_used = "mock heuristic"
        if image_urls:
            result.questions.append("Document images need llama.cpp multimodal mode; mock mode only reads extracted text.")
        return result

    def daily_brief(self, rows: list[dict[str, Any]], currency: str = "LKR") -> dict[str, str]:
        if not rows:
            return {"brief": "Add a few entries, then ask Gemma for the day's pulse.", "model_used": "local rules"}
        if self.mode == "llama" and self.backend.available:
            try:
                brief = self.backend.daily_brief(rows, currency=currency)
                if brief:
                    return {"brief": brief, "model_used": Path(self.backend.model_path).name}
            except Exception as exc:
                return {
                    "brief": daily_brief_fallback(rows),
                    "model_used": f"local rules fallback ({type(exc).__name__})",
                }
        return {"brief": daily_brief_fallback(rows), "model_used": "local rules"}

    def ask_ledger(self, rows: list[dict[str, Any]], question: str, currency: str = "LKR") -> dict[str, str]:
        fallback = answer_ledger_question(rows, question)
        if self.mode == "llama" and self.backend.available and rows and question.strip():
            try:
                answer = self.backend.answer_ledger_question(rows, question, currency=currency)
                if answer:
                    return {"answer": answer, "model_used": Path(self.backend.model_path).name}
            except Exception as exc:
                return {"answer": fallback, "model_used": f"local rules fallback ({type(exc).__name__})"}
        return {"answer": fallback, "model_used": "local rules"}

    def choose_chart(self, rows: list[dict[str, Any]], question: str) -> dict[str, str]:
        fallback = chart_spec_from_question(rows, question)
        if self.mode == "llama" and self.backend.available and rows:
            try:
                spec = self.backend.choose_chart_spec(rows, question, CHART_SPECS)
                if spec.get("chart") in CHART_SPECS:
                    spec["model_used"] = Path(self.backend.model_path).name
                    return spec
            except Exception as exc:
                fallback["model_used"] = f"local rules fallback ({type(exc).__name__})"
                return fallback
        return fallback


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


def prepare_document_input(document_path: Any, max_pages: int = 3) -> dict[str, Any]:
    path = normalize_document_path(document_path)
    if not path or not path.exists():
        return {"text": "", "image_urls": [], "page_count": 0, "kind": "missing"}

    suffix = path.suffix.lower()
    if suffix in {".txt", ".csv", ".md"}:
        return {
            "text": path.read_text(encoding="utf-8", errors="ignore").strip(),
            "image_urls": [],
            "page_count": 1,
            "kind": "text",
        }
    if suffix == ".pdf":
        return prepare_pdf_input(path, max_pages=max_pages)
    if suffix in {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp"}:
        return {"text": "", "image_urls": [image_file_to_data_url(path)], "page_count": 1, "kind": "image"}
    return {"text": "", "image_urls": [], "page_count": 0, "kind": "unsupported"}


def extract_document_text(document_path: Any) -> str:
    return str(prepare_document_input(document_path).get("text") or "")


def normalize_document_path(document_path: Any) -> Path | None:
    if not document_path:
        return None
    if isinstance(document_path, (list, tuple)):
        if not document_path:
            return None
        return normalize_document_path(document_path[0])
    if isinstance(document_path, dict):
        value = document_path.get("path") or document_path.get("name")
        return Path(value) if value else None
    value = getattr(document_path, "name", document_path)
    return Path(str(value)) if value else None


def prepare_pdf_input(path: Path, max_pages: int = 3) -> dict[str, Any]:
    try:
        import fitz
    except Exception:
        return {"text": "", "image_urls": [], "page_count": 0, "kind": "pdf"}

    chunks = []
    image_urls = []
    with fitz.open(path) as document:
        page_indexes = range(min(len(document), max_pages))
        for page_index in page_indexes:
            page = document[page_index]
            text = page.get_text("text").strip()
            if text:
                chunks.append(text)

        for page_index in page_indexes:
            page = document[page_index]
            pixmap = page.get_pixmap(dpi=180)
            image_urls.append(bytes_to_data_url(pixmap.tobytes("png"), "image/png"))

    return {"text": "\n".join(chunks).strip(), "image_urls": image_urls, "page_count": len(image_urls), "kind": "pdf"}


def image_file_to_data_url(path: Path) -> str:
    try:
        from PIL import Image
    except Exception:
        mime = mime_for_path(path)
        return bytes_to_data_url(path.read_bytes(), mime)

    with Image.open(path) as image:
        image.thumbnail((1600, 1600))
        buffer = BytesIO()
        image.convert("RGB").save(buffer, format="JPEG", quality=88)
    return bytes_to_data_url(buffer.getvalue(), "image/jpeg")


def bytes_to_data_url(data: bytes, mime: str) -> str:
    encoded = base64.b64encode(data).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def mime_for_path(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".webp":
        return "image/webp"
    if suffix in {".tif", ".tiff"}:
        return "image/tiff"
    if suffix == ".bmp":
        return "image/bmp"
    return "image/png"
