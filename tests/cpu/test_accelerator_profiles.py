"""Prospective accelerator contracts and CPU-only numerical harness diagnostics."""

from dataclasses import replace
from pathlib import Path

import accelerator_host
import pytest

from carbon.reconstruction.accelerators import (
    GPU_PROFILE,
    PROFILES,
    TPU_PROFILE,
    AcceleratorRole,
    AcceleratorUnavailable,
    require_accelerator_admission,
    resolve_profile,
    validate_worker_observation,
    worker_environment,
)
from carbon.reconstruction.worker.backend_probe import (
    BackendObservation,
    BackendProbeError,
    DeviceObservation,
)
from carbon.reconstruction.worker.model import WorkerFailure


@pytest.mark.parametrize("profile", PROFILES)
@pytest.mark.parametrize("role", tuple(AcceleratorRole))
def test_profiles_fail_closed_for_both_roles(profile, role):
    assert not profile.admission_enabled
    assert profile.document()["execution_acceptance"] == "NOT_EXECUTED"
    assert not profile.document()["final_comparison_eligible"]
    with pytest.raises(AcceleratorUnavailable, match="dispatch_disabled"):
        require_accelerator_admission(profile, role)
    assert resolve_profile(profile.profile_id) is profile
    assert profile.digest.startswith("sha256:")


@pytest.mark.parametrize("name", [None, "gpu", "cpu", "TPU", "", "auto"])
def test_unregistered_backend_aliases_are_rejected(name):
    with pytest.raises(ValueError):
        resolve_profile(name)


@pytest.fixture
def host_record(request, tmp_path):
    """One installed host record; the device identity is never a constant."""
    profile = getattr(request, "param", None) or request.getfixturevalue("profile")
    return accelerator_host.for_profile(tmp_path / "host", profile)


@pytest.mark.parametrize("profile", PROFILES)
def test_environment_is_explicit_and_mutable_caches_do_not_cross_roles(
    profile, host_record
):
    options = {"host_device": host_record}
    miner = worker_environment(profile, AcceleratorRole.MINER_RESEARCH, **options)
    validator = worker_environment(
        profile, AcceleratorRole.VALIDATOR_RECONSTRUCTION, **options
    )
    assert miner["JAX_PLATFORMS"] == profile.backend.value
    assert miner["JAX_ENABLE_X64"] == "false"
    assert miner["JAX_DEFAULT_MATMUL_PRECISION"] == "highest"
    assert miner["JAX_ENABLE_COMPILATION_CACHE"] == "false"
    assert miner["JAX_COMPILATION_CACHE_DIR"] != validator["JAX_COMPILATION_CACHE_DIR"]
    assert not {"LD_LIBRARY_PATH", "JAX_SKIP_CUDA_CONSTRAINTS_CHECK"} & set(miner)
    with pytest.raises(ValueError):
        worker_environment(
            replace(profile, global_device_count=123),
            AcceleratorRole.MINER_RESEARCH,
            **options,
        )
    if profile is GPU_PROFILE:
        assert miner["CUDA_VISIBLE_DEVICES"] == host_record.device_uuid
        # A device-backed overlay cannot be built without installed evidence.
        for missing in (None, "GPU-00000000-1111-2222-3333-444444444444"):
            with pytest.raises((ValueError, WorkerFailure)):
                worker_environment(
                    profile, AcceleratorRole.MINER_RESEARCH, host_device=missing
                )


def observation(profile, device_kind):
    return BackendObservation(
        profile.backend,
        "0.10.2",
        "0.10.2",
        0,
        False,
        tuple(
            DeviceObservation(
                i, 0, "gpu" if profile is GPU_PROFILE else "tpu", device_kind
            )
            for i in range(profile.local_device_count)
        ),
    )


@pytest.mark.parametrize("profile", PROFILES)
def test_exact_topology_and_precision_are_required(profile, host_record):
    # The expected device kind comes from the installed record, so this check
    # is as exact as before while naming no hardware in the source tree.
    value = observation(profile, host_record.device_kind)
    options = {
        "global_device_count": profile.global_device_count,
        "process_count": 1,
        "matmul_precision": "highest",
        "host_device": host_record,
    }
    validate_worker_observation(profile, value, **options)
    for key, wrong in (
        ("global_device_count", 99),
        ("process_count", 2),
        ("matmul_precision", "bfloat16"),
    ):
        with pytest.raises(ValueError):
            validate_worker_observation(profile, value, **{**options, key: wrong})
    for wrong in (
        replace(value, x64_enabled=True),
        replace(value, jax_version="0.10.1"),
        replace(value, devices=(DeviceObservation(0, 0, "cpu", "cpu"),)),
        # A device whose kind is not the one this host recorded.
        observation(profile, "NVIDIA Some Other Device"),
    ):
        with pytest.raises((ValueError, BackendProbeError)):
            validate_worker_observation(profile, wrong, **options)
    # An observation cannot be validated without installed host evidence.
    with pytest.raises((ValueError, WorkerFailure)):
        validate_worker_observation(profile, value, **{**options, "host_device": None})


