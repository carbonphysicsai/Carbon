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
        if (
            type(name) is not str
            or _NAME.fullmatch(name) is None
            or name in {".", ".."}
        ):
            raise ValueError(
                "workspace names are bounded flat identifiers, never paths"
            )
        return name

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
                raise ValueError("workspace compare-and-swap conflict")
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
            raise ValueError("workspace artifact unavailable")
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


def request_capability(ledger, *, owner, request):
    if (
        type(request) is not dict
        or set(request) != CAPABILITY_FIELDS
        or request["reason"] not in CAPABILITY_REASONS
    ):
        raise ValueError("closed capability request required")
    if any(type(v) is not str or not 1 <= len(v) <= 4096 for v in request.values()):
        raise ValueError("bounded capability fields required")
    record = {**request, "disposition": "investigate", "authority_granted": False}
    ledger.note(owner=owner, kind="capability_request", body=record)
    return record
