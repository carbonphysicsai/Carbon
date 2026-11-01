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


def dyn_row(rng):
    r = row(rng)
    return {
        **r,
        "damping_ratio": rng.uniform(0.005, 0.02),
        "E_mpa": rng.choice([70000.0, 200000.0, 110000.0]),
        "rho_t_per_mm3": rng.choice([2.7e-9, 7.85e-9, 4.43e-9]),
    }


def synthetic_dynamic(r):
    """A made-up law of the modal-superposition form (SYNTHETIC)."""
    coef = [0.2, 1.0, -0.35, 0.05, 0.1, 0.9, 0.6]
    return math.exp(sum(c * f for c, f in zip(coef, gate.dynamic_features(r))))


def make_dynamic(count, seed):
    rng = random.Random(seed)
    rows = [dyn_row(rng) for _ in range(count)]
    return [{**r, "dynamic_von_mises_mpa_per_n": synthetic_dynamic(r)} for r in rows]


def test_the_band_amplification_is_the_resonance_peak_inside_and_flat_far_above_the_band():
    zeta = 0.01
    assert gate.band_amplification(300.0, zeta) == pytest.approx(
        1.0 / (2 * zeta * math.sqrt(1 - zeta**2))
    )
    assert gate.band_amplification(50000.0, zeta) == pytest.approx(1.0, rel=1e-3)
    below = gate.band_amplification(20.0, zeta)  # the band lies above the mode: r > 1
    assert below < 0.1


def test_the_first_mode_scales_with_the_alloy_and_the_section():
    base = dyn_row(random.Random(5))
    stiffer = {**base, "E_mpa": base["E_mpa"] * 4.0}
    assert gate.first_mode_hz(stiffer) == pytest.approx(2.0 * gate.first_mode_hz(base))
    heavier = {**base, "rho_t_per_mm3": base["rho_t_per_mm3"] * 4.0}
    assert gate.first_mode_hz(heavier) == pytest.approx(0.5 * gate.first_mode_hz(base))


def test_the_modal_superposition_adversary_recovers_a_synthetic_dynamic_law_and_is_deterministic():
    train = {"schema": gate.TRAIN_SCHEMA, "rows": make_dynamic(150, 7)}
    model = gate.fit_dynamic(train)
    assert model == gate.fit_dynamic(train) and model["train_sha256"].startswith(
        "sha256:"
    )
    assert len(model["structured"]["coefficients"]) == 7 and model["band_hz"] == [
        80.0,
        600.0,
    ]
    probe = make_dynamic(40, 8)
    predicted = gate.predict_dynamic(model, probe)
    truth = [r["dynamic_von_mises_mpa_per_n"] for r in probe]
    assert max(abs(p - t) / t for p, t in zip(predicted, truth)) < 1e-4


@pytest.mark.parametrize(
    "mutate, code",
    [
        (lambda t: {**t, "schema": "x"}, "train_schema"),
        (lambda t: {**t, "rows": []}, "no_rows"),
        (
            lambda t: {
                **t,
                "rows": [{**t["rows"][0], "dynamic_von_mises_mpa_per_n": 0.0}],
            },
            "peak_not_positive",
        ),
        (
            lambda t: {**t, "rows": [{**t["rows"][0], "E_mpa": math.nan}]},
            "row_input_not_finite",
        ),
    ],
)
def test_a_bad_dynamic_train_document_is_refused(mutate, code):
    train = {"schema": gate.TRAIN_SCHEMA, "rows": make_dynamic(5, 9)}
    with pytest.raises(gate.GateRefused) as refused:
        gate.fit_dynamic(mutate(train))
    assert refused.value.code == code
