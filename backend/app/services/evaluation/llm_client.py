"""
Calls Groq's OpenAI-compatible API for rubric-based evaluation.
Single responsibility: (system, user) prompts → parsed JSON dict.

Groq is OpenAI-compatible — same openai SDK, different base_url + api_key.
Model: openai/gpt-oss-120b via https://api.groq.com/openai/v1
JSON mode enforced via response_format={"type":"json_object"}.
4-strategy parse with partial recovery handles any truncation edge cases.
"""
from __future__ import annotations

import json
import re
from openai import AsyncOpenAI

from app.config import get_settings
from app.core.exceptions import EvaluationError, ExternalServiceError
from app.core.logging import get_logger

logger = get_logger(__name__)

_GROQ_BASE_URL = "https://api.groq.com/openai/v1"


async def call_evaluation_llm(system_prompt: str, user_prompt: str) -> dict:
    """Send prompts to Groq and return a parsed JSON dict."""
    settings = get_settings()

    # Groq uses OpenAI-compatible API — just swap base_url and api_key
    client = AsyncOpenAI(
        api_key=settings.groq_api_key,
        base_url=_GROQ_BASE_URL,
    )

    try:
        response = await client.chat.completions.create(
            model=settings.groq_model,
            temperature=settings.groq_temperature,
            max_tokens=settings.groq_max_tokens,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
        )
        raw = response.choices[0].message.content or ""
        if not raw.strip():
            raise EvaluationError("Groq returned an empty evaluation response.")
        return _parse_json_robust(raw)

    except (EvaluationError, ExternalServiceError):
        raise
    except Exception as exc:
        logger.error("groq_eval_failed", error=str(exc))
        raise ExternalServiceError(f"Groq evaluation call failed: {exc}") from exc


# ── JSON parsing (4-strategy with fallbacks) ─────────────────────────────────

def _parse_json_robust(raw: str) -> dict:
    cleaned = _strip_markdown_fence(raw)

    # 1. Direct parse
    try:
        return _validate_and_fill(json.loads(cleaned))
    except (json.JSONDecodeError, EvaluationError):
        pass

    # 2. Extract outermost { ... } block
    brace_match = _extract_brace_block(cleaned)
    if brace_match:
        try:
            return _validate_and_fill(json.loads(brace_match))
        except (json.JSONDecodeError, EvaluationError):
            pass

    # 3. Repair truncated JSON
    repaired = _repair_truncated_json(cleaned)
    if repaired:
        try:
            return _validate_and_fill(json.loads(repaired))
        except (json.JSONDecodeError, EvaluationError):
            pass

    # 4. Partial extraction via regex
    partial = _partial_extract(cleaned)
    if partial and "parameter_scores" in partial:
        logger.warning("groq_json_partial_recovery", keys=list(partial.keys()))
        return _validate_and_fill(partial)

    preview = cleaned[:300].replace('\n', ' ')
    logger.error("groq_json_all_strategies_failed", preview=preview, length=len(cleaned))
    raise EvaluationError(
        f"Could not parse evaluation response (length: {len(cleaned)} chars). "
        "Please try again."
    )


def _validate_and_fill(data: dict) -> dict:
    if "parameter_scores" not in data:
        raise EvaluationError("Response missing 'parameter_scores'.")
    if not data.get("overall_remark"):
        raise EvaluationError("Response missing 'overall_remark'.")
    data.setdefault("annotation_comments", [])
    data.setdefault("strengths", [])
    data.setdefault("improvements", [])
    for ps in data.get("parameter_scores", []):
        ps.setdefault("suggestions", [])
    return data


def _extract_brace_block(text: str) -> str | None:
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i, ch in enumerate(text[start:], start):
        if ch == "{":   depth += 1
        elif ch == "}": depth -= 1
        if depth == 0:  return text[start: i + 1]
    return None


def _repair_truncated_json(text: str) -> str | None:
    start = text.find("{")
    if start == -1:
        return None
    chunk = text[start:]
    ob  = chunk.count("{") - chunk.count("}")
    ob2 = chunk.count("[") - chunk.count("]")
    if ob < 0 or ob2 < 0:
        return None
    repaired = chunk
    if repaired.count('"') % 2 != 0:
        repaired += '"'
    repaired += "]" * ob2 + "}" * ob
    return repaired if ob > 0 or ob2 > 0 else None


def _partial_extract(text: str) -> dict | None:
    result: dict = {}
    m = re.search(r'"parameter_scores"\s*:\s*(\[.*?\])\s*[,}]', text, re.DOTALL)
    if m:
        try: result["parameter_scores"] = json.loads(m.group(1))
        except json.JSONDecodeError: pass
    m = re.search(r'"overall_remark"\s*:\s*"([^"]{10,})"', text, re.DOTALL)
    if m: result["overall_remark"] = m.group(1)
    m = re.search(r'"annotation_comments"\s*:\s*(\[.*?\])\s*[,}]', text, re.DOTALL)
    if m:
        try: result["annotation_comments"] = json.loads(m.group(1))
        except json.JSONDecodeError: result["annotation_comments"] = []
    return result if result else None


def _strip_markdown_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        inner = lines[1:]
        if inner and inner[-1].strip() == "```":
            inner = inner[:-1]
        return "\n".join(inner).strip()
    return text
