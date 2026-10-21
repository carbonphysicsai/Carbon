"""F08 and F02 graph training adapters (Validator's rulings, 2026-10-20).

`codex-queue/reports/LAUNCHPAD_F08_F02_GRAPH_ADAPTER_SPEC_DRAFT_20261020.md`,
approved to build:

1. the training surfaces and bounds below are DEVELOPMENT values, plus a
   closed refusal when `batch_size` exceeds the selected TRAIN rows;
2. one generic pinned trainer (`physical_graph_trainer`), whose source digest
   is in the construction identity (the limits block below);
3. graphs are served on F08 1.4 and F02 2.3 only (no 1.5 / 2.4);
4. F02 gets no restriction beyond its interface.

One module, parameterised per Challenge, on Battery's `direct_graph` pattern:
`training_settings` refuses anything outside the surfaces with a closed
`f08_graph_` / `f02_graph_` code, `build_validated_graph` runs G0/G3/G4
(`carbon.level4.intake`) against the version's served allowlist, then the model
trains with the pinned trainer and predicts one isolated case per call.

It runs inside the isolated build worker with only its staged modules, so the
Challenge constants are kept here, not imported (a test holds them equal to
`f08_train` / `f02_train`). Nothing here is an evaluation, a qualification or
LIVE authority.
"""

from __future__ import annotations

import hashlib
import io
import math
from dataclasses import dataclass

import numpy as np

from . import physical_graph_state
from .construction_recipe import ConstructionRecipe, RecipeRefused, graph_workspace

ADAPTER_SCHEMA = "carbon.physical-graph-training-adapter.v1"
OUTPUT_FORMAT = "carbon.numeric-graph.v1"
PROCEDURE_SCHEMA = "carbon.construction-recipe.v1"
INPUT_NAME = "inputs/features"
TRAINER_MODULE = "carbon.development_session.physical_graph_trainer"
TRAINER_PATH = "carbon/development_session/physical_graph_trainer.py"
#: The pinned trainer's source sha256 (tests/cpu/test_f08_f02_graph_adapters.py
#: re-hashes it). A change to the trainer is a new digest, so a new version.
TRAINER_SHA256 = "3e97569bafd4b2f25312c8e1c01aa3fe5e581af94d2802a85ce17b29b62db7e5"
TRAINER_PIN = (TRAINER_PATH, TRAINER_SHA256)

