"""Fixture-only trainer for a submitted direct graph on fixed public TRAIN.

This is one Challenge-owned development adapter, not a general admission
rule for miner training choices. Unsupported choices are implementation gaps.
It does not execute participant Python or decide scientific qualification.
The isolated construction worker calls it after binding the exact graph bytes
and registered TRAIN archive.
"""

from __future__ import annotations

import io
import math
from dataclasses import dataclass

import numpy as np

from carbon.level4 import intake, validate
from carbon.level4.allowlist import Allowlist
from carbon.level4.train import keys, prepare

from .bundle_graph_state import freeze
from .construction_recipe import ConstructionRecipe, RecipeRefused, graph_workspace

TRAIN_USE = "synthetic-linear-field-2d-public-train"
ADAPTER_ID = "synthetic-linear-field-2d-public-jax-graph-v1"
OUTPUT_FORMAT = "carbon.numeric-graph.v1"
FIELD_SHAPE = (8, 8, 1)


def graph_interface() -> validate.Interface:
    return validate.Interface(
        inputs=(("inputs/forcing", "float32", FIELD_SHAPE),),
        outputs=(("float32", FIELD_SHAPE),),
    )


def training_settings(recipe: ConstructionRecipe, train_cases: int) -> dict:
    """Resolve the synthetic fixture's finite optimizer, independent of names."""
    if type(recipe) is not ConstructionRecipe or type(train_cases) is not int:
        raise RecipeRefused("synthetic_graph_recipe_invalid")
    doc = recipe.to_dict()
    if (
        doc["source"]["kind"] != "graph"
        or doc["output"]["format"] != OUTPUT_FORMAT
        or train_cases < 1
    ):
        raise RecipeRefused("synthetic_graph_source_or_output_invalid")
    procedure = doc["procedure"]
    use = procedure["train_use"]
    if (
        type(use) is not dict
        or use.get("dataset") != TRAIN_USE
        or set(use)
        not in (
            {"dataset", "coverage"},
            {"dataset", "row_indices_by_step"},
        )
    ):
        raise RecipeRefused("synthetic_graph_train_use_unavailable")
    if "coverage" in use and use["coverage"] != "all":
        raise RecipeRefused("synthetic_graph_train_use_unavailable")
    configuration = procedure["configuration"]
    if type(configuration) is not dict or set(configuration) != {"training"}:
        raise RecipeRefused("synthetic_graph_training_adapter_unavailable")
    training = configuration["training"]
    if (
        type(training) is not dict
        or set(training) != {"optimizer", "steps", "learning_rate"}
        or training["optimizer"] not in ("sgd", "adam")
        or type(training["steps"]) is not int
        or not 1 <= training["steps"] <= 512
        or type(training["learning_rate"]) not in (int, float)
        or not math.isfinite(training["learning_rate"])
        or not 0 < training["learning_rate"] <= 10
    ):
        raise RecipeRefused("synthetic_graph_training_adapter_unavailable")
    schedule = use.get("row_indices_by_step")
    if "row_indices_by_step" in use:
        if (
            type(schedule) is not list
            or len(schedule) != training["steps"]
            or any(
                type(rows) is not list
                or not 1 <= len(rows) <= train_cases
                or any(
                    type(index) is not int or not 0 <= index < train_cases
                    for index in rows
                )
                for rows in schedule
            )
        ):
            raise RecipeRefused("synthetic_graph_train_use_invalid")
        schedule = tuple(tuple(rows) for rows in schedule)
    return {
        "optimizer": training["optimizer"],
        "steps": training["steps"],
        "learning_rate": float(training["learning_rate"]),
        "row_indices_by_step": schedule,
    }


def checked_train(raw: bytes, expected_digest: str) -> tuple[np.ndarray, np.ndarray]:
    """Read only the Challenge's two public tensors; no caller data substitution."""
    import hashlib

    if (
        type(raw) is not bytes
        or type(expected_digest) is not str
        or "sha256:" + hashlib.sha256(raw).hexdigest() != expected_digest
    ):
        raise RecipeRefused("synthetic_graph_train_binding_invalid")
    try:
        with np.load(io.BytesIO(raw), allow_pickle=False) as archive:
            if set(archive.files) != {"inputs", "targets"}:
                raise RecipeRefused("synthetic_graph_train_archive_invalid")
            inputs = archive["inputs"].copy()
            targets = archive["targets"].copy()
    except (OSError, ValueError, KeyError):
        raise RecipeRefused("synthetic_graph_train_archive_invalid") from None
    if (
        inputs.dtype != np.float32
        or targets.dtype != np.float32
        or inputs.ndim != 4
        or targets.shape != inputs.shape
        or inputs.shape[1:] != FIELD_SHAPE
        or len(inputs) < 1
        or not np.isfinite(inputs).all()
        or not np.isfinite(targets).all()
    ):
        raise RecipeRefused("synthetic_graph_train_tensor_invalid")
    return inputs, targets


