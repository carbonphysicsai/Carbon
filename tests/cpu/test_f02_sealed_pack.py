"""An F02 sealed batch becomes a private bank in the development bank's own
format (Validator, 2026-10-20), or a typed refusal; never a partial exam."""

from __future__ import annotations

import copy
import random

import numpy as np
import pytest

from carbon.challenge_kit import f02_sealed_pack as sealed
from carbon.challenge_kit import f02_train, physical_pack
from carbon.challenge_validator import f02_hidden as hidden
from carbon.f02 import population

LIMIT = f02_train.LIMIT_C


def batch(seed=11):
    drawn = population.draw(random.Random(seed), 8)[0]
    document = {
        "schema": hidden.DOCUMENT_SCHEMA,
        "challenge": {"id": "f02", "version": "2.1"},
        "role": "exam",
        "kind": "cold_decision",
        "population": population.POPULATION_VERSION,
        "cases": [{"case_id": f"b-{i:02d}", "inputs": c} for i, c in enumerate(drawn)],
    }
    records = []
    for i, case in enumerate(document["cases"]):
        # Synthetic, non-production peaks: alternate sides of the limit.
        peak = LIMIT + (2.0 if i % 2 else -2.0) + 0.01 * i
        p, t = case["inputs"]["peak_w"], case["inputs"]["on_time_s"]
        records.append(
            {
                "case_id": case["case_id"],
                "status": "OK",
                "inputs": case["inputs"],
                "image": hidden.SOLVER_IMAGE,
                "outputs": {
                    "peak_top_c": peak,
                    "extra_energy_j": float((p - 20) * t),
                    "first_95c_crossing_s": None,
                    "peak_time_s": t + 0.5,
                    "recovery_s": 20.0,
                },
                "rung_peaks_c": {"primary": peak, "mesh2": peak + 0.01, "dt0.5": peak},
                "rung_comparison": {"pass": True, "primary_peak_c": peak},
                "rungs": {
                    tag: {"outcome": "EXITED", "exit": 0, "wall_s": 41.5}
                    for tag in sealed.RUNGS
                },
            }
        )
    return document, records


def test_the_bank_has_the_development_banks_shape():
    document, records = batch()
    mine = sealed.sealed_bank(document, records)
    theirs = physical_pack.development_bank("f02", "2.1")
    assert set(mine) == set(theirs)
    assert mine["cohorts"] == theirs["cohorts"] == ("decision_cold_eight",) * 8
    assert mine["inputs"].dtype == theirs["inputs"].dtype
    assert mine["inputs"].shape == theirs["inputs"].shape
    assert mine["references"].shape == theirs["references"].shape
    assert not mine["inputs"].flags.writeable
    for a, b in zip(
        mine["reference_records"], theirs["reference_records"], strict=True
    ):
        assert set(a) == set(b)
        assert set(a["observed"]) == set(b["observed"])
        assert set(a["rung_peaks_c"]) == set(b["rung_peaks_c"])
        assert a["context"] == b["context"]
    assert list(mine["case_ids"]) == sorted(mine["case_ids"])
    assert mine["reference_records"][0]["wall_s"] == 41.5  # the primary's own


def test_private_roles_are_written_as_the_development_packs():
    theirs = physical_pack.development_bank("f02", "2.1")
    assert sealed.private_roles(theirs) == physical_pack._development_private_roles(
        "f02", "2.1"
    )


def test_roles_are_written_once_into_an_empty_directory(tmp_path):
    document, records = batch()
    bank = sealed.sealed_bank(document, records)
    entries = sealed.write_private_roles(tmp_path / "pack", bank)
    assert set(entries) == {"case_bank", "reference_rows", "solver_evidence"}
    roles = sealed.private_roles(bank)
    for role, entry in entries.items():
        assert (tmp_path / "pack" / entry["path"]).read_bytes() == roles[role]
    with pytest.raises(sealed.SealedPackRefused) as refused:
        sealed.write_private_roles(tmp_path / "pack", bank)
    assert refused.value.code == "f02_sealed_pack_not_empty"


def _refusal(document, records):
    with pytest.raises(sealed.SealedPackRefused) as refused:
        sealed.sealed_bank(document, records)
    return refused.value.code


def test_an_exam_is_the_whole_batch_or_nothing():
    document, records = batch()
    assert _refusal(document, records[:7]) == "f02_sealed_case_unresolved"
    invalid = copy.deepcopy(records)
    invalid[3] = {k: invalid[3][k] for k in ("case_id", "inputs", "image")} | {
        "status": "REFERENCE_INVALID"
    }
    assert _refusal(document, invalid) == "f02_sealed_case_unresolved"
    twice = copy.deepcopy(records) + [copy.deepcopy(records[0])]
    assert _refusal(document, twice) == "f02_sealed_records_mismatch"


def test_the_development_banks_checks_hold():
    document, records = batch()
    side = copy.deepcopy(records)
    peak = LIMIT - 0.005
    side[0]["outputs"]["peak_top_c"] = peak
    side[0]["rung_peaks_c"] = {"primary": peak, "mesh2": LIMIT + 0.01, "dt0.5": peak}
    side[0]["rung_comparison"]["primary_peak_c"] = peak
    assert _refusal(document, side) == "f02_sealed_rungs_disagree"
    energy = copy.deepcopy(records)
    energy[1]["outputs"]["extra_energy_j"] += 1.0
    assert _refusal(document, energy) == "f02_sealed_energy_differs"
    one_side = copy.deepcopy(records)
    for record in one_side:
        p = LIMIT - 3.0
        record["outputs"]["peak_top_c"] = p
        record["rung_peaks_c"] = {"primary": p, "mesh2": p, "dt0.5": p}
        record["rung_comparison"]["primary_peak_c"] = p
    assert _refusal(document, one_side) == "f02_sealed_no_straddle"
    image = copy.deepcopy(records)
    image[2]["image"] = "sha256:" + "0" * 64
    assert _refusal(document, image) == "f02_sealed_record_malformed"


def test_only_f02_2_1_is_packed():
    document, records = batch()
    with pytest.raises(sealed.SealedPackRefused):
        sealed.sealed_bank(document, records, version="2.0")


def test_the_evidence_binds_the_document_and_records():
    document, records = batch()
    bank = sealed.sealed_bank(document, records)
    other_document, other_records = batch(seed=12)
    other = sealed.sealed_bank(other_document, other_records)
    assert bank["solver_evidence"] != other["solver_evidence"]
    assert np.array_equal(
        bank["inputs"], sealed.sealed_bank(document, records)["inputs"]
    )
