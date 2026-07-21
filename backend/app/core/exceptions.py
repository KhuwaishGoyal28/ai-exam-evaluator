"""
Domain-specific exceptions.
Each exception maps to one well-defined failure mode.
HTTP status mapping is done in the exception handlers, not here.
"""


class AnswerCheckError(Exception):
    """Base for all application errors."""


class UnsupportedFileTypeError(AnswerCheckError):
    """Raised when uploaded file MIME type is not allowed."""


class FileTooLargeError(AnswerCheckError):
    """Raised when uploaded file exceeds the size limit."""


class OCRExtractionError(AnswerCheckError):
    """Raised when OCR pipeline fails to extract text."""


class LowOCRConfidenceError(AnswerCheckError):
    """Raised when OCR confidence is below acceptable threshold."""


class EvaluationError(AnswerCheckError):
    """Raised when LLM evaluation pipeline fails."""


class AnnotationError(AnswerCheckError):
    """Raised when image/PDF annotation pipeline fails."""


class StorageError(AnswerCheckError):
    """Raised when cloud storage upload/download fails."""


class ExternalServiceError(AnswerCheckError):
    """Raised when a third-party service returns an unexpected error."""
