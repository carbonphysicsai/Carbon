"""Synthetic full-programme rows; no solves, fitting or public label analysis."""

from __future__ import annotations

import copy
import json

import pytest

from carbon.design_search import tasks
from carbon.development_comparison import battery_v3_kit, carbon_arm
from scripts.dev.score_lab import owner_v3_panel_export as producer
from scripts.dev.score_lab import owner_v3_train as train
from tests.cpu.test_score_lab_owner_v3_panel_export import ROOT, _record
from tests.cpu.test_score_lab_owner_v3_train import fixture as coarse_fixture


def fixture():
    raw, registry, base, kwargs = coarse_fixture()
    coarse, receipt = train.prepare(
        raw, registry, base, scope="SYNTHETIC_FIXTURE", **kwargs
    )
    plan = kwargs["plan"]
    pins = json.loads(
        (
            ROOT
            / "Business/research/score-lab-campaign-01/acquisition-v1/source-pins.json"
        ).read_text(encoding="utf-8")
    )
    jobs = [
        {
            "case_id": f"synthetic-train-{n}",
            "source_plan_index": n,
            "c1": 0.25 + n / 100,
            "c2": 0.26,
            "switch_voltage_v": 4.05,
            "h_multiplier": (1, 2, 4)[n % 3],
            "t_amb_c": 10 + n,
            "soc0": 0.1,
            "refined": False,
        }
        for n in range(9)
    ]
    spec = {
        "schema": "carbon.scorelab.public-train-anchor-inputs.v1",
        "source_plan_sha256": train.TRAIN_PLAN_SHA,
        "anchor_count": 9,
        "anchors": jobs,
    }
    anchors_raw = json.dumps(spec).encode()
    rows = [_record(job, plan) for job in jobs]
    raw = b"".join((json.dumps(row) + "\n").encode() for row in rows)
    manifest = {
        "schema": train.ANCHOR_MANIFEST,
        "scope": "SYNTHETIC_FIXTURE",
        "role": "PUBLIC_TRAIN",
        "plan_digest": tasks.digest(plan),
        "source_pins_digest": tasks.digest(pins),
        "anchors_sha256": train._sha(anchors_raw),
        "observer": producer._observer(plan, pins),
        "chunks": [
            {
                "id": "anchors",
                "sha256": train._sha(raw),
                "role": "PUBLIC_TRAIN",
                "source_commit": "9" * 40,
                "source_files": {p: pins["files"][p] for p in producer.SOURCES},
                "rows": [
                    {
                        "line": n + 1,
                        "job_id": job["case_id"],
                        "case_id": rows[n]["case_id"],
                    }
                    for n, job in enumerate(jobs)
                ],
            }
        ],
    }
    return {
        "coarse_raw": coarse,
        "coarse_receipt": receipt,
        "expected_coarse_receipt_digest": receipt["receipt_digest"],
        "anchors_raw": anchors_raw,
        "expected_anchors_sha256": train._sha(anchors_raw),
        "plan": plan,
        "expected_plan_digest": tasks.digest(plan),
        "source_pins": pins,
        "expected_source_pins_digest": tasks.digest(pins),
        "manifest": manifest,
        "expected_manifest_digest": tasks.digest(manifest),
        "raw_chunks": {"anchors": raw},
        "scope": "SYNTHETIC_FIXTURE",
    }


def reseal(args, *, records=None):
    if records is not None:
        raw = b"".join((json.dumps(row) + "\n").encode() for row in records)
        args["raw_chunks"]["anchors"] = raw
        args["manifest"]["chunks"][0]["sha256"] = train._sha(raw)
    args["expected_manifest_digest"] = tasks.digest(args["manifest"])


def test_deterministic_combine_existing_arm_ingestion_and_source_accounting():
    args = fixture()
    data, receipt = train.combine(**args)
    assert train.combine(**args) == (data, receipt)
    assert receipt["anchors_offered"] == receipt["anchors_eligible"] == 9
    assert receipt["offered_training_rows"] == 10
    assert receipt["coarse_offered"] == 1
    assert receipt["coarse_rows_claimed_as_original_TRAIN_completion"] == 0
    assert receipt["numerical_evaluation_reference"] is False
    assert receipt["qualification"] is False
    loaded = carbon_arm.load_train(
        battery_v3_kit.KIT, data, receipt["training_jsonl_digest"]
    )
    assert len(loaded.records) == 9 and loaded.excluded == 1 and loaded.fixture
    assert all(isinstance(source, str) for source in carbon_arm.sources(loaded))
    assert len(receipt["calibration_evaluation_exclusions"]) == 2
    binding = receipt["anchor_ledger"][0]["source"]
    assert binding["chunk_sha256"] == train._sha(args["raw_chunks"]["anchors"])
    assert binding["source_case_id"] == "original:synthetic-train-0"
    assert binding["core_s"] == binding["wall_s"] == 0


