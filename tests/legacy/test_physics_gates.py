# tests/test_physics_gates.py

"""
Tests for physics gates in carbonScorer.
"""

from neurons.scoring.carbon_scorer import carbonScorer


def test_hard_gates_mass_conservation():
    scorer = carbonScorer()
    metrics = {"mass_conservation_error": 1e-2}  # Above threshold
    violations = scorer.check_hard_gates(metrics)
    assert "mass_conservation" in violations


def test_hard_gates_energy_dissipation():
    scorer = carbonScorer()
    metrics = {"energy_dissipation_rate": 1e-3}  # Above threshold
    violations = scorer.check_hard_gates(metrics)
    assert "energy_dissipation" in violations


def test_hard_gates_boundary():
    scorer = carbonScorer()
    metrics = {"boundary_error": 1e-2}
    violations = scorer.check_hard_gates(metrics)
    assert "boundary" in violations


def test_hard_gates_pass():
    scorer = carbonScorer()
    metrics = {
        "mass_conservation_error": 1e-5,
        "energy_dissipation_rate": 1e-6,
        "boundary_error": 1e-5,
    }
    violations = scorer.check_hard_gates(metrics)
    assert len(violations) == 0


def test_soft_gates_symmetry():
    scorer = carbonScorer()
    metrics = {"symmetry_error": 0.2}
    penalties = scorer.apply_soft_gates(metrics)
    assert "symmetry" in penalties
    assert penalties["symmetry"] > 0
