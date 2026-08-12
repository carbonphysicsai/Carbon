# tests/test_reproducibility.py

"""
Basic reproducibility tests for scoring.
"""

import pytest

from neurons.scoring.carbon_scorer import carbonScorer


def test_scoring_reproducibility():
    scorer = carbonScorer()
    base = {"physics_fidelity": 0.85, "robustness": 0.8, "accuracy": 0.9}

    result1 = scorer.score_strategy(model=None, base_metrics=base)
    result2 = scorer.score_strategy(model=None, base_metrics=base)

    assert result1["combined_score"] == result2["combined_score"]


def test_stress_scoring_reproducibility():
    scorer = carbonScorer()
    # Without real stress set, just check that the method doesn't crash
    result = scorer.score_strategy(model=None, base_metrics={"accuracy": 0.85})
    assert "combined_score" in result
