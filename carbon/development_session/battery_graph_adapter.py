"""Battery's graph training adapter (the Validator's ruling (a), 2026-10-22).

The receiver's one graph path (`direct_graph_construction_worker`) runs a
Challenge version's registered graph adapter. F08 1.4 and F02 2.3 have
`physical_graph_adapter` (float32 npz TRAIN, Carbon's pinned trainer). Battery
2.2 has this one: float64 gzip-JSON-lines TRAIN, and Battery's own registered
graph training, the route Battery 2.1 practises locally
(`battery.direct_graph_worker` / `direct_graph_inference`). Neither the F08/F02
adapter and trainer nor any pinned Battery module is edited: Battery's
modules are staged unchanged (`direct_graph_worker.BATTERY_MODULES`) and their
bytes are named in the adapter block, so a change to them is a new identity.

A 2.2 recipe binds 2.2's served kit. Its graph is trained exactly as the base
version's graph route trains it: the recipe re-keyed to the base version's
graph kit (`base_recipe`), its settings resolved by Battery's
`direct_graph.training_settings`, the base version's v7 allowlist and graph
limits. So a graph practised through the old 2.1 local path and through this
adapter gives the same model and the same grades. Inference reopens the inert
state in a separate child and predicts one isolated case per call; outputs are
the served interface's float64 rows.

A refusal the host's settings resolution raises is not raised on the host: it
is staged, and the build child settles it with `build_refusal`'s classes, as
the F08/F02 adapter's in-worker refusals are. Nothing here is an evaluation,
a qualification or LIVE authority.
"""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path

from .construction_recipe import ConstructionRecipe, RecipeRefused

ADAPTER_SCHEMA = "carbon.battery-graph-training-adapter.v1"
PROCEDURE_SCHEMA = "carbon.construction-recipe.v1"
STATE_SCHEMA = "carbon.battery.direct-graph-state.v1"
INPUT_NAME = "inputs/features"
OUTPUT_DTYPE = "float64"
TRAIN_NAME = "train-v1.jsonl.gz"
REPOSITORY = Path(__file__).resolve().parents[2]
BATTERY_CHALLENGE = "battery-fastcharge-ageing-development-v1"


@dataclass(frozen=True)
class Spec:
    challenge_id: str
    version: str
    #: The Battery version whose graph route this version serves unchanged.
    base: str
    adapter_id: str
    rows: int
    inputs: int
    outputs: int


#: The served graph versions (the Validator, 2026-10-22: Battery 2.2, on 2.1's
#: graph route).
SPECS = {
    (BATTERY_CHALLENGE, "2.2"): Spec(
        BATTERY_CHALLENGE,
        "2.2",
        "2.1",
        "battery-fastcharge-ageing-public-jax-graph-v1",
        400,
        4,
        247,
    ),
}
ADAPTER_IDS = frozenset(spec.adapter_id for spec in SPECS.values())


def spec_for(challenge_id: str, version: str) -> Spec:
    spec = SPECS.get((challenge_id, version))
    if spec is None:
        if challenge_id != BATTERY_CHALLENGE:
            raise RecipeRefused("construction_recipe_challenge_invalid")
        raise RecipeRefused("battery_graph_challenge_version_unregistered")
    return spec


def spec_for_adapter(adapter_id: str) -> Spec | None:
    for spec in SPECS.values():
        if spec.adapter_id == adapter_id:
            return spec
    return None


def base_kit(spec: Spec) -> dict:
    """The base version's five-field graph kit."""
    from carbon.battery import construction_kit

    return construction_kit.construction_kit_for(spec.base)


def base_recipe(recipe: ConstructionRecipe) -> ConstructionRecipe:
    """`recipe` re-keyed to its base version's graph kit: only `challenge`
    and `output.interface_digest` change."""
    if type(recipe) is not ConstructionRecipe:
        raise RecipeRefused("construction_recipe_malformed")
    doc = recipe.to_dict()
    spec = spec_for(doc["challenge"]["id"], doc["challenge"]["version"])
    kit = base_kit(spec)
    return ConstructionRecipe.from_dict(
        {
            **doc,
            "challenge": kit,
            "output": {**doc["output"], "interface_digest": kit["interface_digest"]},
        }
    )


