"""Prospective VERIFY-R screen-then-verify leg, DEVELOPMENT only.

The caller commits a prediction-only ordered list before opening the sealed
question. This pure replay checks the bindings but cannot attest wall-clock
ordering or the trustworthiness of a verifier receipt. It performs no solve,
inference, registry-v5 mutation, or official scoring.
"""

from __future__ import annotations

import math

from . import budget_registration, tasks

RULE_SCHEMA = "carbon.design-search.verify-aware-rule.v1"
QUESTION_SCHEMA = "carbon.design-search.verify-aware-question.v1"
COMMIT_SCHEMA = "carbon.design-search.verify-aware-commitment.v1"
CANDIDATE_SCHEMA = "carbon.design-search.verify-aware-candidate.v1"
RESULT_SCHEMA = "carbon.design-search.verify-aware-result.v1"
REFERENCE_STATES = {"FEASIBLE", "INFEASIBLE", "UNRESOLVED", "MISSING", "FAILED_INFRA"}


class VerifyAwareError(ValueError):
    """Malformed registration, commitment, or trusted evidence."""


def _closed(value, fields, label):
    if type(value) is not dict or set(value) != set(fields):
        raise VerifyAwareError(f"closed {label} required")


def _id(value, label):
    if type(value) is not str or not value.strip():
        raise VerifyAwareError(f"{label} required")
    return value


def _number(value, label, *, positive=False):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise VerifyAwareError(f"finite {label} required")
    if (positive and value <= 0) or (not positive and value < 0):
        raise VerifyAwareError(f"nonnegative {label} required")
    return float(value)


def _cost(value, label, *, positive=False):
    _closed(value, {"wall_s", "core_s"}, label)
    for unit in ("wall_s", "core_s"):
        _number(value[unit], f"{label}.{unit}", positive=positive)


def _bound(body, field):
    digest = field + "_digest"
    if type(body) is not dict or digest in body:
        raise VerifyAwareError(f"unbound {field} body required")
    return {**body, digest: tasks.digest(body)}


def _check_bound(value, field):
    digest = field + "_digest"
    if value[digest] != tasks.digest({k: v for k, v in value.items() if k != digest}):
        raise VerifyAwareError(f"{field} digest mismatch")


def register_rule(body):
    """Bind owner-supplied values; registration alone does not adopt a score."""
    rule = _bound(body, "rule")
    _rule(rule)
    return rule


def _rule(rule):
    _closed(
        rule,
        {
            "schema",
            "rule_id",
            "evidence_class",
            "selector_version",
            "k",
            "budget",
            "objective",
            "regret_unit",
            "reference_policy_id",
            "eligibility_policy_id",
            "population_id",
            "proposal_id",
            "weight_law_id",
            "rule_digest",
        },
        "VERIFY-R rule",
    )
    if rule["schema"] != RULE_SCHEMA or rule["evidence_class"] != "DEVELOPMENT":
        raise VerifyAwareError("prospective development rule required")
    for field in (
        "rule_id",
        "selector_version",
        "reference_policy_id",
        "eligibility_policy_id",
        "population_id",
        "proposal_id",
        "weight_law_id",
    ):
        _id(rule[field], field)
    if type(rule["k"]) is not int or rule["k"] <= 0:
        raise VerifyAwareError("registered positive k required")
    _closed(rule["budget"], {"complete_panels", "wall_s", "core_s"}, "budget")
    try:
        cap = budget_registration.BudgetCap(
            rule["budget"]["complete_panels"],
            rule["budget"]["wall_s"],
            rule["budget"]["core_s"],
        )
    except budget_registration.BudgetRegistrationError as exc:
        raise VerifyAwareError("invalid registered budget") from exc
    _closed(rule["objective"], {"direction", "unit"}, "objective")
    if rule["objective"]["direction"] not in ("min", "max"):
        raise VerifyAwareError("objective direction required")
    if rule["objective"]["unit"] != _id(rule["objective"]["unit"], "unit"):
        raise VerifyAwareError("objective unit required")
    _closed(rule["regret_unit"], {"value", "unit"}, "regret unit")
    _number(rule["regret_unit"]["value"], "regret unit", positive=True)
    if rule["regret_unit"]["unit"] != rule["objective"]["unit"]:
        raise VerifyAwareError("regret normalisation must use objective unit")
    _check_bound(rule, "rule")
    return cap


