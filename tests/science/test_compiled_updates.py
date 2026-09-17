"""Engineering comparison only; these tolerances are not scientific gates."""

import jax
import jax.numpy as jnp
import numpy as np
import pytest
from test_c02_jax_conformance import _data

from carbon.reconstruction._vendor.carbon_jax_lab.checkpoint import (
    load_checkpoint,
    save_checkpoint,
)
from carbon.reconstruction._vendor.carbon_jax_lab.config import (
    ModelConfig,
    TaskConfig,
    TrainConfig,
)
from carbon.reconstruction._vendor.carbon_jax_lab.training import (
    CancelledTraining,
    NonFiniteTrainingError,
    Trainer,
)
from carbon.reconstruction.compiled_updates import fit_chunks


def trainer():
    return Trainer(
        ModelConfig(kind="fno1d", width=8, depth=1, n_modes=4),
        TaskConfig(),
        TrainConfig(
            steps=7, warmup_steps=0, batch_size=2, h1_weight=0.01, pde_weight=0.001
        ),
        _data(),
    )


@pytest.mark.parametrize("size", [1, 4, 16])
def test_chunks_match_discrete_state_and_fixed_work_numerics(size):
    baseline, chunked = trainer(), trainer()
    baseline.fit()
    report = fit_chunks(chunked, chunk_size=size)
    assert report["completed_steps"] == 7
    assert report["compile_seconds"] >= 0
    assert report["host_diagnostics_seconds"] >= 0
    assert [v["step"] for v in chunked.history] == list(range(1, 8))
    for expected, actual in zip(
        jax.tree.leaves(baseline.state), jax.tree.leaves(chunked.state), strict=True
    ):
        if np.issubdtype(np.asarray(expected).dtype, np.integer):
            np.testing.assert_array_equal(expected, actual)
        else:
            np.testing.assert_allclose(expected, actual, rtol=2e-5, atol=2e-6)
    for expected, actual in zip(baseline.history, chunked.history, strict=True):
        for key in expected:
            assert actual[key] == pytest.approx(expected[key], rel=2e-5, abs=2e-6)


def test_cancellation_keeps_completed_chunk_and_rejects_next_dispatch():
    value = trainer()
    with pytest.raises(CancelledTraining):
        fit_chunks(value, chunk_size=4, cancel=lambda: int(value.state.step) >= 4)
    assert int(value.state.step) == len(value.history) == 4
    pristine = trainer()
    with pytest.raises(CancelledTraining):
        fit_chunks(pristine, chunk_size=4, cancel=lambda: True)
    assert int(pristine.state.step) == 0
    assert pristine.timing["compile_seconds"] == 0


def test_partial_chunk_checkpoint_resumes_with_exact_rng_and_progress(tmp_path):
    continuous, partial = trainer(), trainer()
    fit_chunks(continuous, chunk_size=4)
    fit_chunks(partial, chunk_size=4, until_step=3)
    checkpoint = tmp_path / "partial"
    save_checkpoint(partial, checkpoint)
    resumed = trainer()
    load_checkpoint(resumed, checkpoint)
    assert int(resumed.state.step) == 3
    fit_chunks(resumed, chunk_size=4)
    for expected, actual in zip(
        jax.tree.leaves(continuous.state), jax.tree.leaves(resumed.state), strict=True
    ):
        if np.issubdtype(np.asarray(expected).dtype, np.integer):
            np.testing.assert_array_equal(expected, actual)
        else:
            np.testing.assert_allclose(expected, actual, rtol=2e-5, atol=2e-6)


def test_nonfinite_does_not_advance_rng_optimizer_or_later_updates():
    value, expected = trainer(), trainer()
    expected.fit(until_step=2)
    original = value._make_step()

    def rejected_after_two(state, arrays):
        proposed, metrics = original(state, arrays)
        valid = metrics["finite"] & (state.step < 2)
        return proposed, {**metrics, "finite": valid}

    value._make_step = lambda: rejected_after_two
    with pytest.raises(NonFiniteTrainingError):
        fit_chunks(value, chunk_size=4)
    assert int(value.state.step) == len(value.history) == 2
    np.testing.assert_array_equal(value.state.rng, expected.state.rng)
    assert int(value.state.optimizer.count) == 2
    assert bool(jnp.all(jnp.isfinite(value.state.rng)))


@pytest.mark.parametrize("size", [True, 0, 3, 64])
def test_unregistered_chunk_size_rejected(size):
    with pytest.raises(ValueError):
        fit_chunks(trainer(), chunk_size=size)
