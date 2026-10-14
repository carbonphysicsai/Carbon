"""Synthetic shared imports; partial persistence never becomes HELD."""

import pytest
from test_challenge_validator_answer_key import battery_validator
from test_challenge_validator_answer_key import published as shared_fixture

from carbon.challenge_validator import answer_key, bank_proof


@pytest.fixture
def published(tmp_path):
    return shared_fixture.__wrapped__(tmp_path)


def test_interruption_before_salt_is_unheld_and_retry_preserves_reference_identity(
    tmp_path, published, monkeypatch
):
    adapter = battery_validator(tmp_path / "fresh-validator", import_only=True)
    commitment, payload = answer_key.verify(
        published["value"], published["key"].public_key
    )
    store = adapter.target.store
    original = store.set_salt

    def interrupted(*args):
        raise RuntimeError("synthetic-interruption")

    monkeypatch.setattr(store, "set_salt", interrupted)
    with pytest.raises(RuntimeError, match="synthetic-interruption"):
        adapter.import_answer_key(commitment, payload)
    fingerprint = commitment["fingerprint"]
    before = store.batch(fingerprint)
    window = store.window(fingerprint)
    journal = adapter.target.journal.path.read_bytes()
    assert before["references_state"] == "COMPLETE"
    assert store.salts([fingerprint]) == []
    assert not adapter.holds_answer_key(commitment)
    monkeypatch.setattr(store, "set_salt", original)
    adapter.import_answer_key(commitment, payload)
    assert adapter.holds_answer_key(commitment)
    assert store.salts([fingerprint]) == [payload["reconstruction_salt"]]
    assert store.batch(fingerprint)["references_digest"] == before["references_digest"]
    assert store.window(fingerprint) == window
    assert adapter.target.journal.path.read_bytes() == journal
    assert adapter.target.store.pool() is None  # Init/open remains explicit.


def test_required_design_is_not_held_until_same_complete_selection_is_persisted(
    tmp_path, published
):
    adapter = battery_validator(tmp_path / "fresh-validator", import_only=True)
    commitment, payload = answer_key.verify(
        published["value"], published["key"].public_key
    )
    adapter.import_answer_key(commitment, payload)
    fingerprint = commitment["fingerprint"]
    questions = {
        "fixture-q1": {"task": "public-fixture"},
        "fixture-q2": {"task": "public-fixture"},
    }
    bound = {
        **commitment,
        "design": {
            "bank": "public-fixture-bank",
            "k": 2,
            "selection_digest": bank_proof.selection_digest(sorted(questions)),
            "tranches": [],
        },
    }
    assert not adapter.holds_answer_key(bound)
    adapter.target.store.set_design(fingerprint, "public-fixture-bank", questions)
    assert adapter.holds_answer_key(bound)
    changed = {
        **bound,
        "design": {**bound["design"], "selection_digest": "sha256:" + "0" * 64},
    }
    assert not adapter.holds_answer_key(changed)
