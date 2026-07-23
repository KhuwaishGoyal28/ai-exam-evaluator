"""
Domain model for the evaluation result.
Pure data — no business logic, no I/O.

Matches the master JSON schema from the Vision agent:
  document_summary, score_summary, page_annotations,
  parameter_breakdown, overall_evaluation
"""
from __future__ import annotations
from dataclasses import dataclass, field
from app.core.constants import RubricParameter


# ── Master-schema types ───────────────────────────────────────────────────────

@dataclass
class DocumentSummary:
    total_pages: int = 1
    estimated_word_count: int = 0
    target_word_count: int = 1200
    transcription_status: str = "SUCCESS"   # SUCCESS | PARTIAL | FAILED
    has_handwritten_content: bool = True
    transcribed_text: str = ""


@dataclass
class ScoreSummary:
    total_score: int = 0
    max_score: int = 100
    grade: str = "D"
    performance_status: str = "Needs Work"


@dataclass
class AnnotationLocation:
    y_percent: float = 50.0             # 0 = top of page, 100 = bottom
    position: str = "RIGHT_MARGIN"      # RIGHT_MARGIN | LEFT_MARGIN | INLINE


@dataclass
class PageAnnotation:
    """One red-ink mark on a specific page."""
    annotation_type: str            # PRAISE | CORRECTION | STRUCTURAL_NOTE
    target_snippet: str             # exact quoted text from student handwriting
    mark_symbol: str                # TICK | CROSS | CIRCLE | UNDERLINE | MARGIN_BOX
    annotation_text: str            # short red ink margin comment
    location: AnnotationLocation = field(default_factory=AnnotationLocation)
    page_number: int = 1


@dataclass
class ParameterBreakdown:
    """One row in the parameter rubric table."""
    parameter_name: str
    marks_obtained: int
    max_marks: int
    examiner_remark: str


@dataclass
class OverallEvaluation:
    summary_remarks: str = ""
    actionable_resubmission_checklist: list[str] = field(default_factory=list)


# ── Legacy types (kept for backward-compat with standard/essay rubric paths) ──

@dataclass
class ParameterScore:
    """Score entry for one rubric parameter (standard 5-param rubric)."""
    parameter: RubricParameter
    score: int
    max_score: int
    justification: str
    suggestions: list[str] = field(default_factory=list)


@dataclass
class EssayParameterScore:
    """Score entry for one parameter in the 12-param essay rubric."""
    parameter: str
    score: int
    max_score: int
    examiner_remark: str
    suggestions: list[str] = field(default_factory=list)


@dataclass
class AnnotationComment:
    """Legacy paragraph-based annotation (kept for image annotation pipeline)."""
    paragraph_index: int
    comment_text: str
    sentiment: str      # "positive" | "neutral" | "negative"


# ── Unified EvaluationResult ──────────────────────────────────────────────────

@dataclass
class EvaluationResult:
    # ── Master-schema fields (primary) ───────────────────────────────────────
    document_summary: DocumentSummary = field(default_factory=DocumentSummary)
    score_summary: ScoreSummary = field(default_factory=ScoreSummary)
    page_annotations: list[PageAnnotation] = field(default_factory=list)
    parameter_breakdown: list[ParameterBreakdown] = field(default_factory=list)
    overall_evaluation: OverallEvaluation = field(default_factory=OverallEvaluation)

    # ── Legacy rubric fields (used when falling back to text-only LLM eval) ──
    parameter_scores: list[ParameterScore] = field(default_factory=list)
    essay_parameter_scores: list[EssayParameterScore] = field(default_factory=list)
    before_resubmit: list[str] = field(default_factory=list)
    annotation_comments: list[AnnotationComment] = field(default_factory=list)

    # ── Shared convenience fields ─────────────────────────────────────────────
    exam_type: str = "Custom / General"
    strengths: list[str] = field(default_factory=list)
    improvements: list[str] = field(default_factory=list)

    # ── Computed properties ───────────────────────────────────────────────────

    @property
    def total_score(self) -> int:
        if self.score_summary.total_score:
            return self.score_summary.total_score
        if self.essay_parameter_scores:
            return sum(p.score for p in self.essay_parameter_scores)
        return sum(p.score for p in self.parameter_scores)

    @property
    def max_total_score(self) -> int:
        return self.score_summary.max_score or 100

    @property
    def overall_remark(self) -> str:
        return self.overall_evaluation.summary_remarks

    @property
    def is_essay(self) -> bool:
        return bool(self.essay_parameter_scores)

    def compute_total(self) -> None:
        """Back-compat: sync legacy score into score_summary."""
        if self.essay_parameter_scores:
            self.score_summary.total_score = sum(
                p.score for p in self.essay_parameter_scores
            )
        elif self.parameter_scores:
            self.score_summary.total_score = sum(
                p.score for p in self.parameter_scores
            )

    def annotations_for_page(self, page_num: int) -> list[PageAnnotation]:
        """Return all PageAnnotations for a given 1-based page number."""
        return [a for a in self.page_annotations if a.page_number == page_num]
