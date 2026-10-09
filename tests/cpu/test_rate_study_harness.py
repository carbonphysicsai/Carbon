"""SUBMISSION-RATE-STUDY-01's harness, slice A (VALIDATOR-30).

The rate rule variants; the study bank drawn down without top-up; the fresh
sets as their own never-window-drawable bank; and the non-consuming fresh
scorer, which scores every model on the same sealed set once each.

Synthetic roots and scripted solves only: no container, chain, network or
spend. Not a security audit (AGENTS.md §13).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from test_challenge_validator_design_windows import adapter
from test_challenge_validator_producer import scripted_solve

from carbon.battery import exam
from carbon.battery.daemon import rule_digest
from carbon.challenge_validator import rate_study
from carbon.challenge_validator.bank import BankRefused
from carbon.challenge_validator.batch_source import ProducerRefused
from carbon.challenge_validator.battery_bank import BankedBatterySource

RATES = {"v2-bank-rate-1": 360, "v2-bank-rate-2": 180, "v2-bank-rate-4": 90}


def test_the_rate_variants_differ_only_as_the_study_needs():
    base = exam.RULES["v2-bank"]
    digests = {rule_digest(base)}
    for name, window in RATES.items():
        rule = exam.RULES[name]
        assert rule["per_hotkey"]["window_blocks"] == window
        assert rule["study"] == "SUBMISSION-RATE-STUDY-01"
        assert rule["bank"]["pool"]["size"] == 3000
        assert rule["bank"]["pool"]["top_up"] is False
        assert rule["bank"]["pool"]["retire_at"] == 5
        assert exam.disclosure(rule) == exam.disclosure(base)
        digests.add(rule_digest(rule))
    assert len(digests) == 4  # each its own, and none is v2-bank's


def small(rule):
    """A rate rule with a tiny pool, for the test's scripted bank."""
    pool = {**rule["bank"]["pool"], "size": 8, "window_cases": 4}
    return {**rule, "bank": {**rule["bank"], "pool": pool}}


@pytest.fixture
def study(tmp_path):
    rule = small(exam.RULES["v2-bank-rate-1"])
    return BankedBatterySource(
        adapter(tmp_path / "producer-state", rule=rule),
        tmp_path / "bank",
        overlay=tmp_path / "overlay",
        repository=REPOSITORY,
        runner=scripted_solve,
    )


def test_the_study_bank_is_drawn_down_and_never_topped_up(study):
    study.top_up()  # the operator's fill
    drawn = []
    with pytest.raises(ProducerRefused) as refused:
        for slot in range(1, 10):
            drawn.append(study.draw(f"pscreen-S{slot}", kind="screening"))
    assert refused.value.code == "producer_bank_short"
    assert drawn  # some windows drew before the bank ran short
    assert len(study.ledger.tranches("pool")) == 1  # no tranche was added


def test_fresh_sets_are_their_own_bank_and_never_window_drawable(study):
    sealed = study.fresh_fill(2, 5)
    assert [s["tranche"] for s in sealed] == ["bank-fresh-T1", "bank-fresh-T2"]
    assert study.fresh_fill(2, 5) == []  # resumable: nothing to do
    with pytest.raises(BankRefused) as refused:
        study.ledger.draw_window("fresh", 1, {"all": 2}, retire_at=5)
    assert refused.value.code == "bank_not_window_drawable"


def test_a_production_rule_has_no_fresh_sets(tmp_path):
    source = BankedBatterySource(
        adapter(tmp_path / "state", rule=exam.RULES["v2-bank"]),
        tmp_path / "bank",
        repository=REPOSITORY,
        runner=scripted_solve,
    )
    with pytest.raises(ProducerRefused) as refused:
        source.fresh_fill(1, 5)
    assert refused.value.code == "producer_fresh_not_a_study"


def test_the_fresh_scorer_is_non_consuming_and_scores_each_model_once(
    study, tmp_path, monkeypatch
):
    study.fresh_fill(1, 6)
    target = study.adapter.target
    calls = []

    def predict(sid, inputs, tag, namespace=None):
        calls.append((sid, namespace))
        _ids, _inputs, refs = rate_study.fresh_set(study.ledger, 1)
        return {c: refs[c].get("outputs") for c in inputs}

    monkeypatch.setattr(target, "_quiz_predictions", predict)
    state = tmp_path / "run"
    state.mkdir(mode=0o700)
    first = rate_study.fresh_score(target, study.ledger, "s1", 1, state)
    again = rate_study.fresh_score(target, study.ledger, "s1", 1, state)
    other = rate_study.fresh_score(target, study.ledger, "s2", 1, state)
    assert first["state"] == "SCORED" and again == first
    assert other["state"] == "SCORED"  # the same set, never consumed
    assert calls == [("s1", "fresh/"), ("s2", "fresh/")]
    with pytest.raises(rate_study.StudyRefused) as refused:
        rate_study.fresh_score(target, study.ledger, "s1", 2, state)
    assert refused.value.code == "study_fresh_set_not_sealed"
