"""DATA plan S8 / gap G10 (bank 21 Nov 2026): every Ladder document a miner was shown is kept append-only
(`LadderStore.history`), while the best / latest row that serving reads keeps overwriting as before.
"""

# ruff: noqa: F811
from __future__ import annotations

from carbon.challenge_validator.ladder_store import LadderStore
from carbon.scoring import grade_feedback as gf
from tests.cpu.test_feedback_reply_v7 import CHALLENGE, _ladder
from tests.cpu.test_gate_failure_feedback import (  # noqa: F401 - the fixture
    EXAM,
    HOTKEY,
    ledger,
)


def test_every_shown_document_is_kept_in_order_and_serving_is_unchanged(
    ledger,
):
    _ladder(ledger, gf.WALL_STOP_STATUS, gf.EARLY_STOP_STATUS)
    store = LadderStore(ledger)
    history = store.history(HOTKEY, CHALLENGE, EXAM)
    assert (
        len(history) == 3
    )  # the scored best, then each later result: nothing overwritten
    assert history[0][1].get("status") is not None
    assert all(type(ns) is int for ns, _doc in history)
    served = store.served(HOTKEY, CHALLENGE, EXAM)
    # serving still reads the best / latest row only: its latest is the newest history entry
    assert served["latest"] == history[-1][1]


def test_another_hotkey_or_exam_has_its_own_history(ledger):
    _ladder(ledger)
    store = LadderStore(ledger)
    assert len(store.history(HOTKEY, CHALLENGE, EXAM)) == 1
    assert store.history("5Other", CHALLENGE, EXAM) == []
