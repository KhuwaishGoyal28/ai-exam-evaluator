"""
Extracts individual page images from a PDF or a single image file.
Single responsibility: UploadedFile → list[Pillow.Image].

For PDFs:
  - Try embedded XObject images per page first (fast, pure-Python).
  - Fall back to rendering a white A4 canvas with the page's extracted text.
For images:
  - Return a single-element list with the image.
"""
from __future__ import annotations

import io
from PIL import Image, ImageDraw, ImageFont

from app.core.constants import FileType
from app.models.domain.answer import UploadedFile
from app.core.logging import get_logger

logger = get_logger(__name__)

_A4_W = 1240
_A4_H = 1754


def extract_pages(uploaded_file: UploadedFile) -> list[Image.Image]:
    """
    Return a list of PIL Images, one per page.
    Always returns at least one image.
    """
    if uploaded_file.file_type != FileType.PDF:
        img = _load_image(uploaded_file.content)
        return [img]

    pages = _extract_pdf_pages(uploaded_file.content)
    if pages:
        return pages

    # Fallback: single blank A4 if everything fails
    logger.warning("page_extractor_fallback", reason="no_pages_extracted")
    return [_blank_a4()]


def _extract_pdf_pages(pdf_bytes: bytes) -> list[Image.Image]:
    """Try to pull one image per page from the PDF using pypdf."""
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(pdf_bytes))
        pages: list[Image.Image] = []

        for page_num, page in enumerate(reader.pages):
            img = _page_to_image(page, page_num)
            pages.append(img)

        logger.info("page_extractor_ok", pages=len(pages))
        return pages

    except Exception as exc:
        logger.warning("page_extractor_failed", error=str(exc))
        return []


def _page_to_image(page, page_num: int) -> Image.Image:
    """
    Convert one pypdf page to a PIL Image.
    Tries embedded images first (scanned/handwritten PDFs); falls back to a
    text canvas only for genuine text-based PDF pages.
    """
    img = _try_embedded_image(page)
    if img is not None:
        logger.info("page_from_image", page=page_num)
        return img.convert("RGB")

    # Text-based page — render the extracted text onto a canvas
    text = (page.extract_text() or "").strip()
    if text:
        logger.info("page_from_text", page=page_num, chars=len(text))
    else:
        logger.info("page_from_blank", page=page_num)
    return _text_to_canvas(text, page_num)


def _try_embedded_image(page) -> Image.Image | None:
    """Pull the first embedded XObject image from a pypdf page."""
    try:
        resources = page.get("/Resources")
        if not resources:
            return None
        xobjs = resources.get("/XObject")
        if not xobjs:
            return None
        for key in xobjs:
            obj = xobjs[key]
            if obj.get("/Subtype") != "/Image":
                continue
            try:
                return Image.open(io.BytesIO(obj.get_data()))
            except Exception:
                continue
    except Exception:
        pass
    return None


def _text_to_canvas(text: str, page_num: int) -> Image.Image:
    """Render page text onto a clean A4-sized white canvas."""
    canvas = Image.new("RGB", (_A4_W, _A4_H), (252, 252, 252))
    draw   = ImageDraw.Draw(canvas)
    font   = _load_font(24)
    small  = _load_font(16)

    # Page header
    draw.rectangle([(0, 0), (_A4_W, 72)], fill=(100, 116, 139))
    draw.text((72, 20), f"Page {page_num + 1}", fill=(255, 255, 255), font=_load_font(26))

    # Body text
    margin  = 72
    y       = 100
    max_y   = _A4_H - 60
    line_h  = 32

    for line in text.splitlines():
        if y >= max_y:
            break
        # Word-wrap each source line
        words   = line.split()
        current = ""
        for word in words:
            test = f"{current} {word}".strip()
            bbox = draw.textbbox((0, 0), test, font=font)
            if bbox[2] - bbox[0] <= _A4_W - margin * 2:
                current = test
            else:
                if current:
                    draw.text((margin, y), current, fill=(30, 30, 30), font=font)
                    y += line_h
                current = word
        if current and y < max_y:
            draw.text((margin, y), current, fill=(30, 30, 30), font=font)
            y += line_h
        y += 8  # paragraph gap

    # Page border
    draw.rectangle([(2, 2), (_A4_W - 2, _A4_H - 2)], outline=(200, 200, 210), width=2)
    return canvas


def _load_image(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data)).convert("RGB")


def _blank_a4() -> Image.Image:
    return Image.new("RGB", (_A4_W, _A4_H), (252, 252, 252))


def _load_font(size: int) -> ImageFont.ImageFont:
    for path in [
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibri.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()
