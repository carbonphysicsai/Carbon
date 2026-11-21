"""Fixed C-03 graph construction under the same direct task lifecycle.

Only bounded inert graph documents, fixed Challenge TRAIN, and Carbon-owned
training code enter the build worker. Separate inference receives the frozen
graph and numeric state, never the submitted manifest or TRAIN archive.
"""

from __future__ import annotations

import functools
import inspect
import json
import re
import time
from pathlib import Path

import numpy as np

from carbon.challenge_validator.strict_json import MalformedStrategy, parse_strategy
from carbon.level4 import staging
from carbon.reconstruction.worker.model import WorkerImageIdentity

from .bundle_construction_worker import (
    TIMING_WALL_SECONDS_MAX,
    BundleBuildResult,
    DirectReconstructionResult,
    _accelerator_kwargs,
    _checked_binding,
    _digest,
    _infer_state,
    _private_controls_digest,
    _stage_modules,
    _trusted_allowlist,
    direct_child_identity,
    optional_timed,
    rebuild_wall_kwargs,
    resources_kwargs,
    verify_direct_resource_policy,
)
from .bundle_graph_state import MAX_BYTES as MAX_STATE_BYTES
from .bundle_graph_state import load as load_state
from .bundle_graph_state import state_limit
from .construction_recipe import (
    ConstructionRecipe,
    RecipeRefused,
    graph_workspace,
    recipe_graph_bounds,
)
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
'''.replace("__STAGED_MODULES__", repr(STAGED_MODULES))


#: The F08/F02 graph adapters (Validator, 2026-10-20): their own staged modules
#: and programs, so the synthetic adapter's program and stage keep their bytes.
PHYSICAL_STAGED_MODULES = (
    *(name for name in STAGED_MODULES if not name.endswith("synthetic_graph_adapter")),
    "carbon.development_session.build_refusal",
    "carbon.development_session.physical_graph_state",
    "carbon.development_session.physical_graph_trainer",
    "carbon.development_session.physical_graph_adapter",
)

PHYSICAL_BUILD_PROGRAM = r'''"""Fixed F08/F02 direct-graph construction (Carbon's pinned trainer); no judge."""
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

from carbon.development_session import build_refusal
from carbon.development_session.construction_recipe import ConstructionRecipe, RecipeRefused, bind_recipe
from carbon.development_session.physical_graph_adapter import (
    TRAINER_SHA256, build_validated_graph, checked_train, spec_for,
)
from carbon.development_session.physical_graph_state import load
from carbon.level4 import intake, staging
from carbon.level4.allowlist import Allowlist
from carbon.level4.graph import GraphRefused

digest = lambda body: "sha256:" + hashlib.sha256(body).hexdigest()
control = json.loads((work / "control.json").read_bytes())
trainer = (work / "carbon.development_session.physical_graph_trainer.py").read_bytes()
if digest(trainer) != "sha256:" + TRAINER_SHA256:
    raise ValueError("pinned graph trainer differs")
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
allowed_raw = (work / "allowlist.json").read_bytes()
allowed = Allowlist(allowed_raw)
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

named = recipe.to_dict()["challenge"]
try:
    spec = spec_for(named["id"], named["version"])
    inputs, targets = checked_train(
        spec, (work / "train.npz").read_bytes(), control["binding"]["train_digest"]
    )
    model = build_validated_graph(
        recipe, raw_manifest, files, allowlist_bytes=allowed_raw,
        train_cases=len(inputs),
    )
except GraphRefused as error:
    decline(error.code)
    sys.exit(0)
except RecipeRefused as error:
    decline(error.code)
    sys.exit(0)
except intake.IntakeBlocked:
    decline("graph_validation_not_ready")
    sys.exit(0)
try:
    fit = model.fit(inputs, targets, seed=control["seed"])
except RecipeRefused as error:
    if not error.code.endswith("_graph_nonfinite_state"):
        raise
    decline(error.code)
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
    "__STAGED_MODULES__", repr(PHYSICAL_STAGED_MODULES)
)


def _decoded_infer_program() -> str:
    """The plain inference program, reading the decoded state and applying its
    decoder to every prediction; nothing else differs."""
    from .bundle_construction_worker import INFER_PROGRAM
    from .bundle_construction_worker import STAGED_MODULES as INFER_MODULES

    program = INFER_PROGRAM
    for old, new in (
        (
            '"""Fixed input-only graph inference; no source or TRAIN."""',
            '"""Fixed input-only decoded graph inference; no source or TRAIN."""',
        ),
        (
            repr(INFER_MODULES),
            repr((*INFER_MODULES, "carbon.development_session.physical_graph_state")),
        ),
        (
            "from carbon.development_session.bundle_graph_state import load\n",
            "from carbon.development_session.physical_graph_state import load\n",
        ),
        (
            "doc, parameters = load(state, recipe, allowed)\n",
            "doc, parameters, decoder_mu, decoder_sd = load(state, recipe, allowed)\n",
        ),
        (
            "result = np.asarray(outputs[0])\n",
            "result = np.asarray(outputs[0]) * decoder_sd + decoder_mu\n",
        ),
    ):
        if program.count(old) != 1:
            raise RuntimeError("decoded graph inference program anchor moved")
        program = program.replace(old, new)
    return program


#: The F08/F02 adapters' inference program: the plain one plus the decoder.
PHYSICAL_INFER_PROGRAM = _decoded_infer_program()
SYNTHETIC_ADAPTER_ID = "synthetic-linear-field-2d-public-jax-graph-v1"

#: Graph route v2 (`physical_graph_adapter_v2`): its own staged modules and
#: programs beside v1's, which keep their bytes (the F08/F02 graph golden).
PHYSICAL_V2_STAGED_MODULES = (
    *(name for name in STAGED_MODULES if not name.endswith("synthetic_graph_adapter")),
    "carbon.development_session.build_refusal",
    "carbon.development_session.build_refusal_v2",
    "carbon.development_session.physical_graph_state",
    "carbon.development_session.physical_graph_state_v2",
    "carbon.development_session.physical_graph_trainer_v2",
    "carbon.development_session.physical_graph_trainer_v3",
    "carbon.development_session.physical_graph_adapter_v2",
)


