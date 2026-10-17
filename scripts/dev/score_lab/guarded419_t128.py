"""Frozen, role-preserving guarded419 T128 admission; no provider or model fit.

The first nine raw records retain their T9 identity. Only the remaining119
receive new T128 jobs. This is an internal nominal provenance boundary, not
security against arbitrary code in this Python process or a dispatch grant.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

from carbon.design_search import tasks
from scripts.dev.battery import guarded_reference as guard
from scripts.dev.score_lab import guarded419_t9 as t9
from scripts.dev.score_lab import owner_v3_panel_export as producer

MODULE = "scripts/dev/score_lab/guarded419_t128.py"
INPUT_FILE = "docs/development/challenge_pipeline/solver-readiness/guarded419-stage128-inputs.v1.json"
INPUT_FILE_SHA = "1b2dec89635a776536835921418ef148d28ccc77fcf3a6b280c383a286cff33c"
ROWS_DIGEST = "sha256:d66f664a4b2d9eba0439351c513a3dd9f4287e4e5897c8df87f651aeea043bb8"
CAL_MODULE = "scripts/dev/score_lab/guarded419_calibration_continue.py"
ADMISSION = "carbon.scorelab.guarded419.t128-admission.v1"
SCHEMA = "carbon.scorelab.guarded419.t128-execution.v1"
DELIVERY = "carbon.scorelab.guarded419.t128-delivery.v1"
DATASET = "carbon.scorelab.battery-v3.guarded419-stage128.v1"
OBSERVER = "carbon.scorelab.battery-v3.guarded419-stage128-observer.v1"
RECORD = "carbon.battery.guarded419-t128-feasibility-record.v1"
CONSTRUCTION = "PUBLIC_CONSTRUCTION"
VALIDATION = "INTERNAL_TRAIN_VALIDATION"
REQUIRED_SOURCES = {*t9.REQUIRED_SOURCES, MODULE, INPUT_FILE, CAL_MODULE}
_TOKEN = object()


class CalibrationPrerequisiteUnavailable(tasks.TaskError):
    """Upstream authenticated CAL15 API is absent; no stage evidence issued."""


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def input_rows():
    """Read only the byte-pinned TRAIN-input projection, not labels or EVAL."""
    raw = (Path(__file__).resolve().parents[3] / INPUT_FILE).read_bytes()
    if _sha(raw) != INPUT_FILE_SHA:
        raise tasks.TaskError("frozen128 input bytes differ")
    document = json.loads(raw)
    rows = document["rows"]
    if (
        document["original_manifest_sha256"] != t9.INPUT_SHA
        or document["research_plan_sha256"] != t9.PLAN_SHA
        or tasks.digest(rows) != ROWS_DIGEST
        or len(rows) != 128
    ):
        raise tasks.TaskError("frozen128 input identity differs")
    return rows


def observer(role):
    if role not in (CONSTRUCTION, VALIDATION):
        raise tasks.TaskError("literal frozen construction/validation role required")
    return {
        "id": OBSERVER,
        "protocol_id": guard.METHOD_ID,
        "method_digest": tasks.digest(guard.METHOD),
        "dataset_id": DATASET,
        "admission_id": ADMISSION,
        "cycles": 30,
        "soc0": 0.1,
        "initial_state": "FRESH",
        "role": role,
    }


def jobs():
    return [
        {
            "case_id": row["proposed_identity"] + ":mesh20",
            **row["inputs"],
            "refined": False,
            "rung": 1,
            "reference_method": guard.METHOD_ID,
            "reference_method_digest": tasks.digest(guard.METHOD),
            "reference_admission": ADMISSION,
            "reference_dataset": DATASET,
            "reference_role": row["stage128_role"],
            "parent_input_index": row["source_plan_index_0_based"],
        }
        for row in input_rows()
    ]


def partition_jobs(partition):
    if type(partition) is not int or partition not in (1, 2):
        raise tasks.TaskError("existing60/59 partition required")
    return jobs()[9:69] if partition == 1 else jobs()[69:]


def validate_job(job):
    # Anchors are evidence reuse only, never another acquisition offer.
    if type(job) is not dict or not any(
        tasks.digest(job) == tasks.digest(j) for j in jobs()[9:]
    ):
        raise tasks.TaskError("exact nonanchor T128 job required")


def tracking_report(record):
    cid = record.get("case_id") if type(record) is dict else None
    job = next((j for j in jobs()[9:] if j["case_id"] == cid), None)
    if job is None:
        raise tasks.TaskError("registered T128 record required")
    return guard._tracking_report(
        record,
        expected_job=job,
        reference_identity=observer(job["reference_role"]),
        record_schema=RECORD,
        method_digest=tasks.digest(guard.METHOD),
    )


def _digest(value):
    if type(value) is not str or not re.fullmatch(r"sha256:[0-9a-f]{64}", value):
        raise tasks.TaskError("independent prerequisite digest required")


def execution_binding(
    *,
    source_commit,
    source_files,
    prerequisites,
    dispatch_id,
    scope="PUBLIC_DEVELOPMENT",
):
    if scope not in ("PUBLIC_DEVELOPMENT", "SYNTHETIC_FIXTURE"):
        raise tasks.TaskError("bounded T128 scope required")
    if type(source_commit) is not str or not re.fullmatch(
        r"[0-9a-f]{40}", source_commit
    ):
        raise tasks.TaskError("exact T128 source commit required")
    if (
        type(source_files) is not dict
        or set(source_files) != REQUIRED_SOURCES
        or any(
            type(v) is not str or not re.fullmatch(r"[0-9a-f]{64}", v)
            for v in source_files.values()
        )
        or source_files[INPUT_FILE] != INPUT_FILE_SHA
    ):
        raise tasks.TaskError("complete T128 source and input-file pins required")
    producer._fields(prerequisites, ("t9", "cal15"), "T128 prerequisites")
    for name in ("t9", "cal15"):
        producer._fields(
            prerequisites[name], ("binding_digest", "manifest_digest"), name
        )
        for pin in prerequisites[name].values():
            _digest(pin)
    if type(dispatch_id) is not str or not dispatch_id.strip():
        raise tasks.TaskError("explicit Root T128 stage identity required")
    return {
        "schema": SCHEMA,
        "scope": scope,
        "execution_source": source_commit,
        "source_files": dict(source_files),
        "protocol_id": guard.METHOD_ID,
        "method_digest": tasks.digest(guard.METHOD),
        "dataset_id": DATASET,
        "observers": {role: observer(role) for role in (CONSTRUCTION, VALIDATION)},
        "input_rows_digest": ROWS_DIGEST,
        "input_manifest_sha256": t9.INPUT_SHA,
        "research_plan_sha256": t9.PLAN_SHA,
        "jobs": jobs(),
        "prerequisites": json.loads(json.dumps(prerequisites)),
        "dispatch": {
            "owner": "Root",
            "id": dispatch_id,
            "max_workers": 2,
            "partitions": [60, 59],
            "max_minutes_each": 90,
            "max_usd_each": 2,
            "stage_aggregate_max_usd": 4,
            "automatic_next_stage": False,
            "probe_fit_and_resource_release": "ROOT_SEPARATE_ACTUAL_BINDING_REQUIRED",
        },
    }


def _binding(binding, expected):
    if tasks.digest(binding) != expected:
        raise tasks.TaskError("T128 binding differs from independent pin")
    rebuilt = execution_binding(
        source_commit=binding["execution_source"],
        source_files=binding["source_files"],
        prerequisites=binding["prerequisites"],
        dispatch_id=binding["dispatch"]["id"],
        scope=binding["scope"],
    )
    if tasks.digest(binding) != tasks.digest(rebuilt):
        raise tasks.TaskError("closed exact T128 admission required")


def _prerequisites(binding, t9_delivery, calibration_evidence):
    pins = binding["prerequisites"]
    if (
        t9_delivery["expected_binding_digest"] != pins["t9"]["binding_digest"]
        or t9_delivery["expected_manifest_digest"] != pins["t9"]["manifest_digest"]
    ):
        raise tasks.TaskError("T9 prerequisite pins differ")
    prior = t9.validate_for(
        t9.validate_delivery(**t9_delivery),
        expected_binding_digest=pins["t9"]["binding_digest"],
        expected_manifest_digest=pins["t9"]["manifest_digest"],
        scope=binding["scope"],
    )
    # Never accept a plain mapping/PASS while the owner's CAL route is absent.
    try:
        from scripts.dev.score_lab import guarded419_calibration_continue as cal
    except ImportError as exc:
        raise CalibrationPrerequisiteUnavailable(
            "authenticated CAL15 adapter is not integrated"
        ) from exc
    if not hasattr(cal, "validate_for"):
        raise CalibrationPrerequisiteUnavailable(
            "CAL15 nominal evidence interface is not integrated"
        )
    calibration = cal.validate_for(
        calibration_evidence,
        expected_binding_digest=pins["cal15"]["binding_digest"],
        expected_manifest_digest=pins["cal15"]["manifest_digest"],
        scope=binding["scope"],
    )
    if (
        calibration["protocol_id"] != guard.METHOD_ID
        or calibration["method_digest"] != tasks.digest(guard.METHOD)
        or calibration["status"] != "COMPATIBLE_FOR_REGISTERED_CALIBRATION_CASES"
        or calibration["expected_case_count"] != 15
    ):
        raise tasks.TaskError("complete authenticated compatible CAL15 required")
    # Worker/admission code may evolve prospectively; physics dependencies may not.
    exceptions = {"scripts/dev/battery/feasibility02.py", guard.MODULE}
    for snapshot in (prior, calibration):
        for path in guard.REQUIRED_SOURCES - exceptions:
            if snapshot["source_files"][path] != binding["source_files"][path]:
                raise tasks.TaskError("prerequisite scientific source differs")
    return prior, calibration


@dataclass(frozen=True, slots=True, init=False)
class ValidatedT128Evidence:
    """Immutable internal evidence; no hostile-Python attestation claim."""

    _snapshot: bytes

    def __init__(self, snapshot, *, _token=None):
        if _token is not _TOKEN:
            raise tasks.TaskError("use authenticated T128 delivery validation")
        object.__setattr__(self, "_snapshot", snapshot)


def _new_delivery(
    binding, manifest, raw_chunks, *, expected_binding_digest, expected_manifest_digest
):
    """Authenticate raw119 delivery only; cannot mint prerequisite-qualified evidence."""
    _binding(binding, expected_binding_digest)
    if tasks.digest(manifest) != expected_manifest_digest:
        raise tasks.TaskError("T128 manifest differs from independent pin")
    producer._fields(
        manifest,
        ("schema", "scope", "binding_digest", "offered_job_ids", "chunks"),
        "T128 manifest",
    )
    offered = {j["case_id"]: j for j in jobs()}
    if (
        manifest["schema"] != DELIVERY
        or manifest["scope"] != binding["scope"]
        or manifest["binding_digest"] != expected_binding_digest
        or manifest["offered_job_ids"] != list(offered)
    ):
        raise tasks.TaskError("exact128 offered order/scope required")
    records, proof, tracking, states = {}, {}, {}, {}
    new_offers = {j["case_id"]: j for j in jobs()[9:]}
    chunk_ids = set()
    for chunk in manifest["chunks"]:
        producer._fields(
            chunk,
            ("id", "sha256", "source_commit", "source_files", "rows"),
            "T128 chunk",
        )
        name = chunk["id"]
        if type(name) is not str or name in chunk_ids or name not in raw_chunks:
            raise tasks.TaskError("unique supplied T128 chunk required")
        chunk_ids.add(name)
        raw = raw_chunks[name]
        if (
            type(raw) is not bytes
            or _sha(raw) != chunk["sha256"]
            or chunk["source_commit"] != binding["execution_source"]
            or chunk["source_files"] != binding["source_files"]
        ):
            raise tasks.TaskError("T128 raw/source identity differs")
        lines, mapped = raw.splitlines(), set()
        for mapping in chunk["rows"]:
            producer._fields(mapping, ("line", "job_id"), "T128 line mapping")
            line, jid = mapping["line"], mapping["job_id"]
            if (
                type(line) is not int
                or not 1 <= line <= len(lines)
                or line in mapped
                or jid not in new_offers
                or jid in records
            ):
                raise tasks.TaskError("unique offered nonanchor T128 row required")
            mapped.add(line)
            row = json.loads(lines[line - 1])
            job = new_offers[jid]
            if (
                type(row) is not dict
                or any(k not in row for k in job)
                or tasks.digest({k: row[k] for k in job}) != tasks.digest(job)
            ):
                raise tasks.TaskError("T128 job input/type/role differs")
            if binding["scope"] == "PUBLIC_DEVELOPMENT" and row.get("fixture"):
                raise tasks.TaskError("fixture cannot become public T128 evidence")
            if row.get("schema") != RECORD or tasks.digest(
                row.get("reference_identity")
            ) != tasks.digest(observer(job["reference_role"])):
                raise tasks.TaskError("foreign T128 schema/observer/role")
            tracking[jid] = tracking_report(row)
            extraction = producer._extract(row)
            records[jid] = t9._json_safe(row)  # Raw proof remains over original bytes.
            states[jid] = {
                "raw_status": row.get("status"),
                "tracking_status": tracking[jid]["status"],
                "extraction_state": extraction["state"],
            }
            proof[jid] = {
                "kind": "NEW_T128",
                "chunk_id": name,
                "line": line,
                "raw_sha256": _sha(raw),
                "source_commit": chunk["source_commit"],
                "source_files": chunk["source_files"],
                "original_job_id": jid,
                "parent_input_index": job["parent_input_index"],
                "binding_digest": expected_binding_digest,
                "manifest_digest": expected_manifest_digest,
            }
        if mapped != {i for i, l in enumerate(lines, 1) if l.strip()}:
            raise tasks.TaskError("unmapped T128 raw rows forbidden")
    if set(raw_chunks) != chunk_ids:
        raise tasks.TaskError("unregistered T128 raw chunks forbidden")
    for jid in offered:
        states.setdefault(
            jid,
            {
                "raw_status": "MISSING",
                "tracking_status": "REFERENCE_UNRESOLVED",
                "extraction_state": "MISSING",
            },
        )
    return records, proof, tracking, states


def validate_delivery(
    binding,
    manifest,
    raw_chunks,
    *,
    expected_binding_digest,
    expected_manifest_digest,
    t9_delivery,
    calibration_evidence,
):
    """Authenticate9 reused rows and all119 new offers without rewriting raw."""
    records, proof, tracking, states = _new_delivery(
        binding,
        manifest,
        raw_chunks,
        expected_binding_digest=expected_binding_digest,
        expected_manifest_digest=expected_manifest_digest,
    )
    prior, calibration = _prerequisites(binding, t9_delivery, calibration_evidence)
    offered = {j["case_id"]: j for j in jobs()}
    for job, original in zip(jobs()[:9], t9.jobs(), strict=True):
        jid, old_id = job["case_id"], original["case_id"]
        if job["parent_input_index"] != original["parent_input_index"] or any(
            job[k] != original[k] for k in input_rows()[0]["inputs"]
        ):
            raise tasks.TaskError("frozen T9 anchor reuse mapping differs")
        raw = prior["records"].get(old_id)
        if raw is not None:
            records[jid] = raw  # Original schema, IDs and context stay untouched.
            proof[jid] = {
                **prior["source_rows"][old_id],
                "kind": "AUTHENTICATED_T9_REUSE",
                "original_job_id": old_id,
                "parent_input_index": job["parent_input_index"],
                "binding_digest": prior["binding_digest"],
                "manifest_digest": prior["manifest_digest"],
            }
        if old_id in prior["tracking"]:
            tracking[jid] = prior["tracking"][old_id]
        states[jid] = dict(prior["per_job"][old_id])
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
        "g0_receipt_digest": prior["g0_receipt_digest"],
        "prerequisite_digests": binding["prerequisites"],
        "prerequisite_sources": {
            "t9": prior["source_files"],
            "cal15": calibration["source_files"],
        },
        "jobs": jobs(),
        "roles_by_job_id": {jid: j["reference_role"] for jid, j in offered.items()},
        "records": records,
        "source_rows": proof,
        "tracking": tracking,
        "per_job": states,
    }
    return ValidatedT128Evidence(
        json.dumps(snapshot, sort_keys=True, allow_nan=False).encode(), _token=_TOKEN
    )


def validate_for(evidence, *, expected_binding_digest, expected_manifest_digest, scope):
    if type(evidence) is not ValidatedT128Evidence:
        raise tasks.TaskError("validated nominal T128 evidence required")
    snapshot = json.loads(evidence._snapshot)
    if (
        snapshot["scope"] != scope
        or snapshot["binding_digest"] != expected_binding_digest
        or snapshot["manifest_digest"] != expected_manifest_digest
    ):
        raise tasks.TaskError("T128 consumer context differs")
    return snapshot


def delivery_manifest(binding, chunks):
    return {
        "schema": DELIVERY,
        "scope": binding["scope"],
        "binding_digest": tasks.digest(binding),
        "offered_job_ids": [j["case_id"] for j in jobs()],
        "chunks": chunks,
    }
