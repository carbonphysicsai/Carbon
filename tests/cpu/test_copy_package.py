"""Per-validator copies of a sealed batch on the answer-key route (c'): the
package carries the batch and a digest-only header; the receiver canonicalises by
content; every validator's canonical bank is byte-identical (E9)."""

from __future__ import annotations

import json
import random

import numpy as np
import pytest
import test_cooling_hidden_family as cooling_family
import test_f02_sealed_pack as f02_pack
import test_f08_sealed_pack as f08_pack
import test_battery_sealed_family_grading as battery_family
import test_motor_sealed_family as motor_family

from carbon.challenge_kit import (
    battery_sealed_pack,
    cooling_sealed_pack,
    f02_sealed_pack,
    f08_sealed_pack,
)
from carbon.challenge_kit import motor_sealed_pack
from carbon.challenge_validator import motor_sealed_grid as grid
from carbon.motor_grid_exam import population
from carbon.scoring import copy_package as cp
from carbon.scoring import sealed_batch_source as source

KEYS = (b"validator-one-key-0123456789", b"validator-two-key-9876543210")
HOTKEYS = ("5Fvalidator-one", "5Fvalidator-two")


def _motor():
    cases, _ = population.draw(random.Random(3), population.CELLS)
    doc = {
        "schema": grid.DOCUMENT_SCHEMA,
        "challenge": {"id": source.MOTOR, "version": "1.1"},
        "role": "grid",
        "kind": "screening",
        "population": population.POPULATION_VERSION,
        "cases": [{"case_id": f"g{i:02d}", "inputs": c} for i, c in enumerate(cases)],
    }
    return doc, motor_family.records_for(doc)


def _cooling():
    cases = cooling_family.population.draw(random.Random(2), 16)[0]
    doc = cooling_family.document(cases)
    return doc, cooling_family.records_for(doc)


def _battery():
    sources = battery_family._ev4_sources()
    cases, _ = battery_family.population.draw(
        random.Random(11), battery_family.population.CELLS
    )
    document = battery_family._document(cases)

    def nearest(inputs):
        t, soc = inputs["t_amb_c"], inputs["soc0"]
        return min(
            sources,
            key=lambda s: ((s[0][0] - t) / 29.0) ** 2 + ((s[0][1] - soc) / 0.36) ** 2,
        )[1]

    records = [
        battery_family._record(c["case_id"], c["inputs"], nearest(c["inputs"])[i % 35])
        for i, c in enumerate(document["cases"])
    ]
    return document, records


FORMATS = {
    "motor-grid": (
        source.MOTOR,
        "1.1",
        _motor,
        motor_sealed_pack.grid_bank,
        motor_sealed_pack,
    ),
    "cooling": (
        source.COOLING,
        "1.1",
        _cooling,
        cooling_sealed_pack.sealed_bank,
        cooling_sealed_pack,
    ),
    "f08": (
        source.F08,
        "1.2",
        f08_pack.batch,
        f08_sealed_pack.sealed_bank,
        f08_sealed_pack,
    ),
    "f02": (
        source.F02,
        "2.1",
        f02_pack.batch,
        f02_sealed_pack.sealed_bank,
        f02_sealed_pack,
    ),
}


def _normal(bank):
    return json.dumps(
        {
            "ids": list(bank["case_ids"]),
            "cohorts": list(bank["cohorts"]),
            "inputs": np.asarray(bank["inputs"]).tolist(),
            "references": np.asarray(bank["references"]).tolist(),
            "records": bank["reference_records"],
        },
        sort_keys=True,
    ).encode()


def _deliver(root, raw, header):
    root.mkdir(parents=True, exist_ok=True)
    (root / source.SEALED_BATCH_FILE).write_bytes(raw)
    (root / cp.HEADER_FILE).write_bytes(header)
    return root


