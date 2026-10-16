"""Bounded guarded419 CAL continuation and authenticated fifteen-triple evidence.

Root owns source/resource admission and each separate dispatch. This module
reuses the existing collector, extraction and numerical/operative guards;
it never fits a model, reads EVAL truth or grants qualification.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath

from carbon.design_search import tasks
from scripts.dev.battery import guarded_reference as guard
from scripts.dev.score_lab import guarded419_t9 as t9
from scripts.dev.score_lab import owner_v3_calibration_continue as collector
from scripts.dev.score_lab import owner_v3_numerics as numerics
from scripts.dev.score_lab import owner_v3_panel_export as producer

MODULE = "scripts/dev/score_lab/guarded419_calibration_continue.py"
COLLECTOR = "scripts/dev/score_lab/owner_v3_calibration_continue.py"
TRAIN_MODULE = "scripts/dev/score_lab/guarded419_train.py"
ARM_MODULE = "carbon/development_comparison/carbon_arm.py"
ADMISSION = "carbon.scorelab.guarded419.cal15-admission.v1"
RECORD = "carbon.battery.guarded419-cal15-feasibility-record.v1"
OBSERVER = "carbon.scorelab.battery-v3.guarded419-cal15-observer.v1"
DATASET = "carbon.scorelab.battery-v3.guarded419-cal15.v1"
SCHEMA = "carbon.scorelab.guarded419.cal15-execution.v1"
DELIVERY = "carbon.scorelab.guarded419.cal15-delivery.v1"
FILE_SPEC = "carbon.scorelab.guarded419.cal15-files.v1"
COMPATIBLE = "COMPATIBLE_FOR_REGISTERED_CALIBRATION_CASES"
REQUIRED_SOURCES = {*t9.REQUIRED_SOURCES, MODULE, COLLECTOR, TRAIN_MODULE, ARM_MODULE}
SEGMENTS = {"pilot-2": (1, 3), "pilot-3": (3, 6), "rest-4": (6, 10), "rest-5": (10, 15)}
PROBE_FILES = ("construction", "inputs", "support", "fit", "predictions", "outcome")
_TOKEN = object()


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _hex(value, size=64):
    if type(value) is not str or not re.fullmatch(
        r"[0-9a-f]{" + str(size) + "}", value
    ):
        raise tasks.TaskError("independent exact content/source hash required")
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
        "role": "PUBLIC_CALIBRATION",
    }


def groups():
    """Original frozen input order; original G0 identities are reused verbatim."""
    result = [guard.first_jobs()]
    coordinates = [(t, h) for t in (5, 15, 25, 35, 40) for h in (1, 2, 4)]
    pilot = {(5, 1), (15, 1), (25, 1), (35, 1), (40, 1), (40, 4)}
    # Preserve original pilot/rest dispatch order and ORIGINAL grid indices.
    ordered = [(i, pair) for i, pair in enumerate(coordinates) if pair in pilot]
    ordered += [(i, pair) for i, pair in enumerate(coordinates) if pair not in pilot]
    for index, (ambient, cooling) in ordered:
        if index == 0:
            continue
        result.append(
            [
                {
                    "case_id": f"guard419:cal:source-index-{index:04d}:mesh{mesh}",
                    "c1": 1.25,
                    "c2": 0.4,
                    "switch_voltage_v": 4.0,
                    "h_multiplier": cooling,
                    "t_amb_c": ambient,
                    "soc0": 0.1,
                    "refined": mesh != 20,
                    "rung": rung,
                    "reference_method": guard.METHOD_ID,
                    "reference_method_digest": tasks.digest(guard.METHOD),
                    "reference_admission": ADMISSION,
                    "reference_dataset": DATASET,
                    "reference_role": "PUBLIC_CALIBRATION",
                    "parent_input_index": index,
                }
                for rung, mesh in enumerate((20, 40, 80), 1)
            ]
        )
    return result


def jobs():
    return [j for group in groups() for j in group]


def validate_job(job):
    if type(job) is not dict or not any(
        tasks.digest(job) == tasks.digest(j) for j in jobs()[3:]
    ):
        raise tasks.TaskError(
            "exact separately registered CAL15 continuation job required"
        )


def tracking_report(record, job):
    return guard._tracking_report(
        record,
        expected_job=job,
        reference_identity=(
            guard.observer({}) if job in guard.first_jobs() else observer()
        ),
        record_schema=guard.RECORD if job in guard.first_jobs() else RECORD,
        method_digest=tasks.digest(guard.METHOD),
    )


def execution_binding(
    *,
    source_commit,
    source_files,
    g0,
    t9_prerequisite,
    segment,
    dispatch_id,
    previous=None,
    scope="PUBLIC_DEVELOPMENT",
):
    if (
        scope not in ("PUBLIC_DEVELOPMENT", "SYNTHETIC_FIXTURE")
        or segment not in SEGMENTS
    ):
        raise tasks.TaskError("registered bounded CAL scope/segment required")
    _hex(source_commit, 40)
    producer._fields(source_files, REQUIRED_SOURCES, "CAL source inventory")
    for value in source_files.values():
        _hex(value)
    producer._fields(
        g0, ("binding_sha256", "records_sha256", "receipt_sha256"), "G0 pins"
    )
    for value in g0.values():
        _hex(value)
    producer._fields(
        t9_prerequisite,
        (
            "binding_digest",
            "manifest_digest",
            "probe_files",
            "evaluation_inputs_digest",
        ),
        "T9 feasibility pins",
    )
    for name in ("binding_digest", "manifest_digest", "evaluation_inputs_digest"):
        if not isinstance(t9_prerequisite[name], str) or not re.fullmatch(
            r"sha256:[0-9a-f]{64}", t9_prerequisite[name]
        ):
            raise tasks.TaskError("independent T9 content digest required")
    producer._fields(
        t9_prerequisite["probe_files"], PROBE_FILES, "construction-probe raw pins"
    )
    for value in t9_prerequisite["probe_files"].values():
        _hex(value)
    if segment == "pilot-2":
        if previous is not None:
            raise tasks.TaskError("first continuation reuses only G0")
    else:
        producer._fields(
            previous, ("manifest_sha256", "binding_digest"), "prior segment pins"
        )
        _hex(previous["manifest_sha256"])
        if not isinstance(previous["binding_digest"], str) or not re.fullmatch(
            r"sha256:[0-9a-f]{64}", previous["binding_digest"]
        ):
            raise tasks.TaskError("prior binding digest required")
    if type(dispatch_id) is not str or not dispatch_id.strip():
        raise tasks.TaskError("Root must bind a distinct CAL dispatch")
    start, end = SEGMENTS[segment]
    return {
        "schema": SCHEMA,
        "scope": scope,
        "execution_source": source_commit,
        "source_files": dict(source_files),
        "protocol_id": guard.METHOD_ID,
        "method_digest": tasks.digest(guard.METHOD),
        "observer": observer(),
        "input_manifest_sha256": t9.INPUT_SHA,
        "research_plan_sha256": t9.PLAN_SHA,
        "g0": producer._copy(g0),
        "t9": producer._copy(t9_prerequisite),
        "segment": segment,
        "previous": producer._copy(previous),
        "jobs": [j for g in groups()[start:end] for j in g],
        "dispatch": {
            "owner": "Root",
            "id": dispatch_id,
            "max_workers": 2,
            "max_minutes": 90,
            "max_usd": 2,
            "automatic_next_stage": False,
        },
    }


def _binding(binding, expected):
    if tasks.digest(binding) != expected:
        raise tasks.TaskError("CAL binding differs from independent pin")
    rebuilt = execution_binding(
        source_commit=binding["execution_source"],
        source_files=binding["source_files"],
        g0=binding["g0"],
        t9_prerequisite=binding["t9"],
        segment=binding["segment"],
        dispatch_id=binding["dispatch"]["id"],
        previous=binding["previous"],
        scope=binding["scope"],
    )
    if tasks.digest(binding) != tasks.digest(rebuilt):
        raise tasks.TaskError("closed exact CAL binding required")


def _prerequisites(binding, *, g0_binding, g0_raw, g0_receipt, t9_delivery, probe_raw):
    """Recompute G0, T9 construction and observed support; bind actual first fit."""
    prior = json.loads(g0_binding)
    if prior["execution_source"] != binding["execution_source"] or any(
        prior["source_files"][p] != binding["source_files"][p]
        for p in guard.REQUIRED_SOURCES
    ):
        raise tasks.TaskError(
            "freeze one final G0/T9/CAL execution source before acquisition"
        )
    g0_digest = t9._g0(binding, g0_binding, g0_raw, g0_receipt)
    producer._fields(
        t9_delivery, ("binding", "manifest", "raw_chunks"), "T9 raw delivery"
    )
    t9_binding = t9_delivery["binding"]
    if (
        t9_binding["scope"] != binding["scope"]
        or t9_binding["execution_source"] != binding["execution_source"]
        or t9_binding["g0"] != binding["g0"]
        or any(
            t9_binding["source_files"][p] != binding["source_files"][p]
            for p in t9.REQUIRED_SOURCES
        )
    ):
        raise tasks.TaskError("T9 source/scope/G0 prerequisite differs")
    evidence = t9.validate_delivery(
        **t9_delivery,
        expected_binding_digest=binding["t9"]["binding_digest"],
        expected_manifest_digest=binding["t9"]["manifest_digest"],
        g0_binding=g0_binding,
        g0_raw=g0_raw,
        g0_receipt=g0_receipt,
    )
    from carbon.development_comparison import carbon_arm
    from scripts.dev.score_lab import guarded419_train as train

    prepared = train.build(
        evidence,
        expected_binding_digest=binding["t9"]["binding_digest"],
        expected_manifest_digest=binding["t9"]["manifest_digest"],
        scope=binding["scope"],
    )
    producer._fields(probe_raw, PROBE_FILES, "actual construction-probe files")
    for name, raw in probe_raw.items():
        if type(raw) is not bytes or _sha(raw) != binding["t9"]["probe_files"][name]:
            raise tasks.TaskError("construction-probe raw bytes differ")
    probe = {name: json.loads(raw) for name, raw in probe_raw.items()}
    support = train.probe_support(
        prepared,
        expected_receipt_digest=prepared.receipt["receipt_digest"],
        evaluation_inputs=probe["inputs"],
        expected_inputs_digest=binding["t9"]["evaluation_inputs_digest"],
        scope=binding["scope"],
    )
    fit, predictions, outcome = (probe[k] for k in ("fit", "predictions", "outcome"))
    if (
        probe["construction"] != prepared.receipt
        or probe["support"] != support
        or support["status"] != "READY_FOR_CONSTRUCTION_PROBE"
        or fit["schema"] != carbon_arm.RECEIPT
        or fit["scope"] != binding["scope"]
        or fit["train"]["sha256"] != prepared.receipt["training_jsonl_digest"]
        or fit["train"]["records"] != support["accepted_rows"]
        or fit["code"]["construction_receipt_digest"]
        != prepared.receipt["receipt_digest"]
        or fit["recipe"]["backend"] != "jax"
        or fit["recipe"]["seed"] != 11
        or fit["recipe"]["settings"] != carbon_arm.TRAINER_DEFAULTS
        or fit["model_id"] != train.MODEL_ID + ":" + prepared.receipt["receipt_digest"]
        or fit["kit"] != train.KIT_ID + ":" + binding["t9"]["binding_digest"]
        or fit["train"]["fixture"] != (binding["scope"] == "SYNTHETIC_FIXTURE")
        or predictions["source_receipt_digest"]
        != carbon_arm.sha256(carbon_arm.canonical(fit))
        or predictions["scope"] != binding["scope"]
        or predictions["model_id"] != fit["model_id"]
        or len(predictions["rows"]) != len(probe["inputs"])
        or fit["abstained"] != 0
        or any(
            type(r.get("values")) is not dict
            or set(r["values"]) != set(train.QUANTITIES)
            or not all(producer._finite(v) for v in r["values"].values())
            for r in predictions["rows"]
        )
        or outcome["status"] != "SUPPORT_AND_DEFAULT11_FIT_COMPLETED"
        or outcome["fit_receipt_sha256"] != _sha(probe_raw["fit"])
        or outcome["predictions_sha256"] != _sha(probe_raw["predictions"])
    ):
        raise tasks.TaskError(
            "genuine supported target-only default11 probe required before CAL"
        )
    return g0_digest, prepared.receipt["receipt_digest"]


def delivery_manifest(binding, chunks):
    return {
        "schema": DELIVERY,
        "scope": binding["scope"],
        "binding_digest": tasks.digest(binding),
        "segment": binding["segment"],
        "offered_job_ids": [j["case_id"] for j in jobs()],
        "chunks": producer._copy(chunks),
    }


def _reduce(
    binding,
    manifest,
    raw_chunks,
    *,
    expected_binding_digest,
    expected_manifest_digest,
    **prerequisites,
):
    _binding(binding, expected_binding_digest)
    g0_digest, train_digest = _prerequisites(binding, **prerequisites)
    if tasks.digest(manifest) != expected_manifest_digest:
        raise tasks.TaskError("CAL manifest differs from independent pin")
    producer._fields(
        manifest,
        ("schema", "scope", "binding_digest", "segment", "offered_job_ids", "chunks"),
        "CAL manifest",
    )
    if (
        manifest["schema"] != DELIVERY
        or manifest["scope"] != binding["scope"]
        or manifest["binding_digest"] != expected_binding_digest
        or manifest["segment"] != binding["segment"]
        or manifest["offered_job_ids"] != [j["case_id"] for j in jobs()]
    ):
        raise tasks.TaskError("registered CAL delivery order/scope/binding required")
    records, source_rows, seen_chunks = {}, {}, set()
    for line, body in enumerate(prerequisites["g0_raw"].splitlines(), 1):
        if body.strip():
            row = json.loads(body)
            records[row["case_id"]] = row
            source_rows[row["case_id"]] = {
                "chunk_id": "original-g0",
                "line": line,
                "raw_sha256": _sha(prerequisites["g0_raw"]),
                "source_commit": binding["execution_source"],
                "source_files": json.loads(prerequisites["g0_binding"])["source_files"],
            }
    segment_names = list(SEGMENTS)
    active = segment_names.index(binding["segment"])
    for position, chunk in enumerate(manifest["chunks"]):
        producer._fields(
            chunk,
            ("id", "sha256", "segment", "source_commit", "source_files", "rows"),
            "CAL chunk",
        )
        name, segment = chunk["id"], chunk["segment"]
        if (
            position > active
            or segment != segment_names[position]
            or type(name) is not str
            or name == "original-g0"
            or name in seen_chunks
            or name not in raw_chunks
        ):
            raise tasks.TaskError("one contiguous original CAL segment chunk required")
        seen_chunks.add(name)
        raw = raw_chunks[name]
        if (
            type(raw) is not bytes
            or _sha(raw) != chunk["sha256"]
            or chunk["source_commit"] != binding["execution_source"]
            or chunk["source_files"] != binding["source_files"]
        ):
            raise tasks.TaskError("CAL raw/source identity differs")
        start, end = SEGMENTS[segment]
        offered = {j["case_id"]: j for g in groups()[start:end] for j in g}
        order = {j["case_id"]: i for i, g in enumerate(groups()[start:end]) for j in g}
        lines, mapped, previous_group = raw.splitlines(), set(), -1
        previous_line = 0
        for mapping in chunk["rows"]:
            producer._fields(mapping, ("line", "job_id"), "CAL original row mapping")
            line, jid = mapping["line"], mapping["job_id"]
            if (
                type(line) is not int
                or not 1 <= line <= len(lines)
                or line in mapped
                or line <= previous_line
                or jid not in offered
                or jid in records
                or order[jid] < previous_group
            ):
                raise tasks.TaskError("unique original in-order CAL row required")
            mapped.add(line)
            previous_line = line
            previous_group = order[jid]
            row = json.loads(lines[line - 1])
            if (
                type(row) is not dict
                or any(row.get(k) != v for k, v in offered[jid].items())
                or tasks.digest({k: row[k] for k in offered[jid]})
                != tasks.digest(offered[jid])
            ):
                raise tasks.TaskError("original CAL input/role/types differ")
            if binding["scope"] == "PUBLIC_DEVELOPMENT" and row.get("fixture"):
                raise tasks.TaskError("synthetic CAL cannot enter public evidence")
            if row.get("schema") != RECORD or tasks.digest(
                row.get("reference_identity")
            ) != tasks.digest(observer()):
                raise tasks.TaskError("foreign CAL record/observer context")
            records[jid] = row
            source_rows[jid] = {
                "chunk_id": name,
                "line": line,
                "raw_sha256": _sha(raw),
                "source_commit": chunk["source_commit"],
                "source_files": chunk["source_files"],
            }
        if mapped != {i for i, body in enumerate(lines, 1) if body.strip()}:
            raise tasks.TaskError("unmapped CAL raw lines forbidden")
    if set(raw_chunks) != seen_chunks or len(manifest["chunks"]) != active + 1:
        raise tasks.TaskError("complete supplied CAL segment inventory required")
    triples, tracking, states, per_case, blocked = {}, {}, {}, {}, False
    all_groups = groups()
    for group in all_groups:
        case = collector._case(group)
        present, values = [j for j in group if j["case_id"] in records], {}
        if present and blocked:
            raise tasks.TaskError(
                "later CAL tuple supplied after failed or missing predecessor"
            )
        for job in group:
            jid = job["case_id"]
            row = records.get(jid)
            observation = tracking_report(row, job)
            extraction = producer._extract(row)
            tracking[jid] = observation
            states[jid] = {
                "raw_status": row.get("status") if row else "MISSING",
                "tracking_status": observation["status"],
                "extraction_state": extraction["state"],
            }
            if extraction["state"] == "EXTRACTED":
                values[str({1: 20, 2: 40, 3: 80}[job["rung"]])] = extraction["values"]
        if present:
            triples[case] = values
        numeric = numerics.calibration_report(
            {case: values} if present else {},
            expected_cases=[case],
            expected_policy_digest=tasks.digest(numerics.POLICY),
        )
        valid = numeric["status"] == COMPATIBLE and all(
            tracking[j["case_id"]]["status"] == "TRACKING_COMPATIBLE" for j in group
        )
        per_case[case] = {
            "status": COMPATIBLE if valid else "REFERENCE_UNRESOLVED",
            "numerical": numeric,
        }
        if not valid:
            blocked = True
    numeric = numerics.calibration_report(
        triples,
        expected_cases=[collector._case(g) for g in all_groups],
        expected_policy_digest=tasks.digest(numerics.POLICY),
    )
    complete = numeric["status"] == COMPATIBLE and not blocked and len(records) == 45
    return {
        "scope": binding["scope"],
        "binding_digest": expected_binding_digest,
        "manifest_digest": expected_manifest_digest,
        "protocol_id": guard.METHOD_ID,
        "method_digest": tasks.digest(guard.METHOD),
        "source_commit": binding["execution_source"],
        "source_files": binding["source_files"],
        "status": COMPATIBLE if complete else "REFERENCE_UNRESOLVED",
        "expected_case_count": 15,
        "missing_cases": numeric["missing_cases"],
        "failed_cases": [
            c
            for c, v in per_case.items()
            if v["status"] != COMPATIBLE and c not in numeric["missing_cases"]
        ],
        "numerical": numeric,
        "per_case": per_case,
        "tracking": tracking,
        "per_job": states,
        "source_rows": source_rows,
        "g0_receipt_digest": g0_digest,
        "construction_receipt_digest": train_digest,
        "offered_jobs": jobs(),
        "observed_rows": len(records),
        "qualification": False,
        "evaluation_release": False,
        "physical_certificate": False,
    }


@dataclass(frozen=True, slots=True, init=False)
class ValidatedCalibrationEvidence:
    """Nominal complete evidence, not a hostile in-process security boundary."""

    _snapshot: bytes

    def __init__(self, snapshot, *, _token=None):
        if _token is not _TOKEN:
            raise tasks.TaskError("use authenticated complete CAL15 delivery")
        object.__setattr__(self, "_snapshot", snapshot)


def validate_delivery(
    binding,
    manifest,
    raw_chunks,
    *,
    expected_binding_digest,
    expected_manifest_digest,
    **prerequisites,
):
    snapshot = _reduce(
        binding,
        manifest,
        raw_chunks,
        expected_binding_digest=expected_binding_digest,
        expected_manifest_digest=expected_manifest_digest,
        **prerequisites,
    )
    if snapshot["status"] != COMPATIBLE:
        raise tasks.TaskError("complete compatible all45-rung CAL15 evidence required")
    return ValidatedCalibrationEvidence(
        json.dumps(snapshot, sort_keys=True, allow_nan=False).encode(), _token=_TOKEN
    )


def validate_for(evidence, *, expected_binding_digest, expected_manifest_digest, scope):
    if type(evidence) is not ValidatedCalibrationEvidence:
        raise tasks.TaskError("validated nominal CAL15 evidence required")
    snapshot = json.loads(evidence._snapshot)
    if (
        snapshot["scope"] != scope
        or snapshot["binding_digest"] != expected_binding_digest
        or snapshot["manifest_digest"] != expected_manifest_digest
        or snapshot["status"] != COMPATIBLE
        or snapshot["expected_case_count"] != 15
        or snapshot["missing_cases"]
        or snapshot["failed_cases"]
    ):
        raise tasks.TaskError("complete CAL15 consumer context differs")
    return snapshot


def _load(entry, load):
    producer._fields(entry, ("path", "sha256"), "pinned CAL file")
    name = entry["path"]
    if (
        type(name) is not str
        or not name
        or PurePosixPath(name).is_absolute()
        or PureWindowsPath(name).is_absolute()
        or PureWindowsPath(name).drive
        or ".." in PureWindowsPath(name).parts
        or ".." in PurePosixPath(name).parts
    ):
        raise tasks.TaskError("relative public CAL evidence file required")
    _hex(entry["sha256"])
    raw = load(name)
    if type(raw) is not bytes or _sha(raw) != entry["sha256"]:
        raise tasks.TaskError("CAL file bytes differ from independent pin")
    return raw


def _materials(spec, *, load, scope):
    producer._fields(
        spec,
        (
            "schema",
            "scope",
            "binding",
            "manifest",
            "raw_chunks",
            "g0",
            "t9",
            "probe",
            "expected_binding_digest",
            "expected_manifest_digest",
        ),
        "CAL file specification",
    )
    if (
        scope not in ("PUBLIC_DEVELOPMENT", "SYNTHETIC_FIXTURE")
        or spec["schema"] != FILE_SPEC
        or spec["scope"] != scope
    ):
        raise tasks.TaskError("exact CAL file scope required")
    producer._fields(
        spec["g0"], ("binding", "records", "receipt"), "G0 file specification"
    )
    producer._fields(
        spec["t9"], ("binding", "manifest", "raw_chunks"), "T9 file specification"
    )
    producer._fields(spec["probe"], PROBE_FILES, "probe file specification")
    raw_binding, raw_manifest = (_load(spec[k], load) for k in ("binding", "manifest"))
    binding, manifest = json.loads(raw_binding), json.loads(raw_manifest)
    if binding["scope"] != scope:
        raise tasks.TaskError("CAL binding/file scope differs")
    material = {
        "binding": binding,
        "manifest": manifest,
        "raw_chunks": {k: _load(v, load) for k, v in spec["raw_chunks"].items()},
        "expected_binding_digest": spec["expected_binding_digest"],
        "expected_manifest_digest": spec["expected_manifest_digest"],
        "g0_binding": _load(spec["g0"]["binding"], load),
        "g0_raw": _load(spec["g0"]["records"], load),
        "g0_receipt": _load(spec["g0"]["receipt"], load),
        "t9_delivery": {
            "binding": json.loads(_load(spec["t9"]["binding"], load)),
            "manifest": json.loads(_load(spec["t9"]["manifest"], load)),
            "raw_chunks": {
                k: _load(v, load) for k, v in spec["t9"]["raw_chunks"].items()
            },
        },
        "probe_raw": {k: _load(v, load) for k, v in spec["probe"].items()},
    }
    return material, raw_manifest


def from_files(spec, *, load, scope):
    """Load pinned public resource keys; only complete CAL can seal.

    Each entry.path is an opaque relative key passed unchanged to load(key).
    In N1 bundles it names a declared manifest.files key, not its disk path.
    The caller owns resolution/custody. There is no filesystem fallback here.
    """
    material, _ = _materials(spec, load=load, scope=scope)
    return validate_delivery(**material)


def run(spec, *, load, records_path, workers=2, root=None):
    """One explicit2/3/4/5-triple Root dispatch; previous data is never rerun."""
    from carbon.battery import truth_env

    if (
        spec.get("scope") != "PUBLIC_DEVELOPMENT"
        or type(workers) is not int
        or not 1 <= workers <= 2
    ):
        raise tasks.TaskError("Root public CAL dispatch requires one or two workers")
    material, prior_raw_manifest = _materials(
        spec, load=load, scope="PUBLIC_DEVELOPMENT"
    )
    binding, prior_manifest, raw_chunks = (
        material[k] for k in ("binding", "manifest", "raw_chunks")
    )
    _binding(binding, material["expected_binding_digest"])
    prerequisites = {
        k: material[k]
        for k in ("g0_binding", "g0_raw", "g0_receipt", "t9_delivery", "probe_raw")
    }
    _prerequisites(binding, **prerequisites)
    if tasks.digest(prior_manifest) != material["expected_manifest_digest"]:
        raise tasks.TaskError("previous CAL manifest differs from independent pin")
    segment = binding["segment"]
    start, end = SEGMENTS[segment]
    if start == 1:
        if prior_manifest != delivery_manifest(binding, []) or raw_chunks:
            raise tasks.TaskError("first continuation reuses only original G0")
    else:
        if (
            _sha(prior_raw_manifest) != binding["previous"]["manifest_sha256"]
            or prior_manifest["binding_digest"] != binding["previous"]["binding_digest"]
            or prior_manifest["segment"]
            != list(SEGMENTS)[list(SEGMENTS).index(segment) - 1]
            or prior_manifest["scope"] != binding["scope"]
            or prior_manifest["schema"] != DELIVERY
            or prior_manifest["offered_job_ids"] != [j["case_id"] for j in jobs()]
        ):
            raise tasks.TaskError(
                "immediately preceding original CAL delivery required"
            )
    chunk_id = segment
    if chunk_id in raw_chunks:
        raise tasks.TaskError("current CAL segment must have fresh output")
    root = Path(root) if root is not None else Path(__file__).resolve().parents[3]
    if any(
        _sha((root / p).read_bytes()) != sha
        for p, sha in binding["source_files"].items()
    ):
        raise tasks.TaskError("shipped CAL source bytes differ")
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
        raise tasks.TaskError("CAL truth runtime differs")
    records = Path(records_path)
    receipt_path = records.with_name(records.name + ".cal15.json")
    temporary = receipt_path.with_name(receipt_path.name + ".tmp")
    if any(os.path.lexists(p) for p in (records, receipt_path, temporary)) or any(
        p.is_symlink() for p in records.parents
    ):
        raise tasks.TaskError("CAL requires fresh non-symlink output/receipt")
    mappings = []
    states = {
        j["case_id"]: "REUSED_OK" if i < start else "NOT_DISPATCHED"
        for i, group in enumerate(groups())
        for j in group
    }
    receipt = {
        "schema": "carbon.scorelab.guarded419.cal15-execution-receipt.v1",
        "scope": binding["scope"],
        "binding_digest": material["expected_binding_digest"],
        "segment": segment,
        "status": "INCOMPLETE_REFERENCE",
        "per_job": states,
        "registered_calibration_complete": False,
        "full_calibration_release": False,
        "evaluation_release": False,
        "qualification": False,
    }

    def current(raw):
        chunk = {
            "id": chunk_id,
            "sha256": _sha(raw),
            "segment": segment,
            "source_commit": binding["execution_source"],
            "source_files": binding["source_files"],
            "rows": mappings,
        }
        manifest = delivery_manifest(binding, prior_manifest["chunks"] + [chunk])
        report = _reduce(
            binding,
            manifest,
            {**raw_chunks, chunk_id: raw},
            expected_binding_digest=material["expected_binding_digest"],
            expected_manifest_digest=tasks.digest(manifest),
            **prerequisites,
        )
        return manifest, report

    # Validate every previous triple before opening output or creating a pool.
    _, prior_report = current(b"")
    if prior_report["observed_rows"] != start * 3 or any(
        prior_report["per_case"][collector._case(g)]["status"] != COMPATIBLE
        for g in groups()[:start]
    ):
        raise tasks.TaskError("actual complete compatible prior CAL segment required")

    def save():
        raw = records.read_bytes()
        manifest, report = current(raw)
        receipt.update(
            records_sha256=_sha(raw),
            manifest=manifest,
            manifest_digest=tasks.digest(manifest),
            calibration=report,
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
            record.setdefault("reference_identity", observer())
        record = truth_env.stamp(record, provenance)
        with records.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True, allow_nan=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        mappings.append({"line": len(mappings) + 1, "job_id": job["case_id"]})
        states[job["case_id"]] = record.get("status", "MALFORMED_RECORD")
        save()
        return record

    def completed(group, rows):
        status = receipt["calibration"]["per_case"][collector._case(group)]["status"]
        if status != COMPATIBLE:
            receipt["status"] = "REFERENCE_UNRESOLVED"
            save()
            return False
        return True

    with records.open("x", encoding="utf-8"):
        pass
    save()
    try:
        if not collector._collect_groups(
            groups()[start:end],
            workers=workers,
            submitted=submitted,
            received=received,
            completed=completed,
            record_schema=RECORD,
        ):
            return 2
    except BaseException as original_error:
        receipt["status"] = "INTERRUPTED_OR_INVALID_REFERENCE"
        try:
            save()
        except Exception as error:  # noqa: BLE001 -- preserve original
            original_error.add_note(
                "CAL receipt persistence failed: " + type(error).__name__
            )
        raise
    receipt["registered_calibration_complete"] = (
        receipt["calibration"]["status"] == COMPATIBLE
    )
    receipt["status"] = (
        "COMPATIBLE_FULL_CALIBRATION_ONLY"
        if receipt["registered_calibration_complete"]
        else "COMPATIBLE_SEGMENT_ONLY"
    )
    save()
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--spec-sha256", required=True)
    parser.add_argument("--public-root", type=Path, required=True)
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args(argv)
    raw = args.spec.read_bytes()
    if _sha(raw) != _hex(args.spec_sha256):
        raise tasks.TaskError("Root-pinned CAL invocation bytes required")
    root = args.public_root.resolve(strict=True)

    def load(name):
        path = (root / name).resolve(strict=True)
        if not path.is_relative_to(root) or not path.is_file():
            raise tasks.TaskError("CAL file escapes public input root")
        return path.read_bytes()

    return run(
        json.loads(raw), load=load, records_path=args.records, workers=args.workers
    )


if __name__ == "__main__":
    raise SystemExit(main())