def test_lock_files_bind_complete_separate_worker_environments():
    import hashlib

    root = Path(__file__).resolve().parents[2]
    for profile in PROFILES:
        body = (root / profile.environment_file).read_bytes()
        assert (
            "sha256:" + hashlib.sha256(body).hexdigest()
            == profile.environment_lock_digest
        )
        assert b"jax==0.10.2" in body and b"--hash=sha256:" in body
    assert (
        b"jax-cuda13-plugin==0.10.2"
        in (root / GPU_PROFILE.environment_file).read_bytes()
    )
    assert b"libtpu==0.0.42" in (root / TPU_PROFILE.environment_file).read_bytes()


def test_cli_discovery_and_dispatch_rejection_do_not_import_jax(capsys):
    from scripts.dev.accelerator_acceptance import main, run_registered_acceptance

    assert main(["--profile", GPU_PROFILE.profile_id, "--role", "MINER_RESEARCH"]) == 0
    assert '"dispatch": "DISABLED"' in capsys.readouterr().out
    with pytest.raises(AcceleratorUnavailable):
        run_registered_acceptance(
            GPU_PROFILE.profile_id, AcceleratorRole.MINER_RESEARCH
        )


def test_actual_fno_physics_update_and_checkpoint_harness_on_cpu_only(tmp_path):
    import jax
    import numpy as np

    from carbon.reconstruction._vendor.carbon_jax_lab.config import (
        ModelConfig,
        TaskConfig,
        TrainConfig,
    )
    from carbon.reconstruction._vendor.carbon_jax_lab.data import Trajectories
    from carbon.reconstruction._vendor.carbon_jax_lab.training import Trainer
    from scripts.dev.accelerator_acceptance import _exercise_training

    assert (
        jax.default_backend() == "cpu"
    ), "this diagnostic must not acquire an accelerator"
    x = np.arange(16, dtype=float) / 16
    # Manufactured stationary Burgers controls: two distinct constant solutions.
    initial = np.asarray([[0.2] * 16, [-0.3] * 16], dtype=float)
    times = np.asarray([[0.0, 0.1], [0.0, 0.1]], dtype=float)
    data = Trajectories(
        initial,
        np.full(2, 0.1),
        times,
        np.repeat(initial[:, None, :], 2, axis=1),
        x,
        "train",
        "accelerator-harness-manufactured-fixture",
    )
    trainer = Trainer(
        ModelConfig(width=4, depth=1, n_modes=4),
        TaskConfig(),
        TrainConfig(
            steps=2, batch_size=2, warmup_steps=0, h1_weight=0.1, pde_weight=0.1
        ),
        data,
    )
    result = _exercise_training(trainer, tmp_path / "instrument")
    assert result["observed_backend"] == "cpu"
    assert result["completed_steps"] == 2
    assert result["parameter_update_observed"]
    assert result["reload_max_absolute_difference"] == 0.0
    assert result["fresh_independent_recipe_reconstruction"] == "NOT_EXECUTED"
    assert not result["scientifically_qualified"]


@pytest.mark.parametrize("accelerator", PROFILES)
def test_compiler_binds_prospective_environment_and_existing_service_rejects_admission(
    monkeypatch, tmp_path, accelerator
):
    import c02_fixtures

    from carbon.reconstruction.accelerators import (
        accelerator_dependency_specs,
        require_reconstruction_profile_admission,
    )
    from carbon.reconstruction.model import ReconstructionFailure
    from carbon.reconstruction.profile import compile_development_profile

    # Modify only the fixture's authoring contract before genuine compilation.
    # A CPU-pinned existing plan is never reinterpreted as an accelerator plan.
    monkeypatch.setattr(c02_fixtures, "ENVIRONMENT_ID", accelerator.profile_id)
    monkeypatch.setattr(c02_fixtures, "ENVIRONMENT_VERSION", "1.0")
    monkeypatch.setattr(
        c02_fixtures,
        "DEPENDENCY_SPECS",
        c02_fixtures.DEPENDENCY_SPECS + accelerator_dependency_specs(accelerator),
    )
    plan = c02_fixtures.compile_c02_plan(
        tmp_path, environment_digest=accelerator.digest
    )
    compiled = compile_development_profile(plan)
    assert compiled.profile_id == accelerator.profile_id
    assert compiled.profile_version == "4.0"
    assert compiled.environment_digest == accelerator.digest
    assert accelerator.environment_lock_digest in compiled.mapping_receipt_json
    with pytest.raises(ReconstructionFailure) as denied:
        require_reconstruction_profile_admission(compiled)
    assert denied.value.code == "reconstruction.accelerator.admission_disabled"


def test_cpu_profile_remains_legacy_and_admitted_by_same_gate(tmp_path):
    from c02_fixtures import compile_c02_plan

    from carbon.reconstruction.accelerators import (
        require_reconstruction_profile_admission,
    )
    from carbon.reconstruction.profile import (
        ENVIRONMENT_DIGEST,
        compile_development_profile,
    )

    compiled = compile_development_profile(compile_c02_plan(tmp_path))
    assert compiled.profile_id == "carbon_c02_jax_development"
    assert compiled.profile_version == "3.0"
    assert compiled.environment_digest == ENVIRONMENT_DIGEST
    assert "execution_profile" not in compiled.mapping_receipt_json
    assert require_reconstruction_profile_admission(compiled) is None
