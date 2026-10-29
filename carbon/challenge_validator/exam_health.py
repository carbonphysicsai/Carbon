"""The operator's exam-health report: how old each Challenge's exam is, and what the weekly check said.

Operator only, never a miner surface: nothing imports this module and it reads the receiver's
own attempt ledger (``exam_keys``, ``fresh_draw_log``) read-only. It answers, per Challenge, in
plain words: which exam version is active, its age in days, the days left before the 90-day
limit stops grading, a warning from day 75, the last weekly overfit check (KEEP, ROTATE or
UNAVAILABLE, with its reason and date), and how many held-back fresh sets are on hand.

It shows no exam key, case, seed, total, standard error or threshold, only the version, the
dates, the outcome and its reason (EXAM_REFRESH_TRACKING_AUDIT_20261029, gap 5).

    python -m carbon.challenge_validator.exam_health --ledger <ledger> --block <current block>
"""

from __future__ import annotations

import datetime
import json
import sqlite3
import sys
from pathlib import Path

from carbon.challenge_validator.exam_cap import (
    _LEAN_CHALLENGES,
    DAY_BLOCKS,
    MAX_EXAM_AGE_BLOCKS,
)

WARN_DAYS = 75
LIMIT_DAYS = MAX_EXAM_AGE_BLOCKS // DAY_BLOCKS

#: The weekly check's closed reasons, in words (exam_rotation.decide).
_REASONS = {
    "sealed_exceeds_fresh_beyond_margin_and_2se": (
        "the king did clearly better on the sealed exam than on fresh cases"
    ),
    "within_margin_and_2se": "the king did about as well on fresh cases",
    "total_unavailable": "one of the two totals could not be read",
    "rebuild_noise_unregistered": "the crown margin is not registered yet",
    "standard_error_unavailable": "the exam's uncertainty was not measured",
}


def _rows(path, query, parameters=()):
    uri = Path(path).resolve().as_uri() + "?mode=ro"
    db = sqlite3.connect(uri, uri=True)
    try:
        cursor = db.execute(query, parameters)
        names = [column[0] for column in cursor.description]
        return [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]
    except sqlite3.OperationalError:
        return []  # the table is not there yet: nothing has been recorded
    finally:
        db.close()


def _version_key(version):
    return tuple(int(part) if part.isdigit() else 0 for part in version.split("."))


def _date(at_ns):
    moment = datetime.datetime.fromtimestamp(at_ns / 1e9, datetime.UTC)
    return moment.strftime("%Y-%m-%d")


def report(ledger, *, block, backlog=None):
    """One dict per Challenge. ``backlog`` is {challenge_id: fresh sets on hand} or None."""
    keys = _rows(
        ledger, "SELECT challenge_id, challenge_version, first_block FROM exam_keys"
    )
    checks = _rows(
        ledger,
        "SELECT challenge_id, challenge_version, block, outcome, reason, at_ns "
        "FROM fresh_draw_log ORDER BY id",
    )
    challenges = list(_LEAN_CHALLENGES)
    challenges += sorted({k["challenge_id"] for k in keys} - set(challenges))
    out = []
    for challenge in challenges:
        own = [k for k in keys if k["challenge_id"] == challenge]
        row = {"challenge": challenge, "backlog": None}
        if backlog is not None and challenge in backlog:
            row["backlog"] = backlog[challenge]
        if not own:
            out.append({**row, "state": "NO_EXAM_GRADED"})
            continue
        # The active exam is the newest key: the latest first block, then the newest version.
        active = max(
            own, key=lambda k: (k["first_block"], _version_key(k["challenge_version"]))
        )
        age_blocks = max(0, int(block) - active["first_block"])
        age = age_blocks // DAY_BLOCKS
        left = LIMIT_DAYS - age
        state = "EXPIRED" if left <= 0 else "WARNING" if age >= WARN_DAYS else "OK"
        mine = [c for c in checks if c["challenge_id"] == challenge]
        last = mine[-1] if mine else None
        out.append(
            {
                **row,
                "state": state,
                "version": active["challenge_version"],
                "age_days": age,
                "days_left": max(0, left),
                "last_check": (
                    None
                    if last is None
                    else {
                        "outcome": last["outcome"],
                        "reason": last["reason"],
                        "date": _date(last["at_ns"]),
                    }
                ),
            }
        )
    return out


def _check_words(last):
    if last is None:
        return "No weekly check has run yet."
    why = _REASONS.get(last["reason"], last["reason"].replace("_", " "))
    verdict = {
        "KEEP": "KEEP: keep the exam",
        "ROTATE": "ROTATE: replace the exam now",
        "UNAVAILABLE": "UNAVAILABLE: it could not decide",
    }[last["outcome"]]
    return f"Last weekly check ({last['date']}): {verdict} ({why})."


def render(rows):
    """Plain words, one block per Challenge, the most urgent first."""
    order = {"EXPIRED": 0, "WARNING": 1, "OK": 2, "NO_EXAM_GRADED": 3}
    lines = []
    for row in sorted(rows, key=lambda r: (order[r["state"]], r["challenge"])):
        name = row["challenge"]
        if row["state"] == "NO_EXAM_GRADED":
            lines.append(
                f"{name}: no exam has been graded yet, so there is no age to show."
            )
        else:
            head = f"{name} (exam v{row['version']}): {row['age_days']} days old"
            if row["state"] == "EXPIRED":
                head += f", past the {LIMIT_DAYS}-day limit. GRADING HAS STOPPED until the exam is replaced."
            elif row["state"] == "WARNING":
                head += f", {row['days_left']} days left. WARNING: replace it before day {LIMIT_DAYS}."
            else:
                head += f", {row['days_left']} days left."
            lines.append(head)
            lines.append("  " + _check_words(row["last_check"]))
            if row["last_check"] and row["last_check"]["outcome"] == "ROTATE":
                lines.append(
                    "  The weekly check says this exam is overfit: replace it now."
                )
        if row["backlog"] is None:
            lines.append("  Held-back fresh sets on hand: not recorded.")
        else:
            lines.append(f"  Held-back fresh sets on hand: {row['backlog']}.")
    return "\n".join(lines)


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(
        prog="python -m carbon.challenge_validator.exam_health",
        description="How old each Challenge's exam is and what the weekly check said (operator only).",
    )
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--block", type=int, required=True, help="the current block")
    parser.add_argument(
        "--backlog",
        type=Path,
        help='JSON {"<challenge>": <fresh sets on hand>} from the custody ledger',
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    backlog = None if args.backlog is None else json.loads(args.backlog.read_bytes())
    rows = report(args.ledger, block=args.block, backlog=backlog)
    print(json.dumps(rows, indent=2, sort_keys=True) if args.json else render(rows))
    return 1 if any(r["state"] == "EXPIRED" for r in rows) else 0


if __name__ == "__main__":
    sys.exit(main())
