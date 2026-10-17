"""Synthetic DEVELOPMENT deliveries and fake pool only; no solver/model/provider."""

from __future__ import annotations

import copy
import dataclasses
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import ClassVar

import pytest

from carbon.battery import truth_env
from carbon.design_search import tasks
from carbon.development_comparison import carbon_arm
from scripts.dev.battery import feasibility02 as worker
from scripts.dev.battery import guarded_reference as guard
from scripts.dev.score_lab import guarded419_calibration_continue as cal
from scripts.dev.score_lab import guarded419_t9 as t9
from scripts.dev.score_lab import guarded419_train as train
from scripts.dev.score_lab import owner_v3_calibration_continue as collector

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "cal15_toy_raw", ROOT / "tests/fixtures/guarded419_t9.py"
)
toy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(toy)


def _bytes(value):
    return (json.dumps(value, sort_keys=True, allow_nan=True) + "\n").encode()


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _record(job, *, fixture=True):
    row = toy.record(job, fixture=fixture)
    row.update(schema=cal.RECORD, reference_identity=cal.observer())
    return row


def _chunk(binding, segment, rows):
    raw = b"".join(_bytes(r) for r in rows)
    return {
        "id": segment,
        "segment": segment,
        "sha256": _sha(raw),
        "source_commit": binding["execution_source"],
        "source_files": binding["source_files"],
        "rows": [{"line": i, "job_id": r["case_id"]} for i, r in enumerate(rows, 1)],
    }, raw


def _make(root, scope):
    delivery = toy.make_delivery(root, scope=scope)
    delivery["binding"]["execution_source"] = "a" * 40
    delivery["expected_binding_digest"] = tasks.digest(delivery["binding"])
    toy.refresh_delivery(
        delivery, [json.loads(l) for l in delivery["raw_chunks"]["t9"].splitlines()]
    )
    evidence = t9.validate_delivery(**delivery)
    prepared = train.build(
        evidence,
        expected_binding_digest=delivery["expected_binding_digest"],
        expected_manifest_digest=delivery["expected_manifest_digest"],
        scope=scope,
    )
    plan = json.loads(
        (
            ROOT
            / "Business/research/score-lab-campaign-01/acquisition-v1/acquisition.json"
        ).read_bytes()
    )
    inputs = [
        {
            "c1": c1,
            "c2": c2,
            "switch_v": switch,
            "cooling": h,
            "ambient_c": t,
            "soc0": 0.1,
        }
        for c1, c2, switch in plan["fallback_evaluation"]["profiles"]
        for t in plan["bands_c"]
        for h in plan["cooling"]
    ]
    support = train.probe_support(
        prepared,
        expected_receipt_digest=prepared.receipt["receipt_digest"],
        evaluation_inputs=inputs,
        expected_inputs_digest=tasks.digest(inputs),
        scope=scope,
    )
    fit = {
        "schema": carbon_arm.RECEIPT,
        "scope": scope,
        "model_id": train.MODEL_ID + ":" + prepared.receipt["receipt_digest"],
        "kit": train.KIT_ID + ":" + delivery["expected_binding_digest"],
        "train": {
            "sha256": prepared.receipt["training_jsonl_digest"],
            "records": support["accepted_rows"],
            "fixture": scope == "SYNTHETIC_FIXTURE",
        },
        "code": {"construction_receipt_digest": prepared.receipt["receipt_digest"]},
        "recipe": {
            "backend": "jax",
            "seed": 11,
            "settings": carbon_arm.TRAINER_DEFAULTS,
        },
        "abstained": 0,
    }
    predictions = {
        "scope": scope,
        "model_id": fit["model_id"],
        "source_receipt_digest": carbon_arm.sha256(carbon_arm.canonical(fit)),
        "rows": [{"values": dict.fromkeys(train.QUANTITIES, 1.0)} for _ in inputs],
    }
    probe = {
        "construction": _bytes(prepared.receipt),
        "inputs": _bytes(inputs),
        "support": _bytes(support),
        "fit": _bytes(fit),
        "predictions": _bytes(predictions),
    }
    probe["outcome"] = _bytes(
        {
            "status": "SUPPORT_AND_DEFAULT11_FIT_COMPLETED",
            "fit_receipt_sha256": _sha(probe["fit"]),
            "predictions_sha256": _sha(probe["predictions"]),
        }
    )
    files = dict(delivery["binding"]["source_files"])
    for name in cal.REQUIRED_SOURCES - set(files):
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"SYNTHETIC_SOURCE_ONLY")
        files[name] = _sha(target.read_bytes())
    binding = cal.execution_binding(
        source_commit="a" * 40,
        source_files=files,
        g0=delivery["binding"]["g0"],
        t9_prerequisite={
            "binding_digest": delivery["expected_binding_digest"],
            "manifest_digest": delivery["expected_manifest_digest"],
            "evaluation_inputs_digest": tasks.digest(inputs),
            "probe_files": {k: _sha(v) for k, v in probe.items()},
        },
        segment="rest-5",
        dispatch_id="SYNTHETIC_TEST_DISPATCH_NOT_REAL_ACQUISITION",
        previous={"manifest_sha256": "1" * 64, "binding_digest": "sha256:" + "2" * 64},
        scope=scope,
    )
    chunks, raw = [], {}
    for segment, (start, end) in cal.SEGMENTS.items():
        chunk, data = _chunk(
            binding,
            segment,
            [
                _record(j, fixture=scope == "SYNTHETIC_FIXTURE")
                for g in cal.groups()[start:end]
                for j in g
            ],
        )
        chunks.append(chunk)
        raw[segment] = data
    manifest = cal.delivery_manifest(binding, chunks)
    return {
        "binding": binding,
        "manifest": manifest,
        "raw_chunks": raw,
        "expected_binding_digest": tasks.digest(binding),
        "expected_manifest_digest": tasks.digest(manifest),
        "g0_binding": delivery["g0_binding"],
        "g0_raw": delivery["g0_raw"],
        "g0_receipt": delivery["g0_receipt"],
        "t9_delivery": {k: delivery[k] for k in ("binding", "manifest", "raw_chunks")},
        "probe_raw": probe,
    }