@dataclass(slots=True)
class SyntheticGraphModel:
    recipe: ConstructionRecipe
    forward: dict
    prepared: object
    allowlist: Allowlist
    settings: dict
    params: list | None = None

    def fit(self, inputs: np.ndarray, targets: np.ndarray, *, seed: int) -> dict:
        import jax
        import jax.numpy as jnp

        if (
            type(seed) is not int
            or seed < 0
            or type(inputs) is not np.ndarray
            or type(targets) is not np.ndarray
            or inputs.shape != targets.shape
            or inputs.dtype != np.float32
            or targets.dtype != np.float32
            or inputs.shape[1:] != FIELD_SHAPE
            or len(inputs) < self.prepared.batch
        ):
            raise RecipeRefused("synthetic_graph_fit_binding_invalid")
        init_key, _train_key = keys(seed)
        params = list(self.prepared.init(init_key))
        if len(params) != len(self.prepared.parameters):
            raise RecipeRefused("synthetic_graph_parameter_count_invalid")
        n = len(inputs)
        x = jnp.asarray(inputs)
        y = jnp.asarray(targets)
        learning_rate = self.settings["learning_rate"]
        optimizer = self.settings["optimizer"]
        if optimizer == "adam":
            import optax

            transform = optax.adam(learning_rate)
            optimizer_state = transform.init(params)

        def loss_fn(values, sample_x, sample_y):
            predicted = self.prepared.predict(values, sample_x)[0]
            if self.prepared.loss is not None:
                return self.prepared.loss(predicted, sample_y, sample_x)
            return jnp.mean((predicted - sample_y) ** 2)

        last_loss = None
        schedule = self.settings["row_indices_by_step"]
        for step in range(self.settings["steps"]):
            if schedule is None:
                step_x, step_y = x, y
            else:
                indices = jnp.asarray(schedule[step], dtype=jnp.int32)
                step_x, step_y = x[indices], y[indices]
            last_loss, gradients = jax.value_and_grad(loss_fn)(params, step_x, step_y)
            if optimizer == "adam":
                updates, optimizer_state = transform.update(
                    gradients, optimizer_state, params
                )
                params = optax.apply_updates(params, updates)
            else:
                params = jax.tree_util.tree_map(
                    lambda value, grad: value - learning_rate * grad,
                    params,
                    gradients,
                )
            if not all(
                np.isfinite(np.asarray(leaf)).all()
                for leaf in jax.tree_util.tree_leaves(params)
            ):
                raise RecipeRefused("synthetic_graph_nonfinite_state")
        self.params = [np.asarray(value) for value in params]
        if schedule is not None:
            last_loss = loss_fn(params, x, y)
        return {
            "steps": self.settings["steps"],
            "train_cases": n,
            "full_train_loss": float(last_loss),
            "recipe_digest": self.recipe.digest,
        }

    def predict(self, inputs: np.ndarray) -> np.ndarray:
        import jax.numpy as jnp

        if self.params is None or type(inputs) is not np.ndarray:
            raise RecipeRefused("synthetic_graph_untrained")
        predicted = self.prepared.predict(
            [jnp.asarray(value) for value in self.params], jnp.asarray(inputs)
        )
        if len(predicted) != 1:
            raise RecipeRefused("synthetic_graph_output_count_invalid")
        result = np.asarray(predicted[0])
        if (
            result.dtype != np.float32
            or result.shape != inputs.shape
            or not np.isfinite(result).all()
        ):
            raise RecipeRefused("synthetic_graph_output_invalid")
        return result

    def frozen_state(self) -> bytes:
        if self.params is None:
            raise RecipeRefused("synthetic_graph_untrained")
        return freeze(self.recipe, self.forward, self.params, self.allowlist)


def build_validated_graph(
    recipe: ConstructionRecipe,
    raw_manifest: bytes,
    files: dict,
    *,
    allowlist_bytes: bytes,
    train_cases: int,
) -> SyntheticGraphModel:
    """Rebuild the submitted graph exactly under the synthetic I/O contract."""
    settings = training_settings(recipe, train_cases)
    graph_workspace(
        recipe, raw_manifest, files, max_bytes=intake.BOUNDS["submission_bytes"]
    )
    allowed = Allowlist(allowlist_bytes)
    interface = graph_interface()
    _, parsed = intake.intake(
        raw_manifest,
        files,
        allowlist=allowed,
        challenge=recipe.to_dict()["challenge"]["id"],
        interface=interface.digest(),
        loss_override="graph",
    )
    verdict = validate.validate_submission(
        parsed,
        allowed,
        interface=interface,
        batch=None,
        loss_override="graph",
    )
    if verdict["status"] != "admitted":
        raise intake.IntakeBlocked("graph validation did not admit")
    if verdict["batch"] > train_cases:
        raise RecipeRefused("synthetic_graph_batch_exceeds_train")
    return SyntheticGraphModel(
        recipe,
        parsed["forward"],
        prepare(parsed, allowed, verdict=verdict),
        allowed,
        settings,
    )
