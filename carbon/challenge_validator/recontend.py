"""Re-contend the challengers that were graded while the king had no evaluation on their exam (Lead 5 Nov).

On all four doors the kings held evaluations only under the previous pack, so every challenger graded since met
``incumbent_regrade_required`` in `BankPromotion.consider_private` and was never compared (381 submissions; TL 5 Nov
06:03). This command files each of those challengers, in ORIGINAL GRADING ORDER, into the crown sweep's queue
(`PoolStore.record_crown_paused`). The serving receiver's own sweep (`crown_pause_sweep`, run at every auto-grade tick)
then decides them, oldest first, each against the king of its moment, through `reconsider_paused_pack`: the receiver's
own consider path with its margin, tie, repeat and averaging rules, from the filed evaluation, with no regrade, no
exam-cap slot (uncharged) and no Ladder document. A resolution is write-once, so each is contended once; an undecided one
(a repeat or rebuild the host could not make, an unmeasured king) stays queued and is retried, holding later ones back.

Which challengers: every private evaluation on the current pack ``--exam``, of a submission other than the king, on a
key the king does not have yet, or filed BEFORE the king's REGRADE onto its key (after it, the live path contended it).
Never on the key the king was first graded on (he won there: those met the king of their moment live). A key the king lacks is filed PENDING_CONTENTION: the receiver's own `king_upkeep` regrades the king at its next
tick, and the sweep in that same tick contends them in filing order. Already filed or decided: ``already_filed``.
The retained entry its repeat grade runs from is the origin's own (a pool grade's bank entry maps to it through its
``regrade-provenance.json``), as the live path files it.

The receiver runs this itself once at start-up, before its first grade (`AutoGrader._king_upkeep`), so the stranded
challengers are queued ahead of anything graded after; the command is the operator's plan / fallback / report.

    python -m carbon.challenge_validator.recontend plan  --root RECEIVER_STATE --pool-store POOL --exam sha256:...
    python -m carbon.challenge_validator.recontend file  --root RECEIVER_STATE --pool-store POOL --exam sha256:... --apply
    python -m carbon.challenge_validator.recontend report --pool-store POOL

``plan`` changes nothing. ``file --apply`` writes the queue records and one log line per challenger to
``<root>/auto-grade/recontend/recontend.jsonl`` (custody: task ids, keys, codes; no score). ``report`` lists every filed
record and its resolution (``OUTCOME:reason``, or pending). Nothing here grades, scores or moves a crown itself.
DEVELOPMENT / TESTNET only.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

from carbon.challenge_validator.interface import is_digest

_TASK = re.compile(r"rtsk_[0-9a-f]{64}")


class RecontendRefused(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _store(path):
    from carbon.battery.pool_store import PoolStore

    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise RecontendRefused("pool_store_unavailable")
    return PoolStore(path)


def _evaluations(store):
    """``[(rowid, body)]`` of every bound private evaluation, in filing (= grading) order."""
    with store.db() as db:
        rows = db.execute(
            "SELECT rowid, body FROM operations WHERE kind='private_evaluation.v1' "
            "AND state='BOUND_DEVELOPMENT_ONLY' ORDER BY rowid"
        ).fetchall()
    out = []
    for rowid, raw in rows:
        try:
            body = json.loads(raw)
        except ValueError:
            continue
        if type(body) is dict:
            out.append((rowid, body))
    return out


def _filed(store, submission_id, key):
    """Whether a crown queue record already exists for this decision (pending or resolved)."""
    op = store._bank_operation("crown_paused.v1", submission_id, key)
    with store.db() as db:
        return (
            db.execute("SELECT 1 FROM operations WHERE op_id=?", (op,)).fetchone()
            is not None
        )


def _provenance(root):
    """``{bank entry id: origin entry id}`` from every regrade-provenance.json under the receiver's artifacts."""
    mapped = {}
    artifacts = Path(root) / "auto-grade" / "artifacts"
    if not artifacts.is_dir():
        return mapped
    for path in sorted(artifacts.glob("*.evaluation/regrade-provenance.json")):
        if path.is_symlink():
            continue
        try:
            body = json.loads(path.read_bytes())
        except (OSError, ValueError):
            continue
        if (
            type(body) is dict
            and is_digest(body.get("entry_id"))
            and is_digest(body.get("origin_entry_id"))
        ):
            mapped[body["entry_id"]] = (
                body["origin_entry_id"],
                body.get("origin_task_id"),
            )
    return mapped


def _origin_entry(root, submission_id, evidence_entry, provenance):
    """The retained entry the live path's repeat runs from for this submission, or None."""
    mapped = provenance.get(evidence_entry)
    if mapped is not None:
        origin_entry, origin_task = mapped
        return origin_entry if origin_task == submission_id else None
    path = (
        Path(root)
        / "auto-grade"
        / "entries"
        / (evidence_entry.removeprefix("sha256:") + ".json")
    )
    try:
        entry = json.loads(path.read_bytes()) if not path.is_symlink() else None
    except (OSError, ValueError):
        return None
    receipt = ((entry or {}).get("custody_receipt") or {}).get("file")
    return evidence_entry if receipt == submission_id + ".custody.json" else None


