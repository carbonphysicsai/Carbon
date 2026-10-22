"""One isolated source-bundle build and separate inert-graph inference route.

The source callable runs only in the provisioned child. The inference worker
receives no source package, TRAIN bytes or constructor, and uses the existing
Carbon graph interpreter. A Challenge owns the exact TRAIN tensor document and
its interface adapter; this module does not choose scientific measurements.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import re
import tarfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from carbon.challenge_validator.strict_json import MalformedStrategy, parse_strategy
from carbon.reconstruction.worker.model import worker_resources_version

from .bundle_graph_state import MAX_BYTES as MAX_STATE_BYTES
from .bundle_graph_state import state_fits, state_limit
from .construction_recipe import ConstructionRecipe, RecipeRefused, bind_recipe
from .library_bundles import LibraryBundleRef, bundle_ref
from .library_environment_cache import VerifiedLibraryOverlay
from .profile import canonical
from .research_carrier import (
    LIBRARY_BUILD_PROVENANCE,
    LIBRARY_OVERLAY_BUILD_PROVENANCE,
    LIBRARY_PREP_PROVENANCE,
    MINER_GPU,
    PRECHARGED_TRIAL,
    VALIDATOR_GPU,
    _run,
)
from .research_image import LibraryWorkerImage


def _accelerator_kwargs(accelerator: str | None) -> dict:
    """Omit the historical CPU field; let the carrier verify explicit GPU pins."""
    if accelerator is None:
        return {}
    if type(accelerator) is not str or accelerator not in (MINER_GPU, VALIDATOR_GPU):
        raise RecipeRefused("bundle_accelerator_invalid")
    return {"accelerator": accelerator}


PREP_PROGRAM = r'''"""Fixed, source-free C03 offline material preparation."""
import os, shutil, sys
from pathlib import Path

work = Path('/scratch/workspace')
for package in ('carbon', 'carbon/development_session'):
    directory = work / package
    directory.mkdir(parents=True, exist_ok=True)
    (directory / '__init__.py').write_text('')
for name in ('library_bundles', 'library_overlay_prep'):
    shutil.copyfile(
        Path('/input') / ('carbon.development_session.' + name + '.py'),
        work / 'carbon' / 'development_session' / (name + '.py'),
    )
sys.path.insert(0, str(work))
from carbon.development_session.library_overlay_prep import prepare
prepare(Path('/input'), Path('/scratch/output'))
'''

PREP_BOOTSTRAP = """
import os
from pathlib import Path
Path('/scratch/workspace').mkdir()
Path('/scratch/output').mkdir()
os.chdir('/scratch/workspace')
os.execv('/opt/carbon-worker/bin/python', ['python', '-I', '/input/program.py'])
"""

OVERLAY_BUILD_BOOTSTRAP = """
import os, shutil
from pathlib import Path
work = Path('/scratch/workspace'); work.mkdir()
Path('/scratch/output').mkdir()
overlay = Path('/input/overlay')
if not overlay.is_dir():
    raise ValueError('verified build overlay missing')
for item in Path('/input').iterdir():
    if item.name in ('program.py', 'overlay'):
        continue
    if not item.is_file():
        raise ValueError('closed build input required')
    shutil.copyfile(item, work / item.name)
