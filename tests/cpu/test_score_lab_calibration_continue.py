"""Toy records and executor only; no solver, provider, model or measured science."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from carbon.battery import truth_env
from carbon.design_search import tasks
from scripts.dev.battery import feasibility02 as worker
from scripts.dev.score_lab import owner_v3 as owner
from scripts.dev.score_lab import owner_v3_calibration_continue as continuation
from scripts.dev.score_lab import owner_v3_numerics as numerics
from scripts.dev.score_lab import owner_v3_panel_export as producer

ROOT = Path(__file__).resolve().parents[2]


def _record(job):
    phase = {"t_max_c": 35.0, "plating_min_v": 0.01, "v_max_v": 4.1}
    return {
        **job,
        "fixture": True,
        "schema": "carbon.battery.feasibility02-record.v1",
        "status": "OK",
        "initial_rest": {"t_start_s": 0, "t_end_s": 120, "t_max_c": 30.0},
        "per_cycle": [
            {"cycle": c, "phases": {p: dict(phase) for p in producer.PHASES}}
            for c in range(1, 31)
        ],
        "capacity_all_ah": [1.0] * 30,
        "q30_over_q1": 1.0,
        "whole_programme": {"v_max_v": 4.1, "t_max_c": 35.0},
        "soc_clock": {"status": "REACHED", "minutes": 40.0, "time_s": 2400.0},
        "core_s": 0.0,
        "wall_s": 0.0,
    }


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _write(path, value):
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


@pytest.fixture
def setup(tmp_path, monkeypatch):
    plan = json.loads(
        (
            ROOT
            / "Business/research/score-lab-campaign-01/acquisition-v1/acquisition.json"
        ).read_bytes()
    )
    jobs = owner.acquisition_inputs(
        plan, expected_digest=tasks.digest(plan), stage="calibration-pilot"
    )
    files = {
        p: _sha(ROOT / p)
        for p in (
            *producer.SOURCES,
            producer.EXPORTER,
            producer.NUMERICS,
            "scripts/dev/score_lab/owner_v3.py",
            "carbon/design_search/tasks.py",
        )
    }
    pilot_binding = {
        "schema": "carbon.scorelab.calibration-execution.v1",
        "scope": "SYNTHETIC_FIXTURE",
        "execution_source": "a" * 40,
        "source_files": files,
        "plan": plan,
        "plan_digest": tasks.digest(plan),
        "policy_digest": tasks.digest(numerics.POLICY),
        "observer": producer._observer(plan, {"files": files}),
    }
    current = {**pilot_binding, "execution_source": "b" * 40}
    provenance = {
        "schema": "carbon.battery.solver-provenance.v1",
        "solver_image": "study@" + plan["image_digest"],
        "overlay_lock_sha256": "sha256:" + plan["overlay_sha256"],
        "overlay_lock": "scripts/dev/exam_design/locks/battery-overlay.lock.json",
        "pybamm": "26.8.0.0",
    }
    paths = {
        name: tmp_path / (name + ".json")
        for name in (
            "binding",
            "execution_binding",
            "pilot_binding",
            "pilot_jobs",
            "pilot_records",
            "records",
        )
    }
    paths["pilot_receipt"] = paths["pilot_records"].with_name(
        paths["pilot_records"].name + ".calibration.json"
    )
    _write(paths["pilot_binding"], pilot_binding)
    _write(paths["execution_binding"], current)
    _write(paths["pilot_jobs"], jobs)
    submitted, evaluated = [], []

    class Future:
        def __init__(self, fn, job):
            self.fn, self.job = fn, job

        def result(self):
            evaluated.append(self.job["case_id"])
            return self.fn(self.job)

    class Pool:
        def __init__(self, workers):
            assert 1 <= workers <= 2

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def submit(self, fn, job):
            submitted.append(job["case_id"])
            return Future(fn, job)

    for module in (worker, continuation):
        monkeypatch.setattr(module, "ProcessPoolExecutor", Pool)
        monkeypatch.setattr(module, "as_completed", lambda fs: list(fs)[::-1])
    monkeypatch.setattr(worker, "_timed", _record)
    monkeypatch.setattr(truth_env, "provenance", lambda _: provenance)
    assert (
        worker.solve_calibration(
            paths["pilot_jobs"],
            paths["pilot_records"],
            2,
            paths["pilot_binding"],
            _sha(paths["pilot_binding"]),
        )
        == 0
    )
    submitted.clear()
    evaluated.clear()

    def refresh():
        contract = {
            "schema": continuation.SCHEMA,
            "execution_binding_sha256": _sha(paths["execution_binding"]),
            "orchestrator_sha256": _sha(continuation.__file__),
            "pilot_binding_sha256": _sha(paths["pilot_binding"]),
            "pilot_records_sha256": _sha(paths["pilot_records"]),
            "pilot_receipt_sha256": _sha(paths["pilot_receipt"]),
        }
        _write(paths["binding"], contract)
        return _sha(paths["binding"])

    refresh()

    def run(workers=2):
        return continuation.run(
            paths, expected_sha256=_sha(paths["binding"]), workers=workers
        )

    def receipt():
        return json.loads(
            paths["records"]
            .with_name(paths["records"].name + ".continuation.json")
            .read_bytes()
        )

    return {
        "paths": paths,
        "refresh": refresh,
        "run": run,
        "receipt": receipt,
        "submitted": submitted,
        "evaluated": evaluated,
        "provenance": provenance,
    }


def test_reuses_six_solves_only_nine_and_preserves_mixed_commit_chunks(setup):
    paths = setup["paths"]
    original = paths["pilot_records"].read_bytes()
    assert setup["run"]() == 0
    receipt = setup["receipt"]()
    assert len(setup["submitted"]) == len(setup["evaluated"]) == 27
    assert len(set(setup["submitted"])) == 27
    assert len(receipt["per_job"]) == 45
    assert list(receipt["per_job"].values()).count("REUSED_OK") == 18
    assert list(receipt["per_job"].values()).count("OK") == 27
    assert receipt["status"] == "COMPATIBLE_FULL_CALIBRATION_ONLY"
    assert receipt["registered_calibration_complete"] is True
    assert receipt["full_calibration_release"] is False
    assert receipt["evaluation_release"] is False
    assert receipt["qualification"] is False
    assert receipt["calibration"]["expected_case_count"] == 15
    assert receipt["calibration"]["missing_cases"] == []
    assert receipt["calibration"]["failed_cases"] == []
    assert len(receipt["per_completed_triple"]) == 9
    assert paths["pilot_records"].read_bytes() == original
    assert len(paths["records"].read_bytes().splitlines()) == 27
    assert [c["source_commit"] for c in receipt["chunks"]] == ["a" * 40, "b" * 40]
    for chunk, path in zip(
        receipt["chunks"], (paths["pilot_records"], paths["records"])
    ):
        assert chunk["sha256"] == "sha256:" + _sha(path)
        assert len(chunk["source_files"]) == 4
        rows = path.read_bytes().splitlines()
        for row in chunk["rows"]:
            raw = json.loads(rows[row["line"] - 1])
            assert raw["case_id"] == row["job_id"] == row["case_id"]
            assert raw["fixture"] is True
    assert not set(setup["submitted"]) & {
        json.loads(r)["case_id"] for r in original.splitlines()
    }
    execution = json.loads(paths["execution_binding"].read_bytes())
    jobs = []
    for stage in ("calibration-pilot", "calibration-rest"):
        jobs.extend(
            owner.acquisition_inputs(
                execution["plan"], expected_digest=execution["plan_digest"], stage=stage
            )["jobs"]
        )
    authenticated, bindings = producer._raw_rows(
        {"scope": "SYNTHETIC_FIXTURE", "chunks": receipt["chunks"]},
        {"reused-pilot": original, "continuation": paths["records"].read_bytes()},
        {j["case_id"]: j for j in jobs},
        execution["observer"]["source_files"],
        execution["plan"],
    )
    assert len(authenticated) == len(bindings) == 45


@pytest.mark.parametrize("failure_group", [0, 2, 8])
def test_failed_triple_prevents_later_submissions(setup, monkeypatch, failure_group):
    plan = json.loads(setup["paths"]["execution_binding"].read_bytes())["plan"]
    rest = owner.acquisition_inputs(
        plan, expected_digest=tasks.digest(plan), stage="calibration-rest"
    )["jobs"]
    bad_id = rest[failure_group * 3 + 2]["case_id"]

    def bad(job):
        row = _record(job)
        if job["case_id"] == bad_id:
            row["soc_clock"]["minutes"] = 100.0
        return row

    monkeypatch.setattr(worker, "_timed", bad)
    assert setup["run"]() == 2
    receipt = setup["receipt"]()
    assert len(setup["submitted"]) == 3 * (failure_group + 1)
    assert receipt["status"] == "NUMERICAL_CALIBRATION_INADEQUATE"
    assert receipt["registered_calibration_complete"] is False
    assert len(receipt["per_job"]) == 45
    assert list(receipt["per_job"].values()).count("NOT_DISPATCHED") == 27 - len(
        setup["submitted"]
    )


@pytest.mark.parametrize("failure", ["infra", "not_reached", "identity", "interrupt"])
def test_incomplete_malformed_and_interrupted_rows_never_advance(
    setup, monkeypatch, failure
):
    def bad(job):
        if failure == "infra":
            raise RuntimeError("synthetic infrastructure failure")
        if failure == "interrupt":
            raise KeyboardInterrupt
        row = _record(job)
        if failure == "identity":
            row["soc0"] = 0.2
        else:
            row["soc_clock"] = {"status": "NOT_REACHED"}
        return row

    monkeypatch.setattr(worker, "_timed", bad)
    if failure in ("identity", "interrupt"):
        with pytest.raises((tasks.TaskError, KeyboardInterrupt)):
            setup["run"]()
    else:
        assert setup["run"]() == 2
    receipt = setup["receipt"]()
    assert len(setup["submitted"]) == 3
    assert receipt["registered_calibration_complete"] is False
    assert list(receipt["per_job"].values()).count("NOT_DISPATCHED") == 24
    assert receipt["records_sha256"] == _sha(setup["paths"]["records"])
    if failure == "infra":
        assert list(receipt["per_job"].values()).count("FAILED_INFRA") == 3


@pytest.mark.parametrize(
    "field",
    [
        "pilot_records",
        "pilot_receipt",
        "pilot_binding",
        "execution_binding",
        "pilot_jobs",
    ],
)
def test_input_byte_drift_refuses_before_output_or_pool(setup, field):
    with setup["paths"][field].open("ab") as handle:
        handle.write(b" ")
    # pilot-jobs is validated structurally by the existing guard, not byte-pinned.
    if field == "pilot_jobs":
        body = json.loads(setup["paths"][field].read_bytes())
        body["jobs"].pop()
        _write(setup["paths"][field], body)
    with pytest.raises(tasks.TaskError):
        setup["run"]()
    assert setup["submitted"] == []
    assert not setup["paths"]["records"].exists()


@pytest.mark.parametrize(
    "drift",
    [
        "status",
        "partial",
        "measurement",
        "source",
        "job_state",
        "calibration",
        "promotion",
    ],
)
def test_even_rehashed_pilot_claim_is_recomputed_before_reuse(setup, drift):
    paths = setup["paths"]
    receipt = json.loads(paths["pilot_receipt"].read_bytes())
    if drift == "status":
        receipt["status"] = "INCOMPLETE_REFERENCE"
    elif drift == "source":
        receipt["execution_source"] = "c" * 40
    elif drift == "job_state":
        receipt["per_job"].pop(next(iter(receipt["per_job"])))
    elif drift == "calibration":
        receipt["calibration"]["expected_case_count"] = 15
    elif drift == "promotion":
        for field in ("pilot_binding", "execution_binding"):
            binding = json.loads(paths[field].read_bytes())
            binding["scope"] = "PUBLIC_DEVELOPMENT"
            _write(paths[field], binding)
    else:
        rows = [json.loads(r) for r in paths["pilot_records"].read_bytes().splitlines()]
        if drift == "partial":
            rows.pop()
        else:
            rows[0]["soc_clock"]["minutes"] = 100.0
        paths["pilot_records"].write_text(
            "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8"
        )
        receipt["records_sha256"] = _sha(paths["pilot_records"])
    _write(paths["pilot_receipt"], receipt)
    setup["refresh"]()
    with pytest.raises(tasks.TaskError):
        setup["run"]()
    assert setup["submitted"] == []
    assert not paths["records"].exists()


@pytest.mark.parametrize("workers", [0, 3, True])
def test_worker_bound_before_any_work(setup, workers):
    with pytest.raises(tasks.TaskError):
        setup["run"](workers)
    assert setup["submitted"] == []


@pytest.mark.parametrize("suffix", ["", ".continuation.json", ".continuation.json.tmp"])
def test_never_resumes_or_overwrites_output(setup, suffix):
    path = Path(str(setup["paths"]["records"]) + suffix)
    path.write_bytes(b"retained unrelated evidence\n")
    with pytest.raises(tasks.TaskError):
        setup["run"]()
    assert path.read_bytes() == b"retained unrelated evidence\n"
    assert setup["submitted"] == []


def test_current_runtime_refuses_and_cli_requires_all_bindings(setup, monkeypatch):
    setup["provenance"]["pybamm"] = "wrong"
    with pytest.raises(tasks.TaskError, match="truth runtime"):
        setup["run"]()
    assert setup["submitted"] == []
    with pytest.raises(SystemExit):
        continuation.main([])
    calls = []
    monkeypatch.setattr(
        continuation, "run", lambda *a, **kw: calls.append((a, kw)) or 2
    )
    args = ["--binding-sha256", "0" * 64, "--workers", "1"]
    for name in setup["paths"]:
        args += ["--" + name.replace("_", "-"), str(setup["paths"][name])]
    assert continuation.main(args) == 2
    assert calls[0][1] == {"expected_sha256": "0" * 64, "workers": 1}


@pytest.mark.parametrize("field", ["schema", "orchestrator_sha256", "extra"])
def test_closed_root_contract_and_orchestrator_pin(setup, field):
    path = setup["paths"]["binding"]
    binding = json.loads(path.read_bytes())
    binding[field] = "0" * 64
    _write(path, binding)
    with pytest.raises(tasks.TaskError):
        setup["run"]()
    assert setup["submitted"] == []
    assert not setup["paths"]["records"].exists()
