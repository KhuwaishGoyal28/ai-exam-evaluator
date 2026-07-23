"""
Groq Vision calls for OCR.
Uses qwen/qwen3.6-27b via Groq's OpenAI-compatible API.

Free-tier limits (on-demand):
  - 8,000 tokens per minute (TPM)
  - A single high-res scanned page encodes to ~1,500–2,500 tokens as JPEG

Strategy to stay within limits:
  - Compress each page image to ≤ 800px wide, JPEG quality 60
    → roughly 800–1,200 tokens per image
  - Send ONE page per request (never batch)
  - Wait 8 seconds between pages so TPM resets
    (8 s gap × ~1,200 tokens ≤ 8,000 TPM budget with headroom)

Public API:
  extract_text_via_vision(image_bytes)  — single image → transcribed text
  extract_text_from_pdf(pdf_bytes)      — multi-page PDF → full transcription
"""
from __future__ import annotations

import asyncio
import base64
import io
from openai import AsyncOpenAI
from PIL import Image

from app.config import get_settings
from app.core.exceptions import OCRExtractionError, ExternalServiceError
from app.core.logging import get_logger

logger = get_logger(__name__)

_GROQ_BASE_URL = "https://api.groq.com/openai/v1"

# Seconds to wait between successive Groq Vision calls to respect 8k TPM limit
_PAGE_DELAY_SECONDS = 8

# Max width (px) to resize images before encoding — keeps token count low
_MAX_IMAGE_WIDTH = 800

# JPEG quality for OCR — 60 is enough for text legibility, saves ~40% tokens
_JPEG_QUALITY = 60

_OCR_SYSTEM = (
    "You are a precise OCR engine processing a handwritten exam answer sheet. "
    "Transcribe EVERY word exactly as written, including spelling mistakes. "
    "Preserve paragraph breaks with a blank line between paragraphs. "
    "Do NOT correct spelling, grammar, or content. "
    "Output only the transcribed text — no commentary, no markdown, no headers."
)


# ── Public API ────────────────────────────────────────────────────────────────

async def extract_text_via_vision(image_bytes: bytes) -> str:
    """Send a single image to Groq Vision and return transcribed text."""
    compressed = _compress_image(image_bytes)
    b64 = base64.b64encode(compressed).decode()
    content = [
        {
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
        },
        {"type": "text", "text": "Transcribe all text from this answer sheet page."},
    ]
    return await _call_groq_vision(content)


async def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """
    Extract text from every page of a PDF by sending each page individually
    to Groq Vision with a delay between calls to respect the TPM limit.
    Works for any number of pages.
    """
    page_images = _render_pdf_to_images(pdf_bytes)

    if not page_images:
        logger.warning("ocr_pdf_render_failed_fallback_single_call")
        # Last resort: try sending the first embedded image directly
        return await extract_text_via_vision(pdf_bytes)

    logger.info("ocr_pdf_pages_found", count=len(page_images))
    page_texts: list[str] = []

    for page_num, img_bytes in enumerate(page_images):
        if page_num > 0:
            # Respect Groq's 8k TPM limit — wait between pages
            logger.info("ocr_page_delay", page=page_num, wait_s=_PAGE_DELAY_SECONDS)
            await asyncio.sleep(_PAGE_DELAY_SECONDS)

        compressed = _compress_image(img_bytes)
        b64 = base64.b64encode(compressed).decode()
        content = [
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
            },
            {
                "type": "text",
                "text": (
                    f"This is page {page_num + 1} of {len(page_images)} of a "
                    "handwritten exam answer sheet. "
                    "Transcribe every word exactly as written."
                ),
            },
        ]
        try:
            text = await _call_groq_vision(content)
            page_texts.append(text)
            logger.info("ocr_page_done", page=page_num + 1, chars=len(text))
        except ExternalServiceError as exc:
            # If one page fails (e.g. still rate-limited), log and continue
            logger.error("ocr_page_failed", page=page_num + 1, error=str(exc))
            page_texts.append(f"[Page {page_num + 1} could not be transcribed]")

    return "\n\n--- PAGE BREAK ---\n\n".join(page_texts)


# ── Core Groq call ────────────────────────────────────────────────────────────

