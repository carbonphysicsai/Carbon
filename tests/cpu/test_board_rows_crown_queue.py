"""Lead, 19 Nov 2026: under fix 1b, a grade whose crown decision waits in the claim-ordered crown queue has ended (its
lane and round freed, its marker written); the board's v4 rows say "grading" only for grades RUNNING
(`Sequencer.running`), so it never shows as grading.
"""

from __future__ import annotations

import threading

from carbon.challenge_validator import grade_sequencer
from carbon.development_session import research_carrier


def test_a_grade_whose_crown_decision_is_queued_is_not_running(monkeypatch):
    monkeypatch.setattr(research_carrier, "yield_grade_session", lambda: None)
    sequencer = grade_sequencer.Sequencer()
    a_running, b_done, a_end = threading.Event(), threading.Event(), threading.Event()
    seen = {}

    def first():  # the earlier grade: still running its graded pass
        with sequencer.task() as task:
            task.bind("A")
            task.release_claim()
            task.reserved()
            a_running.set()
            assert a_end.wait(5)

    def second():  # the later grade: done, its crown decision waits behind A's
        assert a_running.wait(5)
        with sequencer.task() as task:
            task.bind("B")
            task.release_claim()
            task.reserved()
            seen["crown"] = task.crown(lambda: "decided")
        b_done.set()

    threads = [threading.Thread(target=f) for f in (first, second)]
    for thread in threads:
        thread.start()
    assert b_done.wait(5)
    assert seen["crown"] is grade_sequencer.CROWN_QUEUED
    assert sequencer.running() == {"A"}  # B ended: queued crown, not grading
    a_end.set()
    for thread in threads:
        thread.join(5)
    assert sequencer.running() == set()
