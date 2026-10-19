"""The Motor normal-construction pack's public roles pass the receiver's own check."""

from __future__ import annotations

import json

import numpy as np
import pytest

from carbon.challenge_kit import physical_pack, physical_public, physical_public_train
from carbon.challenge_validator import direct_receiver
from carbon.challenge_validator.evaluation_pack import (
    PUBLIC_ROLES,
    EvaluationPackUnavailable,
    prepare_pack,
)
from carbon.motor import challenge as motor
from carbon.motor import domain as motor_domain

MOTOR = motor.CHALLENGE.challenge_id
VERSION = motor.CHALLENGE.version


def _material() -> dict:
    """The construction-side documents the receiver compares a pack against."""
    return {
        "construction_kit": physical_public.construction_kit(MOTOR, VERSION),
        "interface_document": physical_public.interface_document(MOTOR, VERSION),
        "physics_contract": physical_pack.physics_contract(MOTOR, VERSION),
        "train": physical_public_train.load_public_train(MOTOR)["train"],
    }


def _sealed(tmp_path):
    pack = tmp_path / "pack"
    manifest = physical_pack.write_public_pack(pack, MOTOR, VERSION)
    prepared = prepare_pack(
        pack,
        manifest.name,
        public_root=pack,
        private_root=pack,
        challenge_id=MOTOR,
        challenge_version=VERSION,
    )
    sealed = tmp_path / "sealed"
    sealed.mkdir()
    name = prepared.snapshot.manifest_digest[7:] + ".json"
    (sealed / name).write_bytes(prepared.sealed_bytes)
    return pack, sealed, name, prepared.snapshot


def test_every_public_role_is_supplied_and_private_roles_stay_human_input(tmp_path):
    _, _, _, snapshot = _sealed(tmp_path)
    assert set(snapshot.public) == PUBLIC_ROLES
    assert all(entry != "HUMAN_INPUT" for entry in snapshot.public.values())
    assert dict(snapshot.private) == {
        role: "HUMAN_INPUT" for role in physical_pack.PRIVATE_ROLES
    }
    assert snapshot.pack_version == "motor-normal-construction-development-1"


def test_the_receivers_own_pack_check_accepts_the_construction_material(tmp_path):
    pack, sealed, name, snapshot = _sealed(tmp_path)
    check = direct_receiver._pack_check(
        sealed, name, snapshot.manifest_digest, pack, pack, motor.CHALLENGE
    )
    check(_material())  # raises on any construction or train mismatch


@pytest.mark.parametrize(
    ("field", "code"),
    [
        ("construction_kit", "evaluation_pack.construction_mismatch"),
        ("physics_contract", "evaluation_pack.construction_mismatch"),
        ("train", "evaluation_pack.train_mismatch"),
    ],
)
def test_a_different_construction_material_is_refused(tmp_path, field, code):
    pack, sealed, name, snapshot = _sealed(tmp_path)
    check = direct_receiver._pack_check(
        sealed, name, snapshot.manifest_digest, pack, pack, motor.CHALLENGE
    )
    material = _material()
    if field == "train":
        material["train"] = material["train"] + b"\0"
    else:
        material[field] = {**material[field], "version": "other"}
    with pytest.raises(EvaluationPackUnavailable) as refused:
        check(material)
    assert refused.value.code == code


def test_an_edited_role_after_sealing_is_refused(tmp_path):
    pack, _, _, snapshot = _sealed(tmp_path)
    (pack / "public" / "design_objective.json").write_bytes(b"{}")
    with pytest.raises(EvaluationPackUnavailable):
        snapshot.verify_available(pack, pack)


def test_roles_are_the_pinned_bytes_and_the_kit_binds_the_npz(tmp_path):
    roles = physical_pack.public_roles(MOTOR, VERSION)
    kit = json.loads(roles["construction_kit"])
    assert set(kit) == {
        "id",
        "version",
        "train_digest",
        "interface_digest",
        "construction_limits_digest",
    }
    assert (
        kit["train_digest"]
        == physical_public_train.load_public_train(MOTOR)["provenance"]["train_sha256"]
    )
    assert roles["train"][:2] == b"PK"  # the NPZ derivative, not the native JSONL


def test_a_changed_pinned_file_or_unknown_challenge_is_refused(tmp_path, monkeypatch):
    with pytest.raises(ValueError):
        physical_pack.public_roles("f02-unknown", "1.0")
    with pytest.raises(ValueError):
        physical_pack.public_roles(MOTOR, "9.9")
    copy = tmp_path / "data"
    copy.mkdir()
    for path in physical_pack._DATA.iterdir():
        (copy / path.name).write_bytes(path.read_bytes())
    target = copy / "motor-design-objective-20261018.json"
    target.write_bytes(target.read_bytes() + b" ")
    monkeypatch.setattr(physical_pack, "_DATA", copy)
    with pytest.raises(ValueError, match="pinned design_objective"):
        physical_pack.public_roles(MOTOR, VERSION)


