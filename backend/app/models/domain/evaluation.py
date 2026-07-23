"""
Domain model for the evaluation result.
Pure data — no business logic, no I/O.

Supports two rubric modes:
  Standard  — 5 parameters, 0–10 each, total /50
  Essay     — 12 parameters, variable max, total /100
"""
from dataclasses import dataclass, field
from app.core.constants import RubricParameter


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
    parameter: str          # EssayRubricParameter.value string
    score: int
    max_score: int          # per-parameter maximum (varies: 2–12)
    examiner_remark: str    # crisp one-line remark as on the evaluation sheet
    suggestions: list[str] = field(default_factory=list)


@dataclass
class AnnotationComment:
    paragraph_index: int
    comment_text: str
    sentiment: str  # "positive" | "neutral" | "negative"


@dataclass
class EvaluationResult:
    # ── Standard rubric fields ────────────────────────────────────────────────
    parameter_scores: list[ParameterScore] = field(default_factory=list)

    # ── Essay rubric fields (populated only when exam_type == "Essay") ────────
    essay_parameter_scores: list[EssayParameterScore] = field(default_factory=list)
    before_resubmit: list[str] = field(default_factory=list)   # numbered checklist

    # ── Shared fields ─────────────────────────────────────────────────────────
    total_score: int = 0
    max_total_score: int = 50          # 50 for standard, 100 for essay
    overall_remark: str = ""
    annotation_comments: list[AnnotationComment] = field(default_factory=list)
    exam_type: str = "Custom / General"
    strengths: list[str] = field(default_factory=list)
    improvements: list[str] = field(default_factory=list)

    def compute_total(self) -> None:
        """Sum scores from whichever rubric is populated."""
        if self.essay_parameter_scores:
            self.total_score = sum(p.score for p in self.essay_parameter_scores)
        else:
            self.total_score = sum(p.score for p in self.parameter_scores)

    @property
    def is_essay(self) -> bool:
        return bool(self.essay_parameter_scores)
