"""Owner D16 for builds (18 Nov 2026, via the Lead; V2 Y on BUILD_RETRY_SPEC_20261118).

A build that ended on Carbon's side (FAILED_INFRA, or UNRESOLVED: invariant 7) re-runs automatically as its next
generation at its original place, uncharged, a re-run of a re-run included, at most 3 times per failure code and 5
times per task chain; a spent cap writes ``build_retry_cap_spent`` to the owed-list feed. Fixture ids only.
"""

from __future__ import annotations

import json

import pytest
from test_build_requeue import (
    A,
    B,
    N,
    _door,
    _outcome,
    _Provider,
    _queue,
    _requeue,
)
from test_recipe_graded_once import CONTRACT, HOTKEYS

from carbon.challenge_validator import lean_recipe
from carbon.challenge_validator.ledger import AttemptLedger
from carbon.research import DirectTaskStateV3, ResearchTaskId

NEXT = "rtsk_" + "f" * 64


@pytest.fixture
def door_ledger(tmp_path):
    clock = iter(range(1000, 100_000, 10))
    return AttemptLedger(tmp_path / "attempts.sqlite3", clock=lambda: next(clock))


@pytest.fixture(autouse=True)
def _plain_requests(monkeypatch):
    # the fixture's requests are plain tuples, not wire records: their intent digest is over their repr
    import carbon.research

    monkeypatch.setattr(
        carbon.research, "canonical_bytes", lambda request: repr(request).encode()
    )


def _journal(attempts):
    return attempts.path.parent / "auto-grade" / "requeued"


def _lines(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def _spent(attempts, code, count):
    directory = _journal(attempts)
    directory.mkdir(parents=True, exist_ok=True)
    rows = [
        json.dumps(
            {
                "from_task": A,
                "new_task": f"rtsk_{k:064x}",
                "chain_root": A,
                "code": code,
            }
        )
        + "\n"
        for k in range(count)
    ]
    with open(directory / lean_recipe.BUILD_RETRIES, "a") as log:
        log.writelines(rows)


def test_an_unresolved_build_reruns_at_its_place_uncharged(door_ledger):
    _queue(door_ledger)
    door = _door(door_ledger)
    provider = _Provider({A: DirectTaskStateV3.UNRESOLVED})
    assert door._requeue_failed_build(HOTKEYS[0], ResearchTaskId(A), provider) == N
    assert provider.started == [(("req", HOTKEYS[0], 1), False)]
    order = door_ledger.submitted_outcomes(CONTRACT)
    assert order.index(N) < order.index(B)  # the original place, ahead of B
    with door_ledger._db() as db:  # its round/day bypass: the grade is never charged
        assert db.execute(
            "SELECT 1 FROM exam_requeues WHERE submission_id=?", (N,)
        ).fetchone()
    (line,) = _lines(_journal(door_ledger) / lean_recipe.BUILD_RETRIES)
    assert (line["from_task"], line["new_task"], line["chain_root"]) == (A, N, A)
    assert line["code"] == "direct_task_unresolved"


def test_a_rerun_of_a_rerun_counts_in_the_same_chain(door_ledger):
    _queue(door_ledger)
    door = _door(door_ledger)
    provider = _Provider(
        {A: DirectTaskStateV3.FAILED_INFRA, N: DirectTaskStateV3.UNRESOLVED}
    )
    provider._requests[N] = ("req", HOTKEYS[0], 1)
    assert door._requeue_failed_build(HOTKEYS[0], ResearchTaskId(A), provider) == N
    assert door._requeue_failed_build(HOTKEYS[0], ResearchTaskId(N), provider) == NEXT
    lines = _lines(_journal(door_ledger) / lean_recipe.BUILD_RETRIES)
    assert [line["chain_root"] for line in lines] == [A, A]


def test_the_fourth_rerun_of_one_code_is_refused_and_owed(door_ledger):
    _queue(door_ledger)
    _spent(door_ledger, "direct_task_unresolved", lean_recipe.BUILD_CODE_RETRIES)
    door = _door(door_ledger)
    provider = _Provider({A: DirectTaskStateV3.UNRESOLVED})
    assert door._requeue_failed_build(HOTKEYS[0], ResearchTaskId(A), provider) is None
    assert provider.started == []
    (alert,) = _lines(_journal(door_ledger) / lean_recipe.BUILD_ALERTS)
    assert alert["event"] == "build_retry_cap_spent"
    assert alert["reason"] == "owed_list"
    assert (alert["task"], alert["code"], alert["code_retries"]) == (
        A,
        "direct_task_unresolved",
        3,
    )


def test_another_code_reruns_until_the_chain_cap(door_ledger):
    _queue(door_ledger)
    _spent(door_ledger, "direct_task_unresolved", lean_recipe.BUILD_CODE_RETRIES)
    door = _door(door_ledger)
    provider = _Provider({A: DirectTaskStateV3.FAILED_INFRA})
    # a FAILED_INFRA ending is its own code: within the chain's 5
    assert door._requeue_failed_build(HOTKEYS[0], ResearchTaskId(A), provider) == N


def test_the_sixth_rerun_of_a_chain_is_refused_and_owed(door_ledger):
    _queue(door_ledger)
    _spent(door_ledger, "x", 2)
    _spent(door_ledger, "y", 3)
    door = _door(door_ledger)
    provider = _Provider({A: DirectTaskStateV3.FAILED_INFRA})
    assert door._requeue_failed_build(HOTKEYS[0], ResearchTaskId(A), provider) is None
    (alert,) = _lines(_journal(door_ledger) / lean_recipe.BUILD_ALERTS)
    assert alert["chain_retries"] == lean_recipe.BUILD_CHAIN_RETRIES


def test_a_miners_own_resubmit_still_wins(door_ledger):
    _queue(door_ledger)
    door = _door(door_ledger)
    provider = _Provider({A: DirectTaskStateV3.UNRESOLVED})
    # the miner resubmitted the recipe: its next generation is already known, so no door re-run
    _outcome(door_ledger, N)
    assert door._requeue_failed_build(HOTKEYS[0], ResearchTaskId(A), provider) is None
    assert provider.started == []
    assert _requeue(door_ledger) == "new_task_known"
