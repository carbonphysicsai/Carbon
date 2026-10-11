"""The Level 4 staging contract: how a submission travels (development only).

One submission is one manifest plus the documents it names (`submission`).
Its identity is the submission digest, `sha256:` over the canonical manifest
bytes, and that string is what a strategy's Level 4 graph field carries.
Every byte travels exactly as the miner's tooling wrote it: nothing here
re-serializes, and every name is checked against the bytes it names.

Three forms, one content:

* **Directory**, what `python -m carbon.level4.tooling lower` writes on the
  miner's machine: `manifest.json` and one `<hex>.json` per document, where
  `<hex>` is the document digest without its `sha256:` prefix. Nothing else.
* **Envelope**, for JSON transports (the Launchpad's Level 4 slot, the
  validator's intake): `{"schema", "submission", "manifest", "documents"}`,
  bytes as strict base64, documents keyed by their full `sha256:` names.
* **Workspace**, the flat names a rebuild worker is staged with:
  `level4-manifest.json` and `level4-doc-<hex>.json`, beside the record
  (`level4-graph.json`).

This module checks structure and digests only. Sizes are G0's bounds
(`intake.BOUNDS`, HUMAN_INPUT until an owner sets them; the envelope's own
size is the transport's bound); whether the documents are the manifest's,
whole and admissible is G0, G3 and G4's (`intake`, `submission.verify`,
`validate`). A refusal is `graph.GraphRefused` with a typed code.
"""

from __future__ import annotations

import base64
import binascii
import re
from pathlib import Path

from . import graph, submission

SCHEMA = "carbon.level4.staging-bundle.v1"
MANIFEST = "manifest.json"
WORKSPACE_MANIFEST = "level4-manifest.json"
WORKSPACE_PREFIX = "level4-doc-"
_HEX = re.compile(r"[0-9a-f]{64}")
_KEYS = {"schema", "submission", "manifest", "documents"}


class StagingCorrupt(RuntimeError):
    """A worker's staged submission does not match the record it was staged
    for. The bytes passed G0 before staging, so this is Carbon's own
    infrastructure (`FAILED_INFRA`), never the candidate's."""

    kind = "FAILED_INFRA"


def _refuse(code, where=""):
    raise graph.GraphRefused(code, where)


def _hex(name):
    if not (isinstance(name, str) and name.startswith("sha256:")):
        _refuse("staging_name", str(name)[:80])
    value = name[len("sha256:") :]
    if not _HEX.fullmatch(value):
        _refuse("staging_name", name[:80])
    return value


def check(raw_manifest, files):
    """The submission digest of `(raw_manifest, {sha256 name: bytes})`, after
    checking every document's name is the digest of its bytes."""
    if type(raw_manifest) is not bytes or type(files) is not dict:
        _refuse("staging_malformed")
    for name, raw in files.items():
        _hex(name)
        if type(raw) is not bytes:
            _refuse("staging_malformed", name)
        if submission.name(raw) != name:
            _refuse("document_digest_mismatch", name)
    return submission.name(raw_manifest)


# -- directory ----------------------------------------------------------------------


def read_directory(path):
    """`(submission digest, raw manifest, files)` from a lowered directory."""
    root = Path(path)
    raw_manifest, files = None, {}
    for entry in sorted(root.iterdir()):
        if not entry.is_file() or entry.is_symlink():
            _refuse("staging_unexpected_entry", entry.name)
        if entry.name == MANIFEST:
            raw_manifest = entry.read_bytes()
            continue
        stem, dot, suffix = entry.name.partition(".")
        if dot != "." or suffix != "json" or not _HEX.fullmatch(stem):
            _refuse("staging_unexpected_entry", entry.name)
        files["sha256:" + stem] = entry.read_bytes()
    if raw_manifest is None:
        _refuse("staging_manifest_missing")
    return check(raw_manifest, files), raw_manifest, files


def write_directory(path, raw_manifest, files):
    """The directory form; the same layout the lowering CLI writes."""
    check(raw_manifest, files)
    root = Path(path)
    root.mkdir(parents=True, exist_ok=True)
    (root / MANIFEST).write_bytes(raw_manifest)
    for name, raw in files.items():
        (root / (_hex(name) + ".json")).write_bytes(raw)


# -- envelope -----------------------------------------------------------------------


def _b64(raw):
    return base64.b64encode(raw).decode("ascii")


def _unb64(text, where):
    if not isinstance(text, str):
        _refuse("staging_malformed", where)
    try:
        raw = base64.b64decode(text.encode("ascii"), validate=True)
    except (binascii.Error, UnicodeEncodeError):
        _refuse("staging_base64", where)
    if _b64(raw) != text:  # one encoding per byte string
        _refuse("staging_base64", where)
    return raw


def envelope(raw_manifest, files):
    """The JSON-safe envelope of one submission."""
    digest = check(raw_manifest, files)
    return {
        "schema": SCHEMA,
        "submission": digest,
        "manifest": _b64(raw_manifest),
        "documents": {name: _b64(raw) for name, raw in sorted(files.items())},
    }


def from_envelope(value):
    """`(submission digest, raw manifest, files)` from an envelope, or
    `GraphRefused`. The declared submission digest must be the manifest's."""
    if not isinstance(value, dict) or set(value) != _KEYS:
        _refuse("staging_malformed")
    if value["schema"] != SCHEMA:
        _refuse("staging_schema")
    _hex(value["submission"])
    if not isinstance(value["documents"], dict):
        _refuse("staging_malformed", "documents")
    raw_manifest = _unb64(value["manifest"], "manifest")
    files = {name: _unb64(text, name) for name, text in value["documents"].items()}
    digest = check(raw_manifest, files)
    if digest != value["submission"]:
        _refuse("staging_submission_mismatch")
    return digest, raw_manifest, files


# -- workspace ----------------------------------------------------------------------


def workspace(raw_manifest, files):
    """The flat file names a rebuild worker is staged with."""
    check(raw_manifest, files)
    staged = {WORKSPACE_MANIFEST: raw_manifest}
    for name, raw in files.items():
        staged[WORKSPACE_PREFIX + _hex(name) + ".json"] = raw
    return staged


def from_workspace(staged, submission_digest):
    """`(raw manifest, files)` back from a worker's staged files, checked
    against the submission digest its record names. Anything missing or
    mismatched is `StagingCorrupt`: Carbon's, never the candidate's."""
    if WORKSPACE_MANIFEST not in staged:
        raise StagingCorrupt("staged manifest missing")
    files = {}
    for name, raw in staged.items():
        if name.startswith(WORKSPACE_PREFIX) and name.endswith(".json"):
            files["sha256:" + name[len(WORKSPACE_PREFIX) : -len(".json")]] = raw
    raw_manifest = staged[WORKSPACE_MANIFEST]
    try:
        digest = check(raw_manifest, files)
    except graph.GraphRefused as refused:
        raise StagingCorrupt(refused.code) from None
    if digest != submission_digest:
        raise StagingCorrupt("staged submission is not the record's")
    return raw_manifest, files