os.chdir(work)
os.execv('/opt/carbon-worker/bin/python', ['python', '-I', '/input/program.py'])
"""

BUILD_PROGRAM = r'''"""Fixed isolated source-bundle build; no judge or hidden data."""
import hashlib, importlib, json, os, re, shutil, sys
from pathlib import Path
import numpy as np

work = Path.cwd()
out = work.parent / "output"
for package in ("carbon", "carbon/challenge_validator", "carbon/level4",
                "carbon/level4/tooling", "carbon/development_session",
                "carbon/battery", "carbon/reconstruction",
                "carbon/reconstruction/worker", "carbon/registry"):
    folder = work / package
    folder.mkdir(parents=True, exist_ok=True)
    if package != "carbon/registry":
        (folder / "__init__.py").write_text("")
control = json.loads((work / "control.json").read_bytes())
codec_modules = control.get("codec_modules")
if (type(codec_modules) is not list or len(codec_modules) != len(set(codec_modules))
    or any(type(name) is not str or re.fullmatch(
        r"carbon(?:\.[A-Za-z_][A-Za-z_0-9]*){1,5}", name) is None
        for name in codec_modules)):
    raise ValueError("bundle build codec module list differs")
for name in (*__STAGED_MODULES__, *codec_modules):
    destination = work.joinpath(*name.split(".")).with_suffix(".py")
    shutil.copyfile(work / (name + ".py"), destination)
sys.path.insert(0, str(work))

from carbon.development_session.construction_recipe import ConstructionRecipe, bind_recipe
from carbon.development_session.bundle_graph_state import freeze
from carbon.development_session.construction_tensor_codec import (
    input_tensor, requires_x64, train_tensors,
)
from carbon.reconstruction.capability_registry import BATTERY_CHALLENGE
from carbon.level4.allowlist import Allowlist

digest = lambda body: "sha256:" + hashlib.sha256(body).hexdigest()
recipe = ConstructionRecipe.from_bytes((work / "recipe.json").read_bytes())
if recipe.digest != control["recipe_digest"]:
    raise ValueError("bundle build recipe differs")
bind_recipe(recipe.to_dict(), **control["binding"])
source = recipe.to_dict()["source"]
if source["kind"] != "bundle" or source["bundle_ref"] != control["bundle_ref"]:
    raise ValueError("bundle build source differs")
overlay_digest = control.get("overlay_tree_digest")
if overlay_digest is not None:
    overlay = Path('/input/overlay')
    if (type(overlay_digest) is not str or len(overlay_digest) != 71
        or not overlay_digest.startswith('sha256:') or not overlay.is_dir()
        or not (overlay / '.overlay.json').is_file()):
        raise ValueError('verified bundle overlay missing')
    receipt = json.loads((overlay / '.overlay.json').read_bytes())
    if (receipt.get('tree_digest') != overlay_digest
        or receipt.get('bundle_ref') != control['bundle_ref']):
        raise ValueError('bundle overlay binding differs')
    sys.path[0:0] = [str(overlay / 'source'), str(overlay / 'site-packages')]
train_name = ("train.gz" if control["binding"]["challenge_id"] == BATTERY_CHALLENGE
              else "train.npz")
train_raw = (work / train_name).read_bytes()
train_inputs, train_targets = train_tensors(train_raw, control["binding"])
example_raw = (work / "example.npz").read_bytes()
example = input_tensor(example_raw, control["example_digest"])
if example.shape[1:] != train_inputs.shape[1:]:
    raise ValueError("bundle build example shape differs")
if requires_x64(train_inputs, train_targets, example):
    os.environ["JAX_ENABLE_X64"] = "1"
from carbon.level4.tooling import lower_jax, lower_torch

entry = recipe.to_dict()["procedure"]["entrypoint"]
factory = getattr(importlib.import_module(entry["module"]), entry["name"])
if not callable(factory):
    raise ValueError("bundle build entrypoint not callable")
product = factory(
    train_inputs, train_targets, seed=control["seed"],
    configuration=recipe.to_dict()["procedure"]["configuration"],
    train_use=recipe.to_dict()["procedure"]["train_use"],
)
if (type(product) is not dict or set(product) != {"framework", "apply", "parameters"}
    or product["framework"] not in ("jax", "torch")
    or not callable(product["apply"]) or type(product["parameters"]) is not list):
    raise ValueError("bundle build product contract differs")
# From here Carbon's own lowering and freeze run on the candidate's model. A closed
# refusal there is the candidate's, so it leaves only refusal.json (fixed schema, no
# text); every other failure keeps its crash and its infrastructure meaning.
from carbon.development_session.construction_recipe import RecipeRefused
from carbon.level4.graph import GraphRefused
def _refusal_hook(kind, error, trace):
    if issubclass(kind, (GraphRefused, RecipeRefused)):
        code = getattr(error, "code", None)
        where = getattr(error, "op", None) or getattr(error, "where", "")
        (out / "refusal.json").write_text(json.dumps({
            "schema": "carbon.development.bundle-build-refusal.v1",
            "code": code if type(code) is str else "unspecified",
            "at": where if type(where) is str and where else None,
        }, sort_keys=True))
        os._exit(0)
    sys.__excepthook__(kind, error, trace)
sys.excepthook = _refusal_hook
allowed = Allowlist((work / "allowlist.json").read_bytes())
if allowed.digest != control["allowlist_digest"]:
    raise ValueError("bundle build allowlist differs")
if product["framework"] == "jax":
    import jax.numpy as jnp
    if product["parameters"]:
        # Trained arrays travel as state (params/i inputs), as the Torch path does,
        # so a realistic model does not hit the graph-constant cap.
        params = [jnp.asarray(p) for p in product["parameters"]]
        trial = np.asarray(product["apply"](params, jnp.asarray(example)))
        traced = lower_jax.trace(
            lambda *args: product["apply"](list(args[:-1]), args[-1]),
            *params, jnp.asarray(example),
        )
        doc = lower_jax.lower(
            traced, role="forward", allowlist=allowed,
            input_names=[f"params/{i}" for i in range(len(params))] + ["inputs/x"],
        )
        arrays = [np.asarray(p) for p in params]
    else:
        trial = np.asarray(product["apply"](jnp.asarray(example)))
        traced = lower_jax.trace(product["apply"], jnp.asarray(example))
        doc = lower_jax.lower(
            traced, role="forward", allowlist=allowed, input_names=["inputs/x"]
        )
        arrays = []
else:
    import torch
    arrays = [np.asarray(p.detach().cpu().numpy()) for p in product["parameters"]]
    with torch.no_grad():
        trial = np.asarray(product["apply"](
            product["parameters"], torch.as_tensor(example)
        ).detach().cpu().numpy())
    _, core = lower_torch.export(
        product["apply"], product["parameters"], torch.as_tensor(example)
    )
    doc, _ = lower_torch.lower(core, allowlist=allowed)
if (trial.shape != (len(example), *train_targets.shape[1:])
    or trial.dtype.kind not in "fiu" or trial.dtype.itemsize > 8
    or trial.nbytes > 16 * 1024**2 or not np.isfinite(trial).all()):
    raise ValueError("bundle build output shape or value differs")
state = freeze(recipe, doc, arrays, allowed)
(out / "state.npz").write_bytes(state)
native_raw = json.dumps(trial.tolist(), separators=(",", ":"), allow_nan=False).encode()
if not 0 < len(native_raw) <= 16 * 1024**2:
    raise ValueError("bounded native predictions required")
(out / "native-predictions.json").write_bytes(native_raw)
(out / "receipt.json").write_text(json.dumps({
    "schema": "carbon.development.bundle-build.v2",
    "example_digest": control["example_digest"],
    "native_predictions_digest": digest(native_raw),
    "native_dtype": str(trial.dtype),
    "native_shape": list(trial.shape),
    "recipe_digest": recipe.digest,
    "bundle_digest": source["bundle_ref"]["bundle_digest"],
    "train_digest": control["binding"]["train_digest"],
    "state_digest": digest(state),
    "allowlist_digest": allowed.digest,
    "framework": product["framework"],
}, sort_keys=True, allow_nan=False))
'''

INFER_PROGRAM = r'''"""Fixed input-only graph inference; no source or TRAIN."""
import hashlib, json, os, re, shutil, sys, time
from pathlib import Path
import numpy as np

work = Path.cwd()
out = work.parent / "output"
for package in ("carbon", "carbon/challenge_validator", "carbon/level4",
                "carbon/level4/tooling", "carbon/development_session"):
    folder = work / package
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "__init__.py").write_text("")
control = json.loads((work / "control.json").read_bytes())
codec_modules = control.get("codec_modules")
if (type(codec_modules) is not list or len(codec_modules) != len(set(codec_modules))
    or any(type(name) is not str or re.fullmatch(
        r"carbon(?:\.[A-Za-z_][A-Za-z_0-9]*){1,5}", name) is None
        for name in codec_modules)):
    raise ValueError("bundle inference codec module list differs")
for name in (*__STAGED_MODULES__, *codec_modules):
    destination = work.joinpath(*name.split(".")).with_suffix(".py")
    shutil.copyfile(work / (name + ".py"), destination)
sys.path.insert(0, str(work))

from carbon.development_session.construction_recipe import ConstructionRecipe, bind_recipe
from carbon.development_session.bundle_graph_state import load
from carbon.development_session.construction_tensor_codec import input_tensor, requires_x64
from carbon.level4.allowlist import Allowlist

digest = lambda body: "sha256:" + hashlib.sha256(body).hexdigest()
recipe = ConstructionRecipe.from_bytes((work / "recipe.json").read_bytes())
if recipe.digest != control["recipe_digest"]:
    raise ValueError("bundle inference recipe differs")
bind_recipe(recipe.to_dict(), **control["binding"])
state = (work / "state.npz").read_bytes()
if digest(state) != control["state_digest"]:
    raise ValueError("bundle inference state differs")
allowed = Allowlist((work / "allowlist.json").read_bytes())
if allowed.digest != control["allowlist_digest"]:
    raise ValueError("bundle inference allowlist differs")
measure = control.get("measure_query", False)
if type(measure) is not bool:
    raise ValueError("bundle inference measurement control differs")
per_case = control.get("per_case", True)
if type(per_case) is not bool or (measure and per_case):
    raise ValueError("bundle inference per-case control differs")
if measure:
    preprocess_start = time.perf_counter()
doc, parameters = load(state, recipe, allowed)
raw_inputs = (work / "inputs.npz").read_bytes()
inputs = input_tensor(raw_inputs, control["inputs_digest"])
pending = [doc]
graph_x64 = False
while pending:
    value = pending.pop()
    if type(value) is dict:
        if value.get("dtype") in ("float64", "int64", "uint64", "complex128"):
            graph_x64 = True
            break
        pending.extend(value.values())
    elif type(value) is list:
        pending.extend(value)
if graph_x64 or requires_x64(
    inputs, control.get("expected_output_dtype") or inputs.dtype, *parameters
):
    os.environ["JAX_ENABLE_X64"] = "1"
    # load() can already have imported jax (graphs with FFT ops do), after which
    # the environment variable no longer applies.
    import jax
    jax.config.update("jax_enable_x64", True)
from carbon.level4.interpret import rebuild
import jax.numpy as jnp
declared = doc["graphs"][doc["entry"]]["inputs"]
if (len(declared) != len(parameters) + 1
    or declared[-1]["name"] != control.get("input_name", "inputs/x")):
    raise ValueError("bundle inference input binding differs")
parameter_arrays = [jnp.asarray(p) for p in parameters]
input_array = jnp.asarray(inputs)
if measure:
    inference_start = time.perf_counter()
forward = rebuild(doc, allowed)
graph_source = recipe.to_dict()["source"]["kind"] == "graph"
arity = ("graph inference output arity differs"
         if graph_source else "bundle inference output arity differs")
batch = declared[-1]["shape"][0]
blocks = []
if per_case:
    # One case per call: the case is row 0 and the other batch rows are a fixed
    # public constant (zeros), so no output can depend on another case.
    for index in range(len(input_array)):
        part = jnp.pad(input_array[index:index + 1],
                       [(0, batch - 1)] + [(0, 0)] * (input_array.ndim - 1))
        outputs = forward(*parameter_arrays, part)
        if len(outputs) != 1:
            raise ValueError(arity)
        blocks.append(outputs[0][:1])
    outputs = [jnp.concatenate(blocks)]
elif graph_source:
    # The batched cold query kept only for timing (measure_query); never graded.
    for start in range(0, len(input_array), batch):
        part = input_array[start:start + batch]
        used = len(part)
        if used < batch:
            part = jnp.pad(part, [(0, batch - used)] + [(0, 0)] * (part.ndim - 1))
        outputs = forward(*parameter_arrays, part)
        if len(outputs) != 1:
            raise ValueError(arity)
        blocks.append(outputs[0][:used])
    outputs = [jnp.concatenate(blocks)]
else:
    outputs = forward(*parameter_arrays, input_array)
if len(outputs) != 1:
    raise ValueError("bundle inference output arity differs")
result = np.asarray(outputs[0])
if measure:
    postprocess_start = time.perf_counter()
if (list(result.shape) != control["expected_output_shape"]
    or (control.get("expected_output_dtype") is not None
        and result.dtype != np.dtype(control["expected_output_dtype"]))
    or result.dtype.kind not in "fiu" or not np.isfinite(result).all()):
    raise ValueError("bundle inference output contract differs")
body = json.dumps(result.tolist(), allow_nan=False, separators=(",", ":")).encode()
if measure:
    export_start = time.perf_counter()
(out / "predictions.json").write_bytes(body)
receipt = {
    "schema": ("carbon.development.bundle-inference.v2" if measure
               else "carbon.development.bundle-inference.v1"),
    "recipe_digest": recipe.digest,
    "state_digest": control["state_digest"],
    "inputs_digest": control["inputs_digest"],
    "predictions_digest": digest(body),
}
if measure:
    export_end = time.perf_counter()
    receipt["measurement"] = {
        "scope": "COLD_SINGLE_WORKER_QUERY_INCLUDES_GRAPH_LOAD_AND_JAX_COMPILE",
        "timing_s": {
            "preprocess": inference_start - preprocess_start,
            "inference": postprocess_start - inference_start,
            "postprocess": export_start - postprocess_start,
            "export": export_end - export_start,
        },
        "input_shape": list(inputs.shape),
        "input_dtype": str(inputs.dtype),
        "output_shape": list(result.shape),
        "output_dtype": str(result.dtype),
    }
(out / "receipt.json").write_text(json.dumps(receipt, sort_keys=True, allow_nan=False))
'''

STAGED_MODULES = (
    "carbon.challenge_validator.strict_json",
    "carbon.level4.graph",
    "carbon.level4.params",
    "carbon.level4.allowlist",
    "carbon.level4.named",
    "carbon.level4.interpret",
    "carbon.level4.tooling.lower_jax",
    "carbon.level4.tooling.lower_torch",
    "carbon.development_session.construction_recipe",
    "carbon.development_session.bundle_graph_state",
)
from . import build_refusal
from .build_refusal import CandidateBuildRefused

BUILD_PROGRAM = BUILD_PROGRAM.replace("__STAGED_MODULES__", repr(STAGED_MODULES))
INFER_PROGRAM = INFER_PROGRAM.replace("__STAGED_MODULES__", repr(STAGED_MODULES))


def _digest(body: bytes) -> str:
    return "sha256:" + hashlib.sha256(body).hexdigest()


@dataclass(frozen=True)
class BundleOverlayPrepResult:
    snapshot: Path
    receipt: dict
    worker_operation: str
    controls_digest: str | None


def _checked_overlay_snapshot(snapshot: Path, expected_bundle: dict, parent_id: str):
    from .library_overlay_prep import (
        MAX_OVERLAY_BYTES,
        MAX_OVERLAY_FILES,
        OVERLAY_SCHEMA,
    )

    if {path.name for path in snapshot.iterdir()} != {"overlay.tar", "overlay.json"}:
        raise ValueError("bounded overlay output set differs")
    receipt_raw = (snapshot / "overlay.json").read_bytes()
    archive_path = snapshot / "overlay.tar"
    if (
        archive_path.is_symlink()
        or not archive_path.is_file()
        or (snapshot / "overlay.json").is_symlink()
        or not 0 < archive_path.stat().st_size <= MAX_OVERLAY_BYTES
        or not 0 < len(receipt_raw) <= 65536
    ):
        raise ValueError("bounded overlay output required")
    receipt = json.loads(receipt_raw)
    if (
        type(receipt) is not dict
        or set(receipt)
        != {
            "schema",
            "bundle_ref",
            "parent_image_id",
            "archive_sha256",
            "archive_bytes",
            "tree_digest",
            "file_count",
            "total_file_bytes",
        }
        or receipt["schema"] != OVERLAY_SCHEMA
        or receipt["bundle_ref"] != expected_bundle
        or receipt["parent_image_id"] != parent_id
        or receipt["archive_bytes"] != archive_path.stat().st_size
        or receipt["archive_sha256"] != _digest(archive_path.read_bytes())
    ):
        raise ValueError("overlay preparation identity differs")
    rows = []
    seen = set()
    total = 0
    with tarfile.open(archive_path, mode="r:") as archive:
        for member in archive:
            name = member.name
            if (
                member.type != tarfile.REGTYPE
                or member.issparse()
                or not name.startswith(("site-packages/", "source/"))
                or name.startswith("/")
                or any(part in {"", ".", ".."} for part in name.split("/"))
                or "\\" in name
                or ":" in name
                or name.casefold() in seen
                or len(rows) >= MAX_OVERLAY_FILES
                or type(member.size) is not int
                or member.size < 0
                or total + member.size > MAX_OVERLAY_BYTES
            ):
                raise ValueError("overlay archive member differs")
            seen.add(name.casefold())
            total += member.size
            item = archive.extractfile(member)
            if item is None:
                raise ValueError("overlay archive member unavailable")
            body = item.read(MAX_OVERLAY_BYTES + 1)
            if len(body) != member.size:
                raise ValueError("overlay archive member changed")
            rows.append([name, member.size, _digest(body)])
    rows.sort(key=lambda row: row[0])
    if (
        total != receipt["total_file_bytes"]
        or len(rows) != receipt["file_count"]
        or receipt["tree_digest"]
        != _digest(json.dumps(rows, separators=(",", ":")).encode())
    ):
        raise ValueError("overlay preparation tree differs")
    return receipt


def prepare_library_overlay(
    ledger,
    *,
    owner: str,
    identity: str,
    parent,
    recipe: ConstructionRecipe,
    challenge_binding: dict,
    limits_document: dict,
    material: tuple,
    seconds: int = 600,
    deadline: float | None = None,
    cancel: Callable[[], None] | None = None,
    accelerator: str | None = None,
    runner=None,
) -> BundleOverlayPrepResult:
    """Install exact offline wheels only inside a controlled C03 operation."""
    from carbon.reconstruction.worker.model import WorkerImageIdentity

    from .library_bundles import UV_IMAGE, verify_bundle_parent_environment
    from .library_environment_cache import pinned_uv_bytes

    binding = _checked_binding(recipe, challenge_binding)
    verify_direct_resource_policy(binding, limits_document, _ANY_SERVED)
    if (
        type(parent) is not WorkerImageIdentity
        or type(material) is not tuple
        or len(material) != 5
    ):
        raise RecipeRefused("bundle_overlay_prep_binding_invalid")
    selected = bundle_ref(*material)
    if selected.to_dict() != recipe.to_dict()["source"].get("bundle_ref"):
        raise RecipeRefused("bundle_overlay_prep_source_changed")
    manifest, source, wheels, lock, license_text = material
    verify_bundle_parent_environment(manifest, parent)
    parent_build = {
        "schema": "carbon.c03.worker-image-build.v1",
        "source_tree_digest": parent.source_tree_digest,
        "wheel_digest": parent.wheel_digest,
        "lock_digest": parent.lock_digest,
        "base_image_digest": parent.base_image_digest,
        "build_recipe_digest": parent.build_recipe_digest,
        "entrypoint_digest": parent.entrypoint_digest,
    }
    files = {
        "bundle.json": json.dumps(manifest, sort_keys=True).encode(),
        "source.tar.gz": source,
        "requirements.txt": lock,
        "LICENSE": license_text,
        "carbon.development_session.library_bundles.py": (
            Path(__file__).with_name("library_bundles.py").read_bytes()
        ),
        "carbon.development_session.library_overlay_prep.py": (
            Path(__file__).with_name("library_overlay_prep.py").read_bytes()
        ),
    }
    files.update(wheels)
    stage_identity = {
        "schema": "carbon.development.pinned-uv-stage.v1",
        "uv_image": UV_IMAGE,
        "bundle_ref": selected.to_dict(),
        "parent_image_id": parent.image_id,
        "parent_build": parent_build,
    }

    def stage_uv(cli):
        uv_binary = pinned_uv_bytes(cli, deadline=deadline, cancel=cancel)
        return {
            "uv-bin": uv_binary,
            "control.json": json.dumps(
                {
                    "bundle_ref": selected.to_dict(),
                    "parent_image_id": parent.image_id,
                    "parent_build": parent_build,
                    "uv_sha256": _digest(uv_binary),
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode(),
        }

    def checked(snapshot: Path):
        return _checked_overlay_snapshot(snapshot, selected.to_dict(), parent.image_id)

    worker = (runner or _run)(
        ledger,
        owner=owner,
        identity=identity,
        source=PREP_PROGRAM,
        files=files,
        image=parent,
        seconds=seconds,
        provenance=LIBRARY_PREP_PROVENANCE,
        extra_resources=(
            {} if PRECHARGED_TRIAL.get() is not None else {"research_trials": 1}
        ),
        output_validator=checked,
        executable_files=("uv-bin",),
        trusted_stage_provider=stage_uv,
        trusted_stage_identity=stage_identity,
        bootstrap=PREP_BOOTSTRAP,
        **_accelerator_kwargs(accelerator),
    )
    snapshot = ledger.root / worker["operation"] / "snapshot"
    receipt = checked(snapshot)
    if any(
        _digest((snapshot / name).read_bytes()) != worker["files"].get(name)
        for name in ("overlay.tar", "overlay.json")
    ):
        raise ValueError("overlay preparation snapshot changed")
    return BundleOverlayPrepResult(
        snapshot,
        receipt,
        worker["operation"],
        (
            _private_controls_digest(
                ledger,
                owner=owner,
                identity=identity,
                operation=worker["operation"],
                provenance=LIBRARY_PREP_PROVENANCE,
            )
            if runner is None
            else None
        ),
    )


def _tensors(**arrays) -> bytes:
    out = io.BytesIO()
    for value in arrays.values():
        if (
            type(value) is not np.ndarray
            or value.dtype.kind not in "fiu"
            or not np.isfinite(value).all()
        ):
            raise RecipeRefused("bundle_tensor_invalid")
    np.savez(out, **arrays)
    body = out.getvalue()
    if not 0 < len(body) <= MAX_STATE_BYTES:
        raise RecipeRefused("bundle_tensor_oversized")
    return body


def _checked_binding(recipe: ConstructionRecipe, binding: dict) -> dict:
    """Require a trusted Challenge's exact kit, never one echoed by the recipe."""
    if type(binding) is not dict or set(binding) != {
        "challenge_id",
        "challenge_version",
        "train_digest",
        "interface_digest",
        "construction_limits_digest",
    }:
        raise RecipeRefused("bundle_challenge_binding_invalid")
    bind_recipe(recipe.to_dict(), **binding)
    return binding


