"""Two registered construction materials keep distinct sealed pack identities.

This is a DEVELOPMENT source-boundary test. Neither Challenge has a complete
qualified scoring packet in this fixture, so missing scientific roles stay
explicit and no verdict or ranking is produced.
"""

import json
from pathlib import Path

import pytest

from carbon.battery.construction_bundle_material import (
    bundle_material as battery_material,
)
from carbon.challenge_kit.synthetic_linear_field_2d import bundle_material_v5
from carbon.challenge_validator.direct_receiver import _pack_check, _sealed_pack
from carbon.challenge_validator.evaluation_pack import (
    PRIVATE_ROLES,
    PUBLIC_ROLES,
    SCHEMA,
    EvaluationPackUnavailable,
    load_pack,
    prepare_pack,
)
from carbon.development_session.data import write_once
from carbon.development_session.profile import canonical
from carbon.development_session.research_service import DirectFixtureDiscovery
from scripts.dev.battery.prepare_evaluation_pack_v1 import materialize_draft

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _sealed_material(tmp_path, material):
    challenge = material["challenge_key"]
    roots = {name: tmp_path / name for name in ("draft", "public", "private", "sealed")}
    for root in roots.values():
        root.mkdir(mode=0o700)
    (roots["public"] / "train.bin").write_bytes(material["train"])
    public = {role: "HUMAN_INPUT" for role in PUBLIC_ROLES}
    public.update(
        construction_kit={"inline": material["construction_kit"]},
        interface={"inline": material["interface_document"]},
        train={"path": "train.bin"},
        physics_contract={"inline": material["physics_contract"]},
    )
    manifest = {
        "schema": SCHEMA,
        "challenge": {"id": challenge.challenge_id, "version": challenge.version},
        "pack_version": "two-challenge-test-only",
        "public": public,
        "private": {role: "HUMAN_INPUT" for role in PRIVATE_ROLES},
    }
    (roots["draft"] / "pack.json").write_bytes(canonical(manifest))
    selection = {
        "root": str(roots["draft"]),
        "manifest": "pack.json",
        "public_root": str(roots["public"]),
        "private_root": str(roots["private"]),
    }
    selected = prepare_pack(
        roots["draft"],
        "pack.json",
        public_root=roots["public"],
        private_root=roots["private"],
        challenge_id=challenge.challenge_id,
        challenge_version=challenge.version,
    )
    relative = selected.snapshot.manifest_digest[7:] + ".json"
    write_once(roots["sealed"] / relative, selected.sealed_bytes)
    check = _pack_check(
        roots["sealed"],
        relative,
        selected.snapshot.manifest_digest,
        roots["public"],
        roots["private"],
        challenge,
    )
    return roots, selection, selected.snapshot, check


def test_operator_battery_v1_draft_binds_served_material_without_scoring(tmp_path):
    operator_root = tmp_path / "operator"
    prepared = materialize_draft(operator_root)
    snapshot = prepared.snapshot
    material = battery_material()
    assert (snapshot.challenge_id, snapshot.challenge_version) == (
        material["challenge_key"].challenge_id,
        material["challenge_key"].version,
    )
    assert snapshot.missing_roles() == {
        "public": (
            "accuracy_definition",
            "design_objective",
            "important_limit_definition",
        ),
        "private": tuple(sorted(PRIVATE_ROLES | {"source_registration"})),
    }
    sealed_root = tmp_path / "sealed"
    sealed_root.mkdir()
    sealed_name = snapshot.manifest_digest[7:] + ".json"
    write_once(sealed_root / sealed_name, prepared.sealed_bytes)
    _pack_check(
        sealed_root,
        sealed_name,
        snapshot.manifest_digest,
        REPOSITORY_ROOT,
        operator_root,
        material["challenge_key"],
    )(material)
    assert "private" not in snapshot.public_projection()
    assert "reference_rows" not in json.dumps(snapshot.public_projection())


def test_operator_battery_v1_draft_refuses_repository_destination():
    with pytest.raises(ValueError, match="outside the repository"):
        materialize_draft(REPOSITORY_ROOT / "docs")


@pytest.mark.parametrize("kind", ("synthetic", "battery"))
def test_two_challenges_bind_own_sealed_pack_and_keep_scoring_roles_closed(
    tmp_path, kind
):
    material = battery_material() if kind == "battery" else bundle_material_v5()
    other = bundle_material_v5() if kind == "battery" else battery_material()
    roots, selection, snapshot, check = _sealed_material(tmp_path, material)
    challenge = material["challenge_key"]

    discovery = DirectFixtureDiscovery(material, task_admission=True, pack_check=check)
    discovery._checked(discovery.info.challenge_key)
    assert snapshot.challenge_id == challenge.challenge_id
    assert snapshot.challenge_version == challenge.version
    assert (
        snapshot.read_role(roots["public"], "public", "train", max_bytes=16 * 1024**2)
        == material["train"]
    )
    assert (
        snapshot.read_json_role(roots["public"], "public", "interface", max_bytes=65536)
        == material["interface_document"]
    )
    assert (
        snapshot.read_json_role(
            roots["public"], "public", "physics_contract", max_bytes=65536
        )
        == material["physics_contract"]
    )
    assert snapshot.missing_roles() == {
        "public": tuple(
            sorted(
                {
                    "accuracy_definition",
                    "important_limit_definition",
                    "design_objective",
                }
            )
        ),
        "private": tuple(sorted(PRIVATE_ROLES)),
    }
    with pytest.raises(EvaluationPackUnavailable, match="role_unavailable"):
        snapshot.read_source_registration(roots["private"])
    projection = snapshot.public_projection()
    assert projection["challenge"] == {
        "id": challenge.challenge_id,
        "version": challenge.version,
    }
    assert "private" not in projection and "manifest_digest" not in projection
    assert "case_bank" not in json.dumps(projection)

    with pytest.raises(EvaluationPackUnavailable, match="construction_mismatch"):
        check(other)
    with pytest.raises(EvaluationPackUnavailable, match="identity"):
        load_pack(
            roots["sealed"],
            snapshot.manifest_digest[7:] + ".json",
            expected_digest=snapshot.manifest_digest,
            challenge_id=other["challenge_key"].challenge_id,
            challenge_version=other["challenge_key"].version,
        )

    receiver_root = tmp_path / "receiver"
    receiver_root.mkdir(mode=0o700)
    sealed_digest, sealed_check, _ = _sealed_pack(receiver_root, selection, challenge)
    assert sealed_digest == snapshot.manifest_digest
    sealed_check(material)
    write_once(
        receiver_root / "receiver-binding.json",
        canonical({"evaluation_pack_digest": sealed_digest}),
    )
    changed_draft = json.loads((roots["draft"] / "pack.json").read_bytes())
    changed_draft["pack_version"] = "changed-after-admission"
    (roots["draft"] / "pack.json").write_bytes(canonical(changed_draft))
    restarted_digest, restarted_check, _ = _sealed_pack(
        receiver_root, selection, challenge
    )
    assert restarted_digest == sealed_digest
    restarted_check(material)

    (roots["public"] / "train.bin").write_bytes(b"changed")
    with pytest.raises(EvaluationPackUnavailable, match="artifact.digest_mismatch"):
        restarted_check(material)
