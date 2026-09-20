"""Prepare accelerator acceptance without silently dispatching unadmitted work.

Numerical helpers reuse Carbon's actual JAX FNO Trainer/physics/checkpoint code.
They are integration hooks for an admitted worker, not a scheduler or a claim of
fresh independent recipe reconstruction. The public command is discovery only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

from carbon.reconstruction.accelerators import (
    PROFILES,
    AcceleratorRole,
    require_accelerator_admission,
    resolve_profile,
    worker_environment,
)


def _exercise_training(
    trainer, output: Path, *, runtime_key_material=None, cancelled=None
):
    """Exercise actual registered numerical primitives inside a supervised worker.

    The caller owns the trained-data/recipe/grant binding and fresh worker process.
    Only the first registered FNO implementation is supported in this instrument.
    CPU tests exercise this helper; they are explicitly not accelerator evidence.
    """
    import jax
    import jax.numpy as jnp
    import numpy as np

    from carbon.reconstruction._vendor.carbon_jax_lab.checkpoint import (
        load_checkpoint,
        save_checkpoint,
    )
    from carbon.reconstruction._vendor.carbon_jax_lab.training import (
        Trainer,
        burgers_residual,
        predict_trajectories,
        spectral_derivative,
    )

    if (
        type(trainer) is not Trainer
        or trainer.model_config.kind != "fno1d"
        or not trainer.config.h1_weight
        or not trainer.config.pde_weight
        or int(trainer.state.step) != 0
        or not output.is_absolute()
        or output.exists()
        or output.is_symlink()
    ):
        raise ValueError("fresh registered FNO/physics instrument and output required")
    if cancelled is not None and cancelled():
        raise RuntimeError("accelerator.acceptance.cancelled")
    expected_key = (
        None
        if runtime_key_material is None
        else hashlib.sha256(runtime_key_material).hexdigest()
    )
    if expected_key != trainer.runtime_key_digest:
        raise ValueError("exact runtime randomness binding required")
    start = time.monotonic()
    output.mkdir()
    u0, nu, times, target, x = trainer.arrays
    batch = (u0, nu, times[:, -1], target[:, -1])
    prediction = trainer.predictor(trainer.state.params, *batch[:3], x)
    loss_and_grad = jax.jit(jax.value_and_grad(trainer._loss, has_aux=True))
    (loss, terms), gradient = loss_and_grad(
        trainer.state.params, batch, x, trainer.state.step
    )
    derivative = spectral_derivative(prediction, trainer.task_config.domain_length)
    residual = burgers_residual(
        prediction, jnp.zeros_like(prediction), nu, trainer.task_config.domain_length
    )
    jax.block_until_ready((loss, terms, gradient, derivative, residual))
    for leaf in jax.tree.leaves(
        (prediction, loss, terms, gradient, derivative, residual)
    ):
        if not bool(jnp.all(jnp.isfinite(leaf))):
            raise FloatingPointError("nonfinite accelerator numerical primitive")
    initial = [np.asarray(value) for value in jax.tree.leaves(trainer.state.params)]
    trainer.fit(cancel=cancelled, wall_budget_seconds=120.0)
    changed = any(
        not np.array_equal(before, np.asarray(after))
        for before, after in zip(
            initial, jax.tree.leaves(trainer.state.params), strict=True
        )
    )
    if not changed:
        raise RuntimeError("optimizer produced no observed parameter update")
    checkpoint_started = time.monotonic()
    metadata = save_checkpoint(trainer, output / "checkpoint")
    fresh = Trainer(
        trainer.model_config,
        trainer.task_config,
        trainer.config,
        trainer.data,
        runtime_key_material=runtime_key_material,
    )
    # Loading into a fresh object tests state portability in one environment.
    # It is not an independent reconstruction, which must train from the recipe
    # and validator-owned inputs in a separate admitted process.
    load_checkpoint(fresh, output / "checkpoint")
    checkpoint_seconds = time.monotonic() - checkpoint_started
    before = predict_trajectories(trainer.predictor, trainer.state.params, trainer.data)
    after = predict_trajectories(fresh.predictor, fresh.state.params, fresh.data)
    np.save(output / "prediction.npy", after, allow_pickle=False)
    devices = jax.local_devices()
    memory = []
    for device in devices:
        stats = device.memory_stats()
        memory.append(
            {
                "device_id": device.id,
                "statistics": (
                    None
                    if stats is None
                    else {
                        key: int(stats[key])
                        for key in ("bytes_in_use", "peak_bytes_in_use", "bytes_limit")
                        if key in stats
                    }
                ),
            }
        )
    result = {
        "schema": "carbon.accelerator-numerical-instrument.v1",
        "observed_backend": jax.default_backend(),
        "operations": [
            "fno_forward",
            "gradient",
            "adamw_update",
            "fourier",
            "burgers_residual",
            "prediction",
            "logical_checkpoint_export",
            "same_environment_reload",
        ],
        "completed_steps": int(trainer.state.step),
        "parameter_update_observed": changed,
        "training_fingerprint": trainer.data.fingerprint,
        "construction_contract": trainer.contract_id,
        "checkpoint_state_digest": "sha256:" + metadata["state_sha256"],
        "prediction_digest": "sha256:"
        + hashlib.sha256((output / "prediction.npy").read_bytes()).hexdigest(),
        "reload_max_absolute_difference": float(np.max(np.abs(before - after))),
        "loss": float(loss),
        "loss_terms": [float(value) for value in terms],
        "memory_observations": memory,
        "timings": {
            **trainer.timing,
            "checkpoint_and_reload_seconds": checkpoint_seconds,
            "total_seconds": time.monotonic() - start,
        },
        "fresh_independent_recipe_reconstruction": "NOT_EXECUTED",
        "allocation_cleanup": "OUTER_CONTROLLER_MUST_OBSERVE",
        "oom_acceptance": "NOT_EXECUTED",
        "scientifically_qualified": False,
    }
    (output / "instrument.json").write_text(json.dumps(result, sort_keys=True) + "\n")
    return result


def _proposed_environment(profile, role):
    """The overlay this host would get, or why it cannot be shown.

    The device-dependent part of the overlay comes from the installed host
    record. Without one there is nothing to report and nothing to guess, so this
    says so instead of printing a device identity from the source tree - there
    is no longer one to print.
    """
    from carbon.reconstruction.host_inventory import (
        HostDeviceRecord,
        require_host_device,
    )
    from carbon.reconstruction.worker.accelerator_runtime import HOST_ROOT
    from carbon.reconstruction.worker.model import WorkerFailure

    try:
        record = require_host_device(HostDeviceRecord.load(HOST_ROOT), profile)
    except WorkerFailure:
        return {
            "status": "UNAVAILABLE_NO_BOUND_HOST_DEVICE_RECORD",
            "host_device_record": str(HOST_ROOT / "host-device.json"),
        }, None
    return worker_environment(profile, role, host_device=record), record


def run_registered_acceptance(profile_id: str, role: AcceleratorRole) -> None:
    """Fail before numerical imports until the existing controller admits this profile."""
    require_accelerator_admission(resolve_profile(profile_id), role)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profile", required=True, choices=[p.profile_id for p in PROFILES]
    )
    parser.add_argument(
        "--role", required=True, choices=[r.value for r in AcceleratorRole]
    )
    args = parser.parse_args(argv)
    profile = resolve_profile(args.profile)
    role = AcceleratorRole(args.role)
    environment, record = _proposed_environment(profile, role)
    print(
        json.dumps(
            {
                "profile": profile.document(),
                "profile_digest": profile.digest,
                "role": role.value,
                "host_device_record_digest": None if record is None else record.digest,
                "proposed_worker_environment": environment,
                "dispatch": "DISABLED",
                "existing_owner": "carbon.reconstruction.worker.controller",
                "remaining": [
                    "immutable_worker_image",
                    "existing_controller_admission",
                    "exclusive_allocation",
                    "device_memory_and_oom",
                    "cancellation_and_allocation_cleanup",
                    "fresh_miner_and_validator_recipe_reconstruction",
                ],
            },
            sort_keys=True,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
