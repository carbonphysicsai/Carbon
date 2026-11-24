"""Re-rank a version from its kept grades when its crown row names another recorded number (owner G-LEAD-83, 24 Nov 2026).

`crown_official` says which recorded number ranks a version. When that number is not the total, the receiver does two
things ONCE per rule entry and exam, from the private evaluations it already keeps, and nothing is graded, rescored or
rewritten:

The crown is decided first, and until both are made no grade is claimed, for a bounded time
(`auto_grade.AutoGrader._rerank_holds_grades`).

- LADDER: the version's Ladder has a new key (`ladder_store.ladder_label`), so it starts empty. For every hotkey with no
  document under it yet, the best kept evaluation and then the latest one are recorded through the receiver's own path
  (`lean_recipe_retention._record_ladder`), so the board and each miner's feedback follow the new number. Documents under
  the old key stay as they are.
- CROWN: the kept evaluation with the highest ranked number (the oldest of equals) meets the sitting king through the
  ordinary decision (`lean_recipe_retention.reconsider_paused_pack`: the margin, the queue, the pause, the hold, the
  records). Nobody below it can win what it cannot. No hotkey and no submission is named in code or configuration. A
  hotkey the chain does not show registered now is not contended for (its rows stay ranked); while the chain cannot be
  read the step waits. A first that held this crown before is declined (``former_incumbent``) and the king stays.

A kept grade that holds no such number, or does not show that its row check passed (`crown_official.row_check_unknown`),
is not ranked and gets no value (`ranking` counts it by reason). The crown step
waits while crowns are paused or an earlier decision is undecided. Done once, a line in
``<root>/auto-grade/rerank/rerank.jsonl`` (custody: task id, codes; no score) stops a later start from deciding again.

    python -m carbon.challenge_validator.rerank plan --pool-store POOL --challenge ID --version V --exam sha256:...

prints the ranking (operator only: it holds exact values) and changes nothing.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time
from pathlib import Path

from carbon.challenge_validator import crown_official, koth_journal

SCORED = "SCORED_DEVELOPMENT_CANDIDATE"
_TASK = re.compile(r"rtsk_[0-9a-f]{64}")
_SS58 = re.compile(r"[1-9A-HJ-NP-Za-km-z]{47,48}")
#: Crown outcomes that decide the re-rank; anything else (paused, queued, held, undecided) is tried again.
DECIDED = frozenset(
    {
        "FIRST_INCUMBENT",
        "CHALLENGER",
        "INCUMBENT_KEEPS",
        "NO_WINNER",
        "DETHRONED",
        "DECLINED",
    }
)
#: Seconds between two tries of a crown step that could not be decided (the crown sweep's own spacing; sooner while it
#: holds the first grades back, `auto_grade.RERANK_START_RETRY_SECONDS`).
RETRY_SECONDS = 5 * 60


def _number(value):
    return (
        type(value) in (int, float)
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _hotkey(body):
    owner = body.get("owner")
    owner = owner.get("hotkey") if type(owner) is dict else owner
    return owner if type(owner) is str and _SS58.fullmatch(owner) else None


def kept(store, *, challenge_id, exam):
    """The latest kept evaluation of every miner submission on ``exam``, in grading order:
    ``[{"submission_id", "hotkey", "evaluation_key", "recipe_digest", "evidence"}]``."""
    latest = {}
    for body in store.private_evaluation_bodies():
        evidence = body.get("evidence") if type(body) is dict else None
        if (
            type(evidence) is not dict
            or type(evidence.get("model_p")) is not dict
            or evidence.get("challenge") != challenge_id
            or evidence.get("evaluation_pack_digest") != exam
            or type(body.get("submission_id")) is not str
            or not _TASK.fullmatch(body["submission_id"])
            or _hotkey(body) is None
        ):
            continue
        submission_id = body["submission_id"]
        # its place is its FIRST grade's: a later evaluation of the same task (a regrade) is the same submission
        latest[submission_id] = {
            "submission_id": submission_id,
            "hotkey": _hotkey(body),
            "evaluation_key": body.get("evaluation_key"),
            "recipe_digest": body.get("recipe_digest"),
            "evidence": evidence,
        }
    return list(latest.values())


def ranking(rows, score):
    """``(ranked, unranked)``: the scored rows with a stored ranked number, highest first and the oldest of equals first;
    and how many rows have none, by reason."""
    ranked, unranked = [], {}
    for row in rows:
        model = row["evidence"]["model_p"]
        value = crown_official.value(model, score)
        if model.get("score_status") != SCORED:
            reason = str(model.get("score_status"))
        elif not _number(value):
            reason = (
                "row_check_unknown"
                if score != crown_official.TOTAL
                and crown_official.row_check_unknown(model)
                else "no_stored_number"
            )
        else:
            ranked.append({**row, "value": float(value)})
            continue
        unranked[reason] = unranked.get(reason, 0) + 1
    ranked.sort(key=lambda row: -row["value"])  # stable: the oldest of equals first
    return ranked, unranked


def graded_row(evidence):
    """The graded score row of a kept evaluation, as far as it keeps it (`private_evaluation_evidence`): the status, the
    total, both legs and the gates. `_record_ladder` then reads the ranked leg from it.
    """
    model = evidence["model_p"]
    return {
        "status": model.get("score_status"),
        "score": model.get("total_score"),
        "legs": {"A": model.get("physics_benefit"), "D": model.get("design_benefit")},
        "gates": model.get("gate_outcomes"),
    }


def backfill_order(rows, score):
    """``[(hotkey, [row, ...])]``: what each hotkey's fresh Ladder is started from: its best ranked row, then its latest one
    when that is another (so the best it shows is its best, whatever the order it was graded in).
    """
    by_hotkey = {}
    for row in rows:
        by_hotkey.setdefault(row["hotkey"], []).append(row)
    out = []
    for hotkey in sorted(by_hotkey):
        own = by_hotkey[hotkey]
        ranked, _ = ranking(own, score)
        best = ranked[:1]
        out.append(
            (
                hotkey,
                [
                    *best,
                    *(
                        []
                        if best and own[-1]["submission_id"] == best[0]["submission_id"]
                        else own[-1:]
                    ),
                ],
            )
        )
    return out


def _log_path(root):
    return Path(root) / "auto-grade" / "rerank" / "rerank.jsonl"


def done(root, rule_digest, exam):
    """Whether this rule entry's re-rank on this exam was decided already."""
    try:
        lines = _log_path(root).read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return False
    for line in lines:
        try:
            body = json.loads(line)
        except ValueError:
            continue
        if (
            type(body) is dict
            and body.get("kind") == "rerank_decided"
            and body.get("rule_digest") == rule_digest
            and body.get("exam") == exam
        ):
            return True
    return False


