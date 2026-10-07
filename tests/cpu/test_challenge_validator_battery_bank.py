"""Battery windows drawn from the bank, end to end (VALIDATOR-23 slice 2;
OWNER-BANK-ARCHITECTURE-01).

A producer under rule `v2-bank` fills its pool bank with a scripted truth
solve, ticks, and publishes banked windows. An import-only validator under
the same rule verifies every drawn case's Merkle proof before it imports.
There is no container, chain, network or spend. Not a security audit
(AGENTS.md §13).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from carbon.battery import exam, seeds, worker
from carbon.battery.daemon import BatteryValidator, rule_digest
from carbon.battery.pool_store import PoolStore
from carbon.challenge_validator import answer_key as ak
from carbon.challenge_validator import bank_proof
from carbon.challenge_validator import producer as pr
from carbon.challenge_validator.battery import BatteryAdapter
from carbon.challenge_validator.battery_bank import BankedBatterySource

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from test_challenge_validator_producer import scripted_solve

RULE = exam.DEVELOPMENT_RULE_V2_BANK
POOL = RULE["bank"]["pool"]


def adapter(directory, *, import_only=False):
    directory.mkdir(mode=0o700)
    root = seeds.PrivateRoot.create(directory / "root.bin")
    journal = seeds.SeedJournal(directory / "journal.jsonl")
    journal.commit_root(root, seeds.seed_pin("sha256:" + "0" * 64, rule_digest(RULE)))
    target = BatteryValidator(
        store=PoolStore(directory / "state.sqlite3", rule=RULE),
        backend=worker.DirectBackend(REPOSITORY),
        root=root,
        journal=journal,
        repository=REPOSITORY,
        require_commitment=False,
        import_only=import_only,
        allow_published_cases=not import_only,
    )
    target.start()
    target.lock_path = str(directory / "state.sqlite3.lock")
    target.readonly = False
    return BatteryAdapter(target)


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    """One producer, from an empty bank, ticked at block 0: slot 1's
    screening and finalist windows sealed and published."""
    tmp = tmp_path_factory.mktemp("bank")
    source = BankedBatterySource(
        adapter(tmp / "producer-state"),
        tmp / "bank",
        overlay=tmp / "overlay",
        repository=REPOSITORY,
        runner=scripted_solve,
    )
    key = ak.ProducerKey.create(tmp / "producer.key")
    producer = pr.Producer(tmp / "producer", [source], signing_key=key)
    report = producer.tick(0)[source.challenge_id]
    outbox = tmp / "producer" / "outbox" / source.challenge_id
    packages = {p.name: ak.read_private(p) for p in sorted(outbox.glob("*.json"))}
    return {
        "tmp": tmp,
        "source": source,
        "key": key,
        "report": report,
        "packages": packages,
        "outbox": outbox,
    }


def test_an_empty_bank_is_filled_then_both_windows_draw_from_it(run):
    assert run["report"]["filled"] == [1]
    assert run["report"]["finalist"]["filled"] == [1]
    status = run["source"].ledger.status()["pool"]
    assert status["live"] + status["pending"] == POOL["size"]
    assert status["windows"] == 2
    assert status["exposures"] == {
        "0": POOL["size"] - 2 * POOL["window_cases"],
        "1": 2 * POOL["window_cases"],
    }


def test_windows_are_disjoint_and_carry_the_rule_duplicates(run):
    seen = []
    for value in run["packages"].values():
        commitment = value["manifest"]["commitment"]
        document = value["payload"]["document"]
        drawn = sorted(set(value["payload"]["references"]))
        assert len(drawn) == POOL["window_cases"]
        assert len(document["duplicates"]) == POOL["hidden_duplicates"]
        assert commitment["bank"]["selection_digest"] == bank_proof.selection_digest(
            drawn
        )
        assert commitment["bank"]["rule"] == POOL
        seen.append(set(drawn))
    assert len(seen) == 2 and not seen[0] & seen[1]


def test_every_drawn_case_proves_into_a_committed_tranche(run):
    for value in run["packages"].values():
        commitment, payload = value["manifest"]["commitment"], value["payload"]
        roots = {t["tranche"]: t["root"] for t in commitment["bank"]["tranches"]}
        inputs = {c["case_id"]: c["inputs"] for c in payload["document"]["cases"]}
        for case_id, proof in payload["bank"]["proofs"].items():
            assert bank_proof.verify(
                case_id,
                inputs[case_id],
                payload["references"][case_id],
                proof["proof"],
                roots[proof["tranche"]],
            )


def test_an_import_only_validator_imports_banked_windows(run, tmp_path):
    validator = adapter(tmp_path / "validator", import_only=True)
    result = ak.import_local(validator, run["key"].public_key, run["outbox"])
    assert sorted(p["state"] for p in result["packages"]) == ["IMPORTED", "IMPORTED"]


def resigned(run, value, commitment, payload):
    return ak.verify(ak.package(run["key"], commitment, payload), run["key"].public_key)


def canonical_digest(references, needed):
    import hashlib

    from carbon.battery.pool_store import canonical

    rows = [[c, references[c]] for c in needed]
    return "sha256:" + hashlib.sha256(canonical(rows).encode()).hexdigest()


@pytest.mark.parametrize(
    ("change", "code"),
    [
        ("reference", "answer_key_bank_proof"),
        ("drop_bank", "answer_key_bank_missing"),
        ("bank_rule", "answer_key_bank_mismatch"),
        ("selection", "answer_key_bank_mismatch"),
        ("tranche_root", "answer_key_bank_proof"),
    ],
)
def test_a_signed_window_that_did_not_come_from_the_bank_imports_nothing(
    run, tmp_path, change, code
):
    value = json.loads(json.dumps(next(iter(run["packages"].values()))))
    commitment, payload = value["manifest"]["commitment"], value["payload"]
    needed = sorted(payload["references"])
    if change == "reference":
        first = needed[0]
        payload["references"][first] = dict(
            payload["references"][first], status="REFERENCE_TIMEOUT"
        )
        commitment["references_digest"] = canonical_digest(
            payload["references"], needed
        )
    elif change == "drop_bank":
        del payload["bank"]
    elif change == "bank_rule":
        commitment["bank"]["rule"] = dict(POOL, retire_at=99)
    elif change == "selection":
        commitment["bank"]["selection_digest"] = "sha256:" + "0" * 64
    else:
        for tranche in commitment["bank"]["tranches"]:
            tranche["root"] = "sha256:" + "1" * 64
    commitment, payload = resigned(run, value, commitment, payload)
    validator = adapter(tmp_path / "validator", import_only=True)
    with pytest.raises(ak.AnswerKeyRefused) as refused:
        validator.import_answer_key(commitment, payload)
    assert refused.value.code == code
    assert validator.target.store.batches() == []


def test_a_bank_rule_needs_a_bank_and_v2_is_unchanged(tmp_path):
    from carbon.challenge_validator.battery_bank import bank_rule

    with pytest.raises(pr.ProducerRefused) as refused:
        bank_rule(exam.DEVELOPMENT_RULE_V2)
    assert refused.value.code == "producer_rule_has_no_bank"
    assert "bank" not in exam.RULES["v2"]
    assert rule_digest(exam.RULES["v2"]) != rule_digest(RULE)
