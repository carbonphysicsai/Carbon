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

Each Challenge has its own registry (OD-8), so the roadmap, the ids a check
can count and the ids a request may name are that Challenge's. A campaign's
executor names its Challenge; omitted, it is Burgers', exactly as before
Challenges were threaded through, so Burgers' roadmap is unchanged byte for
byte. A demand store lives in one campaign's root, so it holds one
Challenge's demand.
"""

from __future__ import annotations

import hashlib
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from carbon.reconstruction.capability_registry import (
    BURGERS_CHALLENGE,
    Status,
    contract,
)

ROADMAP_SCHEMA = "carbon.construction-roadmap.v1"


def _entries(challenge):
    """One Challenge's registry entries; Burgers' when `challenge` is None."""
    return contract(BURGERS_CHALLENGE if challenge is None else challenge).capabilities


def wanted_ids(challenge=None):
    """The research-only ids of one Challenge: the only ids demand counts."""
    return frozenset(
        c.capability_id for c in _entries(challenge) if c.status is Status.RESEARCH_ONLY
    )


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

    def record(self, owner, capabilities, *, unrecognized=False, challenge=None):
        """Record one miner's demand. Returns the ids counted: only research-only
        ids of `challenge` (Burgers' when None)."""
        principal = _principal(owner)
        if type(capabilities) not in (list, tuple) or any(
            type(c) is not str for c in capabilities
        ):
            raise ValueError("capability ids are a list of strings")
        allowed = wanted_ids(challenge)
        wanted = sorted({c for c in capabilities if c in allowed})
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


def demanded(check, challenge=None):
    """The research-only ids a check-design verdict names, and whether any of
    its items was unrecognized.

    The verdict's ids are its own Challenge's, so they count only when that is
    `challenge`, the campaign's (Burgers' when None). A verdict for a design
    naming a Challenge Carbon does not recognize names no ids, and its
    Challenge is the unrecognized item."""
    if "backbone" not in check:
        return [], check.get("challenge", {}).get("reason") == "unrecognized"
    items = [check["backbone"], *check["fields"], *check["requested"]]
    unrecognized = any(i.get("reason") == "unrecognized" for i in items)
    own = BURGERS_CHALLENGE if challenge is None else challenge
    if check.get("contract", {}).get("challenge", BURGERS_CHALLENGE) != own:
        return [], unrecognized
    wanted = wanted_ids(challenge)
    ids = [
        i["capability"]
        for i in items
        if i.get("capability") in wanted
        and i["verdict"] in ("not_yet_rebuildable", "needs_owner_decision")
    ]
    return ids, unrecognized


def public_roadmap(demand=None, challenge=None):
    """Every capability's public status, with demand where this host collects it.

    `challenge` is the campaign's Challenge token; its own registry is the
    roadmap (Burgers' when None, unchanged).

    Without a demand store the counts are absent, never zero: "not collected
    here" and "nobody asked" are different facts.
    """
    entries = _entries(challenge)
    counts = demand.counts() if demand is not None else None

    def wanted(c):
        return (
            None if counts is None else counts["by_capability"].get(c.capability_id, 0)
        )

    value = {
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
            for c in entries
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
            for c in entries
            if c.status is Status.RESEARCH_ONLY
        ],
        "not_planned": [
            {"id": c.capability_id, "summary": c.summary, "trigger": c.trigger.value}
            for c in entries
            if c.status is Status.EXCLUDED
        ],
    }
    if challenge is not None and challenge != BURGERS_CHALLENGE:
        # Burgers' roadmap keeps its historical form byte for byte; another
        # Challenge's says which registry it is.
        item = contract(challenge)
        value["challenge"] = {"id": item.token, "version": item.version}
    return value
