"""Motor 1.8's 240-wide development bank (`motor18_dev_grid`) and its builder. Claims: each reference keeps the bank's
own torque and gains the record-now linkages, probes stay all-NaN 240 wide, nothing is served until the linkage file is
pinned, the builder refuses a mismatch (inputs, torque beyond the rounding ruling, missing or duplicate records), and the
1.8 dispatch registers this bank in `dev_grid` (add-only). Synthetic numbers only (never solver values)."""

from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
import pytest

from carbon.challenge_kit.physical_public_train import TORQUE_ROUNDING_RULING
from carbon.motor.domain import ANGLE_STEPS, INPUTS
from carbon.scoring import dev_grid
from carbon.scoring import motor18_dev_grid as m

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "dev" / "motor"))
import build_dev_bank_1p8 as builder  # noqa: E402

IDS = ("practice-0000", "decision-d01-r01", "probe-01-d1m")


def _bank():
    inputs = np.arange(3 * len(INPUTS), dtype=float).reshape(3, len(INPUTS)) + 1.0
    references = np.full((3, ANGLE_STEPS), np.nan)
    references[0] = np.linspace(1.0, 2.0, ANGLE_STEPS)
    references[1] = np.linspace(3.0, 4.0, ANGLE_STEPS)
    return {
        "case_ids": IDS,
        "cohorts": ("practice", "decision_sealed_grid", "probe_response"),
        "inputs": inputs,
        "references": references,
        "reference_records": [{}, {}, {}],
        "reference_present": (True, True, False),
        "solver_evidence": b'{"practice_public_bank":"x"}',
    }


def _phases(seed):
    return {
        p: [0.01 * (seed + 1) * math.cos(k / 7 + n) for k in range(ANGLE_STEPS)]
        for n, p in enumerate(m.PHASES)
    }


CASES = {IDS[0]: _phases(0), IDS[1]: _phases(1)}


def test_each_reference_keeps_its_torque_and_gains_the_linkages():
    wide = m.widen(_bank(), CASES)
    refs = wide["references"]
    assert refs.shape == (3, 240)
    assert np.array_equal(refs[0, :60], _bank()["references"][0])  # the bank's own torque, unchanged
    assert refs[0, 60:120].tolist() == CASES[IDS[0]]["A"]
    assert refs[1, 180:240].tolist() == CASES[IDS[1]]["C"]
    assert np.isnan(refs[2]).all()  # a probe: no reference, all-NaN, 240 wide
    assert wide["solver_evidence"] != _bank()["solver_evidence"]  # the linkage joins the identity
    assert wide["case_ids"] == IDS and wide["cohorts"] == _bank()["cohorts"]


def test_a_reference_row_without_its_linkage_refuses():
    with pytest.raises(m.DevBankUnavailable, match="case_without_linkage"):
        m.widen(_bank(), {IDS[0]: _phases(0)})


def test_a_base_bank_that_is_not_torque_wide_refuses():
    bank = _bank()
    bank["references"] = np.zeros((3, 240))
    with pytest.raises(m.DevBankUnavailable, match="not_torque_wide"):
        m.widen(bank, CASES)


def test_nothing_is_served_until_the_linkage_file_is_pinned(monkeypatch):
    monkeypatch.setattr(m, "LINKAGE_SHA256", None)
    with pytest.raises(m.DevBankUnavailable, match="not_pinned"):
        m.bank("1.8")
    with pytest.raises(m.DevBankUnavailable, match="for_1.8_only"):
        m.bank("1.6")


def test_the_pinned_file_is_read_only_at_its_bytes():
    raw = m.canonical({"schema": m.SCHEMA, "cases": CASES})
    pin = hashlib.sha256(raw).hexdigest()
    assert m.load_linkages(raw, pinned=pin) == CASES
    with pytest.raises(m.DevBankUnavailable, match="differs"):
        m.load_linkages(raw + b" ", pinned=pin)
    bad = m.canonical({"schema": m.SCHEMA, "cases": {IDS[0]: {"A": [1.0]}}})
    with pytest.raises(m.DevBankUnavailable, match="invalid"):
        m.load_linkages(bad, pinned=hashlib.sha256(bad).hexdigest())


# --- the builder -------------------------------------------------------------------------------------------------------


def _record(i, *, torque=None, inputs=None, status="OK", phases=None):
    bank = _bank()
    return {
        "case_id": IDS[i],
        "status": status,
        "inputs": inputs
        or {n: float(v) for n, v in zip(INPUTS, bank["inputs"][i], strict=True)},
        "outputs": {
            "torque_nm": [float(v) for v in (torque if torque is not None else bank["references"][i])]
        },
        "record_now": {"phase_flux_linkage_wb": phases or _phases(i)},
    }


