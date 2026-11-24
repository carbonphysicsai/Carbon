"""The per-version exam registry: one data row per ``"<challenge id> <version>"`` (owner G-LEAD-61: exam-agnostic code).

``version_registry`` (with its host overlay) says which Challenge versions exist. ``exam_registry.json`` holds the facts a
grade, a crown or a build needs about a version that has no row in a code table: a module that keeps a table of such facts
reads its own table first and then asks here, so adding an exam is a data row, not a code edit.

- ADD-ONLY beside the code tables: a row in code for a VERSION is read first and never moves, so a reader that finds one
  never asks here. A value held per Challenge (the speed gate's) is the fallback: the version's own row is read before it.
- CLOSED: a row may carry only the `FIELDS` below, each with the one shape its check accepts. What a value means (which
  file, which module, which number) is checked by the module that owns the field.
- ROW-WISE: a malformed row refuses ITSELF (`refusal`), never the file, so one bad row cannot take another exam down. A
  reader that must not fail open asks `require` (typed `ExamRowRefused`), never `field` alone. A file that is not a
  registry at all is refused whole (`ExamRegistryRefused`), as the version overlay is: not JSON, another schema, a
  duplicate key or a NaN / Infinity word anywhere (even inside one row), or nesting the JSON reader cannot take.
- A row for a version the version registry does not name is kept but answers nothing until that version is registered.
- A missing file registers nothing.

Standard library only; no hidden, sealed or custody material: every value here is public registration data. The file sits
under a grading-path prefix, so a change to it is an exam change like any other.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import re
from pathlib import Path

SCHEMA = "carbon.challenge-registry.exam-registry.v1"
REGISTRY = Path(__file__).with_name("exam_registry.json")

_LOG = logging.getLogger(__name__)
_KEY = re.compile(r"[a-z0-9][a-z0-9-]{0,63} [0-9]+(?:\.[0-9]+)*")
_SHA = re.compile(r"[0-9a-f]{64}")
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
_NAME = re.compile(r"[a-z0-9][a-z0-9.-]{0,63}")
_TITLE = re.compile(r"[A-Za-z0-9][A-Za-z0-9 ,.()&+/-]{0,119}")
_PATH = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]*(?:/[A-Za-z0-9_][A-Za-z0-9_.-]*)*")


class ExamRegistryRefused(ValueError):
    """The file is not an exam registry, or an installed row would change."""


class ExamRowRefused(ValueError):
    """The version's row is malformed: nothing is read from it."""


def _is(value, names):
    return type(value) is dict and set(value) == set(names)


def _positive(value):
    try:
        return type(value) in (int, float) and math.isfinite(value) and value > 0
    except OverflowError:  # an integer too large for a float is no measured value
        return False


#: How deep a row may nest; deeper refuses the row (the digest and the copies below would recurse).
MAX_DEPTH = 32


def plain(value):
    """Whether a row's value nests at most `MAX_DEPTH` deep and holds only finite numbers (1e999 reads as infinity)."""
    level = [value]
    for _ in range(MAX_DEPTH):
        inner = []
        for item in level:
            if type(item) is dict:
                inner += item.values()
            elif type(item) is list:
                inner += item
            elif type(item) is float and not math.isfinite(item):
                return False
        if not inner:
            return True
        level = inner
    return False


def _matches(pattern, value):
    return type(value) is str and pattern.fullmatch(value) is not None


def _file(value):
    """``{path, sha256}``: a file inside the checkout (forward slashes, no part that starts with a dot) and its digest."""
    return (
        _is(value, ("path", "sha256"))
        and _matches(_SHA, value["sha256"])
        and _matches(_PATH, value["path"])
    )


def _lane_hours(value):
    return (
        _is(value, ("value", "measurement_digest"))
        and _positive(value["value"])
        and _matches(_DIGEST, value["measurement_digest"])
    )


def _solver_seconds(value):
    return (
        _is(value, ("value", "source"))
        and _positive(value["value"])
        and type(value["source"]) is str
        and bool(value["source"].strip())
    )


def _terms(value):
    return (
        _is(value, ("version", "sha256"))
        and _matches(_NAME, value["version"])
        and _matches(_SHA, value["sha256"])
    )


def _object(value):
    return type(value) is dict and bool(value)


def _entry(value):
    return (
        _is(value, ("title", "portfolio", "status"))
        and _matches(_TITLE, value["title"])
        and value["portfolio"] in ("launch", "launch_pending_readiness")
        and value["status"] in ("open", "retired")
    )


#: Every field a row may carry -> the check of its shape.
FIELDS = {
    # the measured mean GPU-lane-hours of one graded submission (`exam_cap`)
    "rebuild_gpu_lane_hours": _lane_hours,
    # the reference solver's seconds per design (`speed_gate`): the owner's value and where it is recorded
    "solver_seconds_per_design": _solver_seconds,
    # the submission terms the version's submissions must accept (`submission_terms`)
    "terms": _terms,
    # the practice verify set and its receipted digest (`verify_practice`)
    "verify_set": _file,
    # the published exam block's file (`published_exam`)
    "published": _file,
    # the build side: the build reader owns its inner shape
    "build": _object,
    # what a miner can list and select: the catalog entry (`exam_entry`)
    "entry": _entry,
}

#: ``{(challenge id, version): (row, digest)}`` of every installed row, and ``{name: reason}`` of every refused one.
_ROWS: dict = {}
_REFUSED: dict = {}


