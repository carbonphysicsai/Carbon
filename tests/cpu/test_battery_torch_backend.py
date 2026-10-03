"""The PyTorch reconstruction backend for battery recipes (RECON-TORCH-01).

OWNER-PYTORCH-BACKEND-01: a recipe names its backend, and Carbon rebuilds it
with its own trainer for that backend. These tests hold the PyTorch side:
admission rules, determinism under one seed, exact state round trips, the FNO
family, the optimizer and curve ports, and that torch loads only inside the
PyTorch backend. Every surface's effect is covered for both backends by the
controls in `test_battery_construction_contract`.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from carbon.battery import challenge as ch
from carbon.battery import recipes
from carbon.battery.compile import compile_recipe, rebuild
from carbon.development_session.research_catalog import RecipeRejected
from carbon.reconstruction import capability_registry as r
from tests.cpu.test_battery_construction_contract import BATTERY, SMALL, strategy

ROOT = Path(__file__).resolve().parents[2]
#: CI sets CARBON_REQUIRE_TORCH=1 where the science-torch group is installed,
#: so a missing PyTorch stack fails there instead of skipping.
needs_torch = pytest.mark.skipif(
    os.environ.get("CARBON_REQUIRE_TORCH") != "1"
    and (
        importlib.util.find_spec("torch") is None
        or importlib.util.find_spec("neuralop") is None
    ),
    reason="the science-torch group is not installed",
)


def recipe(family="mlp", **parameters):
    return compile_recipe(
        strategy(
            BATTERY, family, **{**SMALL[family], "backend": "pytorch", **parameters}
        )
    )[1]


# --- Admission (no torch needed). ---


def test_the_backend_is_a_registered_choice_with_jax_as_default():
    surface = r.catalog_surfaces(BATTERY)["backend"]
    assert surface[1] == "choice"
    assert tuple(surface[2]) == ("jax", "pytorch")
    assert surface[4] == "jax"
    _, plain = compile_recipe(strategy(BATTERY, "mlp", **SMALL["mlp"]))
    assert plain.settings["backend"] == "jax"


def test_the_fno_family_is_pytorch_only_and_float32_only():
    with pytest.raises(
        RecipeRejected, match="dependency_unsatisfied@/parameters/backend"
    ):
        recipe("fno", backend="jax")
    with pytest.raises(
        RecipeRejected, match="dependency_unsatisfied@/parameters/precision"
    ):
        recipe("fno", precision="float64")
    with pytest.raises(RecipeRejected, match="not_applicable@/parameters/n_modes"):
        recipe("mlp", n_modes=8)


def test_choosing_a_backend_changes_the_recipe_identity_not_jax_defaults():
    _, implicit = compile_recipe(strategy(BATTERY, "mlp", **SMALL["mlp"]))
    _, explicit = compile_recipe(
        strategy(BATTERY, "mlp", **SMALL["mlp"], backend="jax")
    )
    torch_ = recipe("mlp")
    assert implicit.settings == explicit.settings
    assert torch_.recipe_digest not in (implicit.recipe_digest, explicit.recipe_digest)


def test_compiling_a_pytorch_recipe_never_imports_torch():
    code = (
        "import sys, json\n"
        "from carbon.battery.compile import compile_recipe\n"
        "from tests.cpu.test_battery_construction_contract import strategy, BATTERY\n"
        "compile_recipe(strategy(BATTERY, 'fno', backend='pytorch'))\n"
        "print(json.dumps(sorted(m for m in ('torch','neuralop') if m in sys.modules)))\n"
    )
    out = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
        cwd=ROOT,
    )
    assert json.loads(out.stdout.strip().splitlines()[-1]) == []


# --- Rebuilds (torch required). ---


@pytest.fixture(scope="module")
def material():
    return ch.PublicMaterial.load()


@pytest.fixture(scope="module")
def train(material):
    return material.train.subset(48)


def build(material, train, family="mlp", seed=0, **parameters):
    model, stats = rebuild(recipe(family, **parameters), material, seed, train=train)
    return model, stats


@needs_torch
@pytest.mark.parametrize("family", ["mlp", "deeponet", "fno"])
def test_the_same_seed_rebuilds_the_same_weights(material, train, family):
    _, first = build(material, train, family, seed=5)
    _, again = build(material, train, family, seed=5)
    _, other = build(material, train, family, seed=6)
    assert first["backend"] == "pytorch"
    assert first["params_sha256"] == again["params_sha256"]
    assert first["params_sha256"] != other["params_sha256"]


@needs_torch
@pytest.mark.parametrize(
    "family,parameters",
    [
        ("mlp", {}),
        ("mlp", {"trajectory_components": 4}),
        ("mlp", {"ensemble_members": 2}),
        ("deeponet", {"precision": "float64"}),
        ("fno", {}),
        ("fno", {"ensemble_members": 2}),
    ],
)
def test_a_stored_pytorch_state_predicts_exactly_as_the_trained_model(
    material, train, family, parameters
):
    model, _ = build(material, train, family, seed=1, **parameters)
    x = material.train.x[200:208]
    expected = model.predict(x)
    restored = recipes.model_from_bytes(recipes.state_bytes(model))
    got = restored.predict(x)
    assert set(got) == {"v", "t", "eta", "q"}
    for key in expected:
        assert np.array_equal(expected[key], got[key]), key


@needs_torch
def test_a_state_never_loads_under_the_other_backend(material, train):
    model, _ = build(material, train, "mlp", seed=1)
    header, arrays = recipes.export_state(model)
    header["settings"] = {**header["settings"], "backend": "jax"}
    with pytest.raises(ValueError, match="backend"):
        recipes.import_state(header, arrays)


@needs_torch
def test_both_backends_predict_in_the_same_format(material, train):
    x = material.train.x[200:208]
    jax_model, _ = rebuild(
        compile_recipe(strategy(BATTERY, "mlp", **SMALL["mlp"]))[1],
        material,
        0,
        train=train,
    )
    torch_model, _ = build(material, train, "mlp")
    a, b = jax_model.predict(x), torch_model.predict(x)
    assert {k: (v.shape, v.dtype) for k, v in a.items()} == {
        k: (v.shape, v.dtype) for k, v in b.items()
    }


@needs_torch
def test_every_optimizer_trains_the_fourier_operator(material, train):
    choices = r.catalog_surfaces(BATTERY)["optimizer_family"][2]
    hashes = {}
    for name in choices:
        _, stats = build(material, train, "fno", optimizer_family=name)
        assert np.isfinite(stats["final_loss"]), name
        hashes[name] = stats["params_sha256"]
    assert len(set(hashes.values())) == len(choices)


@needs_torch
def test_every_learning_rate_curve_is_the_optax_schedule():
    """The PyTorch curves are ports of the JAX backend's optax schedules."""
    optax = pytest.importorskip("optax")

    from carbon.battery import torch_training
    from carbon.battery.training import curve as jax_curve

    defaults = {n: v[4] for n, v in r.catalog_surfaces(BATTERY).items()}
    for name in r.catalog_surfaces(BATTERY)["learning_rate_curve"][2]:
        for warmup, ratio in ((0, 0.0), (10, 0.25)):
            settings = {
                **defaults,
                "learning_rate": 0.01,
                "learning_rate_curve": name,
                "warmup_steps": warmup,
                "min_learning_rate_ratio": ratio,
            }
            ours = torch_training.curve(settings, 100)
            theirs = jax_curve(optax, settings, 100)
            for i in range(100):
                assert ours(i) == pytest.approx(float(theirs(i)), rel=1e-5, abs=1e-9), (
                    name,
                    warmup,
                    i,
                )


