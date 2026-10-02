"""Battery's adapter for the Challenge-neutral admission study sheet.

`carbon.agent_campaign.study` prepares the Level-0 study sheet and permission
inventory for any Challenge (OWNER-GRAPHITE-04). This module is what battery
supplies to it, moved here unchanged from the shared module:

- battery's capability-to-level map (`LADDER`);
- the sources of battery's own scope pins: the reference generator, the
  reference and truth code, the deciding rule v2, the implementation and
  envelope, the EV2 decision contract and the feedback policy;
- battery's registered attack specimens and the sheet text naming rule v2.

A second Challenge supplies the same items in its own adapter and registers it
in `study._studies`.
"""

from __future__ import annotations

from carbon.agent_campaign.study import HUMAN, ChallengeStudy, digest, file_digest
from carbon.reconstruction.capability_registry import BATTERY_CHALLENGE
from carbon.reconstruction.capability_registry import contract as _contract

CHALLENGE = BATTERY_CHALLENGE

#: Battery's map onto Admission §3's planning ladder, per capability
#: dimension. Level 0 is the pinned implementation; the label records where
#: the ladder would put a dimension. Hybrid templates and learned
#: time-steppers have no rebuildable battery capability; they are placed at
#: Level 4, new model forms behind the constrained inference interface, so
#: that every dimension of battery's contract is placed (GA-D1).
LADDER = {
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
    "hybrid": 4,
    "prediction": 4,
}


def pins(repository="."):
    """Battery's own scope pins; the shared module adds construction and
    permissions."""
    from carbon.battery import daemon, exam, seeds
    from carbon.battery.contracts import implementation_digest
    from carbon.battery.research import (
        EVALUATION_FEEDBACK_FIELDS,
        SCREENING_FEEDBACK_FIELDS,
    )
    from carbon.battery.truth import LOCK_PATH
    from carbon.battery.value import contract as ev

    _decision, decision_digest = ev.load(
        ev.CONTRACTS / "ev2-charge-protocol-selection.v1.json"
    )
    return {
        "generator": seeds.generator_digest(repository),
        "reference": digest(
            {
                "reference.py": file_digest(repository, "carbon/battery/reference.py"),
                "truth.py": file_digest(repository, "carbon/battery/truth.py"),
                "overlay_lock": file_digest(repository, LOCK_PATH),
            }
        ),
        # The deciding score rule, pinned separately from what a miner is shown.
        "score": daemon.rule_digest(exam.RULES["v2"]),
        "environment": digest(
            {
                "implementation": implementation_digest(),
                "envelope": _contract(CHALLENGE).document()["envelope"],
            }
        ),
        # The money and attack budget are owner values: unpinned until set.
        "budget": None,
        "decision_contract": decision_digest,
        # The study population P(x) is science-owned: unpinned until set.
        "population": None,
        "feedback": digest(
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

STUDY = ChallengeStudy(
    challenge=CHALLENGE,
    contract=lambda: _contract(CHALLENGE),
    ladder=LADDER,
    pins=pins,
    specimens=SPECIMENS,
    attacker_feedback=(
        "submission status, typed refusal codes and wall-clock timing; "
        "hidden-batch results stay sealed under rule v2"
    ),
    permitted_hardware="the CPU worker envelope; other hardware " + HUMAN,
)
