"""Two-child public Julia admission in the existing campaign SQLite ledger.

HELD rows reserve allowance without dispatch. Only claim transitions one child
to the ordinary RESERVED worker lifecycle; unknown work is never replayed.
"""

from __future__ import annotations

import json
import math
from pathlib import PurePosixPath

from .profile import canonical, digest
from .research_ledger import (
    DIMENSIONS,
    NO_BUDGET,
    SERVICE_LIMITS,
    _caps,
    _final_reserve,
    _vector,
)

SCOPE = "carbon.public-julia-envelope.scope.v2"


def _identity(value):
    if type(value) is not str or not 1 <= len(value) <= 128 or not value.isascii():
        raise ValueError("bounded sequence identity required")


def _context(ledger, db, owner, scope, *, cleanup=False):
    from .research_control import CampaignControl
    from .research_ledger import NO_BUDGET, _elapsed

    row = db.execute("SELECT manifest,started FROM campaign WHERE id=1").fetchone()
    if row is None:
        raise ValueError("freeze before sequence admission")
    manifest = json.loads(row[0])
    if (
        not ledger.controlled(manifest)
        or manifest.get("owner") != owner
        or type(scope) is not dict
        or scope.get("schema") != SCOPE
        or scope not in manifest.get("runtime", {}).get("scientific_tasks", [])
    ):
        raise ValueError("explicit prospective sequence grant required")
    ledger._check_admission_mode(manifest)
    if cleanup:
        ledger.retained_owner(owner, db=db)
        return manifest, row[1], None
    authority = ledger.authority(manifest)
    CampaignControl.assert_dispatch(db, ledger.generation)
    now = ledger.clock()
    started = now if row[1] is None else row[1]
    # Absent bounds are no deadline: a product campaign has no expiry, and a
    # miner who set no elapsed budget has no wall clock.
    bounds = []
    if authority["expires_unix"] is not None:
        bounds.append(authority["expires_unix"])
    if _elapsed(manifest) is not NO_BUDGET:
        bounds.append(started + _elapsed(manifest))
    deadline = min(bounds) if bounds else None
    if (
        not math.isfinite(now)
        or now < started
        or (deadline is not None and now >= deadline)
    ):
        raise ValueError("sequence deadline exhausted")
    return manifest, started, deadline


def _load(db, parent, owner):
    row = db.execute(
        "SELECT owner,document FROM operation_sequences WHERE parent=?", (parent,)
    ).fetchone()
    if row is None or row[0] != owner:
        raise ValueError("owned sequence unavailable")
    return json.loads(row[1])


