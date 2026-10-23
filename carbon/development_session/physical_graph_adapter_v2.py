"""Graph route v2: one Challenge-neutral graph training adapter for every
Challenge's own graph (owner: "No carbon limits please!"; Launchpad sweep
rows L9-L12, LP_GRAPH_ROUTE_V2_BRIEF_20261023).

It sits beside `physical_graph_adapter` (v1), which F08 1.4 and F02 2.3 keep
byte for byte, with its own pinned trainer (`physical_graph_trainer_v2`) and
ensemble state (`physical_graph_state_v2`). What it adds, for each version
registered in `SPECS`:

1. per-output loss weights (`configuration.output_weights`);
2. ensembles whose members each train the miner's graph on a chosen subset of
   the outputs, with their own seed and, optionally, their own training
   settings, combined per output (`configuration.ensemble`);
3. any number of members: only the build's registered resource limits (wall
   time, memory) bound them;
4. training settings bounded only by structure: a positive rate, betas below
   one, a batch no larger than the selected TRAIN rows, a train fraction
   above zero, and the loss, optimizer and learning-rate curve the trainer
   implements.

What stays (keep list): the output dtype, the interface's (`<f4` on F08 and
F02, `<f8` on Motor and Cooling) - the graph's own computation precision is
the miner's (Validator, 2026-10-23); batch at most the
selected TRAIN rows; train_fraction above zero; containment and constant
bytes (the allowlist); no pretrained state (the recipe); identity bindings.
A loss inside the graph is still refused (`graph_route_loss_unsupported`).

It runs inside the isolated build worker with only its staged modules, so the
Challenge constants are kept here, not imported (a test holds them equal to
each Challenge's TRAIN). Nothing here is an evaluation, a qualification or
LIVE authority; the values are DEVELOPMENT values.
"""

from __future__ import annotations

import hashlib
import io
import math
from dataclasses import dataclass

import numpy as np

from . import physical_graph_state_v2
from .construction_recipe import ConstructionRecipe, RecipeRefused, graph_workspace

ADAPTER_SCHEMA = "carbon.physical-graph-training-adapter.v2"
OUTPUT_FORMAT = "carbon.numeric-graph.v1"
PROCEDURE_SCHEMA = "carbon.construction-recipe.v1"
INPUT_NAME = "inputs/features"
TRAINER_MODULE = "carbon.development_session.physical_graph_trainer_v2"
TRAINER_PATH = "carbon/development_session/physical_graph_trainer_v2.py"
#: The v2 trainer's source sha256 (a test re-hashes it). A change to the
#: trainer is a new digest, so a new version.
TRAINER_SHA256 = "54152a38628862cad0f94314b830130fc6e3d39480a41be94af85eca669a517d"
TRAINER_PIN = (TRAINER_PATH, TRAINER_SHA256)
CODE = "graph_route_"

#: Each surface's (kind, default): the structural bound is the kind's.
#:   uint     an integer, at least `low` (steps 1, warmup 0, batch 1)
#:   positive a finite number above zero
#:   nonneg   a finite number, zero or more
#:   below1   a finite number in [0, 1)
#:   unit     a finite number in [0, 1]
#:   choice   one of the listed values
#: `steps` and `warmup_steps` have no cap: the build wall time bounds them
#: (OWNER-REBUILD-TIME-LIMIT-01). `batch_size` is capped by the selected TRAIN
#: rows (`graph_route_batch_exceeds_train`).
TRAIN_SURFACES = {
    "steps": ("uint", 1, 512),
    "batch_size": ("uint", 1, 8),
    "learning_rate": ("positive", None, 0.002),
    "weight_decay": ("nonneg", None, 0.0001),
    "beta1": ("below1", None, 0.9),
    "beta2": ("below1", None, 0.999),
    "adam_epsilon": ("positive", None, 1e-8),
    "warmup_steps": ("uint", 0, 0),
    "loss": ("choice", ("mse", "mae", "huber"), "mse"),
    "huber_delta": ("positive", None, 1.0),
    "optimizer_family": ("choice", ("adamw", "adam", "sgd", "lion"), "adamw"),
    "learning_rate_curve": ("choice", ("constant", "cosine", "linear"), "constant"),
    "min_learning_rate_ratio": ("unit", None, 0.0),
    "clip_norm": ("nonneg", None, 0.0),
}
#: train_fraction: above zero, at most one (`train_use`).
TRAIN_FRACTION = ("fraction", None, 1.0)
#: Carbon's other registered training surfaces (Burgers' and Battery's train
#: rows): naming one is a capability gap, never the candidate's fault.
UNSERVED_SURFACES = frozenset(
    {
        "backend",
        "curriculum",
        "ema_decay",
        "h1_weight",
        "h2_weight",
        "hard_example_weight",
        "important_region_weight",
        "inference_weights",
        "microbatches",
        "pde_weight",
        "physics_warmup_steps",
        "polish_steps",
        "relative_loss",
        "spectral_weight",
        "tail_averaging",
        "time_weighting",
        "weight_decay_mask",
    }
)
CONFIGURATION_FIELDS = frozenset({"training", "output_weights", "ensemble"})
MEMBER_FIELDS = frozenset({"outputs", "weight", "training"})


