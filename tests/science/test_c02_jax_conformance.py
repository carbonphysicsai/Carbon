"""Required numerical conformance for the vendored C-02 development runtime."""

from __future__ import annotations

import hashlib
import json
import shutil
import uuid
from dataclasses import replace
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np
import pytest
from c02_fixtures import compile_c02_plan
from third_party.transolver_reference import physics_attention_reference

from carbon.execution import ExecutionAttemptRef
from carbon.fees import SubmissionId
from carbon.reconstruction import (
    DevelopmentReplica,
    PublicTrainingArchive,
    ReconstructionFailure,
    ReconstructionStatus,
    development_replicate_digest,
    development_request_digest,
    freeze_development_repeat_plan,
    run_development_repeats,
)
from carbon.reconstruction._vendor.carbon_jax_lab.checkpoint import (
    load_checkpoint,
    load_inference,
    save_checkpoint,
)
from carbon.reconstruction._vendor.carbon_jax_lab.config import (
    SUPPORTED_MODELS,
    ModelConfig,
    TaskConfig,
    TrainConfig,
)
from carbon.reconstruction._vendor.carbon_jax_lab.data import Trajectories
from carbon.reconstruction._vendor.carbon_jax_lab.models import (
    Initializer,
    Operator,
    attention_init,
    physics_attention,
)
from carbon.reconstruction._vendor.carbon_jax_lab.pr40_bridge import (
    from_flax_params,
    to_flax_params,
)
from carbon.reconstruction._vendor.carbon_jax_lab.training import Trainer
from carbon.reconstruction.service import predict, reconstruct
from carbon.resource_policy import (
    RESOURCE_POLICY_CANONICALIZATION_PROFILE,
    RESOURCE_POLICY_SCHEMA_VERSION,
    BoundReconstructionReplicate,
    ReconstructionReplicateIdentity,
    ResearchResourcePolicyRef,
    ResourceClassRef,
)
from carbon.seeding import DerivedSeed


def _data() -> Trajectories:
    points = 16
    positions = np.arange(points, dtype=np.float64) / points
    initial = np.stack(
        (
            np.sin(2 * np.pi * positions),
            np.cos(2 * np.pi * positions),
            np.sin(4 * np.pi * positions) * 0.5,
            np.cos(4 * np.pi * positions) * 0.5,
        )
    )
    times = np.broadcast_to(np.array([0.05, 0.1]), (4, 2)).copy()
    solution = np.stack((initial * 0.98, initial * 0.96), axis=1)
    return Trajectories(
        initial,
        np.array([0.01, 0.02, 0.015, 0.025]),
        times,
        solution,
        positions,
        "train",
        "carbon_c02_science_fixture",
    )


@pytest.mark.parametrize("kind", SUPPORTED_MODELS)
def test_all_six_families_have_finite_forward_and_gradient(kind: str) -> None:
    config = ModelConfig(
        kind=kind,
        width=8,
        depth=1,
        heads=2,
        n_modes=8,
        slices=4,
        latent_points=12,
        branch_points=16,
    )
    model = Operator(config)
    parameters = model.init(jax.random.PRNGKey(1))
    features = jax.random.normal(jax.random.PRNGKey(2), (2, 16, 3))
    positions = jnp.arange(16)[:, None] / 16

    output = model.apply(parameters, features, positions)
    gradient = jax.grad(
        lambda values: jnp.mean(model.apply(values, features, positions) ** 2)
    )(parameters)

    assert output.shape == (2, 16, 1)
    assert bool(jnp.isfinite(output).all())
    assert all(
        np.isfinite(np.asarray(leaf)).all() for leaf in jax.tree.leaves(gradient)
    )
    assert sum(float(jnp.sum(jnp.abs(leaf))) for leaf in jax.tree.leaves(gradient)) > 0


