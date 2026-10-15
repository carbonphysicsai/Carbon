"""Pure preparation of published coarse labels for construction, NEVER truth.

No file access or numerical evaluation. Root authenticates delivery/role, runs
the extraction in TEST, and retains excluded/nonfinite rows in its ledger.
These are not completed rows of the separately registered 4,000-TRAIN plan.
"""

from __future__ import annotations

import hashlib
import json
import re

from carbon.design_search import tasks

SOURCE_SHA = "c6c23a5211af1e16b6decb6e702448d77471a7343fb05ff78e697bce2fa807b7"
REGISTRY_SHA = "b3007401e8a24aa4761d87f07832a0acfb4cd1e3230983bede5dd66ba8eaa4ba"
BASE_REGISTRY_SHA = "ce0ee4dd838fe78e1c902a883c3d4791705ae0efac20553fdb422bf2e320e632"
QUANTITIES = ("charging_t_max_c", "plating_min_v", "v_max_v", "q30_over_q1", "minutes")
NUMBER = r"[0-9]+(?:\.[0-9]+)?"
KEY = re.compile(rf"c1=({NUMBER}),c2=({NUMBER}),sv=({NUMBER}):h([124])@T({NUMBER})")


def _sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def prepare(
    raw,
    registry_raw,
    base_registry_raw,
    *,
    plan,
    expected_plan_digest,
    source_digest,
    registry_digest,
    base_registry_digest,
    scope,
):
    """Return JSONL bytes and a role/coverage receipt, without fits or solves.

    The actual five quantities are copied unchanged; old verdicts and voltage
    allowance are NOT carried into the new evaluator. Null labels remain null
    and the existing trainer counts/excludes them. No imputation or redraw.
    """
    from .owner_v3 import acquisition_inputs

    if scope not in ("SYNTHETIC_FIXTURE", "PUBLIC_DEVELOPMENT"):
        raise tasks.TaskError("development construction only")
    if (
        _sha(raw) != source_digest
        or _sha(registry_raw) != registry_digest
        or _sha(base_registry_raw) != base_registry_digest
    ):
        raise tasks.TaskError("construction source or registry bytes differ")
    if scope == "PUBLIC_DEVELOPMENT" and (
        source_digest != "sha256:" + SOURCE_SHA
        or registry_digest != "sha256:" + REGISTRY_SHA
        or base_registry_digest != "sha256:" + BASE_REGISTRY_SHA
    ):
        raise tasks.TaskError("registered published construction source required")
    document, registry = json.loads(raw), json.loads(registry_raw)
    if (
        document.get("schema") != "carbon.battery.feasibility02-v2-rescore.v1"
        or registry.get("schema")
        != "carbon.battery.feasibility02-v2-rescore-registry.v1"
    ):
        raise tasks.TaskError("published construction source schemas required")
    stages = [
        acquisition_inputs(plan, expected_digest=expected_plan_digest, stage=s)["jobs"]
        for s in ("calibration-pilot", "calibration-rest", "evaluation")
    ]
    exclusions = {
        tuple(
            float(j[k])
            for k in ("c1", "c2", "switch_voltage_v", "h_multiplier", "t_amb_c", "soc0")
        )
        for jobs in stages
        for j in jobs
    }
    records, excluded = [], []
    for case, values in document["cells"].items():
        match = KEY.fullmatch(case)
        if (
            match is None
            or type(values) is not dict
            or not set(QUANTITIES) <= set(values)
        ):
            raise tasks.TaskError(
                "construction input identity or observable inventory missing"
            )
        c1, c2, switch, cooling, ambient = map(float, match.groups())
        identity = (c1, c2, switch, cooling, ambient, 0.1)
        if identity in exclusions:
            excluded.append(case)
            continue
        record = {
            "schema": "carbon.battery-v3.train-record.v1",
            "case_id": "published-coarse402:" + case,
            "source": "public coarse feasibility02 study; construction/discovery only",
            "source_digest": source_digest,
            "registry_digest": registry_digest,
            "base_registry_digest": base_registry_digest,
            "inputs": {
                "c1": c1,
                "c2": c2,
                "switch_v": switch,
                "cooling": int(cooling),
                "ambient_c": ambient,
                "soc0": 0.1,
            },
            "outputs": {q: values[q] for q in QUANTITIES},
        }
        if scope == "SYNTHETIC_FIXTURE":
            record["fixture"] = True
        records.append(record)
    data = b"".join((json.dumps(r, allow_nan=False) + "\n").encode() for r in records)
    ranges = (
        {
            q: [
                min(r["inputs"][q] for r in records),
                max(r["inputs"][q] for r in records),
            ]
            for q in ("c1", "c2", "switch_v", "ambient_c")
        }
        if records
        else {}
    )
    receipt = {
        "schema": "carbon.scorelab.public-coarse-construction.v1",
        "scope": scope,
        "role": "PUBLIC_CONSTRUCTION_DISCOVERY_ONLY",
        "plan_digest": expected_plan_digest,
        "source_digest": source_digest,
        "registry_digest": registry_digest,
        "base_registry_digest": base_registry_digest,
        "source_rows": len(document["cells"]),
        "offered_training_rows": len(records),
        "calibration_evaluation_exclusions": excluded,
        "input_ranges_before_trainer_quality_exclusion": ranges,
        "TRAIN_plan_completed_rows_claimed": 0,
        "numerical_evaluation_reference": False,
        "qualification": False,
        "training_jsonl_digest": _sha(data),
    }
    return data, {**receipt, "receipt_digest": tasks.digest(receipt)}