_ANY_SERVED = object()


def verify_direct_resource_policy(
    binding: dict, limits_document: dict, worker_resources_version=None
) -> str:
    """Check a registered Challenge policy against the actual C-03 lane.

    A request or operator profile cannot author this policy. The kit's pinned
    limits digest is checked first; the worker profile then proves these
    finite limits are the ones this direct source route actually enforces.
    The aggregate task deadline remains an orchestration obligation, not a
    property inferred from either 600-second worker call.

    ``worker_resources_version`` names the profile the run uses (a next
    version's larger worker resources, from the allowlist it builds under);
    `_ANY_SERVED`, for a step that runs at today's resources whatever the
    version (dependency preparation), accepts the policy of either profile.
    """
    from carbon.challenge_kit import synthetic_linear_field_2d

    from .local_diagnostic_plan import MAX_TASK_WALL_SECONDS
    from .research_carrier import _worker_profile

    version = (
        binding.get("challenge_version", binding.get("version"))
        if type(binding) is dict
        else None
    )
    challenge_id = (
        binding.get("challenge_id", binding.get("id"))
        if type(binding) is dict
        else None
    )
    if (
        type(challenge_id) is not str
        or type(version) is not str
        or (
            "challenge_id" in binding
            and "id" in binding
            and binding["challenge_id"] != binding["id"]
        )
        or (
            "challenge_version" in binding
            and "version" in binding
            and binding["challenge_version"] != binding["version"]
        )
    ):
        raise RecipeRefused("construction_resource_policy_binding_invalid")
    expected_scope = "PUBLIC_SYNTHETIC_DEVELOPMENT_ONLY"
    resource_schema = "carbon.synthetic-linear-field-2d.reconstruction-resources.v1"
    from carbon.reconstruction.capability_registry import BATTERY_CHALLENGE

    if challenge_id == BATTERY_CHALLENGE:
        from carbon.battery import challenge, construction_bundle_material

        if version not in construction_bundle_material.VERSIONS:
            raise RecipeRefused("construction_resource_policy_binding_invalid")
        if version == challenge.CHALLENGE.version:
            trusted_limits = construction_bundle_material.construction_limits_document()
            expected_schema = "carbon.battery.bundle-construction-limits.v1"
        else:
            # The step-2 version: its limits carry the bank's row count, so they
            # are read from its own served material, the one source.
            try:
                trusted_limits = construction_bundle_material.versioned_material(
                    version
                )["construction_limits_document"]
            except (ValueError, OSError):
                raise RecipeRefused(
                    "construction_resource_policy_binding_invalid"
                ) from None
            expected_schema = construction_bundle_material.LIMITS_SCHEMA_V2
        expected_scope = "PUBLIC_BATTERY_DEVELOPMENT_ONLY"
        resource_schema = "carbon.battery.bundle-reconstruction-resources.v1"
    elif (
        challenge_id == synthetic_linear_field_2d.CHALLENGE.challenge_id
        and version == "1.3"
    ):
        prospective = getattr(
            synthetic_linear_field_2d, "construction_limits_document_v3", None
        )
        if not callable(prospective):
            raise RecipeRefused("construction_resource_policy_binding_invalid")
        trusted_limits = prospective()
        expected_schema = "carbon.synthetic-linear-field-2d.construction-limits.v3"
    elif (
        challenge_id == synthetic_linear_field_2d.CHALLENGE.challenge_id
        and version in ("1.0", "1.1", "1.2")
    ):
        trusted_limits = synthetic_linear_field_2d.construction_limits_document()
        expected_schema = "carbon.synthetic-linear-field-2d.construction-limits.v2"
    else:
        if challenge_id == "f08-ribbed-bracket":
            from carbon.challenge_kit import f08_public as public_material
        elif challenge_id == "f02":
            from carbon.challenge_kit import f02_public as public_material
        else:
            from carbon.challenge_kit import physical_public as public_material

        try:
            material = public_material.trusted_material(challenge_id, version)
            kit = public_material.construction_kit(challenge_id, version)
        except (ValueError, OSError):
            raise RecipeRefused(
                "construction_resource_policy_binding_invalid"
            ) from None
        if any(
            binding.get(key) != kit[key]
            for key in (
                "train_digest",
                "interface_digest",
                "construction_limits_digest",
            )
        ):
            raise RecipeRefused("construction_resource_policy_binding_invalid")
        trusted_limits = material["limits_document"]
        expected_schema = material["limits_schema"]
        expected_scope = material["scope"]
        resource_schema = material["resource_schema"]
    if (
        type(binding) is not dict
        or type(limits_document) is not dict
        or limits_document != trusted_limits
        or _digest(canonical(limits_document))
        != binding.get("construction_limits_digest")
        or limits_document.get("schema") != expected_schema
        or limits_document.get("scope") != expected_scope
    ):
        raise RecipeRefused("construction_resource_policy_binding_invalid")
    from carbon.reconstruction.worker.model import LARGE_MODEL_ALLOWLIST_VERSIONS

    def expected(resources_version):
        profile = _worker_profile(
            None, LIBRARY_BUILD_PROVENANCE, resources_version
        ).body
        return {
            "schema": resource_schema,
            "cpu_count_max": profile["cpu"]["count"],
            "memory_bytes_max": profile["memory"]["bytes"],
            "swap_bytes_max": profile["memory"]["swap_bytes"],
            "pids_max": profile["pids"],
            "nofile_max": profile["nofile_per_process"],
            "scratch_bytes_max": profile["scratch"]["bytes"],
            "scratch_inodes_max": profile["scratch"]["inodes"],
            "build_wall_seconds_max": profile["deadline_seconds"],
            "inference_wall_seconds_max": profile["deadline_seconds"],
            "total_reconstruction_wall_seconds_max": MAX_TASK_WALL_SECONDS,
            "network": profile["security"]["network"],
            "cleanup_required": True,
        }

    candidates = (
        (None, *sorted(LARGE_MODEL_ALLOWLIST_VERSIONS))
        if worker_resources_version is _ANY_SERVED
        else (worker_resources_version,)
    )
    served = limits_document.get("reconstruction_resource_policy")
    if not any(served == expected(candidate) for candidate in candidates):
        raise RecipeRefused("construction_resource_policy_unserved")
    return binding["construction_limits_digest"]