@pytest.fixture(scope="module")
def template(tmp_path_factory):
    return _make(tmp_path_factory.mktemp("cal-synthetic"), "SYNTHETIC_FIXTURE")


@pytest.fixture
def material(template):
    return copy.deepcopy(template)


def _reseal(material):
    material["expected_binding_digest"] = tasks.digest(material["binding"])
    material["manifest"]["binding_digest"] = material["expected_binding_digest"]
    material["expected_manifest_digest"] = tasks.digest(material["manifest"])


def _replace_rows(material, segment, rows):
    chunk, raw = _chunk(material["binding"], segment, rows)
    index = list(cal.SEGMENTS).index(segment)
    material["manifest"]["chunks"][index] = chunk
    material["raw_chunks"][segment] = raw
    _reseal(material)


def _snapshot(material):
    return cal.validate_for(
        cal.validate_delivery(**material),
        expected_binding_digest=material["expected_binding_digest"],
        expected_manifest_digest=material["expected_manifest_digest"],
        scope=material["binding"]["scope"],
    )


def test_fifteen_frozen_inputs_original_g0_and_legal_partitions():
    plan = json.loads(
        (
            ROOT
            / "Business/research/score-lab-campaign-01/acquisition-v1/acquisition.json"
        ).read_bytes()
    )
    assert cal.groups()[0] == guard.first_jobs()
    assert len(cal.groups()) == 15 and len(cal.jobs()) == 45
    grid = [(t, h) for t in plan["bands_c"] for h in plan["cooling"]]
    pilot = {tuple(pair) for pair in plan["calibration"]["first_wave_t_h"]}
    pilot_order = [pair for pair in grid if pair in pilot]
    rest_order = [pair for pair in grid if pair not in pilot]
    expected = pilot_order + rest_order
    actual = [(g[0]["t_amb_c"], g[0]["h_multiplier"]) for g in cal.groups()]
    assert actual == expected
    profile = tuple(plan["calibration"]["profiles"][0])
    for job in cal.jobs():
        assert (job["c1"], job["c2"], job["switch_voltage_v"]) == profile
    indices = [g[0]["parent_input_index"] for g in cal.groups()[1:]]
    assert indices == [grid.index(pair) for pair in expected[1:]]
    assert [b - a for a, b in cal.SEGMENTS.values()] == [2, 3, 4, 5]
    for group in cal.groups()[1:]:
        assert [j["rung"] for j in group] == [1, 2, 3]
        for job in group:
            cal.validate_job(job)
            with pytest.raises(tasks.TaskError):
                guard.validate_job(job)
            with pytest.raises(tasks.TaskError):
                t9.validate_job(job)