@dataclass(frozen=True)
class Spec:
    challenge_id: str
    version: str
    adapter_id: str
    train_use: str
    train_sha256: str
    rows: int
    inputs: int
    outputs: int
    #: The interface dtype of TRAIN, inputs and outputs: "float32" or "float64".
    dtype: str
    #: The predecessor version whose TRAIN, bank and measurement this one
    #: reuses ("predecessor + graph route v2"), recorded, never implied.
    predecessor: str


#: The graph route v2 versions, each its predecessor's TRAIN and interface
#: (a test holds them equal to the served material). Their train_use ids are
#: the predecessor's TRAIN names: the same TRAIN bytes.
SPECS = {
    ("f08-ribbed-bracket", "1.5"): Spec(
        "f08-ribbed-bracket",
        "1.5",
        "f08-ribbed-bracket-public-jax-graph-v2",
        "f08-pinned-train-v2",
        "4b28e7490eca34061da1431c6379f0f2e5766ff41aedba968eba41ba84fefe0a",
        287,
        6,
        7,
        "float32",
        "1.4",
    ),
    ("f02", "2.4"): Spec(
        "f02",
        "2.4",
        "f02-public-jax-graph-v2",
        "f02-pinned-train40-v2",
        "1201ec5461bfc08ad2ae4522eafc147282f4167e4bb222ed4e798284faa9a4c3",
        40,
        2,
        1,
        "float32",
        "2.3",
    ),
    ("electric-motor-magnetics", "1.4"): Spec(
        "electric-motor-magnetics",
        "1.4",
        "electric-motor-magnetics-public-jax-graph-v2",
        "motor-dev-train-150-v1",
        "5d27220b8b0c0ccddd013299183118cdce61f205057fe99bceb95c1f52173361",
        150,
        8,
        60,
        "float64",
        "1.3",
    ),
    ("chip-cold-plate", "1.4"): Spec(
        "chip-cold-plate",
        "1.4",
        "chip-cold-plate-public-jax-graph-v2",
        "cooling-dev-train-400-v2-encoded",
        "2df26b41a2fdba6a6a64921a9d8c357370374d43d313840ea6e8a371920641d0",
        400,
        9,
        32,
        "float64",
        "1.3",
    ),
}
ADAPTER_IDS = frozenset(spec.adapter_id for spec in SPECS.values())

#: Every closed refusal code this adapter raises: REFUSED (the candidate's),
#: except `graph_route_surface_unserved` (Carbon's GAP). Registered in
#: `build_refusal_v2.CODES`.
REFUSED_SUFFIXES = (
    "batch_exceeds_train",
    "challenge_version_unregistered",
    "ensemble_invalid",
    "input_invalid",
    "loss_unsupported",
    "nonfinite_state",
    "output_unsupported",
    "output_weights_invalid",
    "procedure_invalid",
    "seed_invalid",
    "train_empty",
    "train_invalid",
    "training_field_invalid",
    "training_value_invalid",
    "untrained",
)
GAP_SUFFIXES = ("surface_unserved",)


