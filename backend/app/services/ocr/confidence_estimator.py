"""
Estimates OCR confidence from the extracted text heuristically.
Single responsibility: text → confidence score float.

We cannot get a per-token confidence from GPT-4o, so we use proxy signals:
- ratio of non-ASCII / total chars (high → messy handwriting)
- average word length (very short or very long → likely garbled)
- presence of recognisable English words (using a small common-word set)
"""
import re

_COMMON_WORDS = frozenset({
    "the", "and", "is", "in", "of", "to", "a", "that", "it", "was",
    "for", "on", "are", "as", "with", "his", "they", "at", "be", "this",
    "have", "from", "or", "an", "but", "not", "what", "all", "were", "we",
    "when", "your", "can", "said", "there", "use", "each", "which", "she",
    "do", "how", "their", "if", "will", "up", "other", "about", "out", "many",
})


def estimate_confidence(text: str) -> float:
    """
    Return a confidence float in [0.0, 1.0].
    Returns -1.0 if the text is empty (unable to estimate).
    """
    if not text or len(text.strip()) < 10:
        return -1.0

    words = text.split()
    if not words:
        return -1.0

    non_ascii_chars = sum(1 for c in text if ord(c) > 127)
    non_ascii_ratio = non_ascii_chars / max(len(text), 1)

    avg_word_len = sum(len(w) for w in words) / len(words)
    word_len_score = 1.0 if 3.5 <= avg_word_len <= 9.0 else 0.5

    lower_words = [w.lower().strip(".,;:!?\"'()") for w in words]
    common_hit_ratio = sum(1 for w in lower_words if w in _COMMON_WORDS) / len(lower_words)

    score = (
        (1.0 - min(non_ascii_ratio * 5, 1.0)) * 0.4
        + word_len_score * 0.2
        + common_hit_ratio * 0.4
    )
    return round(min(max(score, 0.0), 1.0), 3)
