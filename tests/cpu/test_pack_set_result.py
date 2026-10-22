"""The set-level grade (OWNER-FULL-EXAM-BANK-01 item 3; the Validator's five
conditions): the set result equals `aggregate` of its batch records; a missing or
infrastructure batch gives no set result; KOTH and the Ladder read only the set;
the epoch counter increments once; a rotation is never compared across keys."""

from __future__ import annotations

import pytest

from carbon.challenge_validator import exam_cap
from carbon.challenge_validator import pack_set_result as psr
from carbon.challenge_validator import sealed_exam_common as common
from carbon.challenge_validator.ledger import AttemptLedger
from carbon.scoring import grade_feedback as gf

CHALLENGE = ("electric-motor-magnetics", "1.0")
HOTKEY = "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"
GATES = ("native_motor_valid", "complete_fixed_coverage")


def _digest(c):
    return "sha256:" + c * 64


BATCHES = [_digest("a"), _digest("b")]
SET_KEY = common.pack_set_key(common.pack_set_document(*CHALLENGE, BATCHES))


@pytest.fixture
def world(tmp_path):
    directory = tmp_path / "ledger"
    directory.mkdir(mode=0o700)
    ledger = AttemptLedger(directory / "attempts.sqlite3")
    return exam_cap.ExamCap(ledger), psr.SetResultStore(ledger)


def _scored(a, d, ok=True):
    return {
        "status": psr.SCORED if ok else psr.GATE_FAILED,
        "score": 0.5 * a + 0.5 * d,
        "legs": {"A": a, "D": d},
        "gates": {name: ("PASS" if ok else "FAIL") for name in GATES},
    }


def _grade(world, graded, *, submission="rtsk_1", block=360, batches=BATCHES):
    cap, store = world
    return psr.grade_set(
        cap,
        store,
        hotkey=HOTKEY,
        challenge_id=CHALLENGE[0],
        challenge_version=CHALLENGE[1],
        set_key=SET_KEY,
        batches=batches,
        submission_id=submission,
        block=block,
        grade_batch=lambda digest: graded[digest],
    )


def _count(world):
    cap, _ = world
    return cap.count(hotkey=HOTKEY, challenge_id=CHALLENGE[0], exam_key=SET_KEY)


def test_the_set_result_equals_the_aggregate_of_its_batch_records(world):
    graded = {BATCHES[0]: _scored(0.8, 0.4), BATCHES[1]: _scored(0.6, 0.2)}
    result = _grade(world, graded)
    expected = common.aggregate(
        [
            {"gates": {g: True for g in GATES}, "A": 0.8, "D": 0.4},
            {"gates": {g: True for g in GATES}, "A": 0.6, "D": 0.2},
        ]
    )
    assert result["status"] == psr.SCORED and result["eligible"] is True
    assert result["graded"]["score"] == pytest.approx(expected["total"])
    assert result["graded"]["legs"] == {
        "A": pytest.approx(expected["A"]),
        "D": pytest.approx(expected["D"]),
    }
    assert result["batches"] == 2 and result["set_key"] == SET_KEY
    assert world[1].result(SET_KEY, "rtsk_1") == result


def test_a_missing_or_infrastructure_batch_gives_no_set_result(world):
    for n, bad in enumerate(
        (
            {"status": "FAILED_INFRA"},
            {"status": "INDETERMINATE_EVIDENCE"},
            {"status": psr.UNAVAILABLE},
            {"not": "a graded row"},
            _scored(0.6, 0.2) | {"legs": {"A": float("nan"), "D": 0.2}},
        ),
        start=1,
    ):
        graded = {BATCHES[0]: _scored(0.8, 0.4), BATCHES[1]: bad}
        result = _grade(world, graded, submission=f"rtsk_{n}", block=360 * n)
        assert result["state"] == psr.UNAVAILABLE and "reason" in result
        assert world[1].result(SET_KEY, f"rtsk_{n}") is None
    # The slot was returned each time: nothing counts against the epoch.
    assert _count(world) == 0


