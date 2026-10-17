"""One bounded Root-dispatched guarded419 DEVELOPMENT EVAL reference chunk.

This runner transports the existing closed EVAL stage binding to feasibility02's
worker pool. It requires actual nominal CAL and pretruth inputs before opening
an output or submitting a reference job. Root separately owns pretruth custody
chronology, provider admission, and subsequent EVAL evidence construction.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from concurrent.futures import ProcessPoolExecutor
from functools import partial
from pathlib import Path, PureWindowsPath

from carbon.battery import truth_env
from carbon.design_search import tasks
from scripts.dev.battery import feasibility02
from scripts.dev.battery import guarded_reference as guard
from scripts.dev.score_lab import guarded419_calibration_continue as cal
from scripts.dev.score_lab import guarded419_context as context_module
from scripts.dev.score_lab import guarded419_eval as evaluation
from scripts.dev.score_lab import owner_v3_panel_export as producer

MODULE = "scripts/dev/score_lab/guarded419_eval_worker.py"
FILE_SPEC = "carbon.scorelab.guarded419.eval-worker-files.v1"
RECEIPT = "carbon.scorelab.guarded419.eval-worker-receipt.v1"
MEMBER_FILES = {
    "fit_receipt": "fit_receipt_sha256",
    "predictions": "predictions_sha256",
    "commitments": "commitments_sha256",
    "commitment_receipt": "commitment_receipt_sha256",
}


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _canonical_key(name):
    if (
        type(name) is not str
        or not name
        or "\\" in name
        or PureWindowsPath(name).drive
        or any(part in ("", ".", "..") for part in name.split("/"))
    ):
        raise tasks.TaskError("canonical relative EVAL input key required")
    return name


def _public_load(root, name):
    """Reject spelling and symlink aliases even when they remain inside root."""
    _canonical_key(name)
    path = root / name
    resolved = path.resolve(strict=True)
    if resolved != path or not resolved.is_relative_to(root) or not resolved.is_file():
        raise tasks.TaskError("EVAL input alias or public-root escape")
    return resolved.read_bytes()


def _head(root):
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode or not re.fullmatch(r"[0-9a-f]{40}", result.stdout.strip()):
        raise tasks.TaskError("actual EVAL execution checkout unavailable")
    return result.stdout.strip()


def _source(pins, runner_sha256, root, calibration_sources=None, *, environ=os.environ):
    """Check local bytes plus checkout or pod bootstrap identity, not attestation."""
    evaluation._hex(runner_sha256)
    commit = pins["execution_source"]
    checkout = (root / ".git").exists()
    if checkout:
        if _head(root) != commit:
            raise tasks.TaskError("EVAL execution commit differs")
        basis = "GIT_CHECKOUT_AND_LOCAL_FILE_HASHES"
    else:
        if environ.get("CODE_REF") != commit:
            raise tasks.TaskError("pinned pod bootstrap CODE_REF differs")
        basis = "POD_BOOTSTRAP_CODE_REF_AND_LOCAL_FILE_HASHES"
    calibration_sources = calibration_sources or {}
    if any(
        pins["files"][name] != expected
        for name, expected in calibration_sources.items()
        if name in pins["files"]
    ):
        raise tasks.TaskError("original CAL and EVAL scientific source pins differ")
    sources = {**calibration_sources, **pins["files"], MODULE: runner_sha256}
    for name, expected in sources.items():
        path = root / name
        if not path.is_file() or _sha(path.read_bytes()) != expected:
            raise tasks.TaskError("actual EVAL source bytes differ: " + name)
        if checkout:
            committed = subprocess.run(
                ["git", "-C", str(root), "show", "HEAD:" + name],
                capture_output=True,
                check=False,
            )
            if committed.returncode or _sha(committed.stdout) != expected:
                raise tasks.TaskError(
                    "EVAL source absent from execution commit: " + name
                )
    return basis


def _selected(spec, offered):
    selected_ids = spec["selected_job_ids"]
    if (
        type(selected_ids) is not list
        or not selected_ids
        or not all(type(job_id) is str for job_id in selected_ids)
        or len(set(selected_ids)) != len(selected_ids)
        or selected_ids
        != [job["case_id"] for job in offered if job["case_id"] in selected_ids]
    ):
        raise tasks.TaskError("nonempty registered ordered EVAL job subset required")
    selected = [job for job in offered if job["case_id"] in selected_ids]
    if any(
        job["reference_role"] != "PUBLIC_EVALUATION"
        or job["reference_admission"] != evaluation.ADMISSION
        for job in selected
    ):
        raise tasks.TaskError("original registered EVAL role required")
    return selected


def _member_files(spec, cohort, load):
    member_files = spec["member_files"]
    members = {member["id"]: member for member in cohort["members"]}
    if type(member_files) is not dict or set(member_files) != set(members):
        raise tasks.TaskError("all eighteen original pretruth member files required")
    seen_paths = set()
    for member_id, entries in member_files.items():
        producer._fields(entries, MEMBER_FILES, "pretruth member file inventory")
        for name, field in MEMBER_FILES.items():
            entry = entries[name]
            if entry["sha256"] != members[member_id][field]:
                raise tasks.TaskError("pretruth member content pin differs")
            canonical = _canonical_key(entry["path"])
            if canonical.casefold() in seen_paths:
                raise tasks.TaskError("pretruth member file path reused")
            seen_paths.add(canonical.casefold())
            cal._load(entry, load)


def _materials(spec, *, load, root):
    """Authenticate every non-EVAL-truth prerequisite before returning offers."""
    producer._fields(
        spec,
        (
            "schema",
            "scope",
            "stage_binding",
            "expected_stage_binding_digest",
            "calibration",
            "pretruth",
            "member_files",
            "selected_job_ids",
            "chunk_id",
            "runner_sha256",
        ),
        "guarded EVAL worker file specification",
    )
    if spec["schema"] != FILE_SPEC or spec["scope"] != "PUBLIC_DEVELOPMENT":
        raise tasks.TaskError("public DEVELOPMENT EVAL worker specification required")
    if not isinstance(spec["chunk_id"], str) or not re.fullmatch(
        r"[a-z0-9][a-z0-9-]{0,79}", spec["chunk_id"]
    ):
        raise tasks.TaskError("Root-bound EVAL chunk identity required")
    binding = json.loads(cal._load(spec["stage_binding"], load))
    if (
        type(binding) is not dict
        or set(binding)
        != {
            "schema",
            "registration_sha256",
            "plan",
            "plan_digest",
            "source_pins",
            "source_pins_digest",
            "refinement_job_ids",
        }
        or binding["schema"] != "carbon.battery.guarded419.eval-worker-context.v1"
        or tasks.digest(binding) != spec["expected_stage_binding_digest"]
    ):
        raise tasks.TaskError("closed independently bound EVAL worker context required")
    context = context_module.load(expected_sha256=binding["registration_sha256"])
    evaluation._plan(binding["plan"], binding["plan_digest"])
    evaluation._source_pins(
        binding["source_pins"], binding["source_pins_digest"], context
    )
    offered = evaluation.jobs(
        binding["plan"],
        expected_plan_digest=binding["plan_digest"],
        context=context,
        refinement_job_ids=binding["refinement_job_ids"],
    )
    selected = _selected(spec, offered)

    raw_pretruth = cal._load(spec["pretruth"], load)
    cohort = evaluation.pretruth_receipt(
        raw_pretruth,
        spec["pretruth"]["sha256"],
        binding["plan"],
        binding["plan_digest"],
        spec["scope"],
        context,
    )
    _member_files(spec, cohort, load)

    calibration_evidence = evaluation.calibration_from_files(
        spec["calibration"], load=load, scope=spec["scope"], context=context
    )
    cal_pin = {
        "binding_digest": spec["calibration"]["expected_binding_digest"],
        "manifest_digest": spec["calibration"]["expected_manifest_digest"],
    }
    calibration = evaluation.validate_calibration(
        calibration_evidence,
        {"scope": spec["scope"], "calibration": cal_pin},
        binding["source_pins"],
        context=context,
    )
    if set(calibration["source_files"]) != cal.REQUIRED_SOURCES:
        raise tasks.TaskError("original CAL14 source inventory differs")
    basis = _source(
        binding["source_pins"],
        spec["runner_sha256"],
        root,
        calibration["source_files"],
    )
    return binding, selected, len(offered), cohort, calibration, basis


def _provenance(root):
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
        raise tasks.TaskError("EVAL truth runtime differs")
    return provenance


def run(spec, *, load, records_path, workers=2, root=None):
    """Collect one explicit ordered EVAL subset; Root owns external limits."""
    if type(workers) is not int or not 1 <= workers <= 2:
        raise tasks.TaskError("EVAL requires one or two workers")
    root = Path(root) if root is not None else Path(__file__).resolve().parents[3]
    binding, selected, offered_count, cohort, calibration, basis = _materials(
        spec, load=load, root=root
    )
    provenance = _provenance(root)
    records = Path(records_path)
    receipt_path = records.with_name(records.name + ".eval.json")
    temporary = receipt_path.with_name(receipt_path.name + ".tmp")
    if any(os.path.lexists(path) for path in (records, receipt_path, temporary)) or any(
        parent.is_symlink() for parent in records.parents
    ):
        raise tasks.TaskError("EVAL requires fresh non-symlink output/receipt")
    states = {job["case_id"]: "NOT_DISPATCHED" for job in selected}
    tracking = {}
    mappings = []
    receipt = {
        "schema": RECEIPT,
        "scope": spec["scope"],
        "role": "HELDOUT_REFERENCE",
        "status": "INCOMPLETE_REFERENCE",
        "chunk_id": spec["chunk_id"],
        "file_spec_digest": tasks.digest(spec),
        "stage_binding_digest": spec["expected_stage_binding_digest"],
        "calibration_binding_digest": calibration["binding_digest"],
        "calibration_manifest_digest": calibration["manifest_digest"],
        "pretruth_sha256": spec["pretruth"]["sha256"],
        "pretruth_member_ids": [member["id"] for member in cohort["members"]],
        "pretruth_file_pins_authenticated": True,
        "pretruth_custody_chronology": "ROOT_EXTERNAL_PROOF_REQUIRED",
        "execution_source": binding["source_pins"]["execution_source"],
        "source_files": binding["source_pins"]["files"],
        "runner_sha256": spec["runner_sha256"],
        "source_identity_basis": basis,
        "solver_provenance": provenance,
        "registered_job_count": offered_count,
        "selected_job_ids": [job["case_id"] for job in selected],
        "registered_refinement_job_ids": binding["refinement_job_ids"],
        "per_job": states,
        "tracking": tracking,
        "automatic_next_stage": False,
        "evaluation_release": False,
        "qualification": False,
    }

    def save():
        raw = records.read_bytes()
        chunk = {
            "id": spec["chunk_id"],
            "sha256": _sha(raw),
            "role": "PUBLIC_EVALUATION",
            "source_commit": binding["source_pins"]["execution_source"],
            "source_files": binding["source_pins"]["files"],
            "rows": list(mappings),
        }
        receipt.update(records_sha256=_sha(raw), chunk=chunk)
        with temporary.open("x", encoding="utf-8") as handle:
            handle.write(json.dumps(receipt, sort_keys=True, allow_nan=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(receipt_path)

    with records.open("x", encoding="utf-8"):
        pass
    save()
    try:
        timed = partial(
            feasibility02._timed,
            stage_binding=binding,
            expected_stage_binding_digest=spec["expected_stage_binding_digest"],
        )
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures = []
            for job in selected:
                states[job["case_id"]] = "SUBMITTED"
                save()
                futures.append(pool.submit(timed, job))
            for job, future in zip(selected, futures, strict=True):
                jid = job["case_id"]
                try:
                    record = future.result()
                except Exception:  # noqa: BLE001
                    # Worker process failure is infrastructure, not physics.
                    states[jid] = "FAILED_INFRA"
                    save()
                    continue
                if (
                    type(record) is not dict
                    or record.get("case_id") != jid
                    or record.get("schema") != evaluation.RECORD
                    or any(record.get(key) != value for key, value in job.items())
                ):
                    states[jid] = "INVALID_REFERENCE"
                    save()
                    continue
                stamped = truth_env.stamp(record, provenance)
                try:
                    observation = guard._tracking_report(
                        stamped,
                        expected_job=job,
                        reference_identity=evaluation.observer(
                            binding["plan"], binding["source_pins"]["files"]
                        ),
                        record_schema=evaluation.RECORD,
                        method_digest=tasks.digest(guard.METHOD),
                    )
                except Exception as error:  # noqa: BLE001 -- retain original row
                    observation = {
                        "status": "REFERENCE_UNRESOLVED",
                        "error_type": type(error).__name__,
                    }
                with records.open("a", encoding="utf-8") as handle:
                    handle.write(
                        json.dumps(stamped, sort_keys=True, allow_nan=True) + "\n"
                    )
                    handle.flush()
                    os.fsync(handle.fileno())
                mappings.append(
                    {"line": len(mappings) + 1, "job_id": jid, "case_id": jid}
                )
                tracking[jid] = observation
                states[jid] = (
                    stamped.get("status", "MALFORMED_RECORD")
                    if observation["status"] == "TRACKING_COMPATIBLE"
                    else "REFERENCE_UNRESOLVED"
                )
                save()
        receipt["status"] = (
            "INCOMPLETE_REFERENCE"
            if len(mappings) != len(selected)
            else (
                "RETURNED_RECORDS_ONLY"
                if all(status == "OK" for status in states.values())
                else "REFERENCE_UNRESOLVED"
            )
        )
        save()
        return 0 if receipt["status"] == "RETURNED_RECORDS_ONLY" else 2
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
        except Exception as error:  # noqa: BLE001 -- preserve original exception
            original_error.add_note(
                "EVAL receipt persistence failed: " + type(error).__name__
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
        raise tasks.TaskError("Root-pinned EVAL invocation bytes required")
    root = args.public_root.resolve(strict=True)

    def load(name):
        return _public_load(root, name)

    return run(
        json.loads(raw), load=load, records_path=args.records, workers=args.workers
    )


if __name__ == "__main__":
    raise SystemExit(main())
