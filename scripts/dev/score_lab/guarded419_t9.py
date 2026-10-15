"""Separately admitted PUBLIC_DEVELOPMENT T9, never an automatic next stage.

Root authenticates G0, exact source/delivery and resource reservation. This
adapter reuses the existing worker; it owns no provider, retries or model fit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from carbon.design_search import tasks
from scripts.dev.battery import guarded_reference as guard
from scripts.dev.score_lab import owner_v3_panel_export as producer

MODULE = "scripts/dev/score_lab/guarded419_t9.py"
ADMISSION = "carbon.scorelab.guarded419.t9-admission.v1"
SCHEMA = "carbon.scorelab.guarded419.t9-execution.v1"
DELIVERY = "carbon.scorelab.guarded419.t9-delivery.v1"
DATASET = "carbon.scorelab.battery-v3.guarded419-train9.v1"
OBSERVER = "carbon.scorelab.battery-v3.guarded419-train9-observer.v1"
RECORD = "carbon.battery.guarded419-t9-feasibility-record.v1"
INPUT_SHA = "a6c4c38ba17b0a8b27a36bfed055f85f924a7fc4bfdee0e2cb24065adfbd3cf3"
PLAN_SHA = "bfdfc92afa046a218b11ee1c52748cbdc9f144f12908a7f8a6453787d909eebf"
ANCHORS = (
    (1, 0.43, 0.31, 4.10, 1.0, 17.0),
    (2, 1.05, 0.54, 4.05, 2.0, 5.5),
    (11, 1.06, 0.66, 4.00, 2.0, 23.5),
    (16, 1.20, 0.96, 4.15, 4.0, 37.0),
    (28, 1.63, 1.53, 4.00, 1.0, 5.0),
    (121, 1.98, 1.97, 4.00, 2.0, 34.0),
    (248, 0.25, 0.25, 4.05, 1.0, 16.5),
    (726, 1.08, 0.78, 4.05, 1.0, 40.0),
    (2002, 2.00, 1.58, 4.15, 1.0, 27.0),
)
REQUIRED_SOURCES = {*guard.REQUIRED_SOURCES, MODULE}
_TOKEN = object()


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _json_safe(value):
    """Nullable evidence projection only; original raw bytes remain retained."""
    if type(value) is float and not math.isfinite(value):
        return None
    if type(value) is dict:
        return {k: _json_safe(v) for k, v in value.items()}
    if type(value) is list:
        return [_json_safe(v) for v in value]
    return value


def observer():
    return {
        "id": OBSERVER,
        "protocol_id": guard.METHOD_ID,
        "method_digest": tasks.digest(guard.METHOD),
        "dataset_id": DATASET,
        "admission_id": ADMISSION,
        "cycles": 30,
        "soc0": 0.1,
        "initial_state": "FRESH",
        "role": "PUBLIC_CONSTRUCTION",
    }


def jobs():
    return [
        {
            "case_id": f"guard419:t9:source-index-{index:04d}:mesh20",
            "c1": c1,
            "c2": c2,
            "switch_voltage_v": switch,
            "h_multiplier": h,
            "t_amb_c": t,
            "soc0": 0.1,
            "refined": False,
            "rung": 1,
            "reference_method": guard.METHOD_ID,
            "reference_method_digest": tasks.digest(guard.METHOD),
            "reference_admission": ADMISSION,
            "reference_dataset": DATASET,
            "reference_role": "PUBLIC_CONSTRUCTION",
            "parent_input_index": index,
        }
        for index, c1, c2, switch, h, t in ANCHORS
    ]


def validate_job(job):
    if type(job) is not dict or not any(
        tasks.digest(job) == tasks.digest(j) for j in jobs()
    ):
        raise tasks.TaskError("exact separately registered T9 anchor required")


def tracking_report(record):
    cid = record.get("case_id") if type(record) is dict else None
    expected = next((j for j in jobs() if j["case_id"] == cid), jobs()[0])
    return guard._tracking_report(
        record,
        expected_job=expected,
        reference_identity=observer(),
        record_schema=RECORD,
        method_digest=tasks.digest(guard.METHOD),
    )


def execution_binding(
    *, source_commit, source_files, g0, dispatch_id, scope="PUBLIC_DEVELOPMENT"
):
    if scope not in ("PUBLIC_DEVELOPMENT", "SYNTHETIC_FIXTURE"):
        raise tasks.TaskError("bounded T9 scope required")
    if not isinstance(source_commit, str) or not re.fullmatch(
        r"[0-9a-f]{40}", source_commit
    ):
        raise tasks.TaskError("exact T9 source commit required")
    if (
        type(source_files) is not dict
        or set(source_files) != REQUIRED_SOURCES
        or any(
            type(v) is not str or not re.fullmatch(r"[0-9a-f]{64}", v)
            for v in source_files.values()
        )
    ):
        raise tasks.TaskError("complete T9 source hashes required")
    producer._fields(
        g0, ("binding_sha256", "records_sha256", "receipt_sha256"), "G0 prerequisite"
    )
    if any(
        type(v) is not str or not re.fullmatch(r"[0-9a-f]{64}", v) for v in g0.values()
    ):
        raise tasks.TaskError("independent G0 raw hashes required")
    if type(dispatch_id) is not str or not dispatch_id.strip():
        raise tasks.TaskError("Root must bind explicit T9 dispatch identity")
    return {
        "schema": SCHEMA,
        "scope": scope,
        "execution_source": source_commit,
        "source_files": dict(source_files),
        "protocol_id": guard.METHOD_ID,
        "method_digest": tasks.digest(guard.METHOD),
        "observer": observer(),
        "dataset_id": DATASET,
        "input_manifest_sha256": INPUT_SHA,
        "research_plan_sha256": PLAN_SHA,
        "jobs": jobs(),
        "g0": dict(g0),
        "dispatch": {
            "owner": "Root",
            "id": dispatch_id,
            "max_workers": 2,
            "max_minutes": 45,
            "max_usd": 2,
            "automatic_next_stage": False,
        },
    }


def _binding(binding, expected):
    if tasks.digest(binding) != expected:
        raise tasks.TaskError("T9 binding differs from independent pin")
    rebuilt = execution_binding(
        source_commit=binding["execution_source"],
        source_files=binding["source_files"],
        g0=binding["g0"],
        dispatch_id=binding["dispatch"]["id"],
        scope=binding["scope"],
    )
    if tasks.digest(binding) != tasks.digest(rebuilt):
        raise tasks.TaskError("closed exact T9 admission required")


def _g0(binding, raw_binding, raw_records, raw_receipt):
    for name, raw in (
        ("binding", raw_binding),
        ("records", raw_records),
        ("receipt", raw_receipt),
    ):
        if _sha(raw) != binding["g0"][name + "_sha256"]:
            raise tasks.TaskError("G0 prerequisite bytes differ")
    prior, receipt = json.loads(raw_binding), json.loads(raw_receipt)
    expected = guard.execution_binding(
        source_commit=prior["execution_source"], source_files=prior["source_files"]
    )
    if tasks.digest(prior) != tasks.digest(expected):
        raise tasks.TaskError("exact original G0 binding required")
    # Only the explicitly assigned worker/tracking extension may differ. Root
    # independently pins both source inventories; no old source is relabelled.
    for path in guard.REQUIRED_SOURCES - {
        "scripts/dev/battery/feasibility02.py",
        guard.MODULE,
    }:
        if prior["source_files"][path] != binding["source_files"][path]:
            raise tasks.TaskError("G0 scientific dependency changed")
    rows = [json.loads(line) for line in raw_records.splitlines() if line.strip()]
    offered = guard.first_jobs()
    if len(rows) != 3 or {r.get("case_id") for r in rows if type(r) is dict} != {
        j["case_id"] for j in offered
    }:
        raise tasks.TaskError("actual complete original G0 triple required")
    if binding["scope"] == "PUBLIC_DEVELOPMENT" and any(r.get("fixture") for r in rows):
        raise tasks.TaskError("fixture G0 cannot admit public acquisition")
    report = guard.calibration_report(prior, rows)
    if report["status"] != "COMPATIBLE_FOR_REGISTERED_CALIBRATION_CASES":
        raise tasks.TaskError("G0 failed or unresolved; no T9 dispatch")
    required = {
        "schema": "carbon.scorelab.guarded419-calibration-execution-receipt.v1",
        "scope": "PUBLIC_DEVELOPMENT",
        "binding_sha256": _sha(raw_binding),
        "execution_source": prior["execution_source"],
        "source_files": prior["source_files"],
        "observer": prior["observer"],
        "plan_digest": prior["plan_digest"],
        "offered_jobs_digest": tasks.digest(offered),
        "per_job": {j["case_id"]: "OK" for j in offered},
        "per_completed_triple": [report],
        "status": "COMPATIBLE_GUARDED_FIRST_TRIPLE_ONLY",
        "full_calibration_release": False,
        "qualification": False,
        "records_sha256": _sha(raw_records),
        "calibration": report,
    }
    if receipt != required:
        raise tasks.TaskError("G0 receipt disagrees with authenticated raw reduction")
    return tasks.digest(receipt)


@dataclass(frozen=True, slots=True, init=False)
class ValidatedT9Evidence:
    """Internal nominal provenance, not a hostile-Python security boundary."""

    _snapshot: bytes

    def __init__(self, snapshot, *, _token=None):
        if _token is not _TOKEN:
            raise tasks.TaskError("use authenticated T9 delivery validation")
        object.__setattr__(self, "_snapshot", snapshot)


def validate_delivery(
    binding,
    manifest,
    raw_chunks,
    *,
    expected_binding_digest,
    expected_manifest_digest,
    g0_binding,
    g0_raw,
    g0_receipt,
):
    """Authenticate every offered input and raw line before issuing evidence."""
    _binding(binding, expected_binding_digest)
    g0_digest = _g0(binding, g0_binding, g0_raw, g0_receipt)
    if tasks.digest(manifest) != expected_manifest_digest:
        raise tasks.TaskError("T9 manifest differs from independent pin")
    producer._fields(
        manifest,
        ("schema", "scope", "binding_digest", "offered_job_ids", "chunks"),
        "T9 manifest",
    )
    offered = {j["case_id"]: j for j in jobs()}
    if (
        manifest["schema"] != DELIVERY
        or manifest["scope"] != binding["scope"]
        or manifest["binding_digest"] != expected_binding_digest
        or manifest["offered_job_ids"] != list(offered)
    ):
        raise tasks.TaskError("exact offered T9 source order and scope required")
    records, proof, tracking, states, chunk_ids = {}, {}, {}, {}, set()
    for chunk in manifest["chunks"]:
        producer._fields(
            chunk, ("id", "sha256", "source_commit", "source_files", "rows"), "T9 chunk"
        )
        name = chunk["id"]
        if type(name) is not str or name in chunk_ids or name not in raw_chunks:
            raise tasks.TaskError("unique supplied T9 chunk required")
        chunk_ids.add(name)
        raw = raw_chunks[name]
        if (
            type(raw) is not bytes
            or _sha(raw) != chunk["sha256"]
            or chunk["source_commit"] != binding["execution_source"]
            or chunk["source_files"] != binding["source_files"]
        ):
            raise tasks.TaskError("T9 raw/source identity differs")
        lines = raw.splitlines()
        mapped = set()
        for mapping in chunk["rows"]:
            producer._fields(mapping, ("line", "job_id"), "T9 row mapping")
            line, jid = mapping["line"], mapping["job_id"]
            if (
                type(line) is not int
                or not 1 <= line <= len(lines)
                or line in mapped
                or jid not in offered
                or jid in records
            ):
                raise tasks.TaskError("unique offered T9 line required")
            mapped.add(line)
            row = json.loads(lines[line - 1])
            if type(row) is not dict or any(
                row.get(k) != v for k, v in offered[jid].items()
            ):
                raise tasks.TaskError("raw T9 anchor identity differs")
            if tasks.digest({k: row[k] for k in offered[jid]}) != tasks.digest(
                offered[jid]
            ):
                raise tasks.TaskError("T9 raw job types differ")
            if binding["scope"] == "PUBLIC_DEVELOPMENT" and row.get("fixture"):
                raise tasks.TaskError("fixture row cannot be public T9 evidence")
            if row.get("schema") != RECORD or tasks.digest(
                row.get("reference_identity")
            ) != tasks.digest(observer()):
                raise tasks.TaskError("foreign T9 record schema or observer context")
            records[jid] = _json_safe(row)
            tracking[jid] = tracking_report(row)
            extraction = producer._extract(row)
            states[jid] = {
                "raw_status": row.get("status"),
                "tracking_status": tracking[jid]["status"],
                "extraction_state": extraction["state"],
            }
            proof[jid] = {
                "chunk_id": name,
                "line": line,
                "raw_sha256": _sha(raw),
                "source_commit": chunk["source_commit"],
                "source_files": chunk["source_files"],
            }
        if mapped != {i for i, l in enumerate(lines, 1) if l.strip()}:
            raise tasks.TaskError("unmapped T9 raw rows forbidden")
    if set(raw_chunks) != chunk_ids:
        raise tasks.TaskError("unregistered T9 raw chunks forbidden")
    for jid in offered:
        states.setdefault(
            jid,
            {
                "raw_status": "MISSING",
                "tracking_status": "REFERENCE_UNRESOLVED",
                "extraction_state": "MISSING",
            },
        )
    snapshot = {
        "scope": binding["scope"],
        "binding_digest": expected_binding_digest,
        "manifest_digest": expected_manifest_digest,
        "protocol_id": guard.METHOD_ID,
        "method_digest": tasks.digest(guard.METHOD),
        "observer_id": OBSERVER,
        "dataset_id": DATASET,
        "source_commit": binding["execution_source"],
        "source_files": binding["source_files"],
        "g0_receipt_digest": g0_digest,
        "jobs": jobs(),
        "records": records,
        "source_rows": proof,
        "tracking": tracking,
        "per_job": states,
    }
    return ValidatedT9Evidence(
        json.dumps(snapshot, sort_keys=True, allow_nan=False).encode(), _token=_TOKEN
    )


def validate_for(evidence, *, expected_binding_digest, expected_manifest_digest, scope):
    if type(evidence) is not ValidatedT9Evidence:
        raise tasks.TaskError("validated nominal T9 evidence required")
    snapshot = json.loads(evidence._snapshot)
    if (
        snapshot["scope"] != scope
        or snapshot["binding_digest"] != expected_binding_digest
        or snapshot["manifest_digest"] != expected_manifest_digest
    ):
        raise tasks.TaskError("T9 consumer context differs")
    return snapshot


def delivery_manifest(binding, raw, mappings):
    return {
        "schema": DELIVERY,
        "scope": binding["scope"],
        "binding_digest": tasks.digest(binding),
        "offered_job_ids": [j["case_id"] for j in jobs()],
        "chunks": [
            {
                "id": "t9",
                "sha256": _sha(raw),
                "source_commit": binding["execution_source"],
                "source_files": binding["source_files"],
                "rows": mappings,
            }
        ],
    }


def run(
    binding,
    *,
    expected_binding_digest,
    g0_binding,
    g0_raw,
    g0_receipt,
    records_path,
    workers=2,
    root=None,
):
    """Root-dispatched existing worker, nine jobs only; no release or retries."""
    from carbon.battery import truth_env
    from scripts.dev.battery import feasibility02 as worker

    _binding(binding, expected_binding_digest)
    _g0(binding, g0_binding, g0_raw, g0_receipt)
    if (
        binding["scope"] != "PUBLIC_DEVELOPMENT"
        or type(workers) is not int
        or not 1 <= workers <= 2
    ):
        raise tasks.TaskError("Root public T9 dispatch with one/two workers required")
    root = worker.ROOT if root is None else Path(root)
    if any(
        _sha((root / p).read_bytes()) != sha
        for p, sha in binding["source_files"].items()
    ):
        raise tasks.TaskError("shipped T9 source bytes differ")
    provenance = truth_env.provenance(".")
    expected = json.loads(g0_binding)["plan"]
    if (
        provenance.get("schema") != "carbon.battery.solver-provenance.v1"
        or provenance.get("solver_image", "").split("@")[-1] != expected["image_digest"]
        or provenance.get("overlay_lock_sha256")
        != "sha256:" + expected["overlay_sha256"]
        or provenance.get("overlay_lock")
        != "scripts/dev/exam_design/locks/battery-overlay.lock.json"
        or provenance.get("pybamm") != "26.8.0.0"
    ):
        raise tasks.TaskError("T9 runtime differs")
    output = Path(records_path)
    receipt_path = output.with_name(output.name + ".t9.json")
    temp = receipt_path.with_name(receipt_path.name + ".tmp")
    if any(os.path.lexists(p) for p in (output, receipt_path, temp)):
        raise tasks.TaskError("T9 requires fresh output paths")
    states = {j["case_id"]: "NOT_DISPATCHED" for j in jobs()}
    mappings = []
    receipt = {
        "schema": "carbon.scorelab.guarded419.t9-execution-receipt.v1",
        "status": "INCOMPLETE_REFERENCE",
        "binding_digest": expected_binding_digest,
        "per_job": states,
        "full_calibration_release": False,
        "evaluation_release": False,
        "n1_release": False,
        "qualification": False,
    }

    def save():
        raw = output.read_bytes()
        manifest = delivery_manifest(binding, raw, mappings)
        receipt.update(
            records_sha256=_sha(raw),
            manifest=manifest,
            manifest_digest=tasks.digest(manifest),
        )
        try:
            evidence = validate_delivery(
                binding,
                manifest,
                {"t9": raw},
                expected_binding_digest=expected_binding_digest,
                expected_manifest_digest=tasks.digest(manifest),
                g0_binding=g0_binding,
                g0_raw=g0_raw,
                g0_receipt=g0_receipt,
            )
            receipt["evidence"] = validate_for(
                evidence,
                expected_binding_digest=expected_binding_digest,
                expected_manifest_digest=tasks.digest(manifest),
                scope=binding["scope"],
            )
        except (ValueError, TypeError, KeyError, tasks.TaskError):
            receipt["status"] = "INVALID_DELIVERY"
            receipt.pop("evidence", None)
        with temp.open("x", encoding="utf-8") as handle:
            handle.write(json.dumps(receipt, sort_keys=True, allow_nan=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        temp.replace(receipt_path)

    with output.open("x", encoding="utf-8"):
        pass
    save()
    try:
        with ProcessPoolExecutor(workers) as pool:
            futures = {}
            for job in jobs():
                future = pool.submit(worker._timed, job)
                futures[future] = job
                states[job["case_id"]] = "SUBMITTED"
                save()
            for future in as_completed(futures):
                job = futures[future]
                try:
                    row = future.result()
                except Exception as exc:  # noqa: BLE001
                    row = {
                        **job,
                        "schema": RECORD,
                        "reference_identity": observer(),
                        "status": "FAILED_INFRA",
                        "error_type": type(exc).__name__,
                    }
                if type(row) is not dict:
                    row = {
                        **job,
                        "schema": RECORD,
                        "reference_identity": observer(),
                        "status": "MALFORMED_RECORD",
                        "raw_return_type": type(row).__name__,
                    }
                row = truth_env.stamp(row, provenance)
                with output.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(row, sort_keys=True) + "\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                mappings.append({"line": len(mappings) + 1, "job_id": job["case_id"]})
                states[job["case_id"]] = row.get("status", "MALFORMED_RECORD")
                save()
    except BaseException:
        receipt["status"] = "INTERRUPTED_OR_INVALID_REFERENCE"
        save()
        raise
    if receipt["status"] != "INVALID_DELIVERY":
        receipt["status"] = "T9_CAPTURED_NOT_TRAIN_QUALIFIED"
    save()
    return 0 if receipt["status"] == "T9_CAPTURED_NOT_TRAIN_QUALIFIED" else 2


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("binding", "g0-binding", "g0-records", "g0-receipt", "records"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--binding-sha256", required=True)
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args(argv)
    raw = args.binding.read_bytes()
    if _sha(raw) != args.binding_sha256:
        raise tasks.TaskError("independent Root binding byte pin required")
    binding = json.loads(raw)
    return run(
        binding,
        expected_binding_digest=tasks.digest(binding),
        g0_binding=args.g0_binding.read_bytes(),
        g0_raw=args.g0_records.read_bytes(),
        g0_receipt=args.g0_receipt.read_bytes(),
        records_path=args.records,
        workers=args.workers,
    )


if __name__ == "__main__":
    raise SystemExit(main())
