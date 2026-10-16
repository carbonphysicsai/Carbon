"""Unsealed synthetic controls; no invented successful CAL or EVAL certificate."""

from __future__ import annotations

import builtins
import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from carbon.design_search import tasks
from scripts.dev.battery import guarded_reference as guard
from scripts.dev.score_lab import guarded419_eval as producer
from scripts.dev.score_lab import owner_v3 as owner
from scripts.dev.score_lab import owner_v3_numerics as numerics
from scripts.dev.score_lab import owner_v3_panel_export as legacy

_spec = importlib.util.spec_from_file_location(
    "guarded419_t9_fixture_for_eval",
    Path(__file__).resolve().parents[1] / "fixtures/guarded419_t9.py",
)
fixture = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fixture)


def original_plan():
    # Input-only original plan used ONLY to exercise unsealed helper primitives.
    # It can never enter the new build/context acceptance path.
    return {**producer.input_plan(), "job": owner.JOB}


def original_jobs():
    plan = original_plan()
    return owner.acquisition_inputs(
        plan, expected_digest=tasks.digest(plan), stage="evaluation"
    )["jobs"]


def raw_fixture():
    plan = producer.input_plan()
    offered = producer._worker_jobs(original_jobs())
    files = {p: "a" * 64 for p in producer.REQUIRED_SOURCES}
    pins = {"execution_source": "b" * 40, "files": files}
    obs = producer.observer(plan, files)
    records = []
    for job in offered[:2]:
        record = fixture.record(job)
        record["schema"] = producer.RECORD
        record["reference_identity"] = copy.deepcopy(obs)
        records.append(record)
    return plan, offered, pins, obs, records


def delivery(records, pins):
    raw = b"".join((json.dumps(r, sort_keys=True) + "\n").encode() for r in records)
    chunk = {
        "id": "synthetic-eval",
        "sha256": hashlib.sha256(raw).hexdigest(),
        "role": "PUBLIC_EVALUATION",
        "source_commit": pins["execution_source"],
        "source_files": pins["files"],
        "rows": [
            {"line": i, "job_id": r["case_id"], "case_id": r["case_id"]}
            for i, r in enumerate(records, 1)
        ],
    }
    return {"scope": "SYNTHETIC_FIXTURE", "chunks": [chunk]}, {chunk["id"]: raw}


def members():
    return [
        {
            "id": f"{producer.COHORT}:{recipe}:seed{seed}",
            "recipe": recipe,
            "seed": seed,
            "train_sha256": "1" * 64,
            "construction_receipt_digest": "sha256:" + "2" * 64,
            "fit_receipt_sha256": "3" * 64,
            "predictions_sha256": "4" * 64,
            "commitments_sha256": "5" * 64,
            "commitment_receipt_sha256": "6" * 64,
            "kit": "carbon.battery-v3.guard419.stage128.kit.v1:sha256:" + "7" * 64,
            "fit_source": "8" * 40,
        }
        for recipe in producer.RECIPES
        for seed in producer.SEEDS
    ]


def test_input_plan_exact_job_only_change_and_same60_order120rungs():
    plan = producer.input_plan()
    producer._plan(plan, tasks.digest(plan))
    root = Path(__file__).resolve().parents[2]
    raw = (root / producer.PLAN_FILE).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == producer.PLAN_SHA
    assert plan == {**json.loads(raw), "job": producer.JOB}
    old = original_jobs()
    new = producer._worker_jobs(old)
    assert len(new) == 120 and len({j["case_id"] for j in new}) == 120
    assert (
        len(
            {
                (
                    j["c1"],
                    j["c2"],
                    j["switch_voltage_v"],
                    j["h_multiplier"],
                    j["t_amb_c"],
                    j["soc0"],
                )
                for j in new
            }
        )
        == 60
    )
    for a, b in zip(old, new, strict=True):
        assert {k: b[k] for k in a if k != "case_id"} == {
            k: v for k, v in a.items() if k != "case_id"
        }
        assert b["parent_input_case_id"] == a["case_id"]
        assert b["case_id"] == a["case_id"].replace(
            "scorelab-v3:", "scorelab-v3:guarded419-v1:", 1
        )
        assert b["reference_role"] == "PUBLIC_EVALUATION"
        assert b["reference_method"] == guard.METHOD_ID
        assert b["reference_method_digest"] == tasks.digest(guard.METHOD)
    inputs = [{k: v for k, v in j.items() if k in old[0]} for j in new]
    assert producer._worker_jobs(inputs) == new
    with pytest.raises(tasks.TaskError):
        producer._worker_jobs([fixture.record(new[0])])


