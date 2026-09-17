"""Durable finite-campaign admission; unknown consumption keeps its reservation.

Trusted controller only. Never mounted into a miner worker. Integer units avoid
floating point underspend; timestamps are operational, not scientific evidence.
"""

from __future__ import annotations

import json
import math
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

from .profile import canonical, digest

VERSION = "carbon.autoresearch.campaign.v1"
CEILINGS = {
    "epochs": 2,
    "research_trials": 16,
    "final_replicas": 12,
    "provider_attempts": 96,
    "provider_nanodollars": 1000000000,
    "numerical_milliseconds": 21600000,
    "reference_trajectories": 512,
    "reference_invocations": 2048,
    "retained_bytes": 10 * 1024**3,
}
ELAPSED_SECONDS = 8 * 3600
# Reserve the unspent final phase before admitting exploratory work. These are
# admission reservations, not promises of sufficient runtime or quality.
FINAL_RESERVE = {
    "final_replicas": 12,
    "provider_attempts": 8,
    "provider_nanodollars": 8 * 20480000,
    "numerical_milliseconds": 12 * 600000,
    "reference_trajectories": 48,
    "reference_invocations": 144,
    "retained_bytes": 2 * 1024**3,
}


def _vector(value):
    if type(value) is not dict or set(value) - set(CEILINGS):
        raise ValueError("unknown resource dimension")
    if any(type(v) is not int or v < 0 for v in value.values()):
        raise ValueError("nonnegative integer accounting required")
    return dict(value)


