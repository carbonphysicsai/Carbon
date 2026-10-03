"""Miner-owned files; no host path, arbitrary mount, or evaluator handle.

File contents are untrusted. Only the isolated research carrier may execute them.
Notebook/capability records live in the controller ledger, outside this snapshot.

No Carbon-imposed size or count limits (owner direction: the research
environment is the miner's machine, cost, time and choice). Contents live in a
content-addressed store under the campaign root rather than in the ledger
database, so a checkpoint of any size persists between runs; the ledger keeps
only name -> digest. The only bound is the miner's own `retained_bytes` budget,
if they set one. Rows written by the earlier blob layout remain readable.
"""

from __future__ import annotations

import os
import re

from .profile import digest

_NAME = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,95}\Z")
_EMPTY = b""


class WorkspaceConflict(ValueError):
    """A write whose `expected_digest` is not the file's current digest.

    Typed so the executor can report it as the requester's to fix, never as
    an infrastructure failure. The message is the historical one.
    """


class WorkspaceFileMissing(ValueError):
    """A read of a name the workspace does not hold. A held file whose stored
    bytes no longer match their digest stays a plain ValueError: that is not
    the requester's to fix."""


def is_workspace_name(name):
    """Whether `name` is a flat workspace identifier (never a path)."""
    return (
        type(name) is str
        and _NAME.fullmatch(name) is not None
        and name
        not in {
            ".",
            "..",
        }
    )


