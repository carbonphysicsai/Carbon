"""Trusted DEVELOPMENT continuation: authenticate six pilot triples, solve nine.

Root pins the continuation binding, actual source commits and resource envelope
before using the existing in-image pod entrypoint. No provider, retry, automatic
resume, evaluation read or scientific-qualification authority lives here.

python -m scripts.dev.score_lab.owner_v3_calibration_continue --binding B
  --binding-sha256 HEX --execution-binding CURRENT --pilot-binding OLD
  --pilot-jobs JOBS --pilot-records RAW --pilot-receipt RECEIPT
  --records FRESH_OUTPUT --workers 2

B has exactly schema/execution_binding_sha256/orchestrator_sha256/
pilot_binding_sha256/pilot_records_sha256/pilot_receipt_sha256. Both execution
bindings use feasibility02's existing schema. Current and old eight source bytes
must agree; their externally authenticated execution commits may differ.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from carbon.battery import truth_env
from carbon.design_search import tasks
from scripts.dev.battery import feasibility02 as worker
from scripts.dev.score_lab import owner_v3 as owner
from scripts.dev.score_lab import owner_v3_numerics as numerics
from scripts.dev.score_lab import owner_v3_panel_export as producer

SCHEMA = "carbon.scorelab.calibration-continuation.v1"
COMPATIBLE = "COMPATIBLE_FOR_REGISTERED_CALIBRATION_CASES"


def _hash(raw):
    return hashlib.sha256(raw).hexdigest()


def _pinned(path, expected):
    if type(expected) is not str or not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise tasks.TaskError("independently pinned raw SHA256 required")
    raw = Path(path).read_bytes()
    if _hash(raw) != expected:
        raise tasks.TaskError("continuation input bytes differ")
    return raw


def _case(group):
    return group[0]["case_id"].rsplit(":mesh", 1)[0]


def _report(triples, cases, binding):
    return numerics.calibration_report(
        triples, expected_cases=cases, expected_policy_digest=binding["policy_digest"]
    )


def _chunk(binding, raw, mappings, identity):
    return {
        "id": identity,
        "sha256": "sha256:" + _hash(raw),
        "role": "PUBLIC_CALIBRATION",
        "source_commit": binding["execution_source"],
        # The public producer requires four observer files, not the guard's eight.
        "source_files": binding["observer"]["source_files"],
        "rows": mappings,
    }


def _prepare(paths, expected_sha256):
    raw = _pinned(paths["binding"], expected_sha256)
    contract = json.loads(raw)
    producer._fields(
        contract,
        (
            "schema",
            "execution_binding_sha256",
            "orchestrator_sha256",
            "pilot_binding_sha256",
            "pilot_records_sha256",
            "pilot_receipt_sha256",
        ),
        "continuation binding",
    )
    if contract["schema"] != SCHEMA:
        raise tasks.TaskError("registered continuation schema required")
    _pinned(__file__, contract["orchestrator_sha256"])
    current, pilot_groups = worker._calibration_contract(
        paths["pilot_jobs"],
        paths["execution_binding"],
        contract["execution_binding_sha256"],
    )
    pilot, _ = worker._calibration_contract(
        paths["pilot_jobs"], paths["pilot_binding"], contract["pilot_binding_sha256"]
    )
    if {k: v for k, v in current.items() if k != "execution_source"} != {
        k: v for k, v in pilot.items() if k != "execution_source"
    }:
        raise tasks.TaskError("pilot observer, source bytes, plan or scope differs")
    pilot_raw = _pinned(paths["pilot_records"], contract["pilot_records_sha256"])
    receipt = json.loads(
        _pinned(paths["pilot_receipt"], contract["pilot_receipt_sha256"])
    )
    producer._fields(
        receipt,
        (
            "schema",
            "scope",
            "binding_sha256",
            "execution_source",
            "source_files",
            "observer",
            "plan_digest",
            "offered_jobs_digest",
            "status",
            "per_job",
            "per_completed_triple",
            "full_calibration_release",
            "qualification",
            "calibration",
            "records_sha256",
        ),
        "pilot stop receipt",
    )
    pilot_jobs = [job for group in pilot_groups for job in group]
    offered = {job["case_id"] for job in pilot_jobs}
    records, mappings = {}, []
    for line, body in enumerate(pilot_raw.splitlines(), 1):
        if not body.strip():
            continue
        record = json.loads(body)
        jid = record.get("case_id") if type(record) is dict else None
        if jid not in offered or jid in records:
            raise tasks.TaskError("unique original pilot rows required")
        records[jid] = record
        mappings.append({"line": line, "job_id": jid, "case_id": jid})
    if set(records) != offered:
        raise tasks.TaskError("complete pilot rows required")
    triples, reports = {}, []
    for group in pilot_groups:
        case = _case(group)
        triples[case] = worker._calibration_rows(
            pilot, group, [records[j["case_id"]] for j in group]
        )
        report = _report({case: triples[case]}, [case], pilot)
        if report["status"] != COMPATIBLE:
            raise tasks.TaskError("pilot is failed or unresolved; continuation refused")
        reports.append(report)
    expected = {
        "schema": "carbon.scorelab.calibration-execution-receipt.v1",
        "scope": pilot["scope"],
        "binding_sha256": contract["pilot_binding_sha256"],
        "execution_source": pilot["execution_source"],
        "source_files": pilot["source_files"],
        "observer": pilot["observer"],
        "plan_digest": pilot["plan_digest"],
        "offered_jobs_digest": tasks.digest(pilot_jobs),
        "status": "COMPATIBLE_PILOT_ONLY",
        "per_job": {j: "OK" for j in offered},
        "per_completed_triple": reports,
        "full_calibration_release": False,
        "qualification": False,
        "calibration": _report(triples, [_case(g) for g in pilot_groups], pilot),
        "records_sha256": contract["pilot_records_sha256"],
    }
    if receipt != expected:
        raise tasks.TaskError("authenticated pilot stop receipt disagrees with raw")
    rest = owner.acquisition_inputs(
        current["plan"],
        expected_digest=current["plan_digest"],
        stage="calibration-rest",
    )["jobs"]
    groups = [rest[i : i + 3] for i in range(0, len(rest), 3)]
    if (
        len(pilot_groups) != 6
        or len(groups) != 9
        or any(len(g) != 3 or [j["rung"] for j in g] != [1, 2, 3] for g in groups)
        or offered & {j["case_id"] for j in rest}
        or len({_case(g) for g in pilot_groups + groups}) != 15
    ):
        raise tasks.TaskError("exact disjoint six-plus-nine calibration required")
    return (
        current,
        triples,
        pilot_groups,
        groups,
        _chunk(pilot, pilot_raw, mappings, "reused-pilot"),
    )


def run(paths, *, expected_sha256, workers=2):
    """Authenticate prior evidence before pool/output creation; never rerun it."""
    if type(workers) is not int or not 1 <= workers <= 2:
        raise tasks.TaskError("continuation requires one or two workers")
    binding, triples, pilot_groups, groups, pilot_chunk = _prepare(
        paths, expected_sha256
    )
    provenance = truth_env.provenance(".")
    plan = binding["plan"]
    if (
        provenance.get("schema") != "carbon.battery.solver-provenance.v1"
        or provenance.get("solver_image", "").split("@")[-1] != plan["image_digest"]
        or provenance.get("overlay_lock_sha256") != "sha256:" + plan["overlay_sha256"]
        or provenance.get("overlay_lock")
        != "scripts/dev/exam_design/locks/battery-overlay.lock.json"
        or provenance.get("pybamm") != "26.8.0.0"
    ):
        raise tasks.TaskError("continuation truth runtime differs")
    records = Path(paths["records"])
    receipt_path = records.with_name(records.name + ".continuation.json")
    temporary = receipt_path.with_name(receipt_path.name + ".tmp")
    if any(p.exists() for p in (records, receipt_path, temporary)):
        raise tasks.TaskError("continuation requires fresh output and receipt")
    states = {j["case_id"]: "REUSED_OK" for g in pilot_groups for j in g}
    states.update({j["case_id"]: "NOT_DISPATCHED" for g in groups for j in g})
    cases = [_case(g) for g in pilot_groups + groups]
    mappings = []
    receipt = {
        "schema": "carbon.scorelab.calibration-continuation-receipt.v1",
        "scope": binding["scope"],
        "binding_sha256": expected_sha256,
        "execution_source": binding["execution_source"],
        "source_files": binding["source_files"],
        "observer": binding["observer"],
        "plan_digest": binding["plan_digest"],
        "offered_jobs_digest": tasks.digest(
            [j for g in pilot_groups + groups for j in g]
        ),
        "per_job": states,
        "per_completed_triple": [],
        "status": "INCOMPLETE_REFERENCE",
        "registered_calibration_complete": False,
        "full_calibration_release": False,
        "evaluation_release": False,
        "qualification": False,
    }

    def save():
        raw = records.read_bytes()
        receipt["records_sha256"] = _hash(raw)
        receipt["chunks"] = [
            pilot_chunk,
            _chunk(binding, raw, mappings, "continuation"),
        ]
        receipt["calibration"] = _report(triples, cases, binding)
        with temporary.open("w", encoding="utf-8") as handle:
            handle.write(json.dumps(receipt, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(receipt_path)

    with records.open("x", encoding="utf-8"):
        pass
    save()
    try:
        with ProcessPoolExecutor(workers) as pool:
            for group in groups:
                futures, rows = {}, []
                for job in group:
                    future = pool.submit(worker._timed, job)
                    futures[future] = job
                    states[job["case_id"]] = "SUBMITTED"
                    save()
                for future in as_completed(futures):
                    job = futures[future]
                    try:
                        record = future.result()
                    except Exception as exc:  # noqa: BLE001 -- preserve infra evidence
                        record = {
                            **job,
                            "schema": "carbon.battery.feasibility02-record.v1",
                            "status": "FAILED_INFRA",
                            "error": repr(exc)[:300],
                        }
                    record = truth_env.stamp(record, provenance)
                    with records.open("a", encoding="utf-8") as handle:
                        handle.write(json.dumps(record, sort_keys=True) + "\n")
                        handle.flush()
                        os.fsync(handle.fileno())
                    rows.append(record)
                    mappings.append(
                        {
                            "line": len(mappings) + 1,
                            "job_id": job["case_id"],
                            "case_id": record.get("case_id"),
                        }
                    )
                    states[job["case_id"]] = record.get("status", "MALFORMED_RECORD")
                    save()
                case = _case(group)
                triples[case] = worker._calibration_rows(binding, group, rows)
                current = _report({case: triples[case]}, [case], binding)
                receipt["per_completed_triple"].append(current)
                if current["status"] != COMPATIBLE:
                    receipt["status"] = current["status"]
                    save()
                    return 2
                save()
    except BaseException:
        receipt["status"] = "INTERRUPTED_OR_INVALID_REFERENCE"
        save()
        raise
    receipt["registered_calibration_complete"] = (
        receipt["calibration"]["status"] == COMPATIBLE
    )
    receipt["status"] = "COMPATIBLE_FULL_CALIBRATION_ONLY"
    save()
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "binding",
        "execution-binding",
        "pilot-binding",
        "pilot-jobs",
        "pilot-records",
        "pilot-receipt",
        "records",
    ):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--binding-sha256", required=True)
    parser.add_argument("--workers", type=int, default=2)
    args = vars(parser.parse_args(argv))
    return run(
        {k: v for k, v in args.items() if k not in ("binding_sha256", "workers")},
        expected_sha256=args["binding_sha256"],
        workers=args["workers"],
    )


if __name__ == "__main__":
    raise SystemExit(main())
