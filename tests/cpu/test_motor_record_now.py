"""Motor "record now, grade later" (owner 5 Nov 14:19): `run_batch_record_now` runs the unchanged reference batch and
keeps, per rotor position, each coil's flux linkage and the least |b| in the magnets in a ``record_now`` section.

Claims: the GetDP input differs from the pinned one by exactly the |b| quantity and its print; the graded ``outputs``
are exactly the pinned analysis'; the flux linkage is turns x stack length x (integral of A_z / mesh area) and the phases
are the winding-signed sums; a missing extra output fails the case by name; the pinned files are never changed (the
counted decision study binds them). Real run_batch code throughout; only GetDP's run is stood in by its output files.
"""

from __future__ import annotations

import importlib.util
import json
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from carbon.motor import domain, getdp

ROOT = Path(__file__).resolve().parents[2]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def record_now():
    return _load(
        "motor_record_now", "scripts/dev/motor/reference/run_batch_record_now.py"
    )


@pytest.fixture
def nominal():
    from test_motor import NOMINAL as nominal

    return nominal


def _params(batch, nominal):
    return {
        **batch.case_params(nominal, {}),
        "coil_area_mm2": domain.coil_area_mm2(nominal),
    }


def _solved(case_dir, p, *, skip=None):
    """GetDP's per-step output files as the pinned .pro writes them, plus the added |b| print and mesh.json."""
    res = case_dir / "res"
    res.mkdir(parents=True, exist_ok=True)
    slots = p["slots"]
    for k in p["steps"]:
        (res / f"torque_{k}.txt").write_text(f"0 {5.0!r}\n")
        if skip != "coil_a":
            (res / f"coil_a_{k}.txt").write_text(
                "".join(f"0 {1e-6 * (j + 1) * (1 + k)!r}\n" for j in range(slots))
            )
        if skip != "bmag":
            low, high = 0.4 + k, 0.9 + k
            (res / f"bmag_{k}.pos").write_text(
                'View "bmag" {\n'
                f"ST(0,0,0,1,0,0,0,1,0){{{low},{low},{low}}};\n"
                f"ST(1,0,0,1,1,0,0,1,0){{{high},{high},{high}}};\n"
                "};\n"
            )
    (case_dir / "log.getdp").write_text("")
    areas = {str(getdp.REGIONS["coil0"] + j): 50.0 + j for j in range(slots)}
    (case_dir / "mesh.json").write_text(
        json.dumps({"steps": {"0": {"nodes": 1, "elements": 1}}, "areas": areas})
    )
    return areas


def test_the_getdp_input_differs_only_by_the_magnet_field_print(record_now, nominal):
    batch = record_now._load_run_batch()
    p = _params(batch, nominal)
    pinned = getdp.pro_text(p, nonlinear=getdp.BRAUER)
    added = record_now.pro_text(getdp.pro_text)(p, nonlinear=getdp.BRAUER)
    assert added.count(record_now.BMAG_QUANTITY) == 1
    assert added.count(record_now.BMAG_PRINT) == 1
    stripped = added.replace(record_now.BMAG_QUANTITY + "\n", "").replace(
        record_now.BMAG_PRINT + "\n", ""
    )
    assert (
        stripped == pinned
    )  # the solve, torque, co-energy and coil prints: byte-identical


