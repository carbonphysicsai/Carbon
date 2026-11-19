"""Live 116, 19 Nov 2026 (no construction-submit for an hour; py-spy: 10 requests waiting at the door-wide `_write`
behind ONE source chunk's owner-tree storage scan and body rewrite): a source stage holds only its OWN owner's lock
(`DirectRecipeIntake._stage`), never `_write`, so one owner's uploads never block another owner's submit. An owner's
own admission still never overlaps its own stage (owner lock first, then its admission scopes). Fixture doubles only.
"""

from __future__ import annotations

import threading
import time
from types import SimpleNamespace

from carbon.challenge_validator.direct_intake import DirectRecipeIntake

CHUNK_S = 0.02


def _intake(evaluate=None):
    intake = object.__new__(DirectRecipeIntake)
    intake._write = threading.Lock()
    intake.door = SimpleNamespace(evaluate=evaluate or (lambda submitted: {"kind": "OUTCOME"}))
    intake._note_recipe_digest = lambda result: None
    return intake


def _received(hotkey):
    return SimpleNamespace(receipt=SimpleNamespace(hotkey=hotkey))


def test_100_owners_x_30_chunks_never_hold_a_submit_past_a_bound():
    inside = {}
    overlap = []
    guard = threading.Lock()

    def stage_source(received):
        owner = received.receipt.hotkey
        with guard:
            if inside.get(owner):
                overlap.append(owner)
            inside[owner] = True
        time.sleep(CHUNK_S)  # the chunk's storage scan + rewrite, per owner
        with guard:
            inside[owner] = False
        return "staged"

    intake = _intake()
    intake._stage_source = stage_source

    def uploads(owner):
        for _ in range(30):
            assert intake._stage(_received(owner)) == "staged"

    workers = [threading.Thread(target=uploads, args=(f"5Owner{i:03d}",)) for i in range(100)]
    for w in workers:
        w.start()
    time.sleep(0.1)  # every owner mid-upload
    began = time.monotonic()
    assert intake._admit(SimpleNamespace(hotkey="5Submitter")) == {"kind": "OUTCOME"}
    took = time.monotonic() - began
    for w in workers:
        w.join(60)
    # 3,000 chunks at 20 ms would hold a door-wide lock for 60 s; per owner, a submit waits for none of them
    assert took < 1.0, took
    assert overlap == []  # one owner's chunks still one at a time


def test_an_owners_own_admission_waits_for_its_stage_without_holding_write():
    order = []
    staging, release = threading.Event(), threading.Event()

    def stage_source(received):
        order.append("stage-start")
        staging.set()
        release.wait(5)
        order.append("stage-end")
        return "staged"

    def evaluate(submitted):
        order.append("admit")
        return {"kind": "OUTCOME"}

    intake = _intake(evaluate)
    intake._stage_source = stage_source
    stage = threading.Thread(target=intake._stage, args=(_received("5Same"),))
    stage.start()
    staging.wait(5)
    admit = threading.Thread(target=intake._admit, args=(SimpleNamespace(hotkey="5Same"),))
    admit.start()
    time.sleep(0.1)
    # the waiting admission holds its owner's turn only: another owner's admission goes through meanwhile
    assert intake._admit(SimpleNamespace(hotkey="5Other")) == {"kind": "OUTCOME"}
    release.set()
    stage.join(5)
    admit.join(5)
    # the other owner's admission ran during the stage; the same owner's only after its stage ended
    assert order == ["stage-start", "admit", "stage-end", "admit"]


def test_admissions_are_one_at_a_time_per_scope_and_parallel_across_scopes():
    """LOCK + CACHE AUDIT #2 (19 Nov 2026): no door-wide writer. Admissions of one allowance group run one at a time
    (the group's rules read each other's state); admissions of unrelated owners overlap."""
    from carbon.challenge_validator import exam_cap

    def run(grouping):
        state = {"inside": 0, "max": 0}
        guard = threading.Lock()

        def evaluate(submitted):
            with guard:
                state["inside"] += 1
                state["max"] = max(state["max"], state["inside"])
            time.sleep(0.02)
            with guard:
                state["inside"] -= 1
            return {"kind": "OUTCOME"}

        exam_cap.install_grouping(grouping)
        try:
            intake = _intake(evaluate)
            threads = [
                threading.Thread(target=intake._admit, args=(SimpleNamespace(hotkey=f"5H{i % 7}"),))
                for i in range(28)
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join(20)
        finally:
            exam_cap.install_grouping(None)
        return state["max"]

    assert run(lambda hotkey: "farm") == 1  # one group: one admission at a time
    assert run(None) > 1  # seven own-hotkey groups: they overlap
