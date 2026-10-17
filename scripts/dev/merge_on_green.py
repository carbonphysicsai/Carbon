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
import tempfile
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from ci_merge import MergeError, check_receipt, passed, strict_base_rule


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
    base_sha: str | None = None
    receipt: dict[str, Any] | None = None
    strict_base_rule: bool = False


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
    if observed.state != "OPEN":
        return (
            Decision.STOP,
            "pull request state could not be confirmed open; no merge authority",
        )
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
            try:
                receipt = check_receipt(observed.receipt)
            except MergeError as error:
                return Decision.STOP, f"no exact head/base/merge acceptance: {error}"
            if receipt["head"]["sha"] != pinned_sha:
                return (
                    Decision.STOP,
                    "receipt names another head; re-validation required",
                )
            if not observed.base_sha:
                return (
                    Decision.STOP,
                    "main's current base could not be read; no merge authority",
                )
            if receipt["base"]["sha"] != observed.base_sha:
                return Decision.STOP, "validated base changed; re-validation required"
            if not passed(receipt):
                return Decision.STOP, "head and merge acceptance are not both passed"
            if not observed.strict_base_rule:
                return (
                    Decision.STOP,
                    "strict main base rule is not confirmed active; an API read alone cannot close the merge race",
                )
            return (
                Decision.MERGE,
                f"green on head {pinned_sha[:12]} and base {observed.base_sha[:12]}",
            )
        finished = (
            f"checks for {pinned_sha[:12]} completed as "
            f"{observed.run_conclusion or 'an unreported conclusion'}"
        )
        if observed.receipt:
            finished += "; " + str(observed.receipt.get("classification", "INCOMPLETE"))
        return Decision.STOP, finished
    if observed.run_status is None:
        return Decision.WAIT, f"no run has appeared yet for {pinned_sha[:12]}"
    if observed.run_status not in {
        "queued",
        "in_progress",
        "waiting",
        "requested",
        "pending",
    }:
        return Decision.STOP, "unrecognized CI run state; no merge authority"
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
    if not isinstance(payload, dict):
        return PullRequestState(state="UNREADABLE", head_sha=None)
    if payload.get("state") != "OPEN" or payload.get("headRefOid") != pinned_sha:
        return PullRequestState(
            state=payload.get("state", "UNREADABLE"), head_sha=payload.get("headRefOid")
        )
    main_ref = _gh("api", "repos/{owner}/{repo}/git/ref/heads/main")
    base = None
    try:
        if main_ref.returncode == 0:
            base = json.loads(main_ref.stdout).get("object", {}).get("sha")
    except (ValueError, AttributeError):
        pass

    runs = _gh(
        "run",
        "list",
        "--workflow",
        "ci.yml",
        "--branch",
        branch,
        "--limit",
        "10",
        "--json",
        "status,conclusion,headSha,databaseId",
    )
    status = conclusion = run_id = None
    if runs.returncode == 0:
        try:
            run_list = json.loads(runs.stdout)
            for run in run_list if isinstance(run_list, list) else []:
                if not isinstance(run, dict):
                    continue
                if run.get("headSha") == pinned_sha:
                    status = run.get("status")
                    conclusion = run.get("conclusion")
                    run_id = run.get("databaseId")
                    break
        except json.JSONDecodeError:
            pass
    receipt = None
    strict = False
    if status == "completed" and run_id:
        detail = _gh("api", f"repos/{{owner}}/{{repo}}/actions/runs/{run_id}")
        try:
            metadata = json.loads(detail.stdout) if detail.returncode == 0 else {}
            if not isinstance(metadata, dict):
                raise MergeError("CI run metadata is not an object")
            attempt = metadata.get("run_attempt")
            if (
                metadata.get("head_sha") == pinned_sha
                and type(attempt) is int
                and attempt > 0
            ):
                with tempfile.TemporaryDirectory(prefix="carbon-ci-merge-") as folder:
                    artifact = _gh(
                        "run",
                        "download",
                        str(run_id),
                        "--name",
                        f"ci-merge-result-{attempt}",
                        "--dir",
                        folder,
                    )
                    path = Path(folder) / "ci-merge-receipt.json"
                    if (
                        artifact.returncode == 0
                        and path.is_file()
                        and path.stat().st_size <= 1024 * 1024
                    ):
                        receipt = check_receipt(
                            json.loads(path.read_text(encoding="utf-8"))
                        )
            rules = _gh("api", "repos/{owner}/{repo}/rules/branches/main")
            if rules.returncode == 0:
                strict = strict_base_rule(json.loads(rules.stdout))
        except (OSError, ValueError, TypeError, MergeError):
            receipt = None
    return PullRequestState(
        state=payload.get("state", "UNREADABLE"),
        head_sha=payload.get("headRefOid"),
        run_status=status,
        run_conclusion=conclusion,
        base_sha=base,
        receipt=receipt,
        strict_base_rule=strict,
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
