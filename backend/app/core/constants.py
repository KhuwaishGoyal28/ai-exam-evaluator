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
    ESSAY       = "Essay"           # ← long-form essay (e.g. UPSC Essay Paper)
    CUSTOM      = "Custom / General"


# ── Generic 5-parameter rubric (non-essay exam types) ────────────────────────

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


# ── 12-parameter Essay rubric (matches Roundtable IAS Essay Evaluation Sheet) ─

class EssayRubricParameter(str, Enum):
    INTRODUCTORY_COMPETENCE        = "Introductory competence"
    LUCIDITY_OF_LANGUAGE           = "Lucidity of language"
    INTERLINKAGE_BETWEEN_PARAGRAPHS= "Interlinkage between paragraphs"
    CLARITY_OF_CONCEPT_EXAMPLES    = "Clarity of concept & examples"
    STRUCTURE_OF_ESSAY             = "Structure of essay"
    BODY_ALIGNMENT_WITH_THEME      = "Body & alignment with theme"
    COMMITMENT_TO_TOPIC            = "Commitment to topic"
    CONCLUDING_REMARKS             = "Concluding remarks"
    FRESH_INSIGHTS                 = "Fresh insights"
    VISIONARY_PERSPECTIVES         = "Visionary perspectives"
    SOCIAL_PUBLIC_SERVICE          = "Social & public-service orientation"
    ADHERENCE_TO_WORD_LIMIT        = "Adherence to word limit"


# Maximum marks per essay rubric parameter (total = 100)
ESSAY_RUBRIC_MAX: dict[EssayRubricParameter, int] = {
    EssayRubricParameter.INTRODUCTORY_COMPETENCE:         8,
    EssayRubricParameter.LUCIDITY_OF_LANGUAGE:           10,
    EssayRubricParameter.INTERLINKAGE_BETWEEN_PARAGRAPHS: 8,
    EssayRubricParameter.CLARITY_OF_CONCEPT_EXAMPLES:    12,
    EssayRubricParameter.STRUCTURE_OF_ESSAY:             10,
    EssayRubricParameter.BODY_ALIGNMENT_WITH_THEME:      12,
    EssayRubricParameter.COMMITMENT_TO_TOPIC:             8,
    EssayRubricParameter.CONCLUDING_REMARKS:             10,
    EssayRubricParameter.FRESH_INSIGHTS:                  8,
    EssayRubricParameter.VISIONARY_PERSPECTIVES:          6,
    EssayRubricParameter.SOCIAL_PUBLIC_SERVICE:           6,
    EssayRubricParameter.ADHERENCE_TO_WORD_LIMIT:         2,
}

ESSAY_RUBRIC_DESCRIPTIONS: dict[EssayRubricParameter, str] = {
    EssayRubricParameter.INTRODUCTORY_COMPETENCE: (
        "Quality of the opening — hook, contextualisation, thesis statement clarity. "
        "Does the introduction grip the reader and set up the central argument?"
    ),
    EssayRubricParameter.LUCIDITY_OF_LANGUAGE: (
        "Clarity, grammar, vocabulary range, sentence variety, and absence of "
        "spelling errors. Register must suit an academic essay."
    ),
    EssayRubricParameter.INTERLINKAGE_BETWEEN_PARAGRAPHS: (
        "Smooth transitions and logical connectors between paragraphs. "
        "Ideas must flow and build on each other, not merely be listed."
    ),
    EssayRubricParameter.CLARITY_OF_CONCEPT_EXAMPLES: (
        "Depth of conceptual understanding and quality of examples used. "
        "Examples should be analysed, not merely named."
    ),
    EssayRubricParameter.STRUCTURE_OF_ESSAY: (
        "Visible architecture: introduction, themed body blocks, and a conclusion. "
        "Proportional paragraph lengths; no one section dominates disproportionately."
    ),
    EssayRubricParameter.BODY_ALIGNMENT_WITH_THEME: (
        "Each body paragraph must tie back to the central theme of the essay topic. "
        "No drift into tangential sub-topics."
    ),
    EssayRubricParameter.COMMITMENT_TO_TOPIC: (
        "The essay stays focused on the exact topic throughout. "
        "No wandering into a different essay under the same title."
    ),
    EssayRubricParameter.CONCLUDING_REMARKS: (
        "Quality of the conclusion — synthesis, forward-looking perspective, "
        "returning to the opening quote/idea. Avoids being merely formulaic."
    ),
    EssayRubricParameter.FRESH_INSIGHTS: (
        "Original observations, unexpected angles, or uncommon analogies that go "
        "beyond textbook content that every candidate writes."
    ),
    EssayRubricParameter.VISIONARY_PERSPECTIVES: (
        "Forward-looking ideas: policy recommendations, societal transformation, "
        "or a constructive way ahead — not just diagnosis of problems."
    ),
    EssayRubricParameter.SOCIAL_PUBLIC_SERVICE: (
        "Awareness of governance, administration, public welfare, or social-justice "
        "dimensions relevant to the essay topic."
    ),
    EssayRubricParameter.ADHERENCE_TO_WORD_LIMIT: (
        "Length is within the prescribed word limit (typically 1000–1200 words). "
        "Penalise significantly short essays that stop well below the target."
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
    ExamType.ESSAY: (
        "Long-form essay (e.g. UPSC Essay Paper, 1000–1200 words). "
        "Evaluate using the 12-parameter essay rubric: introduction quality, language "
        "lucidity, paragraph interlinkage, conceptual clarity, structure, body-theme "
        "alignment, topic commitment, conclusion, fresh insights, visionary outlook, "
        "social/governance orientation, and word-limit adherence. "
        "Score strictly: exceptional essays rarely exceed 75/100."
    ),
    ExamType.CUSTOM: (
        "General descriptive answer. Apply balanced academic standards across all rubric "
        "parameters appropriate for the context. Reward clarity, accuracy, and depth."
    ),
}

OCR_CONFIDENCE_THRESHOLD: float = 0.50
MAX_ANNOTATION_COMMENTS: int = 8