def _stage_modules() -> dict[str, bytes]:
    """Preserve the existing graph worker's exact trusted stage contract."""
    root = Path(__file__).resolve().parents[2]
    return {
        name + ".py": (root / (name.replace(".", "/") + ".py")).read_bytes()
        for name in STAGED_MODULES
    }


def _stage_bundle_modules(
    binding: dict, *, training: bool
) -> tuple[dict[str, bytes], list[str]]:
    from .construction_tensor_codec import worker_module_files

    files = _stage_modules()
    codec_files = worker_module_files(binding, training=training)
    if any(name in files and files[name] != raw for name, raw in codec_files.items()):
        raise RecipeRefused("bundle_worker_module_closure_changed")
    files.update(codec_files)
    return files, sorted(name.removesuffix(".py") for name in codec_files)


def _trusted_allowlist(raw: bytes):
    """Select only an exact repository material; v1 history stays unchanged."""
    from carbon.challenge_kit import synthetic_linear_field_2d
    from carbon.level4.allowlist import Allowlist

    if type(raw) is not bytes or not 0 < len(raw) <= 1024**2:
        raise RecipeRefused("bundle_allowlist_invalid")
    root = Path(__file__).resolve().parents[1] / "level4"
    trusted = (
        (root / "allowlist_v1.json").read_bytes(),
        (root / "allowlist_v2.json").read_bytes(),
        (root / "allowlist_v3.json").read_bytes(),
        (root / "allowlist_v4.json").read_bytes(),
    )
    prospective = getattr(synthetic_linear_field_2d, "allowlist_v5_bytes", None)
    if callable(prospective):
        trusted += (prospective(),)
    from carbon.level4.allowlist import served_bytes, v7_bytes

    # The served allowlists: v6, and v7 on the catalog versions that serve it
    # (`served_versions.V7`); v1-v5 stay trusted for historical builds.
    trusted += (served_bytes(), v7_bytes())
    if raw not in trusted:
        raise RecipeRefused("bundle_allowlist_unregistered")
    return Allowlist(raw)


