"""One Root-dispatched guarded419 T128 partition using the existing worker pool.

This prospective runner is outside T128's frozen scientific source inventory.
The 9 T9 anchors and all CAL rows retain their original source/record identities.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path

from carbon.battery import truth_env
from carbon.design_search import tasks
from scripts.dev.battery import guarded_reference as guard
from scripts.dev.score_lab import guarded419_calibration_continue as cal
from scripts.dev.score_lab import guarded419_t128 as t128
from scripts.dev.score_lab import owner_v3_calibration_continue as collector
from scripts.dev.score_lab import owner_v3_panel_export as producer

MODULE = "scripts/dev/score_lab/guarded419_t128_worker.py"
FILE_SPEC = "carbon.scorelab.guarded419.t128-worker-files.v1"
RECEIPT = "carbon.scorelab.guarded419.t128-worker-receipt.v1"
CHUNKS = {1: "partition-1", 2: "partition-2"}


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _head(root):
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode or len(result.stdout.strip()) != 40:
        raise tasks.TaskError("actual T128 execution checkout unavailable")
    return result.stdout.strip()


def _source(binding, runner_sha256, root, calibration_sources):
    if (
        type(runner_sha256) is not str
        or len(runner_sha256) != 64
        or any(c not in "0123456789abcdef" for c in runner_sha256)
        or _head(root) != binding["execution_source"]
    ):
        raise tasks.TaskError("new T128 runner/execution commit differs")
    if any(
        binding["source_files"][name] != expected
        for name, expected in calibration_sources.items()
        if name in binding["source_files"]
    ):
        raise tasks.TaskError("T128 and original CAL source pins differ")
    sources = {
        **calibration_sources,
        **binding["source_files"],
        MODULE: runner_sha256,
    }
    for name, expected in sources.items():
        path = root / name
        if not path.is_file() or _sha(path.read_bytes()) != expected:
            raise tasks.TaskError("actual T128 source bytes differ: " + name)
        committed = subprocess.run(
            ["git", "-C", str(root), "show", "HEAD:" + name],
            capture_output=True,
            check=False,
        )
        if committed.returncode or _sha(committed.stdout) != expected:
            raise tasks.TaskError("T128 source absent from execution commit: " + name)


def _materials(spec, *, load):
    producer._fields(
        spec,
        (
            "schema",
            "scope",
            "partition",
            "binding",
            "prior_manifest",
            "prior_raw_chunks",
            "calibration",
            "expected_binding_digest",
            "expected_prior_manifest_digest",
            "runner_sha256",
        ),
        "T128 worker file specification",
    )
    if (
        spec["schema"] != FILE_SPEC
        or spec["scope"] not in ("PUBLIC_DEVELOPMENT", "SYNTHETIC_FIXTURE")
        or type(spec["partition"]) is not int
        or spec["partition"] not in CHUNKS
    ):
        raise tasks.TaskError("exact bounded T128 worker scope/partition required")
    binding = json.loads(cal._load(spec["binding"], load))
    prior_manifest = json.loads(cal._load(spec["prior_manifest"], load))
    if type(spec["prior_raw_chunks"]) is not dict:
        raise tasks.TaskError("T128 previous raw chunk map required")
    prior_raw = {
        name: cal._load(entry, load) for name, entry in spec["prior_raw_chunks"].items()
    }
    if binding["scope"] != spec["scope"]:
        raise tasks.TaskError("T128 worker binding/file scope differs")
    t128._binding(binding, spec["expected_binding_digest"])
    if tasks.digest(prior_manifest) != spec["expected_prior_manifest_digest"]:
        raise tasks.TaskError("prior T128 manifest differs from independent pin")
    cal_material, _ = cal._materials(
        spec["calibration"], load=load, scope=spec["scope"]
    )
    calibration_evidence = cal.validate_delivery(**cal_material)
    t9_material = {
        **cal_material["t9_delivery"],
        "expected_binding_digest": binding["prerequisites"]["t9"]["binding_digest"],
        "expected_manifest_digest": binding["prerequisites"]["t9"]["manifest_digest"],
        "g0_binding": cal_material["g0_binding"],
        "g0_raw": cal_material["g0_raw"],
        "g0_receipt": cal_material["g0_receipt"],
    }
    prerequisites = {
        "t9_delivery": t9_material,
        "calibration_evidence": calibration_evidence,
    }
    return (
        binding,
        prior_manifest,
        prior_raw,
        prerequisites,
        cal_material["binding"]["source_files"],
    )


def _previous(binding, manifest, raw_chunks, prerequisites, partition):
    first = t128.partition_jobs(1)
    if partition == 1:
        if manifest != t128.delivery_manifest(binding, []) or raw_chunks:
            raise tasks.TaskError("first T128 partition requires empty prior delivery")
    elif (
        len(manifest["chunks"]) != 1
        or manifest["chunks"][0]["id"] != CHUNKS[1]
        or set(raw_chunks) != {CHUNKS[1]}
    ):
        raise tasks.TaskError("second T128 partition requires first original chunk")
    prior = t128.validate_for(
        t128.validate_delivery(
            binding,
            manifest,
            raw_chunks,
            expected_binding_digest=tasks.digest(binding),
            expected_manifest_digest=tasks.digest(manifest),
            **prerequisites,
        ),
        expected_binding_digest=tasks.digest(binding),
        expected_manifest_digest=tasks.digest(manifest),
        scope=binding["scope"],
    )
    anchors = {j["case_id"] for j in t128.jobs()[:9]}
    if set(prior["records"]) != (
        anchors if partition == 1 else anchors | {j["case_id"] for j in first}
    ):
        raise tasks.TaskError("exact nine reused anchors and prior60 rows required")
    return prior


def run(spec, *, load, records_path, workers=2, root=None):
    """Write one native partition and receipt; Root controls external limits."""
    if type(workers) is not int or not 1 <= workers <= 2:
        raise tasks.TaskError("T128 requires one or two workers")
    binding, prior_manifest, prior_raw, prerequisites, calibration_sources = _materials(
        spec, load=load
    )
    partition = spec["partition"]
    prior = _previous(binding, prior_manifest, prior_raw, prerequisites, partition)
    root = Path(root) if root is not None else Path(__file__).resolve().parents[3]
    _source(binding, spec["runner_sha256"], root, calibration_sources)
    provenance = truth_env.provenance(root)
    if (
        provenance.get("schema") != "carbon.battery.solver-provenance.v1"
        or provenance.get("solver_image")
        != "ghcr.io/carbonphysicsai/carbon-determinism-study@" + guard.IMAGE
        or provenance.get("overlay_lock")
        != "scripts/dev/exam_design/locks/battery-overlay.lock.json"
        or provenance.get("overlay_lock_sha256")
        != "sha256:6267e033b30728b200d9e0c2aa6b55a9117cd67e03c6f89c9a17294d12e594ee"
        or provenance.get("pybamm") != "26.8.0.0"
    ):
        raise tasks.TaskError("T128 truth runtime differs")
    records = Path(records_path)
    receipt_path = records.with_name(records.name + ".t128.json")
    temporary = receipt_path.with_name(receipt_path.name + ".tmp")
    if any(os.path.lexists(p) for p in (records, receipt_path, temporary)) or any(
        p.is_symlink() for p in records.parents
    ):
        raise tasks.TaskError("T128 requires fresh non-symlink output/receipt")
    offers = t128.partition_jobs(partition)
    prior_new_ids = set(prior["records"]) - {job["case_id"] for job in t128.jobs()[:9]}
    expected_new_ids = prior_new_ids | {job["case_id"] for job in offers}
    states = {j["case_id"]: "NOT_DISPATCHED" for j in offers}
    mappings = []
    receipt = {
        "schema": RECEIPT,
        "scope": binding["scope"],
        "partition": partition,
        "status": "INCOMPLETE_REFERENCE",
        "binding_digest": tasks.digest(binding),
        "prior_manifest_digest": tasks.digest(prior_manifest),
        "execution_source": binding["execution_source"],
        "source_files": binding["source_files"],
        "runner_sha256": spec["runner_sha256"],
        "solver_provenance": provenance,
        "offered_job_ids": [j["case_id"] for j in offers],
        "authenticated_t9_anchor_count": 9,
        "authenticated_prior_new_row_count": len(prior["records"]) - 9,
        "per_job": states,
        "automatic_next_stage": False,
        "training_release": False,
        "evaluation_release": False,
        "qualification": False,
    }

    def current(raw):
        chunk = {
            "id": CHUNKS[partition],
            "sha256": _sha(raw),
            "source_commit": binding["execution_source"],
            "source_files": binding["source_files"],
            "rows": mappings,
        }
        manifest = t128.delivery_manifest(binding, prior_manifest["chunks"] + [chunk])
        return manifest, {**prior_raw, CHUNKS[partition]: raw}

    def save():
        raw = records.read_bytes()
        manifest, _ = current(raw)
        receipt.update(
            records_sha256=_sha(raw),
            manifest=manifest,
            manifest_digest=tasks.digest(manifest),
        )
        with temporary.open("x", encoding="utf-8") as handle:
            handle.write(json.dumps(receipt, sort_keys=True, allow_nan=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(receipt_path)

    def submitted(job):
        states[job["case_id"]] = "SUBMITTED"
        save()

    def received(job, record):
        if record.get("status") == "FAILED_INFRA":
            record.setdefault(
                "reference_identity", t128.observer(job["reference_role"])
            )
        stamped = truth_env.stamp(record, provenance)
        with records.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(stamped, sort_keys=True, allow_nan=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        mappings.append({"line": len(mappings) + 1, "job_id": job["case_id"]})
        states[job["case_id"]] = stamped.get("status", "MALFORMED_RECORD")
        save()
        return stamped

    with records.open("x", encoding="utf-8"):
        pass
    save()
    try:
        collector._collect_groups(
            [offers],
            workers=workers,
            submitted=submitted,
            received=received,
            completed=lambda _group, _rows: True,
            record_schema=t128.RECORD,
        )
        manifest, raw_chunks = current(records.read_bytes())
        new, _proof, tracking, admitted = t128._new_delivery(
            binding,
            manifest,
            raw_chunks,
            expected_binding_digest=tasks.digest(binding),
            expected_manifest_digest=tasks.digest(manifest),
        )
        if set(new) != expected_new_ids:
            receipt["status"] = "INCOMPLETE_REFERENCE"
        elif all(
            tracking[j["case_id"]]["status"] == "TRACKING_COMPATIBLE"
            and admitted[j["case_id"]]["extraction_state"] == "EXTRACTED"
            for j in offers
        ):
            receipt["status"] = "COMPATIBLE_PARTITION_ONLY"
        else:
            receipt["status"] = "REFERENCE_UNRESOLVED"
        save()
        return 0 if receipt["status"] == "COMPATIBLE_PARTITION_ONLY" else 2
    except BaseException as original_error:
        receipt["status"] = (
            "INTERRUPTED"
            if isinstance(original_error, (KeyboardInterrupt, SystemExit))
            else (
                "INVALID_REFERENCE"
                if isinstance(original_error, tasks.TaskError)
                else "FAILED_INFRA"
            )
        )
        try:
            save()
        except Exception as error:  # noqa: BLE001 -- preserve original
            original_error.add_note(
                "T128 receipt persistence failed: " + type(error).__name__
            )
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--spec-sha256", required=True)
    parser.add_argument("--public-root", type=Path, required=True)
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args(argv)
    raw = args.spec.read_bytes()
    if _sha(raw) != args.spec_sha256:
        raise tasks.TaskError("Root-pinned T128 invocation bytes required")
    root = args.public_root.resolve(strict=True)

    def load(name):
        path = (root / name).resolve(strict=True)
        if not path.is_relative_to(root) or not path.is_file():
            raise tasks.TaskError("T128 file escapes public input root")
        return path.read_bytes()

    return run(
        json.loads(raw), load=load, records_path=args.records, workers=args.workers
    )


if __name__ == "__main__":
    raise SystemExit(main())
