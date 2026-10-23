"""Physics prior + learned residual (`carbon/backbone_catalog/prior_src/`): the settings Schema mirrors the build, the
Cooling prior port equals the repository's analytic model, and the closed-form KRR is deterministic and beats the plain fit.
"""

from __future__ import annotations

import hashlib
import importlib
import io
import sys
import tarfile
from pathlib import Path

import numpy as np
import pytest

from carbon.backbone_catalog import pipeline, settings
from carbon.backbone_catalog.entries import CatalogRefused

SRC = Path(settings.__file__).resolve().parent / "prior_src"
COOLING = {"id": "chip-cold-plate", "version": "1.3"}


def item(backbone="krr", prior=True, challenge=COOLING):
    entry = {
        "catalog_id": "cooling.prior." + backbone,
        "backbone": backbone,
        "settings_schema": settings.JAX_PRIOR.schema_id,
        "challenges": [challenge],
        "defaults": {"configuration": {"backbone": backbone}, "train_use": {}},
    }
    if prior:
        entry["prior"] = {"id": "cold_plate.analytic.v1", "positive_outputs": [31]}
    return entry


def ok(entry, configuration=None, train_use=None):
    return settings.resolve(entry, configuration or {}, train_use or {})


def refused(entry, configuration=None, train_use=None, code=None):
    with pytest.raises(CatalogRefused) as caught:
        ok(entry, configuration, train_use)
    if code:
        assert caught.value.code == code


def test_the_prior_schema_pins_the_build_file():
    digest = (
        "sha256:" + hashlib.sha256((SRC / "build_prior.py").read_bytes()).hexdigest()
    )
    assert settings.JAX_PRIOR.build_sha256 == digest
    assert settings.schema_for_build(digest) == "carbon-candidate-jax-prior-v1"
    assert settings.JAX_PRIOR.prior and not settings.JAX_V2.prior


def test_krr_settings_are_checked_against_the_interface():
    entry = item()
    ok(entry)
    ok(
        entry,
        {"krr": {"kernel": "matern52", "length_scales": [1.0] * 9, "ridge": 1e-4}},
    )
    ok(entry, {"prior": "none", "krr": {"length_scales": 2}})
    separate = {
        "groups": [
            {"outputs": [0, 31]},
            {
                "outputs": [31, 32],
                "log_space": True,
                "length_scales": 1.5,
                "ridge": 1e-7,
            },
        ]
    }
    ok(entry, {"krr": separate})
    refused(entry, {"krr": {"kernel": "poly"}}, code="catalog_setting_invalid")
    refused(
        entry, {"krr": {"length_scales": [1.0] * 8}}, code="catalog_setting_invalid"
    )
    refused(entry, {"krr": {"ridge": 0}}, code="catalog_setting_invalid")
    refused(entry, {"krr": {"bogus": 1}}, code="catalog_setting_unknown")
    refused(
        entry,
        {"krr": {"groups": [{"outputs": [0, 31]}]}},
        code="catalog_settings_inconsistent",
    )
    refused(
        entry,
        {"krr": {"groups": [{"outputs": [0, 20]}, {"outputs": [21, 32]}]}},
        code="catalog_settings_inconsistent",
    )
    refused(
        entry,
        {"krr": {"groups": [{"outputs": [0, 33]}]}},
        code="catalog_setting_invalid",
    )
    refused(
        entry, {"krr": {"log_space": True}}, code="catalog_setting_invalid"
    )  # only slot 31 is positive
    refused(entry, {"prior": "magic"}, code="catalog_setting_invalid")
    refused(entry, train_use={"steps": 10}, code="catalog_setting_invalid")


def test_without_a_prior_only_prior_none_is_offered_and_other_backbones_take_the_trainer_levers():
    refused(item(prior=False), {"prior": "analytic"}, code="catalog_setting_invalid")
    ok(item(prior=False), {"prior": "none"})
    mlp = item("mlp")
    ok(mlp, {"learning_rate": 0.01}, {"steps": 50, "optimizer": {"name": "adam"}})
    refused(mlp, {"krr": {"ridge": 1e-3}}, code="catalog_setting_invalid")


def test_the_prior_facts_are_read_from_the_bundle_without_importing_it():
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w:gz") as archive:
        data = b'PRIOR_ID = "x.v1"\nPOSITIVE_OUTPUTS = (3, 1)\nimport nonexistent_module_that_would_fail\n'
        info = tarfile.TarInfo("root/carbon_candidate/prior.py")
        info.size = len(data)
        archive.addfile(info, io.BytesIO(data))
    assert pipeline._prior_facts(raw.getvalue()) == {
        "id": "x.v1",
        "positive_outputs": [1, 3],
    }
    empty = io.BytesIO()
    with tarfile.open(fileobj=empty, mode="w:gz"):
        pass
    assert pipeline._prior_facts(empty.getvalue()) is None


