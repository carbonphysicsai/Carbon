"""Additive representative full-history budget proposal; not a paid grant."""

from carbon.design_search import budget_registration as br

FAMILY = "package-warpage"
ID = "WARPAGE-REHEARSAL-PROPOSED-V1"


def validate(raw):
    if (
        type(raw) is not dict
        or set(raw)
        != {
            "schema",
            "registration_id",
            "authority",
            "evidence_scope",
            "challenge_budgets",
            "registration_digest",
        }
        or raw["schema"] != br.SCHEMA
        or raw["registration_id"] != ID
        or raw["evidence_scope"] != "DEVELOPMENT"
    ):
        raise br.BudgetRegistrationError(
            "closed representative warpage proposal required"
        )
    if not isinstance(raw["authority"], str) or not raw["authority"].strip():
        raise br.BudgetRegistrationError("owner preparation authority required")
    if raw["registration_digest"] != br._digest(
        {k: v for k, v in raw.items() if k != "registration_digest"}
    ):
        raise br.BudgetRegistrationError("budget digest mismatch")
    if type(raw["challenge_budgets"]) is not dict or set(raw["challenge_budgets"]) != {
        FAMILY
    }:
        raise br.BudgetRegistrationError("do not change historical family budgets")
    row = raw["challenge_budgets"][FAMILY]
    if type(row) is not dict or set(row) != {
        "decision_scope",
        "basis",
        "justification",
        "source_refs",
        "tiers",
    }:
        raise br.BudgetRegistrationError("complete provenance required")
    if row["basis"] != "ASSUMPTION" or any(
        not isinstance(row[f], str) or not row[f].strip()
        for f in ("decision_scope", "justification")
    ):
        raise br.BudgetRegistrationError("unmeasured budget must be an assumption")
    if (
        type(row["source_refs"]) is not list
        or not row["source_refs"]
        or any(not isinstance(s, str) or not s for s in row["source_refs"])
    ):
        raise br.BudgetRegistrationError("source pointers required")
    return br.RegisteredBudgets(
        ID, raw["registration_digest"], {FAMILY: br._tiers(row["tiers"], FAMILY)}
    )


def proposal():
    return br.seal(
        {
            "schema": br.SCHEMA,
            "registration_id": ID,
            "authority": "Owner 2026-10-11 preparation only; no run/spend or science acceptance",
            "evidence_scope": "DEVELOPMENT",
            "challenge_budgets": {
                FAMILY: {
                    "decision_scope": "one representative full-history package choice, every required stratum; direct/model/cheap arms",
                    "basis": "ASSUMPTION",
                    "justification": "Comparison capacity sensitivity, not measured affordability or a pilot grant; setup, fit, every failed/refined/verification attempt counts",
                    "source_refs": [
                        "docs/development/challenge_pipeline/discovery/warpage-packet/PACKAGE_WARPAGE_DESIGN_PACKET.md"
                    ],
                    "tiers": {
                        "half": {
                            "solver_evaluations": 4,
                            "wall_s": 7200,
                            "core_s": 115200,
                        },
                        "base": {
                            "solver_evaluations": 8,
                            "wall_s": 14400,
                            "core_s": 230400,
                        },
                        "double": {
                            "solver_evaluations": 16,
                            "wall_s": 28800,
                            "core_s": 460800,
                        },
                    },
                }
            },
        }
    )
