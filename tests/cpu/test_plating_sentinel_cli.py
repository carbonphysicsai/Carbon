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


PILOT = FIXTURE.with_name("REFERENCE_PILOT_TRIPLES_CASES.json")


def install_pilot_doubles(
    monkeypatch, mutate_rows=None, bad_probe=None, nonfinite=False
):
    events = []

    def study(path, out, workers, mid_workers):
        events.append("triples")
        assert workers == mid_workers == 4
        assert hashlib.sha256(path.read_bytes()).hexdigest() == pc.PILOT_SHA256
        cases = json.loads(path.read_bytes())["cases"]
        rows = [
            result(job, cases[job["case"]]) for job in pc.ladder(cases, pc.RE_REFERENCE)
        ]
        assert len(rows) == 6
        assert [(r["case"], r["mesh"]) for r in rows] == [
            (0, 40),
            (0, 80),
            (0, 160),
            (1, 40),
            (1, 80),
            (1, 160),
        ]
        if mutate_rows:
            mutate_rows(rows)
        (out / "records.jsonl").write_text(
            "".join(json.dumps(row) + "\n" for row in reversed(rows)),
            encoding="utf-8",
        )
        summary = {
            "solves": len(rows),
            "failed": sum(row["status"] != "OK" for row in rows),
        }
        (out / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
        return summary

    def probe(case, job):
        index = len(events) - 1
        events.append(index)
        raw = result(job, case, "SOLVER_FAILED" if index == bad_probe else "OK")
        if nonfinite and index == bad_probe:
            raw.update(status="OK", plating_margin_v=float("nan"))
        return raw

    study_mock, solver_mock = Mock(side_effect=study), Mock(side_effect=probe)
    monkeypatch.setattr(pc, "run", study_mock)
    monkeypatch.setattr(pc, "solve", solver_mock)
    return events, study_mock, solver_mock


def test_pilot_is_exact_six_rungs_then_nine_single_calls(monkeypatch, tmp_path):
    assert hashlib.sha256(PILOT.read_bytes()).hexdigest() == pc.PILOT_SHA256
    events, study, solver = install_pilot_doubles(monkeypatch)
    out = tmp_path / "pilot"
    assert (
        pc.main(
            [
                "run-pilot",
                "--cases",
                str(PILOT),
                "--jobs",
                str(FIXTURE),
                "--out",
                str(out),
            ]
        )
        == 0
    )
    study.assert_called_once_with(
        out / "inputs/pilot-cases.json", out / "study", workers=4, mid_workers=4
    )
    assert events == ["triples", *range(9)]
    assert solver.call_count == 9
    probes = json.loads(FIXTURE.read_bytes())["probes"]
    for i, probe in enumerate(probes):
        assert solver.call_args_list[i].args == (probe["case"], probe["job"])
        row = json.loads((out / f"sentinels/probe-{i}.jsonl").read_bytes())
        assert row["probe_id"] == probe["probe_id"] and row["probe_index"] == i
    assert (out / "inputs/pilot-cases.json").read_bytes() == PILOT.read_bytes()
    assert (out / "inputs/sentinel-jobs.json").read_bytes() == FIXTURE.read_bytes()
    receipt = json.loads((out / "pilot.json").read_bytes())
    assert receipt["status"] == "COMPLETED" and receipt["completed_probes"] == 9
    assert receipt["reason"] == "LIFECYCLE_ONLY_NOT_ADEQUACY"
    assert receipt["pilot_cases_sha256"] == pc.PILOT_SHA256
    assert receipt["sentinel_manifest_sha256"] == pc.SENTINEL_SHA256
    assert "pass" not in receipt and "reference_batch_pass" not in receipt


@pytest.mark.parametrize("which", ["cases", "jobs"])
def test_pilot_validates_both_inputs_before_any_output_or_work(
    monkeypatch, tmp_path, which
):
    _, study, solver = install_pilot_doubles(monkeypatch)
    changed = tmp_path / "changed.json"
    changed.write_bytes((PILOT if which == "cases" else FIXTURE).read_bytes() + b"\n")
    cases, jobs = (changed, FIXTURE) if which == "cases" else (PILOT, changed)
    out = tmp_path / "pilot"
    with pytest.raises(ValueError, match="frozen RESEARCH_V1 pilot"):
        pc.run_pilot(cases, jobs, out)
    assert not out.exists()
    study.assert_not_called()
    solver.assert_not_called()


def test_pilot_does_no_work_if_output_root_already_exists(monkeypatch, tmp_path):
    _, study, solver = install_pilot_doubles(monkeypatch)
    out = tmp_path / "pilot"
    out.mkdir()
    (out / "prior").write_bytes(b"retained")
    with pytest.raises(FileExistsError):
        pc.run_pilot(PILOT, FIXTURE, out)
    study.assert_not_called()
    solver.assert_not_called()
    assert (out / "prior").read_bytes() == b"retained"


@pytest.mark.parametrize(
    "kind", ["missing", "duplicate", "identity", "failed", "nan", "bool"]
)
def test_bad_baseline_stops_before_all_probes(monkeypatch, tmp_path, kind):
    def mutate(rows):
        if kind == "missing":
            rows.pop()
        elif kind == "duplicate":
            rows[0] = rows[1].copy()
        elif kind == "identity":
            rows[0]["case_id"] = "unlisted"
        elif kind == "failed":
            rows[0]["status"] = "SOLVER_FAILED"
        else:
            rows[0]["plating_margin_v"] = float("nan") if kind == "nan" else True

    events, study, solver = install_pilot_doubles(monkeypatch, mutate_rows=mutate)
    out = tmp_path / "pilot"
    record = pc.run_pilot(PILOT, FIXTURE, out)
    assert record["status"] == "INCOMPLETE" and record["completed_probes"] == 0
    assert record["reason"] == "FAILED_OR_INVALID_TRIPLES"
    study.assert_called_once()
    solver.assert_not_called()
    assert events == ["triples"]
    assert not list((out / "sentinels").iterdir())
    assert (out / "study/records.jsonl").is_file()
    assert json.loads((out / "pilot.json").read_bytes())["status"] == "INCOMPLETE"


@pytest.mark.parametrize("bad_index", [0, 4, 8])
@pytest.mark.parametrize("nonfinite", [False, True])
def test_pilot_stops_on_first_bad_probe_retaining_partial_output(
    monkeypatch, tmp_path, bad_index, nonfinite
):
    events, study, solver = install_pilot_doubles(
        monkeypatch, bad_probe=bad_index, nonfinite=nonfinite
    )
    out = tmp_path / "pilot"
    assert (
        pc.main(
            [
                "run-pilot",
                "--cases",
                str(PILOT),
                "--jobs",
                str(FIXTURE),
                "--out",
                str(out),
            ]
        )
        == 1
    )
    assert events == ["triples", *range(bad_index + 1)]
    assert solver.call_count == bad_index + 1
    study.assert_called_once()
    receipt = json.loads((out / "pilot.json").read_bytes())
    assert (
        receipt["status"] == "INCOMPLETE" and receipt["completed_probes"] == bad_index
    )
    assert not (out / f"sentinels/probe-{bad_index + 1}.jsonl").exists()
    bad_file = out / f"sentinels/probe-{bad_index}.jsonl"
    if nonfinite:
        assert bad_file.read_bytes() == b""
    else:
        assert json.loads(bad_file.read_bytes())["status"] == "SOLVER_FAILED"


def test_pilot_snapshots_survive_caller_input_change(monkeypatch, tmp_path):
    _, study, _ = install_pilot_doubles(monkeypatch)
    case_input, job_input = tmp_path / "cases.json", tmp_path / "jobs.json"
    case_input.write_bytes(PILOT.read_bytes())
    job_input.write_bytes(FIXTURE.read_bytes())
    delegate = study.side_effect

    def change_originals(path, out, workers, mid_workers):
        case_input.write_bytes(b"changed")
        job_input.write_bytes(b"changed")
        return delegate(path, out, workers, mid_workers)

    study.side_effect = change_originals
    assert (
        pc.run_pilot(case_input, job_input, tmp_path / "pilot")["status"] == "COMPLETED"
    )


@pytest.mark.parametrize("bad", [None, True, "not numeric"])
def test_pilot_stops_on_json_serializable_invalid_probe(monkeypatch, tmp_path, bad):
    _, _, solver = install_pilot_doubles(monkeypatch)
    delegate = solver.side_effect

    def invalid(case, job):
        raw = delegate(case, job)
        raw["plating_margin_v"] = bad
        return raw

    solver.side_effect = invalid
    receipt = pc.run_pilot(PILOT, FIXTURE, tmp_path / "pilot")
    assert receipt["status"] == "INCOMPLETE"
    assert receipt["reason"] == "FAILED_OR_INVALID_SENTINEL"
    assert receipt["completed_probes"] == 0
    solver.assert_called_once()


def test_pilot_stops_on_wrong_probe_identity(monkeypatch, tmp_path):
    _, _, solver = install_pilot_doubles(monkeypatch)
    delegate = solver.side_effect

    def invalid(case, job):
        raw = delegate(case, job)
        raw["case_id"] = "unlisted"
        return raw

    solver.side_effect = invalid
    receipt = pc.run_pilot(PILOT, FIXTURE, tmp_path / "pilot")
    assert receipt["status"] == "INCOMPLETE"
    assert receipt["reason"] == "FAILED_OR_INVALID_SENTINEL"
    solver.assert_called_once()