def training_settings(recipe: ConstructionRecipe) -> dict:
    """The recipe's resolved settings on its base version's graph route
    (`battery.direct_graph.training_settings`), or its closed refusal."""
    from carbon.battery import direct_graph

    return direct_graph.training_settings(base_recipe(recipe))


def served_allowlist_bytes(challenge_id: str, version: str) -> bytes:
    """The version's served graph allowlist; the base version's (v7)."""
    from carbon.battery import direct_graph
    from carbon.challenge_kit.served_versions import graph_allowlist_bytes
    from carbon.level4.allowlist import Allowlist

    spec = spec_for(challenge_id, version)
    raw = graph_allowlist_bytes(challenge_id, version)
    if Allowlist(raw).digest != direct_graph.graph_allowlist(spec.base).digest:
        raise ValueError("Battery graph allowlist differs from its base version's")
    return raw


def module_digests() -> dict:
    """Battery's staged training modules, by their exact bytes."""
    from carbon.battery import direct_graph_worker

    folder = REPOSITORY / "carbon" / "battery"
    return {
        module: "sha256:" + hashlib.sha256((folder / module).read_bytes()).hexdigest()
        for module in sorted(direct_graph_worker.BATTERY_MODULES.values())
    }


def adapter_block(challenge_id: str, version: str) -> dict:
    """The `graph_training_adapter` block of a served version's limits."""
    from carbon.battery import challenge, construction_kit, direct_graph
    from carbon.reconstruction.capability_registry import catalog_surfaces

    spec = spec_for(challenge_id, version)
    limits = construction_kit.construction_limits_document_for(spec.base)
    surfaces = catalog_surfaces(BATTERY_CHALLENGE, spec.base)
    return {
        "schema": ADAPTER_SCHEMA,
        "id": spec.adapter_id,
        "source_kind": "graph",
        "base_version": spec.base,
        "base_kit": base_kit(spec),
        "train_use_dataset": direct_graph.TRAIN_USE,
        "train_use_fields": ["curriculum", "dataset", "train_fraction"],
        "train_use_default": {
            "dataset": direct_graph.TRAIN_USE,
            "train_fraction": surfaces["train_fraction"][4],
            "curriculum": surfaces["curriculum"][4],
        },
        "procedure_schema": PROCEDURE_SCHEMA,
        "output_format": direct_graph.OUTPUT_FORMAT,
        "state_schema": STATE_SCHEMA,
        "interface": {
            "input": INPUT_NAME,
            "graph_dtype": "the precision training surface",
            "output_dtype": OUTPUT_DTYPE,
            "input_shape": [spec.inputs],
            "output_shape": [spec.outputs],
        },
        # The base version's graph route, unchanged: its surfaces, caps and
        # intake bounds (v7) and its training limit.
        "graph_limits": {
            name: limits[name]
            for name in (
                "train_surfaces",
                "graph_caps",
                "graph_intake",
                "training_step_cap",
                "training_limit",
            )
        },
        "train_sha256": "sha256:" + challenge.TRAIN_V1_SHA256,
        "trainer": {
            "modules": module_digests(),
            "settings": "battery.direct_graph.training_settings on the base version",
        },
        "inference": "one_isolated_case_per_call",
        "value_status": "DEVELOPMENT",
    }


# --- Host stage (never called inside a worker) ---------------------------------------


def _modules(names) -> dict:
    return {
        name + ".py": (REPOSITORY / (name.replace(".", "/") + ".py")).read_bytes()
        for name in names
    }


def _battery_files(spec: Spec) -> dict:
    from carbon.battery import direct_graph_worker

    folder = REPOSITORY / "carbon" / "battery"
    return {
        **{
            staged: (folder / module).read_bytes()
            for staged, module in direct_graph_worker.BATTERY_MODULES.items()
        },
        **direct_graph_worker.staged_allowlists(spec.base),
    }


def _canonical(value) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def _digest(body: bytes) -> str:
    return "sha256:" + hashlib.sha256(body).hexdigest()


