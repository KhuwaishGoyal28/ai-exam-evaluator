"""
Maps the raw LLM JSON dict to typed EvaluationResult domain objects.
Single responsibility: dict → EvaluationResult.
"""
from app.core.constants import RubricParameter
from app.core.exceptions import EvaluationError
from app.models.domain.evaluation import EvaluationResult, ParameterScore, AnnotationComment
from app.core.logging import get_logger

logger = get_logger(__name__)


def map_llm_response_to_result(
    data: dict,
    exam_type: str = "UPSC Mains",
) -> EvaluationResult:
    parameter_scores    = _map_parameter_scores(data.get("parameter_scores", []))
    annotation_comments = _map_annotation_comments(data.get("annotation_comments", []))
    overall_remark      = _require_string(data, "overall_remark")
    strengths           = _safe_string_list(data.get("strengths", []))
    improvements        = _safe_string_list(data.get("improvements", []))

    result = EvaluationResult(
        parameter_scores=parameter_scores,
        overall_remark=overall_remark,
        annotation_comments=annotation_comments,
        exam_type=exam_type,
        strengths=strengths,
        improvements=improvements,
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
            score=_clamp(item.get("score", 0)),
            max_score=10,
            justification=str(item.get("justification", ""))[:300],
            suggestions=_safe_string_list(item.get("suggestions", [])),
        ))
    if not scores:
        raise EvaluationError("LLM returned no parameter scores.")
    return scores


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


def _safe_string_list(raw: list) -> list[str]:
    return [str(s)[:150] for s in raw if s and str(s).strip()][:4]


def _clamp(v) -> int:
    try:
        return max(0, min(10, int(v)))
    except (TypeError, ValueError):
        return 0


def _norm_sentiment(v: str) -> str:
    return v.lower() if v.lower() in {"positive", "neutral", "negative"} else "neutral"
