"""Closed guarded419 DEVELOPMENT EVAL producer, never a solver or dispatch grant.

Historical producer acceptance is unchanged. This adapter reuses extraction,
numerics and indexed consumers, with prospective nominal context and real CAL.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from carbon.design_search import tasks
from scripts.dev.battery import guarded_reference as guard
from scripts.dev.score_lab import owner_v3 as owner
from scripts.dev.score_lab import owner_v3_numerics as numerics
from scripts.dev.score_lab import owner_v3_panel_export as legacy

MODULE = "scripts/dev/score_lab/guarded419_eval.py"
CONTEXT_MODULE = "scripts/dev/score_lab/guarded419_context.py"
CAL_MODULE = "scripts/dev/score_lab/guarded419_calibration_continue.py"
REGISTRATION_FILE = "Business/research/score-lab-campaign-01/n1-diagnostic-guard419-v1/registration.json"
PLAN_FILE = "Business/research/score-lab-campaign-01/acquisition-v1/acquisition.json"
PLAN_SHA = "524230184fbbcffe2fb8b67e9f784fc75ba790a6e6509b88d01a896c2cb2c73f"
JOB = "battery-v3-job-guard419-dev-v1"
COHORT = "battery-v3-scorelab-guard419-stage128-dev-v1"
OBSERVER = "carbon.scorelab.battery-v3.guarded419-eval-observer.v1"
DATASET = "carbon.scorelab.battery-v3.guarded419-eval60.v1"
ADMISSION = "carbon.scorelab.guarded419.eval-admission.v1"
SCHEMA = "carbon.scorelab.guarded419.eval-inputs.v1"
EXPORT = "carbon.scorelab.guarded419.eval-export.v1"
RECORD = "carbon.battery.guarded419-eval-feasibility-record.v1"
PINS = "carbon.scorelab.guarded419-eval-source-pins.v1"
PRETRUTH = "carbon.scorelab.guarded419.pretruth-cohort.v1"
CANDIDATE_VIEW = legacy.CANDIDATE_VIEW
SCOPES = ("PUBLIC_DEVELOPMENT", "SYNTHETIC_FIXTURE")
REQUIRED_SOURCES = {
    *guard.REQUIRED_SOURCES,
    MODULE,
    CONTEXT_MODULE,
    CAL_MODULE,
    REGISTRATION_FILE,
}
RECIPES = ("default", "small", "wide", "deep", "short", "lower-lr")
SEEDS = (11, 29, 47)
OLD_TRAIN_SHA = "24fafa81bf528ca11606b64183bd8a54b5dc83c9478878c38b31ed393e1dd352"
_TOKEN = object()


class PrerequisiteUnavailable(tasks.TaskError):
    """Real context/CAL API is absent; not failed reference or accepted data."""


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _hex(value, size=64):
    if type(value) is not str or not re.fullmatch(
        r"[0-9a-f]{" + str(size) + "}", value
    ):
        raise tasks.TaskError("exact raw source/content hash required")
    return value


def _digest(value):
    if type(value) is not str or not value.startswith("sha256:"):
        raise tasks.TaskError("canonical content digest required")
    _hex(value[7:])


def _context(context):
    try:
        from scripts.dev.score_lab import guarded419_context as binding
    except ImportError as exc:
        raise PrerequisiteUnavailable("guarded419 context is not integrated") from exc
    registration = binding.validate(context)
    if (
        binding.JOB != JOB
        or binding.EVAL_OBSERVER != OBSERVER
        or registration["protocol_id"] != guard.METHOD_ID
    ):
        raise tasks.TaskError("exact guarded419 diagnostic context required")
    return binding, registration


def input_plan():
    """Existing input-only plan, exactly job changed; no data reclassification."""
    raw = (Path(__file__).resolve().parents[3] / PLAN_FILE).read_bytes()
    if _sha(raw) != PLAN_SHA:
        raise tasks.TaskError("frozen original acquisition input bytes differ")
    return {**json.loads(raw), "job": JOB}


def _plan(plan, expected):
    legacy._digest(plan, expected, "guarded input plan")
    if tasks.digest(plan) != tasks.digest(input_plan()):
        raise tasks.TaskError("frozen plan may change job only, never menu/law/seed")


def _worker_jobs(original):
    """Prospective metadata only; shared worker must separately admit this ID."""
    result = []
    old_prefix, new_prefix = "scorelab-v3:", "scorelab-v3:guarded419-v1:"
    for job in original:
        legacy._fields(
            job,
            (
                "case_id",
                "c1",
                "c2",
                "switch_voltage_v",
                "h_multiplier",
                "t_amb_c",
                "soc0",
                "refined",
                "rung",
            ),
            "input-only EVAL job",
        )
        cid = job["case_id"]
        if type(cid) is not str:
            raise tasks.TaskError("registered input identity required")
        if cid.startswith(new_prefix + "eval:"):
            parent = old_prefix + cid[len(new_prefix) :]
        elif cid.startswith(old_prefix + "eval:"):
            parent = cid
            cid = new_prefix + cid[len(old_prefix) :]
        else:
            raise tasks.TaskError("closed EVAL input namespace required")
        result.append(
            {
                **job,
                "case_id": cid,
                "parent_input_case_id": parent,
                "reference_method": guard.METHOD_ID,
                "reference_method_digest": tasks.digest(guard.METHOD),
                "reference_admission": ADMISSION,
                "reference_dataset": DATASET,
                "reference_role": "PUBLIC_EVALUATION",
            }
        )
    return result


def jobs(plan, *, expected_plan_digest, context, refinement_job_ids=()):
    _context(context)
    _plan(plan, expected_plan_digest)
    base = _worker_jobs(
        owner.acquisition_inputs(
            plan,
            expected_digest=expected_plan_digest,
            stage="evaluation",
            context=context,
        )["jobs"]
    )
    possible = _worker_jobs(
        owner.acquisition_inputs(
            plan,
            expected_digest=expected_plan_digest,
            stage="refinement",
            context=context,
        )["jobs"]
    )
    by_id = {j["case_id"]: j for j in possible}
    if (
        type(refinement_job_ids) not in (list, tuple)
        or len(set(refinement_job_ids)) != len(refinement_job_ids)
        or set(refinement_job_ids) - set(by_id)
    ):
        raise tasks.TaskError("registered conditional80 input IDs required")
    # Preserve frozen input order, not caller-supplied refinement reordering.
    chosen = [j for j in possible if j["case_id"] in refinement_job_ids]
    if list(refinement_job_ids) != [j["case_id"] for j in chosen]:
        raise tasks.TaskError("conditional80 order differs from frozen inputs")
    return base + chosen


def observer(plan, files):
    return {
        "id": OBSERVER,
        "protocol_id": guard.METHOD_ID,
        "method_digest": tasks.digest(guard.METHOD),
        "dataset_id": DATASET,
        "admission_id": ADMISSION,
        "clock": plan["clock"],
        "cycles": 30,
        "soc0": 0.1,
        "initial_state": "FRESH",
        "source_files": dict(files),
    }


def validate_job(
    job,
    *,
    plan,
    expected_plan_digest,
    source_pins,
    expected_source_pins_digest,
    context,
    refinement_job_ids=(),
):
    """Registered input membership, never acquisition or physical authority.

    The dispatcher supplies the independently bound Root registration bundle,
    not context/source/observer fields inferred from the untrusted job. Optional
    mesh80 is absent unless its ordered IDs were explicitly registered.
    """
    _source_pins(source_pins, expected_source_pins_digest, context)
    offered = jobs(
        plan,
        expected_plan_digest=expected_plan_digest,
        context=context,
        refinement_job_ids=refinement_job_ids,
    )
    if type(job) is not dict:
        raise tasks.TaskError("exact registered guarded EVAL job required")
    try:
        digest = tasks.digest(job)
    except (TypeError, ValueError) as exc:
        raise tasks.TaskError("exact registered guarded EVAL job required") from exc
    if not any(digest == tasks.digest(registered) for registered in offered):
        raise tasks.TaskError("exact registered guarded EVAL job required")


def job_context(
    job,
    *,
    plan,
    expected_plan_digest,
    source_pins,
    expected_source_pins_digest,
    context,
    refinement_job_ids=(),
):
    """Return requested record metadata after exact registered-job validation.

    This does not validate CAL/pretruth, release a stage, attest source execution
    or supply operative physical proof. The actual registered runner and raw
    EVAL admission must still establish those independent requirements.
    """
    validate_job(
        job,
        plan=plan,
        expected_plan_digest=expected_plan_digest,
        source_pins=source_pins,
        expected_source_pins_digest=expected_source_pins_digest,
        context=context,
        refinement_job_ids=refinement_job_ids,
    )
    return {
        "record_schema": RECORD,
        "reference_identity": legacy._copy(observer(plan, source_pins["files"])),
    }


def prediction_view(registered, *, scope, context):
    _context(context)
    owner._validate(registered, context=context)
    if scope not in SCOPES:
        raise tasks.TaskError("public development/fixture view only")
    panels = []
    for row in registered["indices"]:
        sub = row["task"]
        if {sub["objective"]["quantity"]} | {
            l["quantity"] for l in sub["limits"]
        } != set(legacy.QUANTITIES):
            raise tasks.TaskError("all five observables required")
        panels.append(
            {
                "index_value": row["index_value"],
                "panel": [
                    {
                        "candidate": candidate,
                        "condition": condition["id"],
                        "observables": list(legacy.QUANTITIES),
                    }
                    for candidate in sub["candidates"]
                    for condition in sub["conditions"]
                ],
            }
        )
    body = {
        "schema": CANDIDATE_VIEW,
        "scope": scope,
        "family": "battery-v3",
        "questions": [
            {
                "case": registered["task_id"],
                "task": legacy._copy(registered),
                "reference": panels,
            }
        ],
    }
    return {**body, "export_digest": tasks.digest(body)}


def population_view(plan, *, expected_plan_digest, scope, context):
    _context(context)
    _plan(plan, expected_plan_digest)
    draws = owner.population_tasks(
        plan, expected_plan_digest=expected_plan_digest, count=64, context=context
    )
    body = {
        "schema": CANDIDATE_VIEW,
        "scope": scope,
        "family": "battery-v3",
        "questions": [
            prediction_view(d["task"], scope=scope, context=context)["questions"][0]
            for d in draws
        ],
    }
    return {**body, "export_digest": tasks.digest(body)}


def _pretruth(
    raw, expected_sha256, *, scope, context, draws_digest, view_digest, plan_digest
):
    """Identity join only; Root custody proves chronology, CLI joins raw receipts."""
    binding, _ = _context(context)
    if type(raw) is not bytes or _sha(raw) != _hex(expected_sha256):
        raise tasks.TaskError("independently prebound pretruth bytes required")
    doc = json.loads(raw)
    legacy._fields(
        doc,
        (
            "schema",
            "scope",
            "job",
            "context_registration_sha256",
            "draws_digest",
            "candidate_view_digest",
            "bank_plan_digest",
            "members",
        ),
        "pretruth",
    )
    if (
        doc["schema"] != PRETRUTH
        or doc["scope"] != scope
        or doc["job"] != JOB
        or doc["context_registration_sha256"] != binding.REGISTRATION_SHA256
        or doc["draws_digest"] != draws_digest
        or doc["candidate_view_digest"] != view_digest
        or doc["bank_plan_digest"] != plan_digest
    ):
        raise tasks.TaskError("pretruth question/bank/diagnostic context differs")
    _members(doc["members"])
    return doc


def pretruth_receipt(raw, expected_sha256, plan, expected_plan_digest, scope, context):
    """Input-only identity checks for the existing CLI, not fit/CAL evidence."""
    _context(context)
    _plan(plan, expected_plan_digest)
    draws = owner.population_tasks(
        plan, expected_plan_digest=expected_plan_digest, count=64, context=context
    )
    view = population_view(
        plan, expected_plan_digest=expected_plan_digest, scope=scope, context=context
    )
    return _pretruth(
        raw,
        expected_sha256,
        scope=scope,
        context=context,
        draws_digest=tasks.digest(draws),
        view_digest=view["export_digest"],
        plan_digest=expected_plan_digest,
    )


def _members(members):
    """Unsealed roster validation only, never actual fit/chronology evidence."""
    expected = {(r, s) for r in RECIPES for s in SEEDS}
    seen = set()
    ids = set()
    if type(members) is not list or len(members) != len(expected):
        raise tasks.TaskError("all eighteen final offers required, including failures")
    for member in members:
        legacy._fields(
            member,
            (
                "id",
                "recipe",
                "seed",
                "train_sha256",
                "construction_receipt_digest",
                "fit_receipt_sha256",
                "predictions_sha256",
                "commitments_sha256",
                "commitment_receipt_sha256",
                "kit",
                "fit_source",
            ),
            "pretruth member",
        )
        key = (member["recipe"], member["seed"])
        if (
            type(member["seed"]) is not int
            or key not in expected
            or key in seen
            or member["id"] != f"{COHORT}:{key[0]}:seed{key[1]}"
            or member["id"] in ids
        ):
            raise tasks.TaskError("new fixed recipe/seed/model roster required")
        seen.add(key)
        ids.add(member["id"])
        for field in (
            "train_sha256",
            "fit_receipt_sha256",
            "predictions_sha256",
            "commitments_sha256",
            "commitment_receipt_sha256",
        ):
            _hex(member[field])
        _hex(member["fit_source"], 40)
        _digest(member["construction_receipt_digest"])
        if (
            member["train_sha256"] == OLD_TRAIN_SHA
            or type(member["kit"]) is not str
            or not member["kit"].startswith(
                "carbon.battery-v3.guard419.stage128.kit.v1:"
            )
        ):
            raise tasks.TaskError(
                "old TRAIN/kit/probe cannot enter guarded final cohort"
            )
        _digest(
            member["kit"].removeprefix("carbon.battery-v3.guard419.stage128.kit.v1:")
        )
    if any(
        len({m[field] for m in members}) != 1
        for field in ("train_sha256", "construction_receipt_digest", "kit")
    ):
        raise tasks.TaskError(
            "all final models require one common construction binding"
        )


def _source_pins(pins, expected, context):
    binding, _ = _context(context)
    legacy._digest(pins, expected, "guarded source pins")
    legacy._fields(
        pins, ("schema", "scope", "execution_source", "files"), "guarded source pins"
    )
    if (
        pins["schema"] != PINS
        or pins["scope"] != "DEVELOPMENT_ONLY"
        or type(pins["files"]) is not dict
        or set(pins["files"]) != REQUIRED_SOURCES
    ):
        raise tasks.TaskError("closed complete guarded source inventory required")
    _hex(pins["execution_source"], 40)
    for value in pins["files"].values():
        _hex(value)
    if pins["files"][REGISTRATION_FILE] != binding.REGISTRATION_SHA256:
        raise tasks.TaskError("source registration differs from nominal context")


def _cal_api():
    try:
        from scripts.dev.score_lab import guarded419_calibration_continue as cal
    except ImportError as exc:
        raise PrerequisiteUnavailable(
            "authenticated CAL15 adapter is not integrated"
        ) from exc
    if not hasattr(cal, "validate_for"):
        raise PrerequisiteUnavailable("CAL15 nominal interface is not integrated")
    return cal


def calibration_from_files(spec, *, load, scope, context):
    """Delegate to the real CAL loader, never to an alternate evidence path.

    In an N1 bundle, CAL entry ``path`` values are logical ``manifest.files``
    keys. ``load`` resolves only that registry; physical paths are not aliases.
    Standalone callers own their loader namespace and its public-root boundary.
    """
    _context(context)
    if scope not in SCOPES:
        raise tasks.TaskError("bounded development calibration scope required")
    if type(spec) is not dict or spec.get("scope") != scope:
        raise tasks.TaskError("CAL file specification scope differs")
    for name in ("expected_binding_digest", "expected_manifest_digest"):
        _digest(spec.get(name))
    cal = _cal_api()
    if not callable(getattr(cal, "from_files", None)) or not callable(
        getattr(cal, "validate_for", None)
    ):
        raise PrerequisiteUnavailable("CAL15 nominal file interface is not integrated")
    evidence = cal.from_files(spec, load=load, scope=scope)
    # A returned mapping/PASS flag is not nominal evidence. The later early
    # gate also checks the bank's independent pins and scientific source map.
    cal.validate_for(
        evidence,
        expected_binding_digest=spec["expected_binding_digest"],
        expected_manifest_digest=spec["expected_manifest_digest"],
        scope=scope,
    )
    return evidence


def _calibration(evidence, manifest, pins, context):
    """No callable stub/flag if the real CAL15 nominal API does not yet exist."""
    _context(context)
    expected = manifest["calibration"]
    legacy._fields(expected, ("binding_digest", "manifest_digest"), "CAL15 pins")
    for value in expected.values():
        _digest(value)
    cal = _cal_api()
    report = cal.validate_for(
        evidence,
        expected_binding_digest=expected["binding_digest"],
        expected_manifest_digest=expected["manifest_digest"],
        scope=manifest["scope"],
    )
    if (
        report["protocol_id"] != guard.METHOD_ID
        or report["method_digest"] != tasks.digest(guard.METHOD)
        or report["status"] != "COMPATIBLE_FOR_REGISTERED_CALIBRATION_CASES"
        or report["expected_case_count"] != 15
        or report.get("missing_cases")
        or report.get("failed_cases")
    ):
        raise tasks.TaskError("actual complete compatible guarded CAL15 required")
    for path in guard.REQUIRED_SOURCES - {
        "scripts/dev/battery/feasibility02.py",
        guard.MODULE,
    }:
        if report["source_files"][path] != pins["files"][path]:
            raise tasks.TaskError("CAL/EVAL scientific source differs")
    return report


def validate_calibration(evidence, manifest, source_pins, *, context):
    """Early full-CAL gate for CLI before it even loads EVAL raw bytes.

    The builder revalidates this same nominal prerequisite before sealing.
    A caller dictionary or a partial delivery is never a CAL certificate.
    """
    return _calibration(evidence, manifest, source_pins, context)


def _raw_rows(manifest, raw_chunks, offered, pins, expected_observer):
    """Unsealed raw authentication; cannot mint EVAL or replace CAL evidence."""
    if type(manifest["chunks"]) is not list or type(raw_chunks) is not dict:
        raise tasks.TaskError("registered raw EVAL chunks required")
    jobs_by_id = {j["case_id"]: j for j in offered}
    found, proof, tracking = {}, {}, {}
    chunks = set()
    for chunk in manifest["chunks"]:
        legacy._fields(
            chunk,
            ("id", "sha256", "role", "source_commit", "source_files", "rows"),
            "EVAL chunk",
        )
        cid = chunk["id"]
        if type(cid) is not str or not cid or cid in chunks or cid not in raw_chunks:
            raise tasks.TaskError("unique supplied EVAL chunk required")
        chunks.add(cid)
        raw = raw_chunks[cid]
        if (
            type(raw) is not bytes
            or _sha(raw) != chunk["sha256"]
            or chunk["role"] != "PUBLIC_EVALUATION"
            or chunk["source_commit"] != pins["execution_source"]
            or chunk["source_files"] != pins["files"]
        ):
            raise tasks.TaskError("raw EVAL source/hash/role differs")
        lines = raw.splitlines()
        mapped = set()
        for mapping in chunk["rows"]:
            legacy._fields(mapping, ("line", "job_id", "case_id"), "EVAL mapping")
            line, jid = mapping["line"], mapping["job_id"]
            if (
                type(line) is not int
                or not 1 <= line <= len(lines)
                or line in mapped
                or jid not in jobs_by_id
                or jid in found
            ):
                raise tasks.TaskError("unique offered EVAL job/source line required")
            mapped.add(line)
            row = json.loads(lines[line - 1])
            job = jobs_by_id[jid]
            if (
                type(row) is not dict
                or mapping["case_id"] != jid
                or any(k not in row for k in job)
                or tasks.digest({k: row[k] for k in job}) != tasks.digest(job)
            ):
                raise tasks.TaskError("raw EVAL input/job/type identity differs")
            if manifest["scope"] == "PUBLIC_DEVELOPMENT" and (
                row.get("fixture") or row.get("scope") == "SYNTHETIC_FIXTURE"
            ):
                raise tasks.TaskError("fixture cannot become public EVAL")
            if row.get("schema") != RECORD or tasks.digest(
                row.get("reference_identity")
            ) != tasks.digest(expected_observer):
                raise tasks.TaskError("foreign EVAL schema/observer/context")
            found[jid] = row
            tracking[jid] = guard._tracking_report(
                row,
                expected_job=job,
                reference_identity=expected_observer,
                record_schema=RECORD,
                method_digest=tasks.digest(guard.METHOD),
            )
            proof[jid] = {
                "chunk": cid,
                "chunk_sha256": chunk["sha256"],
                "line": line,
                "source_case_id": row["case_id"],
                "source_commit": chunk["source_commit"],
                "source_files": chunk["source_files"],
                "raw_row_sha256": _sha(lines[line - 1]),
                "job_digest": tasks.digest(job),
            }
        if mapped != {i for i, l in enumerate(lines, 1) if l.strip()}:
            raise tasks.TaskError("unmapped EVAL raw lines forbidden")
    if set(raw_chunks) != chunks:
        raise tasks.TaskError("unregistered EVAL chunks forbidden")
    extracted = {}
    for jid in jobs_by_id:
        result = legacy._extract(found.get(jid))
        if tracking.get(jid, {}).get("status") != "TRACKING_COMPATIBLE":
            result = {
                **result,
                "state": "MISSING" if jid not in found else "REFERENCE_UNRESOLVED",
                "values": dict.fromkeys(legacy.QUANTITIES),
            }
        extracted[jid] = result
    return extracted, proof, tracking


def _reduce(registered, offered, extracted):
    """Reuse existing pair enclosures; preserve all actions and zero-weight bands."""
    lookup = {}
    for index in registered["indices"]:
        sub = index["task"]
        if len(sub["conditions"]) != 1:
            raise tasks.TaskError("one frozen condition per ambient required")
        for candidate, action in sub["actions"].items():
            key = (
                index["index_value"],
                (action["c1"], action["c2"], action["switch_v"], action["cooling"]),
            )
            if key in lookup:
                raise tasks.TaskError("duplicate physical EVAL action")
            lookup[key] = (candidate, sub["conditions"][0]["id"])
    evaluation = {}
    for job in offered:
        key = (job["t_amb_c"], legacy._action(job))
        if key not in lookup:
            raise tasks.TaskError("foreign physical EVAL input")
        evaluation.setdefault(key, {})[job["rung"]] = job["case_id"]
    if set(evaluation) != set(lookup):
        raise tasks.TaskError("all offered physical inputs required")
    panels = []
    enclosures = []
    pairs = []
    for index in registered["indices"]:
        band = index["index_value"]
        values = {}
        bounds = {}
        for key, rungs in evaluation.items():
            if key[0] != band:
                continue
            if not {1, 2} <= set(rungs):
                raise tasks.TaskError("mandatory20/40 rung inventory required")
            candidate, condition = lookup[key]
            ordered = sorted(rungs)
            ready = all(
                extracted[jid]["state"] == "EXTRACTED" for jid in rungs.values()
            )
            previous, finest = (extracted[rungs[r]]["values"] for r in ordered[-2:])
            pair = numerics.pair_enclosures(
                previous if ready else None,
                finest if ready else None,
                expected_policy_digest=tasks.digest(numerics.POLICY),
            )
            values[(candidate, condition)] = (
                finest if ready else dict.fromkeys(legacy.QUANTITIES)
            )
            bounds[candidate] = (
                pair["intervals"]
                if pair["status"] == "READY_OPERATIONAL_ENCLOSURES"
                else {}
            )
            pairs.append(
                {
                    "index_value": band,
                    "candidate": candidate,
                    "job_ids": list(rungs.values()),
                    "pair": pair,
                }
            )
        panels.append({"index_value": band, "values": values})
        enclosures.append({"index_value": band, "candidates": bounds})
    return panels, enclosures, pairs


class ValidatedEvidence:
    """Internal immutable provenance, not hostile in-process attestation."""

    __slots__ = ("_bytes", "_seal")

    def __new__(cls, *, _token=None, payload=None):
        if _token is not _TOKEN:
            raise tasks.TaskError("use guarded419_eval.build")
        obj = super().__new__(cls)
        object.__setattr__(obj, "_bytes", json.dumps(payload, allow_nan=False).encode())
        object.__setattr__(obj, "_seal", tasks.digest(payload))
        return obj

    def __setattr__(self, name, value):
        raise AttributeError("validated EVAL evidence is immutable")

    def _snapshot(self):
        value = json.loads(self._bytes)
        legacy._digest(value, self._seal, "EVAL object")
        return value

    @property
    def receipt(self):
        return self._snapshot()["receipt"]

    @property
    def references(self):
        return [
            {
                "index_value": p["index_value"],
                "values": {(c, k): v for c, k, v in p["rows"]},
            }
            for p in self._snapshot()["reference_rows"]
        ]

    @property
    def enclosures(self):
        return self._snapshot()["enclosures"]

    @property
    def prediction_view(self):
        return self._snapshot()["prediction_view"]


def build(
    registered,
    *,
    plan,
    expected_plan_digest,
    source_pins,
    expected_source_pins_digest,
    manifest,
    expected_manifest_digest,
    raw_chunks,
    context,
    calibration_evidence,
    pretruth,
    expected_pretruth_sha256,
):
    binding, _ = _context(context)
    _plan(plan, expected_plan_digest)
    _source_pins(source_pins, expected_source_pins_digest, context)
    legacy._digest(manifest, expected_manifest_digest, "guarded EVAL manifest")
    legacy._fields(
        manifest,
        (
            "schema",
            "scope",
            "role",
            "task_digest",
            "plan_digest",
            "source_pins_digest",
            "policy_digest",
            "observer",
            "refinement_job_ids",
            "chunks",
            "diagnostic_context",
            "protocol_id",
            "method_digest",
            "dataset_id",
            "calibration",
            "pretruth_sha256",
        ),
        "guarded EVAL manifest",
    )
    expected_observer = observer(plan, source_pins["files"])
    if (
        manifest["schema"] != SCHEMA
        or manifest["scope"] not in SCOPES
        or manifest["role"] != "HELDOUT_REFERENCE"
        or manifest["task_digest"] != registered["task_digest"]
        or manifest["plan_digest"] != expected_plan_digest
        or manifest["source_pins_digest"] != expected_source_pins_digest
        or manifest["policy_digest"] != tasks.digest(numerics.POLICY)
        or plan["numerical_policy_digest"] != manifest["policy_digest"]
        or manifest["observer"] != expected_observer
        or manifest["diagnostic_context"] != binding.metadata(context)
        or manifest["protocol_id"] != guard.METHOD_ID
        or manifest["method_digest"] != tasks.digest(guard.METHOD)
        or manifest["dataset_id"] != DATASET
        or manifest["pretruth_sha256"] != expected_pretruth_sha256
    ):
        raise tasks.TaskError("closed guarded EVAL identity differs")
    draws = owner.population_tasks(
        plan, expected_plan_digest=expected_plan_digest, count=64, context=context
    )
    if registered not in [d["task"] for d in draws]:
        raise tasks.TaskError("question is not in frozen64 guarded P draws")
    view = population_view(
        plan,
        expected_plan_digest=expected_plan_digest,
        scope=manifest["scope"],
        context=context,
    )
    cohort = _pretruth(
        pretruth,
        expected_pretruth_sha256,
        scope=manifest["scope"],
        context=context,
        draws_digest=tasks.digest(draws),
        view_digest=view["export_digest"],
        plan_digest=expected_plan_digest,
    )
    # Validate real prior evidence before touching any offered EVAL truth bytes.
    calibration = _calibration(calibration_evidence, manifest, source_pins, context)
    offered = jobs(
        plan,
        expected_plan_digest=expected_plan_digest,
        context=context,
        refinement_job_ids=manifest["refinement_job_ids"],
    )
    extracted, proof, tracking = _raw_rows(
        manifest, raw_chunks, offered, source_pins, expected_observer
    )
    panels, enclosures, pairs = _reduce(registered, offered, extracted)
    rows = legacy._reference_rows(panels)
    question_view = prediction_view(
        registered, scope=manifest["scope"], context=context
    )
    receipt = {
        "schema": EXPORT,
        "scope": manifest["scope"],
        "role": manifest["role"],
        "job": JOB,
        "diagnostic_context": binding.metadata(context),
        "protocol_id": guard.METHOD_ID,
        "dataset_id": DATASET,
        "task_digest": registered["task_digest"],
        "limits_digest": legacy._limits_digest(registered),
        "plan_digest": expected_plan_digest,
        "source_pins_digest": expected_source_pins_digest,
        "manifest_digest": expected_manifest_digest,
        "policy_digest": manifest["policy_digest"],
        "observer": expected_observer,
        "observer_digest": tasks.digest(expected_observer),
        "method": guard.METHOD,
        "method_digest": tasks.digest(guard.METHOD),
        "execution_source": source_pins["execution_source"],
        "source_files": source_pins["files"],
        "reference_digest": tasks.digest(rows),
        "enclosure_digest": tasks.digest(enclosures),
        "prediction_view_digest": question_view["export_digest"],
        "population_view_digest": view["export_digest"],
        "draws_digest": cohort["draws_digest"],
        "pretruth_sha256": expected_pretruth_sha256,
        "pretruth_member_ids": [m["id"] for m in cohort["members"]],
        "pretruth_authentication": "ROOT_PREBOUND_BYTES_CLI_RAW_MEMBER_JOIN_CUSTODY_CHRONOLOGY",
        "calibration": calibration,
        "calibration_binding": manifest["calibration"],
        "per_evaluation": pairs,
        "per_job": [
            {
                "job": j,
                "source": proof.get(j["case_id"]),
                "tracking": tracking.get(j["case_id"]),
                **extracted[j["case_id"]],
            }
            for j in offered
        ],
        "source_bindings_digest": tasks.digest(proof),
        "qualification": False,
        "physical_confidence_interval": False,
        "delivery_authentication": "ROOT_PREBOUND_PUBLIC_MANIFEST_REQUIRED",
    }
    receipt["receipt_digest"] = tasks.digest(receipt)
    return ValidatedEvidence(
        _token=_TOKEN,
        payload={
            "receipt": receipt,
            "reference_rows": rows,
            "enclosures": enclosures,
            "prediction_view": question_view,
        },
    )


def validate_for(
    evidence, registered, references, enclosures, *, scope="PUBLIC_DEVELOPMENT", context
):
    binding, _ = _context(context)
    if type(evidence) is not ValidatedEvidence:
        raise tasks.TaskError(
            "nominal guarded EVAL evidence required, never T9/TRAIN/legacy/dict"
        )
    owner._validate(registered, context=context)
    receipt = evidence.receipt
    legacy._digest(
        {k: v for k, v in receipt.items() if k != "receipt_digest"},
        receipt["receipt_digest"],
        "guarded EVAL receipt",
    )
    if (
        scope not in SCOPES
        or receipt["scope"] != scope
        or receipt["job"] != JOB
        or receipt["diagnostic_context"] != binding.metadata(context)
        or receipt["task_digest"] != registered["task_digest"]
        or receipt["limits_digest"] != legacy._limits_digest(registered)
        or receipt["reference_digest"]
        != tasks.digest(legacy._reference_rows(references))
        or receipt["enclosure_digest"] != tasks.digest(enclosures)
        or receipt["policy_digest"] != tasks.digest(numerics.POLICY)
        or receipt["observer"]["id"] != OBSERVER
        or receipt["observer_digest"] != tasks.digest(receipt["observer"])
        or receipt["method_digest"] != tasks.digest(guard.METHOD)
        or receipt["prediction_view_digest"]
        != prediction_view(registered, scope=scope, context=context)["export_digest"]
    ):
        raise tasks.TaskError("consumer guarded EVAL context/task/reference differs")
    return receipt