def spec_for(challenge_id: str, version: str) -> Spec:
    spec = SPECS.get((challenge_id, version))
    if spec is None:
        raise RecipeRefused(CODE + "challenge_version_unregistered")
    return spec


def selected_rows(spec: Spec, fraction: float) -> int:
    """How many TRAIN rows the trainer selects (`physical_graph_trainer_v2`)."""
    return spec.rows if fraction >= 1.0 else int(spec.rows * fraction)


def _number(value) -> bool:
    return type(value) in (int, float) and math.isfinite(value)


def _admitted(value, surface) -> bool:
    kind, low, _default = surface
    if kind == "uint":
        return type(value) is int and low <= value < 2**63
    if kind == "positive":
        return _number(value) and value > 0
    if kind == "nonneg":
        return _number(value) and value >= 0
    if kind == "below1":
        return _number(value) and 0 <= value < 1
    if kind == "unit":
        return _number(value) and 0 <= value <= 1
    if kind == "fraction":
        return _number(value) and 0 < value <= 1
    return type(value) is str and value in low


def _training(selected, base=None) -> dict:
    """A training block resolved over `base` (the defaults when None)."""
    if type(selected) is not dict:
        raise RecipeRefused(CODE + "training_field_invalid")
    unknown = set(selected) - set(TRAIN_SURFACES)
    if unknown - UNSERVED_SURFACES:
        raise RecipeRefused(CODE + "training_field_invalid")
    if unknown:
        raise RecipeRefused(CODE + "surface_unserved")
    values = (
        {name: row[2] for name, row in TRAIN_SURFACES.items()}
        if base is None
        else dict(base)
    )
    values.update(selected)
    if not all(_admitted(values[name], row) for name, row in TRAIN_SURFACES.items()):
        raise RecipeRefused(CODE + "training_value_invalid")
    return values


def _output_weights(value, width: int) -> list:
    if value is None:
        return [1.0] * width
    if (
        type(value) is not list
        or len(value) != width
        or not all(_number(w) and w >= 0 for w in value)
        or not any(w > 0 for w in value)
    ):
        raise RecipeRefused(CODE + "output_weights_invalid")
    return [float(w) for w in value]


def _ensemble(value, training: dict, weights: list, width: int) -> list:
    """The resolved members: each its sorted outputs, weight and training."""
    if value is None:
        return [{"outputs": list(range(width)), "weight": 1.0, "training": training}]
    members = value.get("members") if type(value) is dict else None
    if (
        type(value) is not dict
        or set(value) != {"members"}
        or type(members) is not list
    ):
        raise RecipeRefused(CODE + "ensemble_invalid")
    if not members:
        raise RecipeRefused(CODE + "ensemble_invalid")
    resolved, covered = [], set()
    for member in members:
        if type(member) is not dict or not set(member) <= MEMBER_FIELDS:
            raise RecipeRefused(CODE + "ensemble_invalid")
        outputs = member.get("outputs", list(range(width)))
        weight = member.get("weight", 1.0)
        if (
            type(outputs) is not list
            or not outputs
            or not all(type(i) is int and 0 <= i < width for i in outputs)
            or len(set(outputs)) != len(outputs)
            or not (_number(weight) and weight > 0)
        ):
            raise RecipeRefused(CODE + "ensemble_invalid")
        if not any(weights[i] > 0 for i in outputs):
            # The member would train on nothing it is weighted on.
            raise RecipeRefused(CODE + "ensemble_invalid")
        own = _training(member.get("training", {}), training)
        if own["batch_size"] != training["batch_size"]:
            # The graph is validated and run at one declared batch.
            raise RecipeRefused(CODE + "ensemble_invalid")
        resolved.append(
            {"outputs": sorted(outputs), "weight": float(weight), "training": own}
        )
        covered.update(outputs)
    if covered != set(range(width)):
        # Every output is predicted by some member.
        raise RecipeRefused(CODE + "ensemble_invalid")
    return resolved


