"""Prospective f08 comparison budgets, not a reference-run or spending grant."""

from carbon.design_search import budget_registration as br

FAMILY = "f08"
ID = "F08-DEVELOPMENT-PROPOSED-V1"


def proposal():
    return br.seal(
        {
            "schema": br.SCHEMA,
            "registration_id": ID,
            "authority": "F08-STRUCTURES-READINESS-BUILD-01; owner requested preparation, budget amounts ASSUMPTION",
            "evidence_scope": "DEVELOPMENT",
            "challenge_budgets": {
                FAMILY: {
                    "decision_scope": "One common support over all three complete damping curves; static/eigen acquisition plus all verification/refinements charged",
                    "basis": "ASSUMPTION",
                    "justification": "4/8/16 complete geometry evaluations and 1/2/4 serial host/core hours are sensitivity proposals, not measured cost or approved capacity",
                    "source_refs": [
                        "docs/development/challenge_pipeline/round1/f08-resonance-structure.md",
                        "docs/development/challenge_pipeline/cheap-baselines/f08.md",
                    ],
                    "tiers": {
                        name: {"solver_evaluations": n, "wall_s": wall, "core_s": wall}
                        for name, n, wall in (
                            ("half", 4, 3600),
                            ("base", 8, 7200),
                            ("double", 16, 14400),
                        )
                    },
                }
            },
        }
    )


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
        raise br.BudgetRegistrationError("closed prospective f08 registration required")
    if (
        not isinstance(raw["authority"], str)
        or not raw["authority"].strip()
        or raw["registration_digest"]
        != br._digest({k: v for k, v in raw.items() if k != "registration_digest"})
    ):
        raise br.BudgetRegistrationError("authority and complete digest required")
    if type(raw["challenge_budgets"]) is not dict or set(raw["challenge_budgets"]) != {
        FAMILY
    }:
        raise br.BudgetRegistrationError(
            "historical four-family budgets remain unchanged"
        )
    row = raw["challenge_budgets"][FAMILY]
    if (
        type(row) is not dict
        or set(row)
        != {"decision_scope", "basis", "justification", "source_refs", "tiers"}
        or row["basis"] != "ASSUMPTION"
        or any(
            not isinstance(row[k], str) or not row[k].strip()
            for k in ("decision_scope", "justification")
        )
        or not isinstance(row["source_refs"], list)
        or not row["source_refs"]
        or any(not isinstance(v, str) or not v for v in row["source_refs"])
    ):
        raise br.BudgetRegistrationError("complete honest f08 provenance required")
    return br.RegisteredBudgets(
        ID, raw["registration_digest"], {FAMILY: br._tiers(row["tiers"], FAMILY)}
    )