def test_complete_raw_rereduction_mints_only_nominal_context_bound_copy(material):
    result = _snapshot(material)
    assert result["status"] == cal.COMPATIBLE
    assert result["expected_case_count"] == 15
    assert result["observed_rows"] == len(result["source_rows"]) == 45
    assert not result["missing_cases"] and not result["failed_cases"]
    assert all(
        v["status"] == "TRACKING_COMPATIBLE" and v["checked_phases"] == 181
        for v in result["tracking"].values()
    )
    assert result["numerical"]["expected_case_count"] == 15
    assert not result["evaluation_release"] and not result["qualification"]
    first = guard.first_jobs()[0]["case_id"]
    assert result["source_rows"][first]["chunk_id"] == "original-g0"
    evidence = cal.validate_delivery(**material)
    result["source_files"].clear()
    assert cal.validate_for(
        evidence,
        expected_binding_digest=material["expected_binding_digest"],
        expected_manifest_digest=material["expected_manifest_digest"],
        scope="SYNTHETIC_FIXTURE",
    )["source_files"]
    with pytest.raises(dataclasses.FrozenInstanceError):
        evidence._snapshot = b"{}"
    for bad in ({"status": cal.COMPATIBLE}, b"{}"):
        with pytest.raises(tasks.TaskError):
            cal.validate_for(
                bad,
                expected_binding_digest=material["expected_binding_digest"],
                expected_manifest_digest=material["expected_manifest_digest"],
                scope="SYNTHETIC_FIXTURE",
            )
    with pytest.raises(tasks.TaskError):
        cal.ValidatedCalibrationEvidence(b"{}")
    with pytest.raises(tasks.TaskError):
        cal.validate_for(
            evidence,
            expected_binding_digest=material["expected_binding_digest"],
            expected_manifest_digest="sha256:" + "0" * 64,
            scope="SYNTHETIC_FIXTURE",
        )
    with pytest.raises(tasks.TaskError):
        cal.validate_for(
            evidence,
            expected_binding_digest=material["expected_binding_digest"],
            expected_manifest_digest=material["expected_manifest_digest"],
            scope="PUBLIC_DEVELOPMENT",
        )


