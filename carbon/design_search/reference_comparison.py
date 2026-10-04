"""Challenge-neutral finite-reference comparison and regret semantics."""

from __future__ import annotations


def classify_condition_evidence(rows):
    """Classify one proposal without letting missing evidence hide violations."""

    verdicts = [row.get("verdict") for row in rows]
    if "INFEASIBLE" in verdicts:
        return "CONFIRMED_INFEASIBLE"
    if rows and all(verdict == "FEASIBLE" for verdict in verdicts):
        return "CONFIRMED_FEASIBLE"
    return "UNRESOLVED"


def finite_comparator(
    *,
    designs,
    rows,
    conditions_per_design,
    objective,
    objective_field,
    definition,
    limitations,
    accounting,
):
    """Build a best-observed or exact comparator for a registered finite set.

    ``objective`` receives every condition row for a confirmed-feasible design.
    Confirmed-infeasible designs need not have all other conditions available;
    unresolved designs remain potentially competitive and therefore prevent an
    exact finite-set regret claim.
    """

    candidates = []
    summaries = []
    for design in designs:
        evidence = [row for row in rows if row["design_id"] == design["design_id"]]
        if len(evidence) != conditions_per_design:
            raise ValueError(f"finite_comparator_row_count: {design['design_id']}")
        verdict_counts = {
            verdict: sum(row.get("verdict") == verdict for row in evidence)
            for verdict in ("FEASIBLE", "INFEASIBLE", "REFERENCE_UNAVAILABLE")
        }
        outcome = classify_condition_evidence(evidence)
        resolved = verdict_counts["REFERENCE_UNAVAILABLE"] == 0
        feasible = outcome == "CONFIRMED_FEASIBLE"
        value = objective(evidence) if feasible else None
        item = {
            "design_id": design["design_id"],
            "geometry": design["values"],
            "proposal_outcome": outcome,
            "verdicts": verdict_counts,
            "resolved_all_conditions": resolved,
            "reference_feasible_all_conditions": feasible,
            objective_field: value,
        }
        summaries.append(item)
        if feasible:
            candidates.append((value, design["design_id"], item))
    best_observed = min(candidates) if candidates else None
    unresolved = [
        item for item in summaries if item["proposal_outcome"] == "UNRESOLVED"
    ]
    if unresolved:
        status = "UNRESOLVED_COMPARISON_SET"
        best_complete = None
    elif best_observed is None:
        status = "COMPLETE_SET_NO_REFERENCE_FEASIBLE_DESIGN"
        best_complete = None
    else:
        status = "COMPLETE_FINITE_SET"
        best_complete = best_observed
    return {
        "definition": definition,
        "status": status,
        "coverage": {
            "designs": len(designs),
            "conditions_per_design": conditions_per_design,
            "condition_evidence": len(rows),
            "resolved_condition_evidence": sum(
                row.get("verdict") != "REFERENCE_UNAVAILABLE" for row in rows
            ),
            "fully_resolved_designs": sum(
                item["resolved_all_conditions"] for item in summaries
            ),
            "confirmed_infeasible_designs": sum(
                item["proposal_outcome"] == "CONFIRMED_INFEASIBLE" for item in summaries
            ),
            "confirmed_feasible_designs": sum(
                item["proposal_outcome"] == "CONFIRMED_FEASIBLE" for item in summaries
            ),
            "unresolved_designs": len(unresolved),
            "sufficiently_resolved_for_exact_finite_set_comparator": not unresolved,
        },
        "limitations": limitations,
        "accounting": accounting,
        "designs": summaries,
        "best_observed_reference_feasible": (
            None if best_observed is None else best_observed[2]
        ),
        "best_reference_feasible_in_complete_set": (
            None if best_complete is None else best_complete[2]
        ),
        "rows": rows,
    }


def regret(
    *,
    proposal_outcome,
    selected_objective,
    comparator,
    objective_field,
    value_field,
    selected_field,
    comparator_field,
    difference_field,
):
    """Return exact regret only when the full finite set supports it."""

    if proposal_outcome == "ABSTAIN":
        return {"status": "ABSTAIN", value_field: None}
    if proposal_outcome == "CONFIRMED_INFEASIBLE":
        return {"status": "INFEASIBLE_SELECTION", value_field: None}
    if proposal_outcome == "UNRESOLVED":
        return {"status": "REFERENCE_UNRESOLVED", value_field: None}
    best_observed = comparator["best_observed_reference_feasible"]
    best_complete = comparator["best_reference_feasible_in_complete_set"]
    if comparator["status"] == "UNRESOLVED_COMPARISON_SET":
        return {
            "status": "COMPARATOR_UNRESOLVED_BEST_OBSERVED_DIFFERENCE_ONLY",
            value_field: None,
            selected_field: selected_objective,
            difference_field: (
                None
                if best_observed is None
                else selected_objective - best_observed[objective_field]
            ),
            "best_observed_reference_feasible_design_id": (
                None if best_observed is None else best_observed["design_id"]
            ),
        }
    if best_complete is None:
        return {
            "status": "NO_REFERENCE_FEASIBLE_COMPARATOR",
            value_field: None,
            selected_field: selected_objective,
        }
    return {
        "status": "DEFINED_FINITE_SET",
        value_field: selected_objective - best_complete[objective_field],
        selected_field: selected_objective,
        comparator_field: best_complete[objective_field],
        "comparator_design_id": best_complete["design_id"],
    }
