"""
Pure text-processing helpers used by OCR and evaluation services.
No I/O — safe to unit-test in isolation.
"""
import re


def count_words(text: str) -> int:
    """Return word count of a string (handles extra whitespace gracefully)."""
    return len(text.split())


def split_into_paragraphs(text: str) -> list[str]:
    """
    Split OCR text into paragraph blocks.
    Uses blank lines as separators; falls back to newlines if no blank lines exist.
    """
    paragraphs = re.split(r"\n{2,}", text.strip())
    if len(paragraphs) <= 1:
        # Single-block text: split on single newlines as a fallback
        paragraphs = [line.strip() for line in text.splitlines() if line.strip()]
    return [p.strip() for p in paragraphs if p.strip()]


def truncate_text(text: str, max_chars: int = 4000) -> str:
    """Truncate text to max_chars, preserving whole words."""
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars]
    last_space = truncated.rfind(" ")
    return truncated[:last_space] + "…" if last_space > 0 else truncated


def sanitise_for_prompt(text: str) -> str:
    """Remove characters that could confuse prompt delimiters."""
    return text.replace("```", "'''").replace("<|", "< |").strip()