#: A TRUST candidate's build container (SELF_TRUST H3d-2c part 2): the v2 set plus the two-phase trust trainer (v4), the trust
#: ensemble state (v3), the per-version trust registration and the trust-head shape rule. Used ONLY for a recipe that declares
#: self-trust (`PHYSICAL_V2_TRUST_BUILD_PROGRAM`): every other build keeps `PHYSICAL_V2_STAGED_MODULES` byte for byte.
PHYSICAL_V2_TRUST_STAGED_MODULES = (
    *PHYSICAL_V2_STAGED_MODULES,
    "carbon.development_session.physical_graph_state_v3",
    "carbon.development_session.physical_graph_trainer_v4",
    "carbon.development_session.physical_graph_trust_registry",
    "carbon.level4.trust_head",
)


def _v2_build_program() -> str:
    """v1's build program on the v2 adapter, trainer and ensemble state; an
    interface in float64 (Motor, Cooling) runs with JAX's 64-bit mode on,
    set before JAX loads."""
    program = PHYSICAL_BUILD_PROGRAM.replace(
        repr(PHYSICAL_STAGED_MODULES), repr(PHYSICAL_V2_STAGED_MODULES)
    )
    for old, new in (
        (
            (
                '"""Fixed F08/F02 direct-graph construction (Carbon\'s pinned trainer);'
                ' no judge."""\nimport hashlib, json, shutil, sys\n'
            ),
            (
                '"""Fixed graph route v2 construction (Carbon\'s trainer v2); no judge."""\n'
                "import hashlib, json, os, shutil, sys\n"
            ),
        ),
        (
            "sys.path.insert(0, str(work))\n",
            (
                "sys.path.insert(0, str(work))\n"
                'if json.loads((work / "control.json").read_bytes()).get("x64") is True:\n'
                '    os.environ["JAX_ENABLE_X64"] = "1"\n'
            ),
        ),
        (
            "from carbon.development_session import build_refusal\n",
            "from carbon.development_session import build_refusal_v2 as build_refusal\n",
        ),
        (
            "from carbon.development_session.physical_graph_adapter import (\n",
            "from carbon.development_session.physical_graph_adapter_v2 import (\n",
        ),
        (
            "from carbon.development_session.physical_graph_state import load\n",
            "from carbon.development_session.physical_graph_state_v2 import load\n",
        ),
        (
            '(work / "carbon.development_session.physical_graph_trainer.py")',
            '(work / "carbon.development_session.physical_graph_trainer_v2.py")',
        ),
        (
            "    TRAINER_SHA256, build_validated_graph, checked_train, spec_for,\n",
            "    TRAINER_SHA256, TRAINER_V3_SHA256, build_validated_graph, checked_train, spec_for,\n",
        ),
        (
            '    raise ValueError("pinned graph trainer differs")\n',
            (
                '    raise ValueError("pinned graph trainer differs")\n'
                'trainer3 = (work / "carbon.development_session.physical_graph_trainer_v3.py").read_bytes()\n'
                'if digest(trainer3) != "sha256:" + TRAINER_V3_SHA256:\n'
                '    raise ValueError("pinned graph trainer v3 differs")\n'
            ),
        ),
        (
            '    if not error.code.endswith("_graph_nonfinite_state"):\n',
            '    if error.code != "graph_route_nonfinite_state":\n',
        ),
    ):
        if program.count(old) != 1:
            raise RuntimeError("graph route v2 build program anchor moved")
        program = program.replace(old, new)
    return program


def _v2_infer_program() -> str:
    """The decoded inference program over an ensemble: every member's
    prediction, combined per output, then the decoder."""
    from .bundle_construction_worker import INFER_PROGRAM
    from .bundle_construction_worker import STAGED_MODULES as INFER_MODULES

    program = INFER_PROGRAM
    for old, new in (
        (
            '"""Fixed input-only graph inference; no source or TRAIN."""',
            (
                '"""Fixed input-only graph route v2 ensemble inference; no source or'
                ' TRAIN."""'
            ),
        ),
        (
            repr(INFER_MODULES),
            repr(
                (
                    *INFER_MODULES,
                    "carbon.development_session.physical_graph_state",
                    "carbon.development_session.physical_graph_state_v2",
                )
            ),
        ),
        (
            "from carbon.development_session.bundle_graph_state import load\n",
            "from carbon.development_session.physical_graph_state_v2 import load\n",
        ),
        (
            "doc, parameters = load(state, recipe, allowed)\n",
            (
                "doc, members, decoder_mu, decoder_sd, combine = load(state, recipe,"
                " allowed)\nparameters = list(members[0])\n"
            ),
        ),
        (
            "parameter_arrays = [jnp.asarray(p) for p in parameters]\n",
            (
                "parameter_arrays = [jnp.asarray(p) for p in parameters]\n"
                "member_arrays = [[jnp.asarray(p) for p in member] for member in members]\n"
            ),
        ),
        (
            "forward = rebuild(doc, allowed)\n",
            (
                "member_forward = rebuild(doc, allowed)\n"
                "def forward(*arguments):\n"
                "    # Each output: the members that train it, by the combination.\n"
                "    part = arguments[-1]\n"
                "    total = None\n"
                "    for weights, arrays in zip(combine, member_arrays):\n"
                "        produced = member_forward(*arrays, part)\n"
                "        if len(produced) != 1:\n"
                '            raise ValueError("graph inference output arity differs")\n'
                "        term = produced[0] * jnp.asarray(weights)\n"
                "        total = term if total is None else total + term\n"
                "    return [total]\n"
            ),
        ),
        (
            "result = np.asarray(outputs[0])\n",
            "result = np.asarray(outputs[0]) * decoder_sd + decoder_mu\n",
        ),
    ):
        if program.count(old) != 1:
            raise RuntimeError("graph route v2 inference program anchor moved")
        program = program.replace(old, new)
    return program


PHYSICAL_V2_BUILD_PROGRAM = _v2_build_program()


def _v2_trust_build_program() -> str:
    """`PHYSICAL_V2_BUILD_PROGRAM` for a trust candidate: anchored changes only (each anchor exactly once): the staged-module list gains
    the trust modules, the post-fit `load` is the trust state's, and the pinned trust trainer's digest is checked beside v2's and
    v3's. Nothing else moves."""
    program = PHYSICAL_V2_BUILD_PROGRAM
    for old, new in (
        (repr(PHYSICAL_V2_STAGED_MODULES), repr(PHYSICAL_V2_TRUST_STAGED_MODULES)),
        (
            "from carbon.development_session.physical_graph_state_v2 import load\n",
            "from carbon.development_session.physical_graph_state_v3 import load\n",
        ),
        (
            "    TRAINER_SHA256, TRAINER_V3_SHA256, build_validated_graph, checked_train, spec_for,\n",
            "    TRAINER_SHA256, TRAINER_V3_SHA256, TRAINER_V4_SHA256, build_validated_graph, checked_train, spec_for,\n",
        ),
        (
            '    raise ValueError("pinned graph trainer v3 differs")\n',
            (
                '    raise ValueError("pinned graph trainer v3 differs")\n'
                'trainer4 = (work / "carbon.development_session.physical_graph_trainer_v4.py").read_bytes()\n'
                'if digest(trainer4) != "sha256:" + TRAINER_V4_SHA256:\n'
                '    raise ValueError("pinned graph trainer v4 differs")\n'
            ),
        ),
    ):
        if program.count(old) != 1:
            raise RuntimeError("graph route v2 trust build program anchor moved")
        program = program.replace(old, new)
    return program


