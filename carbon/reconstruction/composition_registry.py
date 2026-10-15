"""Digest-checked composition metadata; no executable construction compiler.

Doors recognize a development contract from these public records. Acceptance
still requires the separately supplied development compiler and its bounds.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

DIRECTORY = Path(__file__).with_name("development_compositions")
SCHEMA = "carbon.development-composition-registry.v1"
DOCUMENT_SCHEMA = "carbon.development-composition.v1"
_NAME = re.compile(r"[a-z0-9][a-z0-9-]{0,80}\Z")
_SHA = re.compile(r"sha256:[0-9a-f]{64}\Z")
_KEYS = {
    "schema",
    "version",
    "challenge",
    "scope",
    "authority",
    "review",
    "participant_code",
    "base_contract",
    "composes",
}


def registry(directory=None):
    directory = DIRECTORY if directory is None else Path(directory)
    try:
        value = json.loads((directory / "registry.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise RuntimeError("composition registry unreadable") from None
    versions = value.get("versions") if type(value) is dict else None
    current = value.get("current") if type(value) is dict else None
    if (
        type(value) is not dict
        or set(value) != {"schema", "versions", "current"}
        or value["schema"] != SCHEMA
        or type(versions) is not dict
        or not all(
            type(k) is str
            and _NAME.fullmatch(k)
            and type(v) is str
            and _SHA.fullmatch(v)
            for k, v in versions.items()
        )
        or len(set(versions.values())) != len(versions)
        or type(current) is not dict
        or not all(
            type(k) is str and k and type(v) is str and v in versions
            for k, v in current.items()
        )
    ):
        raise RuntimeError("composition registry malformed")
    return value


def document(value, directory=None):
    directory = DIRECTORY if directory is None else Path(directory)
    versions = registry(directory)["versions"]
    by_digest = {v: k for k, v in versions.items()}
    name = (
        value
        if type(value) is str and value in versions
        else by_digest.get(value) if type(value) is str else None
    )
    if name is None:
        return None
    try:
        doc = json.loads((directory / (name + ".json")).read_text(encoding="utf-8"))
        raw = json.dumps(
            doc, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    except (OSError, ValueError, TypeError):
        raise RuntimeError("composition document unreadable") from None
    if "sha256:" + hashlib.sha256(raw).hexdigest() != versions[name]:
        raise RuntimeError("composition document changed")
    if (
        type(doc) is not dict
        or set(doc) != _KEYS
        or doc["schema"] != DOCUMENT_SCHEMA
        or doc["version"] != name
        or type(doc["challenge"]) is not str
        or not doc["challenge"]
        or doc["scope"] != "DEVELOPMENT"
        or doc["participant_code"] is not False
    ):
        raise RuntimeError("composition document malformed")
    base, entries = doc["base_contract"], doc["composes"]
    if (
        type(base) is not dict
        or set(base) != {"digest", "record_sequence"}
        or type(base["digest"]) is not str
        or not _SHA.fullmatch(base["digest"])
        or type(base["record_sequence"]) is not int
        or base["record_sequence"] < 1
        or type(entries) is not list
        or not entries
    ):
        raise RuntimeError("composition document malformed")
    levels = set()
    for entry in entries:
        if (
            type(entry) is not dict
            or set(entry) != {"level", "version", "digest"}
            or type(entry["level"]) is not int
            or not 1 <= entry["level"] <= 4
            or entry["level"] in levels
            or type(entry["version"]) is not str
            or not _NAME.fullmatch(entry["version"])
            or type(entry["digest"]) is not str
            or not _SHA.fullmatch(entry["digest"])
        ):
            raise RuntimeError("composition document malformed")
        levels.add(entry["level"])
    return doc


def names(directory=None):
    versions = registry(directory)["versions"]
    return frozenset(versions) | frozenset(versions.values())
