"""Closed DEVELOPMENT question and budget inputs; no scientific defaults."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from carbon.design_search.budget_registration import BudgetCap
from carbon.product.envelope_guard import configuration as data

QUESTION_SCHEMA = "carbon.product.assistant-question.v1"
BUDGET_SCHEMA = "carbon.product.assistant-budget.v1"
REGRET_SCHEMA = "carbon.product.assistant-regret-evidence.v1"


class AssistantConfigurationError(ValueError):
    """Fixed refusal codes, with no source or exception detail."""


def require(condition, code):
    if not condition:
        raise AssistantConfigurationError(code)


def checked(function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except data.GuardConfigurationError as error:
        raise AssistantConfigurationError(str(error)) from None


def snapshot(value):
    return checked(data.snapshot, value)


def number(value, *, nonnegative=False):
    return checked(data.number, value, nonnegative=nonnegative)


def closed(value, fields):
    return checked(data.closed, value, fields)


def digest(value):
    return checked(data.digest, value)


def cost(value):
    closed(value, {"wall_s", "core_s"})
    return {k: number(v, nonnegative=True) for k, v in value.items()}


def question(raw):
    q = snapshot(raw)
    closed(
        q,
        {
            "schema",
            "scope",
            "version",
            "basis",
            "authority_ref",
            "question_id",
            "population_ref",
            "proposal_ref",
            "weighting_ref",
            "measurement_id",
            "measurement_digest",
            "objective",
            "constraints",
            "units",
            "actions",
            "k",
            "search_policy",
        },
    )
    require(
        q["schema"] == QUESTION_SCHEMA and q["scope"] == "DEVELOPMENT",
        "development_question_required",
    )
    require(
        q["basis"] in ("SYNTHETIC_FIXTURE", "REGISTERED_DEVELOPMENT"),
        "question_basis_required",
    )
    for key in ("version", "question_id", "measurement_id"):
        checked(data.token, q[key])
    for key in (
        "population_ref",
        "proposal_ref",
        "weighting_ref",
        "measurement_digest",
    ):
        checked(data.sha, q[key])
    if q["authority_ref"] is not None:
        checked(data.sha, q["authority_ref"])
    require(
        q["search_policy"] == "FINITE_BANK_DECLARED_ORDER_V1",
        "unsupported_search_policy",
    )
    closed(q["objective"], {"direction", "unit"})
    require(
        q["objective"]["direction"] in ("min", "max"), "objective_direction_required"
    )
    checked(data.unit, q["objective"]["unit"])
    require(
        type(q["units"]) is dict and 1 <= len(q["units"]) <= 16, "input_units_required"
    )
    for name, unit in q["units"].items():
        checked(data.token, name)
        checked(data.unit, unit)
    constraints = q["constraints"]
    require(
        type(constraints) is list and 1 <= len(constraints) <= 16,
        "constraints_required",
    )
    seen = set()
    for c in constraints:
        closed(c, {"id", "relation", "limit", "unit", "reference_band"})
        checked(data.token, c["id"])
        require(c["id"] not in seen and c["id"] != "objective", "duplicate_constraint")
        seen.add(c["id"])
        require(c["relation"] in ("le", "ge"), "constraint_relation_required")
        checked(data.unit, c["unit"])
        if c["limit"] is not None:
            c["limit"] = number(c["limit"])
        if c["reference_band"] is not None:
            c["reference_band"] = number(c["reference_band"], nonnegative=True)
    actions = q["actions"]
    require(
        type(actions) is list and 1 <= len(actions) <= 256,
        "bounded_action_bank_required",
    )
    seen, queries = set(), set()
    for a in actions:
        closed(a, {"id", "query"})
        checked(data.token, a["id"])
        closed(a["query"], q["units"])
        a["query"] = {k: number(v) for k, v in a["query"].items()}
        query_hash = digest(a["query"])
        require(a["id"] not in seen and query_hash not in queries, "duplicate_action")
        seen.add(a["id"])
        queries.add(query_hash)
    checked(data.count, q["k"], 1, len(actions))
    return q


def budget(raw):
    b = snapshot(raw)
    closed(
        b,
        {
            "schema",
            "scope",
            "version",
            "basis",
            "authority_ref",
            "cap",
            "max_guard_queries",
            "max_model_calls",
            "guard_bound",
            "reference_bound",
            "startup_cost",
        },
    )
    require(
        b["schema"] == BUDGET_SCHEMA and b["scope"] == "DEVELOPMENT",
        "development_budget_required",
    )
    require(
        b["basis"]
        in ("SYNTHETIC_FIXTURE", "MEASURED_DEVELOPMENT", "DEVELOPMENT_ESTIMATE"),
        "budget_basis_required",
    )
    checked(data.token, b["version"])
    if b["authority_ref"] is not None:
        checked(data.sha, b["authority_ref"])
    closed(b["cap"], {"solver_evaluations", "wall_s", "core_s"})
    checked(data.count, b["cap"]["solver_evaluations"], 1, 2048)
    for key in ("wall_s", "core_s"):
        b["cap"][key] = number(b["cap"][key], nonnegative=True)
        require(b["cap"][key] > 0, "positive_budget_required")
    cap = BudgetCap(**b["cap"])
    checked(data.count, b["max_guard_queries"], 1, 2048)
    checked(data.count, b["max_model_calls"], 1, 524288)
    for key in ("guard_bound", "reference_bound", "startup_cost"):
        b[key] = cost(b[key])
    require(
        all(
            v > 0 for key in ("guard_bound", "reference_bound") for v in b[key].values()
        ),
        "positive_call_bounds_required",
    )
    return b, cap


@dataclass(frozen=True)
class Measurement:
    objective: float | None
    values: dict
    units: dict


@dataclass(frozen=True)
class MeasurementBinding:
    measurement_id: str
    code_digest: str
    measure: Callable

    def __post_init__(self):
        checked(data.token, self.measurement_id)
        checked(data.sha, self.code_digest)
        require(callable(self.measure), "trusted_measurement_callable_required")


@dataclass(frozen=True)
class ReferenceObservation:
    status: str
    prediction: object
    query_digest: str
    image_digest: str
    receipt_digest: str


@dataclass(frozen=True)
class ReferenceBinding:
    image_digest: str
    record_digest: str
    runtime_digest: str
    kind: str
    status: str
    solve: Callable

    def __post_init__(self):
        for key in ("image_digest", "record_digest", "runtime_digest"):
            checked(data.sha, getattr(self, key))
        require(
            self.kind
            in ("SYNTHETIC_FIXTURE", "TRUSTED_IN_PROCESS", "PUBLIC_RECORD_REPLAY"),
            "reference_kind_required",
        )
        require(
            self.status
            in (
                "READY",
                "SOLVER_NOT_ACCEPTED",
                "UNRESOLVED",
                "FAILED_REFERENCE",
                "FAILED_INFRA",
            ),
            "reference_status_required",
        )
        require(callable(self.solve), "trusted_reference_callable_required")


def measure(binding, q, outputs, *, reference=False):
    m = binding.measure(outputs)
    require(type(m) is Measurement, "nominal_measurement_required")
    ids = {c["id"] for c in q["constraints"]}
    closed(m.values, ids)
    closed(m.units, {"objective", *ids})
    expected_units = {
        "objective": q["objective"]["unit"],
        **{c["id"]: c["unit"] for c in q["constraints"]},
    }
    require(m.units == expected_units, "measurement_units_mismatch")
    objective = None if m.objective is None else number(m.objective)
    values = {k: number(v) for k, v in m.values.items()}
    outcomes = {}
    for c in q["constraints"]:
        if c["limit"] is None or (reference and c["reference_band"] is None):
            outcomes[c["id"]] = "UNRESOLVED"
            continue
        distance = (
            (c["limit"] - values[c["id"]])
            if c["relation"] == "le"
            else (values[c["id"]] - c["limit"])
        )
        require(abs(distance) != float("inf"), "derived_measurement_nonfinite")
        band = c["reference_band"] if reference else 0.0
        outcomes[c["id"]] = (
            "PASS"
            if distance >= 0 and band == 0
            else (
                "PASS"
                if distance > band
                else "FAIL" if distance < -band else "UNRESOLVED"
            )
        )
    status = (
        "INFEASIBLE"
        if "FAIL" in outcomes.values()
        else (
            "UNRESOLVED"
            if objective is None or "UNRESOLVED" in outcomes.values()
            else "FEASIBLE"
        )
    )
    return {
        "status": status,
        "objective": objective,
        "values": values,
        "checks": outcomes,
    }


def regret_evidence(raw, pins):
    if raw is None:
        return {
            "value": None,
            "interval": None,
            "status": "GAP",
            "reason": "MATCHED_INDEPENDENT_ASSESSMENT_MISSING",
        }
    r = snapshot(raw)
    closed(
        r,
        {
            "schema",
            "scope",
            "role",
            "pins",
            "source_digest",
            "sample_count",
            "value",
            "interval",
            "unit",
            "method",
            "confidence",
        },
    )
    require(
        r["schema"] == REGRET_SCHEMA
        and r["scope"] == "DEVELOPMENT"
        and r["role"] == "INDEPENDENT_ASSESSMENT",
        "independent_regret_evidence_required",
    )
    require(r["pins"] == pins, "regret_identity_mismatch")
    checked(data.sha, r["source_digest"])
    checked(data.count, r["sample_count"], 1)
    checked(data.token, r["method"])
    value = number(r["value"], nonnegative=True)
    require(
        type(r["interval"]) is list and len(r["interval"]) == 2,
        "regret_interval_required",
    )
    low, high = [number(v, nonnegative=True) for v in r["interval"]]
    require(
        low <= value <= high and 0 < number(r["confidence"]) < 1,
        "regret_interval_invalid",
    )
    require(r["unit"] == pins["objective_unit"], "regret_units_mismatch")
    return {
        **r,
        "value": value,
        "interval": [low, high],
        "status": "RECORDED_ESTIMATE",
        "basis": "HOST_SUPPLIED_INDEPENDENT_ASSESSMENT_ASSERTION",
    }
