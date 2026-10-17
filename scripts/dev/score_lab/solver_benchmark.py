"""Pure DEVELOPMENT model-versus-solver benchmark receiver.

The producer measures the solver and model; this reducer executes neither. It
does not select a winner or turn a fixture result into a Challenge score.
"""

from __future__ import annotations

import hashlib
import json
import math
import statistics

from carbon.scoring.solver_benchmark_v2 import measurement_status

SCHEMA = "carbon.score-lab.solver-benchmark.v1"
RESULT_SCHEMA = "carbon.score-lab.solver-benchmark-result.v1"
ROLES = frozenset({"P", "Q"})


class BenchmarkRefused(ValueError):
    """Malformed or unregistered benchmark evidence."""


def _digest(body):
    try:
        encoded = json.dumps(
            body, sort_keys=True, separators=(",", ":"), allow_nan=False
        )
    except (TypeError, ValueError) as exc:
        raise BenchmarkRefused("noncanonical_input") from exc
    return "sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _number(value, *, positive=False, nonnegative=False):
    if type(value) not in (int, float):
        raise BenchmarkRefused("nonfinite_measurement")
    try:
        number = float(value)
    except (OverflowError, ValueError) as exc:
        raise BenchmarkRefused("nonfinite_measurement") from exc
    if not math.isfinite(number):
        raise BenchmarkRefused("nonfinite_measurement")
    if positive and number <= 0 or nonnegative and number < 0:
        raise BenchmarkRefused("measurement_out_of_range")
    return number


def _derived(value):
    if type(value) not in (int, float):
        raise BenchmarkRefused("derived_nonfinite")
    try:
        number = float(value)
    except (OverflowError, ValueError) as exc:
        raise BenchmarkRefused("derived_nonfinite") from exc
    if not math.isfinite(number):
        raise BenchmarkRefused("derived_nonfinite")
    return number


def _sum(values):
    try:
        return _derived(math.fsum(values))
    except OverflowError as exc:
        raise BenchmarkRefused("derived_nonfinite") from exc


def _latency_distribution(values):
    """Descriptive serial per-query seconds; p95 uses the nearest rank."""
    ordered = sorted(values)
    if not ordered:
        raise BenchmarkRefused("latency_empty")
    middle = len(ordered) // 2
    median = (
        ordered[middle]
        if len(ordered) % 2
        else _derived(ordered[middle - 1] / 2 + ordered[middle] / 2)
    )
    return {
        "min_s": ordered[0],
        "median_s": median,
        "p95_s": ordered[math.ceil(0.95 * len(ordered)) - 1],
        "max_s": ordered[-1],
    }


def register(body):
    """Bind a declared workload; registration does not attest physical truth."""
    if type(body) is not dict or set(body) != {
        "schema",
        "scope",
        "challenge",
        "job_digest",
        "train_digest",
        "output",
        "reference",
        "cases",
        "mandatory_gates",
        "timing_profile",
    }:
        raise BenchmarkRefused("registration_shape")
    if body["schema"] != SCHEMA or body["scope"] not in {
        "SYNTHETIC_DEVELOPMENT",
        "PUBLIC_DEVELOPMENT",
    }:
        raise BenchmarkRefused("registration_scope")
    for key in ("challenge", "job_digest", "train_digest"):
        if type(body[key]) is not str or not body[key]:
            raise BenchmarkRefused("registration_identity")
    output = body["output"]
    if (
        type(output) is not dict
        or set(output) != {"quantity", "unit", "size", "metric"}
        or any(
            type(output[k]) is not str or not output[k] for k in ("quantity", "unit")
        )
        or type(output["size"]) is not int
        or output["size"] < 1
        or output["metric"] != "mean_absolute_error"
    ):
        raise BenchmarkRefused("output_contract")
    reference = body["reference"]
    if (
        type(reference) is not dict
        or set(reference)
        != {"solver_digest", "fidelity_digest", "applicability_digest"}
        or any(type(v) is not str or not v for v in reference.values())
    ):
        raise BenchmarkRefused("reference_contract")
    profile = body["timing_profile"]
    if (
        type(profile) is not dict
        or set(profile) != {"basis", "model_device", "solver_device", "batch_size"}
        or profile["basis"] != "ready_input_to_comparable_output"
        or any(
            type(profile[k]) is not str or not profile[k]
            for k in ("model_device", "solver_device")
        )
        or type(profile["batch_size"]) is not int
        or profile["batch_size"] != 1
    ):
        raise BenchmarkRefused("timing_profile")
    gates = body["mandatory_gates"]
    if (
        type(gates) is not list
        or not gates
        or any(type(g) is not str or not g for g in gates)
        or len(gates) != len(set(gates))
    ):
        raise BenchmarkRefused("mandatory_gates")
    cases = body["cases"]
    if type(cases) is not list or not cases:
        raise BenchmarkRefused("case_roster")
    ids = []
    for case in cases:
        if (
            type(case) is not dict
            or set(case) != {"id", "role", "weight"}
            or type(case["id"]) is not str
            or not case["id"]
            or type(case["role"]) is not str
            or case["role"] not in ROLES
        ):
            raise BenchmarkRefused("case_roster")
        _number(case["weight"], positive=True)
        ids.append(case["id"])
    if len(ids) != len(set(ids)) or not any(c["role"] == "P" for c in cases):
        raise BenchmarkRefused("case_roster")
    return {**body, "registration_digest": _digest(body)}