def training_settings(recipe: ConstructionRecipe) -> dict:
    """The recipe's resolved settings, or a closed refusal."""
    if type(recipe) is not ConstructionRecipe:
        raise RecipeRefused("construction_recipe_malformed")
    doc = recipe.to_dict()
    spec = spec_for(doc["challenge"]["id"], doc["challenge"]["version"])
    if doc["source"]["kind"] != "graph" or doc["output"]["format"] != OUTPUT_FORMAT:
        raise RecipeRefused(CODE + "output_unsupported")
    config = doc["procedure"]["configuration"]
    use = doc["procedure"]["train_use"]
    if (
        not set(config) <= CONFIGURATION_FIELDS
        or set(use) != {"dataset", "train_fraction"}
        or use["dataset"] != spec.train_use
    ):
        raise RecipeRefused(CODE + "procedure_invalid")
    training = _training(config.get("training", {}))
    if not _admitted(use["train_fraction"], TRAIN_FRACTION):
        raise RecipeRefused(CODE + "training_value_invalid")
    weights = _output_weights(config.get("output_weights"), spec.outputs)
    members = _ensemble(config.get("ensemble"), training, weights, spec.outputs)
    rows = selected_rows(spec, use["train_fraction"])
    if rows < 1:
        raise RecipeRefused(CODE + "train_empty")
    if training["batch_size"] > rows:
        # Never more cases per update than the selected TRAIN rows.
        raise RecipeRefused(CODE + "batch_exceeds_train")
    return {
        "train_fraction": use["train_fraction"],
        "output_weights": weights,
        "ensemble": members,
        # The one batch the graph is validated and every member trains at.
        "batch_size": training["batch_size"],
    }


def graph_interface(spec: Spec):
    from carbon.level4.validate import Interface

    return Interface(
        inputs=((INPUT_NAME, spec.dtype, (spec.inputs,)),),
        outputs=((spec.dtype, (spec.outputs,)),),
    )


def checked_train(spec: Spec, raw: bytes, expected_digest: str):
    """The Challenge's two public TRAIN tensors, by exact digest and shape."""
    if (
        type(raw) is not bytes
        or expected_digest != "sha256:" + spec.train_sha256
        or "sha256:" + hashlib.sha256(raw).hexdigest() != expected_digest
    ):
        raise RecipeRefused(CODE + "train_invalid")
    try:
        with np.load(io.BytesIO(raw), allow_pickle=False) as archive:
            if set(archive.files) != {"inputs", "targets"}:
                raise RecipeRefused(CODE + "train_invalid")
            inputs = archive["inputs"].copy()
            targets = archive["targets"].copy()
    except (OSError, ValueError, KeyError) as error:
        if type(error) is RecipeRefused:
            raise
        raise RecipeRefused(CODE + "train_invalid") from None
    if (
        inputs.dtype != np.dtype(spec.dtype)
        or targets.dtype != np.dtype(spec.dtype)
        or inputs.shape != (spec.rows, spec.inputs)
        or targets.shape != (spec.rows, spec.outputs)
        or not np.isfinite(inputs).all()
        or not np.isfinite(targets).all()
    ):
        raise RecipeRefused(CODE + "train_invalid")
    return inputs, targets


