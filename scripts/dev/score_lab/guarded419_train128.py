"""Role-separated guarded419 construction and validation, without I/O or fitting."""

from __future__ import annotations

import json
from dataclasses import replace

from carbon.design_search import tasks
from scripts.dev.score_lab import guarded419_train as train9
from scripts.dev.score_lab import owner_v3_panel_export as producer

CONSTRUCTION = "PUBLIC_CONSTRUCTION"
VALIDATION = "INTERNAL_TRAIN_VALIDATION"
TRAIN_SCHEMA = "carbon.battery-v3.guard419.stage128.train-record.v1"
VALIDATION_SCHEMA = "carbon.battery-v3.guard419.stage128.validation-record.v1"
RECEIPT = "carbon.scorelab.guarded419.role-separated-train128.v1"
_TOKEN = object()


class ValidatedSplit:
    """Immutable result; requires the real prerequisite-qualified producer."""

    __slots__ = ("_bytes", "_seal")

    def __new__(cls, *, _token=None, payload=None):
        if _token is not _TOKEN:
            raise tasks.TaskError("use guarded419_train128.build")
        obj = super().__new__(cls)
        object.__setattr__(obj, "_bytes", json.dumps(payload, allow_nan=False).encode())
        object.__setattr__(obj, "_seal", tasks.digest(payload))
        return obj

    def __setattr__(self, name, value):
        raise AttributeError("validated split is immutable")

    def _snapshot(self):
        body = json.loads(self._bytes)
        if tasks.digest(body) != self._seal:
            raise tasks.TaskError("validated split changed")
        return body

    @property
    def receipt(self):
        return self._snapshot()["receipt"]

    @property
    def construction_jsonl(self):
        return train9._jsonl(self._snapshot()["construction"])

    @property
    def validation_jsonl(self):
        return train9._jsonl(self._snapshot()["validation"])


