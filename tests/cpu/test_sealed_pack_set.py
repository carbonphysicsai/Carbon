"""OWNER-FULL-EXAM-BANK-01: a Challenge version's exam is the union of its active
sealed batches. The producer signs a pack-set manifest (the batch packs by
manifest digest); its digest is the evaluation key. A validator imports the
batch packs and the set through the one answer-key route, in any order, and
takes the set back only when every batch re-verifies and was delivered."""

from __future__ import annotations

import hashlib
import json

import pytest

from carbon.challenge_validator import answer_key as ak
from carbon.challenge_validator import sealed_exam_common as common
from carbon.challenge_validator import sealed_pack_import as sp
from carbon.challenge_validator.evaluation_pack import (
    PRIVATE_ROLES,
    PUBLIC_ROLES,
    SCHEMA,
    UNAVAILABLE,
)

CHALLENGE = "test-challenge"
VERSION = "1.0"
WINDOW = {"slot": 1, "activate_block": 10, "retire_block": 100}


def _sha(body):
    return "sha256:" + hashlib.sha256(body).hexdigest()


def _pack(n):
    files = {
        "public/interface.json": b'{"interface":1}',
        "private/case_bank.npz": b"sealed-case-bank-bytes-%d" % n,
    }
    manifest = {
        "schema": SCHEMA,
        "challenge": {"id": CHALLENGE, "version": VERSION},
        "pack_version": str(n),
        "public": {name: UNAVAILABLE for name in PUBLIC_ROLES},
        "private": {name: UNAVAILABLE for name in PRIVATE_ROLES},
    }
    manifest["public"]["interface"] = {
        "path": "public/interface.json",
        "sha256": _sha(files["public/interface.json"]),
    }
    manifest["private"]["case_bank"] = {
        "path": "private/case_bank.npz",
        "sha256": _sha(files["private/case_bank.npz"]),
    }
    return json.dumps(manifest, sort_keys=True).encode(), files


def _batch_package(key, n):
    manifest, files = _pack(n)
    commitment = sp.commitment_for(CHALLENGE, VERSION, manifest, files, WINDOW)
    return commitment, ak.package(key, commitment, sp.payload_for(manifest, files))


def _set_package(key, digests, challenge=CHALLENGE, version=VERSION):
    commitment = sp.set_commitment_for(challenge, version, digests, WINDOW)
    return commitment, ak.package(key, commitment, sp.set_payload_for(commitment))


class _Fetcher:
    def __init__(self, *packages):
        self.packages = {
            p["manifest"]["commitment"]["fingerprint"]: p for p in packages
        }

    def ask(self, challenge_id, fingerprint=None):
        if fingerprint is None:
            return {"packages": [ak.listing_entry(p) for p in self.packages.values()]}
        return {"package": self.packages[fingerprint]}


@pytest.fixture
def world(tmp_path):
    key = ak.ProducerKey.create(str(tmp_path / "producer.key"))
    one, package_one = _batch_package(key, 1)
    two, package_two = _batch_package(key, 2)
    digests = [one["manifest_digest"], two["manifest_digest"]]
    set_commitment, set_package = _set_package(key, digests)
    adapter = sp.SealedPackAdapter(
        CHALLENGE, VERSION, sp.SealedPackStore(tmp_path / "packs")
    )
    return {
        "key": key,
        "digests": digests,
        "set": set_commitment,
        "packages": (set_package, package_one, package_two),
        "adapter": adapter,
        "store": adapter.store,
    }


def test_the_set_key_is_the_evaluation_key_of_its_batches(world):
    document = common.pack_set_document(CHALLENGE, VERSION, world["digests"])
    assert world["set"]["set_key"] == world["set"]["fingerprint"]
    assert world["set"]["set_key"] == common.pack_set_key(document)
    assert world["set"]["batches"] == sorted(world["digests"])


def test_a_set_and_its_batches_import_in_any_order_and_are_taken_back(world):
    # The set is listed (and so imported) before either of its batches.
    result = ak.sync(
        world["adapter"],
        _Fetcher(*world["packages"]),
        world["key"].public_key,
        CHALLENGE,
    )
    assert sorted(entry["state"] for entry in result["packages"]) == ["IMPORTED"] * 3
    assert world["adapter"].holds_answer_key(world["set"])
    batches = world["store"].pack_set(world["set"]["set_key"], CHALLENGE, VERSION)
    assert [digest for digest, _directory in batches] == sorted(world["digests"])
    for digest, directory in batches:
        assert (directory / "evaluation-pack.json").is_file()
        assert world["store"].delivered(digest, CHALLENGE, VERSION)
    again = ak.sync(
        world["adapter"],
        _Fetcher(*world["packages"]),
        world["key"].public_key,
        CHALLENGE,
    )
    assert {entry["state"] for entry in again["packages"]} == {"HELD"}


