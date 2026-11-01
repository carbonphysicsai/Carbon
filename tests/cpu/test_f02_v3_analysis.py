"""The nonlinearity defect metrics and the closed-form gate of Burst Thermal 3.0, on SYNTHETIC data.

Claims: the three defect metrics are computed from solved records exactly as defined (each in C and in multiples of U), the
decision rule needs the owner's threshold and U, and the two adversaries of the closed-form gate (structured superposition and
the client's ten runs) fit TRAIN scalars and predict a probe pool: the strong one recovers a system that IS structured
superposition and is NOT fooled into matching a strongly non-separable one; the stop rule needs the owner's margin. Every
number is a synthetic test value; nothing here is a score."""

from __future__ import annotations

import json
import math
import random

import numpy as np
import pytest

from scripts.dev.reference_packages.elmer import f02_closed_form_gate as gate
from scripts.dev.reference_packages.elmer import f02_nonlinearity_defects as nl

U = 0.012

# --- the defect metrics ------------------------------------------------------------------------------------------


def _record(point, variant, peak, **extra):
    return {"point": point, "variant": variant, "peak_c": peak, **extra}


def test_each_metric_is_computed_as_defined_in_c_and_in_multiples_of_u():
    records = [
        _record("a", "kT", 90.30),
        _record("a", "const", 90.00),
        _record("a", "p_low", 60.0, power_w=70.0),
        _record("a", "p_mid", 78.2, power_w=110.0),
        _record("a", "p_high", 100.0, power_w=150.0),
        _record("a", "base", 80.0),
        _record("a", "shift", 85.4, delta_c=5.0),
        _record("a", "split_0", 70.0),
        _record("a", "split_05", 71.0),
        _record("a", "split_1", 74.0),
    ]
    found = nl.defects(records, u=U)
    row = found["points"]["a"]
    assert row["property_effect"]["c"] == pytest.approx(0.30)
    assert row["property_effect"]["u_multiple"] == pytest.approx(0.30 / U)
    # the line through (70, 60) and (150, 100) at 110 W is 80.0; the mid peak is 78.2
    assert row["affine_in_power"]["c"] == pytest.approx(1.8)
    parts = row["superposition_parts"]
    assert parts["additivity"]["c"] == pytest.approx(0.4)  # 85.4 against 80 + 5
    assert parts["split"]["c"] == pytest.approx(
        1.0
    )  # 71 against the mean of 70 and 74 (72)
    assert row["superposition"]["c"] == pytest.approx(1.0)  # the largest part
    assert found["max"]["superposition"]["point"] == "a"


def test_the_two_pulse_part_sums_the_shifted_single_pulse_responses():
    start = 40.0
    single = [(0.0, 40.0), (20.0, 40.0), (30.0, 70.0), (60.0, 50.0), (120.0, 40.0)]
    shifted = [(t + 15.0, v) for t, v in single]
    # an exactly additive two-pulse series on the shifted axis, then a deviation of 0.7 C at the peak
    axis = sorted({t for t, _ in single} | {t for t, _ in shifted})

    def at(series, t):
        return nl._interp(series, t)

    two = [
        (t, start + (at(single, t) - start) + (at(shifted, t) - start)) for t in axis
    ]
    peak = max(v for _, v in two)
    record = _record(
        "p",
        "two_pulse",
        peak + 0.7,
        series=two,
        start_c=start,
        singles=[
            {"shift_s": 0.0, "series": single},
            {"shift_s": 15.0, "series": single},
        ],
    )
    found = nl.defects([record], u=U)["points"]["p"]
    assert found["superposition_parts"]["two_pulse"]["c"] == pytest.approx(
        0.7, abs=1e-9
    )


def test_a_point_with_no_variants_for_a_metric_leaves_it_out_and_bad_records_are_refused():
    found = nl.defects([_record("a", "kT", 1.0), _record("a", "const", 1.1)], u=U)
    assert set(found["points"]["a"]) == {"property_effect"} and set(found["max"]) == {
        "property_effect"
    }
    for bad in (
        [{"point": "a", "variant": "kT"}],
        [_record("a", "kT", float("nan"))],
        [_record("a", "kT", 1.0), _record("a", "kT", 2.0)],
        [
            _record("a", "p_low", 1.0, power_w=70.0),
            _record("a", "p_mid", 1.0, power_w=60.0),
            _record("a", "p_high", 1.0, power_w=150.0),
        ],
    ):
        with pytest.raises(nl.DefectInputRefused):
            nl.defects(bad, u=U)
    with pytest.raises(nl.DefectInputRefused, match="u_required"):
        nl.defects([_record("a", "kT", 1.0)], u=0.0)


