"""Opt-in DEVELOPMENT experiment over the unchanged registered JAX update.

This worker-only helper is not selected by an existing execution profile. The
controller must still own admission and an independent hard deadline. Chunk
boundaries bound cancellation opportunities; they are not a wall-time guarantee.
"""

from __future__ import annotations

import math
import time

CHUNK_SIZES = (1, 4, 16)
EXPERIMENT_ID = "carbon.jax.compiled-update-experiment.v1"


def fit_chunks(trainer, *, chunk_size, until_step=None, cancel=None, wall_seconds=None):
    """Run fixed update chunks and preserve each accepted step in host history."""
    import jax
    import jax.numpy as jnp
    import numpy as np

    from carbon.reconstruction._vendor.carbon_jax_lab.training import (
        CancelledTraining,
        NonFiniteTrainingError,
        Trainer,
    )

    if type(trainer) is not Trainer:
        raise TypeError("registered JAX Trainer required")
    if type(chunk_size) is not int or chunk_size not in CHUNK_SIZES:
        raise ValueError("unsupported bounded update chunk")
    progress = int(trainer.state.step)
    stop = trainer.config.steps if until_step is None else until_step
    if type(stop) is not int or not progress <= stop <= trainer.config.steps:
        raise ValueError("invalid stop step")
    if wall_seconds is not None and (
        type(wall_seconds) not in (int, float)
        or not math.isfinite(wall_seconds)
        or wall_seconds <= 0
    ):
        raise ValueError("positive finite wall budget required")
    update = trainer._make_step()
    compiled = {}
    started = time.monotonic()
    report = {
        "experiment": EXPERIMENT_ID,
        "chunk_size": chunk_size,
        "compile_seconds": 0.0,
        "execution_seconds": 0.0,
        "host_diagnostics_seconds": 0.0,
        "max_chunk_execution_seconds": 0.0,
        "chunks": 0,
    }

    def check_cancel():
        if cancel is not None and cancel():
            raise CancelledTraining("cancelled at compiled chunk boundary")
        if wall_seconds is not None and time.monotonic() - started >= wall_seconds:
            raise CancelledTraining("research wall budget exhausted between chunks")

    def make_chunk(length):
        def run(state, arrays):
            def body(carry, unused):
                previous, healthy = carry
                proposed, metrics = update(previous, arrays)
                accepted = healthy & metrics["finite"]
                next_state = jax.tree.map(
                    lambda new, old: jnp.where(accepted, new, old), proposed, previous
                )
                return (next_state, accepted), {**metrics, "finite": accepted}

            (state, _), metrics = jax.lax.scan(
                body, (state, jnp.array(True)), xs=None, length=length
            )
            return state, metrics

        return jax.jit(run)

    while progress < stop:
        check_cancel()
        length = min(chunk_size, stop - progress)
        if length not in compiled:
            before = time.monotonic()
            compiled[length] = (
                make_chunk(length).lower(trainer.state, trainer.arrays).compile()
            )
            duration = time.monotonic() - before
            report["compile_seconds"] += duration
            trainer.timing["compile_seconds"] += duration
        check_cancel()
        before = time.monotonic()
        proposed, metrics = compiled[length](trainer.state, trainer.arrays)
        jax.block_until_ready((proposed, metrics))
        duration = time.monotonic() - before
        report["execution_seconds"] += duration
        report["max_chunk_execution_seconds"] = max(
            report["max_chunk_execution_seconds"], duration
        )
        trainer.timing["train_execution_seconds"] += duration
        before = time.monotonic()
        host = jax.device_get(metrics)
        finite = np.asarray(host["finite"], dtype=bool)
        accepted = int(np.count_nonzero(finite))
        trainer.state = proposed
        for index in range(accepted):
            trainer.history.append(
                {
                    "step": progress + index + 1,
                    **{k: float(v[index]) for k, v in host.items() if k != "finite"},
                }
            )
        progress += accepted
        report["host_diagnostics_seconds"] += time.monotonic() - before
        report["chunks"] += 1
        if accepted != length:
            raise NonFiniteTrainingError(
                "nonfinite chunk update rejected; preceding accepted state retained"
            )
    report["total_seconds"] = time.monotonic() - started
    report["completed_steps"] = progress
    return report
