"""Measured bounded DEVELOPMENT search; model optimism never verifies a pick."""

from __future__ import annotations

import json
import time
from collections.abc import Mapping
from dataclasses import dataclass

from carbon.challenge_validator import validity
from carbon.design_search.budget_registration import (
    BudgetLedger,
    BudgetRegistrationError,
)
from carbon.product.envelope_guard import (
    EnvelopeGuard,
    ModelBinding,
    Prediction,
    development_pins,
)
from carbon.product.envelope_guard import configuration as guard_data

from . import configuration as cfg

RESULT_SCHEMA = "carbon.product.assistant-result.v1"
SELECTOR = "carbon.product.assistant-finite-bank.v1"


def _plain(value):
    if isinstance(value, Mapping):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    return value


def _now():
    return time.perf_counter(), time.process_time()


def _elapsed(start, end):
    return {
        k: cfg.number(b - a, nonnegative=True)
        for k, a, b in zip(("wall_s", "core_s"), start, end)
    }


def _replay(body):
    # Measured timing can alter where a budget stops, but never the identity
    # of an otherwise identical decision. Counts and overrun status are retained.
    return {k: v for k, v in body.items() if k not in ("spent", "audit_digest")}


@dataclass(frozen=True, init=False)
class SearchResult:
    """Immutable DEVELOPMENT result; copies cannot mutate a later assessment."""

    _body: Mapping

    def __init__(self, body):
        encoded = cfg.checked(guard_data.canonical, body)
        cfg.require(len(encoded) <= 8_000_000, "result_size_limit")
        value = json.loads(encoded)
        cfg.require(
            value.get("schema") == RESULT_SCHEMA
            and value.get("scope") == "DEVELOPMENT",
            "development_result_required",
        )
        cfg.require(
            value.get("audit_digest") == cfg.digest(_replay(value)),
            "result_digest_mismatch",
        )
        cfg.require(
            value.get("qualification_claim") is False
            and value.get("production_authority") is False
            and value.get("independent_pick_verification_required") is True,
            "result_authority_invalid",
        )
        object.__setattr__(self, "_body", guard_data.freeze(value))

    def to_dict(self):
        return _plain(self._body)


class _Meter:
    """Wrap the native ledger; retain actual costs even on a bound overrun."""

    def __init__(self, budget, cap, startup):
        self.budget, self.ledger = budget, BudgetLedger(cap)
        self.last = _now()
        self.excess = {"wall_s": 0.0, "core_s": 0.0}
        self.overrun = False
        self.queries = self.model_calls = 0
        self.events = []
        self._overhead(startup)

    def _overhead(self, amount):
        if not self.ledger.charge_overhead(amount):
            self.excess = {k: self.excess[k] + amount[k] for k in amount}
            self.overrun = True

    def sync(self):
        now = _now()
        self._overhead(_elapsed(self.last, now))
        self.last = now
        return not self.overrun

    def call(self, function, bound, *, reference=False):
        if not self.sync():
            return "BUDGET_EXCEEDED", None
        # The native ledger's admission predicate is reused without charging
        # an invented solve cost. Actual cost is recorded after the trusted call.
        if not self.ledger._fits(bound, solver_attempt=reference):
            return "BUDGET_DEFERRED", None
        start = _now()
        status, value = "OK", None
        try:
            value = function()
        # Trusted adapter failures are infrastructure; exception text is private.
        except Exception:  # noqa: BLE001
            status = "FAILED_INFRA"
        end = _now()
        amount = _elapsed(start, end)
        if reference:
            # Timer resolution can be zero; a positive one-nanosecond accounting
            # quantum is engineering bookkeeping, not a scientific tolerance.
            amount = {k: max(v, 1e-9) for k, v in amount.items()}
            try:
                self.ledger.charge_solver_attempt(bound, amount)
            except BudgetRegistrationError:
                self.overrun = True
                status = "PLANNING_BOUND_EXCEEDED"
        else:
            self._overhead(amount)
            if any(amount[k] > bound[k] for k in amount):
                self.overrun = True
                status = "PLANNING_BOUND_EXCEEDED"
        # Include dispatch and accounting overhead in the next sync.
        self._overhead(_elapsed(self.last, start))
        self.last = end
        self.events.append(
            {"kind": "REFERENCE" if reference else "GUARD", "status": status}
        )
        return status, value

    def spent(self):
        self.sync()
        return {
            "wall_s": self.ledger.wall_s + self.excess["wall_s"],
            "core_s": self.ledger.core_s + self.excess["core_s"],
            "reference_calls": self.ledger.solver_evaluations,
            "guard_queries": self.queries,
            "model_calls": self.model_calls,
            "budget_or_bound_exceeded": self.overrun,
        }


