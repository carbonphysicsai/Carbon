"""The catalog trainer v2 for JAX (`carbon/backbone_catalog/build_v2_src/build_jax.py`): the limits it removes, the keep-list
refusals that stay, and the TRAIN-dtype guard. The source is a bundle file (relative import), so it is loaded as a package
beside a small stub registry."""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

import numpy as np
import pytest

jax = pytest.importorskip("jax")
pytest.importorskip("equinox")
pytest.importorskip("optax")

SRC = (
    Path(__file__).resolve().parents[2]
    / "carbon"
    / "backbone_catalog"
    / "build_v2_src"
    / "build_jax.py"
)
N_OUT = 6

STUB_REGISTRY = """
import equinox as eqx
import jax


def build_backbone(name, key, n_in):
    model = eqx.nn.MLP(n_in, 6, 8, 1, key=key)
    return model, lambda m, x: jax.vmap(m)(x)
"""


def make_package(root: Path):
    package = root / "v2jax"
    package.mkdir()
    (package / "__init__.py").write_text("")
    (package / "jax_backbones_dc.py").write_text(STUB_REGISTRY)
    (package / "build.py").write_bytes(SRC.read_bytes())
    return package


@pytest.fixture(scope="module")
def trainer(tmp_path_factory):
    import importlib

    if not jax.config.jax_enable_x64:
        jax.config.update("jax_enable_x64", True)
    root = tmp_path_factory.mktemp("trainer_v2_jax")
    make_package(root)
    sys.path.insert(0, str(root))
    try:
        yield importlib.import_module("v2jax.build")
    finally:
        sys.path.remove(str(root))
        for name in [m for m in sys.modules if m == "v2jax" or m.startswith("v2jax.")]:
            del sys.modules[name]


def data(n=40, n_in=3, seed=0):
    rng = np.random.default_rng(seed)
    x = rng.normal(size=(n, n_in))
    y = np.stack([np.sin(x @ rng.normal(size=n_in) + k) for k in range(N_OUT)], 1)
    return x, y


def run(trainer, train_use=None, seed=1, configuration=None):
    x, y = data()
    cfg = {"backbone": "stub", "learning_rate": 0.01, **(configuration or {})}
    return trainer.build(x, y, seed=seed, configuration=cfg, train_use=train_use or {})


def predict(product, x):
    return np.asarray(product["apply"](product["parameters"], x))


def test_a_plain_build_is_deterministic_and_float64(trainer):
    a, b = run(trainer, {"steps": 10}), run(trainer, {"steps": 10})
    assert all(
        np.array_equal(np.asarray(p), np.asarray(q))
        for p, q in zip(a["parameters"], b["parameters"])
    )
    out = predict(a, data()[0])
    assert out.shape == (40, N_OUT) and out.dtype == np.float64


def test_output_weights_follow_the_weights(trainer):
    x, y = data()
    favour = run(trainer, {"steps": 80, "loss": {"output_weights": [1, 0, 0, 0, 0, 0]}})
    even = run(trainer, {"steps": 80})
    err = lambda p: float(np.mean((predict(p, x)[:, 0] - y[:, 0]) ** 2))  # noqa: E731
    assert err(favour) < err(even)
    for kind in ("l1", "huber", "log_cosh", "relative_l2"):
        assert run(
            trainer,
            {"steps": 3, "loss": {"kind": kind, "output_weights": [1, 2, 3, 4, 5, 6]}},
        )


@pytest.mark.parametrize(
    "weights", [[1, 2], [-1, 1, 1, 1, 1, 1], [0] * N_OUT, [float("nan")] * N_OUT, "x"]
)
def test_bad_output_weights_are_refused(trainer, weights):
    with pytest.raises(ValueError):
        run(trainer, {"loss": {"output_weights": weights}})


def test_members_on_disjoint_subsets_combine_per_output(trainer):
    spec = {"members": [{"outputs": [0, 1]}, {"outputs": [2, 3]}, {"outputs": [4, 5]}]}
    cover = trainer.members_cover(spec, N_OUT)
    assert (trainer.combination("mean", spec, cover, None, None) == cover).all()
    product = run(trainer, {"steps": 6, "ensemble": spec})
    assert np.isfinite(predict(product, data()[0])).all()


def test_an_uncovered_output_is_refused(trainer):
    with pytest.raises(ValueError, match="covered by no ensemble member"):
        run(
            trainer,
            {"ensemble": {"members": [{"outputs": [0, 1]}, {"outputs": [2, 3]}]}},
        )
    with pytest.raises(ValueError, match="output indices"):
        run(trainer, {"ensemble": {"members": [{"outputs": [0, 99]}]}})


