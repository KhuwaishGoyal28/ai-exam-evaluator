"""
Maps the raw Vision agent JSON (master schema) → EvaluationResult domain object.

Also handles the legacy LLM-only JSON (standard 5-param / essay 12-param)
for non-handwritten uploads that fall back to the text eval path.
"""
from __future__ import annotations

from app.core.constants import RubricParameter, EssayRubricParameter, ESSAY_RUBRIC_MAX
from app.core.exceptions import EvaluationError
from app.core.logging import get_logger
from app.models.domain.evaluation import (
    EvaluationResult,
    DocumentSummary,
    ScoreSummary,
    PageAnnotation,
    AnnotationLocation,
    ParameterBreakdown,
    OverallEvaluation,
    ParameterScore,
    EssayParameterScore,
    AnnotationComment,
)

logger = get_logger(__name__)

_ESSAY_EXAM_TYPE = "Essay"


# ── Primary mapper — master Vision JSON ──────────────────────────────────────

def map_vision_result(data: dict, exam_type: str = "Custom / General") -> EvaluationResult:
    """
    Map the master-schema JSON from run_vision_evaluation() → EvaluationResult.
    This is the primary path for all handwritten PDF submissions.
    """
    doc   = _map_document_summary(data.get("document_summary", {}))
    score = _map_score_summary(data.get("score_summary", {}))
    pages = _map_page_annotations(data.get("page_annotations", []))
    params = _map_parameter_breakdown(data.get("parameter_breakdown", []))
    overall = _map_overall_evaluation(data.get("overall_evaluation", {}))

    # Build legacy AnnotationComment list from page_annotations so the
    # existing image-annotation pipeline (comment boxes, ticks) still works.
    legacy_comments = _page_annotations_to_legacy_comments(pages)

    # Build before_resubmit from checklist
    before_resubmit = overall.actionable_resubmission_checklist

    # Build strengths / improvements from PRAISE / CORRECTION annotations
    strengths = [
        a.annotation_text for a in pages
        if a.annotation_type == "PRAISE"
    ][:3]
    improvements = [
        a.annotation_text for a in pages
        if a.annotation_type in ("CORRECTION", "STRUCTURAL_NOTE")
    ][:3]

    return EvaluationResult(
        document_summary=doc,
        score_summary=score,
        page_annotations=pages,
        parameter_breakdown=params,
        overall_evaluation=overall,
        annotation_comments=legacy_comments,
        before_resubmit=before_resubmit,
        exam_type=exam_type,
        strengths=strengths,
        improvements=improvements,
    )


def _map_document_summary(raw: dict) -> DocumentSummary:
    return DocumentSummary(
        total_pages=int(raw.get("total_pages", 1)),
        estimated_word_count=int(raw.get("estimated_word_count", 0)),
        target_word_count=int(raw.get("target_word_count", 1200)),
        transcription_status=str(raw.get("transcription_status", "SUCCESS")),
        has_handwritten_content=bool(raw.get("has_handwritten_content", True)),
        transcribed_text=str(raw.get("transcribed_text", "")),
    )


def _map_score_summary(raw: dict) -> ScoreSummary:
    total = _clamp(raw.get("total_score", 0), 0, 200)
    max_s = int(raw.get("max_score", 100)) or 100
    pct   = total / max_s
    # Compute grade from score if not provided
    grade = str(raw.get("grade", ""))
    if not grade:
        grade = "A" if pct >= 0.8 else "B" if pct >= 0.6 else "C" if pct >= 0.4 else "D"
    perf = str(raw.get("performance_status", ""))
    if not perf:
        perf = ("Excellent" if pct >= 0.8 else "Strong Draft"
                if pct >= 0.6 else "Needs Work")
    return ScoreSummary(
        total_score=total,
        max_score=max_s,
        grade=grade,
        performance_status=perf,
    )


def _map_page_annotations(raw_pages: list) -> list[PageAnnotation]:
    result: list[PageAnnotation] = []
    for page_block in raw_pages:
        page_num = int(page_block.get("page_number", 1))
        for ann in page_block.get("annotations", []):
            loc_raw = ann.get("location", {})
            loc = AnnotationLocation(
                y_percent=float(loc_raw.get("y_percent", 50)),
                position=str(loc_raw.get("position", "RIGHT_MARGIN")),
            )
            result.append(PageAnnotation(
                annotation_type=str(ann.get("type", "STRUCTURAL_NOTE")),
                target_snippet=str(ann.get("target_snippet", ""))[:200],
                mark_symbol=str(ann.get("mark_symbol", "MARGIN_BOX")),
                annotation_text=str(ann.get("annotation_text", ""))[:120],
                location=loc,
                page_number=page_num,
            ))
    return result


def _map_parameter_breakdown(raw: list) -> list[ParameterBreakdown]:
    result: list[ParameterBreakdown] = []
    for item in raw:
        max_m = int(item.get("max_marks", 10))
        obtained = _clamp(item.get("marks_obtained", 0), 0, max_m)
        result.append(ParameterBreakdown(
            parameter_name=str(item.get("parameter_name", ""))[:80],
            marks_obtained=obtained,
            max_marks=max_m,
            examiner_remark=str(item.get("examiner_remark", ""))[:120],
        ))
    return result