def _control(spec: Spec, base: ConstructionRecipe, settings_raw: bytes | None, refusal):
    from carbon.battery import direct_graph_worker

    return {
        "base_kit": base_kit(spec),
        "base_recipe_digest": base.digest,
        "settings_digest": None if settings_raw is None else _digest(settings_raw),
        "refusal": refusal,
        "train_cases": spec.rows,
        "max_state_bytes": direct_graph_worker.state_bytes_for(spec.base),
    }


#: The build child's Carbon modules: Battery's graph worker's, plus the
#: refusal classes it settles a refusal with.
BUILD_MODULES = (
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
    "carbon.development_session.build_refusal",
)


def build_stage(
    binding: dict, limits_document: dict, allowlist_bytes: bytes, recipe
) -> tuple[Spec, dict]:
    """Check the served identity; return the build child's extra files."""
    from carbon.battery import challenge

    spec = spec_for(binding["challenge_id"], binding["challenge_version"])
    if limits_document.get("graph_training_adapter") != adapter_block(
        spec.challenge_id, spec.version
    ):
        raise RecipeRefused("direct_graph_adapter_identity_invalid")
    if allowlist_bytes != served_allowlist_bytes(spec.challenge_id, spec.version):
        raise RecipeRefused("direct_graph_allowlist_unregistered")
    if binding["train_digest"] != "sha256:" + challenge.TRAIN_V1_SHA256:
        raise RecipeRefused("direct_graph_train_binding_invalid")
    base = base_recipe(recipe)
    try:
        settings_raw, refusal = _canonical(training_settings(recipe)), None
    except RecipeRefused as refused:
        settings_raw, refusal = None, refused.code
    files = {
        **_modules(BUILD_MODULES),
        **_battery_files(spec),
        "base-recipe.json": base.canonical_bytes,
        "battery-control.json": _canonical(_control(spec, base, settings_raw, refusal)),
    }
    if settings_raw is not None:
        files["settings.json"] = settings_raw
    return spec, files


def inference_files(binding: dict, recipe: ConstructionRecipe) -> dict:
    """The inference child's extra files, beside the plain inference stage
    (`bundle_construction_worker._infer_state`), which they never overwrite."""
    from carbon.battery import direct_graph_worker

    from .bundle_construction_worker import _stage_bundle_modules

    spec = spec_for(binding["challenge_id"], binding["challenge_version"])
    base = base_recipe(recipe)
    settings_raw = _canonical(training_settings(recipe))
    plain, _codec = _stage_bundle_modules(binding, training=False)
    modules = _modules(
        name for name in direct_graph_worker.STAGED_MODULES if name + ".py" not in plain
    )
    return {
        **modules,
        **_battery_files(spec),
        "base-recipe.json": base.canonical_bytes,
        "settings.json": settings_raw,
        "battery-control.json": _canonical(_control(spec, base, settings_raw, None)),
    }


def check_state(state: bytes, recipe: ConstructionRecipe) -> None:
    """The host's check of a built state's identity (the inference child
    revalidates the graph and every array before use)."""
    from carbon.challenge_validator.strict_json import parse_strategy

    base = base_recipe(recipe)
    try:
        with zipfile.ZipFile(io.BytesIO(state)) as archive:
            if "__header__.npy" not in archive.namelist():
                raise RecipeRefused("battery_graph_state_header_invalid")
        import numpy as np

        with np.load(io.BytesIO(state), allow_pickle=False) as data:
            header = parse_strategy(bytes(data["__header__"]), max_bytes=65536)
    except RecipeRefused:
        raise
    except (OSError, ValueError, KeyError, zipfile.BadZipFile):
        raise RecipeRefused("battery_graph_state_invalid") from None
    if (
        type(header) is not dict
        or header.get("schema") != STATE_SCHEMA
        or header.get("recipe_digest") != base.digest
        or header.get("submission_digest")
        != recipe.to_dict()["source"]["submission_digest"]
    ):
        raise RecipeRefused("battery_graph_state_identity_invalid")


# --- Worker programs ----------------------------------------------------------------

