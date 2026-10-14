"""Operator-state proof of an initial, definitive pod-create rejection.

No provider call, timeout rule or absence-based inference lives here. Only a
trusted ComputeStore with the original typed rejection can issue the value.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from contextlib import contextmanager
from dataclasses import dataclass, field

from scripts.dev.exam_design.runpod.operator_compute import (
    ComputeError,
    ComputeStore,
    Execution,
    IntentState,
    ProvisionRequest,
)

SCHEMA = "carbon.pod-job.noncreation.v1"
CAMPAIGN = "pod-jobs"
_ISSUER = object()
_SHA = re.compile(r"sha256:[0-9a-f]{64}")


class NonCreationRefused(ValueError):
    pass


def digest(value):
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return "sha256:" + hashlib.sha256(encoded.encode()).hexdigest()


def binding(store, spec_digest):
    """Original claim scope; no raw host path or credential is disclosed."""
    if not isinstance(store, ComputeStore):
        raise NonCreationRefused("trusted compute store required")
    result = {
        "provider": "runpod",
        "spec_digest": spec_digest,
        "store_digest": digest({"compute_store_path": str(store.path.resolve())}),
    }
    validate_binding(result)
    return result


def validate_binding(value):
    if (
        type(value) is not dict
        or set(value) != {"provider", "spec_digest", "store_digest"}
        or value["provider"] != "runpod"
        or any(
            type(value[key]) is not str or not _SHA.fullmatch(value[key])
            for key in ("spec_digest", "store_digest")
        )
    ):
        raise NonCreationRefused("closed pod-job origin binding required")
    return value


def _snapshot(store, job_id):
    intent = store.intent(CAMPAIGN, job_id)
    if intent is None or intent.state is not IntentState.REJECTED:
        raise NonCreationRefused("authoritative initial REJECTED intent required")
    if (
        intent.provider != "runpod"
        or intent.tenant != CAMPAIGN
        or intent.miner != CAMPAIGN
    ):
        raise NonCreationRefused("pod-job provider/owner mismatch")
    if store.resources(CAMPAIGN, job_id):
        raise NonCreationRefused(
            "a bound/adopted/terminated resource is not non-creation"
        )
    # This is the existing durable one-resend fence, not an inferred list result.
    if (
        store._one(
            "SELECT 1 FROM resend_claims WHERE campaign_id = ? AND intent_id = ?",
            (CAMPAIGN, job_id),
        )
        is not None
    ):
        raise NonCreationRefused("a prior ambiguous resend cannot prove non-creation")
    return {
        "campaign": CAMPAIGN,
        "job_id": job_id,
        "provider": intent.provider,
        "request_digest": intent.request_digest,
        "ownership_tag_digest": digest({"tag": intent.ownership_tag}),
        "intent_created_at": intent.created_at,
        "intent_state": str(intent.state),
        "resources_ever_bound": 0,
        "resend_claimed": False,
    }


def source_id(record):
    return digest(
        {
            key: value
            for key, value in record.items()
            if key not in ("observed_at", "source_id")
        }
    )


def validate_record(record, job_id, expected_binding):
    """Validate historical audit shape; this alone never issues a live proof."""
    keys = {
        "schema",
        "decision",
        "origin",
        "intent",
        "failure",
        "observed_at",
        "source_id",
    }
    if (
        type(record) is not dict
        or set(record) != keys
        or record["schema"] != SCHEMA
        or record["decision"] != "DEFINITIVE_REJECTED"
    ):
        raise NonCreationRefused("closed definitive-rejection audit required")
    validate_binding(record["origin"])
    if record["origin"] != expected_binding:
        raise NonCreationRefused("non-creation proof belongs to another claim/root")
    intent = record["intent"]
    if type(intent) is not dict or set(intent) != {
        "campaign",
        "job_id",
        "provider",
        "request_digest",
        "ownership_tag_digest",
        "intent_created_at",
        "intent_state",
        "resources_ever_bound",
        "resend_claimed",
    }:
        raise NonCreationRefused("closed intent audit required")
    if (
        intent["campaign"] != CAMPAIGN
        or intent["job_id"] != job_id
        or intent["provider"] != "runpod"
        or intent["intent_state"] != str(IntentState.REJECTED)
        or type(intent["resources_ever_bound"]) is not int
        or intent["resources_ever_bound"] != 0
        or intent["resend_claimed"] is not False
    ):
        raise NonCreationRefused("intent audit is not definitive non-creation")
    for key in ("request_digest", "ownership_tag_digest"):
        raw = intent[key]
        if type(raw) is not str or not re.fullmatch(r"(?:sha256:)?[0-9a-f]{64}", raw):
            raise NonCreationRefused("intent identity digest required")
    failure = record["failure"]
    if (
        type(failure) is not dict
        or set(failure)
        != {"operation", "execution", "resources_may_remain", "http_status"}
        or failure["operation"] != "provision"
        or failure["execution"] != str(Execution.EXECUTED)
        or failure["resources_may_remain"] is not False
    ):
        raise NonCreationRefused("original typed create refusal required")
    if failure["http_status"] is not None and (
        type(failure["http_status"]) is not int
        or failure["http_status"] not in (400, 401, 403, 404, 422)
    ):
        raise NonCreationRefused(
            "ambiguous HTTP outcome cannot be a definitive refusal"
        )
    for value in (record["observed_at"], intent["intent_created_at"]):
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise NonCreationRefused("finite reconcile timestamp required")
    if record["observed_at"] < intent["intent_created_at"] or record[
        "source_id"
    ] != source_id(record):
        raise NonCreationRefused("reconcile causality or source identity mismatch")
    return record


@dataclass(frozen=True)
class NonCreationEvidence:
    encoded: bytes
    _store: ComputeStore = field(repr=False, compare=False)
    _issuer: object = field(default=None, repr=False, compare=False)

    def __post_init__(self):
        if self._issuer is not _ISSUER or type(self.encoded) is not bytes:
            raise NonCreationRefused(
                "non-creation evidence is operator-issued, not caller-declared"
            )

    def record(self):
        return json.loads(self.encoded)

    def verify(self, job_id, expected_binding):
        record = self.record()
        validate_record(record, job_id, expected_binding)
        if (
            binding(self._store, expected_binding["spec_digest"]) != expected_binding
            or _snapshot(self._store, job_id) != record["intent"]
        ):
            raise NonCreationRefused(
                "non-creation evidence is stale or has another origin"
            )
        return record

    @contextmanager
    def fenced(self, job_id, expected_binding):
        """Keep durable state stable through the caller's ledger append."""
        with self._store._tx():
            yield self.verify(job_id, expected_binding)


def reconcile_rejection(store, request, spec_digest, failure):
    """Reconcile an initial typed refusal with current durable operator state."""
    if (
        not isinstance(store, ComputeStore)
        or not isinstance(request, ProvisionRequest)
        or not isinstance(failure, ComputeError)
    ):
        raise NonCreationRefused("trusted store and original typed failure required")
    job_id = request.intent_id
    snapshot = _snapshot(store, job_id)
    if (
        request.campaign_id != CAMPAIGN
        or request.digest() != snapshot["request_digest"]
    ):
        raise NonCreationRefused("original dispatched request identity required")
    record = {
        "schema": SCHEMA,
        "decision": "DEFINITIVE_REJECTED",
        "origin": binding(store, spec_digest),
        "intent": snapshot,
        "failure": {
            "operation": failure.operation,
            "execution": str(failure.execution),
            "resources_may_remain": failure.resources_may_remain,
            "http_status": failure.http_status,
        },
        "observed_at": store.clock(),
    }
    record["source_id"] = source_id(record)
    validate_record(record, job_id, record["origin"])
    return NonCreationEvidence(
        json.dumps(
            record, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode(),
        store,
        _ISSUER,
    )