def _log(root, record):
    path = _log_path(root)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as log:
        log.write(
            json.dumps({"at_ns": time.time_ns(), **record}, sort_keys=True) + "\n"
        )
        log.flush()
        os.fsync(log.fileno())


def backfill(adapter, rows, score):
    """Start the fresh Ladder of every hotkey that has no document under the new key; returns ``(recorded, refused)``."""
    from carbon.challenge_validator.ladder_store import LadderStore
    from carbon.challenge_validator.lean_recipe_retention import _record_ladder

    if not rows:
        return 0, 0
    discovery = adapter.discovery
    snapshot = discovery.evaluation_pack_snapshot
    score_pack = snapshot.read_json_role(
        discovery.evaluation_pack_private_root, "private", "score_pack", max_bytes=65536
    )
    ladder = LadderStore(adapter.ledger)
    challenge = discovery.info.challenge_key
    # one label for the whole start: the newest kept evaluation's, which the next live grade carries too
    exam_version = rows[-1]["evidence"]["evaluation_version"]
    recorded = refused = 0
    for hotkey, start in backfill_order(rows, score):
        if ladder.served(hotkey, challenge, snapshot.manifest_digest)["latest"]:
            continue
        for row in start:
            state = _record_ladder(
                adapter,
                row["submission_id"],
                exam_key=snapshot.manifest_digest,
                exam_version=exam_version,
                gates=score_pack["hard_gates"],
                graded=graded_row(row["evidence"]),
                recipe_digest=row["recipe_digest"],
                leg_minimums={
                    name: leg["minimum"] for name, leg in score_pack["legs"].items()
                },
                score_pack=score_pack,
            )
            if str(state).startswith("RECORDED"):
                recorded += 1
            else:
                refused += 1
                koth_journal.note(
                    "rerank_ladder_refused",
                    submission_id=row["submission_id"],
                    code=str(state),
                )
    return recorded, refused


def registered_now(window):
    """``hotkey -> bool`` from the receiver's own finalized chain snapshot, or None when it holds no usable one."""
    from carbon.battery.intake import grading_snapshot

    snapshot = None if window is None else grading_snapshot(window)
    return None if snapshot is None else lambda key: snapshot.resolve(key) is not None