_PRELUDE = r"""import gzip, hashlib, json, os, re, shutil, sys, time
from pathlib import Path
import numpy as np

work = Path.cwd()
out = work.parent / "output"
for package in ("carbon", "carbon/challenge_validator", "carbon/level4",
                "carbon/level4/tooling", "carbon/development_session"):
    folder = work / package
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "__init__.py").write_text("")
digest = lambda body: "sha256:" + hashlib.sha256(body).hexdigest()
control = json.loads((work / "control.json").read_bytes())
extra_raw = (work / "battery-control.json").read_bytes()
extra = json.loads(extra_raw)
names = list(__STAGED_MODULES__) + list(control.get("codec_modules") or [])
for name in names:
    if re.fullmatch(r"carbon(?:\.[A-Za-z_][A-Za-z_0-9]*){1,5}", name) is None:
        raise ValueError("staged module name differs")
    destination = work.joinpath(*name.split(".")).with_suffix(".py")
    shutil.copyfile(work / (name + ".py"), destination)
for allowlist in ("allowlist_v1.json", "allowlist_v6.json", "allowlist_v7.json"):
    if (work / allowlist).exists():
        shutil.copyfile(work / allowlist, work / "carbon/level4" / allowlist)
lab = work / "carbon_battery_lab"
lab.mkdir()
(lab / "__init__.py").write_text("")
for staged, module in __BATTERY_MODULES__:
    shutil.copyfile(work / staged, lab / module)
sys.path.insert(0, str(work))

from carbon.development_session.construction_recipe import ConstructionRecipe, bind_recipe
from carbon_battery_lab import direct_graph

recipe = ConstructionRecipe.from_bytes((work / "recipe.json").read_bytes())
if recipe.digest != control["recipe_digest"]:
    raise ValueError("graph recipe differs")
bind_recipe(recipe.to_dict(), **control["binding"])
base = ConstructionRecipe.from_bytes((work / "base-recipe.json").read_bytes())
if base.digest != extra["base_recipe_digest"]:
    raise ValueError("graph base recipe differs")
mine, theirs = recipe.to_dict(), base.to_dict()
kit = extra["base_kit"]
if (theirs["challenge"] != kit
    or theirs["output"] != {**mine["output"], "interface_digest": kit["interface_digest"]}
    or {k: v for k, v in theirs.items() if k not in ("challenge", "output")}
    != {k: v for k, v in mine.items() if k not in ("challenge", "output")}):
    raise ValueError("graph base recipe is not the recipe re-keyed")
bind_recipe(theirs, challenge_id=kit["id"], challenge_version=kit["version"],
            train_digest=kit["train_digest"], interface_digest=kit["interface_digest"],
            construction_limits_digest=kit["construction_limits_digest"])
settings = None
if extra["settings_digest"] is not None:
    settings_raw = (work / "settings.json").read_bytes()
    if digest(settings_raw) != extra["settings_digest"]:
        raise ValueError("graph training settings differ")
    settings = json.loads(settings_raw)
"""

