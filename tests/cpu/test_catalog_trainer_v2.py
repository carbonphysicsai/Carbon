"""The catalog trainer v2 (`carbon/backbone_catalog/build_v2_src/`): the Carbon limits it removes, the keep-list refusals
that stay, and the equalities with v1 that must hold. The sources are bundle files (relative imports), so they are
loaded as a package beside a small stub registry."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import numpy as np
import pytest

torch = pytest.importorskip("torch")

SRC = (
    Path(__file__).resolve().parents[2] / "carbon" / "backbone_catalog" / "build_v2_src"
)
N_OUT = 6

STUB_BACKBONES = """
import torch

POINTS = 6
DEFAULT_STEPS = 12


class _Net(torch.nn.Module):
    def __init__(self, n_in, width):
        super().__init__()
        self.net = torch.nn.Sequential(torch.nn.Linear(n_in, width), torch.nn.GELU(), torch.nn.Linear(width, POINTS))

    def forward(self, x):
        return self.net(x)


def build_backbone(name, n_in):
    return _Net(n_in, 8)


ENTRIES = {"stub.Lib": ("M", "structured_1D", {"n_hidden": 8})}


def _library(model, n_in, geotype, **overrides):
    return _Net(n_in, overrides["n_hidden"])
"""


@pytest.fixture(scope="module")
def trainer(tmp_path_factory):
    root = tmp_path_factory.mktemp("trainer_v2")
    package = root / "v2pkg"
    package.mkdir()
    (package / "__init__.py").write_text("")
    (package / "backbones.py").write_text(STUB_BACKBONES)
    (package / "common.py").write_bytes((SRC / "common.py").read_bytes())
    (package / "build.py").write_bytes((SRC / "build.py").read_bytes())
    sys.path.insert(0, str(root))
    try:
        yield importlib.import_module("v2pkg.build")
    finally:
        sys.path.remove(str(root))
        for name in [m for m in sys.modules if m == "v2pkg" or m.startswith("v2pkg.")]:
            del sys.modules[name]


def data(n=40, n_in=3, seed=0):
    rng = np.random.default_rng(seed)
    x = rng.normal(size=(n, n_in))
    y = np.stack([np.sin(x @ rng.normal(size=n_in) + k) for k in range(N_OUT)], 1)
    return x, y


def run(trainer, train_use=None, configuration=None, seed=1):
    x, y = data()
    cfg = {"backbone": "stub.Plain", "learning_rate": 0.01, **(configuration or {})}
    return trainer.build(x, y, seed=seed, configuration=cfg, train_use=train_use or {})


def predict(product, x):
    return product["apply"](product["parameters"], torch.as_tensor(x)).numpy()


def test_a_plain_build_trains_and_is_deterministic(trainer):
    a, b = run(trainer), run(trainer)
    assert all(
        bool(torch.equal(p, q)) for p, q in zip(a["parameters"], b["parameters"])
    )
    assert predict(a, data()[0]).shape == (40, N_OUT)


# L1: per-output loss weights
def test_output_weights_change_the_loss_and_default_to_the_plain_mean(trainer):
    pred, y = torch.randn(5, N_OUT), torch.randn(5, N_OUT)
    plain = trainer._loss(pred, y, {})
    assert torch.equal(plain, ((pred - y) ** 2).mean(1).mean())
    only_first = trainer._loss(
        pred,
        y,
        {},
        None,
        trainer.output_weights({"output_weights": [1, 0, 0, 0, 0, 0]}, N_OUT),
    )
    assert torch.allclose(only_first, ((pred[:, 0] - y[:, 0]) ** 2).mean())
    doubled = trainer._loss(
        pred,
        y,
        {},
        None,
        trainer.output_weights({"output_weights": [2.0] * N_OUT}, N_OUT),
    )
    assert torch.allclose(doubled, plain)  # weights are normalised
    for kind in ("l1", "huber", "log_cosh", "relative_l2"):
        w = trainer.output_weights({"output_weights": [1, 2, 3, 4, 5, 6]}, N_OUT)
        assert trainer._loss(pred, y, {"kind": kind}, None, w) != trainer._loss(
            pred, y, {"kind": kind}
        )


def test_weighted_training_follows_the_weights(trainer):
    x, y = data()
    favour = run(trainer, {"steps": 60, "loss": {"output_weights": [1, 0, 0, 0, 0, 0]}})
    even = run(trainer, {"steps": 60})
    err = lambda p: float(np.mean((predict(p, x)[:, 0] - y[:, 0]) ** 2))  # noqa: E731
    assert err(favour) < err(even)


@pytest.mark.parametrize(
    "weights",
    [[1, 2], [-1, 1, 1, 1, 1, 1], [0, 0, 0, 0, 0, 0], [float("nan")] * N_OUT, "x"],
)
def test_bad_output_weights_are_refused(trainer, weights):
    with pytest.raises(ValueError):
        run(trainer, {"loss": {"output_weights": weights}})


# L2/L3/L13: ensembles with output subsets, more than four members, more combine kinds
def test_members_on_disjoint_subsets_combine_per_output(trainer):
    spec = {"members": [{"outputs": [0, 1]}, {"outputs": [2, 3]}, {"outputs": [4, 5]}]}
    cover, narrowed = trainer._members(spec, N_OUT)
    assert narrowed and cover.sum(0).tolist() == [1.0] * N_OUT
    w = trainer._combination("mean", spec, cover, None, None, None)
    assert torch.equal(w, cover)  # each output comes from the one member that covers it
    product = run(trainer, {"steps": 20, "ensemble": spec})
    assert predict(product, data()[0]).shape == (40, N_OUT)


def test_an_uncovered_output_is_refused(trainer):
    with pytest.raises(ValueError, match="covered by no ensemble member"):
        run(
            trainer,
            {"ensemble": {"members": [{"outputs": [0, 1]}, {"outputs": [2, 3]}]}},
        )
    with pytest.raises(ValueError, match="output indices"):
        run(trainer, {"ensemble": {"members": [{"outputs": [0, 99]}]}})


def test_more_than_four_members_are_accepted(trainer):
    product = run(trainer, {"steps": 4, "ensemble": {"members": 6}})
    assert len(product["parameters"]) == 6 * 4


def test_the_plain_mean_ensemble_is_the_average_of_its_members(trainer):
    members = [torch.nn.Linear(3, N_OUT) for _ in range(3)]
    ensemble = trainer.Ensemble(
        members, torch.full((3, N_OUT), 1 / 3, dtype=torch.float64)
    )
    x = torch.randn(4, 3)
    expected = (members[0](x) + members[1](x) + members[2](x)) * (1 / 3)
    assert torch.allclose(ensemble(x), expected, atol=1e-6)


@pytest.mark.parametrize(
    "combine", ["mean", "stacking", "stacking_per_output", "best_per_output"]
)
def test_every_combine_kind_builds(trainer, combine):
    spec = {
        "members": [{"outputs": [0, 1, 2, 3]}, {"outputs": [2, 3, 4, 5]}, {}],
        "combine": combine,
    }
    product = run(trainer, {"steps": 6, "ensemble": spec})
    assert np.isfinite(predict(product, data()[0])).all()


def test_explicit_combine_weights(trainer):
    spec = {"members": 2, "combine": "weights", "weights": [0.25, [1, 1, 1, 0, 0, 0]]}
    product = run(trainer, {"steps": 4, "ensemble": spec})
    assert np.isfinite(predict(product, data()[0])).all()
    for bad in (
        {"members": 2, "combine": "weights", "weights": [1]},
        {"members": 2, "combine": "magic"},
    ):
        with pytest.raises(ValueError):
            run(trainer, {"steps": 2, "ensemble": bad})


# L4: the added choice-list members
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


def test_an_unimplemented_choice_is_refused_not_faked(trainer):
    for use in (
        {"optimizer": {"name": "nope"}},
        {"schedule": {"name": "nope"}},
        {"loss": {"kind": "nope"}},
    ):
        with pytest.raises(ValueError):
            run(trainer, {"steps": 2, **use})


# L5: precision
def test_pytorch_precision_float32_is_allowed_and_float64_is_not_offered(trainer):
    assert run(trainer, {"steps": 3, "precision": "float32"})
    with pytest.raises(ValueError, match="precision must be"):
        run(trainer, {"steps": 3, "precision": "float64"})


# L6: arch keys
def test_library_arch_keys_are_taken_and_checked(trainer):
    assert trainer.arch_keys("stub.Lib") == trainer.LIBRARY_ARCH
    assert trainer.arch_keys("stub.Plain") == ()
    small = run(
        trainer, {"steps": 3}, {"backbone": "stub.Lib", "arch": {"n_hidden": 4}}
    )
    default = run(trainer, {"steps": 3}, {"backbone": "stub.Lib"})
    assert (
        small["parameters"][0].shape[0] == 4 and default["parameters"][0].shape[0] == 8
    )
    for arch in ({"bogus": 1}, {"n_hidden": 0}, {"n_hidden": 1.5}, {"dropout": 1.0}):
        with pytest.raises(ValueError):
            run(trainer, {"steps": 3}, {"backbone": "stub.Lib", "arch": arch})
    with pytest.raises(ValueError, match="arch settings are not supported"):
        run(trainer, {"steps": 3}, {"backbone": "stub.Plain", "arch": {"n_hidden": 4}})


def test_the_transolver_rule_is_kept(trainer):
    with pytest.raises(ValueError, match="multiple of heads"):
        trainer.make_model(
            {"backbone": "transolver", "arch": {"hidden": 33, "heads": 4}}, 3
        )


# L7: quantize bits
def test_quantize_bits_have_no_upper_bound_but_a_floor_of_two(trainer):
    assert run(trainer, {"steps": 3, "quantize": {"bits": 24}})
    assert run(trainer, {"steps": 3, "quantize": {"bits": 2}})
    for bits in (1, 0, -3, 2.5):
        with pytest.raises(ValueError):
            run(trainer, {"steps": 3, "quantize": {"bits": bits}})


# L8: seed range
def test_seeds_may_be_any_unsigned_64_bit_integer(trainer):
    assert run(trainer, {"steps": 3}, seed=2**63 + 5)
    assert run(
        trainer,
        {"steps": 3, "seeds": {"candidates": [0, 2**40, 2**64 - 1], "trial_steps": 2}},
    )
    for bad in (-1, 2**64, 1.5):
        with pytest.raises(ValueError, match="seed"):
            run(trainer, {"steps": 3, "seeds": {"candidates": [bad], "trial_steps": 2}})
    with pytest.raises(ValueError, match="seed"):
        run(trainer, {"steps": 3}, seed=2**64)


# the keep list still fires
def test_keep_list_refusals_still_fire(trainer):
    for use in ({"steps": 0}, {"bogus": 1}, {"search": {"candidates": [{"bogus": 1}]}}):
        with pytest.raises(ValueError):
            run(trainer, use)
    with pytest.raises(ValueError):
        run(trainer, {"steps": 2}, {"learning_rate": 5})
    with pytest.raises(ValueError):
        run(trainer, {"steps": 2}, {"bogus": 1})


def test_default_steps_come_from_the_registry(trainer):
    assert trainer.DEFAULT_STEPS == 12