def test_transolver_adapter_matches_forward_and_directional_gradient() -> None:
    config = ModelConfig(width=8, heads=2, slices=4)
    parameters = attention_init(Initializer(jax.random.PRNGKey(10)), config)
    numpy_parameters = jax.tree.map(np.asarray, parameters)
    value = np.random.default_rng(2).normal(size=(2, 17, 8)).astype("float32")
    direction = np.random.default_rng(3).normal(size=value.shape).astype("float32")

    expected = physics_attention_reference(numpy_parameters, value, 2)
    observed = physics_attention(parameters, jnp.asarray(value), 2)
    derivative = jax.jvp(
        lambda item: physics_attention(parameters, item, 2),
        (jnp.asarray(value),),
        (jnp.asarray(direction),),
    )[1]
    epsilon = 2e-3
    finite_difference = (
        physics_attention_reference(numpy_parameters, value + epsilon * direction, 2)
        - physics_attention_reference(numpy_parameters, value - epsilon * direction, 2)
    ) / (2 * epsilon)

    np.testing.assert_allclose(observed, expected, rtol=3e-5, atol=3e-6)
    np.testing.assert_allclose(derivative, finite_difference, rtol=2e-2, atol=2e-4)


def test_pr40_parameter_bridge_round_trip() -> None:
    model = Operator(ModelConfig(width=8, heads=2, depth=2, n_modes=16))
    parameters = model.init(jax.random.PRNGKey(0))
    converted = from_flax_params(to_flax_params(parameters), 2)

    for left, right in zip(
        jax.tree.leaves(parameters), jax.tree.leaves(converted), strict=True
    ):
        np.testing.assert_array_equal(left, right)


def test_full_width_seed_checkpoint_and_exact_resume(tmp_path: Path) -> None:
    data = _data()
    model = ModelConfig(width=8, depth=1, heads=2, n_modes=8)
    train = TrainConfig(steps=2, warmup_steps=1, batch_size=2)
    seed = bytes(range(32))
    continuous = Trainer(model, TaskConfig(), train, data, runtime_key_material=seed)
    continuous.fit()
    partial = Trainer(model, TaskConfig(), train, data, runtime_key_material=seed)
    partial.fit(until_step=1)
    checkpoint = tmp_path / "checkpoint"
    metadata = save_checkpoint(partial, checkpoint)
    resumed = Trainer(model, TaskConfig(), train, data, runtime_key_material=seed)
    load_checkpoint(resumed, checkpoint)
    resumed.fit()

    assert metadata["runtime_key_digest"] is not None
    for left, right in zip(
        jax.tree.leaves(continuous.state), jax.tree.leaves(resumed.state), strict=True
    ):
        np.testing.assert_array_equal(left, right)


def test_checkpoint_rejects_extra_member(tmp_path: Path) -> None:
    trainer = Trainer(
        ModelConfig(width=8, depth=1, heads=2, n_modes=8),
        TaskConfig(),
        TrainConfig(steps=2, warmup_steps=1, batch_size=2),
        _data(),
        runtime_key_material=bytes(range(32)),
    )
    checkpoint = tmp_path / "checkpoint"
    save_checkpoint(trainer, checkpoint)
    (checkpoint / "unexpected").write_text("rejected", encoding="utf-8")

    with pytest.raises(ValueError, match="members"):
        load_inference(checkpoint)


