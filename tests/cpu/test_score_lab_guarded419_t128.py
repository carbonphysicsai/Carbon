"""Frozen metadata/raw-delivery controls; CAL release stays explicitly unavailable."""

from __future__ import annotations

import builtins
import copy
import dataclasses
import hashlib
import importlib.util
import json
from collections import Counter
from pathlib import Path

import pytest

from carbon.design_search import tasks
from scripts.dev.battery import guarded_reference as guard
from scripts.dev.score_lab import guarded419_t9 as t9
from scripts.dev.score_lab import guarded419_t128 as t128

_spec = importlib.util.spec_from_file_location(
    "guarded419_t128_fixture",
    Path(__file__).resolve().parents[1] / "fixtures/guarded419_t128.py",
)
fixture = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fixture)


def new_rows(delivery):
    return t128._new_delivery(
        **{
            k: delivery[k]
            for k in (
                "binding",
                "manifest",
                "raw_chunks",
                "expected_binding_digest",
                "expected_manifest_digest",
            )
        }
    )


def offered_records(delivery):
    return [
        json.loads(line)
        for line in delivery["raw_chunks"]["synthetic-t128"].splitlines()
    ]


def test_frozen_exact128_roles_source_inputs_and_existing_partitions():
    rows = t128.input_rows()
    assert tasks.digest(rows) == t128.ROWS_DIGEST
    assert Counter(r["stage128_role"] for r in rows) == {
        "PUBLIC_CONSTRUCTION": 105,
        "INTERNAL_TRAIN_VALIDATION": 23,
    }
    jobs = t128.jobs()
    assert len(jobs) == 128 and len({j["case_id"] for j in jobs}) == 128
    root = Path(__file__).resolve().parents[2]
    source = json.loads(
        (
            root
            / "docs/development/evidence/battery-feasibility-02/plans/v3-train-plan.json"
        ).read_text(encoding="utf-8")
    )["jobs"]
    assert [r["prefix_position_1_based"] for r in rows] == list(range(1, 129))
    for r, j in zip(rows, jobs, strict=True):
        old = source[r["source_plan_index_0_based"]]
        assert old["case_id"] == r["source_case_id"]
        assert {k: old[k] for k in r["inputs"]} == r["inputs"]
        assert {k: j[k] for k in r["inputs"]} == r["inputs"]
        assert j["reference_role"] == r["stage128_role"]
    for index, (j, old) in enumerate(zip(jobs[:9], t9.jobs(), strict=True)):
        assert j["parent_input_index"] == old["parent_input_index"]
        assert j["reference_role"] == t128.CONSTRUCTION
        assert rows[index]["is_coverage_anchor"]
        with pytest.raises(tasks.TaskError):
            t128.validate_job(j)
    assert [len(t128.partition_jobs(i)) for i in (1, 2)] == [60, 59]
    assert t128.partition_jobs(1) + t128.partition_jobs(2) == jobs[9:]
    assert [
        sum(j["reference_role"] == t128.VALIDATION for j in t128.partition_jobs(i))
        for i in (1, 2)
    ] == [12, 11]
    for n, j in enumerate(jobs[9:], 1):
        assert j["reference_role"] == (
            t128.VALIDATION if n % 5 == 0 else t128.CONSTRUCTION
        )
        t128.validate_job(j)
        with pytest.raises(tasks.TaskError):
            t9.validate_job(j)
        with pytest.raises(tasks.TaskError):
            guard.validate_job(j)


@pytest.mark.parametrize("partition", [True, False, 0, 3, "1", None])
def test_partition_never_widens_or_uses_bool_as_integer(partition):
    with pytest.raises(tasks.TaskError):
        t128.partition_jobs(partition)


