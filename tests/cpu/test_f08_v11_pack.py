"""F08 1.1: TRAIN v2 (v1 + the N1r near-limit stratum) and the straddling
ladder exam, beside an unchanged 1.0."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from carbon.challenge_kit import f08_public, f08_train, physical_pack
from carbon.challenge_validator.evaluation_pack import prepare_pack

CID = f08_train.CHALLENGE_ID
REPOSITORY = Path(__file__).resolve().parents[2]
#: 1.0's construction kit at the base this version was added on.
KIT_1_0 = {
    "id": CID,
    "version": "1.0",
    "train_digest": "sha256:65eb6a5f4e95ab3e2120c78cf3cd6a60d37554934c7d7ddea71e53cdadaac947",
    "interface_digest": "sha256:7af2d3cc0c0c1759da859b8c37938802f0cf4ac8cae5193a7afef62cd94013bd",
    "construction_limits_digest": "sha256:88f56b8af03054a6002e92590784257df52580782b59c7a6bc019c17197725c3",
}  # fmt: skip


def test_version_1_0_is_unchanged():
    assert f08_public.construction_kit(CID, "1.0") == KIT_1_0
    assert f08_train.load_public_train()["inputs"].shape == (255, 6)


def test_train_v2_is_v1_then_the_near_limit_stratum():
    v1, v2 = f08_train.load_public_train("1.0"), f08_train.load_public_train("1.1")
    assert hashlib.sha256(v2["train"]).hexdigest() == f08_train.TRAIN_V2_SHA256
    assert v2["inputs"].shape == (287, 6) and v2["targets"].shape == (287, 7)
    assert np.array_equal(v2["inputs"][:255], v1["inputs"])
    assert np.array_equal(v2["targets"][:255], v1["targets"])
    assert v2["case_ids"][:255] == v1["case_ids"]
    assert v2["case_ids"][255:] == tuple(f"near-limit-{i:04d}" for i in range(32))
    assert not v2["inputs"].flags.writeable
    stratum = v2["provenance"]["near_limit_stratum"]
    assert stratum["measured_split"] == {"safe": 16, "unsafe": 16}
    # The worst dynamic peak is the larger tip peak (the lightest damping).
    worst = v2["targets"][255:, 1]
    assert (worst <= 0.15).sum() == 16
    assert v2["provenance"]["superseded_stratum"]["role"] == "HISTORY_NOT_TRAIN"
    assert v2["provenance"]["mesh"] == f08_train.TRAIN_MESH_STATEMENT


def test_train_v2_rederives_byte_for_byte_from_committed_sources():
    raw, provenance = f08_train.derive_public_train_v2(
        f08_train.load_public_train("1.0")["train"],
        f08_train.near_limit_sources(REPOSITORY),
    )
    assert raw == f08_train.load_public_train("1.1")["train"]
    assert (
        f08_train._canonical(provenance)
        == (f08_train._DATA / f08_train._PROVENANCE_V2).read_bytes()
    )


def test_train_v2_refuses_a_changed_source_or_split():
    sources = f08_train.near_limit_sources(REPOSITORY)
    v1 = f08_train.load_public_train("1.0")["train"]
    changed = dict(sources)
    changed["n1r-b0-observed.json"] = sources["n1r-b0-observed.json"] + b" "
    with pytest.raises(ValueError, match="source identity differs"):
        f08_train.derive_public_train_v2(v1, changed)
    with pytest.raises(ValueError, match="unknown public f08 TRAIN version"):
        f08_train.load_public_train("1.2")


def test_train_v2_refuses_changed_bytes(tmp_path, monkeypatch):
    for name in (
        f08_train._TRAIN,
        f08_train._PROVENANCE,
        f08_train._TRAIN_V2,
        f08_train._PROVENANCE_V2,
    ):
        (tmp_path / name).write_bytes((f08_train._DATA / name).read_bytes())
    raw = (tmp_path / f08_train._TRAIN_V2).read_bytes()
    (tmp_path / f08_train._TRAIN_V2).write_bytes(raw[:-1] + bytes([raw[-1] ^ 1]))
    monkeypatch.setattr(f08_train, "_DATA", tmp_path)
    with pytest.raises(ValueError, match="artifact identity differs"):
        f08_train.load_public_train("1.1")


def test_kit_1_1_binds_train_v2_and_states_the_mesh_shift():
    kit = f08_public.construction_kit(CID, "1.1")
    assert kit["train_digest"] == "sha256:" + f08_train.TRAIN_V2_SHA256
    assert kit["construction_limits_digest"] != KIT_1_0["construction_limits_digest"]
    limits = f08_public.construction_limits_document(CID, "1.1")
    assert limits["train_cases"] == 287
    assert limits["train_mesh"]["train_mesh_h_mm"] == 3.0
    assert limits["train_mesh"]["exam_reference_mesh_h_mm"] == 1.7
    assert limits["near_limit_action_evaluation_role"] == "EXCLUDED_ALL_32"
    assert limits["live_eligible"] is False


def test_ladder_bank_straddles_the_limit_and_packs(tmp_path):
    bank = physical_pack.development_bank(CID, "1.1")
    assert bank["case_ids"] == tuple(f"ladder-{i}" for i in range(8))
    assert set(bank["cohorts"]) == {"decision_near_limit"}
    assert bank["decision_coverage"] == "RANKING_AND_FEASIBILITY_STRADDLE"
    slices = f08_public.interface_document(CID, "1.1")["output"]["named_slices"]
    observed = json.loads(bank["solver_evidence"])
    tip = slices["peak_tip_z005_mm_per_n"][0]
    for i, case_id in enumerate(bank["case_ids"]):
        case = observed["cases"][f"pilot-000{i}-h1.7"]
        assert case["h_mm"] == 1.7
        assert bank["references"][i, tip] == np.float32(
            case["damping"]["zeta_0.005"]["worst_mm_per_n"]
        )
        assert bank["reference_records"][i]["case_id"] == case_id
    worst = [
        observed["cases"][f"pilot-000{i}-h1.7"]["worst_dynamic_mm_per_n"]
        for i in range(8)
    ]
    assert sum(w <= 0.15 for w in worst) == 4
    margin = min(abs(w - 0.15) for w in worst)
    limits = json.loads(
        physical_pack.public_roles(CID, "1.1")["important_limit_definition"]
    )
    assert limits["exam_straddle"]["smallest_margin_mm_per_n"] == round(margin, 5)
    assert limits["decision_coverage"] == "RANKING_AND_FEASIBILITY_STRADDLE"
    # The kit's TRAIN shift is far inside the smallest exam margin.
    assert (
        limits["train_mesh"]["worst_dynamic_shift_h3_minus_h17_mm_per_n"]["max_abs"]
        * 20
        < margin
    )
    pack = tmp_path / "f08-1.1"
    manifest = physical_pack.write_public_pack(
        pack, CID, "1.1", exposed_development_bank=True
    )
    body = json.loads(manifest.read_bytes())
    assert body["pack_version"] == "f08-normal-construction-development-2-exposed-bank"
    prepared = prepare_pack(
        pack,
        manifest.name,
        public_root=pack,
        private_root=pack,
        challenge_id=CID,
        challenge_version="1.1",
    )
    missing = prepared.snapshot.verify_available(pack, pack)
    assert set(missing["public"]) == {"accuracy_definition"}
    assert set(missing["private"]) == {"score_pack"}
    assert (pack / "public" / "train.npz").read_bytes() == (
        f08_train.load_public_train("1.1")["train"]
    )


def test_ladder_refuses_rows_that_differ_from_the_frozen_actions(monkeypatch):
    path, _ = physical_pack._F08_LADDER_ACTIONS
    monkeypatch.setattr(physical_pack, "_F08_LADDER_ACTIONS", (path, "0" * 64))
    with pytest.raises(ValueError):
        physical_pack.development_bank(CID, "1.1")


def test_no_train_v2_action_is_a_ladder_action():
    bank = physical_pack.development_bank(CID, "1.1")
    train = f08_train.load_public_train("1.1")["inputs"]
    exam = {tuple(row) for row in bank["inputs"].tolist()}
    assert not exam & {tuple(row) for row in train.tolist()}


def test_a_planted_train_exam_overlap_is_refused(monkeypatch):
    bank = physical_pack.development_bank(CID, "1.1")
    real = f08_train.load_public_train

    def planted(version=f08_train.CHALLENGE_VERSION):
        material = dict(real(version))
        if version != "1.1":
            return material
        inputs = np.array(material["inputs"])
        inputs[100] = bank["inputs"][3]
        material["inputs"] = inputs
        return material

    monkeypatch.setattr(f08_train, "load_public_train", planted)
    with pytest.raises(ValueError, match="exam action is a TRAIN action"):
        physical_pack.development_bank(CID, "1.1")