#: (kind, low, high, default), copied from the registered rows of
#: `carbon/reconstruction/capability_registry.py` the spec names (its lines
#: ~252-379; `train_fraction` from Battery's row, ~1023). `high` None: no fixed
#: cap (OWNER-REBUILD-TIME-LIMIT-01; the build wall time bounds training).
#: `precision` admits float32 only, the interface's `<f4`.
TRAIN_SURFACES = {
    "steps": ("uint", 2, None, 512),
    "batch_size": ("uint", 1, 64, 8),
    "learning_rate": ("float", 0.000001, 0.05, 0.002),
    "weight_decay": ("float", 0.0, 0.1, 0.0001),
    "beta1": ("float", 0.0, 0.9999, 0.9),
    "beta2": ("float", 0.0, 0.99999, 0.999),
    "adam_epsilon": ("float", 1e-12, 0.01, 1e-8),
    "warmup_steps": ("uint", 0, None, 0),
    "precision": ("choice", ("float32",), None, "float32"),
}
TRAIN_FRACTION = ("float", 0.1, 1.0, 1.0)
#: Carbon's other registered training surfaces (Burgers' and Battery's train
#: rows; a test derives this set): naming one is a capability gap, never the
#: candidate's fault. `train_fraction` is served, in `train_use`.
UNSERVED_SURFACES = frozenset(
    {
        "backend",
        "clip_norm",
        "curriculum",
        "ema_decay",
        "ensemble_members",
        "h1_weight",
        "h2_weight",
        "hard_example_weight",
        "important_region_weight",
        "inference_weights",
        "learning_rate_curve",
        "microbatches",
        "min_learning_rate_ratio",
        "optimizer_family",
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


@dataclass(frozen=True)
class Spec:
    challenge_id: str
    version: str
    prefix: str
    adapter_id: str
    train_use: str
    train_sha256: str
    rows: int
    inputs: int
    outputs: int


#: The served graph versions. TRAIN digests equal `f08_train.TRAIN_V2_SHA256`
#: and `f02_train.TRAIN_SHA256`; shapes equal their interface documents.
SPECS = {
    ("f08-ribbed-bracket", "1.4"): Spec(
        "f08-ribbed-bracket",
        "1.4",
        "f08",
        "f08-ribbed-bracket-public-jax-graph-v1",
        "f08-pinned-train-v2",
        "4b28e7490eca34061da1431c6379f0f2e5766ff41aedba968eba41ba84fefe0a",
        287,
        6,
        7,
    ),
    ("f02", "2.3"): Spec(
        "f02",
        "2.3",
        "f02",
        "f02-public-jax-graph-v1",
        "f02-pinned-train40-v2",
        "1201ec5461bfc08ad2ae4522eafc147282f4167e4bb222ed4e798284faa9a4c3",
        40,
        2,
        1,
    ),
}
PREFIXES = {spec.challenge_id: spec.prefix for spec in SPECS.values()}
ADAPTER_IDS = frozenset(spec.adapter_id for spec in SPECS.values())

#: Every closed refusal code this adapter raises, by prefix: REFUSED (the
#: candidate's), except `surface_unserved` (Carbon's GAP). Registered in
#: `build_refusal.CODES`.
REFUSED_SUFFIXES = (
    "batch_exceeds_train",
    "challenge_version_unregistered",
    "input_invalid",
    "loss_unsupported",
    "nonfinite_state",
    "output_unsupported",
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
        prefix = PREFIXES.get(challenge_id)
        if prefix is None:
            raise RecipeRefused("construction_recipe_challenge_invalid")
        raise RecipeRefused(f"{prefix}_graph_challenge_version_unregistered")
    return spec


def selected_rows(spec: Spec, fraction: float) -> int:
    """How many TRAIN rows the trainer selects (`physical_graph_trainer`)."""
    return spec.rows if fraction >= 1.0 else int(spec.rows * fraction)


def _admitted(value, surface) -> bool:
    kind, low, high, _default = surface
    if kind == "uint":
        return (
            type(value) is int
            and low <= value
            and (value <= high if high is not None else value < 2**63)
        )
    if kind == "float":
        return (
            type(value) in (int, float)
            and math.isfinite(value)
            and low <= value <= high
        )
    return type(value) is str and value in low


def training_settings(recipe: ConstructionRecipe) -> dict:
    """The recipe's resolved training settings, or a closed refusal."""
    if type(recipe) is not ConstructionRecipe:
        raise RecipeRefused("construction_recipe_malformed")
    doc = recipe.to_dict()
    spec = spec_for(doc["challenge"]["id"], doc["challenge"]["version"])
    code = spec.prefix + "_graph_"
    if doc["source"]["kind"] != "graph" or doc["output"]["format"] != OUTPUT_FORMAT:
        raise RecipeRefused(code + "output_unsupported")
    config = doc["procedure"]["configuration"]
    use = doc["procedure"]["train_use"]
    if (
        set(config) != {"training"}
        or type(config["training"]) is not dict
        or set(use) != {"dataset", "train_fraction"}
        or use["dataset"] != spec.train_use
    ):
        raise RecipeRefused(code + "procedure_invalid")
    selected = config["training"]
    unknown = set(selected) - set(TRAIN_SURFACES)
    if unknown - UNSERVED_SURFACES:
        raise RecipeRefused(code + "training_field_invalid")
    if unknown:
        raise RecipeRefused(code + "surface_unserved")
    values = {name: row[3] for name, row in TRAIN_SURFACES.items()}
    values.update(selected)
    if not all(_admitted(values[name], row) for name, row in TRAIN_SURFACES.items()):
        raise RecipeRefused(code + "training_value_invalid")
    if not _admitted(use["train_fraction"], TRAIN_FRACTION):
        raise RecipeRefused(code + "training_value_invalid")
    values["train_fraction"] = use["train_fraction"]
    rows = selected_rows(spec, values["train_fraction"])
    if rows < 1:
        raise RecipeRefused(code + "train_empty")
    if values["batch_size"] > rows:
        # The Validator's addition (2026-10-20): never more cases per update
        # than the selected TRAIN rows.
        raise RecipeRefused(code + "batch_exceeds_train")
    return values


def graph_interface(spec: Spec):
    from carbon.level4.validate import Interface

    return Interface(
        inputs=((INPUT_NAME, "float32", (spec.inputs,)),),
        outputs=(("float32", (spec.outputs,)),),
    )


def checked_train(spec: Spec, raw: bytes, expected_digest: str):
    """The Challenge's two public TRAIN tensors, by exact digest and shape."""
    if (
        type(raw) is not bytes
        or expected_digest != "sha256:" + spec.train_sha256
        or "sha256:" + hashlib.sha256(raw).hexdigest() != expected_digest
    ):
        raise RecipeRefused(spec.prefix + "_graph_train_invalid")
    try:
        with np.load(io.BytesIO(raw), allow_pickle=False) as archive:
            if set(archive.files) != {"inputs", "targets"}:
                raise RecipeRefused(spec.prefix + "_graph_train_invalid")
            inputs = archive["inputs"].copy()
            targets = archive["targets"].copy()
    except (OSError, ValueError, KeyError) as error:
        if type(error) is RecipeRefused:
            raise
        raise RecipeRefused(spec.prefix + "_graph_train_invalid") from None
    if (
        inputs.dtype != np.float32
        or targets.dtype != np.float32
        or inputs.shape != (spec.rows, spec.inputs)
        or targets.shape != (spec.rows, spec.outputs)
        or not np.isfinite(inputs).all()
        or not np.isfinite(targets).all()
    ):
        raise RecipeRefused(spec.prefix + "_graph_train_invalid")
    return inputs, targets


@dataclass(slots=True)
class PhysicalGraphModel:
    """In-worker trained graph and decoder; never a judge-side import."""

    recipe: ConstructionRecipe
    spec: Spec
    forward: dict
    prepared: object
    allowlist: object
    settings: dict
    params: list | None = None
    mu: np.ndarray | None = None
    sd: np.ndarray | None = None

    def fit(self, inputs: np.ndarray, targets: np.ndarray, *, seed: int) -> dict:
        from . import physical_graph_trainer

        code = self.spec.prefix + "_graph_"
        if type(seed) is not int or seed < 0:
            raise RecipeRefused(code + "seed_invalid")
        if (
            type(inputs) is not np.ndarray
            or type(targets) is not np.ndarray
            or inputs.dtype != np.float32
            or targets.dtype != np.float32
            or inputs.shape != (self.spec.rows, self.spec.inputs)
            or targets.shape != (self.spec.rows, self.spec.outputs)
        ):
            raise RecipeRefused(code + "train_invalid")
        fitted = physical_graph_trainer.train(
            self.prepared, inputs, targets, self.settings, seed=seed
        )
        if fitted["selected_rows"] < 1:
            raise RecipeRefused(code + "train_empty")
        params = fitted["params"]
        if len(params) != len(self.prepared.parameters) or not all(
            np.isfinite(value).all() for value in params
        ):
            raise RecipeRefused(code + "nonfinite_state")
        if not math.isfinite(fitted["train_loss"]):
            raise RecipeRefused(code + "nonfinite_state")
        self.params, self.mu, self.sd = params, fitted["mu"], fitted["sd"]
        blob = b"".join(np.ascontiguousarray(value).tobytes() for value in params)
        return {
            "adapter_id": self.spec.adapter_id,
            "trainer_sha256": "sha256:" + TRAINER_SHA256,
            "steps": self.settings["steps"],
            "train_cases": fitted["selected_rows"],
            "train_loss": fitted["train_loss"],
            "params_sha256": "sha256:" + hashlib.sha256(blob).hexdigest(),
            "recipe_digest": self.recipe.digest,
        }

    def predict(self, inputs: np.ndarray, *, isolated: bool = False) -> np.ndarray:
        """`isolated` is the judge's per-case grading: one case per call, row 0."""
        import jax.numpy as jnp

        code = self.spec.prefix + "_graph_"
        if self.params is None:
            raise RecipeRefused(code + "untrained")
        if (
            type(inputs) is not np.ndarray
            or inputs.dtype != np.float32
            or inputs.ndim != 2
            or inputs.shape[1] != self.spec.inputs
            or not len(inputs)
            or not np.isfinite(inputs).all()
        ):
            raise RecipeRefused(code + "input_invalid")
        normalized = np.asarray(
            self.prepared.predict(
                [jnp.asarray(value) for value in self.params],
                jnp.asarray(inputs),
                isolated=isolated,
            )[0]
        )
        result = (normalized * self.sd + self.mu).astype(np.float32)
        if result.shape != (len(inputs), self.spec.outputs) or not (
            np.isfinite(result).all()
        ):
            raise RecipeRefused(code + "nonfinite_state")
        return result

    def frozen_state(self) -> bytes:
        if self.params is None:
            raise RecipeRefused(self.spec.prefix + "_graph_untrained")
        return physical_graph_state.freeze(
            self.recipe, self.forward, self.params, self.allowlist, self.mu, self.sd
        )


def build_validated_graph(
    recipe: ConstructionRecipe,
    raw_manifest: bytes,
    files: dict,
    *,
    allowlist_bytes: bytes,
    train_cases: int,
) -> PhysicalGraphModel:
    """Verify graph bytes, G0/G3/G4 and the exact interface before fit.

    `allowlist_bytes` must be the version's served graph allowlist; the host
    checks it (`served_allowlist_bytes`) before staging, and the worker checks
    the staged bytes' digest against the host's control.
    """
    from carbon.level4 import intake, validate
    from carbon.level4.allowlist import Allowlist
    from carbon.level4.train import prepare

    settings = training_settings(recipe)
    spec = spec_for(
        recipe.to_dict()["challenge"]["id"], recipe.to_dict()["challenge"]["version"]
    )
    if type(train_cases) is not int or train_cases != spec.rows:
        raise RecipeRefused(spec.prefix + "_graph_train_invalid")
    allowed = Allowlist(allowlist_bytes)
    # The version's own intake bound: its allowlist's (containment on v7).
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
        raise RecipeRefused(spec.prefix + "_graph_loss_unsupported")
    return PhysicalGraphModel(
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
    """The pinned trainer's exact bytes, or ValueError if they moved."""
    from pathlib import Path

    raw = (Path(__file__).resolve().parents[2] / TRAINER_PATH).read_bytes()
    if hashlib.sha256(raw).hexdigest() != TRAINER_SHA256:
        raise ValueError("pinned physical graph trainer bytes differ")
    return raw


def adapter_block(challenge_id: str, version: str) -> dict:
    """The `graph_training_adapter` block of a served version's limits."""
    spec = spec_for(challenge_id, version)

    def surface(row):
        kind, low, high, default = row
        return {
            "kind": kind,
            "low": list(low) if type(low) is tuple else low,
            "high": high,
            "default": default,
        }

    return {
        "schema": ADAPTER_SCHEMA,
        "id": spec.adapter_id,
        "source_kind": "graph",
        "train_use_dataset": spec.train_use,
        "train_use_fields": ["dataset", "train_fraction"],
        "procedure_schema": PROCEDURE_SCHEMA,
        "output_format": OUTPUT_FORMAT,
        "state_schema": physical_graph_state.GRAPH_SCHEMA,
        "state_decoder_schema": physical_graph_state.DECODER_SCHEMA,
        "interface": {
            "input": INPUT_NAME,
            "dtype": "float32",
            "input_shape": [spec.inputs],
            "output_shape": [spec.outputs],
        },
        "train_surfaces": {
            name: surface(row) for name, row in sorted(TRAIN_SURFACES.items())
        },
        "train_fraction": surface(TRAIN_FRACTION),
        "batch_size_limit": "selected_train_rows",
        "trainer": {
            "module": TRAINER_MODULE,
            "sha256": "sha256:" + TRAINER_SHA256,
            "target_standardisation": "per_column_selected_train_rows",
            "loss": "unweighted_mse_standardised_units",
            "optimizer": "adamw",
            "seed": "carbon.level4.train.keys",
        },
        "inference": "one_isolated_case_per_call",
        "value_status": "DEVELOPMENT",
    }
