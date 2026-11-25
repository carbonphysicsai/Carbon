"""Host-side registration of NEW Challenge FAMILIES (add-only), outside the worker image.

A family the code does not name is registered only by its row in
``scripts/validator_host_classes/family_registry.json`` (door-code design #1, v2 ruling row 4033; the same trust domain
as ``version_overlay.json``). A row holds what a family's shared code asks about it:

- ``kind``: the name the pool and practice tables dispatch on;
- ``opacity``: which per-row ids its copies rename (a subset of ``copy_derivation.OPAQUE``; may be empty);
- ``baseline``: the declared input bounds its learned baseline scales by and its registered (length, ridge), or null;
- ``modules``: by role, the ``carbon.*`` module that serves it, each with its file's sha256.

``install()`` (idempotent) reads the file and keeps every valid row:

- it is ADD-ONLY: a family the code serves already, a row that changes one an earlier ``install()`` kept, and a kind
  another family uses are refused;
- a refused row refuses ITSELF (logged, ``refused()``), never the file: one bad row cannot take another family down. A
  file that is not valid JSON, has a repeated key or has the wrong schema refuses whole (``FamilyRefused``);
- a module's file is hashed (CRLF read as LF) at ``install()`` and again before it is imported; a mismatch is refused
  and the module is never imported;
- a family with no row is unregistered: ``family()`` is None and every caller refuses it, never a nearby one.

A kept row EXTENDS, add-only, the tables the shared code keeps for its own families (`_extend`: the pool kind, the copy
opacity, the sealed target), so no shared producer file, adapter file or worker image input changes when a family is
registered: their bytes, and every digest made of them, are those of a process with no row (owner G-LEAD-97). A name a
table already holds is refused, never replaced, and the family's own pack names its modules by sha256.

The module is not a worker build input and nothing is installed in the worker image. The file ships empty, so nothing
here changes what any served family reads.
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import re
import sys
from pathlib import Path

from carbon.challenge_registry import pinned_module

SCHEMA = "carbon.challenge-kit.family-registry.v1"
REGISTRY_PATH = (
    Path(__spec__.origin).resolve().parents[2]
    / "scripts"
    / "validator_host_classes"
    / "family_registry.json"
)
#: The families the code serves itself (their tables stay code); a row naming one is refused. Families the worker image's
#: version registry declares are refused too (`_builtin`).
BUILTIN = frozenset(
    {
        "battery-fastcharge-ageing-development-v1",
        "chip-cold-plate",
        "electric-motor-magnetics",
        "f02",
        "f08-ribbed-bracket",
    }
)
#: The kind names the code's own tables use: a new family never takes one.
BUILTIN_KINDS = frozenset({"battery", "cooling", "f02", "f08", "motor", "registered"})
ROLES = ("bank", "kind", "sealed_grader", "sealed_kit")
_ROW = {"kind", "opacity", "baseline", "modules"}
#: `copy_derivation.OPAQUE` (a test holds them equal; not imported: that module loads the scoring packages).
_OPAQUE = ("case_id", "design_id", "condition_id")
_FAMILY = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
_KIND = re.compile(r"[a-z][a-z0-9_]*")
_MAX = sys.float_info.max
_LOG = logging.getLogger(__name__)

_INSTALLED: dict = {}
_REFUSED: dict = {}


class FamilyRefused(ValueError):
    """The family registry file, or one row of it, is refused."""


def _pairs(items):
    found = {}
    for name, value in items:
        if name in found:
            raise FamilyRefused(f"the family registry repeats the key {name!r}")
        found[name] = value
    return found


def canonical_digest(row: dict) -> str:
    body = json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()


def _builtin(challenge_id: str) -> bool:
    if challenge_id in BUILTIN:
        return True
    from . import version_overlay, version_registry

    return any(
        key[0] == challenge_id and not version_overlay.is_overlay(*key)
        for key in version_registry.VERSIONS
    )


def _number(value) -> bool:
    # a range check, never `math.isfinite`: that raises on an int no float holds
    return type(value) in (int, float) and -_MAX <= value <= _MAX


def _check_baseline(value) -> None:
    if value is None:
        return
    if not isinstance(value, dict) or set(value) != {"bounds", "length_ridge"}:
        raise FamilyRefused("baseline must be null or {bounds, length_ridge}")
    bounds, fit = value["bounds"], value["length_ridge"]
    if not isinstance(bounds, dict) or not bounds:
        raise FamilyRefused("baseline bounds must name every input")
    for name, pair in bounds.items():
        if (
            not isinstance(pair, list)
            or len(pair) != 2
            or not all(map(_number, pair))
            or not pair[0] < pair[1]
        ):
            raise FamilyRefused(f"baseline bound {name!r} must be [low, high]")
    if fit is not None and (
        not isinstance(fit, list)
        or len(fit) != 2
        or not all(_number(v) and v > 0 for v in fit)
    ):
        raise FamilyRefused("baseline length_ridge must be null or [length, ridge]")


def _check_row(challenge_id, row) -> None:
    if not _FAMILY.fullmatch(challenge_id):
        raise FamilyRefused("a family id is lowercase words joined by '-'")
    if _builtin(challenge_id):
        raise FamilyRefused("the code serves this family; a row may only add one")
    if not isinstance(row, dict) or set(row) != _ROW:
        raise FamilyRefused(f"a row has exactly {sorted(_ROW)}")
    kind = row["kind"]
    if not isinstance(kind, str) or not _KIND.fullmatch(kind):
        raise FamilyRefused("kind must be a lowercase name")
    if kind in BUILTIN_KINDS or any(
        other != challenge_id and known["kind"] == kind
        for other, known in _INSTALLED.items()
    ):
        raise FamilyRefused(f"kind {kind!r} belongs to another family")
    opacity = row["opacity"]
    if (
        not isinstance(opacity, list)
        or len(set(map(str, opacity))) != len(opacity)
        or not all(name in _OPAQUE for name in opacity)
    ):
        raise FamilyRefused(f"opacity must be a subset of {_OPAQUE}")
    _check_baseline(row["baseline"])
    modules = row["modules"]
    if not isinstance(modules, dict) or set(modules) - set(ROLES):
        raise FamilyRefused(f"modules may name only {ROLES}")
    try:
        for block in modules.values():
            pinned_module.check(block)
    except pinned_module.PinnedModuleRefused as error:
        raise FamilyRefused(str(error)) from error


def load(path=None) -> dict:
    """The file's rows by family, unchecked. Empty when the file is absent."""
    path = Path(REGISTRY_PATH if path is None else path)
    if not path.exists():
        return {}
    try:
        document = json.loads(path.read_bytes(), object_pairs_hook=_pairs)
    except FamilyRefused:
        raise
    except (ValueError, RecursionError) as error:
        raise FamilyRefused("the family registry is not valid JSON") from error
    if (
        not isinstance(document, dict)
        or document.get("schema") != SCHEMA
        or set(document) - {"schema", "source", "families"}
        or not isinstance(document.get("families"), dict)
    ):
        raise FamilyRefused("the family registry has the wrong schema")
    return document["families"]


