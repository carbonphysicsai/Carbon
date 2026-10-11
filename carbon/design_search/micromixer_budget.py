"""F17-only prospective comparison budget; preserve historical registrations."""

from carbon.design_search import budget_registration as br

FAMILY = "f17"
ID = "F17-DEVELOPMENT-PROPOSED-V1"


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
        raise br.BudgetRegistrationError("closed prospective f17 budget required")
    if not isinstance(raw["authority"], str) or not raw["authority"].strip():
        raise br.BudgetRegistrationError("preparation authority required")
    if raw["registration_digest"] != br._digest(
        {k: v for k, v in raw.items() if k != "registration_digest"}
    ):
        raise br.BudgetRegistrationError("budget digest mismatch")
    if type(raw["challenge_budgets"]) is not dict or set(raw["challenge_budgets"]) != {
        FAMILY
    }:
        raise br.BudgetRegistrationError("f17 only; never change historical budgets")
    row = raw["challenge_budgets"][FAMILY]
    if type(row) is not dict or set(row) != {
        "decision_scope",
        "basis",
        "justification",
        "source_refs",
        "tiers",
    }:
        raise br.BudgetRegistrationError("complete f17 provenance required")
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
        raise br.BudgetRegistrationError("source pointers required")
    return br.RegisteredBudgets(
        ID, raw["registration_digest"], {FAMILY: br._tiers(row["tiers"], FAMILY)}
    )


def proposal():
    return br.seal(
        {
            "schema": br.SCHEMA,
            "registration_id": ID,
            "authority": "Owner 2026-10-11 preparation only; no solver/spend/science acceptance",
            "evidence_scope": "DEVELOPMENT",
            "challenge_budgets": {
                FAMILY: {
                    "decision_scope": "one full nine-condition finite-channel geometry choice, charged flow plus scalar; direct/model/cheap arms",
                    "basis": "ASSUMPTION",
                    "justification": "Capacity sensitivity; full-case C1 remains UNMEASURED. Charge meshes, flows, scalar, fits, failed/refined and verification attempts. No free velocity oracle.",
                    "source_refs": [
                        "docs/development/challenge_pipeline/round1/f17-passive-micromixer.md",
                        "docs/development/challenge_pipeline/cheap-baselines/f17.md",
                    ],
                    "tiers": {
                        "half": {
                            "solver_evaluations": 2,
                            "wall_s": 7200,
                            "core_s": 115200,
                        },
                        "base": {
                            "solver_evaluations": 4,
                            "wall_s": 14400,
                            "core_s": 230400,
                        },
                        "double": {
                            "solver_evaluations": 8,
                            "wall_s": 28800,
                            "core_s": 460800,
                        },
                    },
                }
            },
        }
    )
