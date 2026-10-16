"""Deterministic fake-record controls through the real T9 producer and trainer loader.

No fit, physical solver, provider, reference data or private role is used.
The shared fixture is owned by the prospective T9 producer ticket.
"""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest

from carbon.design_search import tasks
from carbon.development_comparison import battery_v3_kit, carbon_arm
from scripts.dev.score_lab import guarded419_train as train

SCOPE = "SYNTHETIC_FIXTURE"


def _factory():
    path = Path(__file__).resolve().parents[1] / "fixtures/guarded419_t9.py"
    spec = importlib.util.spec_from_file_location("guarded419_t9_toy_delivery", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _delivery(tmp_path):
    return _factory().make_delivery(tmp_path)


def _build(delivery):
    from scripts.dev.score_lab import guarded419_t9 as t9

    evidence = t9.validate_delivery(**delivery)
    return train.build(
        evidence,
        expected_binding_digest=delivery["expected_binding_digest"],
        expected_manifest_digest=delivery["expected_manifest_digest"],
        scope=SCOPE,
    )


def _edit(delivery, change):
    """Rebind modified toy bytes so controls reach admission, not just hashing."""
    result = copy.deepcopy(delivery)
    records = []
    for chunk in result["manifest"]["chunks"]:
        raw = result["raw_chunks"][chunk["id"]]
        lines = {
            i: json.loads(line)
            for i, line in enumerate(raw.splitlines(), 1)
            if line.strip()
        }
        for mapping in chunk["rows"]:
            row = lines[mapping["line"]]
            row = change(row)
            if row is not None:
                records.append(row)
    return _factory().refresh_delivery(result, records)


def _records(value):
    return [json.loads(line) for line in value.training_jsonl.splitlines()]


def _probe(value, inputs):
    return {
        "expected_receipt_digest": value.receipt["receipt_digest"],
        "evaluation_inputs": inputs,
        "expected_inputs_digest": tasks.digest(inputs),
        "scope": SCOPE,
    }


def test_target_only_bytes_replay_and_existing_loader_parity(tmp_path):
    delivery = _delivery(tmp_path)
    value, replay = _build(delivery), _build(delivery)
    assert value.training_jsonl == replay.training_jsonl
    assert value.receipt == replay.receipt
    rows = _records(value)
    assert len(rows) == value.receipt["accepted_training_rows"] == 9
    assert all(row["schema"] == train.SCHEMA and row["fixture"] is True for row in rows)
    assert all(set(row["outputs"]) == set(train.QUANTITIES) for row in rows)
    kit, loaded, support = train.load_probe(
        value, **_probe(value, [r["inputs"] for r in rows])
    )
    assert kit.kit_id != battery_v3_kit.KIT.kit_id
    assert kit.train_schema == train.SCHEMA != battery_v3_kit.KIT.train_schema
    assert kit.inputs == battery_v3_kit.KIT.inputs and kit.domain is None
    assert kit.targets == battery_v3_kit.KIT.targets
    assert loaded.fixture and len(loaded.records) == 9 and loaded.excluded == 0
    assert support["covered_input_count"] == 9
    assert value.receipt["historical_labels_or_models_reused"] == 0
    assert value.receipt["numerical_evaluation_reference"] is False


def test_raw_mappings_and_public_scope_cannot_construct_or_mutate_train(tmp_path):
    delivery = _delivery(tmp_path)
    value = _build(delivery)
    with pytest.raises(tasks.TaskError, match="use guarded419_train.build"):
        train.ValidatedTrain(payload={"receipt": {"status": "PASS"}})
    with pytest.raises(tasks.TaskError, match="authenticated development"):
        train.probe_support(
            value.receipt, **_probe(value, [_records(value)[0]["inputs"]])
        )
    with pytest.raises(AttributeError):
        value._seal = "changed"
    with pytest.raises(tasks.TaskError):
        train.build(
            {"status": "PASS", "records": _records(value)},
            expected_binding_digest=delivery["expected_binding_digest"],
            expected_manifest_digest=delivery["expected_manifest_digest"],
            scope=SCOPE,
        )
    receipt = value.receipt
    receipt["accepted_training_rows"] = 999
    assert value.receipt["accepted_training_rows"] == 9
    kwargs = _probe(value, [_records(value)[0]["inputs"]])
    kwargs["scope"] = "PUBLIC_DEVELOPMENT"
    with pytest.raises(tasks.TaskError, match="scope differs"):
        train.load_probe(value, **kwargs)


def test_finite_buyer_infeasible_examples_are_not_filtered(tmp_path):
    def unsafe(row):
        for cycle in row["per_cycle"]:
            for phase in cycle["phases"].values():
                phase["t_max_c"] = 70.0
                phase["plating_min_v"] = -0.01
        row["q30_over_q1"] = 0.9
        return row

    value = _build(_edit(_delivery(tmp_path), unsafe))
    assert value.receipt["accepted_training_rows"] == 9
    assert all(row["outputs"]["charging_t_max_c"] == 70 for row in _records(value))
    assert all(row["outputs"]["plating_min_v"] == -0.01 for row in _records(value))
    assert all(row["outputs"]["q30_over_q1"] == 0.9 for row in _records(value))


def test_missing_and_infrastructure_failure_keep_all_offers(tmp_path):
    delivery = _delivery(tmp_path)
    seen = []

    def change(row):
        seen.append(row["case_id"])
        if len(seen) == 1:
            return None
        if len(seen) == 2:
            row["status"] = "FAILED_INFRA"
        return row

    value = _build(_edit(delivery, change))
    receipt, rows = value.receipt, _records(value)
    assert len(receipt["ledger"]) == len(rows) == 9
    by_id = {row["case_id"]: row for row in rows}
    assert by_id[seen[0]]["label_state"] == "MISSING"
    assert by_id[seen[1]]["label_state"] == "FAILED_INFRA"
    assert all(v is None for cid in seen[:2] for v in by_id[cid]["outputs"].values())
    assert receipt["accepted_training_rows"] == 7


@pytest.mark.parametrize(
    "defect",
    [
        "partial_cycle",
        "clock_not_reached",
        "unknown_scale",
        "wrong_cv",
        "nonfinite_output",
    ],
)
def test_partial_or_fidelity_unresolved_rows_never_supply_training_labels(
    tmp_path, defect
):
    first = []

    def change(row):
        if first:
            return row
        first.append(row["case_id"])
        if defect == "partial_cycle":
            row["per_cycle"].pop()
        elif defect == "clock_not_reached":
            row["soc_clock"]["status"] = "NOT_REACHED"
        elif defect == "unknown_scale":
            row["observation_provenance"]["runtime_voltage_scale"][
                "series_cells"
            ] = None
        elif defect == "nonfinite_output":
            row["q30_over_q1"] = float("nan")
        else:
            row["per_cycle"][0]["phases"]["cv"]["voltage_contact_observation"][
                "descriptor"
            ]["value"] = 4.199
        return row

    value = _build(_edit(_delivery(tmp_path), change))
    assert value.receipt["accepted_training_rows"] == 8
    row = next(r for r in _records(value) if r["case_id"] == first[0])
    assert all(v is None for v in row["outputs"].values())
    assert row["label_state"] != "ADMITTED_CONSTRUCTION"


def test_failed_extreme_anchor_cannot_inflate_observed_support(tmp_path):
    def change(row):
        if row["c1"] == 2.0:
            row["status"] = "FAILED_INFRA"
        return row

    value = _build(_edit(_delivery(tmp_path), change))
    extreme = next(r["inputs"] for r in _records(value) if r["inputs"]["c1"] == 2.0)
    report = train.probe_support(value, **_probe(value, [extreme]))
    assert report["status"] == "TRAIN_INADEQUATE"
    assert report["covered_input_count"] == 0 and report["accepted_rows"] == 8
    assert "c1" in report["gaps"][0]["features"]
    with pytest.raises(carbon_arm.ArmRefused, match="TRAIN_INADEQUATE"):
        train.load_probe(value, **_probe(value, [extreme]))


def test_technical_minimum_is_enforced_even_with_marginal_input_coverage(tmp_path):
    count = []

    def change(row):
        count.append(row["case_id"])
        if len(count) > 1:
            row["status"] = "FAILED_INFRA"
        return row

    value = _build(_edit(_delivery(tmp_path), change))
    admitted = next(
        r["inputs"]
        for r in _records(value)
        if r["label_state"] == "ADMITTED_CONSTRUCTION"
    )
    report = train.probe_support(value, **_probe(value, [admitted]))
    assert report["covered_input_count"] == 1 and report["accepted_rows"] == 1
    assert report["status"] == "TRAIN_INADEQUATE"
    with pytest.raises(carbon_arm.ArmRefused, match="TRAIN_INADEQUATE"):
        train.load_probe(value, **_probe(value, [admitted]))


def test_input_inventory_has_no_reference_values_and_is_independently_pinned(tmp_path):
    value = _build(_delivery(tmp_path))
    inputs = [_records(value)[0]["inputs"]]
    kwargs = _probe(value, inputs)
    kwargs["expected_inputs_digest"] = "sha256:" + "0" * 64
    with pytest.raises(tasks.TaskError, match="pinned public input inventory"):
        train.probe_support(value, **kwargs)
    bad = [{**inputs[0], "reference": {"minutes": 1}}]
    with pytest.raises(tasks.TaskError, match="input-only"):
        train.probe_support(value, **_probe(value, bad))
    with pytest.raises(tasks.TaskError, match="unique"):
        train.probe_support(value, **_probe(value, inputs * 2))


@pytest.mark.parametrize(
    "defect",
    ["old_schema", "old_context", "foreign_source", "calibration_role", "raw_drift"],
)
def test_rehashed_old_or_foreign_provenance_cannot_become_new_train(tmp_path, defect):
    delivery = _delivery(tmp_path)

    def change(row):
        if defect == "old_schema":
            row["schema"] = "carbon.battery.feasibility02-record.v1"
        elif defect == "old_context":
            row["reference_identity"]["protocol_id"] = "legacy4.2"
        elif defect == "calibration_role":
            row["reference_role"] = "PUBLIC_CALIBRATION"
        return row

    delivery = _edit(delivery, change)
    if defect == "foreign_source":
        chunk = delivery["manifest"]["chunks"][0]
        path = next(iter(chunk["source_files"]))
        chunk["source_files"][path] = "0" * 64
        delivery["expected_manifest_digest"] = tasks.digest(delivery["manifest"])
    elif defect == "raw_drift":
        chunk = delivery["manifest"]["chunks"][0]
        delivery["raw_chunks"][chunk["id"]] += b" "
    # Contradictory identity/source is a contract refusal, not a fit or penalty.
    with pytest.raises(tasks.TaskError):
        _build(delivery)
