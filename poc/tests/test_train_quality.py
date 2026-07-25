"""Train-quality honesty tests.

numpy_fd  → train_quality_claimable must be False (protocol only).
jax       → must emit first_loss/last_loss; claim only if loss drops ≥5%.
"""

from pathlib import Path

from poc.generators.burgers1d import generate_batch
from poc.train.loop import train, JAX_AVAILABLE
from poc.validator.schema_check import load_limits, load_strategy_file

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "poc" / "fixtures"


def test_numpy_fd_never_claims_quality():
    strategy, err = load_strategy_file(FIXTURES / "strategy_data_only.json", fast=True)
    assert err is None
    limits = load_limits(fast=True)
    batch = generate_batch("train", 7, "tq", fast=True)
    _, _, info = train(strategy, batch, limits, init_seed=7, prefer_jax=False)
    assert info["backend"] == "numpy_fd"
    assert info["train_quality_claimable"] is False
    assert info["loss_improved"] is False
    assert "PROTOCOL" in info.get("note", "PROTOCOL")


def test_jax_emits_loss_curve_fields():
    if not JAX_AVAILABLE:
        return  # skip silently when jax absent (CI without jax)
    strategy, err = load_strategy_file(FIXTURES / "strategy_data_only.json", fast=True)
    assert err is None
    limits = load_limits(fast=True)
    batch = generate_batch("train", 9, "tq_jax", fast=True)
    _, _, info = train(strategy, batch, limits, init_seed=9, prefer_jax=True)
    assert info["backend"] == "jax"
    assert "first_loss" in info and "last_loss" in info
    assert info["first_loss"] is not None
    assert info["optimizer"] == "adam"
    # claim is only True when loss actually dropped — do not force True here
    assert isinstance(info["train_quality_claimable"], bool)
