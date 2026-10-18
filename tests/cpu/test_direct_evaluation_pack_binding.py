"""Opt-in direct receiver keeps one sealed Challenge pack through task use."""

from __future__ import annotations

import json

import pytest

from carbon.challenge_kit.synthetic_linear_field_2d import bundle_material_v5
from carbon.challenge_validator.direct_receiver import _pack_check, _sealed_pack
from carbon.challenge_validator.evaluation_pack import (
    PRIVATE_ROLES,
    PUBLIC_ROLES,
    SCHEMA,
    EvaluationPackUnavailable,
    prepare_pack,
)
from carbon.development_session.data import write_once
from carbon.development_session.profile import canonical
from carbon.development_session.research_service import DirectFixtureDiscovery


def _bound(tmp_path, *, altered_kit=False):
    material = bundle_material_v5()
    challenge = material["challenge_key"]
    draft = tmp_path / "draft"
    public = tmp_path / "public"
    private = tmp_path / "private"
    sealed = tmp_path / "sealed"
    for path in (draft, public, private, sealed):
        path.mkdir(mode=0o700)
    (public / "train.bin").write_bytes(material["train"])
    kit = dict(material["construction_kit"])
    if altered_kit:
        kit["id"] = "wrong-challenge"
    roles = {name: "HUMAN_INPUT" for name in PUBLIC_ROLES}
    roles.update(
        construction_kit={"inline": kit},
        interface={"inline": material["interface_document"]},
        train={"path": "train.bin"},
        physics_contract={"inline": material["physics_contract"]},
    )
    body = {
        "schema": SCHEMA,
        "challenge": {"id": challenge.challenge_id, "version": challenge.version},
        "pack_version": "test-only",
        "public": roles,
        "private": {name: "HUMAN_INPUT" for name in PRIVATE_ROLES},
    }
    (draft / "evaluation-pack.json").write_text(json.dumps(body), encoding="utf-8")
    prepared = prepare_pack(
        draft,
        "evaluation-pack.json",
        public_root=public,
        private_root=private,
        challenge_id=challenge.challenge_id,
        challenge_version=challenge.version,
    )
    relative = prepared.snapshot.manifest_digest[7:] + ".json"
    write_once(sealed / relative, prepared.sealed_bytes)
    check = _pack_check(
        sealed,
        relative,
        prepared.snapshot.manifest_digest,
        public,
        private,
        challenge,
    )
    selection = {
        "root": str(draft),
        "manifest": "evaluation-pack.json",
        "public_root": str(public),
        "private_root": str(private),
    }
    return material, public, check, selection


def test_sealed_pack_rechecked_when_fixed_train_changes(tmp_path):
    material, public, check, _selection = _bound(tmp_path)
    discovery = DirectFixtureDiscovery(material, task_admission=True, pack_check=check)
    discovery._checked(discovery.info.challenge_key)
    (public / "train.bin").write_bytes(b"changed")
    with pytest.raises(EvaluationPackUnavailable, match="artifact.digest_mismatch"):
        discovery._checked(discovery.info.challenge_key)


def test_pack_must_match_registered_construction_content(tmp_path):
    material, _public, check, _selection = _bound(tmp_path, altered_kit=True)
    with pytest.raises(EvaluationPackUnavailable, match="construction_mismatch"):
        DirectFixtureDiscovery(material, task_admission=True, pack_check=check)


def test_restart_uses_original_sealed_pack_after_draft_edit(tmp_path):
    material, _public, _check, selection = _bound(tmp_path)
    receiver_root = tmp_path / "receiver"
    receiver_root.mkdir(mode=0o700)
    challenge = material["challenge_key"]
    digest, check = _sealed_pack(receiver_root, selection, challenge)
    check(material)
    write_once(
        receiver_root / "receiver-binding.json",
        canonical({"evaluation_pack_digest": digest}),
    )
    draft = tmp_path / "draft" / "evaluation-pack.json"
    changed = json.loads(draft.read_text(encoding="utf-8"))
    changed["pack_version"] = "edited-after-admission"
    draft.write_text(json.dumps(changed), encoding="utf-8")
    restarted_digest, restarted_check = _sealed_pack(
        receiver_root, selection, challenge
    )
    assert restarted_digest == digest
    restarted_check(material)
    (receiver_root / "evaluation-packs" / (digest[7:] + ".json")).unlink()
    with pytest.raises(EvaluationPackUnavailable):
        _sealed_pack(receiver_root, selection, challenge)
