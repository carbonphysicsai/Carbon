import gzip
import json
import subprocess
from pathlib import Path

import numpy as np
import pytest

from carbon.battery.recipes import Layout
from carbon.development_comparison.monotone_capacity import layout_type


def _data(capacity):
    data = type("Data", (), {})()
    data.v = np.array([[3.7, 3.8, 3.9]])
    data.q = np.asarray([capacity], dtype=float)
    data.t = np.array([[25.0, 26.0, 27.0]])
    data.x = np.array([[1.0, 0.5, 25.0, 0.7]])
    data.eta = np.array([0.2])
    return data


def test_monotone_layout_round_trips_capacity_targets_and_never_rises():
    candidate_type = layout_type(Layout)
    candidate = candidate_type(3, 3, bounded_v=False, predict_v0=False, fade=True)
    data = _data([2.0, 1.8, 1.5])

    target = candidate.targets(data)
    decoded = candidate.split(target)
    np.testing.assert_allclose(decoded[3], data.q, rtol=0.0, atol=1e-14)
    assert np.all(np.diff(decoded[3], axis=1) <= 0.0)

    arbitrary_logits = target.copy()
    arbitrary_logits[:, candidate.nv + candidate.nt + 2 :] = [[-3.0, 2.0]]
    predicted_capacity = candidate.split(arbitrary_logits)[3]
    assert np.all(np.diff(predicted_capacity, axis=1) < 0.0)


def test_monotone_layout_refuses_nonpositive_observed_fade():
    candidate = layout_type(Layout)(3, 3, bounded_v=False, predict_v0=False, fade=True)

    with pytest.raises(ValueError, match="requires_positive_observed_fade"):
        candidate.targets(_data([2.0, 2.0, 1.5]))


def test_candidate_builder_rejects_unsupported_construction():
    from carbon.development_comparison.monotone_capacity import (
        MonotoneCapacityCandidate,
    )

    model = type(
        "Model", (), {"family": "mlp", "settings": {"capacity_fade_head": False}}
    )()
    with pytest.raises(ValueError, match="requires_capacity_fade_head"):
        MonotoneCapacityCandidate(model)


def test_layout_binding_is_restored_after_failed_fit():
    from carbon.battery import recipes
    from carbon.development_comparison.monotone_capacity import (
        MonotoneCapacityCandidate,
    )

    original = recipes.Layout

    def fail(self):
        raise RuntimeError("stop")

    model = type(
        "Model",
        (),
        {"family": "mlp", "settings": {"capacity_fade_head": True}, "fit": fail},
    )()
    with pytest.raises(RuntimeError, match="stop"):
        MonotoneCapacityCandidate(model).fit()
    assert recipes.Layout is original


def test_public_prediction_precheck_counts_strict_rises():
    from carbon.development_comparison.monotone_capacity import count_capacity_increases

    result = count_capacity_increases(
        {
            "case-a": {"capacity_ah": [2.0, 1.8, 1.7]},
            "case-b": {"capacity_ah": [2.0, 2.1, 1.9]},
        }
    )
    assert result == {
        "cases": 2,
        "adjacent_transitions": 4,
        "increasing_cases": 1,
        "increasing_transitions": 1,
        "disposition": "INCREASES_OBSERVED",
    }


