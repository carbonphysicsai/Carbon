"""Pure DEVELOPMENT calibration reduction; no solver, I/O or physical claim.

The producer authenticates actual source/rung/observer/role/provenance before
calling this arithmetic. A compatible calibration receipt is not evidence for
an unevaluated action or a production plating-reference claim.
"""

from __future__ import annotations

import math

from carbon.design_search import tasks

POLICY = {
    "id": "carbon.scorelab.battery-v3.operational-enclosure.v1",
    "scope": "DEVELOPMENT_ONLY",
    "floors": {
        "charging_t_max_c": 0.05,
        "plating_min_v": 0.00005,
        "minutes": 0.05,
        "q30_over_q1": 0.0001,
    },
    "radius": "max(floor, 2 * abs(finest - previous))",
    "voltage": {"upper_v": 4.2, "max_pair_change_v": 0.000001},
    "units": {
        "charging_t_max_c": "C",
        "plating_min_v": "V",
        "minutes": "min",
        "q30_over_q1": "1",
        "v_max_v": "V",
    },
    "physical_confidence_interval": False,
}
QUANTITIES = frozenset(POLICY["units"])


def _valid(values):
    return (
        type(values) is dict
        and set(values) == QUANTITIES
        and all(type(v) in (float, int) and math.isfinite(v) for v in values.values())
    )


def pair_enclosures(previous, finest, *, expected_policy_digest):
    """Operational intervals from the two named rungs; null time stays unknown."""
    if expected_policy_digest != tasks.digest(POLICY):
        raise tasks.TaskError("registered numerical policy differs")
    body = {
        "policy_digest": expected_policy_digest,
        "input_digest": tasks.digest([previous, finest]),
    }
    if not _valid(previous) or not _valid(finest):
        return {**body, "status": "REFERENCE_UNRESOLVED", "intervals": None}
    bounds = {}
    for quantity, floor in POLICY["floors"].items():
        point = finest[quantity]
        radius = max(floor, 2 * abs(point - previous[quantity]))
        bounds[quantity] = [point - radius, point + radius]
        if not math.isfinite(radius) or not all(
            math.isfinite(x) for x in bounds[quantity]
        ):
            return {
                **body,
                "status": "REFERENCE_UNRESOLVED",
                "intervals": None,
                "reason": "NONFINITE_INTERVAL_ARITHMETIC",
            }
    # Boundary convention is a two-observed-rung numerical check, NOT a
    # certified enclosure or a relaxed physical voltage limit.
    a, b = previous["v_max_v"], finest["v_max_v"]
    bounds["v_max_v"] = [min(a, b), max(a, b)]
    voltage_ok = (
        max(a, b) <= POLICY["voltage"]["upper_v"]
        and abs(a - b) <= POLICY["voltage"]["max_pair_change_v"]
    )
    return {
        **body,
        "status": (
            "READY_OPERATIONAL_ENCLOSURES" if voltage_ok else "REFERENCE_UNRESOLVED"
        ),
        "intervals": bounds,
        "voltage_boundary_contact": max(a, b) == POLICY["voltage"]["upper_v"],
        "physical_confidence_interval": False,
    }


def calibration_report(triples, *, expected_cases, expected_policy_digest):
    """Check a fixed offered set, including missing triples; no global PASS.

    triples[case] has exact keys '20','40','80', each an extracted five-quantity
    record. Source SHA/rung/job provenance remains a required producer receipt.
    Call on each newly completed triple for an early failure, and on the full
    registered stage before release. A partial result cannot release that stage.
    """
    expected = tuple(expected_cases)
    if (
        len(set(expected)) != len(expected)
        or not expected
        or set(triples) - set(expected)
    ):
        raise tasks.TaskError("complete registered calibration identities required")
    if expected_policy_digest != tasks.digest(POLICY):
        raise tasks.TaskError("registered numerical policy differs")
    missing, failed, rows = [], [], {}
    for case in expected:
        triple = triples.get(case)
        if (
            type(triple) is not dict
            or set(triple) != {"20", "40", "80"}
            or not all(_valid(v) for v in triple.values())
        ):
            missing.append(case)
            continue
        pair = pair_enclosures(
            triple["20"], triple["40"], expected_policy_digest=expected_policy_digest
        )
        finest_pair = pair_enclosures(
            triple["40"], triple["80"], expected_policy_digest=expected_policy_digest
        )
        if pair["intervals"] is None or finest_pair["intervals"] is None:
            missing.append(case)
            rows[case] = {"compatible": False, "pair": pair, "finest_pair": finest_pair}
            continue
        outside = [
            q
            for q in POLICY["floors"]
            if not pair["intervals"][q][0] <= triple["80"][q] <= pair["intervals"][q][1]
        ]
        compatible = (
            not outside and finest_pair["status"] == "READY_OPERATIONAL_ENCLOSURES"
        )
        if not compatible:
            failed.append(case)
        rows[case] = {
            "compatible": compatible,
            "outside_quantities": outside,
            "pair": pair,
            "finest_pair": finest_pair,
        }
    body = {
        "schema": "carbon.scorelab.battery-v3.calibration-reduction.v1",
        "policy_digest": expected_policy_digest,
        "expected_cases_digest": tasks.digest(expected),
        "expected_case_count": len(expected),
        "input_digest": tasks.digest(triples),
        "status": (
            "NUMERICAL_CALIBRATION_INADEQUATE"
            if failed
            else (
                "INCOMPLETE_REFERENCE"
                if missing
                else "COMPATIBLE_FOR_REGISTERED_CALIBRATION_CASES"
            )
        ),
        "missing_cases": missing,
        "failed_cases": failed,
        "per_case": rows,
        "qualification": False,
        "public_producer_provenance_binding": "REQUIRED_SEPARATELY",
    }
    return {**body, "receipt_digest": tasks.digest(body)}
