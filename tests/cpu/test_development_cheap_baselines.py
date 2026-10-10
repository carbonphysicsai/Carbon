"""No solver fixtures: held-out custody, supported interpolation and reporting."""

from __future__ import annotations

import copy
import hashlib
import json

import numpy as np
import pytest

from carbon.design_search import indexed, tasks
from carbon.development_comparison import cheap_baselines as cb


def row(c1, c2, value, *, band=25, cooling=1):
    return {
        "band": band,
        "c1": c1,
        "c2": c2,
        "switch_v": 4,
        "cooling": cooling,
        "values": {"temperature": value, "minutes": 20 - value},
    }


def test_battery_requires_all_corners_and_partitions_discrete_actions():
    rows = [row(a, b, a + b) for a in (1, 2) for b in (0.25, 0.5)]
    model = cb.ConservativeMap(rows)
    e = model.predict(band=25, c1=1.5, c2=0.375, switch_v=4, cooling=1)
    assert e.point["temperature"] == pytest.approx(1.875)
    assert e.lower["temperature"] == 1.25 and e.upper["temperature"] == 2.5
    for kwargs in ({"cooling": 2}, {"switch_v": 4.1}, {"band": 5}, {"c1": 3}):
        args = {
            "band": 25,
            "c1": 1.5,
            "c2": 0.375,
            "switch_v": 4,
            "cooling": 1,
        } | kwargs
        with pytest.raises(cb.Unsupported):
            model.predict(**args)
    with pytest.raises(cb.Unsupported):
        cb.ConservativeMap(rows[:-1]).predict(
            band=25, c1=1.5, c2=0.375, switch_v=4, cooling=1
        )


def test_band_bracketing_never_extrapolates_and_identical_row_is_exact():
    model = cb.ConservativeMap([row(1, 0.5, 10, band=15), row(1, 0.5, 30, band=35)])
    e = model.predict(band=25, c1=1, c2=0.5, switch_v=4, cooling=1)
    assert e.point["temperature"] == 20
    assert e.lower["temperature"] == 10 and e.upper["temperature"] == 30
    e = model.predict(band=15, c1=1, c2=0.5, switch_v=4, cooling=1)
    assert e.point == e.lower == e.upper
    with pytest.raises(cb.Unsupported):
        model.predict(band=40, c1=1, c2=0.5, switch_v=4, cooling=1)


def test_nonfinite_and_conflicting_inputs_are_refused():
    with pytest.raises(ValueError):
        cb.ConservativeMap([row(1, 0.5, float("nan"))])
    with pytest.raises(ValueError):
        cb.ConservativeMap([row(1, 0.5, 1), row(1, 0.5, 2)])


def test_safety_band_is_not_interpolation_slack():
    task = {
        "limits": [{"quantity": "temperature", "op": "<=", "value": 45, "band": 0.5}],
        "objective": {"quantity": "minutes", "sense": "min"},
    }
    envelope = cb.Envelope(
        {"temperature": 40, "minutes": 20},
        {"temperature": 39, "minutes": 19},
        {"temperature": 45, "minutes": 21},
    )
    with pytest.raises(cb.Unsupported):
        cb.conservative_values(task, envelope)
    e = cb.Envelope(envelope.point, envelope.lower, {"temperature": 44, "minutes": 21})
    assert cb.conservative_values(task, e) == {"temperature": 44, "minutes": 21}


@pytest.mark.parametrize("kernel", ["gaussian", "multiquadric"])
def test_full_signed_curves_use_fitted_geometry_not_identifiers(kernel):
    x = [[0], [1], [2]]
    curves = [[-2, 0, 2], [-1, 1, 3], [0, 2, 4]]
    model = cb.CurveSurface(x, curves, kernel=kernel)
    pred = model.predict([[1]])
    assert pred.shape == (1, 3) and np.max(np.abs(pred[0] - curves[1])) < 1e-6
    with pytest.raises(cb.Unsupported):
        model.predict([[3]])
    with pytest.raises(ValueError):
        cb.CurveSurface([[0], [0]], [[1, 2], [2, 3]])
    with pytest.raises(ValueError):
        cb.CurveSurface(x, [[1, 2]])


def test_curve_reductions_do_not_divide_zero_current_cogging_by_mean():
    values = cb.curve_observables([5, 6, 7], [-0.02, 0, 0.02])
    assert values == {
        "mean_nm": 6,
        "pk_pk_nm": 2,
        "ripple_fraction": 1 / 3,
        "cogging_nm": 0.04,
    }
    with pytest.raises(cb.Unsupported):
        cb.curve_observables([-1, 1], [0, 0])


