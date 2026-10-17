"""Fixed C-03 graph construction under the same direct task lifecycle.

Only bounded inert graph documents, fixed Challenge TRAIN, and Carbon-owned
training code enter the build worker. Separate inference receives the frozen
graph and numeric state, never the submitted manifest or TRAIN archive.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

import numpy as np

from carbon.challenge_validator.strict_json import MalformedStrategy, parse_strategy
from carbon.level4 import intake, staging
from carbon.reconstruction.worker.model import WorkerImageIdentity

from .bundle_construction_worker import (
    BundleBuildResult,
    DirectReconstructionResult,
    _checked_binding,
    _digest,
    _infer_state,
    _private_controls_digest,
    _stage_modules,
    _trusted_allowlist,
    direct_child_identity,
    verify_direct_resource_policy,
)
from .bundle_graph_state import MAX_BYTES as MAX_STATE_BYTES
from .bundle_graph_state import load as load_state
from .construction_recipe import ConstructionRecipe, RecipeRefused, graph_workspace
from .profile import canonical
from .research_carrier import PRECHARGED_TRIAL, _run

BUILD_PROVENANCE = "DIRECT_GRAPH_PUBLIC_RECONSTRUCTION"
INFERENCE_PROVENANCE = "DIRECT_GRAPH_PUBLIC_INFERENCE"
OUTCOME_SCHEMA = "carbon.development.graph-build-outcome.v1"


class GraphConstructionDecision(Exception):
    """A settled fixed-worker validation outcome, never stderr classification."""

    def __init__(self, state: str, reason_code: str, detail_code: str):
        if (
            state not in ("REFUSED", "UNRESOLVED")
            or reason_code
            not in ("graph_submission_invalid", "carbon_graph_adapter_unavailable")
            or type(detail_code) is not str
        ):
            raise ValueError("closed graph construction decision required")
        super().__init__(reason_code)
        self.state = state
        self.reason_code = reason_code
        self.detail_code = detail_code


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
    "carbon.development_session.bundle_graph_state",
    "carbon.development_session.synthetic_graph_adapter",
)

BUILD_PROGRAM = r'''"""Fixed synthetic direct-graph construction; no judge."""
import hashlib, json, shutil, sys
from pathlib import Path
import numpy as np

work = Path.cwd()
out = work.parent / "output"
for package in ("carbon", "carbon/challenge_validator", "carbon/level4",
                "carbon/development_session"):
    folder = work / package
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "__init__.py").write_text("")
for name in __STAGED_MODULES__:
    destination = work.joinpath(*name.split(".")).with_suffix(".py")
    shutil.copyfile(work / (name + ".py"), destination)
sys.path.insert(0, str(work))

from carbon.development_session.bundle_graph_state import load
from carbon.development_session.construction_recipe import ConstructionRecipe, RecipeRefused, bind_recipe
from carbon.development_session.synthetic_graph_adapter import (
    build_validated_graph, checked_train,
)
from carbon.level4 import intake, staging
from carbon.level4.allowlist import Allowlist
from carbon.level4.graph import GraphRefused

digest = lambda body: "sha256:" + hashlib.sha256(body).hexdigest()
control = json.loads((work / "control.json").read_bytes())
recipe = ConstructionRecipe.from_bytes((work / "recipe.json").read_bytes())
if recipe.digest != control["recipe_digest"]:
    raise ValueError("graph build recipe differs")
bind_recipe(recipe.to_dict(), **control["binding"])
source = recipe.to_dict()["source"]
if source["kind"] != "graph" or source["submission_digest"] != control["submission_digest"]:
    raise ValueError("graph build source differs")
raw_envelope = (work / "source-envelope.json").read_bytes()
if digest(raw_envelope) != control["envelope_digest"]:
    raise ValueError("graph source envelope differs")
declared, raw_manifest, files = staging.from_envelope(json.loads(raw_envelope))
if declared != source["submission_digest"]:
    raise ValueError("graph source digest differs")
raw_train = (work / "train.npz").read_bytes()
inputs, targets = checked_train(raw_train, control["binding"]["train_digest"])
allowed_raw = (work / "allowlist.json").read_bytes()
allowed = Allowlist(allowed_raw)
if allowed.digest != control["allowlist_digest"]:
    raise ValueError("graph allowlist differs")
def decline(state, detail):
    reason = ("graph_submission_invalid" if state == "REFUSED"
              else "carbon_graph_adapter_unavailable")
    (out / "outcome.json").write_text(json.dumps({
        "schema": "carbon.development.graph-build-outcome.v1",
        "state": state,
        "reason_code": reason,
        "detail_code": detail,
    }, sort_keys=True, allow_nan=False))

try:
    model = build_validated_graph(
        recipe, raw_manifest, files, allowlist_bytes=allowed_raw,
        train_cases=len(inputs),
    )
except GraphRefused as error:
    state = ("UNRESOLVED" if error.code in {
        "op_not_allowlisted", "op_not_supported_v0",
    } else "REFUSED")
    decline(state, error.code)
    sys.exit(0)
except RecipeRefused as error:
    state = ("UNRESOLVED" if error.code in {
        "synthetic_graph_train_use_unavailable",
        "synthetic_graph_training_adapter_unavailable",
        "synthetic_graph_source_or_output_invalid",
    } else "REFUSED")
    decline(state, error.code)
    sys.exit(0)
except intake.IntakeBlocked:
    decline("UNRESOLVED", "graph_validation_not_ready")
    sys.exit(0)
try:
    fit = model.fit(inputs, targets, seed=control["seed"])
except RecipeRefused as error:
    if error.code != "synthetic_graph_nonfinite_state":
        raise
    decline("REFUSED", error.code)
    sys.exit(0)
state = model.frozen_state()
load(state, recipe, allowed)
(out / "state.npz").write_bytes(state)
receipt = {
    "schema": "carbon.development.graph-build.v1",
    "recipe_digest": recipe.digest,
    "submission_digest": source["submission_digest"],
    "train_digest": control["binding"]["train_digest"],
    "state_digest": digest(state),
    "allowlist_digest": allowed.digest,
    "framework": "jax",
    "fit": fit,
}
(out / "receipt.json").write_text(json.dumps(receipt, sort_keys=True, allow_nan=False))
'''.replace(
    "__STAGED_MODULES__", repr(STAGED_MODULES)
)


def _checked_envelope(recipe: ConstructionRecipe, source_envelope: bytes) -> bytes:
    if (
        type(recipe) is not ConstructionRecipe
        or recipe.to_dict()["source"]["kind"] != "graph"
        or type(source_envelope) is not bytes
        or not 0 < len(source_envelope) <= 2 * intake.BOUNDS["submission_bytes"]
    ):
        raise RecipeRefused("direct_graph_source_invalid")
    try:
        envelope = json.loads(source_envelope)
        declared, raw_manifest, files = staging.from_envelope(envelope)
    except (TypeError, ValueError, KeyError, UnicodeError):
        raise RecipeRefused("direct_graph_source_invalid") from None
    if declared != recipe.to_dict()["source"]["submission_digest"]:
        raise RecipeRefused("construction_recipe_graph_digest_mismatch")
    graph_workspace(
        recipe, raw_manifest, files, max_bytes=intake.BOUNDS["submission_bytes"]
    )
    canonical_envelope = canonical(staging.envelope(raw_manifest, files))
    if source_envelope != canonical_envelope:
        raise RecipeRefused("direct_graph_source_noncanonical")
    return source_envelope


def reconstruct_public_graph(
    ledger,
    *,
    owner: str,
    identity: str,
    image: WorkerImageIdentity,
    recipe: ConstructionRecipe,
    challenge_binding: dict,
    limits_document: dict,
    source_envelope: bytes,
    train: bytes,
    allowlist_bytes: bytes,
    seed: int,
    seconds: int,
    runner=None,
) -> BundleBuildResult:
    """Rebuild the actual graph in a fresh isolated C-03 construction child."""
    if (
        type(image) is not WorkerImageIdentity
        or type(seed) is not int
        or seed < 0
        or type(train) is not bytes
        or not 0 < len(train) <= MAX_STATE_BYTES
        or type(seconds) is not int
        or seconds < 1
    ):
        raise RecipeRefused("direct_graph_build_binding_invalid")
    binding = _checked_binding(recipe, challenge_binding)
    verify_direct_resource_policy(binding, limits_document)
    if _digest(train) != binding["train_digest"]:
        raise RecipeRefused("direct_graph_train_binding_invalid")
    _checked_envelope(recipe, source_envelope)
    allowed = _trusted_allowlist(allowlist_bytes)
    files = _stage_modules()
    root = Path(__file__).resolve().parents[2]
    files.update(
        {
            name + ".py": (root / (name.replace(".", "/") + ".py")).read_bytes()
            for name in STAGED_MODULES
        }
    )
    files.update(
        {
            "recipe.json": recipe.canonical_bytes,
            "source-envelope.json": source_envelope,
            "train.npz": train,
            "allowlist.json": allowlist_bytes,
            "control.json": canonical(
                {
                    "recipe_digest": recipe.digest,
                    "binding": binding,
                    "submission_digest": recipe.to_dict()["source"][
                        "submission_digest"
                    ],
                    "envelope_digest": _digest(source_envelope),
                    "allowlist_digest": allowed.digest,
                    "seed": seed,
                }
            ),
        }
    )

    def checked(snapshot: Path):
        names = {path.name for path in snapshot.iterdir()}
        if names == {"outcome.json"}:
            path = snapshot / "outcome.json"
            if (
                path.is_symlink()
                or not path.is_file()
                or not 0 < path.stat().st_size <= 4096
            ):
                raise ValueError("bounded direct graph outcome required")
            try:
                outcome = parse_strategy(path.read_bytes(), max_bytes=4096)
            except MalformedStrategy:
                raise ValueError("direct graph outcome malformed") from None
            if (
                type(outcome) is not dict
                or set(outcome) != {"schema", "state", "reason_code", "detail_code"}
                or outcome["schema"] != OUTCOME_SCHEMA
                or outcome["state"] not in ("REFUSED", "UNRESOLVED")
                or outcome["reason_code"]
                != (
                    "graph_submission_invalid"
                    if outcome["state"] == "REFUSED"
                    else "carbon_graph_adapter_unavailable"
                )
                or type(outcome["detail_code"]) is not str
                or not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", outcome["detail_code"])
            ):
                raise ValueError("direct graph outcome identity differs")
            return outcome
        if names != {"state.npz", "receipt.json"}:
            raise ValueError("direct graph build output set differs")
        for name, ceiling in (("state.npz", MAX_STATE_BYTES), ("receipt.json", 65536)):
            path = snapshot / name
            if (
                path.is_symlink()
                or not path.is_file()
                or not 0 < path.stat().st_size <= ceiling
            ):
                raise ValueError("bounded direct graph build output required")
        state = (snapshot / "state.npz").read_bytes()
        try:
            receipt = parse_strategy(
                (snapshot / "receipt.json").read_bytes(), max_bytes=65536
            )
        except MalformedStrategy:
            raise ValueError("direct graph build receipt malformed") from None
        expected = {
            "schema": "carbon.development.graph-build.v1",
            "recipe_digest": recipe.digest,
            "submission_digest": recipe.to_dict()["source"]["submission_digest"],
            "train_digest": binding["train_digest"],
            "state_digest": _digest(state),
            "allowlist_digest": allowed.digest,
            "framework": "jax",
            "fit": receipt.get("fit"),
        }
        if receipt != expected or type(receipt["fit"]) is not dict:
            raise ValueError("direct graph build receipt identity differs")
        load_state(state, recipe, allowed)
        return state, receipt

    worker = (runner or _run)(
        ledger,
        owner=owner,
        identity=identity,
        source=BUILD_PROGRAM,
        files=files,
        image=image,
        seconds=seconds,
        provenance=BUILD_PROVENANCE,
        extra_resources=(
            {} if PRECHARGED_TRIAL.get() is not None else {"research_trials": 1}
        ),
        output_validator=checked,
    )
    snapshot = ledger.root / worker["operation"] / "snapshot"
    result = checked(snapshot)
    if type(result) is dict:
        if _digest((snapshot / "outcome.json").read_bytes()) != worker["files"].get(
            "outcome.json"
        ):
            raise ValueError("direct graph outcome custody differs")
        raise GraphConstructionDecision(
            result["state"], result["reason_code"], result["detail_code"]
        )
    state, receipt = result
    if any(
        _digest((snapshot / name).read_bytes()) != worker["files"].get(name)
        for name in ("state.npz", "receipt.json")
    ):
        raise ValueError("direct graph build output custody differs")
    return BundleBuildResult(
        recipe.digest,
        _digest(state),
        snapshot / "state.npz",
        worker["operation"],
        receipt,
    )


def reconstruct_and_infer_graph_public(
    ledger,
    *,
    owner: str,
    identity: str,
    image: WorkerImageIdentity,
    recipe: ConstructionRecipe,
    challenge_binding: dict,
    limits_document: dict,
    source_envelope: bytes,
    train: bytes,
    inputs: np.ndarray,
    expected_output_shape: tuple[int, ...],
    allowlist_bytes: bytes,
    seed: int,
    measure_query: bool = False,
    runner=None,
) -> DirectReconstructionResult:
    """Use the normal two-child budget and source-free inference boundary."""
    binding = _checked_binding(recipe, challenge_binding)
    policy_digest = verify_direct_resource_policy(binding, limits_document)
    policy = limits_document["reconstruction_resource_policy"]
    started = time.monotonic()
    deadline = started + policy["total_reconstruction_wall_seconds_max"]
    build_identity = direct_child_identity(identity, "build")
    inference_identity = direct_child_identity(identity, "inference")

    def phase_seconds(name: str) -> int:
        remaining = int(deadline - time.monotonic())
        if remaining < 40:
            raise RecipeRefused("construction_total_deadline_reached")
        return min(policy[name], remaining)

    build = reconstruct_public_graph(
        ledger,
        owner=owner,
        identity=build_identity,
        image=image,
        recipe=recipe,
        challenge_binding=binding,
        limits_document=limits_document,
        source_envelope=source_envelope,
        train=train,
        allowlist_bytes=allowlist_bytes,
        seed=seed,
        seconds=phase_seconds("build_wall_seconds_max"),
        runner=runner,
    )
    expected = ledger.root / build.worker_operation / "snapshot" / "state.npz"
    if build.state_path != expected or expected.is_symlink() or not expected.is_file():
        raise RecipeRefused("direct_graph_state_custody_invalid")
    state = expected.read_bytes()
    if _digest(state) != build.state_digest:
        raise RecipeRefused("direct_graph_state_changed")
    inference = _infer_state(
        ledger,
        owner=owner,
        identity=inference_identity,
        inference_image=image,
        recipe=recipe,
        binding=binding,
        state=state,
        state_digest=build.state_digest,
        inputs=inputs,
        expected_output_shape=expected_output_shape,
        expected_output_dtype="float32",
        measure_query=measure_query,
        allowlist_bytes=allowlist_bytes,
        input_name="inputs/forcing",
        provenance=INFERENCE_PROVENANCE,
        seconds=phase_seconds("inference_wall_seconds_max"),
        runner=runner,
    )
    elapsed = time.monotonic() - started
    if elapsed > policy["total_reconstruction_wall_seconds_max"]:
        raise RecipeRefused("construction_total_deadline_reached")
    if build.state_digest != inference.state_digest:
        raise RecipeRefused("direct_graph_inference_custody_invalid")
    controls = (
        (
            _private_controls_digest(
                ledger,
                owner=owner,
                identity=build_identity,
                operation=build.worker_operation,
                provenance=BUILD_PROVENANCE,
            ),
            _private_controls_digest(
                ledger,
                owner=owner,
                identity=inference_identity,
                operation=inference.worker_operation,
                provenance=INFERENCE_PROVENANCE,
            ),
        )
        if runner is None
        else (None, None)
    )
    return DirectReconstructionResult(
        build,
        inference,
        policy_digest,
        "C03_DOCKER" if runner is None else "TEST_ONLY_LOCAL_RUNNER",
        controls[0],
        controls[1],
        elapsed,
    )
