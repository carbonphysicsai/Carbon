"""Design release stays held until shared-answer dependencies can be proven.

These are synthetic producer-side ledgers; no solver, chain, or network runs.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from carbon.challenge_validator.answer_key import ProducerKey
from carbon.challenge_validator.bank import BankLedger, BankRefused, BankSource
from carbon.challenge_validator.batch_source import ProducerRefused
from carbon.challenge_validator.battery_bank import BANK, SLOT_ROLE, BankedBatterySource
from carbon.challenge_validator.producer import Producer

DESIGN = "design:toy"


class Cases(BankSource):
    challenge_id = "synthetic-bank"

    def draw_tranche(self, bank, role, count):
        return [
            {"case_id": f"{role}-{index}", "inputs": {"x": index}}
            for index in range(count)
        ]

    def terminal(self):
        return ("OK",)


def _fill(ledger, bank):
    drawn = ledger.draw_tranche(bank, 1)
    jobs = ledger.jobs(drawn["tranche"])
    assert (
        ledger.ingest(
            drawn["tranche"],
            [{"case_id": job["case_id"], "status": "OK"} for job in jobs],
        )
        == 0
    )
    ledger.seal(drawn["tranche"])


class ReleaseSource:
    release = BankedBatterySource.release

    def __init__(self, pool, design):
        self.ledger = pool
        self.design = SimpleNamespace(bank=DESIGN, ledger=design)
        self.rows = {}

    def _row(self, fingerprint):
        return self.rows[fingerprint]

    def _window(self, role):
        match = SLOT_ROLE.fullmatch(role)
        assert match is not None
        return 2 * int(match.group(2)) + (match.group(1) == "pfinal"), []


def _source(tmp_path):
    pool = BankLedger(tmp_path / "pool", Cases())
    design = BankLedger(tmp_path / "design", Cases())
    source = ReleaseSource(pool, design)
    source.rows = {
        "screen1": {"role": "pscreen-S1", "kind": "screening"},
        "screen2": {"role": "pscreen-S2", "kind": "screening"},
        "final1": {"role": "pfinal-S1", "kind": "finalist"},
    }
    return source


def _key(tmp_path):
    return ProducerKey.create(tmp_path / "producer.key")


def test_retired_design_question_is_revealed_but_held_from_public_train(tmp_path):
    source = _source(tmp_path)
    _fill(source.ledger, BANK)
    _fill(source.design.ledger, DESIGN)
    for slot in (1, 2):
        source.design.ledger.draw_window(DESIGN, slot, {"all": 1}, retire_at=2)
        source.ledger.draw_window(BANK, 2 * slot, {"all": 1}, retire_at=2)
    signer = _key(tmp_path)
    directory = tmp_path / "training"

    first = source.release(["screen1"], directory, signer)
    assert first["published"] == []
    assert first["design"] == {
        "revealed": 1,
        "retired": 1,
        "publishable": 0,
        "state": "NO_PUBLISHABLE_DESIGN_CASES",
    }
    assert list(directory.glob("*.json")) == []

    second = source.release(["screen1", "screen2"], directory, signer)
    assert second["design"]["revealed"] == 2
    assert second["design"]["publishable"] == 1
    assert second["design"]["state"] == "MISSING_SHARED_ANSWER_DEPENDENCY_EVIDENCE"
    assert len(second["published"]) == 1
    [path] = list(directory.glob("*.json"))
    assert json.loads(path.read_text())["manifest"]["bank"] == BANK
    with pytest.raises(BankRefused, match="bank_design_release_dependency_unverified"):
        source.design.ledger.publish(tmp_path / "design-training", signer)
    assert not (tmp_path / "design-training").exists()

    repeated = source.release(["screen1", "screen2"], directory, signer)
    assert repeated["published"] == []
    assert repeated["design"]["publishable"] == 1
    assert len(list(directory.glob("*.json"))) == 1

    # The normal producer summary carries the held-release reason and count.
    appended = []
    journal = SimpleNamespace(
        entries=lambda: [
            {
                "event": "scheduled",
                "challenge_id": Cases.challenge_id,
                "fingerprint": fingerprint,
                "window": {"retire_block": 9},
            }
            for fingerprint in ("screen1", "screen2")
        ],
        append=lambda *args, **kwargs: appended.append((args, kwargs)),
    )
    producer = SimpleNamespace(
        sources={Cases.challenge_id: source},
        journal=journal,
        signing_key=signer,
        _private_dir=lambda *parts: directory,
    )
    report = Producer._release(producer, Cases.challenge_id, 9)
    assert report["design"]["state"] == "MISSING_SHARED_ANSWER_DEPENDENCY_EVIDENCE"
    assert report["published_cases"] == 0 and appended == []


def test_missing_screening_design_window_refuses_before_pool_release(tmp_path):
    source = _source(tmp_path)
    _fill(source.ledger, BANK)
    source.ledger.draw_window(BANK, 2, {"all": 1}, retire_at=1)
    with pytest.raises(
        ProducerRefused, match="producer_design_release_linkage_missing"
    ):
        source.release(["screen1"], tmp_path / "training", _key(tmp_path))
    assert all(e["event"] != "window_revealed" for e in source.ledger.entries())
    assert not (tmp_path / "training").exists()


def test_unretired_design_question_stays_private_after_ended_window(tmp_path):
    source = _source(tmp_path)
    _fill(source.ledger, BANK)
    _fill(source.design.ledger, DESIGN)
    source.ledger.draw_window(BANK, 2, {"all": 1}, retire_at=1)
    source.design.ledger.draw_window(DESIGN, 1, {"all": 1}, retire_at=2)
    result = source.release(["screen1"], tmp_path / "training", _key(tmp_path))
    assert result["design"]["retired"] == 0
    assert result["design"]["publishable"] == 0
    assert result["design"]["state"] == "NO_PUBLISHABLE_DESIGN_CASES"
    assert len(result["published"]) == 1
    assert all(
        json.loads(path.read_text())["manifest"]["bank"] == BANK
        for path in (tmp_path / "training").glob("*.json")
    )


def test_finalist_end_has_no_design_window_to_reveal(tmp_path):
    source = _source(tmp_path)
    _fill(source.ledger, BANK)
    source.ledger.draw_window(BANK, 3, {"all": 1}, retire_at=1)
    result = source.release(["final1"], tmp_path / "training", _key(tmp_path))
    assert result["design"] == {
        "revealed": 0,
        "retired": 0,
        "publishable": 0,
        "state": "NO_PUBLISHABLE_DESIGN_CASES",
    }
    assert len(result["published"]) == 1
