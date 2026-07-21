"""Unit tests for text_utils — pure functions, no mocks needed."""
import pytest
from app.utils.text_utils import (
    count_words,
    split_into_paragraphs,
    truncate_text,
    sanitise_for_prompt,
)


def test_count_words_basic():
    assert count_words("Hello world foo") == 3


def test_count_words_extra_whitespace():
    assert count_words("  hello   world  ") == 2


def test_split_paragraphs_blank_lines():
    text = "Para one.\n\nPara two.\n\nPara three."
    result = split_into_paragraphs(text)
    assert len(result) == 3
    assert result[0] == "Para one."


def test_split_paragraphs_newline_fallback():
    text = "Line one.\nLine two.\nLine three."
    result = split_into_paragraphs(text)
    assert len(result) == 3


def test_truncate_respects_word_boundary():
    text = "Hello world this is a test"
    result = truncate_text(text, max_chars=11)
    assert result.startswith("Hello")
    assert len(result) <= 15  # word boundary + ellipsis


def test_truncate_no_op_when_short():
    text = "Short text"
    assert truncate_text(text, max_chars=100) == text


def test_sanitise_removes_prompt_injection():
    text = "Normal text ``` with backticks <| and pipes"
    result = sanitise_for_prompt(text)
    assert "```" not in result
    assert "<|" not in result
