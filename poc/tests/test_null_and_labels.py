"""Unit tests: null baseline verdict + label checks."""

from poc.eval.null_baseline import beats_null, train_quality_verdict
from poc.generators.label_checks import check_label_conservation, LABEL_MASS_TAU
from poc.generators.burgers1d import generate_batch


def test_beats_null_logic():
    assert beats_null(0.4, 1.0) is True
    assert beats_null(0.99, 1.0) is False  # < 5% relative
    assert beats_null(1.1, 1.0) is False


def test_verdict_requires_all_gates():
    v = train_quality_verdict(
        backend="jax",
        loss_improved=True,
        eval_rel_l2=0.3,
        null_rel_l2=0.9,
    )
    assert v["train_quality_claim"] is True

    v2 = train_quality_verdict(
        backend="numpy_fd",
        loss_improved=True,
        eval_rel_l2=0.3,
        null_rel_l2=0.9,
    )
    assert v2["train_quality_claim"] is False
    assert "backend_not_jax" in v2["reasons"]

    v3 = train_quality_verdict(
        backend="jax",
        loss_improved=True,
        eval_rel_l2=0.8,
        null_rel_l2=0.9,
    )
    assert v3["train_quality_claim"] is False
    assert any("eval_rel_l2" in r for r in v3["reasons"])


def test_labels_pass_on_fresh_batch():
    b = generate_batch("train", 0, "u", fast=True)
    ok, info = check_label_conservation(b)
    assert ok, info
    assert info["max_mass_err"] <= LABEL_MASS_TAU