@dataclass(slots=True)
class EnsembleGraphModel:
    """In-worker trained ensemble and decoder; never a judge-side import."""

    recipe: ConstructionRecipe
    spec: Spec
    forward: dict
    prepared: object
    allowlist: object
    settings: dict
    members: list | None = None
    combine: np.ndarray | None = None
    mu: np.ndarray | None = None
    sd: np.ndarray | None = None

    def fit(self, inputs: np.ndarray, targets: np.ndarray, *, seed: int) -> dict:
        from . import physical_graph_trainer_v2

        if type(seed) is not int or seed < 0:
            raise RecipeRefused(CODE + "seed_invalid")
        if (
            type(inputs) is not np.ndarray
            or type(targets) is not np.ndarray
            or inputs.dtype != np.dtype(self.spec.dtype)
            or targets.dtype != np.dtype(self.spec.dtype)
            or inputs.shape != (self.spec.rows, self.spec.inputs)
            or targets.shape != (self.spec.rows, self.spec.outputs)
        ):
            raise RecipeRefused(CODE + "train_invalid")
        fitted = physical_graph_trainer_v2.train(
            self.prepared, inputs, targets, self.settings, seed=seed
        )
        if fitted["selected_rows"] < 1:
            raise RecipeRefused(CODE + "train_empty")
        members = fitted["members"]
        if len(members) != len(self.settings["ensemble"]) or not all(
            len(params) == len(self.prepared.parameters)
            and all(np.isfinite(value).all() for value in params)
            for params in members
        ):
            raise RecipeRefused(CODE + "nonfinite_state")
        losses = [fitted["train_loss"], *fitted["member_losses"]]
        if not all(math.isfinite(value) for value in losses):
            raise RecipeRefused(CODE + "nonfinite_state")
        self.members, self.combine = members, fitted["combine"]
        self.mu, self.sd = fitted["mu"], fitted["sd"]
        blob = b"".join(
            np.ascontiguousarray(value).tobytes()
            for params in members
            for value in params
        )
        return {
            "adapter_id": self.spec.adapter_id,
            "trainer_sha256": "sha256:" + TRAINER_SHA256,
            "members": len(members),
            "steps": [
                member["training"]["steps"] for member in self.settings["ensemble"]
            ],
            "train_cases": fitted["selected_rows"],
            "train_loss": fitted["train_loss"],
            "member_losses": fitted["member_losses"],
            "params_sha256": "sha256:" + hashlib.sha256(blob).hexdigest(),
            "recipe_digest": self.recipe.digest,
        }

    def predict(self, inputs: np.ndarray, *, isolated: bool = False) -> np.ndarray:
        """`isolated` is the judge's per-case grading: one case per call, row 0."""
        import jax.numpy as jnp

        if self.members is None:
            raise RecipeRefused(CODE + "untrained")
        if (
            type(inputs) is not np.ndarray
            or inputs.dtype != np.dtype(self.spec.dtype)
            or inputs.ndim != 2
            or inputs.shape[1] != self.spec.inputs
            or not len(inputs)
            or not np.isfinite(inputs).all()
        ):
            raise RecipeRefused(CODE + "input_invalid")
        x = jnp.asarray(inputs)
        normalized = sum(
            np.asarray(
                self.prepared.predict(
                    [jnp.asarray(value) for value in params], x, isolated=isolated
                )[0]
            )
            * self.combine[index]
            for index, params in enumerate(self.members)
        )
        result = (normalized * self.sd + self.mu).astype(self.spec.dtype)
        if result.shape != (len(inputs), self.spec.outputs) or not (
            np.isfinite(result).all()
        ):
            raise RecipeRefused(CODE + "nonfinite_state")
        return result

    def frozen_state(self) -> bytes:
        if self.members is None:
            raise RecipeRefused(CODE + "untrained")
        return physical_graph_state_v2.freeze(
            self.recipe,
            self.forward,
            self.members,
            self.allowlist,
            self.mu,
            self.sd,
            self.combine,
        )


def build_validated_graph(
    recipe: ConstructionRecipe,
    raw_manifest: bytes,
    files: dict,
    *,
    allowlist_bytes: bytes,
    train_cases: int,
) -> EnsembleGraphModel:
    """Verify graph bytes, G0/G3/G4 and the exact interface before fit.

    `allowlist_bytes` must be the version's served graph allowlist; the host
    checks it (`served_allowlist_bytes`) before staging, and the worker checks
    the staged bytes' digest against the host's control."""
    from carbon.level4 import intake, validate
    from carbon.level4.allowlist import Allowlist
    from carbon.level4.train import prepare

    settings = training_settings(recipe)
    named = recipe.to_dict()["challenge"]
    spec = spec_for(named["id"], named["version"])
    if type(train_cases) is not int or train_cases != spec.rows:
        raise RecipeRefused(CODE + "train_invalid")
    allowed = Allowlist(allowlist_bytes)
    graph_workspace(
        recipe,
        raw_manifest,
        files,
        max_bytes=intake.bounds_for(allowed)["submission_bytes"],
    )
    interface = graph_interface(spec)
    _, parsed = intake.intake(
        raw_manifest,
        files,
        allowlist=allowed,
        challenge=spec.challenge_id,
        interface=interface.digest(),
        loss_override="none",
    )
    verdict = validate.validate_submission(
        parsed,
        allowed,
        interface=interface,
        batch=settings["batch_size"],
        loss_override="none",
    )
    if verdict["status"] != "admitted":
        raise intake.IntakeBlocked("graph validation did not admit")
    if "loss" in parsed:
        raise RecipeRefused(CODE + "loss_unsupported")
    return EnsembleGraphModel(
        recipe,
        spec,
        parsed["forward"],
        prepare(parsed, allowed, verdict=verdict),
        allowed,
        settings,
    )


