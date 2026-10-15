"""Synthetic fake-worker controls only; no solver/provider or measured science."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from carbon.battery import truth_env
from carbon.design_search import tasks
from scripts.dev.battery import feasibility02 as worker
from scripts.dev.score_lab import owner_v3 as owner
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
    source_paths = {
        *producer.SOURCES,
        producer.EXPORTER,
        producer.NUMERICS,
        "scripts/dev/score_lab/owner_v3.py",
        "carbon/design_search/tasks.py",
    }
    files = {
        p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in source_paths
    }
    binding = {
        "schema": "carbon.scorelab.calibration-execution.v1",
        "scope": "SYNTHETIC_FIXTURE",
        "execution_source": "a" * 40,
        "source_files": files,
        "plan": plan,
        "plan_digest": tasks.digest(plan),
        "policy_digest": tasks.digest(numerics.POLICY),
        "observer": producer._observer(plan, {"files": files}),
    }
    provenance = {
        "schema": "carbon.battery.solver-provenance.v1",
        "solver_image": "study@" + plan["image_digest"],
        "overlay_lock_sha256": "sha256:" + plan["overlay_sha256"],
        "overlay_lock": "scripts/dev/exam_design/locks/battery-overlay.lock.json",
        "pybamm": "26.8.0.0",
    }
    job_path, binding_path, records = (
        tmp_path / p for p in ("jobs.json", "binding.json", "records.jsonl")
    )
    submitted, evaluated = [], []

    class Future:
        def __init__(self, fn, job):
            self.fn, self.job = fn, job

        def result(self):
            evaluated.append(self.job["case_id"])
            return self.fn(self.job)

    class Pool:
        def __init__(self, workers):
            assert workers == 2

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def submit(self, fn, job):
            # A next-tuple submission must see the previous assessment already
            # persisted. This catches moving the check after an eager whole map.
            if submitted and len(submitted) % 3 == 0:
                receipt = json.loads(
                    records.with_name(records.name + ".calibration.json").read_bytes()
                )
                assert len(receipt["per_completed_triple"]) == len(submitted) // 3
                assert receipt["per_completed_triple"][-1]["failed_cases"] == []
            submitted.append(job["case_id"])
            return Future(fn, job)

    monkeypatch.setattr(worker, "ProcessPoolExecutor", Pool)
    # Reverse completion order proves grouping uses authenticated rung identity,
    # not arrival order or a positional zip with submitted jobs.
    monkeypatch.setattr(worker, "as_completed", lambda futures: reversed(list(futures)))
    monkeypatch.setattr(worker, "_timed", _record)
    monkeypatch.setattr(truth_env, "provenance", lambda _: dict(provenance))

    def write():
        job_path.write_text(json.dumps(jobs), encoding="utf-8")
        raw = json.dumps(binding).encode()
        binding_path.write_bytes(raw)
        return hashlib.sha256(raw).hexdigest()

    def run():
        return worker.solve_calibration(job_path, records, 2, binding_path, write())

    def receipt():
        return json.loads(
            records.with_name(records.name + ".calibration.json").read_bytes()
        )

    return {
        "plan": plan,
        "jobs": jobs,
        "binding": binding,
        "provenance": provenance,
        "job_path": job_path,
        "binding_path": binding_path,
        "records": records,
        "submitted": submitted,
        "evaluated": evaluated,
        "write": write,
        "run": run,
        "receipt": receipt,
    }


def test_all_good_triples_advance_but_pilot_never_releases_full_calibration(setup):
    assert setup["run"]() == 0
    receipt = setup["receipt"]()
    assert len(setup["submitted"]) == len(setup["evaluated"]) == 18
    assert receipt["status"] == "COMPATIBLE_PILOT_ONLY"
    assert receipt["calibration"]["expected_case_count"] == 6
    assert receipt["calibration"]["missing_cases"] == []
    assert receipt["full_calibration_release"] is False
    assert receipt["qualification"] is False
    assert len(receipt["per_completed_triple"]) == 6
    body = setup["records"].read_bytes()
    assert receipt["records_sha256"] == hashlib.sha256(body).hexdigest()
    assert len(body.splitlines()) == 18
    assert all(json.loads(line)["fixture"] for line in body.splitlines())


@pytest.mark.parametrize("quantity", sorted(numerics.QUANTITIES))
def test_first_failed_triple_stops_all_later_dispatch(setup, monkeypatch, quantity):
    def bad(job):
        record = _record(job)
        if job["rung"] == 3:
            if quantity == "minutes":
                record["soc_clock"].update(minutes=50.0, time_s=3000.0)
            elif quantity == "q30_over_q1":
                record["q30_over_q1"] = 0.9
            elif quantity == "v_max_v":
                record["whole_programme"]["v_max_v"] = 4.3
            else:
                key = "t_max_c" if quantity == "charging_t_max_c" else quantity
                for cycle in record["per_cycle"]:
                    for phase in cycle["phases"].values():
                        phase[key] = 50.0 if quantity == "charging_t_max_c" else -0.1
        return record

    monkeypatch.setattr(worker, "_timed", bad)
    assert setup["run"]() == 2
    receipt = setup["receipt"]()
    assert len(setup["submitted"]) == len(setup["evaluated"]) == 3
    assert receipt["status"] == "NUMERICAL_CALIBRATION_INADEQUATE"
    assert len(receipt["calibration"]["failed_cases"]) == 1
    assert len(receipt["calibration"]["missing_cases"]) == 5
    assert list(receipt["per_job"].values()).count("NOT_DISPATCHED") == 15
    assert len(setup["records"].read_bytes().splitlines()) == 3


@pytest.mark.parametrize("failure", ["solver", "infra", "not-reached", "partial"])
def test_failed_or_incomplete_rows_survive_and_never_release(
    setup, monkeypatch, failure
):
    def incomplete(job):
        record = _record(job)
        if job["rung"] == 2:
            if failure == "infra":
                raise RuntimeError("synthetic worker failure")
            if failure == "solver":
                record["status"] = "REFERENCE_SOLVER_FAILED"
            elif failure == "not-reached":
                record["soc_clock"] = {"status": "NOT_REACHED"}
            else:
                record["per_cycle"].pop()
        return record

    monkeypatch.setattr(worker, "_timed", incomplete)
    assert setup["run"]() == 2
    receipt = setup["receipt"]()
    assert receipt["status"] == "INCOMPLETE_REFERENCE"
    assert receipt["full_calibration_release"] is False
    assert len(setup["submitted"]) == 3
    rows = [json.loads(line) for line in setup["records"].read_bytes().splitlines()]
    assert len(rows) == 3
    if failure in ("solver", "infra"):
        assert {r["status"] for r in rows} == {
            "OK",
            "FAILED_INFRA" if failure == "infra" else "REFERENCE_SOLVER_FAILED",
        }


@pytest.mark.parametrize(
    "drift",
    [
        "source",
        "observer",
        "plan",
        "policy",
        "case",
        "rung",
        "subset",
        "runtime",
        "scope",
    ],
)
def test_binding_drift_refused_before_any_dispatch(setup, drift):
    if drift == "source":
        setup["binding"]["source_files"][producer.NUMERICS] = "0" * 64
    elif drift == "observer":
        setup["binding"]["observer"]["cycles"] = 1
    elif drift == "plan":
        setup["binding"]["plan_digest"] = "sha256:" + "0" * 64
    elif drift == "policy":
        setup["binding"]["policy_digest"] = "sha256:" + "0" * 64
    elif drift == "scope":
        setup["binding"]["scope"] = "LIVE"
    elif drift == "runtime":
        setup["provenance"]["pybamm"] = "wrong"
    elif drift == "subset":
        setup["jobs"]["jobs"].pop()
    else:
        setup["jobs"]["jobs"][0]["case_id" if drift == "case" else "rung"] = "wrong"
    with pytest.raises(tasks.TaskError):
        setup["run"]()
    assert setup["submitted"] == []
    assert not setup["records"].exists()


def test_binding_byte_digest_refused_before_dispatch(setup):
    setup["write"]()
    with pytest.raises(tasks.TaskError, match="binding bytes"):
        worker.solve_calibration(
            setup["job_path"], setup["records"], 2, setup["binding_path"], "0" * 64
        )
    assert not setup["submitted"]


@pytest.mark.parametrize("drift", ["case_id", "rung", "c1", "soc0", "refined"])
def test_returned_identity_drift_retained_and_stops(setup, monkeypatch, drift):
    def wrong(job):
        record = _record(job)
        if job["rung"] == 2:
            record[drift] = {
                "case_id": "wrong",
                "rung": 3,
                "c1": 1.5,
                "soc0": 0.12,
                "refined": False,
            }[drift]
        return record

    monkeypatch.setattr(worker, "_timed", wrong)
    with pytest.raises(tasks.TaskError):
        setup["run"]()
    assert len(setup["submitted"]) == 3
    assert len(setup["records"].read_bytes().splitlines()) == 3
    assert setup["receipt"]()["status"] == "INTERRUPTED_OR_INVALID_REFERENCE"


@pytest.mark.parametrize("workers", [0, 3, True])
def test_worker_bound_rejects_before_dispatch(setup, workers):
    with pytest.raises(tasks.TaskError, match="one or two"):
        worker.solve_calibration(
            setup["job_path"],
            setup["records"],
            workers,
            setup["binding_path"],
            setup["write"](),
        )
    assert not setup["submitted"]


def test_existing_output_is_not_resumed_or_overwritten(setup):
    setup["records"].write_text("retained unrelated bytes\n", encoding="utf-8")
    with pytest.raises(tasks.TaskError, match="fresh"):
        setup["run"]()
    assert setup["records"].read_text(encoding="utf-8") == "retained unrelated bytes\n"
    assert not setup["submitted"]


def test_interruption_retains_partial_rows_and_undispatched_menu(setup, monkeypatch):
    def interrupt(job):
        if job["rung"] == 2:
            raise KeyboardInterrupt
        return _record(job)

    monkeypatch.setattr(worker, "_timed", interrupt)
    with pytest.raises(KeyboardInterrupt):
        setup["run"]()
    assert len(setup["submitted"]) == 3
    assert len(setup["records"].read_bytes().splitlines()) == 1
    receipt = setup["receipt"]()
    assert receipt["status"] == "INTERRUPTED_OR_INVALID_REFERENCE"
    assert list(receipt["per_job"].values()).count("NOT_DISPATCHED") == 15
    assert receipt["calibration"]["status"] == "INCOMPLETE_REFERENCE"


def test_default_cli_still_calls_ordinary_solve(monkeypatch):
    calls = []
    monkeypatch.setattr(worker, "solve", lambda *args: calls.append(args))
    assert (
        worker.main(
            [
                "solve",
                "--jobs",
                "jobs.json",
                "--records",
                "records.jsonl",
                "--workers",
                "4",
            ]
        )
        == 0
    )
    assert calls == [(Path("jobs.json"), Path("records.jsonl"), 4)]


def test_calibration_cli_requires_pair_and_in_image_solve(monkeypatch):
    for argv in (
        ["solve", "--calibration-binding", "binding.json"],
        [
            "plan",
            "--calibration-binding",
            "b",
            "--calibration-binding-sha256",
            "0" * 64,
        ],
    ):
        with pytest.raises(SystemExit):
            worker.main(argv)
    calls = []
    monkeypatch.setattr(worker, "solve_calibration", lambda *a: calls.append(a) or 2)
    assert (
        worker.main(
            [
                "solve",
                "--jobs",
                "j",
                "--records",
                "r",
                "--workers",
                "2",
                "--calibration-binding",
                "b",
                "--calibration-binding-sha256",
                "0" * 64,
            ]
        )
        == 2
    )
    assert calls == [(Path("j"), Path("r"), 2, Path("b"), "0" * 64)]