def test_the_record_keeps_flux_linkage_and_magnet_field_beside_unchanged_outputs(
    record_now, nominal, tmp_path
):
    batch = record_now._load_run_batch()
    p = _params(batch, nominal)
    areas = _solved(tmp_path, p)
    pinned, pinned_reasons = batch.analyze(tmp_path, p)
    result, reasons = record_now.analyze(batch.analyze, getdp)(tmp_path, p)
    assert reasons == pinned_reasons == []
    assert {k: v for k, v in result.items() if k != "record_now"} == pinned
    kept = result["record_now"]
    positions = len(result["outputs"]["torque_nm"])
    assert len(kept["coil_flux_linkage_wb"]) == len(kept["magnet_min_b_t"]) == positions
    integral = 1e-6 * 2 * (1 + p["steps"][0])  # coil 1 at the first position, Wb m
    mesh_area_m2 = areas[str(getdp.REGIONS["coil0"] + 1)] * 1e-6
    expected = p["turns"] * (p["length"] * 1e-3) * integral / mesh_area_m2
    assert kept["coil_a_integral_wbm"][0][1] == pytest.approx(integral, rel=1e-12)
    assert kept["coil_flux_linkage_wb"][0][1] == pytest.approx(expected, rel=1e-12)
    table = getdp.winding(p["slots"], p["poles"])
    for phase in ("A", "B", "C"):
        assert kept["phase_flux_linkage_wb"][phase][0] == pytest.approx(
            sum(
                sign * kept["coil_flux_linkage_wb"][0][j]
                for j, (named, sign) in enumerate(table)
                if named == phase
            ),
            rel=1e-12,
        )
    assert kept["magnet_min_b_t"][:2] == pytest.approx(
        [0.4 + p["steps"][0], 0.4 + p["steps"][1]]
    )


@pytest.mark.parametrize(
    "skip, reason", [("coil_a", "no coil flux"), ("bmag", "no magnet field")]
)
def test_a_missing_extra_output_fails_the_case_by_name(
    record_now, nominal, tmp_path, skip, reason
):
    batch = record_now._load_run_batch()
    p = _params(batch, nominal)
    _solved(tmp_path, p, skip=skip)
    result, reasons = record_now.analyze(batch.analyze, getdp)(tmp_path, p)
    assert result is None and reason in reasons[0]


def test_a_real_run_case_writes_the_print_and_records_the_extra_outputs(
    record_now, nominal, tmp_path, monkeypatch
):
    """`run_case` of the installed batch: its .pro carries the |b| print, its record the ``record_now`` section; only
    GetDP's run is stood in (it writes the files GetDP would)."""
    batch = record_now.install(record_now._load_run_batch())

    def solved(case_dir, p, name, cpus, timeout_s):
        _solved(case_dir, {**p, "slots": p["slots"]})
        return None, 1.0, "exit 0"

    monkeypatch.setattr(batch, "solve", solved)
    out = tmp_path / "out"
    (out / "cases").mkdir(parents=True)
    args = SimpleNamespace(cpus=1, timeout_s=60, keep="all")
    entry = {"case_id": "case-0", "inputs": nominal}
    batch.run_case(entry, out, args, "batch-0", threading.Lock())
    (record,) = [
        json.loads(line)
        for line in (out / "records.jsonl").read_text().splitlines()
        if line.strip()
    ]
    assert record["status"] == "OK", record.get("reasons")
    assert set(record["outputs"]) == {"torque_nm"}
    assert record["record_now"]["schema"] == record_now.RECORD_NOW_SCHEMA
    # Validator (exam science) 14:44 (2) + (3): the record names THIS runner and its sha, and the pinned one it wraps
    import hashlib

    def sha(path):
        return "sha256:" + hashlib.sha256((ROOT / path).read_bytes()).hexdigest()

    runner = record["runner"]
    assert runner["name"] == "record-now"
    assert runner["file"] == "scripts/dev/motor/reference/run_batch_record_now.py"
    assert runner["sha256"] == sha(runner["file"])
    assert runner["wraps"] == {
        "file": "scripts/dev/motor/reference/run_batch.py",
        "sha256": sha("scripts/dev/motor/reference/run_batch.py"),
    }
    assert record["wall_s_basis"] == "record-now runner" and "wall_s" in record
    pro = (out / "cases" / "case-0" / "machine.pro").read_text()
    assert record_now.BMAG_PRINT in pro


def test_installing_changes_no_pinned_module(record_now):
    pinned = getdp.pro_text
    batch = record_now.install(record_now._load_run_batch())
    assert (
        getdp.pro_text is pinned
    )  # carbon.motor.getdp itself is untouched; the batch gets a shim
    assert batch.getdp is not getdp
