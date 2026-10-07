"""The same-host import (the Test Lead's ruling, 2026-10-07): the development
pool on the producer host takes producer-published batches straight from the
producer's outbox, verified as a fetched package is. It does so from its next
rotation: an already open pool keeps scoring its own batches until a
producer window covers the newest block.

Synthetic roots and scripted solves; no chain, network or container.
"""

import json
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from test_challenge_validator_answer_key import battery_validator
from test_challenge_validator_rotation import EVERY, made  # noqa: F401 - fixture

from carbon.battery.daemon import BatteryValidator
from carbon.challenge_validator import answer_key as ak
from carbon.challenge_validator.battery import BatteryAdapter


def outbox(made):  # noqa: F811
    return made["dir"] / "producer" / "outbox" / made["source"].challenge_id


def test_the_outbox_imports_then_holds(made):  # noqa: F811
    made["producer"].tick(100)
    adapter = battery_validator(made["dir"] / "dev", import_only=True)
    key = made["key"].public_key
    first = ak.import_local(adapter, key, outbox(made))
    assert {p["state"] for p in first["packages"]} == {"IMPORTED"}
    again = ak.import_local(adapter, key, outbox(made))
    assert {p["state"] for p in again["packages"]} == {"HELD"}


def test_a_bad_package_is_refused_and_the_rest_still_import(made):  # noqa: F811
    made["producer"].tick(100)
    directory = outbox(made)
    victim = min(directory.glob("*.json"))
    value = json.loads(victim.read_text())
    value["payload"]["references"].popitem()
    victim.write_text(json.dumps(value))
    adapter = battery_validator(made["dir"] / "dev", import_only=True)
    result = ak.import_local(adapter, made["key"].public_key, directory)
    states = sorted(p["state"] for p in result["packages"])
    assert states == ["IMPORTED", "REFUSED"]
    [refused] = [p for p in result["packages"] if p["state"] == "REFUSED"]
    assert refused["code"] == "answer_key_payload_mismatch"


def test_an_outbox_others_can_read_is_refused(made):  # noqa: F811
    made["producer"].tick(100)
    outbox(made).chmod(0o755)
    adapter = battery_validator(made["dir"] / "dev", import_only=True)
    try:
        ak.import_local(adapter, made["key"].public_key, outbox(made))
    except ak.AnswerKeyRefused as refused:
        assert refused.code == "answer_key_outbox_not_owner_only"
    else:
        raise AssertionError("an open outbox was read")


def test_an_open_self_drawn_pool_switches_at_the_next_producer_window(
    made,  # noqa: F811
):
    """The development pool opened on its own batches; once it runs
    import-only, it keeps them until a producer window covers the newest
    block, then scores on the producer's batches."""
    own = battery_validator(made["dir"] / "dev")  # draws its own
    for role in ("pscreen-O1", "pscreen-O2", "pscreen-O3"):
        fp = own.target.prepare_batch(role, kind="screening", count=12)
        jobs = own.target.reference_jobs(fp)
        own.target.ingest_references(
            fp,
            [
                {
                    "case_id": j["case_id"],
                    "status": "OK",
                    "inputs": {k: v for k, v in j.items() if k != "case_id"},
                }
                for j in jobs
            ],
        )
    own.target.store.open_pool()
    mine = list(own.target.store.pool()["active"])
    # The same state, now import-only (`batch_source: "answer_key"`).
    target = own.target
    switched = BatteryValidator(
        store=target.store,
        backend=target.backend,
        root=target.root,
        journal=target.journal,
        repository=target.repository,
        require_commitment=False,
        import_only=True,
    )
    switched.lock_path, switched.readonly = target.lock_path, False
    adapter = BatteryAdapter(switched)
    made["producer"].tick(100)  # slot 1: blocks [EVERY, 4 * EVERY)
    ak.import_local(adapter, made["key"].public_key, outbox(made))

    def at(block, sid):
        switched.store.admit(
            sid,
            request_digest="d",
            hotkey="5M",
            challenge="c",
            strategy="{}",
            binding={"receipt": {"block": block}, "attempt": 1},
        )
        switched.store.rotate_if_ready()
        return switched.store.pool()["active"]

    assert at(EVERY - 10, "s1") == mine  # before the window: never stalls
    produced = at(EVERY + 10, "s2")
    assert produced and not set(produced) & set(mine)