def test_raw_delivery_positive_both_roles_no_qualification(tmp_path):
    delivery = fixture.make_unadmitted_delivery(tmp_path)
    records, proof, tracking, states = new_rows(delivery)
    assert len(records) == len(proof) == len(tracking) == 2 and len(states) == 128
    assert {r["reference_role"] for r in records.values()} == {
        t128.CONSTRUCTION,
        t128.VALIDATION,
    }
    assert all(
        t["status"] == "TRACKING_COMPATIBLE"
        and t["checked_phases"] == t["required_phases"] == 181
        for t in tracking.values()
    )
    assert sum(s["extraction_state"] == "EXTRACTED" for s in states.values()) == 2
    assert all(
        p["raw_sha256"]
        == hashlib.sha256(delivery["raw_chunks"][p["chunk_id"]]).hexdigest()
        for p in proof.values()
    )
    assert not isinstance(records, t128.ValidatedT128Evidence)
    with pytest.raises(tasks.TaskError):
        t128.validate_for(
            records,
            expected_binding_digest=delivery["expected_binding_digest"],
            expected_manifest_digest=delivery["expected_manifest_digest"],
            scope="SYNTHETIC_FIXTURE",
        )


def test_complete119_raw_inventory_keeps_all23_validation_and9_missing_reuses(tmp_path):
    delivery = fixture.make_unadmitted_delivery(tmp_path, all_rows=True)
    records, proof, tracking, states = new_rows(delivery)
    assert len(records) == len(proof) == len(tracking) == 119
    assert len(states) == 128
    assert Counter(r["reference_role"] for r in records.values()) == {
        t128.CONSTRUCTION: 96,
        t128.VALIDATION: 23,
    }
    assert all(
        s["extraction_state"] == "EXTRACTED"
        for jid, s in states.items()
        if jid in records
    )
    assert all(states[j["case_id"]]["raw_status"] == "MISSING" for j in t128.jobs()[:9])
    assert all(t["status"] == "TRACKING_COMPATIBLE" for t in tracking.values())


@pytest.mark.parametrize(
    "field,value",
    [
        ("c1", 9.0),
        ("soc0", True),
        ("parent_input_index", -1),
        ("reference_role", "PUBLIC_CONSTRUCTION"),
        ("schema", t9.RECORD),
    ],
)
def test_rehashed_raw_input_role_type_and_context_substitution_refused(
    tmp_path, field, value
):
    delivery = fixture.make_unadmitted_delivery(tmp_path)
    rows = offered_records(delivery)
    # Second row is the literal validation role: changing it to construction is a real attack.
    rows[1][field] = value
    fixture.refresh_delivery(delivery, rows)
    with pytest.raises(tasks.TaskError):
        new_rows(delivery)


def test_rehashed_observer_role_and_duplicate_mapping_refused(tmp_path):
    delivery = fixture.make_unadmitted_delivery(tmp_path)
    rows = offered_records(delivery)
    rows[1]["reference_identity"] = t128.observer(t128.CONSTRUCTION)
    fixture.refresh_delivery(delivery, rows)
    with pytest.raises(tasks.TaskError):
        new_rows(delivery)
    delivery = fixture.make_unadmitted_delivery(tmp_path / "fresh")
    delivery["manifest"]["chunks"][0]["rows"][1] = copy.deepcopy(
        delivery["manifest"]["chunks"][0]["rows"][0]
    )
    delivery["expected_manifest_digest"] = tasks.digest(delivery["manifest"])
    with pytest.raises(tasks.TaskError):
        new_rows(delivery)


def test_missing_failed_and_nonfinite_rows_retained_not_repaired(tmp_path):
    delivery = fixture.make_unadmitted_delivery(tmp_path)
    rows = offered_records(delivery)
    rows[0]["status"] = "REFERENCE_SOLVER_FAILED"
    rows[1]["whole_programme"]["v_max_v"] = float("nan")
    fixture.refresh_delivery(delivery, rows)
    records, proof, tracking, states = new_rows(delivery)
    assert len(records) == len(proof) == 2 and len(states) == 128
    assert all(t["status"] == "REFERENCE_UNRESOLVED" for t in tracking.values())
    assert states[rows[0]["case_id"]]["raw_status"] == "REFERENCE_SOLVER_FAILED"
    assert states[rows[0]["case_id"]]["extraction_state"] != "EXTRACTED"
    assert states[rows[1]["case_id"]]["extraction_state"] != "EXTRACTED"
    assert records[rows[1]["case_id"]]["whole_programme"]["v_max_v"] is None
    assert b"NaN" in delivery["raw_chunks"]["synthetic-t128"]
    assert sum(s["raw_status"] == "MISSING" for s in states.values()) == 126