@pytest.mark.parametrize(
    "defect",
    [
        "wrong_role",
        "old_schema",
        "missing_last_cv",
        "nonfinite",
        "numeric_outside",
        "wrong_input_type",
        "duplicate",
        "unmapped",
        "source_drift",
        "segment_order",
        "missing_rung",
    ],
)
def test_rehashed_foreign_or_incomplete_full_delivery_never_seals(material, defect):
    segment = "pilot-2"
    rows = [json.loads(l) for l in material["raw_chunks"][segment].splitlines()]
    if defect == "wrong_role":
        rows[0]["reference_role"] = "PUBLIC_EVALUATION"
    elif defect == "old_schema":
        rows[0]["schema"] = guard.RECORD
    elif defect == "missing_last_cv":
        del rows[0]["per_cycle"][-1]["phases"]["cv"]["voltage_contact_observation"][
            "terminal_state"
        ]["current_control_equations"][0]["normalization"]
    elif defect == "nonfinite":
        rows[0]["whole_programme"]["v_max_v"] = float("nan")
    elif defect == "numeric_outside":
        rows[2]["soc_clock"].update(minutes=35.0, time_s=2100.0)
    elif defect == "wrong_input_type":
        rows[0]["h_multiplier"] = float(rows[0]["h_multiplier"])
    elif defect == "duplicate":
        rows.append(copy.deepcopy(rows[0]))
    elif defect == "missing_rung":
        rows.pop()
    if defect == "unmapped":
        material["raw_chunks"][segment] += _bytes(rows[0])
        material["manifest"]["chunks"][0]["sha256"] = _sha(
            material["raw_chunks"][segment]
        )
    elif defect == "source_drift":
        material["manifest"]["chunks"][0]["source_files"] = {
            **material["binding"]["source_files"],
            "scripts/dev/score_lab/owner_v3.py": "f" * 64,
        }
    elif defect == "segment_order":
        material["manifest"]["chunks"].reverse()
    else:
        _replace_rows(material, segment, rows)
    _reseal(material)
    with pytest.raises(tasks.TaskError):
        cal.validate_delivery(**material)


@pytest.mark.parametrize(
    "defect",
    [
        "g0_bytes",
        "forged_g0_receipt",
        "g0_scientific_source",
        "t9_binding",
        "fit_old_train",
        "fit_wrong_seed",
        "support_forged",
        "predictions_nonfinite",
    ],
)
def test_independently_rechecked_prerequisites_refuse_optimistic_flags(
    material, defect
):
    if defect == "g0_bytes":
        material["g0_raw"] += b" \n"
    elif defect == "forged_g0_receipt":
        receipt = json.loads(material["g0_receipt"])
        receipt["status"] = "PASS"
        material["g0_receipt"] = _bytes(receipt)
        material["binding"]["g0"]["receipt_sha256"] = _sha(material["g0_receipt"])
    elif defect == "g0_scientific_source":
        material["binding"]["source_files"]["scripts/dev/score_lab/owner_v3.py"] = (
            "f" * 64
        )
    elif defect == "t9_binding":
        material["t9_delivery"]["binding"]["scope"] = "PUBLIC_DEVELOPMENT"
    else:
        key = (
            "fit"
            if defect.startswith("fit")
            else "support" if defect.startswith("support") else "predictions"
        )
        value = json.loads(material["probe_raw"][key])
        if defect == "fit_old_train":
            value["train"]["sha256"] = "sha256:" + "f" * 64
        elif defect == "fit_wrong_seed":
            value["recipe"]["seed"] = 29
        elif defect == "support_forged":
            value["covered_input_count"] = 0
        else:
            value["rows"][0]["values"]["minutes"] = float("nan")
        material["probe_raw"][key] = _bytes(value)
        material["binding"]["t9"]["probe_files"][key] = _sha(material["probe_raw"][key])
    _reseal(material)
    with pytest.raises(tasks.TaskError):
        cal.validate_delivery(**material)


def _file_spec(material):
    namespace, counter = {}, 0

    def entry(raw):
        nonlocal counter
        counter += 1
        key = f"CAL_RESOURCE_{counter}"
        namespace[key] = raw
        return {"path": key, "sha256": _sha(raw)}

    return {
        "schema": cal.FILE_SPEC,
        "scope": material["binding"]["scope"],
        "binding": entry(_bytes(material["binding"])),
        "manifest": entry(_bytes(material["manifest"])),
        "raw_chunks": {k: entry(v) for k, v in material["raw_chunks"].items()},
        "g0": {
            "binding": entry(material["g0_binding"]),
            "records": entry(material["g0_raw"]),
            "receipt": entry(material["g0_receipt"]),
        },
        "t9": {
            "binding": entry(_bytes(material["t9_delivery"]["binding"])),
            "manifest": entry(_bytes(material["t9_delivery"]["manifest"])),
            "raw_chunks": {
                k: entry(v) for k, v in material["t9_delivery"]["raw_chunks"].items()
            },
        },
        "probe": {k: entry(v) for k, v in material["probe_raw"].items()},
        "expected_binding_digest": material["expected_binding_digest"],
        "expected_manifest_digest": material["expected_manifest_digest"],
    }, namespace


