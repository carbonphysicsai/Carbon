"""Pure prospective dual A/D candidates, shared by workbench and validator.

Trusted producers supply registered measurements and mandatory gate outcomes.
This module runs no model/solver and cannot qualify reference applicability,
problem independence or measurement provenance. Legacy scores are unchanged.
"""

from __future__ import annotations

import hashlib
import json
import math

PACK_SCHEMA = "carbon.scoring.dual-benchmark-pack.v4"
INPUT_SCHEMA = "carbon.scoring.dual-benchmark-input.v1"
RESULT_SCHEMA = "carbon.scoring.dual-benchmark-score.v4"
_SCOPES = {"PUBLIC_DEVELOPMENT", "SYNTHETIC_DEVELOPMENT"}
_STATES = {
    "RESOLVED",
    "REFERENCE_UNRESOLVED",
    "REFERENCE_INFRA",
    "CANDIDATE_INVALID",
    "CANDIDATE_INFRA",
    "NOT_MEASURED",
}
_GATES = {
    "PASS",
    "FAIL",
    "REFERENCE_UNRESOLVED",
    "REFERENCE_INFRA",
    "CANDIDATE_INFRA",
    "NOT_MEASURED",
}
_DECISIONS = {
    "VERIFIED_FEASIBLE",
    "MISSED_OPPORTUNITY",
    "NONE_FEASIBLE",
    "REFERENCE_UNRESOLVED",
    "NOT_MEASURED",
    # A pool-graded version's outcome (`pool_exam.OUTCOME_POOL`): its D is the pool exam's own min(V, C), final
    # before this reduction, so the pack's decision policy names no cap for it (a missing policy entry is neither
    # a cap nor an ineligibility).
    "POOL_GRADED",
}


class DualScoreRefused(ValueError):
    """Malformed or mismatched candidate contract/evidence."""


def _shape(value, keys, code):
    if type(value) is not dict or set(value) != set(keys):
        raise DualScoreRefused(code)


def _number(value):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _text(value):
    return type(value) is str and bool(value)


def _sha(value):
    return (
        type(value) is str
        and value.startswith("sha256:")
        and len(value) == 71
        and all(c in "0123456789abcdef" for c in value[7:])
    )


def _digest(body):
    try:
        raw = json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError, RecursionError, UnicodeError) as exc:
        raise DualScoreRefused("noncanonical_input") from exc
    return "sha256:" + hashlib.sha256(raw.encode()).hexdigest()


def register_pack(body):
    """Bind explicit candidate values; registration is not scientific adoption."""
    _shape(
        body,
        {
            "schema",
            "scope",
            "challenge",
            "physics_contract_digest",
            "measurement_contract_digest",
            "hard_gates",
            "legs",
            "value_weight",
            "combination",
            "decision_policy",
        },
        "pack_shape",
    )
    if (
        body["schema"] != PACK_SCHEMA
        or not _text(body["scope"])
        or body["scope"] not in _SCOPES
        or not _text(body["challenge"])
        or not all(
            _sha(body[k])
            for k in ("physics_contract_digest", "measurement_contract_digest")
        )
    ):
        raise DualScoreRefused("pack_identity")
    gates = body["hard_gates"]
    if (
        type(gates) is not list
        or not gates
        or not all(_text(g) for g in gates)
        or len(gates) != len(set(gates))
    ):
        raise DualScoreRefused("pack_gates")
    _shape(body["legs"], {"A", "D"}, "pack_legs")
    seen = set()
    for leg in body["legs"].values():
        _shape(leg, {"components", "minimum"}, "pack_leg")
        minimum = leg["minimum"]
        if minimum is not None and (not _number(minimum) or not 0 <= minimum <= 1):
            raise DualScoreRefused("pack_minimum")
        components = leg["components"]
        if type(components) is not list or not components:
            raise DualScoreRefused("pack_components")
        for c in components:
            _shape(
                c, {"metric", "unit", "transform", "scale", "weight"}, "pack_component"
            )
            if (
                not _text(c["metric"])
                or c["metric"] in seen
                or not _text(c["unit"])
                or not _number(c["weight"])
                or not 0 < c["weight"] <= 1
            ):
                raise DualScoreRefused("pack_component_identity")
            seen.add(c["metric"])
            if c["transform"] == "reciprocal_loss":
                if not _number(c["scale"]) or c["scale"] <= 0:
                    raise DualScoreRefused("pack_scale")
            elif c["transform"] != "unit_benefit" or c["scale"] is not None:
                raise DualScoreRefused("pack_transform")
        if not math.isclose(
            math.fsum(c["weight"] for c in components), 1, rel_tol=0, abs_tol=1e-12
        ):
            raise DualScoreRefused("pack_component_weights")
    weight = body["value_weight"]
    if not _number(weight) or not 0 <= weight <= 1:
        raise DualScoreRefused("pack_value_weight")
    if body["combination"] == "bottleneck_capped_geometric":
        if not 0 < weight < 1:
            raise DualScoreRefused("joint_weight_requires_both_legs")
    elif body["combination"] != "weighted_arithmetic_mean":
        raise DualScoreRefused("pack_combination")
    _shape(
        body["decision_policy"],
        {"VERIFIED_FEASIBLE", "MISSED_OPPORTUNITY", "NONE_FEASIBLE"},
        "pack_decision_policy",
    )
    for policy in body["decision_policy"].values():
        _shape(policy, {"eligible", "maximum_D"}, "pack_outcome_policy")
        if (
            type(policy["eligible"]) is not bool
            or not _number(policy["maximum_D"])
            or not 0 <= policy["maximum_D"] <= 1
        ):
            raise DualScoreRefused("pack_outcome_policy")
    # Return a detached canonical copy, so a caller cannot mutate nested inputs.
    return json.loads(
        json.dumps({**body, "pack_digest": _digest(body)}, allow_nan=False)
    )


