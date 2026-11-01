"""Host-side registration of NEW Challenge versions (add-only), outside the worker image.

``version_registry.py`` is a worker-image build input: a change to it moves the image id and voids every live pack. The
worker image reads no per-version registry fact (it takes an allowlist string and the ``REBUILD_LIMIT_SECONDS``
constant), so a NEW version's registration can live on the host, in ``scripts/validator_host_classes/version_overlay.json``,
the same trust domain as ``pool_constants.json``.

``install()`` (idempotent) runs at the end of ``version_registry.py`` and merges the overlay's entries into
``version_registry.VERSIONS`` in place, before any module derives a set from it:

- it is ADD-ONLY: an entry whose (Challenge, version) the image already registers, or one that changes an entry an
  earlier ``install()`` added, is refused (``OverlayRefused``), never merged;
- each entry's canonical sha256 is its registration digest (``entry_digest``); a pack that serves the version binds it,
  so a changed overlay entry is a different version identity and an old pack is refused;
- a missing overlay file registers nothing: a version that is only in the overlay is then unregistered, and every
  caller refuses it (``UnregisteredVersion``), never a nearby one.

This module is a worker build input beside ``version_registry.py``; in the image the overlay file is absent, so nothing is
added and the image's registry is exactly what it declares.

The hook was added to the worker image once (Validator, 2026-11-01); a later version is an overlay entry, not an image change.

DISPATCH (image-move3d, Validator 2026-11-01). A version whose SEALED adapter is a new module is reached only through the
Challenge's sealed grader module (`motor_sealed_dual_pack` and its peers), whose bytes are a live producer identity and must
not move. An entry may therefore carry ``dispatch: {module, sha256, config?}``: ``module`` is a ``carbon.*`` dispatch module,
``sha256`` the sha256 of its file (CRLF read as LF), checked BEFORE the module is imported (a mismatch is refused). When the
Challenge's sealed module is imported (or at once if it already is), the dispatch module's ``dispatch(config)`` result is
registered through the sealed module's EXISTING tables: its ``POOL_VERSIONS`` entry and wrappers around its ``adapter``,
``sealed_adapter``, ``adapter_for_bank`` and ``write_sealed_pack`` that serve the overlay version and DELEGATE UNCHANGED for
every other version. It is add-only: a version the sealed module already registers is refused. The sealed module's bytes
(so every producer digest) never change, and with no ``dispatch`` entry nothing here runs. Generic: keyed by (Challenge,
version), usable by any new sealed adapter.
"""

from __future__ import annotations

import dataclasses
import hashlib
import importlib
import importlib.abc
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import ClassVar

SCHEMA = "carbon.challenge-kit.version-overlay.v1"
# The repository root is found from the module spec: this module reads no package data of its own.
OVERLAY_PATH = (
    Path(__spec__.origin).resolve().parents[2]
    / "scripts"
    / "validator_host_classes"
    / "version_overlay.json"
)


#: The repository root (the dispatch module is found and hashed under it, never imported before it is checked).
_ROOT = Path(__spec__.origin).resolve().parents[2]
#: The sealed grader module of each Challenge, whose tables a dispatch extends.
SEALED_TARGET = {
    "electric-motor-magnetics": "carbon.scoring.motor_sealed_dual_pack",
    "f02": "carbon.scoring.f02_sealed_dual_pack",
    "f08-ribbed-bracket": "carbon.scoring.f08_sealed_dual_pack",
    "chip-cold-plate": "carbon.scoring.cooling_encoded_dual_pack",
}
_SHA = re.compile(r"[0-9a-f]{64}")
_MODULE = re.compile(r"carbon(\.[a-z_][a-z0-9_]*)+")


class OverlayRefused(ValueError):
    """The overlay is malformed, redefines an image-registered version, or changes an entry already installed."""


_TUPLES = ("development_evaluation", "catalog_entries_from")
_INSTALLED: dict = {}
#: The validated ``dispatch`` blocks by (Challenge, version), filled by `load`.
_DISPATCH: dict = {}
#: Dispatches armed (waiting for their sealed module) or applied, by (Challenge, version).
_ARMED: dict = {}
_APPLIED: set = set()


