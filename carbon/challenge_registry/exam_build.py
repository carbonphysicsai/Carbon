"""The build half of a registered exam: what a build reads about a version that has no code-table row (owner G-LEAD-61).

A row of ``exam_registry.json`` may carry ``build``:

- ``module``, ``sha256``: the ``carbon.*`` module that serves the version's public construction material
  (`FUNCTIONS`), hashed before it is imported (`pinned_module`);
- ``graph_spec``: the graph route v2 facts of the version (`SPEC_FIELDS`), or null when it takes no graph recipes;
- ``inference_program``: ``eager``, ``compiled`` or ``per_case`` (null exactly when ``graph_spec`` is);
- ``total_wall_seconds`` (may be left out): the version's whole-task wall, an owner value at or above the one every
  version with its rebuild wall has (`version_registry.task_wall_seconds`); raise-only;
- ``nonfinite_rule`` (may be left out): the version's rule for a proven non-finite answer (`NONFINITE_RULES`, owner
  G-LEAD-75; `carbon.development_session.nonfinite_infer`); a version without it keeps today's;
- ``trust`` (exactly when ``graph_spec.trust_outputs`` is above zero): the version's self-trust training registration, the
  pinned ``derive`` module and the owner's ``sigma_floor`` (one per trust output), ``epochs`` and ``learning_rate``. The
  derive is staged alone into the build container, so it may import only `TRUST_IMPORTS`.

Every build site asks here FIRST and, for a version with no build row, runs the code it always ran. A version the code
serves itself (`code_serves`) is never read from a row, so no row can move a live version; only a NEW version of any
family, registered in ``version_overlay.json``, can be served by one. A malformed row refuses ITSELF: every build site
that asks about THAT version raises `ExamBuildRefused` (never the family's code, never a nearby version), and every other
version is served as before. `ExamBuildRefused` is Carbon's fault, not a recipe refusal, and no ValueError, so nothing
that catches a bad recipe or a bad document can read it as the miner's.

Host side only: the worker image and the build and inference containers have neither this module nor the file.
"""

from __future__ import annotations

import ast
import hashlib
import logging
import math
import re
from types import MappingProxyType

from . import exam_registry, pinned_module
from .code_served import code_serves

#: What a build module serves, each as ``function(challenge_id, version)`` (the shapes are `physical_public`'s,
#: `physical_public_train.load_public_train`'s and `physical_pack`'s for the same names); and its ``SCOPE``.
FUNCTIONS = (
    "construction_kit",
    "interface_document",
    "construction_limits_document",
    "trusted_material",
    "load_public_train",
    "development_bank",
    "physics_contract",
    "public_roles",
)
PROGRAMS = ("eager", "compiled", "per_case")
SPEC_FIELDS = (
    "train_sha256",
    "rows",
    "inputs",
    "outputs",
    "dtype",
    "trainer",
    "layout",
    "trust_outputs",
)
_BLOCK = {"module", "sha256", "graph_spec", "inference_program"}
_OPTIONAL = {"total_wall_seconds", "nonfinite_rule", "trust"}
#: The registered non-finite rules (`nonfinite_infer.RULE`; a test holds them equal).
NONFINITE_RULES = ("first_free_per_day.v1",)
_TRUST = {"derive", "sigma_floor", "epochs", "learning_rate"}
#: What a registered derive module may import: the build container stages no other Carbon module for it.
TRUST_IMPORTS = ("__future__", "jax", "math", "numpy")
_SHA = re.compile(r"[0-9a-f]{64}")
_LOG = logging.getLogger(__name__)
_REFUSED: dict = {}


class ExamBuildRefused(RuntimeError):
    """A version's registry row or build block is refused, or its module serves less than `FUNCTIONS` (Carbon's fault)."""


def _count(value, low=1):
    return type(value) is int and value >= low


