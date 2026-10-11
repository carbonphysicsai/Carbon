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
        "The validator's own construction runtime (the same pinned backend "
        "environment - JAX, or PyTorch where the Challenge offers it - and "
        "training code), runnable by the miner."
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
        "A GPU research path on hardware the miner runs themselves, set up "
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
#: The compute-cost calculator (OWNER-COMPUTE-BUDGET-01): every Challenge with
#: a training budget adapter offers it under "train".
COST_EVIDENCE = "carbon.training_budget.cost:cost"

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
            (
                "carbon.battery.research:implementation_files",
                "carbon.battery.practice:staged_files",
                COST_EVIDENCE,
            ),
            "training.py and the PyTorch trainer (torch_training.py, "
            "torch_families.py) are published and staged byte-identical in "
            "practice. Practice runs a recipe in its own backend; PyTorch "
            "recipes need the PyTorch worker image "
            "(scripts/dev/torch_worker_image.sh) as the miner's worker image "
            "(OWNER-PYTORCH-BACKEND-01). The cost calculator "
            "(`python -m carbon.training_budget.cost`) is the validator's own, "
            "so a miner sees a recipe's cost and the budget before submitting "
            "(OWNER-COMPUTE-BUDGET-01).",
        ),
        "generate": Provided(
            (
                "carbon.challenge_kit.battery:draw",
                "carbon.challenge_kit.battery:label",
            ),
            "carbon/challenge_kit/battery.py, a command on the miner's own "
            "machine (OWNER-MINER-OWN-MACHINE-01): uniform draws over the "
            "published input box with the validator's own rule "
            "(seeds.draw_inputs), from the miner's own seed roots and mock "
            "seeding only, labelled by the pinned PyBaMM reference in the "
            "pinned truth image through the validator's own no-network solve "
            "run, with typed reference failures. Output has TRAIN v1's shape. "
            "Not in the research sandbox yet; that is a later, separately "
            "reviewed step.",
        ),
        "evaluate": Provided(
            ("carbon.battery.practice:score_practice",),
            "Exam gates on the 200 public PRACTICE cases. Scoring "
            "miner-generated cases (from the battery kit) is not yet wired.",
        ),
        "compute": Provided(
            (
                "carbon.development_session.battery_gpu:gpu_scope",
                "carbon.battery.research:BatteryPractice",
                "carbon.development_session.battery_gpu:remote_worker",
                "carbon.compute.remote_route:campaign_runner",
            ),
            "Setup (Set up your environment, Compute) offers this machine's "
            "CPU, every miner's default, its own GPU, or the miner's own "
            "remote machine or container. For this machine's GPU, setup "
            "detects it, installs the host device record and verifies the "
            "pinned GPU worker (scripts/dev/accelerator_worker_image.sh); "
            "battery practice then runs on it with JAX_PLATFORMS=cuda (C-MLP-03 "
            "slice 3). A remote setup is any the miner runs "
            "(OWNER-MINER-COMPUTE-LINK-ONLY-01, amended 2026-10-02), reached "
            "with their own SSH: a machine with Docker (ssh-docker, the worker "
            "checked by image ID and sent with consent) or a container started "
            "from the pinned worker (ssh-container, its build identity "
            "checked). Carbon never starts, stops or bills it, and the route "
            "is Challenge-neutral (docs/development/MINER_REMOTE_SETUP.md). "
            "Every feedback records the backend observed. GPU practice is for "
            "speed only; the validator rebuilds on its own pinned backend. A "
            "real practice on a local GPU, and one on a remote setup, are the "
            "slices' acceptance and need the hardware. The miner's own code "
            "cell runs on the same GPU lane: run_python, and run_julia in its "
            "CUDA environment (current, CUDA.jl on CUDA 13.0; JULIA-GPU-01) on "
            "this machine's GPU; a remote setup runs run_python only.",
        ),
        "model": Provided(
            (
                "carbon.development_session.model_provider:select",
                "carbon.development_session.model_provider:published_pricing",
            ),
            "Setup (Set up your environment, Inference) connects every adapter "
            "with the miner's own key and checks it live: Engy (Chat "
            "Completions by default, or Messages), Chutes at its published "
            "per-token price, OpenAI, Anthropic, and the OpenAI-compatible "
            "adapters at the miner's own endpoint and declared price "
            "(C-MLP-03 slice 2). A live completion through Chutes and Engy "
            "with miner-held keys is the ticket's acceptance and needs the "
            "miner's keys.",
        ),
        "agent": Provided(
            (
                "scripts.dev.miner_launchpad.hermes_setup:config_document",
                "carbon.miner_mcp.standard_cli:main",
            ),
            "Setup offers Carbon's autonomous agent or Hermes Agent (Nous "
            "Research) on the miner's machine: with consent to the exact files, "
            "setup writes a Hermes profile with the inference choice as its "
            "model and Carbon's MCP server over stdio, each changing tool "
            "asking first (C-MLP-03 slice 5). A Hermes-driven battery campaign "
            "is the acceptance and needs Hermes and the miner's keys. Mira "
            "(autoscience.ai) publishes no tool connection, so it is not "
            "offered.",
        ),
    },
    # CHALLENGE-AI-COOLING-06: Level-0 DEVELOPMENT construction only. Official
    # evaluation stays fail closed (`cooling_validator_not_served`).
    "chip-cold-plate": {
        "research": Provided(
            (
                "carbon.cold_plate.research:challenge_parts",
                "carbon.cold_plate.research:ColdPlatePublicMaterial",
            ),
            "Public material: the objective (task, inputs, outputs, sampling "
            "law, gates, score), the capability registry, the 400 public TRAIN "
            "and 100 public PRACTICE OpenFOAM records, and the reference-method "
            "description. Counted CFD and private material are absent by "
            "structure.",
        ),
        "hypothesize": Provided((REGISTRY_EVIDENCE,)),
        "train": Provided(
            (
                "carbon.cold_plate.research:implementation_files",
                "carbon.cold_plate.practice:staged_files",
            ),
            "The Gaussian kernel-ridge reconstruction (learned_baseline.py, "
            "domain.py, recipes.py) is published and staged byte-identical in "
            "practice, with the pinned public TRAIN bytes, in the pinned NumPy "
            "CPU isolated carrier. It is a closed-form fit; there is no JAX or "
            "PyTorch trainer for this Challenge.",
        ),
        "generate": Gap(
            reason=(
                "No miner-runnable cold-plate kit draws and labels new cases. "
                "The population screen and draw (carbon.cold_plate.population) "
                "and the OpenFOAM case writer are repository code, but the "
                "pinned OpenFOAM reference runs only on an operator host. "
                "Research uses the fixed public TRAIN and PRACTICE records."
            ),
            next_step=(
                "A separately reviewed cold-plate challenge-kit ticket, as the "
                "battery kit did (OWNER-CHALLENGE-KIT-01), to run the public "
                "draw and the pinned OpenFOAM labelling on the miner's own "
                "machine."
            ),
        ),
        "evaluate": Provided(
            ("carbon.cold_plate.practice:score_practice",),
            "Exam gates and components (carbon.cold_plate.exam) on the 100 "
            "public PRACTICE cases; labels stay host-side. Scoring "
            "miner-generated cases is not wired.",
        ),
        "compute": Gap(
            reason=(
                "Level-0 practice is CPU only in the pinned isolated carrier "
                "(COOL-L0-D4): the cold-plate campaign refuses a GPU image or "
                "a remote setup, and the miner's code cell is CPU only."
            ),
            next_step=(
                "A cold-plate GPU or remote practice lane needs its own ticket "
                "with a pinned worker declaration, and the hardware to accept "
                "it."
            ),
        ),
        "model": Provided(
            (
                "carbon.development_session.model_provider:select",
                "carbon.challenge_registry.agent_plan:provider_plan",
                "carbon.cold_plate.campaign:prepare_cold_plate",
            ),
            "The same Challenge-neutral setup (Set up your environment, "
            "Inference) as battery: a cold-plate campaign freezes the miner's "
            "model selection and ceilings in its Challenge-neutral run plan "
            "and calls with the miner's own key. A live cold-plate campaign "
            "with miner-held keys is the acceptance and needs the miner's keys.",
        ),
        "agent": Provided(
            (
                "carbon.challenge_registry.agent_plan:graphite_plan",
                "carbon.agent_campaign.graphite.miner.edition:offered",
                "scripts.dev.miner_launchpad.hermes_setup:config_document",
                "carbon.miner_mcp.standard_cli:main",
            ),
            "Graphite is offered on every Challenge with a registered research "
            "campaign, so it runs a cold-plate campaign under its registered "
            "policy; Carbon's MCP server attaches to a prepared cold-plate "
            "campaign through that campaign, so an external MCP agent such as "
            "Hermes Agent drives the same research tools. An agent-driven "
            "cold-plate campaign is the acceptance and needs the miner's keys.",
        ),
    },
    # CHALLENGE-MOTOR-02: Level-0 DEVELOPMENT construction only. Official
    # evaluation stays fail closed (`motor_validator_not_served`).
    "electric-motor-magnetics": {
        "research": Provided(
            (
                "carbon.motor.research:challenge_parts",
                "carbon.motor.research:MotorPublicMaterial",
            ),
            "Public material: the objective (task, inputs, outputs, sampling "
            "law, gates, score), the capability registry, the 150 public TRAIN "
            "and 30 public PRACTICE GetDP records, and the reference-method "
            "description. The private pool, decision-study evidence and future "
            "confirmation material are absent by structure.",
        ),
        "hypothesize": Provided((REGISTRY_EVIDENCE,)),
        "train": Provided(
            (
                "carbon.motor.research:implementation_files",
                "carbon.motor.practice:staged_files",
                COST_EVIDENCE,
            ),
            "The Gaussian kernel-ridge reconstruction (learned_baseline.py, "
            "domain.py, recipes.py) is published and staged byte-identical in "
            "practice, with the pinned public TRAIN bytes, in the pinned NumPy "
            "CPU isolated carrier; it is a closed-form fit. The neural families "
            "(MOTOR-NEURAL-01: an MLP and a DeepONet, JAX or PyTorch) train "
            "through Carbon's shared trainers (carbon.motor.neural), and the "
            "training budget calculator prices them; their practice waits for a "
            "JAX and PyTorch practice image (refused as backend_not_served).",
        ),
        "generate": Gap(
            reason=(
                "No miner-runnable Motor kit draws and labels new cases. The "
                "population draw and buildability screen are repository code, "
                "but the pinned Gmsh/GetDP reference runs only on an operator "
                "host. Research uses the fixed public TRAIN and PRACTICE records."
            ),
            next_step=(
                "A separately reviewed Motor challenge-kit ticket to run the "
                "public draw and pinned Gmsh/GetDP labelling on the miner's own "
                "machine."
            ),
        ),
        "evaluate": Provided(
            ("carbon.motor.practice:score_practice",),
            "Exam gates and components (carbon.motor.exam) on the 30 public "
            "PRACTICE cases; labels stay host-side. Scoring miner-generated "
            "cases is not wired.",
        ),
        "compute": Gap(
            reason=(
                "Level-0 practice is CPU only in the pinned isolated carrier "
                "(MOTOR-L0-D4): the Motor campaign refuses a GPU image or "
                "remote setup, and the miner's code cell is CPU only."
            ),
            next_step=(
                "A Motor GPU or remote practice lane needs its own ticket with "
                "a pinned worker declaration and the hardware to accept it."
            ),
        ),
        "model": Provided(
            (
                "carbon.development_session.model_provider:select",
                "carbon.challenge_registry.agent_plan:provider_plan",
                "carbon.motor.campaign:prepare_motor",
            ),
            "The Challenge-neutral setup freezes the miner's model selection "
            "and ceilings in its run plan and calls with the miner's own key. "
            "A live Motor campaign with miner-held keys remains the acceptance.",
        ),
        "agent": Provided(
            (
                "carbon.challenge_registry.agent_plan:graphite_plan",
                "carbon.agent_campaign.graphite.miner.edition:offered",
                "scripts.dev.miner_launchpad.hermes_setup:config_document",
                "carbon.miner_mcp.standard_cli:main",
            ),
            "Graphite is offered on every Challenge with a registered research "
            "campaign, so it runs Motor under the registered policy. Carbon's "
            "MCP server attaches through that campaign; execution still needs "
            "the miner's keys and downstream admission authority.",
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
