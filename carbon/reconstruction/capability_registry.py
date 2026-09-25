"""The construction capability registry: one source for what a miner may submit.

Owner direction OWNER-CONSTRUCTION-DECLARATIVE-01: Carbon widens construction
declaratively. Every design capability a miner might want has one entry here,
whether Carbon can rebuild it today, it is research-only, or it is excluded by
the declarative rule. The research catalog's backbones and fields, the
reconstruction profile's backbone map and the public capability catalogue are
all derived from this registry, so they cannot drift apart.

Pure data: importing this module never initializes a numerical runtime.

Status is engineering state, never qualification. ADMITTED exists in the public
vocabulary but no entry may claim it here: admission for an evaluation contract
needs qualification evidence this registry cannot supply.

Construction contracts are per Challenge (OWNER-BATTERY-TESTNET-01, OD-8). One
registry, one compiler, but each Challenge version has its own
`ChallengeContract`: the capabilities registered for that Challenge, their
surfaces and ranges, and its declared resource envelope, pinned by its own
contract digest. A family rebuildable for one Challenge is not thereby
rebuildable for another. `REGISTRY` remains the Burgers contract's entries, and
every function defaults to Burgers, so the historical vocabulary is unchanged.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum

REGISTRY_SCHEMA = "carbon.construction-capability-registry.v1"
CONTRACT_SCHEMA = "carbon.challenge-construction-contract.v1"


class Dimension(str, Enum):
    MODEL_FAMILY = "model_family"
    ARCHITECTURE = "architecture"
    OBJECTIVE = "objective"
    OPTIMIZER = "optimizer"
    SCHEDULE = "schedule"
    BATCHING = "batching"
    STAGES = "stages"
    TRAINING_DATA = "training_data"
    PHYSICAL_STRUCTURE = "physical_structure"
    HYBRID = "hybrid"
    PREDICTION = "prediction"
    INFERENCE = "inference"


class Status(str, Enum):
    #: A miner may explore it in research; Carbon cannot rebuild it yet.
    RESEARCH_ONLY = "research_only"
    #: Carbon compiles and rebuilds it through the registered DEVELOPMENT path.
    #: This does not establish official qualification.
    REBUILDABLE_DEVELOPMENT = "rebuildable_development"
    #: Admitted for an evaluation contract. Never set by this registry.
    ADMITTED = "admitted"
    #: Outside the declarative rule; not on the roadmap.
    EXCLUDED = "excluded"


class Blocker(str, Enum):
    NONE = "none"
    ENGINEERING = "engineering"
    OWNER_DECISION = "owner_decision"
    EXCLUDED = "excluded"


class Trigger(str, Enum):
    """The five escalation triggers (owner mandate, 2026-09-23)."""

    EXTERNAL_STATE = "external_data_or_learned_state"
    EXECUTABLE_SUBMISSION = "executable_submission"
    EVIDENCE_DESIGN = "evidence_design_change"
    COMPARISON_REGIME = "new_comparison_or_resource_regime"
    AUTHORITY_BOUNDARY = "authority_boundary_widening"


@dataclass(frozen=True)
class Surface:
    """A catalog field: group, type, minimum or choices, maximum, default."""

    group: str
    kind: str
    low: object
    high: object
    default: object

    def __post_init__(self):
        if self.group not in ("model", "task", "train"):
            raise ValueError("surface group is model, task or train")
        if self.kind not in ("uint", "float", "bool", "choice"):
            raise ValueError("surface kind is uint, float, bool or choice")


@dataclass(frozen=True)
class Capability:
    capability_id: str
    dimension: Dimension
    summary: str
    status: Status
    blocker: Blocker = Blocker.NONE
    trigger: Trigger | None = None
    #: A model family's strategy selector, and the lab kind that rebuilds it.
    selector: str | None = None
    lab_kind: str | None = None
    #: A field's catalog surface, and the families it applies to (None = all).
    surface: Surface | None = None
    applies_to: tuple[str, ...] | None = None

    def __post_init__(self):
        if type(self.dimension) is not Dimension or type(self.status) is not Status:
            raise TypeError("exact Dimension and Status required")
        prefix, _, name = self.capability_id.partition(".")
        if prefix != self.dimension.value or not name:
            raise ValueError("capability id is <dimension>.<name>")
        if self.status is Status.ADMITTED:
            raise ValueError(
                "admission needs qualification evidence, not a registry entry"
            )
        family = self.selector is not None or self.lab_kind is not None
        if self.status is Status.REBUILDABLE_DEVELOPMENT:
            if self.blocker is not Blocker.NONE or self.trigger is not None:
                raise ValueError("a rebuildable capability has no blocker")
            if self.dimension is Dimension.MODEL_FAMILY:
                if not (self.selector and self.lab_kind) or self.surface:
                    raise ValueError(
                        "a rebuildable family names its selector and lab kind"
                    )
            elif self.surface is None or family:
                raise ValueError("a rebuildable field carries its catalog surface")
        elif family or self.surface is not None or self.applies_to is not None:
            raise ValueError("only a rebuildable capability carries an implementation")
        if self.status is Status.RESEARCH_ONLY and self.blocker not in (
            Blocker.ENGINEERING,
            Blocker.OWNER_DECISION,
        ):
            raise ValueError(
                "research-only work is blocked on engineering or the owner"
            )
        if self.status is Status.EXCLUDED and self.blocker is not Blocker.EXCLUDED:
            raise ValueError("an excluded capability is blocked as excluded")
        if (self.blocker in (Blocker.OWNER_DECISION, Blocker.EXCLUDED)) != (
            self.trigger is not None
        ):
            raise ValueError("an owner or exclusion blocker names exactly its trigger")


def _family(name, selector, lab_kind, summary):
    return Capability(
        f"model_family.{name}",
        Dimension.MODEL_FAMILY,
        summary,
        Status.REBUILDABLE_DEVELOPMENT,
        selector=selector,
        lab_kind=lab_kind,
    )


def _field(dimension, name, surface, summary, applies_to=None):
    return Capability(
        f"{dimension.value}.{name}",
        dimension,
        summary,
        Status.REBUILDABLE_DEVELOPMENT,
        surface=surface,
        applies_to=applies_to,
    )


def _todo(dimension, name, summary):
    return Capability(
        f"{dimension.value}.{name}",
        dimension,
        summary,
        Status.RESEARCH_ONLY,
        Blocker.ENGINEERING,
    )


def _owner(dimension, name, summary, trigger):
    return Capability(
        f"{dimension.value}.{name}",
        dimension,
        summary,
        Status.RESEARCH_ONLY,
        Blocker.OWNER_DECISION,
        trigger,
    )


def _excluded(dimension, name, summary, trigger):
    return Capability(
        f"{dimension.value}.{name}",
        dimension,
        summary,
        Status.EXCLUDED,
        Blocker.EXCLUDED,
        trigger,
    )


FNO, DEEPONET, TRANSOLVER = ("fno",), ("deeponet",), ("transolver",)
HAAR, GNO, GINO = ("haar_operator",), ("gno",), ("gino",)
#: Families built from stacked blocks over a grid: depth and remat apply.
BLOCKED = FNO + TRANSOLVER + HAAR + GNO + GINO

A, M, T = Dimension.ARCHITECTURE, Dimension.MODEL_FAMILY, Dimension.TRAINING_DATA
O, S, B = Dimension.OPTIMIZER, Dimension.SCHEDULE, Dimension.BATCHING
J, P = Dimension.OBJECTIVE, Dimension.PHYSICAL_STRUCTURE
ST, H, PR, INF = (
    Dimension.STAGES,
    Dimension.HYBRID,
    Dimension.PREDICTION,
    Dimension.INFERENCE,
)

REGISTRY = (
    # --- Model families Carbon rebuilds (vendored carbon_jax_lab). ---
    _family("fno", "fno", "fno1d", "Fourier neural operator"),
    _family("deeponet", "deeponet", "deeponet1d", "DeepONet branch/trunk operator"),
    _family(
        "transolver",
        "transolver",
        "physics_attention1d",
        "Carbon's Transolver: slice/attention/deslice blocks adapted from "
        "THUML/Transolver with declared departures (softplus temperature, "
        "optional quadrature weights, dropout fixed at zero)",
    ),
    _family(
        "haar_operator", "haar_operator", "haar_operator1d", "Haar wavelet operator"
    ),
    _family("gno", "gno", "gno1d", "Graph neural operator (dense radius quadrature)"),
    _family("gino", "gino", "gino1d", "Graph-informed neural operator (latent FNO)"),
    # --- Fields Carbon rebuilds. Order is the catalog's order. ---
    _field(B, "steps", Surface("train", "uint", 2, 1000000, 512), "Target updates"),
    _field(A, "width", Surface("model", "uint", 2, 128, 24), "Channel width"),
    _field(A, "depth", Surface("model", "uint", 1, 8, 2), "Blocks", BLOCKED),
    _field(
        A, "n_modes", Surface("model", "uint", 2, 64, 16), "Spectral modes", FNO + GINO
    ),
    _field(
        A,
        "branch_points",
        Surface("model", "uint", 2, 64, 32),
        "DeepONet sensors",
        DEEPONET,
    ),
    _field(
        A, "heads", Surface("model", "uint", 1, 16, 2), "Attention heads", TRANSOLVER
    ),
    _field(
        A,
        "slices",
        Surface("model", "uint", 1, 64, 4),
        "Physical-state slices",
        TRANSOLVER,
    ),
    _field(
        A,
        "expansion",
        Surface("model", "uint", 1, 8, 2),
        "Feed-forward multiplier",
        TRANSOLVER,
    ),
    # Haar levels are bounded by the 64-point TRAIN grid (2**6); checked again
    # against RESEARCH_GRID_POINTS at compile time.
    _field(A, "wavelet_levels", Surface("model", "uint", 1, 6, 2), "Haar levels", HAAR),
    # The lab's graph_radius, under a name B-02B's composition-graph guard
    # admits; the profile maps it back. Periodic unit coordinates; the lower
    # bound is one grid spacing (1/64).
    _field(
        A,
        "neighborhood_radius",
        Surface("model", "float", 0.015625, 0.5, 0.2),
        "Neighbourhood radius",
        GNO + GINO,
    ),
    _field(
        A,
        "latent_points",
        Surface("model", "uint", 2, 64, 12),
        "GINO latent grid",
        GINO,
    ),
    _field(
        A,
        "remat",
        Surface("model", "bool", None, None, False),
        "Rematerialize blocks",
        BLOCKED,
    ),
    _field(
        P,
        "hard_initial_condition",
        Surface("task", "bool", None, None, True),
        "u0 + (t/27)*output",
    ),
    _field(
        P,
        "enforce_mean",
        Surface("task", "bool", None, None, True),
        "Project to the initial mean",
    ),
    _field(B, "batch_size", Surface("train", "uint", 1, 64, 8), "Cases per update"),
    _field(
        B, "microbatches", Surface("train", "uint", 1, 8, 1), "Gradient accumulation"
    ),
    _field(
        O,
        "learning_rate",
        Surface("train", "float", 0.000001, 0.05, 0.002),
        "AdamW peak rate",
    ),
    _field(
        S,
        "min_learning_rate_ratio",
        Surface("train", "float", 0.0, 1.0, 0.1),
        "Cosine floor",
    ),
    _field(S, "warmup_steps", Surface("train", "uint", 0, 100000, 0), "Linear warmup"),
    _field(
        O, "weight_decay", Surface("train", "float", 0.0, 0.1, 0.0001), "AdamW decay"
    ),
    _field(
        O,
        "clip_norm",
        Surface("train", "float", 0.001, 100.0, 1.0),
        "Global-norm clipping",
    ),
    _field(O, "beta1", Surface("train", "float", 0.0, 0.9999, 0.9), "AdamW beta1"),
    _field(O, "beta2", Surface("train", "float", 0.0, 0.99999, 0.999), "AdamW beta2"),
    _field(
        O, "adam_epsilon", Surface("train", "float", 1e-12, 0.01, 1e-8), "AdamW epsilon"
    ),
    _field(
        INF, "ema_decay", Surface("train", "float", 0.0, 0.99999, 0.99), "EMA decay"
    ),
    _field(
        J,
        "relative_loss",
        Surface("train", "bool", None, None, False),
        "Relative data loss",
    ),
    _field(
        J, "h1_weight", Surface("train", "float", 0.0, 10.0, 0.0), "H1 derivative loss"
    ),
    _field(
        J,
        "pde_weight",
        Surface("train", "float", 0.0, 10.0, 0.0),
        "Burgers residual loss",
    ),
    _field(
        ST,
        "physics_warmup_steps",
        Surface("train", "uint", 0, 100000, 0),
        "PDE-loss ramp",
    ),
    _field(
        INF,
        "inference_weights",
        Surface("train", "choice", ("params", "ema"), None, "params"),
        "Predict from params or EMA",
    ),
    # --- Research-only, engineering next (no owner decision needed). ---
    _todo(O, "weight_decay_mask", "Decay matrices only, or all parameters"),
    # One id per item, so a check-design verdict and a demand count name it.
    *(
        _todo(O, name, summary)
        for name, summary in (
            ("lion", "Lion (sign-momentum) optimizer"),
            ("lamb", "LAMB layer-adaptive optimizer"),
            ("adafactor", "Adafactor factored second moments"),
            ("radam", "Rectified Adam"),
            ("nadamw", "Nesterov AdamW"),
            ("sgd_momentum", "SGD with momentum"),
            ("muon", "Muon orthogonalized updates"),
            ("prodigy", "Prodigy learning-rate-free adaptation"),
            ("schedule_free", "Schedule-free AdamW"),
            ("sam", "Sharpness-aware minimization"),
        )
    ),
    *(
        _todo(S, name, summary)
        for name, summary in (
            ("constant", "Constant learning rate"),
            ("piecewise", "Piecewise-constant steps"),
            ("exponential", "Exponential decay"),
            ("one_cycle", "One-cycle schedule"),
            ("sgdr", "Cosine with warm restarts"),
            ("polynomial", "Polynomial decay"),
            ("train_loss_plateau", "Reduce on a TRAIN-loss plateau"),
        )
    ),
    _todo(INF, "weight_averaging", "SWA or tail averaging"),
    _todo(
        INF, "ensembles", "Independently trained members, within the existing budget"
    ),
    _todo(J, "spectral_weighting", "Frequency-weighted data loss"),
    _todo(J, "time_weighting", "Time-weighted data loss"),
    _todo(J, "sobolev", "Sobolev terms beyond H1"),
    _todo(
        ST,
        "explicit_stages",
        "Per-stage step split and optimizer, such as an L-BFGS polish",
    ),
    _todo(
        A,
        "activation_normalization_init",
        "Activation, normalization and initialization choices",
    ),
    _todo(A, "deeponet_depth", "DeepONet branch and trunk depth"),
    _todo(M, "foundax_deeponet", "foundax DeepONet branch/trunk/combination variants"),
    _todo(
        M,
        "foundax_fno",
        "foundax FNO as its own backbone, with its own schedule semantics",
    ),
    _todo(M, "unet1d", "foundax U-Net 1D with a deterministic norm"),
    _todo(M, "mgno1d", "foundax multigrid neural operator"),
    *(
        _todo(M, name, summary)
        for name, summary in (
            ("pointnet", "foundax PointNet, per point"),
            ("gnot", "foundax GNOT (general neural operator transformer)"),
            ("cgptno", "foundax CGPT-NO"),
            ("moegptno", "foundax MoE-GPT-NO"),
            ("geofno", "foundax Geo-FNO in 1D"),
            ("pcno", "foundax point-cloud neural operator in 1D"),
        )
    ),
    _todo(PR, "rollout", "Learned time-stepper with rollout or pushforward training"),
    _todo(T, "curriculum", "Curriculum over TRAIN strata or resolution"),
    _todo(T, "hard_example_sampling", "Adaptive sampling on TRAIN loss only"),
    _todo(
        T, "exact_symmetry_augmentation", "Periodic shift and reflection u(x) -> -u(-x)"
    ),
    _todo(
        P,
        "structure_layers",
        "Conservative flux form, equivariant or positivity layers",
    ),
    _todo(
        H,
        "candidate_solver_template",
        "A Carbon-registered candidate-side solver with a learned correction",
    ),
    _todo(
        H,
        "symbolic_template",
        "Registered expression template; Carbon fits coefficients",
    ),
    # --- Research-only until the owner decides (one of the five triggers). ---
    _owner(
        T,
        "case_count_and_resolution",
        "TRAIN case count, grid resolution and times",
        Trigger.COMPARISON_REGIME,
    ),
    _owner(
        T,
        "label_method",
        "Per-submission reference label method",
        Trigger.EVIDENCE_DESIGN,
    ),
    _owner(
        T,
        "support_leaving_augmentation",
        "Augmentations that leave TRAIN support, such as a Galilean boost",
        Trigger.COMPARISON_REGIME,
    ),
    _owner(
        H,
        "reference_solver_reuse",
        "Hybrids reusing the exam's reference solvers",
        Trigger.EVIDENCE_DESIGN,
    ),
    _owner(INF, "precision", "Precision beyond float32", Trigger.COMPARISON_REGIME),
    _owner(
        M,
        "two_and_three_dimensional",
        "2D and 3D families; needs a new Challenge",
        Trigger.AUTHORITY_BOUNDARY,
    ),
    _owner(
        M,
        "pytorch_backend",
        "PyTorch families (neuraloperator, PhysicsNeMo); new worker image",
        Trigger.AUTHORITY_BOUNDARY,
    ),
    _owner(
        M,
        "julia_backend",
        "Julia families (NeuralOperators.jl, NeuralPDE, DiffEqFlux); new worker image",
        Trigger.AUTHORITY_BOUNDARY,
    ),
    # --- Excluded by the declarative rule. ---
    _excluded(
        M,
        "pretrained_weights",
        "Pretrained weights, checkpoints or embeddings",
        Trigger.EXTERNAL_STATE,
    ),
    _excluded(
        T,
        "submitted_datasets",
        "Uploaded datasets or miner-chosen seeds",
        Trigger.EXTERNAL_STATE,
    ),
    _excluded(
        J,
        "loss_expressions",
        "Losses supplied as code or expressions",
        Trigger.EXECUTABLE_SUBMISSION,
    ),
    _excluded(
        H,
        "composition_graphs",
        "Participant-defined composition graphs",
        Trigger.EXECUTABLE_SUBMISSION,
    ),
    _excluded(
        INF,
        "final_label_selection",
        "Checkpoint selection by final labels",
        Trigger.EVIDENCE_DESIGN,
    ),
)


# --- Battery: carbon.battery-fastcharge-ageing-development.v1 (OD-1). ---
#
# Inputs are four scalars (first- and second-stage C-rate, ambient temperature,
# initial state of charge); outputs are voltage and temperature on a 30 s grid,
# a scalar plating margin and capacity at four checkpoint cycles. Bounds below
# are engineering admission bounds, not quality or scientific claims; the
# declared resource envelope dominates them.
KNN, MLP = ("knn",), ("mlp",)


def _battery_family(name, lab_kind, summary):
    return _family(name, name, lab_kind, summary)


_GRID_OPERATOR = (
    "not applicable to battery: a grid-to-grid operator over a spatial input "
    "field, and battery inputs are four scalars with no field; no adapter planned"
)

BATTERY_REGISTRY = (
    _battery_family(
        "knn",
        "battery_knn",
        "Inverse-distance k-nearest-neighbour over unit-scaled inputs; "
        "V(0) from the published OCV table and T(0) = ambient",
    ),
    _battery_family(
        "mlp",
        "battery_mlp",
        "Full-batch GELU MLP with Adam(W) and cosine decay on normalized "
        "trajectory targets; T(0) = ambient",
    ),
    _field(
        A,
        "neighbours",
        Surface("model", "uint", 1, 64, 5),
        "Neighbours averaged",
        KNN,
    ),
    _field(A, "width", Surface("model", "uint", 8, 512, 256), "Hidden width", MLP),
    _field(A, "depth", Surface("model", "uint", 1, 6, 3), "Hidden layers", MLP),
    _field(
        A,
        "trajectory_components",
        Surface("model", "uint", 0, 32, 0),
        "PCA heads per trajectory (0 = one output per sample)",
        MLP,
    ),
    _field(
        A,
        "arrhenius_features",
        Surface("model", "bool", None, None, False),
        "Add Arrhenius, log-rate and interaction input features",
        MLP,
    ),
    _field(B, "steps", Surface("train", "uint", 16, 20000, 6000), "Updates", MLP),
    _field(
        O,
        "learning_rate",
        Surface("train", "float", 0.00001, 0.05, 0.002),
        "Adam peak rate (cosine to zero)",
        MLP,
    ),
    _field(
        O,
        "weight_decay",
        Surface("train", "float", 0.0, 0.1, 0.0),
        "Decoupled decay",
        MLP,
    ),
    _field(
        INF,
        "ensemble_members",
        Surface("train", "uint", 1, 4, 1),
        "Members sharing the step budget equally",
        MLP,
    ),
    _field(
        P,
        "bounded_voltage_head",
        Surface("task", "bool", None, None, True),
        "Voltage head that cannot exceed the 4.2 V cycler limit (off: the raw control)",
        MLP,
    ),
    _field(
        P,
        "ocv_initial_voltage",
        Surface("task", "bool", None, None, True),
        "V(0) from the published OCV table (off: predicted)",
        MLP,
    ),
    _field(
        P,
        "capacity_fade_head",
        Surface("task", "bool", None, None, True),
        "Capacity as cycle-1 capacity plus fade (off: each checkpoint directly)",
        MLP,
    ),
    # --- Applicability of the operator families (M1 assessment). ---
    _todo(
        M,
        "deeponet",
        "needs a battery adapter: branch over the four scalar inputs, trunk over "
        "the 30 s time grid, scalar heads for plating margin and capacity",
    ),
    *(
        _todo(M, name, _GRID_OPERATOR)
        for name in ("fno", "transolver", "haar_operator", "gno", "gino")
    ),
    _todo(B, "minibatch", "Minibatch updates; the recipe trains full-batch"),
    *(
        _todo(O, name, summary)
        for name, summary in (
            ("lion", "Lion (sign-momentum) optimizer"),
            ("sgd_momentum", "SGD with momentum"),
        )
    ),
    _todo(S, "warmup_steps", "Linear warmup before the cosine decay"),
    _owner(
        T,
        "important_region_weighting",
        "Down- or up-weighting TRAIN cases by the exam's important region",
        Trigger.EVIDENCE_DESIGN,
    ),
    _owner(
        T,
        "case_count_and_resolution",
        "TRAIN case count, subsets, time grid and checkpoint cycles",
        Trigger.COMPARISON_REGIME,
    ),
    _owner(INF, "precision", "Precision beyond float32", Trigger.COMPARISON_REGIME),
    _excluded(
        M,
        "pretrained_weights",
        "Pretrained weights, checkpoints or embeddings",
        Trigger.EXTERNAL_STATE,
    ),
    _excluded(
        T,
        "submitted_datasets",
        "Uploaded datasets or miner-chosen seeds",
        Trigger.EXTERNAL_STATE,
    ),
    _excluded(
        J,
        "loss_expressions",
        "Losses supplied as code or expressions",
        Trigger.EXECUTABLE_SUBMISSION,
    ),
    _excluded(
        INF,
        "final_label_selection",
        "Checkpoint selection by final labels",
        Trigger.EVIDENCE_DESIGN,
    ),
)


@dataclass(frozen=True)
class ChallengeContract:
    """One Challenge version's construction contract.

    `token` is the Strategy `challenge_id` (Strategy 1.0 identifiers carry no
    dots); `identity` is the Challenge's registered name. `lanes` name the
    subsets of rebuildable families a specific execution lane offers: a lane
    admits a family only with that lane's own evidence, so widening the
    research catalog never widens a lane. The envelope is declared engineering
    admission, never a scientific or economic value.
    """

    token: str
    version: str
    identity: str
    catalog_version: str
    capabilities: tuple[Capability, ...]
    envelope: tuple[tuple[str, object], ...]
    lanes: tuple[tuple[str, tuple[str, ...]], ...] = ()

    def __post_init__(self):
        if not all(type(c) is Capability for c in self.capabilities):
            raise TypeError("exact Capability entries required")
        ids = [c.capability_id for c in self.capabilities]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate capability id in " + self.token)
        fields = [
            c.capability_id.partition(".")[2] for c in self.capabilities if c.surface
        ]
        if len(fields) != len(set(fields)):
            raise ValueError("duplicate field name in " + self.token)
        families = {
            c.selector
            for c in self.capabilities
            if c.dimension is Dimension.MODEL_FAMILY
            and c.status is Status.REBUILDABLE_DEVELOPMENT
        }
        if not families:
            raise ValueError("a contract rebuilds at least one family")
        for c in self.capabilities:
            if c.applies_to is not None and not set(c.applies_to) <= families:
                raise ValueError(
                    c.capability_id + " applies to a family this contract lacks"
                )
        for _, lane in self.lanes:
            if not lane or not set(lane) <= families:
                raise ValueError("a lane offers only rebuildable families")

    def document(self):
        """Everything the contract digest pins, as plain JSON data."""
        return {
            "schema": CONTRACT_SCHEMA,
            "registry_schema": REGISTRY_SCHEMA,
            "challenge": {"id": self.token, "version": self.version},
            "identity": self.identity,
            "catalog_version": self.catalog_version,
            "capabilities": [
                {
                    "id": c.capability_id,
                    "status": c.status.value,
                    "blocker": c.blocker.value,
                    "trigger": None if c.trigger is None else c.trigger.value,
                    "selector": c.selector,
                    "lab_kind": c.lab_kind,
                    "surface": (
                        None
                        if c.surface is None
                        else [
                            c.surface.group,
                            c.surface.kind,
                            (
                                list(c.surface.low)
                                if type(c.surface.low) is tuple
                                else c.surface.low
                            ),
                            c.surface.high,
                            c.surface.default,
                        ]
                    ),
                    "applies_to": None if c.applies_to is None else list(c.applies_to),
                }
                for c in self.capabilities
            ],
            "envelope": dict(self.envelope),
            "lanes": {name: list(lane) for name, lane in self.lanes},
        }

    @property
    def digest(self):
        body = json.dumps(
            self.document(), sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
        return "sha256:" + hashlib.sha256(body).hexdigest()


BURGERS_CHALLENGE = "burgers-dynamics-v1"
BATTERY_CHALLENGE = "battery-fastcharge-ageing-development-v1"

_WORKER_ENVELOPE = (
    ("worker_cpu", 2),
    ("worker_memory_bytes", 4 * 1024**3),
    ("worker_swap_bytes", 0),
    ("worker_deadline_seconds", 600),
    ("precision", "float32"),
)

BURGERS_CONTRACT = ChallengeContract(
    token=BURGERS_CHALLENGE,
    version="1.0",
    identity="carbon.burgers-autoresearch-development.v1",
    catalog_version="carbon.burgers-autoresearch-recipes.v1",
    capabilities=REGISTRY,
    envelope=_WORKER_ENVELOPE,
    # The historical C-W1 session and the GPU diagnostic lane offer exactly the
    # two families they were accepted with.
    lanes=(
        ("session", ("fno", "deeponet")),
        ("gpu_diagnostic", ("fno", "deeponet")),
    ),
)

BATTERY_CONTRACT = ChallengeContract(
    token=BATTERY_CHALLENGE,
    version="1.0",
    identity="carbon.battery-fastcharge-ageing-development.v1",
    catalog_version="carbon.battery-fastcharge-ageing-recipes.v1",
    capabilities=BATTERY_REGISTRY,
    envelope=_WORKER_ENVELOPE + (("train_cases", 400), ("batching", "full")),
)

CONTRACTS = {c.token: c for c in (BURGERS_CONTRACT, BATTERY_CONTRACT)}


class UnknownChallenge(KeyError):
    """A Challenge with no registered construction contract."""


def contract(challenge=BURGERS_CHALLENGE):
    """The construction contract for exactly this Challenge token."""
    try:
        return CONTRACTS[challenge]
    except (KeyError, TypeError):
        raise UnknownChallenge("no construction contract for this challenge") from None


def contract_digest(challenge=BURGERS_CHALLENGE):
    return contract(challenge).digest


def lane_families(challenge, lane):
    """The families a named lane of one Challenge offers, from the registry."""
    return dict(contract(challenge).lanes)[lane]


def status_map(capability_id):
    """{challenge: status} for every Challenge that registers this capability."""
    return {
        token: c.status.value
        for token, item in CONTRACTS.items()
        for c in item.capabilities
        if c.capability_id == capability_id
    }


def _index(entries):
    seen = {}
    for item in entries:
        if item.capability_id in seen:
            raise ValueError("duplicate capability id " + item.capability_id)
        seen[item.capability_id] = item
    return seen


_BY_ID = {token: _index(item.capabilities) for token, item in CONTRACTS.items()}


def capability(capability_id, challenge=BURGERS_CHALLENGE):
    contract(challenge)
    return _BY_ID[challenge][capability_id]


def rebuildable_families(challenge=BURGERS_CHALLENGE):
    """(selector, lab kind) for every family Carbon rebuilds, in registry order."""
    return tuple(
        (c.selector, c.lab_kind)
        for c in contract(challenge).capabilities
        if c.dimension is Dimension.MODEL_FAMILY
        and c.status is Status.REBUILDABLE_DEVELOPMENT
    )


def catalog_surfaces(challenge=BURGERS_CHALLENGE):
    """The research catalog's fields, in its historical tuple form:
    name -> (group, type, minimum/choices, maximum, default, families|None)."""
    return {
        c.capability_id.partition(".")[2]: (
            c.surface.group,
            c.surface.kind,
            c.surface.low,
            c.surface.high,
            c.surface.default,
            c.applies_to,
        )
        for c in contract(challenge).capabilities
        if c.surface is not None
    }


def public_registry(challenge=BURGERS_CHALLENGE):
    """Every capability's public status for one Challenge. Only
    registry-defined text, never anything a miner supplied."""
    value = {
        "schema": REGISTRY_SCHEMA,
        "status_meaning": {
            Status.RESEARCH_ONLY.value: "explore in research; Carbon cannot rebuild it yet",
            Status.REBUILDABLE_DEVELOPMENT.value: "Carbon rebuilds it in DEVELOPMENT; not official qualification",
            Status.ADMITTED.value: "admitted for an evaluation contract",
            Status.EXCLUDED.value: "outside the declarative rule",
        },
        "capabilities": [
            {
                "id": c.capability_id,
                "dimension": c.dimension.value,
                "summary": c.summary,
                "status": c.status.value,
                "blocker": c.blocker.value,
                "trigger": None if c.trigger is None else c.trigger.value,
                "selector": c.selector,
                "applies_to": None if c.applies_to is None else list(c.applies_to),
            }
            for c in contract(challenge).capabilities
        ],
    }
    if challenge != BURGERS_CHALLENGE:
        # Burgers keeps its historical projection byte for byte.
        item = contract(challenge)
        value["challenge"] = {"id": item.token, "version": item.version}
        value["contract_digest"] = item.digest
    return value