def install(path=None) -> dict:
    """Keep the file's valid rows (add-only, idempotent); {family: row digest} of every kept row."""
    for challenge_id, row in load(path).items():
        try:
            known = _INSTALLED.get(challenge_id)
            if known is not None:
                if known != row:
                    raise FamilyRefused("installed before with a different row")
                continue
            _check_row(challenge_id, row)
            _extend(challenge_id, row)
        except FamilyRefused as error:
            _REFUSED[challenge_id] = str(error)
            _LOG.warning("family registry row %r refused: %s", challenge_id, error)
            continue
        _REFUSED.pop(challenge_id, None)
        _INSTALLED[challenge_id] = copy.deepcopy(row)
    return {name: canonical_digest(row) for name, row in _INSTALLED.items()}


def _extend(challenge_id, row) -> None:
    """Add the family to the shared tables (`FamilyRefused` if a table holds the name already: nothing is replaced). With no
    kept row this is never called and no scoring module is imported."""
    from carbon.challenge_kit import version_overlay
    from carbon.scoring import copy_derivation, pool_version

    grader = row["modules"].get("sealed_grader")
    tables = [
        (pool_version.KINDS, row["kind"]),
        (copy_derivation.OPAQUE_BY_CHALLENGE, tuple(row["opacity"])),
    ]
    if grader is not None:
        tables.append((version_overlay.SEALED_TARGET, grader["module"]))
    for table, _value in tables:
        if challenge_id in table:
            raise FamilyRefused(f"{challenge_id!r} is in a shared table already")
    for table, value in tables:
        table[challenge_id] = value


def families() -> tuple:
    """Every registered family, sorted."""
    return tuple(sorted(_INSTALLED))


def refused() -> dict:
    """{family: reason} of every row `install` refused."""
    return dict(_REFUSED)


def family(challenge_id: str) -> dict | None:
    """``{kind, opacity, baseline}`` of a registered family, or None (unregistered: the caller refuses it)."""
    row = _INSTALLED.get(challenge_id)
    if row is None:
        return None
    return {
        "kind": row["kind"],
        "opacity": tuple(row["opacity"]),
        "baseline": copy.deepcopy(row["baseline"]),
    }


def module(challenge_id: str, role: str):
    """A registered family's module for ``role``, hashed before it is imported (`FamilyRefused` without one)."""
    if role not in ROLES:
        raise FamilyRefused(f"{role!r} is not a family module role")
    row = _INSTALLED.get(challenge_id)
    if row is None or role not in row["modules"]:
        raise FamilyRefused(f"{challenge_id!r} registers no {role} module")
    try:
        return pinned_module.load(row["modules"][role])
    except pinned_module.PinnedModuleRefused as error:
        raise FamilyRefused(str(error)) from error


install()
