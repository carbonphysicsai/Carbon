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

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "dev"))

from merge_on_green import Decision, PullRequestState, decide

PINNED = "a" * 40
MOVED = "b" * 40


def test_green_on_the_pinned_revision_merges() -> None:
    decision, reason = decide(
        PINNED,
        PullRequestState(
            "OPEN", PINNED, run_status="completed", run_conclusion="success"
        ),
    )
    assert decision is Decision.MERGE
    assert PINNED[:12] in reason


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


def test_the_merge_decision_is_pinned_to_the_revision_that_was_checked() -> None:
    """Green on some other revision is not green on this one."""
    decision, _ = decide(
        PINNED,
        PullRequestState(
            "OPEN", MOVED, run_status="completed", run_conclusion="success"
        ),
    )
    assert decision is Decision.STOP
