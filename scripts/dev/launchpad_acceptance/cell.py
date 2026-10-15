"""Prospective public-cell validation and append-only writing.

No evidence is collected here. The caller supplies an observation explicitly;
validation does not authenticate it or confer scientific/security authority.
Historical cells remain readable through T06, without prospective rewriting.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

from .matrix import BY_CELL
from .release_check import _REQUIRED, ROOT, _cell, _nonfinite, _unique

_CODE = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,95}\Z")
_FIELD = re.compile(r"[a-z][a-z0-9_]{0,79}\Z")
_DIGEST = re.compile(r"(?:sha256:[0-9a-f]{64}|git:[0-9a-f]{40})\Z")
_FORBIDDEN = {
    "key",
    "keys",
    "secret",
    "secrets",
    "token",
    "tokens",
    "password",
    "credential",
    "credentials",
    "authorization",
    "account",
    "wallet",
    "hotkey",
    "address",
    "addresses",
    "hostname",
    "host",
    "ip",
    "endpoint",
    "balance",
    "balances",
    "spend",
    "spent",
    "cost",
    "amount",
    "price",
    "profile",
    "profiles",
    "seed",
    "seeds",
    "hidden",
    "protected",
    "score",
    "sample",
    "samples",
    "case",
    "cases",
    "mnemonic",
    "private",
}
_SENSITIVE = re.compile(
    r"(?:sk-[A-Za-z0-9_-]{8,}|-----BEGIN|Bearer\s|0x[0-9a-fA-F]{64}|"
    r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b|\b[15][1-9A-HJ-NP-Za-km-z]{46,48}\b|"
    r"(?:https?|ssh)://|[A-Za-z]:[\\/]|/home/|/Users/|"
    r"(?<![A-Za-z0-9])[A-Za-z0-9]{48,}(?![A-Za-z0-9])|(?:AKIA|ASIA)[A-Z0-9]{16})",
    re.IGNORECASE,
)
_CODE_FIELDS = {"backend", "transport", "final_state", "findings", "outcome", "result"}
_REFERENCE_FIELDS = {"source", "reference", "references", "finding_register"}


def public_reference(value):
    """Relative public source reference, never followed by this module."""
    if type(value) is not str or len(value) > 512 or _SENSITIVE.search(value):
        return False
    path, _, fragment = value.partition("#")
    return (
        re.fullmatch(
            r"(?:\.agent/decisions/[A-Za-z0-9_.-]+\.md|docs/development/LAUNCHPAD_[A-Za-z0-9_.-]+\.md|"
            r"docs/development/evidence/(?:launchpad-acceptance|fresh-miner)-\d{4}-\d{2}-\d{2}/[A-Za-z0-9_./-]+\.(?:md|json))",
            path,
        )
        is not None
        and "\\" not in path
        and not any(part in ("", ".", "..") for part in path.split("/"))
        and re.fullmatch(r"[A-Za-z0-9_./-]+", path) is not None
        and re.fullmatch(r"[A-Za-z0-9_-]*", fragment) is not None
    )


def _evidence(value, key="evidence", depth=0, count=None):
    count = [0] if count is None else count
    count[0] += 1
    if depth > 8 or count[0] > 512:
        raise ValueError("EVIDENCE_TOO_LARGE")
    if type(value) is dict:
        for name, child in value.items():
            if type(name) is not str or not _FIELD.fullmatch(name):
                raise ValueError("INVALID_EVIDENCE_FIELD")
            digest_field = name.endswith(("_digest", "_digests", "_hash", "_hashes"))
            if set(name.split("_")) & _FORBIDDEN and not (
                name in ("profile_digest", "profile_hash")
                and type(child) is str
                and _DIGEST.fullmatch(child)
            ):
                raise ValueError("FORBIDDEN_EVIDENCE_FIELD")
            if digest_field and type(child) not in (str, list):
                raise ValueError("INVALID_EVIDENCE_DIGEST")
            _evidence(child, name, depth + 1, count)
        return
    if type(value) is list:
        if not value:
            raise ValueError("EMPTY_EVIDENCE_LIST")
        for child in value:
            _evidence(child, key, depth + 1, count)
        return
    if key.endswith(("_digest", "_digests", "_hash", "_hashes")):
        if type(value) is not str or not _DIGEST.fullmatch(value):
            raise ValueError("INVALID_EVIDENCE_DIGEST")
        return
    if key in _REFERENCE_FIELDS or key.endswith("_reference"):
        if not public_reference(value):
            raise ValueError("INVALID_PUBLIC_REFERENCE")
        return
    if type(value) is bool or (type(value) is int and 0 <= value <= 2**63 - 1):
        return
    if type(value) is str and not _SENSITIVE.search(value):
        if (
            key in _CODE_FIELDS or key.endswith(("_code", "_codes"))
        ) and _CODE.fullmatch(value):
            return
        if key == "campaign_id" and re.fullmatch(r"[0-9a-f]{32}", value):
            return
        if key == "submission_id" and re.fullmatch(r"bsub-[0-9a-f]{16,64}", value):
            return
    raise ValueError("UNSUPPORTED_PUBLIC_EVIDENCE_VALUE")


def validate_cell(document):
    """Validate a new public record; return a detached canonical JSON object.

    T06's pinned structural validator supplies shared schema/date/revision rules.
    This wrapper adds prospective disclosure/known-cell/PASS evidence constraints.
    """
    try:
        _cell(document, "prospective")
        if set(document) - (_REQUIRED | {"attempt"}):
            raise ValueError("UNKNOWN_CELL_FIELD")
        definition = BY_CELL.get(document["cell"])
        if definition is None:
            raise ValueError("UNKNOWN_CELL")
        refusal = document["refusal_code"]
        if refusal is not None and (
            type(refusal) is not str
            or not _CODE.fullmatch(refusal)
            or _SENSITIVE.search(refusal)
        ):
            raise ValueError("INVALID_REFUSAL_CODE")
        for field in ("actor", "machine_kind"):
            if (
                len(document[field]) > 160
                or _SENSITIVE.search(document[field])
                or "\n" in document[field]
            ):
                raise ValueError("INVALID_PUBLIC_METADATA")
        _evidence(document["evidence"])
        if document["result"] == "PASS":
            if definition.blocked_reason:
                raise ValueError("CELL_BLOCKED_BY_OWNER")
            if not document["within_cap"]:
                raise ValueError("PASS_OUTSIDE_CAP")
            if any(
                name not in document["evidence"]
                for name in definition.required_evidence_fields
            ):
                raise ValueError("MISSING_PASS_EVIDENCE")
        return json.loads(json.dumps(document, allow_nan=False))
    except (KeyError, TypeError, RecursionError) as failure:
        raise ValueError("MALFORMED_ACCEPTANCE_CELL") from failure


def decode_cell(raw):
    if type(raw) not in (str, bytes) or len(raw) > 65536:
        raise ValueError("CELL_INPUT_TOO_LARGE")
    try:
        return validate_cell(
            json.loads(raw, object_pairs_hook=_unique, parse_constant=_nonfinite)
        )
    except (json.JSONDecodeError, RecursionError) as failure:
        raise ValueError("MALFORMED_ACCEPTANCE_JSON") from failure


def write_cell(document, repository=ROOT):
    """Exclusive creation in the fixed public tree; never replace a past attempt."""
    checked = validate_cell(document)
    raw = (
        json.dumps(checked, sort_keys=True, indent=2, allow_nan=False) + "\n"
    ).encode("utf-8")
    if len(raw) > 65536:
        raise ValueError("CELL_INPUT_TOO_LARGE")
    root = Path(repository)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("INVALID_REPOSITORY_ROOT")
    root = root.resolve(strict=True)
    directory = root
    for part in (
        "docs",
        "development",
        "evidence",
        "launchpad-acceptance-" + checked["date"],
        "cells",
    ):
        directory = directory / part
        if directory.is_symlink() or (directory.exists() and not directory.is_dir()):
            raise ValueError("UNSAFE_CELL_DIRECTORY")
        directory.mkdir(exist_ok=True)
    suffix = "-run" + str(checked["attempt"]) if checked.get("attempt", 0) else ""
    destination = directory / (checked["cell"] + suffix + ".json")
    # Publish complete bytes exclusively; an I/O failure cannot leave a partial
    # *.json record in the authoritative reader's inventory.
    descriptor, temporary = tempfile.mkstemp(
        prefix=".cell-", suffix=".pending", dir=directory
    )
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, destination, follow_symlinks=False)
        except FileExistsError as failure:
            raise ValueError("CELL_ATTEMPT_ALREADY_RECORDED") from failure
    finally:
        Path(temporary).unlink()
    return destination.relative_to(root).as_posix()
