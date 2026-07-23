"""
Groq Vision — Combined OCR + Evaluation Agent.

Uses qwen/qwen3.6-27b via Groq's OpenAI-compatible API.

One Vision call per page using the master system prompt.
Returns a structured JSON payload matching the teacher-evaluation schema:
  {student_name, subject, total_marks, grade, rubric,
   strengths, weaknesses, remarks, annotations}

Free-tier limits (on-demand): 8,000 TPM.
Strategy: compress each page to ≤800px / JPEG-60, one page per call,
8-second delay between pages so TPM budget resets.

Public API:
  run_vision_evaluation(page_images, question, exam_type)  → dict
  render_pdf_to_page_images(pdf_bytes)                     → list[bytes]
  extract_text_via_vision(image_bytes)                     → str  (shim)
  extract_text_from_pdf(pdf_bytes)                         → str  (shim)
"""
from __future__ import annotations

import asyncio
import base64
import io
import json
import re

from openai import AsyncOpenAI
from PIL import Image

from app.config import get_settings
from app.core.exceptions import OCRExtractionError, ExternalServiceError
from app.core.logging import get_logger

logger = get_logger(__name__)

_GROQ_BASE_URL      = "https://api.groq.com/openai/v1"
_PAGE_DELAY_SECONDS = 8      # wait between pages to respect 8k TPM
_MAX_IMAGE_WIDTH    = 800    # px — keeps tokens low while text stays legible
_JPEG_QUALITY       = 60     # enough for OCR; saves ~40% tokens vs quality 90


# ── Master System Prompt ──────────────────────────────────────────────────────

