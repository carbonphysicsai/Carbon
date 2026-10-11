"""MOTOR-NEURAL-01: Motor's neural families (an MLP and a DeepONet over the
torque curve) train through Carbon's shared JAX and PyTorch trainers, compile
from a finite Level-0 menu, and stay fail closed where nothing serves them
yet (practice's numpy worker, the validator)."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from carbon.motor import domain, neural
from carbon.motor.challenge import PublicMaterial
from carbon.motor.compile import NEURAL_FAMILIES, NEURAL_VALUES, compile_recipe, rebuild
from carbon.motor.contracts import IMPLEMENTATION_SOURCES, implementation_digest
from carbon.reconstruction import capability_registry as registry
from carbon.training_budget import adapter as tb

REPOSITORY = Path(__file__).resolve().parents[2]
TOKEN = registry.MOTOR_CHALLENGE


def strategy(backbone, **parameters):
    return {
        "schema_version": "1.0",
        "challenge_id": TOKEN,
        "backbone": backbone,
        "parameters": parameters,
    }


#: Small and quick: the tests check the mechanism, never a model's quality.
QUICK = {"width": "width_64", "depth": "depth_2", "steps": "steps_500"}


@pytest.fixture(scope="module")
def material():
    return PublicMaterial.load(REPOSITORY)


# -- the menu -------------------------------------------------------------------------------
def test_every_registered_token_has_exactly_one_value():
    surfaces = registry.catalog_surfaces(TOKEN)
    for name, values in NEURAL_VALUES.items():
        assert set(values) == set(surfaces[name][2]), name
    assert set(NEURAL_FAMILIES) == set(registry.MOTOR_NEURAL)
    # The research session's numpy worker offers the kernel ridge only.
    assert registry.lane_families(TOKEN, "session") == ("kernel_ridge",)


def test_the_defaults_compile_to_the_surfaced_settings():
    _, mlp = compile_recipe(strategy("mlp"))
    assert mlp.settings == {
        "activation": "gelu",
        "backend": "jax",
        "depth": 3,
        "learning_rate": 0.002,
        "steps": 2000,
        "width": 128,
    }
    _, deeponet = compile_recipe(strategy("deeponet"))
    assert deeponet.settings == {**mlp.settings, "basis_functions": 16}
    assert set(mlp.settings) == neural.SURFACED["mlp"]
    assert set(deeponet.settings) == neural.SURFACED["deeponet"]


def test_kernel_ridge_fields_do_not_apply_to_a_neural_family():
    from carbon.development_session.research_catalog import RecipeRejected
    from carbon.reconstruction.challenge_contracts import SubmissionRefused

    with pytest.raises((RecipeRejected, SubmissionRefused)):
        compile_recipe(strategy("mlp", length="length_4"))
    with pytest.raises((RecipeRejected, SubmissionRefused)):
        compile_recipe(strategy("mlp", basis_functions="basis_8"))


def test_the_implementation_pins_the_neural_code_and_its_shared_trainers():
    assert {"neural.py", "battery_training.py", "battery_torch_training.py"} <= set(
        IMPLEMENTATION_SOURCES
    )
    assert implementation_digest().startswith("sha256:")


# -- the rebuild ----------------------------------------------------------------------------
@pytest.mark.parametrize("family", NEURAL_FAMILIES)
def test_a_jax_rebuild_is_reproducible_and_predicts_the_curve(family, material):
    _, recipe = compile_recipe(strategy(family, **QUICK))
    first = neural.build(family, recipe.settings, material.train, 3)
    second = neural.build(family, recipe.settings, material.train, 3)
    other = neural.build(family, recipe.settings, material.train, 4)
    assert first[1]["params_sha256"] == second[1]["params_sha256"]
    assert first[1]["params_sha256"] != other[1]["params_sha256"]
    assert first[1]["backend"] == "jax" and first[1]["trainer"] == neural.TRAINER
    [curve] = [first[0].predict(material.practice[0]["inputs"])["torque_nm"]]
    assert len(curve) == domain.ANGLE_STEPS and all(map(math.isfinite, curve))
    assert sum(curve) / len(curve) >= 0


@pytest.mark.parametrize("family", NEURAL_FAMILIES)
def test_the_pytorch_backend_trains_the_same_network_through_the_same_mechanism(
    family, material
):
    pytest.importorskip("torch")
    settings = compile_recipe(strategy(family, **QUICK))[1].settings
    torch_settings = dict(settings, backend="pytorch")
    model, stats = neural.build(family, torch_settings, material.train, 3)
    again = neural.build(family, torch_settings, material.train, 3)[1]
    jax_stats = neural.build(family, settings, material.train, 3)[1]
    assert stats["params_sha256"] == again["params_sha256"]
    assert stats["backend"] == "pytorch"
    # One shared mechanism: the same parameterization, so the same count.
    assert stats["n_params"] == jax_stats["n_params"]
    curve = model.predict(material.practice[0]["inputs"])["torque_nm"]
    assert len(curve) == domain.ANGLE_STEPS and all(map(math.isfinite, curve))


def test_a_neural_rebuild_needs_carbons_seed_and_the_kernel_ridge_takes_none(
    material,
):
    _, recipe = compile_recipe(strategy("mlp", **QUICK))
    with pytest.raises(ValueError):
        rebuild(recipe, material)
    assert rebuild(recipe, material, seed=0).predict(material.practice[0]["inputs"])
    _, krr = compile_recipe(strategy("kernel_ridge"))
    with pytest.raises(ValueError):
        rebuild(krr, material, seed=0)
    assert rebuild(krr, material).predict(material.practice[0]["inputs"])


def test_settings_other_than_the_surfaces_are_refused():
    with pytest.raises(ValueError):
        neural.NeuralModel("mlp", {"width": 8})
    with pytest.raises(ValueError):
        neural.NeuralModel("fno", {})


# -- fail closed where nothing serves them yet -------------------------------------------------
def test_practice_refuses_a_neural_recipe_before_anything_starts():
    from carbon.motor.research import MotorPractice

    practice = object.__new__(MotorPractice)
    practice.backends = ("numpy",)
    assert practice.backend_refusal(strategy("mlp")) == ("numpy",)
    assert practice.backend_refusal(strategy("deeponet")) == ("numpy",)
    assert practice.backend_refusal(strategy("kernel_ridge")) is None


# -- the training budget adapter -------------------------------------------------------------
def test_motor_has_a_training_budget_adapter():
    assert TOKEN in tb.registered() and TOKEN not in tb.gaps()
    adapter = tb.adapter_for(TOKEN)
    assert adapter.backends() == ("jax", "pytorch")
    assert adapter.train_cases() == 150
    assert adapter.training_programs(strategy("kernel_ridge")) == []
    [program] = adapter.training_programs(strategy("mlp", **QUICK), train_cases=40)
    assert (program.backend, program.members, program.main_steps) == ("jax", 1, 500)
    assert program.cases_per_update == 40
    assert program.fit(16)["n_params"] > 0
    with pytest.raises(tb.AdapterGap):
        tb.record(adapter, "finalist_rule")
    assert tb.record(adapter, "worker") is rebuild
