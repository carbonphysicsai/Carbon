"""Oracle generator quality gate — fail CI if production solver drifts."""

from poc.eval.oracle_check import cross_check_generator, ORACLE_TAU_REL


def test_oracle_mean_rel_under_tau():
    result = cross_check_generator(n_samples=6, seed_nonce=0, fast=True)
    assert result["passed"], (
        f"oracle failed mean_rel={result['mean_rel']:.4f} tau={result['tau']} "
        f"max_rel={result['max_rel']:.4f}"
    )
    assert result["mean_rel"] <= ORACLE_TAU_REL


def test_oracle_finite_samples():
    result = cross_check_generator(n_samples=4, seed_nonce=3, fast=True)
    assert all(r == r for r in result["rels"])  # no NaN