@pytest.mark.parametrize("backbone", ("fno", "deeponet"))
def test_compiled_plan_service_update_reload_and_target_free_prediction(
    tmp_path: Path, backbone: str
) -> None:
    source = tmp_path / f"{backbone}-train.npz"
    data = _data()
    data.save(source)
    archive = PublicTrainingArchive.from_file(source, provenance="c02_public_fixture")
    plan = compile_c02_plan(tmp_path, backbone=backbone)
    execution = ExecutionAttemptRef(
        SubmissionId(str(uuid.UUID("12345678-1234-4234-8234-123456789abc"))), 1
    )
    seed = DerivedSeed(bytes(range(32)))
    artifact = tmp_path / f"{backbone}-artifact"

    receipt = reconstruct(
        execution_ref=execution,
        plan=plan,
        training_archive=archive,
        derived_seed=seed,
        artifact_path=artifact,
    )
    duplicate = reconstruct(
        execution_ref=execution,
        plan=plan,
        training_archive=archive,
        derived_seed=seed,
        artifact_path=artifact,
    )
    output, prediction_receipt = predict(
        receipt,
        initial=data.initial[:2],
        viscosity=data.viscosity[:2],
        requested_times=data.times[:2, ::-1],
        positions=data.positions,
    )

    assert receipt.status is ReconstructionStatus.COMPLETE
    assert receipt.completed_steps == 2
    assert duplicate == receipt
    assert output.shape == (2, 2, 16)
    assert np.isfinite(output).all()
    assert prediction_receipt.output_digest.startswith("sha256:")
    manifest = json.loads((artifact / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["scope"] == "UNQUALIFIED_PUBLIC_DEVELOPMENT"
    assert manifest["training_role"] == "TRAIN"
    assert "solution" not in manifest


def test_outer_service_resume_matches_uninterrupted_checkpoint(tmp_path: Path) -> None:
    source = tmp_path / "resume-train.npz"
    data = _data()
    data.save(source)
    archive = PublicTrainingArchive.from_file(source, provenance="c02_resume_fixture")
    plan = compile_c02_plan(tmp_path, backbone="fno")
    execution = ExecutionAttemptRef(
        SubmissionId(str(uuid.UUID("22345678-1234-4234-8234-123456789abc"))), 1
    )
    seed = DerivedSeed(bytes(range(32)))
    partial = reconstruct(
        execution_ref=execution,
        plan=plan,
        training_archive=archive,
        derived_seed=seed,
        artifact_path=tmp_path / "partial-artifact",
        until_step=1,
    )
    resumed = reconstruct(
        execution_ref=execution,
        plan=plan,
        training_archive=archive,
        derived_seed=seed,
        artifact_path=tmp_path / "resumed-artifact",
        resume_from=partial,
    )
    continuous = reconstruct(
        execution_ref=execution,
        plan=plan,
        training_archive=archive,
        derived_seed=seed,
        artifact_path=tmp_path / "continuous-artifact",
    )

    assert partial.status is ReconstructionStatus.PARTIAL
    assert resumed.status is ReconstructionStatus.COMPLETE
    assert resumed.checkpoint_digest == continuous.checkpoint_digest


def _service_fixture(tmp_path: Path, *, steps: int = 2):
    source = tmp_path / "train.npz"
    data = _data()
    data.save(source)
    archive = PublicTrainingArchive.from_file(
        source, provenance="c02_hardening_fixture"
    )
    plan = compile_c02_plan(tmp_path, backbone="fno", steps=steps)
    execution = ExecutionAttemptRef(
        SubmissionId(str(uuid.UUID("32345678-1234-4234-8234-123456789abc"))), 1
    )
    seed = DerivedSeed(bytes(range(32)))
    return data, archive, plan, execution, seed


def test_resume_rejects_tampered_receipt_and_compatible_wrong_checkpoint(
    tmp_path: Path,
) -> None:
    data, archive, plan, execution, seed = _service_fixture(tmp_path)
    partial = reconstruct(
        execution_ref=execution,
        plan=plan,
        training_archive=archive,
        derived_seed=seed,
        artifact_path=tmp_path / "partial",
        until_step=1,
    )
    complete = reconstruct(
        execution_ref=execution,
        plan=plan,
        training_archive=archive,
        derived_seed=seed,
        artifact_path=tmp_path / "complete",
    )
    with pytest.raises(ReconstructionFailure) as caught:
        predict(
            partial,
            initial=data.initial[:1],
            viscosity=data.viscosity[:1],
            requested_times=data.times[:1],
            positions=data.positions,
        )
    assert caught.value.code == "reconstruction.prediction.artifact_status_invalid"

    with pytest.raises(ReconstructionFailure) as caught:
        reconstruct(
            execution_ref=execution,
            plan=plan,
            training_archive=archive,
            derived_seed=seed,
            artifact_path=tmp_path / "tampered-resume",
            resume_from=replace(partial, artifact_digest="sha256:" + "0" * 64),
        )
    assert caught.value.code == "reconstruction.resume.binding_mismatch"

    substituted = tmp_path / "substituted"
    shutil.copytree(partial.artifact_path, substituted)
    shutil.rmtree(substituted / "checkpoint")
    shutil.copytree(complete.artifact_path / "checkpoint", substituted / "checkpoint")
    with pytest.raises(ReconstructionFailure) as caught:
        reconstruct(
            execution_ref=execution,
            plan=plan,
            training_archive=archive,
            derived_seed=seed,
            artifact_path=tmp_path / "wrong-checkpoint-resume",
            resume_from=replace(partial, artifact_path=substituted),
        )
    assert caught.value.code in {
        "reconstruction.artifact.reconciliation_required",
        "reconstruction.resume.binding_mismatch",
    }


def test_loaded_outer_manifest_rejects_coercion_nonfinite_and_disagreement(
    tmp_path: Path,
) -> None:
    _data_value, archive, plan, execution, seed = _service_fixture(tmp_path)
    artifact = tmp_path / "valid-artifact"
    reconstruct(
        execution_ref=execution,
        plan=plan,
        training_archive=archive,
        derived_seed=seed,
        artifact_path=artifact,
    )
    for index, (field, value) in enumerate(
        (
            ("completed_steps", True),
            ("compile_seconds", float("nan")),
            ("train_execution_seconds", float("inf")),
            ("status", "PARTIAL"),
            ("normalization_scale", 2.0),
        )
    ):
        tampered = tmp_path / f"tampered-{index}"
        shutil.copytree(artifact, tampered)
        manifest_path = tampered / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest[field] = value
        manifest_path.write_text(
            json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        with pytest.raises(ReconstructionFailure) as caught:
            reconstruct(
                execution_ref=execution,
                plan=plan,
                training_archive=archive,
                derived_seed=seed,
                artifact_path=tampered,
            )
        assert caught.value.code in {
            "reconstruction.artifact.manifest_invalid",
            "reconstruction.artifact.reconciliation_required",
        }


@pytest.mark.parametrize(
    ("mode", "code"),
    (
        ("nan", "reconstruction.prediction.output_nonfinite"),
        ("shape", "reconstruction.prediction.output_contract_invalid"),
        ("dtype", "reconstruction.prediction.output_contract_invalid"),
        ("raise", "reconstruction.prediction.numerical_failure"),
        ("backend", "reconstruction.prediction.backend_unavailable"),
    ),
)
def test_outer_prediction_rejects_invalid_computed_outputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str, code: str
) -> None:
    data, archive, plan, execution, seed = _service_fixture(tmp_path)
    receipt = reconstruct(
        execution_ref=execution,
        plan=plan,
        training_archive=archive,
        derived_seed=seed,
        artifact_path=tmp_path / "artifact",
    )

    class InjectedPredictor:
        task = TaskConfig()

        def __call__(self, params, u0, nu, times, positions):
            del params, nu, times, positions
            if mode == "raise":
                raise RuntimeError("test-only numerical failure")
            shape = (u0.shape[0], u0.shape[1] + (1 if mode == "shape" else 0))
            dtype = np.float64 if mode == "dtype" else np.float32
            value = np.zeros(shape, dtype=dtype)
            if mode == "nan":
                value[0, 0] = np.nan
            return value

    import carbon.reconstruction._vendor.carbon_jax_lab.checkpoint as checkpoint_module

    if mode == "backend":

        def unavailable(*args, **kwargs):
            del args, kwargs
            raise RuntimeError("test-only backend initialization failure")

        monkeypatch.setattr(checkpoint_module, "load_inference", unavailable)
    else:
        monkeypatch.setattr(
            checkpoint_module,
            "load_inference",
            lambda *args, **kwargs: (InjectedPredictor(), object(), {}),
        )
    monkeypatch.setattr(jax, "jit", lambda function: function)
    monkeypatch.setattr(jax, "block_until_ready", lambda value: value)
    with pytest.raises(ReconstructionFailure) as caught:
        predict(
            receipt,
            initial=data.initial[:1],
            viscosity=data.viscosity[:1],
            requested_times=data.times[:1, ::-1],
            positions=data.positions,
        )
    assert caught.value.code == code


@pytest.mark.parametrize("invalid", ("overflow", "grid", "empty"))
def test_prediction_request_rejects_unrepresentable_or_invalid_inputs(
    tmp_path: Path, invalid: str
) -> None:
    data, archive, plan, execution, seed = _service_fixture(tmp_path)
    receipt = reconstruct(
        execution_ref=execution,
        plan=plan,
        training_archive=archive,
        derived_seed=seed,
        artifact_path=tmp_path / "artifact",
    )
    initial = data.initial[:1].copy()
    viscosity = data.viscosity[:1].copy()
    times = data.times[:1, ::-1].copy()
    positions = data.positions.copy()
    if invalid == "overflow":
        initial[0, 0] = np.finfo(np.float64).max
    elif invalid == "grid":
        positions[3] += 0.001
    else:
        initial = initial[:, :0]
        positions = positions[:0]
    with pytest.raises(ReconstructionFailure) as caught:
        predict(
            receipt,
            initial=initial,
            viscosity=viscosity,
            requested_times=times,
            positions=positions,
        )
    assert caught.value.code == "reconstruction.prediction.request_invalid"


def _repeat_member(
    plan,
    archive: PublicTrainingArchive,
    request_digest: str,
    execution: ExecutionAttemptRef,
    seed: DerivedSeed,
    replica_id: str,
    *,
    cancel: bool = False,
) -> DevelopmentReplica:
    digest = "sha256:" + hashlib.sha256(seed.as_backend_bytes()).hexdigest()
    policy = ResearchResourcePolicyRef(
        plan.challenge_key,
        "c02_development_repeat_policy",
        "1.0",
        RESOURCE_POLICY_SCHEMA_VERSION,
        RESOURCE_POLICY_CANONICALIZATION_PROFILE,
        "sha256:" + "2" * 64,
    )
    resource = ResourceClassRef(
        plan.challenge_key,
        "c02_local_cpu_fixture",
        "1.0",
        RESOURCE_POLICY_SCHEMA_VERSION,
        RESOURCE_POLICY_CANONICALIZATION_PROFILE,
        "sha256:" + "3" * 64,
    )
    placeholder = BoundReconstructionReplicate(
        ReconstructionReplicateIdentity(
            plan.challenge_key,
            plan.to_ref(),
            policy,
            resource,
            replica_id,
            "sha256:" + "0" * 64,
        )
    )
    replicate_digest = development_replicate_digest(
        binding=placeholder,
        execution_ref=execution,
        randomness_digest=digest,
        training_data_digest=archive.content_digest,
        request_digest=request_digest,
    )
    binding = BoundReconstructionReplicate(
        replace(placeholder.replicate_identity, replicate_digest=replicate_digest)
    )
    return DevelopmentReplica(binding, execution, digest, cancel)


@pytest.mark.parametrize("backbone", ("fno", "deeponet"))
def test_frozen_multireplica_runner_is_idempotent_and_retains_failures(
    tmp_path: Path, backbone: str
) -> None:
    source = tmp_path / "train.npz"
    data = _data()
    data.save(source)
    archive = PublicTrainingArchive.from_file(source, provenance="c02_repeat_fixture")
    plan = compile_c02_plan(tmp_path, backbone=backbone)
    request = {
        "initial": data.initial[:1],
        "viscosity": data.viscosity[:1],
        "requested_times": data.times[:1, ::-1],
        "positions": data.positions,
    }
    request_digest = development_request_digest(request)
    seeds = {
        "replica-a": DerivedSeed(bytes(range(32))),
        "replica-b": DerivedSeed(bytes(reversed(range(32)))),
        "replica-cancelled": DerivedSeed(bytes([7]) * 32),
    }
    members = []
    for index, (replica_id, seed) in enumerate(seeds.items(), start=1):
        execution = ExecutionAttemptRef(
            SubmissionId(str(uuid.UUID(f"42345678-1234-4234-8234-{index:012d}"))), 1
        )
        members.append(
            _repeat_member(
                plan,
                archive,
                request_digest,
                execution,
                seed,
                replica_id,
                cancel=replica_id.endswith("cancelled"),
            )
        )
    frozen = freeze_development_repeat_plan(
        plan_id=f"c02-{backbone}-bounded-repeat-fixture",
        construction_plan_digest=plan.to_ref().content_digest,
        training_data_digest=archive.content_digest,
        request_digest=request_digest,
        replicas=tuple(members),
    )
    output = tmp_path / "repeat-output"
    first = run_development_repeats(
        frozen,
        construction_plan=plan,
        training_archive=archive,
        derived_seeds=seeds,
        request=request,
        output_directory=output,
    )
    second = run_development_repeats(
        frozen,
        construction_plan=plan,
        training_archive=archive,
        derived_seeds=seeds,
        request=request,
        output_directory=output,
    )

    assert first == second
    assert first["required"] == 3
    assert first["completed"] == 2, first
    assert first["failed_or_incomplete"] == 1
    assert first["dispersion"]["status"] == "DESCRIPTIVE_ONLY"
    assert first["dispersion"]["conditional_on_successful_subset"] is True
    assert {item["disposition"] for item in first["outcomes"]} == {
        "COMPLETE",
        "CANCELLED",
    }
    assert len(tuple((output / "records").glob("*.json"))) == 3
    assert len(tuple((output / "predictions").glob("*.npz"))) == 2


def test_singleton_repeat_executes_once_and_ambiguous_reopen_requires_reconciliation(
    tmp_path: Path,
) -> None:
    source = tmp_path / "train.npz"
    data = _data()
    data.save(source)
    archive = PublicTrainingArchive.from_file(
        source, provenance="c02_singleton_fixture"
    )
    plan = compile_c02_plan(tmp_path, backbone="fno")
    request = {
        "initial": data.initial[:1],
        "viscosity": data.viscosity[:1],
        "requested_times": data.times[:1, ::-1],
        "positions": data.positions,
    }
    request_digest = development_request_digest(request)
    seed = DerivedSeed(bytes([11]) * 32)
    execution = ExecutionAttemptRef(
        SubmissionId(str(uuid.UUID("52345678-1234-4234-8234-123456789abc"))), 1
    )
    member = _repeat_member(plan, archive, request_digest, execution, seed, "singleton")
    frozen = freeze_development_repeat_plan(
        plan_id="c02-fno-singleton-fixture",
        construction_plan_digest=plan.to_ref().content_digest,
        training_data_digest=archive.content_digest,
        request_digest=request_digest,
        replicas=(member,),
    )
    seeds = {"singleton": seed}
    report = run_development_repeats(
        frozen,
        construction_plan=plan,
        training_archive=archive,
        derived_seeds=seeds,
        request=request,
        output_directory=tmp_path / "singleton-output",
    )
    assert report["completed"] == 1
    assert report["dispersion"]["status"] == "UNRESOLVED_INSUFFICIENT_REPLICAS"
    assert report["dispersion"]["mean_pointwise_sample_standard_deviation"] is None

    ambiguous = tmp_path / "ambiguous-output"
    (ambiguous / "artifacts" / "singleton").mkdir(parents=True)
    reopened = run_development_repeats(
        frozen,
        construction_plan=plan,
        training_archive=archive,
        derived_seeds=seeds,
        request=request,
        output_directory=ambiguous,
    )
    assert reopened["completed"] == 0
    assert reopened["outcomes"][0]["disposition"] == "RECONCILIATION_REQUIRED"
