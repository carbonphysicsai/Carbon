"""A registered schema-v2 exam cadence for fixtures (the committed registry carries no values until the recal).

Fixture numbers, not measurements: tests that grade through an ExamCap register this so the cap does not fail closed
with exam_cadence_unregistered (that refusal has its own tests in test_exam_cap.py).
"""

from __future__ import annotations

from carbon.challenge_validator import exam_cap


def cadence_v2(capacity=270.0, challenges=None):
    names = tuple(challenges) if challenges else exam_cap.registered_challenges()
    return {
        "capacity_gpu_lane_hours_per_day": capacity,
        "rebuild_gpu_lane_hours": dict.fromkeys(names, 1.0),
        "lanes": 1,
        "measurement_digest": "sha256:" + "a" * 64,
        "class_record_digest": "sha256:" + "b" * 64,
    }
