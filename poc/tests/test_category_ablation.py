"""Stress category ablation — categories must affect coverage and robustness signal."""

from __future__ import annotations

from copy import deepcopy

from poc.generators.stress_categories import (
    CATEGORIES,
    COVERAGE_THRESHOLD,
    STRESS_SPEC_VERSION,
    coverage_ok,
    generate_stress_suite,
)
from poc.eval.score import score_run


def test_full_suite_passes_coverage():
    suite = generate_stress_suite(42, fast=True)
    ok, msg = coverage_ok(suite)
    assert ok, msg
    assert suite.spec_version == STRESS_SPEC_VERSION


def test_ablation_reduces_coverage():
    """Simulate missing category by removing from a suite copy."""
    suite = generate_stress_suite(99, fast=True)
    # Drop highest-weight category
    drop = "extended_envelope"
    suite2_batches = {k: v for k, v in suite.batches.items() if k != drop}
    present = list(suite2_batches.keys())
    coverage = sum(CATEGORIES[c]["weight"] for c in present)
    assert coverage < COVERAGE_THRESHOLD
    # Mimic StressSuite fields for coverage_ok
    class _S:
        pass

    s = _S()
    s.coverage = coverage
    s.categories_present = present
    ok, msg = coverage_ok(s)
    assert not ok
    assert "missing" in msg or coverage < COVERAGE_THRESHOLD


def test_coverage_fail_zeros_score():
    scored = score_run(
        {"rel_l2": 0.1, "residual_mean": 0.1, "conservation_error": 0.01},
        {"rel_l2": 0.1},
        gate_results=[{"id": "finite", "pass": True, "value": 1.0, "tau": 1.0}],
        stress_coverage=0.50,  # below 0.95
    )
    assert scored["coverage_fail"] is True
    assert scored["combined"] == 0.0
    assert "stress_coverage" in scored["hard_gate_failures"]


def test_category_payload_hashes_distinct():
    suite = generate_stress_suite(7, fast=True)
    hashes = list(suite.meta["payload_hashes"].values())
    assert len(hashes) == len(CATEGORIES)
    assert len(set(hashes)) == len(hashes), "categories must produce distinct data"