def _map_overall_evaluation(raw: dict) -> OverallEvaluation:
    checklist = [
        str(s)[:150] for s in raw.get("actionable_resubmission_checklist", [])
        if s and str(s).strip()
    ][:5]
    return OverallEvaluation(
        summary_remarks=str(raw.get("summary_remarks", ""))[:600],
        actionable_resubmission_checklist=checklist,
    )


def _page_annotations_to_legacy_comments(
    annotations: list[PageAnnotation],
) -> list[AnnotationComment]:
    """
    Convert PageAnnotation list → legacy AnnotationComment list.
    paragraph_index is approximated from y_percent (0–100 → 0–9).
    sentiment is derived from annotation_type.
    """
    SENTIMENT_MAP = {
        "PRAISE":          "positive",
        "CORRECTION":      "negative",
        "STRUCTURAL_NOTE": "neutral",
    }
    result: list[AnnotationComment] = []
    for ann in annotations:
        para_idx = max(0, int(ann.location.y_percent / 10))
        sentiment = SENTIMENT_MAP.get(ann.annotation_type, "neutral")
        result.append(AnnotationComment(
            paragraph_index=para_idx,
            comment_text=ann.annotation_text[:100],
            sentiment=sentiment,
        ))
    return result


# ── Legacy mapper — text-only LLM JSON (standard 5-param / essay 12-param) ───

def map_llm_response_to_result(
    data: dict,
    exam_type: str = "Custom / General",
) -> EvaluationResult:
    """
    Legacy path: map the Groq text-eval JSON → EvaluationResult.
    Used as fallback when the upload is a typed/text PDF (not handwritten).
    """
    annotation_comments = _map_legacy_annotation_comments(
        data.get("annotation_comments", [])
    )
    overall_remark = _require_string(data, "overall_remark")
    strengths      = _safe_string_list(data.get("strengths", []))
    improvements   = _safe_string_list(data.get("improvements", []))

    if exam_type == _ESSAY_EXAM_TYPE:
        return _map_essay_result(
            data, overall_remark, annotation_comments,
            strengths, improvements, exam_type,
        )
    return _map_standard_result(
        data, overall_remark, annotation_comments,
        strengths, improvements, exam_type,
    )


def _map_standard_result(
    data, overall_remark, annotation_comments, strengths, improvements, exam_type,
) -> EvaluationResult:
    parameter_scores = _map_parameter_scores(data.get("parameter_scores", []))
    total = sum(p.score for p in parameter_scores)
    pct   = total / 50
    grade = "A" if pct >= 0.8 else "B" if pct >= 0.6 else "C" if pct >= 0.4 else "D"
    return EvaluationResult(
        parameter_scores=parameter_scores,
        annotation_comments=annotation_comments,
        before_resubmit=_safe_string_list(data.get("before_resubmit", []), max_items=5),
        exam_type=exam_type,
        strengths=strengths,
        improvements=improvements,
        score_summary=ScoreSummary(total_score=total, max_score=50, grade=grade),
        overall_evaluation=OverallEvaluation(summary_remarks=overall_remark),
        document_summary=DocumentSummary(transcribed_text=""),
    )


def _map_essay_result(
    data, overall_remark, annotation_comments, strengths, improvements, exam_type,
) -> EvaluationResult:
    essay_scores    = _map_essay_parameter_scores(data.get("parameter_scores", []))
    before_resubmit = _safe_string_list(
        data.get("before_resubmit", []), max_len=150, max_items=6
    )
    total = sum(p.score for p in essay_scores)
    pct   = total / 100
    grade = "A" if pct >= 0.8 else "B" if pct >= 0.6 else "C" if pct >= 0.4 else "D"
    return EvaluationResult(
        essay_parameter_scores=essay_scores,
        before_resubmit=before_resubmit,
        annotation_comments=annotation_comments,
        exam_type=exam_type,
        strengths=strengths,
        improvements=improvements,
        score_summary=ScoreSummary(total_score=total, max_score=100, grade=grade),
        overall_evaluation=OverallEvaluation(
            summary_remarks=overall_remark,
            actionable_resubmission_checklist=before_resubmit,
        ),
        document_summary=DocumentSummary(transcribed_text=""),
    )


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


def _map_essay_parameter_scores(raw: list) -> list[EssayParameterScore]:
    known = {p.value: p for p in EssayRubricParameter}
    scores: list[EssayParameterScore] = []
    for item in raw:
        name  = item.get("parameter", "")
        param = known.get(name)
        if param is None:
            logger.warning("unknown_essay_parameter", parameter=name)
            continue
        max_m = ESSAY_RUBRIC_MAX[param]
        scores.append(EssayParameterScore(
            parameter=name,
            score=_clamp(item.get("score", 0), 0, max_m),
            max_score=max_m,
            examiner_remark=str(item.get("examiner_remark", ""))[:120],
            suggestions=_safe_string_list(
                item.get("suggestions", []), max_len=100, max_items=1
            ),
        ))
    if not scores:
        raise EvaluationError("LLM returned no essay parameter scores.")
    return scores


def _map_legacy_annotation_comments(raw: list) -> list[AnnotationComment]:
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


# ── Helpers ───────────────────────────────────────────────────────────────────

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
