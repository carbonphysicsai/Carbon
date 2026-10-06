"""Durable cooperative campaign control in the existing resource ledger.

Pause is between bounded operations, not training-checkpoint resume. A stop or
lost generation never authorizes replay, refunds unknown charges or proves
worker cleanup. The supervisor must hold the campaign's OS lock.
"""

from __future__ import annotations

import json
import math
import time


class DispatchStopped(Exception):
    """A durable control request prevents further dispatch."""


class CampaignDeadlineReached(DispatchStopped):
    """The campaign's own time ended dispatch: its elapsed budget, or a
    development grant's expiry (RESEARCH-BUDGET-REFUSAL-TYPING-01).

    Still a DispatchStopped with the historical text, so every caller reads
    it as it did. `refusal` is the ledger's typed record of the same limit
    (`research_ledger.LedgerRefusal`, dimension `elapsed_seconds`)."""

    def __init__(self, message, refusal):
        super().__init__(message)
        self.refusal = refusal


class DispatchPaused(Exception):
    """Pause won the admission transaction; wait without losing the operation."""


#: Where `settled` leaves a dispatch: nothing of it runs any more. READY is a
#: campaign waiting for its miner; the rest are terminal or need the miner.
SETTLED_STATES = frozenset(
    {
        "READY",
        "PAUSED",
        "STOPPED",
        "COMPLETED",
        "INTERRUPTED",
        "RECONCILIATION_REQUIRED",
    }
)


def read_settlement(ledger):
    """The controller's state for the owner report, read without changing
    the ledger: the observed and desired state, whether nothing runs
    (`settled`), and when the current dispatch settled (`settled_unix`) -
    None while it runs, or when it settled before settlement times were
    recorded. None for a ledger no controller ever ran."""
    with ledger.db() as db:
        tables = {
            row[0]
            for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('launchpad_control','launchpad_settlement')"
            )
        }
        if "launchpad_control" not in tables:
            return None
        generation, desired, state = db.execute(
            "SELECT generation,desired,observed FROM launchpad_control WHERE id=1"
        ).fetchone()
        recorded = (
            db.execute(
                "SELECT generation,state,settled_unix FROM launchpad_settlement WHERE id=1"
            ).fetchone()
            if "launchpad_settlement" in tables
            else None
        )
    settled = state in SETTLED_STATES
    return {
        "state": state,
        "desired": desired,
        "generation": generation,
        "settled": settled,
        "settled_unix": (
            recorded[2]
            if settled
            and recorded is not None
            and (recorded[0], recorded[1]) == (generation, state)
            else None
        ),
    }


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
            # When the last dispatch settled, and to what (OPERATOR-USABILITY-01
            # D1). Added 2026-10-05: a ledger settled before then has no row.
            db.execute(
                "CREATE TABLE IF NOT EXISTS launchpad_settlement (id INTEGER PRIMARY KEY CHECK(id=1), generation INTEGER NOT NULL, state TEXT NOT NULL, settled_unix REAL NOT NULL)"
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
                    from .research_ledger import (
                        ELAPSED_DIMENSION,
                        MINER_CEILING_REACHED,
                        NO_BUDGET,
                        LedgerRefusal,
                        _elapsed,
                        manifest_basis,
                    )

                    manifest = json.loads(frozen[0])
                    authority = self.ledger.authority(manifest)
                    # Either bound may be absent: a product campaign has no
                    # expiry, and a miner who set no elapsed budget has no
                    # wall clock. Absent is no deadline, never a default one.
                    bounds = []
                    if authority["expires_unix"] is not None:
                        bounds.append(authority["expires_unix"])
                    elapsed = _elapsed(manifest)
                    if frozen[1] is not None and elapsed is not NO_BUDGET:
                        bounds.append(frozen[1] + elapsed)
                    now = self.ledger.clock()
                    if bounds and now >= min(bounds):
                        message = "original campaign deadline reached"
                        started = now if frozen[1] is None else frozen[1]
                        raise CampaignDeadlineReached(
                            message,
                            LedgerRefusal(
                                message,
                                code=MINER_CEILING_REACHED,
                                dimension=ELAPSED_DIMENSION,
                                basis=manifest_basis(manifest),
                                used=max(0, math.floor(now - started)),
                                requested=0,
                                ceiling=None if elapsed is NO_BUDGET else elapsed,
                            ),
                        )
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

    def settled(
        self, generation, *, completed=False, cleanup_verified=False, ready=False
    ):
        """Record how a dispatch ended. `ready` is a campaign prepared and
        waiting for its miner - launched with no agent, or between a miner's
        own operations - which is neither interrupted nor complete."""
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
            elif ready:
                state = "READY"
            elif desired == "PAUSE":
                state = "PAUSED"
            else:
                state = "INTERRUPTED"
            db.execute("UPDATE launchpad_control SET observed=? WHERE id=1", (state,))
            db.execute(
                "INSERT OR REPLACE INTO launchpad_settlement VALUES(1,?,?,?)",
                (generation, state, self.ledger.clock()),
            )
        self._refresh_report()
        return state

    def _refresh_report(self):
        """Rewrite the owner report so it says how the dispatch settled.

        The run writes its report as it closes, before the dispatch settles,
        so until 2026-10-05 a READY or STOPPED campaign's report still read
        as running (OPERATOR-USABILITY-01 D1). The report is a derived view:
        a campaign not yet frozen has none, and one that cannot be written
        now (its storage bound, say) leaves the settlement in the ledger,
        where the next report reads it."""
        try:
            with self.ledger.db() as db:
                frozen = db.execute(
                    "SELECT manifest FROM campaign WHERE id=1"
                ).fetchone()
            if frozen is None:
                return
            owner = json.loads(frozen[0])["owner"]
            from .research_report import report

            report(self.ledger, owner=owner)
        except Exception:  # noqa: BLE001 - the settlement stands without its view
            return
