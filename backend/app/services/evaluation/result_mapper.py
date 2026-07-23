"""
Maps the raw LLM JSON dict to typed EvaluationResult domain objects.
Single responsibility: dict → EvaluationResult.

Supports two rubric modes:
  Standard (5-param)  — exam_type != "Essay"
  Essay    (12-param) — exam_type == "Essay"
"""
from app.core.constants import RubricParameter, EssayRubricParameter, ESSAY_RUBRIC_MAX
from app.core.exceptions import EvaluationError
from app.models.domain.evaluation import (
    EvaluationResult,
    ParameterScore,
    EssayParameterScore,
    AnnotationComment,
)
from app.core.logging import get_logger

logger = get_logger(__name__)

_ESSAY_EXAM_TYPE = "Essay"


def map_llm_response_to_result(
    data: dict,
    exam_type: str = "Custom / General",
) -> EvaluationResult:
    annotation_comments = _map_annotation_comments(data.get("annotation_comments", []))
    overall_remark      = _require_string(data, "overall_remark")
    strengths           = _safe_string_list(data.get("strengths", []))
    improvements        = _safe_string_list(data.get("improvements", []))

    if exam_type == _ESSAY_EXAM_TYPE:
        return _map_essay_result(
            data, overall_remark, annotation_comments, strengths, improvements, exam_type
        )
    return _map_standard_result(
        data, overall_remark, annotation_comments, strengths, improvements, exam_type
    )


# ── Standard 5-param ─────────────────────────────────────────────────────────

def _map_standard_result(
    data: dict,
    overall_remark: str,
    annotation_comments: list[AnnotationComment],
    strengths: list[str],
    improvements: list[str],
    exam_type: str,
) -> EvaluationResult:
    parameter_scores = _map_parameter_scores(data.get("parameter_scores", []))
    result = EvaluationResult(
        parameter_scores=parameter_scores,
        overall_remark=overall_remark,
        annotation_comments=annotation_comments,
        exam_type=exam_type,
        strengths=strengths,
        improvements=improvements,
        max_total_score=50,
    )
    result.compute_total()
    return result


def _map_parameter_scores(raw: list) -> list[ParameterScore]:
    known = {p.value: p for p in RubricParameter}
    scores = []
    for item in raw:
        name = item.get("parameter", "")
        if name not in known:
            logger.warning("unknown_rubric_parameter", parameter=name)
            continue
        scores.append(ParameterScore(
            parameter=known[name],
            score=_clamp(item.get("score", 0), 0, 10),
            max_score=10,
            justification=str(item.get("justification", ""))[:300],
            suggestions=_safe_string_list(item.get("suggestions", [])),
        ))
    if not scores:
        raise EvaluationError("LLM returned no parameter scores.")
    return scores


# ── Essay 12-param ────────────────────────────────────────────────────────────

def _map_essay_result(
    data: dict,
    overall_remark: str,
    annotation_comments: list[AnnotationComment],
    strengths: list[str],
    improvements: list[str],
    exam_type: str,
) -> EvaluationResult:
    essay_scores    = _map_essay_parameter_scores(data.get("parameter_scores", []))
    before_resubmit = _safe_string_list(data.get("before_resubmit", []), max_len=150, max_items=6)

    result = EvaluationResult(
        essay_parameter_scores=essay_scores,
        before_resubmit=before_resubmit,
        overall_remark=overall_remark,
        annotation_comments=annotation_comments,
        exam_type=exam_type,
        strengths=strengths,
        improvements=improvements,
        max_total_score=100,
    )
    result.compute_total()
    return result


def _map_essay_parameter_scores(raw: list) -> list[EssayParameterScore]:
    known_names = {p.value: p for p in EssayRubricParameter}
    scores: list[EssayParameterScore] = []

    for item in raw:
        name = item.get("parameter", "")
        param = known_names.get(name)
        if param is None:
            logger.warning("unknown_essay_parameter", parameter=name)
            continue

        max_m = ESSAY_RUBRIC_MAX[param]
        scores.append(EssayParameterScore(
            parameter=name,
            score=_clamp(item.get("score", 0), 0, max_m),
            max_score=max_m,
            examiner_remark=str(item.get("examiner_remark", ""))[:120],
            suggestions=_safe_string_list(item.get("suggestions", []), max_len=100, max_items=1),
        ))

    if not scores:
        raise EvaluationError("LLM returned no essay parameter scores.")
    return scores


# ── Shared helpers ────────────────────────────────────────────────────────────

def _map_annotation_comments(raw: list) -> list[AnnotationComment]:
    out = []
    for item in raw:
        try:
            out.append(AnnotationComment(
                paragraph_index=max(0, int(item.get("paragraph_index", 0))),
                comment_text=str(item.get("comment_text", ""))[:100],
                sentiment=_norm_sentiment(item.get("sentiment", "neutral")),
            ))
        except (TypeError, ValueError) as e:
            logger.warning("skipped_malformed_comment", error=str(e))
    return out


def _require_string(data: dict, key: str) -> str:
    val = data.get(key, "")
    if not val:
        raise EvaluationError(f"LLM returned empty '{key}'.")
    return str(val)[:600]


def _safe_string_list(
    raw: list,
    max_len: int = 150,
    max_items: int = 4,
) -> list[str]:
    return [str(s)[:max_len] for s in raw if s and str(s).strip()][:max_items]


def _clamp(v, lo: int, hi: int) -> int:
    try:
        return max(lo, min(hi, int(v)))
    except (TypeError, ValueError):
        return lo


def _norm_sentiment(v: str) -> str:
    return v.lower() if v.lower() in {"positive", "neutral", "negative"} else "neutral"
