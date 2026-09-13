"""Required numerical conformance for the vendored C-02 development runtime."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np
import pytest
from c02_fixtures import compile_c02_plan
from third_party.transolver_reference import physics_attention_reference

from carbon.execution import ExecutionAttemptRef
from carbon.fees import SubmissionId
from carbon.reconstruction import PublicTrainingArchive, ReconstructionStatus
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