@pytest.fixture
def base(monkeypatch):
    monkeypatch.setattr(m, "_base_bank", _bank)


def _write(tmp_path, records, name="r.jsonl"):
    path = tmp_path / name
    path.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
    return str(path)


def test_the_builder_makes_the_file_the_bank_reads(tmp_path, base, monkeypatch):
    path = _write(tmp_path, [_record(0), _record(1), _record(2, status="REFERENCE_INVALID")])
    out = tmp_path / "linkage.json"
    assert builder.main([path, "--out", str(out)]) == 0
    raw = out.read_bytes()
    assert raw.endswith(b"\n") and b"\r" not in raw
    document = json.loads(raw)
    assert document["torque_check"]["byte_equal"] == 2
    assert document["torque_check"]["host_order_rounding"] == []
    monkeypatch.setattr(m, "LINKAGE_FILE", out)
    monkeypatch.setattr(m, "LINKAGE_SHA256", hashlib.sha256(raw).hexdigest())
    wide = m.bank("1.8")
    assert wide["references"].shape == (3, 240)
    assert wide["references"][1, 60:120].tolist() == _phases(1)["A"]


def test_torque_inside_the_rounding_ruling_is_recorded_beyond_it_stops(tmp_path, base):
    near = list(_bank()["references"][1])
    near[5] += TORQUE_ROUNDING_RULING["max_abs_delta_nm"] / 2
    document = builder.build([_write(tmp_path, [_record(0), _record(1, torque=near)])])
    assert document["torque_check"]["host_order_rounding"] == [IDS[1]]
    assert document["torque_check"]["max_abs_delta_nm"] > 0
    far = list(_bank()["references"][1])
    far[5] += 1e-6
    with pytest.raises(builder.BuildRefused, match="STOP"):
        builder.build([_write(tmp_path, [_record(0), _record(1, torque=far)], "f.jsonl")])


@pytest.mark.parametrize(
    "records, code",
    [
        (lambda: [_record(0)], "no OK record"),
        (lambda: [_record(0), _record(1), _record(1)], "more than one"),
        (
            lambda: [_record(0), _record(1, inputs={n: 0.5 for n in INPUTS})],
            "inputs differ",
        ),
        (
            lambda: [_record(0), _record(1, phases={"A": [1.0] * 60, "B": [1.0] * 60})],
            "phase flux linkage",
        ),
    ],
)
def test_the_builder_refuses_records_that_are_not_the_banks(tmp_path, base, records, code):
    with pytest.raises(builder.BuildRefused, match=code):
        builder.build([_write(tmp_path, records())])


# --- the dev-grid registration -----------------------------------------------------------------------------------------


@pytest.fixture
def registry():
    saved = dict(dev_grid._REGISTERED)
    dev_grid._REGISTERED.clear()
    yield dev_grid._REGISTERED
    dev_grid._REGISTERED.clear()
    dev_grid._REGISTERED.update(saved)


def test_an_overlay_version_registers_its_dev_grid_add_only(registry):
    key = ("electric-motor-magnetics", "9.9")

    def bank(version):
        return {"bank_of": version}

    def adapter(version):
        return {"adapter_of": version}

    assert dev_grid.kind(*key) is None
    dev_grid.register(*key, bank=bank, adapter=adapter)
    dev_grid.register(*key, bank=bank, adapter=adapter)  # the same pair again: no-op
    assert dev_grid.kind(*key) == dev_grid.REGISTERED_KIND
    assert dev_grid.bank(*key) == {"bank_of": "9.9"}
    assert dev_grid.adapter(*key) == {"adapter_of": "9.9"}
    with pytest.raises(ValueError, match="different dev grid"):
        dev_grid.register(*key, bank=adapter, adapter=bank)
    with pytest.raises(ValueError, match="worker-image"):
        dev_grid.register("electric-motor-magnetics", "1.6", bank=bank, adapter=adapter)


def test_the_1_8_dispatch_registers_the_240_wide_dev_bank(registry):
    from carbon.scoring import motor18_dual_pack, pool_version

    saved = dict(pool_version._BINDINGS)
    try:
        motor18_dual_pack.dispatch({})
    finally:
        pool_version._BINDINGS.clear()
        pool_version._BINDINGS.update(saved)
    assert registry[("electric-motor-magnetics", "1.8")] == (m.bank, m.adapter)
