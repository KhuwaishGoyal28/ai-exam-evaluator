"""Unit tests for OCR confidence estimator."""
from app.services.ocr.confidence_estimator import estimate_confidence


def test_empty_text_returns_minus_one():
    assert estimate_confidence("") == -1.0


def test_very_short_text_returns_minus_one():
    assert estimate_confidence("hi") == -1.0


def test_clean_english_text_high_confidence():
    text = (
        "The role of civil services in India is very important. "
        "They are responsible for the implementation of government policies. "
        "The IAS officers have a long and distinguished history in the country."
    )
    score = estimate_confidence(text)
    assert score >= 0.5


def test_garbled_text_lower_confidence():
    # Garbled text should score at or below the mid-point threshold
    text = "xqz rrr @@@ ### $$$ ??? !!!  "
    score = estimate_confidence(text)
    assert score <= 0.5
