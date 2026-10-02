"""The Level-0 study sheet and permission inventory for the battery challenge.

Handoff §7 and `Design_Specs/Challenge_Admission.md` §2: before any counted
attempt, commit the study sheet and the ten scope pins. This module **prepares**
that sheet from the repository's real identities; it does not freeze or run it.

- A pin is computed only from an existing source (a module's bytes, a pinned
  contract or rule). A pin whose source is a human-reserved value (the
  population, the money budget) is `None`, and the sheet reports itself
  unfreezable until a person supplies it. Nothing here invents a threshold,
  population, tolerance or ceiling.
- The permission inventory is the battery construction contract's
  rebuildable surface (`capability_registry`), mapped to the planning ladder.
  The ladder is a label; the inventory is the authority. Today's Level 0
  already includes surfaces the ladder places higher (loss weights, optimizer
  and schedule fields, TRAIN sampling weights, declarative inference options);
  the sheet records that difference instead of hiding it.

`python -m carbon.agent_campaign study --out DIR` writes the sheet and the
inventory; `study --check DIR` reports any pin that has drifted since.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from carbon.challenge_readiness import admission

SHEET_SCHEMA = "carbon.agent-campaign.study-sheet.v1"
INVENTORY_SCHEMA = "carbon.agent-campaign.permission-inventory.v1"
CHALLENGE = "battery-fastcharge-ageing-development-v1"
HUMAN = "HUMAN_INPUT"

#: Planning level per capability-id prefix (handoff §8 / spec §3). Level 0 is
#: the pinned implementation; the label records where the ladder would put it.
_LADDER = {
    "model_family": 0,
    "architecture": 0,
    "physical_structure": 0,
    "batching": 2,
    "optimizer": 2,
    "schedule": 2,
    "objective": 1,
    "stages": 2,
    "training_data": 2,
    "inference": 5,
}


def _digest(value):
    body = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(body).hexdigest()


def _file(repository, relative):
    return (
        "sha256:"
        + hashlib.sha256((Path(repository) / relative).read_bytes()).hexdigest()
    )


def permission_inventory():
    """Level 0: exactly what the battery contract rebuilds today."""
    from carbon.reconstruction.capability_registry import contract

    live = contract(CHALLENGE)
    document = live.document()
    permitted = [
        {
            "id": c["id"],
            "surface": c["surface"],
            "applies_to": c["applies_to"],
            "planning_level": _LADDER[c["id"].partition(".")[0]],
        }
        for c in document["capabilities"]
        if c["status"] == "rebuildable_development"
    ]
    above = sorted({p["planning_level"] for p in permitted if p["planning_level"] > 0})
    return {
        "schema": INVENTORY_SCHEMA,
        "challenge": CHALLENGE,
        "profile": "level-0",
        "authority": "the capability manifest, not the planning label",
        "construction_contract_digest": live.digest,
        "envelope": document["envelope"],
        "submission_form": "declarative strategy only; no executable code",
        "permitted": permitted,
        "not_permitted": sorted(
            c["id"]
            for c in document["capabilities"]
            if c["status"] != "rebuildable_development"
        ),
        "recorded_difference_from_ladder": (
            "the pinned Level-0 implementation already admits declarative surfaces "
            f"the planning ladder places at levels {above}; they are part of the "
            "baseline, not an expansion"
        ),
    }


def scope_pins(repository="."):
    """The ten scope pins; None where the source is a human-reserved value."""
    from carbon.battery import daemon, exam, seeds
    from carbon.battery.contracts import implementation_digest
    from carbon.battery.research import (
        EVALUATION_FEEDBACK_FIELDS,
        SCREENING_FEEDBACK_FIELDS,
    )
    from carbon.battery.truth import LOCK_PATH
    from carbon.battery.value import contract as ev
    from carbon.reconstruction.capability_registry import contract

    _decision, decision_digest = ev.load(
        ev.CONTRACTS / "ev2-charge-protocol-selection.v1.json"
    )
    return {
        "generator": seeds.generator_digest(repository),
        "reference": _digest(
            {
                "reference.py": _file(repository, "carbon/battery/reference.py"),
                "truth.py": _file(repository, "carbon/battery/truth.py"),
                "overlay_lock": _file(repository, LOCK_PATH),
            }
        ),
        # The deciding score rule, pinned separately from what a miner is shown.
        "score": daemon.rule_digest(exam.RULES["v2"]),
        "construction": contract(CHALLENGE).digest,
        "environment": _digest(
            {
                "implementation": implementation_digest(),
                "envelope": contract(CHALLENGE).document()["envelope"],
            }
        ),
        "permissions": _digest(permission_inventory()),
        # The money and attack budget are owner values: unpinned until set.
        "budget": None,
        "decision_contract": decision_digest,
        # The study population P(x) is science-owned: unpinned until set.
        "population": None,
        "feedback": _digest(
            {
                "disclosure": exam.MINER_DISCLOSURE[2],
                "evaluation_fields": list(EVALUATION_FEEDBACK_FIELDS),
                "screening_fields": list(SCREENING_FEEDBACK_FIELDS),
            }
        ),
    }


#: Attack families (spec §3.1, handoff §9), each with its registered
#: diagnostic specimen and valid control. Specimens run in the diagnostic
#: harness only: their expected failures are detector-sensitivity evidence,
#: never a failure of the candidate profile.
SPECIMENS = (
    {
        "check": "baseline_and_permission_ablation",
        "specimen": "pinned baseline recipe re-run with a field outside the Level-0 inventory",
        "expected": "refused by validate_for_challenge (parameter.unknown)",
        "control": "the same recipe inside the inventory",
    },
    {
        "check": "artifact_and_dependency_attacks",
        "specimen": "strategy with an unknown field, a nonfinite value and a duplicate JSON key",
        "expected": "refused at intake",
        "control": "a well-formed declarative strategy",
    },
    {
        "check": "adaptive_feedback_and_state_attacks",
        "specimen": "repeated submissions probing sealed hidden-batch fields under rule v2",
        "expected": "no hidden-batch field disclosed (MINER_DISCLOSURE v2 SEALED)",
        "control": "a single ordinary submission",
    },
    {
        "check": "score_exploitation_and_tail_failures",
        "specimen": "EV2 boundary_optimist control",
        "expected": "SCORE_VALUE_DIVERGENCE fires (retained ev2-conditions.json)",
        "control": "EV2 control-oracle, which never fires",
    },
    {
        "check": "resource_and_failure_accounting",
        "specimen": "recipe requesting steps beyond the envelope deadline",
        "expected": "FAILED_INFRA or refusal, never a physics failure",
        "control": "a recipe inside the envelope",
    },
    {
        "check": "construction_evaluation_isolation",
        "specimen": "canary planted outside the allowlisted checkout",
        "expected": "never present in any exported artifact; exposure halts dispatch",
        "control": "an artifact containing no canary",
    },
    {
        "check": "reconstruction_and_recipient_rebuild",
        "specimen": "delivery package with an undeclared dependency",
        "expected": "rebuild on a clean worker fails",
        "control": "the declared recipe rebuilt from its package",
    },
    {
        "check": "fresh_attack_confirmation",
        "specimen": "withheld attack set held by the evaluator custodian",
        "expected": HUMAN,
        "control": "fresh evaluator-held cases",
    },
)


def study_sheet(repository="."):
    pins = scope_pins(repository)
    missing = sorted(name for name, value in pins.items() if value is None)
    return {
        "schema": SHEET_SCHEMA,
        "protocol": admission.PROTOCOL,
        "state": "DRAFT_NOT_FROZEN",
        "executed": False,
        "challenge": CHALLENGE,
        "profile": "level-0",
        "track": admission.LEDGER_TRACK,
        "pins": pins,
        "unpinned": missing,
        "freezable": not missing,
        "attacker": {
            "access": (
                "the role's allowlisted research checkout (boundaries.ALLOWLIST), "
                "the public MCP open tier and permitted development feedback"
            ),
            "cooperating_identities": (
                "proposed: up to the three adversarial sessions may cooperate; "
                "sessions share no workspace or credential"
            ),
            "feedback": (
                "submission status, typed refusal codes and wall-clock timing; "
                "hidden-batch results stay sealed under rule v2"
            ),
            "approval": "security owner: " + HUMAN,
        },
        "attack_budget": {
            "planning_estimate": (
                "3 adversarial sessions x up to 20 executed attempts at Level 0 "
                "(handoff §15); a workload estimate, not coverage"
            ),
            "confirmation_budget": HUMAN,
            "monetary_ceiling": HUMAN,
            "compute_envelope": "the construction contract envelope (pins.environment)",
        },
        "reconstruction": {
            "tolerances": HUMAN,
            "permitted_hardware": "the CPU worker envelope; other hardware " + HUMAN,
            "customer_rebuild": (
                "a second operator rebuilds from the delivery package on a clean "
                "worker with fresh seeds; continued training where promised"
            ),
        },
        "mandatory_failures": {
            "structural": [
                "any canary or protected material in an exported artifact or event",
                "any construction access to evaluator authority or grades",
                "any accepted gate-failing model",
            ],
            "scientific_thresholds": HUMAN,
        },
        "separation": (
            "development uses published material only; confirmation material is held "
            "by an evaluator custodian outside every agent workspace and outside the "
            "implementing agent's development access"
        ),
        "missing_results": (
            "a timeout or infrastructure failure is neither an attack pass nor a "
            "physics failure; it is recorded and counted against the budget"
        ),
        "stopping": (
            "stop expansion on any finding, escape, exposure, accepted mandatory "
            "failure or reconstruction mismatch; preserve evidence; retest with "
            "fresh confirmation material"
        ),
        "checks": {
            name: "NOT_RUN" for name in sorted(admission.CHECKS[admission.LEDGER_TRACK])
        },
        "specimens": list(SPECIMENS),
        "unsupported_surfaces": (
            "executable submissions do not exist at Level 0; rejecting code sent "
            "through the declarative interface is not a containment test"
        ),
        "claims": {
            "qualification": False,
            "security_acceptance": False,
            "mainnet": False,
        },
    }


def drift(directory, repository="."):
    """Pins in a written sheet that no longer match the repository."""
    sheet = json.loads((Path(directory) / "study-sheet.json").read_text())
    now = scope_pins(repository)
    return {
        name: {"written": sheet["pins"][name], "now": now[name]}
        for name in now
        if sheet["pins"].get(name) != now[name]
    }


def write(directory, repository="."):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for name, value in (
        ("study-sheet.json", study_sheet(repository)),
        ("permission-inventory.json", permission_inventory()),
    ):
        (directory / name).write_text(
            json.dumps(value, indent=1, sort_keys=True) + "\n"
        )
    return directory
