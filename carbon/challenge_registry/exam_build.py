"""The build half of a registered exam: what a build reads about a version that has no code-table row (owner G-LEAD-61).

A row of ``exam_registry.json`` may carry ``build``:

- ``module``, ``sha256``: the ``carbon.*`` module that serves the version's public construction material
  (`FUNCTIONS`), hashed before it is imported (`pinned_module`);
- ``graph_spec``: the graph route v2 facts of the version (`SPEC_FIELDS`), or null when it takes no graph recipes;
- ``inference_program``: ``eager``, ``compiled`` or ``per_case`` (null exactly when ``graph_spec`` is);
- ``total_wall_seconds`` (may be left out): the version's whole-task wall, an owner value at or above the one every
  version with its rebuild wall has (`version_registry.task_wall_seconds`); raise-only.

Every build site asks here FIRST and, for a version with no build row, runs the code it always ran. A version the code
serves itself (`code_serves`) is never read from a row, so no row can move a live version; only a NEW version of any
family, registered in ``version_overlay.json``, can be served by one. A malformed row refuses ITSELF: every build site
that asks about THAT version raises `ExamBuildRefused` (never the family's code, never a nearby version), and every other
version is served as before. `ExamBuildRefused` is Carbon's fault, not a recipe refusal, and no ValueError, so nothing
that catches a bad recipe or a bad document can read it as the miner's.

Host side only: the worker image and the build and inference containers have neither this module nor the file.
"""

from __future__ import annotations

import logging
import re
from types import MappingProxyType

from . import exam_registry, pinned_module

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
_OPTIONAL = {"total_wall_seconds"}
#: The host-overlay versions the code's own tables serve (Motor 1.9's reserved one included). Closed: a later version is
#: a row, never a new name here. Every version of the worker image's registry is code-served too (`code_serves`).
CODE_SERVED_OVERLAY = frozenset(
    {
        ("chip-cold-plate", "1.7"),
        ("chip-cold-plate", "1.8"),
        ("electric-motor-magnetics", "1.6"),
        ("electric-motor-magnetics", "1.8"),
        ("electric-motor-magnetics", "1.9"),
    }
)
_SHA = re.compile(r"[0-9a-f]{64}")
_LOG = logging.getLogger(__name__)
_REFUSED: dict = {}


class ExamBuildRefused(RuntimeError):
    """A version's registry row or build block is refused, or its module serves less than `FUNCTIONS` (Carbon's fault)."""


def code_serves(challenge_id: str, version: str) -> bool:
    """Whether the code's own tables serve the version (a build row for it is refused)."""
    from carbon.challenge_kit import version_overlay

    key = (challenge_id, version)
    return key in CODE_SERVED_OVERLAY or not version_overlay.is_overlay(*key)


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
