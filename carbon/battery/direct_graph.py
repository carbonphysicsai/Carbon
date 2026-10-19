"""Battery's prospective family-neutral graph construction adapter.

The graph and training choices come from one direct recipe. This module
reuses Carbon's registered graph semantics and Battery TRAIN loop, without a
base MLP/DeepONet recipe. It is *not* a public worker entrypoint: callers use
the separately isolated direct_graph_worker for public DEVELOPMENT practice.
Official evaluation remains unserved pending a separate inference transfer.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import zipfile

import numpy as np

from carbon.development_session.construction_recipe import (
    ConstructionRecipe,
    RecipeRefused,
    graph_workspace,
)

from . import domain

OUTPUT_FORMAT = "carbon.battery.raw-numeric.v1"
TRAIN_USE = "battery-pinned-train-v1"
CHALLENGE_ID = "battery-fastcharge-ageing-development-v1"


def _surface_value(value, surface) -> bool:
    _group, kind, low, high, _default, _families = surface
    if kind == "uint":
        return type(value) is int and low <= value <= high
    if kind == "float":
        return (
            type(value) in (int, float)
            and math.isfinite(value)
            and low <= value <= high
        )
    if kind == "bool":
        return type(value) is bool
    return type(value) is str and value in low


def training_settings(recipe: ConstructionRecipe) -> dict:
    """Resolve registered Battery training surfaces, without family admission.

    The current direct graph adapter supports one JAX model and the existing
    Battery trainer. Other profiles receive a precise compatibility refusal;
    no architecture name, level or combination is consulted.
    """
    from carbon.reconstruction.capability_registry import (
        BATTERY_CHALLENGE,
        catalog_surfaces,
    )

    if type(recipe) is not ConstructionRecipe:
        raise RecipeRefused("construction_recipe_malformed")
    doc = recipe.to_dict()
    if doc["source"]["kind"] != "graph" or doc["output"]["format"] != OUTPUT_FORMAT:
        raise RecipeRefused("battery_graph_output_unsupported")
    config = doc["procedure"]["configuration"]
    use = doc["procedure"]["train_use"]
    if (
        set(config) != {"training"}
        or type(config["training"]) is not dict
        or type(use) is not dict
        or set(use) != {"dataset", "train_fraction", "curriculum"}
        or use["dataset"] != TRAIN_USE
    ):
        raise RecipeRefused("battery_graph_procedure_invalid")
    surfaces = {
        name: row
        for name, row in catalog_surfaces(BATTERY_CHALLENGE).items()
        if row[0] == "train"
    }
    selected = config["training"]
    if set(selected) - set(surfaces) or set(selected) & {
        "train_fraction",
        "curriculum",
    }:
        raise RecipeRefused("battery_graph_training_field_invalid")
    values = {name: row[4] for name, row in surfaces.items()}
    values.update(selected)
    values["train_fraction"] = use["train_fraction"]
    values["curriculum"] = use["curriculum"]
    if any(not _surface_value(value, surfaces[name]) for name, value in values.items()):
        raise RecipeRefused("battery_graph_training_value_invalid")
    if values["backend"] != "jax":
        raise RecipeRefused("battery_graph_backend_unsupported")
    if values["ensemble_members"] != 1:
        raise RecipeRefused("battery_graph_ensemble_unsupported")
    from .compile import rebuild_issues

    if rebuild_issues(
        "graph", values, frozenset(selected) | {"train_fraction", "curriculum"}
    ):
        raise RecipeRefused("battery_graph_training_dependency_invalid")
    return values


def graph_interface(settings: dict):
    """Fixed raw-input/flat-normalized-target interface of this adapter."""
    from carbon.level4.validate import Interface

    dtype = "float64" if settings["precision"] == "float64" else "float32"
    width = 2 * domain.GRID_POINTS + 1 + len(domain.CAPACITY_CYCLES)
    return Interface(
        inputs=(("inputs/features", dtype, (len(domain.INPUTS),)),),
        outputs=((dtype, (width,)),),
    )


def _targets(train: domain.TrainingData) -> np.ndarray:
    return np.column_stack((train.v, train.t, train.eta, train.q))


class DirectGraphModel:
    """In-worker trained graph and numeric state; never a judge-side import."""

    def __init__(self, recipe: ConstructionRecipe, prepared, settings: dict):
        self.recipe = recipe
        self.prepared = prepared
        self.settings = settings
        self.params = None
        self.mu = None
        self.sd = None

    def fit(self, train: domain.TrainingData, *, seed: int) -> dict:
        import jax

        from carbon.level4.train import TRAIN_KEY_FOLD

        from . import recipes, training

        if type(seed) is not int or seed < 0:
            raise RecipeRefused("battery_graph_seed_invalid")
        selected = recipes.train_subset(train, self.settings["train_fraction"], seed)
        if not selected.case_ids:
            raise RecipeRefused("battery_graph_train_empty")
        dtype = np.float64 if self.settings["precision"] == "float64" else np.float32
        x = selected.x.astype(dtype)
        y = _targets(selected).astype(dtype)
        self.mu = y.mean(axis=0)
        self.sd = y.std(axis=0) + dtype(1e-9)
        z = (y - self.mu) / self.sd
        group = [
            np.full(domain.GRID_POINTS, 1 / domain.GRID_POINTS),
            np.full(domain.GRID_POINTS, 1 / domain.GRID_POINTS),
            np.ones(1),
            np.full(len(domain.CAPACITY_CYCLES), 1 / len(domain.CAPACITY_CYCLES)),
        ]
        gw = np.concatenate(group).astype(dtype)
        sw = np.where(
            selected.important, self.settings["important_region_weight"], 1.0
        ).astype(dtype)
        n = len(selected.case_ids)
        order = np.argsort(
            np.argsort(selected.x[:, 0] + selected.x[:, 1], kind="stable")
        )
        if self.settings["curriculum"] == "high_rate_first":
            order = n - 1 - order
        prepared = self.prepared

        def init(key):
            return jax.random.fold_in(key, TRAIN_KEY_FOLD), prepared.init(key)

        def apply(params, features):
            return prepared.apply(list(params), features)[0]

        def trajectory(values):
            g = domain.GRID_POINTS
            return values[:, :g], values[:, g : 2 * g]

        with jax.enable_x64(dtype is np.float64):
            self.params = training.train(
                init=init,
                apply=apply,
                f=x,
                z=z,
                sw=sw,
                gw=gw,
                trajectory=trajectory,
                settings=self.settings,
                seed=seed,
                order=order,
            )
            prediction = np.asarray(prepared.predict(list(self.params), x)[0])
        leaves = [np.asarray(a) for a in jax.tree_util.tree_leaves(self.params)]
        if not all(np.isfinite(a).all() for a in leaves):
            raise RecipeRefused("battery_graph_nonfinite_state")
        blob = b"".join(a.tobytes() for a in leaves)
        return {
            "params_sha256": hashlib.sha256(blob).hexdigest(),
            "n_params": int(sum(a.size for a in leaves)),
            "train_loss": float(np.mean((prediction - z) ** 2)),
            "recipe_digest": self.recipe.digest,
        }

    def predict(self, x: np.ndarray, *, isolated: bool = False) -> dict:
        """`isolated` is the judge's per-case grading: one case per call, row 0."""
        import jax
        import jax.numpy as jnp

        if self.params is None:
            raise RecipeRefused("battery_graph_untrained")
        dtype = np.float64 if self.settings["precision"] == "float64" else np.float32
        x = np.asarray(x, dtype=dtype)
        if x.ndim != 2 or x.shape[1] != len(domain.INPUTS) or not np.isfinite(x).all():
            raise RecipeRefused("battery_graph_input_invalid")
        with jax.enable_x64(dtype is np.float64):
            normalized = np.asarray(
                self.prepared.predict(
                    list(self.params), jnp.asarray(x), isolated=isolated
                )[0]
            )
        y = normalized * self.sd + self.mu
        g = domain.GRID_POINTS
        return {
            "v": y[:, :g],
            "t": y[:, g : 2 * g],
            "eta": y[:, 2 * g],
            "q": y[:, 2 * g + 1 :],
        }


