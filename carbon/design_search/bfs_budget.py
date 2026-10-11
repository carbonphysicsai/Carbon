"""Additive BFS DEVELOPMENT proposal using #1047 accounting, not a grant."""

from carbon.design_search import budget_registration as br

FAMILY = "backward-facing-step"
ID = "BFS-DEVELOPMENT-PROPOSED-V1"


def validate(raw):
    if type(raw) is not dict or set(raw) != {
        "schema",
        "registration_id",
        "authority",
        "evidence_scope",
        "challenge_budgets",
        "registration_digest",
    }:
        raise br.BudgetRegistrationError("closed BFS budget form required")
    if (
        raw["schema"] != br.SCHEMA
        or raw["registration_id"] != ID
        or raw["evidence_scope"] != "DEVELOPMENT"
    ):
        raise br.BudgetRegistrationError(
            "prospective BFS development proposal required"
        )
    if not isinstance(raw["authority"], str) or not raw["authority"].strip():
        raise br.BudgetRegistrationError("delegated proposal authority record required")
    if raw["registration_digest"] != br._digest(
        {k: v for k, v in raw.items() if k != "registration_digest"}
    ):
        raise br.BudgetRegistrationError("BFS budget digest mismatch")
    if type(raw["challenge_budgets"]) is not dict or set(raw["challenge_budgets"]) != {
        FAMILY
    }:
        raise br.BudgetRegistrationError(
            "extension must not change historical four-family budgets"
        )
    row = raw["challenge_budgets"][FAMILY]
    if type(row) is not dict or set(row) != {
        "decision_scope",
        "basis",
        "justification",
        "source_refs",
        "tiers",
    }:
        raise br.BudgetRegistrationError("complete BFS provenance required")
    if row["basis"] != "ASSUMPTION" or any(
        not isinstance(row[k], str) or not row[k].strip()
        for k in ("decision_scope", "justification")
    ):
        raise br.BudgetRegistrationError("honest assumed BFS budget basis required")
    if (
        type(row["source_refs"]) is not list
        or not row["source_refs"]
        or any(not isinstance(r, str) or not r.strip() for r in row["source_refs"])
    ):
        raise br.BudgetRegistrationError("BFS source anchors required")
    return br.RegisteredBudgets(
        ID, raw["registration_digest"], {FAMILY: br._tiers(row["tiers"], FAMILY)}
    )
