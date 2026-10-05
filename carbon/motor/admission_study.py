"""Motor's adapter for the Challenge-neutral Level-0 admission sheet."""

from __future__ import annotations

from carbon.agent_campaign.study import HUMAN, ChallengeStudy, digest, file_digest
from carbon.reconstruction.capability_registry import MOTOR_CHALLENGE
from carbon.reconstruction.capability_registry import contract as _contract

CHALLENGE = MOTOR_CHALLENGE

# Every construction dimension is deliberately placed even where Level 0 has
# no rebuildable capability in that dimension.  A planning label grants
# nothing; the capability manifest remains the permission boundary.
LADDER = {
    "model_family": 0,
    "architecture": 0,
    "physical_structure": 1,
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
    from .contracts import implementation_digest

    return {
        "generator": file_digest(repository, "carbon/motor/population.py"),
        "reference": digest(
            {
                "mesh": file_digest(repository, "carbon/motor/mesh.py"),
                "getdp": file_digest(repository, "carbon/motor/getdp.py"),
                "runner": file_digest(
                    repository, "scripts/dev/motor/reference/run_batch.py"
                ),
                "dockerfile": file_digest(
                    repository, "scripts/dev/motor/reference/Dockerfile"
                ),
            }
        ),
        "score": file_digest(repository, "carbon/motor/exam.py"),
        "environment": digest(
            {
                "implementation": implementation_digest(),
                "envelope": _contract(CHALLENGE).document()["envelope"],
                "worker": "verified C-03 Linux CPU isolated carrier",
            }
        ),
        # Attack/monetary authority remains owner-held.
        "budget": None,
        "decision_contract": file_digest(
            repository,
            "docs/development/studies/MOTOR_SYNTHETIC_DECISION_V1.json",
        ),
        # A fresh evaluator-held confirmation population does not exist yet.
        "population": None,
        "feedback": digest(
            {
                "practice": "aggregate public-practice components and typed gates",
                "evaluation": "not served by this construction ticket",
                "private_case_detail": False,
            }
        ),
    }


SPECIMENS = (
    {
        "check": "baseline_and_permission_ablation",
        "specimen": "kernel-ridge strategy with a field outside the Level-0 inventory",
        "expected": "refused by validate_for_challenge (parameter.unknown)",
        "control": "the same strategy with only length and ridge",
    },
    {
        "check": "artifact_and_dependency_attacks",
        "specimen": "strategy with an unknown field, nonfinite ridge or duplicate JSON key",
        "expected": "refused before compilation or worker dispatch",
        "control": "well-formed strict JSON using a registered grid point",
    },
    {
        "check": "adaptive_feedback_and_state_attacks",
        "specimen": "repeated practice requests probing private-pool or decision-reference fields",
        "expected": "only public aggregate practice feedback is disclosed",
        "control": "one ordinary public-practice request",
    },
    {
        "check": "score_exploitation_and_tail_failures",
        "specimen": "flat torque curve with correct mean or a ripple curve shifted to the wrong phase",
        "expected": "typed gates and separate mean/ripple public-practice components expose the failure",
        "control": "registered KRR rebuilt and evaluated on the complete public practice set",
    },
    {
        "check": "resource_and_failure_accounting",
        "specimen": "practice attempt exceeding the pinned worker deadline",
        "expected": "FAILED_INFRA or resource refusal, never a physics or score failure",
        "control": "the default KRR recipe inside the declared CPU envelope",
    },
    {
        "check": "construction_evaluation_isolation",
        "specimen": "canary beside private or decision-study GetDP evidence outside the public allowlist",
        "expected": "the construction worker never receives it; any exposure halts dispatch",
        "control": "worker staging contains only recipe code and digest-pinned public material",
    },
    {
        "check": "reconstruction_and_recipient_rebuild",
        "specimen": "delivery package with changed TRAIN bytes or an undeclared dependency",
        "expected": "digest check or clean-worker rebuild fails closed",
        "control": "the declared recipe rebuilt from the registered package",
    },
    {
        "check": "fresh_attack_confirmation",
        "specimen": "fresh motor confirmation set held only by the evaluator custodian",
        "expected": HUMAN,
        "control": "fresh evaluator-held cases outside every construction workspace",
    },
)

STUDY = ChallengeStudy(
    challenge=CHALLENGE,
    contract=lambda: _contract(CHALLENGE),
    ladder=LADDER,
    pins=pins,
    specimens=SPECIMENS,
    attacker_feedback=(
        "submission state, typed refusal codes, resource outcome and public-practice "
        "aggregate components; no counted, private or confirmation case detail"
    ),
    permitted_hardware=(
        "the pinned Linux CPU reconstruction worker; accelerators and wider hardware "
        "remain " + HUMAN
    ),
    rebuild_policy=(
        "a second operator deterministically refits the registered closed-form KRR "
        "recipe from the same digest-pinned public TRAIN bytes on a clean worker"
    ),
)
