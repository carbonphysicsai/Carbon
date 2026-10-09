"""Battery's Level 4 development record, for the shared dispatch.

`development_rebuild` asks this module whether a construction carries a
Level 4 graph record and how to stage or build it. A Level 4 construction is
a graph-only submission (OWNER-LEVEL4-GRAPH-ONLY-01): its record names the
submission's digest and the allowlist it was admitted under. G5's profile,
compiling a checked graph in the C-03 lane, is accepted for development and
testnet (OWNER-L4-G5-COMPILE-ISOLATION-01).

The rebuild trains the submission's documents, which the validator stages
beside the record in the staging contract's workspace form
(`carbon.level4.staging.workspace`; LEVEL4_STAGING_CONTRACT.md). Carbon's
own code builds and trains it (`level4_model.GraphModel`):

* **In the worker** (`program`, `staged`): the reconstruct program's one
  build line becomes the Level 4 build. Carbon's `carbon.level4` modules,
  its allowlist and the graph model are staged as files, loaded by a fixed
  prelude, and never come from the submission.
* **Inference** (`infer_program`, `infer_staged`): a Level 4 state carries
  its documents, so its inference program stages the same modules and
  rebuilds the graph from the state alone. Every other state keeps the
  Level 0 inference program, byte for byte.
* **In process** (`build_in_process`): the same model, for local runs.

With no staged documents, every rebuild fails closed as Carbon's
environment (`BLOCKED`), never the candidate's.

Imports nothing beyond the standard library at module level: the validator
and daemon reach this module, and must never reach the variant mechanism.
"""

from __future__ import annotations

import json
from pathlib import Path

SCHEMA = "carbon.battery.level4-graph.v1"
CAPABILITY = "hybrid.composition_graphs"
#: Why a Level 4 rebuild stops when no documents were staged.
BLOCKED = "level4_submission_documents_not_staged"
REBUILD_LABEL = (
    "rebuild: CPU-verified only; the graph is trained from the staged "
    "submission; G5 accepted for development and testnet only"
)
STAGED = "level4-graph.json"
#: Carbon's modules a Level 4 rebuild and inference stage, by name, in the
#: order the prelude loads them (each module's imports come first).
MODULES = (
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
    "carbon.level4.staging",
)
ALLOWLIST_FILE = "allowlist_v1.json"
MODEL_FILE = "battery-level4-model.py"

#: Loads the staged modules as the `carbon` packages they come from: each
#: from its staged file, in `MODULES` order. Nothing else is importable as
#: `carbon` in the worker.
_PRELUDE = r"""import importlib.util as _util, types as _types
for _package in ("carbon", "carbon.level4", "carbon.challenge_validator"):
    _module = _types.ModuleType(_package)
    _module.__path__ = []
    sys.modules[_package] = _module
for _name in __MODULES__:
    _spec = _util.spec_from_file_location(_name, work / (_name + ".py"))
    _module = _util.module_from_spec(_spec)
    sys.modules[_name] = _module
    _spec.loader.exec_module(_module)
shutil.copyfile(work / "battery-level4-model.py", lab / "level4_model.py")
""".replace("__MODULES__", repr(MODULES))
_BUILD = 'model = recipes.build(recipe["family"], recipe["settings"])\n'
_LEVEL4_BUILD = _PRELUDE + """from carbon_battery_lab import level4_model  # noqa: E402

model = level4_model.build_from_work(recipe, work)
"""
_INFER_LOAD = 'model = recipes.model_from_bytes((work / "state.npz").read_bytes())\n'


def graph_record(reconstruction):
    """A construction's Level 4 graph record, or None."""
    if not isinstance(reconstruction, dict):
        return None
    found = reconstruction.get(CAPABILITY)
    if isinstance(found, dict) and found.get("schema") == SCHEMA:
        return dict(found)
    return None


def is_graph(found):
    return isinstance(found, dict) and found.get("schema") == SCHEMA


def _replace(base, line, body):
    import textwrap

    for indent in ("    ", ""):
        if base.count(indent + line) == 1:
            return base.replace(indent + line, textwrap.indent(body, indent))
    raise RuntimeError("the program's line moved")


def program(base):
    """`base` (a Level-0 reconstruct program) with its one build line replaced
    by the Level 4 build, at the same indent, so it lands inside the
    program's `try:`: a missing document or module is its `except
    ImportError` (Carbon's environment), and a refused or failed graph is
    the candidate's."""
    return _replace(base, _BUILD, _LEVEL4_BUILD)


def _module_files():
    root = Path(__file__).resolve().parents[2]
    files = {
        name + ".py": (root / (name.replace(".", "/") + ".py")).read_bytes()
        for name in MODULES
    }
    files[ALLOWLIST_FILE] = (root / "carbon" / "level4" / ALLOWLIST_FILE).read_bytes()
    files[MODEL_FILE] = (Path(__file__).with_name("level4_model.py")).read_bytes()
    return files


def staged(found):
    """The record and Carbon's own files a Level 4 rebuild stages. The
    submission's documents are the validator's to stage beside them
    (`staging.workspace`)."""
    return {
        STAGED: json.dumps(found, sort_keys=True, separators=(",", ":")).encode(),
        **_module_files(),
    }


def infer_program(base):
    """`base` (the Level-0 inference program) with Carbon's Level 4 modules
    loaded before the state is read, for a Level 4 state only."""
    return _replace(base, _INFER_LOAD, _PRELUDE + _INFER_LOAD)


def infer_staged():
    """Carbon's own files a Level 4 state's inference stages."""
    return _module_files()


def build_in_process(recipe, found, workspace=None):
    """The untrained graph model for a Level 4 record, built from the files a
    rebuild was staged with (`carbon.level4.staging.workspace`). With no
    staged files the rebuild fails closed as Carbon's environment
    (`BLOCKED`), never the candidate's."""
    if workspace is None:
        raise ImportError(BLOCKED)
    from .level4_model import build

    return build(recipe, found, workspace)
