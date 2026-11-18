"""Owner D16 for builds (18 Nov 2026, via the Lead; V2 Y on BUILD_RETRY_SPEC_20261118): a build that ended on Carbon's
side (FAILED_INFRA, or UNRESOLVED: invariant 7) re-runs automatically as its next generation at its original place,
uncharged, a re-run of a re-run included, at most 3 times per failure code and 5 times per task chain; a spent cap writes
``build_retry_cap_spent`` to the owed-list feed. Fixture ids only.
"""

from __future__ import annotations

import json

from test_build_requeue import (  # noqa: F401 - the ledger fixture, the request patch and the door doubles
    A,
    B,
    N,
    _plain_requests,
    _door,
    _Provider,
    _queue,
    _requeue,
    ledger,
)
from test_recipe_graded_once import CONTRACT, HOTKEYS

from carbon.challenge_validator import lean_recipe
from carbon.research import DirectTaskStateV3, ResearchTaskId

NEXT = "rtsk_" + "f" * 64


def _journal(ledger):
    return ledger.path.parent / "auto-grade" / "requeued"


def _lines(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def test_an_unresolved_build_reruns_at_its_place_uncharged(ledger):
    _queue(ledger)
    door, provider = _door(ledger), _Provider({A: DirectTaskStateV3.UNRESOLVED})
    assert door._requeue_failed_build(HOTKEYS[0], ResearchTaskId(A), provider) == N
    assert provider.started == [(("req", HOTKEYS[0], 1), False)]
    order = ledger.submitted_outcomes(CONTRACT)
    assert order.index(N) < order.index(B)  # the original place, ahead of the later arrival
    with ledger._db() as db:  # its round/day bypass: the grade is never charged
        assert db.execute(
            "SELECT 1 FROM exam_requeues WHERE submission_id=?", (N,)
        ).fetchone()
    (line,) = _lines(_journal(ledger) / lean_recipe.BUILD_RETRIES)
    assert (line["from_task"], line["new_task"], line["chain_root"]) == (A, N, A)
    assert line["code"] == "direct_task_unresolved"


def test_a_rerun_of_a_rerun_counts_in_the_same_chain(ledger):
    _queue(ledger)
    door = _door(ledger)
    provider = _Provider({A: DirectTaskStateV3.FAILED_INFRA, N: DirectTaskStateV3.UNRESOLVED})
    provider._requests[N] = ("req", HOTKEYS[0], 1)
    assert door._requeue_failed_build(HOTKEYS[0], ResearchTaskId(A), provider) == N
    assert door._requeue_failed_build(HOTKEYS[0], ResearchTaskId(N), provider) == NEXT
    lines = _lines(_journal(ledger) / lean_recipe.BUILD_RETRIES)
    assert [line["chain_root"] for line in lines] == [A, A]


def _spent(ledger, code, count):
    directory = _journal(ledger)
    directory.mkdir(parents=True, exist_ok=True)
    with open(directory / lean_recipe.BUILD_RETRIES, "a") as log:
        for k in range(count):
            log.write(
                json.dumps(
                    {"from_task": A, "new_task": f"rtsk_{k:064x}", "chain_root": A, "code": code}
                )
                + "\n"
            )


def test_the_fourth_rerun_of_one_code_is_refused_and_owed(ledger):
    _queue(ledger)
    _spent(ledger, "direct_task_unresolved", lean_recipe.BUILD_CODE_RETRIES)
    door, provider = _door(ledger), _Provider({A: DirectTaskStateV3.UNRESOLVED})
    assert door._requeue_failed_build(HOTKEYS[0], ResearchTaskId(A), provider) is None
    assert provider.started == []
    (alert,) = _lines(_journal(ledger) / lean_recipe.BUILD_ALERTS)
    assert alert["event"] == "build_retry_cap_spent" and alert["reason"] == "owed_list"
    assert (alert["task"], alert["code"], alert["code_retries"]) == (
        A,
        "direct_task_unresolved",
        3,
    )


def test_another_code_reruns_until_the_chain_cap(ledger):
    _queue(ledger)
    _spent(ledger, "direct_task_unresolved", lean_recipe.BUILD_CODE_RETRIES)
    door, provider = _door(ledger), _Provider({A: DirectTaskStateV3.FAILED_INFRA})
    # a FAILED_INFRA ending is its own code: within the chain's 5
    assert door._requeue_failed_build(HOTKEYS[0], ResearchTaskId(A), provider) == N


def test_the_sixth_rerun_of_a_chain_is_refused_and_owed(ledger):
    _queue(ledger)
    _spent(ledger, "x", 2)
    _spent(ledger, "y", 3)
    door, provider = _door(ledger), _Provider({A: DirectTaskStateV3.FAILED_INFRA})
    assert door._requeue_failed_build(HOTKEYS[0], ResearchTaskId(A), provider) is None
    (alert,) = _lines(_journal(ledger) / lean_recipe.BUILD_ALERTS)
    assert alert["chain_retries"] == lean_recipe.BUILD_CHAIN_RETRIES


def test_a_miners_own_resubmit_still_wins(ledger):
    _queue(ledger)
    door, provider = _door(ledger), _Provider({A: DirectTaskStateV3.UNRESOLVED})
    # the miner resubmitted the recipe: its next generation is already known, so the door does not re-run it
    from test_build_requeue import _outcome

    _outcome(ledger, N)
    assert door._requeue_failed_build(HOTKEYS[0], ResearchTaskId(A), provider) is None
    assert provider.started == []
    assert _requeue(ledger) == "new_task_known"
