"""Motor's dual measurement from predictions reproduces the recorded baseline.

The committed applied definition's G1 gate policy records the learned-krr-v1
baseline legs (A 0.28108361796711556, D 0.3419193228890681), computed on
18 Oct from saved workflow summaries. Rebuilding that same model from public
TRAIN and measuring its predictions on the 90-row exposed development bank
must give the same legs: the port computes the registered definition, not a
new one. The rebuild runs with BLAS pinned to one thread (Validator,
2026-10-20), and its legs are asserted exactly: A 0.28108361796791453 (G1 +
8.0e-13: the recorded value came from another host's thread count) and D
exactly G1's. Then: an altered prediction changes the result; a gate failure,
a missing cohort row and an invalid curve are typed, never silent.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from carbon.motor.challenge import PublicMaterial
from carbon.scoring import motor_dual_measurement as mdm
from carbon.scoring import motor_dual_pack

ROOT = Path(__file__).resolve().parents[2]
#: The pinned single-thread rebuild's legs, asserted exactly.
BASELINE_A = 0.28108361796791453
BASELINE_D = 0.3419193228890681
#: MOTOR_DUAL_TRANSFER_ACQUISITION_MANIFEST_20261018 pilot_case_ids.
PILOT_ORDER = (
    "difficult-1-deep-saturation",
    "difficult-2-sharpest-cogging",
    "difficult-3-weakest-field",
    "difficult-4-field-weakening",
    *(f"ordinary-{i}" for i in range(1, 9)),
)
#: The registered values, read from the committed applied definition.
DEFINITION = {
    "schema": mdm.DEFINITION_SCHEMA,
    "method": mdm.METHOD,
    **motor_dual_pack._definition_values(),
    "cohort_counts": {
        "practice": 30,
        "pilot_ordinary": 8,
        "pilot_difficult": 4,
        "decision_representative": 32,
        "decision_boundary_stress": 16,
    },
}


def _jsonl(path):
    return [json.loads(line) for line in path.read_text("utf-8").splitlines() if line]


def _role(name):
    return json.loads((ROOT / "carbon/challenge_kit/data" / name).read_text("utf-8"))


@pytest.fixture(scope="module")
def bank():
    """The exposed development bank in the declared order (Data Collection's
    physical_pack.development_bank order: practice, pilot, design x condition)."""
    rows = []
    for record in _jsonl(
        ROOT / "docs/development/evidence/motor-pools-v1/practice.jsonl"
    ):
        rows.append(
            {
                "case_id": record["case_id"],
                "cohort": "practice",
                "inputs": record["inputs"],
                "record": record,
            }
        )
    pilot = {
        r["case_id"]: r
        for r in _jsonl(ROOT / "docs/development/evidence/motor-pilot-v1/records.jsonl")
    }
    for case_id in PILOT_ORDER:
        record = pilot[case_id]
        cohort = {"ordinary": "pilot_ordinary", "corner": "pilot_difficult"}[
            record["kind"]
        ]
        rows.append(
            {
                "case_id": case_id,
                "cohort": cohort,
                "inputs": record["inputs"],
                "record": record,
            }
        )
    study = json.loads(
        (ROOT / "docs/development/studies/MOTOR_SYNTHETIC_DECISION_V2.json").read_text(
            "utf-8"
        )
    )
    solved = {
        c["case_id"]: c
        for c in json.loads(
            (
                ROOT / "docs/development/evidence/track-b-replay/motor-counted-v2.json"
            ).read_text("utf-8")
        )["cases"]
    }
    for design in study["designs"]:
        for condition in study["conditions"]:
            case_id = f"decision-{design['design_id']}-{condition['condition_id']}"
            rows.append(
                {
                    "case_id": case_id,
                    "cohort": "decision_" + condition["group"].lower(),
                    "inputs": {**design["values"], **condition["values"]},
                    "record": solved[case_id],
                    "design_id": design["design_id"],
                }
            )
    return rows


@pytest.fixture(scope="module")
def baseline(bank):
    material = PublicMaterial.load(ROOT)
    outputs = motor_dual_pack.baseline_outputs([row["inputs"] for row in bank])
    return material, outputs


def _measure(bank, material, outputs, repeats=None, definition=DEFINITION):
    try:
        limits = _role("motor-important-limit-definition-20261018.json")
        objective = _role("motor-design-objective-20261018.json")
    except FileNotFoundError:
        pytest.skip("Motor public roles are on Data Collection's packs branch")
    return mdm.measure(
        bank=bank,
        outputs=outputs,
        repeats=repeats or [outputs, outputs],
        definition=definition,
        limits=limits,
        objective=objective,
        train=material.train,
    )


def test_the_rebuilt_baseline_reproduces_the_recorded_legs(bank, baseline):
    material, outputs = baseline
    result = _measure(bank, material, outputs)
    assert result["gates"] == {
        "native_motor_valid": True,
        "complete_fixed_coverage": True,
    }
    assert result["A"] == BASELINE_A
    assert result["D"] == BASELINE_D
    assert result["decision_outcome"] == "VERIFIED_FEASIBLE"


def test_a_changed_prediction_changes_its_loss_and_a_is_the_minimum(bank, baseline):
    """Negative control: the port reads the predictions. A is the minimum of
    the eight benefits, so a cohort that is not the binding one moves its own
    loss and leaves A where the binding cohort puts it."""
    material, outputs = baseline
    base = _measure(bank, material, outputs)
    shifted = [list(v) for v in outputs]
    for i, row in enumerate(bank):
        if row["cohort"] == "practice":
            shifted[i] = [t + 0.5 for t in shifted[i]]
    result = _measure(bank, material, shifted, repeats=[shifted, shifted])
    assert result["losses"]["practice30_mean_f0"] > base["losses"]["practice30_mean_f0"]
    benefit = 1 / (1 + result["losses"]["practice30_mean_f0"] / 0.17)
    assert result["A"] == pytest.approx(min(BASELINE_A, benefit), rel=0, abs=1e-12)
    worse = [list(v) for v in outputs]
    for i, row in enumerate(bank):
        if row["cohort"].startswith("decision_"):
            worse[i] = [t * 1.5 for t in worse[i]]
    assert _measure(bank, material, worse, repeats=[worse, worse])["A"] < BASELINE_A


def test_a_repeat_beyond_motors_rule_fails_the_native_gate(bank, baseline):
    material, outputs = baseline
    drifted = [list(v) for v in outputs]
    drifted[0] = [t + 1e-3 for t in drifted[0]]
    result = _measure(bank, material, outputs, repeats=[outputs, drifted])
    assert result["gates"]["native_motor_valid"] is False
    assert result["gate_failed_cases"] == [bank[0]["case_id"]]


def test_a_missing_cohort_row_and_an_invalid_curve_are_typed(bank, baseline):
    material, outputs = baseline
    with pytest.raises(mdm.MotorMeasurementRefused, match="motor_prediction_roster"):
        _measure(bank[:-1], material, outputs)
    with pytest.raises(mdm.MotorMeasurementRefused, match="motor_bank_cohorts"):
        _measure(bank[:-1], material, outputs[:-1], repeats=[outputs[:-1]] * 2)
    broken = [list(v) for v in outputs]
    decision_row = next(
        i for i, r in enumerate(bank) if r["cohort"].startswith("decision_")
    )
    broken[decision_row] = [float("nan")] * 60
    result = _measure(bank, material, broken, repeats=[broken, broken])
    assert result["gates"]["native_motor_valid"] is False
    assert result["A"] is None and result["D"] is None
    assert result["decision_outcome"] == "MISSED_OPPORTUNITY"


def test_the_definition_must_be_the_registered_one():
    for changed in ({"verification_budget": 0}, {"f0_scale": -1}, {"losses": []}):
        with pytest.raises(mdm.MotorMeasurementRefused, match="motor_definition"):
            mdm.validate_definition({**DEFINITION, **changed})