async def _call_groq_vision(user_content: list[dict]) -> str:
    """Single Groq Vision API call. Raises ExternalServiceError on failure."""
    settings = get_settings()
    client = AsyncOpenAI(
        api_key=settings.groq_api_key,
        base_url=_GROQ_BASE_URL,
    )

    try:
        response = await client.chat.completions.create(
            model=settings.groq_vision_model,
            max_tokens=settings.groq_vision_max_tokens,
            messages=[
                {"role": "system", "content": _OCR_SYSTEM},
                {"role": "user",   "content": user_content},
            ],
        )
        text = (response.choices[0].message.content or "").strip()
        if not text:
            raise OCRExtractionError("Groq Vision returned empty text.")
        return text
    except OCRExtractionError:
        raise
    except Exception as exc:
        logger.error("groq_vision_failed", error=str(exc))
        raise ExternalServiceError(f"Groq Vision call failed: {exc}") from exc


# ── Image compression ─────────────────────────────────────────────────────────

def _compress_image(image_bytes: bytes) -> bytes:
    """
    Resize image to _MAX_IMAGE_WIDTH (preserving aspect ratio) and re-encode
    as JPEG at _JPEG_QUALITY. Reduces token usage dramatically while keeping
    text legible for OCR.
    """
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        w, h = img.size
        if w > _MAX_IMAGE_WIDTH:
            ratio = _MAX_IMAGE_WIDTH / w
            img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=_JPEG_QUALITY)
        compressed = buf.getvalue()
        logger.info(
            "image_compressed",
            original_bytes=len(image_bytes),
            compressed_bytes=len(compressed),
        )
        return compressed
    except Exception as exc:
        logger.warning("image_compress_failed", error=str(exc))
        return image_bytes  # return original on failure


# ── PDF → JPEG page images ────────────────────────────────────────────────────

def _render_pdf_to_images(pdf_bytes: bytes) -> list[bytes]:
    """
    Convert each page of a PDF to raw JPEG bytes.
    Tries three strategies in order:
      1. Extract embedded XObject images (scanned PDFs — fastest)
      2. Rasterise with pdf2image / poppler
      3. Rasterise with PyMuPDF (fitz)
    Returns empty list only when all three fail.
    """
    images = _extract_embedded_images(pdf_bytes)
    if images:
        return images

    images = _rasterise_with_pdf2image(pdf_bytes)
    if images:
        return images

    return _rasterise_with_pymupdf(pdf_bytes)


def _extract_embedded_images(pdf_bytes: bytes) -> list[bytes]:
    """Pull the first embedded XObject image from each page via pypdf."""
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(pdf_bytes))
        result: list[bytes] = []

        for page in reader.pages:
            resources = page.get("/Resources")
            if not resources:
                continue
            xobjs = resources.get("/XObject")
            if not xobjs:
                continue
            for key in xobjs:
                obj = xobjs[key]
                if obj.get("/Subtype") != "/Image":
                    continue
                try:
                    img = Image.open(io.BytesIO(obj.get_data())).convert("RGB")
                    buf = io.BytesIO()
                    img.save(buf, format="JPEG", quality=90)
                    result.append(buf.getvalue())
                    break  # one image per page
                except Exception:
                    continue

        if result:
            logger.info("pdf_embedded_images_extracted", pages=len(result))
        return result
    except Exception as exc:
        logger.warning("pdf_extract_embedded_failed", error=str(exc))
        return []


def _rasterise_with_pdf2image(pdf_bytes: bytes) -> list[bytes]:
    """Rasterise PDF pages using pdf2image (requires poppler on PATH)."""
    try:
        from pdf2image import convert_from_bytes

        pil_images = convert_from_bytes(pdf_bytes, dpi=120, fmt="jpeg")
        result: list[bytes] = []
        for img in pil_images:
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=85)
            result.append(buf.getvalue())
        logger.info("pdf_rasterised_pdf2image", pages=len(result))
        return result
    except ImportError:
        return []
    except Exception as exc:
        logger.warning("pdf2image_failed", error=str(exc))
        return []


def _rasterise_with_pymupdf(pdf_bytes: bytes) -> list[bytes]:
    """Rasterise PDF pages using PyMuPDF (fitz)."""
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        result: list[bytes] = []
        for page in doc:
            mat = fitz.Matrix(120 / 72, 120 / 72)  # 120 dpi — lower than before
            pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
            result.append(pix.tobytes("jpeg"))
        doc.close()
        logger.info("pdf_rasterised_pymupdf", pages=len(result))
        return result
    except ImportError:
        return []
    except Exception as exc:
        logger.warning("pymupdf_failed", error=str(exc))
        return []


def _detect_mime(data: bytes) -> str:
    if data[:3] == b"\xff\xd8\xff":       return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":  return "image/png"
    if data[:4] in (b"RIFF", b"WEBP"):    return "image/webp"
    return "image/jpeg"
