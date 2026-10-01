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

A retired Challenge (the registry's RETIRED status) owes no research
environment, so it is declared `Retired` as a whole: not a per-provision
status, and never a gap. A gap is work owed; retired is work no longer owed.
Its record of what it provided stays here unchanged, so evidence recorded
while it was offered keeps its meaning (OWNER-RESEARCH-ENVIRONMENT-01 as
amended by the owner's decision (a), 27 September 2026).

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
    # OWNER-MINER-ENVIRONMENT-01 (2026-09-30): the environment is fully loaded
    # after registration. Carbon facilitates; the miner's own accounts, keys
    # and machines provide these, and nothing is hosted by Carbon.
    "compute": (
        "A GPU research path on the miner's own or rented hardware, set up "
        "from the Control Center after registration."
    ),
    "model": (
        "The named inference providers, connectable in setup with the "
        "miner's own key."
    ),
    "agent": (
        "The named agents, connectable in setup, driving the Challenge's "
        "research tools."
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


#: A per-provision status. `Retired` is deliberately not one of these.
Status = Provided | Gap


@dataclass(frozen=True)
class Retired:
    """A Challenge no longer offered: it carries no research-environment
    obligation, so nothing about it can be a gap.

    `provided` is the historical record - what the Challenge provided, and
    through which symbols, while it was offered. It is kept, not reinterpreted:
    retiring is prospective and deletes nothing.
    """

    decision: str
    provided: dict[str, Provided]

    def __post_init__(self):
        if not self.decision.strip():
            raise ValueError("a retirement names the decision that made it")
        if not set(self.provided) <= set(PROVISIONS):
            raise ValueError("a retired record names only known provisions")
        if any(type(value) is not Provided for value in self.provided.values()):
            # A gap is work owed; nothing is owed by a retired Challenge.
            raise TypeError("a retired record holds what was provided, never a gap")


REGISTRY_EVIDENCE = "carbon.reconstruction.capability_registry:public_registry"

ENVIRONMENTS: dict[str, dict[str, Status] | Retired] = {
    "burgers-dynamics-v1": Retired(
        decision=(
            "Retired from the research path (#366); kept in this standard as "
            "Retired by the owner's decision (a), 27 September 2026."
        ),
        provided={
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
    ),
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
                "Build carbon/challenge_kit/battery.py as a command on the "
                "miner's own machine (OWNER-MINER-OWN-MACHINE-01): uniform "
                "draws over the published input box from the miner's own seed "
                "roots, labelled by the pinned PyBaMM reference in the pinned "
                "truth image, with the Burgers kit's no-official-seed tests."
            ),
        ),
        "evaluate": Provided(
            ("carbon.battery.practice:score_practice",),
            "Exam gates on the 200 public PRACTICE cases. Scoring "
            "miner-generated cases follows once `generate` is closed.",
        ),
        "compute": Gap(
            reason=(
                "Battery has no GPU research path: its campaign refuses a GPU "
                "runtime, the GPU lane binds Burgers material, and no rented "
                "compute provider has a launch path."
            ),
            next_step=(
                "C-MLP-03 slices 3 and 4: a battery-bound GPU practice path on "
                "the miner's own GPU, then rented GPU on the miner's account."
            ),
        ),
        "model": Gap(
            reason=(
                "Only the priced Engy and pinned adapters launch, and only from "
                "a hand-written runner profile; no named inference provider is "
                "connectable in setup."
            ),
            next_step=(
                "C-MLP-03 slice 2: the named inference providers, connected in "
                "setup with the miner's own key and checked live."
            ),
        ),
        "agent": Gap(
            reason=(
                "Setup offers only Carbon's own autonomous agent. Hermes, the "
                "other agent OWNER-MINER-ENVIRONMENT-01 names, is not "
                "connectable in setup."
            ),
            next_step=(
                "C-MLP-03 slice 5: connect Hermes to the Challenge's research "
                "tools through carbon-mcp. Closing this does not wait on Mira, "
                "which the decision adds only once verified (which Mira is "
                "open owner input)."
            ),
        ),
    },
}


def offered() -> dict[str, dict[str, Status]]:
    """The Challenges that owe a research environment: every one not retired."""
    return {
        challenge: table
        for challenge, table in ENVIRONMENTS.items()
        if not isinstance(table, Retired)
    }


def retired() -> dict[str, Retired]:
    return {
        challenge: record
        for challenge, record in ENVIRONMENTS.items()
        if isinstance(record, Retired)
    }


def gaps() -> dict[str, dict[str, Gap]]:
    """Every open gap, by offered Challenge, for reports and the Hub. A
    retired Challenge owes nothing and is never reported here."""
    return {
        challenge: {k: v for k, v in table.items() if isinstance(v, Gap)}
        for challenge, table in offered().items()
        if any(isinstance(v, Gap) for v in table.values())
    }
