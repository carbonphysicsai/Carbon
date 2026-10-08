"""A Level 4 submission: one manifest plus the documents it names.

The single format both the Launchpad (freeze, commit) and the validator read
(LAUNCHPAD-LEVELS-01; OWNER-LEVEL4-GRAPH-ONLY-01). The manifest is strict
JSON:

    {"schema": SCHEMA, "challenge": "<id>", "level": 4,
     "interface": "sha256:<the Challenge interface's digest>",
     "allowlist": {"version": "...", "digest": "sha256:..."},
     "documents": {"forward": "sha256:...", "loss": "sha256:...",
                   "init": "sha256:..." | "init_spec": "sha256:..."}}

* **One byte form.** Every document and the manifest travel as canonical
  bytes: JSON, sorted keys, no whitespace, ASCII escapes (`canonical`). A document is
  named by the SHA-256 of those bytes. Non-canonical bytes are refused, so a
  submission has exactly one representation.
* **One identity.** `digest(manifest)` names the whole submission. The
  manifest pins every document's digest, so it covers them all.
* `forward` is required; `loss` is optional; exactly one of `init` (an init
  graph) or `init_spec` (an initializer declaration) is required.

Size bounds are the caller's. Here they stay `HUMAN_INPUT`; the transport
bound belongs to the validator's intake.
"""

from __future__ import annotations

import hashlib
import json

from . import graph, initializers

SCHEMA = "carbon.development.level4-submission.v0"
LEVEL = 4
SLOTS = {"forward": "forward", "loss": "loss", "init": "init"}
_KEYS = {"schema", "challenge", "level", "interface", "allowlist", "documents"}
_DIGEST_LENGTH = len("sha256:") + 64


def canonical(value):
    """The one byte form: JSON with sorted keys, no whitespace and ASCII
    escapes; the same bytes as `graph.dumps`, so `name` equals `graph.digest`."""
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def name(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def digest(manifest):
    """The whole submission's identity: the digest of its canonical manifest."""
    return name(canonical(manifest))


def build(
    *, challenge, interface, allowlist, forward, loss=None, init=None, init_spec=None
):
    """`(manifest, {name: bytes})` for documents already lowered (miner side)."""
    if (init is None) == (init_spec is None):
        raise graph.GraphRefused("submission_init_slot")
    documents, files = {}, {}
    for slot, value in (
        ("forward", forward),
        ("loss", loss),
        ("init", init),
        ("init_spec", init_spec),
    ):
        if value is None:
            continue
        raw = canonical(value)
        documents[slot] = name(raw)
        files[documents[slot]] = raw
    manifest = {
        "schema": SCHEMA,
        "challenge": challenge,
        "level": LEVEL,
        "interface": interface,
        "allowlist": {"version": allowlist.version, "digest": allowlist.digest},
        "documents": documents,
    }
    return manifest, files


def _strict(raw, max_bytes, code):
    from carbon.challenge_validator.strict_json import MalformedStrategy, parse_strategy

    try:
        value = parse_strategy(raw, max_bytes=max_bytes)
    except MalformedStrategy as refused:
        raise graph.GraphRefused("json_" + refused.code, code) from None
    if canonical(value) != bytes(raw):
        raise graph.GraphRefused("not_canonical", code)
    return value


def _is_digest(value):
    return (
        type(value) is str
        and len(value) == _DIGEST_LENGTH
        and value.startswith("sha256:")
        and all(c in "0123456789abcdef" for c in value[7:])
    )


def verify(raw_manifest, files, *, allowlist, challenge, interface, max_bytes):
    """Parse a submission and check it is whole and pinned, or refuse.

    `files` maps each document's name to its bytes. Returns
    `(manifest, {slot: parsed document})`. This checks identity, form and
    pinning only; G4 (`validate`) judges the graphs."""
    manifest = _strict(raw_manifest, max_bytes, "manifest")
    if set(manifest) != _KEYS or manifest["schema"] != SCHEMA:
        raise graph.GraphRefused("submission_malformed")
    if manifest["level"] != LEVEL:
        raise graph.GraphRefused("submission_level")
    if manifest["challenge"] != challenge:
        raise graph.GraphRefused("submission_challenge")
    if manifest["interface"] != interface:
        raise graph.GraphRefused("submission_interface")
    if manifest["allowlist"] != {
        "version": allowlist.version,
        "digest": allowlist.digest,
    }:
        raise graph.GraphRefused("submission_allowlist")
    documents = manifest["documents"]
    if type(documents) is not dict or not set(documents) <= {*SLOTS, "init_spec"}:
        raise graph.GraphRefused("submission_malformed")
    if "forward" not in documents or ("init" in documents) == (
        "init_spec" in documents
    ):
        raise graph.GraphRefused("submission_init_slot")
    if set(files) != set(documents.values()) or len(set(documents.values())) != len(
        documents
    ):
        raise graph.GraphRefused("submission_documents")
    parsed = {}
    for slot, document_name in documents.items():
        if not _is_digest(document_name):
            raise graph.GraphRefused("submission_malformed", slot)
        raw = files[document_name]
        if name(raw) != document_name:
            raise graph.GraphRefused("document_digest_mismatch", slot)
        if slot == "init_spec":
            _strict(raw, max_bytes, slot)
            parsed[slot] = initializers.parse(raw, max_bytes=max_bytes)
            continue
        doc = _strict(raw, max_bytes, slot)
        graph.check_structure(doc)
        if doc["role"] != SLOTS[slot]:
            raise graph.GraphRefused("role_mismatch", slot)
        if doc["allowlist"] != allowlist.version:
            raise graph.GraphRefused("allowlist_version_mismatch", slot)
        parsed[slot] = doc
    if "init_spec" in parsed and parsed["init_spec"]["graph"] != documents["forward"]:
        raise graph.GraphRefused("init_spec_graph_mismatch")
    return manifest, parsed
