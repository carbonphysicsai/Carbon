"""Lead, 19 Nov 2026 (live 116: one round held the grade claim lock ~25 min with no container): a round whose claim
loop met "not yet" tasks logs one ``grade_claim_scan`` line with their closed codes; each round thread counts its own.
"""

from __future__ import annotations

import threading

from carbon.challenge_validator import auto_grade


def _grader():
    return auto_grade.AutoGrader.__new__(auto_grade.AutoGrader)


def test_a_round_logs_its_retried_tasks_codes_and_seconds(monkeypatch):
    lines = []
    monkeypatch.setattr(
        "carbon.battery.intake.log", lambda event, **f: lines.append((event, f))
    )
    grader = _grader()
    grader._scan_local().codes = {}
    grader._note_next("owned_task_unavailable")
    grader._note_next("owned_task_unavailable")
    grader._note_next("task_not_succeeded")
    grader._log_claim_scan(3, started=0.0)
    [(event, fields)] = lines
    assert event == "grade_claim_scan" and fields["retried"] == 3
    assert fields["next_owned_task_unavailable"] == 2
    assert fields["next_task_not_succeeded"] == 1
    assert type(fields["seconds"]) is float


def test_a_round_with_nothing_retried_logs_nothing(monkeypatch):
    lines = []
    monkeypatch.setattr(
        "carbon.battery.intake.log", lambda event, **f: lines.append((event, f))
    )
    grader = _grader()
    grader._log_claim_scan(0, started=0.0)
    assert lines == []


def test_each_round_thread_counts_its_own_codes():
    grader = _grader()
    grader._scan_local().codes = {}
    grader._note_next("task_not_succeeded")
    seen = {}

    def other():
        grader._scan_local().codes = {}
        grader._note_next("owned_task_unavailable")
        seen.update(grader._scan_local().codes)

    thread = threading.Thread(target=other)
    thread.start()
    thread.join()
    assert seen == {"owned_task_unavailable": 1}
    assert grader._scan_local().codes == {"task_not_succeeded": 1}