# --- Host side (never called inside the worker) ------------------------------------


def served_allowlist_bytes(challenge_id: str, version: str) -> bytes:
    """The version's served graph allowlist (`served_versions`)."""
    from carbon.challenge_kit.served_versions import graph_allowlist_bytes

    spec_for(challenge_id, version)
    return graph_allowlist_bytes(challenge_id, version)


def trainer_source() -> bytes:
    """The v2 trainer's exact bytes, or ValueError if they moved."""
    from pathlib import Path

    raw = (Path(__file__).resolve().parents[2] / TRAINER_PATH).read_bytes()
    if hashlib.sha256(raw).hexdigest() != TRAINER_SHA256:
        raise ValueError("pinned physical graph trainer v2 bytes differ")
    return raw


def _surface(row) -> dict:
    kind, low, default = row
    return {
        "kind": kind,
        **({"choices": list(low)} if kind == "choice" else {}),
        **({"low": low} if kind == "uint" else {}),
        "default": default,
    }


def adapter_block(challenge_id: str, version: str) -> dict:
    """The `graph_training_adapter` block of a graph route v2 version's limits."""
    spec = spec_for(challenge_id, version)
    return {
        "schema": ADAPTER_SCHEMA,
        "id": spec.adapter_id,
        "source_kind": "graph",
        "train_use_dataset": spec.train_use,
        "train_use_fields": ["dataset", "train_fraction"],
        "procedure_schema": PROCEDURE_SCHEMA,
        "configuration_fields": sorted(CONFIGURATION_FIELDS),
        "output_format": OUTPUT_FORMAT,
        "state_schema": physical_graph_state_v2.ENSEMBLE_SCHEMA,
        "state_decoder_schema": physical_graph_state_v2.DECODER_SCHEMA,
        "interface": {
            "input": INPUT_NAME,
            "dtype": spec.dtype,
            "input_shape": [spec.inputs],
            "output_shape": [spec.outputs],
        },
        "train_surfaces": {
            name: _surface(row) for name, row in sorted(TRAIN_SURFACES.items())
        },
        "train_fraction": _surface(TRAIN_FRACTION),
        "batch_size_limit": "selected_train_rows",
        "precision": "the output is the interface dtype; computation is the graph's",
        "output_weights": {
            "length": spec.outputs,
            "kind": "nonneg",
            "default": "1 for every output",
            "rule": "at least one above zero",
        },
        "ensemble": {
            "member_fields": sorted(MEMBER_FIELDS),
            "member_training": "any surface but batch_size (the graph's one batch)",
            "members": "one or more; no cap beyond the build's resource limits",
            "default": "one member on every output",
            "outputs": "distinct output indices; every output in some member",
            "combine": "per output, the weight-weighted mean of its members",
            "member_seed": "carbon.level4.train.keys folded with the member index",
        },
        "trainer": {
            "module": TRAINER_MODULE,
            "sha256": "sha256:" + TRAINER_SHA256,
            "target_standardisation": "per_column_selected_train_rows",
            "loss": "per-output weighted, over the member's outputs",
            "seed": "carbon.level4.train.keys",
        },
        "predecessor": spec.predecessor,
        "inference": "one_isolated_case_per_call",
        "value_status": "DEVELOPMENT",
    }