def test_a_batch_that_raises_is_typed_infrastructure_with_no_partial_mean(world):
    cap, store = world

    def grade_batch(digest):
        if digest == BATCHES[1]:
            raise RuntimeError("worker lost")
        return _scored(0.8, 0.4)

    result = psr.grade_set(
        cap,
        store,
        hotkey=HOTKEY,
        challenge_id=CHALLENGE[0],
        challenge_version=CHALLENGE[1],
        set_key=SET_KEY,
        batches=BATCHES,
        submission_id="rtsk_1",
        block=360,
        grade_batch=grade_batch,
    )
    assert result == {"state": psr.UNAVAILABLE, "reason": "set_batch_unavailable"}
    assert store.result(SET_KEY, "rtsk_1") is None
    assert _count(world) == 0
    # A retry after the infrastructure recovers grades the whole set.
    graded = {BATCHES[0]: _scored(0.8, 0.4), BATCHES[1]: _scored(0.6, 0.2)}
    assert _grade(world, graded)["status"] == psr.SCORED


def test_a_gate_failure_on_any_batch_makes_the_set_ineligible(world):
    graded = {BATCHES[0]: _scored(0.8, 0.4), BATCHES[1]: _scored(0.9, 0.9, ok=False)}
    result = _grade(world, graded)
    assert result["status"] == psr.GATE_FAILED and result["eligible"] is False
    assert result["graded"]["score"] is None
    assert set(result["graded"]["gates"].values()) == {"FAIL"} or "FAIL" in set(
        result["graded"]["gates"].values()
    )
    # A graded outcome spends the slot, once.
    assert _count(world) == 1


def test_the_epoch_counter_increments_once_for_n_batches(world):
    graded = {BATCHES[0]: _scored(0.8, 0.4), BATCHES[1]: _scored(0.6, 0.2)}
    _grade(world, graded)
    assert _count(world) == 1
    # A repeat of the same submission reuses its row: still one.
    _grade(world, graded)
    assert _count(world) == 1
    # A second submission is a second graded submission.
    _grade(world, graded, submission="rtsk_2", block=720)
    assert _count(world) == 2


def test_the_ladder_and_koth_read_only_the_set_result(world):
    graded = {BATCHES[0]: _scored(0.9, 0.7), BATCHES[1]: _scored(0.5, 0.3)}
    result = _grade(world, graded)
    # The Ladder's input is the set-level row; the document shows its total only.
    shown = gf.ladder_feedback(
        result["graded"],
        best=None,
        exam_version="motor-dual-sealed-batch-30-v1",
        gate_registry=GATES,
        rebuild_noise=None,
    )
    # A = mean(0.9, 0.5) = 0.7, D = mean(0.7, 0.3) = 0.5, total 0.6.
    assert shown["total"] == pytest.approx(0.6)
    assert set(shown) == gf.FIELDS
    # The per-batch rows exist for the operator only and are not in the set result.
    rows = world[1].batch_rows(SET_KEY, "rtsk_1")
    assert sorted(rows) == sorted(BATCHES)
    assert "graded" in result and "batches" in result
    assert not any(key in result for key in BATCHES)
    assert result["graded"]["score"] != rows[BATCHES[0]]["score"]
    assert result["graded"]["score"] != rows[BATCHES[1]]["score"]


def test_only_the_same_set_key_is_comparable(world):
    rotated = common.pack_set_key(
        common.pack_set_document(*CHALLENGE, [BATCHES[0], _digest("c")])
    )
    assert psr.comparable(SET_KEY, SET_KEY)
    assert not psr.comparable(SET_KEY, rotated)
    assert not psr.comparable(SET_KEY, None)
    assert not psr.comparable("", "")


def test_a_set_without_batches_is_refused(world):
    with pytest.raises(psr.SetResultRefused):
        _grade(world, {}, batches=[])