BUILD_PROGRAM = (
    r'''"""Fixed Battery direct-graph construction (Battery's registered training); no judge."""
'''
    + _PRELUDE
    + r'''
from carbon.development_session import build_refusal
from carbon.development_session.construction_recipe import RecipeRefused
from carbon.level4 import intake, staging
from carbon.level4.allowlist import Allowlist
from carbon.level4.graph import GraphRefused
from carbon_battery_lab.domain import TrainingData

source = mine["source"]
if source["kind"] != "graph" or source["submission_digest"] != control["submission_digest"]:
    raise ValueError("graph build source differs")
raw_envelope = (work / "source-envelope.json").read_bytes()
if digest(raw_envelope) != control["envelope_digest"]:
    raise ValueError("graph source envelope differs")
declared, raw_manifest, files = staging.from_envelope(json.loads(raw_envelope))
if declared != source["submission_digest"]:
    raise ValueError("graph source digest differs")
allowed = Allowlist((work / "allowlist.json").read_bytes())
if allowed.digest != control["allowlist_digest"]:
    raise ValueError("graph allowlist differs")
def decline(code):
    # OWNER-BUILD-REFUSAL-SPLIT-01: a registered candidate refusal is REFUSED;
    # Carbon's gaps, and any unregistered code, stay UNRESOLVED.
    state = ("REFUSED" if build_refusal.outcome(code) == build_refusal.REFUSED
             else "UNRESOLVED")
    reason = ("graph_submission_invalid" if state == "REFUSED"
              else "carbon_graph_adapter_unavailable")
    (out / "outcome.json").write_text(json.dumps({
        "schema": "carbon.development.graph-build-outcome.v1",
        "state": state,
        "reason_code": reason,
        "detail_code": code,
    }, sort_keys=True, allow_nan=False))

if extra["refusal"] is not None:
    decline(extra["refusal"])
    sys.exit(0)
raw_train = (work / "'''
    + TRAIN_NAME
    + r"""").read_bytes()
if digest(raw_train) != control["binding"]["train_digest"]:
    raise ValueError("pinned TRAIN bytes differ")
records = [json.loads(line) for line in gzip.decompress(raw_train).splitlines() if line.strip()]
if len(records) != extra["train_cases"] or any(
    row.get("role") != "train" or row.get("status") != "OK" for row in records
):
    raise ValueError("TRAIN role/count differs")
train = TrainingData.from_records(records)
try:
    model = direct_graph.build_validated_graph(
        base, raw_manifest, files,
        max_bytes=direct_graph.submission_bytes(kit["version"]),
        train_cases=len(train.case_ids), resolved_settings=settings,
    )
    fit = model.fit(train, seed=control["seed"])
except GraphRefused as error:
    decline(error.code)
    sys.exit(0)
except RecipeRefused as error:
    decline(error.code)
    sys.exit(0)
except intake.IntakeBlocked:
    decline("graph_validation_not_ready")
    sys.exit(0)
state = direct_graph.frozen_state_bytes(
    model, raw_manifest, files, max_bytes=extra["max_state_bytes"]
)
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
"""
)

INFER_PROGRAM = (
    r'''"""Fixed input-only Battery graph inference from inert state; no source or TRAIN."""
'''
    + _PRELUDE
    + r"""
from carbon.development_session.construction_tensor_codec import input_tensor
from carbon_battery_lab.domain import INPUTS

state = (work / "state.npz").read_bytes()
if digest(state) != control["state_digest"]:
    raise ValueError("graph inference state differs")
measure = control.get("measure_query", False)
if type(measure) is not bool:
    raise ValueError("graph inference measurement control differs")
if measure:
    preprocess_start = time.perf_counter()
model = direct_graph.load_frozen_state(
    state, recipe=base, max_bytes=extra["max_state_bytes"],
    train_cases=extra["train_cases"], resolved_settings=settings,
)
inputs = input_tensor((work / "inputs.npz").read_bytes(), control["inputs_digest"])
x = np.asarray(inputs, dtype=float)
if x.ndim != 2 or x.shape[1] != len(INPUTS):
    raise ValueError("graph inference inputs differ")
if measure:
    inference_start = time.perf_counter()
# One isolated case per call (the judge's grading), as the local path predicts.
y = model.predict(x, isolated=True)
if measure:
    postprocess_start = time.perf_counter()
result = np.column_stack((y["v"], y["t"], y["eta"], y["q"])).astype(np.float64)
if (list(result.shape) != control["expected_output_shape"]
    or result.dtype != np.dtype(control.get("expected_output_dtype", "float64"))
    or not np.isfinite(result).all()):
    raise ValueError("graph inference output contract differs")
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
        "input_shape": list(x.shape),
        "input_dtype": str(x.dtype),
        "output_shape": list(result.shape),
        "output_dtype": str(result.dtype),
    }
(out / "receipt.json").write_text(json.dumps(receipt, sort_keys=True, allow_nan=False))
"""
)


def _programs():
    from carbon.battery import direct_graph_worker

    battery = repr(tuple(direct_graph_worker.BATTERY_MODULES.items()))
    return tuple(
        program.replace("__STAGED_MODULES__", repr(staged)).replace(
            "__BATTERY_MODULES__", battery
        )
        for program, staged in (
            (BUILD_PROGRAM, BUILD_MODULES),
            (INFER_PROGRAM, direct_graph_worker.STAGED_MODULES),
        )
    )


def build_program() -> str:
    return _programs()[0]


def infer_program() -> str:
    return _programs()[1]
