"""The F08 2.0 closed-form gate: the structured adversary recovers a SYNTHETIC notch law, the client's fit is weaker, the
stop rule needs an owner margin. The 'peaks' here come from a made-up formula, never from physics or a solve."""

from __future__ import annotations

import math
import random
import sys
from pathlib import Path

import pytest

CALCULIX = (
    Path(__file__).resolve().parents[2] / "scripts/dev/reference_packages/calculix"
)
sys.path.insert(0, str(CALCULIX))

import f08_closed_form_gate as gate


def row(rng):
    t = rng.uniform(4.0, 8.0)
    tr = rng.uniform(3.0, 6.0)
    return {
        "length_mm": rng.uniform(150.0, 260.0),
        "width_mm": rng.uniform(40.0, 80.0),
        "thickness_mm": t,
        "rib_height_mm": rng.uniform(8.0, 20.0),
        "rib_thickness_mm": tr,
        "relief_length_mm": rng.uniform(0.0, 60.0),
        "fillet_radius_mm": rng.uniform(0.5, 0.45 * min(t, tr)),
        "load_angle_deg": rng.uniform(-20.0, 20.0),
        "load_offset_mm": rng.uniform(-5.0, 5.0),
    }


def synthetic_peak(r):
    """A made-up law of the structured form (nominal stress times a power-law notch factor): SYNTHETIC."""
    kt = (
        1.9
        * (r["fillet_radius_mm"] / r["thickness_mm"]) ** -0.35
        * (r["rib_height_mm"] / r["rib_thickness_mm"]) ** 0.1
    )
    return gate.nominal_stress(r) * kt


def make(count, seed):
    rng = random.Random(seed)
    rows = [row(rng) for _ in range(count)]
    return [{**r, "peak_von_mises_mpa": synthetic_peak(r)} for r in rows]


TRAIN = {"schema": gate.TRAIN_SCHEMA, "rows": make(120, 1)}


def test_the_section_properties_match_a_plain_plate_when_the_ribs_vanish_in_the_limit():
    plate = {
        "width_mm": 20.0,
        "thickness_mm": 5.0,
        "rib_height_mm": 1e-9,
        "rib_thickness_mm": 1e-9,
    }
    s = gate.section(plate)
    assert s["iy"] == pytest.approx(20.0 * 5.0**3 / 12, rel=1e-6)
    assert s["iz"] == pytest.approx(5.0 * 20.0**3 / 12, rel=1e-6)
    assert s["zbar"] == pytest.approx(2.5, rel=1e-6)


def test_the_nominal_stress_falls_with_a_deeper_section_and_rises_with_the_lateral_load():
    base = {**TRAIN["rows"][0], "load_angle_deg": 0.0}
    deeper = {**base, "thickness_mm": base["thickness_mm"] * 1.5}
    assert gate.nominal_stress(deeper) < gate.nominal_stress(base)
    tilted = {**base, "load_angle_deg": 20.0}
    assert gate.nominal_stress(tilted) != gate.nominal_stress(base)


def test_the_structured_adversary_recovers_a_synthetic_notch_law_far_better_than_the_client_fit():
    model = gate.fit(TRAIN)
    probe = make(40, 2)
    out = gate.predict(model, probe)
    truth = [r["peak_von_mises_mpa"] for r in probe]

    def worst(pred):
        return max(abs(p - t) / t for p, t in zip(pred, truth))

    assert worst(out["structured"]) < 1e-3  # the law is of its form
    assert worst(out["client"]) > 5 * worst(out["structured"])


def test_a_model_records_its_fitted_parameters_and_the_train_digest_and_is_deterministic():
    one, two = gate.fit(TRAIN), gate.fit(TRAIN)
    assert one == two and gate.digest(one) == gate.digest(two)
    assert (
        one["train_sha256"].startswith("sha256:") and len(one["client"]["rows"]) == 10
    )
    assert len(one["structured"]["coefficients"]) == 5
    other = gate.fit({**TRAIN, "rows": make(120, 3)})
    assert other["train_sha256"] != one["train_sha256"]


@pytest.mark.parametrize(
    "mutate, code",
    [
        (lambda t: {**t, "schema": "x"}, "train_schema"),
        (lambda t: {**t, "rows": []}, "no_rows"),
        (
            lambda t: {**t, "rows": [{**t["rows"][0], "peak_von_mises_mpa": 0.0}]},
            "peak_not_positive",
        ),
        (
            lambda t: {**t, "rows": [{**t["rows"][0], "fillet_radius_mm": math.nan}]},
            "row_input_not_finite",
        ),
    ],
)
def test_a_bad_train_document_is_refused(mutate, code):
    with pytest.raises(gate.GateRefused) as refused:
        gate.fit(mutate(TRAIN))
    assert refused.value.code == code


def test_the_stop_rule_needs_the_owners_margin():
    with pytest.raises(gate.GateRefused) as refused:
        gate.stop_rule(0.8, 0.9, "HUMAN_INPUT")
    assert refused.value.code == "margin_not_registered"
    assert gate.stop_rule(0.89, 0.90, 0.02)["stop"] is True
    assert gate.stop_rule(0.70, 0.90, 0.02)["stop"] is False
