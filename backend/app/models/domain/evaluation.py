"""
Domain model for the evaluation result.
Pure data — no business logic, no I/O.
"""
from dataclasses import dataclass, field
from app.core.constants import RubricParameter


@dataclass
class ParameterScore:
    parameter: RubricParameter
    score: int
    max_score: int
    justification: str
    suggestions: list[str] = field(default_factory=list)  # actionable tips


@dataclass
class AnnotationComment:
    paragraph_index: int
    comment_text: str
    sentiment: str  # "positive" | "neutral" | "negative"


@dataclass
class EvaluationResult:
    parameter_scores: list[ParameterScore] = field(default_factory=list)
    total_score: int = 0
    max_total_score: int = 50
    overall_remark: str = ""
    annotation_comments: list[AnnotationComment] = field(default_factory=list)
    exam_type: str = "UPSC Mains"
    strengths: list[str] = field(default_factory=list)
    improvements: list[str] = field(default_factory=list)

    def compute_total(self) -> None:
        self.total_score = sum(p.score for p in self.parameter_scores)
