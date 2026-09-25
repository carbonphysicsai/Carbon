"""The battery truth service (M2): typed reference failures, bounds, resume.

Claims tested:
- each way a solve can end has exactly one typed status: OK, solver failure,
  timeout, worker death and the memory bound, the last two being FAILED_INFRA;
- resume skips terminal records and retries only FAILED_INFRA;
- the promoted reference configuration is the campaign's pinned one, and the
  truth image pins the overlay lock's exact bytes;
- a reference failure is never charged to a candidate: the exam withdraws the
  case for every model.
"""

import json
import os
import time

import numpy as np

from carbon.battery import exam, truth
from carbon.battery import reference as ours


def job(case_id, **extra):
    return {
        "case_id": case_id,
        "c1": 1.0,
        "c2": 0.5,
        "t_amb_c": 25.0,
        "soc0": 0.2,
        **extra,
    }


def fake_solver(job):
    kind = job["case_id"].split("-")[0]
    if kind == "raise":
        raise RuntimeError("solver diverged")
    if kind == "hang":
        time.sleep(30)
    if kind == "die":
        os._exit(3)
    if kind == "hog":
        bytearray(512 * 1024**2)
    if kind == "flaky" and not os.path.exists(job["marker"]):
        open(job["marker"], "w").close()
        os._exit(9)
    return {"status": "OK", "outputs": {"plating_margin_v": 0.01}}


def service(tmp_path, **kw):
    kw = {"solver": fake_solver, "timeout_s": 2.0, "memory_bytes": 256 * 1024**2, **kw}
    return truth.TruthService(tmp_path / "records.jsonl", **kw)


def test_every_ending_is_typed(tmp_path):
    svc = service(tmp_path, workers=3)
    report = svc.run(
        [job("ok-1"), job("raise-1"), job("hang-1"), job("die-1"), job("hog-1")]
    )
    status = {r["case_id"]: r for r in svc.records()}
    assert status["ok-1"]["status"] == truth.OK
    assert status["raise-1"]["status"] == truth.SOLVER_FAILED
    assert status["hang-1"]["status"] == truth.TIMEOUT
    assert status["die-1"]["status"] == truth.FAILED_INFRA
    assert status["die-1"]["reason"] == "worker_exit"
    assert status["hog-1"]["status"] == truth.FAILED_INFRA
    assert status["hog-1"]["reason"] == "memory_bound"
    assert report["counts"] == {
        "OK": 1,
        "REFERENCE_SOLVER_FAILED": 1,
        "REFERENCE_TIMEOUT": 1,
        "FAILED_INFRA": 2,
    }


def test_resume_retries_only_infrastructure_failures(tmp_path):
    svc = service(tmp_path)
    marker = str(tmp_path / "marker")
    jobs = [job("ok-1"), job("raise-1"), job("flaky-1", marker=marker)]
    first = svc.run(jobs)
    assert first["counts"]["FAILED_INFRA"] == 1
    second = svc.run(jobs)
    assert second["skipped_completed"] == 2
    assert second["counts"] == {
        "OK": 1,
        "REFERENCE_SOLVER_FAILED": 0,
        "REFERENCE_TIMEOUT": 0,
        "FAILED_INFRA": 0,
    }
    third = svc.run(jobs)
    assert third["skipped_completed"] == 3 and sum(third["counts"].values()) == 0


def test_the_reference_is_the_campaigns_pinned_configuration():
    from scripts.dev.exam_design import battery_reference as research

    assert ours.SPEC == research.SPEC
    assert ours.STORED_VARIABLES == research.STORED_VARIABLES
    assert np.array_equal(ours.time_grid(), research.time_grid())
    lock = json.loads(open(truth.LOCK_PATH).read())  # noqa: SIM115
    assert lock["root_requirement"] == truth.TRUTH_IMAGE["root_requirement"]
    assert lock["base_image"] == truth.TRUTH_IMAGE["base_image"]
    assert truth.lock_digest().startswith("sha256:")
    import sys

    assert "pybamm" not in sys.modules  # importing the module never loads PyBaMM


def test_a_reference_failure_is_never_charged_to_a_candidate():
    shapes = {
        "voltage_v": (3,),
        "temperature_c": (3,),
        "plating_margin_v": (),
        "capacity_ah": (2,),
    }
    good = {
        "status": "OK",
        "inputs": {"t_amb_c": 25.0},
        "outputs": {
            "voltage_v": [3.6, 3.9, 4.1],
            "temperature_c": [25.0, 26.0, 27.0],
            "plating_margin_v": 0.02,
            "capacity_ah": [4.8, 4.79],
        },
    }
    refs = {
        "a": dict(good, case_id="a"),
        "b": {"case_id": "b", "status": truth.TIMEOUT},
    }
    tol = exam.Tolerances(0.01, 0.01, 0.01, 0.01, 5.8)
    scales = {"s_v": 0.1, "s_t": 1.0, "s_eta": 0.01, "s_q1": 0.05, "s_fade": 0.002}
    store = exam.CaseStore(refs, {"a": 3.6, "b": 3.6}, tol, scales, shapes)
    pred = {k: good["outputs"][k] for k in shapes}
    rows, agg = exam.evaluate({"a": pred, "b": pred}, ["a", "b"], store)
    assert [r["state"] for r in rows] == [exam.SCORABLE, exam.REFERENCE_INVALID]
    assert agg["n_reference_invalid"] == 1 and agg["n_gate_failed"] == 0
    assert agg["eligible"] and agg["n_scored"] == 1
    # A candidate's missing prediction is infrastructure, not a gate failure.
    rows, agg = exam.evaluate({"a": None}, ["a"], store, infra_failed={"a"})
    assert rows[0]["state"] == exam.FAILED_INFRA and agg["n_gate_failed"] == 0
