"""Synthetic T128 partition collection; no model, solver or provider execution."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path
from typing import ClassVar

import pytest

from carbon.battery import truth_env
from carbon.design_search import tasks
from scripts.dev.battery import feasibility02 as worker
from scripts.dev.battery import guarded_reference as guard
from scripts.dev.score_lab import guarded419_t128 as t128
from scripts.dev.score_lab import guarded419_t128_worker as runner
from scripts.dev.score_lab import owner_v3_calibration_continue as collector

ROOT = Path(__file__).resolve().parents[2]


def _module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cal_test = _module(
    "cal_toy_for_t128_worker",
    ROOT / "tests/cpu/test_score_lab_guarded419_calibration_continue.py",
)
toy = _module("t128_toy_for_worker", ROOT / "tests/fixtures/guarded419_t128.py")


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _bytes(value):
    return (json.dumps(value, sort_keys=True) + "\n").encode()


def _entry(namespace, raw):
    name = f"T128_RESOURCE_{len(namespace) + 1}"
    namespace[name] = raw
    return {"path": name, "sha256": _sha(raw)}


@pytest.fixture(scope="module")
def template(tmp_path_factory):
    root = tmp_path_factory.mktemp("t128-worker-synthetic")
    cal_material = cal_test._make(root, "SYNTHETIC_FIXTURE")
    cal_spec, namespace = cal_test._file_spec(cal_material)
    files = {name: "b" * 64 for name in t128.REQUIRED_SOURCES}
    files.update(
        {
            name: value
            for name, value in cal_material["binding"]["source_files"].items()
            if name in files
        }
    )
    files[t128.INPUT_FILE] = t128.INPUT_FILE_SHA
    binding = t128.execution_binding(
        source_commit="c" * 40,
        source_files=files,
        prerequisites={
            "t9": {
                "binding_digest": cal_material["binding"]["t9"]["binding_digest"],
                "manifest_digest": cal_material["binding"]["t9"]["manifest_digest"],
            },
            "cal15": {
                "binding_digest": cal_material["expected_binding_digest"],
                "manifest_digest": cal_material["expected_manifest_digest"],
            },
        },
        dispatch_id="SYNTHETIC_T128_WORKER_TEST",
        scope="SYNTHETIC_FIXTURE",
    )
    prior_manifest = t128.delivery_manifest(binding, [])
    spec = {
        "schema": runner.FILE_SPEC,
        "scope": "SYNTHETIC_FIXTURE",
        "partition": 1,
        "binding": _entry(namespace, _bytes(binding)),
        "prior_manifest": _entry(namespace, _bytes(prior_manifest)),
        "prior_raw_chunks": {},
        "calibration": cal_spec,
        "expected_binding_digest": tasks.digest(binding),
        "expected_prior_manifest_digest": tasks.digest(prior_manifest),
        "runner_sha256": "f" * 64,
    }
    return root, spec, namespace, binding, cal_material


@pytest.fixture
def setup(template, monkeypatch):
    root, spec, namespace, binding, cal_material = template
    spec, namespace = copy.deepcopy((spec, namespace))
    monkeypatch.setattr(runner, "_source", lambda *_: None)
    provenance = cal_test.toy.record(guard.first_jobs()[0])["solver_provenance"]
    monkeypatch.setattr(truth_env, "provenance", lambda _: provenance)
    monkeypatch.setattr(collector, "as_completed", lambda futures: list(futures))

    class Pool:
        offered: ClassVar[list] = []
        fail_at = None
        infra_at = None
        interrupt_at = None
        wrong_role_at = None

        def __init__(self, workers):
            assert workers == 2

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def submit(self, function, job):
            assert function is worker._timed
            self.offered.append(job)
            index = len(self.offered)

            class Future:
                def result(self):
                    if index == Pool.infra_at:
                        raise RuntimeError("synthetic infrastructure failure")
                    if index == Pool.interrupt_at:
                        raise KeyboardInterrupt("synthetic interruption")
                    row = toy.record(job)
                    if index == Pool.wrong_role_at:
                        row["reference_identity"] = t128.observer(t128.CONSTRUCTION)
                    if index == Pool.fail_at:
                        row["status"] = "REFERENCE_SOLVER_FAILED"
                    return row

            return Future()

    monkeypatch.setattr(collector, "ProcessPoolExecutor", Pool)
    return root, spec, namespace, binding, cal_material, Pool


def _receipt(path):
    return json.loads(path.with_name(path.name + ".t128.json").read_bytes())


def _second(spec, namespace, binding, receipt, raw):
    result = copy.deepcopy(spec)
    result["partition"] = 2
    result["prior_manifest"] = _entry(namespace, _bytes(receipt["manifest"]))
    result["prior_raw_chunks"] = {
        runner.CHUNKS[1]: _entry(namespace, raw),
    }
    result["expected_prior_manifest_digest"] = tasks.digest(receipt["manifest"])
    assert result["expected_binding_digest"] == tasks.digest(binding)
    return result


def test_existing_partitions_and_authenticated_prerequisites_before_pool(
    setup, tmp_path
):
    root, spec, namespace, _binding, _cal, pool = setup
    assert [len(t128.partition_jobs(i)) for i in (1, 2)] == [60, 59]
    assert t128.partition_jobs(1) + t128.partition_jobs(2) == t128.jobs()[9:]
    bad = copy.deepcopy(spec)
    bad["calibration"]["expected_manifest_digest"] = "sha256:" + "0" * 64
    out = tmp_path / "blocked.jsonl"
    with pytest.raises(tasks.TaskError):
        runner.run(bad, load=namespace.__getitem__, records_path=out, root=root)
    assert not out.exists() and not pool.offered
    bad = copy.deepcopy(spec)
    bad["partition"] = 2
    with pytest.raises(tasks.TaskError):
        runner.run(bad, load=namespace.__getitem__, records_path=out, root=root)
    assert not out.exists() and not pool.offered


def test_two_bounded_partitions_reuse_nine_and_preserve_105_23_roles(setup, tmp_path):
    root, spec, namespace, binding, cal_material, pool = setup
    first = tmp_path / "first.jsonl"
    assert (
        runner.run(spec, load=namespace.__getitem__, records_path=first, root=root) == 0
    )
    first_receipt = _receipt(first)
    assert len(pool.offered) == 60
    assert pool.offered == t128.partition_jobs(1)
    assert first_receipt["status"] == "COMPATIBLE_PARTITION_ONLY"
    assert first_receipt["authenticated_t9_anchor_count"] == 9
    assert first_receipt["authenticated_prior_new_row_count"] == 0
    assert not first_receipt["training_release"]
    assert not first_receipt["evaluation_release"]
    second_spec = _second(spec, namespace, binding, first_receipt, first.read_bytes())
    second = tmp_path / "second.jsonl"
    assert (
        runner.run(
            second_spec, load=namespace.__getitem__, records_path=second, root=root
        )
        == 0
    )
    second_receipt = _receipt(second)
    assert len(pool.offered) == 119
    assert pool.offered == t128.jobs()[9:]
    assert second_receipt["authenticated_prior_new_row_count"] == 60
    assert second_receipt["status"] == "COMPATIBLE_PARTITION_ONLY"
    assert not second_receipt["training_release"]
    assert not second_receipt["evaluation_release"]
    cal_material = copy.deepcopy(cal_material)
    t9_delivery = {
        **cal_material["t9_delivery"],
        "expected_binding_digest": binding["prerequisites"]["t9"]["binding_digest"],
        "expected_manifest_digest": binding["prerequisites"]["t9"]["manifest_digest"],
        "g0_binding": cal_material["g0_binding"],
        "g0_raw": cal_material["g0_raw"],
        "g0_receipt": cal_material["g0_receipt"],
    }
    from scripts.dev.score_lab import guarded419_calibration_continue as cal

    nominal = t128.validate_delivery(
        binding,
        second_receipt["manifest"],
        {
            runner.CHUNKS[1]: first.read_bytes(),
            runner.CHUNKS[2]: second.read_bytes(),
        },
        expected_binding_digest=tasks.digest(binding),
        expected_manifest_digest=second_receipt["manifest_digest"],
        t9_delivery=t9_delivery,
        calibration_evidence=cal.validate_delivery(**cal_material),
    )
    snapshot = t128.validate_for(
        nominal,
        expected_binding_digest=tasks.digest(binding),
        expected_manifest_digest=second_receipt["manifest_digest"],
        scope="SYNTHETIC_FIXTURE",
    )
    assert len(snapshot["records"]) == 128
    assert [snapshot["roles_by_job_id"][j["case_id"]] for j in t128.jobs()].count(
        t128.VALIDATION
    ) == 23
    assert all(
        snapshot["source_rows"][j["case_id"]]["kind"] == "AUTHENTICATED_T9_REUSE"
        for j in t128.jobs()[:9]
    )


def test_second_partition_refuses_missing_prior_row_before_pool(setup, tmp_path):
    root, spec, namespace, binding, _cal, pool = setup
    first = tmp_path / "prior.jsonl"
    assert (
        runner.run(spec, load=namespace.__getitem__, records_path=first, root=root) == 0
    )
    receipt = _receipt(first)
    rows = [json.loads(line) for line in first.read_bytes().splitlines()][:-1]
    partial_raw = b"".join(_bytes(row) for row in rows)
    prior_chunk = copy.deepcopy(receipt["manifest"]["chunks"][0])
    prior_chunk["sha256"] = _sha(partial_raw)
    prior_chunk["rows"] = [
        {"line": i, "job_id": row["case_id"]} for i, row in enumerate(rows, 1)
    ]
    partial_manifest = t128.delivery_manifest(binding, [prior_chunk])
    second_spec = _second(
        spec, namespace, binding, {"manifest": partial_manifest}, partial_raw
    )
    second = tmp_path / "second-blocked.jsonl"
    with pytest.raises(tasks.TaskError, match="prior60 rows required"):
        runner.run(
            second_spec, load=namespace.__getitem__, records_path=second, root=root
        )
    assert not second.exists()
    assert len(pool.offered) == 60


def test_second_partition_missing_current_row_stays_incomplete(
    setup, tmp_path, monkeypatch
):
    root, spec, namespace, binding, _cal, pool = setup
    first = tmp_path / "prior.jsonl"
    assert (
        runner.run(spec, load=namespace.__getitem__, records_path=first, root=root) == 0
    )
    second_spec = _second(spec, namespace, binding, _receipt(first), first.read_bytes())
    missing_id = t128.partition_jobs(2)[-1]["case_id"]
    original_collect = collector._collect_groups

    def omit_one_returned_row(groups, **kwargs):
        received = kwargs["received"]

        def keep_all_but_one(job, record):
            if job["case_id"] == missing_id:
                return record
            return received(job, record)

        return original_collect(groups, **{**kwargs, "received": keep_all_but_one})

    monkeypatch.setattr(collector, "_collect_groups", omit_one_returned_row)
    second = tmp_path / "second-incomplete.jsonl"
    assert (
        runner.run(
            second_spec, load=namespace.__getitem__, records_path=second, root=root
        )
        == 2
    )
    receipt = _receipt(second)
    assert len(pool.offered) == 119
    assert len(second.read_bytes().splitlines()) == 58
    assert receipt["authenticated_prior_new_row_count"] == 60
    assert receipt["per_job"][missing_id] == "SUBMITTED"
    assert receipt["status"] == "INCOMPLETE_REFERENCE"
    assert not receipt["training_release"] and not receipt["evaluation_release"]


@pytest.mark.parametrize("failure", ["solver", "infra"])
def test_observed_failures_remain_raw_and_never_release(setup, tmp_path, failure):
    root, spec, namespace, _binding, _cal, pool = setup
    if failure == "solver":
        pool.fail_at = 2
    else:
        pool.infra_at = 2
    out = tmp_path / "failure.jsonl"
    assert (
        runner.run(spec, load=namespace.__getitem__, records_path=out, root=root) == 2
    )
    receipt = _receipt(out)
    rows = [json.loads(line) for line in out.read_bytes().splitlines()]
    assert len(rows) == 60
    assert rows[1]["status"] == (
        "REFERENCE_SOLVER_FAILED" if failure == "solver" else "FAILED_INFRA"
    )
    assert receipt["status"] == "REFERENCE_UNRESOLVED"
    assert receipt["per_job"][rows[1]["case_id"]] == rows[1]["status"]
    assert not receipt["training_release"] and not receipt["evaluation_release"]


def test_interruption_retains_partial_native_receipt(setup, tmp_path):
    root, spec, namespace, _binding, _cal, pool = setup
    pool.interrupt_at = 2
    out = tmp_path / "interrupted.jsonl"
    with pytest.raises(KeyboardInterrupt, match="synthetic interruption"):
        runner.run(spec, load=namespace.__getitem__, records_path=out, root=root)
    receipt = _receipt(out)
    assert len(out.read_bytes().splitlines()) == 1
    assert receipt["status"] == "INTERRUPTED"
    assert receipt["per_job"][t128.partition_jobs(1)[1]["case_id"]] == "SUBMITTED"
    assert not receipt["training_release"]


def test_wrong_observer_retains_raw_and_invalid_reference_receipt(setup, tmp_path):
    root, spec, namespace, _binding, _cal, pool = setup
    pool.wrong_role_at = 5  # Fifth nonanchor offer has validation-only role.
    out = tmp_path / "wrong-role.jsonl"
    with pytest.raises(tasks.TaskError, match="foreign T128 schema/observer/role"):
        runner.run(spec, load=namespace.__getitem__, records_path=out, root=root)
    receipt = _receipt(out)
    assert len(out.read_bytes().splitlines()) == 60
    assert receipt["status"] == "INVALID_REFERENCE"
    assert not receipt["training_release"] and not receipt["evaluation_release"]


def test_source_binds_runner_and_all_existing_files_to_actual_commit(tmp_path):
    head = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    files = {name: _sha((ROOT / name).read_bytes()) for name in t128.REQUIRED_SOURCES}
    binding = {"execution_source": head, "source_files": files}
    from scripts.dev.score_lab import guarded419_calibration_continue as cal

    calibration_sources = {
        name: _sha((ROOT / name).read_bytes()) for name in cal.REQUIRED_SOURCES
    }
    runner_sha = _sha((ROOT / runner.MODULE).read_bytes())
    runner._source(binding, runner_sha, ROOT, calibration_sources)
    with pytest.raises(tasks.TaskError, match="execution commit"):
        runner._source(
            {**binding, "execution_source": "0" * 40},
            runner_sha,
            ROOT,
            calibration_sources,
        )
    with pytest.raises(tasks.TaskError, match="source bytes differ"):
        runner._source(binding, "f" * 64, ROOT, calibration_sources)
    with pytest.raises(tasks.TaskError, match="original CAL source pins differ"):
        runner._source(
            binding,
            runner_sha,
            ROOT,
            {**calibration_sources, "scripts/dev/battery/feasibility02.py": "f" * 64},
        )


def test_mixed_source_or_prior_raw_pin_refused_before_pool(setup, tmp_path):
    root, spec, namespace, binding, _cal, pool = setup
    bad = copy.deepcopy(spec)
    document = json.loads(namespace[bad["binding"]["path"]])
    document["source_files"]["carbon/battery/reference.py"] = "f" * 64
    bad["binding"] = _entry(namespace, _bytes(document))
    bad["expected_binding_digest"] = tasks.digest(document)
    mixed_manifest = t128.delivery_manifest(document, [])
    bad["prior_manifest"] = _entry(namespace, _bytes(mixed_manifest))
    bad["expected_prior_manifest_digest"] = tasks.digest(mixed_manifest)
    out = tmp_path / "mixed.jsonl"
    with pytest.raises(tasks.TaskError):
        runner.run(bad, load=namespace.__getitem__, records_path=out, root=root)
    assert not out.exists() and not pool.offered
    first = tmp_path / "first.jsonl"
    assert (
        runner.run(spec, load=namespace.__getitem__, records_path=first, root=root) == 0
    )
    prior = _receipt(first)
    second = _second(spec, namespace, binding, prior, first.read_bytes())
    bad_key = second["prior_raw_chunks"][runner.CHUNKS[1]]["path"]
    namespace[bad_key] += b" \n"
    out = tmp_path / "second-blocked.jsonl"
    with pytest.raises(tasks.TaskError):
        runner.run(second, load=namespace.__getitem__, records_path=out, root=root)
    assert not out.exists() and len(pool.offered) == 60