@pytest.mark.parametrize(
    "field,value",
    [("soc0", 0.2), ("cycles", 1), ("cooling", [1, 2]), ("job", owner.JOB)],
)
def test_rehashed_plan_cannot_change_population_or_old_job(field, value):
    plan = producer.input_plan()
    plan[field] = value
    with pytest.raises(tasks.TaskError):
        producer._plan(plan, tasks.digest(plan))


def test_both_raw_rungs_real_tracking_and_failed_missing_ledger_without_seal():
    _, offered, pins, obs, records = raw_fixture()
    manifest, chunks = delivery(records, pins)
    extracted, proof, tracking = producer._raw_rows(
        manifest, chunks, offered, pins, obs
    )
    assert len(extracted) == 120 and len(proof) == len(tracking) == 2
    assert all(
        t["status"] == "TRACKING_COMPATIBLE"
        and t["checked_phases"] == t["required_phases"] == 181
        for t in tracking.values()
    )
    assert [extracted[j["case_id"]]["state"] for j in offered[:2]] == ["EXTRACTED"] * 2
    assert sum(r["state"] == "MISSING" for r in extracted.values()) == 118
    assert all(
        p["raw_row_sha256"]
        == hashlib.sha256(chunks[p["chunk"]].splitlines()[p["line"] - 1]).hexdigest()
        for p in proof.values()
    )
    assert not isinstance(extracted, producer.ValidatedEvidence)
    records[0]["status"] = "REFERENCE_SOLVER_FAILED"
    manifest, chunks = delivery(records, pins)
    result, _, _ = producer._raw_rows(manifest, chunks, offered, pins, obs)
    assert result[records[0]["case_id"]]["state"] == "REFERENCE_UNRESOLVED"
    assert result[records[0]["case_id"]]["raw_status"] == "REFERENCE_SOLVER_FAILED"
    assert all(v is None for v in result[records[0]["case_id"]]["values"].values())


@pytest.mark.parametrize(
    "mutation",
    [
        "role",
        "schema",
        "observer",
        "input",
        "bool",
        "source",
        "duplicate",
        "unmapped",
        "extra",
        "fixture",
    ],
)
def test_rehashed_raw_context_type_source_mapping_and_public_promotion_refused(
    mutation,
):
    _, offered, pins, obs, records = raw_fixture()
    if mutation == "schema":
        records[0]["schema"] = guard.RECORD
    elif mutation == "observer":
        records[0]["reference_identity"]["id"] = "old-observer"
    elif mutation == "input":
        records[0]["c1"] += 0.01
    elif mutation == "bool":
        records[0]["rung"] = True
    manifest, chunks = delivery(records, pins)
    chunk = manifest["chunks"][0]
    if mutation == "role":
        chunk["role"] = "PUBLIC_CONSTRUCTION"
    elif mutation == "source":
        chunk["source_commit"] = "c" * 40
    elif mutation == "duplicate":
        chunk["rows"][1] = copy.deepcopy(chunk["rows"][0])
    elif mutation == "unmapped":
        chunk["rows"].pop()
    elif mutation == "extra":
        chunks["unregistered"] = b"{}\n"
    elif mutation == "fixture":
        manifest["scope"] = "PUBLIC_DEVELOPMENT"
    with pytest.raises(tasks.TaskError):
        producer._raw_rows(manifest, chunks, offered, pins, obs)


def test_tracking_failure_is_reference_unresolved_not_candidate_failure():
    _, offered, pins, obs, records = raw_fixture()
    records[0]["per_cycle"][0]["phases"]["cv"]["voltage_contact_observation"][
        "cv_voltage_minus_target"
    ]["target_v"] = 4.2
    manifest, chunks = delivery(records, pins)
    values, _, tracking = producer._raw_rows(manifest, chunks, offered, pins, obs)
    jid = records[0]["case_id"]
    assert tracking[jid]["status"] == "REFERENCE_UNRESOLVED"
    assert values[jid]["state"] == "REFERENCE_UNRESOLVED"
    assert all(v is None for v in values[jid]["values"].values())