def test_file_constructor_uses_declared_ids_never_disk_paths_or_eval_reads(material):
    spec, namespace = _file_spec(material)
    # Real CLI manifests resolve resource IDs to DIFFERENT disk-path values.
    manifest_files = {
        key: {"path": "public-on-disk/" + key + ".json"} for key in namespace
    }
    reads = []

    def load(key):
        if key not in manifest_files:
            raise tasks.TaskError(
                "undeclared resource refused before EVAL payload read"
            )
        reads.append(key)
        return namespace[key]

    evidence = cal.from_files(spec, load=load, scope="SYNTHETIC_FIXTURE")
    assert (
        cal.validate_for(
            evidence,
            expected_binding_digest=material["expected_binding_digest"],
            expected_manifest_digest=material["expected_manifest_digest"],
            scope="SYNTHETIC_FIXTURE",
        )["observed_rows"]
        == 45
    )
    spec["binding"]["path"] = manifest_files[spec["binding"]["path"]]["path"]
    reads.clear()
    with pytest.raises(tasks.TaskError, match="undeclared resource"):
        cal.from_files(spec, load=load, scope="SYNTHETIC_FIXTURE")
    assert reads == []


def test_worker_cal_admission_is_exact_and_failure_keeps_requested_context(monkeypatch):
    job = cal.groups()[1][0]

    class BuildReached(Exception):
        pass

    def build(_):
        raise BuildReached

    monkeypatch.setitem(
        sys.modules,
        "pybamm",
        SimpleNamespace(
            lithium_ion=SimpleNamespace(DFN=build), set_logging_level=lambda _: None
        ),
    )
    with pytest.raises(BuildReached):
        worker._simulation(job)
    for key, value in (
        ("reference_role", "PUBLIC_EVALUATION"),
        ("rung", 0),
        ("soc0", 0.2),
    ):
        with pytest.raises(tasks.TaskError):
            worker._simulation({**job, key: value})
    with pytest.raises(tasks.TaskError):
        worker._simulation({**job, "reference_admission": t9.ADMISSION})
    result = worker.solve_one(job)
    assert result["status"] == "REFERENCE_SOLVER_FAILED"
    assert (
        result["schema"] == cal.RECORD
        and result["reference_identity"] == cal.observer()
    )


def _run_spec(material, segment="pilot-2", *, previous=None):
    binding = cal.execution_binding(
        source_commit=material["binding"]["execution_source"],
        source_files=material["binding"]["source_files"],
        g0=material["binding"]["g0"],
        t9_prerequisite=material["binding"]["t9"],
        segment=segment,
        dispatch_id="SYNTHETIC_BOUNDED_TEST",
        previous=previous,
        scope="PUBLIC_DEVELOPMENT",
    )
    value = {
        **material,
        "binding": binding,
        "manifest": cal.delivery_manifest(binding, []),
        "raw_chunks": {},
        "expected_binding_digest": tasks.digest(binding),
    }
    value["expected_manifest_digest"] = tasks.digest(value["manifest"])
    return _file_spec(value)


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    root = tmp_path / "sources"
    value = _make(root, "PUBLIC_DEVELOPMENT")
    provenance = toy.record(guard.first_jobs()[0])["solver_provenance"]
    monkeypatch.setattr(truth_env, "provenance", lambda _: provenance)
    monkeypatch.setattr(collector, "as_completed", lambda fs: list(fs))

    class Pool:
        submitted: ClassVar[list] = []
        fail = False
        infra = False
        interrupt = False

        def __init__(self, workers):
            assert workers == 2

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def submit(self, function, job):
            assert function is worker._timed
            self.submitted.append(job)

            def result():
                if self.infra:
                    raise RuntimeError("synthetic infrastructure failure")
                if self.interrupt:
                    raise KeyboardInterrupt("synthetic interruption")
                row = _record(job, fixture=False)
                if self.fail:
                    row["status"] = "REFERENCE_SOLVER_FAILED"
                return row

            class Future:
                def result(self):
                    return result()

            return Future()

    monkeypatch.setattr(collector, "ProcessPoolExecutor", Pool)
    spec, namespace = _run_spec(value)
    return root, spec, namespace, Pool


