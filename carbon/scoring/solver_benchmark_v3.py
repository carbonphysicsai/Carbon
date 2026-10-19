"""Prospective DEVELOPMENT Score Pack v3 for measured model/solver benchmarks.

This closed rule never changes A5/v1 scoring. A Challenge must register its
own physics gate IDs and accuracy ceiling before any candidate is ranked.
"""

from __future__ import annotations

import hashlib
import json
import math

PACK_SCHEMA = "carbon.scoring.solver-benchmark-pack.v3"
RESULT_SCHEMA = "carbon.scoring.solver-benchmark-score.v3"
BENCHMARK_SCHEMA = "carbon.score-lab.solver-benchmark-result.v2"


class BenchmarkScoreRefused(ValueError):
    """A malformed or mismatched prospective benchmark Score Pack."""


COUNT_KEYS = frozenset(
    {
        "resolved",
        "reference_unresolved",
        "reference_infra",
        "candidate_invalid",
        "candidate_infra",
        "scientific_inadmissible",
    }
)


def _finite_number(value):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(float(value))
    except (OverflowError, ValueError):
        return False


def measurement_status(counts):
    """One shared status order; reference gaps never become candidate faults."""
    if (
        type(counts) is not dict
        or set(counts) != COUNT_KEYS
        or any(type(v) is not int or v < 0 for v in counts.values())
        or counts["scientific_inadmissible"] > counts["resolved"]
    ):
        raise BenchmarkScoreRefused("benchmark_counts")
    if counts["reference_infra"] or counts["candidate_infra"]:
        return "FAILED_INFRA"
    if counts["reference_unresolved"]:
        return "INDETERMINATE_EVIDENCE"
    if counts["scientific_inadmissible"]:
        return "SCIENTIFIC_INADMISSIBLE"
    if counts["candidate_invalid"]:
        return "CANDIDATE_INVALID"
    return "MEASURED_DEVELOPMENT"


def _digest(body):
    try:
        encoded = json.dumps(
            body, sort_keys=True, separators=(",", ":"), allow_nan=False
        )
    except (TypeError, ValueError) as exc:
        raise BenchmarkScoreRefused("noncanonical_pack") from exc
    return "sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def register_pack(body):
    """Bind exact development rule values; None keeps the pack unready."""
    if type(body) is not dict or set(body) != {
        "schema",
        "scope",
        "challenge",
        "benchmark_registration_digest",
        "physics_contract",
        "output",
        "hard_gates",
        "accuracy_ceiling",
        "performance_objective",
    }:
        raise BenchmarkScoreRefused("pack_shape")
    if (
        body["schema"] != PACK_SCHEMA
        or body["scope"] not in {"SYNTHETIC_DEVELOPMENT", "PUBLIC_DEVELOPMENT"}
        or type(body["challenge"]) is not str
        or not body["challenge"]
        or type(body["benchmark_registration_digest"]) is not str
        or not body["benchmark_registration_digest"]
    ):
        raise BenchmarkScoreRefused("pack_identity")
    physics = body["physics_contract"]
    if (
        type(physics) is not dict
        or set(physics) != {"version", "definition_digest"}
        or any(type(v) is not str or not v for v in physics.values())
        or not physics["definition_digest"].startswith("sha256:")
        or len(physics["definition_digest"]) != 71
        or any(c not in "0123456789abcdef" for c in physics["definition_digest"][7:])
    ):
        raise BenchmarkScoreRefused("pack_physics_contract")
    output = body["output"]
    if (
        type(output) is not dict
        or set(output) != {"quantity", "unit", "metric"}
        or any(type(output[k]) is not str or not output[k] for k in output)
        or output["metric"] != "mean_absolute_error"
    ):
        raise BenchmarkScoreRefused("pack_output")
    gates = body["hard_gates"]
    if (
        type(gates) is not list
        or not gates
        or any(type(g) is not str or not g for g in gates)
        or len(gates) != len(set(gates))
    ):
        raise BenchmarkScoreRefused("pack_gates")
    ceiling = body["accuracy_ceiling"]
    if ceiling is not None and (not _finite_number(ceiling) or ceiling < 0):
        raise BenchmarkScoreRefused("pack_accuracy_ceiling")
    if body["performance_objective"] != "maximize_paired_speedup":
        raise BenchmarkScoreRefused("pack_performance_objective")
    return {**body, "pack_digest": _digest(body)}