def test_whole_protocol_removed_in_every_band(monkeypatch):
    physical = []
    for b in (15, 25, 35):
        for c1 in (1.0, 1.5, 2.0):
            for c2 in (0.25, 0.375, 0.5):
                physical.append(
                    {
                        "band": b,
                        "candidate": f"{c1}-{c2}",
                        "condition": str(b),
                        "action": {"c1": c1, "c2": c2, "switch_v": 4, "cooling": 1},
                        "values": {"temperature": b + c1 + c2},
                    }
                )
    monkeypatch.setattr(cb, "_physical_rows", lambda _: physical)
    pred, _, cost = cb.battery_predictions({"family": "battery-v3"}, holdout="protocol")
    # Interior rows and supported edge lines interpolate; corners cannot.
    assert len(pred) == 15 and cost["folds"] == 9
    for b in (15, 25, 35):
        assert pred[(b, "1.5-0.375", str(b))]["temperature"] == pytest.approx(b + 1.875)
    pred, _, cost = cb.battery_predictions({"family": "battery-v3"}, holdout="band")
    assert len(pred) == 9 and {key[0] for key in pred} == {25}
    assert cost["folds"] == 3


def test_empty_and_unresolved_comparisons_are_not_agreement():
    assert cb._agreement([])["exact_pick_agreement_rate"] is None
    unknown = {
        "kind": "ABSTENTION_UNRESOLVED",
        "reference_resolved": False,
        "selected": None,
        "best": None,
        "regret": None,
    }
    assert cb._agreement([unknown])["resolved"] == 0
    none = {**unknown, "kind": "CORRECT_ABSTENTION", "reference_resolved": True}
    assert cb._agreement([none])["exact_pick_agreement_rate"] == 1


def test_physical_duplicates_cannot_change_truth_between_questions():
    task = {"schema": tasks.RUNNABLE_SCHEMA, "actions": {"a": {"c1": 1}}}
    entry = {
        "task": task,
        "reference": [{"candidate": "a", "condition": "x", "values": {"t": 1}}],
    }
    export = {"questions": [entry, copy.deepcopy(entry)]}
    assert len(cb._physical_rows(export)) == 1
    export["questions"][1]["reference"][0]["values"]["t"] = 2
    with pytest.raises(ValueError):
        cb._physical_rows(export)


def toy_decision():
    task = tasks.task(
        "development-comparator-toy",
        identity={
            "challenge": "toy",
            "contract_version": "v1",
            "action_grammar": {
                "schema": tasks.GRAMMAR_SCHEMA,
                "version": "toy.v1",
                "variables": [
                    {"name": "choice", "type": "integer", "min": 0, "max": 1, "step": 1}
                ],
                "rules": [],
            },
            "optimizer": {"class": "exhaustive", "version": "v1"},
            "query_budget": 2,
            "seed": 17,
            "observer_version": "toy.v1",
            "reference_bank": "toy.v1",
        },
        conditions=[{"id": "x", "stratum": "s"}],
        strata={"s": {"p": 1, "q": 1, "w": 1}},
        candidates=["a", "b"],
        actions={"a": {"choice": 0}, "b": {"choice": 1}},
        objective={
            "quantity": "minutes",
            "unit": "min",
            "sense": "min",
            "aggregate": "worst",
        },
        limits=[
            {"quantity": "margin", "unit": "toy", "op": ">=", "value": 0, "band": 0.1}
        ],
    )
    panel = [
        {"candidate": "a", "condition": "x", "values": {"margin": 1, "minutes": 2}},
        {"candidate": "b", "condition": "x", "values": {"margin": -1, "minutes": 1}},
    ]
    return task, panel


def test_indexed_exact_lookup_and_missing_band_denominators():
    task, panel = toy_decision()
    registered = indexed.indexed_task(
        "toy-map",
        index_axis="temperature",
        indices=[
            {"index_value": b, "buyer_weight": 0.5, "task": task} for b in (5, 15)
        ],
        query_budget=4,
        value_equivalence={
            "quantity": "minutes",
            "unit": "min",
            "tolerance": 0,
            "rule": indexed.EQUIVALENCE_RULE,
        },
    )
    export = {
        "questions": [
            {
                "case": "toy",
                "task": registered,
                "reference": [{"index_value": b, "panel": panel} for b in (5, 15)],
            }
        ]
    }
    predictions = {
        (b, r["candidate"], "x"): r["values"] for b in (5, 15) for r in panel
    }
    report = cb.decision_report(export, predictions)
    assert report["summary"]["exact_pick_agreement_rate"] == 1
    assert set(report["per_band"]) == {"5", "15"}
    assert report["decisions"][0]["feasibility"][0]["agreement_rate"] == 1
    assert report["summary"]["abstentions"] == 0
    held = {k: v for k, v in predictions.items() if k[0] == 5}
    report = cb.decision_report(export, held)
    assert report["summary"]["abstentions"] == 1
    assert report["per_band"]["15"]["missed_opportunities"] == 1
    assert report["decisions"][0]["feasibility"][1]["prediction_unavailable"] == 2