_MASTER_SYSTEM = """\
You are a Senior Academic Evaluator, Vision OCR Expert, and experienced CBSE/ICSE school teacher.
You check handwritten student answer sheets exactly as a human teacher would — with red ink,
ticks, crosses, circles, underlines, and short margin comments.

YOUR COMPLETE TASK:
1. Read ALL handwritten content on the page (pen or pencil).
2. IGNORE all pre-printed text: question numbers, headers, footers, watermarks, page numbers,
   logos, printed instructions, ruled lines, and any typeset text.
3. Evaluate the handwritten answers against the rubric.
4. Generate natural teacher-style annotations pointing to specific paragraphs and sentences.
5. Return ONLY valid JSON — no prose, no markdown outside the JSON.

═══════════════════════════════════════
HANDWRITING DETECTION RULES
═══════════════════════════════════════
- Transcribe ONLY pen/pencil handwritten content.
- Preserve paragraph structure and sentence breaks.
- Do NOT autocorrect spelling or grammar — copy exactly as written.
- If page has NO handwritten text, set has_handwritten_content: false and total_marks: 4.

═══════════════════════════════════════
ANNOTATION RULES (like a real teacher)
═══════════════════════════════════════
- Maximum 8–20 annotations per page. Do NOT annotate every sentence.
- Annotate only the most important lines — strong points and clear errors.
- Annotation TYPES:
    tick       → strong correct content, good vocabulary, good argument
    cross      → factual error, wrong answer, logical mistake
    circle     → spelling error, grammar mistake, unclear word
    underline  → important key point worth highlighting
    comment    → structural advice, suggestion, brief encouragement

- Annotation TEXT must be SHORT (2–5 words):
    Good examples: "Excellent", "Good", "Grammar", "Rewrite", "Spelling",
    "Clear thesis", "Needs example", "Strong point", "Weak conclusion",
    "Very Good", "Excellent Vocabulary", "Good flow", "Add example",
    "Unclear", "Wrong fact", "Good intro", "Needs depth"

- POSITION: use paragraph (1-based) and sentence (1-based) within that paragraph.
  The Python renderer uses these to calculate pixel positions.
  If a comment is for a whole paragraph (not a specific sentence), omit "sentence".

═══════════════════════════════════════
EVALUATION RUBRIC (100 marks total)
═══════════════════════════════════════
Introduction        5   — hook, thesis, context setting
Content             20  — accuracy, depth, key points covered
Grammar             10  — sentence correctness, tense, subject-verb agreement
Vocabulary          10  — word choice, variety, appropriateness
Presentation        10  — neatness, margins, legibility, structure
Handwriting         20  — clarity, consistency, letter formation
Conclusion          5   — summary, closing thought, final impression
Creativity          10  — originality, examples, analogies, fresh ideas
Flow                10  — paragraph transitions, logical progression, coherence

═══════════════════════════════════════
GRADING SCALE
═══════════════════════════════════════
90–100  → A+
80–89   → A
70–79   → B+
60–69   → B
50–59   → C
40–49   → D
Below 40 → F

═══════════════════════════════════════
OUTPUT JSON SCHEMA (return exactly this)
═══════════════════════════════════════
{
  "student_name": "extracted from sheet or empty string",
  "subject": "extracted from sheet or empty string",
  "has_handwritten_content": true,
  "transcribed_text": "full handwritten text from this page",
  "total_marks": 84,
  "max_marks": 100,
  "grade": "A",
  "performance_level": "Excellent | Very Good | Good | Average | Needs Improvement",
  "rubric": {
    "introduction":  {"marks": 4, "max": 5,  "remark": "Strong hook."},
    "content":       {"marks": 17,"max": 20, "remark": "Well covered with good examples."},
    "grammar":       {"marks": 8, "max": 10, "remark": "Minor tense errors."},
    "vocabulary":    {"marks": 9, "max": 10, "remark": "Excellent word choice."},
    "presentation":  {"marks": 9, "max": 10, "remark": "Neat and well-structured."},
    "handwriting":   {"marks": 17,"max": 20, "remark": "Clear and consistent."},
    "conclusion":    {"marks": 4, "max": 5,  "remark": "Good closing statement."},
    "creativity":    {"marks": 8, "max": 10, "remark": "Original examples used."},
    "flow":          {"marks": 8, "max": 10, "remark": "Good transitions between paragraphs."}
  },
  "strengths": [
    "Excellent vocabulary throughout",
    "Logical argument structure"
  ],
  "weaknesses": [
    "Minor grammar errors in paragraph 3",
    "Conclusion needs stronger closing"
  ],
  "remarks": "Good effort. Focus on grammar and strengthen your conclusion. Keep practicing.",
  "annotations": [
    {
      "page": 1,
      "paragraph": 1,
      "sentence": 2,
      "type": "tick",
      "comment": "Strong introduction"
    },
    {
      "page": 1,
      "paragraph": 2,
      "sentence": 3,
      "type": "circle",
      "comment": "Grammar"
    },
    {
      "page": 1,
      "paragraph": 3,
      "type": "comment",
      "comment": "Needs example"
    },
    {
      "page": 1,
      "paragraph": 4,
      "sentence": 1,
      "type": "underline",
      "comment": "Key point"
    }
  ]
}

IMPORTANT REMINDERS:
- total_marks must equal the sum of all rubric marks.
- Annotations must reference real content from the handwritten text.
- Keep annotation comments short (2–5 words maximum).
- Return ONLY the JSON object. No text before or after it.
"""


# ── Public entry point ────────────────────────────────────────────────────────

