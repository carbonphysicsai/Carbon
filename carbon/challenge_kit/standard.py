"""The research environment standard (OWNER-RESEARCH-ENVIRONMENT-01).

Owner rule, 2026-09-27: "the research environment MUST be enabled with
everything they need to research, hypothesize, train, test, iterate."

Every Challenge with a construction contract declares here, per provision,
either the code that provides it or a named gap. The test
`tests/cpu/test_research_environment_standard.py` fails when:
- a Challenge has a construction contract but no declaration;
- a provision is missing, or its evidence does not import;
- a gap has no reason or no owner-visible next step.

A gap is allowed to exist; it is not allowed to be silent. Closing a gap means
replacing it with `Provided(...)` evidence in the same PR.

This standard governs what a miner can *use*. It never widens what a submission
may *declare* (the construction contract) and never touches official
evaluation: official seeds, derived seeds and draw ids stay out of every
sandbox (invariants 1, 2 and 12; OWNER-CHALLENGE-KIT-01).
"""

from __future__ import annotations

from dataclasses import dataclass

#: The five things the owner named, made concrete. Each Challenge must cover
#: every one.
PROVISIONS = {
    "research": (
        "Public material: the objective, population and sampling description, "
        "reference method description, public datasets and documentation."
    ),
    "hypothesize": (
        "The Challenge's full construction vocabulary, including research-only "
        "entries and why each is gated, so a miner can see what can be tried."
    ),
    "train": (
        "The validator's own construction runtime (the same pinned JAX "
        "environment and training code), runnable by the miner."
    ),
    "generate": (
        "The Challenge's public generator and reference solver, runnable in the "
        "sandbox with the miner's own seeds under the published population, so a "
        "miner can make as much training and test data as they need."
    ),
    "evaluate": (
        "Practice scoring with the exam's own gates and metrics, on public or "
        "miner-generated cases, repeatable so a miner can iterate."
    ),
}


@dataclass(frozen=True)
class Provided:
    """The provision exists. `evidence` is an importable `module:symbol`."""

    evidence: tuple[str, ...]
    note: str = ""


@dataclass(frozen=True)
class Gap:
    """The provision is missing. Both fields are required and non-empty."""

    reason: str
    next_step: str


Status = Provided | Gap

REGISTRY_EVIDENCE = "carbon.reconstruction.capability_registry:public_registry"

ENVIRONMENTS: dict[str, dict[str, Status]] = {
    "burgers-dynamics-v1": {
        "research": Provided(
            ("carbon.development_session.research_service:make_research_service",)
        ),
        "hypothesize": Provided((REGISTRY_EVIDENCE,)),
        "train": Provided(
            ("carbon.development_session.research_image:permitted_files",),
            "The vendored JAX lab ships into the miner analysis image.",
        ),
        "generate": Provided(
            (
                "carbon.challenge_kit.burgers:generate",
                "carbon.challenge_kit.burgers:solve",
            ),
            "OWNER-CHALLENGE-KIT-01: public generator and reference solvers.",
        ),
        "evaluate": Provided(
            ("carbon.development_session.research_service:make_research_service",)
        ),
    },
    "battery-fastcharge-ageing-development-v1": {
        "research": Provided(("carbon.battery.research:challenge_parts",)),
        "hypothesize": Provided((REGISTRY_EVIDENCE,)),
        "train": Provided(
            ("carbon.battery.research:implementation_files",),
            "training.py is published and staged byte-identical in practice.",
        ),
        "generate": Gap(
            reason=(
                "No battery challenge kit. The sandbox offers only the fixed "
                "TRAIN v1 and 200 PRACTICE cases; nothing miner-facing runs the "
                "pinned PyBaMM reference, so a miner cannot generate new "
                "training or test data inside Carbon."
            ),
            next_step=(
                "Build carbon/challenge_kit/battery.py: the pinned PyBaMM "
                "overlay and the public population, miner seeds only, "
                "following the Burgers kit and its no-official-seed tests."
            ),
        ),
        "evaluate": Provided(
            ("carbon.battery.practice:score_practice",),
            "Exam gates on the 200 public PRACTICE cases. Scoring "
            "miner-generated cases follows once `generate` is closed.",
        ),
    },
}


def gaps() -> dict[str, dict[str, Gap]]:
    """Every open gap, by Challenge, for reports and the Hub."""
    return {
        challenge: {k: v for k, v in table.items() if isinstance(v, Gap)}
        for challenge, table in ENVIRONMENTS.items()
        if any(isinstance(v, Gap) for v in table.values())
    }
