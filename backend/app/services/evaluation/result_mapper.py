"""
Maps raw Vision agent JSON → EvaluationResult domain object.

PRIMARY PATH  (teacher-evaluation schema from Vision agent):
  map_vision_result(data, exam_type) → EvaluationResult
  Schema: {student_name, subject, total_marks, grade, rubric{}, annotations[]}

LEGACY PATH  (text-LLM fallback — standard 5-param or essay 12-param):
  map_llm_response_to_result(data, exam_type) → EvaluationResult
"""
from __future__ import annotations

from app.core.constants import RubricParameter, EssayRubricParameter, ESSAY_RUBRIC_MAX
from app.core.exceptions import EvaluationError
from app.core.logging import get_logger
from app.models.domain.evaluation import (
    EvaluationResult,
    EvaluationSummary,
    RubricItem,
    TeacherAnnotation,
    # Legacy types
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

# ── CBSE 9-parameter rubric defaults ─────────────────────────────────────────
_RUBRIC_DEFAULTS: dict[str, int] = {
    "introduction": 5,
    "content":      20,
    "grammar":      10,
    "vocabulary":   10,
    "presentation": 10,
    "handwriting":  20,
    "conclusion":   5,
    "creativity":   10,
    "flow":         10,
}

_VALID_ANNOTATION_TYPES = {"tick", "cross", "circle", "underline", "comment"}
_ESSAY_EXAM_TYPE = "Essay"


# ── Primary mapper ────────────────────────────────────────────────────────────

def map_vision_result(
    data: dict,
    exam_type: str = "Custom / General",
) -> EvaluationResult:
    """
    Map the teacher-evaluation JSON from run_vision_evaluation() → EvaluationResult.
    This is the primary path for all handwritten uploads.
    """
    summary = _map_evaluation_summary(data)
    total_pages = int(data.get("total_pages", 1))
    summary.total_pages = total_pages

    # Build legacy AnnotationComment list from TeacherAnnotations so the
    # old PIL pipeline can still render something if PyMuPDF is unavailable.
    legacy_comments = _teacher_annotations_to_legacy_comments(summary.annotations)

    # Build legacy page_annotations from TeacherAnnotations
    legacy_page_anns = _teacher_annotations_to_page_annotations(summary.annotations)

    return EvaluationResult(
        evaluation_summary=summary,
        annotation_comments=legacy_comments,
        page_annotations=legacy_page_anns,
        exam_type=exam_type,
        strengths=summary.strengths[:4],
        improvements=summary.weaknesses[:4],
        score_summary=ScoreSummary(
            total_score=summary.total_marks,
            max_score=summary.max_marks,
            grade=summary.grade,
            performance_status=summary.performance_level,
        ),
        overall_evaluation=OverallEvaluation(
            summary_remarks=summary.remarks,
            actionable_resubmission_checklist=summary.weaknesses[:5],
        ),
        document_summary=DocumentSummary(
            total_pages=total_pages,
            transcribed_text=summary.transcribed_text,
            has_handwritten_content=summary.has_handwritten_content,
        ),
    )


def _map_evaluation_summary(data: dict) -> EvaluationSummary:
    total = _clamp(data.get("total_marks", 0), 0, 200)
    max_m = int(data.get("max_marks", 100)) or 100
    pct   = total / max_m

    grade = str(data.get("grade", "")).strip()
    if not grade:
        grade = _compute_grade(pct)

    perf = str(data.get("performance_level", "")).strip()
    if not perf:
        perf = _compute_performance(pct)

    rubric = _map_rubric(data.get("rubric", {}))

    # If rubric total doesn't match total_marks, use rubric total
    rubric_total = sum(item.marks for item in rubric.values())
    if rubric_total > 0 and abs(rubric_total - total) > 5:
        logger.warning("rubric_total_mismatch",
                       rubric_total=rubric_total, reported_total=total)
        total = rubric_total

    annotations = _map_annotations(data.get("annotations", []))

    return EvaluationSummary(
        student_name=str(data.get("student_name", "")).strip()[:100],
        subject=str(data.get("subject", "")).strip()[:100],
        has_handwritten_content=bool(data.get("has_handwritten_content", True)),
        transcribed_text=str(data.get("transcribed_text", ""))[:8000],
        total_marks=total,
        max_marks=max_m,
        grade=grade,
        performance_level=perf,
        rubric=rubric,
        strengths=_safe_str_list(data.get("strengths", []), max_items=5),
        weaknesses=_safe_str_list(data.get("weaknesses", []), max_items=5),
        remarks=str(data.get("remarks", "")).strip()[:500],
        annotations=annotations,
    )


def _map_rubric(raw: dict) -> dict[str, RubricItem]:
    result: dict[str, RubricItem] = {}
    for key, default_max in _RUBRIC_DEFAULTS.items():
        raw_item = raw.get(key, {})
        if isinstance(raw_item, dict):
            marks  = _clamp(raw_item.get("marks", 0), 0, default_max)
            max_v  = int(raw_item.get("max", default_max))
            remark = str(raw_item.get("remark", "")).strip()[:150]
        else:
            marks  = _clamp(raw_item, 0, default_max)
            max_v  = default_max
            remark = ""
        result[key] = RubricItem(marks=marks, max=max_v, remark=remark)
    return result


def _map_annotations(raw: list) -> list[TeacherAnnotation]:
    result: list[TeacherAnnotation] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        ann_type = str(item.get("type", "comment")).lower().strip()
        if ann_type not in _VALID_ANNOTATION_TYPES:
            ann_type = "comment"
        comment = str(item.get("comment", "")).strip()[:80]
        if not comment:
            continue
        page      = max(1, int(item.get("page", 1)))
        paragraph = max(1, int(item.get("paragraph", 1)))
        sentence_raw = item.get("sentence")
        sentence = max(1, int(sentence_raw)) if sentence_raw is not None else None
        result.append(TeacherAnnotation(
            page=page,
            paragraph=paragraph,
            annotation_type=ann_type,
            comment=comment,
            sentence=sentence,
        ))
    return result


# ── Legacy converters ─────────────────────────────────────────────────────────

def _teacher_annotations_to_legacy_comments(
    annotations: list[TeacherAnnotation],
) -> list[AnnotationComment]:
    """Convert TeacherAnnotation → AnnotationComment for the old PIL pipeline."""
    SENTIMENT = {
        "tick":      "positive",
        "underline": "positive",
        "cross":     "negative",
        "circle":    "negative",
        "comment":   "neutral",
    }
    result: list[AnnotationComment] = []
    for ann in annotations:
        # Approximate paragraph_index from paragraph number (0-based)
        para_idx = max(0, ann.paragraph - 1)
        result.append(AnnotationComment(
            paragraph_index=para_idx,
            comment_text=ann.comment[:100],
            sentiment=SENTIMENT.get(ann.annotation_type, "neutral"),
        ))
    return result


def _teacher_annotations_to_page_annotations(
    annotations: list[TeacherAnnotation],
) -> list[PageAnnotation]:
    """Convert TeacherAnnotation → legacy PageAnnotation (y_percent approximated)."""
    TYPE_MAP = {
        "tick":      ("PRAISE",          "TICK"),
        "cross":     ("CORRECTION",      "CROSS"),
        "circle":    ("CORRECTION",      "CIRCLE"),
        "underline": ("PRAISE",          "UNDERLINE"),
        "comment":   ("STRUCTURAL_NOTE", "MARGIN_BOX"),
    }
    result: list[PageAnnotation] = []
    for ann in annotations:
        ann_type, mark_sym = TYPE_MAP.get(ann.annotation_type, ("STRUCTURAL_NOTE", "MARGIN_BOX"))
        # Approximate y_percent from paragraph (assume ~10 paragraphs per page)
        y_pct = min(95.0, (ann.paragraph - 1) * 10.0 + 5.0)
        result.append(PageAnnotation(
            annotation_type=ann_type,
            target_snippet="",
            mark_symbol=mark_sym,
            annotation_text=ann.comment,
            location=AnnotationLocation(y_percent=y_pct, position="RIGHT_MARGIN"),
            page_number=ann.page,
        ))
    return result


# ── Legacy LLM mapper (text PDF fallback) ────────────────────────────────────

def map_llm_response_to_result(
    data: dict,
    exam_type: str = "Custom / General",
) -> EvaluationResult:
    """
    Legacy path: map Groq text-eval JSON → EvaluationResult.
    Used when the upload is a typed/text PDF with no handwritten content.
    """
    annotation_comments = _map_legacy_annotation_comments(
        data.get("annotation_comments", [])
    )
    overall_remark = _require_string(data, "overall_remark")
    strengths      = _safe_str_list(data.get("strengths", []))
    improvements   = _safe_str_list(data.get("improvements", []))

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
    grade = _compute_grade_legacy(pct)
    return EvaluationResult(
        parameter_scores=parameter_scores,
        annotation_comments=annotation_comments,
        before_resubmit=_safe_str_list(
            data.get("before_resubmit", []), max_items=5
        ),
        exam_type=exam_type,
        strengths=strengths,
        improvements=improvements,
        score_summary=ScoreSummary(
            total_score=total, max_score=50, grade=grade
        ),
        overall_evaluation=OverallEvaluation(summary_remarks=overall_remark),
        document_summary=DocumentSummary(transcribed_text=""),
        evaluation_summary=EvaluationSummary(
            has_handwritten_content=False,
            total_marks=total,
            max_marks=50,
            grade=grade,
            remarks=overall_remark,
        ),
    )


def _map_essay_result(
    data, overall_remark, annotation_comments, strengths, improvements, exam_type,
) -> EvaluationResult:
    essay_scores    = _map_essay_parameter_scores(data.get("parameter_scores", []))
    before_resubmit = _safe_str_list(
        data.get("before_resubmit", []), max_len=150, max_items=6
    )
    total = sum(p.score for p in essay_scores)
    pct   = total / 100
    grade = _compute_grade_legacy(pct)
    return EvaluationResult(
        essay_parameter_scores=essay_scores,
        before_resubmit=before_resubmit,
        annotation_comments=annotation_comments,
        exam_type=exam_type,
        strengths=strengths,
        improvements=improvements,
        score_summary=ScoreSummary(
            total_score=total, max_score=100, grade=grade
        ),
        overall_evaluation=OverallEvaluation(
            summary_remarks=overall_remark,
            actionable_resubmission_checklist=before_resubmit,
        ),
        document_summary=DocumentSummary(transcribed_text=""),
        evaluation_summary=EvaluationSummary(
            has_handwritten_content=False,
            total_marks=total,
            max_marks=100,
            grade=grade,
            remarks=overall_remark,
        ),
    )


def _map_parameter_scores(raw: list) -> list[ParameterScore]:
    known = {p.value: p for p in RubricParameter}
    scores: list[ParameterScore] = []
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
            suggestions=_safe_str_list(item.get("suggestions", [])),
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
            suggestions=_safe_str_list(
                item.get("suggestions", []), max_len=100, max_items=1
            ),
        ))
    if not scores:
        raise EvaluationError("LLM returned no essay parameter scores.")
    return scores