# Frozen input metadata only; no labels, secrets or protected cases.
ANCHORS_SHA = "58513536f11d9e5cf6396d883138d2e7cb88440e97086dcf4850c0e6aff2c43b"
TRAIN_PLAN_SHA = "b42b41f149e317832c5b41d0c533b046ad16962f47416c553c63be8b7bcf60df"
ANCHOR_MANIFEST = "carbon.scorelab.public-train-anchor-sources.v1"
INPUTS = ("c1", "c2", "switch_voltage_v", "h_multiplier", "t_amb_c", "soc0")


def combine(
    coarse_raw,
    coarse_receipt,
    *,
    expected_coarse_receipt_digest,
    anchors_raw,
    expected_anchors_sha256,
    plan,
    expected_plan_digest,
    source_pins,
    expected_source_pins_digest,
    manifest,
    expected_manifest_digest,
    raw_chunks,
    scope,
):
    """Combine coarse construction and all offered TRAIN anchors, without I/O.

    Root authenticates public delivery and independently binds expected hashes.
    Manifest fields: schema, scope, role, plan_digest, source_pins_digest,
    anchors_sha256, observer, chunks. Chunk fields: id, sha256, role,
    source_commit, source_files, rows; each mapping: line, job_id, case_id.
    Every nonblank raw line is mapped exactly once; absent jobs remain MISSING.
    Return (TRAIN JSONL bytes, receipt). This does not fit or qualify anything.
    """
    from . import owner_v3_panel_export as producer
    from .owner_v3 import acquisition_inputs

    if scope not in ("PUBLIC_DEVELOPMENT", "SYNTHETIC_FIXTURE"):
        raise tasks.TaskError("development TRAIN only")
    producer._digest(plan, expected_plan_digest, "acquisition plan")
    producer._digest(source_pins, expected_source_pins_digest, "source pins")
    producer._digest(manifest, expected_manifest_digest, "TRAIN manifest")
    coarse_body = {k: v for k, v in coarse_receipt.items() if k != "receipt_digest"}
    producer._digest(coarse_body, expected_coarse_receipt_digest, "coarse receipt")
    if (
        coarse_receipt.get("receipt_digest") != expected_coarse_receipt_digest
        or coarse_receipt.get("schema")
        != "carbon.scorelab.public-coarse-construction.v1"
        or coarse_receipt.get("scope") != scope
        or coarse_receipt.get("role") != "PUBLIC_CONSTRUCTION_DISCOVERY_ONLY"
        or coarse_receipt.get("plan_digest") != expected_plan_digest
        or coarse_receipt.get("training_jsonl_digest") != _sha(coarse_raw)
        or _sha(anchors_raw) != expected_anchors_sha256
    ):
        raise tasks.TaskError("coarse bytes, receipt, role or anchor bytes differ")
    if scope == "PUBLIC_DEVELOPMENT" and (
        expected_anchors_sha256 != "sha256:" + ANCHORS_SHA
        or coarse_receipt.get("source_digest") != "sha256:" + SOURCE_SHA
        or coarse_receipt.get("registry_digest") != "sha256:" + REGISTRY_SHA
        or coarse_receipt.get("base_registry_digest") != "sha256:" + BASE_REGISTRY_SHA
    ):
        raise tasks.TaskError("registered public construction sources required")
    spec = json.loads(anchors_raw)
    if (
        spec.get("schema") != "carbon.scorelab.public-train-anchor-inputs.v1"
        or spec.get("source_plan_sha256") != TRAIN_PLAN_SHA
        or spec.get("anchor_count") != 9
        or len(spec.get("anchors", ())) != 9
    ):
        raise tasks.TaskError("frozen nine TRAIN anchors required")
    jobs = {}
    seen_inputs, indices = set(), []
    excluded = {
        tuple(j[k] for k in INPUTS)
        for stage in ("calibration-pilot", "calibration-rest", "evaluation")
        for j in acquisition_inputs(
            plan, expected_digest=expected_plan_digest, stage=stage
        )["jobs"]
    }
    for job in spec["anchors"]:
        key = tuple(job.get(k) for k in INPUTS)
        index, jid = job.get("source_plan_index"), job.get("case_id")
        if (
            not all(producer._finite(v) for v in key)
            or key[-1] != 0.1
            or key[3] not in (1, 2, 4)
            or job.get("refined") is not False
            or producer._rung(job)[0] != 1
            or type(index) is not int
            or index < 0
            or type(jid) is not str
            or not jid
            or jid in jobs
            or key in seen_inputs
            or key in excluded
        ):
            raise tasks.TaskError(
                "unique disjoint standard-rung TRAIN anchors required"
            )
        jobs[jid] = job
        seen_inputs.add(key)
        indices.append(index)
    if indices != sorted(set(indices)):
        raise tasks.TaskError("registered TRAIN source order required")
    producer._fields(
        manifest,
        (
            "schema",
            "scope",
            "role",
            "plan_digest",
            "source_pins_digest",
            "anchors_sha256",
            "observer",
            "chunks",
        ),
        "TRAIN manifest",
    )
    if (
        manifest["schema"] != ANCHOR_MANIFEST
        or manifest["scope"] != scope
        or manifest["role"] != "PUBLIC_TRAIN"
        or manifest["plan_digest"] != expected_plan_digest
        or manifest["source_pins_digest"] != expected_source_pins_digest
        or manifest["anchors_sha256"] != expected_anchors_sha256
        or manifest["observer"] != producer._observer(plan, source_pins)
    ):
        raise tasks.TaskError("TRAIN role, observer or registered identity differs")
    found, bindings = _anchor_rows(manifest, raw_chunks, jobs, plan, source_pins, scope)
    records = [json.loads(line) for line in coarse_raw.splitlines() if line.strip()]
    if len(records) != coarse_receipt.get("offered_training_rows"):
        raise tasks.TaskError("coarse offered count differs")
    coarse_keys = set()
    for row in records:
        if (
            row.get("schema") != "carbon.battery-v3.train-record.v1"
            or set(row.get("inputs", ()))
            != {"c1", "c2", "switch_v", "cooling", "ambient_c", "soc0"}
            or set(row.get("outputs", ())) != set(QUANTITIES)
            or bool(row.get("fixture", False)) != (scope == "SYNTHETIC_FIXTURE")
        ):
            raise tasks.TaskError("coarse TRAIN schema or fixture scope differs")
        values = row["inputs"]
        key = tuple(
            values[k] for k in ("c1", "c2", "switch_v", "cooling", "ambient_c", "soc0")
        )
        if (
            not all(producer._finite(v) for v in key)
            or key in excluded
            or key in coarse_keys
            or key in seen_inputs
        ):
            raise tasks.TaskError("coarse inputs duplicate or overlap reserved roles")
        coarse_keys.add(key)
    ledger = []
    for jid, job in jobs.items():
        extracted = producer._extract(found.get(jid))
        values = extracted["values"]
        eligible = extracted["state"] == "EXTRACTED" and all(
            producer._finite(values[q]) for q in QUANTITIES
        )
        # A failed programme can contain partial finite quantities. It still
        # cannot enter TRAIN or extend support; retain state in the sidecar.
        outputs = values if eligible else dict.fromkeys(QUANTITIES)
        row = {
            "schema": "carbon.battery-v3.train-record.v1",
            "case_id": jid,
            "source": "registered public TRAIN anchor; construction only",
            "role": "PUBLIC_TRAIN",
            "source_manifest_digest": expected_manifest_digest,
            "inputs": dict(
                zip(
                    ("c1", "c2", "switch_v", "cooling", "ambient_c", "soc0"),
                    (job[k] for k in INPUTS),
                )
            ),
            "outputs": outputs,
            "label_state": extracted["state"],
        }
        if scope == "SYNTHETIC_FIXTURE":
            row["fixture"] = True
        records.append(row)
        ledger.append(
            {
                "case_id": jid,
                "source_plan_index": job["source_plan_index"],
                "job_digest": tasks.digest(job),
                "eligible": eligible,
                **extracted,
                "source": bindings.get(jid),
            }
        )
    data = b"".join(
        (json.dumps(row, sort_keys=True, allow_nan=False) + "\n").encode()
        for row in records
    )
    receipt = {
        "schema": "carbon.scorelab.public-train-combined.v1",
        "scope": scope,
        "role": "PUBLIC_CONSTRUCTION_DISCOVERY_ONLY",
        "plan_digest": expected_plan_digest,
        "source_pins_digest": expected_source_pins_digest,
        "coarse_receipt_digest": expected_coarse_receipt_digest,
        "coarse_jsonl_digest": _sha(coarse_raw),
        "anchors_sha256": expected_anchors_sha256,
        "anchor_manifest_digest": expected_manifest_digest,
        "source_plan_sha256": TRAIN_PLAN_SHA,
        "coarse_offered": len(coarse_keys),
        "anchors_offered": len(jobs),
        "anchors_eligible": sum(row["eligible"] for row in ledger),
        "anchor_ledger": ledger,
        "calibration_evaluation_exclusions": coarse_receipt[
            "calibration_evaluation_exclusions"
        ],
        "training_jsonl_digest": _sha(data),
        "offered_training_rows": len(records),
        "coarse_rows_claimed_as_original_TRAIN_completion": 0,
        "numerical_evaluation_reference": False,
        "qualification": False,
    }
    return data, {**receipt, "receipt_digest": tasks.digest(receipt)}