def native_build_predictions(build) -> np.ndarray:
    """Read one bounded original native output from its checked build snapshot."""
    receipt = build.receipt
    if (
        type(receipt) is not dict
        or receipt.get("schema") != "carbon.development.bundle-build.v2"
        or receipt.get("recipe_digest") != build.recipe_digest
        or receipt.get("state_digest") != build.state_digest
    ):
        raise ValueError("native build prediction identity differs")
    path = build.state_path.parent / "native-predictions.json"
    if (
        path.is_symlink()
        or not path.is_file()
        or not 0 < path.stat().st_size <= 16 * 1024**2
    ):
        raise ValueError("bounded native prediction snapshot required")
    raw = path.read_bytes()
    if _digest(raw) != receipt.get("native_predictions_digest"):
        raise ValueError("native prediction snapshot changed")
    try:
        dtype = np.dtype(receipt["native_dtype"])
        shape = receipt["native_shape"]
        if (
            dtype.kind not in "fiu"
            or dtype.itemsize > 8
            or type(shape) is not list
            or not shape
            or len(shape) > 16
            or any(type(n) is not int or n < 1 for n in shape)
            or math.prod(shape) * dtype.itemsize > 16 * 1024**2
        ):
            raise ValueError("native prediction tensor contract differs")
        values = json.loads(raw)
        if type(values) is not list:
            raise ValueError("native predictions must be an array")
        observed = np.asarray(values)
        if observed.dtype.kind not in "fiu" or not np.isfinite(observed).all():
            raise ValueError("native predictions must be numeric")
        if dtype.kind in "iu":
            bounds = np.iinfo(dtype)
            if (
                observed.dtype.kind not in "iu"
                or int(observed.min()) < bounds.min
                or int(observed.max()) > bounds.max
            ):
                raise ValueError("native integer prediction range differs")
        result = np.asarray(values, dtype=dtype)
        if list(result.shape) != shape or not np.isfinite(result).all():
            raise ValueError("native prediction tensor contract differs")
    except (KeyError, TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise ValueError("native prediction tensor contract differs") from exc
    return result


def compare_build_inference_predictions(
    build, inference, *, expected_output_dtype=None
):
    """Diagnose lowering only for the same recipe, state and exact public probe."""
    if build.receipt.get("schema") != "carbon.development.bundle-build.v2":
        return None  # Historical results contain no native prediction artifact.
    native = native_build_predictions(build)
    probe = build.receipt["example_digest"]
    if probe != inference.receipt.get("inputs_digest"):
        return {
            "schema": "carbon.development.bundle-prediction-comparison-unavailable.v1",
            "reason_code": "different_public_probe",
            "native_probe_digest": probe,
            "lowered_probe_digest": inference.receipt.get("inputs_digest"),
        }
    if native.size > 1_000_000:
        return {
            "schema": "carbon.development.bundle-prediction-comparison-unavailable.v1",
            "reason_code": "comparison_resource_bound",
            "probe_digest": probe,
        }
    measured = inference.receipt.get("measurement", {})
    dtype = measured.get("output_dtype", expected_output_dtype)
    if dtype is None:
        return {
            "schema": "carbon.development.bundle-prediction-comparison-unavailable.v1",
            "reason_code": "lowered_dtype_unavailable",
            "probe_digest": probe,
        }
    if not _exact_numeric_dtype(dtype, dtype):
        raise ValueError("lowered prediction dtype differs")
    from .bundle_prediction_comparison import compare_native_lowered_predictions

    return compare_native_lowered_predictions(
        native=native,
        lowered=np.asarray(inference.predictions, dtype=np.dtype(dtype)),
        native_identity={
            "recipe_digest": build.recipe_digest,
            "state_digest": build.state_digest,
            "probe_digest": probe,
        },
        lowered_identity={
            "recipe_digest": inference.recipe_digest,
            "state_digest": inference.state_digest,
            "probe_digest": inference.receipt["inputs_digest"],
        },
    )


@dataclass(frozen=True)
class BundleBuildResult:
    recipe_digest: str
    state_digest: str
    state_path: Path
    worker_operation: str
    receipt: dict


def reconstruct_public(
    ledger,
    *,
    owner: str,
    identity: str,
    image: LibraryWorkerImage | VerifiedLibraryOverlay,
    construction_parent=None,
    recipe: ConstructionRecipe,
    challenge_binding: dict,
    train: bytes,
    example: np.ndarray,
    seed: int,
    allowlist_bytes: bytes,
    limits_document: dict | None = None,
    seconds: int = 600,
    accelerator: str | None = None,
    runner=None,
) -> BundleBuildResult:
    """Run an exact source entrypoint only in the provisioned child worker."""
    from carbon.reconstruction.worker.model import WorkerImageIdentity

    overlay = image if type(image) is VerifiedLibraryOverlay else None
    accelerator_kwargs = _accelerator_kwargs(accelerator)
    if accelerator_kwargs and overlay is None:
        # A library child has no WorkerImageIdentity lock/profile fields. GPU
        # checks must use the exact pinned parent plus its verified overlay.
        raise RecipeRefused("bundle_gpu_overlay_required")
    image_ref = (
        overlay.bundle_ref.to_dict() if overlay is not None else image.bundle_ref
    )
    worker_image = construction_parent if overlay is not None else image
    if (
        (
            overlay is None
            and (
                type(image) is not LibraryWorkerImage
                or image.provisioned.bundle != LibraryBundleRef.from_dict(image_ref)
            )
        )
        or (
            overlay is not None
            and (
                type(construction_parent) is not WorkerImageIdentity
                or overlay.parent_image_id != construction_parent.image_id
            )
        )
        or type(recipe) is not ConstructionRecipe
        or recipe.to_dict()["source"]["kind"] != "bundle"
        or recipe.to_dict()["output"]["format"] != "carbon.numeric-graph.v1"
        or image_ref != recipe.to_dict()["source"]["bundle_ref"]
        or type(seed) is not int
        or seed < 0
        or type(train) is not bytes
        or not 0 < len(train) <= MAX_STATE_BYTES
        or _digest(train) != recipe.to_dict()["challenge"]["train_digest"]
        or type(allowlist_bytes) is not bytes
        or not 0 < len(allowlist_bytes) <= 1024**2
    ):
        raise RecipeRefused("bundle_build_binding_invalid")
    binding = _checked_binding(recipe, challenge_binding)
    allowed = _trusted_allowlist(allowlist_bytes)
    resources_version = worker_resources_version(allowed.version)
    if limits_document is not None:
        verify_direct_resource_policy(binding, limits_document, resources_version)
    example_bytes = _tensors(inputs=example)
    files, codec_modules = _stage_bundle_modules(binding, training=True)
    from carbon.reconstruction.capability_registry import BATTERY_CHALLENGE

    train_name = (
        "train.gz" if binding["challenge_id"] == BATTERY_CHALLENGE else "train.npz"
    )
    files.update(
        {
            "recipe.json": recipe.canonical_bytes,
            train_name: train,
            "example.npz": example_bytes,
            "allowlist.json": allowlist_bytes,
            "control.json": json.dumps(
                {
                    "recipe_digest": recipe.digest,
                    "bundle_ref": image_ref,
                    **(
                        {"overlay_tree_digest": overlay.tree_digest}
                        if overlay is not None
                        else {}
                    ),
                    "binding": binding,
                    "codec_modules": codec_modules,
                    "example_digest": _digest(example_bytes),
                    "allowlist_digest": allowed.digest,
                    "seed": seed,
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode(),
        }
    )

    def checked(snapshot: Path):
        if {path.name for path in snapshot.iterdir()} == {"refusal.json"}:
            # A closed refusal of the candidate's graph; anything not exactly
            # that stays a validation failure, never a candidate verdict.
            refusal = snapshot / "refusal.json"
            if (
                refusal.is_symlink()
                or not refusal.is_file()
                or build_refusal.parse(refusal.read_bytes()) is None
            ):
                raise ValueError("bundle build refusal malformed")
            return None, None
        if {path.name for path in snapshot.iterdir()} != {
            "state.npz",
            "receipt.json",
            "native-predictions.json",
        }:
            raise ValueError("bundle build output set differs")
        for name, ceiling in (
            # The state's ceiling is the allowlist version's (none when
            # uncapped: the worker's output envelope already bounded it).
            ("state.npz", state_limit(allowed)),
            ("receipt.json", 65536),
            ("native-predictions.json", 16 * 1024**2),
        ):
            path = snapshot / name
            if (
                path.is_symlink()
                or not path.is_file()
                or not 0 < path.stat().st_size
                or (ceiling is not None and path.stat().st_size > ceiling)
            ):
                raise ValueError("bounded bundle build output required")
        state = (snapshot / "state.npz").read_bytes()
        receipt_raw = (snapshot / "receipt.json").read_bytes()
        try:
            receipt = parse_strategy(receipt_raw, max_bytes=65536)
        except MalformedStrategy:
            raise ValueError("bundle build receipt malformed") from None
        if receipt != {
            "schema": "carbon.development.bundle-build.v2",
            "example_digest": _digest(example_bytes),
            "native_predictions_digest": _digest(
                (snapshot / "native-predictions.json").read_bytes()
            ),
            "native_dtype": receipt.get("native_dtype"),
            "native_shape": receipt.get("native_shape"),
            "recipe_digest": recipe.digest,
            "bundle_digest": image_ref["bundle_digest"],
            "train_digest": binding["train_digest"],
            "state_digest": _digest(state),
            "allowlist_digest": allowed.digest,
            "framework": receipt.get("framework"),
        } or receipt["framework"] not in ("jax", "torch"):
            raise ValueError("bundle build receipt identity differs")
        native_build_predictions(
            BundleBuildResult(
                recipe.digest, _digest(state), snapshot / "state.npz", "", receipt
            )
        )
        return state, receipt

    worker = (runner or _run)(
        ledger,
        owner=owner,
        identity=identity,
        source=BUILD_PROGRAM,
        files=files,
        image=worker_image,
        seconds=seconds,
        provenance=(
            LIBRARY_OVERLAY_BUILD_PROVENANCE
            if overlay is not None
            else LIBRARY_BUILD_PROVENANCE
        ),
        extra_resources=(
            {} if PRECHARGED_TRIAL.get() is not None else {"research_trials": 1}
        ),
        output_validator=checked,
        **accelerator_kwargs,
        **(
            {"trusted_overlay": overlay, "bootstrap": OVERLAY_BUILD_BOOTSTRAP}
            if overlay is not None
            else {}
        ),
        **(
            {}
            if resources_version is None
            else {"worker_resources_version": resources_version}
        ),
    )
    snapshot = ledger.root / worker["operation"] / "snapshot"
    state, receipt = checked(snapshot)
    if state is None:
        refusal = snapshot / "refusal.json"
        if _digest(refusal.read_bytes()) != worker["files"].get("refusal.json"):
            raise ValueError("bundle build output custody differs")
        code, at = build_refusal.parse(refusal.read_bytes())
        raise CandidateBuildRefused(code, at)
    if any(
        _digest((snapshot / name).read_bytes()) != worker["files"].get(name)
        for name in ("state.npz", "receipt.json", "native-predictions.json")
    ):
        raise ValueError("bundle build output custody differs")
    return BundleBuildResult(
        recipe.digest,
        _digest(state),
        snapshot / "state.npz",
        worker["operation"],
        receipt,
    )


@dataclass(frozen=True)
class BundleInferenceResult:
    recipe_digest: str
    state_digest: str
    predictions_digest: str
    predictions: list
    worker_operation: str
    receipt: dict


def infer_public(
    ledger,
    *,
    owner: str,
    identity: str,
    image: LibraryWorkerImage | VerifiedLibraryOverlay,
    inference_image,
    recipe: ConstructionRecipe,
    challenge_binding: dict,
    build: BundleBuildResult,
    inputs: np.ndarray,
    expected_output_shape: tuple[int, ...],
    allowlist_bytes: bytes,
    limits_document: dict | None = None,
    expected_output_dtype: str | None = None,
    measure_query: bool = False,
    seconds: int = 600,
    accelerator: str | None = None,
    runner=None,
) -> BundleInferenceResult:
    """Reopen inert state in the base C-03 image with input-only tensors."""
    from carbon.reconstruction.worker.model import WorkerImageIdentity

    if measure_query and (
        type(expected_output_dtype) is not str or not expected_output_dtype
    ):
        raise RecipeRefused("measured_output_dtype_unregistered")
    if type(build) is not BundleBuildResult:
        raise RecipeRefused("bundle_inference_custody_invalid")
    expected = ledger.root / build.worker_operation / "snapshot" / "state.npz"
    image_ref = (
        image.bundle_ref.to_dict()
        if type(image) is VerifiedLibraryOverlay
        else image.bundle_ref
    )
    if (
        type(image) not in (LibraryWorkerImage, VerifiedLibraryOverlay)
        or type(inference_image) is not WorkerImageIdentity
        or type(recipe) is not ConstructionRecipe
        or recipe.to_dict()["source"]["kind"] != "bundle"
        or image_ref != recipe.to_dict()["source"]["bundle_ref"]
        or recipe.to_dict()["output"]["format"] != "carbon.numeric-graph.v1"
        or build.recipe_digest != recipe.digest
        or build.state_path != expected
        or expected.is_symlink()
        or not expected.is_file()
        or type(allowlist_bytes) is not bytes
        or not 0 < len(allowlist_bytes) <= 1024**2
        or not state_fits(expected.stat().st_size, allowlist_bytes)
        or type(expected_output_shape) is not tuple
        or not expected_output_shape
        or any(type(n) is not int or n < 1 for n in expected_output_shape)
    ):
        raise RecipeRefused("bundle_inference_custody_invalid")
    state = expected.read_bytes()
    binding = _checked_binding(recipe, challenge_binding)
    if limits_document is not None:
        verify_direct_resource_policy(
            binding,
            limits_document,
            worker_resources_version(_trusted_allowlist(allowlist_bytes).version),
        )
    if _digest(state) != build.state_digest:
        raise RecipeRefused("bundle_inference_state_changed")
    return _infer_state(
        ledger,
        owner=owner,
        identity=identity,
        inference_image=inference_image,
        recipe=recipe,
        binding=binding,
        state=state,
        state_digest=build.state_digest,
        inputs=inputs,
        expected_output_shape=expected_output_shape,
        expected_output_dtype=expected_output_dtype,
        measure_query=measure_query,
        allowlist_bytes=allowlist_bytes,
        seconds=seconds,
        **_accelerator_kwargs(accelerator),
        runner=runner,
    )


def infer_saved_bundle(
    ledger,
    *,
    owner: str,
    identity: str,
    image: LibraryWorkerImage,
    inference_image,
    recipe: ConstructionRecipe,
    challenge_binding: dict,
    state_bytes: bytes,
    expected_state_digest: str,
    inputs: np.ndarray,
    expected_input_shape: tuple[int, ...],
    expected_input_dtype: str,
    expected_output_shape: tuple[int, ...],
    expected_output_dtype: str,
    allowlist_bytes: bytes,
    limits_document: dict | None = None,
    seconds: int = 600,
    accelerator: str | None = None,
    runner=None,
) -> BundleInferenceResult:
    """Infer from a separately validated saved graph; never stage source or TRAIN.

    The caller owns bank-entry/custody validation and the trusted image resolver.
    An injected runner supplies TEST_ONLY evidence, not an isolated C-03 run.
    This result has no per-query latency or peak-memory measurement.
    """
    from carbon.reconstruction.worker.model import WorkerImageIdentity

    if (
        type(image) is not LibraryWorkerImage
        or type(inference_image) is not WorkerImageIdentity
        or type(recipe) is not ConstructionRecipe
        or recipe.to_dict()["source"]["kind"] != "bundle"
        or image.bundle_ref != recipe.to_dict()["source"]["bundle_ref"]
        or recipe.to_dict()["output"]["format"] != "carbon.numeric-graph.v1"
        or type(state_bytes) is not bytes
        or type(expected_state_digest) is not str
        or type(allowlist_bytes) is not bytes
        or not 0 < len(allowlist_bytes) <= 1024**2
        or not state_fits(len(state_bytes), allowlist_bytes)
    ):
        raise RecipeRefused("saved_bundle_inference_binding_invalid")
    if _digest(state_bytes) != expected_state_digest:
        raise RecipeRefused("saved_bundle_inference_state_changed")
    binding = _checked_binding(recipe, challenge_binding)
    allowed = _trusted_allowlist(allowlist_bytes)
    if limits_document is not None:
        verify_direct_resource_policy(
            binding, limits_document, worker_resources_version(allowed.version)
        )
    from .bundle_graph_state import load

    load(state_bytes, recipe, allowed)
    if (
        type(inputs) is not np.ndarray
        or type(expected_input_shape) is not tuple
        or not expected_input_shape
        or any(type(n) is not int or n < 1 for n in expected_input_shape)
        or inputs.shape != expected_input_shape
        or type(expected_output_shape) is not tuple
        or not expected_output_shape
        or any(type(n) is not int or n < 1 for n in expected_output_shape)
        or not _exact_numeric_dtype(inputs.dtype, expected_input_dtype)
        or not _exact_numeric_dtype(expected_output_dtype, expected_output_dtype)
    ):
        raise RecipeRefused("saved_bundle_inference_tensor_contract_invalid")
    return _infer_state(
        ledger,
        owner=owner,
        identity=identity,
        inference_image=inference_image,
        recipe=recipe,
        binding=binding,
        state=state_bytes,
        state_digest=expected_state_digest,
        inputs=inputs,
        expected_output_shape=expected_output_shape,
        expected_output_dtype=expected_output_dtype,
        allowlist_bytes=allowlist_bytes,
        measure_query=True,
        seconds=seconds,
        **_accelerator_kwargs(accelerator),
        runner=runner,
    )


def _exact_numeric_dtype(actual, expected: str) -> bool:
    if type(expected) is not str:
        return False
    try:
        dtype = np.dtype(expected)
        return dtype.kind in "fiu" and dtype == np.dtype(actual)
    except (TypeError, ValueError):
        return False


def _infer_state(
    ledger,
    *,
    owner: str,
    identity: str,
    inference_image,
    recipe: ConstructionRecipe,
    binding: dict,
    state: bytes,
    state_digest: str,
    inputs: np.ndarray,
    expected_output_shape: tuple[int, ...],
    allowlist_bytes: bytes,
    expected_output_dtype: str | None = None,
    measure_query: bool = False,
    per_case: bool = True,
    input_name: str = "inputs/x",
    provenance: str = "DIRECT_BUNDLE_PUBLIC_INFERENCE",
    seconds: int = 600,
    accelerator: str | None = None,
    runner=None,
    program: str | None = None,
    staged_files: dict[str, bytes] | None = None,
) -> BundleInferenceResult:
    """`program` and `staged_files` serve a graph adapter's own inference
    program and its extra trusted modules (`direct_graph_construction_worker`).
    Omitted, this is the plain inference program."""
    if provenance not in (
        "DIRECT_BUNDLE_PUBLIC_INFERENCE",
        "DIRECT_GRAPH_PUBLIC_INFERENCE",
    ):
        raise RecipeRefused("direct_inference_provenance_invalid")
    allowed = _trusted_allowlist(allowlist_bytes)
    inputs_bytes = _tensors(inputs=inputs)
    files, codec_modules = _stage_bundle_modules(binding, training=False)
    if staged_files is not None:
        if any(name in files for name in staged_files):
            raise RecipeRefused("bundle_worker_module_closure_changed")
        files.update(staged_files)
    control = {
        "recipe_digest": recipe.digest,
        "binding": binding,
        "codec_modules": codec_modules,
        "state_digest": state_digest,
        "inputs_digest": _digest(inputs_bytes),
        "allowlist_digest": allowed.digest,
        "expected_output_shape": list(expected_output_shape),
    }
    if expected_output_dtype is not None:
        control["expected_output_dtype"] = expected_output_dtype
    if measure_query:
        control["measure_query"] = True
    if measure_query or not per_case:
        # The measured query is the batched cold query kept only for timing; the
        # graded query runs one case at a time (the program's default).
        control["per_case"] = False
    if input_name != "inputs/x":
        if input_name not in ("inputs/forcing", "inputs/features"):
            raise RecipeRefused("direct_inference_input_name_invalid")
        control["input_name"] = input_name
    files.update(
        {
            "recipe.json": recipe.canonical_bytes,
            "state.npz": state,
            "inputs.npz": inputs_bytes,
            "allowlist.json": allowlist_bytes,
            "control.json": json.dumps(
                control, sort_keys=True, separators=(",", ":")
            ).encode(),
        }
    )
    if "train.npz" in files or "train.gz" in files or "source.tar.gz" in files:
        raise ValueError("inference stage contains construction material")

    def checked(snapshot: Path):
        if {path.name for path in snapshot.iterdir()} != {
            "predictions.json",
            "receipt.json",
        }:
            raise ValueError("bundle inference output set differs")
        for name, ceiling in (
            ("predictions.json", 16 * 1024**2),
            ("receipt.json", 65536),
        ):
            path = snapshot / name
            if (
                path.is_symlink()
                or not path.is_file()
                or not 0 < path.stat().st_size <= ceiling
            ):
                raise ValueError("bounded bundle inference output required")
        raw = (snapshot / "predictions.json").read_bytes()
        receipt_raw = (snapshot / "receipt.json").read_bytes()
        try:
            predictions = json.loads(raw)
            receipt = parse_strategy(receipt_raw, max_bytes=65536)
        except (ValueError, MalformedStrategy):
            raise ValueError("bundle inference output malformed") from None
        expected_receipt = {
            "schema": (
                "carbon.development.bundle-inference.v2"
                if measure_query
                else "carbon.development.bundle-inference.v1"
            ),
            "recipe_digest": recipe.digest,
            "state_digest": state_digest,
            "inputs_digest": _digest(inputs_bytes),
            "predictions_digest": _digest(raw),
        }
        if measure_query:
            measured = receipt.get("measurement")
            if (
                type(measured) is not dict
                or set(measured)
                != {
                    "scope",
                    "timing_s",
                    "input_shape",
                    "input_dtype",
                    "output_shape",
                    "output_dtype",
                }
                or measured["scope"]
                != "COLD_SINGLE_WORKER_QUERY_INCLUDES_GRAPH_LOAD_AND_JAX_COMPILE"
                or measured["input_shape"] != list(inputs.shape)
                or measured["input_dtype"] != str(inputs.dtype)
                or measured["output_shape"] != list(expected_output_shape)
                or not _exact_numeric_dtype(
                    measured["output_dtype"], expected_output_dtype
                )
                or type(measured["timing_s"]) is not dict
                or set(measured["timing_s"])
                != {"preprocess", "inference", "postprocess", "export"}
                or any(
                    type(value) not in (int, float)
                    or not math.isfinite(value)
                    or value < 0
                    for value in measured["timing_s"].values()
                )
                or sum(measured["timing_s"].values()) <= 0
            ):
                raise ValueError("bundle inference measurement differs")
            expected_receipt["measurement"] = measured
        if type(predictions) is not list or receipt != expected_receipt:
            raise ValueError("bundle inference output identity differs")
        return raw, predictions, receipt

    worker = (runner or _run)(
        ledger,
        owner=owner,
        identity=identity,
        source=INFER_PROGRAM if program is None else program,
        files=files,
        image=inference_image,
        seconds=seconds,
        provenance=provenance,
        extra_resources=(
            {} if PRECHARGED_TRIAL.get() is not None else {"research_trials": 1}
        ),
        output_validator=checked,
        **_accelerator_kwargs(accelerator),
        # A model built under a next version's larger resources is loaded
        # and run under them too.
        **(
            {}
            if worker_resources_version(allowed.version) is None
            else {"worker_resources_version": allowed.version}
        ),
    )
    snapshot = ledger.root / worker["operation"] / "snapshot"
    raw, predictions, receipt = checked(snapshot)
    if any(
        _digest((snapshot / name).read_bytes()) != worker["files"].get(name)
        for name in ("predictions.json", "receipt.json")
    ):
        raise ValueError("bundle inference output custody differs")
    return BundleInferenceResult(
        recipe.digest,
        state_digest,
        _digest(raw),
        predictions,
        worker["operation"],
        receipt,
    )


@dataclass(frozen=True)
class DirectReconstructionResult:
    """Private two-stage result; injected runners are test-only evidence."""

    build: BundleBuildResult
    inference: BundleInferenceResult
    policy_digest: str
    execution_boundary: str
    build_controls_digest: str | None
    inference_controls_digest: str | None
    elapsed_seconds: float
    prediction_comparison: dict | None = None
    #: The batched cold query kept for timing when the task is measured.
    timed: BundleInferenceResult | None = None


def _private_controls_digest(
    ledger, *, owner: str, identity: str, operation: str, provenance: str
) -> str:
    """Bind a settled real C-03 operation and its effective control record."""
    if (
        type(operation) is not str
        or re.fullmatch(r"operation-[0-9a-f]{64}", operation) is None
    ):
        raise RecipeRefused("bundle_controls_unavailable")
    operation_root = ledger.root / operation
    if operation_root.is_symlink() or not operation_root.is_dir():
        raise RecipeRefused("bundle_controls_unavailable")
    path = operation_root / "resources.json"
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 1024**2:
        raise RecipeRefused("bundle_controls_unavailable")
    raw = path.read_bytes()
    try:
        observed = json.loads(raw)
    except ValueError:
        raise RecipeRefused("bundle_controls_unavailable") from None
    if (
        type(observed) is not dict
        or type(observed.get("controls")) is not dict
        or type(observed.get("controls_digest")) is not str
        or type(observed.get("resources")) is not dict
        or observed["controls_digest"] != _digest(canonical(observed["controls"]))
    ):
        raise RecipeRefused("bundle_controls_unavailable")
    with ledger.db() as db:
        row = db.execute(
            "SELECT state,result FROM operations WHERE id=? AND owner=?",
            (identity, owner),
        ).fetchone()
    if row is None or row[0] != "SUCCEEDED":
        raise RecipeRefused("bundle_controls_unavailable")
    try:
        result = json.loads(row[1])
    except (TypeError, ValueError):
        raise RecipeRefused("bundle_controls_unavailable") from None
    if (
        type(result) is not dict
        or result.get("schema") != "carbon.autoresearch.worker-result.v1"
        or result.get("operation") != operation
        or result.get("provenance") != provenance
        or result.get("scientific_qualification") is not False
        or result.get("official_eligible") is not False
    ):
        raise RecipeRefused("bundle_controls_unavailable")
    return _digest(raw)


def direct_child_identity(identity: str, phase: str) -> str:
    """Derive bounded, distinct ledger identities for a direct task's phases."""
    if (
        type(identity) is not str
        or not identity
        or phase
        not in (
            "prep",
            "build",
            "inference",
            "timed",
        )
    ):
        raise RecipeRefused("bundle_child_identity_invalid")
    return (
        "direct-" + hashlib.sha256(identity.encode("utf-8")).hexdigest() + "-" + phase
    )


def reconstruct_and_infer_public(
    ledger,
    *,
    owner: str,
    identity: str,
    image: LibraryWorkerImage | VerifiedLibraryOverlay,
    inference_image,
    construction_parent=None,
    recipe: ConstructionRecipe,
    challenge_binding: dict,
    limits_document: dict,
    train: bytes,
    example: np.ndarray,
    seed: int,
    inputs: np.ndarray,
    expected_output_shape: tuple[int, ...],
    allowlist_bytes: bytes,
    expected_output_dtype: str | None = None,
    measure_query: bool = False,
    total_deadline_started: float | None = None,
    accelerator: str | None = None,
    inference_accelerator: str | None = None,
    runner=None,
) -> DirectReconstructionResult:
    """Fresh build and source-free inference under the fixture's finite policy.

    Both carrier calls confirm cleanup before returning. Each phase gets at
    most its registered wall allowance and at most the remaining aggregate
    allowance. A checked caller selects the construction and inference controls
    independently from their pinned images; this route never infers GPU
    permission from the bundle's runtime label.
    A test runner proves bytes and custody, never C-03 isolation.
    """
    binding = _checked_binding(recipe, challenge_binding)
    policy_digest = verify_direct_resource_policy(
        binding,
        limits_document,
        worker_resources_version(_trusted_allowlist(allowlist_bytes).version),
    )
    policy = limits_document["reconstruction_resource_policy"]
    now = time.monotonic()
    if total_deadline_started is not None and (
        type(total_deadline_started) is not float
        or not 0 < total_deadline_started <= now
    ):
        raise RecipeRefused("construction_total_deadline_invalid")
    started = now if total_deadline_started is None else total_deadline_started
    deadline = started + policy["total_reconstruction_wall_seconds_max"]
    build_identity = direct_child_identity(identity, "build")
    inference_identity = direct_child_identity(identity, "inference")

    def phase_seconds(name: str) -> int:
        remaining = int(deadline - time.monotonic())
        if remaining < 40:
            raise RecipeRefused("construction_total_deadline_reached")
        return min(policy[name], remaining)

    build = reconstruct_public(
        ledger,
        owner=owner,
        identity=build_identity,
        image=image,
        construction_parent=construction_parent,
        recipe=recipe,
        challenge_binding=binding,
        train=train,
        example=example,
        seed=seed,
        allowlist_bytes=allowlist_bytes,
        limits_document=limits_document,
        seconds=phase_seconds("build_wall_seconds_max"),
        **_accelerator_kwargs(accelerator),
        runner=runner,
    )
    inference = infer_public(
        ledger,
        owner=owner,
        identity=inference_identity,
        image=image,
        inference_image=inference_image,
        recipe=recipe,
        challenge_binding=binding,
        build=build,
        inputs=inputs,
        expected_output_shape=expected_output_shape,
        expected_output_dtype=expected_output_dtype,
        allowlist_bytes=allowlist_bytes,
        limits_document=limits_document,
        seconds=phase_seconds("inference_wall_seconds_max"),
        **_accelerator_kwargs(inference_accelerator),
        runner=runner,
    )
    timed = (
        infer_public(
            ledger,
            owner=owner,
            identity=direct_child_identity(identity, "timed"),
            image=image,
            inference_image=inference_image,
            recipe=recipe,
            challenge_binding=binding,
            build=build,
            inputs=inputs,
            expected_output_shape=expected_output_shape,
            expected_output_dtype=expected_output_dtype,
            measure_query=True,
            allowlist_bytes=allowlist_bytes,
            limits_document=limits_document,
            seconds=phase_seconds("inference_wall_seconds_max"),
            **_accelerator_kwargs(inference_accelerator),
            runner=runner,
        )
        if measure_query
        else None
    )
    elapsed = time.monotonic() - started
    if elapsed > policy["total_reconstruction_wall_seconds_max"]:
        raise RecipeRefused("construction_total_deadline_reached")
    if build.state_digest != inference.state_digest or (
        timed is not None and timed.state_digest != build.state_digest
    ):
        raise RecipeRefused("bundle_inference_custody_invalid")
    comparison = compare_build_inference_predictions(
        build, inference, expected_output_dtype=expected_output_dtype
    )
    elapsed = time.monotonic() - started
    if elapsed > policy["total_reconstruction_wall_seconds_max"]:
        raise RecipeRefused("construction_total_deadline_reached")
    controls = (
        (
            _private_controls_digest(
                ledger,
                owner=owner,
                identity=build_identity,
                operation=build.worker_operation,
                provenance=(
                    LIBRARY_OVERLAY_BUILD_PROVENANCE
                    if type(image) is VerifiedLibraryOverlay
                    else LIBRARY_BUILD_PROVENANCE
                ),
            ),
            _private_controls_digest(
                ledger,
                owner=owner,
                identity=inference_identity,
                operation=inference.worker_operation,
                provenance="DIRECT_BUNDLE_PUBLIC_INFERENCE",
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
        comparison,
        timed,
    )
