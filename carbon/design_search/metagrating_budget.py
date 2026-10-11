"""Additive DEVELOPMENT MG budget route; no mutation of EQUAL-BUDGET-V1.

Uses #1047's exact provenance/tier shape and hard accounting. This accepts a
proposal for comparison software, never solver dispatch or paid authority.
"""

from carbon.design_search import budget_registration as br

FAMILY = "metagrating-3d"
ID = "EQUAL-BUDGET-MG-DEVELOPMENT-V1"


def validate(raw):
    if type(raw) is not dict or set(raw) != {
        "schema",
        "registration_id",
        "authority",
        "evidence_scope",
        "challenge_budgets",
        "registration_digest",
    }:
        raise br.BudgetRegistrationError("closed MG budget form required")
    if (
        raw["schema"] != br.SCHEMA
        or raw["registration_id"] != ID
        or raw["evidence_scope"] != "DEVELOPMENT"
    ):
        raise br.BudgetRegistrationError(
            "prospective DEVELOPMENT MG registration required"
        )
    if not isinstance(raw["authority"], str) or not raw["authority"]:
        raise br.BudgetRegistrationError("delegated authority record required")
    if raw["registration_digest"] != br._digest(
        {k: v for k, v in raw.items() if k != "registration_digest"}
    ):
        raise br.BudgetRegistrationError("budget digest mismatch")
    if type(raw["challenge_budgets"]) is not dict or set(raw["challenge_budgets"]) != {
        FAMILY
    }:
        raise br.BudgetRegistrationError(
            "MG extension must not alter historical four-family budgets"
        )
    row = raw["challenge_budgets"][FAMILY]
    if type(row) is not dict or set(row) != {
        "decision_scope",
        "basis",
        "justification",
        "source_refs",
        "tiers",
    }:
        raise br.BudgetRegistrationError("complete MG budget provenance required")
    if row["basis"] != "ASSUMPTION" or any(
        not isinstance(row[f], str) or not row[f].strip()
        for f in ("decision_scope", "justification")
    ):
        raise br.BudgetRegistrationError("honest assumed budget basis required")
    if (
        type(row["source_refs"]) is not list
        or not row["source_refs"]
        or any(not isinstance(r, str) or not r for r in row["source_refs"])
    ):
        raise br.BudgetRegistrationError("source anchors required")
    tiers = br._tiers(row["tiers"], FAMILY)
    return br.RegisteredBudgets(ID, raw["registration_digest"], {FAMILY: tiers})
