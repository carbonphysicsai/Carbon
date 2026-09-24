"""Miner-owned bounded files; no host path, arbitrary mount, or evaluator handle.

File contents are untrusted. Only the isolated research carrier may execute them.
Notebook/capability records live in the controller ledger, outside this snapshot.
"""

from __future__ import annotations

import re

from .profile import digest

MAX_FILE_BYTES = 8 * 1024**2
MAX_WORKSPACE_BYTES = 128 * 1024**2
MAX_FILES = 256
_NAME = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,95}\Z")


class ResearchWorkspace:
    def __init__(self, ledger, owner):
        if type(owner) is not str or not owner or len(owner) > 128:
            raise ValueError("requester binding required")
        self.ledger, self.owner = ledger, owner
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

    def put(self, name, body, *, expected_digest=None):
        name = self.name(name)
        if type(body) is not bytes or len(body) > MAX_FILE_BYTES:
            raise ValueError("workspace file cap")
        self.ledger.check_storage(2 * len(body) + 65536)
        fingerprint = digest(body)
        with self.ledger.db() as db:
            db.execute("BEGIN IMMEDIATE")
            old = db.execute(
                "SELECT digest,LENGTH(body) FROM workspace WHERE owner=? AND name=?",
                (self.owner, name),
            ).fetchone()
            if old and old[0] == fingerprint:
                return fingerprint
            if (old[0] if old else None) != expected_digest:
                raise ValueError("workspace compare-and-swap conflict")
            count, total = db.execute(
                "SELECT COUNT(*),COALESCE(SUM(LENGTH(body)),0) FROM workspace WHERE owner=?",
                (self.owner,),
            ).fetchone()
            if (
                count + (0 if old else 1) > MAX_FILES
                or total - (old[1] if old else 0) + len(body) > MAX_WORKSPACE_BYTES
            ):
                raise ValueError("workspace aggregate cap")
            db.execute(
                "INSERT OR REPLACE INTO workspace VALUES(?,?,?,?)",
                (self.owner, name, body, fingerprint),
            )
        return fingerprint

    def get(self, name):
        self.name(name)
        with self.ledger.db() as db:
            row = db.execute(
                "SELECT body,digest FROM workspace WHERE owner=? AND name=?",
                (self.owner, name),
            ).fetchone()
        if not row or digest(row[0]) != row[1]:
            raise ValueError("workspace artifact unavailable")
        return row[0]

    def inventory(self):
        with self.ledger.db() as db:
            return [
                {"name": n, "bytes": s, "digest": d}
                for n, s, d in db.execute(
                    "SELECT name,LENGTH(body),digest FROM workspace WHERE owner=? ORDER BY name",
                    (self.owner,),
                )
            ]

    def snapshot(self, names):
        if (
            type(names) is not list
            or len(names) > MAX_FILES
            or len(names) != len(set(names))
        ):
            raise ValueError("bounded distinct workspace selection required")
        result = {name: self.get(name) for name in names}
        if sum(map(len, result.values())) > MAX_WORKSPACE_BYTES:
            raise ValueError("workspace snapshot cap")
        return result


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
        or set(request) - {"capability"} != CAPABILITY_FIELDS
        or request["reason"] not in CAPABILITY_REASONS
    ):
        raise ValueError("closed capability request required")
    # Optionally, the registry capability this asks for, so it counts as demand.
    if "capability" in request:
        from carbon.reconstruction.capability_registry import capability

        try:
            capability(request["capability"])
        except (KeyError, TypeError):
            raise ValueError(
                "capability names a registry id (see the roadmap), or is omitted"
            ) from None
    if any(type(v) is not str or not 1 <= len(v) <= 4096 for v in request.values()):
        raise ValueError("bounded capability fields required")
    record = {**request, "disposition": "investigate", "authority_granted": False}
    ledger.note(owner=owner, kind="capability_request", body=record)
    return record
