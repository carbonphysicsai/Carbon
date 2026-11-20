"""OWNER G-LEAD-10 for builds (20 Nov 2026, "Go with the table"), replacing owner D16's 3-per-code / 5-per-chain re-runs.

A build that ended on Carbon's side with a PROVEN Carbon-side class (`infra_diagnosis.classify`) is rebuilt ONCE as its
next generation at its original place, uncharged, on a healthy box (``healthy_box`` in `BUILD_RETRIES`), skipped if its
miner submitted since the failure; an UNKNOWN cause is not rebuilt (the miner resubmits when ready; no allowance was
used); a rebuild is never rebuilt again. Each refusal writes ``build_not_rerun`` to the owed-list feed. A receiver
stop's own cancellation keeps its earlier rule (`test_carbon_cut_requeue`). Fixture ids only.
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


def test_a_proven_carbon_side_build_is_rebuilt_once_at_its_place_on_a_healthy_box(
    door_ledger,
):
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
    assert line["code"] == "carbon_build_wall_busy_host"
    assert line["healthy_box"] is True
    # its build takes a slot only on a healthy box
    from carbon.development_session.bundle_construction_worker import (
        direct_child_identity,
    )

    assert direct_child_identity(N, "build") in lean_recipe.rebuild_build_identities(
        door_ledger.path
    )


def test_a_rebuild_is_never_rebuilt_again(door_ledger):
    _queue(door_ledger)
    door = _door(door_ledger)
    provider = _Provider(
        {A: DirectTaskStateV3.FAILED_INFRA, N: DirectTaskStateV3.FAILED_INFRA}
    )
    provider._requests[N] = ("req", HOTKEYS[0], 1)
    assert door._requeue_failed_build(HOTKEYS[0], ResearchTaskId(A), provider) == N
    assert door._requeue_failed_build(HOTKEYS[0], ResearchTaskId(N), provider) is None
    assert len(provider.started) == 1
    (alert,) = _lines(_journal(door_ledger) / lean_recipe.BUILD_ALERTS)
    assert (alert["event"], alert["reason"], alert["task"]) == (
        "build_not_rerun",
        "one_rebuild_spent",
        N,
    )


@pytest.mark.parametrize(
    "diagnosis",
    [
        None,  # no retained diagnosis
        {"failed_stage": "orchestration", "reason_code": "graph_decision", "tail": "x"},
    ],
)
def test_an_unknown_cause_is_not_rebuilt(door_ledger, diagnosis):
    _queue(door_ledger)
    door = _door(door_ledger)
    provider = _Provider({A: DirectTaskStateV3.FAILED_INFRA}, diagnosis=diagnosis)
    assert door._requeue_failed_build(HOTKEYS[0], ResearchTaskId(A), provider) is None
    assert provider.started == []
    (alert,) = _lines(_journal(door_ledger) / lean_recipe.BUILD_ALERTS)
    assert (alert["event"], alert["reason"]) == (
        "build_not_rerun",
        "unknown_no_rebuild",
    )


def test_a_miner_who_submitted_since_the_failure_gets_no_rebuild(tmp_path):
    clock = iter(range(1000, 100_000, 10))
    ledger = AttemptLedger(tmp_path / "attempts.sqlite3", clock=lambda: next(clock))
    _outcome(ledger, A)  # at 1000
    _outcome(ledger, B, hotkey=HOTKEYS[1])  # another miner's: never counts
    door = _door(ledger)
    # the failure completed at 1 us (1000 ns): A's own row is not "since"
    provider = _Provider({A: DirectTaskStateV3.FAILED_INFRA}, completed=1)
    _outcome(ledger, "rtsk_" + "9" * 64)  # the miner submitted again after the failure
    assert door._requeue_failed_build(HOTKEYS[0], ResearchTaskId(A), provider) is None
    assert provider.started == []
    (alert,) = _lines(_journal(ledger) / lean_recipe.BUILD_ALERTS)
    assert alert["reason"] == "miner_submitted_since"


def test_without_a_later_submission_the_rebuild_runs(tmp_path):
    clock = iter(range(1000, 100_000, 10))
    ledger = AttemptLedger(tmp_path / "attempts.sqlite3", clock=lambda: next(clock))
    _outcome(ledger, A)
    _outcome(ledger, B, hotkey=HOTKEYS[1])
    door = _door(ledger)
    provider = _Provider({A: DirectTaskStateV3.FAILED_INFRA}, completed=1)
    assert door._requeue_failed_build(HOTKEYS[0], ResearchTaskId(A), provider) == N


def test_a_miners_own_resubmit_still_wins(door_ledger):
    _queue(door_ledger)
    door = _door(door_ledger)
    provider = _Provider({A: DirectTaskStateV3.UNRESOLVED})
    # the miner resubmitted the recipe: its next generation is already known, so no door re-run
    _outcome(door_ledger, N)
    assert door._requeue_failed_build(HOTKEYS[0], ResearchTaskId(A), provider) is None
    assert provider.started == []
    assert _requeue(door_ledger) == "new_task_known"
