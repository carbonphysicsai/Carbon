"""Finalist batches through the shared answer key (VALIDATOR-19; the dress
rehearsal, OWNER-REHEARSAL-AND-RELEASE-01).

Each producer slot carries one finalist batch beside its screening batch,
under the same signed window. Import-only validators claim a final's
finalist set by producer window, never by their own import order, so every
validator judges the same final on the same fresh cases.

Synthetic roots and scripted solves; no chain, network, container or spend.
"""

import json
import sys
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from test_challenge_validator_answer_key import battery_validator
from test_challenge_validator_rotation import (  # noqa: F401 - fixture
    EVERY,
    made,
)

from carbon.challenge_validator import answer_key as ak
from carbon.challenge_validator.batch_source import ProducerRefused


def packages(made, kind):  # noqa: F811
    challenge = made["source"].challenge_id
    directory = made["dir"] / "producer" / "outbox" / challenge
    out = []
    for path in sorted(directory.glob("*.json")):
        value = json.loads(path.read_text())
        if ak.verify(value, made["key"].public_key)[0]["kind"] == kind:
            out.append(value)
    return out


def test_a_tick_fills_each_slot_with_a_finalist_batch_too(made):  # noqa: F811
    producer, challenge = made["producer"], made["source"].challenge_id
    report = producer.tick(100)[challenge]
    assert report["filled"] == [1]
    assert report["finalist"] == {"filled": [1], "unfilled": []}
    [screening] = packages(made, "screening")
    [finalist] = packages(made, "finalist")
    window = lambda v: ak.verify(v, made["key"].public_key)[0]["window"]
    assert window(screening) == window(finalist)
    # The same block again changes nothing.
    before = producer.journal.entries()
    producer.tick(100)
    assert producer.journal.entries() == before


def test_validators_claim_the_same_finalist_set_whatever_their_import_order(
    made,  # noqa: F811
):
    producer = made["producer"]
    producer.tick(100)
    producer.tick(EVERY + 100)
    values = packages(made, "screening") + packages(made, "finalist")
    claims = []
    for name, order in (("a", values), ("b", values[::-1])):
        adapter = battery_validator(made["dir"] / name, import_only=True)
        for value in order:
            adapter.import_answer_key(*ak.verify(value, made["key"].public_key))
        store = adapter.target.store
        store.open_pool()
        store.admit(
            "s1",
            request_digest="d",
            hotkey="5Miner",
            challenge="c",
            strategy="{}",
            binding={"receipt": {"block": 2 * EVERY + 5}, "attempt": 1},
        )
        store.freeze_final("f1", challenger="s1", incumbent="s0", frozen={"x": 1})
        claims.append(store.claim_finalist_set("f1"))
    assert claims[0] is not None and claims[0] == claims[1]
    # The earliest live window's set: slot 1's, before slot 2's. Packages are
    # named by fingerprint (random roots), so slot 1's is found by its window,
    # never by file order.
    commitments = [
        ak.verify(value, made["key"].public_key)[0]
        for value in packages(made, "finalist")
    ]
    [first] = [c for c in commitments if c["window"]["slot"] == 1]
    assert claims[0] == first["fingerprint"]


def test_a_publish_that_failed_after_its_schedule_is_retried(
    made, monkeypatch  # noqa: F811
):
    """3a at r3: the first tick scheduled a slot's screening batch, then its
    publish failed (the outbox was 0755). Every later tick skipped the taken
    slot, so validators never received the batch, and an import-only pool
    stayed ROTATION_PENDING. A tick now republishes it."""
    producer, challenge = made["producer"], made["source"].challenge_id
    real = producer.publish

    def fail_once(challenge_id, fingerprint):
        monkeypatch.setattr(producer, "publish", real)
        raise ProducerRefused("producer_dir_not_owner_only")

    monkeypatch.setattr(producer, "publish", fail_once)
    with pytest.raises(ProducerRefused):
        producer.tick(100)
    assert packages(made, "screening") == []
    report = producer.tick(100)[challenge]
    assert report["republished"] == [{"slot": 1, "kind": "screening"}]
    assert report["finalist"] == {"filled": [1], "unfilled": []}
    assert len(packages(made, "screening")) == len(packages(made, "finalist")) == 1
    # Nothing left to republish: the same block again changes nothing.
    before = producer.journal.entries()
    assert "republished" not in producer.tick(100)[challenge]
    assert producer.journal.entries() == before
