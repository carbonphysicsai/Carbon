"""Explicit retry preserves the existing neutral screening/result boundary."""

from carbon.challenge_validator import Adapters, AttemptLedger, Validator
from tests.cpu.test_challenge_validator_contract import Fake, sub


class RetryFake(Fake):
    def __init__(self):
        super().__init__()
        self.retry_seen = []
        self.retry_result = None

    def retry(self, admitted, predecessor):
        self.retry_seen.append((admitted, predecessor))
        return self.outcome("sub-1") if self.retry_result is None else self.retry_result


def _door(tmp_path, adapter):
    tmp_path.chmod(0o700)
    ledger = AttemptLedger(tmp_path / "attempts.sqlite3")
    return Validator(Adapters([adapter]), ledger)


def test_explicit_retry_keeps_normal_screening_owner_and_result_envelope(tmp_path):
    adapter = RetryFake()
    door = _door(tmp_path, adapter)
    original = door.evaluate(sub())
    predecessor = "rtsk_" + "a" * 64
    retried = door.evaluate(sub(), retry_of=predecessor)
    assert retried == original
    assert len(adapter.seen) == 1
    admitted, seen_predecessor = adapter.retry_seen[0]
    assert admitted.hotkey == "hk-owner"
    assert admitted.receipt == sub().receipt
    assert seen_predecessor == predecessor
    assert retried["qualification"] is False
    assert retried["reward"] is False


def test_retry_cannot_bypass_strict_strategy_screening(tmp_path):
    adapter = RetryFake()
    result = _door(tmp_path, adapter).evaluate(
        sub('{"duplicate": 1, "duplicate": 2}'), retry_of="rtsk_" + "a" * 64
    )
    assert result["kind"] == "REFUSED"
    assert result["code"] == "duplicate_key"
    assert adapter.retry_seen == []
    assert adapter.seen == []


def test_adapter_without_retry_never_falls_back_to_another_evaluation(tmp_path):
    adapter = Fake()
    result = _door(tmp_path, adapter).evaluate(sub(), retry_of="rtsk_" + "a" * 64)
    assert result["kind"] == "UNAVAILABLE"
    assert result["code"] == "construction_retry_unavailable"
    assert adapter.seen == []


def test_retry_outcome_remains_subject_to_neutral_contract_checks(tmp_path):
    adapter = RetryFake()
    adapter.retry_result = {"private_worker_text": "must never escape"}
    result = _door(tmp_path, adapter).evaluate(sub(), retry_of="rtsk_" + "a" * 64)
    assert result["kind"] == "FAILED_INFRA"
    assert result["code"] == "outcome_contract_violation"
    assert "must never escape" not in str(result)
    assert adapter.seen == []