def _split(source):
    """Unsealed mapping primitive, not admission or prerequisite qualification."""
    jobs, roles = source["jobs"], source["roles_by_job_id"]
    ids = [j["case_id"] for j in jobs]
    if (
        len(ids) != 128
        or len(set(ids)) != 128
        or set(roles) != set(ids)
        or list(roles.values()).count(CONSTRUCTION) != 105
        or list(roles.values()).count(VALIDATION) != 23
        or set(source["per_job"]) != set(ids)
        or set(source["records"]) - set(ids)
        or set(source["tracking"]) - set(ids)
        or set(source["source_rows"]) != set(source["records"])
    ):
        raise tasks.TaskError("frozen 128 offers and 105/23 role inventory required")
    construction, validation, ledger = [], [], []
    for job in jobs:
        jid, role = job["case_id"], roles[job["case_id"]]
        if job.get("reference_role") != role or producer._rung(job)[0] != 1:
            raise tasks.TaskError(
                "registered construction/validation role or rung differs"
            )
        raw = source["records"].get(jid)
        extracted = producer._extract(raw)
        tracking = source["tracking"].get(jid)
        accepted = (
            type(tracking) is dict
            and tracking.get("status") == "TRACKING_COMPATIBLE"
            and tracking.get("checked_phases") == tracking.get("required_phases") == 181
            and extracted["state"] == "EXTRACTED"
            and set(extracted["values"]) == set(train9.QUANTITIES)
            and all(train9._finite(v) for v in extracted["values"].values())
        )
        proof = source["source_rows"].get(jid)
        if raw is not None and (
            type(proof) is not dict
            or raw.get("case_id") != proof.get("original_job_id")
            or proof.get("parent_input_index") != job.get("parent_input_index")
        ):
            raise tasks.TaskError("original raw identity/source-index mapping required")
        state = (
            "ADMITTED_CONSTRUCTION"
            if accepted and role == CONSTRUCTION
            else (
                "ADMITTED_INTERNAL_VALIDATION"
                if accepted
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
        )
        row = {
            "schema": TRAIN_SCHEMA if role == CONSTRUCTION else VALIDATION_SCHEMA,
            "case_id": jid,
            "role": role,
            "source": "authenticated guarded419 stage128; construction/validation only",
            "protocol_id": source["protocol_id"],
            "method_digest": source["method_digest"],
            "observer_id": source["observer_id"],
            "dataset_id": source["dataset_id"],
            "binding_digest": source["binding_digest"],
            "manifest_digest": source["manifest_digest"],
            "inputs": {
                target: job[original] for original, target in train9.FEATURE_MAP.items()
            },
            "outputs": (
                extracted["values"] if accepted else dict.fromkeys(train9.QUANTITIES)
            ),
            "label_state": state,
        }
        if source["scope"] == "SYNTHETIC_FIXTURE":
            row["fixture"] = True
        (construction if role == CONSTRUCTION else validation).append(row)
        ledger.append(
            {
                "case_id": jid,
                "role": role,
                "eligible": accepted,
                "state": state,
                "extraction": extracted,
                "tracking": tracking,
                "source": proof,
                "producer_disposition": source["per_job"][jid],
            }
        )
    return construction, validation, ledger


def build(evidence, *, expected_binding_digest, expected_manifest_digest, scope):
    """Accept only the nominal source after real T9/CAL prerequisites validate."""
    if scope not in train9.SCOPES:
        raise tasks.TaskError("development construction only")
    from scripts.dev.score_lab import guarded419_t128 as admission

    source = admission.validate_for(
        evidence,
        expected_binding_digest=expected_binding_digest,
        expected_manifest_digest=expected_manifest_digest,
        scope=scope,
    )
    construction, validation, ledger = _split(source)
    receipt = {
        "schema": RECEIPT,
        "scope": scope,
        "binding_digest": expected_binding_digest,
        "manifest_digest": expected_manifest_digest,
        "protocol_id": source["protocol_id"],
        "method_digest": source["method_digest"],
        "observer_id": source["observer_id"],
        "dataset_id": source["dataset_id"],
        "source_commit": source["source_commit"],
        "source_files": source["source_files"],
        "prerequisite_digests": source["prerequisite_digests"],
        "prerequisite_sources": source["prerequisite_sources"],
        "g0_receipt_digest": source["g0_receipt_digest"],
        "construction_jsonl_digest": train9._sha(train9._jsonl(construction)),
        "validation_jsonl_digest": train9._sha(train9._jsonl(validation)),
        "construction_offered": len(construction),
        "validation_offered": len(validation),
        "construction_accepted": sum(
            r["eligible"] and r["role"] == CONSTRUCTION for r in ledger
        ),
        "validation_accepted": sum(
            r["eligible"] and r["role"] == VALIDATION for r in ledger
        ),
        "ledger": ledger,
        "output_units": dict(train9.UNITS),
        "validation_rows_used_for_fitting": 0,
        "historical_labels_or_models_reused": 0,
        "numerical_evaluation_reference": False,
        "qualification": False,
    }
    receipt["receipt_digest"] = tasks.digest(receipt)
    return ValidatedSplit(
        _token=_TOKEN,
        payload={
            "construction": construction,
            "validation": validation,
            "receipt": receipt,
        },
    )


def _validated(value, expected_receipt_digest, scope):
    if type(value) is not ValidatedSplit or scope not in train9.SCOPES:
        raise tasks.TaskError("prerequisite-qualified role-separated TRAIN required")
    body = value._snapshot()
    receipt = body["receipt"]
    if (
        receipt["schema"] != RECEIPT
        or receipt["scope"] != scope
        or receipt["receipt_digest"] != expected_receipt_digest
        or tasks.digest({k: v for k, v in receipt.items() if k != "receipt_digest"})
        != expected_receipt_digest
        or train9._sha(train9._jsonl(body["construction"]))
        != receipt["construction_jsonl_digest"]
        or train9._sha(train9._jsonl(body["validation"]))
        != receipt["validation_jsonl_digest"]
    ):
        raise tasks.TaskError("split receipt, bytes or scope differs")
    return body


def load_construction(
    value, *, expected_receipt_digest, evaluation_inputs, expected_inputs_digest, scope
):
    """Shared loader after accepted-CONSTRUCTION-only marginal support check; no fit."""
    from carbon.development_comparison import battery_v3_kit, carbon_arm

    body = _validated(value, expected_receipt_digest, scope)
    _inputs(evaluation_inputs, expected_inputs_digest, scope)
    support = train9._support(body["construction"], evaluation_inputs)
    if support["status"] != "READY_FOR_CONSTRUCTION_PROBE":
        raise carbon_arm.ArmRefused("TRAIN_INADEQUATE")
    receipt = body["receipt"]
    kit = replace(
        battery_v3_kit.KIT,
        train_schema=TRAIN_SCHEMA,
        kit_id="carbon.battery-v3.guard419.stage128.kit.v1:"
        + receipt["binding_digest"],
        model_id="battery-v3-scorelab-guard419-stage128-dev-v1:"
        + expected_receipt_digest,
    )
    train = carbon_arm.load_train(
        kit, value.construction_jsonl, receipt["construction_jsonl_digest"]
    )
    if (
        len(train.records) != support["accepted_rows"]
        or train.excluded != support["excluded_rows"]
    ):
        raise tasks.TaskError("shared trainer admission differs")
    return (
        kit,
        train,
        {
            **support,
            "training_receipt_digest": expected_receipt_digest,
            "evaluation_inputs_digest": expected_inputs_digest,
            "validation_rows_used_for_support": 0,
        },
    )


def _inputs(evaluation_inputs, expected_inputs_digest, scope):
    """Input metadata validation only; never admits a split or training labels."""
    if (
        type(evaluation_inputs) is not list
        or not evaluation_inputs
        or scope not in train9.SCOPES
        or (scope == "PUBLIC_DEVELOPMENT" and len(evaluation_inputs) != 60)
        or any(
            type(r) is not dict
            or set(r) != set(train9.FEATURE_MAP.values())
            or not all(train9._finite(v) for v in r.values())
            or r["cooling"] not in (1, 2, 4)
            or r["soc0"] != 0.1
            for r in evaluation_inputs
        )
        or len(
            {
                tuple(r[n] for n in train9.FEATURE_MAP.values())
                for r in evaluation_inputs
            }
        )
        != len(evaluation_inputs)
        or tasks.digest(evaluation_inputs) != expected_inputs_digest
    ):
        raise tasks.TaskError(
            "independently pinned input-only physical inventory required"
        )


def _validation_summary(records, predictions):
    """Unsealed arithmetic primitive; no mixed-unit scalar or eligibility claim."""
    if type(predictions) is not dict or set(predictions) != {
        r["case_id"] for r in records
    }:
        raise tasks.TaskError("all offered validation predictions required")
    errors = {q: [] for q in train9.QUANTITIES}
    states = []
    for row in records:
        pred = predictions[row["case_id"]]
        reference_ok = all(train9._finite(v) for v in row["outputs"].values())
        valid = (
            type(pred) is dict
            and set(pred) == set(train9.QUANTITIES)
            and all(train9._finite(v) for v in pred.values())
        )
        state = (
            "REFERENCE_UNAVAILABLE"
            if not reference_ok
            else (
                "ABSTAINED"
                if pred is None
                else (
                    "INVALID_PREDICTION"
                    if not valid
                    else "MEASURED_INTERNAL_VALIDATION"
                )
            )
        )
        if state == "MEASURED_INTERNAL_VALIDATION":
            for q in train9.QUANTITIES:
                error = abs(pred[q] - row["outputs"][q])
                if not train9._finite(error):
                    raise tasks.TaskError("nonfinite derived validation error")
                errors[q].append(error)
        states.append({"case_id": row["case_id"], "state": state})
    means = {
        q: sum(error / len(values) for error in values) if values else None
        for q, values in errors.items()
    }
    if any(mean is not None and not train9._finite(mean) for mean in means.values()):
        raise tasks.TaskError("nonfinite aggregate validation error")
    return {
        "offered_validation_rows": len(records),
        "states": states,
        "per_quantity": {
            q: {
                "unit": train9.UNITS[q],
                "paired_count": len(v),
                "mean_absolute_error": means[q],
            }
            for q, v in errors.items()
        },
        "qualification": False,
    }


def validation_report(
    value, predictions, *, expected_receipt_digest, expected_predictions_digest, scope
):
    body = _validated(value, expected_receipt_digest, scope)
    if tasks.digest(predictions) != expected_predictions_digest:
        raise tasks.TaskError("validation prediction digest differs")
    report = {
        "schema": "carbon.scorelab.guarded419.internal-validation128.v1",
        "scope": scope,
        "split_receipt_digest": expected_receipt_digest,
        "predictions_digest": expected_predictions_digest,
        **_validation_summary(body["validation"], predictions),
    }
    return {**report, "receipt_digest": tasks.digest(report)}
