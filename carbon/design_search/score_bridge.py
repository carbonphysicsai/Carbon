"""Pure DEVELOPMENT design-q bridge for a validator-owned caller.

The caller seals the question bank and commits prediction panels before it
opens references. This module verifies those bindings and executes the frozen
Carbon optimizer, but a pure function cannot attest the caller's timing.
"""

from __future__ import annotations

import math
import statistics

from carbon.design_search import indexed, tasks

BANK_SCHEMA = "carbon.design-search.score-bank.v1"
RULE_SCHEMA = "carbon.design-search.score-rule.v1"
PREDICTIONS_SCHEMA = "carbon.design-search.committed-predictions.v1"
RESULT_SCHEMA = "carbon.design-search.score-result.v1"
MINER_SCHEMA = "carbon.design-search.sealed-score-outcome.v1"
Q_TRANSFORM = "inverse_one_plus_mean_loss.v1"
QUESTION_AGGREGATE = "arithmetic_mean.v1"
KIND_COSTS = frozenset(
    {
        "SELECTED_INFEASIBLE",
        "MISSED_OPPORTUNITY",
        "SELECTED_UNRESOLVED",
        "ABSTENTION_UNRESOLVED",
        "CORRECT_ABSTENTION",
    }
)


class ScoreBridgeFailure(ValueError):
    """Typed fail-closed evaluation cause; never a partial score."""

    status = "FAILED_INFRA"
    cause = "bank_unavailable"


class CandidatePredictionFailure(ScoreBridgeFailure):
    status = "INELIGIBLE"
    cause = "q_candidate_failed"


class ReferenceMaterialFailure(ScoreBridgeFailure):
    status = "VOID"
    cause = "reference_unavailable"


class InfrastructureFailure(ScoreBridgeFailure):
    status = "FAILED_INFRA"
    cause = "bank_unavailable"


def seal_score_bank(questions):
    """Bind an ordered producer question/reference bank without I/O."""
    body = {"schema": BANK_SCHEMA, "sealed": True, "questions": questions}
    return {**body, "seal_digest": tasks.digest(body)}


def register_score_rule(body):
    """Bind every score-bearing value; registration is not qualification."""
    registered = {**body, "registration_digest": tasks.digest(body)}
    _rule(registered)
    return registered


def commit_prediction_panels(model_id, questions):
    """Bind already-produced panels without accessing the reference bank."""
    body = {
        "schema": PREDICTIONS_SCHEMA,
        "model_id": model_id,
        "questions": questions,
    }
    return {**body, "predictions_digest": tasks.digest(body)}


def _finite(value, *, nonnegative=False, positive=False):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise InfrastructureFailure("registered score value is not finite")
    if (nonnegative and value < 0) or (positive and value <= 0):
        raise InfrastructureFailure("registered score value is out of range")
    return value


def _rule(registered):
    try:
        if (
            type(registered) is not dict
            or set(registered)
            != {
                "schema",
                "version",
                "challenge",
                "contract_version",
                "objective",
                "value_equivalence",
                "loss",
                "kind_costs",
                "question_aggregate",
                "q_transform",
                "registration_digest",
            }
            or registered["schema"] != RULE_SCHEMA
            or registered["registration_digest"]
            != tasks.digest(
                {k: v for k, v in registered.items() if k != "registration_digest"}
            )
            or any(
                type(registered[key]) is not str or not registered[key]
                for key in ("version", "challenge", "contract_version")
            )
            or registered["question_aggregate"] != QUESTION_AGGREGATE
            or registered["q_transform"] != Q_TRANSFORM
        ):
            raise InfrastructureFailure("registered score rule required")
        objective = registered["objective"]
        equivalence = registered["value_equivalence"]
        loss = registered["loss"]
        costs = registered["kind_costs"]
        if (
            type(objective) is not dict
            or set(objective) != {"quantity", "unit", "sense"}
            or type(objective["quantity"]) is not str
            or not objective["quantity"]
            or type(objective["unit"]) is not str
            or not objective["unit"]
            or objective["sense"] not in tasks.SENSES
            or type(equivalence) is not dict
            or set(equivalence) != {"quantity", "unit", "tolerance", "rule"}
            or equivalence["rule"] != indexed.EQUIVALENCE_RULE
            or (equivalence["quantity"], equivalence["unit"])
            != (objective["quantity"], objective["unit"])
            or type(loss) is not dict
            or set(loss) != {"unit", "regret_multiplier", "regret_divisor"}
            or type(loss["unit"]) is not str
            or not loss["unit"]
            or type(costs) is not dict
            or set(costs) != KIND_COSTS
        ):
            raise InfrastructureFailure("invalid score rule quantities or costs")
        _finite(equivalence["tolerance"], nonnegative=True)
        _finite(loss["regret_multiplier"], nonnegative=True)
        _finite(loss["regret_divisor"], positive=True)
        for cost in costs.values():
            _finite(cost, nonnegative=True)
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        if isinstance(exc, InfrastructureFailure):
            raise
        raise InfrastructureFailure("invalid registered score rule") from exc


