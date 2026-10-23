"""A sealed pack is graded on its carried sealed batch, through a REAL ``parse_pack``
snapshot (Validator P0, 2026-10-23).

``evaluation_pack.parse_pack`` freezes the private role entries as ``MappingProxyType``.
``sealed_batch_source._pinned_case_bank`` once required ``type(entry) is dict``, read every
parsed pack as unpinned and returned ``None`` ("development pack"), so a sealed exam was
graded on the PUBLIC development bank: a fail-open. The existing tests passed a plain-dict
``SimpleNamespace``, which hid it. Here the packs are written as the executors write them,
sealed as the receiver seals them, and parsed as the receiver parses them."""

from __future__ import annotations

import json
from collections.abc import Mapping
from types import MappingProxyType

import pytest
from test_f02_sealed_pack import batch as f02_batch
from test_f08_sealed_pack import batch as f08_batch
from test_motor_sealed_family import records_for

from carbon.challenge_kit import (
    f02_sealed_pack,
    f08_sealed_pack,
    motor_sealed_pack,
    physical_pack,
)
from carbon.challenge_validator import motor_sealed_grid as grid
from carbon.challenge_validator.evaluation_pack import parse_pack, prepare_pack
from carbon.motor_grid_exam import population
from carbon.scoring import (
    cooling_dual_pack,
    f02_dual_pack,
    f02_sealed_dual_pack,
    f08_dual_pack,
    f08_sealed_dual_pack,
    motor_dual_pack,
    motor_sealed_dual_pack,
)
from carbon.scoring import physical_dual_pack as physical
from carbon.scoring import sealed_batch_source as source

PLATFORM = {"inference_image_id": "sha256:" + "1" * 64}


def _motor_batch():
    import random

    cases, _ = population.draw(random.Random(3), population.CELLS)
    doc = {
        "schema": grid.DOCUMENT_SCHEMA,
        "challenge": {"id": source.MOTOR, "version": "1.1"},
        "role": "grid",
        "kind": "screening",
        "population": population.POPULATION_VERSION,
        "cases": [{"case_id": f"g{i:02d}", "inputs": c} for i, c in enumerate(cases)],
    }
    return doc, records_for(doc)


# kind -> (challenge, version, development adapter, sealed writer, bank builder, batch)
CASES = {
    "f08": (
        f08_dual_pack.CHALLENGE,
        "1.4",
        lambda: f08_dual_pack.adapter(version="1.4"),
        f08_sealed_dual_pack.write_sealed_pack,
        lambda d, r: f08_sealed_pack.sealed_bank(d, r, version="1.4"),
        f08_batch,
    ),
    "f02": (
        f02_dual_pack.CHALLENGE,
        "2.3",
        lambda: physical.versioned(f02_dual_pack, "2.3"),
        f02_sealed_dual_pack.write_sealed_pack,
        lambda d, r: f02_sealed_pack.sealed_bank(d, r, version="2.3"),
        f02_batch,
    ),
    "motor": (
        motor_dual_pack.CHALLENGE,
        "1.3",
        lambda: physical.versioned(motor_dual_pack, "1.3"),
        motor_sealed_dual_pack.write_sealed_pack,
        lambda d, r: motor_sealed_pack.grid_bank(d, r, version="1.3"),
        _motor_batch,
    ),
}
DEV_ONLY = {
    "cooling": (
        cooling_dual_pack.CHALLENGE,
        "1.2",
        lambda: physical.versioned(cooling_dual_pack, "1.2"),
    ),
}


def _parse(root, challenge, version):
    prepared = prepare_pack(
        root,
        physical.MANIFEST_NAME,
        public_root=root,
        private_root=root,
        challenge_id=challenge,
        challenge_version=version,
    )
    return parse_pack(
        prepared.sealed_bytes,
        expected_digest=prepared.snapshot.manifest_digest,
        challenge_id=challenge,
        challenge_version=version,
    )


def _resolve(snapshot, root, challenge, version, development):
    return source.resolve(
        challenge=challenge,
        version=version,
        selected_pack=snapshot,
        private_root=root,
        development_adapter=development,
    )