def _anchor_rows(manifest, raw_chunks, jobs, plan, source_pins, scope):
    """Authenticate TRAIN-only source mappings; reuse the registered extractor."""
    from . import owner_v3_panel_export as producer

    if type(raw_chunks) is not dict or type(manifest["chunks"]) is not list:
        raise tasks.TaskError("TRAIN raw chunks required")
    found, bindings, chunk_ids = {}, {}, set()
    source_files = {p: source_pins["files"][p] for p in producer.SOURCES}
    for chunk in manifest["chunks"]:
        producer._fields(
            chunk,
            ("id", "sha256", "role", "source_commit", "source_files", "rows"),
            "TRAIN chunk",
        )
        cid = chunk["id"]
        if type(cid) is not str or not cid or cid in chunk_ids:
            raise tasks.TaskError("unique TRAIN chunk identity required")
        chunk_ids.add(cid)
        raw = raw_chunks.get(cid)
        if (
            type(raw) is not bytes
            or _sha(raw) != chunk["sha256"]
            or chunk["role"] != "PUBLIC_TRAIN"
            or chunk["source_files"] != source_files
            or type(chunk["source_commit"]) is not str
            or not re.fullmatch(r"[0-9a-f]{40}", chunk["source_commit"])
        ):
            raise tasks.TaskError("TRAIN raw bytes, role or producer source differs")
        lines = {n: line for n, line in enumerate(raw.splitlines(), 1) if line.strip()}
        mapped = set()
        for mapping in chunk["rows"]:
            producer._fields(
                mapping, ("line", "job_id", "case_id"), "TRAIN row mapping"
            )
            n, jid = mapping["line"], mapping["job_id"]
            if (
                type(n) is not int
                or n not in lines
                or n in mapped
                or jid not in jobs
                or jid in found
            ):
                raise tasks.TaskError("unique registered TRAIN source mapping required")
            mapped.add(n)
            record, job = json.loads(lines[n]), jobs[jid]
            if (
                type(record) is not dict
                or record.get("case_id") != mapping["case_id"]
                or record.get("schema") != "carbon.battery.feasibility02-record.v1"
                or (
                    scope == "PUBLIC_DEVELOPMENT"
                    and (
                        record.get("fixture")
                        or record.get("scope") == "SYNTHETIC_FIXTURE"
                    )
                )
                or any(
                    not producer._finite(record.get(k)) or record[k] != job[k]
                    for k in INPUTS
                )
                or producer._rung(record)[0] != 1
            ):
                raise tasks.TaskError(
                    "TRAIN source inputs, scope or standard rung differs"
                )
            provenance = record.get("solver_provenance", {})
            if (
                provenance.get("schema") != "carbon.battery.solver-provenance.v1"
                or provenance.get("solver_image", "").split("@")[-1]
                != plan["image_digest"]
                or provenance.get("overlay_lock_sha256")
                != "sha256:" + plan["overlay_sha256"]
                or provenance.get("overlay_lock")
                != "scripts/dev/exam_design/locks/battery-overlay.lock.json"
                or provenance.get("pybamm") != "26.8.0.0"
            ):
                raise tasks.TaskError("TRAIN solver provenance differs")
            found[jid] = record
            bindings[jid] = {
                "chunk": cid,
                "chunk_sha256": chunk["sha256"],
                "line": n,
                "source_case_id": record["case_id"],
                "source_commit": chunk["source_commit"],
                "source_files": source_files,
                "raw_row_sha256": _sha(lines[n]),
                "solver_provenance_digest": tasks.digest(provenance),
                "core_s": record.get("core_s"),
                "wall_s": record.get("wall_s"),
            }
        if mapped != set(lines):
            raise tasks.TaskError("unmapped TRAIN raw lines")
    if chunk_ids != set(raw_chunks):
        raise tasks.TaskError("unregistered TRAIN raw chunk")
    return found, bindings