@pytest.mark.parametrize(
    ("capacity", "disposition"),
    [
        ([2.0, 1.8, 1.7], "STOP_NO_MEASURABLE_HELP"),
        ([2.0, 2.1, 1.9], "INCREASES_OBSERVED"),
    ],
)
def test_public_prediction_precheck_output_has_required_caveat(
    tmp_path, capsys, capacity, disposition
):
    from carbon.development_comparison.monotone_capacity import (
        HUNT_RECOVERY_CAVEAT,
        main,
    )

    path = tmp_path / "public-predictions.json.gz"
    with gzip.open(path, "wt", encoding="utf-8") as stream:
        json.dump({"case-a": {"capacity_ah": capacity}}, stream)
    assert main(["--count-increases", str(path)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["disposition"] == disposition
    assert result["maturity"] == "DEVELOPMENT"
    assert result["benefit_measured"] is False
    assert result["hunt_recovery_caveat"] == HUNT_RECOVERY_CAVEAT
    assert "partly-broken hunt" in result["hunt_recovery_caveat"]
    assert "not a measurement of Level 5" in result["hunt_recovery_caveat"]


def _model_with_fixed_weights(*, candidate):
    """Synthetic inference state using real recipe serialization; never trains."""
    from carbon.battery import recipes

    settings = {
        "width": 4,
        "steps": 1,
        "depth": 1,
        "learning_rate": 0.001,
        "weight_decay": 0.0,
        "arrhenius_features": False,
        "bounded_voltage_head": False,
        "ocv_initial_voltage": False,
        "capacity_fade_head": True,
        "important_region_weight": 1.0,
        "train_fraction": 1.0,
        "ensemble_members": 1,
    }
    model = recipes.MLP("mlp", settings)
    layout = layout_type(Layout) if candidate else Layout
    model.layout = layout(3, 3, bounded_v=False, predict_v0=True, fade=True)
    capacity = [2.0, 1.8, 1.5] if candidate else [2.0, 2.1, 1.8]
    target = model.layout.targets(_data(capacity))[0]
    model.s = recipes.Structure([0.0, 1.0], [3.0, 4.0])
    model.mu, model.sd = np.zeros_like(target), np.ones_like(target)
    model.classic, model.x64 = True, False
    model.params = [(np.zeros((4, target.size)), target.copy())]
    model._net = recipes._classic_net
    return model


@pytest.mark.parametrize("ensemble", [False, True])
def test_fitted_baseline_cannot_be_labelled_as_candidate(ensemble):
    from carbon.battery import recipes
    from carbon.development_comparison.monotone_capacity import (
        MonotoneCapacityCandidate,
    )

    baseline = _model_with_fixed_weights(candidate=False)
    assert np.any(np.diff(baseline.predict(_data([]).x)["q"], axis=1) > 0.0)
    model = baseline
    if ensemble:
        model = recipes.Ensemble(2, "mlp", baseline.settings)
        model.members = [_model_with_fixed_weights(candidate=True), baseline]
    with pytest.raises(ValueError, match="candidate_layout_required"):
        MonotoneCapacityCandidate(model)


@pytest.mark.parametrize("ensemble", [False, True])
def test_candidate_fixed_state_export_import_preserves_predictions(ensemble):
    from carbon.battery import recipes
    from carbon.development_comparison.monotone_capacity import (
        MonotoneCapacityCandidate,
        import_state,
    )

    model = _model_with_fixed_weights(candidate=True)
    if ensemble:
        member = model
        model = recipes.Ensemble(2, "mlp", member.settings)
        model.members = [member, _model_with_fixed_weights(candidate=True)]
    wrapped = MonotoneCapacityCandidate(model)
    x = _data([]).x
    expected = wrapped.predict(x)
    assert np.all(np.diff(expected["q"], axis=1) <= 0.0)
    header, arrays = wrapped.export_state()
    assert header["construction_variant"] == "battery-monotone-capacity-fade-v1"
    restored = import_state(header, arrays)
    actual = restored.predict(x)
    for key in expected:
        np.testing.assert_array_equal(actual[key], expected[key])
    restored_header, restored_arrays = restored.export_state()
    assert restored_header == header
    for key in arrays:
        np.testing.assert_array_equal(restored_arrays[key], arrays[key])
    assert recipes.Layout is Layout


def test_unregistered_candidate_is_outside_registered_graphite_ship():
    from carbon.agent_campaign.graphite import pods
    from carbon.challenge_validator import scoring
    from carbon.development_comparison import monotone_capacity
    from carbon.reconstruction.capability_registry import BATTERY_CHALLENGE

    repository = Path(__file__).resolve().parents[2]
    ref = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    shipped = pods.ship_list(ref, repository, scoring.scoring_for(BATTERY_CHALLENGE))
    candidate_path = Path(monotone_capacity.__file__).resolve().relative_to(repository)
    assert candidate_path.as_posix() not in shipped
    assert "carbon/battery/recipes.py" in shipped


@pytest.mark.parametrize("ensemble", [False, True])
def test_candidate_rechecks_layout_before_prediction_and_export(ensemble):
    from carbon.battery import recipes
    from carbon.development_comparison.monotone_capacity import (
        MonotoneCapacityCandidate,
    )

    model = _model_with_fixed_weights(candidate=True)
    member = model
    if ensemble:
        model = recipes.Ensemble(2, "mlp", member.settings)
        model.members = [_model_with_fixed_weights(candidate=True), member]
    wrapped = MonotoneCapacityCandidate(model)
    member.layout = Layout(3, 3, bounded_v=False, predict_v0=True, fade=True)
    with pytest.raises(ValueError, match="candidate_layout_required"):
        wrapped.predict(_data([]).x)
    with pytest.raises(ValueError, match="candidate_layout_required"):
        wrapped.export_state()


def test_fresh_candidate_must_fit_before_export_and_fit_uses_sidecar(monkeypatch):
    from carbon.battery import recipes
    from carbon.development_comparison.monotone_capacity import (
        MonotoneCapacityCandidate,
    )

    model = recipes.build("mlp", _model_with_fixed_weights(candidate=True).settings)
    wrapped = MonotoneCapacityCandidate(model)
    with pytest.raises(ValueError, match="candidate_layout_required"):
        wrapped.export_state()

    def fit():
        model.layout = recipes.Layout(3, 3, bounded_v=False, predict_v0=True, fade=True)
        return "fixture-fit"

    monkeypatch.setattr(model, "fit", fit)
    assert wrapped.fit() == "fixture-fit"
    assert type(model.layout) is not Layout
    np.testing.assert_allclose(
        model.layout.split(model.layout.targets(_data([2, 1.8, 1.5])))[3],
        [[2, 1.8, 1.5]],
    )
    assert recipes.Layout is Layout
