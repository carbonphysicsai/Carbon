"""Synthetic delivery and fake executor; no physical solve or authority claim."""

from __future__ import annotations

import copy
import dataclasses
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from carbon.battery import truth_env
from carbon.design_search import tasks
from scripts.dev.battery import feasibility02 as worker
from scripts.dev.battery import guarded_reference as guard
from scripts.dev.score_lab import guarded419_t9 as t9

_spec = importlib.util.spec_from_file_location(
    "guarded419_t9_fixture",
    Path(__file__).resolve().parents[1] / "fixtures/guarded419_t9.py",
)
fixture = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fixture)


def snapshot(delivery):
    evidence = t9.validate_delivery(**delivery)
    return t9.validate_for(
        evidence,
        expected_binding_digest=delivery["expected_binding_digest"],
        expected_manifest_digest=delivery["expected_manifest_digest"],
        scope=delivery["binding"]["scope"],
    )


def test_nine_exact_anchors_sealed_snapshot_and_strict_g0_separation(tmp_path):
    delivery = fixture.make_delivery(tmp_path)
    result = snapshot(delivery)
    assert [j["parent_input_index"] for j in result["jobs"]] == [
        1,
        2,
        11,
        16,
        28,
        121,
        248,
        726,
        2002,
    ]
    assert (
        len(result["records"])
        == len(result["source_rows"])
        == len(result["tracking"])
        == 9
    )
    assert all(
        r["status"] == "TRACKING_COMPATIBLE" and r["checked_phases"] == 181
        for r in result["tracking"].values()
    )
    assert all(r["extraction_state"] == "EXTRACTED" for r in result["per_job"].values())
    for job in result["jobs"]:
        t9.validate_job(job)
        with pytest.raises(tasks.TaskError):
            guard.validate_job(job)
        assert (
            guard.tracking_report(result["records"][job["case_id"]])["status"]
            == "REFERENCE_UNRESOLVED"
        )
    evidence = t9.validate_delivery(**delivery)
    result["jobs"].clear()
    assert (
        len(
            t9.validate_for(
                evidence,
                expected_binding_digest=delivery["expected_binding_digest"],
                expected_manifest_digest=delivery["expected_manifest_digest"],
                scope="SYNTHETIC_FIXTURE",
            )["jobs"]
        )
        == 9
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        evidence._snapshot = b"{}"
    with pytest.raises(tasks.TaskError):
        t9.ValidatedT9Evidence(b"{}")
    with pytest.raises(tasks.TaskError):
        t9.validate_for(
            {"status": "PASS"},
            expected_binding_digest=delivery["expected_binding_digest"],
            expected_manifest_digest=delivery["expected_manifest_digest"],
            scope="SYNTHETIC_FIXTURE",
        )
    with pytest.raises(tasks.TaskError):
        t9.validate_for(
            evidence,
            expected_binding_digest=delivery["expected_binding_digest"],
            expected_manifest_digest=delivery["expected_manifest_digest"],
            scope="PUBLIC_DEVELOPMENT",
        )


@pytest.mark.parametrize("kind", ["missing", "failed", "nonfinite", "wrong_target"])
def test_all_offered_rows_retained_with_missing_failed_nonfinite_or_bad_guard(
    tmp_path, kind
):
    delivery = fixture.make_delivery(tmp_path)
    rows = [json.loads(line) for line in delivery["raw_chunks"]["t9"].splitlines()]
    jid = rows[-1]["case_id"]
    if kind == "missing":
        rows.pop()
    elif kind == "failed":
        rows[-1]["status"] = "FAILED_INFRA"
    elif kind == "nonfinite":
        rows[-1]["per_cycle"][0]["phases"]["cc1"]["plating_min_v"] = float("nan")
    else:
        rows[-1]["per_cycle"][0]["phases"]["cv"]["voltage_contact_observation"][
            "descriptor"
        ]["value"] = 4.2
    fixture.refresh_delivery(delivery, rows)
    result = snapshot(delivery)
    assert len(result["jobs"]) == len(result["per_job"]) == 9
    if kind == "missing":
        assert jid not in result["records"] and jid not in result["source_rows"]
        assert result["per_job"][jid]["raw_status"] == "MISSING"
    elif kind == "nonfinite":
        assert result["per_job"][jid]["extraction_state"] == "REFERENCE_UNRESOLVED"
        assert (
            result["records"][jid]["per_cycle"][0]["phases"]["cc1"]["plating_min_v"]
            is None
        )
    else:
        assert result["tracking"][jid]["status"] == "REFERENCE_UNRESOLVED"
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize(
    "kind",
    [
        "wrong_job",
        "duplicate",
        "role",
        "source",
        "unmapped",
        "raw_drift",
        "old_schema",
        "old_context",
    ],
)
def test_rehashed_wrong_delivery_or_unbound_bytes_are_refused(tmp_path, kind):
    delivery = fixture.make_delivery(tmp_path)
    rows = [json.loads(line) for line in delivery["raw_chunks"]["t9"].splitlines()]
    if kind == "wrong_job":
        rows[0]["soc0"] = 0.2
    if kind == "role":
        rows[0]["reference_role"] = "PUBLIC_EVALUATION"
    if kind == "duplicate":
        rows[1] = copy.deepcopy(rows[0])
    if kind == "old_schema":
        rows[0]["schema"] = guard.RECORD
    if kind == "old_context":
        rows[0]["reference_identity"] = guard.observer({})
    fixture.refresh_delivery(delivery, rows)
    if kind == "source":
        delivery["manifest"]["chunks"][0]["source_commit"] = "f" * 40
    if kind == "unmapped":
        delivery["manifest"]["chunks"][0]["rows"].pop()
    if kind == "raw_drift":
        delivery["raw_chunks"]["t9"] += b" "
    delivery["expected_manifest_digest"] = tasks.digest(delivery["manifest"])
    with pytest.raises(tasks.TaskError):
        snapshot(delivery)


@pytest.mark.parametrize(
    "kind", ["bytes", "partial", "lying_receipt", "wrong_tracking", "source"]
)
def test_g0_prerequisite_is_reduced_not_a_pass_flag(tmp_path, kind):
    delivery = fixture.make_delivery(tmp_path)
    if kind == "bytes":
        delivery["g0_raw"] += b" "
    else:
        if kind == "lying_receipt":
            receipt = json.loads(delivery["g0_receipt"])
            receipt["qualification"] = True
            delivery["g0_receipt"] = json.dumps(receipt, sort_keys=True).encode()
        elif kind == "source":
            prior = json.loads(delivery["g0_binding"])
            prior["source_files"]["carbon/battery/reference.py"] = "f" * 64
            delivery["g0_binding"] = json.dumps(prior, sort_keys=True).encode()
        else:
            rows = [json.loads(line) for line in delivery["g0_raw"].splitlines()]
            if kind == "partial":
                rows.pop()
            else:
                rows[0]["observation_provenance"]["runtime_voltage_scale"] = None
            delivery["g0_raw"] = b"".join(
                (json.dumps(row, sort_keys=True) + "\n").encode() for row in rows
            )
        delivery["binding"]["g0"] = {
            k + "_sha256": hashlib.sha256(delivery[name]).hexdigest()
            for k, name in (
                ("binding", "g0_binding"),
                ("records", "g0_raw"),
                ("receipt", "g0_receipt"),
            )
        }
        delivery["expected_binding_digest"] = tasks.digest(delivery["binding"])
        rows = [json.loads(line) for line in delivery["raw_chunks"]["t9"].splitlines()]
        fixture.refresh_delivery(delivery, rows)
    with pytest.raises(tasks.TaskError):
        snapshot(delivery)


@pytest.mark.parametrize("failure", ["none", "infra", "interrupt", "partial_submit"])
def test_existing_worker_adapter_durable_partial_outputs_no_next_stage(
    tmp_path, monkeypatch, failure
):
    delivery = fixture.make_delivery(tmp_path, scope="PUBLIC_DEVELOPMENT")
    submitted = []

    class Future:
        def __init__(self, job):
            self.job = job

        def result(self):
            if self.job == t9.jobs()[0]:
                if failure == "infra":
                    raise RuntimeError("synthetic infrastructure")
                if failure == "interrupt":
                    raise KeyboardInterrupt
            return fixture.record(self.job, fixture=False)

    class Pool:
        def __init__(self, workers):
            assert workers == 2

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def submit(self, fn, job):
            assert fn is worker._timed
            if failure == "partial_submit" and len(submitted) == 2:
                raise RuntimeError("synthetic submission failure")
            submitted.append(job)
            return Future(job)

    monkeypatch.setattr(t9, "ProcessPoolExecutor", Pool)
    monkeypatch.setattr(t9, "as_completed", lambda futures: list(futures))
    monkeypatch.setattr(
        truth_env,
        "provenance",
        lambda _: fixture.record(guard.first_jobs()[0])["solver_provenance"],
    )
    output = tmp_path / "actual-path-toy.jsonl"
    args = {
        k: delivery[k]
        for k in ("g0_binding", "g0_raw", "g0_receipt", "expected_binding_digest")
    }
    if failure in ("interrupt", "partial_submit"):
        with pytest.raises((KeyboardInterrupt, RuntimeError)):
            t9.run(delivery["binding"], **args, records_path=output, root=tmp_path)
    else:
        assert (
            t9.run(delivery["binding"], **args, records_path=output, root=tmp_path) == 0
        )
    receipt = json.loads(output.with_name(output.name + ".t9.json").read_bytes())
    assert receipt["records_sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()
    assert len(receipt["per_job"]) == 9
    assert (
        receipt["qualification"]
        is receipt["evaluation_release"]
        is receipt["n1_release"]
        is receipt["full_calibration_release"]
        is False
    )
    if failure == "partial_submit":
        assert list(receipt["per_job"].values()).count("SUBMITTED") == 2
        assert list(receipt["per_job"].values()).count("NOT_DISPATCHED") == 7
    else:
        assert len(submitted) == 9
    if failure == "infra":
        assert list(receipt["per_job"].values()).count("FAILED_INFRA") == 1
        first = t9.jobs()[0]["case_id"]
        assert receipt["evidence"]["per_job"][first]["raw_status"] == "FAILED_INFRA"
        assert (
            receipt["evidence"]["tracking"][first]["status"] == "REFERENCE_UNRESOLVED"
        )
    if failure == "none":
        assert len(output.read_bytes().splitlines()) == 9


def test_bad_g0_refuses_before_output_or_pool(tmp_path, monkeypatch):
    delivery = fixture.make_delivery(tmp_path, scope="PUBLIC_DEVELOPMENT")
    monkeypatch.setattr(
        t9, "ProcessPoolExecutor", lambda *_: pytest.fail("pool before G0 admission")
    )
    output = tmp_path / "must-not-exist"
    args = {
        k: delivery[k]
        for k in ("g0_binding", "g0_raw", "g0_receipt", "expected_binding_digest")
    }
    args["g0_raw"] += b" "
    with pytest.raises(tasks.TaskError):
        t9.run(delivery["binding"], **args, records_path=output, root=tmp_path)
    assert not output.exists()


def test_t9_solver_failure_retains_requested_context_without_acceptance(monkeypatch):
    import sys
    from types import SimpleNamespace

    monkeypatch.setitem(
        sys.modules, "pybamm", SimpleNamespace(set_logging_level=lambda _: None)
    )

    def fail(_):
        raise RuntimeError("synthetic pre-solve failure")

    monkeypatch.setattr(worker, "_simulation", fail)
    row = worker.solve_one(t9.jobs()[0])
    assert row["status"] == "REFERENCE_SOLVER_FAILED"
    assert row["reference_identity"] == t9.observer()
    assert t9.tracking_report(row)["status"] == "REFERENCE_UNRESOLVED"


@pytest.mark.parametrize("suffix", ["", ".t9.json", ".t9.json.tmp"])
def test_dangling_output_is_occupied_and_never_dispatched(
    tmp_path, monkeypatch, suffix
):
    delivery = fixture.make_delivery(tmp_path, scope="PUBLIC_DEVELOPMENT")
    output = tmp_path / "fresh-only.jsonl"
    occupied = Path(str(output) + suffix)
    target = tmp_path / "outside-absent"
    occupied.symlink_to(target)
    monkeypatch.setattr(
        t9, "ProcessPoolExecutor", lambda *_: pytest.fail("occupied output dispatched")
    )
    monkeypatch.setattr(
        truth_env,
        "provenance",
        lambda _: fixture.record(guard.first_jobs()[0])["solver_provenance"],
    )
    args = {
        k: delivery[k]
        for k in ("g0_binding", "g0_raw", "g0_receipt", "expected_binding_digest")
    }
    with pytest.raises(tasks.TaskError, match="fresh output"):
        t9.run(delivery["binding"], **args, records_path=output, root=tmp_path)
    assert occupied.is_symlink()
    assert not target.exists()
