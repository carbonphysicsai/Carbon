"""Delivery standard 1.3: WAIT is never returned for an unreachable condition.

The watchers this replaces polled a pinned SHA until a timeout. When the head
moved, the pin could never match again and the loop ran to exhaustion in
silence, so six pull requests sat green and unmerged. The defect was not the
pin — the expected-head guard is why the pin exists — it was that "not yet" and
"never" produced the same behaviour.

These are ordinary cases plus one property: over every terminal state, the
decision must not be WAIT.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "dev"))

import merge_on_green as watcher
from merge_on_green import Decision, PullRequestState, decide, strict_base_rule

PINNED = "a" * 40
MOVED = "b" * 40
BASE = "c" * 40


def receipt():
    return {
        "schema": "carbon.ci-merge-receipt.v1",
        "head": {"sha": PINNED, "tree": "d" * 40},
        "base": {"sha": BASE, "tree": "e" * 40},
        "merge": {"sha": "f" * 40, "tree": "0" * 40, "parents": [BASE, PINNED]},
        "head_result": "PASSED",
        "merge_result": "PASSED",
        "classification": "PASSED",
        "gate_result": "PASSED",
        "required_jobs": {"Contract and authority acceptance": 1},
        "jobs": [
            {
                "family": "Contract and authority acceptance",
                "revision": revision,
                "index": 0,
                "id": index + 1,
                "attempt": 1,
                "status": "completed",
                "conclusion": "success",
            }
            for index, revision in enumerate(("head", "merge"))
        ],
    }


def green(**changes):
    fields = {
        "state": "OPEN",
        "head_sha": PINNED,
        "base_sha": BASE,
        "run_status": "completed",
        "run_conclusion": "success",
        "receipt": receipt(),
        "strict_base_rule": True,
    }
    return PullRequestState(**{**fields, **changes})


def test_green_on_the_pinned_revision_merges() -> None:
    decision, reason = decide(
        PINNED,
        green(),
    )
    assert decision is Decision.MERGE
    assert PINNED[:12] in reason
    assert BASE[:12] in reason


@pytest.mark.parametrize(
    "changes",
    [
        {"receipt": None},
        {"base_sha": MOVED},
        {"base_sha": None},
        {"strict_base_rule": False},
    ],
)
def test_green_head_alone_does_not_authorize_merging(changes):
    decision, reason = decide(PINNED, green(**changes))
    assert decision is Decision.STOP and reason


@pytest.mark.parametrize(
    "mutation", ["wrong_head", "missing_merge_job", "unfinished_gate", "failed_merge"]
)
def test_only_complete_current_pair_acceptance_can_merge(mutation):
    value = receipt()
    if mutation == "wrong_head":
        value["head"]["sha"] = MOVED
        value["merge"]["parents"][1] = MOVED
    elif mutation == "missing_merge_job":
        value["jobs"].pop()
    elif mutation == "unfinished_gate":
        value["gate_result"] = "PENDING"
    else:
        value["jobs"][-1]["conclusion"] = "failure"
    assert decide(PINNED, green(receipt=value))[0] is Decision.STOP


@pytest.mark.parametrize(
    "strict,app,expected",
    [
        (True, 15368, True),
        (False, 15368, False),
        ("true", 15368, False),
        (True, 1, False),
        (True, "15368", False),
    ],
)
def test_base_guard_must_be_an_effective_strict_actions_gate(strict, app, expected):
    rules = [
        {
            "type": "required_status_checks",
            "parameters": {
                "strict_required_status_checks_policy": strict,
                "required_status_checks": [
                    {"context": "Merge gate", "integration_id": app}
                ],
            },
        }
    ]
    assert strict_base_rule(rules) is expected
    assert not strict_base_rule([])
    assert not strict_base_rule({})


def test_a_head_that_moved_stops_rather_than_waiting() -> None:
    """The case that produced the standard.

    The pinned revision can never be the head again, so every further poll is
    guaranteed to observe the same thing. Reporting it is the only honest
    option; continuing to poll is indistinguishable from patience.
    """
    decision, reason = decide(PINNED, PullRequestState("OPEN", MOVED))
    assert decision is Decision.STOP
    assert "no longer this pull request's head" in reason
    assert PINNED[:12] in reason and MOVED[:12] in reason


@pytest.mark.parametrize(
    "observed",
    [
        PullRequestState("MERGED", PINNED),
        PullRequestState("CLOSED", PINNED),
        PullRequestState("OPEN", None),
        PullRequestState("UNREADABLE", None),
        PullRequestState("UNREADABLE", PINNED),
        PullRequestState("OPEN", PINNED, run_status="UNKNOWN"),
        PullRequestState("OPEN", MOVED),
        PullRequestState(
            "OPEN", PINNED, run_status="completed", run_conclusion="failure"
        ),
        PullRequestState(
            "OPEN", PINNED, run_status="completed", run_conclusion="cancelled"
        ),
        PullRequestState("OPEN", PINNED, run_status="completed", run_conclusion=None),
    ],
)
def test_no_terminal_state_is_ever_reported_as_waiting(
    observed: PullRequestState,
) -> None:
    """The property, not an example of it.

    Each of these is a condition that cannot become true by waiting. If any one
    of them returned WAIT, the watcher would sit on it silently, which is the
    entire failure this module exists to prevent.
    """
    decision, reason = decide(PINNED, observed)
    assert decision is not Decision.WAIT, f"{observed} was reported as waiting"
    assert reason, "a stop with no reason is the thing being prevented"


@pytest.mark.parametrize(
    "observed,expected",
    [
        (PullRequestState("OPEN", PINNED), "no run has appeared yet"),
        (PullRequestState("OPEN", PINNED, run_status="queued"), "queued"),
        (PullRequestState("OPEN", PINNED, run_status="in_progress"), "in_progress"),
    ],
)
def test_a_wait_says_what_it_is_waiting_for(
    observed: PullRequestState, expected: str
) -> None:
    decision, reason = decide(PINNED, observed)
    assert decision is Decision.WAIT
    # A report that says only "waiting" cannot be told apart from one that
    # should say "stuck", so the reason carries the condition being waited on.
    assert expected in reason
    assert PINNED[:12] in reason


def test_a_missing_run_is_a_wait_and_a_finished_one_is_not() -> None:
    """Absent evidence is not a verdict, which is standard 1.2 one level down.

    No run for the pinned revision means the run has not appeared yet, and that
    can still change. A run that finished without success cannot.
    """
    assert decide(PINNED, PullRequestState("OPEN", PINNED))[0] is Decision.WAIT
    assert (
        decide(
            PINNED,
            PullRequestState(
                "OPEN", PINNED, run_status="completed", run_conclusion="failure"
            ),
        )[0]
        is Decision.STOP
    )


@pytest.mark.parametrize(
    "mutation",
    [
        None,
        "base_moved",
        "bad_artifact",
        "missing_artifact",
        "wrong_run_head",
        "bad_run_response",
        "loose_rule",
    ],
)
def test_observe_reads_current_main_and_the_latest_ci_attempt(monkeypatch, mutation):
    calls = []

    def fake_gh(*args):
        calls.append(args)
        data = None
        code = 0
        if args[:2] == ("pr", "view"):
            data = {"state": "OPEN", "headRefOid": PINNED}
        elif args[:2] == ("run", "list"):
            assert "--workflow" in args and "ci.yml" in args
            data = [
                {
                    "headSha": PINNED,
                    "databaseId": 123,
                    "status": "completed",
                    "conclusion": "success",
                }
            ]
        elif args == ("api", "repos/{owner}/{repo}/git/ref/heads/main"):
            data = {"object": {"sha": MOVED if mutation == "base_moved" else BASE}}
        elif args == ("api", "repos/{owner}/{repo}/actions/runs/123"):
            data = {
                "head_sha": MOVED if mutation == "wrong_run_head" else PINNED,
                "run_attempt": 2,
            }
            if mutation == "bad_run_response":
                data = []
        elif args[:2] == ("run", "download"):
            assert args[args.index("--name") + 1] == "ci-merge-result-2"
            folder = Path(args[args.index("--dir") + 1])
            if mutation == "missing_artifact":
                code = 1
            else:
                (folder / "ci-merge-receipt.json").write_text(
                    "bad" if mutation == "bad_artifact" else json.dumps(receipt())
                )
        elif args == ("api", "repos/{owner}/{repo}/rules/branches/main"):
            data = [
                {
                    "type": "required_status_checks",
                    "parameters": {
                        "strict_required_status_checks_policy": mutation
                        != "loose_rule",
                        "required_status_checks": [
                            {"context": "Merge gate", "integration_id": 15368}
                        ],
                    },
                }
            ]
        else:
            raise AssertionError(args)
        return subprocess.CompletedProcess(args, code, json.dumps(data), "")

    monkeypatch.setattr(watcher, "_gh", fake_gh)
    observed = watcher.observe(123, "fixture-branch", PINNED)
    assert decide(PINNED, observed)[0] is (
        Decision.MERGE if mutation is None else Decision.STOP
    )
    assert not any(args[:2] == ("pr", "merge") for args in calls)


def test_dry_run_never_calls_merge_even_for_a_valid_pair(monkeypatch, capsys):
    calls = []

    def fake_gh(*args):
        calls.append(args)
        assert args[:2] == ("pr", "view")
        return subprocess.CompletedProcess(
            args,
            0,
            json.dumps({"headRefOid": PINNED, "headRefName": "fixture-branch"}),
            "",
        )

    monkeypatch.setattr(watcher, "_gh", fake_gh)
    monkeypatch.setattr(watcher, "observe", lambda *args: green())
    assert watcher.main(["--pr", "123", "--dry-run"]) == 0
    assert "MERGE:" in capsys.readouterr().out
    assert len(calls) == 1


def test_the_merge_decision_is_pinned_to_the_revision_that_was_checked() -> None:
    """Green on some other revision is not green on this one."""
    decision, _ = decide(
        PINNED,
        PullRequestState(
            "OPEN", MOVED, run_status="completed", run_conclusion="success"
        ),
    )
    assert decision is Decision.STOP