def reserve_sequence(ledger, parent, *, owner, scope, children):
    """Reserve the complete exact two-worker vector or write nothing."""
    _identity(parent)
    _identity(owner)
    if type(children) is not list or len(children) != 2:
        raise ValueError("exactly two children required")
    normalized = []
    total = {}
    for ordinal, child in enumerate(children):
        if type(child) is not dict or set(child) != {"request", "resources"}:
            raise ValueError("closed sequence child required")
        resources = _vector(child["resources"])
        if (
            set(resources)
            != {
                "numerical_milliseconds",
                "reference_trajectories",
                "reference_invocations",
                "retained_bytes",
            }
            or resources["numerical_milliseconds"] != 720000
            or resources["reference_trajectories"] != 2
            or resources["reference_invocations"] != 2
            or resources["retained_bytes"] <= 0
        ):
            raise ValueError("registered two-refinement worker reservation required")
        request = json.loads(canonical(child["request"]))
        identity = (
            "seq-child-"
            + digest(canonical([owner, parent, ordinal, scope, request]))[7:]
        )
        normalized.append({"id": identity, "request": request, "resources": resources})
        for key, value in resources.items():
            total[key] = total.get(key, 0) + value
    document = {"scope": scope, "children": normalized}
    payload = canonical(document)
    if len(payload) > 131072:
        raise ValueError("bounded sequence document required")
    with ledger.db() as db:
        db.execute("BEGIN IMMEDIATE")
        manifest, started, deadline = _context(ledger, db, owner, scope)
        old = db.execute(
            "SELECT owner,document FROM operation_sequences WHERE parent=?", (parent,)
        ).fetchone()
        if old:
            if old != (owner, payload):
                raise ValueError("sequence replay conflict")
            return {"dispatch": False, "children": [c["id"] for c in normalized]}
        if (
            deadline is not None
            and ledger.clock() + total["numerical_milliseconds"] / 1000 > deadline
        ):
            raise ValueError("complete sequence cannot fit remaining time")
        used = ledger._usage(db)
        caps, reserve = _caps(manifest), _final_reserve(manifest)
        for key in DIMENSIONS:
            want = total.get(key, 0)
            service = SERVICE_LIMITS.get(key)
            if service is not None and used[key] + want > service:
                raise ValueError("carbon service capacity: " + key)
            cap = caps.get(key, NO_BUDGET)
            if cap is NO_BUDGET:
                continue
            headroom = reserve.get(key, 0)
            if key == "final_replicas":
                headroom = max(0, headroom - used[key])
            if used[key] + want + headroom > cap:
                # Names the aggregate, because a sequence can fit child by
                # child and still not fit as a whole.
                raise ValueError("miner budget, sequence aggregate: " + key)
        now = ledger.clock()
        db.execute("UPDATE campaign SET started=? WHERE id=1", (started,))
        db.execute(
            "INSERT INTO operations VALUES(?,?,?,?,?,?,?,?,?)",
            (
                parent,
                owner,
                "research",
                digest(payload),
                "RESERVED",
                canonical({}),
                None,
                None,
                now,
            ),
        )
        db.execute(
            "INSERT INTO operation_sequences VALUES(?,?,?)", (parent, owner, payload)
        )
        for child in normalized:
            db.execute(
                "INSERT INTO operations VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    child["id"],
                    owner,
                    "research",
                    digest(canonical(child["request"])),
                    "HELD",
                    canonical(child["resources"]),
                    None,
                    None,
                    now,
                ),
            )
    return {"dispatch": True, "children": [c["id"] for c in normalized]}


def _observed_cleanup(ledger, child, result):
    receipt = result.get("cleanup_receipt") if type(result) is dict else None
    if type(receipt) is not dict or set(receipt) != {"path", "digest"}:
        raise ValueError("observed controller cleanup receipt required")
    relative = receipt["path"]
    if (
        type(relative) is not str
        or "\\" in relative
        or PurePosixPath(relative).is_absolute()
        or ".." in PurePosixPath(relative).parts
    ):
        raise ValueError("invalid cleanup receipt path")
    path = ledger.root / relative
    if (
        not path.resolve().is_relative_to(ledger.root.resolve())
        or any(p.is_symlink() for p in [path, *path.parents])
        or path.stat().st_size > 65536
    ):
        raise ValueError("cleanup receipt path unavailable")
    body = path.read_bytes()
    journal = json.loads(body)
    if (
        digest(body) != receipt["digest"]
        or journal.get("schema") != "carbon.c04.reference-launch.v1"
        or journal.get("request_digest") != child["request"]["request_digest"]
        or journal.get("image_id") != child["request"]["image"]
        or journal.get("state") != "ASSOCIATED_DEVELOPMENT_ONLY"
    ):
        raise ValueError("previous worker cleanup is not confirmed")