def seal_question(body):
    question = _bound(body, "question")
    _question(question)
    return question


def _question(question):
    _closed(
        question,
        {
            "schema",
            "question_id",
            "action_family_id",
            "rule_digest",
            "reference_policy_id",
            "population_id",
            "proposal_id",
            "weight_law_id",
            "weight",
            "objective",
            "bank",
            "question_digest",
        },
        "question",
    )
    if question["schema"] != QUESTION_SCHEMA:
        raise VerifyAwareError("unsupported question schema")
    _id(question["question_id"], "question ID")
    _id(question["action_family_id"], "action family")
    for field in (
        "rule_digest",
        "reference_policy_id",
        "population_id",
        "proposal_id",
        "weight_law_id",
    ):
        _id(question[field], field)
    _number(question["weight"], "question weight", positive=True)
    _closed(question["objective"], {"direction", "unit"}, "question objective")
    if question["objective"]["direction"] not in ("min", "max"):
        raise VerifyAwareError("question objective direction invalid")
    _id(question["objective"]["unit"], "question objective unit")
    if type(question["bank"]) is not list or not question["bank"]:
        raise VerifyAwareError("nonempty registered action bank required")
    seen = set()
    for row in question["bank"]:
        _closed(
            row,
            {
                "action_id",
                "action_family_id",
                "reference",
                "planning_bound",
                "actual_cost",
            },
            "bank action",
        )
        action_id = _id(row["action_id"], "action ID")
        if action_id in seen or row["action_family_id"] != question["action_family_id"]:
            raise VerifyAwareError("duplicate or out-of-family bank action")
        seen.add(action_id)
        _closed(row["reference"], {"status", "value"}, "reference")
        status = row["reference"]["status"]
        if status not in REFERENCE_STATES:
            raise VerifyAwareError("unknown reference status")
        if status == "FEASIBLE":
            if type(row["reference"]["value"]) not in (int, float) or not math.isfinite(
                row["reference"]["value"]
            ):
                raise VerifyAwareError("finite feasible objective required")
        elif row["reference"]["value"] is not None:
            raise VerifyAwareError("only feasible actions have an objective")
        _cost(row["planning_bound"], "planning bound", positive=True)
        _cost(row["actual_cost"], "actual complete-panel cost", positive=True)
        if any(
            row["actual_cost"][unit] > row["planning_bound"][unit]
            for unit in ("wall_s", "core_s")
        ):
            raise VerifyAwareError("planning bound below actual complete-panel cost")
    _check_bound(question, "question")


def commit_list(body):
    """Seal a prediction-only list; caller must enforce commit-before-reference."""
    commitment = _bound(body, "commitment")
    _commit(commitment)
    return commitment


def _commit(commitment):
    _closed(
        commitment,
        {
            "schema",
            "model_id",
            "question_id",
            "action_family_id",
            "selector_version",
            "ordered_actions",
            "commitment_receipt_id",
            "commitment_digest",
        },
        "commitment",
    )
    if commitment["schema"] != COMMIT_SCHEMA:
        raise VerifyAwareError("unsupported commitment schema")
    for field in (
        "model_id",
        "question_id",
        "action_family_id",
        "selector_version",
        "commitment_receipt_id",
    ):
        _id(commitment[field], field)
    actions = commitment["ordered_actions"]
    if type(actions) is not list or any(type(a) is not str or not a for a in actions):
        raise VerifyAwareError("ordered action list required; empty list is abstention")
    if len(actions) != len(set(actions)):
        raise VerifyAwareError("duplicate action in committed list")
    _check_bound(commitment, "commitment")


