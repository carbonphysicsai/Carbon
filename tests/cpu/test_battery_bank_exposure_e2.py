"""Rule `v2-bank-e2` (OWNER-BANK-EXPOSURE-E2-01): the pool bank's E = 2.

A new rule version: `v2-bank` is unchanged (its deployments' seed pins bind
its digest), and nothing but the pool's exposure differs.
"""

from __future__ import annotations

from carbon.battery import exam
from carbon.battery.daemon import rule_digest


def test_only_the_pool_exposure_differs():
    e2, v2_bank = exam.RULES["v2-bank-e2"], exam.RULES["v2-bank"]
    assert e2["bank"]["pool"]["retire_at"] == 2
    assert v2_bank["bank"]["pool"]["retire_at"] == 5
    rest = dict(e2, authority=None, bank=None)
    assert rest == dict(v2_bank, authority=None, bank=None)
    assert {k: v for k, v in e2["bank"]["pool"].items() if k != "retire_at"} == {
        k: v for k, v in v2_bank["bank"]["pool"].items() if k != "retire_at"
    }
    assert "OWNER-BANK-EXPOSURE-E2-01" in e2["authority"]


def test_it_is_its_own_rule_and_discloses_as_v2():
    assert rule_digest(exam.RULES["v2-bank-e2"]) != rule_digest(exam.RULES["v2-bank"])
    assert exam.disclosure(exam.RULES["v2-bank-e2"]) == exam.disclosure(
        exam.RULES["v2-bank"]
    )