def test_false_feasible_and_reference_unresolved_reported_separately():
    task, panel = toy_decision()
    pred = {
        (None, "a", "x"): {"margin": 1, "minutes": 2},
        (None, "b", "x"): {"margin": 1, "minutes": 1},
    }
    report = cb.feasibility_report(task, panel, pred, band=None)
    assert report["false_feasible"] == 1 and report["agreement_rate"] == 0.5
    panel[1]["values"]["margin"] = 0.05
    report = cb.feasibility_report(task, panel, pred, band=None)
    assert report["reference_unresolved"] == 1 and report["compared"] == 1
    assert report["agreement_rate"] == 1 and report["false_feasible"] == 0


def test_motor_whole_geometry_curves_and_binding(monkeypatch):
    curve_rows, physical = [], []
    for g in range(3):
        for skew in (0, 2):
            candidate = f"g{g}-s{skew}"
            coordinates = dict.fromkeys(cb.MOTOR_FEATURES, 1.0)
            coordinates.update(magnet_mm=float(g), skew_deg=skew)
            loaded, cog = [5 + g, 6 + g, 7 + g], [-0.02, 0, 0.02]
            curve_rows.append(
                {
                    "candidate": candidate,
                    "geometry_id": str(g),
                    "coordinates": coordinates,
                    "loaded_nm": loaded,
                    "cogging_nm": cog,
                }
            )
            physical.append(
                {
                    "candidate": candidate,
                    "condition": "x",
                    "values": cb.curve_observables(loaded, cog),
                }
            )
    monkeypatch.setattr(cb, "_physical_rows", lambda _: physical)
    export = {
        "family": "motor",
        "export_digest": "toy",
        "questions": [{"task": {"identity": {"observer_version": "toy"}}}],
    }
    sidecar = {
        "export_digest": "toy",
        "sampling": "one-period-without-repeated-endpoint",
        "source_hashes": ["toy"],
        "observer_version": "toy",
        "angle_deg": [0, 4, 8],
        "rows": curve_rows,
    }
    pred, cost = cb.motor_predictions(export, sidecar, kernel="gaussian")
    assert cost["folds"] == 3 and cost["held_out_unit"] == "whole_geometry_all_skews"
    assert {k[1] for k in pred} == {"g1-s0", "g1-s2"}
    broken = copy.deepcopy(sidecar)
    broken["export_digest"] = "other"
    with pytest.raises(ValueError, match="bind"):
        cb.motor_predictions(export, broken, kernel="gaussian")
    broken = copy.deepcopy(sidecar)
    broken["rows"][0]["loaded_nm"][0] += 1
    with pytest.raises(ValueError, match="reductions"):
        cb.motor_predictions(export, broken, kernel="gaussian")
    broken = copy.deepcopy(sidecar)
    broken["observer_version"] = "different"
    with pytest.raises(ValueError, match="observer"):
        cb.motor_predictions(export, broken, kernel="gaussian")


def test_cli_identity_and_exclusive_output(tmp_path, monkeypatch):
    panel, output = tmp_path / "panel.json", tmp_path / "report.json"
    raw = b'{"family":"motor"}'
    panel.write_bytes(raw)
    monkeypatch.setattr(cb, "measure", lambda *a, **k: {"family": "motor"})
    args = [
        "--panel",
        str(panel),
        "--expected-sha256",
        hashlib.sha256(raw).hexdigest(),
        "--output",
        str(output),
    ]
    assert cb.main(args) == 0
    saved = output.read_bytes()
    assert b"\r" not in saved
    assert json.loads(saved)["environment"]["canonical"] is False
    with pytest.raises(FileExistsError):
        cb.main(args)
    assert output.read_bytes() == saved
    args[3] = "0" * 64
    with pytest.raises(ValueError, match="byte identity"):
        cb.main(args)
