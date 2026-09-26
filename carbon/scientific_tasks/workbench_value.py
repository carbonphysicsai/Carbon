"""Narrow Workbench adapter for public synthetic engineering-value studies.

It lets an operator:
- import a public synthetic Engineering Value Contract
  (`carbon.engineering-value-contract.v1`) and review it in the Workbench's
  terms: decision, design variables, conditions, objective, constraints and
  preferences;
- inspect a retained EV1 results document.

It adds no scheduler, evaluator, task store or browser code, and it never
runs anything. The experiment runs through `python -m carbon.battery.value`.

The client-data boundary is unchanged (GOAL-WORKBENCH-15 E8): only a
`PUBLIC_SYNTHETIC` contract is accepted. A client study needs the private
execution route and is refused here by name, with no opt-in and no flag.
"""

from __future__ import annotations

from carbon.battery.value import contract as ev

CONTRACT_VIEW = "carbon.workbench.engineering-value.contract-view.v1"
RESULTS_VIEW = "carbon.workbench.engineering-value.results-view.v1"


class StudyRefused(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def contract_view(document):
    """A reviewable view of an imported public synthetic contract."""
    if type(document) is not dict:
        raise StudyRefused("contract_malformed")
    scope = (document.get("data_scope") or {}).get("classification")
    if scope != "PUBLIC_SYNTHETIC":
        raise StudyRefused("client_material_requires_private_route")
    try:
        ev.validate(document)
    except (ev.ContractError, ValueError) as refused:
        raise StudyRefused(getattr(refused, "code", "contract_invalid")) from None
    return {
        "schema": CONTRACT_VIEW,
        "contract": {
            "id": document["contract_id"],
            "version": document["version"],
            "digest": ev.digest(document),
            "status": document["status"],
        },
        "decision": document["decision"]["statement"],
        "intended_use": document["decision"]["intended_use"],
        "design_variables": {
            name: {"unit": spec["unit"], "allowed": list(spec["allowed"])}
            for name, spec in document["design_variables"].items()
        },
        "operating_envelope": document["operating_conditions"]["envelope"],
        "scenarios": {
            split: [s["id"] for s in document["scenarios"][split]]
            for split in ("development", "verification")
        },
        "objective": {
            k: document["objective"][k] for k in ("name", "sense", "unit", "definition")
        },
        "constraints": document["constraints"],
        "preferences_status": document["preferences_status"],
        "reference_limitations": document["reference"]["measurement_limitations"],
        "data_scope": document["data_scope"],
        "qualification": "NOT_QUALIFIED",
    }


def results_view(results):
    """A read-only view of a retained EV1 results document."""
    if (
        type(results) is not dict
        or results.get("schema") != "carbon.engineering-value-results.v1"
    ):
        raise StudyRefused("results_malformed")
    if (
        results.get("claims", {}).get("evidence_class")
        != "PUBLIC_SYNTHETIC_DEVELOPMENT"
    ):
        raise StudyRefused("client_material_requires_private_route")
    summary = results["summary"]
    return {
        "schema": RESULTS_VIEW,
        "contract_digest": results["contract_digest"],
        "scenarios": {
            sid: {
                "split": info["split"],
                "best_in_tested_set": info["best_in_tested_set"],
                "status_counts": info["status_counts"],
            }
            for sid, info in results["references"].items()
        },
        "members": summary["members"],
        "rules": {
            rule: {
                "measurable": row["measurable"],
                "tau_development": row["tau_development"],
                "tau_verification": row["tau_verification"],
            }
            for rule, row in results["comparison"].items()
        },
        "chosen_rule": summary["chosen_rule_on_development"],
        "claims": results["claims"],
        "qualification": "NOT_QUALIFIED",
        "verified_by": "import only; reread from the experiment root to verify",
    }
