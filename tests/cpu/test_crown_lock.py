"""V2 (18 Nov 2026), replacing the door-wide `Sequencer.exclusive`: every crown decision reads the king's CURRENT
standing under `grade_sequencer.CROWN_LOCK`. A re-measure that changes the king's stored mean (same model id) while a
grade waits for the lock is what the decision then reads; nothing about the king is read before the lock."""

from __future__ import annotations

import threading
from types import SimpleNamespace

from carbon.challenge_validator import grade_sequencer, koth_journal
from carbon.challenge_validator import lean_recipe_retention as retention

TASK = "rtsk_" + "a" * 64


class _Store:
    def __init__(self):
        self.mean = 1.0

    def incumbent(self):
        return {"model_id": "king"}

    def crown_mean(self, submission_id, key):
        # the king's crown-average mean as filed now (`crown_average.screening` reads it inside the decision)
        return self.mean if submission_id == "king" else None


class _Promotion:
    def __init__(self, store, seen):
        self.store, self.seen = store, seen

    def retain_private(self, submission_id, **inputs):
        return {"evaluation_key": "sha256:" + "e" * 64}

    def consider_private(self, submission_id, key, comparator, **kwargs):
        # the king's standing as the store holds it NOW, and whether the crown lock is held by this thread
        assert "average" not in kwargs  # no king value is passed in from before the lock
        self.seen.append(
            (self.store.crown_mean("king", key), grade_sequencer.CROWN_LOCK._is_owned())
        )
        return {"outcome": "INCUMBENT_KEEPS", "reason": "test"}


def test_a_remeasure_while_a_grade_waits_for_the_crown_lock_is_what_the_decision_reads(monkeypatch):
    from carbon.challenge_validator import koth_registry

    monkeypatch.setattr(retention, "_pool_admit", lambda *a, **k: None)
    monkeypatch.setattr(retention, "_control_check", lambda *a, **k: None)
    monkeypatch.setattr(retention, "_floor_exam", lambda adapter: None)
    monkeypatch.setattr(retention, "_registry_version", lambda adapter: None)
    monkeypatch.setattr(retention, "_watch_repeat_miss", lambda *a, **k: None)
    monkeypatch.setattr(retention, "_file_if_paused", lambda *a, **k: None)
    monkeypatch.setattr(koth_registry, "comparator", lambda *a, **k: "cmp")
    monkeypatch.setattr(koth_registry, "control", lambda *a, **k: None)
    monkeypatch.setattr(koth_journal, "contention", lambda *a, **k: None)
    store, seen = _Store(), []
    promotion = _Promotion(store, seen)
    adapter = SimpleNamespace(
        challenge_id="electric-motor-magnetics",
        discovery=SimpleNamespace(
            evaluation_pack_snapshot=SimpleNamespace(read_json_role=lambda *a, **k: {}),
            evaluation_pack_public_root=None,
            evaluation_pack_sealed=True,
            evaluation_pack_digest="sha256:" + "d" * 64,
        ),
    )
    inputs = {"entry": None, "score_pack": None}
    held, go = threading.Event(), threading.Event()

    def remeasure():
        # the king's upkeep: it holds the crown lock and rewrites his mean (same model id)
        with grade_sequencer.CROWN_LOCK:
            held.set()
            go.wait(5)
            store.mean = 2.0

    upkeep = threading.Thread(target=remeasure, daemon=True)
    upkeep.start()
    assert held.wait(5)
    result = {}
    grade = threading.Thread(
        target=lambda: result.update(
            retention._contend(adapter, promotion, TASK, {}, inputs, "sha256:" + "f" * 64)
        ),
        daemon=True,
    )
    grade.start()
    grade.join(0.3)
    assert grade.is_alive() and seen == []  # the grade waits for the crown lock
    go.set()
    upkeep.join(5)
    grade.join(5)
    assert seen == [(2.0, True)]  # the decision read the new mean, holding the lock
    assert result.get("outcome") == "INCUMBENT_KEEPS"