def score(benchmark, pack):
    """Same rule for validator and ScoreLab callers; no I/O or callbacks."""
    if type(pack) is not dict or pack.get("pack_digest") != _digest(
        {k: v for k, v in pack.items() if k != "pack_digest"}
    ):
        raise BenchmarkScoreRefused("pack_digest")
    register_pack({k: v for k, v in pack.items() if k != "pack_digest"})
    if (
        type(benchmark) is not dict
        or benchmark.get("schema") != BENCHMARK_SCHEMA
        or benchmark.get("registration_digest") != pack["benchmark_registration_digest"]
        or benchmark.get("scope") != pack["scope"]
        or benchmark.get("challenge") != pack["challenge"]
        or benchmark.get("physics_contract") != pack["physics_contract"]
        or benchmark.get("output") != pack["output"]
        or benchmark.get("ranking") is not None
        or type(benchmark.get("models")) is not list
    ):
        raise BenchmarkScoreRefused("benchmark_binding")
    if pack["accuracy_ceiling"] is None:
        return {
            "schema": RESULT_SCHEMA,
            "status": "PACK_NOT_READY",
            "pack_digest": pack["pack_digest"],
            "ranking": None,
            "models": [],
        }
    rows = []
    seen = set()
    for model in benchmark["models"]:
        if type(model) is not dict or type(model.get("artifact_digest")) is not str:
            raise BenchmarkScoreRefused("benchmark_model")
        identity = model["artifact_digest"]
        if not identity or identity in seen:
            raise BenchmarkScoreRefused("benchmark_model")
        seen.add(identity)
        p = model.get("by_role", {}).get("P")
        if type(p) is not dict or type(p.get("gate_failures")) is not dict:
            raise BenchmarkScoreRefused("benchmark_role")
        if set(p["gate_failures"]) != set(pack["hard_gates"]):
            raise BenchmarkScoreRefused("benchmark_gate_binding")
        measured_status = p.get("status")
        counts = p.get("counts")
        attempted = p.get("attempted")
        if (
            type(attempted) is not int
            or attempted < 1
            or measurement_status(counts) != measured_status
            or sum(
                counts[key] for key in COUNT_KEYS if key != "scientific_inadmissible"
            )
            != attempted
            or any(
                type(n) is not int or n < 0 or n > counts["scientific_inadmissible"]
                for n in p["gate_failures"].values()
            )
            or (
                counts["scientific_inadmissible"] > 0
                and not any(p["gate_failures"].values())
            )
        ):
            raise BenchmarkScoreRefused("benchmark_status")
        if measured_status == "MEASURED_DEVELOPMENT":
            if p.get("mandatory_gates_pass") is not True or any(
                type(n) is not int or n != 0 for n in p["gate_failures"].values()
            ):
                raise BenchmarkScoreRefused("benchmark_gate_inconsistent")
            error = p.get("mean_absolute_error")
            speedup = p.get("paired_speedup")
            if (
                not _finite_number(error)
                or error < 0
                or not _finite_number(speedup)
                or speedup <= 0
            ):
                raise BenchmarkScoreRefused("benchmark_measurement")
            if error > pack["accuracy_ceiling"]:
                state, performance = "ACCURACY_INELIGIBLE", None
            else:
                state, performance = "SCORED_DEVELOPMENT", float(speedup)
        else:
            state, performance = measured_status, None
        rows.append(
            {
                "artifact_digest": identity,
                "status": state,
                "performance_score": performance,
            }
        )
    admitted = sorted(
        (row for row in rows if row["status"] == "SCORED_DEVELOPMENT"),
        key=lambda row: (-row["performance_score"], row["artifact_digest"]),
    )
    leaders = (
        [
            row["artifact_digest"]
            for row in admitted
            if row["performance_score"] == admitted[0]["performance_score"]
        ]
        if admitted
        else []
    )
    return {
        "schema": RESULT_SCHEMA,
        "status": "DEVELOPMENT_ONLY",
        "pack_digest": pack["pack_digest"],
        "ranking": [row["artifact_digest"] for row in admitted],
        "leaders": leaders,
        "models": rows,
    }