class ResearchWorkspace:
    def __init__(self, ledger, owner):
        if type(owner) is not str or not owner or len(owner) > 128:
            raise ValueError("requester binding required")
        self.ledger, self.owner = ledger, owner
        self.objects = ledger.root / "workspace-objects"
        self.objects.mkdir(mode=0o700, exist_ok=True)
        with ledger.db() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS workspace (owner TEXT NOT NULL,name TEXT NOT NULL,body BLOB NOT NULL,digest TEXT NOT NULL,PRIMARY KEY(owner,name))"
            )

    @staticmethod
    def name(name):
        if not is_workspace_name(name):
            raise ValueError(
                "workspace names are bounded flat identifiers, never paths"
            )
        return name

    def current_digest(self, name):
        """The digest this workspace records for `name`, or None when it holds
        no such file. Reads no file bytes: what a write's `expected_digest` is
        compared with, and what tells a missing file from a held one."""
        self.name(name)
        with self.ledger.db() as db:
            row = db.execute(
                "SELECT digest FROM workspace WHERE owner=? AND name=?",
                (self.owner, name),
            ).fetchone()
        return None if row is None else row[0]

    def _object(self, fingerprint):
        return self.objects / fingerprint.removeprefix("sha256:")

    def _store(self, body, fingerprint):
        target = self._object(fingerprint)
        if target.exists():
            return
        staged = target.with_suffix(".staging")
        staged.unlink(missing_ok=True)
        handle = os.open(staged, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(handle, "wb") as out:
            out.write(body)
        os.replace(staged, target)

    def put(self, name, body, *, expected_digest=None):
        name = self.name(name)
        if type(body) is not bytes:
            raise ValueError("workspace files are bytes")
        self.ledger.check_storage(len(body) + 65536)
        fingerprint = digest(body)
        with self.ledger.db() as db:
            db.execute("BEGIN IMMEDIATE")
            old = db.execute(
                "SELECT digest FROM workspace WHERE owner=? AND name=?",
                (self.owner, name),
            ).fetchone()
            if old and old[0] == fingerprint:
                return fingerprint
            if (old[0] if old else None) != expected_digest:
                raise WorkspaceConflict("workspace compare-and-swap conflict")
            self._store(body, fingerprint)
            db.execute(
                "INSERT OR REPLACE INTO workspace VALUES(?,?,?,?)",
                (self.owner, name, _EMPTY, fingerprint),
            )
        return fingerprint

    def get(self, name):
        self.name(name)
        with self.ledger.db() as db:
            row = db.execute(
                "SELECT body,digest FROM workspace WHERE owner=? AND name=?",
                (self.owner, name),
            ).fetchone()
        if not row:
            raise WorkspaceFileMissing("workspace artifact unavailable")
        body = row[0]
        if body == _EMPTY and row[1] != digest(_EMPTY):
            path = self._object(row[1])
            body = path.read_bytes() if path.is_file() else None
        if body is None or digest(body) != row[1]:
            raise ValueError("workspace artifact unavailable")
        return body

    def _size(self, body_length, fingerprint):
        if body_length:
            return body_length
        path = self._object(fingerprint)
        return path.stat().st_size if path.is_file() else 0

    def inventory(self):
        with self.ledger.db() as db:
            rows = db.execute(
                "SELECT name,LENGTH(body),digest FROM workspace WHERE owner=? ORDER BY name",
                (self.owner,),
            ).fetchall()
        return [{"name": n, "bytes": self._size(s, d), "digest": d} for n, s, d in rows]

    def snapshot(self, names):
        if type(names) is not list or len(names) != len(set(names)):
            raise ValueError("distinct workspace selection required")
        return {name: self.get(name) for name in names}


CAPABILITY_REASONS = {
    "missing_adapter",
    "missing_data_support",
    "resource_ceiling",
    "host_limitation",
    "contract_incompatibility",
    "prohibited_authority_or_data",
}
CAPABILITY_FIELDS = {
    "purpose",
    "operation",
    "hypothesis",
    "public_evidence",
    "reason",
    "expected_benefit",
    "estimated_cost",
    "minimal_safe_design",
    "verification",
}


#: The text bound on every capability request field, in characters.
CAPABILITY_TEXT = 4096


def capability_request_refusal(request, challenge=None):
    """What is wrong with one capability request, before anything records it.

    Returns None, or `(code, field, message)`: a closed correction code, the
    one sub-field it is about (a name Carbon registered, never one the
    requester sent) and the historical message. The first problem found is
    the one named. `challenge` is the campaign's Challenge token; its own
    registry decides whether an optional `capability` is a registry id
    (Burgers' when None, as before Challenges were threaded through).
    """
    from carbon.reconstruction.capability_registry import (
        BURGERS_CHALLENGE,
        UnknownChallenge,
        capability,
    )

    closed = "closed capability request required"
    if type(request) is not dict:
        return "capability_request_object_required", "arguments_json.request", closed
    missing = sorted(CAPABILITY_FIELDS - set(request))
    if missing:
        return (
            "capability_request_field_missing",
            "arguments_json.request." + missing[0],
            closed,
        )
    if set(request) - CAPABILITY_FIELDS - {"capability"}:
        return "capability_request_field_unexpected", "arguments_json.request", closed
    # A reason sent as a list or object is named as a reason too: checked
    # by type first, since such a value cannot even be looked up.
    if (
        type(request["reason"]) is not str
        or request["reason"] not in CAPABILITY_REASONS
    ):
        return (
            "capability_request_reason_unknown",
            "arguments_json.request.reason",
            closed,
        )
    for name in sorted(request):
        value = request[name]
        if type(value) is not str or not 1 <= len(value) <= CAPABILITY_TEXT:
            return (
                "capability_request_text_bounded",
                "arguments_json.request." + name,
                "bounded capability fields required",
            )
    if "capability" in request:
        # Optionally, the registry capability this asks for, so it counts as
        # demand: an id of this campaign's own Challenge.
        try:
            capability(
                request["capability"],
                BURGERS_CHALLENGE if challenge is None else challenge,
            )
        except (KeyError, TypeError, UnknownChallenge):
            return (
                "capability_id_unknown",
                "arguments_json.request.capability",
                "capability names a registry id (see the roadmap), or is omitted",
            )
    return None


def request_capability(ledger, *, owner, request, challenge=None):
    """Record one closed capability request; `challenge` as in
    `capability_request_refusal`."""
    refused = capability_request_refusal(request, challenge)
    if refused is not None:
        raise ValueError(refused[2])
    record = {**request, "disposition": "investigate", "authority_granted": False}
    ledger.note(owner=owner, kind="capability_request", body=record)
    return record