def _case_map(rows, roster, cause):
    if type(rows) is not list:
        raise BenchmarkRefused(cause)
    mapped = {}
    for row in rows:
        if (
            type(row) is not dict
            or type(row.get("id")) is not str
            or row["id"] not in roster
            or row["id"] in mapped
        ):
            raise BenchmarkRefused(cause)
        mapped[row["id"]] = row
    if set(mapped) != roster:
        raise BenchmarkRefused(cause)
    return mapped


def _outputs(values, size):
    if type(values) is not list or len(values) != size:
        raise BenchmarkRefused("output_shape")
    return [_number(value) for value in values]


def compare(registration, references, models, *, score_pack=None):
    """Report paired accuracy, gates and measured speed on the full roster.

    The same registered reference map is used for every model. An unresolved
    reference withholds that role's aggregate for *all* models. Candidate
    failures and adverse gates remain counted; no row is redrawn or imputed.
    """
    if type(registration) is not dict or registration.get(
        "registration_digest"
    ) != _digest({k: v for k, v in registration.items() if k != "registration_digest"}):
        raise BenchmarkRefused("registration_digest")
    register({k: v for k, v in registration.items() if k != "registration_digest"})
    roster = {case["id"] for case in registration["cases"]}
    refs = _case_map(references, roster, "reference_roster")
    reference_rows = {}
    for cid, row in refs.items():
        status = row.get("status")
        if type(status) is not str or status not in {
            "RESOLVED",
            "UNRESOLVED",
            "FAILED_INFRA",
        }:
            raise BenchmarkRefused("reference_status")
        if status == "RESOLVED":
            if (
                set(row)
                != {
                    "id",
                    "status",
                    "outputs",
                    "elapsed_s",
                    "source",
                    "solver_digest",
                    "fidelity_digest",
                    "applicability_digest",
                    "peak_memory_bytes",
                }
                or row["source"] != "MEASURED_SOLVER_RUN"
                or row["solver_digest"] != registration["reference"]["solver_digest"]
                or row["fidelity_digest"]
                != registration["reference"]["fidelity_digest"]
                or row["applicability_digest"]
                != registration["reference"]["applicability_digest"]
            ):
                raise BenchmarkRefused("solver_measurement_required")
            reference_rows[cid] = {
                "outputs": _outputs(row["outputs"], registration["output"]["size"]),
                "elapsed_s": _number(row["elapsed_s"], positive=True),
                "peak_memory_bytes": _number(
                    row["peak_memory_bytes"], nonnegative=True
                ),
            }
        elif set(row) != {"id", "status"}:
            raise BenchmarkRefused("unresolved_reference_shape")
    if type(models) is not list or not models:
        raise BenchmarkRefused("model_roster")
    seen = set()
    results = []
    for model in models:
        if (
            type(model) is not dict
            or set(model)
            != {
                "artifact_digest",
                "job_digest",
                "train_digest",
                "build_seconds",
                "cases",
            }
            or type(model["artifact_digest"]) is not str
            or not model["artifact_digest"]
            or model["artifact_digest"] in seen
        ):
            raise BenchmarkRefused("model_roster")
        if model["job_digest"] != registration["job_digest"]:
            raise BenchmarkRefused("model_job_identity")
        if model["train_digest"] != registration["train_digest"]:
            raise BenchmarkRefused("model_train_identity")
        seen.add(model["artifact_digest"])
        build_seconds = _number(model["build_seconds"], nonnegative=True)
        measured = _case_map(model["cases"], roster, "model_case_roster")
        by_role = {}
        for role in sorted({c["role"] for c in registration["cases"]}):
            selected = [c for c in registration["cases"] if c["role"] == role]
            counts = {
                "resolved": 0,
                "reference_unresolved": 0,
                "reference_infra": 0,
                "candidate_invalid": 0,
                "candidate_infra": 0,
                "scientific_inadmissible": 0,
            }
            gate_failures = {gate: 0 for gate in registration["mandatory_gates"]}
            phase_seconds = {
                phase: 0.0
                for phase in ("preprocess", "export", "inference", "postprocess")
            }
            errors, weights, solver_times, model_times, memories = [], [], [], [], []
            for case in selected:
                cid = case["id"]
                ref_status = refs[cid]["status"]
                if ref_status != "RESOLVED":
                    counts[
                        (
                            "reference_infra"
                            if ref_status == "FAILED_INFRA"
                            else "reference_unresolved"
                        )
                    ] += 1
                    continue
                row = measured[cid]
                status = row.get("status")
                if status == "FAILED_INFRA":
                    if set(row) != {"id", "status"}:
                        raise BenchmarkRefused("model_infra_shape")
                    counts["candidate_infra"] += 1
                    continue
                if status == "INVALID":
                    if set(row) != {"id", "status"}:
                        raise BenchmarkRefused("model_invalid_shape")
                    counts["candidate_invalid"] += 1
                    continue
                if status != "OK" or set(row) != {
                    "id",
                    "status",
                    "source",
                    "outputs",
                    "gates",
                    "timing_s",
                    "peak_memory_bytes",
                }:
                    raise BenchmarkRefused("model_measurement_shape")
                if row["source"] != "MEASURED_INFERENCE_RUN":
                    raise BenchmarkRefused("model_measurement_required")
                try:
                    prediction = _outputs(
                        row["outputs"], registration["output"]["size"]
                    )
                except BenchmarkRefused:
                    counts["candidate_invalid"] += 1
                    continue
                if (
                    type(row["gates"]) is not dict
                    or set(row["gates"]) != set(registration["mandatory_gates"])
                    or any(type(v) is not bool for v in row["gates"].values())
                ):
                    raise BenchmarkRefused("mandatory_gate_measurement")
                timing = row["timing_s"]
                if type(timing) is not dict or set(timing) != {
                    "preprocess",
                    "export",
                    "inference",
                    "postprocess",
                }:
                    raise BenchmarkRefused("complete_query_timing")
                total = _sum(_number(v, nonnegative=True) for v in timing.values())
                if total <= 0:
                    raise BenchmarkRefused("complete_query_timing")
                peak = _number(row["peak_memory_bytes"], nonnegative=True)
                for gate, passed in row["gates"].items():
                    gate_failures[gate] += not passed
                if any(not passed for passed in row["gates"].values()):
                    counts["scientific_inadmissible"] += 1
                reference = reference_rows[cid]
                try:
                    case_error = statistics.fmean(
                        _derived(abs(a - b))
                        for a, b in zip(prediction, reference["outputs"], strict=True)
                    )
                except OverflowError as exc:
                    raise BenchmarkRefused("derived_nonfinite") from exc
                errors.append(_derived(case_error))
                weights.append(float(case["weight"]))
                solver_times.append(reference["elapsed_s"])
                model_times.append(total)
                for phase, elapsed in timing.items():
                    phase_seconds[phase] = _derived(phase_seconds[phase] + elapsed)
                memories.append(peak)
                counts["resolved"] += 1
            complete = counts["resolved"] == len(selected)
            mandatory_gates_pass = complete and counts["scientific_inadmissible"] == 0
            status = measurement_status(counts)
            solver_total = _sum(solver_times) if complete else None
            model_total = _sum(model_times) if complete else None
            mean_error = (
                _derived(
                    _sum(w * e for w, e in zip(weights, errors, strict=True))
                    / _sum(weights)
                )
                if complete
                else None
            )
            by_role[role] = {
                "status": status,
                "mandatory_gates_pass": mandatory_gates_pass,
                "attempted": len(selected),
                "counts": counts,
                "gate_failures": gate_failures,
                "mean_absolute_error": mean_error,
                "solver_seconds": solver_total,
                "model_seconds": model_total,
                "solver_query_latency": (
                    _latency_distribution(solver_times) if complete else None
                ),
                "model_query_latency": (
                    _latency_distribution(model_times) if complete else None
                ),
                "model_phase_seconds": phase_seconds if complete else None,
                "paired_speedup": (
                    _derived(solver_total / model_total) if complete else None
                ),
                "observed_serial_queries_per_second": (
                    _derived(len(selected) / model_total) if complete else None
                ),
                "model_peak_memory_bytes": max(memories) if complete else None,
                "solver_peak_memory_bytes": (
                    max(reference_rows[c["id"]]["peak_memory_bytes"] for c in selected)
                    if complete
                    else None
                ),
            }
        results.append(
            {
                "artifact_digest": model["artifact_digest"],
                "build_seconds": build_seconds,
                "by_role": by_role,
            }
        )
    eligible_p = [
        row
        for row in results
        if row["by_role"]["P"]["status"] == "MEASURED_DEVELOPMENT"
    ]
    for row in results:
        row["pareto_p"] = (
            None
            if row not in eligible_p
            else not any(
                other is not row
                and other["by_role"]["P"]["mean_absolute_error"]
                <= row["by_role"]["P"]["mean_absolute_error"]
                and other["by_role"]["P"]["model_seconds"]
                <= row["by_role"]["P"]["model_seconds"]
                and (
                    other["by_role"]["P"]["mean_absolute_error"]
                    < row["by_role"]["P"]["mean_absolute_error"]
                    or other["by_role"]["P"]["model_seconds"]
                    < row["by_role"]["P"]["model_seconds"]
                )
                for other in eligible_p
            )
        )
    result = {
        "schema": RESULT_SCHEMA,
        "scope": registration["scope"],
        "challenge": registration["challenge"],
        "output": {
            key: registration["output"][key] for key in ("quantity", "unit", "metric")
        },
        "registration_digest": registration["registration_digest"],
        "ranking": None,
        "models": results,
    }
    if score_pack is not None:
        from carbon.scoring.engine import ScoreEngine

        result["scoring"] = ScoreEngine.score_solver_benchmark_v2(result, score_pack)
    return result
