#!/usr/bin/env python3
"""Merge a pull request when its pinned revision goes green, or say why not.

Delivery standard 1.3: a wait that cannot say what it is waiting for is not
waiting. The watchers this replaces were shell loops that pinned a SHA copied
from a template and polled until a timeout. When the head moved, the pin could
never match again, so the loop ran to exhaustion in silence — and from outside,
"not yet" and "never" look identical. Six pull requests sat green and unmerged
on 2026-09-22 for exactly that reason. The expected-head guard behaved
correctly; the waiting did not.

So the decision is a pure function over the pull request's observed state, and
`WAIT` is only ever returned for a condition that can still come true. Every
terminal state — merged, closed, head moved, run finished without success — is
a `STOP` carrying the reason, which is the difference between reporting a
condition and continuing to sit on one.

    python3 scripts/dev/merge_on_green.py --pr 123 --head <sha>

The head may be omitted, in which case the pull request's current head is
pinned at the moment the watch starts. It is still pinned: the point is not to
merge whatever arrives, it is to merge the revision whose checks were seen.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from enum import Enum


class Decision(Enum):
    MERGE = "MERGE"
    WAIT = "WAIT"
    STOP = "STOP"


@dataclass(frozen=True)
class PullRequestState:
    """What one observation of the pull request saw.

    `run_status` and `run_conclusion` describe the checks **for the pinned
    revision**. `run_status=None` means no run for that revision was visible,
    which is a wait rather than a verdict: a run that has not appeared yet can
    still appear.
    """

    state: str
    head_sha: str | None
    run_status: str | None = None
    run_conclusion: str | None = None


def decide(pinned_sha: str, observed: PullRequestState) -> tuple[Decision, str]:
    """What to do about this pull request, and why, in terms that can be read.

    The ordering matters: every way the pin can stop being reachable is checked
    before anything that could return WAIT, so an unsatisfiable condition can
    never be reported as patience.
    """
    if observed.state == "MERGED":
        return Decision.STOP, "already merged; nothing to wait for"
    if observed.state == "CLOSED":
        return Decision.STOP, "closed without merging; the wait cannot come true"
    if not observed.head_sha:
        return (
            Decision.STOP,
            "the pull request's head could not be read; not waiting blind",
        )
    if observed.head_sha != pinned_sha:
        moved = (
            f"the pinned revision {pinned_sha[:12]} is no longer this pull "
            f"request's head ({observed.head_sha[:12]}); the wait cannot come "
            "true, so it is reported rather than continued"
        )
        return Decision.STOP, moved
    if observed.run_status == "completed":
        if observed.run_conclusion == "success":
            return Decision.MERGE, f"green on {pinned_sha[:12]}"
        finished = (
            f"checks for {pinned_sha[:12]} completed as "
            f"{observed.run_conclusion or 'an unreported conclusion'}"
        )
        return Decision.STOP, finished
    if observed.run_status is None:
        return Decision.WAIT, f"no run has appeared yet for {pinned_sha[:12]}"
    return (
        Decision.WAIT,
        f"checks for {pinned_sha[:12]} are {observed.run_status}",
    )


def _gh(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["gh", *args], capture_output=True, text=True, check=False)


def observe(pr: int, branch: str, pinned_sha: str) -> PullRequestState:
    """Read the pull request and the checks for the pinned revision."""
    view = _gh("pr", "view", str(pr), "--json", "state,headRefOid")
    if view.returncode != 0:
        return PullRequestState(state="UNREADABLE", head_sha=None)
    try:
        payload = json.loads(view.stdout)
    except json.JSONDecodeError:
        return PullRequestState(state="UNREADABLE", head_sha=None)

    runs = _gh(
        "run",
        "list",
        "--branch",
        branch,
        "--limit",
        "10",
        "--json",
        "status,conclusion,headSha",
    )
    status = conclusion = None
    if runs.returncode == 0:
        try:
            for run in json.loads(runs.stdout):
                if run.get("headSha") == pinned_sha:
                    status = run.get("status")
                    conclusion = run.get("conclusion")
                    break
        except json.JSONDecodeError:
            pass
    return PullRequestState(
        state=payload.get("state", "UNREADABLE"),
        head_sha=payload.get("headRefOid"),
        run_status=status,
        run_conclusion=conclusion,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pr", type=int, required=True)
    parser.add_argument("--head", help="revision to pin; defaults to the head now")
    parser.add_argument("--branch", help="branch whose runs to read")
    parser.add_argument("--interval", type=float, default=30.0)
    parser.add_argument(
        "--deadline-seconds",
        type=float,
        default=7200.0,
        help="stop and report rather than waiting indefinitely",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="decide and report; never merge"
    )
    args = parser.parse_args(argv)

    view = _gh("pr", "view", str(args.pr), "--json", "headRefOid,headRefName")
    if view.returncode != 0:
        print(
            f"cannot read pull request {args.pr}: {view.stderr.strip()}",
            file=sys.stderr,
        )
        return 2
    payload = json.loads(view.stdout)
    pinned = args.head or payload.get("headRefOid")
    branch = args.branch or payload.get("headRefName")
    if not pinned or not branch:
        print("the pull request reported no head or branch", file=sys.stderr)
        return 2
    print(f"watching {pinned} on {branch} for #{args.pr}", flush=True)

    started = time.monotonic()
    while True:
        decision, reason = decide(pinned, observe(args.pr, branch, pinned))
        if decision is Decision.STOP:
            print(f"STOP: {reason}", flush=True)
            return 1
        if decision is Decision.MERGE:
            print(f"MERGE: {reason}", flush=True)
            if args.dry_run:
                return 0
            merged = _gh(
                "pr", "merge", str(args.pr), "--merge", "--match-head-commit", pinned
            )
            print((merged.stdout or merged.stderr).strip(), flush=True)
            return 0 if merged.returncode == 0 else 1
        if time.monotonic() - started > args.deadline_seconds:
            # A deadline is not a failure of the pull request. It is this
            # watcher declining to keep waiting without saying so.
            print(f"STOP: deadline reached while {reason}", flush=True)
            return 1
        print(f"waiting: {reason}", flush=True)
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
