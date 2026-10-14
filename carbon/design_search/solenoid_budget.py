"""Isolated representative solenoid comparison proposal, not a launch grant."""

from carbon.design_search import budget_registration as br

FAMILY = "solenoid-pole"
ID = "SOLENOID-POLE-PILOT-PROPOSED-V1"


def proposal():
    return br.seal(
        {
            "schema": br.SCHEMA,
            "registration_id": ID,
            "authority": "PKT-10 PILOT-RUNNABILITY-TOP2-01; engineering ASSUMPTION only, owner selects scientific and buyer budgets",
            "evidence_scope": "REPRESENTATIVE",
            "challenge_budgets": {
                FAMILY: {
                    "decision_scope": "One pole geometry across nominal/hot/gap, each 27 nonlinear field states plus required refinement and virtual-work probes",
                    "basis": "ASSUMPTION",
                    "justification": "Complete twelve-geometry menu, four serial wall/core hours per question; half/double sensitivity. Not the separate USD36.40 acquisition/worker lifecycle cap; no adoption or spend grant.",
                    "source_refs": [
                        "docs/development/challenge_pipeline/challenge-factory/pilots/solenoid-pole.md"
                    ],
                    "tiers": {
                        name: {
                            "solver_evaluations": count,
                            "wall_s": seconds,
                            "core_s": seconds,
                        }
                        for name, count, seconds in (
                            ("half", 6, 7200),
                            ("base", 12, 14400),
                            ("double", 24, 28800),
                        )
                    },
                }
            },
        }
    )


def validate(raw):
    # Immutable engineering proposal: it cannot change historical budgets or
    # accept a caller-invented adopted law under this proposal identity.
    if raw != proposal():
        raise br.BudgetRegistrationError(
            "exact representative solenoid proposal required"
        )
    return br.RegisteredBudgets(
        ID,
        raw["registration_digest"],
        {FAMILY: br._tiers(raw["challenge_budgets"][FAMILY]["tiers"], FAMILY)},
    )
