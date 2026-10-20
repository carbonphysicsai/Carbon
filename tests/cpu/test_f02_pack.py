"""F02 2.0: TRAIN40-v2, the decided S1 spread and the eight accepted cold
actions as a selectable DEVELOPMENT pack (OWNER-F02-TRAIN40-V2-01)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from carbon.challenge_kit import f02_public, f02_train, physical_pack
from carbon.challenge_validator.evaluation_pack import prepare_pack

CID, VERSION = f02_train.CHALLENGE_ID, f02_train.CHALLENGE_VERSION
REPOSITORY = Path(__file__).resolve().parents[2]


def test_train40_v2_is_pinned_and_rederives_byte_for_byte():
    material = f02_train.load_public_train()
    assert hashlib.sha256(material["train"]).hexdigest() == f02_train.TRAIN_SHA256
    assert material["inputs"].shape == (40, 2) and material["targets"].shape == (40, 1)
    assert not material["inputs"].flags.writeable
    raw, provenance = f02_train.derive_public_train(
        (REPOSITORY / f02_train.SOURCE[0]).read_bytes()
    )
    assert raw == material["train"]
    assert (
        f02_train._canonical(provenance)
        == (f02_train._DATA / f02_train._PROVENANCE).read_bytes()
    )
    assert provenance["strata"] == {
        "S1": {"at_or_below": 12, "above": 12},
        "S2": {"at_or_below": 0, "above": 16},
    }


def test_the_decided_spread_is_the_s1_population_std():
    rows = [
        json.loads(line)
        for line in (REPOSITORY / f02_train.SOURCE[0]).read_text().splitlines()
    ]
    s1 = [r["outputs"]["peak_top_c"] for r in rows if r["case_id"].endswith("v2s1")]
    assert len(s1) == 24
    std = f02_train.load_public_train()["train_peak_std_c"]
    assert std == pytest.approx(float(np.std(s1, ddof=0)), rel=1e-15)
    assert round(std, 3) == 6.701 == f02_train.TRAIN_PEAK_STD_RECORDED_C
    # Not the full-TRAIN figure the owner did not pick.
    assert round(float(np.std([r["outputs"]["peak_top_c"] for r in rows])), 3) == 16.704


def test_a_changed_source_or_version_refuses(tmp_path, monkeypatch):
    raw = (REPOSITORY / f02_train.SOURCE[0]).read_bytes()
    with pytest.raises(ValueError, match="source identity differs"):
        f02_train.derive_public_train(raw + b"\n")
    with pytest.raises(ValueError, match="unknown public f02 TRAIN version"):
        f02_train.load_public_train("1.0")
    with pytest.raises(ValueError, match="unknown public f02 Challenge identity"):
        f02_public.construction_kit(CID, "1.0")
    for name in (f02_train._TRAIN, f02_train._PROVENANCE):
        (tmp_path / name).write_bytes((f02_train._DATA / name).read_bytes())
    body = (tmp_path / f02_train._TRAIN).read_bytes()
    (tmp_path / f02_train._TRAIN).write_bytes(body[:-1] + bytes([body[-1] ^ 1]))
    monkeypatch.setattr(f02_train, "_DATA", tmp_path)
    with pytest.raises(ValueError, match="artifact identity differs"):
        f02_train.load_public_train()


def test_the_pack_actions_are_the_scoring_producers():
    from carbon.scoring import private_evaluation_source as producer

    assert physical_pack.F02_ACTIONS == producer._F02_ACTIONS


def test_bank_is_the_eight_accepted_primaries_and_straddles():
    bank = physical_pack.development_bank(CID, VERSION)
    assert bank["case_ids"] == tuple(sorted(physical_pack.F02_ACTIONS))
    assert bank["inputs"].shape == (8, 2) and bank["references"].shape == (8, 1)
    judgement = json.loads(bank["solver_evidence"])
    for i, case_id in enumerate(bank["case_ids"]):
        primary = judgement["observables"][case_id + "-primary"]
        assert bank["references"][i, 0] == np.float32(primary["peak_top_c"])
        assert tuple(bank["inputs"][i]) == physical_pack.F02_ACTIONS[case_id]
    peaks = bank["references"][:, 0]
    assert (peaks <= 95.0).sum() == 3 and (peaks > 95.0).sum() == 5
    assert bank["decision_coverage"] == "RANKING_AND_FEASIBILITY_STRADDLE"
    train = f02_train.load_public_train()["inputs"].tolist()
    assert not {tuple(r) for r in bank["inputs"].tolist()} & {tuple(r) for r in train}


def test_a_planted_train_exam_overlap_is_refused(monkeypatch):
    real = f02_train.load_public_train

    def planted(version=VERSION):
        material = dict(real(version))
        inputs = np.array(material["inputs"])
        inputs[7] = (85.0, 5.0)
        material["inputs"] = inputs
        return material

    monkeypatch.setattr(f02_train, "load_public_train", planted)
    with pytest.raises(ValueError, match="exam action is a TRAIN action"):
        physical_pack.development_bank(CID, VERSION)


def test_a_changed_judgement_refuses(monkeypatch):
    path, _ = physical_pack._F02_JUDGEMENT
    monkeypatch.setattr(physical_pack, "_F02_JUDGEMENT", (path, "0" * 64))
    with pytest.raises(ValueError):
        physical_pack.development_bank(CID, VERSION)


def test_kit_carries_the_spread_and_the_pack_prepares(tmp_path):
    limits = f02_public.construction_limits_document(CID, VERSION)
    assert limits["train_cases"] == 40
    assert limits["train_peak_std_c"]["recorded"] == 6.701
    assert limits["live_eligible"] is False and limits["accuracy_gate"] is None
    roles = physical_pack.public_roles(CID, VERSION)
    assert "accuracy_definition" not in roles  # scoring authority: HUMAN_INPUT
    design = json.loads(roles["design_objective"])
    assert design["design_policy_and_scales"] == physical_pack.UNAVAILABLE
    important = json.loads(roles["important_limit_definition"])
    assert important["constraints"] == {"peak_top_c_max": 95.0}
    pack = tmp_path / "f02"
    manifest = physical_pack.write_public_pack(
        pack, CID, VERSION, exposed_development_bank=True
    )
    body = json.loads(manifest.read_bytes())
    assert body["pack_version"] == "f02-normal-construction-development-2-exposed-bank"
    prepared = prepare_pack(
        pack,
        manifest.name,
        public_root=pack,
        private_root=pack,
        challenge_id=CID,
        challenge_version=VERSION,
    )
    missing = prepared.snapshot.verify_available(pack, pack)
    assert set(missing["public"]) == {"accuracy_definition"}
    assert set(missing["private"]) == {"score_pack"}
    assert (pack / "public" / "train.npz").read_bytes() == (
        f02_train.load_public_train()["train"]
    )


def test_the_construction_worker_admits_the_f02_kit_and_refuses_edits():
    from carbon.development_session.bundle_construction_worker import (
        verify_direct_resource_policy,
    )
    from carbon.development_session.construction_recipe import RecipeRefused

    kit = f02_public.construction_kit(CID, VERSION)
    limits = f02_public.construction_limits_document(CID, VERSION)
    assert (
        verify_direct_resource_policy(kit, limits) == kit["construction_limits_digest"]
    )
    changed = dict(limits, train_cases=41)
    with pytest.raises(RecipeRefused):
        verify_direct_resource_policy(kit, changed)
    with pytest.raises(RecipeRefused):
        verify_direct_resource_policy(
            dict(kit, train_digest="sha256:" + "0" * 64), limits
        )


def test_each_reference_carries_its_measured_primary_wall_time():
    bank = physical_pack.development_bank(CID, VERSION)
    ledger = [
        json.loads(line)
        for line in (REPOSITORY / physical_pack._F02_LEDGER[0]).read_text().splitlines()
    ]
    finished = {e["case"]: e for e in ledger if e.get("event") == "FINISHED"}
    for record in bank["reference_records"]:
        solve = finished[record["case_id"] + "-primary"]
        assert record["wall_s"] == solve["wall_s"] > 0
        assert solve["outcome"] == "COMPLETED" and solve["exit"] == 0
    assert [r["wall_s"] for r in bank["reference_records"]] == [
        224.033,
        167.579,
        184.539,
        166.959,
        168.551,
        166.014,
        164.61,
        167.224,
    ]