def _check_spec(spec) -> None:
    if type(spec) is not dict or set(spec) != set(SPEC_FIELDS):
        raise ExamBuildRefused("build_graph_spec_fields")
    if (
        type(spec["train_sha256"]) is not str
        or not _SHA.fullmatch(spec["train_sha256"])
        or not all(_count(spec[name]) for name in ("rows", "inputs", "outputs"))
        or spec["dtype"] not in ("float32", "float64")
        or spec["trainer"] not in ("v2", "v3")
        or not (spec["layout"] is None or type(spec["layout"]) is dict)
        or (spec["layout"] is not None and spec["trainer"] != "v3")
        or not _count(spec["trust_outputs"], 0)
    ):
        raise ExamBuildRefused("build_graph_spec_value")


def _number(value) -> bool:
    return (
        type(value) is int or (type(value) is float and math.isfinite(value))
    ) and abs(value) <= 1e308


def _check_trust(trust, outputs) -> None:
    if type(trust) is not dict or set(trust) != _TRUST:
        raise ExamBuildRefused("build_trust_fields")
    floor = trust["sigma_floor"]
    if (
        type(floor) is not list
        or len(floor) != outputs
        or not all(_number(value) and value >= 0 for value in floor)
        or not _count(trust["epochs"])
        or not _number(trust["learning_rate"])
        or trust["learning_rate"] <= 0
    ):
        raise ExamBuildRefused("build_trust_value")
    try:
        pinned_module.check(trust["derive"])
        source = pinned_module.source_file(trust["derive"]["module"]).read_bytes()
    except (pinned_module.PinnedModuleRefused, OSError) as error:
        raise ExamBuildRefused(str(error)) from error
    _check_derive(source)


def _check_derive(source: bytes) -> None:
    """A derive module defines ``derive`` and imports nothing its container does not have."""
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError) as error:
        raise ExamBuildRefused("build_trust_derive_unparseable") from error
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = ["." if node.level else node.module]
        else:
            continue
        if any(name.split(".")[0] not in TRUST_IMPORTS for name in names):
            raise ExamBuildRefused("build_trust_derive_import")
    if not any(
        isinstance(node, ast.FunctionDef) and node.name == "derive"
        for node in tree.body
    ):
        raise ExamBuildRefused("build_trust_derive_missing")


def _check(key, block) -> None:
    from carbon.challenge_kit import version_registry

    if type(block) is not dict or set(block) - _OPTIONAL != _BLOCK:
        raise ExamBuildRefused("build_block_fields")
    entry = version_registry.entry(*key)
    if "total_wall_seconds" in block and not _count(
        block["total_wall_seconds"],
        version_registry.task_wall_seconds(entry.rebuild_wall_seconds),
    ):
        raise ExamBuildRefused("build_total_wall_seconds")
    spec, program = block["graph_spec"], block["inference_program"]
    if "nonfinite_rule" in block and (
        block["nonfinite_rule"] not in NONFINITE_RULES or spec is None
    ):
        raise ExamBuildRefused("build_nonfinite_rule")
    if (spec is not None) != (entry.graph_adapter == "v2"):
        raise ExamBuildRefused("build_graph_spec_differs_from_the_version")
    if spec is None:
        if program is not None:
            raise ExamBuildRefused("build_inference_program")
    else:
        _check_spec(spec)
        if program not in PROGRAMS:
            raise ExamBuildRefused("build_inference_program")
        if program == "per_case" and spec["trust_outputs"]:
            # the per-case program has no trust variant (`v2_trust_infer_query`)
            raise ExamBuildRefused("build_inference_program_trust")
    trust_outputs = 0 if spec is None else spec["trust_outputs"]
    if ("trust" in block) != (trust_outputs > 0):
        raise ExamBuildRefused("build_trust_differs_from_the_spec")
    if trust_outputs:
        _check_trust(block["trust"], trust_outputs)
    try:
        pinned_module.check({name: block[name] for name in ("module", "sha256")})
    except pinned_module.PinnedModuleRefused as error:
        raise ExamBuildRefused(str(error)) from error


