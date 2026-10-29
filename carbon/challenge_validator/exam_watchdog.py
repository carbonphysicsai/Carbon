"""The weekly fresh-draw check's watchdog: an alert when the check did not run or its last run failed.

Operator only, never a miner surface: nothing imports this module. It reads the receiver's attempt ledger
(``exam_keys``, ``fresh_draw_log``) read-only, schedules nothing and rotates nothing (the weekly timer in
``exam_rotation`` is the only runner). It alerts, per active exam, when

- no ``fresh_draw_log`` row is newer than 8 days (the timer did not run, or its run could not even log a miss), or
- the newest row is a week the check could not run: ``chain_unavailable`` alerts; ``no_incumbent`` and
  ``fresh_draw_set_unavailable`` (expected until the first crown / the backlog exists) only WARN with exit 0, or
- the weekly service's last result is not ``success`` (systemd ``Result``, read with ``systemctl --user show``).

The alert path is the exam-age report's: plain lines, exit code 1 only for an ALERT (a WARN exits 0).

    python -m carbon.challenge_validator.exam_watchdog --ledger <ledger> [--no-unit-check]
"""

from __future__ import annotations

import sqlite3
import subprocess
import sys
import time
from pathlib import Path

from carbon.challenge_validator.exam_rotation import UNIT_NAME

MAX_SILENCE_DAYS = 8
_DAY_NS = 24 * 3600 * 10**9
#: Reasons of a week the check could not run (exam_rotation.run_weekly); KEEP and ROTATE are decisions, not failures.


def _rows(path, query):
    """Read-only rows of the ledger as dicts; an absent table has no rows."""
    db = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)
    try:
        cursor = db.execute(query)
        names = [column[0] for column in cursor.description]
        return [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]
    except sqlite3.OperationalError:
        return []
    finally:
        db.close()


#: Expected early (no crown yet; no held-back fresh sets yet): a WARN line, exit 0, so the alert does not fire every
#: week from day one and get ignored. The others (staleness, chain_unavailable, a failed timer) are ALERTs, exit 1.
WARN_MISSES = ("no_incumbent", "fresh_draw_set_unavailable")
RUN_MISSES = ("chain_unavailable", "no_incumbent", "fresh_draw_set_unavailable")


def unit_result(*, run=subprocess.run):
    """The weekly service's last systemd ``Result`` ('success', 'exit-code', ...), or None when it cannot be read."""
    done = run(
        [
            "systemctl",
            "--user",
            "show",
            f"{UNIT_NAME}.service",
            "-p",
            "Result",
            "--value",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    return done.stdout.strip() if done.returncode == 0 and done.stdout.strip() else None


def alerts(ledger, *, now_ns, unit=None):
    """[{challenge, kind, detail}] for every active exam whose weekly check is overdue or failed, plus one
    ``weekly_unit_failed`` when ``unit`` (a callable like `unit_result`) reports a result other than success.
    """
    keys = _rows(ledger, "SELECT DISTINCT challenge_id FROM exam_keys")
    checks = _rows(
        ledger,
        "SELECT challenge_id, outcome, reason, at_ns FROM fresh_draw_log ORDER BY id",
    )
    found = []
    for challenge in sorted(k["challenge_id"] for k in keys):
        mine = [c for c in checks if c["challenge_id"] == challenge]
        newest = max((c["at_ns"] for c in mine), default=None)
        if newest is None or now_ns - newest > MAX_SILENCE_DAYS * _DAY_NS:
            found.append(
                {
                    "challenge": challenge,
                    "kind": "weekly_check_overdue",
                    "severity": "ALERT",
                    "detail": f"no weekly check row newer than {MAX_SILENCE_DAYS} days",
                }
            )
        last = mine[-1] if mine else None
        if last and last["outcome"] == "UNAVAILABLE" and last["reason"] in RUN_MISSES:
            found.append(
                {
                    "challenge": challenge,
                    "kind": "weekly_check_failed",
                    "severity": "WARN" if last["reason"] in WARN_MISSES else "ALERT",
                    "detail": f"the last weekly run could not run: {last['reason']}",
                }
            )
    if unit is not None:
        result = unit()
        if result is not None and result != "success":
            found.append(
                {
                    "challenge": None,
                    "kind": "weekly_unit_failed",
                    "severity": "ALERT",
                    "detail": f"the weekly service's last result is {result}",
                }
            )
    return found


def render(found):
    if not found:
        return "Weekly fresh-draw check: on time, nothing failed."
    lines = []
    for alert in found:
        who = alert["challenge"] or "weekly timer"
        lines.append(f"{alert['severity']} {who}: {alert['kind']}: {alert['detail']}.")
    return "\n".join(lines)


def main(argv=None, *, clock=time.time_ns, unit=unit_result):
    import argparse

    parser = argparse.ArgumentParser(
        prog="python -m carbon.challenge_validator.exam_watchdog",
        description="Alert when the weekly fresh-draw check is overdue or failed (operator only).",
    )
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--no-unit-check", action="store_true")
    args = parser.parse_args(argv)
    found = alerts(
        args.ledger, now_ns=clock(), unit=None if args.no_unit_check else unit
    )
    print(render(found))
    return 1 if any(a["severity"] == "ALERT" for a in found) else 0


if __name__ == "__main__":
    sys.exit(main())
