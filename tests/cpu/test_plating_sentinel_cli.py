"""Closed public sentinel CLI contract; the solver is replaced in every test."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from scripts.dev.battery import plating_convergence as pc

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures/battery/REFERENCE_SENTINELS_RESEARCH_V1.json"
)


def result(job, case, status="OK"):
    record = {
        **job,
        "case_id": case["case_id"],
        "status": status,
        "wall_s": 1.25,
        "cpu_s": 1.0,
        "maxrss_mb": 10,
    }
    if status == "OK":
        record.update(plating_margin_v=-0.002, points=12)
    else:
        record["error"] = "synthetic solver failure"
    return record


@pytest.mark.parametrize("index", range(9))
def test_each_probe_calls_exact_existing_solve_once(monkeypatch, tmp_path, index):
    assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest() == pc.SENTINEL_SHA256
    probe = json.loads(FIXTURE.read_bytes())["probes"][index]
    case = probe["case"]
    job = probe["job"]
    # Independently check the catalogue IDs and all registered numerical tuples.
    assert job["case"] == (100, 77, 9)[index // 3]
    assert job["mesh"] == 80 and job["cycles"] == 1
    assert (job["rtol"], job["period_s"]) == ((1e-8, None), (1e-6, 5), (1e-8, 5))[
        index % 3
    ]
    assert case["source"] == "ev4" and case["split"] == "development"
    raw_result = result(job, case)
    solver = Mock(return_value=raw_result.copy())
    monkeypatch.setattr(pc, "solve", solver)
    monkeypatch.setattr(pc, "run", Mock(side_effect=AssertionError("study entered")))
    monkeypatch.setattr(pc, "_stage", Mock(side_effect=AssertionError("pool entered")))
    out = tmp_path / "probe.json"
    assert (
        pc.main(
            [
                "run-probe",
                "--jobs",
                str(FIXTURE),
                "--probe-index",
                str(index),
                "--out",
                str(out),
            ]
        )
        == 0
    )
    solver.assert_called_once_with(case, job)
    assert json.loads(out.read_text(encoding="utf-8")) == {
        **raw_result,
        "probe_id": probe["probe_id"],
        "probe_index": index,
        "manifest_sha256": pc.SENTINEL_SHA256,
    }


@pytest.mark.parametrize("index", [-1, 9, True, False, 1.0, "0", None])
def test_bad_index_refused_before_solve_or_output(monkeypatch, tmp_path, index):
    solver = Mock(side_effect=AssertionError("solver called"))
    monkeypatch.setattr(pc, "solve", solver)
    out = tmp_path / "probe.json"
    with pytest.raises(ValueError, match="integer in 0..8"):
        pc.run_probe(FIXTURE, index, out)
    solver.assert_not_called()
    assert not out.exists()


@pytest.mark.parametrize(
    "mutation",
    [
        "mesh",
        "cycles",
        "rtol",
        "period_s",
        "case",
        "source",
        "split",
        "tuple",
        "schema",
        "extra_job",
        "extra_case",
        "extra_probe",
        "extra_root",
        "reorder",
        "duplicate_key",
        "malformed",
        "format_only",
    ],
)
def test_any_manifest_tampering_refused_before_solve(monkeypatch, tmp_path, mutation):
    document = json.loads(FIXTURE.read_bytes())
    probe = document["probes"][0]
    if mutation in {"mesh", "cycles", "rtol", "period_s", "case"}:
        probe["job"][mutation] = {
            "mesh": 320,
            "cycles": 30,
            "rtol": 1e-3,
            "period_s": 1,
            "case": 0,
        }[mutation]
    elif mutation in {"source", "split"}:
        probe["case"][mutation] = "verification"
    elif mutation == "tuple":
        probe["case"]["c1"] = 1.9
    elif mutation == "schema":
        document["schema"] = pc.CASES_SCHEMA
    elif mutation == "extra_job":
        probe["job"]["atol"] = 1e-3
    elif mutation == "extra_case":
        probe["case"]["solver_options"] = {}
    elif mutation == "extra_probe":
        document["probes"].append(probe.copy())
    elif mutation == "extra_root":
        document["method"] = "arbitrary"
    elif mutation == "reorder":
        document["probes"].reverse()
    raw = json.dumps(document).encode()
    if mutation == "duplicate_key":
        raw = raw.replace(b'"mesh": 80', b'"mesh": 320, "mesh": 80', 1)
    elif mutation == "malformed":
        raw = b'{"probes":'
    elif mutation == "format_only":
        raw = FIXTURE.read_bytes() + b"\n"
    jobs = tmp_path / "tampered.json"
    jobs.write_bytes(raw)
    solver = Mock(side_effect=AssertionError("solver called"))
    monkeypatch.setattr(pc, "solve", solver)
    out = tmp_path / "probe.json"
    with pytest.raises(ValueError, match="frozen RESEARCH_V1"):
        pc.run_probe(jobs, 0, out)
    solver.assert_not_called()
    assert not out.exists()


def test_existing_output_prevents_a_solve(monkeypatch, tmp_path):
    out = tmp_path / "probe.json"
    out.write_text("prior evidence\n", encoding="utf-8")
    solver = Mock(side_effect=AssertionError("solver called"))
    monkeypatch.setattr(pc, "solve", solver)
    with pytest.raises(FileExistsError):
        pc.run_probe(FIXTURE, 0, out)
    solver.assert_not_called()
    assert out.read_text(encoding="utf-8") == "prior evidence\n"


def test_solver_failure_is_preserved_and_never_retried(monkeypatch, tmp_path):
    probe = json.loads(FIXTURE.read_bytes())["probes"][0]
    raw_result = result(probe["job"], probe["case"], "SOLVER_FAILED")
    solver = Mock(return_value=raw_result.copy())
    monkeypatch.setattr(pc, "solve", solver)
    out = tmp_path / "failure.json"
    assert (
        pc.main(
            [
                "run-probe",
                "--jobs",
                str(FIXTURE),
                "--probe-index",
                "0",
                "--out",
                str(out),
            ]
        )
        == 1
    )
    solver.assert_called_once()
    record = json.loads(out.read_text(encoding="utf-8"))
    assert record["status"] == "SOLVER_FAILED"
    assert record["error"] == raw_result["error"]
    assert "plating_margin_v" not in record and "pass" not in record


@pytest.mark.parametrize("margin", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_result_never_becomes_successful_json(monkeypatch, tmp_path, margin):
    probe = json.loads(FIXTURE.read_bytes())["probes"][0]
    raw_result = result(probe["job"], probe["case"])
    raw_result["plating_margin_v"] = margin
    solver = Mock(return_value=raw_result)
    monkeypatch.setattr(pc, "solve", solver)
    out = tmp_path / "invalid.json"
    with pytest.raises(SystemExit) as exc:
        pc.main(
            [
                "run-probe",
                "--jobs",
                str(FIXTURE),
                "--probe-index",
                "0",
                "--out",
                str(out),
            ]
        )
    assert exc.value.code != 0
    solver.assert_called_once()
    assert out.read_bytes() == b""


@pytest.mark.parametrize(
    "extra",
    [
        ["--mesh", "320"],
        ["--cycles", "30"],
        ["--rtol", "1e-3"],
        ["--workers", "4"],
        ["--method", "arbitrary"],
    ],
)
def test_cli_rejects_overrides_before_solve(monkeypatch, tmp_path, extra):
    solver = Mock(side_effect=AssertionError("solver called"))
    monkeypatch.setattr(pc, "solve", solver)
    with pytest.raises(SystemExit) as exc:
        pc.main(
            [
                "run-probe",
                "--jobs",
                str(FIXTURE),
                "--probe-index",
                "0",
                "--out",
                str(tmp_path / "probe.json"),
                *extra,
            ]
        )
    assert exc.value.code == 2
    solver.assert_not_called()
