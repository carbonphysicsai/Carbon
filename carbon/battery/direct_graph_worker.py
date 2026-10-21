"""Fixed-program isolated public reconstruction for a direct Battery graph.

This stages only pinned TRAIN, an exact graph submission, the direct recipe,
and Carbon's own graph/training modules. No practice labels, hidden evaluation
material, wallet, judge module or participant Python source enters the worker.
This registered callback serves public DEVELOPMENT graph practice only;
official receiver inference and bundle execution remain unserved.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

from carbon.development_session.construction_recipe import (
    ConstructionRecipe,
    RecipeRefused,
    bind_recipe,
    graph_workspace,
)
from carbon.development_session.profile import canonical, digest

from . import challenge, construction_kit, direct_graph
from .public_model_retention import MAX_STATE_BYTES

PROVENANCE = "BATTERY_DIRECT_GRAPH_PUBLIC_RECONSTRUCTION"
STAGED_MODULES = (
    "carbon.challenge_validator.strict_json",
    "carbon.level4.graph",
    "carbon.level4.params",
    "carbon.level4.allowlist",
    "carbon.level4.named",
    "carbon.level4.interpret",
    "carbon.level4.initializers",
    "carbon.level4.submission",
    "carbon.level4.loss",
    "carbon.level4.validate",
    "carbon.level4.train",
    "carbon.level4.intake",
    "carbon.level4._parse_worker",
    "carbon.level4.staging",
    "carbon.development_session.construction_recipe",
)
BATTERY_MODULES = {
    "battery-domain.py": "domain.py",
    "battery-recipes.py": "recipes.py",
    "battery-training.py": "training.py",
    "battery-direct-graph.py": "direct_graph.py",
}

PROGRAM = r'''"""Fixed Carbon direct-graph public TRAIN reconstruction."""
import gzip, hashlib, json, shutil, sys
from pathlib import Path

import numpy as np

work = Path.cwd()
out = work.parent / "output"
for package in (
    "carbon", "carbon/challenge_validator", "carbon/level4",
    "carbon/development_session",
):
    folder = work / package
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "__init__.py").write_text("")
for name in __STAGED_MODULES__:
    destination = work.joinpath(*name.split(".")).with_suffix(".py")
    shutil.copyfile(work / (name + ".py"), destination)
shutil.copyfile(work / "allowlist_v1.json", work / "carbon/level4/allowlist_v1.json")
shutil.copyfile(work / "allowlist_v6.json", work / "carbon/level4/allowlist_v6.json")
lab = work / "carbon_battery_lab"
lab.mkdir()
(lab / "__init__.py").write_text("")
for staged, module in __BATTERY_MODULES__:
    shutil.copyfile(work / staged, lab / module)
sys.path.insert(0, str(work))

from carbon.development_session.construction_recipe import ConstructionRecipe, bind_recipe
from carbon.level4 import intake, staging
from carbon_battery_lab import direct_graph, recipes
from carbon_battery_lab.domain import INPUTS, TrainingData

control = json.loads((work / "control.json").read_bytes())
recipe = ConstructionRecipe.from_bytes((work / "recipe.json").read_bytes())
if recipe.digest != control["recipe_digest"]:
    raise ValueError("staged direct recipe digest differs")
bind_recipe(
    recipe.to_dict(), challenge_id=control["kit"]["id"],
    challenge_version=control["kit"]["version"],
    train_digest=control["kit"]["train_digest"],
    interface_digest=control["kit"]["interface_digest"],
    construction_limits_digest=control["kit"]["construction_limits_digest"],
)
settings = json.loads((work / "settings.json").read_bytes())
if control["settings_digest"] != "sha256:" + hashlib.sha256(
    json.dumps(settings, sort_keys=True, separators=(",", ":")).encode()
).hexdigest():
    raise ValueError("staged training settings differ")
raw_train = (work / "train-v1.jsonl.gz").read_bytes()
if "sha256:" + hashlib.sha256(raw_train).hexdigest() != control["kit"]["train_digest"]:
    raise ValueError("pinned TRAIN bytes differ")
records = [json.loads(line) for line in gzip.decompress(raw_train).splitlines() if line.strip()]
if len(records) != control["train_cases"] or any(
    row.get("role") != "train" or row.get("status") != "OK" for row in records
):
    raise ValueError("TRAIN role/count differs")
train = TrainingData.from_records(records)
staged = {
    path.name: path.read_bytes() for path in work.iterdir()
    if path.name == staging.WORKSPACE_MANIFEST
    or path.name.startswith(staging.WORKSPACE_PREFIX)
}
raw_manifest, files = staging.from_workspace(
    staged, recipe.to_dict()["source"]["submission_digest"]
)
model = direct_graph.build_validated_graph(
    recipe, raw_manifest, files,
    max_bytes=intake.BOUNDS["submission_bytes"],
    train_cases=len(train.case_ids), resolved_settings=settings,
)
fit = model.fit(train, seed=control["seed"])
state = direct_graph.frozen_state_bytes(
    model, raw_manifest, files, max_bytes=control["max_state_bytes"]
)
(out / "state.npz").write_bytes(state)
inputs = json.loads((work / "test-inputs.json").read_bytes())["cases"]
x = np.asarray([[case["inputs"][name] for name in INPUTS] for case in inputs], float)
predicted = recipes.to_predictions(
    model.predict(x), [case["case_id"] for case in inputs]
)
(out / "predictions.json").write_text(json.dumps(predicted, sort_keys=True))
(out / "fit.json").write_text(json.dumps({
    **fit,
    "state_sha256": "sha256:" + hashlib.sha256(state).hexdigest(),
    "graph_digest": recipe.to_dict()["source"]["submission_digest"],
    "interface_digest": control["kit"]["interface_digest"],
    "train_digest": control["kit"]["train_digest"],
}, sort_keys=True, allow_nan=False))
'''.replace("__STAGED_MODULES__", repr(STAGED_MODULES)).replace(
    "__BATTERY_MODULES__", repr(tuple(BATTERY_MODULES.items()))
)


def checked_test_inputs(test_inputs: dict) -> bytes:
    """Bounded input-only cases for build and separate inference workers."""
    from carbon.level4 import intake

    if (
        type(test_inputs) is not dict
        or set(test_inputs) != {"cases"}
        or type(test_inputs["cases"]) is not list
        or not test_inputs["cases"]
    ):
        raise RecipeRefused("battery_direct_test_inputs_invalid")
    seen = set()
    for case in test_inputs["cases"]:
        if type(case) is not dict or set(case) != {"case_id", "inputs"}:
            raise RecipeRefused("battery_direct_test_inputs_invalid")
        case_id, values = case["case_id"], case["inputs"]
        if type(case_id) is not str or not case_id or case_id in seen:
            raise RecipeRefused("battery_direct_test_inputs_invalid")
        seen.add(case_id)
        if type(values) is not dict or set(values) != set(challenge.INPUTS):
            raise RecipeRefused("battery_direct_test_inputs_invalid")
        for name in challenge.INPUTS:
            value = values[name]
            low, high = challenge.INPUT_BOUNDS[name]
            if (
                type(value) not in (int, float)
                or not math.isfinite(value)
                or not low <= value <= high
            ):
                raise RecipeRefused("battery_direct_test_inputs_invalid")
    raw = canonical(test_inputs)
    if len(raw) > intake.BOUNDS["submission_bytes"]:
        raise RecipeRefused("battery_direct_test_inputs_oversized")
    return raw


def staged_files(
    root: Path,
    recipe: ConstructionRecipe,
    source_envelope: bytes,
    *,
    seed: int,
    test_inputs: dict,
) -> dict[str, bytes]:
    """Host-verified public bytes for one fixed-program reconstruction."""
    from carbon.level4 import intake, staging

    if type(recipe) is not ConstructionRecipe or type(seed) is not int or seed < 0:
        raise RecipeRefused("battery_direct_request_invalid")
    kit = construction_kit.construction_kit()
    bind_recipe(
        recipe.to_dict(),
        challenge_id=kit["id"],
        challenge_version=kit["version"],
        train_digest=kit["train_digest"],
        interface_digest=kit["interface_digest"],
        construction_limits_digest=kit["construction_limits_digest"],
    )
    if recipe.to_dict()["source"]["kind"] != "graph":
        raise RecipeRefused("battery_direct_source_unsupported")
    settings = direct_graph.training_settings(recipe)
    if (
        type(source_envelope) is not bytes
        or len(source_envelope) > intake.BOUNDS["submission_bytes"] * 2
    ):
        raise RecipeRefused("battery_direct_envelope_invalid")
    try:
        envelope = json.loads(source_envelope)
        declared, raw_manifest, files = staging.from_envelope(envelope)
    except (TypeError, ValueError, UnicodeError, KeyError):
        raise RecipeRefused("battery_direct_envelope_invalid") from None
    if declared != recipe.to_dict()["source"]["submission_digest"]:
        raise RecipeRefused("construction_recipe_graph_digest_mismatch")
    workspace = graph_workspace(
        recipe, raw_manifest, files, max_bytes=intake.BOUNDS["submission_bytes"]
    )
    # The host checks G0/G3/G4 before reserving the carrier. The isolated
    # worker repeats every check against the staged bytes.
    direct_graph.build_validated_graph(
        recipe,
        raw_manifest,
        files,
        max_bytes=intake.BOUNDS["submission_bytes"],
        train_cases=challenge.TRAIN_V1_CASES,
        resolved_settings=settings,
    )
    raw_train = challenge._pinned(
        Path(root) / challenge.TRAIN_V1_PATH, challenge.TRAIN_V1_SHA256, "train_v1"
    )
    files_out = {
        name
        + ".py": (
            Path(__file__).resolve().parents[2] / (name.replace(".", "/") + ".py")
        ).read_bytes()
        for name in STAGED_MODULES
    }
    files_out.update(
        {
            name: Path(__file__).with_name(module).read_bytes()
            for name, module in BATTERY_MODULES.items()
        }
    )
    files_out["allowlist_v1.json"] = (
        Path(__file__).resolve().parents[2] / "carbon" / "level4" / "allowlist_v1.json"
    ).read_bytes()
    from carbon.level4.allowlist import served_bytes

    # The served allowlist the staged direct_graph validates against.
    files_out["allowlist_v6.json"] = served_bytes()
    settings_raw = canonical(settings)
    test_inputs_raw = checked_test_inputs(test_inputs)
    files_out.update(
        {
            "recipe.json": recipe.canonical_bytes,
            "settings.json": settings_raw,
            "train-v1.jsonl.gz": raw_train,
            "test-inputs.json": test_inputs_raw,
            "control.json": canonical(
                {
                    "recipe_digest": recipe.digest,
                    "settings_digest": digest(settings_raw),
                    "kit": kit,
                    "seed": seed,
                    "train_cases": challenge.TRAIN_V1_CASES,
                    "max_state_bytes": MAX_STATE_BYTES,
                }
            ),
            **workspace,
        }
    )
    return files_out


@dataclass(frozen=True)
class DirectGraphResult:
    recipe_digest: str
    graph_digest: str
    interface_digest: str
    train_digest: str
    state_digest: str
    state_path: Path
    predictions_digest: str
    predictions: dict
    fit: dict
    worker_operation: str


def reconstruct_public(
    ledger,
    *,
    owner: str,
    identity: str,
    image,
    root: Path,
    recipe: ConstructionRecipe,
    source_envelope: bytes,
    seed: int,
    test_inputs: dict,
    runner=None,
) -> DirectGraphResult:
    """Execute the actual graph in Carbon's bounded isolated research carrier.

    The caller owns ledger reservation, trusted image and seed. This is public
    DEVELOPMENT only; validator authority and judge transfer are separate.
    """
    from carbon.development_session.research_carrier import PRECHARGED_TRIAL, _run

    files = staged_files(
        root, recipe, source_envelope, seed=seed, test_inputs=test_inputs
    )
    source = recipe.to_dict()["source"]
    kit = construction_kit.construction_kit()

    def read_outputs(snapshot: Path) -> tuple[bytes, bytes, dict, dict]:
        expected = {"state.npz", "predictions.json", "fit.json"}
        if {path.name for path in snapshot.iterdir()} != expected:
            raise ValueError("direct reconstruction output set differs")

        def bounded(name: str, ceiling: int) -> bytes:
            path = snapshot / name
            if (
                path.is_symlink()
                or not path.is_file()
                or not 0 < path.stat().st_size <= ceiling
            ):
                raise ValueError("bounded direct reconstruction output required")
            return path.read_bytes()

        state = bounded("state.npz", MAX_STATE_BYTES)
        predictions_raw = bounded("predictions.json", 16 * 1024 * 1024)
        fit = json.loads(bounded("fit.json", 65536))
        predictions = json.loads(predictions_raw)
        if (
            type(fit) is not dict
            or type(predictions) is not dict
            or set(predictions) != {case["case_id"] for case in test_inputs["cases"]}
            or fit.get("recipe_digest") != recipe.digest
            or fit.get("graph_digest") != source["submission_digest"]
            or fit.get("interface_digest") != kit["interface_digest"]
            or fit.get("train_digest") != kit["train_digest"]
            or fit.get("state_sha256") != digest(state)
        ):
            raise ValueError("direct reconstruction result identity differs")
        return state, predictions_raw, fit, predictions

    worker = (runner or _run)(
        ledger,
        owner=owner,
        identity=identity,
        source=PROGRAM,
        files=files,
        image=image,
        seconds=600,
        provenance=PROVENANCE,
        extra_resources=(
            {} if PRECHARGED_TRIAL.get() is not None else {"research_trials": 1}
        ),
        output_validator=read_outputs,
    )
    snapshot = ledger.root / worker["operation"] / "snapshot"
    state, predictions_raw, fit, predictions = read_outputs(snapshot)
    if any(
        digest(body) != worker["files"].get(name)
        for name, body in (
            ("state.npz", state),
            ("predictions.json", predictions_raw),
            ("fit.json", (snapshot / "fit.json").read_bytes()),
        )
    ):
        raise ValueError("direct reconstruction output digest differs")
    return DirectGraphResult(
        recipe.digest,
        source["submission_digest"],
        kit["interface_digest"],
        kit["train_digest"],
        digest(state),
        snapshot / "state.npz",
        digest(predictions_raw),
        predictions,
        fit,
        worker["operation"],
    )