def _rank(q, rows, field):
    sign = 1 if q["objective"]["direction"] == "min" else -1
    return sorted(
        [r for r in rows if r.get(field, {}).get("status") == "FEASIBLE"],
        key=lambda r: (sign * r[field]["objective"], r["id"]),
    )


def _observe(reference, measurement, q, query, meter, bound, outputs_spec):
    query_hash = cfg.digest({"query": query, "units": q["units"]})
    status, value = meter.call(
        lambda: reference.solve(dict(query)), bound, reference=True
    )
    if status != "OK":
        return {"status": status, "candidate_failure": False}
    try:
        cfg.require(
            type(value) is cfg.ReferenceObservation,
            "nominal_reference_observation_required",
        )
        cfg.require(
            value.query_digest == query_hash
            and value.image_digest == reference.image_digest,
            "reference_observation_identity_mismatch",
        )
        cfg.checked(guard_data.sha, value.receipt_digest)
        cfg.require(
            value.status in ("OK", "UNRESOLVED", "FAILED_REFERENCE", "FAILED_INFRA"),
            "reference_observation_status_invalid",
        )
        if value.status != "OK":
            cfg.require(value.prediction is None, "failed_reference_has_prediction")
            return {
                "status": value.status,
                "receipt_digest": value.receipt_digest,
                "candidate_failure": False,
            }
        cfg.require(
            type(value.prediction) is Prediction,
            "nominal_reference_prediction_required",
        )
        cfg.require(
            value.prediction.intervals is None, "reference_intervals_not_supported"
        )
        cfg.closed(value.prediction.outputs, outputs_spec)
        outputs = {}
        for name, description in outputs_spec.items():
            vector = value.prediction.outputs[name]
            vector = [vector] if type(vector) in (int, float) else vector
            cfg.require(
                type(vector) in (list, tuple) and len(vector) == description["length"],
                "reference_output_shape_invalid",
            )
            outputs[name] = [cfg.number(v) for v in vector]
        observed = cfg.measure(measurement, q, outputs, reference=True)
        return {
            **observed,
            "receipt_digest": value.receipt_digest,
            "query_digest": query_hash,
            "image_digest": value.image_digest,
            "candidate_failure": False,
        }
    except (
        cfg.AssistantConfigurationError,
        KeyError,
        TypeError,
        ValueError,
        OverflowError,
    ):
        return {
            "status": "UNRESOLVED",
            "reason": "REFERENCE_OBSERVATION_INVALID",
            "candidate_failure": False,
        }
    # Trusted measurement failures are infrastructure, never candidate science.
    except Exception:  # noqa: BLE001
        return {
            "status": "FAILED_INFRA",
            "reason": "REFERENCE_MEASUREMENT_UNAVAILABLE",
            "candidate_failure": False,
        }


