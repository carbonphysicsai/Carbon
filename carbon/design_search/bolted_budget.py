"""Isolated REPRESENTATIVE proposal; no grant or historical identity change."""

from __future__ import annotations

from . import budget_registration as br

FAMILY = "bolted-joint"
REGISTRATION_ID = "BOLTED-JOINT-REPRESENTATIVE-PROPOSED-V1"


def proposal():
    return br.seal(
        {
            "schema": br.SCHEMA,
            "registration_id": REGISTRATION_ID,
            "authority": "Owner's BOLTED-JOINT-REHEARSAL-BUILD-01 engineering preparation; budgets are ASSUMPTION, not adopted or execution authority",
            "evidence_scope": "REPRESENTATIVE",
            "challenge_budgets": {
                FAMILY: {
                    "decision_scope": "One complete eccentric joint choice across every assembly/lock/service condition; partial histories are not evaluations",
                    "basis": "ASSUMPTION",
                    "justification": "Base 8 complete menu evaluations, 2 host-hours and 4 core-hours. Unmeasured sensitivity only; all fit, queries, failures and verification charged equally.",
                    "source_refs": [
                        "docs/development/challenge_pipeline/activation-kits/bolted-joint.md",
                        "docs/development/challenge_pipeline/bolted-rehearsal/README.md",
                    ],
                    "tiers": {
                        "half": {
                            "solver_evaluations": 4,
                            "wall_s": 3600,
                            "core_s": 7200,
                        },
                        "base": {
                            "solver_evaluations": 8,
                            "wall_s": 7200,
                            "core_s": 14400,
                        },
                        "double": {
                            "solver_evaluations": 16,
                            "wall_s": 14400,
                            "core_s": 28800,
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
        raise br.BudgetRegistrationError(
            "closed representative budget proposal required"
        )
    if (
        raw["schema"] != br.SCHEMA
        or raw["registration_id"] != REGISTRATION_ID
        or raw["evidence_scope"] != "REPRESENTATIVE"
    ):
        raise br.BudgetRegistrationError("representative proposal identity required")
    if raw["registration_digest"] != br._digest(
        {k: v for k, v in raw.items() if k != "registration_digest"}
    ):
        raise br.BudgetRegistrationError("budget proposal digest mismatch")
    rows = raw["challenge_budgets"]
    if type(rows) is not dict or set(rows) != {FAMILY}:
        raise br.BudgetRegistrationError("bolted family only")
    row = rows[FAMILY]
    if (
        type(row) is not dict
        or set(row)
        != {"decision_scope", "basis", "justification", "source_refs", "tiers"}
        or row["basis"] != "ASSUMPTION"
    ):
        raise br.BudgetRegistrationError("unmeasured proposal provenance required")
    if any(
        type(raw[k]) is not str or not raw[k].strip() for k in ("authority",)
    ) or any(
        type(row[k]) is not str or not row[k].strip()
        for k in ("decision_scope", "justification")
    ):
        raise br.BudgetRegistrationError("nonempty authority/decision/basis required")
    if (
        type(row["source_refs"]) is not list
        or not row["source_refs"]
        or any(type(v) is not str or not v for v in row["source_refs"])
    ):
        raise br.BudgetRegistrationError("source pointers required")
    return br.RegisteredBudgets(
        REGISTRATION_ID,
        raw["registration_digest"],
        {FAMILY: br._tiers(row["tiers"], FAMILY)},
    )
