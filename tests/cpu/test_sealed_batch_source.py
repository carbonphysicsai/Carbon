"""E4: a sealed pack is graded on its carried sealed batch, never on the
development bank (Validator ruling, carriage (a))."""

from __future__ import annotations

import hashlib
from types import SimpleNamespace

import pytest
import random

from test_motor_sealed_family import records_for

from carbon.challenge_kit import motor_sealed_pack as pack
from carbon.challenge_validator import motor_sealed_grid as grid
from carbon.motor_grid_exam import population
from carbon.challenge_kit import physical_pack
from carbon.scoring import motor_dual_pack as dev
from carbon.scoring import sealed_batch_source as source

MOTOR = source.MOTOR
VERSION = "1.3"


def _sha(body):
    return "sha256:" + hashlib.sha256(body).hexdigest()


def _snapshot(case_bank_bytes):
    return SimpleNamespace(private={"case_bank": {"sha256": _sha(case_bank_bytes)}})


@pytest.fixture(scope="module")
def batch():
    cases, _ = population.draw(random.Random(3), population.CELLS)
    doc = {
        "schema": grid.DOCUMENT_SCHEMA,
        "challenge": {"id": MOTOR, "version": "1.1"},
        "role": "grid",
        "kind": "screening",
        "population": population.POPULATION_VERSION,
        "cases": [{"case_id": f"g{i:02d}", "inputs": c} for i, c in enumerate(cases)],
    }
    records = records_for(doc)
    bank = pack.grid_bank(doc, records)
    return doc, records, pack.private_roles(bank)["case_bank"]


def _resolve(snapshot, root):
    return source.resolve(
        challenge=MOTOR,
        version=VERSION,
        selected_pack=snapshot,
        private_root=root,
        development_adapter=dev.adapter(VERSION) if hasattr(dev, "adapter") else None,
    )


def test_a_development_pack_keeps_the_development_path(tmp_path):
    development = physical_pack.development_bank(MOTOR, VERSION)
    roles = pack.private_roles(development)
    assert _resolve(_snapshot(roles["case_bank"]), tmp_path) is None


def test_a_sealed_pack_without_its_batch_fails_closed(tmp_path, batch):
    with pytest.raises(source.SealedBankRefused) as caught:
        _resolve(_snapshot(batch[2]), tmp_path)
    assert caught.value.code == "sealed_bank_missing"


def test_a_sealed_pack_with_its_batch_loads_the_sealed_bank(tmp_path, batch):
    doc, records, case_bank = batch
    (tmp_path / source.SEALED_BATCH_FILE).write_bytes(source.batch_bytes(doc, records))
    bank, adapter = _resolve(_snapshot(case_bank), tmp_path)
    assert bank["case_ids"] == pack.grid_bank(doc, records)["case_ids"]
    assert adapter is not None


def test_a_batch_that_is_not_the_packs_is_refused(tmp_path, batch):
    doc, records, _case_bank = batch
    (tmp_path / source.SEALED_BATCH_FILE).write_bytes(source.batch_bytes(doc, records))
    other = _snapshot(b"not this pack")
    with pytest.raises(source.SealedBankRefused) as caught:
        _resolve(other, tmp_path)
    assert caught.value.code == "sealed_bank_mismatch"


def test_a_malformed_batch_file_is_refused(tmp_path, batch):
    (tmp_path / source.SEALED_BATCH_FILE).write_bytes(b"{}")
    with pytest.raises(source.SealedBankRefused) as caught:
        _resolve(_snapshot(batch[2]), tmp_path)
    assert caught.value.code == "sealed_bank_malformed"
