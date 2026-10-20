"""Battery 2.0's bank to REFERENCE_PRESENT_MASK_INTERFACE_20261020 §1:
practice, then EV4's development grid, then the B15 probe pairs, with an
authoritative reference_present mask; 1.0 is unchanged."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import numpy as np
import pytest

from carbon.battery import domain
from carbon.challenge_kit import battery_pack as bp

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def bank():
    return bp.development_bank("2.0")


def test_rows_are_in_the_fixed_order_with_their_cohorts(bank):
    v1 = bp.development_bank("1.0")
    assert bank["case_ids"][:200] == v1["case_ids"]
    assert (
        bank["cohorts"] == ("practice",) * 200 + ("decision",) * 420 + ("probe",) * 400
    )
    grid = bank["case_ids"][200:620]
    assert grid[0] == "ev4:D-T5-S0.12:c1=0.5,c2=0.2:0"
    assert all(c.startswith("ev4:D-") and c.endswith(":0") for c in grid)
    probes = bank["case_ids"][620:]
    assert probes[:4] == ("p0-base", "p0-partner", "p1-base", "p1-partner")
    assert probes[-1] == "p199-partner"
    assert bank["inputs"].shape == (1020, 4) and bank["inputs"].dtype == np.float64
    assert bank["references"].shape == (1020, 247)


def test_the_mask_is_authoritative_and_matches_the_rows(bank):
    present = bank["reference_present"]
    assert type(present) is tuple and len(present) == 1020
    for i, row in enumerate(bank["references"]):
        assert np.isfinite(row).all() if present[i] else np.isnan(row).all()
    assert all(present[:200])  # practice always present
    assert not any(present[620:])  # probes never
    records = bank["reference_records"]
    for i in range(200, 620):
        assert present[i] is (records[i]["status"] == "OK")
    failed = [bank["case_ids"][i] for i in range(200, 620) if not present[i]]
    assert failed == [
        f"ev4:D-T5-S0.48:c1=2,c2={c2}:0" for c2 in ("0.2", "0.4", "0.6", "0.8", "1")
    ]
    assert sum(present) == 615


def test_grid_rows_are_the_verbatim_ev4_references(bank):
    with gzip.open(ROOT / bp._EV4_REFERENCES[0]) as stream:
        by_id = {r["case_id"]: r for r in map(json.loads, stream.read().splitlines())}
    for i in range(200, 620):
        record = by_id[bank["case_ids"][i]]
        assert bank["reference_records"][i] == record
        assert list(bank["inputs"][i]) == [record["inputs"][k] for k in domain.INPUTS]
        if record["status"] == "OK":
            o = record["outputs"]
            flat = [*o["voltage_v"], *o["temperature_c"], o["plating_margin_v"]]
            assert list(bank["references"][i]) == flat + list(o["capacity_ah"])


def test_probe_rows_are_the_public_plan_pairs_without_truth(bank):
    plan = json.loads((ROOT / bp._B15_PLAN[0]).read_bytes())
    for i, pair in enumerate(plan["pairs"]):
        for k, side in enumerate(("base", "partner")):
            row = 620 + 2 * i + k
            assert list(bank["inputs"][row]) == [pair[side][n] for n in domain.INPUTS]
            assert bank["reference_records"][row] == {
                "case_id": f"p{i}-{side}",
                "role": "probe",
                "pair": i,
                "side": side,
                "axis": pair["axis"],
            }


def test_practice_rows_and_version_1_0_are_unchanged(bank):
    v1 = bp.development_bank("1.0")
    assert "reference_present" not in v1
    assert np.array_equal(bank["inputs"][:200], v1["inputs"])
    assert np.array_equal(bank["references"][:200], v1["references"])
    assert bank["reference_records"][:200] == v1["reference_records"]


def test_changed_pins_and_unknown_versions_refuse(monkeypatch):
    with pytest.raises(ValueError):
        bp.development_bank("3.0")
    monkeypatch.setattr(bp, "_B15_PLAN", (bp._B15_PLAN[0], "0" * 64))
    with pytest.raises(ValueError):
        bp.development_bank("2.0")
    monkeypatch.undo()
    monkeypatch.setattr(bp, "_EV4_REFERENCES", (bp._EV4_REFERENCES[0], "0" * 64))
    with pytest.raises(ValueError):
        bp.development_bank("2.0")
