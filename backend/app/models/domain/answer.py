"""
Domain model representing a submitted answer and its processing state.
Pure data — no business logic, no I/O.
"""
from dataclasses import dataclass, field
from app.core.constants import FileType


@dataclass
class UploadedFile:
    """Raw file received from the user before any processing."""
    filename: str
    mime_type: str
    file_type: FileType
    content: bytes
    size_bytes: int


@dataclass
class StoredFile:
    """A file that has been persisted to cloud storage."""
    public_id: str
    url: str
    secure_url: str
    resource_type: str
    format: str


@dataclass
class OCRResult:
    """Output of the OCR pipeline."""
    extracted_text: str
    confidence: float          # 0.0 – 1.0; -1.0 if provider doesn't report it
    word_count: int
    paragraph_blocks: list[str] = field(default_factory=list)
    low_confidence: bool = False
