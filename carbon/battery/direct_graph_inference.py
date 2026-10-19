"""Separate fixed-program inference over a rebuilt Battery graph state.

Only the numeric state, exact recipe, Carbon graph interpreter and input-only
cases enter this C-03 worker. TRAIN data and participant construction source
do not. Public DEVELOPMENT practice uses this after an independent build;
official evaluation still requires its own private receiver composition.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from carbon.challenge_validator.strict_json import MalformedStrategy, parse_strategy
from carbon.development_session.construction_recipe import (
    ConstructionRecipe,
    RecipeRefused,
    bind_recipe,
)
from carbon.development_session.profile import canonical, digest

from . import challenge, construction_kit, direct_graph, direct_graph_worker
from .public_model_retention import MAX_STATE_BYTES

PROVENANCE = "BATTERY_DIRECT_GRAPH_PUBLIC_INFERENCE"

PROGRAM = r'''"""Fixed Carbon inference from inert graph and numeric state."""
import hashlib, json, shutil, sys
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
lab = work / "carbon_battery_lab"
lab.mkdir()
(lab / "__init__.py").write_text("")
for staged, module in __BATTERY_MODULES__:
    shutil.copyfile(work / staged, lab / module)
sys.path.insert(0, str(work))

from carbon.development_session.construction_recipe import ConstructionRecipe, bind_recipe
from carbon_battery_lab import direct_graph, recipes
from carbon_battery_lab.domain import INPUTS

control = json.loads((work / "control.json").read_bytes())
recipe = ConstructionRecipe.from_bytes((work / "recipe.json").read_bytes())
if recipe.digest != control["recipe_digest"]:
    raise ValueError("inference recipe digest differs")
bind_recipe(
    recipe.to_dict(), challenge_id=control["kit"]["id"],
    challenge_version=control["kit"]["version"],
    train_digest=control["kit"]["train_digest"],
    interface_digest=control["kit"]["interface_digest"],
    construction_limits_digest=control["kit"]["construction_limits_digest"],
)
settings_raw = (work / "settings.json").read_bytes()
if "sha256:" + hashlib.sha256(settings_raw).hexdigest() != control["settings_digest"]:
    raise ValueError("inference settings digest differs")
settings = json.loads(settings_raw)
state = (work / "state.npz").read_bytes()
if "sha256:" + hashlib.sha256(state).hexdigest() != control["state_digest"]:
    raise ValueError("inference state digest differs")
model = direct_graph.load_frozen_state(
    state, recipe=recipe, max_bytes=control["max_state_bytes"],
    train_cases=control["train_cases"], resolved_settings=settings,
)
inputs_raw = (work / "test-inputs.json").read_bytes()
if "sha256:" + hashlib.sha256(inputs_raw).hexdigest() != control["inputs_digest"]:
    raise ValueError("inference input digest differs")
cases = json.loads(inputs_raw)["cases"]
x = np.asarray([[case["inputs"][name] for name in INPUTS] for case in cases], float)
predictions = recipes.to_predictions(
    model.predict(x, isolated=True), [case["case_id"] for case in cases]
)
body = json.dumps(predictions, sort_keys=True, allow_nan=False).encode()
(out / "predictions.json").write_bytes(body)
(out / "receipt.json").write_text(json.dumps({
    "schema": "carbon.battery.direct-graph-inference.v1",
    "recipe_digest": recipe.digest,
    "state_digest": control["state_digest"],
    "inputs_digest": control["inputs_digest"],
    "predictions_digest": "sha256:" + hashlib.sha256(body).hexdigest(),
}, sort_keys=True, allow_nan=False))
'''.replace("__STAGED_MODULES__", repr(direct_graph_worker.STAGED_MODULES)).replace(
    "__BATTERY_MODULES__", repr(tuple(direct_graph_worker.BATTERY_MODULES.items()))
)


def staged_files(
    recipe: ConstructionRecipe, state: bytes, test_inputs: dict
) -> dict[str, bytes]:
    """Trusted host stage: exact identities, no TRAIN or construction source."""
    if (
        type(recipe) is not ConstructionRecipe
        or type(state) is not bytes
        or not 0 < len(state) <= MAX_STATE_BYTES
    ):
        raise RecipeRefused("battery_direct_inference_state_invalid")
    kit = construction_kit.construction_kit()
    bind_recipe(
        recipe.to_dict(),
        challenge_id=kit["id"],
        challenge_version=kit["version"],
        train_digest=kit["train_digest"],
        interface_digest=kit["interface_digest"],
        construction_limits_digest=kit["construction_limits_digest"],
    )
    settings = direct_graph.training_settings(recipe)
    settings_raw = canonical(settings)
    inputs_raw = direct_graph_worker.checked_test_inputs(test_inputs)
    root = Path(__file__).resolve().parents[2]
    files = {
        name + ".py": (root / (name.replace(".", "/") + ".py")).read_bytes()
        for name in direct_graph_worker.STAGED_MODULES
    }
    files.update(
        {
            name: Path(__file__).with_name(module).read_bytes()
            for name, module in direct_graph_worker.BATTERY_MODULES.items()
        }
    )
    files["allowlist_v1.json"] = (root / "carbon/level4/allowlist_v1.json").read_bytes()
    files.update(
        {
            "state.npz": state,
            "recipe.json": recipe.canonical_bytes,
            "settings.json": settings_raw,
            "test-inputs.json": inputs_raw,
            "control.json": canonical(
                {
                    "recipe_digest": recipe.digest,
                    "state_digest": digest(state),
                    "settings_digest": digest(settings_raw),
                    "inputs_digest": digest(inputs_raw),
                    "kit": kit,
                    "max_state_bytes": MAX_STATE_BYTES,
                    "train_cases": challenge.TRAIN_V1_CASES,
                }
            ),
        }
    )
    if "train-v1.jsonl.gz" in files or any(
        name.startswith("level4-doc-") for name in files
    ):
        raise ValueError("inference stage contains construction material")
    return files


@dataclass(frozen=True)
class DirectInferenceResult:
    recipe_digest: str
    state_digest: str
    predictions_digest: str
    predictions: dict
    worker_operation: str


def infer_public(
    ledger,
    *,
    owner: str,
    identity: str,
    image,
    recipe: ConstructionRecipe,
    build: direct_graph_worker.DirectGraphResult,
    test_inputs: dict,
    runner=None,
) -> DirectInferenceResult:
    """Reopen the build's numeric state in a fresh bounded inference worker."""
    from carbon.development_session.research_carrier import _run

    expected = ledger.root / build.worker_operation / "snapshot" / "state.npz"
    if (
        build.recipe_digest != recipe.digest
        or build.state_path != expected
        or expected.is_symlink()
        or not expected.is_file()
        or not 0 < expected.stat().st_size <= MAX_STATE_BYTES
    ):
        raise ValueError("direct inference build custody differs")
    state = expected.read_bytes()
    if digest(state) != build.state_digest:
        raise ValueError("direct inference build state differs")
    files = staged_files(recipe, state, test_inputs)
    inputs_digest = digest(files["test-inputs.json"])

    def read_outputs(snapshot: Path):
        if {path.name for path in snapshot.iterdir()} != {
            "predictions.json",
            "receipt.json",
        }:
            raise ValueError("direct inference output set differs")
        for name, ceiling in (
            ("predictions.json", 16 * 1024 * 1024),
            ("receipt.json", 65536),
        ):
            path = snapshot / name
            if (
                path.is_symlink()
                or not path.is_file()
                or not 0 < path.stat().st_size <= ceiling
            ):
                raise ValueError("bounded direct inference output required")
        try:
            predictions_raw = (snapshot / "predictions.json").read_bytes()
            predictions = parse_strategy(predictions_raw, max_bytes=16 * 1024 * 1024)
            receipt = parse_strategy(
                (snapshot / "receipt.json").read_bytes(), max_bytes=65536
            )
        except MalformedStrategy:
            raise ValueError("direct inference output malformed") from None
        if (
            type(predictions) is not dict
            or type(receipt) is not dict
            or set(predictions) != {case["case_id"] for case in test_inputs["cases"]}
            or receipt
            != {
                "schema": "carbon.battery.direct-graph-inference.v1",
                "recipe_digest": recipe.digest,
                "state_digest": build.state_digest,
                "inputs_digest": inputs_digest,
                "predictions_digest": digest(predictions_raw),
            }
        ):
            raise ValueError("direct inference output identity differs")
        return predictions_raw, predictions

    worker = (runner or _run)(
        ledger,
        owner=owner,
        identity=identity,
        image=image,
        source=PROGRAM,
        files=files,
        seconds=600,
        provenance=PROVENANCE,
        extra_resources={},
        output_validator=read_outputs,
    )
    snapshot = ledger.root / worker["operation"] / "snapshot"
    raw, predictions = read_outputs(snapshot)
    if digest(raw) != worker["files"].get("predictions.json") or digest(
        (snapshot / "receipt.json").read_bytes()
    ) != worker["files"].get("receipt.json"):
        raise ValueError("direct inference carrier receipt differs")
    return DirectInferenceResult(
        recipe.digest, build.state_digest, digest(raw), predictions, worker["operation"]
    )