class DecisionAssistant:
    """Finite-bank trusted-host search, with separate independent verification."""

    def __init__(
        self, *, question_law, model, guard_inputs, measurement, budget, reference=None
    ):
        started = _now()
        cfg.require(type(model) is ModelBinding, "nominal_model_binding_required")
        cfg.require(
            type(measurement) is cfg.MeasurementBinding,
            "nominal_measurement_binding_required",
        )
        cfg.require(
            reference is None or type(reference) is cfg.ReferenceBinding,
            "nominal_reference_binding_required",
        )
        q = cfg.question(question_law)
        b, cap = cfg.budget(budget)
        cfg.require(
            (measurement.measurement_id, measurement.code_digest)
            == (q["measurement_id"], q["measurement_digest"]),
            "measurement_identity_mismatch",
        )
        cfg.require(
            type(guard_inputs) is dict and "model" not in guard_inputs,
            "guard_inputs_without_model_required",
        )
        try:
            guard = EnvelopeGuard(model=model, **guard_inputs)
            pins = development_pins(
                model=model, **{k: v for k, v in guard_inputs.items() if k != "policy"}
            )
            pins["policy"] = (
                None
                if guard_inputs["policy"] is None
                else guard_data.digest(guard_inputs["policy"])
            )
            units = {
                k: v["unit"] for k, v in guard_inputs["envelope"]["inputs"].items()
            }
            cfg.require(q["units"] == units, "question_guard_units_mismatch")
            policy = guard_inputs["policy"]
            worst_calls = 0 if policy is None else policy["max_model_calls"]
            if policy is not None and policy["basis"] == "SYNTHETIC_FIXTURE":
                cfg.require(
                    q["basis"] == "SYNTHETIC_FIXTURE"
                    and b["basis"] == "SYNTHETIC_FIXTURE",
                    "fixture_guard_scope_mismatch",
                )
            if q["basis"] == "REGISTERED_DEVELOPMENT":
                cfg.require(
                    b["basis"] != "SYNTHETIC_FIXTURE", "fixture_budget_scope_mismatch"
                )
            if reference is not None:
                cfg.require(
                    reference.image_digest == pins["reference_image"]
                    and reference.record_digest == pins["reference_record"],
                    "reference_binding_mismatch",
                )
                if reference.kind == "SYNTHETIC_FIXTURE":
                    cfg.require(
                        q["basis"] == "SYNTHETIC_FIXTURE"
                        and b["basis"] == "SYNTHETIC_FIXTURE",
                        "fixture_reference_scope_mismatch",
                    )
        except guard_data.GuardConfigurationError:
            raise cfg.AssistantConfigurationError(
                "guard_configuration_invalid"
            ) from None
        except (KeyError, TypeError, AttributeError):
            raise cfg.AssistantConfigurationError(
                "assistant_configuration_invalid"
            ) from None
        self._q, self._b = guard_data.freeze(q), guard_data.freeze(b)
        self._cap, self._guard = cap, guard
        self._measurement, self._reference = measurement, reference
        self._outputs = guard_data.freeze(
            cfg.snapshot(guard_inputs["contract"]["outputs"])
        )
        self._reference_envelope = guard_data.freeze(
            guard_data.envelope(guard_inputs["reference_envelope"])
        )
        self._reference_validity = guard_data.declaration(
            guard_inputs["reference_validity"], self._reference_envelope["inputs"]
        )
        self._worst_calls = worst_calls
        self._pins = guard_data.freeze(
            {
                "question_digest": cfg.digest(q),
                "budget_digest": cfg.digest(b),
                "guard": pins,
                "model_artifact": model.artifact_digest,
                "model_runtime": model.runtime_digest,
                "measurement_digest": measurement.code_digest,
                "population_ref": q["population_ref"],
                "proposal_ref": q["proposal_ref"],
                "weighting_ref": q["weighting_ref"],
                "selector_version": SELECTOR,
                "objective_unit": q["objective"]["unit"],
                "reference_runtime": (
                    None if reference is None else reference.runtime_digest
                ),
                "reference_kind": None if reference is None else reference.kind,
                "reference_status": None if reference is None else reference.status,
                "guard_reference_status": (
                    None
                    if guard_inputs["reference"] is None
                    else guard_inputs["reference"]["status"]
                ),
            }
        )
        setup = _elapsed(started, _now())
        self._setup = {k: setup[k] + b["startup_cost"][k] for k in setup}

    @property
    def regret_pins(self):
        return _plain(self._pins)

    def run(self, *, expected_regret_evidence=None):
        q, b = _plain(self._q), _plain(self._b)
        pins = self.regret_pins
        expected = cfg.regret_evidence(expected_regret_evidence, pins)
        meter = _Meter(b, self._cap, self._setup)
        rows, reasons = [], []
        if q["authority_ref"] is None or b["authority_ref"] is None:
            reasons.append("QUESTION_OR_BUDGET_HUMAN_INPUT")
        if self._reference is not None and self._reference.status != "READY":
            reasons.append(self._reference.status)
        for action in q["actions"]:
            row = {
                **action,
                "guard": None,
                "predicted": {"status": "UNRESOLVED"},
                "reference": {"status": "NOT_ASSESSED"},
            }
            rows.append(row)
            if reasons:
                row["search_status"] = "DEFERRED"
                continue
            if (
                meter.queries >= b["max_guard_queries"]
                or meter.model_calls + self._worst_calls > b["max_model_calls"]
            ):
                reasons.append("MODEL_OR_GUARD_BUDGET_EXHAUSTED")
                row["search_status"] = "DEFERRED"
                continue
            status, receipt = meter.call(
                lambda a=action: self._guard.evaluate(a["query"], units=q["units"]),
                b["guard_bound"],
            )
            if status not in ("BUDGET_DEFERRED", "BUDGET_EXCEEDED"):
                meter.queries += 1
                if type(receipt) is dict:
                    meter.model_calls += receipt["probes"]["model_calls"]
            if status != "OK":
                reasons.append(status)
                row["search_status"] = status
                continue
            row["search_status"] = "SEARCHED"
            row["guard"] = {
                k: receipt[k]
                for k in (
                    "schema",
                    "scope",
                    "evidence_basis",
                    "verdict",
                    "reasons",
                    "checks",
                    "decision_digest",
                    "probes",
                    "identities",
                    "law_policy",
                    "b9_policy",
                    "reference",
                    "code_verification",
                    "qualification_claim",
                    "independent_pick_verification_required",
                )
            }
            if receipt["verdict"] != "REFUSE" and receipt["prediction"] is not None:
                try:
                    row["predicted"] = cfg.measure(
                        self._measurement, q, receipt["prediction"]
                    )
                # Trusted measurement failures cannot create a feasible pick.
                except Exception:  # noqa: BLE001
                    row["predicted"] = {
                        "status": "UNRESOLVED",
                        "reason": "MODEL_MEASUREMENT_UNAVAILABLE",
                    }
        provisional = _rank(q, rows, "predicted")[: q["k"]]
        unknown = [
            r
            for r in rows
            if r["guard"] is not None
            and r["guard"]["verdict"] == "VERIFY"
            and r["predicted"]["status"] == "UNRESOLVED"
        ]
        offered = list(provisional)
        for row in unknown:
            if len(offered) < q["k"]:
                offered.append(row)
        plan = sorted(
            offered,
            key=lambda r: (
                0 if r["guard"]["verdict"] == "VERIFY" else 1,
                provisional.index(r) if r in provisional else q["k"],
                r["id"],
            ),
        )
        frozen = {
            "provisional_top_k": [r["id"] for r in provisional],
            "verification_plan": [
                {
                    "id": r["id"],
                    "guard_verdict": r["guard"]["verdict"],
                    "must_verify": True,
                }
                for r in plan
            ],
        }
        commitment = cfg.digest({"pins": pins, "rows": rows, **frozen})
        if not plan:
            reasons.append("NO_PROVISIONAL_CANDIDATE_TO_VERIFY")
        # No reference has been consulted before this immutable commitment.
        if self._reference is None:
            reasons.append("REFERENCE_EXECUTOR_MISSING")
        elif not reasons:
            for row in plan:
                row["reference"] = _observe(
                    self._reference,
                    self._measurement,
                    q,
                    row["query"],
                    meter,
                    b["reference_bound"],
                    _plain(self._outputs),
                )
                if row["reference"]["status"] in (
                    "BUDGET_DEFERRED",
                    "BUDGET_EXCEEDED",
                    "PLANNING_BOUND_EXCEEDED",
                ):
                    reasons.append(row["reference"]["status"])
                    break
        complete = bool(plan) and all(
            r["reference"]["status"] in ("FEASIBLE", "INFEASIBLE") for r in plan
        )
        if (
            self._reference is not None
            and self._reference.kind == "PUBLIC_RECORD_REPLAY"
        ):
            complete = False
            reasons.append("REFERENCE_REPLAY_NOT_FRESH_VERIFICATION")
        verified = _rank(q, plan, "reference")
        recommendation = (
            verified[0]["id"] if complete and verified and not reasons else None
        )
        selected = [r for r in plan if r["predicted"]["status"] == "FEASIBLE"]
        resolved = [
            r
            for r in selected
            if r["reference"]["status"] in ("FEASIBLE", "INFEASIBLE")
        ]
        false_count = sum(r["reference"]["status"] == "INFEASIBLE" for r in resolved)
        spent = meter.spent()
        if spent["budget_or_bound_exceeded"]:
            recommendation = None
            reasons.append("BUDGET_OR_BOUND_EXCEEDED")
        body = {
            "schema": RESULT_SCHEMA,
            "scope": "DEVELOPMENT",
            "basis": q["basis"],
            "status": (
                "REFERENCE_RELATIVE_CHOICE" if recommendation is not None else "ABSTAIN"
            ),
            "reasons": sorted(set(reasons)),
            "pins": pins,
            "candidates": rows,
            **frozen,
            "search_commitment_digest": commitment,
            "search_complete": all(r.get("search_status") == "SEARCHED" for r in rows),
            "verification_complete": complete,
            "recommendation": recommendation,
            "verified_order": (
                [r["id"] for r in verified]
                if self._reference is None
                or self._reference.kind != "PUBLIC_RECORD_REPLAY"
                else []
            ),
            "reference_observation_order": [r["id"] for r in verified],
            "reference_execution_kind": (
                None if self._reference is None else self._reference.kind
            ),
            "expected_regret": expected,
            "realized_regret": {
                "value": None,
                "status": "GAP",
                "reason": "FULL_FINITE_BANK_ASSESSMENT_NOT_RUN",
            },
            "selected_pick_false_feasibility": {
                "selected": len(selected),
                "resolved": len(resolved),
                "unresolved": len(selected) - len(resolved),
                "false_feasible": false_count,
                "fraction_conditional_on_resolved": (
                    None if not resolved else false_count / len(resolved)
                ),
            },
            "spent": spent,
            "budget_events": meter.events,
            "qualification_claim": False,
            "production_authority": False,
            "independent_pick_verification_required": True,
        }
        body["audit_digest"] = cfg.digest(_replay(body))
        body["spent"] = meter.spent()
        if meter.overrun:
            body.update(status="ABSTAIN", recommendation=None)
            body["reasons"] = sorted(
                set(body["reasons"]) | {"BUDGET_OR_BOUND_EXCEEDED"}
            )
        body["audit_digest"] = cfg.digest(_replay(body))
        return SearchResult(body)


