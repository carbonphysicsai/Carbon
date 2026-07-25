# tests/test_scorer.py

"""
Tests for CarbonScorer multi-objective scoring.
"""

import pytest

from neurons.scoring.carbon_scorer import CarbonScorer


def test_weighted_combined_score():
    scorer = CarbonScorer()
    # Simulate base metrics
    base = {
        "physics_fidelity": 0.9,
        "robustness": 0.8,
        "accuracy": 0.85,
    }
    result = scorer.score_strategy(model=None, base_metrics=base)

    # Expected weighted average (no stress)
    expected = 0.45 * 0.9 + 0.30 * 0.8 + 0.25 * 0.85
    assert abs(result["combined_score"] - expected) < 0.01


def test_score_strategy_without_stress():
    scorer = CarbonScorer()
    result = scorer.score_strategy(model=None, base_metrics={"accuracy": 0.9})
    assert "combined_score" in result
    assert result["accuracy"] == 0.85  # default in compute_accuracy
