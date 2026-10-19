"""The Motor normal-construction pack's public roles pass the receiver's own check."""

from __future__ import annotations

import json

import pytest

from carbon.challenge_kit import physical_pack, physical_public, physical_public_train
from carbon.challenge_validator import direct_receiver
from carbon.challenge_validator.evaluation_pack import (
    PUBLIC_ROLES,
    EvaluationPackUnavailable,
    prepare_pack,
)
from carbon.motor import challenge as motor

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
        physical_pack.public_roles("chip-cold-plate", "1.0")
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