def block(challenge_id: str, version: str) -> dict | None:
    """The version's checked build block (a fresh copy), or None: it has no build row, or the code serves it. A refused
    row raises `ExamBuildRefused`."""
    key = (challenge_id, version)
    if code_serves(*key):
        if exam_registry.field(*key, "build") is not None:
            _note(key, "build_version_is_code_served")
        return None
    try:
        found = exam_registry.require(*key, "build")
        if found is not None:
            _check(key, found)
    except exam_registry.ExamRowRefused as error:
        _note(key, str(error))
        raise ExamBuildRefused(str(error)) from error
    except ExamBuildRefused as error:
        _note(key, str(error))
        raise
    return found


def _note(key, reason) -> None:
    if _REFUSED.get(key) != reason:
        _REFUSED[key] = reason
        _LOG.warning("exam registry build row %r refused: %s", key, reason)


def refused() -> dict:
    """``{(challenge id, version): reason}`` of every build block refused so far."""
    return dict(_REFUSED)


def keys() -> tuple:
    """Every (challenge id, version) a build row serves (a refused row serves none, and stops no other)."""

    def serves(key):
        try:
            return block(*key) is not None
        except ExamBuildRefused:
            return False

    return tuple(key for key in exam_registry.keys("build") if serves(key))


def module(challenge_id: str, version: str):
    """The module that serves the version's construction material, or None: the code serves it, or nothing does."""
    found = block(challenge_id, version)
    if found is None:
        return None
    try:
        loaded = pinned_module.load(
            {name: found[name] for name in ("module", "sha256")}
        )
    except pinned_module.PinnedModuleRefused as error:
        raise ExamBuildRefused(str(error)) from error
    missing = [name for name in FUNCTIONS if not callable(getattr(loaded, name, None))]
    if missing or type(getattr(loaded, "SCOPE", None)) is not str:
        raise ExamBuildRefused(f"build_module_incomplete: {missing or ['SCOPE']}")
    return loaded


def total_wall_seconds(challenge_id: str, version: str) -> int | None:
    """The whole-task wall the version's build row names, or None."""
    found = block(challenge_id, version)
    return None if found is None else found.get("total_wall_seconds")


def nonfinite_rule(challenge_id: str, version: str) -> str | None:
    """The non-finite rule the version's build row names, or None."""
    found = block(challenge_id, version)
    return None if found is None else found.get("nonfinite_rule")


def trust(challenge_id: str, version: str) -> dict | None:
    """The version's registered trust values and derive block (a fresh copy), or None: it offers no trust interface."""
    found = block(challenge_id, version)
    return None if found is None else found.get("trust")


def trust_derive_source(challenge_id: str, version: str) -> bytes:
    """The exact bytes of the version's derive module that its build container is staged with: read once and hashed as
    read (CRLF as LF), so the staged bytes are the registered ones."""
    found = trust(challenge_id, version)
    if found is None:
        raise ExamBuildRefused("build_trust_not_registered")
    named = found["derive"]
    try:
        raw = pinned_module.source_file(named["module"]).read_bytes()
    except (pinned_module.PinnedModuleRefused, OSError) as error:
        raise ExamBuildRefused(str(error)) from error
    raw = raw.replace(b"\r\n", b"\n")
    if hashlib.sha256(raw).hexdigest() != named["sha256"]:
        raise ExamBuildRefused("build_trust_derive_differs")
    _check_derive(raw)
    return raw


def trust_derive(challenge_id: str, version: str):
    """The version's derive function on the host, from its pinned module, or None: it registers none."""
    found = trust(challenge_id, version)
    if found is None:
        return None
    try:
        return pinned_module.load(found["derive"]).derive
    except (pinned_module.PinnedModuleRefused, AttributeError) as error:
        raise ExamBuildRefused(str(error)) from error


def graph_specs():
    """``{(challenge id, version): graph_spec}`` of every build row that has one."""
    found = {key: block(*key)["graph_spec"] for key in keys()}
    return MappingProxyType({k: v for k, v in found.items() if v is not None})


def versions_running(*programs) -> frozenset:
    """The registered versions whose ``inference_program`` is one of ``programs``."""
    unknown = set(programs) - set(PROGRAMS)
    if unknown:
        raise KeyError(min(unknown))
    return frozenset(
        key for key in keys() if block(*key)["inference_program"] in programs
    )