def canonical_digest(row: dict) -> str:
    body = json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()


def _no_duplicates(pairs):
    found = dict(pairs)
    if len(found) != len(pairs):
        raise ExamRegistryRefused("exam_registry_duplicate_key")
    return found


def _no_constant(name):
    raise ExamRegistryRefused(f"exam_registry_number: {name}")


def _document(path):
    try:
        raw = Path(path).read_bytes()
    except FileNotFoundError:
        return {}
    except OSError as failure:
        raise ExamRegistryRefused("exam_registry_unreadable") from failure
    try:
        document = json.loads(
            raw, object_pairs_hook=_no_duplicates, parse_constant=_no_constant
        )
    except ExamRegistryRefused:
        raise
    except (ValueError, RecursionError) as failure:
        raise ExamRegistryRefused("exam_registry_not_json") from failure
    if (
        not _is(document, ("schema", "source", "exams"))
        or document["schema"] != SCHEMA
        or type(document["source"]) is not str
        or type(document["exams"]) is not dict
    ):
        raise ExamRegistryRefused("exam_registry_schema")
    return document["exams"]


def _row_refusal(row):
    """Why a row is refused, or None."""
    if not _object(row):
        return "row_not_an_object"
    unknown = sorted(set(row) - set(FIELDS))
    if unknown:
        return f"unknown_field: {unknown[0]}"
    for name in sorted(row):
        if not plain(row[name]) or not FIELDS[name](row[name]):
            return f"malformed_field: {name}"
    return None


def install(path=None) -> dict:
    """Read a registry file's rows (add-only, idempotent): ``{(challenge id, version): digest}`` of every row in force.

    A row that was installed or refused before and is now another row refuses the whole call; nothing is merged.
    """
    good, bad = {}, {}
    for name, row in _document(REGISTRY if path is None else path).items():
        reason = (
            _row_refusal(row) if _matches(_KEY, name) else "key_not_a_challenge_version"
        )
        if reason is None:
            challenge_id, _, version = name.partition(" ")
            good[(challenge_id, version)] = (row, canonical_digest(row))
        else:
            bad[name] = reason
    for key, (_, row_digest) in good.items():
        name = " ".join(key)
        if name in _REFUSED or (key in _ROWS and _ROWS[key][1] != row_digest):
            raise ExamRegistryRefused(f"exam_registry_row_changed: {name}")
    for name in bad:
        challenge_id, _, version = name.partition(" ")
        if (challenge_id, version) in _ROWS:
            raise ExamRegistryRefused(f"exam_registry_row_changed: {name}")
    for name, reason in bad.items():
        if name not in _REFUSED:
            _LOG.warning("exam registry row %r refused: %s", name, reason)
    _ROWS.update(good)
    _REFUSED.update(bad)
    return {key: row_digest for key, (_, row_digest) in _ROWS.items()}


def _registered(challenge_id, version):
    from carbon.challenge_kit import version_registry

    return version_registry.find(challenge_id, version) is not None


def refused() -> dict:
    """``{row name: reason}`` of every refused row."""
    return dict(_REFUSED)


def refused_keys() -> tuple:
    """The registered (challenge id, version) pairs whose row is refused, sorted as `keys`."""
    found = [
        (challenge_id, version)
        for challenge_id, _, version in (
            name.partition(" ") for name in _REFUSED if _matches(_KEY, name)
        )
        if _registered(challenge_id, version)
    ]
    return tuple(sorted(found, key=_order))


def _order(key):
    return key[0], tuple(map(int, key[1].split(".")))


def refusal(challenge_id, version):
    """Why this version's row is refused, or None (no row, or a good one)."""
    return _REFUSED.get(f"{challenge_id} {version}")


def field(challenge_id, version, name):
    """One field of a registered version's row (a fresh copy), or None: no row, no such field, a refused row, or a
    version the version registry does not name."""
    if name not in FIELDS:
        raise KeyError(name)
    found = _ROWS.get((challenge_id, version))
    if found is None or name not in found[0] or not _registered(challenge_id, version):
        return None
    return json.loads(json.dumps(found[0][name]))


def require(challenge_id, version, name):
    """`field`, refusing typed (`ExamRowRefused`) when the version HAS a row and it is malformed (never read as absent)."""
    reason = refusal(challenge_id, version)
    if reason is not None:
        raise ExamRowRefused(f"{challenge_id} {version}: {reason}")
    return field(challenge_id, version, name)


def keys(name) -> tuple:
    """The registered (challenge id, version) pairs whose row carries ``name``, by Challenge, then by version."""
    if name not in FIELDS:
        raise KeyError(name)
    found = [
        key for key, (row, _) in _ROWS.items() if name in row and _registered(*key)
    ]
    return tuple(sorted(found, key=_order))


def newest(keys_of_one_challenge):
    """The newest of (challenge id, version) pairs of one Challenge."""
    return max(keys_of_one_challenge, key=_order)


def digest(challenge_id, version):
    """The canonical digest of the version's row, or None."""
    found = _ROWS.get((challenge_id, version))
    return None if found is None else found[1]


install()

__all__ = [
    "FIELDS",
    "MAX_DEPTH",
    "REGISTRY",
    "SCHEMA",
    "ExamRegistryRefused",
    "ExamRowRefused",
    "canonical_digest",
    "digest",
    "field",
    "install",
    "keys",
    "newest",
    "plain",
    "refusal",
    "refused",
    "refused_keys",
    "require",
]
