"""E4 option (1): a validator's traceable copy of a sealed pack, with canonical identity.

Two hotkeys receive different copy packs (different manifest digests M_h, kept local)
that canonicalise to one pack (manifest digest M_c). Everything shared keys on M_c:
the stored canonical pack, the pack-set key, the delivery record. Not a security
audit; synthetic packs, in process."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from test_copy_package import FORMATS, HOTKEYS, KEYS

from carbon.challenge_validator import answer_key as ak
from carbon.challenge_validator import copy_delivery as delivery
from carbon.challenge_validator import copy_route
from carbon.challenge_validator import sealed_exam_common as common
from carbon.challenge_validator import sealed_pack_import as spi
from carbon.challenge_validator.evaluation_pack import (
    PRIVATE_ROLES,
    PUBLIC_ROLES,
    SCHEMA,
    UNAVAILABLE,
)
from carbon.scoring import copy_derivation as cd
from carbon.scoring import copy_package as cp
from carbon.scoring import sealed_batch_source as source

MASTER = b"carbon-test-master-key-0123456789"
WINDOW = {"slot": 1, "activate_block": 10, "retire_block": 10**9}


def _sha(raw):
    import hashlib

    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _canonical_pack(name):
    """(challenge, version, canonical manifest, canonical files, canonical batch)."""
    challenge, version, build, _builder, kit = FORMATS[name]
    document, records = build()
    raw, _src, _fp = cp.canonical_batch(challenge, version, document, records)
    carried = json.loads(raw)
    bank = source._build(
        challenge, kit, carried["document"], carried["records"], version
    )
    roles = kit.private_roles(bank)
    files = {"public/interface.json": b'{"interface":1}'}
    manifest = {
        "schema": SCHEMA,
        "challenge": {"id": challenge, "version": version},
        "pack_version": "1",
        "public": {n: UNAVAILABLE for n in PUBLIC_ROLES},
        "private": {n: UNAVAILABLE for n in PRIVATE_ROLES},
    }
    manifest["public"]["interface"] = {
        "path": "public/interface.json",
        "sha256": _sha(files["public/interface.json"]),
    }
    for role in delivery.COPY_ROLES:
        path = f"private/{role}.bin"
        files[path] = roles[role]
        manifest["private"][role] = {"path": path, "sha256": _sha(roles[role])}
    manifest_bytes = (
        json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    return challenge, version, manifest_bytes, files, carried


@pytest.fixture(scope="module")
def producer(tmp_path_factory):
    return ak.ProducerKey.create(str(tmp_path_factory.mktemp("k") / "producer.key"))


def _issue(producer, name, hotkey):
    challenge, version, manifest, files, carried = _canonical_pack(name)
    return delivery.issue_copy(
        producer,
        MASTER,
        challenge=challenge,
        version=version,
        canonical_manifest=manifest,
        canonical_files=files,
        document=carried["document"],
        records=carried["records"],
        hotkey=hotkey,
        window=WINDOW,
    ), (challenge, version, manifest, files)


@pytest.mark.parametrize("name", sorted(FORMATS))
def test_two_hotkeys_copies_import_to_one_canonical_pack(tmp_path, producer, name):
    stores, digests, locals_ = [], [], []
    for n, hotkey in enumerate(HOTKEYS):
        package, (challenge, version, manifest, files) = _issue(producer, name, hotkey)
        store = spi.SealedPackStore(tmp_path / f"v{n}")
        digest = delivery.import_copy(
            store, package, producer.public_key, hotkey=hotkey
        )
        stores.append(store)
        digests.append(digest)
        locals_.append(package["manifest"]["commitment"]["manifest_digest"])
        # The canonical pack is an ordinary, verified, delivered pack under M_c.
        assert digest == _sha(manifest)
        directory = store.pack_directory(digest, challenge, version)
        assert (directory / spi.MANIFEST_NAME).read_bytes() == manifest
        for relative, body in files.items():
            assert (directory / relative).read_bytes() == body
        assert store.delivered(digest, challenge, version)
        # The delivered copy stays local, beside it.
        local = delivery.copies_directory(store.root, digest)
        assert (local / cp.HEADER_FILE).is_file()
    # E9: one canonical identity for both, byte-identical canonical packs.
    assert digests[0] == digests[1]
    one = stores[0].pack_directory(digests[0], challenge, version)
    two = stores[1].pack_directory(digests[1], challenge, version)
    for path in sorted(one.rglob("*")):
        if path.is_file():
            assert path.read_bytes() == (two / path.relative_to(one)).read_bytes()
    # Shared identities (pack-set document and key) are the same for both.
    keys = [
        common.pack_set_key(common.pack_set_document(challenge, version, [d]))
        for d in digests
    ]
    assert keys[0] == keys[1]
    # No copy manifest digest leaks into a shared (canonical-keyed) record.
    if locals_[0] != digests[0]:
        assert locals_[0] != locals_[1]
        for store, local in zip(stores, locals_, strict=True):
            for record in (store.root / spi.DELIVERED_DIRECTORY).glob("*.json"):
                assert local.encode() not in record.read_bytes()
            canonical_dir = store.pack_directory(digests[0], challenge, version)
            for path in canonical_dir.rglob("*"):
                if path.is_file():
                    assert local.encode() not in path.read_bytes()


@pytest.mark.parametrize("name", sorted(FORMATS))
def test_the_producer_resolves_the_canonical_pack_for_its_own_hotkey_only(
    tmp_path, producer, name
):
    from types import SimpleNamespace

    from carbon.scoring import battery_sealed_dual_pack

    source.register(battery_sealed_dual_pack)
    package, (challenge, version, manifest, files) = _issue(producer, name, HOTKEYS[0])
    store = spi.SealedPackStore(tmp_path / "v")
    digest = delivery.import_copy(
        store, package, producer.public_key, hotkey=HOTKEYS[0]
    )
    directory = store.pack_directory(digest, challenge, version)
    pinned = json.loads(manifest)["private"]["case_bank"]["sha256"]
    snapshot = SimpleNamespace(private={"case_bank": {"sha256": pinned}})
    bank, adapter = source.resolve(
        challenge=challenge,
        version=version,
        selected_pack=snapshot,
        private_root=directory,
        development_adapter=None,
        copy_hotkey=HOTKEYS[0],
    )
    assert adapter is not None and bank["cohorts"]
    with pytest.raises(source.SealedBankRefused):
        source.resolve(
            challenge=challenge,
            version=version,
            selected_pack=snapshot,
            private_root=directory,
            development_adapter=None,
            copy_hotkey=HOTKEYS[1],
        )


def test_a_copy_for_another_hotkey_a_tampered_batch_or_a_foreign_manifest_is_refused(
    tmp_path, producer
):
    package, (challenge, version, manifest, files) = _issue(
        producer, "motor-grid", HOTKEYS[0]
    )
    store = spi.SealedPackStore(tmp_path / "v")
    with pytest.raises(ak.AnswerKeyRefused, match="copy_wrong_hotkey"):
        delivery.import_copy(store, package, producer.public_key, hotkey=HOTKEYS[1])
    assert not list(store.root.glob("*"))
    # A batch that is not this pack's (swapped carried batch).
    other, _ = _issue(producer, "motor-grid", HOTKEYS[1])
    swapped = json.loads(json.dumps(package))
    swapped["payload"]["copy"]["batch"] = other["payload"]["copy"]["batch"]
    swapped["manifest"]["payload_digest"] = ak._digest(swapped["payload"])
    swapped["signature"] = producer.sign_in(copy_route.PACK_DOMAIN, swapped["manifest"])
    with pytest.raises(ak.AnswerKeyRefused):
        delivery.import_copy(store, swapped, producer.public_key, hotkey=HOTKEYS[0])
    # A signature from another key.
    stranger = ak.ProducerKey.create(str(tmp_path / "s.key"))
    with pytest.raises(ak.AnswerKeyRefused):
        delivery.import_copy(store, package, stranger.public_key, hotkey=HOTKEYS[0])
    assert not [p for p in store.root.glob("*") if not p.name.startswith(".")]


def test_the_per_hotkey_route_syncs_a_copy_end_to_end(tmp_path, producer):
    package, (challenge, version, manifest, files) = _issue(
        producer, "cooling", HOTKEYS[0]
    )

    class Fetcher:
        def ask(self, challenge_id, fingerprint=None):
            if fingerprint is None:
                return {"packages": [copy_route.listing_entry(package)]}
            return {"package": package}

    store = spi.SealedPackStore(tmp_path / "v")
    first = delivery.sync_copies(
        store, Fetcher(), producer.public_key, challenge, hotkey=HOTKEYS[0]
    )
    assert first["packages"][0]["state"] == "IMPORTED"
    again = delivery.sync_copies(
        store, Fetcher(), producer.public_key, challenge, hotkey=HOTKEYS[0]
    )
    assert again["packages"][0]["state"] == "HELD"
    store.withdraw(_sha(manifest), "test", 1)
    gone = delivery.sync_copies(
        store, Fetcher(), producer.public_key, challenge, hotkey=HOTKEYS[0]
    )
    assert gone["packages"][0]["state"] == "WITHDRAWN"


def test_the_per_validator_key_is_derived_from_the_master_and_the_hotkey():
    assert delivery.validator_key(MASTER, "a") != delivery.validator_key(MASTER, "b")
    assert delivery.validator_key(MASTER, "a") == delivery.validator_key(MASTER, "a")
    with pytest.raises(ak.AnswerKeyRefused):
        delivery.validator_key(b"short", "a")
    _ = (Path, cd, KEYS)
