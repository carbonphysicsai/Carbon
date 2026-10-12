"""PHYSICS-CONTRACT-01: the Challenge-neutral law checker and battery's contract.

Laws are hard gates when adopted, never score terms. Nothing here is live:
every tolerance's quantile and margin is HUMAN_INPUT in the contract.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from carbon.challenge_validator import physics_contract as pc

ROOT = Path(__file__).resolve().parents[2]
BATTERY = ROOT / "carbon/battery/physics_contract.v1.json"


def test_battery_contract_loads_and_leaves_every_tolerance_to_the_owner():
    contract = pc.load(BATTERY)
    assert contract["challenge"] == "battery-fastcharge-ageing-development-v1"
    assert {law["id"] for law in contract["laws"]} == {
        "B1",
        "B2",
        "B3",
        "B4",
        "B5a",
        "B5b",
        "B6",
        "B7",
        "B8",
        "B9",
        "B10",
    }
    tolerance = contract["tolerance"]
    assert tolerance["quantile"] == tolerance["margin"] == pc.HUMAN_INPUT
    assert tolerance["gate_max_violation_rate"] == pc.HUMAN_INPUT
    # The probe region is battery's own input box.
    from carbon.battery.domain import INPUT_BOUNDS

    assert {k: tuple(v) for k, v in contract["probe_region"].items()} == INPUT_BOUNDS


@pytest.mark.parametrize(
    "change, code",
    [
        ({"schema": "other"}, "physics_contract_schema"),
        ({"probe_region": {"x": [1, 0]}}, "physics_contract_region:x"),
        ({"laws": [{"id": "L", "type": "magic"}]}, "physics_contract_law_type"),
    ],
)
def test_a_malformed_contract_is_refused(change, code):
    contract = {**pc.load(BATTERY), **change}
    with pytest.raises(pc.ContractRefused, match=code):
        pc.validate(contract)


def _law(contract, lid):
    return next(law for law in contract["laws"] if law["id"] == lid)


def test_single_point_residuals_are_zero_when_the_law_holds_and_sized_when_not():
    contract = pc.load(BATTERY)
    inputs = {"c1": 1.0, "c2": 0.5, "t_amb_c": 25.0, "soc0": 0.2}
    good = {
        "voltage_v": [3.6, 3.9, 4.2],
        "temperature_c": [25.0, 27.0, 30.0],
        "plating_margin_v": 0.01,
        "capacity_ah": [5.0, 4.9, 4.8, 4.7],
    }
    aux = {"ocv": lambda soc: 3.6}
    for lid in ("B1", "B2", "B3", "B4", "B9"):
        assert pc.single_residual(_law(contract, lid), inputs, good, aux) == 0.0
    bad = {
        **good,
        "voltage_v": [3.5, 4.3],
        "temperature_c": [26.0, 23.5],
        "capacity_ah": [5.0, 5.1, 4.8, 4.9],
    }
    assert pc.single_residual(_law(contract, "B1"), inputs, bad, aux) == pytest.approx(
        0.1
    )
    assert pc.single_residual(_law(contract, "B2"), inputs, bad, aux) == pytest.approx(
        1.0
    )
    assert pc.single_residual(_law(contract, "B3"), inputs, bad, aux) == pytest.approx(
        0.1
    )
    assert pc.single_residual(_law(contract, "B4"), inputs, bad, aux) == pytest.approx(
        0.1
    )
    assert pc.single_residual(_law(contract, "B9"), inputs, bad, aux) == pytest.approx(
        1.5
    )
    # A missing output is UNRESOLVED (None), never a pass or a fail.
    assert pc.single_residual(_law(contract, "B4"), inputs, {}, aux) is None


def _toy_battery(points, *, wrong=False):
    """A toy model: peak T and the T curve rise with c1, c2 and ambient, and
    the plating margin falls with c1 and rises with ambient; `wrong` flips
    the c1 dependence."""
    out = []
    for p in points:
        sign = -1.0 if wrong else 1.0
        # Always above ambient, so the curve's maximum is the peak.
        peak = p["t_amb_c"] + 25 + sign * 10 * p["c1"] + 3 * p["c2"]
        out.append(
            {
                "voltage_v": [3.7] + [4.0] * 120,
                "temperature_c": [p["t_amb_c"]] + [peak] * 120,
                "plating_margin_v": 0.05 - sign * 0.02 * p["c1"] + 0.001 * p["t_amb_c"],
                "capacity_ah": [5.0, 4.9, 4.8, 4.7],
            }
        )
    return out


def test_probe_pairs_find_a_broken_direction_with_no_solver():
    contract = pc.load(BATTERY)
    ok = pc.check_probes(contract, _toy_battery, seed="t", count=20)
    for lid in ("B5a", "B5b", "B6", "B7", "B8"):
        assert ok[lid] and max(ok[lid]) == 0.0, lid
    broken = pc.check_probes(
        contract, lambda pts: _toy_battery(pts, wrong=True), seed="t", count=20
    )
    assert min(broken["B5a"]) > 0 and min(broken["B6"]) > 0
    assert max(broken["B5b"]) == 0.0  # c2's direction is unchanged


def test_probes_are_deterministic_in_the_seed_and_stay_in_the_region():
    contract = pc.load(BATTERY)
    law = _law(contract, "B5a")
    a = pc.probe_pairs(contract, law, seed="s", count=10)
    assert a == pc.probe_pairs(contract, law, seed="s", count=10)
    assert a != pc.probe_pairs(contract, law, seed="other", count=10)
    region = contract["probe_region"]
    for _along, base, partner, _step in a:
        for point in (base, partner):
            for k, (low, high) in region.items():
                assert low <= point[k] <= high + 1e-12


def test_the_tolerance_is_the_reference_quantile_plus_margin_and_unset_until_registered():
    ref = [0.0, 0.1, 0.2, 0.3, 0.4]
    assert pc.tolerance(ref, q=1.0, margin=0.05) == pytest.approx(0.45)
    assert pc.tolerance(ref, q=0.5, margin=0.0) == pytest.approx(0.2)
    assert pc.tolerance(ref, q=pc.HUMAN_INPUT, margin=0.0) is None
    assert pc.tolerance(ref, q=1.0, margin=pc.HUMAN_INPUT) is None
    assert pc.violation_rate([0.0, 0.5, 0.1], 0.2) == pytest.approx(1 / 3)
    assert pc.violation_rate([0.1], None) is None


def test_outside_validity_and_absent_outputs_are_unresolved_not_zero_residuals():
    contract = pc.load(BATTERY)
    inputs = {"c1": 1.0, "c2": 0.5, "t_amb_c": 25.0, "soc0": 0.2}
    outputs = _toy_battery([inputs])[0]
    readings = pc.case_readings(
        contract, [({**inputs, "c1": 3.0}, outputs), (inputs, {})]
    )
    assert all(row == {"residuals": [], "unresolved": 2} for row in readings.values())
    declared = {
        **contract,
        "validity_models": [
            {
                "name": "fixture",
                "source": "synthetic non-production",
                "quantities": {"t_amb_c": [20, 30]},
            }
        ],
    }
    assert pc.applicable(declared, inputs)
    assert not pc.applicable(declared, {**inputs, "t_amb_c": 15})
    assert not pc.applicable(declared, {**inputs, "t_amb_c": float("nan")})


@pytest.mark.parametrize(
    "value", [float("nan"), float("inf"), float("-inf"), True, "25"]
)
def test_invalid_predictions_cannot_be_hidden_by_min_max_or_zero(value):
    contract = pc.load(BATTERY)
    inputs = {"c1": 1.0, "c2": 0.5, "t_amb_c": 25.0, "soc0": 0.2}
    outputs = _toy_battery([inputs])[0]
    bad = {**outputs, "temperature_c": [25.0, value] + [30.0] * 119}
    assert pc.single_residual(_law(contract, "B9"), inputs, bad) is None
    assert pc.pair_residual(_law(contract, "B8"), outputs, bad, "t_amb_c", 1) is None
    assert pc.case_readings(contract, [(inputs, bad)])["B9"]["unresolved"] == 1


def test_short_curves_and_prediction_count_mismatches_are_refused():
    contract = pc.load(BATTERY)
    law = _law(contract, "B8")
    assert (
        pc.pair_residual(
            law, {"temperature_c": [1, 2]}, {"temperature_c": [1]}, "t_amb_c", 1
        )
        is None
    )
    with pytest.raises(pc.ContractRefused, match="prediction_count"):
        pc.check_probes(contract, lambda points: [], seed="t", count=1)


def test_digest_and_step_validation_are_prospective():
    import copy

    contract = pc.load(BATTERY)
    assert pc.digest(contract) == pc.digest(dict(reversed(list(contract.items()))))
    changed = copy.deepcopy(contract)
    changed["laws"][0]["high"] += 0.01
    assert pc.digest(contract) != pc.digest(changed)
    changed["laws"][4]["step"] = 0
    with pytest.raises(pc.ContractRefused, match="law_step"):
        pc.validate(changed)
    with pytest.raises(pc.ContractRefused, match="margin"):
        pc.tolerance([0.0], q=1, margin=-1)
    with pytest.raises(pc.ContractRefused, match="quantile"):
        pc.tolerance([0.0], q=1.1, margin=0)