def build_validated_graph(
    recipe: ConstructionRecipe,
    raw_manifest: bytes,
    files: dict,
    *,
    max_bytes: int,
    train_cases: int,
    resolved_settings: dict | None = None,
) -> DirectGraphModel:
    """Verify graph bytes, G0/G3/G4 and exact interface before fit.

    Hostile graph compilation/training still belongs in an isolated worker;
    this function is intentionally not registered as a public campaign hook.
    """
    from carbon.level4 import allowlist as allowlist_module
    from carbon.level4 import intake, validate
    from carbon.level4.train import prepare

    # A trusted host may stage resolved settings into the isolated worker.
    # It must call training_settings(recipe) before doing so; no miner supplies
    # this argument through a public operation.
    settings = (
        training_settings(recipe) if resolved_settings is None else resolved_settings
    )
    if type(settings) is not dict or type(train_cases) is not int or train_cases <= 0:
        raise RecipeRefused("battery_graph_trusted_context_invalid")
    graph_workspace(recipe, raw_manifest, files, max_bytes=max_bytes)
    interface = graph_interface(settings)
    allowlist = allowlist_module.load()
    _, parsed = intake.intake(
        raw_manifest,
        files,
        allowlist=allowlist,
        challenge=CHALLENGE_ID,
        interface=interface.digest(),
        loss_override="none",
    )
    cases = int(train_cases * settings["train_fraction"])
    batch = min(settings["batch_size"], cases)
    verdict = validate.validate_submission(
        parsed, allowlist, interface=interface, batch=batch, loss_override="none"
    )
    if verdict["status"] != "admitted":
        raise intake.IntakeBlocked("graph caps unavailable")
    if "loss" in parsed:
        raise RecipeRefused("battery_graph_loss_unsupported")
    return DirectGraphModel(
        recipe, prepare(parsed, allowlist, verdict=verdict), settings
    )