def _normalize(value, component):
    if not _number(value) or value < 0:
        return None
    if component["transform"] == "unit_benefit":
        return float(value) if value <= 1 else None
    scale = component["scale"]
    # Avoid overflow in value/scale or value+scale for finite extreme inputs.
    ratio = value / scale if value <= scale else scale / value
    return 1 / (1 + ratio) if value <= scale else ratio / (1 + ratio)


def score(benchmark, pack):
    """Reduce trusted A/D measurements with common reference deferral, no I/O."""
    if type(pack) is not dict or "pack_digest" not in pack:
        raise DualScoreRefused("pack_digest")
    checked = register_pack({k: v for k, v in pack.items() if k != "pack_digest"})
    if checked != pack:
        raise DualScoreRefused("pack_digest")
    _shape(
        benchmark,
        {
            "schema",
            "scope",
            "challenge",
            "physics_contract_digest",
            "measurement_contract_digest",
            "population_role",
            "common_mask_digest",
            "models",
        },
        "benchmark_shape",
    )
    if (
        benchmark["schema"] != INPUT_SCHEMA
        or any(
            benchmark[k] != pack[k]
            for k in (
                "scope",
                "challenge",
                "physics_contract_digest",
                "measurement_contract_digest",
            )
        )
        or not _text(benchmark["population_role"])
        or benchmark["population_role"] not in {"P", "Q"}
        or not _sha(benchmark["common_mask_digest"])
    ):
        raise DualScoreRefused("benchmark_binding")
    models = benchmark["models"]
    if type(models) is not list or not models:
        raise DualScoreRefused("benchmark_models")
    components = {
        c["metric"]: c for leg in pack["legs"].values() for c in leg["components"]
    }
    identities, states = set(), []
    for model in models:
        _shape(
            model,
            {"artifact_digest", "gates", "measurements", "decision_outcome"},
            "model_shape",
        )
        identity = model["artifact_digest"]
        if not _sha(identity) or identity in identities:
            raise DualScoreRefused("model_identity")
        identities.add(identity)
        _shape(model["gates"], pack["hard_gates"], "model_gates")
        if any(type(s) is not str or s not in _GATES for s in model["gates"].values()):
            raise DualScoreRefused("model_gate_status")
        _shape(model["measurements"], components, "model_measurements")
        if (
            not _text(model["decision_outcome"])
            or model["decision_outcome"] not in _DECISIONS
        ):
            raise DualScoreRefused("model_decision")
        states.extend(model["gates"].values())
        if model["decision_outcome"] == "REFERENCE_UNRESOLVED":
            states.append("REFERENCE_UNRESOLVED")
        for name, measurement in model["measurements"].items():
            _shape(measurement, {"status", "value", "unit"}, "measurement_shape")
            if (
                type(measurement["status"]) is not str
                or measurement["status"] not in _STATES
                or measurement["unit"] != components[name]["unit"]
            ):
                raise DualScoreRefused("measurement_contract")
            if measurement["status"] != "RESOLVED" and measurement["value"] is not None:
                raise DualScoreRefused("unresolved_measurement_value")
            states.append(measurement["status"])
    common = (
        "FAILED_INFRA"
        if "REFERENCE_INFRA" in states
        else "INDETERMINATE_EVIDENCE" if "REFERENCE_UNRESOLVED" in states else None
    )
    rows, digest_models = [], []
    for model in models:
        metrics = model["measurements"]
        local = set(model["gates"].values()) | {m["status"] for m in metrics.values()}
        if model["decision_outcome"] == "NOT_MEASURED":
            local.add("NOT_MEASURED")
        normalized = {
            name: (
                _normalize(m["value"], components[name])
                if m["status"] == "RESOLVED"
                else None
            )
            for name, m in metrics.items()
        }
        legs = {
            name: (
                None
                if any(normalized[c["metric"]] is None for c in leg["components"])
                else min(
                    1.0,
                    math.fsum(
                        c["weight"] * normalized[c["metric"]] for c in leg["components"]
                    ),
                )
            )
            for name, leg in pack["legs"].items()
        }
        if model["decision_outcome"] == "NOT_MEASURED":
            legs["D"] = None
        measured_legs = dict(legs)
        policy = pack["decision_policy"].get(model["decision_outcome"])
        if policy is not None and legs["D"] is not None:
            legs["D"] = min(legs["D"], policy["maximum_D"])
        if common:
            status = common
        elif "CANDIDATE_INFRA" in local:
            status = "FAILED_INFRA"
        elif "NOT_MEASURED" in local:
            status = "INDETERMINATE_EVIDENCE"
        elif "CANDIDATE_INVALID" in local or any(
            v is None for v in normalized.values()
        ):
            status = "CANDIDATE_INVALID"
        elif "FAIL" in local:
            status = "MANDATORY_GATE_FAILED"
        elif policy is not None and not policy["eligible"]:
            status = "DECISION_OUTCOME_INELIGIBLE"
        elif any(
            leg["minimum"] is not None and legs[name] < leg["minimum"]
            for name, leg in pack["legs"].items()
        ):
            status = "REQUIRED_LEG_MINIMUM_FAILED"
        else:
            status = "SCORED_DEVELOPMENT_CANDIDATE"
        total = None
        if status == "SCORED_DEVELOPMENT_CANDIDATE":
            a, d, w = legs["A"], legs["D"], pack["value_weight"]
            if pack["combination"] == "weighted_arithmetic_mean":
                total = (1 - w) * a + w * d
            else:
                total = (
                    0.0
                    if a == 0 or d == 0
                    else min(a, d) * math.exp((1 - w) * math.log(a) + w * math.log(d))
                )
            if benchmark["population_role"] == "Q":
                status, total = "DIAGNOSTIC_Q", None
        rows.append(
            {
                "artifact_digest": model["artifact_digest"],
                "status": status,
                "gates": dict(model["gates"]),
                "components": normalized,
                "legs": legs,
                "measured_legs_before_outcome_policy": measured_legs,
                "decision_outcome": model["decision_outcome"],
                "score": total,
            }
        )
        # Hash the typed measurement view, not unencodable NaN/Inf or hostile
        # nested candidate values. Original prediction bytes remain producer
        # evidence; this digest does not purport to be their raw-byte hash.
        typed_metrics = {}
        for name, measurement in metrics.items():
            if measurement["status"] == "RESOLVED" and not _number(
                measurement["value"]
            ):
                typed_metrics[name] = {
                    "status": "CANDIDATE_INVALID",
                    "value": None,
                    "unit": measurement["unit"],
                    "rejected_value_type": type(measurement["value"]).__name__,
                }
            else:
                typed_metrics[name] = dict(measurement)
        digest_models.append({**model, "measurements": typed_metrics})
    return {
        "schema": RESULT_SCHEMA,
        "scope": pack["scope"],
        "challenge": pack["challenge"],
        "pack_digest": pack["pack_digest"],
        "evidence_digest": _digest({**benchmark, "models": digest_models}),
        "evidence_digest_basis": "CANONICAL_TYPED_MEASUREMENTS_NOT_ORIGINAL_PREDICTION_BYTES",
        "common_mask_digest": benchmark["common_mask_digest"],
        "population_role": benchmark["population_role"],
        "models": rows,
        "combination": pack["combination"],
        "value_weight": pack["value_weight"],
        "weight_interpretation": (
            "ARITHMETIC_VALUE_COEFFICIENT"
            if pack["combination"] == "weighted_arithmetic_mean"
            else "GEOMETRIC_EMPHASIS_NOT_LITERAL_TOTAL_SHARE"
        ),
        "official_score": False,
    }