def test_a_set_with_a_missing_batch_grades_nothing(world):
    set_package, package_one, _ = world["packages"]
    ak.sync(
        world["adapter"],
        _Fetcher(set_package, package_one),
        world["key"].public_key,
        CHALLENGE,
    )
    with pytest.raises(ak.AnswerKeyRefused, match="answer_key_pack_set_batch_missing"):
        world["store"].pack_set(world["set"]["set_key"], CHALLENGE, VERSION)


def test_a_set_that_was_never_imported_is_missing(world):
    with pytest.raises(ak.AnswerKeyRefused, match="answer_key_pack_set_missing"):
        world["store"].pack_set(world["set"]["set_key"], CHALLENGE, VERSION)
    with pytest.raises(ak.AnswerKeyRefused):
        world["store"].pack_set("not-a-digest", CHALLENGE, VERSION)


def test_a_batch_placed_by_hand_is_not_a_delivered_batch(world, tmp_path):
    """A batch copied into the store has no delivery record: the set refuses it."""
    import shutil

    set_package, package_one, package_two = world["packages"]
    ak.sync(
        world["adapter"],
        _Fetcher(set_package, package_one, package_two),
        world["key"].public_key,
        CHALLENGE,
    )
    victim = sorted(world["digests"])[0]
    record = (
        world["store"].root / ".delivered" / (victim.removeprefix("sha256:") + ".json")
    )
    record.unlink()
    with pytest.raises(ak.AnswerKeyRefused, match="answer_key_pack_set_batch_missing"):
        world["store"].pack_set(world["set"]["set_key"], CHALLENGE, VERSION)
    assert shutil  # the copy case is covered by test_sealed_pack_import


def test_a_set_for_another_challenge_or_version_is_refused(world):
    ak.sync(
        world["adapter"],
        _Fetcher(*world["packages"]),
        world["key"].public_key,
        CHALLENGE,
    )
    with pytest.raises(ak.AnswerKeyRefused, match="answer_key_wrong_challenge"):
        world["store"].pack_set(world["set"]["set_key"], CHALLENGE, "9.9")
    other = sp.SealedPackAdapter(
        "another-challenge", VERSION, sp.SealedPackStore(world["store"].root)
    )
    with pytest.raises(ak.AnswerKeyRefused, match="answer_key_wrong_challenge"):
        other.import_answer_key(world["set"], sp.set_payload_for(world["set"]))


def test_a_tampered_set_is_refused(world):
    commitment = world["set"]
    payload = sp.set_payload_for(commitment)
    for bad_commitment, bad_payload in (
        (
            {**commitment, "set_key": _sha(b"other"), "fingerprint": _sha(b"other")},
            payload,
        ),
        ({**commitment, "batches": commitment["batches"][:1]}, payload),
        (commitment, {"batches": list(reversed(payload["batches"]))}),
        (commitment, {"batches": payload["batches"][:1]}),
        ({**commitment, "kind": "screening"}, payload),
        ({k: v for k, v in commitment.items() if k != "window"}, payload),
    ):
        with pytest.raises(ak.AnswerKeyRefused):
            sp.verify_set(bad_commitment, bad_payload)


def test_the_signature_covers_the_set(world):
    package = world["packages"][0]
    forged = json.loads(json.dumps(package))
    forged["manifest"]["commitment"]["batches"] = forged["manifest"]["commitment"][
        "batches"
    ][:1]
    with pytest.raises(ak.AnswerKeyRefused, match="answer_key_signature"):
        ak.verify(forged, world["key"].public_key)
    with pytest.raises(ak.AnswerKeyRefused):
        ak.package(
            world["key"],
            {**world["set"], "kind": "screening"},
            sp.set_payload_for(world["set"]),
        )


# --- signed withdrawal (mainnet exam delivery; VALIDATOR-24 for sealed packs) -------------


class _WithdrawingFetcher(_Fetcher):
    def __init__(self, notices, *packages):
        super().__init__(*packages)
        self.notices = notices

    def ask(self, challenge_id, fingerprint=None):
        answer = super().ask(challenge_id, fingerprint)
        if fingerprint is None:
            answer["withdrawals"] = self.notices
        return answer


def _imported(world):
    ak.sync(
        world["adapter"],
        _Fetcher(*world["packages"]),
        world["key"].public_key,
        CHALLENGE,
    )


