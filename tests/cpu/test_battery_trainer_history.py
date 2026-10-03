"""Battery trainer v2: a capped TRAIN-loss history, in practice only (RSURF-D3).

The owner, 2026-10-03: practice may record a short training-loss history from
TRAIN data only, as a new trainer version, and earlier records keep their old
one. These tests hold what makes that safe:
- recording changes no weight;
- it is off unless practice turns it on;
- the validator's reconstruction program never turns it on;
- the history is capped and checked before it reaches feedback.
"""

from __future__ import annotations

import math

import pytest

from carbon.battery import challenge as ch
from carbon.battery import practice, training, worker
from carbon.battery.compile import compile_recipe, rebuild
from carbon.battery.research_view import LEARNING_CURVE
from tests.cpu.test_battery_construction_contract import BATTERY, SMALL, strategy
from tests.cpu.test_battery_torch_backend import needs_torch


@pytest.fixture(scope="module")
def material():
    return ch.PublicMaterial.load()


@pytest.fixture(scope="module")
def train(material):
    return material.train.subset(48)


@pytest.fixture
def recording():
    """Turn recording on for one test, and always off again after it."""
    training.record_training_history(True)
    try:
        yield
    finally:
        training.record_training_history(False)


def fit(material, train, family, seed=3, **parameters):
    recipe = compile_recipe(
        strategy(BATTERY, family, **{**SMALL[family], **parameters})
    )[1]
    return rebuild(recipe, material, seed, train=train)[1]


CASES = [
    ("mlp", {}),
    ("mlp", {"batch_size": 16}),
    ("mlp", {"ensemble_members": 2}),
    ("deeponet", {}),
]


@pytest.mark.parametrize("family,parameters", CASES)
def test_recording_changes_no_weight(material, train, family, parameters):
    off = fit(material, train, family, **parameters)
    training.record_training_history(True)
    try:
        on = fit(material, train, family, **parameters)
    finally:
        training.record_training_history(False)
    assert "loss_history" not in off
    assert on["params_sha256"] == off["params_sha256"]
    assert on["final_loss"] == off["final_loss"]
    history = on["loss_history"]
    assert history["trainer"] == training.TRAINER_VERSION
    steps = [p[0] for p in history["points"]]
    assert steps == sorted(set(steps)) and steps[0] == 0
    assert all(math.isfinite(p[1]) for p in history["points"])
    if parameters.get("ensemble_members"):
        assert history["member"] == "1 of 2"


@needs_torch
@pytest.mark.parametrize(
    "family,parameters",
    [("mlp", {"backend": "pytorch"}), ("fno", {}), ("fno", {"ensemble_members": 2})],
)
def test_recording_changes_no_pytorch_weight(material, train, family, parameters):
    test_recording_changes_no_weight(material, train, family, parameters)


def test_off_is_the_default_and_nothing_lingers(material, train):
    assert training.recording_history() is False
    assert "loss_history" not in fit(material, train, "mlp")
    assert training.take_history() is None


def test_the_history_is_capped_and_evenly_spaced(material, train, recording):
    stats = fit(material, train, "mlp", steps=300)
    points = stats["loss_history"]["points"]
    assert len(points) == training.HISTORY_POINTS
    assert points[0][0] == 0 and points[-1][0] == 299
    assert stats["loss_history"]["updates"] == 300


def test_keep_history_bounds_and_drops_non_finite(recording):
    training.keep_history(enumerate([1.0] * 1000), 1000)
    kept = training.take_history()
    assert len(kept["points"]) == training.HISTORY_POINTS
    assert kept["points"][0][0] == 0 and kept["points"][-1][0] == 999
    training.keep_history([(0, 1.0), (1, float("nan")), (2, 0.5)], 3)
    assert training.take_history()["points"] == [[0, 1.0], [2, 0.5]]
    # Taken once.
    assert training.take_history() is None
    training.record_training_history(False)
    training.keep_history([(0, 1.0)], 1)
    assert training.take_history() is None


def test_knn_trains_nothing_and_records_nothing(material, train, recording):
    assert "loss_history" not in fit(material, train, "knn")


def test_only_practice_turns_it_on():
    assert "training.record_training_history(True)" in practice.PROGRAM
    assert "record_training_history" not in worker.RECONSTRUCT_PROGRAM


def test_practice_feedback_carries_a_checked_history_only():
    recipe = compile_recipe(strategy(BATTERY, "mlp", **SMALL["mlp"]))[1]
    good = {
        "trainer": training.TRAINER_VERSION,
        "updates": 32,
        "objective": "the trainer's own loss on TRAIN data",
        "points": [[0, 0.9], [16, 0.4], [31, 0.2]],
    }

    def shown(history):
        fit = {"final_loss": 0.2, "n_params": 10, "loss_history": history}
        return practice.feedback(
            {}, fit, recipe=recipe, backend={"kind": "jax"}, worker={}
        )["fit"].get("loss_history")

    assert shown(good) == good
    too_many = {"points": [[i, 1.0] for i in range(training.HISTORY_POINTS + 1)]}
    for bad in (
        too_many,
        {"points": [[1, 1.0], [0, 1.0]]},
        {"points": [[0, 1.0], [0, 1.0]]},
        {"points": [[0, float("nan")]]},
        {"points": [[0, True]]},
        {"points": [[0.5, 1.0]]},
        {"points": "0,1"},
        "history",
        None,
    ):
        assert shown(bad) is None


def test_the_view_declares_the_curve_recorded():
    assert LEARNING_CURVE["recorded"] is True
    assert "TRAIN" in LEARNING_CURVE["basis"]
