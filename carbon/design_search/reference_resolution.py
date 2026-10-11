"""Producer-only use of digest-bound, per-candidate reference settlements.

The producer verifies the refinement rungs before sealing the export. This
module consumes its verdicts; it never infers a verdict from a near-limit
point estimate or changes the registered task's physical limits.
"""

from __future__ import annotations

from decimal import Decimal

from carbon.design_search import indexed, tasks

REFINEMENT_METHOD = "two-rungs-same-side-change-below-band.v1"


def validate_rule(rule):
    if (
        type(rule) is not dict
        or set(rule) != {"id", "method"}
        or type(rule["id"]) is not str
        or not rule["id"]
        or rule["method"] != REFINEMENT_METHOD
    ):
        raise tasks.TaskError("named two-rung refinement rule required")


def assessed(task, panel, verdicts):
    """Apply only explicit producer verdicts to band-unresolved candidates."""
    if type(verdicts) is not list:
        raise tasks.TaskError("per-candidate settled verdicts required")
    truth = tasks.assess(task, panel, reference=True)
    seen = set()
    for row in verdicts:
        if (
            type(row) is not dict
            or set(row) != {"candidate", "feasible"}
            or type(row["candidate"]) is not str
            or row["candidate"] not in truth
            or row["candidate"] in seen
            or type(row["feasible"]) is not bool
        ):
            raise tasks.TaskError("invalid per-candidate settled verdict")
        candidate = row["candidate"]
        seen.add(candidate)
        previous = truth[candidate]["feasible"]
        if previous is not None and previous is not row["feasible"]:
            raise tasks.TaskError("settled verdict contradicts resolved reference")
        truth[candidate]["feasible"] = row["feasible"]
    return truth


def state_and_winner(task, truth):
    """An unresolved candidate matters only if it can alter the decision."""
    best = tasks.select(task, truth)
    uncertain = [c for c, row in truth.items() if row["feasible"] is None]
    if best is None:
        return ("UNRESOLVED" if uncertain else "NONE_FEASIBLE"), None
    possible = {
        candidate: {
            **row,
            "feasible": True if candidate in uncertain else row["feasible"],
        }
        for candidate, row in truth.items()
    }
    if tasks.select(task, possible) != best:
        return "UNRESOLVED", None
    return "FEASIBLE_EXISTS", best


def indexed_verdicts(registered, settled):
    if type(settled) is not list or len(settled) != len(registered["indices"]):
        raise tasks.TaskError("one settled verdict panel per index required")
    result = []
    for row, index_row in zip(settled, registered["indices"]):
        if (
            type(row) is not dict
            or set(row) != {"index_value", "verdicts"}
            or row["index_value"] != index_row["index_value"]
            or type(row["verdicts"]) is not list
        ):
            raise tasks.TaskError("settled index order differs from registration")
        result.append(row["verdicts"])
    return result


def indexed_state_and_winner(registered, panels, settled):
    verdicts = indexed_verdicts(registered, settled)
    states = []
    winners = []
    for row, panel, candidate_verdicts in zip(registered["indices"], panels, verdicts):
        truth = assessed(row["task"], panel, candidate_verdicts)
        state, winner = state_and_winner(row["task"], truth)
        states.append(state)
        winners.append(winner)
    if "NONE_FEASIBLE" in states:
        return "NONE_FEASIBLE", None
    if "UNRESOLVED" in states:
        return "UNRESOLVED", None
    return "FEASIBLE_EXISTS", tasks.digest(winners)


def judge(task, commitment, panel, verdicts):
    """Keep commitment validation while using the producer's settled truth."""
    outcome = tasks.judge(task, commitment, panel)
    truth = assessed(task, panel, verdicts)
    state, best = state_and_winner(task, truth)
    pick = outcome["selected"]
    resolved = state != "UNRESOLVED"
    regret = None
    if pick is None:
        kind = {
            "FEASIBLE_EXISTS": "MISSED_OPPORTUNITY",
            "NONE_FEASIBLE": "CORRECT_ABSTENTION",
            "UNRESOLVED": "ABSTENTION_UNRESOLVED",
        }[state]
    elif truth[pick]["feasible"] is None:
        # The question may have a fixed best, but this model's pick does not.
        kind = "SELECTED_UNRESOLVED"
        resolved = False
    elif truth[pick]["feasible"] is False:
        kind = "SELECTED_INFEASIBLE"
    else:
        kind = "SELECTED_FEASIBLE"
        if best is not None:
            objective = task["objective"]
            regret = tasks._signed(objective, truth[pick]["objective"]) - tasks._signed(
                objective, truth[best]["objective"]
            )
    return {
        **outcome,
        "kind": kind,
        "best": best,
        "reference_state": state,
        "reference_resolved": resolved,
        "regret": regret,
    }


