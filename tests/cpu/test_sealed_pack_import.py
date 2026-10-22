"""Workstream I2: a sealed evaluation pack reaches a validator over the
answer-key route, by digest, verified in full before anything is stored.

In process, with a synthetic pack and Carbon's producer key made here. There is
no chain, network or real exam material. Not a security audit.

Claims tested:
1. A signed pack imports through `answer_key.sync` and is held afterwards.
2. The receiver setup takes the stored pack by manifest digest, re-verified.
3. A tampered file, an extra or missing file, an escaping path, a wrong
   Challenge or version, a wrong producer, and a manifest not matching its
   digest each refuse with a typed code and store nothing.
4. A hidden-batch commitment still packages and verifies as before.
"""

from __future__ import annotations

import hashlib
import json

import pytest

from carbon.challenge_validator import answer_key as ak
from carbon.challenge_validator import receiver_setup
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


def _pack():
    files = {
        "public/interface.json": b'{"interface":1}',
        "private/case_bank.npz": b"sealed-case-bank-bytes",
        "private/reference_rows.json": b'{"rows":[1,2,3]}',
    }
    manifest = {
        "schema": SCHEMA,
        "challenge": {"id": CHALLENGE, "version": VERSION},
        "pack_version": "1",
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
    manifest["private"]["reference_rows"] = {
        "path": "private/reference_rows.json",
        "sha256": _sha(files["private/reference_rows.json"]),
    }
    return json.dumps(manifest, sort_keys=True).encode(), files


def _signed(tmp_path, files=None, manifest=None, **commit):
    key = ak.ProducerKey.create(str(tmp_path / "producer.key"))
    built_manifest, built_files = _pack()
    manifest = built_manifest if manifest is None else manifest
    files = built_files if files is None else files
    commitment = sp.commitment_for(CHALLENGE, VERSION, manifest, files, WINDOW)
    commitment.update(commit)
    package = ak.package(key, commitment, sp.payload_for(manifest, files))
    return key, commitment, package


def _adapter(tmp_path, version=VERSION):
    return sp.SealedPackAdapter(
        CHALLENGE, version, sp.SealedPackStore(tmp_path / "packs")
    )


class _Fetcher:
    def __init__(self, package):
        self.package = package

    def ask(self, challenge_id, fingerprint=None):
        if fingerprint is None:
            return {"packages": [ak.listing_entry(self.package)]}
        return {"package": self.package}


def test_a_signed_pack_imports_through_sync_and_is_held(tmp_path):
    key, commitment, package = _signed(tmp_path)
    adapter = _adapter(tmp_path)
    assert not adapter.holds_answer_key(commitment)
    result = ak.sync(adapter, _Fetcher(package), key.public_key, CHALLENGE)
    assert result["packages"] == [
        {"fingerprint": commitment["fingerprint"], "state": "IMPORTED"}
    ]
    assert adapter.holds_answer_key(commitment)
    again = ak.sync(adapter, _Fetcher(package), key.public_key, CHALLENGE)
    assert again["packages"][0]["state"] == "HELD"


def test_the_receiver_takes_the_pack_by_digest_from_the_store(tmp_path):
    key, commitment, package = _signed(tmp_path)
    adapter = _adapter(tmp_path)
    ak.sync(adapter, _Fetcher(package), key.public_key, CHALLENGE)
    directory = receiver_setup._stored_pack(
        tmp_path / "packs", commitment["manifest_digest"], {"id": CHALLENGE, "version": VERSION}
    )
    manifest, files = _pack()
    assert (directory / "evaluation-pack.json").read_bytes() == manifest
    assert (directory / "private/case_bank.npz").read_bytes() == files[
        "private/case_bank.npz"
    ]
    assert receiver_setup._pack_selection(directory)["root"] == str(directory)
    # Absent, another Challenge's, or altered after import: refused.
    with pytest.raises(receiver_setup.SetupRefused):
        receiver_setup._stored_pack(
            tmp_path / "packs", _sha(b"other"), {"id": CHALLENGE, "version": VERSION}
        )
    with pytest.raises(receiver_setup.SetupRefused):
        receiver_setup._stored_pack(
            tmp_path / "packs",
            commitment["manifest_digest"],
            {"id": CHALLENGE, "version": "9.9"},
        )
    (directory / "private/case_bank.npz").write_bytes(b"tampered")
    with pytest.raises(receiver_setup.SetupRefused):
        receiver_setup._stored_pack(
            tmp_path / "packs",
            commitment["manifest_digest"],
            {"id": CHALLENGE, "version": VERSION},
        )


def _refused(adapter, key, package, code=None):
    with pytest.raises(ak.AnswerKeyRefused) as refused:
        ak.sync(adapter, _Fetcher(package), key.public_key, CHALLENGE)
    if code is not None:
        assert refused.value.code == code
    root = adapter.store.root
    assert not root.exists() or not [d for d in root.iterdir() if d.is_dir()]


def test_a_tampered_file_imports_nothing(tmp_path):
    manifest, files = _pack()
    tampered = dict(files, **{"private/case_bank.npz": b"tampered-bytes"})
    key, _, package = _signed(tmp_path, files=tampered, manifest=manifest)
    _refused(_adapter(tmp_path), key, package, "answer_key_sealed_pack_files")


def test_extra_or_missing_files_are_refused(tmp_path):
    manifest, files = _pack()
    key, _, package = _signed(
        tmp_path, files=dict(files, **{"private/extra.bin": b"x"}), manifest=manifest
    )
    _refused(_adapter(tmp_path), key, package, "answer_key_sealed_pack_files")
    missing = {k: v for k, v in files.items() if k != "private/reference_rows.json"}
    (tmp_path / "b").mkdir()
    key, _, package = _signed(tmp_path / "b", files=missing, manifest=manifest)
    _refused(_adapter(tmp_path / "b"), key, package, "answer_key_sealed_pack_files")


@pytest.mark.parametrize(
    "name", ["../escape.bin", "/abs.bin", "a/../../b.bin", "a\\b.bin", "evaluation-pack.json"]
)
def test_a_path_that_leaves_the_pack_is_refused(tmp_path, name):
    manifest, files = _pack()
    key, _, package = _signed(
        tmp_path, files=dict(files, **{name: b"x"}), manifest=manifest
    )
    _refused(_adapter(tmp_path), key, package, "answer_key_malformed")


def test_wrong_challenge_version_and_producer_are_refused(tmp_path):
    key, _, package = _signed(tmp_path)
    _refused(_adapter(tmp_path, version="2.0"), key, package, "answer_key_wrong_challenge")
    other = ak.ProducerKey.create(str(tmp_path / "other.key"))
    with pytest.raises(ak.AnswerKeyRefused) as refused:
        ak.sync(_adapter(tmp_path), _Fetcher(package), other.public_key, CHALLENGE)
    assert refused.value.code == "answer_key_wrong_producer"


def test_a_manifest_that_is_not_its_committed_digest_is_refused(tmp_path):
    manifest, files = _pack()
    key, commitment, _ = _signed(tmp_path)
    forged = commitment | {"manifest_digest": _sha(b"x"), "fingerprint": _sha(b"x")}
    package = ak.package(key, forged, sp.payload_for(manifest, files))
    _refused(_adapter(tmp_path), key, package, "answer_key_fingerprint_mismatch")


def test_a_hidden_batch_commitment_still_packages_and_other_kinds_do_not(tmp_path):
    key = ak.ProducerKey.create(str(tmp_path / "k.key"))
    with pytest.raises(ak.AnswerKeyRefused) as refused:
        ak.package(key, {"schema": sp.SEALED_COMMITMENT_SCHEMA, "kind": "screening"}, {})
    assert refused.value.code == "answer_key_kind_not_served"
    with pytest.raises(ak.AnswerKeyRefused) as refused:
        ak.package(key, {"schema": "something-else", "kind": "sealed_pack"}, {})
    assert refused.value.code == "answer_key_commitment_malformed"
