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
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from pathlib import Path

SCHEMA = "carbon.challenge-kit.version-overlay.v1"
# The repository root is found from the module spec: this module reads no package data of its own.
OVERLAY_PATH = (
    Path(__spec__.origin).resolve().parents[2]
    / "scripts"
    / "validator_host_classes"
    / "version_overlay.json"
)


class OverlayRefused(ValueError):
    """The overlay is malformed, redefines an image-registered version, or changes an entry already installed."""


_TUPLES = ("development_evaluation", "catalog_entries_from")
_INSTALLED: dict = {}


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
    return dict(_INSTALLED)


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