async def run_vision_evaluation(
    page_images: list[bytes],
    question: str | None,
    exam_type: str,
) -> dict:
    """
    Evaluate all pages of a handwritten answer sheet.

    Sends each page individually to Groq Vision (one call per page,
    8-second delay between calls to respect the 8k TPM free-tier limit).

    Returns a merged master-schema dict.
    """
    if not page_images:
        raise OCRExtractionError("No page images provided for vision evaluation.")

    total_pages = len(page_images)
    merged: dict = {}

    for page_num, img_bytes in enumerate(page_images):
        if page_num > 0:
            logger.info("vision_page_delay", page=page_num + 1,
                        wait_s=_PAGE_DELAY_SECONDS)
            await asyncio.sleep(_PAGE_DELAY_SECONDS)

        page_result = await _evaluate_single_page(
            img_bytes=img_bytes,
            page_num=page_num,
            total_pages=total_pages,
            question=question,
            exam_type=exam_type,
        )
        logger.info("vision_page_done", page=page_num + 1,
                    marks=page_result.get("total_marks", "?"))

        if page_num == 0:
            merged = page_result
            if "annotations" not in merged:
                merged["annotations"] = []
        else:
            # Merge additional page annotations
            extra = page_result.get("annotations", [])
            merged["annotations"].extend(extra)

            # Append transcribed text
            extra_text = page_result.get("transcribed_text", "").strip()
            if extra_text:
                existing = merged.get("transcribed_text", "")
                merged["transcribed_text"] = (
                    f"{existing}\n\n--- PAGE {page_num + 1} ---\n\n{extra_text}"
                )

    merged["total_pages"] = total_pages
    return merged


async def _evaluate_single_page(
    img_bytes: bytes,
    page_num: int,
    total_pages: int,
    question: str | None,
    exam_type: str,
) -> dict:
    """Compress one page image and call Groq Vision. Returns parsed JSON dict."""
    compressed = _compress_image(img_bytes)
    b64 = base64.b64encode(compressed).decode()

    is_first = (page_num == 0)
    scoring_note = (
        "This is PAGE 1. Provide FULL rubric scoring, strengths, weaknesses, remarks, "
        "and all annotations for this page."
        if is_first else
        f"This is PAGE {page_num + 1} of {total_pages}. "
        "Provide ONLY annotations for this page. "
        "Set rubric marks identical to page 1 values (scoring is holistic). "
        "Keep strengths/weaknesses/remarks from page 1."
    )

    user_content = [
        {
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
        },
        {
            "type": "text",
            "text": (
                f"EXAM TYPE: {exam_type}\n"
                f"TOPIC / QUESTION: {question or 'General answer sheet'}\n"
                f"PAGE: {page_num + 1} of {total_pages}\n\n"
                f"{scoring_note}\n\n"
                "Evaluate the handwritten content on this page. "
                "Return ONLY the JSON schema from your system prompt."
            ),
        },
    ]

    raw = await _call_groq_vision(user_content)
    return _parse_json_robust(raw, page_num=page_num + 1)


# ── Groq Vision API call ──────────────────────────────────────────────────────

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
                {"role": "system", "content": _MASTER_SYSTEM},
                {"role": "user",   "content": user_content},
            ],
        )
        text = (response.choices[0].message.content or "").strip()
        if not text:
            raise OCRExtractionError("Groq Vision returned an empty response.")
        return text
    except OCRExtractionError:
        raise
    except Exception as exc:
        logger.error("groq_vision_failed", error=str(exc))
        raise ExternalServiceError(f"Groq Vision call failed: {exc}") from exc


# ── JSON parsing (3-strategy with fallback) ───────────────────────────────────