def test_the_decision_rule_needs_the_owners_threshold_and_looks_at_ii_and_iii_only():
    weak = nl.defects(
        [
            _record("a", "kT", 95.0),
            _record(
                "a", "const", 90.0
            ),  # a big property effect alone does not make it strong
            _record("a", "base", 80.0),
            _record("a", "shift", 85.1, delta_c=5.0),
        ],
        u=U,
    )
    assert nl.too_weak(weak, threshold_c=0.5) is True
    assert nl.too_weak(weak, threshold_c=0.05) is False
    with pytest.raises(nl.DefectInputRefused, match="threshold_required"):
        nl.too_weak(weak, threshold_c=None)
    only_property = nl.defects(
        [_record("a", "kT", 1.0), _record("a", "const", 2.0)], u=U
    )
    assert nl.too_weak(only_property, threshold_c=0.5) is None


# --- the closed-form gate ----------------------------------------------------------------------------------------

RANGES = {
    "peak_w": (70, 150),
    "on_time_s": (4, 20),
    "left_source_fraction": (0.5, 0.9),
    "ramp_fraction": (0.0, 1.0),
    "coolant_c": (25, 45),
    "h_w_m2_k": (1500, 3500),
    "start_offset_c": (0, 20),
    "tim_thickness_mm": (0.1, 0.4),
}


def _rows(n, seed):
    rng = random.Random(seed)
    rows = []
    for _ in range(n):
        row = {name: rng.uniform(*span) for name, span in RANGES.items()}
        row["pulses"] = rng.choice([1, 2])
        row["gap_s"] = rng.uniform(5, 15) if row["pulses"] == 2 else None
        rows.append(row)
    return rows


MODES = 2
TRUE_THETA = np.array(
    # alpha (const, ln h, ln tim) for two modes, beta likewise, then the patch couplings and kappa
    [math.log(0.05), -0.4, 0.3, math.log(0.012), -0.2, 0.2]
    + [math.log(0.6), 0.5, -0.1, math.log(0.06), 0.3, -0.2]
    + [-0.3, 0.4]
    + [0.0004]
)


def _truth(rows):
    return gate.predict_peaks(TRUE_THETA, MODES, rows)


def test_a_structured_system_is_recovered_by_the_strong_adversary_and_not_by_the_client():
    train, probe = _rows(70, 1), _rows(40, 2)
    peaks = _truth(train)
    model = gate.fit_superposition(train, peaks, modes=MODES, seed=0, starts=2)
    assert model["train_rmse_c"] < 0.15
    truth = _truth(probe)
    strong = gate.accuracy(
        truth, gate.predict_superposition(model, probe), u=U, within_u=20
    )
    client = gate.accuracy(
        truth,
        gate.predict_client(gate.fit_client(train, peaks), probe),
        u=U,
        within_u=20,
    )
    assert strong["rmse_c"] < 0.5
    assert (
        client["rmse_c"] > 4 * strong["rmse_c"]
    )  # ten runs and a regression cannot match a structured fit
    assert strong["share_within"] > client["share_within"]


def test_a_strongly_non_separable_system_is_not_matched_by_the_structured_fit():
    train, probe = _rows(70, 3), _rows(40, 4)

    def hard(rows):
        base = gate.predict_peaks(TRUE_THETA, MODES, rows)
        h = np.array([r["h_w_m2_k"] for r in rows])
        p = np.array([r["peak_w"] for r in rows])
        d = np.array([r["on_time_s"] for r in rows])
        tim = np.array([r["tim_thickness_mm"] for r in rows])
        # an interaction no per-patch modal sum with log-linear rates can follow (h, power, on-time and TIM together)
        return base + 6.0 * np.sin(h / 400.0) * np.tanh((p - 110.0) / 15.0) * np.cos(
            d / 3.0
        ) * (tim / 0.2)

    model = gate.fit_superposition(train, hard(train), modes=MODES, seed=0, starts=2)
    miss = gate.accuracy(
        hard(probe), gate.predict_superposition(model, probe), u=U, within_u=20
    )
    easy = gate.fit_superposition(train, _truth(train), modes=MODES, seed=0, starts=2)
    hit = gate.accuracy(
        _truth(probe), gate.predict_superposition(easy, probe), u=U, within_u=20
    )
    assert miss["rmse_c"] > 5 * hit["rmse_c"]
    assert miss["share_within"] < 0.5


