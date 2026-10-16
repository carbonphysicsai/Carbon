"""Target-only public guarded419 construction; no solve, fit or file access.

Only the authenticated T9 producer can supply evidence to ``build``. The
historical coarse TRAIN bridge is never involved. This module retains all
offered failures, reuses full-programme extraction and prepares the existing
trainer only after accepted-label support is measured on input metadata.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import replace

from carbon.design_search import tasks

SCHEMA = "carbon.battery-v3.guard419.train-record.v1"
RECEIPT = "carbon.scorelab.guarded419.target-only-train.v1"
KIT_ID = "carbon.battery-v3.guard419.kit.v1"
MODEL_ID = "battery-v3-scorelab-guard419-probe9.default.v1"
FEATURE_MAP = {
    "c1": "c1",
    "c2": "c2",
    "switch_voltage_v": "switch_v",
    "h_multiplier": "cooling",
    "t_amb_c": "ambient_c",
    "soc0": "soc0",
}
QUANTITIES = ("charging_t_max_c", "minutes", "plating_min_v", "q30_over_q1", "v_max_v")
UNITS = {
    "charging_t_max_c": "degC",
    "minutes": "min",
    "plating_min_v": "V",
    "q30_over_q1": "dimensionless",
    "v_max_v": "V",
}
SCOPES = ("PUBLIC_DEVELOPMENT", "SYNTHETIC_FIXTURE")
_TOKEN = object()


def _sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def _jsonl(records):
    return b"".join(
        (json.dumps(row, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
        for row in records
    )


class ValidatedTrain:
    """Immutable result of source/role/operative-guard authentication.

    This is a local construction boundary, not an attestation against arbitrary
    code in this Python process. Consumers independently pin its receipt.
    """

    __slots__ = ("_payload", "_seal")

    def __new__(cls, *, _token=None, payload=None):
        if _token is not _TOKEN:
            raise tasks.TaskError("use guarded419_train.build")
        obj = super().__new__(cls)
        object.__setattr__(
            obj, "_payload", json.dumps(payload, allow_nan=False).encode()
        )
        object.__setattr__(obj, "_seal", tasks.digest(payload))
        return obj

    def __setattr__(self, name, value):
        raise AttributeError("validated TRAIN is immutable")

    def _snapshot(self):
        body = json.loads(self._payload)
        if tasks.digest(body) != self._seal:
            raise tasks.TaskError("validated TRAIN changed")
        return body

    @property
    def receipt(self):
        return self._snapshot()["receipt"]

    @property
    def training_jsonl(self):
        return _jsonl(self._snapshot()["records"])


def build(evidence, *, expected_binding_digest, expected_manifest_digest, scope):
    """Map authenticated T9 evidence to construction records, preserving nine offers.

    The producer validates the raw delivery and recomputes the actual-job
    operative guard before constructing its sealed evidence. A plain mapping
    or a claimed success report cannot enter this path. Upstream availability
    is an explicit dependency, never an alternative acceptance path.
    """
    if scope not in SCOPES:
        raise tasks.TaskError("development construction only")
    try:
        from scripts.dev.score_lab import guarded419_t9 as t9
    except ImportError as exc:
        raise tasks.TaskError("guarded419 T9 producer is not integrated") from exc
    from scripts.dev.score_lab import owner_v3_panel_export as producer

    source = t9.validate_for(
        evidence,
        expected_binding_digest=expected_binding_digest,
        expected_manifest_digest=expected_manifest_digest,
        scope=scope,
    )
    if (
        source["scope"] != scope
        or source["binding_digest"] != expected_binding_digest
        or source["manifest_digest"] != expected_manifest_digest
        or type(source["jobs"]) is not list
        or len(source["jobs"]) != 9
    ):
        raise tasks.TaskError("authenticated ordered T9 evidence required")
    records, ledger, seen = [], [], set()
    for job in source["jobs"]:
        jid = job["case_id"]
        if jid in seen or producer._rung(job)[0] != 1:
            raise tasks.TaskError("unique standard-rung T9 offers required")
        seen.add(jid)
        raw = source["records"].get(jid)
        extracted = producer._extract(raw)
        tracking = source["tracking"].get(jid)
        guard_ok = (
            type(tracking) is dict
            and tracking.get("status") == "TRACKING_COMPATIBLE"
            and tracking.get("checked_phases") == 181
            and tracking.get("required_phases") == 181
        )
        eligible = (
            guard_ok
            and extracted["state"] == "EXTRACTED"
            and set(extracted["values"]) == set(QUANTITIES)
            and all(_finite(v) for v in extracted["values"].values())
        )
        state = (
            "ADMITTED_CONSTRUCTION"
            if eligible
            else (
                "MISSING"
                if raw is None
                else (
                    extracted["state"]
                    if extracted["state"] != "EXTRACTED"
                    else "REFERENCE_UNRESOLVED"
                )
            )
        )
        record = {
            "schema": SCHEMA,
            "case_id": jid,
            "source": "authenticated guarded419 T9; construction only, not EVAL truth",
            "role": "PUBLIC_TRAIN_CONSTRUCTION",
            "protocol_id": source["protocol_id"],
            "method_digest": source["method_digest"],
            "observer_id": source["observer_id"],
            "dataset_id": source["dataset_id"],
            "binding_digest": expected_binding_digest,
            "manifest_digest": expected_manifest_digest,
            "inputs": {
                target: job[original] for original, target in FEATURE_MAP.items()
            },
            "outputs": extracted["values"] if eligible else dict.fromkeys(QUANTITIES),
            "label_state": state,
        }
        if scope == "SYNTHETIC_FIXTURE":
            record["fixture"] = True
        records.append(record)
        ledger.append(
            {
                "case_id": jid,
                "job_digest": tasks.digest(job),
                "eligible": eligible,
                "state": state,
                "extraction": extracted,
                "tracking": tracking,
                "producer_disposition": source["per_job"][jid],
                "source": source["source_rows"].get(jid),
            }
        )
    if (
        set(source["records"]) - seen
        or set(source["per_job"]) != seen
        or set(source["tracking"]) - seen
        or set(source["source_rows"]) != set(source["records"])
    ):
        raise tasks.TaskError("T9 evidence inventory differs from offered jobs")
    receipt = {
        "schema": RECEIPT,
        "scope": scope,
        "role": "PUBLIC_TRAIN_CONSTRUCTION",
        "protocol_id": source["protocol_id"],
        "method_digest": source["method_digest"],
        "observer_id": source["observer_id"],
        "dataset_id": source["dataset_id"],
        "source_commit": source["source_commit"],
        "source_files": source["source_files"],
        "binding_digest": expected_binding_digest,
        "manifest_digest": expected_manifest_digest,
        "g0_receipt_digest": source["g0_receipt_digest"],
        "training_jsonl_digest": _sha(_jsonl(records)),
        "offered_training_rows": len(records),
        "accepted_training_rows": sum(r["eligible"] for r in ledger),
        "ledger": ledger,
        "output_units": dict(UNITS),
        "validation_rows_used_for_fitting": 0,
        "historical_labels_or_models_reused": 0,
        "numerical_evaluation_reference": False,
        "full_calibration_release": False,
        "qualification": False,
        "artifact_role": "NINE_ANCHOR_PROBE_NOT_FINAL_EIGHTEEN",
    }
    receipt["receipt_digest"] = tasks.digest(receipt)
    return ValidatedTrain(
        _token=_TOKEN, payload={"records": records, "receipt": receipt}
    )


def _validated(value, expected_receipt_digest, scope):
    if type(value) is not ValidatedTrain or scope not in SCOPES:
        raise tasks.TaskError("authenticated development TRAIN required")
    body = value._snapshot()
    receipt = body["receipt"]
    fields = {k: v for k, v in receipt.items() if k != "receipt_digest"}
    if (
        receipt.get("scope") != scope
        or receipt.get("schema") != RECEIPT
        or receipt.get("receipt_digest") != expected_receipt_digest
        or tasks.digest(fields) != expected_receipt_digest
        or receipt.get("training_jsonl_digest") != _sha(_jsonl(body["records"]))
    ):
        raise tasks.TaskError("TRAIN receipt, bytes or scope differs")
    return body


def _support(records, inputs):
    """Observed marginal ranges/categories, using admitted labels only."""
    admitted = [
        row for row in records if all(_finite(v) for v in row["outputs"].values())
    ]
    names = tuple(FEATURE_MAP.values())
    support = {}
    if admitted:
        for name in names:
            values = [row["inputs"][name] for row in admitted]
            support[name] = (
                sorted(set(values)) if name == "cooling" else [min(values), max(values)]
            )
    gaps = []
    for i, row in enumerate(inputs):
        unsupported = [
            name
            for name in names
            if not admitted
            or (
                row[name] not in support[name]
                if name == "cooling"
                else not support[name][0] <= row[name] <= support[name][1]
            )
        ]
        if unsupported:
            gaps.append({"input_ordinal": i, "features": unsupported})
    ready = len(admitted) >= 2 and not gaps
    return {
        "status": "READY_FOR_CONSTRUCTION_PROBE" if ready else "TRAIN_INADEQUATE",
        "accepted_rows": len(admitted),
        "offered_rows": len(records),
        "excluded_rows": len(records) - len(admitted),
        "technical_minimum_rows": 2,
        "evaluation_input_count": len(inputs),
        "covered_input_count": len(inputs) - len(gaps),
        "observed_support": support,
        "gaps": gaps,
        "meaning": "Marginal input coverage only, not joint support or prediction adequacy",
        "units": dict(UNITS),
        "qualification": False,
    }


def probe_support(
    value, *, expected_receipt_digest, evaluation_inputs, expected_inputs_digest, scope
):
    """Read input metadata only. A failed extreme anchor cannot extend support.

    Root independently pins this ordered public input inventory. Exactly sixty
    distinct physical inputs belong to the first real diagnostic. Fixture
    tests can use smaller inventories but remain structurally fixture-only.
    """
    body = _validated(value, expected_receipt_digest, scope)
    if (
        type(evaluation_inputs) is not list
        or not evaluation_inputs
        or tasks.digest(evaluation_inputs) != expected_inputs_digest
        or (scope == "PUBLIC_DEVELOPMENT" and len(evaluation_inputs) != 60)
    ):
        raise tasks.TaskError(
            "exact independently pinned public input inventory required"
        )
    seen = set()
    for row in evaluation_inputs:
        if (
            type(row) is not dict
            or set(row) != set(FEATURE_MAP.values())
            or not all(_finite(v) for v in row.values())
            or row["cooling"] not in (1, 2, 4)
            or row["soc0"] != 0.1
        ):
            raise tasks.TaskError("input-only six-feature inventory required")
        identity = tuple(row[name] for name in FEATURE_MAP.values())
        if identity in seen:
            raise tasks.TaskError("physical input inventory must be unique")
        seen.add(identity)
    report = {
        "schema": "carbon.scorelab.guarded419.probe-support.v1",
        "scope": scope,
        "training_receipt_digest": expected_receipt_digest,
        "evaluation_inputs_digest": expected_inputs_digest,
        **_support(body["records"], evaluation_inputs),
    }
    return {**report, "receipt_digest": tasks.digest(report)}


def load_probe(
    value, *, expected_receipt_digest, evaluation_inputs, expected_inputs_digest, scope
):
    """Return the existing kit/Train pair and support receipt; never fit.

    Only this accepted construction set enters the unchanged trainer's
    normalization. The nine-anchor probe is separate from the later cohort.
    """
    from carbon.development_comparison import battery_v3_kit, carbon_arm

    body = _validated(value, expected_receipt_digest, scope)
    support = probe_support(
        value,
        expected_receipt_digest=expected_receipt_digest,
        evaluation_inputs=evaluation_inputs,
        expected_inputs_digest=expected_inputs_digest,
        scope=scope,
    )
    if support["status"] != "READY_FOR_CONSTRUCTION_PROBE":
        raise carbon_arm.ArmRefused("TRAIN_INADEQUATE")
    receipt = body["receipt"]
    kit = replace(
        battery_v3_kit.KIT,
        kit_id=KIT_ID + ":" + receipt["binding_digest"],
        train_schema=SCHEMA,
        model_id=MODEL_ID + ":" + expected_receipt_digest,
    )
    data = value.training_jsonl
    train = carbon_arm.load_train(kit, data, receipt["training_jsonl_digest"])
    if (
        len(train.records) != support["accepted_rows"]
        or train.excluded != support["excluded_rows"]
    ):
        raise tasks.TaskError(
            "shared trainer admission differs from authenticated TRAIN"
        )
    return kit, train, support
