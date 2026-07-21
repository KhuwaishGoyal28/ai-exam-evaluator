"""Unit tests for result_mapper — pure mapping, no I/O."""
import pytest
from app.services.evaluation.result_mapper import map_llm_response_to_result
from app.core.exceptions import EvaluationError
from app.core.constants import RubricParameter


_VALID_RESPONSE = {
    "parameter_scores": [
        {"parameter": p.value, "score": 7, "justification": "Good."}
        for p in RubricParameter
    ],
    "overall_remark": "A solid answer with good structure.",
    "annotation_comments": [
        {"paragraph_index": 0, "comment_text": "Great intro", "sentiment": "positive"},
        {"paragraph_index": 1, "comment_text": "Unsupported claim", "sentiment": "negative"},
    ],
}


def test_maps_all_parameters():
    result = map_llm_response_to_result(_VALID_RESPONSE)
    assert len(result.parameter_scores) == len(list(RubricParameter))


def test_total_score_computed():
    result = map_llm_response_to_result(_VALID_RESPONSE)
    assert result.total_score == 7 * len(list(RubricParameter))


def test_maps_annotation_comments():
    result = map_llm_response_to_result(_VALID_RESPONSE)
    assert len(result.annotation_comments) == 2
    assert result.annotation_comments[0].sentiment == "positive"


def test_raises_on_empty_scores():
    bad = {**_VALID_RESPONSE, "parameter_scores": []}
    with pytest.raises(EvaluationError):
        map_llm_response_to_result(bad)


def test_raises_on_empty_remark():
    bad = {**_VALID_RESPONSE, "overall_remark": ""}
    with pytest.raises(EvaluationError):
        map_llm_response_to_result(bad)


def test_score_clamped_to_range():
    data = {
        **_VALID_RESPONSE,
        "parameter_scores": [
            {"parameter": RubricParameter.STRUCTURE.value, "score": 99, "justification": "x"}
        ],
    }
    result = map_llm_response_to_result(data)
    assert result.parameter_scores[0].score == 10
