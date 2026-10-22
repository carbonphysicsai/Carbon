"""An F08 sealed batch becomes a private bank in the development bank's own
format (Validator, 2026-10-20), or a typed refusal; never a partial exam."""

from __future__ import annotations

import copy

import pytest
from test_f08_hidden_family import document, ok_record

from carbon.challenge_kit import f08_sealed_pack as sealed
from carbon.challenge_kit import physical_pack
from carbon.f08.domain import LIMIT_MM_PER_N

F08 = ("f08-ribbed-bracket", "1.2")


def batch(seed=11):
    doc = document(seed)
    records = []
    for i, case in enumerate(doc["cases"]):
        # Synthetic, non-production values: alternate sides of the limit.
        worst = LIMIT_MM_PER_N + (0.004 if i % 2 else -0.004) + 1e-5 * i
        record = ok_record(case["inputs"], worst=worst)
        record["case_id"] = case["case_id"]
        record["rungs"] = {
            tag: {"stop_reason": "exit", "exit": 0, "wall_s": w}
            for tag, w in (("h3", 80.0), ("h2.25", 200.0), ("h1.7", 964.2))
        }
        records.append(record)
    return doc, records


def test_the_bank_has_the_development_banks_shape():
    doc, records = batch()
    mine = sealed.sealed_bank(doc, records)
    theirs = physical_pack.development_bank(*F08)
    assert set(mine) == set(theirs)
    assert mine["cohorts"] == theirs["cohorts"] == ("decision_near_limit",) * 8
    assert mine["inputs"].dtype == theirs["inputs"].dtype
    assert mine["inputs"].shape == theirs["inputs"].shape
    assert mine["references"].shape == theirs["references"].shape
    assert not mine["references"].flags.writeable
    for a, b in zip(
        mine["reference_records"], theirs["reference_records"], strict=True
    ):
        assert set(a) - {"condition_id"} == set(b)  # the one additive key (C3)
        assert a["condition_id"] == "condition-0"
        assert set(a["observed"]) == set(b["observed"])
        assert set(a["damping"]) == set(b["damping"])
        # Sealed records carry the pinned rebuild; the ladder bank keeps
        # RR-PACKS-07's lost build, whose 8 rows the rebuild reproduces
        # bit for bit (f08-rebuild-20261021).
        assert a["image"]["kind"] == b["image"]["kind"] == "calculix"
        assert a["image"]["solvers"]["gmsh"] == b["image"]["solvers"]["gmsh"]
        assert a["image"]["solvers"]["ccx"]["sha256"].startswith("cdd00603")
        assert b["image"]["solvers"]["ccx"]["sha256"].startswith("21edfdcb")
    first = mine["reference_records"][0]
    assert first["wall_s"] == 964.2  # the reference rung's own
    assert mine["references"][0][1] == pytest.approx(
        records[0]["damping"]["zeta_0.005"]["worst_mm_per_n"]
    )


def test_private_roles_are_written_as_the_development_packs():
    theirs = physical_pack.development_bank(*F08)
    assert sealed.private_roles(theirs) == physical_pack._development_private_roles(
        *F08
    )


def test_roles_are_written_once_into_an_empty_directory(tmp_path):
    bank = sealed.sealed_bank(*batch())
    entries = sealed.write_private_roles(tmp_path / "pack", bank)
    roles = sealed.private_roles(bank)
    for role, entry in entries.items():
        assert (tmp_path / "pack" / entry["path"]).read_bytes() == roles[role]
    with pytest.raises(sealed.SealedPackRefused) as refused:
        sealed.write_private_roles(tmp_path / "pack", bank)
    assert refused.value.code == "f08_sealed_pack_not_empty"


def _refusal(doc, records):
    with pytest.raises(sealed.SealedPackRefused) as refused:
        sealed.sealed_bank(doc, records)
    return refused.value.code


def test_an_exam_is_the_whole_batch_or_nothing():
    doc, records = batch()
    assert _refusal(doc, records[:7]) == "f08_sealed_case_unresolved"
    invalid = copy.deepcopy(records)
    invalid[3] = {k: invalid[3][k] for k in ("case_id", "inputs", "image")} | {
        "status": "REFERENCE_INVALID"
    }
    assert _refusal(doc, invalid) == "f08_sealed_case_unresolved"
    assert _refusal(doc, records + [records[0]]) == "f08_sealed_records_mismatch"


def test_the_development_banks_checks_hold():
    doc, records = batch()
    side = copy.deepcopy(records)
    worst = side[0]["outputs"]["worst_dynamic_mm_per_n"]
    side[0]["rung_worst_dynamic_mm_per_n"]["h3"] = LIMIT_MM_PER_N + 0.01
    assert worst <= LIMIT_MM_PER_N
    assert _refusal(doc, side) == "f08_sealed_rungs_disagree"
    one_side = copy.deepcopy(records)
    for i, record in enumerate(one_side):
        safe = ok_record(record["inputs"], worst=LIMIT_MM_PER_N - 0.01)
        one_side[i] = {**record, **{k: safe[k] for k in safe if k != "inputs"}}
    assert _refusal(doc, one_side) == "f08_sealed_no_straddle"
    ladder = copy.deepcopy(records)
    ladder[2]["outputs"]["mode_ladder"] = {"verdict": "FAIL"}
    assert _refusal(doc, ladder) == "f08_sealed_record_malformed"
    no_wall = copy.deepcopy(records)
    del no_wall[1]["rungs"]
    assert _refusal(doc, no_wall) == "f08_sealed_no_measured_reference_rung"


def test_only_f08_1_2_is_packed():
    with pytest.raises(sealed.SealedPackRefused):
        sealed.sealed_bank(*batch(), version="1.1")