def _map_legacy_annotation_comments(raw: list) -> list[AnnotationComment]:
    out: list[AnnotationComment] = []
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

def _compute_grade(pct: float) -> str:
    if pct >= 0.90: return "A+"
    if pct >= 0.80: return "A"
    if pct >= 0.70: return "B+"
    if pct >= 0.60: return "B"
    if pct >= 0.50: return "C"
    if pct >= 0.40: return "D"
    return "F"


def _compute_grade_legacy(pct: float) -> str:
    if pct >= 0.8: return "A"
    if pct >= 0.6: return "B"
    if pct >= 0.4: return "C"
    return "D"


def _compute_performance(pct: float) -> str:
    if pct >= 0.90: return "Excellent"
    if pct >= 0.75: return "Very Good"
    if pct >= 0.60: return "Good"
    if pct >= 0.45: return "Average"
    return "Needs Improvement"


def _require_string(data: dict, key: str) -> str:
    val = data.get(key, "")
    if not val:
        raise EvaluationError(f"LLM returned empty '{key}'.")
    return str(val)[:600]


def _safe_str_list(
    raw: list,
    max_len: int = 200,
    max_items: int = 6,
) -> list[str]:
    return [str(s)[:max_len] for s in raw if s and str(s).strip()][:max_items]


def _clamp(v, lo: int, hi: int) -> int:
    try:
        return max(lo, min(hi, int(v)))
    except (TypeError, ValueError):
        return lo


def _norm_sentiment(v: str) -> str:
    v = str(v).lower()
    return v if v in {"positive", "neutral", "negative"} else "neutral"