def test_an_existing_pack_directory_is_never_overwritten(tmp_path):
    physical_pack.write_public_pack(tmp_path / "p", MOTOR, VERSION)
    with pytest.raises(ValueError):
        physical_pack.write_public_pack(tmp_path / "p", MOTOR, VERSION)


def test_the_motor_bank_carries_the_three_registered_cohorts_in_order():
    bank = physical_pack.development_bank(MOTOR, VERSION)
    assert len(bank["case_ids"]) == 90
    assert bank["case_ids"][0] == "practice-0000"
    assert bank["case_ids"][30:34] == (
        "difficult-1-deep-saturation",
        "difficult-2-sharpest-cogging",
        "difficult-3-weakest-field",
        "difficult-4-field-weakening",
    )
    assert bank["case_ids"][42:44] == ("decision-d01-r01", "decision-d01-r02")
    counts = {c: bank["cohorts"].count(c) for c in set(bank["cohorts"])}
    assert counts == {
        "practice": 30,
        "pilot_ordinary": 8,
        "pilot_difficult": 4,
        "decision_representative": 32,
        "decision_boundary_stress": 16,
    }
    assert bank["inputs"].shape == (90, 8) and bank["inputs"].dtype == "<f8"
    assert bank["references"].shape == (90, 60)
    first = dict(zip(motor_domain.INPUTS, bank["inputs"][42], strict=True))
    assert first["current_density_a_mm2"] == 8.0 and first["airgap_mm"] == 0.4
    assert [r["case_id"] for r in bank["reference_records"]] == list(bank["case_ids"])


def test_the_exposed_bank_case_bank_is_the_scored_query_byte_for_byte(tmp_path):
    from carbon.development_session.bundle_construction_worker import _tensors

    pack = tmp_path / "pack"
    manifest = physical_pack.write_public_pack(
        pack, MOTOR, VERSION, exposed_development_bank=True
    )
    prepared = prepare_pack(
        pack,
        manifest.name,
        public_root=pack,
        private_root=pack,
        challenge_id=MOTOR,
        challenge_version=VERSION,
    )
    snapshot = prepared.snapshot
    missing = snapshot.verify_available(pack, pack)
    assert set(missing["private"]) == {"score_pack"}
    assert snapshot.pack_version.endswith("-exposed-bank")
    bank = physical_pack.development_bank(MOTOR, VERSION)
    # Retention scores the query _tensors(inputs=material["practice_inputs"]) and
    # requires it to equal the case bank; practice inputs are the bank's inputs.
    query = _tensors(inputs=np.array(bank["inputs"]))
    assert snapshot.read_role(pack, "private", "case_bank", max_bytes=1 << 24) == query
    rows = snapshot.read_json_role(pack, "private", "reference_rows", max_bytes=1 << 24)
    assert type(rows) is list and len(rows) == 90
    assert rows[30]["cohort"] == "pilot_difficult" and rows[30]["row"] == 30
    solver = snapshot.read_json_role(
        pack, "private", "solver_evidence", max_bytes=65536
    )
    assert solver == json.loads(bank["solver_evidence"])


def test_a_changed_development_bank_source_is_refused(monkeypatch):
    banks = {MOTOR: dict(physical_pack._BANKS[MOTOR])}
    path, _ = banks[MOTOR]["references"]
    banks[MOTOR]["references"] = (path, "0" * 64)
    monkeypatch.setattr(physical_pack, "_BANKS", banks)
    with pytest.raises(ValueError, match="pinned development bank references"):
        physical_pack.development_bank(MOTOR, VERSION)


def test_cooling_bank_uses_its_interface_layout_and_unbound_roles_stay_open(tmp_path):
    from carbon.cold_plate import challenge as cooling

    cid, version = cooling.CHALLENGE.challenge_id, cooling.CHALLENGE.version
    bank = physical_pack.development_bank(cid, version)
    assert bank["inputs"].shape == (48, 9) and bank["references"].shape == (48, 32)
    first = bank["reference_records"][0]["outputs"]
    assert bank["references"][0, 0] == first["peak_c"]
    assert list(bank["references"][0, 1:31]) == first["profile_c"]
    assert bank["references"][0, 31] == first["pressure_drop_pa"]
    assert physical_pack.physics_contract(cid, version) is None
    pack = tmp_path / "cooling"
    manifest = physical_pack.write_public_pack(
        pack, cid, version, exposed_development_bank=True
    )
    prepared = prepare_pack(
        pack,
        manifest.name,
        public_root=pack,
        private_root=pack,
        challenge_id=cid,
        challenge_version=version,
    )
    missing = prepared.snapshot.verify_available(pack, pack)
    assert set(missing["public"]) == {"physics_contract", "accuracy_definition"}
    assert set(missing["private"]) == {"score_pack"}
