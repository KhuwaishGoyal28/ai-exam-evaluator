"""
Builds the structured LLM prompt for rubric-based evaluation.
Single responsibility: inputs → (system_prompt, user_prompt).

Two rubric modes:
  - Standard (5-param, 0–10 each, /50)  — all non-Essay exam types
  - Essay    (12-param, variable max, /100) — ExamType.ESSAY only
"""
import json
from app.core.constants import (
    RUBRIC_DESCRIPTIONS, EXAM_TYPE_CONTEXT,
    ESSAY_RUBRIC_DESCRIPTIONS, ESSAY_RUBRIC_MAX,
    RubricParameter, EssayRubricParameter,
    MAX_ANNOTATION_COMMENTS, ExamType,
)
from app.utils.text_utils import truncate_text, sanitise_for_prompt

# ── System prompts ────────────────────────────────────────────────────────────

_STANDARD_SYSTEM = """\
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

_ESSAY_SYSTEM = """\
You are a senior essay examiner specialising in competitive examination essays \
(UPSC, state PSC, and equivalent).

Evaluate the essay using the 12-parameter rubric below. Each parameter has its own \
maximum mark — the total is 100. Be strict and calibrated: a well-written, complete \
essay that covers most parameters competently should score 65–72/100. \
Genuinely exceptional essays (rare) may reach 80+.

For each parameter provide:
  - score: integer within [0, max_marks]
  - examiner_remark: one crisp sentence (≤ 100 chars) — exactly as a human examiner \
    would write in the margin of the evaluation sheet.
  - suggestions: zero or one actionable tip (≤ 90 chars).

Also produce 4–5 "before_resubmit" checklist items — concrete, specific fixes the \
student must address before resubmitting (e.g. fix a factual error, add a counter-view, \
expand a specific example). These mirror the numbered boxes at the bottom of a \
Roundtable IAS evaluation sheet.

Respond ONLY with a valid JSON object matching the exact schema. \
No markdown, no prose outside the JSON.
"""


def build_evaluation_prompt(
    extracted_text: str,
    question: str | None,
    paragraphs: list[str],
    exam_type: ExamType = ExamType.CUSTOM,
) -> tuple[str, str]:
    """Return (system_prompt, user_prompt) for the LLM."""
    if exam_type == ExamType.ESSAY:
        return _build_essay_prompt(extracted_text, question, paragraphs)
    return _build_standard_prompt(extracted_text, question, paragraphs, exam_type)


# ── Standard (5-param) ────────────────────────────────────────────────────────

def _build_standard_prompt(
    extracted_text: str,
    question: str | None,
    paragraphs: list[str],
    exam_type: ExamType,
) -> tuple[str, str]:
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
{_format_standard_rubric()}

SCHEMA:
{_build_standard_schema()}

RULES: annotation_comments ≤ 5 items; paragraph_index 0-based; \
comment_text ≤ 60 chars; sentiment = positive|neutral|negative; \
suggestions ≤ 1 tip each ≤ 80 chars; strengths/improvements ≤ 2 items each.
"""
    return _STANDARD_SYSTEM, user_prompt


def _format_standard_rubric() -> str:
    return "\n".join(
        f"  {p.value}: {desc}" for p, desc in RUBRIC_DESCRIPTIONS.items()
    )


def _build_standard_schema() -> str:
    schema = {
        "parameter_scores": [
            {
                "parameter": p.value,
                "score": 0,
                "justification": "one sentence",
                "suggestions": ["tip"],
            }
            for p in RubricParameter
        ],
        "overall_remark":      "2-3 sentence summary",
        "strengths":           ["strength 1", "strength 2"],
        "improvements":        ["improvement 1", "improvement 2"],
        "annotation_comments": [
            {
                "paragraph_index": 0,
                "comment_text":    "comment ≤80 chars",
                "sentiment":       "positive|neutral|negative",
            }
        ],
    }
    return json.dumps(schema, separators=(',', ':'))


# ── Essay (12-param) ──────────────────────────────────────────────────────────

def _build_essay_prompt(
    extracted_text: str,
    question: str | None,
    paragraphs: list[str],
) -> tuple[str, str]:
    # Essay papers are long; allow up to 3000 chars (~750 tokens) for better coverage
    safe_text = sanitise_for_prompt(truncate_text(extracted_text, 3000))
    safe_q    = sanitise_for_prompt((question or "Not provided")[:300])

    user_prompt = f"""\
ESSAY TOPIC / QUESTION: {safe_q}

ESSAY TEXT:
{safe_text}

PARAGRAPHS (for annotation targeting):
{_format_paragraph_list(paragraphs, max_paras=12)}

RUBRIC (score must be integer within [0, max_marks]):
{_format_essay_rubric()}

SCHEMA:
{_build_essay_schema()}

RULES:
- Every parameter_scores entry must use the exact parameter name from the rubric.
- score must be an integer in [0, max_marks] for that parameter.
- examiner_remark ≤ 100 chars; write as a single sharp examiner sentence.
- suggestions: list of 0 or 1 string, each ≤ 90 chars.
- annotation_comments: 5–8 items; paragraph_index 0-based; comment_text ≤ 80 chars; \
  sentiment = positive|neutral|negative.
- before_resubmit: 4–5 numbered strings — specific, actionable fixes (≤ 120 chars each).
- overall_remark: 3–4 sentence evaluator summary as it would appear on a formal sheet.
- strengths: 2–3 items; improvements: 2–3 items.
"""
    return _ESSAY_SYSTEM, user_prompt


def _format_essay_rubric() -> str:
    lines = []
    for param, desc in ESSAY_RUBRIC_DESCRIPTIONS.items():
        max_m = ESSAY_RUBRIC_MAX[param]
        lines.append(f"  [{max_m} marks] {param.value}: {desc}")
    return "\n".join(lines)


def _build_essay_schema() -> str:
    schema = {
        "parameter_scores": [
            {
                "parameter":       p.value,
                "score":           0,
                "max_marks":       ESSAY_RUBRIC_MAX[p],
                "examiner_remark": "one crisp sentence ≤100 chars",
                "suggestions":     ["optional tip ≤90 chars"],
            }
            for p in EssayRubricParameter
        ],
        "overall_remark":      "3–4 sentence evaluator summary",
        "strengths":           ["strength 1", "strength 2"],
        "improvements":        ["improvement 1", "improvement 2"],
        "before_resubmit": [
            "1. Fix the Gita line — 'selfless' should be 'selfish'.",
            "2. Develop two examples (Ashoka, Covid collector) into 4-5 analysed sentences.",
        ],
        "annotation_comments": [
            {
                "paragraph_index": 0,
                "comment_text":    "comment ≤80 chars",
                "sentiment":       "positive|neutral|negative",
            }
        ],
    }
    return json.dumps(schema, separators=(',', ':'))


# ── Shared helpers ────────────────────────────────────────────────────────────

def _format_paragraph_list(paragraphs: list[str], max_paras: int = 10) -> str:
    capped = paragraphs[:max_paras]
    lines  = [
        f"[{i}] {p[:70]}{'…' if len(p) > 70 else ''}"
        for i, p in enumerate(capped)
    ]
    if len(paragraphs) > max_paras:
        lines.append(f"… +{len(paragraphs) - max_paras} more paragraphs")
    return "\n".join(lines) if lines else "[0] (single block)"