def _registry():
    # Resolved lazily: `version_registry` calls `install()` at its own end, so it may be only partly initialised when
    # this module is first imported (and this module may be the one imported first).
    from . import version_registry

    return version_registry


def canonical_digest(entry: dict) -> str:
    body = json.dumps(entry, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()


def _build(entry: dict):
    registry = _registry()
    entry = {k: v for k, v in entry.items() if k != "dispatch"}
    unknown = set(entry) - {f.name for f in dataclasses.fields(registry.Version)}
    if unknown:
        raise OverlayRefused(f"unknown version fields {sorted(unknown)}")
    fields = {
        k: (tuple(v) if k in _TUPLES and v is not None else v) for k, v in entry.items()
    }
    try:
        return registry.Version(**fields)
    except TypeError as error:
        raise OverlayRefused(f"incomplete version entry: {error}") from error


def load(path=None) -> dict:
    """The overlay's entries by (Challenge, version): {key: (Version, digest)}. Empty when the file is absent."""
    path = Path(OVERLAY_PATH if path is None else path)
    if not path.exists():
        return {}
    try:
        document = json.loads(path.read_bytes())
    except ValueError as error:
        raise OverlayRefused("the version overlay is not valid JSON") from error
    if not isinstance(document, dict) or document.get("schema") != SCHEMA:
        raise OverlayRefused("the version overlay has the wrong schema")
    found = {}
    for name, entry in (document.get("versions") or {}).items():
        if not isinstance(entry, dict):
            raise OverlayRefused(f"{name!r}: an entry must be an object")
        version = _build(entry)
        key = (version.challenge_id, version.version)
        if name != f"{key[0]} {key[1]}":
            raise OverlayRefused(f"{name!r} does not name its own Challenge version")
        if "dispatch" in entry:
            _DISPATCH[key] = _check_dispatch(key, entry["dispatch"])
        found[key] = (version, canonical_digest(entry))
    return found


def install(path=None) -> dict:
    """Merge the overlay into the registry (add-only, idempotent); returns {key: digest} of every overlay entry."""
    registry = _registry()
    entries = load(path)
    image_keys = frozenset(registry.VERSIONS) - frozenset(_INSTALLED)
    for key, (version, digest) in entries.items():
        if key in image_keys:
            raise OverlayRefused(
                f"{key!r} is registered by the worker image's registry; the overlay may only add new versions"
            )
        known = _INSTALLED.get(key)
        if known is not None and known != digest:
            raise OverlayRefused(f"{key!r} was installed with a different entry")
    for key, (version, digest) in entries.items():
        if key not in _INSTALLED:
            registry.VERSIONS[key] = version
            _INSTALLED[key] = digest
    for key in entries:
        if key in _DISPATCH:
            _arm(key, _DISPATCH[key])
    return dict(_INSTALLED)


# --- dispatch ------------------------------------------------------------------------------------------------------


def _dispatch_file(module: str) -> Path:
    if not _MODULE.fullmatch(module):
        raise OverlayRefused(f"dispatch module {module!r} must be a carbon.* module")
    return _ROOT.joinpath(*module.split(".")).with_suffix(".py")


def _file_sha256(path: Path) -> str:
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise OverlayRefused(
            f"dispatch module file {path.name} is unreadable"
        ) from error
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def _check_dispatch(key, block) -> dict:
    """The block's shape and the dispatch module file's sha256, checked WITHOUT importing the module."""
    if (
        not isinstance(block, dict)
        or not {"module", "sha256"} <= set(block)
        or set(block) - {"module", "sha256", "config"}
        or not isinstance(block["module"], str)
        or not isinstance(block["sha256"], str)
        or not _SHA.fullmatch(block["sha256"])
        or not isinstance(block.get("config", {}), dict)
    ):
        raise OverlayRefused(f"{key!r}: malformed dispatch block")
    if key[0] not in SEALED_TARGET:
        raise OverlayRefused(
            f"{key!r}: no sealed grader module is registered for this Challenge"
        )
    if _file_sha256(_dispatch_file(block["module"])) != block["sha256"]:
        raise OverlayRefused(
            f"{key!r}: the dispatch module's sha256 does not match the entry"
        )
    return {"module": block["module"], "config": block.get("config", {})}


class _After(importlib.abc.MetaPathFinder):
    """Runs `_apply_pending` right after a sealed grader module finishes importing."""

    _busy: ClassVar[set] = set()

    def find_spec(self, name, path=None, target=None):
        if name in self._busy or name not in {SEALED_TARGET[k[0]] for k in _ARMED}:
            return None
        self._busy.add(name)
        try:
            spec = importlib.util.find_spec(name)
        finally:
            self._busy.discard(name)
        if (
            spec is None
            or spec.loader is None
            or not hasattr(spec.loader, "exec_module")
        ):
            return None
        loader = spec.loader
        real = loader.exec_module

        def exec_module(module):
            real(module)
            _apply_pending(name, module)

        loader.exec_module = exec_module
        return spec


_FINDER = _After()


def _arm(key, block) -> None:
    if key in _ARMED:
        if _ARMED[key] != block:
            raise OverlayRefused(f"{key!r} was armed with a different dispatch")
        return
    _ARMED[key] = block
    target = SEALED_TARGET[key[0]]
    if target in sys.modules:
        _apply_pending(target, sys.modules[target])
    elif _FINDER not in sys.meta_path:
        sys.meta_path.insert(0, _FINDER)


def _apply_pending(target_name, module) -> None:
    for key, block in list(_ARMED.items()):
        if SEALED_TARGET[key[0]] == target_name and key not in _APPLIED:
            _extend(module, key, block)
            _APPLIED.add(key)


def _extend(target, key, block) -> None:
    """Register one overlay version in a sealed grader module's existing tables; every other version delegates unchanged."""
    version = key[1]
    pools = getattr(target, "POOL_VERSIONS", None)
    if not isinstance(pools, dict):
        raise OverlayRefused(f"{target.__name__} has no POOL_VERSIONS table to extend")
    if version in pools or version in getattr(target, "VERSIONS", {}):
        raise OverlayRefused(
            f"{key!r} is registered by {target.__name__}; a dispatch may only add new versions"
        )
    module = importlib.import_module(block["module"])
    spec = module.dispatch(block["config"])
    if spec["version"] != version or spec["challenge"] != key[0]:
        raise OverlayRefused(f"{key!r}: the dispatch module registers another version")
    pools[version] = tuple(spec["pool_versions"])
    if isinstance(getattr(target, "VERSIONS", None), dict):
        target.VERSIONS[version] = tuple(spec["pool_versions"])
    # (function name in the sealed module, the version's position in its call, the dispatch spec's key)
    for name, position, entry in (
        ("adapter", 0, "adapter"),
        ("sealed_adapter", 0, "adapter"),
        ("adapter_for_bank", 1, "adapter_for_bank"),
        ("write_sealed_pack", None, "writer"),
    ):
        original = getattr(target, name, None)
        mine = spec.get(entry)
        if original is not None and mine is not None:
            setattr(target, name, _wrapper(original, mine, version, position))


def _wrapper(original, mine, version, position):
    def wrapped(*args, **kwargs):
        if position is None:
            chosen = kwargs.get("version")
        else:
            chosen = args[position] if len(args) > position else kwargs.get("version")
        if chosen == version:
            return mine(*args, **kwargs)
        return original(*args, **kwargs)

    wrapped.__wrapped__ = original
    wrapped.__name__ = getattr(original, "__name__", "wrapped")
    return wrapped


def entry_digest(challenge_id: str, version: str) -> str:
    """The registration digest of an overlay version (``OverlayRefused`` for one the overlay does not add)."""
    install()
    try:
        return _INSTALLED[(challenge_id, version)]
    except KeyError:
        raise OverlayRefused(
            f"{(challenge_id, version)!r} is not an overlay version"
        ) from None


def is_overlay(challenge_id: str, version: str) -> bool:
    return (challenge_id, version) in _INSTALLED