PHYSICAL_V2_TRUST_BUILD_PROGRAM = _v2_trust_build_program()
PHYSICAL_V2_INFER_PROGRAM = _v2_infer_program()

#: Graph route v2 versions whose inference compiles each member's forward (`jax.jit`) instead of interpreting it op by
#: op, as the SAME version (owner, Sun 15 Nov 2026 via the Lead: "nope I'm counting that as the same version. 15 decimal
#: places is fine."). The per-case loop, padding, combination and decoder are unchanged, and every call of one
#: operation (graded per case, the repeat pair, the menu row check, the speed warm-up and timed calls, the batched
#: timing query) goes through the one compiled function, so the timed calls answer bit for bit as the graded run did
#: (`single_call_timing.outputs_match_graded`) and a call uses the memory it does today. Every other version keeps
#: `PHYSICAL_V2_INFER_PROGRAM` byte for byte. Only `carbon/development_session` changes: no exam key moves (this file is
#: in the adapter's source identity, so it reaches a door by a door switch, never a values roll). The build's own post-fit
#: predictions (and the kit's local ones) are compiled separately, Challenge-side, by
#: `physical_graph_adapter_v2.JIT_BUILD_VERSIONS` (the shared `carbon.level4.train.JIT_FORWARD_VERSIONS` stays empty):
#: they never meet the judge's outputs. For a graph whose branches or loop counts turn on a value (comparisons, rounding,
#: a tolerance loop), compiled and eager answers can differ by more than rounding; every judged call is compiled alike.
JIT_INFERENCE_VERSIONS = frozenset({("electric-motor-magnetics", "1.8")})
_EAGER_MEMBER = "member_forward = rebuild(doc, allowed)\n"
_COMPILED_MEMBER = (
    "import jax\n"
    "# Compiled once per input shape, then every call of this operation runs the same executable.\n"
    "member_forward = jax.jit(rebuild(doc, allowed))\n"
)


def _v2_compiled_infer_program() -> str:
    """`PHYSICAL_V2_INFER_PROGRAM` with its member forward compiled: one anchored change, nothing else."""
    if PHYSICAL_V2_INFER_PROGRAM.count(_EAGER_MEMBER) != 1:
        raise RuntimeError("graph route v2 inference program anchor moved")
    return PHYSICAL_V2_INFER_PROGRAM.replace(_EAGER_MEMBER, _COMPILED_MEMBER)


PHYSICAL_V2_COMPILED_INFER_PROGRAM = _v2_compiled_infer_program()

#: Graph route v2 versions whose GRADED per-case procedure runs isolated blocks as vmap lanes, as the SAME version
#: (owner, Sun 15 Nov 2026, Lead session: "I want the 64 rows working", then "Yes and yes"; and ~11:1x CST via the Lead:
#: differences at the 13th-15th decimal are negligible; bound 1e-12, held as a TEST assertion against eager, never a
#: runtime rule). Measured on the grade class (Deploy-B, bench_jit3): 1.421e-14 max |diff| against eager, 1.1 s per pass
#: against 3.4 s for the per-case compiled calls.
#: ONE FIXED LANE LAYOUT PER MODEL: L = `vmap64_lanes` of the model's own graph (at most `VMAP64_LANES`); query row i is
#: lane i % L of chunk i // L; each lane is its own block (the case at row 0 of the declared batch, the other batch rows
#: zero, exactly the per-case call's block), and a short last chunk's spare lanes are all-zero blocks whose answers are
#: dropped. Nothing else changes: the member forward is the compiled one (`JIT_INFERENCE_VERSIONS`), the members combine
#: and the decoder applies as before, and every single-design call (the speed warm-up and timed calls, the practice
#: per-call timing, the batched timing query) stays the per-case compiled `forward`. So a timed call and the graded row
#: agree only within the registered speed-match tolerance (`carbon.challenge_validator.speed_match`, a values row; a
#: disagreement beyond it is Carbon's), while two runs of the same chunks agree bit for bit (the repeat pair over the
#: whole query; the subset repeat over the ORIGINAL chunks, `vmap64_rerun_rows`). The menu row check of a vmap-64 version
#: runs no inference: its row independence is STRUCTURAL (each row its own lane), its side file holds the retained graded
#: rows under the basis STRUCTURAL_ISOLATED_VMAP64, and it is never repeatability evidence
#: (`lean_recipe_retention._structural_rowcheck`). A version here must also be in `JIT_INFERENCE_VERSIONS`.
#: EMPTY since the owner's 116 rollback to A9 behaviour (Sun 15 Nov 2026, typed in Deploy-B: per-case compiled, no batched
#: grading): Motor 1.8 grades with the per-case compiled program again, byte for byte the 57af6692 program
#: (tests/cpu/test_motor18_compiled_forward.py pins its sha). The vmap-64 machinery stays, unused, for a later ruling.
VMAP64_INFERENCE_VERSIONS: frozenset = frozenset()
#: The most lanes one compiled call carries.
VMAP64_LANES = 64
#: RESOURCE CONTAINMENT, not science (review of 15 Nov, finding 3): the share of the version's registered worker memory
#: (`memory_bytes_max`) that one chunk's planned activations, with every member's parameters, may take. Each lane is a
#: full declared-batch block, so a chunk of L lanes holds about L times a per-case call's activations; L is cut until
#: the static over-estimate fits this share, so a model that fits per case today is not pushed out of memory by vmap.
VMAP64_MEMORY_SHARE = 0.5


