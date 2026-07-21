"""
Immutable application-level constants.
Nothing from config goes here — only things that never change.
"""
from enum import Enum


class FileType(str, Enum):
    IMAGE = "image"
    PDF   = "pdf"


class ExamType(str, Enum):
    # School
    CLASS_6_8   = "Class 6–8 Test"
    CLASS_9_10  = "Class 9–10 / Board"
    CLASS_11_12 = "Class 11–12 / Board"
    # Entrance / Competitive
    JEE         = "JEE / Engineering"
    NEET        = "NEET / Medical"
    UPSC        = "UPSC / Civil Services"
    LAW         = "CLAT / Law"
    MBA         = "CAT / MBA"
    # College / University
    COLLEGE     = "College / University"
    # Others
    LANGUAGE    = "Language / Literature"
    CUSTOM      = "Custom / General"


class RubricParameter(str, Enum):
    STRUCTURE         = "Structure"
    CONTENT_ACCURACY  = "Content & Accuracy"
    LANGUAGE          = "Language & Expression"
    RELEVANCE         = "Relevance to Question"
    CRITICAL_THINKING = "Critical Thinking"


RUBRIC_DESCRIPTIONS: dict[RubricParameter, str] = {
    RubricParameter.STRUCTURE: (
        "Logical flow: introduction, body paragraphs, conclusion. "
        "Coherent transitions between ideas."
    ),
    RubricParameter.CONTENT_ACCURACY: (
        "Factual correctness, relevant examples, depth of knowledge, "
        "no misleading or invented facts."
    ),
    RubricParameter.LANGUAGE: (
        "Grammar, vocabulary, sentence clarity, and conciseness. "
        "Register appropriate for the subject and level."
    ),
    RubricParameter.RELEVANCE: (
        "Directly addresses the question asked. "
        "Stays on topic; no padding or off-topic content."
    ),
    RubricParameter.CRITICAL_THINKING: (
        "Analysis beyond facts: reasoning, implications, "
        "balanced arguments, original insight."
    ),
}

# Exam-type-specific context injected into the LLM evaluation prompt.
EXAM_TYPE_CONTEXT: dict[ExamType, str] = {
    ExamType.CLASS_6_8: (
        "School test for classes 6–8. Evaluate age-appropriately: clarity of thought, "
        "basic factual accuracy, neat structure, and simple correct language. "
        "Be encouraging; mark scheme is lenient. Short answers expected."
    ),
    ExamType.CLASS_9_10: (
        "Class 9–10 board-level answer. Evaluate for key point coverage, definitions, "
        "examples, diagrams (if any), and correct subject terminology. "
        "Follow board marking scheme: marks per point/step."
    ),
    ExamType.CLASS_11_12: (
        "Class 11–12 board or pre-entrance answer. Evaluate for conceptual depth, "
        "correct formulae/derivations (Science), analytical arguments (Humanities/Commerce), "
        "structured presentation, and subject-specific terminology."
    ),
    ExamType.JEE: (
        "JEE / Engineering entrance descriptive answer. Evaluate for conceptual clarity, "
        "correct formulae and derivations, stepwise solution, units and significant figures. "
        "Award partial credit for correct intermediate steps. Precision over verbosity."
    ),
    ExamType.NEET: (
        "NEET / Medical entrance answer. Evaluate for anatomical/physiological accuracy, "
        "correct medical terminology, clinical relevance, and labelled diagrams. "
        "Mark scheme is point-based."
    ),
    ExamType.UPSC: (
        "UPSC Civil Services Mains (GS/Essay). Evaluate for multi-dimensional analysis, "
        "current affairs integration, constitutional/ethical perspective, and balanced "
        "arguments. Expected length: 150–250 words. Academic register required."
    ),
    ExamType.LAW: (
        "CLAT / Law exam answer. Evaluate for legal reasoning, case law citation, "
        "statutory interpretation, logical argument flow, and conclusion precision."
    ),
    ExamType.MBA: (
        "CAT / MBA entrance answer. Evaluate for data interpretation accuracy, "
        "quantitative reasoning steps, business context application, and concise conclusions."
    ),
    ExamType.COLLEGE: (
        "College or university-level answer. Evaluate for academic rigour, theoretical "
        "understanding, evidence-based arguments, proper citations (if mentioned), "
        "and structured academic writing."
    ),
    ExamType.LANGUAGE: (
        "Language or literature answer. Evaluate for textual comprehension, use of "
        "literary devices, grammar and expression quality, interpretation depth, "
        "and coherent written argument."
    ),
    ExamType.CUSTOM: (
        "General descriptive answer. Apply balanced academic standards across all rubric "
        "parameters appropriate for the context. Reward clarity, accuracy, and depth."
    ),
}

OCR_CONFIDENCE_THRESHOLD: float = 0.50
MAX_ANNOTATION_COMMENTS: int = 8
