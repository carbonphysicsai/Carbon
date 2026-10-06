"""Rotation and retirement by finalized block (VALIDATOR-19 slice 3).

The producer schedules each batch into a slot of its Challenge's registered
cadence (battery rule v2: one batch per 1,080 blocks, three live). It
publishes ahead of each window and retires batches when their window ends.
Import-only validators activate exactly the batches whose windows cover the
newest finalized block, so two validators holding the same batches rotate at
the same blocks.

Synthetic roots, scripted solves and in-process stores only: no chain,
network, container or spend. Not a security audit (AGENTS.md §13).
"""

import hashlib
import json
import sys
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from test_challenge_validator_answer_key import battery_validator
from test_challenge_validator_producer import scripted_solve

from carbon.battery import exam
from carbon.challenge_validator import answer_key as ak
from carbon.challenge_validator import distribution as dist
from carbon.challenge_validator import producer as pr
from carbon.challenge_validator.battery import BatteryBatchSource

V2 = exam.DEVELOPMENT_RULE_V2
EVERY = V2["rotation"]["every_blocks"]
SIZE = 12


@pytest.fixture
def made(tmp_path):
    source = BatteryBatchSource(
        battery_validator(tmp_path / "producer-state"),
        overlay=tmp_path / "overlay",
        runner=scripted_solve,
    )
    key = ak.ProducerKey.create(tmp_path / "producer.key")
    producer = pr.Producer(tmp_path / "producer", [source], signing_key=key)
    # Small batches keep the scripted solves fast; the slot logic is unchanged.
    real_draw = producer.draw
    producer.draw = lambda c, role, *, kind, size=None: real_draw(
        c, role, kind=kind, size=SIZE
    )
    return {"producer": producer, "source": source, "key": key, "dir": tmp_path}


def outbox(made):
    challenge = made["source"].challenge_id
    directory = made["dir"] / "producer" / "outbox" / challenge
    return sorted(directory.glob("*.json")) if directory.exists() else []


def events(producer, kind):
    return [e for e in producer.journal.entries() if e["event"] == kind]


# -- the producer's schedule ----------------------------------------------------------------


def test_battery_rule_v2_names_its_own_cadence(made):
    assert made["source"].cadence() == {"every_blocks": EVERY, "active": 3}
    assert pr.Producer.window(made["source"].cadence(), 2) == {
        "slot": 2,
        "activate_block": 2 * EVERY,
        "retire_block": 5 * EVERY,
    }


def test_a_tick_fills_the_next_slot_ahead_of_its_window(made):
    producer, challenge = made["producer"], made["source"].challenge_id
    report = producer.tick(100)[challenge]
    assert (report["slot"], report["filled"], report["unfilled"]) == (0, [1], [])
    [path] = outbox(made)
    commitment = ak.verify(json.loads(path.read_text()), made["key"].public_key)[0]
    assert commitment["window"] == pr.Producer.window(made["source"].cadence(), 1)
    # The same block again changes nothing.
    before = producer.journal.entries()
    assert producer.tick(100)[challenge]["filled"] == []
    assert producer.journal.entries() == before


def test_a_batch_retires_when_its_window_ends_and_releases_nothing(made):
    producer, challenge = made["producer"], made["source"].challenge_id
    producer.tick(100)
    [first] = outbox(made)
    report = producer.tick(4 * EVERY)[challenge]
    assert report["retired"] == 1 and report["filled"] == [5]
    assert first.name not in [p.name for p in outbox(made)]
    retired_dir = made["dir"] / "producer" / "retired" / challenge
    assert (retired_dir / first.name).exists()
    [retired] = events(producer, "retired")
    assert retired["release"] == "HUMAN_INPUT"
    # Retired is final: it is never published again.
    with pytest.raises(pr.ProducerRefused) as refused:
        producer.publish(challenge, retired["fingerprint"])
    assert refused.value.code == "producer_retired"


def sealed(producer, challenge, role):
    drawn = producer.draw(challenge, role, kind="screening")
    producer.solve(challenge, drawn["fingerprint"])
    producer.seal(challenge, drawn["fingerprint"])
    return drawn["fingerprint"]


def test_a_slot_is_never_scheduled_late_twice_or_unsealed(made):
    producer, challenge = made["producer"], made["source"].challenge_id
    a, b = sealed(producer, challenge, "pscreen-A"), sealed(producer, challenge, "pscreen-B")
    cases = [
        ((a, 1, EVERY), "producer_slot_started"),
        ((a, 1, 0), None),
        ((b, 1, 0), "producer_slot_taken"),
        ((a, 2, 0), "producer_already_scheduled"),
        (("sha256:" + "0" * 64, 3, 0), "producer_not_sealed"),
    ]
    for (fingerprint, slot, block), code in cases:
        if code is None:
            producer.schedule(challenge, fingerprint, slot, block=block)
            continue
        with pytest.raises(pr.ProducerRefused) as refused:
            producer.schedule(challenge, fingerprint, slot, block=block)
        assert refused.value.code == code