def test_bounded_collector_reuses_g0_stops_before_next_tuple_and_retains_partial(
    runtime, tmp_path
):
    root, spec, namespace, pool = runtime
    pool.fail = True
    out = tmp_path / "partial.jsonl"
    assert cal.run(spec, load=namespace.__getitem__, records_path=out, root=root) == 2
    receipt = json.loads(out.with_name(out.name + ".cal15.json").read_bytes())
    rows = [json.loads(l) for l in out.read_bytes().splitlines()]
    assert len(rows) == len(pool.submitted) == 3
    assert all(
        j["case_id"] not in {g["case_id"] for g in guard.first_jobs()}
        for j in pool.submitted
    )
    assert receipt["status"] == "REFERENCE_UNRESOLVED"
    assert sum(s == "NOT_DISPATCHED" for s in receipt["per_job"].values()) == 39
    assert not receipt["registered_calibration_complete"]
    assert receipt["calibration"]["observed_rows"] == 6
    assert all(r["status"] == "REFERENCE_SOLVER_FAILED" for r in rows)


def test_successful_first_segment_is_six_new_rungs_not_full_calibration(
    runtime, tmp_path
):
    root, spec, namespace, pool = runtime
    out = tmp_path / "six.jsonl"
    assert cal.run(spec, load=namespace.__getitem__, records_path=out, root=root) == 0
    assert len(pool.submitted) == 6
    receipt = json.loads(out.with_name(out.name + ".cal15.json").read_bytes())
    assert receipt["status"] == "COMPATIBLE_SEGMENT_ONLY"
    assert receipt["calibration"]["observed_rows"] == 9
    assert (
        not receipt["registered_calibration_complete"]
        and not receipt["evaluation_release"]
    )


def test_interruption_preserves_raw_and_durable_nonacceptance(runtime, tmp_path):
    root, spec, namespace, pool = runtime
    pool.interrupt = True
    out = tmp_path / "interrupted.jsonl"
    with pytest.raises(KeyboardInterrupt, match="synthetic interruption"):
        cal.run(spec, load=namespace.__getitem__, records_path=out, root=root)
    receipt = json.loads(out.with_name(out.name + ".cal15.json").read_bytes())
    assert receipt["status"] == "INTERRUPTED_OR_INVALID_REFERENCE"
    assert out.read_bytes() == b"" and len(pool.submitted) == 3


def test_existing_output_refuses_before_pool(runtime, tmp_path):
    root, spec, namespace, pool = runtime
    out = tmp_path / "existing.jsonl"
    out.write_bytes(b"ORIGINAL_EVIDENCE")
    with pytest.raises(tasks.TaskError, match="fresh"):
        cal.run(spec, load=namespace.__getitem__, records_path=out, root=root)
    assert out.read_bytes() == b"ORIGINAL_EVIDENCE" and not pool.submitted