@pytest.mark.parametrize(
    "state", ["REFERENCE_SOLVER_FAILED", "NOT_REACHED", "NONFINITE", "SHORT_PROGRAMME"]
)
def test_failed_or_incomplete_labels_remain_offered_and_cannot_extend_support(state):
    args = fixture()
    records = [json.loads(line) for line in args["raw_chunks"]["anchors"].splitlines()]
    if state == "REFERENCE_SOLVER_FAILED":
        records[0]["status"] = state
    elif state == "NOT_REACHED":
        records[0]["soc_clock"] = {"status": "NOT_REACHED"}
    elif state == "NONFINITE":
        records[0]["whole_programme"]["v_max_v"] = float("nan")
    else:
        records[0]["per_cycle"].pop()
    reseal(args, records=records)
    data, receipt = train.combine(**args)
    assert receipt["anchors_offered"] == 9 and receipt["anchors_eligible"] == 8
    assert receipt["anchor_ledger"][0]["eligible"] is False
    assert all(
        value is None for value in json.loads(data.splitlines()[1])["outputs"].values()
    )
    loaded = carbon_arm.load_train(
        battery_v3_kit.KIT, data, receipt["training_jsonl_digest"]
    )
    assert loaded.excluded == 2
    assert min(row["inputs"]["c1"] for row in loaded.records) == 0.26


def test_missing_anchor_has_a_row_and_missing_status_without_a_source():
    args = fixture()
    records = [json.loads(line) for line in args["raw_chunks"]["anchors"].splitlines()][
        1:
    ]
    mappings = args["manifest"]["chunks"][0]["rows"][1:]
    for mapping in mappings:
        mapping["line"] -= 1
    args["manifest"]["chunks"][0]["rows"] = mappings
    reseal(args, records=records)
    data, receipt = train.combine(**args)
    assert len(data.splitlines()) == 10
    assert receipt["anchor_ledger"][0]["state"] == "MISSING"
    assert receipt["anchor_ledger"][0]["source"] is None
    assert receipt["anchors_eligible"] == 8


def test_no_returned_anchor_labels_is_nine_missing_not_a_coverage_success():
    args = fixture()
    args["manifest"]["chunks"] = []
    args["raw_chunks"] = {}
    reseal(args)
    data, receipt = train.combine(**args)
    assert len(data.splitlines()) == 10
    assert receipt["anchors_eligible"] == 0
    assert {row["state"] for row in receipt["anchor_ledger"]} == {"MISSING"}
    assert all(row["source"] is None for row in receipt["anchor_ledger"])


@pytest.mark.parametrize("field", ["coarse_raw", "anchors_raw"])
def test_source_byte_drift_refuses(field):
    args = fixture()
    args[field] += b" "
    with pytest.raises(tasks.TaskError, match="bytes"):
        train.combine(**args)


@pytest.mark.parametrize(
    "mutation",
    ["role", "observer", "source", "unmapped", "duplicate", "foreign_chunk", "scope"],
)
def test_manifest_drift_or_unregistered_rows_refuse_even_when_manifest_is_resealed(
    mutation,
):
    args = fixture()
    chunk = args["manifest"]["chunks"][0]
    if mutation == "role":
        chunk["role"] = "PUBLIC_EVALUATION"
    elif mutation == "observer":
        args["manifest"]["observer"]["soc0"] = 0.12
    elif mutation == "source":
        chunk["source_files"][producer.SOURCES[0]] = "0" * 64
    elif mutation == "unmapped":
        chunk["rows"].pop()
    elif mutation == "duplicate":
        chunk["rows"].append(copy.deepcopy(chunk["rows"][0]))
    elif mutation == "foreign_chunk":
        args["raw_chunks"]["other"] = b""
    else:
        args["manifest"]["scope"] = "PUBLIC_DEVELOPMENT"
    reseal(args)
    with pytest.raises(tasks.TaskError):
        train.combine(**args)


@pytest.mark.parametrize("mutation", ["inputs", "rung", "image", "overlay", "clock"])
def test_raw_drift_is_refused_or_unavailable_with_a_resealed_source(mutation):
    args = fixture()
    records = [json.loads(line) for line in args["raw_chunks"]["anchors"].splitlines()]
    row = records[0]
    if mutation == "inputs":
        row["soc0"] = 0.12
    elif mutation == "rung":
        row["refined"] = True
    elif mutation == "image":
        row["solver_provenance"]["solver_image"] = "wrong"
    elif mutation == "overlay":
        row["solver_provenance"]["overlay_lock_sha256"] = "sha256:" + "0" * 64
    else:
        row["soc_clock"]["time_s"] = 0
    reseal(args, records=records)
    if mutation == "clock":
        _, receipt = train.combine(**args)
        assert not receipt["anchor_ledger"][0]["eligible"]
    else:
        with pytest.raises(tasks.TaskError):
            train.combine(**args)


def test_caleval_overlap_and_fixture_promotion_refused():
    args = fixture()
    spec = json.loads(args["anchors_raw"])
    spec["anchors"][0].update(
        c1=0.5, c2=0.25, switch_voltage_v=4.0, h_multiplier=1, t_amb_c=5
    )
    args["anchors_raw"] = json.dumps(spec).encode()
    args["expected_anchors_sha256"] = train._sha(args["anchors_raw"])
    with pytest.raises(tasks.TaskError, match="disjoint"):
        train.combine(**args)
    args = fixture()
    args["scope"] = "PUBLIC_DEVELOPMENT"
    body = {k: v for k, v in args["coarse_receipt"].items() if k != "receipt_digest"}
    body["scope"] = "PUBLIC_DEVELOPMENT"
    args["expected_coarse_receipt_digest"] = tasks.digest(body)
    args["coarse_receipt"] = {**body, "receipt_digest": tasks.digest(body)}
    with pytest.raises(tasks.TaskError, match="registered public"):
        train.combine(**args)