def test_an_unscheduled_batch_is_never_published(made):
    producer, challenge = made["producer"], made["source"].challenge_id
    fingerprint = sealed(producer, challenge, "pscreen-U")
    with pytest.raises(pr.ProducerRefused) as refused:
        producer.publish(challenge, fingerprint)
    assert refused.value.code == "producer_not_scheduled"


def test_no_cadence_no_schedule(made, monkeypatch):
    producer, challenge = made["producer"], made["source"].challenge_id
    monkeypatch.setattr(made["source"], "cadence", lambda: None)
    assert producer.tick(100) == {challenge: {"cadence": None}}
    fingerprint = sealed(producer, challenge, "pscreen-N")
    with pytest.raises(pr.ProducerRefused) as refused:
        producer.schedule(challenge, fingerprint, 1, block=0)
    assert refused.value.code == "producer_no_cadence"


def test_a_challenge_needs_the_owners_approval_record(tmp_path):
    decisions = tmp_path / ".agent" / "decisions"
    decisions.mkdir(parents=True)
    body = b"## OWNER-PRODUCE-01: approved\n"
    (decisions / "d.md").write_bytes(body)
    good = {
        "record": "OWNER-PRODUCE-01",
        "file": "d.md",
        "sha256": hashlib.sha256(body).hexdigest(),
    }
    assert pr.require_approval(good, repository=tmp_path) == "OWNER-PRODUCE-01"
    for bad in (
        None,
        {**good, "sha256": "0" * 64},
        {**good, "record": "OWNER-OTHER-01"},
        {**good, "file": "../d.md"},
        {**good, "file": "missing.md"},
    ):
        with pytest.raises(pr.ProducerRefused) as refused:
            pr.require_approval(bad, repository=tmp_path)
        assert refused.value.code == "producer_challenge_not_approved"


# -- the distribution host serves only live windows ----------------------------------------


def test_a_retired_package_is_never_served(made, tmp_path):
    producer, challenge = made["producer"], made["source"].challenge_id
    producer.tick(100)
    [path] = outbox(made)
    inbox = tmp_path / "inbox"
    inbox.mkdir(mode=0o700)
    (inbox / path.name).write_text(path.read_text())
    (inbox / path.name).chmod(0o600)
    store = dist.Inbox(inbox, made["key"].public_key)
    window = pr.Producer.window(made["source"].cadence(), 1)
    assert len(store.packages(challenge, block=window["retire_block"] - 1)[0]) == 1
    assert store.packages(challenge, block=window["retire_block"])[0] == {}


# -- import-only validators rotate by the windows -------------------------------------------


def published(made, slots):
    """One published package per slot, scheduled at block 0."""
    producer, challenge = made["producer"], made["source"].challenge_id
    values = []
    for slot in slots:
        fingerprint = sealed(producer, challenge, f"pscreen-W{slot}")
        producer.schedule(challenge, fingerprint, slot, block=0)
        producer.publish(challenge, fingerprint)
        name = fingerprint.removeprefix("sha256:") + ".json"
        directory = made["dir"] / "producer" / "outbox" / challenge
        values.append(json.loads((directory / name).read_text()))
    return values


def at_block(adapter, block, n=[0]):  # noqa: B006 - a test-only counter
    """A received submission at `block`, then the rotation step."""
    n[0] += 1
    adapter.target.store.admit(
        f"s{n[0]}",
        request_digest="d",
        hotkey="5Miner",
        challenge="c",
        strategy="{}",
        binding={"receipt": {"block": block}, "attempt": 1},
    )
    adapter.target.store.rotate_if_ready()
    return adapter.target.store.pool()


def importer(made, name, values):
    adapter = battery_validator(made["dir"] / name, import_only=True)
    for value in values:
        adapter.import_answer_key(*ak.verify(value, made["key"].public_key))
    adapter.target.store.open_pool()
    return adapter


def test_import_only_validators_rotate_by_the_windows_and_agree(made):
    one, two, three = published(made, (1, 2, 4))
    fp = [ak.verify(v, made["key"].public_key)[0]["fingerprint"] for v in (one, two, three)]
    first = importer(made, "v1", [one, two, three])
    second = importer(made, "v2", [three, one, two])  # another import order
    assert first.target.store.pool()["status"] == "ROTATION_PENDING"
    expected = [
        (EVERY + 10, [fp[0]]),
        (2 * EVERY + 10, [fp[0], fp[1]]),
        (4 * EVERY + 10, [fp[1], fp[2]]),
        # No window covers it: the current batches keep scoring (never stall).
        (9 * EVERY, [fp[1], fp[2]]),
    ]
    for block, active in expected:
        assert at_block(first, block)["active"] == active
        assert at_block(second, block)["active"] == active
    store = first.target.store
    assert store.batch(fp[0])["state"] == "RETIRED"
    kinds = [e for e in store.events() if e["kind"] == "rotation_overdue"]
    assert kinds


def test_an_unwindowed_package_is_refused_by_an_import_only_validator(made):
    [value] = published(made, (1,))
    commitment, payload = ak.verify(value, made["key"].public_key)
    adapter = battery_validator(made["dir"] / "v3", import_only=True)
    with pytest.raises(ak.AnswerKeyRefused) as refused:
        adapter.import_answer_key({**commitment, "window": None}, payload)
    assert refused.value.code == "answer_key_no_window"