def test_dangling_symlink_output_refuses_before_pool(runtime, tmp_path):
    root, spec, namespace, pool = runtime
    out = tmp_path / "symbolic.jsonl"
    target = tmp_path / "never-created.jsonl"
    out.symlink_to(target)
    with pytest.raises(tasks.TaskError, match="fresh"):
        cal.run(spec, load=namespace.__getitem__, records_path=out, root=root)
    assert out.is_symlink() and not target.exists() and not pool.submitted


def test_next_segment_authenticates_and_reuses_actual_previous_output(
    runtime, tmp_path
):
    root, spec, namespace, pool = runtime
    first = tmp_path / "first.jsonl"
    assert cal.run(spec, load=namespace.__getitem__, records_path=first, root=root) == 0
    first_receipt = json.loads(first.with_name(first.name + ".cal15.json").read_bytes())
    previous = first_receipt["manifest"]
    material, _ = cal._materials(
        spec, load=namespace.__getitem__, scope="PUBLIC_DEVELOPMENT"
    )
    binding = cal.execution_binding(
        source_commit=material["binding"]["execution_source"],
        source_files=material["binding"]["source_files"],
        g0=material["binding"]["g0"],
        t9_prerequisite=material["binding"]["t9"],
        segment="pilot-3",
        dispatch_id="SYNTHETIC_SECOND_PARTITION",
        previous={
            "manifest_sha256": _sha(_bytes(previous)),
            "binding_digest": previous["binding_digest"],
        },
        scope="PUBLIC_DEVELOPMENT",
    )
    material.update(
        binding=binding,
        manifest=previous,
        raw_chunks={"pilot-2": first.read_bytes()},
        expected_binding_digest=tasks.digest(binding),
        expected_manifest_digest=tasks.digest(previous),
    )
    second_spec, second_namespace = _file_spec(material)
    second = tmp_path / "second.jsonl"
    assert (
        cal.run(
            second_spec,
            load=second_namespace.__getitem__,
            records_path=second,
            root=root,
        )
        == 0
    )
    assert len(pool.submitted) == len({j["case_id"] for j in pool.submitted}) == 15
    second_receipt = json.loads(
        second.with_name(second.name + ".cal15.json").read_bytes()
    )
    assert second_receipt["calibration"]["observed_rows"] == 18
    assert len(second.read_bytes().splitlines()) == 9
    assert first_receipt["records_sha256"] == _sha(first.read_bytes())
    assert not second_receipt["registered_calibration_complete"]
    material["binding"]["previous"]["manifest_sha256"] = "0" * 64
    material["expected_binding_digest"] = tasks.digest(material["binding"])
    bad_spec, bad_namespace = _file_spec(material)
    with pytest.raises(tasks.TaskError, match="preceding"):
        cal.run(
            bad_spec,
            load=bad_namespace.__getitem__,
            records_path=tmp_path / "refused.jsonl",
            root=root,
        )
    assert not (tmp_path / "refused.jsonl").exists()


def test_infrastructure_failure_is_retained_with_cal_requested_context(
    runtime, tmp_path
):
    root, spec, namespace, pool = runtime
    pool.infra = True
    out = tmp_path / "infra.jsonl"
    assert cal.run(spec, load=namespace.__getitem__, records_path=out, root=root) == 2
    rows = [json.loads(line) for line in out.read_bytes().splitlines()]
    assert len(rows) == len(pool.submitted) == 3
    assert all(
        row["status"] == "FAILED_INFRA"
        and row["schema"] == cal.RECORD
        and row["reference_identity"] == cal.observer()
        for row in rows
    )
    receipt = json.loads(out.with_name(out.name + ".cal15.json").read_bytes())
    assert (
        not receipt["registered_calibration_complete"] and not receipt["qualification"]
    )