def _parse_json_robust(raw: str, page_num: int = 1) -> dict:
    """Try three strategies to extract valid JSON from the Vision response."""
    # 1. Strip markdown fences
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    cleaned = re.sub(r"\s*```\s*$", "", cleaned)

    # 2. Direct parse
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # 3. Extract outermost { ... } block
    start = cleaned.find("{")
    if start != -1:
        depth = 0
        for i, ch in enumerate(cleaned[start:], start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
            if depth == 0:
                try:
                    return json.loads(cleaned[start: i + 1])
                except json.JSONDecodeError:
                    break

    # 4. Fallback — minimal valid structure so pipeline continues
    logger.warning("vision_json_parse_failed", page=page_num,
                   preview=raw[:300])
    return _fallback_result(page_num)


def _fallback_result(page_num: int) -> dict:
    """Return a minimal valid result when JSON parsing fails completely."""
    return {
        "student_name": "",
        "subject": "",
        "has_handwritten_content": False,
        "transcribed_text": "",
        "total_marks": 4,
        "max_marks": 100,
        "grade": "F",
        "performance_level": "Needs Improvement",
        "rubric": {
            "introduction":  {"marks": 0, "max": 5,  "remark": "Could not process page."},
            "content":       {"marks": 0, "max": 20, "remark": "Could not process page."},
            "grammar":       {"marks": 0, "max": 10, "remark": ""},
            "vocabulary":    {"marks": 0, "max": 10, "remark": ""},
            "presentation":  {"marks": 0, "max": 10, "remark": ""},
            "handwriting":   {"marks": 0, "max": 20, "remark": ""},
            "conclusion":    {"marks": 0, "max": 5,  "remark": ""},
            "creativity":    {"marks": 0, "max": 10, "remark": ""},
            "flow":          {"marks": 0, "max": 10, "remark": ""},
        },
        "strengths": [],
        "weaknesses": ["Could not read handwriting on this page."],
        "remarks": "Page could not be processed. Please re-upload with better image quality.",
        "annotations": [{"page": page_num, "paragraph": 1, "type": "comment",
                         "comment": "Unreadable"}],
    }


# ── Image compression ─────────────────────────────────────────────────────────

def _compress_image(image_bytes: bytes) -> bytes:
    """
    Resize to ≤800px wide and encode as JPEG-60.
    Reduces token count ~40% while keeping handwriting legible.
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
        logger.info("image_compressed",
                    original_kb=len(image_bytes) // 1024,
                    compressed_kb=len(compressed) // 1024)
        return compressed
    except Exception as exc:
        logger.warning("image_compress_failed", error=str(exc))
        return image_bytes


# ── PDF → per-page JPEG images ────────────────────────────────────────────────

def render_pdf_to_page_images(pdf_bytes: bytes) -> list[bytes]:
    """
    Convert every page of a PDF to JPEG bytes.
    Tries three strategies: embedded XObject images → pdf2image → PyMuPDF.
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
                    break   # one image per page is sufficient
                except Exception:
                    continue

        if result:
            logger.info("pdf_embedded_images_extracted", pages=len(result))
        return result
    except Exception as exc:
        logger.warning("pdf_embedded_failed", error=str(exc))
        return []


def _rasterise_with_pdf2image(pdf_bytes: bytes) -> list[bytes]:
    """Rasterise PDF pages using pdf2image (requires poppler on PATH)."""
    try:
        from pdf2image import convert_from_bytes

        pil_images = convert_from_bytes(pdf_bytes, dpi=150)
        result: list[bytes] = []
        for img in pil_images:
            buf = io.BytesIO()
            img.convert("RGB").save(buf, format="JPEG", quality=88)
            result.append(buf.getvalue())
        logger.info("pdf2image_rasterised", pages=len(result))
        return result
    except ImportError:
        return []
    except Exception as exc:
        logger.warning("pdf2image_failed", error=str(exc))
        return []


def _rasterise_with_pymupdf(pdf_bytes: bytes) -> list[bytes]:
    """Rasterise PDF pages using PyMuPDF (fitz) at 150 dpi."""
    try:
        import fitz

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        result: list[bytes] = []
        mat = fitz.Matrix(150 / 72, 150 / 72)   # 150 dpi
        for page in doc:
            pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
            result.append(pix.tobytes("jpeg"))
        doc.close()
        logger.info("pymupdf_rasterised", pages=len(result))
        return result
    except ImportError:
        return []
    except Exception as exc:
        logger.warning("pymupdf_failed", error=str(exc))
        return []


# ── Legacy shims (used by old ocr_pipeline.py path for plain images) ──────────

async def extract_text_via_vision(image_bytes: bytes) -> str:
    """Shim: extract handwritten text from a single image."""
    result = await run_vision_evaluation(
        [image_bytes], question=None, exam_type="Custom / General"
    )
    return result.get("transcribed_text", "")


async def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Shim: render PDF pages and extract handwritten text."""
    pages = render_pdf_to_page_images(pdf_bytes)
    if not pages:
        return ""
    result = await run_vision_evaluation(
        pages, question=None, exam_type="Custom / General"
    )
    return result.get("transcribed_text", "")