@pytest.mark.parametrize("mutation", ["role", "order", "source", "chunks", "fixture"])
def test_rehashed_binding_manifest_or_public_fixture_refused(tmp_path, mutation):
    delivery = fixture.make_unadmitted_delivery(tmp_path)
    if mutation == "role":
        delivery["binding"]["jobs"][13]["reference_role"] = t128.CONSTRUCTION
    elif mutation == "order":
        delivery["manifest"]["offered_job_ids"].reverse()
    elif mutation == "source":
        delivery["manifest"]["chunks"][0]["source_commit"] = "f" * 40
    elif mutation == "chunks":
        delivery["raw_chunks"]["unregistered"] = b"{}\n"
    else:
        delivery["binding"]["scope"] = "PUBLIC_DEVELOPMENT"
        delivery["manifest"]["scope"] = "PUBLIC_DEVELOPMENT"
    delivery["expected_binding_digest"] = tasks.digest(delivery["binding"])
    delivery["manifest"]["binding_digest"] = delivery["expected_binding_digest"]
    delivery["expected_manifest_digest"] = tasks.digest(delivery["manifest"])
    with pytest.raises(tasks.TaskError):
        new_rows(delivery)


def test_anchors_cannot_be_returned_as_new_jobs(tmp_path):
    delivery = fixture.make_unadmitted_delivery(tmp_path)
    fixture.refresh_delivery(delivery, [fixture.record(t128.jobs()[0])])
    with pytest.raises(tasks.TaskError):
        new_rows(delivery)


def test_nominal_constructor_closed_and_immutable():
    with pytest.raises(tasks.TaskError):
        t128.ValidatedT128Evidence(b"{}")
    assert dataclasses.is_dataclass(t128.ValidatedT128Evidence)


def test_missing_cal_api_is_typed_and_never_promotes_caller_pass(tmp_path, monkeypatch):
    delivery = fixture.make_unadmitted_delivery(tmp_path)
    original = builtins.__import__

    def without_cal(name, globals=None, locals=None, fromlist=(), level=0):
        if (
            name == "scripts.dev.score_lab"
            and "guarded419_calibration_continue" in fromlist
        ):
            raise ImportError("deliberately absent CAL adapter")
        return original(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", without_cal)
    delivery["calibration_evidence"] = {"status": "PASS", "expected_case_count": 15}
    with pytest.raises(t128.CalibrationPrerequisiteUnavailable):
        t128.validate_delivery(**delivery)


def test_forged_or_failed_g0_prevents_any_seal_before_cal(tmp_path):
    delivery = fixture.make_unadmitted_delivery(tmp_path)
    receipt = json.loads(delivery["t9_delivery"]["g0_receipt"])
    receipt["status"] = "PASS"
    raw = (json.dumps(receipt, sort_keys=True) + "\n").encode()
    prior = delivery["t9_delivery"]
    prior["g0_receipt"] = raw
    prior["binding"]["g0"]["receipt_sha256"] = hashlib.sha256(raw).hexdigest()
    prior["expected_binding_digest"] = tasks.digest(prior["binding"])
    prior["manifest"]["binding_digest"] = prior["expected_binding_digest"]
    prior["expected_manifest_digest"] = tasks.digest(prior["manifest"])
    delivery["binding"]["prerequisites"]["t9"] = {
        "binding_digest": prior["expected_binding_digest"],
        "manifest_digest": prior["expected_manifest_digest"],
    }
    delivery["expected_binding_digest"] = tasks.digest(delivery["binding"])
    delivery["manifest"]["binding_digest"] = delivery["expected_binding_digest"]
    delivery["expected_manifest_digest"] = tasks.digest(delivery["manifest"])
    with pytest.raises(tasks.TaskError, match="G0 receipt disagrees"):
        t128.validate_delivery(**delivery)