def test_closed_dispatch_preserves_g0_t9_and_exact_t128_roles():
    from scripts.dev.score_lab import guarded419_t128 as t128

    g0 = worker._guarded_job_context(guard.first_jobs()[0])
    assert g0 == {"schema": guard.RECORD, "reference_identity": guard.observer({})}
    anchor = worker._guarded_job_context(t9.jobs()[0])
    assert anchor == {"schema": t9.RECORD, "reference_identity": t9.observer()}
    job = t128.jobs()[9]
    actual = worker._guarded_job_context(job)
    assert actual == {
        "schema": t128.RECORD,
        "reference_identity": t128.observer(job["reference_role"]),
    }
    for bad in (
        t128.jobs()[0],
        {**job, "reference_role": "PUBLIC_EVALUATION"},
        {**job, "reference_admission": "UNKNOWN"},
        {k: v for k, v in job.items() if k != "reference_method"},
    ):
        with pytest.raises(tasks.TaskError):
            worker._guarded_job_context(bad)
    with pytest.raises(tasks.TaskError):
        worker._guarded_job_context(job, stage_binding={})
    assert (
        worker._guarded_job_context({"case_id": "LEGACY_NO_REFERENCE_METADATA"}) is None
    )


def test_eval_dispatch_rebuilds_context_checks_actual_source_and_refinement_membership():
    from scripts.dev.score_lab import guarded419_context as ctx
    from scripts.dev.score_lab import guarded419_eval as evaluation

    context = ctx.load(expected_sha256=ctx.REGISTRATION_SHA256)
    plan = evaluation.input_plan()
    source_pins = {
        "schema": evaluation.PINS,
        "scope": "DEVELOPMENT_ONLY",
        "execution_source": "a" * 40,
        "files": {
            p: _sha((ROOT / p).read_bytes()) for p in evaluation.REQUIRED_SOURCES
        },
    }
    bundle = {
        "schema": "carbon.battery.guarded419.eval-worker-context.v1",
        "registration_sha256": ctx.REGISTRATION_SHA256,
        "plan": plan,
        "plan_digest": tasks.digest(plan),
        "source_pins": source_pins,
        "source_pins_digest": tasks.digest(source_pins),
        "refinement_job_ids": [],
    }
    offered = evaluation.jobs(
        plan, expected_plan_digest=tasks.digest(plan), context=context
    )
    job = offered[0]
    actual = worker._guarded_job_context(
        job, stage_binding=bundle, expected_stage_binding_digest=tasks.digest(bundle)
    )
    assert actual == {
        "schema": evaluation.RECORD,
        "reference_identity": evaluation.observer(plan, source_pins["files"]),
    }
    assert (
        "context" not in bundle
    )  # The nominal protected-constructor object is NOT serialized.
    with pytest.raises(tasks.TaskError):
        worker._guarded_job_context(job)
    with pytest.raises(tasks.TaskError):
        worker._guarded_job_context(
            job,
            stage_binding=bundle,
            expected_stage_binding_digest="sha256:" + "0" * 64,
        )
    forged = copy.deepcopy(bundle)
    forged["source_pins"]["files"]["scripts/dev/score_lab/owner_v3.py"] = "f" * 64
    forged["source_pins_digest"] = tasks.digest(forged["source_pins"])
    with pytest.raises(tasks.TaskError, match="actual EVAL worker source bytes"):
        worker._guarded_job_context(
            job,
            stage_binding=forged,
            expected_stage_binding_digest=tasks.digest(forged),
        )
    refine_id = job["case_id"].rsplit(":mesh", 1)[0] + ":mesh80"
    refined = evaluation.jobs(
        plan,
        expected_plan_digest=tasks.digest(plan),
        context=context,
        refinement_job_ids=[refine_id],
    )[-1]
    with pytest.raises(tasks.TaskError):
        worker._guarded_job_context(
            refined,
            stage_binding=bundle,
            expected_stage_binding_digest=tasks.digest(bundle),
        )
    selected = {**bundle, "refinement_job_ids": [refine_id]}
    assert (
        worker._guarded_job_context(
            refined,
            stage_binding=selected,
            expected_stage_binding_digest=tasks.digest(selected),
        )["schema"]
        == evaluation.RECORD
    )
