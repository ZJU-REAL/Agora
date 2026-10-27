import pytest

from benchmarks.metrics import intraclass_correlation


def test_intraclass_correlation_is_high_for_stable_subjects():
    score = intraclass_correlation([
        [0.9, 0.91, 0.89], [0.2, 0.21, 0.19], [0.6, 0.61, 0.59]])
    assert score > 0.99


def test_intraclass_correlation_validates_shape():
    with pytest.raises(ValueError, match="equal length"):
        intraclass_correlation([[1, 2], [3, 4, 5]])
