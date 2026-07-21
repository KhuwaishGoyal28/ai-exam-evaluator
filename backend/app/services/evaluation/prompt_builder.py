"""
Builds the structured LLM prompt for rubric-based evaluation.
Single responsibility: inputs → (system_prompt, user_prompt).
Generic across ALL exam types — no exam-specific hardcoding here.
"""
import json
from app.core.constants import (
    RUBRIC_DESCRIPTIONS, EXAM_TYPE_CONTEXT, RubricParameter,
    MAX_ANNOTATION_COMMENTS, ExamType,
)
from app.utils.text_utils import truncate_text, sanitise_for_prompt

_SYSTEM_PROMPT = """\
You are an experienced exam evaluator who checks papers across all levels: \
school tests, board exams, entrance exams, and university assignments.

Score the student answer using the 5-parameter rubric below. \
Adjust your expectations to the exam level provided — be age-appropriate and context-aware. \
Do NOT apply criteria from a different subject or level than specified.

Scoring: 0–10 per parameter (integers only).
Calibration: 9–10 = outstanding for the level; 7–8 = good; 5–6 = average; \
3–4 = below average; 0–2 = poor or missing.

Respond ONLY with a valid JSON object matching the exact schema. \
No markdown, no prose outside the JSON.
"""


def build_evaluation_prompt(
    extracted_text: str,
    question: str | None,
    paragraphs: list[str],
    exam_type: ExamType = ExamType.CUSTOM,
) -> tuple[str, str]:
    """
    Return (system_prompt, user_prompt) for the LLM.

    Token budget for Groq free tier (8K TPM total):
      ~350  system prompt
      ~400  rubric + schema + rules
      ~375  answer text  (≤1500 chars)
      ~200  paragraph list (≤10 paragraphs, ≤60 chars each)
      ~100  question + exam context
    ─────────────────────────────────────────────────
      ~1425 input total  →  leaves ~1500 for output
    """
    # Hard-cap at 1500 chars (~375 tokens) — enough to judge quality
    safe_text    = sanitise_for_prompt(truncate_text(extracted_text, 1500))
    safe_q       = sanitise_for_prompt((question or "Not provided")[:200])
    exam_context = EXAM_TYPE_CONTEXT.get(exam_type, EXAM_TYPE_CONTEXT[ExamType.CUSTOM])

    user_prompt = f"""\
EXAM TYPE: {exam_type.value}
CONTEXT: {exam_context[:200]}

QUESTION: {safe_q}

STUDENT ANSWER (excerpt):
{safe_text}

PARAGRAPHS:
{_format_paragraph_list(paragraphs)}

RUBRIC (0–10 each):
{_format_rubric_block()}

SCHEMA:
{_build_response_schema()}

RULES: annotation_comments ≤ 5 items; paragraph_index 0-based; \
comment_text ≤ 60 chars; sentiment = positive|neutral|negative; \
suggestions ≤ 1 tip each ≤ 80 chars; strengths/improvements ≤ 2 items each.
"""
    return _SYSTEM_PROMPT, user_prompt


def _format_paragraph_list(paragraphs: list[str]) -> str:
    # Cap at 10 paragraphs, 60 chars each — enough for annotation targeting
    capped = paragraphs[:10]
    lines  = [f"[{i}] {p[:60]}{'…' if len(p) > 60 else ''}"
              for i, p in enumerate(capped)]
    if len(paragraphs) > 10:
        lines.append(f"… +{len(paragraphs) - 10} more paragraphs")
    return "\n".join(lines) if lines else "[0] (single block)"


def _format_rubric_block() -> str:
    return "\n".join(f"  {p.value}: {desc}" for p, desc in RUBRIC_DESCRIPTIONS.items())


def _build_response_schema() -> str:
    """Compact JSON schema — keeps token usage low."""
    schema = {
        "parameter_scores": [
            {"parameter": p.value, "score": 0,
             "justification": "one sentence", "suggestions": ["tip"]}
            for p in RubricParameter
        ],
        "overall_remark":   "2-3 sentence summary",
        "strengths":        ["strength 1", "strength 2"],
        "improvements":     ["improvement 1", "improvement 2"],
        "annotation_comments": [
            {"paragraph_index": 0,
             "comment_text": "comment ≤80 chars",
             "sentiment": "positive|neutral|negative"}
        ],
    }
    return json.dumps(schema, separators=(',', ':'))