def _task(registered, rule):
    try:
        if type(registered) is not dict:
            raise InfrastructureFailure("registered design task required")
        schema = registered.get("schema")
        if schema == tasks.INDEXED_SCHEMA:
            indexed.validate_indexed(registered)
            identity = registered["identity"]
            objective = identity["objective"]
            if identity["value_equivalence"] != rule["value_equivalence"]:
                raise InfrastructureFailure("indexed value equivalence differs")
        elif schema == tasks.RUNNABLE_SCHEMA:
            tasks._verify_task_digest(registered)
            identity = registered["identity"]
            objective = registered["objective"]
        else:
            raise InfrastructureFailure("runnable design task required")
        if (
            identity["challenge"] != rule["challenge"]
            or identity["contract_version"] != rule["contract_version"]
            or any(
                objective[key] != rule["objective"][key] for key in rule["objective"]
            )
        ):
            raise InfrastructureFailure("task and score rule identities differ")
        return schema
    except (KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, InfrastructureFailure):
            raise
        raise InfrastructureFailure("invalid registered design task") from exc


def _panel(rows, registered, failure, *, complete):
    if type(rows) is not list:
        raise failure("prediction or reference panel required")
    expected = {
        (candidate, condition["id"])
        for candidate in registered["candidates"]
        for condition in registered["conditions"]
    }
    needed = {registered["objective"]["quantity"]}
    needed.update(limit["quantity"] for limit in registered["limits"])
    if registered["secondary"] is not None:
        needed.add(registered["secondary"]["quantity"])
    panel = {}
    for row in rows:
        if (
            type(row) is not dict
            or set(row) != {"candidate", "condition", "values"}
            or (row["candidate"], row["condition"]) not in expected
            or (row["candidate"], row["condition"]) in panel
            or type(row["values"]) is not dict
            or set(row["values"]) != needed
            or any(
                type(value) not in (int, float) or not math.isfinite(value)
                for value in row["values"].values()
            )
        ):
            raise failure("invalid prediction or reference panel")
        panel[(row["candidate"], row["condition"])] = dict(row["values"])
    if complete and set(panel) != expected:
        raise failure("reference panel is incomplete")
    return panel


def _indexed_panels(rows, registered, failure, *, complete):
    if type(rows) is not list or len(rows) != len(registered["indices"]):
        raise failure("complete indexed panels required")
    panels = []
    for entry, index_row in zip(rows, registered["indices"]):
        if (
            type(entry) is not dict
            or set(entry) != {"index_value", "panel"}
            or entry["index_value"] != index_row["index_value"]
        ):
            raise failure("indexed panel order differs")
        panels.append(
            _panel(entry["panel"], index_row["task"], failure, complete=complete)
        )
    return panels


def _bank(sealed_bank, rule):
    try:
        if (
            type(sealed_bank) is not dict
            or set(sealed_bank) != {"schema", "sealed", "questions", "seal_digest"}
            or sealed_bank["schema"] != BANK_SCHEMA
            or sealed_bank["sealed"] is not True
            or sealed_bank["seal_digest"]
            != tasks.digest(
                {k: v for k, v in sealed_bank.items() if k != "seal_digest"}
            )
            or type(sealed_bank["questions"]) is not list
            or not sealed_bank["questions"]
        ):
            raise InfrastructureFailure("sealed score bank unavailable")
        checked = []
        seen = set()
        for question in sealed_bank["questions"]:
            if (
                type(question) is not dict
                or set(question) != {"question_id", "task", "reference"}
                or type(question["question_id"]) is not str
                or not question["question_id"]
                or question["question_id"] in seen
            ):
                raise InfrastructureFailure("invalid score bank question")
            seen.add(question["question_id"])
            schema = _task(question["task"], rule)
            reference = question["reference"]
            if reference is None:
                raise ReferenceMaterialFailure("quiz reference missing")
            if type(reference) is not dict or reference.get("status") == "FAILED_INFRA":
                raise InfrastructureFailure("quiz reference failed")
            if reference.get("status") != "OK":
                raise ReferenceMaterialFailure("quiz reference unavailable")
            if schema == tasks.INDEXED_SCHEMA:
                if set(reference) != {"status", "per_index"}:
                    raise ReferenceMaterialFailure("indexed reference incomplete")
                panels = _indexed_panels(
                    reference["per_index"],
                    question["task"],
                    ReferenceMaterialFailure,
                    complete=True,
                )
            else:
                if set(reference) != {"status", "panel"}:
                    raise ReferenceMaterialFailure("reference incomplete")
                panels = _panel(
                    reference["panel"],
                    question["task"],
                    ReferenceMaterialFailure,
                    complete=True,
                )
            checked.append((question, schema, panels))
        return checked
    except ScoreBridgeFailure:
        raise
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise InfrastructureFailure("sealed score bank invalid") from exc