def test_the_waveform_goes_through_the_convolution_for_every_shape():
    row = _rows(1, 5)[0]
    one = {**row, "pulses": 1, "gap_s": None}
    two = {**row, "pulses": 2, "gap_s": 9.0}
    grid = np.arange(0.0, 120.0 + 0.05, gate.DT_S)
    assert gate.waveform_power(one, grid).max() == pytest.approx(row["peak_w"])
    assert (gate.waveform_power(two, grid) > 25.0).sum() < (
        gate.waveform_power({**two, "ramp_fraction": 0.0}, grid) > 25.0
    ).sum() + 5
    peaks = gate.predict_peaks(
        TRUE_THETA, MODES, [one, two, {**one, "ramp_fraction": 0.0}]
    )
    assert len(set(np.round(peaks, 6))) == 3  # the shapes give different peaks


def test_the_stop_rule_needs_the_owners_margin_and_names_the_adversaries_within_it():
    totals = {"structured_superposition": 0.93, "client_ten_runs": 0.55}
    assert gate.stop_rule(totals, 0.95, margin_n=0.03) == {
        "stop": True,
        "adversaries_within_margin": ["structured_superposition"],
        "margin_n": 0.03,
    }
    assert gate.stop_rule(totals, 0.95, margin_n=0.01)["stop"] is False
    for bad in (None, 0, -1, True):
        with pytest.raises(gate.GateRefused, match="margin_required"):
            gate.stop_rule(totals, 0.95, margin_n=bad)


def test_the_client_selection_is_ten_well_spread_deterministic_rows():
    rows = _rows(60, 6)
    first, second = gate.client_selection(rows), gate.client_selection(rows)
    assert first == second and len(set(first)) == 10


def test_inputs_must_be_complete_and_a_probe_needs_the_owners_criterion():
    row = _rows(1, 7)[0]
    broken = {k: v for k, v in row.items() if k != "h_w_m2_k"}
    with pytest.raises(gate.GateRefused, match="inputs_incomplete"):
        gate._row(broken)
    with pytest.raises(gate.GateRefused, match="criterion_required"):
        gate.accuracy([1.0], [1.0], u=0.012, within_u=0)
    with pytest.raises(gate.GateRefused, match="probe_shape"):
        gate.accuracy([1.0, 2.0], [1.0], u=0.012, within_u=5)


def test_the_command_fits_predicts_and_scores_without_any_default_criterion(
    tmp_path, capsys
):
    train, probe = _rows(40, 8), _rows(10, 9)
    peaks = _truth(train)
    train_file = tmp_path / "train.json"
    train_file.write_text(
        json.dumps(
            {
                "schema": gate.TRAIN_SCHEMA,
                "rows": [
                    {"inputs": r, "peak_top_c": float(p)}
                    for r, p in zip(train, peaks, strict=True)
                ],
            }
        )
    )
    model_file, rows_file, pred_file, truth_file = (
        tmp_path / n for n in ("m.json", "r.json", "p.json", "t.json")
    )
    assert (
        gate.main(
            [
                "fit",
                "--train",
                str(train_file),
                "--out",
                str(model_file),
                "--modes",
                "2",
            ]
        )
        == 0
    )
    rows_file.write_text(json.dumps({"rows": probe}))
    assert (
        gate.main(
            [
                "predict",
                "--model",
                str(model_file),
                "--rows",
                str(rows_file),
                "--out",
                str(pred_file),
            ]
        )
        == 0
    )
    truth_file.write_text(json.dumps([float(v) for v in _truth(probe)]))
    capsys.readouterr()
    assert (
        gate.main(
            [
                "score",
                "--truth",
                str(truth_file),
                "--predictions",
                str(pred_file),
                "--u",
                "0.012",
                "--within-u",
                "20",
            ]
        )
        == 0
    )
    scored = json.loads(capsys.readouterr().out)
    assert set(scored) == {"structured_superposition", "client_ten_runs"}
    with pytest.raises(SystemExit):
        gate.main(
            [
                "score",
                "--truth",
                str(truth_file),
                "--predictions",
                str(pred_file),
                "--u",
                "0.012",
            ]
        )