@pytest.fixture(scope="module")
def prior_build(tmp_path_factory):
    jax = pytest.importorskip("jax")
    jax.config.update("jax_enable_x64", True)
    root = tmp_path_factory.mktemp("prior_pkg")
    package = root / "ppkg"
    package.mkdir()
    (package / "__init__.py").write_text("")
    (package / "prior.py").write_bytes((SRC / "prior_cooling.py").read_bytes())
    (package / "build.py").write_bytes((SRC / "build_prior.py").read_bytes())
    sys.path.insert(0, str(root))
    try:
        yield importlib.import_module("ppkg.build"), importlib.import_module(
            "ppkg.prior"
        )
    finally:
        sys.path.remove(str(root))
        for name in [m for m in sys.modules if m == "ppkg" or m.startswith("ppkg.")]:
            del sys.modules[name]


def cooling_inputs(n, seed=0):
    from carbon.cold_plate import domain

    rng = np.random.default_rng(seed)
    low = np.array([domain.INPUT_BOUNDS[k][0] for k in domain.INPUTS])
    high = np.array([domain.INPUT_BOUNDS[k][1] for k in domain.INPUTS])
    rows = low + (high - low) * rng.random((n, len(domain.INPUTS)))
    rows[:, 6] = 1.0 + 0.5 * rng.random(n)  # a hot spot ratio the profile can reach
    return rows


def test_the_cooling_prior_equals_the_repositorys_analytic_model_and_encoding(
    prior_build,
):
    import jax.numpy as jnp

    from carbon.cold_plate import analytic, domain, output_encoding

    _, prior = prior_build
    rows = cooling_inputs(3)
    got = np.asarray(prior.prior(jnp.asarray(rows)))
    for row, mine in zip(rows, got):
        reference = analytic.predict(dict(zip(domain.INPUTS, map(float, row))))
        native = np.concatenate(
            [
                [reference["peak_c"]],
                reference["profile_c"],
                [reference["pressure_drop_pa"]],
            ]
        )
        expected = output_encoding.encode_targets(native.reshape(1, -1))[0]
        assert np.abs(mine - expected).max() < 1e-6
    assert prior.PRIOR_ID == "cold_plate.analytic.v1" and prior.POSITIVE_OUTPUTS == (
        31,
    )


def test_solve_spd_matches_numpy_and_krr_is_deterministic_and_beats_the_plain_fit(
    prior_build,
):
    import jax.numpy as jnp

    build, prior = prior_build
    rng = np.random.default_rng(1)
    a = rng.normal(size=(30, 30))
    spd = a @ a.T + 30 * np.eye(30)
    rhs = rng.normal(size=(30, 4))
    assert np.allclose(build._solve_spd(spd, rhs), np.linalg.solve(spd, rhs), atol=1e-9)

    x = cooling_inputs(24)
    wiggle = 0.05 * np.sin(x[:, :1] * 7.0) * np.ones((1, 32))
    y = np.asarray(prior.prior(jnp.asarray(x))) + wiggle
    first = build.build(x, y, seed=1, configuration={"backbone": "krr"}, train_use={})
    second = build.build(x, y, seed=1, configuration={"backbone": "krr"}, train_use={})
    assert all(
        np.array_equal(np.asarray(p), np.asarray(q))
        for p, q in zip(first["parameters"], second["parameters"])
    )
    held = cooling_inputs(8, seed=5)
    truth = np.asarray(prior.prior(jnp.asarray(held))) + 0.05 * np.sin(
        held[:, :1] * 7.0
    ) * np.ones((1, 32))
    with_prior = np.asarray(first["apply"](first["parameters"], held))
    plain = build.build(
        x, y, seed=1, configuration={"backbone": "krr", "prior": "none"}, train_use={}
    )
    without = np.asarray(plain["apply"](plain["parameters"], held))
    assert (
        np.abs(with_prior[:, 1:31] - truth[:, 1:31]).mean()
        < np.abs(without[:, 1:31] - truth[:, 1:31]).mean()
    )
    for bad in (
        {"backbone": "krr", "krr": {"groups": [{"outputs": [0, 31]}]}},
        {"backbone": "krr", "krr": {"log_space": True}},
    ):
        with pytest.raises(ValueError):
            build.build(x, y, seed=1, configuration=bad, train_use={})
    with pytest.raises(ValueError, match="takes no settings"):
        build.build(
            x, y, seed=1, configuration={"backbone": "krr"}, train_use={"steps": 5}
        )