class CampaignLedger:
    def __init__(self, root: Path, *, clock=time.time):
        if not root.is_absolute() or root.is_symlink():
            raise ValueError("private absolute campaign root required")
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        root.chmod(0o700)
        self.root, self.clock = root, clock
        self.path = root / "campaign.sqlite3"
        if self.path.is_symlink():
            raise ValueError("symlink ledger rejected")
        with self.db() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS campaign (id INTEGER PRIMARY KEY CHECK(id=1), manifest BLOB NOT NULL, digest TEXT NOT NULL, started REAL);
                CREATE TABLE IF NOT EXISTS operations (id TEXT PRIMARY KEY, owner TEXT NOT NULL, phase TEXT NOT NULL, request_digest TEXT NOT NULL, state TEXT NOT NULL, reservation BLOB NOT NULL, actual BLOB, result BLOB, created REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS notes (sequence INTEGER PRIMARY KEY, owner TEXT NOT NULL, kind TEXT NOT NULL, body BLOB NOT NULL, created REAL NOT NULL);
            """)
        self.path.chmod(0o600)

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.execute("PRAGMA synchronous=FULL")
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def freeze(self, manifest):
        if type(manifest) is not dict or manifest.get("schema") != VERSION:
            raise ValueError("versioned campaign manifest required")
        if (
            manifest.get("ceilings") != CEILINGS
            or manifest.get("elapsed_seconds") != ELAPSED_SECONDS
        ):
            raise ValueError("owner envelope differs")
        for key in (
            "campaign_id",
            "implementation",
            "objective",
            "sampling",
            "control",
            "selection",
            "replica_policy",
            "provider",
            "owner",
        ):
            if not manifest.get(key):
                raise ValueError("incomplete prospective campaign manifest")
        payload = canonical(manifest)
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            old = db.execute("SELECT manifest FROM campaign WHERE id=1").fetchone()
            if old:
                if old[0] != payload:
                    raise ValueError("campaign freeze conflict")
            else:
                db.execute(
                    "INSERT INTO campaign VALUES(1,?,?,NULL)",
                    (payload, digest(payload)),
                )
        return digest(payload)

    def _usage(self, db):
        used = dict.fromkeys(CEILINGS, 0)
        for reserved, actual in db.execute("SELECT reservation,actual FROM operations"):
            # A reconciled final actual vector replaces, never adds to, reservation.
            for key, value in json.loads(
                actual if actual is not None else reserved
            ).items():
                used[key] += value
        return used

    def reserve(self, identity, *, owner, phase, request, resources):
        if phase not in {"research", "final", "selection", "report"}:
            raise ValueError("invalid campaign phase")
        for value in (identity, owner):
            if (
                type(value) is not str
                or not 1 <= len(value) <= 128
                or not value.isascii()
            ):
                raise ValueError("bounded identity required")
        resources = _vector(resources)
        fingerprint = digest(canonical(request))
        now = self.clock()
        if not math.isfinite(now):
            raise ValueError("invalid clock")
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            frozen = db.execute(
                "SELECT manifest,started FROM campaign WHERE id=1"
            ).fetchone()
            if frozen is None:
                raise ValueError("freeze before dispatch")
            old = db.execute(
                "SELECT owner,phase,request_digest,state,reservation,result FROM operations WHERE id=?",
                (identity,),
            ).fetchone()
            if old:
                if old[:3] != (owner, phase, fingerprint) or old[4] != canonical(
                    resources
                ):
                    raise ValueError("operation replay conflict")
                return {
                    "dispatch": False,
                    "state": old[3],
                    "result": json.loads(old[5]) if old[5] else None,
                }
            started = frozen[1]
            if started is None:
                started = now
            if now < started or now >= started + ELAPSED_SECONDS:
                raise ValueError("campaign elapsed-time exhausted or clock regressed")
            if resources.get("numerical_milliseconds", 0) > 600000:
                raise ValueError("per-worker ceiling")
            if resources.get("numerical_milliseconds", 0) > 0:
                if (
                    now + resources["numerical_milliseconds"] / 1000
                    > started + ELAPSED_SECONDS
                ):
                    raise ValueError("worker cannot fit remaining elapsed time")
                active = db.execute(
                    "SELECT reservation FROM operations WHERE state='RESERVED'"
                ).fetchall()
                if any(
                    json.loads(row[0]).get("numerical_milliseconds", 0) > 0
                    for row in active
                ):
                    raise ValueError("one numerical worker; reconcile active operation")
            used = self._usage(db)
            for key, cap in CEILINGS.items():
                headroom = FINAL_RESERVE.get(key, 0) if phase == "research" else 0
                if used[key] + resources.get(key, 0) + headroom > cap:
                    raise ValueError("campaign resource admission: " + key)
            db.execute("UPDATE campaign SET started=? WHERE id=1", (started,))
            db.execute(
                "INSERT INTO operations VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    identity,
                    owner,
                    phase,
                    fingerprint,
                    "RESERVED",
                    canonical(resources),
                    None,
                    None,
                    now,
                ),
            )
        return {"dispatch": True, "state": "RESERVED", "result": None}

    def finish(self, identity, *, owner, state, actual, result):
        if state not in {"SUCCEEDED", "FAILED_INFRA", "CANCELLED"}:
            raise ValueError("terminal state required")
        actual = _vector(actual)
        body = canonical(result)
        if len(body) > 1024**2:
            raise ValueError("bounded result required")
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            old = db.execute(
                "SELECT owner,state,reservation,actual,result FROM operations WHERE id=?",
                (identity,),
            ).fetchone()
            if old is None or old[0] != owner:
                raise ValueError("operation unavailable")
            if old[1] != "RESERVED":
                if (old[1], old[3], old[4]) == (state, canonical(actual), body):
                    return
                raise ValueError("terminal conflict")
            reserved = json.loads(old[2])
            if set(actual) != set(reserved):
                raise ValueError(
                    "reconcile every reserved dimension; unknown is not zero"
                )
            if any(actual[k] > reserved[k] for k in actual):
                raise ValueError(
                    "reservation exceeded; retain unresolved charge and stop"
                )
            # Attempts/trials count even if execution failed or was cancelled.
            for key in (
                "provider_attempts",
                "research_trials",
                "final_replicas",
                "epochs",
            ):
                if actual.get(key, 0) != reserved.get(key, 0):
                    raise ValueError("attempt counters cannot be refunded")
            db.execute(
                "UPDATE operations SET state=?,actual=?,result=? WHERE id=?",
                (state, canonical(actual), body, identity),
            )

    def note(self, *, owner, kind, body):
        if kind not in {
            "hypothesis",
            "decision",
            "capability_request",
            "operational_error",
            "security_incident",
            "notebook",
        }:
            raise ValueError("unknown note kind")
        payload = canonical(body)
        if (
            type(owner) is not str
            or len(owner) > 128
            or not owner
            or len(payload) > 65536
        ):
            raise ValueError("bounded note required")
        with self.db() as db:
            db.execute(
                "INSERT INTO notes(owner,kind,body,created) VALUES(?,?,?,?)",
                (owner, kind, payload, self.clock()),
            )

    def status(self, *, owner):
        with self.db() as db:
            campaign = db.execute(
                "SELECT digest,started FROM campaign WHERE id=1"
            ).fetchone()
            operations = [
                {
                    "id": row[0],
                    "phase": row[1],
                    "state": row[2],
                    "reservation": json.loads(row[3]),
                    "actual": json.loads(row[4]) if row[4] else None,
                    "result": json.loads(row[5]) if row[5] else None,
                }
                for row in db.execute(
                    "SELECT id,phase,state,reservation,actual,result FROM operations WHERE owner=? ORDER BY created,id",
                    (owner,),
                )
            ]
            notes = [
                {"sequence": row[0], "kind": row[1], "body": json.loads(row[2])}
                for row in db.execute(
                    "SELECT sequence,kind,body FROM notes WHERE owner=? ORDER BY sequence",
                    (owner,),
                )
            ]
            return {
                "campaign_digest": campaign[0] if campaign else None,
                "started_unix": campaign[1] if campaign else None,
                "ceilings": dict(CEILINGS),
                "used": self._usage(db),
                "operations": operations,
                "notes": notes,
            }