def judge_indexed(registered, commitment, panels, settled):
    """Rejudge producer-only indexed power without changing score contracts."""
    indexed.validate_indexed(registered)
    # The canonical judge authenticates the map commitment and query ledger.
    base = tasks.judge_indexed(registered, commitment, panels)
    verdicts = indexed_verdicts(registered, settled)
    per_index = []
    selected_sum = Decimal(0)
    best_sum = Decimal(0)
    complete_value = True
    tolerance = tasks._number(
        registered["identity"]["value_equivalence"]["tolerance"], "tolerance"
    )
    for row, subcommitment, reference, candidate_verdicts in zip(
        registered["indices"],
        commitment["subcommitments"],
        panels,
        verdicts,
    ):
        task = row["task"]
        outcome = judge(task, subcommitment, reference["values"], candidate_verdicts)
        truth = assessed(task, reference["values"], candidate_verdicts)
        pick, best = outcome["selected"], outcome["best"]
        selected_objective = truth[pick]["objective"] if pick is not None else None
        best_objective = truth[best]["objective"] if best is not None else None
        if (
            outcome["kind"] == "SELECTED_FEASIBLE"
            and outcome["reference_resolved"]
            and best is not None
        ):
            delta = tasks._number(
                selected_objective, "selected objective"
            ) - tasks._number(best_objective, "reference-best objective")
            if task["objective"]["sense"] == "max":
                delta = -delta
            outcome["regret"] = indexed._equivalent_regret(delta, tolerance)
            outcome["value_equivalent"] = outcome["regret"] == 0
            weight = tasks._number(row["buyer_weight"], "buyer weight")
            selected_sum += weight * tasks._number(
                selected_objective, "selected objective"
            )
            best_sum += weight * tasks._number(
                best_objective, "reference-best objective"
            )
        else:
            complete_value = False
            outcome["value_equivalent"] = None
        per_index.append(
            {
                "index_value": row["index_value"],
                "buyer_weight": row["buyer_weight"],
                "outcome": outcome,
                "selected_objective": selected_objective,
                "reference_best_objective": best_objective,
            }
        )
    states = [row["outcome"]["reference_state"] for row in per_index]
    state = (
        "NONE_FEASIBLE"
        if "NONE_FEASIBLE" in states
        else "UNRESOLVED" if "UNRESOLVED" in states else "FEASIBLE_EXISTS"
    )
    kinds = [row["outcome"]["kind"] for row in per_index]
    unresolved_pick = "SELECTED_UNRESOLVED" in kinds
    resolved = state != "UNRESOLVED" and not unresolved_pick
    if unresolved_pick:
        kind = "SELECTED_UNRESOLVED"
    elif "SELECTED_INFEASIBLE" in kinds:
        kind = "SELECTED_INFEASIBLE"
    elif not resolved:
        kind = (
            "ABSTENTION_UNRESOLVED"
            if all(row["outcome"]["selected"] is None for row in per_index)
            else "SELECTED_UNRESOLVED"
        )
    elif state == "NONE_FEASIBLE":
        kind = "CORRECT_ABSTENTION"
    elif "MISSED_OPPORTUNITY" in kinds:
        kind = "MISSED_OPPORTUNITY"
    else:
        kind = "SELECTED_FEASIBLE"
    aggregate = None
    if complete_value and kind == "SELECTED_FEASIBLE":
        sense = registered["identity"]["objective"]["sense"]
        delta = selected_sum - best_sum if sense == "min" else best_sum - selected_sum
        aggregate = {
            "selected_objective": float(selected_sum),
            "reference_best_objective": float(best_sum),
            "regret": indexed._equivalent_regret(delta, tolerance),
            "unit": registered["identity"]["objective"]["unit"],
        }
    return {
        **base,
        "kind": kind,
        "reference_state": state,
        "reference_resolved": resolved,
        "per_index": per_index,
        "aggregate": aggregate,
        "regret": aggregate["regret"] if aggregate is not None else None,
    }