def plan(root, pool_store, exam):
    """``{"king", "file": [...], "skipped": {sid: code}}`` (read-only). ``file`` is in grading order, each
    ``{"submission_id", "evaluation_key", "entry_id", "pin"}``."""
    if not is_digest(exam):
        raise RecontendRefused("exam_digest_invalid")
    store = _store(pool_store)
    incumbent = store.incumbent()
    if incumbent is None:
        raise RecontendRefused("no_incumbent")
    king = incumbent["model_id"]
    rows = _evaluations(store)
    king_first = {}
    for rowid, body in rows:
        if body.get("submission_id") == king:
            king_first.setdefault(body.get("evaluation_key"), rowid)
    # The key the king was first graded on is the one he WON on (a task is graded on its own exam once; any later key of
    # his is a regrade). Challengers on that key met the king of their moment live, so none of them was stranded.
    won_on = next(iter(king_first), None)
    # His rebuild on a new exam (route (b)) is filed under its DERIVED row, linked to him per key: that row is his grade
    # on that key, so a challenger graded after it met him live and is not filed again on a restart (audit #4).
    linked = getattr(store, "king_rebuild_of", None)
    if linked is not None:
        for rowid, body in rows:
            sid, key = body.get("submission_id"), body.get("evaluation_key")
            if (
                type(sid) is str
                and sid.startswith("krb_")
                and (linked(king, key) or {}).get("derived_submission_id") == sid
            ):
                king_first[key] = min(king_first.get(key, rowid), rowid)
    provenance = _provenance(root)
    to_file, skipped, seen = [], {}, set()
    for rowid, body in rows:
        sid, key = body.get("submission_id"), body.get("evaluation_key")
        evidence = body.get("evidence") or {}
        if (
            sid == king
            or type(sid) is not str
            or not _TASK.fullmatch(sid)
            or evidence.get("evaluation_pack_digest") != exam
            or (sid, key) in seen
        ):
            continue
        seen.add((sid, key))
        if key == won_on or (key in king_first and rowid > king_first[key]):
            continue  # met the king of its moment live (his own exam, or graded after his regrade onto it)
        elif _filed(store, sid, key):
            skipped[sid] = "already_filed"
        else:
            entry = _origin_entry(root, sid, evidence.get("entry_id"), provenance)
            pin = evidence.get("source_receipt_sha256")
            if entry is None:
                skipped[sid] = "origin_entry_unresolved"
            elif not is_digest(pin):
                skipped[sid] = "source_pin_unavailable"
            else:
                to_file.append(
                    {
                        "submission_id": sid,
                        "evaluation_key": key,
                        "entry_id": entry,
                        "pin": pin,
                        # no king evaluation on this key yet: it waits for his automatic regrade (`king_upkeep`)
                        "state": (
                            "PAUSED" if key in king_first else "PENDING_CONTENTION"
                        ),
                    }
                )
    return {"king": king, "exam": exam, "file": to_file, "skipped": skipped}


def file(root, pool_store, exam, *, apply=False, clock=time.time_ns):
    """`plan`, then (``apply``) file each challenger into the crown sweep's queue in grading order and log it."""
    planned = plan(root, pool_store, exam)
    if apply and planned["file"]:
        store = _store(pool_store)
        log_dir = Path(root) / "auto-grade" / "recontend"
        log_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        with open(log_dir / "recontend.jsonl", "a", encoding="utf-8") as log:
            for item in planned["file"]:
                store.record_crown_paused(
                    item["submission_id"],
                    item["evaluation_key"],
                    kind="pack",
                    exam=exam,
                    entry_id=item["entry_id"],
                    pin=item["pin"],
                    state=item["state"],
                )
                log.write(
                    json.dumps(
                        {
                            "at_ns": clock(),
                            "kind": "recontend_filed",
                            "king": planned["king"],
                            "submission_id": item["submission_id"],
                            "evaluation_key": item["evaluation_key"],
                            "state": item["state"],
                        },
                        sort_keys=True,
                    )
                    + "\n"
                )
                log.flush()
                os.fsync(log.fileno())
    return {
        "apply": apply,
        "king": planned["king"],
        "filed": [i["submission_id"] for i in planned["file"]],
        "skipped": planned["skipped"],
    }


def report(pool_store):
    """Every crown queue record of kind pack, oldest first, with its resolution code or None (pending)."""
    store = _store(pool_store)
    with store.db() as db:
        rows = db.execute(
            "SELECT body FROM operations WHERE kind='crown_paused.v1' ORDER BY rowid"
        ).fetchall()
    out = []
    for (raw,) in rows:
        record = json.loads(raw)
        if record.get("kind") != "pack":
            continue
        resolved = store.crown_pause_resolved(
            record["submission_id"], record["evaluation_key"]
        )
        out.append(
            {
                "submission_id": record["submission_id"],
                "evaluation_key": record["evaluation_key"],
                "resolution": resolved,
            }
        )
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="recontend", description=__doc__.splitlines()[0]
    )
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("plan", "file"):
        command = sub.add_parser(name)
        command.add_argument("--root", required=True)
        command.add_argument("--pool-store", required=True)
        command.add_argument("--exam", required=True)
        if name == "file":
            command.add_argument("--apply", action="store_true")
    shown = sub.add_parser("report")
    shown.add_argument("--pool-store", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "plan":
            out = plan(args.root, args.pool_store, args.exam)
            out = {**out, "file": [i["submission_id"] for i in out["file"]]}
        elif args.command == "file":
            out = file(args.root, args.pool_store, args.exam, apply=args.apply)
        else:
            out = report(args.pool_store)
    except RecontendRefused as refused:
        print(json.dumps({"refused": refused.code}))
        return 2
    print(json.dumps(out, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
