"""One source-pinned T15 mesh160 raw reference diagnostic worker.

Root owns pod_jobs resource admission, owner method review, at-use quote and
TEST lease. This worker has no provider access, retry or mesh320 continuation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

from carbon.design_search import tasks
from scripts.dev.battery import feasibility02
from scripts.dev.battery import guarded_reference as guard
from scripts.dev.score_lab import guarded419_t15_mesh160 as diagnostic

MODULE = "scripts/dev/score_lab/guarded419_t15_mesh160_worker.py"
SCHEMA = "carbon.scorelab.guarded419.t15-mesh160-worker-spec.v1"
RECEIPT = "carbon.scorelab.guarded419.t15-mesh160-worker-receipt.v1"
REQUIRED_SOURCES = {
    *guard.REQUIRED_SOURCES,
    "scripts/dev/battery/feasibility02.py",
    "carbon/battery/truth_env.py",
    "scripts/dev/score_lab/guarded419_t15_mesh160.py",
    MODULE,
}


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _hex(value, size):
    return type(value) is str and re.fullmatch(r"[0-9a-f]{" + str(size) + r"}", value)


def _job_echo_valid(row):
    try:
        return tasks.digest(
            {key: row.get(key) for key in diagnostic.job()}
        ) == tasks.digest(diagnostic.job())
    except (TypeError, ValueError, tasks.TaskError):
        return False


def _head(root):
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode or not _hex(result.stdout.strip(), 40):
        raise tasks.TaskError("actual mesh160 execution checkout unavailable")
    return result.stdout.strip()


def _source(spec, root, *, environ=os.environ):
    if not _hex(spec["execution_source"], 40):
        raise tasks.TaskError("exact mesh160 execution commit required")
    commit = spec["execution_source"]
    checkout = (root / ".git").exists()
    if checkout:
        if _head(root) != commit:
            raise tasks.TaskError("mesh160 execution checkout differs")
    elif environ.get("CODE_REF") != commit:
        raise tasks.TaskError("mesh160 pod bootstrap CODE_REF differs")
    for name, expected in spec["source_files"].items():
        path = root / name
        if (
            path.is_symlink()
            or any(
                parent.is_symlink()
                for parent in path.parents
                if parent != root and parent.is_relative_to(root)
            )
            or not path.is_file()
            or not path.resolve().is_relative_to(root.resolve())
            or _sha(path.read_bytes()) != expected
        ):
            raise tasks.TaskError("actual mesh160 source bytes differ: " + name)
        if checkout:
            committed = subprocess.run(
                ["git", "-C", str(root), "show", "HEAD:" + name],
                capture_output=True,
                check=False,
            )
            if committed.returncode or _sha(committed.stdout) != expected:
                raise tasks.TaskError("committed mesh160 source bytes differ: " + name)
    return (
        "GIT_CHECKOUT_AND_LOCAL_BYTES" if checkout else "POD_CODE_REF_AND_LOCAL_BYTES"
    )


def _spec(spec):
    if type(spec) is not dict or set(spec) != {
        "schema",
        "scope",
        "execution_source",
        "source_files",
        "job",
        "observer",
        "attempt_id",
    }:
        raise tasks.TaskError("closed mesh160 worker specification required")
    if spec["schema"] != SCHEMA or spec["scope"] != "PUBLIC_DEVELOPMENT":
        raise tasks.TaskError("mesh160 DEVELOPMENT diagnostic scope required")
    if (
        type(spec["source_files"]) is not dict
        or set(spec["source_files"]) != REQUIRED_SOURCES
        or not all(_hex(value, 64) for value in spec["source_files"].values())
    ):
        raise tasks.TaskError("complete mesh160 source byte pins required")
    diagnostic.validate_job(spec["job"])
    if tasks.digest(spec["observer"]) != tasks.digest(diagnostic.observer()):
        raise tasks.TaskError("exact mesh160 returned-entry observer required")
    if type(spec["attempt_id"]) is not str or not re.fullmatch(
        r"[a-z0-9][a-z0-9-]{0,79}", spec["attempt_id"]
    ):
        raise tasks.TaskError("one distinct Root attempt identity required")


def _provenance(root):
    from carbon.battery import truth_env

    actual = truth_env.provenance(root)
    if (
        actual.get("schema") != "carbon.battery.solver-provenance.v1"
        or actual.get("solver_image")
        != "ghcr.io/carbonphysicsai/carbon-determinism-study@" + guard.IMAGE
        or actual.get("overlay_lock")
        != "scripts/dev/exam_design/locks/battery-overlay.lock.json"
        or actual.get("overlay_lock_sha256")
        != "sha256:6267e033b30728b200d9e0c2aa6b55a9117cd67e03c6f89c9a17294d12e594ee"
        or actual.get("pybamm") != "26.8.0.0"
    ):
        raise tasks.TaskError("mesh160 truth runtime differs")
    return actual


def _save(path, receipt):
    temporary = path.with_name(path.name + ".tmp")
    raw = (json.dumps(receipt, sort_keys=True, allow_nan=False) + "\n").encode()
    with temporary.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def prepare_spec(*, root, attempt_id, out):
    """Make one exact source-bound input; performs no solver/provider action."""
    root = Path(root)
    files = {}
    for name in sorted(REQUIRED_SOURCES):
        path = root / name
        if (
            path.is_symlink()
            or any(
                parent.is_symlink()
                for parent in path.parents
                if parent != root and parent.is_relative_to(root)
            )
            or not path.is_file()
            or not path.resolve().is_relative_to(root.resolve())
        ):
            raise tasks.TaskError("ordinary mesh160 source file required")
        files[name] = _sha(path.read_bytes())
    spec = {
        "schema": SCHEMA,
        "scope": "PUBLIC_DEVELOPMENT",
        "execution_source": _head(root),
        "source_files": files,
        "job": diagnostic.job(),
        "observer": diagnostic.observer(),
        "attempt_id": attempt_id,
    }
    _spec(spec)
    _source(spec, root)
    raw = (json.dumps(spec, sort_keys=True, allow_nan=False) + "\n").encode()
    out = Path(out)
    if out.is_symlink() or any(parent.is_symlink() for parent in out.parents):
        raise tasks.TaskError("mesh160 input path alias refused")
    with out.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    return {"spec_path": str(out), "spec_sha256": _sha(raw)}


def run(spec, *, records_path, root=None, solve=feasibility02._timed, stamp=None):
    """No resume/retry; retain raw result even when tracking is unresolved."""
    _spec(spec)
    root = Path(root) if root is not None else Path(__file__).resolve().parents[3]
    source_basis = _source(spec, root)
    provenance = _provenance(root)
    if stamp is None:
        from carbon.battery import truth_env

        stamp = truth_env.stamp
    records = Path(records_path)
    receipt_path = records.with_name(records.name + ".mesh160.json")
    temporary = receipt_path.with_name(receipt_path.name + ".tmp")
    if any(os.path.lexists(path) for path in (records, receipt_path, temporary)) or any(
        parent.is_symlink() for parent in records.parents
    ):
        raise tasks.TaskError("mesh160 requires fresh non-symlink output and receipt")
    receipt = {
        "schema": RECEIPT,
        "scope": "PUBLIC_DEVELOPMENT",
        "attempt_id": spec["attempt_id"],
        "execution_source": spec["execution_source"],
        "source_files": spec["source_files"],
        "source_identity_basis": source_basis,
        "job": diagnostic.job(),
        "observer": diagnostic.observer(),
        "solver_provenance": provenance,
        "status": "INCOMPLETE_REFERENCE",
        "per_job": {diagnostic.CASE_ID: "NOT_DISPATCHED"},
        "raw_records_sha256": None,
        "raw_rows": [],
        "route_readout": None,
        "automatic_retry": False,
        "automatic_next_stage": False,
        "reference_verdict": False,
        "physical_certificate": False,
        "model_release": False,
        "score_release": False,
        "qualification": False,
    }
    _save(receipt_path, receipt)
    receipt["per_job"][diagnostic.CASE_ID] = "SUBMITTED"
    _save(receipt_path, receipt)
    try:
        row = solve(diagnostic.job())
    except Exception as exc:  # noqa: BLE001 -- worker failure is not physics
        receipt["per_job"][diagnostic.CASE_ID] = "FAILED_INFRA"
        receipt["status"] = "FAILED_INFRA_REFERENCE_UNRESOLVED"
        receipt["error_type"] = type(exc).__name__
        _save(receipt_path, receipt)
        return 2
    if (
        type(row) is not dict
        or row.get("case_id") != diagnostic.CASE_ID
        or row.get("schema") != diagnostic.RECORD
        or not _job_echo_valid(row)
    ):
        receipt["per_job"][diagnostic.CASE_ID] = "INVALID_REFERENCE"
        receipt["status"] = "REFERENCE_UNRESOLVED"
        _save(receipt_path, receipt)
        return 2
    stamped = stamp(row, provenance)
    raw = (json.dumps(stamped, sort_keys=True, allow_nan=True) + "\n").encode()
    with records.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        readout = diagnostic.route_readout(stamped)
    except Exception as exc:  # noqa: BLE001 -- raw bytes survive malformed reference
        readout = {
            "status": "REFERENCE_UNRESOLVED",
            "mesh320_route": "NOT_ADMITTED",
            "error_type": type(exc).__name__,
            "reference_verdict": False,
        }
    receipt["raw_records_sha256"] = _sha(raw)
    receipt["raw_rows"] = [{"line": 1, "job_id": diagnostic.CASE_ID}]
    receipt["route_readout"] = readout
    receipt["status"] = readout["status"]
    receipt["per_job"][diagnostic.CASE_ID] = (
        "OK_NONVERDICT"
        if readout["status"] == "RETURNED_NONVERDICT_DIAGNOSTIC"
        else "REFERENCE_UNRESOLVED"
    )
    _save(receipt_path, receipt)
    return 0 if readout["status"] == "RETURNED_NONVERDICT_DIAGNOSTIC" else 2


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "run"))
    parser.add_argument("--spec", type=Path)
    parser.add_argument("--spec-sha256")
    parser.add_argument("--records", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--attempt-id")
    args = parser.parse_args(argv)
    if args.command == "prepare":
        if (
            args.out is None
            or args.attempt_id is None
            or any(
                value is not None
                for value in (args.spec, args.spec_sha256, args.records)
            )
        ):
            parser.error("prepare requires only --out and --attempt-id")
        print(
            json.dumps(
                prepare_spec(
                    root=Path(__file__).resolve().parents[3],
                    attempt_id=args.attempt_id,
                    out=args.out,
                ),
                sort_keys=True,
            )
        )
        return 0
    if (
        args.spec is None
        or args.spec_sha256 is None
        or args.records is None
        or any(value is not None for value in (args.out, args.attempt_id))
    ):
        parser.error("run requires only --spec, --spec-sha256 and --records")
    raw = args.spec.read_bytes()
    if not _hex(args.spec_sha256, 64) or _sha(raw) != args.spec_sha256:
        raise tasks.TaskError("independently pinned mesh160 spec bytes required")
    return run(json.loads(raw), records_path=args.records)


if __name__ == "__main__":
    raise SystemExit(main())