def test_a_jax_rebuild_never_imports_torch():
    code = (
        "import sys, json\n"
        "from carbon.battery import challenge as ch\n"
        "from carbon.battery.compile import compile_recipe, rebuild\n"
        "from tests.cpu.test_battery_construction_contract import strategy, BATTERY, SMALL\n"
        "m = ch.PublicMaterial.load()\n"
        "_, rec = compile_recipe(strategy(BATTERY, 'mlp', **SMALL['mlp']))\n"
        "model, _ = rebuild(rec, m, 0, train=m.train.subset(16))\n"
        "model.predict(m.train.x[:2])\n"
        "print(json.dumps('torch' in sys.modules))\n"
    )
    out = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
        cwd=ROOT,
    )
    assert json.loads(out.stdout.strip().splitlines()[-1]) is False


@needs_torch
def test_the_determinism_harness_reports_exact_differences_and_no_verdict():
    from carbon.battery.torch_determinism import SCHEMA, study

    report = study(
        strategy(BATTERY, "mlp", **{**SMALL["mlp"], "backend": "pytorch"}),
        repeats=2,
        seed=3,
        root=ROOT,
    )
    assert report["schema"] == SCHEMA and report["backend"] == "pytorch"
    assert "sets no tolerance" in report["authority"]
    # Two fresh interpreters on one host, one seed: the same weights.
    assert report["all_weights_identical"] is True
    (row,) = report["comparisons"]
    assert all(
        d["identical"] and d["max_abs"] == 0.0 for d in row["predictions"].values()
    )
    assert not {"pass", "fail", "tolerance"} & set(report)