@pytest.mark.parametrize("name", sorted(FORMATS))
def test_two_validators_copies_canonicalize_to_one_exam(tmp_path, name):
    challenge, version, build, _bank, _kit = FORMATS[name]
    document, records = build()
    canonical = []
    copies = []
    for n, (key, hotkey) in enumerate(zip(KEYS, HOTKEYS, strict=True)):
        raw, header = cp.make_copy(
            challenge, version, document, records, key=key, hotkey=hotkey
        )
        root = _deliver(tmp_path / f"v{n}", raw, header)
        bank, canon = cp.receive(challenge, version, root, hotkey=hotkey)
        copies.append(bank)
        canonical.append(_normal(canon))
        # The header carries digests and the hotkey only.
        text = header.decode()
        assert all(word not in text for word in ("permutation", "mapping", "order"))
    assert canonical[0] == canonical[1]
    # The copies differ from each other wherever the Challenge renames ids.
    # F02 and Battery keep their meaningful ids; their builders re-sort by id, so
    # their copies are identical (the trace is the signed delivery record).
    if name not in ("f02", "battery"):
        assert _normal(copies[0]) != _normal(copies[1])


@pytest.mark.parametrize("name", sorted(FORMATS))
def test_a_package_without_a_header_or_with_a_tampered_one_is_refused(tmp_path, name):
    challenge, version, build, _bank, _kit = FORMATS[name]
    document, records = build()
    raw, header = cp.make_copy(
        challenge, version, document, records, key=KEYS[0], hotkey=HOTKEYS[0]
    )
    bare = tmp_path / "bare"
    bare.mkdir()
    (bare / source.SEALED_BATCH_FILE).write_bytes(raw)
    with pytest.raises(cp.CopyPackageRefused) as caught:
        cp.receive(challenge, version, bare, hotkey=HOTKEYS[0])
    assert caught.value.code == "copy_header_missing"
    root = _deliver(tmp_path / "ok", raw, header)
    with pytest.raises(cp.CopyPackageRefused) as caught:
        cp.receive(challenge, version, root, hotkey=HOTKEYS[1])
    assert caught.value.code == "copy_header_mismatch"
    tampered = json.loads(header)
    tampered["canonical_digest"] = "sha256:" + "0" * 64
    root = _deliver(tmp_path / "bad", raw, cp.header_bytes(tampered))
    with pytest.raises(cp.CopyPackageRefused) as caught:
        cp.receive(challenge, version, root, hotkey=HOTKEYS[0])
    assert caught.value.code == "canonical_digest_mismatch"
    other = json.loads(header)
    other["copy_digest"] = "sha256:" + "1" * 64
    root = _deliver(tmp_path / "swap", raw, cp.header_bytes(other))
    with pytest.raises(cp.CopyPackageRefused) as caught:
        cp.receive(challenge, version, root, hotkey=HOTKEYS[0])
    assert caught.value.code == "copy_digest_mismatch"


@pytest.mark.parametrize("name", sorted(FORMATS))
def test_the_producer_resolves_each_validators_copy_to_the_same_canonical_bank(
    tmp_path, name
):
    from types import SimpleNamespace

    from carbon.scoring import battery_sealed_dual_pack

    # Validator-only registration, as the retention path does it.
    source.register(battery_sealed_dual_pack)
    challenge, version, build, builder, kit = FORMATS[name]
    document, records = build()
    banks = []
    for n, (key, hotkey) in enumerate(zip(KEYS, HOTKEYS, strict=True)):
        raw, header = cp.make_copy(
            challenge, version, document, records, key=key, hotkey=hotkey
        )
        root = _deliver(tmp_path / f"v{n}", raw, header)
        copy_bank = source._build(
            challenge,
            kit,
            source.read_batch(root)[0],
            source.read_batch(root)[1],
            version,
        )
        pinned = source._sha(kit.private_roles(copy_bank)["case_bank"])
        snapshot = SimpleNamespace(private={"case_bank": {"sha256": pinned}})
        bank, adapter = source.resolve(
            challenge=challenge,
            version=version,
            selected_pack=snapshot,
            private_root=root,
            development_adapter=None if name != "f02" else _f02_adapter(version),
            copy_hotkey=hotkey,
        )
        assert adapter is not None
        banks.append(_normal(bank))
        # Without the header the same package is refused.
        (root / cp.HEADER_FILE).unlink()
        with pytest.raises(source.SealedBankRefused) as caught:
            source.resolve(
                challenge=challenge,
                version=version,
                selected_pack=snapshot,
                private_root=root,
                development_adapter=None,
                copy_hotkey=hotkey,
            )
        assert caught.value.code == "copy_header_missing"
    assert banks[0] == banks[1]


