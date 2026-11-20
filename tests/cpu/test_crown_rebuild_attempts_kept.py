"""Crown rebuild attempts a decision did not use are kept as private data (data harvest plan G6, Lead 20 Nov 2026):
a busy host's (``contended``), an infrastructure failure, a grade that is not a measurement, a disagreeing host-fault
repeat. No decision reads them; every outcome is the same as without them."""

from __future__ import annotations

import pytest

from carbon.battery.pool_store import PoolStore
from carbon.challenge_validator import bank_promotion as bp
from carbon.challenge_validator import crown_average as ca
from carbon.challenge_validator.interface import digest

KEY = digest("evaluation-key")


def _grade(total, status=bp.SCORED):
    return {"evidence": {"model_p": {"score_status": status, "total_score": total}}}


class _Kept:
    def __init__(self):
        self.rows = []

    def __call__(self, seed, again, reason, body):
        self.rows.append((seed, again, reason, body))


def test_a_contended_try_and_an_unmeasured_grade_are_kept_and_the_measurement_still_wins():
    tries = [
        ca.RebuildInfra(ca.REBUILD_HOST_CONTENDED),
        _grade(None, bp.FAILED_INFRA),
        _grade(0.7),
    ]

    def rebuild(seed):
        step = tries.pop(0)
        if isinstance(step, Exception):
            raise step
        return step

    kept = _Kept()
    status, total, _body = ca._one(rebuild, 5, 2, kept)
    assert (status, total) == (bp.SCORED, 0.7)
    assert kept.rows == [
        (5, False, ca.REBUILD_HOST_CONTENDED, None),
        (5, False, bp.FAILED_INFRA, _grade(None, bp.FAILED_INFRA)),
    ]


def test_without_a_keep_every_outcome_is_unchanged():
    def rebuild(seed):
        raise ca.RebuildInfra(ca.REBUILD_HOST_CONTENDED)

    with pytest.raises(ca.RebuildInfra) as raised:
        ca._one(rebuild, 5, 2)
    assert str(raised.value) == ca.REBUILD_HOST_CONTENDED


def test_a_keep_that_fails_never_changes_or_stops_a_decision():
    class Broken:
        def record_crown_rebuild_attempt(self, *args, **kwargs):
            raise OSError("disk")

    keep = ca._kept_attempts(Broken(), "sub-1", KEY)
    keep(5, False, ca.REBUILD_HOST_CONTENDED, None)  # no raise
    assert ca._kept_attempts(object(), "sub-1", KEY) is None
    assert ca._kept_attempts(Broken(), "sub-1", "not-a-digest") is None


def test_the_pool_store_keeps_every_attempt_as_its_own_private_row(tmp_path):
    store = PoolStore(tmp_path / "private.sqlite", clock=lambda: 123.0)
    keep = ca._kept_attempts(store, "sub-1", KEY)
    keep(5, False, ca.REBUILD_HOST_CONTENDED, None)
    keep(5, False, ca.REBUILD_HOST_CONTENDED, None)
    keep(9, True, bp.REPEAT_MISMATCH, _grade(0.71))
    rows = store.crown_rebuild_attempts("sub-1")
    assert [(r["seed"], r["again"], r["reason"], r["contended"]) for r in rows] == [
        (5, False, ca.REBUILD_HOST_CONTENDED, True),
        (5, False, ca.REBUILD_HOST_CONTENDED, True),
        (9, True, bp.REPEAT_MISMATCH, False),
    ]
    assert rows[2]["body"] == _grade(0.71)
    assert store.crown_rebuild_attempts("other") == []
    # the decision cache never sees them
    assert store.crown_rebuild_cached("sub-1", KEY, 5, False) is None
