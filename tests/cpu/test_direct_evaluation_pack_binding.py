"""Opt-in direct receiver keeps one sealed Challenge pack through task use."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from test_direct_v3_durable_tasks import _fixture

from carbon.challenge_kit.synthetic_linear_field_2d import bundle_material_v5
from carbon.challenge_validator.direct_receiver import _pack_check, _sealed_pack
from carbon.challenge_validator.evaluation_pack import (
    PRIVATE_ROLES,
    PUBLIC_ROLES,
    SCHEMA,
    EvaluationPackUnavailable,
    prepare_pack,
)
from carbon.challenge_validator.lean_recipe import LeanRecipeAdapter
from carbon.challenge_validator.lean_recipe_retention import (
    RetentionUnavailable,
    _retain_private_pack_binding,
)
from carbon.challenge_validator.ledger import AttemptLedger
from carbon.development_session.construction_recipe import ConstructionRecipe
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


def test_private_retention_sidecar_binds_owner_campaign_and_task(tmp_path):
    digest = "sha256:" + "a" * 64
    task_id = "rtsk_" + "b" * 64
    campaign = {
        "campaign_id": "direct-test-only",
        "receiver_binding": {"evaluation_pack_digest": digest},
    }
    database = tmp_path / "ledger.sqlite3"
    with sqlite3.connect(database) as db:
        db.execute("CREATE TABLE campaign (id INTEGER PRIMARY KEY, manifest TEXT)")
        db.execute("INSERT INTO campaign VALUES (1, ?)", (json.dumps(campaign),))

    class Ledger:
        @contextmanager
        def db(self):
            with sqlite3.connect(database) as connection:
                yield connection

    challenge = SimpleNamespace(challenge_id="test-challenge", version="1.0")
    discovery = SimpleNamespace(
        info=SimpleNamespace(challenge_key=challenge),
        evaluation_pack_digest=digest,
        _checked=lambda key: (key, None),
    )
    adapter = SimpleNamespace(
        discovery=discovery,
        challenge_id=challenge.challenge_id,
        challenge_version=challenge.version,
    )
    provider = SimpleNamespace(evaluation_pack_digest=digest, ledger=Ledger())
    task = SimpleNamespace(
        terminal_receipt=SimpleNamespace(
            state_digest="sha256:" + "c" * 64,
            predictions_digest="sha256:" + "d" * 64,
        )
    )
    artifact_root = tmp_path / task_id
    artifact_root.mkdir(mode=0o700)
    result = {
        "artifact_path": artifact_root,
        "entry_id": "sha256:" + "f" * 64,
        "official_eligible": False,
    }
    retained = _retain_private_pack_binding(adapter, provider, task_id, task, result)
    assert retained["evaluation_pack_digest"] == digest
    assert retained["official_eligible"] is False
    sidecar = json.loads(retained["evaluation_pack_binding_path"].read_bytes())
    assert sidecar["task_id"] == task_id
    assert sidecar["campaign_id"] == campaign["campaign_id"]
    assert sidecar["evaluation_pack_digest"] == digest
    assert sidecar["entry_id"] == result["entry_id"]
    assert (
        _retain_private_pack_binding(adapter, provider, task_id, task, result)
        == retained
    )
    provider.evaluation_pack_digest = "sha256:" + "e" * 64
    with pytest.raises(RetentionUnavailable, match="task_binding_changed"):
        _retain_private_pack_binding(adapter, provider, task_id, task, result)
    provider.evaluation_pack_digest = None
    with pytest.raises(RetentionUnavailable, match="task_binding_changed"):
        _retain_private_pack_binding(adapter, provider, task_id, task, result)
    discovery.evaluation_pack_digest = None
    assert (
        _retain_private_pack_binding(adapter, provider, task_id, task, result) is result
    )


def test_pack_pin_changes_private_task_identity_without_public_contract_change(
    tmp_path, monkeypatch
):
    request, provider_factory, discovery = _fixture(
        tmp_path, monkeypatch, material=bundle_material_v5()
    )
    provider = provider_factory()
    try:
        attempts = tmp_path / "attempts"
        attempts.mkdir(mode=0o700)
        adapter = LeanRecipeAdapter(
            discovery,
            lambda owner: provider if owner == "miner" else None,
            AttemptLedger(attempts / "ledger.sqlite3"),
        )
        recipe = ConstructionRecipe.from_dict(request.recipe)
        historical = adapter._request("miner", recipe)
        selected = adapter._request(
            "miner", recipe, evaluation_pack_digest="sha256:" + "a" * 64
        )
        assert historical.idempotency_key != selected.idempotency_key
        assert "evaluation_pack_digest" not in adapter.identities()
    finally:
        provider.close()
