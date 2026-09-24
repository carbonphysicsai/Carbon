"""Which capabilities miners want, and the public roadmap that shows it.

Owner decision OWNER-CONSTRUCTION-ESCALATION-01: the miner-visible roadmap
publishes aggregated demand counts per registry capability id. Demand is a
signal only - it never affects scoring or qualification, and a listing is not
a delivery promise.

What is recorded, and what is not:

- Only registry ids for research-only capabilities: the things Carbon could
  build next. An id that is not one cannot be recorded at all.
- Each miner counts once per capability, however often they ask, so demand
  measures how many miners want something rather than how loudly one does.
- Miners are stored as digests; distinctness is all a count needs.
- Text a miner supplied that Carbon does not recognize is never stored. Only
  the number of miners who sent any is kept, for the public "unrecognized"
  count.

Counts are those of the host that ran the checks. On Carbon's hosted door that
is Carbon; a miner running locally keeps their demand on their own machine.
"""

from __future__ import annotations

import hashlib
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from carbon.reconstruction.capability_registry import REGISTRY, Status

ROADMAP_SCHEMA = "carbon.construction-roadmap.v1"
_WANTED = {c.capability_id for c in REGISTRY if c.status is Status.RESEARCH_ONLY}


def _principal(owner):
    if type(owner) is not str or not owner:
        raise ValueError("a principal is required")
    return hashlib.sha256(owner.encode()).hexdigest()


class DemandStore:
    """Distinct-miner demand per research-only capability, on this host."""

    def __init__(self, path):
        path = Path(path)
        if not path.is_absolute() or not path.parent.is_dir():
            raise ValueError("an absolute path in an existing directory")
        self.path = path
        new = not path.exists()
        with self._db() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS demand(capability TEXT NOT NULL,"
                "principal TEXT NOT NULL,PRIMARY KEY(capability,principal))"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS unrecognized(principal TEXT PRIMARY KEY)"
            )
        if new:
            path.chmod(0o600)

    @contextmanager
    def _db(self):
        """One transaction: committed on success, rolled back on error, closed."""
        connection = sqlite3.connect(self.path, isolation_level="IMMEDIATE")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def record(self, owner, capabilities, *, unrecognized=False):
        """Record one miner's demand. Returns the ids counted."""
        principal = _principal(owner)
        if type(capabilities) not in (list, tuple) or any(
            type(c) is not str for c in capabilities
        ):
            raise ValueError("capability ids are a list of strings")
        wanted = sorted({c for c in capabilities if c in _WANTED})
        with self._db() as db:
            db.executemany(
                "INSERT OR IGNORE INTO demand VALUES(?,?)",
                [(c, principal) for c in wanted],
            )
            if unrecognized:
                db.execute("INSERT OR IGNORE INTO unrecognized VALUES(?)", (principal,))
        return wanted

    def counts(self):
        with self._db() as db:
            rows = db.execute(
                "SELECT capability,COUNT(*) FROM demand GROUP BY capability"
            ).fetchall()
            (unknown,) = db.execute("SELECT COUNT(*) FROM unrecognized").fetchone()
        return {"by_capability": dict(rows), "unrecognized": unknown}


def demanded(check):
    """The research-only ids a check-design verdict names, and whether any of
    its items was unrecognized."""
    items = [check["backbone"], *check["fields"], *check["requested"]]
    ids = [
        i["capability"]
        for i in items
        if i.get("capability") in _WANTED
        and i["verdict"] in ("not_yet_rebuildable", "needs_owner_decision")
    ]
    return ids, any(i.get("reason") == "unrecognized" for i in items)


def public_roadmap(demand=None):
    """Every capability's public status, with demand where this host collects it.

    Without a demand store the counts are absent, never zero: "not collected
    here" and "nobody asked" are different facts.
    """
    counts = demand.counts() if demand is not None else None

    def wanted(c):
        return (
            None if counts is None else counts["by_capability"].get(c.capability_id, 0)
        )

    return {
        "schema": ROADMAP_SCHEMA,
        "demand": (
            "distinct miners on this host who asked, per capability"
            if counts is not None
            else "not collected on this host"
        ),
        "unrecognized": None if counts is None else counts["unrecognized"],
        "terms": (
            "Demand is a signal only: it never affects scoring or qualification, "
            "and a listing is not a delivery promise. Rebuildable means Carbon "
            "rebuilds it in DEVELOPMENT, not official qualification."
        ),
        "available": [
            {
                "id": c.capability_id,
                "dimension": c.dimension.value,
                "summary": c.summary,
            }
            for c in REGISTRY
            if c.status is Status.REBUILDABLE_DEVELOPMENT
        ],
        "roadmap": [
            {
                "id": c.capability_id,
                "dimension": c.dimension.value,
                "summary": c.summary,
                "blocked_on": c.blocker.value,
                "trigger": None if c.trigger is None else c.trigger.value,
                "demand": wanted(c),
            }
            for c in REGISTRY
            if c.status is Status.RESEARCH_ONLY
        ],
        "not_planned": [
            {"id": c.capability_id, "summary": c.summary, "trigger": c.trigger.value}
            for c in REGISTRY
            if c.status is Status.EXCLUDED
        ],
    }