def _predictions(committed, checked):
    try:
        if (
            type(committed) is not dict
            or set(committed)
            != {"schema", "model_id", "questions", "predictions_digest"}
            or committed["schema"] != PREDICTIONS_SCHEMA
            or type(committed["model_id"]) is not str
            or not committed["model_id"]
            or type(committed["questions"]) is not list
            or len(committed["questions"]) != len(checked)
            or committed["predictions_digest"]
            != tasks.digest(
                {k: v for k, v in committed.items() if k != "predictions_digest"}
            )
        ):
            raise CandidatePredictionFailure("committed prediction panels required")
        panels = []
        for submitted, (question, schema, _) in zip(committed["questions"], checked):
            fields = (
                {"question_id", "task_digest", "per_index"}
                if schema == tasks.INDEXED_SCHEMA
                else {"question_id", "task_digest", "panel"}
            )
            if (
                type(submitted) is not dict
                or set(submitted) != fields
                or submitted["question_id"] != question["question_id"]
                or submitted["task_digest"] != question["task"]["task_digest"]
            ):
                raise CandidatePredictionFailure("prediction task identity differs")
            if schema == tasks.INDEXED_SCHEMA:
                panel = _indexed_panels(
                    submitted["per_index"],
                    question["task"],
                    CandidatePredictionFailure,
                    complete=False,
                )
            else:
                panel = _panel(
                    submitted["panel"],
                    question["task"],
                    CandidatePredictionFailure,
                    complete=False,
                )
            panels.append(panel)
        return panels
    except ScoreBridgeFailure:
        raise
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise CandidatePredictionFailure("committed predictions invalid") from exc


def _predictor(registered, panel):
    action_index = {
        tasks.digest(action): candidate
        for candidate, action in registered["actions"].items()
    }

    def predict(action, condition):
        candidate = action_index[tasks.digest(action)]
        return dict(panel[(candidate, condition["id"])])

    return predict


def _run(question, schema, predicted, reference, model_id):
    registered = question["task"]
    if schema == tasks.INDEXED_SCHEMA:
        callbacks = [
            _predictor(row["task"], panel)
            for row, panel in zip(registered["indices"], predicted)
        ]
        positions = {
            tasks.digest(row["index_value"]): position
            for position, row in enumerate(registered["indices"])
        }

        def predict(index_value, action, condition):
            return callbacks[positions[tasks.digest(index_value)]](action, condition)

        run = tasks.run_indexed_optimizer(registered, predict, model_id=model_id)
    else:
        run = tasks.run_optimizer(
            registered, _predictor(registered, predicted), model_id=model_id
        )
    if run["accounting"]["model_failures"]:
        raise CandidatePredictionFailure("model failed on design query")
    if schema == tasks.INDEXED_SCHEMA:
        refs = [
            {"index_value": row["index_value"], "values": panel}
            for row, panel in zip(registered["indices"], reference)
        ]
        outcome = tasks.judge_indexed(registered, run["commitment"], refs)
    else:
        outcome = tasks.judge(registered, run["commitment"], reference)
        # EV4 prices a selected reference-feasible design against the best
        # *known feasible* design even when another option lies in a band.
        if outcome["kind"] == "SELECTED_FEASIBLE" and outcome["regret"] is None:
            assessed = tasks.assess(registered, reference, reference=True)
            best = tasks.select(registered, assessed)
            if best is None:
                raise ReferenceMaterialFailure("feasible pick has no reference best")
            selected = run["commitment"]["selected"]
            objective = registered["objective"]
            outcome["best"] = best
            outcome["regret"] = tasks._signed(
                objective, assessed[selected]["objective"]
            ) - tasks._signed(objective, assessed[best]["objective"])
    return outcome, run["accounting"]


