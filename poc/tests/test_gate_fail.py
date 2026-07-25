"""Unit tests for hard-gate zeroing without full train."""

from poc.eval.gates import run_gates, all_passed
from poc.eval.score import score_run


def test_loss_signal_fails_when_all_disabled():
    strategy = {
        "loss": {
            "data_mse": False,
            "physics_residual": False,
            "conservation_penalty": False,
        }
    }
    metrics = {
        "finite_ok": 1.0,
        "conservation_error": 0.0,
        "residual_mean": 0.0,
        "eval_rel_l2": 0.1,
    }
    gates = run_gates(metrics, strategy=strategy)
    ok, fails = all_passed(gates)
    assert not ok
    assert "loss_signal" in fails


def test_accuracy_ceiling_fails_on_garbage():
    strategy = {
        "loss": {
            "data_mse": True,
            "physics_residual": False,
            "conservation_penalty": False,
        }
    }
    metrics = {
        "finite_ok": 1.0,
        "conservation_error": 0.0,
        "residual_mean": 0.1,
        "eval_rel_l2": 1.5,
    }
    gates = run_gates(metrics, strategy=strategy)
    ok, fails = all_passed(gates)
    assert not ok
    assert "accuracy_ceiling" in fails
    score = score_run(
        {"rel_l2": 1.5, "residual_mean": 0.1, "conservation_error": 0.0},
        {"rel_l2": 1.5},
        gates,
    )
    assert score["combined"] == 0.0
    assert score["gate_failed"] is True