def _f02_adapter(version):
    from carbon.scoring import physical_adapters

    return physical_adapters.adapter(source.F02, version)


@pytest.mark.parametrize("name", sorted(FORMATS))
def test_a_custody_batch_is_repacked_canonically_with_a_signed_append_only_record(
    tmp_path, name
):
    from carbon.challenge_validator import answer_key as ak
    from carbon.challenge_validator import canonicalisation_record as record

    challenge, version, build, _builder, _kit = FORMATS[name]
    document, records = build()
    manifest, raw = record.manifest_for(challenge, version, document, records)
    # The re-pack is the same exam: no re-solve, values unchanged.
    assert manifest["re_solved"] is False
    root = tmp_path / "repack"
    root.mkdir()
    (root / source.SEALED_BATCH_FILE).write_bytes(raw)
    carried = source.read_batch(root)
    bank = source._build(
        challenge, source._kit(challenge), carried[0], carried[1], version
    )
    original = source._build(
        challenge, source._kit(challenge), document, records, version
    )
    opaque = cp.cd.opaque_for(challenge)
    assert (
        cp.cd.content_digest(bank, opaque=opaque) == manifest["canonical_fingerprint"]
    )
    assert (
        cp.cd.content_digest(original, opaque=opaque)
        == manifest["canonical_fingerprint"]
    )
    # A second re-pack of the re-pack is a fixed point.
    again, _src, canonical = cp.canonical_batch(challenge, version, *carried)
    assert again == raw and canonical == manifest["canonical_fingerprint"]
    # Signed, create-only.
    signer = ak.ProducerKey.create(str(tmp_path / "producer.key"))
    signed = record.sign(signer, manifest)
    assert record.verify(signed, signer.public_key) == manifest
    other = ak.ProducerKey.create(str(tmp_path / "other.key"))
    assert record.verify(signed, other.public_key) is None
    store = record.RecordStore(tmp_path / "records")
    store.append(signed, signer.public_key)
    assert store.get(manifest["source_fingerprint"], signer.public_key) == manifest
    with pytest.raises(ak.AnswerKeyRefused):
        store.append(signed, signer.public_key)
    tampered = json.loads(json.dumps(signed))
    tampered["manifest"]["canonical_fingerprint"] = "sha256:" + "2" * 64
    assert record.verify(tampered, signer.public_key) is None


@pytest.mark.parametrize("version", ["1.2", "1.3"])
def test_cooling_copies_resolve_under_every_served_cooling_version(tmp_path, version):
    from types import SimpleNamespace

    challenge, _v, build, _builder, kit = FORMATS["cooling"]
    document, records = build()
    raw, header = cp.make_copy(
        challenge, "1.1", document, records, key=KEYS[0], hotkey=HOTKEYS[0]
    )
    root = _deliver(tmp_path / "v", raw, header)
    copy_bank = source._build(challenge, kit, *source.read_batch(root), "1.1")
    pinned = source._sha(kit.private_roles(copy_bank)["case_bank"])
    # Header names the served exam version it was made for.
    header_doc = json.loads(header)
    header_doc["challenge_version"] = version
    (root / cp.HEADER_FILE).write_bytes(cp.header_bytes(header_doc))
    bank, adapter = source.resolve(
        challenge=challenge,
        version=version,
        selected_pack=SimpleNamespace(private={"case_bank": {"sha256": pinned}}),
        private_root=root,
        development_adapter=None,
        copy_hotkey=HOTKEYS[0],
    )
    assert adapter is not None and bank["cohorts"]
