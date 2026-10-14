"""PKT-19: existing-law gate controls and counterfactual threshold curves.

Only built-in synthetic fixtures are admitted. No candidate/reference data
input, native solver, miner execution, adoption or registered-rule mutation.
The check option reads only the artifact the operator asks it to compare.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from itertools import pairwise
from pathlib import Path

import numpy as np

from carbon.battery import exam
from carbon.challenge_validator import physics_contract
from carbon.measurement_runtime import development, development_controls
from carbon.scoring import development as scoring

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "carbon.physics-law-gate-controls.v1"
SOURCES = (
    "carbon/measurement_runtime/development.py",
    "carbon/measurement_runtime/development_controls.py",
    "carbon/scoring/development.py",
    "carbon/battery/exam.py",
    "carbon/battery/domain.py",
    "carbon/battery/physics_contract.v2.json",
    "carbon/challenge_validator/physics_contract.py",
    ".agent/decisions/2026-10-13-OWNER-PHYSICS-GATES-01.md",
    "scripts/dev/physics_law_gates.py",
)


def hypothetical_gate(readings, *, threshold=None, strict=False, arithmetic_floor=0.0):
    """Counterfactual only: unset threshold and unresolved cases fail closed.

    Every reading contributes to the basis. No score parameter exists.
    A returned pass never adopts a threshold or confers scientific authority.
    """
    if (
        type(readings) is not dict
        or not readings
        or any(type(k) is not str or not k for k in readings)
        or type(strict) is not bool
        or type(arithmetic_floor) not in (int, float)
        or not math.isfinite(arithmetic_floor)
        or arithmetic_floor < 0
    ):
        raise ValueError("nonempty closed reading basis required")
    if threshold is not None and (
        type(threshold) not in (int, float)
        or not math.isfinite(threshold)
        or threshold < 0
    ):
        raise ValueError("finite nonnegative hypothetical threshold required")
    admitted, excluded, unresolved = [], [], []
    for name, residual in sorted(readings.items()):
        if (
            type(residual) not in (int, float)
            or not math.isfinite(residual)
            or residual < 0
        ):
            unresolved.append(name)
        elif threshold is None:
            continue
        elif not math.isfinite(residual + arithmetic_floor):
            unresolved.append(name)
        elif (strict and residual + arithmetic_floor < threshold) or (
            not strict and residual + arithmetic_floor <= threshold
        ):
            admitted.append(name)
        else:
            excluded.append(name)
    return {
        "state": (
            "HUMAN_INPUT"
            if threshold is None
            else (
                "UNRESOLVED"
                if unresolved
                else "BREACHED" if excluded else "HELD_COUNTERFACTUAL_ONLY"
            )
        ),
        "threshold": threshold,
        "strict": strict,
        "arithmetic_floor": arithmetic_floor,
        "n_cases": len(readings),
        "n_measured": len(readings) - len(unresolved),
        "n_checked": len(readings) - len(unresolved) if threshold is not None else 0,
        "n_admitted": len(admitted),
        "n_excluded": len(excluded),
        "n_unresolved": len(unresolved),
        "admitted": admitted,
        "excluded": excluded,
        "unresolved": unresolved,
        "counterfactual_all_pass": threshold is not None
        and not excluded
        and not unresolved,
        "adoption": "HUMAN_INPUT",
        "scope": "ONE_LAW_COUNTERFACTUAL_NOT_CANDIDATE_ADMISSION",
    }


def _thresholds(readings, floor=0.0):
    """Observed breakpoints, their midpoints and next floats; no fitted optimum."""
    values = sorted(
        {
            0.0,
            *(
                float(v) + floor
                for v in readings.values()
                if type(v) in (int, float) and math.isfinite(v) and v >= 0
            ),
        }
    )
    return sorted(
        {
            *values,
            *(math.nextafter(v, math.inf) for v in values),
            *((a + b) / 2 for a, b in pairwise(values)),
        }
    )


def _rows(measurement):
    return tuple(
        {
            "role": role,
            "case": f"{role}-fixture-{case}",
            "replica": replica,
            "measurement": measurement,
        }
        for role in scoring.RULE["roles"]
        for case in range(12)
        for replica in range(3)
    )


def _burgers():
    controls = development_controls.controls("verification-v2")
    measured = {
        name: controls["results"][name]
        for name in (
            "exact",
            "mean_drift",
            "frozen_initial",
            "plausible_statistics_wrong_trajectory",
        )
    }
    # A boundary/initial-condition negative control with the same mean and
    # extrema: shift only the prescribed first row. The auxiliary reference
    # here is a structural fixture; no reference adequacy is being asserted.
    x = np.arange(64) * (2 * math.pi / 64)
    initial = 0.1 + 0.4 * np.sin(x)
    reference = np.broadcast_to(initial, (3, 64)).copy()
    bad_initial = reference.copy()
    bad_initial[0] = np.roll(initial, 2)
    measured["wrong_initial"] = development.measure(
        bad_initial,
        reference,
        times=[0.0, 0.1, 1.0],
        length=2 * math.pi,
        viscosity=0.005,
        initial=initial,
        amplitude=0.4,
        characteristic_time=1.0,
    )
    judged = {name: scoring.summarize(_rows(m)) for name, m in measured.items()}
    baseline = measured["plausible_statistics_wrong_trajectory"]
    decision = scoring.compare(
        _rows(baseline),
        _rows(measured["mean_drift"]),
        prospective=True,
        reference_field_indicator=0.0,
        reference_energy_indicator=0.0,
    )
    laws = {}
    for name in ("conserved_mean", "initial_condition"):
        readings = {case: m["metrics"][name] for case, m in measured.items()}
        readings["missing_observation"] = None
        floor = scoring.RULE["arithmetic_floor"]
        laws[name] = {
            "units": "initial-amplitude normalized",
            "measurement_version": development.VERSION,
            "existing_limit": scoring.RULE["hard_limits"][name],
            "existing_rule": scoring.RULE["id"],
            "readings": readings,
            "unconfigured": hypothetical_gate(
                readings, strict=True, arithmetic_floor=floor
            ),
            "curve": [
                hypothetical_gate(
                    readings, threshold=t, strict=True, arithmetic_floor=floor
                )
                for t in _thresholds(readings, floor)
            ],
        }
    return {
        "fixture": "verification-v2 analytic controls plus structural wrong-initial control",
        "comparison_basis": "One synthetic control repeated to fill the 2x12x3 API rectangle; not independent cases or replicas.",
        "laws": laws,
        "actual_registered_judge": {
            name: {
                "failed_mandatory": j["failed_mandatory"],
                "descriptive_score": j["score"],
            }
            for name, j in judged.items()
        },
        "score_cannot_compensate": {
            "disposition": decision.disposition,
            "accepted_improvement": decision.accepted_improvement,
            "challenger_score": decision.challenger["score"],
            "baseline_score": decision.baseline["score"],
        },
        "blind_spot_control": "frozen_initial preserves initial condition/mean but has wrong dynamics; it is not proof of the PDE",
    }


def _battery_cases():
    good = {
        "voltage_v": [3.6] * 121,
        "temperature_c": [25.0] * 121,
        "plating_margin_v": 0.1,
        "capacity_ah": [4.5] * 4,
    }
    cases = {"compliant_fixture": good}
    for name in (
        "wrong_initial_temperature",
        "over_inventory",
        "zero_capacity",
        "missing_capacity",
    ):
        cases[name] = copy.deepcopy(good)
    cases["wrong_initial_temperature"]["temperature_c"][0] = 26.0
    cases["over_inventory"]["capacity_ah"][0] = 5.5
    cases["zero_capacity"]["capacity_ah"][0] = 0.0
    del cases["missing_capacity"]["capacity_ah"]
    return cases


def _battery_judge(
    prediction,
    *,
    t0_allowance,
    inventory_bound,
    reference_valid=True,
    infra_failed=False,
):
    # These numbers are closed synthetic control settings, not production
    # calibration. No deployment, reference set or scientific state is read.
    return exam.evaluate_case(
        prediction,
        {"status": "OK", "reference_valid": reference_valid},
        {"c1": 1.0, "c2": 0.5, "t_amb_c": 25.0, "soc0": 0.2},
        3.6,
        exam.Tolerances(
            0.0,
            t0_allowance,
            0.0,
            0.0,
            inventory_bound,
            evidence={"scope": "SYNTHETIC_FIXTURE"},
        ),
        {
            "voltage_v": (121,),
            "temperature_c": (121,),
            "plating_margin_v": (),
            "capacity_ah": (4,),
        },
        infra_failed=infra_failed,
    )


def _battery():
    contract = json.loads(
        (ROOT / "carbon/battery/physics_contract.v2.json").read_text(encoding="utf-8")
    )
    law = next(law for law in contract["laws"] if law["id"] == "B2")
    cases = _battery_cases()
    actual = {
        name: _battery_judge(pred, t0_allowance=0.0, inventory_bound=5.0)
        for name, pred in cases.items()
    }
    readings = {
        name: (
            physics_contract.single_residual(law, {"t_amb_c": 25.0}, pred)
            if "capacity_ah" in pred
            else None
        )
        for name, pred in cases.items()
    }
    curves = []
    for threshold in _thresholds(readings):
        verdicts = {
            name: _battery_judge(pred, t0_allowance=threshold, inventory_bound=5.0)
            for name, pred in cases.items()
        }
        row = hypothetical_gate(readings, threshold=threshold)
        row["actual_initial_temperature_verdicts"] = {
            name: verdict["gates"].get("initial_temperature", "UNRESOLVED")
            for name, verdict in verdicts.items()
        }
        curves.append(row)
    bounds = _thresholds(
        {
            name: max(pred["capacity_ah"]) if "capacity_ah" in pred else None
            for name, pred in cases.items()
        }
    )
    inventory_curve = []
    for bound in bounds:
        verdicts = {
            name: _battery_judge(pred, t0_allowance=0.0, inventory_bound=bound)
            for name, pred in cases.items()
        }
        inventory_curve.append(
            {
                "hypothetical_inventory_bound_ah": bound,
                "admitted": sorted(
                    name
                    for name, v in verdicts.items()
                    if v["gates"].get("capacity_bound") == exam.PASS
                ),
                "excluded": sorted(
                    name
                    for name, v in verdicts.items()
                    if v["gates"].get("capacity_bound") == exam.FAIL
                ),
                "unresolved": sorted(
                    name
                    for name, v in verdicts.items()
                    if "capacity_bound" not in v["gates"]
                ),
                "n_cases": len(cases),
                "adoption": "HUMAN_INPUT",
            }
        )
        row = inventory_curve[-1]
        row.update(
            {
                "n_" + key: len(row[key])
                for key in ("admitted", "excluded", "unresolved")
            }
        )
        row["n_checked"] = row["n_cases"] - row["n_unresolved"]
    rows = []
    for name in ("compliant_fixture", "wrong_initial_temperature"):
        row = copy.deepcopy(actual[name])
        row.update(
            error=0.0, components={k: 0.0 for k in exam.COMPONENTS}, important=False
        )
        rows.append(row)
    return {
        "fixture": "synthetic 25 C / 3.6 V / 4.5 Ah outputs; 5 Ah fixture inventory bound",
        "actual_registered_judge": actual,
        "failure_classification_controls": {
            "reference_invalid": _battery_judge(
                cases["compliant_fixture"],
                t0_allowance=0.0,
                inventory_bound=5.0,
                reference_valid=False,
            ),
            "infra_failed": _battery_judge(
                cases["compliant_fixture"],
                t0_allowance=0.0,
                inventory_bound=5.0,
                infra_failed=True,
            ),
        },
        "initial_temperature": {
            "units": "C absolute",
            "readings": readings,
            "unconfigured": hypothetical_gate(readings),
            "curve": curves,
        },
        "capacity_inventory_bound": {
            "units": "Ah",
            "definition": "0 < Q_k <= Q_bound",
            "bound_semantics": "Derived from the registered parameter set, never fitted to admit models; curve is fixture parameter sensitivity only.",
            "new_bound_adoption": None,
            "curve": inventory_curve,
        },
        "perfect_error_cannot_compensate": exam.aggregate(rows),
    }


def report():
    burgers, battery = _burgers(), _battery()
    bj, tj = burgers["actual_registered_judge"], battery["actual_registered_judge"]
    checks = {
        "burgers_positive_control_admissible": not bj["exact"]["failed_mandatory"],
        "burgers_mean_drift_caught": any(
            x.endswith(":conserved_mean") for x in bj["mean_drift"]["failed_mandatory"]
        ),
        "burgers_initial_condition_caught": any(
            x.endswith(":initial_condition")
            for x in bj["wrong_initial"]["failed_mandatory"]
        ),
        "burgers_better_score_cannot_compensate": burgers["score_cannot_compensate"][
            "disposition"
        ]
        == "REJECTED_MANDATORY"
        and burgers["score_cannot_compensate"]["challenger_score"]
        > burgers["score_cannot_compensate"]["baseline_score"],
        "battery_positive_control_scorable": tj["compliant_fixture"]["state"]
        == exam.SCORABLE,
        "battery_initial_condition_caught": tj["wrong_initial_temperature"][
            "gates"
        ].get("initial_temperature")
        == exam.FAIL,
        "battery_inventory_control_caught": tj["over_inventory"]["gates"].get(
            "capacity_bound"
        )
        == exam.FAIL,
        "battery_zero_capacity_caught": tj["zero_capacity"]["gates"].get(
            "capacity_bound"
        )
        == exam.FAIL,
        "battery_missing_capacity_cannot_pass": tj["missing_capacity"]["state"]
        == exam.GATE_FAILED,
        "battery_perfect_error_cannot_compensate": not battery[
            "perfect_error_cannot_compensate"
        ]["eligible"],
        "reference_failure_not_candidate_breach": battery[
            "failure_classification_controls"
        ]["reference_invalid"]
        == {"state": exam.REFERENCE_INVALID, "gates": {}},
        "infra_failure_not_candidate_breach": battery[
            "failure_classification_controls"
        ]["infra_failed"]
        == {"state": exam.FAILED_INFRA, "gates": {}},
    }
    return {
        "schema": SCHEMA,
        "scope": "SYNTHETIC_CONTROLS_NOT_QUALIFICATION",
        "classification": "DOCUMENTATION_LAG",
        "source_sha256": {
            path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
            for path in SOURCES
        },
        "new_scientific_scope": {
            "law": None,
            "observable": None,
            "challenge": None,
            "applicability": None,
            "tolerance": None,
            "adoption": "HUMAN_INPUT",
            "admissible": False,
        },
        "new_gate_effective": False,
        "checks": checks,
        "controls_passed": all(checks.values()),
        "burgers": burgers,
        "battery": battery,
        "observability_limits": [
            "Burgers mean/initial gates already exist; passing them does not establish correct dynamics.",
            "Fourier periodic closure is a representation identity, not an independently tested spatial boundary.",
            "Integrated-energy and finite-mode weak-PDE diagnostics stay underresolved diagnostics.",
            "Battery capacity_bound is an inventory-derived inequality, not a full charge/heat conservation equality.",
            "Battery V/T/plating-margin/cycle-capacity outputs omit the internal inventories/current/heat fluxes needed for that equality.",
            "B15 remains adopted; B16/B9 card and B8 diagnostic roles are unchanged.",
        ],
    }


def encoded_report():
    return (
        json.dumps(report(), indent=2, sort_keys=True, allow_nan=False) + "\n"
    ).encode("utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--check", type=Path, help="compare existing generated fixture bytes"
    )
    args = parser.parse_args(argv)
    if args.output is not None and args.check is not None:
        parser.error("choose output or check")
    raw = encoded_report()
    if args.check is not None:
        if args.check.read_bytes() != raw:
            raise SystemExit("generated synthetic curves differ")
    elif args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(raw)
    else:
        print(raw.decode("utf-8"), end="")
    if not json.loads(raw)["controls_passed"]:
        raise SystemExit("an existing-law control failed")


if __name__ == "__main__":
    main()