def step(
    adapter,
    pool,
    *,
    root,
    artifacts,
    entries,
    registered=None,
    reconsider=None,
    start=backfill,
):
    """The re-rank of the served version, if its rule asks for one and it was not decided: the crown, then the Ladder start.
    Returns True when there is nothing (more) to do, False when the crown step must be tried again.
    """
    active = crown_official.ACTIVE
    score = None if active is None else active.get("score", crown_official.TOTAL)
    if active is None or score == crown_official.TOTAL or pool is None:
        return True
    exam = adapter.discovery.evaluation_pack_digest
    if exam is None or done(root, active["digest"], exam):
        return True
    if registered is None:
        koth_journal.note("rerank_waits", reason="registration_unknown")
        return False
    rows = kept(pool, challenge_id=active["challenge"], exam=exam)
    everyone, unranked = ranking(rows, score)
    ranked = [row for row in everyone if registered(row["hotkey"])]
    koth_journal.note(
        "rerank_started",
        ranked=len(everyone),
        unregistered=len(everyone) - len(ranked),
        unranked=sum(unranked.values()),
    )
    if not ranked:
        outcome, first = {"outcome": "NO_WINNER", "reason": "nothing_ranked"}, None
    else:
        first = ranked[0]["submission_id"]
        incumbent = (pool.incumbent() or {}).get("model_id")
        if incumbent == first:
            outcome = {"outcome": "INCUMBENT_KEEPS", "reason": "already_incumbent"}
        elif any(
            event["body"].get("model_id") == first for event in pool.events("incumbent")
        ):
            # the pay ledger keeps one record per crowned model, with the king it beat: a former king crowned again would be
            # refused by the pay loop every cycle (v2 7300). Declined by name, the sitting king stays, for a human to rule.
            outcome = {"outcome": "DECLINED", "reason": "former_incumbent"}
        else:
            record = {
                "submission_id": first,
                "evaluation_key": ranked[0]["evaluation_key"],
                "entry_id": ranked[0]["evidence"].get("entry_id"),
                "pin": ranked[0]["evidence"].get("source_receipt_sha256"),
            }
            if reconsider is None:
                from carbon.challenge_validator.lean_recipe_retention import (
                    reconsider_paused_pack,
                )

                outcome = reconsider_paused_pack(
                    adapter,
                    pool,
                    record,
                    artifact_directory=artifacts,
                    entry_directory=entries,
                )
            else:
                outcome = reconsider(record)
            koth_journal.contention("rerank", first, outcome, incumbent, store=pool)
    koth_journal.note(
        "rerank_crown",
        candidate=first,
        outcome=outcome.get("outcome"),
        reason=outcome.get("reason"),
    )
    if outcome.get("outcome") not in DECIDED:
        return False
    # the crown first, then the Ladder: a start cut short between the two meets a decided crown and starts the rest
    recorded, refused = start(adapter, rows, score)
    koth_journal.note("rerank_ladder", recorded=recorded, refused=refused)
    _log(
        root,
        {
            "kind": "rerank_decided",
            "rule_digest": active["digest"],
            "exam": exam,
            "score": score,
            "submission_id": first,
            "outcome": outcome["outcome"],
            "reason": outcome.get("reason"),
            "ranked": len(everyone),
            "unregistered": len(everyone) - len(ranked),
            "unranked": unranked,
        },
    )
    return True


def plan(store, *, challenge_id, version, exam, score):
    """What a re-rank of this version by ``score`` would rank (read only; exact values: operator only)."""
    rows = kept(store, challenge_id=challenge_id, exam=exam)
    ranked, unranked = ranking(rows, score)
    return {
        "challenge": challenge_id,
        "version": version,
        "exam": exam,
        "score": score,
        "incumbent": (store.incumbent() or {}).get("model_id"),
        "undecided_crowns": len(store.paused_crowns()),
        "unranked": unranked,
        "ranked": [
            {
                "submission_id": row["submission_id"],
                "hotkey": row["hotkey"],
                "value": row["value"],
                "total": row["evidence"]["model_p"].get("total_score"),
                "evaluation_key": row["evaluation_key"],
            }
            for row in ranked
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(prog="rerank", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    command = sub.add_parser("plan")
    command.add_argument("--pool-store", required=True)
    command.add_argument("--challenge", required=True)
    command.add_argument("--version", required=True)
    command.add_argument("--exam", required=True)
    command.add_argument(
        "--score", choices=crown_official.SCORES, default=crown_official.ACCURACY
    )
    args = parser.parse_args(argv)
    from carbon.battery.pool_store import PoolStore

    path = Path(args.pool_store)
    if path.is_symlink() or not path.is_file():
        print(json.dumps({"refused": "pool_store_unavailable"}))
        return 2
    out = plan(
        PoolStore(path),
        challenge_id=args.challenge,
        version=args.version,
        exam=args.exam,
        score=args.score,
    )
    print(json.dumps(out, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
