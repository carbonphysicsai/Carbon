"""Acceptance for the shared answer key (VALIDATOR-19 slice 4).

Several import-only battery validators, each with its own root, import the
same signed packages. They must hold the same batches, activate the same ones
at every block, and seed and score one submission alike. The leak family is
measured, never judged: a leak narrows to the hotkeys that fetched the batch,
and a permit holder's exposure is counted.

In process: synthetic roots, scripted solves and `DirectBackend`. No chain,
network, container or spend. Not a security audit (AGENTS.md §13).
"""

import json
import sys
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from test_battery_validator_daemon import (
    BATTERY,
    batch,
    refs,  # noqa: F401 - fixture
)
from test_challenge_validator_answer_key import battery_validator
from test_challenge_validator_rotation import (  # noqa: F401 - fixture
    EVERY,
    importer,
    made,
    published,
)
from test_graphite_hidden_score import knn

from carbon.battery import seeds
from carbon.challenge_validator import acceptance as acc
from carbon.challenge_validator import answer_key as ak
from carbon.challenge_validator import distribution as dist

BLOCKS = [EVERY + 1, 2 * EVERY + 1, 3 * EVERY + 1, 4 * EVERY + 1, 6 * EVERY]


@pytest.fixture
def three(made):  # noqa: F811
    values = published(made, (1, 2, 3))
    return values, [
        importer(made, f"v{i}", order)
        for i, order in enumerate((values, values[::-1], values[1:] + values[:1]))
    ]


# -- the shared seed ------------------------------------------------------------------------


def test_the_shared_seed_depends_on_the_salts_never_their_order():
    a, b, c = ("a" * 64, "b" * 64, "c" * 64)
    assert seeds.shared_seed([a, b], "x") == seeds.shared_seed([b, a], "x")
    assert seeds.shared_seed([a, b], "x") != seeds.shared_seed([a, c], "x")
    assert seeds.shared_seed([a, b], "x") != seeds.shared_seed([a, b], "y")
    with pytest.raises(ValueError):
        seeds.shared_seed([], "x")


def test_import_only_validators_seed_a_submission_alike(three):
    _values, validators = three
    for validator in validators:
        validator.target.store.admit(
            "s-seed",
            request_digest="d",
            hotkey="5Miner",
            challenge="c",
            strategy="{}",
            binding={"receipt": {"block": 2 * EVERY + 5}, "attempt": 1},
        )
        validator.target.store.rotate_if_ready()
    seeds_ = {v.target._reconstruction_seed("s-seed") for v in validators}
    assert len(seeds_) == 1
    # Each validator's own root would have given different seeds.
    own = {seeds.reconstruction_seed(v.target.root, "s-seed") for v in validators}
    assert len(own) == len(validators)


def test_a_package_without_its_salt_imports_nothing(made, tmp_path):  # noqa: F811
    [value] = published(made, (1,))
    commitment, payload = ak.verify(value, made["key"].public_key)
    payload = {k: v for k, v in payload.items() if k != "reconstruction_salt"}
    adapter = battery_validator(tmp_path / "nosalt", import_only=True)
    with pytest.raises(ak.AnswerKeyRefused) as refused:
        adapter.import_answer_key(commitment, payload)
    assert refused.value.code == "answer_key_malformed"


# -- parity ---------------------------------------------------------------------------------


def test_validators_hold_and_activate_the_same_batches(three):
    _values, validators = three
    report = acc.parity(validators, BLOCKS)
    assert report == {
        "validators": 3,
        "batches": 3,
        "held_identical": True,
        "blocks_checked": len(BLOCKS),
        "active_identical": True,
        "differing_blocks": [],
    }
    text = json.dumps(report)
    assert "salt" not in text.replace("salt_digest", "")


def test_a_validator_missing_a_batch_is_named_by_block(made, three):  # noqa: F811
    values, validators = three
    short = importer(made, "short", values[:2])
    report = acc.parity([*validators, short], BLOCKS)
    assert not report["held_identical"]
    assert report["differing_blocks"] == [3 * EVERY + 1, 4 * EVERY + 1]