def test_more_than_four_members_are_accepted(trainer):
    assert len(
        run(trainer, {"steps": 3, "ensemble": {"members": 6}})["parameters"]
    ) == 6 * len(run(trainer, {"steps": 3})["parameters"])


@pytest.mark.parametrize(
    "combine", ["mean", "stacking", "stacking_per_output", "best_per_output"]
)
def test_every_combine_kind_builds(trainer, combine):
    spec = {
        "members": [{"outputs": [0, 1, 2, 3]}, {"outputs": [2, 3, 4, 5]}, {}],
        "combine": combine,
    }
    assert np.isfinite(
        predict(run(trainer, {"steps": 4, "ensemble": spec}), data()[0])
    ).all()


def test_explicit_combine_weights_and_a_bad_kind(trainer):
    good = {"members": 2, "combine": "weights", "weights": [0.25, [1, 1, 1, 0, 0, 0]]}
    assert np.isfinite(
        predict(run(trainer, {"steps": 3, "ensemble": good}), data()[0])
    ).all()
    for bad in (
        {"members": 2, "combine": "weights", "weights": [1]},
        {"members": 2, "combine": "magic"},
    ):
        with pytest.raises(ValueError):
            run(trainer, {"steps": 2, "ensemble": bad})


@pytest.mark.parametrize(
    "optimizer", ["adagrad", "nadam", "radam", "adamw", "sgd", "rmsprop"]
)
def test_added_optimizers_train(trainer, optimizer):
    assert run(trainer, {"steps": 3, "optimizer": {"name": optimizer}})


@pytest.mark.parametrize(
    "schedule", ["exponential", "polynomial", "cosine_restarts", "cosine", "onecycle"]
)
def test_added_schedules_train(trainer, schedule):
    assert run(trainer, {"steps": 6, "schedule": {"name": schedule}})


def test_unimplemented_choices_are_refused(trainer):
    for use in (
        {"optimizer": {"name": "nope"}},
        {"schedule": {"name": "nope"}},
        {"loss": {"kind": "nope"}},
    ):
        with pytest.raises(ValueError):
            run(trainer, {"steps": 2, **use})


def test_quantize_bits_have_no_upper_bound_but_a_floor_of_two(trainer):
    assert run(trainer, {"steps": 3, "quantize": {"bits": 24}})
    assert run(trainer, {"steps": 3, "quantize": {"bits": 2}})
    for bits in (1, 0, 2.5):
        with pytest.raises(ValueError):
            run(trainer, {"steps": 3, "quantize": {"bits": bits}})


def test_seeds_stay_uint32_for_the_numpy_seeded_trainer(trainer):
    assert run(
        trainer, {"steps": 3, "seeds": {"candidates": [0, 2**32 - 1], "trial_steps": 2}}
    )
    for bad in (-1, 2**32):
        with pytest.raises(ValueError, match="seed"):
            run(trainer, {"steps": 3, "seeds": {"candidates": [bad], "trial_steps": 2}})


def test_keep_list_refusals_still_fire(trainer):
    for use in ({"steps": 0}, {"bogus": 1}):
        with pytest.raises(ValueError):
            run(trainer, use)
    with pytest.raises(ValueError):
        run(trainer, {"steps": 2}, configuration={"learning_rate": 5})


def test_the_x64_guard_follows_the_trains_own_dtype(tmp_path):
    """A float32 TRAIN trains in float32 with x64 off; a float64 TRAIN without x64 is refused."""
    package = make_package(tmp_path)
    script = textwrap.dedent(f"""
        import sys
        import numpy as np
        sys.path.insert(0, {str(tmp_path)!r})
        from v2jax import build
        x = np.random.default_rng(0).normal(size=(30, 3))
        y = np.random.default_rng(1).normal(size=(30, 6))
        cfg = {{"backbone": "stub", "learning_rate": 0.01}}
        p = build.build(x.astype(np.float32), y.astype(np.float32), seed=1, configuration=cfg, train_use={{"steps": 3}})
        out = np.asarray(p["apply"](p["parameters"], x.astype(np.float32)))
        assert out.dtype == np.float32, out.dtype
        try:
            build.build(x, y, seed=1, configuration=cfg, train_use={{"steps": 3}})
        except RuntimeError as error:
            assert "float64 TRAIN" in str(error)
            print("OK")
        """)
    env = {**os.environ, "JAX_ENABLE_X64": "0", "JAX_PLATFORMS": "cpu"}
    done = subprocess.run(
        [sys.executable, "-c", script],
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert "OK" in done.stdout, done.stderr[-1500:]
    assert package.is_dir()