def assess_finite_bank(assistant, result, *, reference, budget):
    """Separate post-freeze assessment; its cost never disappears into search.

    The oracle is the complete declared finite bank, not a global optimum or an
    expected-regret population. Failed/unknown observations keep regret null.
    """
    started = _now()
    cfg.require(
        type(assistant) is DecisionAssistant and type(result) is SearchResult,
        "nominal_assistant_result_required",
    )
    cfg.require(
        type(reference) is cfg.ReferenceBinding, "nominal_reference_binding_required"
    )
    body = result.to_dict()
    cfg.require(body["pins"] == assistant.regret_pins, "assessment_result_mismatch")
    pins = body["pins"]["guard"]
    cfg.require(
        reference.image_digest == pins["reference_image"]
        and reference.record_digest == pins["reference_record"],
        "assessment_reference_mismatch",
    )
    b, cap = cfg.budget(budget)
    setup = _elapsed(started, _now())
    meter = _Meter(b, cap, {k: setup[k] + b["startup_cost"][k] for k in setup})
    q = _plain(assistant._q)
    rows = []
    # A new callback cannot remove a hold frozen into the searched workflow.
    # Changed acceptance needs a new configuration/result, not a reassessment
    # of that historical result under silently widened authority.
    holds = [
        state
        for state in (
            body["pins"]["reference_status"],
            body["pins"]["guard_reference_status"],
            reference.status,
        )
        if state is not None and state != "READY"
    ]
    reference_status = holds[0] if holds else reference.status
    if reference.kind == "SYNTHETIC_FIXTURE":
        cfg.require(
            q["basis"] == "SYNTHETIC_FIXTURE" and b["basis"] == "SYNTHETIC_FIXTURE",
            "fixture_reference_scope_mismatch",
        )
    if (
        reference_status == "READY"
        and q["authority_ref"] is not None
        and b["authority_ref"] is not None
    ):
        for action in q["actions"]:
            # KEEP the Guard's immutable declared-use predicate. Registered MMS
            # verification conditions are evidence, not query restrictions.
            if not assistant._guard._reference_scope_matches(action["query"]):
                rows.append(
                    {
                        "id": action["id"],
                        "reference": {
                            "status": "UNRESOLVED",
                            "reason": "REFERENCE_ACCEPTANCE_SCOPE_MISMATCH",
                            "candidate_failure": False,
                        },
                    }
                )
                continue
            declaration = assistant._reference_validity
            supported = all(
                v["low"] <= action["query"][k] <= v["high"]
                for k, v in assistant._reference_envelope["inputs"].items()
            )
            applicable = not isinstance(declaration, validity.Undeclared) and (
                isinstance(declaration, validity.NoPropertyModel)
                or validity.applicability(declaration.models, action["query"]) is None
            )
            if not supported or not applicable:
                rows.append(
                    {
                        "id": action["id"],
                        "reference": {
                            "status": "UNRESOLVED",
                            "reason": "REFERENCE_APPLICABILITY_UNRESOLVED",
                            "candidate_failure": False,
                        },
                    }
                )
                continue
            observed = _observe(
                reference,
                assistant._measurement,
                q,
                action["query"],
                meter,
                b["reference_bound"],
                _plain(assistant._outputs),
            )
            rows.append({"id": action["id"], "reference": observed})
            if observed["status"] in (
                "BUDGET_DEFERRED",
                "BUDGET_EXCEEDED",
                "PLANNING_BOUND_EXCEEDED",
            ):
                break
    complete = len(rows) == len(q["actions"]) and all(
        r["reference"]["status"] in ("FEASIBLE", "INFEASIBLE") for r in rows
    )
    observations_complete = complete
    if reference.kind == "PUBLIC_RECORD_REPLAY":
        complete = False
    ranked = _rank(q, rows, "reference")
    lookup = {r["id"]: r["reference"] for r in rows}
    choice = lookup.get(body["recommendation"])
    value = None
    if complete and ranked and choice is not None and choice["status"] == "FEASIBLE":
        sign = 1 if q["objective"]["direction"] == "min" else -1
        try:
            value = cfg.number(
                max(
                    0.0,
                    sign * (choice["objective"] - ranked[0]["reference"]["objective"]),
                ),
                nonnegative=True,
            )
        except cfg.AssistantConfigurationError:
            value = None
    spent = meter.spent()
    if meter.overrun:
        value, complete = None, False
    report = {
        "schema": "carbon.product.assistant-assessment.v1",
        "scope": "DEVELOPMENT",
        "search_audit_digest": body["audit_digest"],
        "search_commitment_digest": body["search_commitment_digest"],
        "reference_status": reference_status,
        "reference_holds": sorted(set(holds)),
        "reference_image": reference.image_digest,
        "reference_record": reference.record_digest,
        "reference_runtime": reference.runtime_digest,
        "reference_kind": reference.kind,
        "assessment_budget_digest": cfg.digest(b),
        "basis": "FINITE_BANK_REFERENCE_RELATIVE",
        "source_basis": q["basis"],
        "cost_basis": b["basis"],
        "global_optimum_established": False,
        "complete": complete,
        "observations_complete": observations_complete,
        "bank_size": len(q["actions"]),
        "covered_rows": len(rows),
        "observed": sum("receipt_digest" in row["reference"] for row in rows),
        "rows": rows,
        "best_finite_bank_id": None if not complete or not ranked else ranked[0]["id"],
        "none_feasible_established": complete and not ranked,
        "realized_regret": {
            "value": value,
            "unit": q["objective"]["unit"],
            "status": "MEASURED" if value is not None else "GAP",
        },
        "spent": spent,
        "qualification_claim": False,
    }
    report["assessment_digest"] = cfg.digest(
        {k: v for k, v in report.items() if k != "spent"}
    )
    return report