def evaluate_question(rule, question, commitment, verifier_receipt, eligibility):
    """Replay one frozen list with independent costs and reference outcomes."""
    cap = _rule(rule)
    _question(question)
    _closed(eligibility, {"policy_id", "verdict"}, "eligibility")
    if eligibility["policy_id"] != rule["eligibility_policy_id"] or eligibility[
        "verdict"
    ] not in ("PASS", "FAIL"):
        raise VerifyAwareError("registered eligibility verdict required")
    if (
        question["rule_digest"] != rule["rule_digest"]
        or question["reference_policy_id"] != rule["reference_policy_id"]
        or question["population_id"] != rule["population_id"]
        or question["proposal_id"] != rule["proposal_id"]
        or question["weight_law_id"] != rule["weight_law_id"]
        or question["objective"] != rule["objective"]
    ):
        raise VerifyAwareError("question differs from registered decision law")
    if commitment is None:
        return {
            "schema": RESULT_SCHEMA,
            "rule_digest": rule["rule_digest"],
            "status": "INCOMPLETE_MODEL_OUTPUT",
            "score": None,
            "question_id": question["question_id"],
            "weight": question["weight"],
        }
    _commit(commitment)
    if (
        commitment["question_id"] != question["question_id"]
        or commitment["action_family_id"] != question["action_family_id"]
        or commitment["selector_version"] != rule["selector_version"]
        or len(commitment["ordered_actions"]) > rule["k"]
    ):
        raise VerifyAwareError("commitment outside registered question or k")
    rows = {row["action_id"]: row for row in question["bank"]}
    if any(action not in rows for action in commitment["ordered_actions"]):
        raise VerifyAwareError("out-of-family or unregistered action")
    _closed(
        verifier_receipt,
        {"origin", "commitment_digest", "startup_cost", "search_cost"},
        "verifier receipt",
    )
    if (
        verifier_receipt["origin"] != "independent_verifier"
        or verifier_receipt["commitment_digest"] != commitment["commitment_digest"]
    ):
        raise VerifyAwareError("independent verifier receipt must bind commitment")
    _cost(verifier_receipt["startup_cost"], "startup")
    _cost(verifier_receipt["search_cost"], "inference/search")
    if eligibility["verdict"] == "FAIL":
        return {
            "schema": RESULT_SCHEMA,
            "rule_digest": rule["rule_digest"],
            "status": "INELIGIBLE",
            "score": None,
            "question_id": question["question_id"],
            "weight": question["weight"],
        }
    ledger = budget_registration.BudgetLedger(cap)
    overhead_fit = all(
        ledger.charge_overhead(verifier_receipt[key])
        for key in ("startup_cost", "search_cost")
    )
    attempted = []
    if overhead_fit:
        for action in commitment["ordered_actions"]:
            row = rows[action]
            if not ledger.charge_solver_attempt(
                row["planning_bound"], row["actual_cost"]
            ):
                break
            attempted.append(row)
    statuses = [row["reference"]["status"] for row in question["bank"]]
    base = {
        "schema": RESULT_SCHEMA,
        "rule_digest": rule["rule_digest"],
        "question_id": question["question_id"],
        "weight": question["weight"],
        "attempted": [row["action_id"] for row in attempted],
        "attempt_statuses": [row["reference"]["status"] for row in attempted],
        "spent": {
            "complete_panels": ledger.solver_evaluations,
            "wall_s": ledger.wall_s,
            "core_s": ledger.core_s,
        },
        "budget_stopped": len(attempted) < len(commitment["ordered_actions"]),
        "correct_abstention": not commitment["ordered_actions"]
        and set(statuses) == {"INFEASIBLE"},
    }
    if "FAILED_INFRA" in statuses:
        return {**base, "status": "FAILED_INFRA", "score": None}
    if "MISSING" in statuses:
        return {**base, "status": "INSUFFICIENT_REFERENCE", "score": None}
    feasible_bank = [
        row for row in question["bank"] if row["reference"]["status"] == "FEASIBLE"
    ]
    feasible_attempts = [
        row for row in attempted if row["reference"]["status"] == "FEASIBLE"
    ]
    sign = 1 if rule["objective"]["direction"] == "min" else -1
    best = lambda rows: min(
        rows, key=lambda row: (sign * row["reference"]["value"], row["action_id"])
    )
    comparator = best(feasible_bank) if feasible_bank else None
    picked = best(feasible_attempts) if feasible_attempts else None
    gap = (
        None
        if picked is None or comparator is None
        else max(
            0.0,
            sign * (picked["reference"]["value"] - comparator["reference"]["value"]),
        )
    )
    loss = 1.0 if picked is None else min(1.0, gap / rule["regret_unit"]["value"])
    question_status = (
        "UNRESOLVED_FAMILY"
        if "UNRESOLVED" in statuses and comparator is None
        else (
            "BEST_KNOWN_ONLY"
            if "UNRESOLVED" in statuses
            else "NONE_FEASIBLE" if comparator is None else "SCORED"
        )
    )
    return {
        **base,
        "status": question_status,
        "score": loss,
        "buyer_unit_gap": gap,
        "best_known_only": "UNRESOLVED" in statuses,
        "verified_return": picked is not None,
        "picked_action": None if picked is None else picked["action_id"],
        "picked_value": None if picked is None else picked["reference"]["value"],
    }


