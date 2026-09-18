"""Durable cooperative campaign control in the existing resource ledger.

Pause is between bounded operations, not training-checkpoint resume. A stop or
lost generation never authorizes replay, refunds unknown charges or proves
worker cleanup. The supervisor must hold the campaign's OS lock.
"""

from __future__ import annotations

import json
import time


class DispatchStopped(Exception):
    """A durable control request prevents further dispatch."""


class DispatchPaused(Exception):
    """Pause won the admission transaction; wait without losing the operation."""


class CampaignControl:
    def __init__(self, ledger):
        self.ledger = ledger
        with ledger.db() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS launchpad_control (id INTEGER PRIMARY KEY CHECK(id=1), generation INTEGER NOT NULL, desired TEXT NOT NULL, observed TEXT NOT NULL)"
            )
            db.execute(
                "INSERT OR IGNORE INTO launchpad_control VALUES(1,0,'RUN','QUEUED')"
            )

    def status(self):
        with self.ledger.db() as db:
            row = db.execute(
                "SELECT generation,desired,observed FROM launchpad_control WHERE id=1"
            ).fetchone()
        return dict(zip(("generation", "desired", "state"), row, strict=True))

    def acquire(self):
        """Called only while holding the exclusive campaign supervisor lock."""
        with self.ledger.db() as db:
            db.execute("BEGIN IMMEDIATE")
            state = db.execute(
                "SELECT observed FROM launchpad_control WHERE id=1"
            ).fetchone()[0]
            if state in {"STOPPED", "COMPLETED"}:
                raise DispatchStopped("terminal campaign")
            db.execute(
                "UPDATE launchpad_control SET generation=generation+1, observed='RECONCILING' WHERE id=1"
            )
            return db.execute(
                "SELECT generation FROM launchpad_control WHERE id=1"
            ).fetchone()[0]

    def request(self, action):
        if action not in {"pause", "resume", "stop"}:
            raise ValueError("unsupported research control")
        with self.ledger.db() as db:
            db.execute("BEGIN IMMEDIATE")
            desired, state = db.execute(
                "SELECT desired,observed FROM launchpad_control WHERE id=1"
            ).fetchone()
            if state in {"COMPLETED", "STOPPED"}:
                return
            if desired == "STOP" and action != "stop":
                raise ValueError("stop cannot be reversed")
            target = {
                "pause": ("PAUSE", "PAUSE_REQUESTED"),
                "resume": ("RUN", "RESUME_REQUESTED"),
                "stop": ("STOP", "STOPPING"),
            }[action]
            db.execute(
                "UPDATE launchpad_control SET desired=?,observed=? WHERE id=1", target
            )

    @staticmethod
    def assert_dispatch(db, generation):
        row = db.execute(
            "SELECT generation,desired,observed FROM launchpad_control WHERE id=1"
        ).fetchone()
        if row is not None and row[0] == generation and row[1] == "PAUSE":
            raise DispatchPaused("pause won admission race")
        if (
            row is None
            or row[0] != generation
            or row[1] != "RUN"
            or row[2] in {"COMPLETED", "STOPPED", "RECONCILIATION_REQUIRED"}
        ):
            raise DispatchStopped("dispatch fenced by campaign control")

    def checkpoint(self, generation):
        while True:
            with self.ledger.db() as db:
                db.execute("BEGIN IMMEDIATE")
                frozen = db.execute(
                    "SELECT manifest,started FROM campaign WHERE id=1"
                ).fetchone()
                if frozen is not None:
                    manifest = json.loads(frozen[0])
                    grant = self.ledger._grant(manifest)
                    deadline = grant["expires_unix"]
                    if frozen[1] is not None:
                        deadline = min(
                            deadline, frozen[1] + manifest["elapsed_seconds"]
                        )
                    if self.ledger.clock() >= deadline:
                        raise DispatchStopped("original campaign deadline reached")
                current, desired, state = db.execute(
                    "SELECT generation,desired,observed FROM launchpad_control WHERE id=1"
                ).fetchone()
                if (
                    current != generation
                    or desired == "STOP"
                    or state in {"COMPLETED", "STOPPED", "RECONCILIATION_REQUIRED"}
                ):
                    raise DispatchStopped("dispatch fenced by campaign control")
                if desired == "RUN":
                    db.execute(
                        "UPDATE launchpad_control SET observed='RUNNING' WHERE id=1"
                    )
                    return
                active = db.execute(
                    "SELECT 1 FROM operations WHERE state='RESERVED' AND id NOT IN (SELECT parent FROM operation_sequences) LIMIT 1"
                ).fetchone()
                db.execute(
                    "UPDATE launchpad_control SET observed=? WHERE id=1",
                    ("PAUSE_REQUESTED" if active else "PAUSED",),
                )
            time.sleep(0.1)

    def settled(self, generation, *, completed=False, cleanup_verified=False):
        with self.ledger.db() as db:
            db.execute("BEGIN IMMEDIATE")
            current, desired = db.execute(
                "SELECT generation,desired FROM launchpad_control WHERE id=1"
            ).fetchone()
            if current != generation:
                raise DispatchStopped("stale completion ignored")
            active = db.execute(
                "SELECT 1 FROM operations WHERE state IN ('RESERVED','HELD') LIMIT 1"
            ).fetchone()
            if active or not cleanup_verified:
                state = "RECONCILIATION_REQUIRED"
            elif desired == "STOP":
                state = "STOPPED"
            elif completed:
                state = "COMPLETED"
            elif desired == "PAUSE":
                state = "PAUSED"
            else:
                state = "INTERRUPTED"
            db.execute("UPDATE launchpad_control SET observed=? WHERE id=1", (state,))
            return state
