"""Prospective DEVELOPMENT v3 export from authenticated feasibility02 JSONL.

This pure bridge performs no file access, solve, fit or dispatch. Root binds
the public input manifest before outcomes and authenticates its delivery.
Matching digests establish matched bytes, not a signature or qualification.

``build(registered, plan=..., expected_plan_digest=..., source_pins=...,
expected_source_pins_digest=..., manifest=..., expected_manifest_digest=...,
raw_chunks={chunk_id: bytes})`` returns ``ValidatedEvidence``. Its references,
enclosures and receipt properties return copies. ``validate_for`` checks the
exact consumer inputs; the consumer also checks Root's prebound plan, source
pins and manifest digests. A caller-provided calibration flag is never used.

Manifest v1 has exactly: schema, scope, role, task_digest, plan_digest,
source_pins_digest, policy_digest, observer, refinement_job_ids, chunks.
Observer fields are id, clock, cycles, soc0, initial_state and source_files.
Each chunk has id, sha256, role, source_commit, source_files, rows. Each row
mapping has line (one-based physical JSONL line), job_id (canonical acquisition
job), case_id (original source identity). Every nonblank source line is mapped;
missing offered jobs stay present as MISSING. Roles are PUBLIC_CALIBRATION or
PUBLIC_EVALUATION. Fixtures use SYNTHETIC_FIXTURE scope and cannot enter PUBLIC.

The historical .005-C/filtering exporter is unchanged. This version preserves
the owner's .01-C action menu, every band, every offered row and raw failure or
NOT_REACHED state, using feasibility02_v2.measures and the registered numerical
helper without defining another enclosure formula.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from decimal import Decimal

from carbon.design_search import tasks
from scripts.dev.battery.feasibility02_v2 import measures
from scripts.dev.score_lab import owner_v3_numerics as numerics

SCHEMA = "carbon.scorelab.battery-v3.producer-inputs.v1"
EXPORT = "carbon.scorelab.battery-v3.solved-panel-export.v1"
CANDIDATE_VIEW = "carbon.development-carbon-arm.candidate-view.v1"
OBSERVER = "carbon.scorelab.battery-v3.full30-soc10-80-observer.v1"
EXPORTER = "scripts/dev/score_lab/owner_v3_panel_export.py"
NUMERICS = "scripts/dev/score_lab/owner_v3_numerics.py"
SOURCES = (
    "scripts/dev/battery/feasibility02.py",
    "scripts/dev/battery/feasibility02_v2.py",
    "carbon/battery/reference.py",
    "carbon/battery/truth_env.py",
)
QUANTITIES = tuple(sorted(numerics.QUANTITIES))
PHASES = ("cc1", "cc2", "cv", "rest_after_charge", "discharge", "rest_after_discharge")
_TOKEN = object()


def _copy(value):
    return json.loads(json.dumps(value, allow_nan=False))


def _fields(value, fields, where):
    if type(value) is not dict or set(value) != set(fields):
        raise tasks.TaskError(f"{where}: exact registered fields required")


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def _hash(value):
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _digest(value, expected, where):
    if not isinstance(expected, str) or tasks.digest(value) != expected:
        raise tasks.TaskError(f"{where}: registered digest differs")


def _limits_digest(registered):
    return tasks.digest(
        [
            {
                "index_value": r["index_value"],
                "objective": r["task"]["objective"],
                "limits": r["task"]["limits"],
            }
            for r in registered["indices"]
        ]
    )


def _reference_rows(references):
    return [
        {
            "index_value": p["index_value"],
            "rows": [[*key, value] for key, value in sorted(p["values"].items())],
        }
        for p in references
    ]


class ValidatedEvidence:
    """Immutable construction result; raw dictionaries cannot enter validate_for."""

    __slots__ = ("_bytes", "_seal")

    def __new__(cls, *, _token=None, payload=None):
        if _token is not _TOKEN:
            raise tasks.TaskError("use the producer build function")
        obj = super().__new__(cls)
        object.__setattr__(obj, "_bytes", json.dumps(payload, allow_nan=False).encode())
        object.__setattr__(obj, "_seal", tasks.digest(payload))
        return obj

    def __setattr__(self, name, value):
        raise AttributeError("validated producer evidence is immutable")

    def _snapshot(self):
        payload = json.loads(self._bytes)
        _digest(payload, self._seal, "producer object")
        return payload

    @property
    def receipt(self):
        return self._snapshot()["receipt"]

    @property
    def references(self):
        return [
            {
                "index_value": p["index_value"],
                "values": {
                    (c, condition): values for c, condition, values in p["rows"]
                },
            }
            for p in self._snapshot()["reference_rows"]
        ]

    @property
    def enclosures(self):
        return self._snapshot()["enclosures"]

    @property
    def prediction_view(self):
        return self._snapshot()["prediction_view"]


def prediction_view(registered, *, scope):
    """Input/observable inventory available before reference outcomes exist."""
    from scripts.dev.score_lab import owner_v3

    owner_v3._validate(registered)
    if scope not in ("PUBLIC_DEVELOPMENT", "SYNTHETIC_FIXTURE"):
        raise tasks.TaskError("development-only candidate view required")
    panels = []
    for row in registered["indices"]:
        subtask = row["task"]
        quantities = {subtask["objective"]["quantity"]} | {
            l["quantity"] for l in subtask["limits"]
        }
        if quantities != set(QUANTITIES):
            raise tasks.TaskError("exact five v3 observables required")
        panels.append(
            {
                "index_value": row["index_value"],
                "panel": [
                    {
                        "candidate": candidate,
                        "condition": condition["id"],
                        "observables": list(QUANTITIES),
                    }
                    for candidate in subtask["candidates"]
                    for condition in subtask["conditions"]
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
                "task": _copy(registered),
                "reference": panels,
            }
        ],
    }
    return {**body, "export_digest": tasks.digest(body)}


def _registered_jobs(plan, expected):
    # Local import avoids a cycle with the consumer's optional producer check.
    from scripts.dev.score_lab import owner_v3

    stages = {}
    for stage in ("calibration-pilot", "calibration-rest", "evaluation", "refinement"):
        stages[stage] = owner_v3.acquisition_inputs(
            plan, expected_digest=expected, stage=stage
        )["jobs"]
    return stages


def _action(job):
    return (job["c1"], job["c2"], job["switch_voltage_v"], job["h_multiplier"])


def _task_actions(registered, plan_digest, observer, evaluation):
    from scripts.dev.score_lab import owner_v3

    owner_v3._validate(registered)
    actions = {}
    expected = {(j["t_amb_c"], _action(j)) for j in evaluation}
    for row in registered["indices"]:
        sub = row["task"]
        if (
            sub["identity"]["observer_version"] != observer
            or sub["identity"]["reference_bank"] != plan_digest
            or len(sub["conditions"]) != 1
        ):
            raise tasks.TaskError(
                "registered plan, observer and one condition per band required"
            )
        limits = {l["quantity"]: l for l in sub["limits"]}
        if len(sub["limits"]) != 4 or set(limits) != set(QUANTITIES) - {"minutes"}:
            raise tasks.TaskError("all four owner-v3 hard limits required")
        for q, op, unit, lo, hi in (
            ("charging_t_max_c", "<=", "C", 42.5, 45),
            ("plating_min_v", ">=", "V", 0, 0.002),
            ("v_max_v", "<=", "V", 4.2, 4.2),
            ("q30_over_q1", ">=", "1", 0.99, 0.99),
        ):
            limit = limits[q]
            value = limit["value"]
            if (
                limit["op"] != op
                or limit["unit"] != unit
                or not _finite(value)
                or not lo <= value <= hi
            ):
                raise tasks.TaskError("hard limit differs from owner D2 support")
        grammar = sub["identity"]["action_grammar"]
        variables = {v["name"]: v for v in grammar["variables"]}
        if any(variables.get(v, {}).get("step") != 0.01 for v in ("c1", "c2")):
            raise tasks.TaskError("owner .01-C action lattice required")
        seen = set()
        for candidate, action in sub["actions"].items():
            _fields(action, ("c1", "c2", "switch_v", "cooling"), "task action")
            key = (action["c1"], action["c2"], action["switch_v"], action["cooling"])
            if any(Decimal(str(action[c])) * 100 % 1 for c in ("c1", "c2")):
                raise tasks.TaskError("action is outside owner .01-C lattice")
            banded = (row["index_value"], key)
            if banded not in expected or key in seen:
                raise tasks.TaskError(
                    "task action differs from offered evaluation menu"
                )
            seen.add(key)
            actions[banded] = (candidate, sub["conditions"][0]["id"])
        if {(row["index_value"], key) for key in seen} != {
            key for key in expected if key[0] == row["index_value"]
        }:
            raise tasks.TaskError(
                "every offered action and band must remain registered"
            )
    return actions


def _observer(plan, pins):
    return {
        "id": OBSERVER,
        "clock": plan["clock"],
        "cycles": 30,
        "soc0": 0.1,
        "initial_state": "FRESH",
        "source_files": {path: pins["files"][path] for path in SOURCES},
    }


def _rung(record):
    refined = record.get("refined")
    if type(refined) is not bool:
        raise tasks.TaskError("explicit refined input required")
    rung = record.get("rung")
    if rung is None:
        # Exact pinned feasibility02 source gives this meaning to a missing rung.
        return (2 if refined else 1), "PINNED_SOURCE_REFINED"
    if type(rung) is not int or rung not in (1, 2, 3) or refined != (rung != 1):
        raise tasks.TaskError("raw rung/refined identity differs; rung0 is not truth")
    return rung, "EXPLICIT_RUNG"


def _raw_rows(manifest, raw_chunks, jobs, source_files, plan):
    chunks = manifest["chunks"]
    if type(chunks) is not list or type(raw_chunks) is not dict:
        raise tasks.TaskError("registered raw chunks required")
    found, bindings, chunk_ids = {}, {}, set()
    for chunk in chunks:
        _fields(
            chunk,
            ("id", "sha256", "role", "source_commit", "source_files", "rows"),
            "chunk",
        )
        cid = chunk["id"]
        if type(cid) is not str or not cid or cid in chunk_ids:
            raise tasks.TaskError("unique source chunk identity required")
        chunk_ids.add(cid)
        body = raw_chunks.get(cid)
        if (
            type(body) is not bytes
            or _hash(body) != chunk["sha256"]
            or type(chunk["source_commit"]) is not str
            or not re.fullmatch(r"[0-9a-f]{40}", chunk["source_commit"])
            or chunk["source_files"] != source_files
        ):
            raise tasks.TaskError("raw bytes or pinned producer source differs")
        lines = {n: line for n, line in enumerate(body.splitlines(), 1) if line.strip()}
        mapped = set()
        for mapping in chunk["rows"]:
            _fields(mapping, ("line", "job_id", "case_id"), "row mapping")
            line, jid = mapping["line"], mapping["job_id"]
            if (
                type(line) is not int
                or line not in lines
                or line in mapped
                or jid in found
                or jid not in jobs
            ):
                raise tasks.TaskError(
                    "unique registered job/source line mapping required"
                )
            mapped.add(line)
            try:
                record = json.loads(lines[line])
            except (ValueError, UnicodeError) as exc:
                raise tasks.TaskError("invalid raw JSONL record") from exc
            if type(record) is not dict or record.get("case_id") != mapping["case_id"]:
                raise tasks.TaskError("original raw case identity differs")
            if manifest["scope"] == "PUBLIC_DEVELOPMENT" and (
                record.get("fixture") or record.get("scope") == "SYNTHETIC_FIXTURE"
            ):
                raise tasks.TaskError("fixture cannot become public evidence")
            job = jobs[jid]
            role = (
                "PUBLIC_CALIBRATION"
                if jid.startswith("scorelab-v3:cal:")
                else "PUBLIC_EVALUATION"
            )
            if chunk["role"] != role:
                raise tasks.TaskError("calibration/evaluation source roles differ")
            if record.get("schema") != "carbon.battery.feasibility02-record.v1":
                raise tasks.TaskError("legacy or foreign observer record refused")
            for key in (
                "c1",
                "c2",
                "switch_voltage_v",
                "h_multiplier",
                "t_amb_c",
                "soc0",
            ):
                if not _finite(record.get(key)) or record[key] != job[key]:
                    raise tasks.TaskError(
                        "raw action/condition/SOC differs from offered job"
                    )
            rung, basis = _rung(record)
            if rung != job["rung"]:
                raise tasks.TaskError("raw solver rung differs from offered job")
            provenance = record.get("solver_provenance", {})
            if (
                provenance.get("schema") != "carbon.battery.solver-provenance.v1"
                or provenance.get("solver_image", "").split("@")[-1]
                != plan["image_digest"]
                or provenance.get("overlay_lock_sha256")
                != "sha256:" + plan["overlay_sha256"]
                or provenance.get("pybamm") != "26.8.0.0"
                or provenance.get("overlay_lock")
                != "scripts/dev/exam_design/locks/battery-overlay.lock.json"
            ):
                raise tasks.TaskError(
                    "pinned solver image/overlay/model source differs"
                )
            found[jid] = record
            bindings[jid] = {
                "chunk": cid,
                "chunk_sha256": chunk["sha256"],
                "line": line,
                "source_case_id": mapping["case_id"],
                "source_commit": chunk["source_commit"],
                "raw_row_sha256": _hash(lines[line]),
                "rung": rung,
                "rung_basis": basis,
                "job_digest": tasks.digest(job),
                "solver_provenance_digest": tasks.digest(provenance),
            }
        if mapped != set(lines):
            raise tasks.TaskError("unmapped raw lines cannot silently disappear")
    if chunk_ids != set(raw_chunks):
        raise tasks.TaskError("unregistered raw source chunk")
    return found, bindings


def _extract(record):
    empty = dict.fromkeys(QUANTITIES)
    if record is None:
        return {
            "state": "MISSING",
            "raw_status": None,
            "clock_status": None,
            "values": empty,
        }
    status = record.get("status")
    if type(status) is not str or not status:
        raise tasks.TaskError("raw reference status required")
    clock = record.get("soc_clock")
    if type(clock) is not dict:
        clock = {}
    clock_status = clock.get("status")
    result = {
        "state": status,
        "raw_status": status,
        "clock_status": clock_status if type(clock_status) is str else None,
        "values": empty,
    }
    if status != "OK":
        return result
    try:
        cycles = record["per_cycle"]
        if (
            type(cycles) is not list
            or len(cycles) != 30
            or [c["cycle"] for c in cycles] != list(range(1, 31))
            or any(set(c["phases"]) != set(PHASES) for c in cycles)
            or any(
                not _finite(c["phases"][phase][q])
                for c in cycles
                for phase in PHASES
                for q in ("t_max_c", "plating_min_v", "v_max_v")
            )
            or len(record["capacity_all_ah"]) != 30
            or not all(_finite(c) and c > 0 for c in record["capacity_all_ah"])
            or record["initial_rest"]["t_start_s"] != 0
            or record["initial_rest"]["t_end_s"] != 120
        ):
            raise ValueError("full programme/initial rest unavailable")
        values = measures(record)
        result["values"] = {
            q: values[q] if _finite(values[q]) else None for q in QUANTITIES
        }
        if clock["status"] != "REACHED":
            result["state"] = (
                "NOT_REACHED"
                if clock["status"] == "NOT_REACHED"
                else "REFERENCE_UNRESOLVED"
            )
            result["values"]["minutes"] = None
        elif (
            not _finite(clock.get("time_s"))
            or clock["time_s"] < 120
            or clock["minutes"] != clock["time_s"] / 60
            or any(result["values"][q] is None for q in QUANTITIES)
        ):
            result["state"] = "REFERENCE_UNRESOLVED"
            result["values"]["minutes"] = None
        else:
            result["state"] = "EXTRACTED"
    except (KeyError, TypeError, ValueError, OverflowError):
        result["state"] = "REFERENCE_UNRESOLVED"
        result["values"] = empty
    return result


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
):
    """Validate offered source rows and reduce them with the fixed numerical policy."""
    _digest(plan, expected_plan_digest, "acquisition")
    _digest(source_pins, expected_source_pins_digest, "source pins")
    _digest(manifest, expected_manifest_digest, "producer manifest")
    _fields(
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
        ),
        "manifest",
    )
    if (
        manifest["schema"] != SCHEMA
        or manifest["scope"] not in ("PUBLIC_DEVELOPMENT", "SYNTHETIC_FIXTURE")
        or manifest["role"] != "HELDOUT_REFERENCE"
        or manifest["task_digest"] != registered.get("task_digest")
        or manifest["plan_digest"] != expected_plan_digest
        or manifest["source_pins_digest"] != expected_source_pins_digest
        or manifest["policy_digest"] != tasks.digest(numerics.POLICY)
        or plan.get("numerical_policy_digest") != manifest["policy_digest"]
    ):
        raise tasks.TaskError("registered development producer binding differs")
    if (
        type(source_pins) is not dict
        or source_pins.get("scope") != "DEVELOPMENT_ONLY"
        or source_pins.get("schema") != "carbon.scorelab.acquisition-source-pins.v1"
        or type(source_pins.get("files")) is not dict
    ):
        raise tasks.TaskError("registered development source pins required")
    files = source_pins["files"]
    if any(
        not re.fullmatch(r"[0-9a-f]{64}", files.get(path, ""))
        for path in (*SOURCES, EXPORTER, NUMERICS)
    ):
        raise tasks.TaskError("observer, exporter and numerical source pins required")
    observer = _observer(plan, source_pins)
    if manifest["observer"] != observer:
        raise tasks.TaskError("observer clock, fresh state or source differs")
    stages = _registered_jobs(plan, expected_plan_digest)
    actions = _task_actions(
        registered, expected_plan_digest, OBSERVER, stages["evaluation"]
    )
    refinement = manifest["refinement_job_ids"]
    possible = {j["case_id"]: j for j in stages["refinement"]}
    if (
        type(refinement) is not list
        or len(set(refinement)) != len(refinement)
        or set(refinement) - set(possible)
    ):
        raise tasks.TaskError("registered conditional refinement identities required")
    offered = (
        stages["calibration-pilot"]
        + stages["calibration-rest"]
        + stages["evaluation"]
        + [possible[j] for j in refinement]
    )
    jobs = {j["case_id"]: j for j in offered}
    raw, bindings = _raw_rows(
        manifest, raw_chunks, jobs, observer["source_files"], plan
    )
    extracted = {jid: _extract(raw.get(jid)) for jid in jobs}
    triples = {}
    for job in stages["calibration-pilot"] + stages["calibration-rest"]:
        case = job["case_id"].rsplit(":mesh", 1)[0]
        triples.setdefault(case, {})[str({1: 20, 2: 40, 3: 80}[job["rung"]])] = (
            extracted[job["case_id"]]["values"]
        )
    calibration = numerics.calibration_report(
        triples,
        expected_cases=list(triples),
        expected_policy_digest=manifest["policy_digest"],
    )
    evaluation = {}
    for job in stages["evaluation"] + [possible[j] for j in refinement]:
        evaluation.setdefault((job["t_amb_c"], _action(job)), {})[job["rung"]] = job[
            "case_id"
        ]
    panels, enclosures, pair_receipts = [], [], []
    for row in registered["indices"]:
        band = row["index_value"]
        panel = {"index_value": band, "values": {}}
        enclosure = {"index_value": band, "candidates": {}}
        for (ambient, action), rungs in evaluation.items():
            if ambient != band:
                continue
            candidate, condition = actions[(band, action)]
            ordered = sorted(rungs)
            previous, finest = (extracted[rungs[r]] for r in ordered[-2:])
            ready = all(
                extracted[jid]["state"] == "EXTRACTED" for jid in rungs.values()
            )
            pair = numerics.pair_enclosures(
                previous["values"] if ready else None,
                finest["values"] if ready else None,
                expected_policy_digest=manifest["policy_digest"],
            )
            panel["values"][(candidate, condition)] = finest["values"]
            enclosure["candidates"][candidate] = (
                pair["intervals"]
                if pair["status"] == "READY_OPERATIONAL_ENCLOSURES"
                else {}
            )
            pair_receipts.append(
                {
                    "index_value": band,
                    "candidate": candidate,
                    "job_ids": list(rungs.values()),
                    "pair": pair,
                }
            )
        panels.append(panel)
        enclosures.append(enclosure)
    reference_rows = _reference_rows(panels)
    view = prediction_view(registered, scope=manifest["scope"])
    method = {
        "export": EXPORT,
        "exporter_sha256": files[EXPORTER],
        "numerics_sha256": files[NUMERICS],
        "policy_digest": manifest["policy_digest"],
    }
    receipt = {
        "schema": EXPORT,
        "scope": manifest["scope"],
        "role": manifest["role"],
        "task_digest": registered["task_digest"],
        "limits_digest": _limits_digest(registered),
        "plan_digest": expected_plan_digest,
        "source_pins_digest": expected_source_pins_digest,
        "manifest_digest": expected_manifest_digest,
        "policy_digest": manifest["policy_digest"],
        "observer": observer,
        "observer_digest": tasks.digest(observer),
        "method": method,
        "method_digest": tasks.digest(method),
        "reference_digest": tasks.digest(reference_rows),
        "enclosure_digest": tasks.digest(enclosures),
        "prediction_view_digest": view["export_digest"],
        "calibration": calibration,
        "per_evaluation": pair_receipts,
        "per_job": [
            {"job": job, "source": bindings.get(jid), **extracted[jid]}
            for jid, job in jobs.items()
        ],
        "source_bindings_digest": tasks.digest(bindings),
        "qualification": False,
        "physical_confidence_interval": False,
        "delivery_authentication": "ROOT_PREBOUND_PUBLIC_MANIFEST_REQUIRED",
    }
    receipt["receipt_digest"] = tasks.digest(receipt)
    return ValidatedEvidence(
        _token=_TOKEN,
        payload={
            "receipt": receipt,
            "reference_rows": reference_rows,
            "enclosures": enclosures,
            "prediction_view": view,
        },
    )


def validate_for(
    evidence, registered, references, enclosures, *, scope="PUBLIC_DEVELOPMENT"
):
    """Match a constructed export to the exact task, source and numerical data."""
    if type(evidence) is not ValidatedEvidence:
        raise tasks.TaskError(
            "validated producer evidence required, never a raw flag/dict"
        )
    receipt = evidence.receipt
    _digest(
        {k: v for k, v in receipt.items() if k != "receipt_digest"},
        receipt["receipt_digest"],
        "producer receipt",
    )
    if (
        scope not in ("PUBLIC_DEVELOPMENT", "SYNTHETIC_FIXTURE")
        or receipt["scope"] != scope
        or receipt["task_digest"] != registered.get("task_digest")
        or receipt["limits_digest"] != _limits_digest(registered)
        or receipt["reference_digest"] != tasks.digest(_reference_rows(references))
        or receipt["enclosure_digest"] != tasks.digest(enclosures)
        or receipt["policy_digest"] != tasks.digest(numerics.POLICY)
        or receipt["prediction_view_digest"]
        != prediction_view(registered, scope=scope)["export_digest"]
        or receipt["observer_digest"] != tasks.digest(receipt["observer"])
        or receipt["method_digest"] != tasks.digest(receipt["method"])
    ):
        raise tasks.TaskError(
            "consumer task, limits, references or producer bindings differ"
        )
    # Revalidate task digests, including zero-weight mandatory bands.
    from scripts.dev.score_lab import owner_v3

    owner_v3._validate(registered)
    calibration = receipt["calibration"]
    _digest(
        {k: v for k, v in calibration.items() if k != "receipt_digest"},
        calibration["receipt_digest"],
        "calibration receipt",
    )
    if (
        calibration["status"] != "COMPATIBLE_FOR_REGISTERED_CALIBRATION_CASES"
        or calibration["missing_cases"]
        or calibration["failed_cases"]
    ):
        raise tasks.TaskError("complete compatible registered calibration is required")
    return receipt
