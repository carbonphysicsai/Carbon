"""Prospective C-07 disclosure amendment for complete DEVELOPMENT cohorts.

Only aggregate normalized observations leave this owner. No labels, raw values,
case identity, reference scale, seed, file path or diagnostic text is projected.
This module cannot construct an official ScoreInput or winner decision.
"""

from __future__ import annotations

import math

from carbon.measurement_runtime.model import (
    MEASUREMENT_IDS,
    PHYSICS_IDS,
    BurgersMeasurementRequest,
    BurgersMeasurementResult,
    MeasurementDisposition,
)


def aggregate_development_feedback(
    cohorts: tuple[
        tuple[
            str, tuple[tuple[BurgersMeasurementRequest, BurgersMeasurementResult], ...]
        ],
        ...,
    ],
    *,
    expected_cases: dict[str, frozenset[str]],
) -> dict[str, object]:
    if set(expected_cases) != {"EVAL", "STRESS"} or any(
        type(cases) is not frozenset or len(cases) != 12
        for cases in expected_cases.values()
    ):
        raise ValueError("exact frozen cohort membership required")
    if type(cohorts) is not tuple or tuple(item[0] for item in cohorts) != (
        "EVAL",
        "STRESS",
    ):
        raise ValueError("exact EVAL and STRESS cohorts required")
    public = {}
    all_requests = set()
    plan = None
    role_cases = []
    for role, pairs in cohorts:
        if type(pairs) is not tuple or len(pairs) != 36:
            raise ValueError("all 12 parents and all three replicas required")
        coverage = set()
        errors = {name: [] for name in MEASUREMENT_IDS}
        physics = {name: [] for name in PHYSICS_IDS}
        for request, result in pairs:
            if (
                type(request) is not BurgersMeasurementRequest
                or type(result) is not BurgersMeasurementResult
            ):
                raise ValueError("domain-owned measurement values required")
            if (
                request.request_digest != result.request_digest
                or result.disposition
                is not MeasurementDisposition.COMPLETE_DEVELOPMENT_ONLY
            ):
                raise ValueError("incomplete or mismatched measurement")
            if request.request_digest in all_requests:
                raise ValueError("duplicate measurement")
            all_requests.add(request.request_digest)
            if plan is None:
                plan = request.candidate_plan_digest
            if request.candidate_plan_digest != plan:
                raise ValueError("mixed strategies")
            identity = (request.case_digest, request.candidate_replica_id)
            if identity in coverage:
                raise ValueError("duplicate case/replica")
            coverage.add(identity)
            for item in result.measurements:
                errors[item.measurement_id].append(item.normalized_error)
            for item in result.physics:
                physics[item.physics_id].append(item.normalized_defect)
        cases = {case for case, _ in coverage}
        replicas = {replica for _, replica in coverage}
        if (
            cases != expected_cases[role]
            or replicas != {f"reconstruction-replica-{index}" for index in range(3)}
            or coverage != {(case, replica) for case in cases for replica in replicas}
        ):
            raise ValueError("incomplete case/replica product")
        role_cases.append(cases)

        def means(observations):
            return {
                name: {
                    "mean": math.fsum(values) / len(values) if values else None,
                    "observed": len(values),
                    "missing": 36 - len(values),
                }
                for name, values in sorted(observations.items())
            }

        public[role] = {
            "parents": 12,
            "replicas": 3,
            "normalized_errors": means(errors),
            "normalized_physics_defects": means(physics),
        }
    if role_cases[0] & role_cases[1]:
        raise ValueError("EVAL/STRESS overlap")
    return {
        "schema": "carbon.c07.development-aggregate-feedback.v1",
        "cohorts": public,
        "decision": "UNRESOLVED_NO_QUALIFIED_LIMIT",
        "score": None,
        "uncertainty": None,
        "accepted_improvement": None,
        "eligibility": {
            "protected": False,
            "official": False,
            "score": False,
            "reward": False,
        },
    }