def claim_sequence_child(ledger, parent, *, owner, ordinal):
    if type(ordinal) is not int or ordinal not in (0, 1):
        raise ValueError("sequence ordinal required")
    with ledger.db() as db:
        db.execute("BEGIN IMMEDIATE")
        document = _load(db, parent, owner)
        _manifest, _started, deadline = _context(ledger, db, owner, document["scope"])
        parent_state = db.execute(
            "SELECT state FROM operations WHERE id=?", (parent,)
        ).fetchone()[0]
        if parent_state != "RESERVED":
            raise ValueError("sequence is terminal")
        child = document["children"][ordinal]
        row = db.execute(
            "SELECT state FROM operations WHERE id=?", (child["id"],)
        ).fetchone()
        if row is None or row[0] != "HELD":
            raise ValueError("child already claimed or closed; no redispatch")
        if ordinal:
            previous = document["children"][ordinal - 1]
            prior = db.execute(
                "SELECT state,result FROM operations WHERE id=?", (previous["id"],)
            ).fetchone()
            if prior is None or prior[0] != "SUCCEEDED":
                raise ValueError("previous child is not complete")
            _observed_cleanup(ledger, previous, json.loads(prior[1]))
        active = db.execute(
            "SELECT reservation FROM operations WHERE state='RESERVED'"
        ).fetchall()
        if any(json.loads(row[0]).get("numerical_milliseconds", 0) for row in active):
            raise ValueError("one numerical worker; reconcile active operation")
        if (
            deadline is not None
            and ledger.clock() + child["resources"]["numerical_milliseconds"] / 1000
            > deadline
        ):
            raise ValueError("child cannot fit remaining time")
        db.execute("UPDATE operations SET state='RESERVED' WHERE id=?", (child["id"],))
        db.execute(
            "INSERT INTO operation_sequence_claims VALUES(?,?,?)",
            (child["id"], ledger.generation, ledger.clock()),
        )
    return child


def cancel_sequence_held(ledger, parent, *, owner):
    """Release only rows whose durable state proves no claim ever occurred."""
    with ledger.db() as db:
        db.execute("BEGIN IMMEDIATE")
        document = _load(db, parent, owner)
        _context(ledger, db, owner, document["scope"], cleanup=True)
        for child in document["children"]:
            if db.execute(
                "SELECT 1 FROM operations JOIN operation_sequence_claims ON child=id WHERE id=? AND state='HELD'",
                (child["id"],),
            ).fetchone():
                raise ValueError("claimed child cannot regain refundable HELD capacity")
            db.execute(
                "UPDATE operations SET state='CANCELLED',actual=?,result=? WHERE id=? AND owner=? AND state='HELD'",
                (
                    canonical(dict.fromkeys(child["resources"], 0)),
                    canonical({"cleanup": "NEVER_CLAIMED", "dispatch": False}),
                    child["id"],
                    owner,
                ),
            )


def sequence_status(ledger, parent, *, owner):
    with ledger.db() as db:
        document = _load(db, parent, owner)
        rows = []
        for child in document["children"]:
            row = db.execute(
                "SELECT state,reservation,actual,result FROM operations WHERE id=? AND owner=?",
                (child["id"], owner),
            ).fetchone()
            if row is None:
                raise ValueError("sequence child missing")
            rows.append(
                {
                    "id": child["id"],
                    "state": row[0],
                    "reservation": json.loads(row[1]),
                    "actual": json.loads(row[2]) if row[2] else None,
                    "result": json.loads(row[3]) if row[3] else None,
                }
            )
    return {"parent": parent, "scope": document["scope"], "children": rows}


def settle_sequence(ledger, parent, *, owner):
    with ledger.db() as db:
        db.execute("BEGIN IMMEDIATE")
        document = _load(db, parent, owner)
        _context(ledger, db, owner, document["scope"], cleanup=True)
        states = []
        for child in document["children"]:
            state, result = db.execute(
                "SELECT state,result FROM operations WHERE id=?", (child["id"],)
            ).fetchone()
            if state not in {"SUCCEEDED", "CANCELLED", "FAILED_INFRA"}:
                raise ValueError("unresolved sequence; reservation retained")
            if state == "SUCCEEDED":
                _observed_cleanup(ledger, child, json.loads(result))
            elif (
                json.loads(result).get("cleanup") != "NEVER_CLAIMED"
                or db.execute(
                    "SELECT 1 FROM operation_sequence_claims WHERE child=?",
                    (child["id"],),
                ).fetchone()
            ):
                raise ValueError("dispatched failure requires separate reconciliation")
            states.append(state)
        state = "SUCCEEDED" if states == ["SUCCEEDED", "SUCCEEDED"] else "CANCELLED"
        body = canonical(
            {
                "schema": "carbon.public-julia-sequence.result.v1",
                "children": [c["id"] for c in document["children"]],
            }
        )
        db.execute(
            "UPDATE operations SET state=?,actual=?,result=? WHERE id=? AND state='RESERVED'",
            (state, canonical({}), body, parent),
        )