def frozen_state_bytes(
    model: DirectGraphModel,
    raw_manifest: bytes,
    files: dict,
    *,
    max_bytes: int,
) -> bytes:
    """Bounded numeric/graph custody bytes, never a pickle or executable import.

    A separate inference-domain reader must revalidate the graph and numeric
    shapes before use. Creating these bytes alone grants no judge access.
    """
    import jax

    from carbon.level4 import staging

    if type(model) is not DirectGraphModel or model.params is None:
        raise RecipeRefused("battery_graph_untrained")
    if type(max_bytes) is not int or max_bytes <= 0:
        raise RecipeRefused("battery_graph_state_bound_invalid")
    actual = staging.check(raw_manifest, files)
    if actual != model.recipe.to_dict()["source"]["submission_digest"]:
        raise RecipeRefused("construction_recipe_graph_digest_mismatch")
    leaves = [np.asarray(a) for a in jax.tree_util.tree_leaves(model.params)]
    if not all(np.isfinite(a).all() and a.dtype.kind in "fiu" for a in leaves):
        raise RecipeRefused("battery_graph_nonfinite_state")
    arrays = {
        "mu": np.asarray(model.mu),
        "sd": np.asarray(model.sd),
        "manifest": np.frombuffer(raw_manifest, dtype=np.uint8),
    }
    names = sorted(files)
    for index, name in enumerate(names):
        arrays[f"document{index:04d}"] = np.frombuffer(files[name], dtype=np.uint8)
    for index, leaf in enumerate(leaves):
        arrays[f"parameter{index:04d}"] = leaf
    header = {
        "schema": "carbon.battery.direct-graph-state.v1",
        "recipe": model.recipe.to_dict(),
        "recipe_digest": model.recipe.digest,
        "submission_digest": actual,
        "documents": names,
        "parameter_count": len(leaves),
        "interface_digest": model.recipe.to_dict()["challenge"]["interface_digest"],
        "train_digest": model.recipe.to_dict()["challenge"]["train_digest"],
    }
    arrays["__header__"] = np.frombuffer(
        json.dumps(
            header, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode(),
        dtype=np.uint8,
    )
    out = io.BytesIO()
    np.savez(out, **arrays)
    body = out.getvalue()
    if len(body) > max_bytes:
        raise RecipeRefused("battery_graph_state_oversized")
    return body


def load_frozen_state(
    raw: bytes,
    *,
    recipe: ConstructionRecipe,
    max_bytes: int,
    train_cases: int,
    resolved_settings: dict | None = None,
) -> DirectGraphModel:
    """Revalidate numeric state and graph before inference in a separate worker.

    This reader takes inert NPZ bytes, never pickle or participant Python. The
    caller must still run it in the bounded inference domain; invoking it in a
    judge process is not an authority grant.
    """
    import jax

    from carbon.challenge_validator.strict_json import parse_strategy
    from carbon.level4 import intake, staging

    if (
        type(raw) is not bytes
        or type(max_bytes) is not int
        or not 0 < len(raw) <= max_bytes
        or type(recipe) is not ConstructionRecipe
    ):
        raise RecipeRefused("battery_graph_state_invalid")
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            names = archive.namelist()
            if (
                len(names) != len(set(names))
                or any(
                    entry.compress_type != zipfile.ZIP_STORED
                    for entry in archive.infolist()
                )
                or sum(entry.file_size for entry in archive.infolist()) > max_bytes
            ):
                raise RecipeRefused("battery_graph_state_archive_invalid")
        with np.load(io.BytesIO(raw), allow_pickle=False) as data:
            if "__header__" not in data or data["__header__"].dtype != np.uint8:
                raise RecipeRefused("battery_graph_state_header_invalid")
            header = parse_strategy(bytes(data["__header__"]), max_bytes=65536)
            if (
                type(header) is not dict
                or set(header)
                != {
                    "schema",
                    "recipe",
                    "recipe_digest",
                    "submission_digest",
                    "documents",
                    "parameter_count",
                    "interface_digest",
                    "train_digest",
                }
                or header["schema"] != "carbon.battery.direct-graph-state.v1"
                or header["recipe"] != recipe.to_dict()
                or header["recipe_digest"] != recipe.digest
                or header["submission_digest"]
                != recipe.to_dict()["source"]["submission_digest"]
                or header["interface_digest"]
                != recipe.to_dict()["challenge"]["interface_digest"]
                or header["train_digest"]
                != recipe.to_dict()["challenge"]["train_digest"]
                or type(header["documents"]) is not list
                or type(header["parameter_count"]) is not int
                or header["parameter_count"] < 0
            ):
                raise RecipeRefused("battery_graph_state_identity_invalid")
            expected = {
                "__header__",
                "manifest",
                "mu",
                "sd",
                *(f"document{index:04d}" for index in range(len(header["documents"]))),
                *(
                    f"parameter{index:04d}"
                    for index in range(header["parameter_count"])
                ),
            }
            if set(data.files) != expected or set(names) != {
                name + ".npy" for name in expected
            }:
                raise RecipeRefused("battery_graph_state_archive_invalid")
            if data["manifest"].dtype != np.uint8:
                raise RecipeRefused("battery_graph_state_document_invalid")
            manifest = bytes(data["manifest"])
            documents = {}
            for index, name in enumerate(header["documents"]):
                item = data[f"document{index:04d}"]
                if type(name) is not str or item.dtype != np.uint8 or name in documents:
                    raise RecipeRefused("battery_graph_state_document_invalid")
                documents[name] = bytes(item)
            if staging.check(manifest, documents) != header["submission_digest"]:
                raise RecipeRefused("battery_graph_state_document_invalid")
            model = build_validated_graph(
                recipe,
                manifest,
                documents,
                max_bytes=intake.BOUNDS["submission_bytes"],
                train_cases=train_cases,
                resolved_settings=resolved_settings,
            )
            dtype = (
                np.float64 if model.settings["precision"] == "float64" else np.float32
            )
            with jax.enable_x64(dtype is np.float64):
                template = model.prepared.init(jax.random.PRNGKey(0))
            leaves, structure = jax.tree_util.tree_flatten(template)
            if len(leaves) != header["parameter_count"]:
                raise RecipeRefused("battery_graph_state_parameter_invalid")
            parameters = []
            for index, template_leaf in enumerate(leaves):
                value = data[f"parameter{index:04d}"]
                if (
                    value.dtype.kind != "f"
                    or value.dtype != np.asarray(template_leaf).dtype
                    or value.shape != np.asarray(template_leaf).shape
                    or not np.isfinite(value).all()
                ):
                    raise RecipeRefused("battery_graph_state_parameter_invalid")
                parameters.append(value)
            width = 2 * domain.GRID_POINTS + 1 + len(domain.CAPACITY_CYCLES)
            mu, sd = data["mu"], data["sd"]
            if any(
                value.shape != (width,)
                or value.dtype != dtype
                or not np.isfinite(value).all()
                for value in (mu, sd)
            ) or not np.all(sd > 0):
                raise RecipeRefused("battery_graph_state_normalization_invalid")
            model.params = structure.unflatten(parameters)
            model.mu, model.sd = mu, sd
            return model
    except RecipeRefused:
        raise
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile):
        raise RecipeRefused("battery_graph_state_invalid") from None