def real_package(key, identities, refs, role, slot):  # noqa: F811
    """A signed package of published development cases and their PyBaMM
    references (the daemon tests' fixtures), so a construction really scores."""
    import hashlib

    from carbon.battery.pool_store import canonical
    from carbon.challenge_validator.producer import COMMITMENT_SCHEMA, Producer

    private = batch(refs, role)
    document = private.document()
    duplicates = set(document["duplicates"])
    needed = sorted(
        c["case_id"] for c in document["cases"] if c["case_id"] not in duplicates
    )
    references = {c: refs[c] for c in needed}
    rows = [[c, references[c]] for c in needed]
    commitment = {
        "schema": COMMITMENT_SCHEMA,
        "challenge_id": BATTERY,
        "fingerprint": private.fingerprint,
        "role": role,
        "kind": "screening",
        "journal_sequence": slot,
        "cases": len(document["cases"]),
        "references_digest": "sha256:"
        + hashlib.sha256(canonical(rows).encode()).hexdigest(),
        "contract_digest": identities["contract_digest"],
        "rule_digest": identities["rule_digest"],
        "seed_pin": identities["seed_pin"],
        "window": Producer.window({"every_blocks": EVERY, "active": 3}, slot),
    }
    payload = {
        "document": document,
        "references": references,
        "reconstruction_salt": hashlib.sha256(role.encode()).hexdigest(),
    }
    return ak.package(key, commitment, payload)


def test_one_submission_scores_alike_on_every_validator(tmp_path, refs):  # noqa: F811
    key = ak.ProducerKey.create(tmp_path / "producer.key")
    validators = []
    for index in range(3):
        adapter = battery_validator(tmp_path / f"s{index}", import_only=True)
        # The fixtures' cases are published development examples.
        adapter.target.allow_published_cases = True
        validators.append(adapter)
    identities = validators[0].identities()
    values = [
        real_package(key, identities, refs, f"pscreen-B0{slot - 1}", slot)
        for slot in (1, 2, 3)
    ]
    for index, adapter in enumerate(validators):
        for value in values[index:] + values[:index]:
            adapter.import_answer_key(*ak.verify(value, key.public_key))
        adapter.target.store.open_pool()
    from carbon.agent_campaign.graphite.hidden_score import HiddenPool

    block = 3 * EVERY + 5
    doors = [
        HiddenPool(v.target, run_id="acceptance", clock=lambda: block).submit
        for v in validators
    ]
    report = acc.score_parity(doors, knn(7))
    assert report["states"] == ["SCORED"] * 3
    assert report["identical"] is True


# -- the leak family, measured --------------------------------------------------------------


def test_a_leak_narrows_to_the_fetchers_in_the_window(tmp_path):
    log = dist.FetchLog(tmp_path / "fetch.jsonl")
    fp = "sha256:" + "a" * 64
    log.note(hotkey="5A", block=100, fingerprint=fp, verdict="SERVED")
    log.note(hotkey="5B", block=200, fingerprint=fp, verdict="SERVED")
    log.note(hotkey="5C", block=900, fingerprint=fp, verdict="SERVED")
    log.note(hotkey="5D", block=150, fingerprint=fp, verdict="LISTED")
    log.note(hotkey="5E", block=150, fingerprint="sha256:" + "b" * 64, verdict="SERVED")
    path = tmp_path / "fetch.jsonl"
    assert dist.fetchers(path, fp) == ["5A", "5B", "5C"]
    assert dist.fetchers(path, fp, from_block=100, to_block=500) == ["5A", "5B"]


def test_a_permit_holders_exposure_is_counted_from_the_cadence(made):  # noqa: F811
    cadence = made["source"].cadence()
    assert acc.permit_exposure(cadence, 360) == {
        "batches_at_once": 3,
        "batches_over_holding": 4,
        "longest_remaining_use_blocks": 3 * EVERY,
    }
    assert acc.permit_exposure(cadence, 10 * EVERY)["batches_over_holding"] == 13
