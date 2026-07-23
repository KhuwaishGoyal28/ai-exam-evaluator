"""
Domain model for the evaluation result.
Pure data — no business logic, no I/O.

Primary schema matches the teacher-evaluation JSON from the Vision agent:
  student_name, subject, total_marks, grade, rubric (9 params),
  strengths, weaknesses, remarks, annotations (paragraph+sentence coords)
"""
from __future__ import annotations
from dataclasses import dataclass, field
from app.core.constants import RubricParameter


# ── Primary schema types (teacher-evaluation) ─────────────────────────────────

@dataclass
class RubricItem:
    """One row in the 9-parameter CBSE rubric table."""
    marks: int
    max: int
    remark: str = ""


@dataclass
class TeacherAnnotation:
    """
    One red-ink annotation on the answer sheet.
    Position is logical (paragraph + sentence), not pixel-based.
    The PDF renderer calculates actual positions from these.
    """
    page: int                    # 1-based page number
    paragraph: int               # 1-based paragraph number on the page
    annotation_type: str         # tick | cross | circle | underline | comment
    comment: str                 # 2-5 word teacher remark
    sentence: int | None = None  # 1-based sentence within paragraph (optional)


@dataclass
class EvaluationSummary:
    """Top-level evaluation result matching the Vision agent output schema."""
    student_name: str = ""
    subject: str = ""
    has_handwritten_content: bool = True
    transcribed_text: str = ""
    total_marks: int = 0
    max_marks: int = 100
    grade: str = "D"
    performance_level: str = "Needs Improvement"
    rubric: dict[str, RubricItem] = field(default_factory=dict)
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    remarks: str = ""
    annotations: list[TeacherAnnotation] = field(default_factory=list)
    total_pages: int = 1

    def annotations_for_page(self, page_num: int) -> list[TeacherAnnotation]:
        """Return all annotations for a given 1-based page number."""
        return [a for a in self.annotations if a.page == page_num]

    @property
    def rubric_total(self) -> int:
        """Sum of all rubric marks (should equal total_marks)."""
        return sum(item.marks for item in self.rubric.values())


# ── Legacy types (kept for backward-compat with standard/essay rubric paths) ──

@dataclass
class DocumentSummary:
    total_pages: int = 1
    estimated_word_count: int = 0
    target_word_count: int = 1200
    transcription_status: str = "SUCCESS"
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
    y_percent: float = 50.0
    position: str = "RIGHT_MARGIN"


@dataclass
class PageAnnotation:
    """Legacy pixel-position annotation (kept for old pipeline compat)."""
    annotation_type: str
    target_snippet: str
    mark_symbol: str
    annotation_text: str
    location: AnnotationLocation = field(default_factory=AnnotationLocation)
    page_number: int = 1


@dataclass
class ParameterBreakdown:
    parameter_name: str
    marks_obtained: int
    max_marks: int
    examiner_remark: str


@dataclass
class OverallEvaluation:
    summary_remarks: str = ""
    actionable_resubmission_checklist: list[str] = field(default_factory=list)


@dataclass
class ParameterScore:
    """Score for one parameter in the standard 5-param rubric."""
    parameter: RubricParameter
    score: int
    max_score: int
    justification: str
    suggestions: list[str] = field(default_factory=list)


@dataclass
class EssayParameterScore:
    """Score for one parameter in the 12-param essay rubric."""
    parameter: str
    score: int
    max_score: int
    examiner_remark: str
    suggestions: list[str] = field(default_factory=list)


@dataclass
class AnnotationComment:
    """Legacy paragraph-based annotation for the PIL annotation pipeline."""
    paragraph_index: int
    comment_text: str
    sentiment: str   # positive | neutral | negative


# ── Unified EvaluationResult ──────────────────────────────────────────────────

@dataclass
class EvaluationResult:
    """
    Unified result object.

    PRIMARY (handwritten path):
      evaluation_summary is populated — use this for all output.

    LEGACY (text PDF fallback path):
      parameter_scores / essay_parameter_scores are populated instead.
    """

    # ── Primary: teacher-evaluation schema ────────────────────────────────
    evaluation_summary: EvaluationSummary = field(
        default_factory=EvaluationSummary
    )

    # ── Legacy: old rubric schemas ────────────────────────────────────────
    document_summary: DocumentSummary = field(default_factory=DocumentSummary)
    score_summary: ScoreSummary = field(default_factory=ScoreSummary)
    page_annotations: list[PageAnnotation] = field(default_factory=list)
    parameter_breakdown: list[ParameterBreakdown] = field(default_factory=list)
    overall_evaluation: OverallEvaluation = field(default_factory=OverallEvaluation)
    parameter_scores: list[ParameterScore] = field(default_factory=list)
    essay_parameter_scores: list[EssayParameterScore] = field(default_factory=list)
    before_resubmit: list[str] = field(default_factory=list)
    annotation_comments: list[AnnotationComment] = field(default_factory=list)

    # ── Shared ────────────────────────────────────────────────────────────
    exam_type: str = "Custom / General"
    strengths: list[str] = field(default_factory=list)
    improvements: list[str] = field(default_factory=list)

    # ── Computed properties (read either primary or legacy) ───────────────

    @property
    def total_score(self) -> int:
        es = self.evaluation_summary
        if es.total_marks:
            return es.total_marks
        if self.score_summary.total_score:
            return self.score_summary.total_score
        if self.essay_parameter_scores:
            return sum(p.score for p in self.essay_parameter_scores)
        return sum(p.score for p in self.parameter_scores)

    @property
    def max_total_score(self) -> int:
        return self.evaluation_summary.max_marks or self.score_summary.max_score or 100

    @property
    def overall_remark(self) -> str:
        return (
            self.evaluation_summary.remarks
            or self.overall_evaluation.summary_remarks
        )

    @property
    def is_essay(self) -> bool:
        return bool(self.essay_parameter_scores)

    @property
    def is_primary(self) -> bool:
        """True when the Vision teacher-evaluation path was used."""
        return self.evaluation_summary.has_handwritten_content

    def compute_total(self) -> None:
        """Back-compat: sync legacy score_summary from primary source."""
        self.score_summary.total_score = self.total_score
        self.score_summary.max_score   = self.max_total_score
        self.score_summary.grade       = self.evaluation_summary.grade

    def annotations_for_page(self, page_num: int) -> list[PageAnnotation]:
        """Legacy helper — returns old-style PageAnnotation for given page."""
        return [a for a in self.page_annotations if a.page_number == page_num]