def _result(status, cause, *, bank_digest=None, rule_digest=None):
    return {
        "schema": RESULT_SCHEMA,
        "status": status,
        "cause": cause,
        "eligible": False if status == "INELIGIBLE" else None,
        "bank_digest": bank_digest,
        "rule_digest": rule_digest,
        "per_question": [],
        "mean_regret": None,
        "mean_loss": None,
        "q": None,
    }


def evaluate_design_score(sealed_bank, committed_predictions, registered_rule):
    """Run committed panels and judge against one sealed scoring bank.

    This pure bridge returns a typed non-score on missing truth or bad model
    output. The validator applies its own lifecycle, retry and score policy.
    """
    bank_digest = sealed_bank.get("seal_digest") if type(sealed_bank) is dict else None
    rule_digest = (
        registered_rule.get("registration_digest")
        if type(registered_rule) is dict
        else None
    )
    try:
        _rule(registered_rule)
        checked = _bank(sealed_bank, registered_rule)
        predictions = _predictions(committed_predictions, checked)
        rows = []
        losses = []
        regrets = []
        for (question, schema, reference), predicted in zip(checked, predictions):
            try:
                outcome, accounting = _run(
                    question,
                    schema,
                    predicted,
                    reference,
                    committed_predictions["model_id"],
                )
            except ScoreBridgeFailure:
                raise
            except (tasks.TaskError, KeyError, TypeError, ValueError) as exc:
                raise InfrastructureFailure("design evaluation failed") from exc
            kind = outcome["kind"]
            if kind == "SELECTED_FEASIBLE":
                regret = outcome["regret"]
                if (
                    regret is None
                    or type(regret) not in (int, float)
                    or not math.isfinite(regret)
                ):
                    raise ReferenceMaterialFailure("reference regret unavailable")
                if regret < 0:
                    raise InfrastructureFailure("negative reference regret")
                tolerance = registered_rule["value_equivalence"]["tolerance"]
                regret = 0.0 if regret <= tolerance else float(regret)
                loss = (
                    registered_rule["loss"]["regret_multiplier"]
                    * regret
                    / registered_rule["loss"]["regret_divisor"]
                )
                if not math.isfinite(loss):
                    raise InfrastructureFailure("design loss overflowed")
                regrets.append(regret)
            elif kind in KIND_COSTS:
                regret = None
                loss = registered_rule["kind_costs"][kind]
            else:
                raise InfrastructureFailure("unregistered design outcome kind")
            rows.append(
                {
                    "question_id": question["question_id"],
                    "outcome": outcome,
                    "regret": regret,
                    "regret_unit": registered_rule["objective"]["unit"],
                    "loss": loss,
                    "loss_unit": registered_rule["loss"]["unit"],
                    "accounting": accounting,
                }
            )
            losses.append(loss)
        try:
            mean_loss = statistics.fmean(losses)
        except (OverflowError, ValueError) as exc:
            raise InfrastructureFailure("design loss aggregation failed") from exc
        if not math.isfinite(mean_loss):
            raise InfrastructureFailure("design loss aggregation overflowed")
        try:
            mean_regret = statistics.fmean(regrets) if regrets else None
        except (OverflowError, ValueError) as exc:
            raise InfrastructureFailure("design regret aggregation failed") from exc
        if mean_regret is not None and not math.isfinite(mean_regret):
            raise InfrastructureFailure("design regret aggregation overflowed")
        return {
            "schema": RESULT_SCHEMA,
            "status": "OK",
            "cause": None,
            "eligible": True,
            "bank_digest": bank_digest,
            "rule_digest": rule_digest,
            "per_question": rows,
            "mean_regret": mean_regret,
            "mean_loss": mean_loss,
            "q": 1.0 / (1.0 + mean_loss),
        }
    except ScoreBridgeFailure as exc:
        return _result(
            exc.status, exc.cause, bank_digest=bank_digest, rule_digest=rule_digest
        )


def miner_score_projection(result):
    """Positive allow-list: a miner sees only that an outcome was sealed."""
    if type(result) is not dict or result.get("schema") != RESULT_SCHEMA:
        raise tasks.TaskError("internal design score result required")
    return {"schema": MINER_SCHEMA, "outcome": "SEALED"}
