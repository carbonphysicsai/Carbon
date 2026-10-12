"""Additive cooling-cell DEVELOPMENT comparison cap, never a paid grant."""

from carbon.design_search import budget_registration as br

FAMILY = "cooling-cell"
ID = "EQUAL-BUDGET-COOLING-DEVELOPMENT-V1"


def proposal():
    return br.seal(
        {
            "schema": br.SCHEMA,
            "registration_id": ID,
            "authority": "COOLING-CELL-READINESS-BUILD-01 owner request; ASSUMPTION proposal for Test Lead, not spend authority",
            "evidence_scope": "DEVELOPMENT",
            "challenge_budgets": {
                FAMILY: {
                    "decision_scope": "one geometry/flow action across every frozen buyer service, final verification included",
                    "basis": "ASSUMPTION",
                    "justification": "Prospective eight complete actions/four serial host-hours on two allocated CPU cores; may not fit. Every condition, refinement, failed attempt, fit, query and final solve counts. Test Lead selects buyer budgets.",
                    "source_refs": [
                        "docs/development/challenge_pipeline/cheap-baselines/cooling-cell.md",
                        "#1047 form; historical EQUAL-BUDGET-V1 unchanged",
                    ],
                    "tiers": {
                        "half": {
                            "solver_evaluations": 4,
                            "wall_s": 7200,
                            "core_s": 14400,
                        },
                        "base": {
                            "solver_evaluations": 8,
                            "wall_s": 14400,
                            "core_s": 28800,
                        },
                        "double": {
                            "solver_evaluations": 16,
                            "wall_s": 28800,
                            "core_s": 57600,
                        },
                    },
                }
            },
        }
    )


def validate(raw):
    if type(raw) is not dict or set(raw) != {
        "schema",
        "registration_id",
        "authority",
        "evidence_scope",
        "challenge_budgets",
        "registration_digest",
    }:
        raise br.BudgetRegistrationError("closed cooling budget form required")
    if (
        raw["schema"] != br.SCHEMA
        or raw["registration_id"] != ID
        or raw["evidence_scope"] != "DEVELOPMENT"
    ):
        raise br.BudgetRegistrationError(
            "prospective DEVELOPMENT cooling registration required"
        )
    if not isinstance(raw["authority"], str) or not raw["authority"].strip():
        raise br.BudgetRegistrationError("authority record required")
    if raw["registration_digest"] != br._digest(
        {k: v for k, v in raw.items() if k != "registration_digest"}
    ):
        raise br.BudgetRegistrationError("budget digest mismatch")
    if type(raw["challenge_budgets"]) is not dict or set(raw["challenge_budgets"]) != {
        FAMILY
    }:
        raise br.BudgetRegistrationError(
            "cooling extension cannot alter historical budgets"
        )
    row = raw["challenge_budgets"][FAMILY]
    if (
        type(row) is not dict
        or set(row)
        != {"decision_scope", "basis", "justification", "source_refs", "tiers"}
        or row["basis"] != "ASSUMPTION"
    ):
        raise br.BudgetRegistrationError(
            "complete assumed cooling budget provenance required"
        )
    if (
        any(
            not isinstance(row[f], str) or not row[f].strip()
            for f in ("decision_scope", "justification")
        )
        or type(row["source_refs"]) is not list
        or not row["source_refs"]
        or any(not isinstance(v, str) or not v.strip() for v in row["source_refs"])
    ):
        raise br.BudgetRegistrationError(
            "scope, justification and source anchors required"
        )
    return br.RegisteredBudgets(
        ID, raw["registration_digest"], {FAMILY: br._tiers(row["tiers"], FAMILY)}
    )
