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


def test_the_cooling_prior_follows_the_repositorys_analytic_model_and_stays_small(
    prior_build,
):
    import jax
    import jax.numpy as jnp

    from carbon.cold_plate import analytic, domain, output_encoding

    _, prior = prior_build
    rows = cooling_inputs(3)
    references = []
    for row in rows:
        reference = analytic.predict(dict(zip(domain.INPUTS, map(float, row))))
        references.append(reference)
    # the same model at the repository's own resolution (20 cells per segment, 3 passes) agrees to rounding
    peak, profile, pressure = prior.native(jnp.asarray(rows), 20, 3)
    for k, reference in enumerate(references):
        assert abs(float(peak[k]) - reference["peak_c"]) < 1e-6
        assert (
            np.abs(np.asarray(profile[k]) - np.array(reference["profile_c"])).max()
            < 1e-6
        )
        assert abs(float(pressure[k]) / reference["pressure_drop_pa"] - 1) < 1e-9
    # the shipped resolution (10 cells, 2 passes) stays close to it, in the interface's encoding
    got = np.asarray(prior.prior(jnp.asarray(rows)))
    for reference, mine in zip(references, got):
        native = np.concatenate(
            [
                [reference["peak_c"]],
                reference["profile_c"],
                [reference["pressure_drop_pa"]],
            ]
        )
        expected = output_encoding.encode_targets(native.reshape(1, -1))[0]
        assert np.abs(mine[1:31] - expected[1:31]).max() < 0.15
        assert abs(mine[31] / expected[31] - 1) < 5e-4
    assert prior.PRIOR_ID == "cold_plate.analytic.v1" and prior.POSITIVE_OUTPUTS == (
        31,
    )
    # the graph must stay small: a custody ceiling of 1 MiB bound it at about 130 bytes per equation
    assert len(jax.make_jaxpr(prior.prior)(jnp.asarray(rows)).jaxpr.eqns) < 7500


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


def _prior_module(tmp_path_factory, file):
    import importlib.util

    spec = importlib.util.spec_from_file_location("prior_under_test", SRC / file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_motor_prior_equals_the_repositorys_analytic_model(
    prior_build, tmp_path_factory
):
    import jax.numpy as jnp

    from carbon.motor import analytic, domain

    prior = _prior_module(tmp_path_factory, "prior_motor.py")
    rng = np.random.default_rng(3)
    low = np.array([domain.INPUT_BOUNDS[k][0] for k in domain.INPUTS])
    high = np.array([domain.INPUT_BOUNDS[k][1] for k in domain.INPUTS])
    rows = low + (high - low) * rng.random((6, len(domain.INPUTS)))
    got = np.asarray(prior.prior(jnp.asarray(rows)))
    assert got.shape == (6, 60)
    for row, mine in zip(rows, got):
        reference = analytic.predict(dict(zip(domain.INPUTS, map(float, row))))[
            "torque_nm"
        ]
        assert np.allclose(mine, reference, rtol=1e-10, atol=1e-12)
    assert prior.PRIOR_ID == "prior.motor.surface-pm-v1"


def test_the_f08_prior_equals_an_independent_beam_computation(
    prior_build, tmp_path_factory
):
    import jax.numpy as jnp

    prior = _prior_module(tmp_path_factory, "prior_f08.py")
    rng = np.random.default_rng(4)
    low = np.array([b[0] for b in prior.INPUT_BOUNDS])
    high = np.array([b[1] for b in prior.INPUT_BOUNDS])
    rows = low + (high - low) * rng.random((5, 6))
    got = np.asarray(prior.prior(jnp.asarray(rows)))
    for (length, w, t, hr, tr, relief), mine in zip(rows * 1e-3, got):
        # independent reading of the note: composite section by parallel axes, compliance by integrating (L-x)^2/(E I)
        def section(narrow):
            pw = w - (0.020 if narrow else 0.0)
            parts = [
                (pw * t, t / 2, pw * t**3 / 12),
                (tr * hr, t + hr / 2, tr * hr**3 / 12),
                (tr * hr, t + hr / 2, tr * hr**3 / 12),
            ]
            area = sum(a for a, _, _ in parts)
            zc = sum(a * z for a, z, _ in parts) / area
            return area, sum(i + a * (z - zc) ** 2 for a, z, i in parts)

        (a1, i1), (a2, i2) = section(False), section(True)
        s, e = length / 2 - relief / 2, length / 2 + relief / 2
        seg = lambda lo, hi: ((length - lo) ** 3 - (length - hi) ** 3) / 3  # noqa: E731
        delta = (seg(0, s) + seg(e, length)) / (70e9 * i1) + seg(s, e) / (70e9 * i2)
        mass = 2700.0 * (a1 * (length - relief) + a2 * relief)
        f1 = np.sqrt(1 / delta / (33 / 140 * mass)) / (2 * np.pi)
        expected = [delta * 1e3]
        for z in (0.005, 0.01, 0.02):
            expected += [delta * 1e3 / (2 * z), f1 * np.sqrt(1 - 2 * z * z)]
        assert np.allclose(mine, expected, rtol=1e-9)
    assert prior.PRIOR_ID == "prior.f08.cantilever-beam-v1" and prior.N_OUT == 7


def test_the_f02_prior_matches_a_numerical_integration_of_its_two_node_network(
    prior_build, tmp_path_factory
):
    import jax.numpy as jnp

    prior = _prior_module(tmp_path_factory, "prior_f02.py")
    rows = np.array([[80.0, 5.0], [110.0, 10.0], [140.0, 20.0], [85.0, 5.0]])
    got = np.asarray(prior.prior(jnp.asarray(rows))).ravel()
    c_s, c_c = 2330.0 * 700.0 * 4e-4 * 5e-4, 8960.0 * 385.0 * 9e-4 * 2e-3
    r_con = 1.0 / (4 * 130.0 * np.sqrt(0.5 * 4e-4 / np.pi))
    r_sc = 5e-4 / (2 * 130 * 4e-4) + 2e-4 / (5 * 4e-4) + 2e-3 / (2 * 390 * 9e-4) + r_con
    r_cv = 1.0 / (2500.0 * 9e-4)
    for (power, on), mine in zip(rows, got):
        ts = tc = 40.0
        dt = 1e-4
        for _ in range(int(round(on / dt))):
            ts, tc = (
                ts + dt * (power - (ts - tc) / r_sc) / c_s,
                tc + dt * ((ts - tc) / r_sc - (tc - 30.0) / r_cv) / c_c,
            )
        assert abs(ts - mine) < 0.05
    assert prior.PRIOR_ID == "prior.f02.two-node-rc-v1" and prior.N_OUT == 1