def aggregate(rule, results):
    """Compute v on all offered questions; never silently drop an incomplete leg."""
    _rule(rule)
    if type(results) is not list or not results:
        raise VerifyAwareError("nonempty offered question set required")
    if any(
        type(row) is not dict
        or row.get("schema") != RESULT_SCHEMA
        or row.get("rule_digest") != rule["rule_digest"]
        for row in results
    ):
        raise VerifyAwareError("question result differs from registered rule")
    if len({row["question_id"] for row in results}) != len(results):
        raise VerifyAwareError("duplicate question result")
    incomplete = [row["question_id"] for row in results if row["score"] is None]
    if incomplete:
        return {
            "schema": RESULT_SCHEMA,
            "rule_digest": rule["rule_digest"],
            "status": "INCOMPLETE_LEGS",
            "v": None,
            "offered": len(results),
            "unscored": len(incomplete),
        }
    weights = [_number(row["weight"], "weight", positive=True) for row in results]
    losses = [_number(row["score"], "bounded regret") for row in results]
    if any(loss > 1 for loss in losses):
        raise VerifyAwareError("bounded regret exceeds one")
    mean_loss = sum(w * loss for w, loss in zip(weights, losses, strict=True)) / sum(
        weights
    )
    return {
        "schema": RESULT_SCHEMA,
        "rule_digest": rule["rule_digest"],
        "status": "SCORED",
        "v": 1 / (1 + mean_loss),
        "mean_service_regret": mean_loss,
        "offered": len(results),
        "unscored": 0,
        "best_known_only": sum(row["status"] == "BEST_KNOWN_ONLY" for row in results),
        "unresolved_family": sum(
            row["status"] == "UNRESOLVED_FAMILY" for row in results
        ),
        "none_feasible": sum(row["status"] == "NONE_FEASIBLE" for row in results),
    }


def score_model(
    rule, model_id, questions, commitments, verifier_receipts, eligibilities
):
    """Return every offered question and its common weighted VERIFY-R leg.

    The caller supplies independently captured receipts and must enforce
    commit-before-reference. No missing question is selected away here.
    """
    _rule(rule)
    _id(model_id, "model ID")
    if type(questions) is not list or not questions:
        raise VerifyAwareError("nonempty offered question list required")
    for question in questions:
        _question(question)
    if any(
        type(mapping) is not dict
        for mapping in (commitments, verifier_receipts, eligibilities)
    ):
        raise VerifyAwareError("question keyed evidence maps required")
    ids = [question["question_id"] for question in questions]
    if (
        len(set(ids)) != len(ids)
        or set(verifier_receipts) != set(ids)
        or set(eligibilities) != set(ids)
    ):
        raise VerifyAwareError("complete unique question receipts required")
    if set(commitments) - set(ids):
        raise VerifyAwareError("extra model commitment")
    if any(
        commitment is not None and commitment.get("model_id") != model_id
        for commitment in commitments.values()
    ):
        raise VerifyAwareError("commitment model identity mismatch")
    rows = [
        evaluate_question(
            rule,
            question,
            commitments.get(question["question_id"]),
            verifier_receipts[question["question_id"]],
            eligibilities[question["question_id"]],
        )
        for question in questions
    ]
    return {"aggregate": aggregate(rule, rows), "questions": rows}


