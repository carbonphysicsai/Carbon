"""Unsealed structural fixtures and real prerequisite refusal; no fake CAL PASS.

Full nominal positive integration waits for the actual CAL owner's fixture.
No fitted model, solver, private material or provider is used.
"""

from __future__ import annotations

import copy
import importlib.util
from dataclasses import replace
from pathlib import Path

import pytest

from carbon.design_search import tasks
from carbon.development_comparison import battery_v3_kit, carbon_arm
from scripts.dev.battery import guarded_reference as guard
from scripts.dev.score_lab import guarded419_t128 as admission
from scripts.dev.score_lab import guarded419_train as train9
from scripts.dev.score_lab import guarded419_train128 as consumer


def _factory():
    path = Path(__file__).resolve().parents[1] / "fixtures/guarded419_t128.py"
    spec = importlib.util.spec_from_file_location("unadmitted_t128_fixture", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def unsealed(tmp_path_factory):
    delivery = _factory().make_unadmitted_delivery(
        tmp_path_factory.mktemp("t128-raw"), all_rows=True
    )
    records, proof, tracking, states = admission._new_delivery(
        delivery["binding"],
        delivery["manifest"],
        delivery["raw_chunks"],
        expected_binding_digest=delivery["expected_binding_digest"],
        expected_manifest_digest=delivery["expected_manifest_digest"],
    )
    # This is deliberately NOT a nominal producer/consumer object: no CAL15
    # prerequisite is supplied and the nine unreused anchors remain MISSING.
    source = {
        "scope": "SYNTHETIC_FIXTURE",
        "jobs": admission.jobs(),
        "roles_by_job_id": {
            j["case_id"]: j["reference_role"] for j in admission.jobs()
        },
        "records": records,
        "source_rows": proof,
        "tracking": tracking,
        "per_job": states,
        "protocol_id": guard.METHOD_ID,
        "method_digest": tasks.digest(guard.METHOD),
        "observer_id": admission.OBSERVER,
        "dataset_id": admission.DATASET,
        "binding_digest": delivery["expected_binding_digest"],
        "manifest_digest": delivery["expected_manifest_digest"],
    }
    return source, delivery


def test_unsealed_mapping_preserves_128_offers_and_105_23_roles(unsealed):
    source, _ = unsealed
    construction, validation, ledger = consumer._split(source)
    assert len(construction) == 105 and len(validation) == 23 and len(ledger) == 128
    assert {r["case_id"] for r in construction}.isdisjoint(
        r["case_id"] for r in validation
    )
    assert all(r["role"] == consumer.CONSTRUCTION for r in construction)
    assert all(r["role"] == consumer.VALIDATION for r in validation)
    assert sum(r["state"] == "MISSING" for r in ledger) == 9
    assert (
        sum(r["eligible"] and r["role"] == consumer.CONSTRUCTION for r in ledger) == 96
    )
    assert sum(r["eligible"] and r["role"] == consumer.VALIDATION for r in ledger) == 23
    assert [r["case_id"] for r in ledger] == [j["case_id"] for j in source["jobs"]]
    assert (construction, validation, ledger) == consumer._split(source)


def test_actual_missing_cal_cannot_mint_qualified_split(unsealed):
    source, delivery = unsealed
    with pytest.raises(tasks.TaskError):
        admission.validate_delivery(**delivery)
    with pytest.raises(tasks.TaskError):
        consumer.build(
            source,
            expected_binding_digest=delivery["expected_binding_digest"],
            expected_manifest_digest=delivery["expected_manifest_digest"],
            scope="SYNTHETIC_FIXTURE",
        )
    with pytest.raises(tasks.TaskError, match="use guarded419_train128.build"):
        consumer.ValidatedSplit(payload=source)
    with pytest.raises(tasks.TaskError, match="prerequisite-qualified"):
        consumer.load_construction(
            source,
            expected_receipt_digest="sha256:" + "0" * 64,
            evaluation_inputs=[],
            expected_inputs_digest=tasks.digest([]),
            scope="SYNTHETIC_FIXTURE",
        )


def test_validation_schema_is_rejected_by_shared_construction_loader(unsealed):
    construction, validation, _ = consumer._split(unsealed[0])
    # Plain synthetic loader/schema unit check; this is NOT consumer admission,
    # a model fit or prerequisite-qualified construction evidence.
    kit = replace(battery_v3_kit.KIT, train_schema=consumer.TRAIN_SCHEMA)
    raw = train9._jsonl(construction)
    loaded = carbon_arm.load_train(kit, raw, train9._sha(raw))
    assert loaded.fixture and len(loaded.records) == 96 and loaded.excluded == 9
    raw = train9._jsonl(validation)
    with pytest.raises(carbon_arm.ArmRefused, match="TRAIN_RECORD_SHAPE"):
        carbon_arm.load_train(kit, raw, train9._sha(raw))
    mixed = train9._jsonl(construction + validation)
    with pytest.raises(carbon_arm.ArmRefused, match="TRAIN_RECORD_SHAPE"):
        carbon_arm.load_train(kit, mixed, train9._sha(mixed))


def test_validation_values_cannot_extend_construction_support(unsealed):
    construction, validation, _ = consumer._split(unsealed[0])
    candidate = dict(validation[0]["inputs"], c1=999.0)
    support = train9._support(construction, [candidate])
    assert (
        support["status"] == "TRAIN_INADEQUATE" and support["covered_input_count"] == 0
    )
    assert support["offered_rows"] == 105
    assert support["accepted_rows"] == 96
    assert support["observed_support"]["c1"][1] < candidate["c1"]


@pytest.mark.parametrize(
    "defect", ["cooling", "soc0", "nonfinite", "duplicate", "fields", "digest"]
)
def test_input_inventory_refuses_drift_before_support(unsealed, defect):
    construction, _, _ = consumer._split(unsealed[0])
    rows = [dict(construction[0]["inputs"])]
    if defect == "cooling":
        rows[0]["cooling"] = 3
    elif defect == "soc0":
        rows[0]["soc0"] = 0.2
    elif defect == "nonfinite":
        rows[0]["c1"] = float("inf")
    elif defect == "duplicate":
        rows.append(dict(rows[0]))
    elif defect == "fields":
        rows[0]["label"] = 0.0
    expected = (
        "sha256:" + "0" * 64
        if defect in ("nonfinite", "digest")
        else tasks.digest(rows)
    )
    with pytest.raises(tasks.TaskError, match="input-only"):
        consumer._inputs(rows, expected, "SYNTHETIC_FIXTURE")


@pytest.mark.parametrize("defect", ["role_swap", "missing_role", "raw_identity"])
def test_role_and_original_identity_drift_are_refused(unsealed, defect):
    source = copy.deepcopy(unsealed[0])
    jid = next(iter(source["records"]))
    if defect == "role_swap":
        source["roles_by_job_id"][jid] = consumer.VALIDATION
    elif defect == "missing_role":
        source["roles_by_job_id"].pop(jid)
    else:
        source["records"][jid]["case_id"] = "rewritten-raw-identity"
    with pytest.raises(tasks.TaskError):
        consumer._split(source)


def test_internal_validation_retains_native_units_and_all_outcome_denominators(
    unsealed,
):
    _, rows, _ = consumer._split(unsealed[0])
    rows = copy.deepcopy(rows[:4])
    delta = {
        "minutes": 1.0,
        "charging_t_max_c": 0.5,
        "plating_min_v": 0.002,
        "q30_over_q1": 0.0001,
        "v_max_v": 0.01,
    }
    predictions = {
        rows[0]["case_id"]: {
            q: rows[0]["outputs"][q] + delta[q] for q in train9.QUANTITIES
        },
        rows[1]["case_id"]: None,
        rows[2]["case_id"]: {"minutes": 1.0},
        rows[3]["case_id"]: dict(rows[3]["outputs"]),
    }
    rows[3]["outputs"] = dict.fromkeys(train9.QUANTITIES)
    report = consumer._validation_summary(rows, predictions)
    assert report["offered_validation_rows"] == 4
    assert [r["state"] for r in report["states"]] == [
        "MEASURED_INTERNAL_VALIDATION",
        "ABSTAINED",
        "INVALID_PREDICTION",
        "REFERENCE_UNAVAILABLE",
    ]
    for q, expected in delta.items():
        measure = report["per_quantity"][q]
        assert measure["unit"] == train9.UNITS[q] and measure["paired_count"] == 1
        assert measure["mean_absolute_error"] == pytest.approx(expected)
    assert "mean_absolute_error" not in report and report["qualification"] is False
    predictions.pop(rows[0]["case_id"])
    with pytest.raises(tasks.TaskError, match="all offered"):
        consumer._validation_summary(rows, predictions)
