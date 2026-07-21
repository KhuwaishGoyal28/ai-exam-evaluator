"""
OpenAI Vision calls for OCR.
Two public functions — each does exactly one thing:

  extract_text_via_vision(image_bytes)  — JPEG/PNG bytes → transcribed text
  extract_text_from_pdf(pdf_bytes)      — PDF bytes → transcribed text

GPT-4o-mini accepts base64 image URLs and PDF data natively.
"""
from __future__ import annotations

import base64
from openai import AsyncOpenAI

from app.config import get_settings
from app.core.exceptions import OCRExtractionError, ExternalServiceError
from app.core.logging import get_logger

logger = get_logger(__name__)

_OCR_SYSTEM = (
    "You are a precise OCR engine processing an exam answer sheet. "
    "Transcribe EVERY word from ALL pages exactly as written. "
    "For handwritten text: preserve paragraph breaks with blank lines. "
    "For multi-page documents: separate pages with '--- PAGE BREAK ---'. "
    "Do NOT correct spelling, grammar, or content. "
    "Output only the transcribed text — no commentary, no markdown."
)


async def extract_text_via_vision(image_bytes: bytes) -> str:
    """Send a JPEG/PNG image to GPT-4o Vision and return transcribed text."""
    mime = _detect_mime(image_bytes)
    b64  = base64.b64encode(image_bytes).decode()
    return await _call_vision_api([
        {
            "type":      "image_url",
            "image_url": {"url": f"data:{mime};base64,{b64}", "detail": "high"},
        },
        {"type": "text", "text": "Transcribe all text from this answer sheet."},
    ])


async def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Send a PDF to GPT-4o Vision as base64 and return transcribed text."""
    b64 = base64.b64encode(pdf_bytes).decode()
    return await _call_vision_api([
        {
            "type":      "image_url",
            "image_url": {"url": f"data:application/pdf;base64,{b64}", "detail": "high"},
        },
        {"type": "text", "text": "Transcribe all text from all pages of this answer sheet."},
    ])


async def _call_vision_api(user_content: list[dict]) -> str:
    """Core OpenAI Vision call. Single responsibility: call + validate response."""
    settings = get_settings()
    client   = AsyncOpenAI(api_key=settings.openai_api_key)

    try:
        response = await client.chat.completions.create(
            model=settings.openai_vision_model,
            max_tokens=settings.openai_max_tokens,
            messages=[
                {"role": "system", "content": _OCR_SYSTEM},
                {"role": "user",   "content": user_content},
            ],
        )
        text = (response.choices[0].message.content or "").strip()
        if not text:
            raise OCRExtractionError("GPT-4o Vision returned empty text.")
        return text
    except OCRExtractionError:
        raise
    except Exception as exc:
        logger.error("openai_vision_failed", error=str(exc))
        raise ExternalServiceError(f"OpenAI Vision call failed: {exc}") from exc


def _detect_mime(data: bytes) -> str:
    if data[:3] == b"\xff\xd8\xff":      return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n": return "image/png"
    if data[:4] in (b"RIFF", b"WEBP"):   return "image/webp"
    return "image/jpeg"