def test_unsealed_enclosures_reuse_actual_policy_and_keep_zero_weight_band():
    plan = original_plan()
    registered = owner.population_tasks(
        plan, expected_plan_digest=tasks.digest(plan), count=1
    )[0]["task"]
    registered = copy.deepcopy(registered)
    # This artificial zero buyer weight is an INTERNAL helper control only;
    # a changed registered question cannot enter the fixed64 build path.
    registered["indices"][0]["buyer_weight"] = 0
    offered = producer._worker_jobs(original_jobs())
    point = {
        "charging_t_max_c": 30.0,
        "plating_min_v": 0.01,
        "minutes": 30.0,
        "q30_over_q1": 1.0,
        "v_max_v": 4.19,
    }
    extracted = {
        j["case_id"]: {"state": "EXTRACTED", "values": dict(point)} for j in offered
    }
    panels, bounds, pairs = producer._reduce(registered, offered, extracted)
    assert len(panels) == len(bounds) == 5 and len(pairs) == 60
    assert all(len(p["values"]) == 12 for p in panels)
    expected = numerics.pair_enclosures(
        point, point, expected_policy_digest=tasks.digest(numerics.POLICY)
    )
    assert pairs[0]["pair"] == expected
    missing = offered[0]["case_id"]
    extracted[missing] = {
        "state": "MISSING",
        "values": dict.fromkeys(legacy.QUANTITIES),
    }
    panels, bounds, pairs = producer._reduce(registered, offered, extracted)
    assert len(panels[0]["values"]) == 12
    assert pairs[0]["pair"]["status"] == "REFERENCE_UNRESOLVED"
    assert bounds[0]["candidates"][pairs[0]["candidate"]] == {}


def test_exact_final18_identity_roster_is_not_fit_or_cal_evidence():
    cohort = members()
    assert producer._members(cohort) is None
    assert len({m["id"] for m in cohort}) == 18
    with pytest.raises(tasks.TaskError):
        producer.ValidatedEvidence(payload={"status": "PASS"})


@pytest.mark.parametrize(
    "mutation",
    [
        "drop",
        "duplicate",
        "oldtrain",
        "oldmodel",
        "probe",
        "seed",
        "kit",
        "hash",
        "fit_source",
        "construction",
    ],
)
def test_unsealed_roster_rejects_legacy_probe_substitution_and_missing_offers(mutation):
    cohort = members()
    if mutation == "drop":
        cohort.pop()
    elif mutation == "duplicate":
        cohort[1] = copy.deepcopy(cohort[0])
    elif mutation == "oldtrain":
        cohort[0]["train_sha256"] = producer.OLD_TRAIN_SHA
    elif mutation == "oldmodel":
        cohort[0]["id"] = "battery-v3-scorelab-cohort-dev-v1:default:seed11"
    elif mutation == "probe":
        cohort[0]["id"] = "battery-v3-scorelab-guard419-probe9.default.v1"
    elif mutation == "seed":
        cohort[0]["seed"] = True
    elif mutation == "kit":
        cohort[0]["kit"] = "carbon.battery-v3.kit.v1"
    elif mutation == "hash":
        cohort[0]["fit_receipt_sha256"] = "sha256:" + "a" * 64
    elif mutation == "fit_source":
        cohort[0]["fit_source"] = "a" * 39
    else:
        cohort[0]["construction_receipt_digest"] = "sha256:" + "9" * 64
    with pytest.raises(tasks.TaskError):
        producer._members(cohort)


def test_missing_real_cal_interface_is_typed_unavailable_no_fake_pass(monkeypatch):
    original = builtins.__import__

    def missing(name, globals=None, locals=None, fromlist=(), level=0):
        if (
            name == "scripts.dev.score_lab"
            and "guarded419_calibration_continue" in fromlist
        ):
            raise ImportError("deliberately absent real CAL")
        return original(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", missing)
    with pytest.raises(producer.PrerequisiteUnavailable, match="CAL15"):
        producer._cal_api()


def test_raw_dict_context_cannot_mint_or_validate_nominal_evidence():
    with pytest.raises(tasks.TaskError):
        producer.validate_for(
            {"status": "PASS"},
            {},
            [],
            [],
            scope="PUBLIC_DEVELOPMENT",
            context={"status": "PASS"},
        )