def test_a_parsed_pack_freezes_its_role_entries_as_read_only_mappings(tmp_path):
    """The premise of the bug: the entry is a Mapping, not a dict."""
    challenge, version, development, *_ = CASES["f08"]
    adapter = development()
    adapter.write_development_pack(tmp_path / "pack", **PLATFORM)
    snapshot = _parse(tmp_path / "pack", challenge, version)
    entry = snapshot.private["case_bank"]
    assert isinstance(entry, MappingProxyType) and isinstance(entry, Mapping)
    assert type(entry) is not dict
    assert source._pinned_case_bank(snapshot) == entry["sha256"]


@pytest.mark.parametrize("kind", sorted(CASES))
def test_a_sealed_pack_resolves_to_its_sealed_bank(kind, tmp_path):
    challenge, version, development, write, build, make_batch = CASES[kind]
    doc, records = make_batch()
    records = [{"wall_s": 100.0, **r} for r in records]
    bank = build(doc, records)
    root = tmp_path / "pack"
    write(root, bank, version=version, **PLATFORM)
    (root / source.SEALED_BATCH_FILE).write_bytes(source.batch_bytes(doc, records))
    snapshot = _parse(root, challenge, version)
    resolved = _resolve(snapshot, root, challenge, version, development())
    assert resolved is not None, "a sealed pack must never resolve to the dev bank"
    sealed_bank, adapter = resolved
    assert tuple(sealed_bank["case_ids"]) == tuple(bank["case_ids"])
    assert tuple(sealed_bank["case_ids"]) != tuple(
        physical_pack.development_bank(challenge, version)["case_ids"]
    )
    assert adapter is not None


@pytest.mark.parametrize("kind", sorted({*CASES, *DEV_ONLY}))
def test_a_development_pack_resolves_to_the_development_path(kind, tmp_path):
    challenge, version, development, *_ = {**CASES, **DEV_ONLY}[kind]
    adapter = development()
    adapter.write_development_pack(tmp_path / "pack", **PLATFORM)
    snapshot = _parse(tmp_path / "pack", challenge, version)
    assert _resolve(snapshot, tmp_path / "pack", challenge, version, adapter) is None


@pytest.mark.parametrize("kind", sorted({*CASES, *DEV_ONLY}))
def test_a_pack_that_is_not_the_development_pack_never_falls_back_to_it(kind, tmp_path):
    """A pinned case bank that is not the development bank's, with no sealed batch to
    load (or one that is unreadable), refuses; it is never graded on the public bank."""
    challenge, version, development, *_ = {**CASES, **DEV_ONLY}[kind]
    adapter = development()
    root = tmp_path / "pack"
    manifest = adapter.write_development_pack(root, **PLATFORM)
    draft = json.loads(manifest.read_bytes())
    # a different case bank: prepare_pack pins what the file holds, so the pack no
    # longer positively equals the development bank
    (root / draft["private"]["case_bank"]["path"]).write_bytes(b"another case bank")
    snapshot = _parse(root, challenge, version)
    with pytest.raises(source.SealedBankRefused):
        _resolve(snapshot, root, challenge, version, adapter)
    (root / source.SEALED_BATCH_FILE).write_bytes(b"{}")  # unreadable batch
    with pytest.raises(source.SealedBankRefused) as caught:
        _resolve(snapshot, root, challenge, version, adapter)
    assert caught.value.code == "sealed_bank_malformed"


def test_a_pack_with_no_pinned_case_bank_is_unresolved_never_development(tmp_path):
    from types import SimpleNamespace

    for entry in (None, {"kind": "hidden_batch_store"}, {"sha256": 7}):
        snapshot = SimpleNamespace(
            private={} if entry is None else {"case_bank": entry}
        )
        with pytest.raises(source.SealedBankRefused) as caught:
            _resolve(snapshot, tmp_path, f08_dual_pack.CHALLENGE, "1.4", None)
        assert caught.value.code == "sealed_pack_unresolved"
