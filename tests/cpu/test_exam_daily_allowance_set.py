"""Owner G18 (19 Nov 2026, "10 now"): the registry's ``daily_allowance`` sets ``a`` directly, per allowance group per
Challenge per rolling day; the one-per-epoch limit is unchanged. Real `AttemptLedger` and `ExamCap`.
"""

from __future__ import annotations

import json

import pytest

from carbon.challenge_validator import exam_cap
from carbon.challenge_validator.exam_cap import ExamCap, ExamCapRefused
from carbon.challenge_validator.ledger import AttemptLedger

CHALLENGE, VERSION, EXAM = "electric-motor-magnetics", "1.8", "sha256:" + "1" * 64
BLOCK = 10_000
EPOCH = exam_cap.EPOCH_BLOCKS


def _cadence(**extra):
    # a capacity whose formula alone would allow 1000 a day
    return {
        "capacity_gpu_lane_hours_per_day": 1000.0,
        "rebuild_gpu_lane_hours": {CHALLENGE: 1.0},
        "lanes": 1,
        "measurement_digest": "sha256:" + "a" * 64,
        "class_record_digest": "sha256:" + "b" * 64,
        **extra,
    }


def _cap(tmp_path, cadence):
    (tmp_path / "ledger").mkdir(mode=0o700)
    return ExamCap(
        AttemptLedger(tmp_path / "ledger" / "attempts.sqlite3"), cadence=cadence
    )


_N = iter(range(10_000))


def _sid():
    return f"rtsk_{next(_N):064x}"


def _grade(cap, block, hotkey="hk1"):
    row = cap.reserve(
        hotkey=hotkey,
        challenge_id=CHALLENGE,
        challenge_version=VERSION,
        exam_key=EXAM,
        submission_id=_sid(),
        block=block,
    )
    cap.settle(row, "SCORED_DEVELOPMENT_CANDIDATE")


def _admission(cap, block, hotkey="hk1"):
    return cap.admission_refusal(
        hotkey=hotkey,
        challenge_id=CHALLENGE,
        challenge_version=VERSION,
        exam_key=EXAM,
        submission_id=_sid(),
        block=block,
    )


def test_the_committed_registry_sets_ten():
    cadence = exam_cap.registered_cadence()
    assert cadence["daily_allowance"] == 10


def test_ten_a_day_are_admitted_and_the_eleventh_is_refused(tmp_path):
    cap = _cap(tmp_path, _cadence(daily_allowance=10))
    # ten graded exams, one per round, inside one rolling day (20 rounds)
    for index in range(10):
        block = BLOCK + index * EPOCH
        assert _admission(cap, block) is None
        _grade(cap, block)
    eleventh = BLOCK + 10 * EPOCH
    assert cap.allowance(hotkey="hk1", block=eleventh)["allowance"] == 10
    told = _admission(cap, eleventh)
    assert told is not None and told["code"] == "exam_daily_allowance_reached"
    with pytest.raises(ExamCapRefused) as refused:
        _grade(cap, eleventh)
    assert refused.value.code == "exam_daily_allowance_reached"
    # another hotkey (its own group, no grouping installed) still has its ten
    assert _admission(cap, eleventh, hotkey="hk2") is None
    # a day after the first, its slot is free again
    assert _admission(cap, BLOCK + exam_cap.DAY_BLOCKS) is None


def test_the_epoch_limit_is_unchanged(tmp_path):
    cap = _cap(tmp_path, _cadence(daily_allowance=10))
    _grade(cap, BLOCK)
    assert _admission(cap, BLOCK)["code"] == "epoch_limit_reached"


def test_without_the_key_the_formula_stands(tmp_path):
    cap = _cap(tmp_path, _cadence())
    assert cap.allowance(hotkey="hk1", block=BLOCK)["allowance"] == 1000


@pytest.mark.parametrize("bad", [0, -1, True, 1.5, "10", None])
def test_a_malformed_value_refuses(tmp_path, bad):
    document = {
        "schema": exam_cap.REGISTRY_SCHEMA,
        "source": "test",
        **_cadence(daily_allowance=bad),
    }
    path = tmp_path / "exam_cadence.json"
    path.write_text(json.dumps(document))
    with pytest.raises(ExamCapRefused) as refused:
        exam_cap.registered_cadence(path)
    assert refused.value.code == "exam_cadence_unregistered"


def test_an_unknown_key_still_refuses(tmp_path):
    document = {
        "schema": exam_cap.REGISTRY_SCHEMA,
        "source": "test",
        **_cadence(allowance=10),
    }
    path = tmp_path / "exam_cadence.json"
    path.write_text(json.dumps(document))
    with pytest.raises(ExamCapRefused):
        exam_cap.registered_cadence(path)