def test_a_signed_withdrawal_of_a_batch_stops_it_and_its_set(world):
    _imported(world)
    victim = sorted(world["digests"])[0]
    notice = ak.withdrawal_notice(world["key"], CHALLENGE, victim, "leaked", 7)
    result = ak.sync(
        world["adapter"],
        _WithdrawingFetcher([notice], *world["packages"]),
        world["key"].public_key,
        CHALLENGE,
    )
    assert {"fingerprint": victim, "state": "WITHDRAWN"} in result["packages"]
    store = world["store"]
    assert store.withdrawn(victim)
    assert not store.delivered(victim, CHALLENGE, VERSION)
    with pytest.raises(ak.AnswerKeyRefused, match="answer_key_sealed_pack_withdrawn"):
        store.pack_directory(victim, CHALLENGE, VERSION)
    # A set that lists the withdrawn batch grades nothing.
    with pytest.raises(
        ak.AnswerKeyRefused, match="answer_key_pack_set_batch_withdrawn"
    ):
        store.pack_set(world["set"]["set_key"], CHALLENGE, VERSION)
    # The other batch is untouched; the withdrawn files stay for audit.
    other = sorted(world["digests"])[1]
    assert store.delivered(other, CHALLENGE, VERSION)
    assert (store.root / victim.removeprefix("sha256:")).is_dir()


def test_a_withdrawn_pack_is_never_imported_again(world, tmp_path):
    victim = sorted(world["digests"])[0]
    notice = ak.withdrawal_notice(world["key"], CHALLENGE, victim, "leaked", 7)
    # Withdrawn before it was ever imported: the sync skips it and records it.
    result = ak.sync(
        world["adapter"],
        _WithdrawingFetcher([notice], *world["packages"]),
        world["key"].public_key,
        CHALLENGE,
    )
    states = {e["fingerprint"]: e["state"] for e in result["packages"]}
    assert states[victim] == "WITHDRAWN"
    assert not world["store"].delivered(victim, CHALLENGE, VERSION)
    package = next(
        p
        for p in world["packages"]
        if p["manifest"]["commitment"]["fingerprint"] == victim
    )
    commitment, payload = ak.verify(package, world["key"].public_key)
    with pytest.raises(ak.AnswerKeyRefused, match="answer_key_withdrawn"):
        world["adapter"].import_answer_key(commitment, payload)
    assert not world["adapter"].holds_answer_key(commitment)


def test_a_signed_withdrawal_of_a_set_stops_the_set(world):
    _imported(world)
    key = world["set"]["set_key"]
    notice = ak.withdrawal_notice(world["key"], CHALLENGE, key, "rotated_early", 9)
    ak.sync(
        world["adapter"],
        _WithdrawingFetcher([notice], *world["packages"]),
        world["key"].public_key,
        CHALLENGE,
    )
    store = world["store"]
    assert not world["adapter"].holds_answer_key(world["set"])
    with pytest.raises(ak.AnswerKeyRefused, match="answer_key_pack_set_withdrawn"):
        store.pack_set(key, CHALLENGE, VERSION)
    with pytest.raises(ak.AnswerKeyRefused, match="answer_key_withdrawn"):
        store.import_pack_set(world["set"], sp.set_payload_for(world["set"]))
    # The batches stay delivered; only the set is withdrawn.
    assert all(store.delivered(d, CHALLENGE, VERSION) for d in world["digests"])


def test_a_withdrawal_is_create_only(world):
    store = world["store"]
    digest = world["digests"][0]
    store.withdraw(digest, "leaked", 7)
    store.withdraw(digest, "leaked", 7)  # the same notice again: a no-op
    with pytest.raises(ak.AnswerKeyRefused, match="answer_key_withdrawal_changed"):
        store.withdraw(digest, "other_reason", 7)


def test_a_forged_or_foreign_withdrawal_changes_nothing(world, tmp_path):
    _imported(world)
    victim = sorted(world["digests"])[0]
    stranger = ak.ProducerKey.create(str(tmp_path / "stranger.key"))
    forged = ak.withdrawal_notice(stranger, CHALLENGE, victim, "leaked", 7)
    with pytest.raises(ak.AnswerKeyRefused):
        ak.sync(
            world["adapter"],
            _WithdrawingFetcher([forged], *world["packages"]),
            world["key"].public_key,
            CHALLENGE,
        )
    other_challenge = ak.withdrawal_notice(
        world["key"], "another-challenge", victim, "leaked", 7
    )
    with pytest.raises(ak.AnswerKeyRefused, match="answer_key_wrong_challenge"):
        ak.sync(
            world["adapter"],
            _WithdrawingFetcher([other_challenge], *world["packages"]),
            world["key"].public_key,
            CHALLENGE,
        )
    assert not world["store"].withdrawn(victim)
    assert world["store"].delivered(victim, CHALLENGE, VERSION)