def vmap64_lanes(doc, members, memory_bytes, share, most):
    """The lane count L of one model: min(most, max(1, (share * memory_bytes - parameter_bytes) // per_case_bytes)).

    per_case_bytes over-estimates one per-case call: the declared bytes of the data input block plus the declared
    output bytes of EVERY node of EVERY graph of the document, at the declared batch, as if all were alive at once;
    parameter_bytes is every member's parameters. A pure function of the graph document and the member count, so the
    layout is FIXED per model: the graded pass, the repeat pair, the menu row check and the subset repeat all chunk the
    query alike. Self-contained: the inference program carries this function's own source.
    """
    from carbon.level4.graph import nbytes

    graphs = doc["graphs"]
    declared = graphs[doc["entry"]]["inputs"]
    parameter_bytes = members * sum(nbytes(entry) for entry in declared[:-1])
    per_case_bytes = nbytes(declared[-1]) + sum(
        nbytes(out)
        for graph in graphs.values()
        for node in graph["nodes"]
        for out in node["out"]
    )
    budget = int(memory_bytes * share) - parameter_bytes
    return min(most, max(1, budget // max(1, per_case_bytes)))


_LANES_ANCHOR = _COMPILED_MEMBER


def _lanes_defined() -> str:
    """The lane count's definition the vmap program carries after its compiled member forward: `vmap64_lanes`'s own
    source, read only when the vmap program is built (never at import, so a host without sources still loads this
    module)."""
    return (
        _COMPILED_MEMBER
        + "# vmap-64: this model's fixed lane count (resource containment, never science).\n"
        + inspect.getsource(vmap64_lanes)
        + "lane_count = vmap64_lanes(doc, len(member_arrays), __MEMORY_BYTES__, __SHARE__,"
        + " __MOST__)\n"
    )


_PER_CASE_CALLS = (
    "    # public constant (zeros), so no output can depend on another case.\n"
    "    for index in range(len(input_array)):\n"
    "        part = jnp.pad(input_array[index:index + 1],\n"
    "                       [(0, batch - 1)] + [(0, 0)] * (input_array.ndim - 1))\n"
    "        outputs = forward(*parameter_arrays, part)\n"
    "        if len(outputs) != 1:\n"
    "            raise ValueError(arity)\n"
    "        blocks.append(outputs[0][:1])\n"
)
_VMAP64_CALLS = """    # public constant (zeros), so no output can depend on another case.
    # vmap-64 (owner, Sun 15 Nov 2026): the SAME per-case blocks, lane_count per compiled call. Row i is lane
    # i % lane_count of chunk i // lane_count; each lane is its own block (the case at row 0, the other batch rows
    # zero), and a short last chunk's spare lanes are all-zero blocks whose answers are dropped. No lane sees another.
    lane_forward = jax.jit(jax.vmap(lambda arrays, block: member_forward(*arrays, block),
                                    in_axes=(None, 0)))
    for start in range(0, len(input_array), lane_count):
        used = min(lane_count, len(input_array) - start)
        chunk = jnp.zeros((lane_count, batch) + tuple(input_array.shape[1:]), input_array.dtype)
        chunk = chunk.at[:used, 0].set(input_array[start:start + used])
        total = None
        for weights, arrays in zip(combine, member_arrays):
            produced = lane_forward(arrays, chunk)
            if len(produced) != 1:
                raise ValueError(arity)
            term = produced[0][:, 0] * jnp.asarray(weights)
            total = term if total is None else total + term
        blocks.append(total[:used])
"""


@functools.lru_cache(maxsize=1)
def vmap64_infer_template() -> str:
    """`PHYSICAL_V2_COMPILED_INFER_PROGRAM` with two anchored replacements and nothing else: the model's lane count,
    defined after its compiled member forward, and the graded per-case loop run as isolated lanes (every anchor the
    derived speed and practice programs read is kept). ``__MEMORY_BYTES__`` stays for `vmap64_infer_program`.
    """
    program = PHYSICAL_V2_COMPILED_INFER_PROGRAM
    for old, new in (
        (_LANES_ANCHOR, _lanes_defined()),
        (_PER_CASE_CALLS, _VMAP64_CALLS),
    ):
        if program.count(old) != 1:
            raise RuntimeError("graph route v2 inference program anchor moved")
        program = program.replace(old, new)
    return program.replace("__SHARE__", repr(VMAP64_MEMORY_SHARE)).replace(
        "__MOST__", str(VMAP64_LANES)
    )


def _version_memory_bytes(challenge_id: str, version: str) -> int:
    """The version's registered worker memory (`memory_bytes_max` of its construction limits)."""
    from carbon.challenge_kit import physical_public

    policy = physical_public.construction_limits_document(challenge_id, version)[
        "reconstruction_resource_policy"
    ]
    memory = policy["memory_bytes_max"]
    if type(memory) is not int or memory <= 0:
        raise RuntimeError("vmap-64 version worker memory unregistered")
    return memory


@functools.lru_cache(maxsize=8)
def vmap64_infer_program(challenge_id: str, version: str) -> str:
    """The vmap-64 inference program of one version: the template with that version's registered worker memory."""
    if (challenge_id, version) not in VMAP64_INFERENCE_VERSIONS:
        raise RuntimeError("not a vmap-64 version")
    return vmap64_infer_template().replace(
        "__MEMORY_BYTES__", str(_version_memory_bytes(challenge_id, version))
    )


def vmap64_model_lanes(challenge_id: str, version: str, doc, members: int) -> int:
    """The lane count L the version's program uses for a model: the same function over the same inputs."""
    return vmap64_lanes(
        doc,
        members,
        _version_memory_bytes(challenge_id, version),
        VMAP64_MEMORY_SHARE,
        VMAP64_LANES,
    )


def vmap64_state_lanes(
    challenge_id: str, version: str, state: bytes, recipe, allowlist_bytes: bytes
) -> int:
    """L of a retained state, read through the version's own strict loader (`physical_graph_state_v2.load`)."""
    from carbon.level4.allowlist import Allowlist

    from . import physical_graph_state_v2

    doc, members, _mu, _sd, _combine = physical_graph_state_v2.load(
        state, recipe, Allowlist(allowlist_bytes)
    )
    return vmap64_model_lanes(challenge_id, version, doc, len(members))


def vmap64_chunks(positions, row_count: int, lanes: int) -> dict:
    """The ORIGINAL chunks of a model with ``lanes`` lanes (`vmap64_lanes`) that hold ``positions`` (indices into a
    graded query of ``row_count`` rows): ``{chunk index: (query rows of that chunk, in lane order)}``, ascending. A
    chunk is whole (all its rows, the last chunk short when ``row_count`` is not a multiple of ``lanes``), so a fresh
    process that runs the rows of these chunks, concatenated in ascending chunk order, through the same program and
    model (so the same L) puts every row in its original chunk and lane with the same companions and the same zero
    padding, and so answers it bit for bit as the graded run did (see `vmap64_rerun_rows`).
    """
    if (
        type(row_count) is not int
        or row_count <= 0
        or type(lanes) is not int
        or not 1 <= lanes <= VMAP64_LANES
        or type(positions) not in (list, tuple)
        or not positions
        or any(
            type(p) is not int or type(p) is bool or not 0 <= p < row_count
            for p in positions
        )
    ):
        raise ValueError("vmap64_chunk_positions_invalid")
    chosen = sorted({p // lanes for p in positions})
    return {
        chunk: tuple(range(chunk * lanes, min((chunk + 1) * lanes, row_count)))
        for chunk in chosen
    }


def vmap64_rerun_rows(positions, row_count: int, lanes: int) -> tuple:
    """``(rows, where)``: the graded-query rows a re-run must query, in order (the ORIGINAL chunks of
    `vmap64_chunks`, ascending), and for each of ``positions`` (in the given order) the index of its answer in that
    re-run. Only the last original chunk can be short, and it is then also last in the re-run, so its padding is
    the same."""
    chunks = vmap64_chunks(positions, row_count, lanes)
    rows = [row for chunk in chunks.values() for row in chunk]
    at = {row: index for index, row in enumerate(rows)}
    return rows, [at[p] for p in positions]


#: Graph route v2 versions whose GRADED per-case loop runs in per-case worker processes inside the one inference
#: container (Lead's order, Mon 16 Nov 2026; `case_procs`): one process per core of the container's cpuset (the round's
#: lane), each pinned to its core, the rows split into contiguous slices and reassembled in row order. Each row is still
#: its own per-case call of the same compiled forward, and every pass checks the first row of every slice against the
#: parent's own one-process answer BIT FOR BIT (any difference: the whole pass in one process), so the graded answers,
#: the repeat pair, the subset repeat and the menu row check are the one-process ones. The speed gate's single calls
#: and the practice timed program derive from the one-process program (`case_procs.serial_program`): timing is
#: unchanged byte for byte. A version here must also be in `JIT_INFERENCE_VERSIONS` and not in
#: `VMAP64_INFERENCE_VERSIONS` (which wins). A program change: it reaches a door only by a door switch on the owner's words.
CASE_PROCS_INFERENCE_VERSIONS: frozenset = frozenset(
    {("electric-motor-magnetics", "1.8")}
)


@functools.lru_cache(maxsize=8)
def case_procs_infer_program(challenge_id: str, version: str) -> str:
    """The per-case processes inference program of one version: the compiled program with that version's registered
    worker memory and inference wall (`case_procs.procs_program`)."""
    from . import case_procs

    if (challenge_id, version) not in CASE_PROCS_INFERENCE_VERSIONS:
        raise RuntimeError("not a per-case processes version")
    from carbon.challenge_kit import physical_public

    wall = physical_public.construction_limits_document(challenge_id, version)[
        "reconstruction_resource_policy"
    ]["inference_wall_seconds_max"]
    return case_procs.procs_program(
        PHYSICAL_V2_COMPILED_INFER_PROGRAM,
        _version_memory_bytes(challenge_id, version),
        wall,
    )


def graph_adapter_ids() -> frozenset:
    """Every graph adapter the receiver can run: the synthetic one (1.3), the
    F08 1.4 / F02 2.3 adapters and every graph route v2 adapter."""
    from . import graph_adapters

    return frozenset({SYNTHETIC_ADAPTER_ID}) | graph_adapters.adapter_ids()


def v2_infer_query(challenge_id: str, version: str) -> dict:
    """The `_infer_state` arguments of a graph route v2 version's
    source-free inference: the ensemble state, combined and decoded by its own
    program (the receiver and regrade share it); a version in
    `JIT_INFERENCE_VERSIONS` gets that program with its member forward
    compiled, and one in `VMAP64_INFERENCE_VERSIONS` the compiled program with
    its graded per-case loop run as isolated vmap-64 lanes. The output dtype is
    the interface's, which each caller passes."""
    from . import physical_graph_adapter_v2

    physical_graph_adapter_v2.spec_for(challenge_id, version)
    compiled = (challenge_id, version) in JIT_INFERENCE_VERSIONS
    lanes = (challenge_id, version) in VMAP64_INFERENCE_VERSIONS
    if lanes and not compiled:
        raise RuntimeError("a vmap-64 version must also be a compiled version")
    # (vmap-64 wins over per-case processes: the two sets are disjoint, a test holds that; a test opting a version
    # into the dormant vmap-64 machinery gets the vmap-64 program, as before)
    procs = (challenge_id, version) in CASE_PROCS_INFERENCE_VERSIONS and not lanes
    if procs and not compiled:
        raise RuntimeError(
            "a per-case processes version must also be a compiled version"
        )
    root = Path(__file__).resolve().parents[2]
    names = (
        "carbon.development_session.physical_graph_state",
        "carbon.development_session.physical_graph_state_v2",
    )
    return {
        "input_name": "inputs/features",
        "program": (
            vmap64_infer_program(challenge_id, version)
            if lanes
            else (
                case_procs_infer_program(challenge_id, version)
                if procs
                else (
                    PHYSICAL_V2_COMPILED_INFER_PROGRAM
                    if compiled
                    else PHYSICAL_V2_INFER_PROGRAM
                )
            )
        ),
        "staged_files": {
            name + ".py": (root / (name.replace(".", "/") + ".py")).read_bytes()
            for name in names
        },
    }


def v2_trust_infer_query(challenge_id: str, version: str, trust_outputs: int) -> dict:
    """The `_infer_state` arguments of a graph route v2 TRUST candidate (SELF_TRUST H3f): the version's own inference
    program turned into its trust variant (`trust_infer.trust_program`) plus `trust_outputs`, the count k of trust columns
    the container splits off. Only the plain and the compiled programs offer it: a per-case-processes or vmap-64 version
    does not (a typed refusal, never a silent plain program)."""
    from .trust_infer import trust_program

    if type(trust_outputs) is not int or trust_outputs < 1:
        raise RecipeRefused("direct_graph_trust_interface_not_offered")
    key = (challenge_id, version)
    if key in VMAP64_INFERENCE_VERSIONS or key in CASE_PROCS_INFERENCE_VERSIONS:
        raise RecipeRefused("direct_graph_trust_program_not_offered")
    from .bundle_construction_worker import STAGED_MODULES as INFER_MODULES

    query = v2_infer_query(challenge_id, version)
    state_v3 = "carbon.development_session.physical_graph_state_v3"
    modules = (
        *INFER_MODULES,
        "carbon.development_session.physical_graph_state",
        "carbon.development_session.physical_graph_state_v2",
    )
    program = trust_program(query["program"])
    if program.count(repr(modules)) != 1:
        raise RuntimeError("graph route v2 trust inference program anchor moved")
    program = program.replace(repr(modules), repr((*modules, state_v3)))
    root = Path(__file__).resolve().parents[2]
    return {
        **query,
        "program": program,
        "staged_files": {
            **query["staged_files"],
            state_v3
            + ".py": (root / (state_v3.replace(".", "/") + ".py")).read_bytes(),
        },
        "trust_outputs": trust_outputs,
    }


def _v2_adapter_ids() -> frozenset:
    from . import physical_graph_adapter_v2

    return physical_graph_adapter_v2.ADAPTER_IDS


def registered_inference_contract(binding, limits_document, *, recipe=None):
    """The strict state loader, fixed query and output dtype of one adapter.

    Select by the version's registered adapter declaration, never by a state
    header, device or a caller-supplied program. The caller first authenticates
    the recipe/binding and published limits through the ordinary policy check.
    """
    from . import (
        battery_graph_adapter,
        graph_adapters,
        physical_graph_state,
        physical_graph_state_v2,
    )

    if (
        type(binding) is not dict
        or type(limits_document) is not dict
        or any(
            type(binding.get(key)) is not str or not binding[key]
            for key in ("challenge_id", "challenge_version")
        )
    ):
        raise RecipeRefused("direct_graph_adapter_identity_invalid")
    challenge_id, version = binding["challenge_id"], binding["challenge_version"]
    block = limits_document.get("graph_training_adapter")
    if type(block) is not dict:
        raise RecipeRefused("direct_graph_adapter_identity_invalid")
    adapter_id = block.get("id")
    module = graph_adapters.for_version(challenge_id, version)
    if module is None:
        from carbon.challenge_kit.synthetic_linear_field_2d import (
            construction_limits_document_v3,
        )

        if (
            adapter_id != SYNTHETIC_ADAPTER_ID
            or block != construction_limits_document_v3()["graph_training_adapter"]
        ):
            raise RecipeRefused("direct_graph_adapter_identity_invalid")
        return (
            load_state,
            {"input_name": "inputs/forcing", "provenance": INFERENCE_PROVENANCE},
            "float32",
        )
    if block != module.adapter_block(challenge_id, version):
        raise RecipeRefused("direct_graph_adapter_identity_invalid")
    query = {"provenance": INFERENCE_PROVENANCE}
    if adapter_id in battery_graph_adapter.ADAPTER_IDS:
        if type(recipe) is not ConstructionRecipe:
            raise RecipeRefused("direct_graph_adapter_identity_invalid")

        def load_battery(state, bound_recipe, _allowlist):
            battery_graph_adapter.check_state(state, bound_recipe)

        query.update(
            input_name=battery_graph_adapter.INPUT_NAME,
            program=battery_graph_adapter.infer_program(),
            staged_files=battery_graph_adapter.inference_files(binding, recipe),
        )
        return load_battery, query, battery_graph_adapter.OUTPUT_DTYPE
    if adapter_id in _v2_adapter_ids():
        # A candidate that declared self-trust runs its version's trust program variant (the recipe's output binding is
        # the declaration); a version that offers none refuses it. Every other candidate's query is exactly as before.
        trust_outputs = 0
        if type(recipe) is ConstructionRecipe and recipe.declares_self_trust:
            trust_outputs = module.spec_for(challenge_id, version).trust_outputs
            if trust_outputs < 1:
                raise RecipeRefused("direct_graph_trust_interface_not_offered")
        query.update(
            v2_trust_infer_query(challenge_id, version, trust_outputs)
            if trust_outputs
            else v2_infer_query(challenge_id, version)
        )
        if trust_outputs:
            from . import physical_graph_state_v3

            loader = physical_graph_state_v3.load
        else:
            loader = physical_graph_state_v2.load
        return (
            loader,
            query,
            module.spec_for(challenge_id, version).dtype,
        )
    from . import physical_graph_adapter

    if adapter_id not in physical_graph_adapter.ADAPTER_IDS:
        raise RecipeRefused("direct_graph_adapter_identity_invalid")
    root = Path(__file__).resolve().parents[2]
    name = "carbon.development_session.physical_graph_state"
    query.update(
        input_name="inputs/features",
        program=PHYSICAL_INFER_PROGRAM,
        staged_files={
            name + ".py": (root / (name.replace(".", "/") + ".py")).read_bytes()
        },
    )
    return physical_graph_state.load, query, "float32"


_WIDE_DTYPES = (b'"float64"', b'"int64"', b'"uint64"', b'"complex128"')


def _envelope_has_wide_values(source_envelope: bytes) -> bool:
    """Whether a checked graph source envelope's documents name a 64-bit dtype.
    A conservative text scan: a false positive turns 64-bit mode on while every
    array keeps its declared dtype; it never changes a result."""
    from carbon.level4 import staging

    _, _, files = staging.from_envelope(json.loads(source_envelope))
    return any(wide in raw for raw in files.values() for wide in _WIDE_DTYPES)


def _v2_stage(
    binding: dict, limits_document: dict, allowlist_bytes: bytes, *, trust: bool = False
):
    """Check a graph route v2 adapter's served identity; return its staged
    files (as `_physical_stage` does for v1). A `trust` candidate (its recipe declares self-trust) also checks the pinned trust
    trainer's bytes and stages the trust modules (`PHYSICAL_V2_TRUST_STAGED_MODULES`).
    """
    from carbon.level4.allowlist import Allowlist

    from . import physical_graph_adapter_v2 as adapter

    spec = adapter.spec_for(binding["challenge_id"], binding["challenge_version"])
    if limits_document.get("graph_training_adapter") != adapter.adapter_block(
        spec.challenge_id, spec.version
    ):
        raise RecipeRefused("direct_graph_adapter_identity_invalid")
    if allowlist_bytes != adapter.served_allowlist_bytes(
        spec.challenge_id, spec.version
    ):
        raise RecipeRefused("direct_graph_allowlist_unregistered")
    if binding["train_digest"] != "sha256:" + spec.train_sha256:
        raise RecipeRefused("direct_graph_train_binding_invalid")
    adapter.trainer_source()
    adapter.trainer_source(spec)
    if trust:
        if spec.trust_outputs < 1:
            raise RecipeRefused("direct_graph_trust_interface_not_offered")
        adapter.trust_trainer_source()
    root = Path(__file__).resolve().parents[2]
    files = {
        name + ".py": (root / (name.replace(".", "/") + ".py")).read_bytes()
        for name in (
            PHYSICAL_V2_TRUST_STAGED_MODULES if trust else PHYSICAL_V2_STAGED_MODULES
        )
    }
    return spec, Allowlist(allowlist_bytes), files


def _physical_stage(binding: dict, limits_document: dict, allowlist_bytes: bytes):
    """Check a physical adapter's served identity; return its staged files."""
    from carbon.level4.allowlist import Allowlist

    from . import physical_graph_adapter as adapter

    spec = adapter.spec_for(binding["challenge_id"], binding["challenge_version"])
    if limits_document.get("graph_training_adapter") != adapter.adapter_block(
        spec.challenge_id, spec.version
    ):
        raise RecipeRefused("direct_graph_adapter_identity_invalid")
    if allowlist_bytes != adapter.served_allowlist_bytes(
        spec.challenge_id, spec.version
    ):
        raise RecipeRefused("direct_graph_allowlist_unregistered")
    if binding["train_digest"] != "sha256:" + spec.train_sha256:
        raise RecipeRefused("direct_graph_train_binding_invalid")
    adapter.trainer_source()
    root = Path(__file__).resolve().parents[2]
    files = {
        name + ".py": (root / (name.replace(".", "/") + ".py")).read_bytes()
        for name in PHYSICAL_STAGED_MODULES
    }
    return spec, Allowlist(allowlist_bytes), files


def _checked_envelope(recipe: ConstructionRecipe, source_envelope: bytes) -> bytes:
    if (
        type(recipe) is not ConstructionRecipe
        or recipe.to_dict()["source"]["kind"] != "graph"
    ):
        raise RecipeRefused("direct_graph_source_invalid")
    # The recipe's exact version's intake bound (containment on v7).
    bound = recipe_graph_bounds(recipe)["submission_bytes"]
    if type(source_envelope) is not bytes or not 0 < len(source_envelope) <= 2 * bound:
        raise RecipeRefused("direct_graph_source_invalid")
    try:
        envelope = json.loads(source_envelope)
        declared, raw_manifest, files = staging.from_envelope(envelope)
    except (TypeError, ValueError, KeyError, UnicodeError):
        raise RecipeRefused("direct_graph_source_invalid") from None
    if declared != recipe.to_dict()["source"]["submission_digest"]:
        raise RecipeRefused("construction_recipe_graph_digest_mismatch")
    graph_workspace(recipe, raw_manifest, files, max_bytes=bound)
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
    adapter_id: str = SYNTHETIC_ADAPTER_ID,
    accelerator: str | None = None,
) -> BundleBuildResult:
    """Rebuild the actual graph in a fresh isolated C-03 construction child.

    `adapter_id` selects the Challenge's graph adapter (`graph_adapter_ids`):
    the synthetic 1.3 adapter keeps its exact program and stage; the F08 1.4 /
    F02 2.3 adapter runs its own program with Carbon's pinned trainer; Battery
    2.2's (`battery_graph_adapter`) runs Battery's registered training on its
    float64 TRAIN."""
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
    from . import battery_graph_adapter, physical_graph_adapter

    train_name = "train.npz"
    if adapter_id == SYNTHETIC_ADAPTER_ID:
        allowed = _trusted_allowlist(allowlist_bytes)
        files = _stage_modules()
        root = Path(__file__).resolve().parents[2]
        files.update(
            {
                name + ".py": (root / (name.replace(".", "/") + ".py")).read_bytes()
                for name in STAGED_MODULES
            }
        )
        program = BUILD_PROGRAM

        def load_built(state):
            load_state(state, recipe, allowed)

    elif adapter_id in _v2_adapter_ids():
        from . import physical_graph_state_v2

        trust = type(recipe) is ConstructionRecipe and recipe.declares_self_trust
        spec, allowed, physical_files = _v2_stage(
            binding, limits_document, allowlist_bytes, trust=trust
        )
        if spec.adapter_id != adapter_id:
            raise RecipeRefused("direct_graph_adapter_identity_invalid")
        files = _stage_modules()
        files.update(physical_files)
        program = (
            PHYSICAL_V2_TRUST_BUILD_PROGRAM if trust else PHYSICAL_V2_BUILD_PROGRAM
        )
        # JAX's 64-bit mode is on when the interface is float64, and also whenever the
        # miner's graph holds a 64-bit value (OWNER-GRAPH-OPS-OPEN-01, Validator row 7):
        # TRAIN, the decoder and the outputs keep the interface dtype either way.
        x64 = spec.dtype == "float64" or _envelope_has_wide_values(source_envelope)

        def load_built(state):
            if trust:
                from . import physical_graph_state_v3

                physical_graph_state_v3.load(state, recipe, allowed)
            else:
                physical_graph_state_v2.load(state, recipe, allowed)

    elif adapter_id in physical_graph_adapter.ADAPTER_IDS:
        from . import physical_graph_state

        spec, allowed, physical_files = _physical_stage(
            binding, limits_document, allowlist_bytes
        )
        if spec.adapter_id != adapter_id:
            raise RecipeRefused("direct_graph_adapter_identity_invalid")
        files = _stage_modules()
        files.update(physical_files)
        program = PHYSICAL_BUILD_PROGRAM

        def load_built(state):
            physical_graph_state.load(state, recipe, allowed)

    elif adapter_id in battery_graph_adapter.ADAPTER_IDS:
        from carbon.level4.allowlist import Allowlist

        spec, battery_files = battery_graph_adapter.build_stage(
            binding, limits_document, allowlist_bytes, recipe
        )
        if spec.adapter_id != adapter_id:
            raise RecipeRefused("direct_graph_adapter_identity_invalid")
        allowed = Allowlist(allowlist_bytes)
        files = _stage_modules()
        files.update(battery_files)
        program = battery_graph_adapter.build_program()
        train_name = battery_graph_adapter.TRAIN_NAME

        def load_built(state):
            battery_graph_adapter.check_state(state, recipe)

    else:
        raise RecipeRefused("direct_graph_adapter_unavailable")
    files.update(
        {
            "recipe.json": recipe.canonical_bytes,
            "source-envelope.json": source_envelope,
            train_name: train,
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
                    # Graph route v2 only, so v1's control bytes are unchanged.
                    **({"x64": x64} if adapter_id in _v2_adapter_ids() else {}),
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
        for name, ceiling in (
            ("state.npz", state_limit(allowed)),
            ("receipt.json", 65536),
        ):
            path = snapshot / name
            if (
                path.is_symlink()
                or not path.is_file()
                or not 0 < path.stat().st_size
                or (ceiling is not None and path.stat().st_size > ceiling)
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
        load_built(state)
        return state, receipt

    worker = (runner or _run)(
        ledger,
        owner=owner,
        identity=identity,
        source=program,
        files=files,
        image=image,
        seconds=seconds,
        provenance=BUILD_PROVENANCE,
        extra_resources=(
            {} if PRECHARGED_TRIAL.get() is not None else {"research_trials": 1}
        ),
        output_validator=checked,
        **_accelerator_kwargs(accelerator),
        **rebuild_wall_kwargs(limits_document),
        **resources_kwargs(binding),
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
    timing_optional: bool = False,
    runner=None,
    adapter_id: str = SYNTHETIC_ADAPTER_ID,
    accelerator: str | None = None,
    inference_image: WorkerImageIdentity | None = None,
    inference_accelerator: str | None = None,
) -> DirectReconstructionResult:
    """Use the normal two-child budget and source-free inference boundary.

    `accelerator` is the GPU for the build and, as practice runs it, for the inference too. A
    validator that rebuilds on its GPU and grades on its CPU names `inference_image` (its own
    worker) and `inference_accelerator` (None = the CPU): the build keeps `image` and
    `accelerator`, the inference child takes the pair given. Absent, nothing changes."""
    if inference_image is None and inference_accelerator is not None:
        raise RecipeRefused("direct_graph_build_binding_invalid")
    binding = _checked_binding(recipe, challenge_binding)
    policy_digest = verify_direct_resource_policy(binding, limits_document)
    policy = limits_document["reconstruction_resource_policy"]
    from carbon.reconstruction import grade_lanes

    started = time.monotonic()
    deadline = started + policy["total_reconstruction_wall_seconds_max"]
    build_identity = direct_child_identity(identity, "build")
    inference_identity = direct_child_identity(identity, "inference")
    waited_at_start = grade_lanes.waited_seconds()

    def queued() -> float:
        # Carbon's queue since the start (a lane re-take, a build machine's slot), never the miner's time: added back to
        # the total deadline (live 116, 18 Nov 2026); each phase keeps its own registered cap
        return grade_lanes.waited_seconds() - waited_at_start

    def phase_seconds(name: str) -> int:
        remaining = int(deadline + queued() - time.monotonic())
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
        adapter_id=adapter_id,
        **({} if accelerator is None else {"accelerator": accelerator}),
    )
    expected = ledger.root / build.worker_operation / "snapshot" / "state.npz"
    if build.state_path != expected or expected.is_symlink() or not expected.is_file():
        raise RecipeRefused("direct_graph_state_custody_invalid")
    state = expected.read_bytes()
    if _digest(state) != build.state_digest:
        raise RecipeRefused("direct_graph_state_changed")
    query = {
        "ledger": ledger,
        "owner": owner,
        "inference_image": image if inference_image is None else inference_image,
        "recipe": recipe,
        "binding": binding,
        "state": state,
        "state_digest": build.state_digest,
        "inputs": inputs,
        "expected_output_shape": expected_output_shape,
        "expected_output_dtype": "float32",
        "allowlist_bytes": allowlist_bytes,
        "input_name": "inputs/forcing",
        "provenance": INFERENCE_PROVENANCE,
        "runner": runner,
        **rebuild_wall_kwargs(limits_document),
        # The miner's own GPU for both children (practice only): absent for
        # every CPU run, so their calls and identities are unchanged.
        **_accelerator_kwargs(
            accelerator if inference_image is None else inference_accelerator
        ),
    }
    _loader, registered_query, dtype = registered_inference_contract(
        binding, limits_document, recipe=recipe
    )
    if limits_document["graph_training_adapter"]["id"] != adapter_id:
        raise RecipeRefused("direct_graph_adapter_identity_invalid")
    query.update(registered_query)
    query["expected_output_dtype"] = dtype
    # Graded one case at a time, as a bundle is (row 0 plus zero filler), so no
    # output can depend on its batch; the batched cold query is kept only for
    # timing when the task is measured, never graded.
    inference = _infer_state(
        **query,
        identity=inference_identity,
        measure_query=False,
        per_case=True,
        seconds=phase_seconds("inference_wall_seconds_max"),
    )

    def timing_seconds() -> int:
        # The speed result's cold query gets its own capped allowance (a practice that
        # used most of the aggregate wall in the build would otherwise leave it too few
        # seconds, and the watchdog would stop its container: Cooling 1.4 '-timed').
        if not timing_optional:
            return phase_seconds("inference_wall_seconds_max")
        return min(policy["inference_wall_seconds_max"], TIMING_WALL_SECONDS_MAX)

    def timed_query():
        return _infer_state(
            **query,
            identity=direct_child_identity(identity, "timed"),
            measure_query=True,
            per_case=False,
            seconds=timing_seconds(),
            practice_timing=True,
        )

    before_timing = time.monotonic() - started
    timed = None
    if measure_query:
        timed = optional_timed(timed_query) if timing_optional else timed_query()
    elapsed = time.monotonic() - started
    if timing_optional:
        # Only for the speed result: it is not part of the practice's aggregate wall.
        elapsed = before_timing
    if (
        timing_optional
        and timed is not None
        and timed.state_digest != build.state_digest
    ):
        timed = None
    if elapsed - queued() > policy["total_reconstruction_wall_seconds_max"]:
        raise RecipeRefused("construction_total_deadline_reached")
    if build.state_digest != inference.state_digest or (
        timed is not None and timed.state_digest != build.state_digest
    ):
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
    timed_controls = (
        _private_controls_digest(
            ledger,
            owner=owner,
            identity=direct_child_identity(identity, "timed"),
            operation=timed.worker_operation,
            provenance=INFERENCE_PROVENANCE,
        )
        if timed is not None and runner is None
        else None
    )
    return DirectReconstructionResult(
        build,
        inference,
        policy_digest,
        "C03_DOCKER" if runner is None else "TEST_ONLY_LOCAL_RUNNER",
        controls[0],
        controls[1],
        elapsed,
        timed=timed,
        timed_controls_digest=timed_controls,
    )