def register_candidate(body):
    """Prospective score-map adapter; never mutate the historical v5 registry."""
    candidate = _bound(body, "candidate")
    _closed(
        candidate,
        {
            "schema",
            "candidate_id",
            "rule_digest",
            "weights",
            "gate_policy_id",
            "candidate_digest",
        },
        "candidate",
    )
    if candidate["schema"] != CANDIDATE_SCHEMA or candidate["candidate_id"] not in (
        "VERIFY-R",
        "A-VERIFY-R",
    ):
        raise VerifyAwareError("unsupported prospective candidate")
    _id(candidate["rule_digest"], "rule digest")
    _id(candidate["gate_policy_id"], "gate policy")
    weights = candidate["weights"]
    if type(weights) is not dict or set(weights) != (
        {"v"} if candidate["candidate_id"] == "VERIFY-R" else {"a", "v"}
    ):
        raise VerifyAwareError("candidate legs must be registered")
    if any(
        _number(w, "leg weight", positive=True) <= 0 for w in weights.values()
    ) or not math.isclose(sum(weights.values()), 1.0, abs_tol=1e-12):
        raise VerifyAwareError("positive normalized leg weights required")
    _check_bound(candidate, "candidate")
    return candidate


def candidate_score(candidate, rule, result, *, accuracy=None, gate_verdict="PASS"):
    """One member's raw prospective score for the existing proof score-map seam."""
    if type(candidate) is not dict:
        raise VerifyAwareError("candidate registration required")
    body = {k: v for k, v in candidate.items() if k != "candidate_digest"}
    if register_candidate(body) != candidate:
        raise VerifyAwareError("candidate digest mismatch")
    _rule(rule)
    if (
        candidate["rule_digest"] != rule["rule_digest"]
        or candidate["gate_policy_id"] != rule["eligibility_policy_id"]
    ):
        raise VerifyAwareError("candidate differs from registered rule/gate")
    if gate_verdict not in ("PASS", "FAIL"):
        raise VerifyAwareError("registered gate verdict required")
    if (
        type(result) is not dict
        or result.get("schema") != RESULT_SCHEMA
        or result.get("rule_digest") != rule["rule_digest"]
    ):
        raise VerifyAwareError("verified-search aggregate required")
    if gate_verdict == "FAIL" or result["status"] != "SCORED":
        return None
    legs = {"v": _number(result["v"], "v", positive=True)}
    if legs["v"] > 1:
        raise VerifyAwareError("v leg exceeds one")
    if "a" in candidate["weights"]:
        if accuracy is None:
            return None
        legs["a"] = _number(accuracy, "accuracy leg", positive=True)
        if legs["a"] > 1:
            raise VerifyAwareError("accuracy leg exceeds one")
    return math.exp(
        sum(
            weight * math.log(legs[name])
            for name, weight in candidate["weights"].items()
        )
    )


def prospective_score_map(candidate, rule, reports, accuracy_legs, gate_verdicts):
    """Adapt verified-search legs to score-proof's (scores, verdicts) seam.

    Missing legs remain None; failed mandatory gates rank below every member
    with a complete passing score. The proof caller supplies a separate product
    value target and never treats historical Q3 as this new v leg.
    """
    _rule(rule)
    if type(reports) is not dict or not reports:
        raise VerifyAwareError("member reports required")
    members = set(reports)
    if set(gate_verdicts) != members or set(accuracy_legs) != members:
        raise VerifyAwareError("complete member gate and accuracy maps required")
    raw = {
        member: candidate_score(
            candidate,
            rule,
            reports[member],
            accuracy=accuracy_legs[member],
            gate_verdict="PASS",
        )
        for member in reports
    }
    if any(verdict not in ("PASS", "FAIL") for verdict in gate_verdicts.values()):
        raise VerifyAwareError("closed mandatory gate verdicts required")
    finite = [value for value in raw.values() if value is not None]
    floor = (min(finite) if finite else 0.0) - 1.0
    return (
        {
            member: (
                None
                if score is None
                else floor if gate_verdicts[member] == "FAIL" else score
            )
            for member, score in raw.items()
        },
        dict(gate_verdicts),
    )
