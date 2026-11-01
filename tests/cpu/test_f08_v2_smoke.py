"""The F08 2.0 smoke preparer: the corners are corners of the signed 1.7 box, everything is labelled TEST_ONLY, and the
cgroup counters are read. Nothing is meshed or solved here."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

CALCULIX = (
    Path(__file__).resolve().parents[2] / "scripts/dev/reference_packages/calculix"
)
sys.path.insert(0, str(CALCULIX))

import f08_deck_v2 as v2
import f08_v2_smoke as smoke


def test_the_corners_are_corners_of_the_signed_1_7_box():
    stiff, heavy = smoke.corner_case("stiffest"), smoke.corner_case("heaviest")
    assert (stiff["length_mm"], stiff["thickness_mm"], stiff["rib_height_mm"]) == (
        180.0,
        8.0,
        16.0,
    )
    assert heavy["length_mm"] == 260.0 and heavy["width_mm"] == 100.0
    for case in (stiff, heavy):
        for name, (low, high) in smoke.BOX.items():
            assert case[name] in (low, high)
    with pytest.raises(v2.Refused, match="unknown_corner"):
        smoke.corner_case("middle")


def test_prepare_writes_a_compiling_mesh_program_and_a_test_only_plan(tmp_path):
    plan = smoke.prepare(tmp_path, "stiffest", h_mm=1.7, fillet_h_mm=0.5)
    assert plan["tables"] == "TEST_ONLY" and plan["h_mm"] == 1.7
    text = (tmp_path / "make_mesh.py").read_text()
    assert v2.script_compiles(text) and "SizeMin" in text
    saved = json.loads((tmp_path / "smoke.json").read_text())
    assert saved["case"]["alloy"] == "SMOKE_STAND_IN" and len(saved["then"]) == 3
    # the synthetic table is only usable in test mode
    with pytest.raises(v2.Refused):
        v2.validate_case(saved["case"])  # production ranges are HUMAN_INPUT
    row = v2.material("SMOKE_STAND_IN", table=saved["table"], test_mode=True)
    assert row["tables"] == "TEST_ONLY"


def test_the_cgroup_counters_give_cpu_seconds_and_peak_memory_for_v2_and_v1_hosts():
    v2_text = "/sys/fs/cgroup/cpu.stat:usage_usec 2500000\n/sys/fs/cgroup/memory.peak:1073741824\n"
    assert smoke.parse_cgroup(v2_text) == {"cpu_s": 2.5, "peak_mem_mib": 1024.0}
    v1_text = "/sys/fs/cgroup/cpuacct/cpuacct.usage:3000000000\n/sys/fs/cgroup/memory/memory.max_usage_in_bytes:536870912\n"
    assert smoke.parse_cgroup(v1_text) == {"cpu_s": 3.0, "peak_mem_mib": 512.0}
    assert smoke.parse_cgroup("") == {"cpu_s": None, "peak_mem_mib": None}


def test_report_reads_the_mesh_and_counters(tmp_path):
    smoke.prepare(tmp_path, "heaviest")
    (tmp_path / "mesh.json").write_text(
        json.dumps({"nodes": 120000, "elements": 80000, "fillet_elements": 900})
    )
    (tmp_path / "cgroup.txt").write_text(
        "/sys/fs/cgroup/cpu.stat:usage_usec 1000000\n/sys/fs/cgroup/memory.peak:2097152\n"
    )
    out = smoke.report(tmp_path)
    assert out["nodes"] == 120000 and out["fillet_elements"] == 900
    assert (
        out["cpu_s"] == 1.0
        and out["peak_mem_mib"] == 2.0
        and out["tables"] == "TEST_ONLY"
    )
    assert (tmp_path / "smoke-report.json").is_file()
