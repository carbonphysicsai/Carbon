"""Closed prospective guarded419 N1 context; no execution or data acceptance.

The original 4.2-V statistics are fixed EXTERNAL scoring constants. They are
not compatible construction labels, new model normalizers or EVAL truth.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from carbon.design_search import tasks

JOB = "battery-v3-job-guard419-dev-v1"
ID = "carbon.scorelab.battery-v3.guarded419-n1-context.v1"
PROTOCOL = "carbon.scorelab.battery-v3.guarded419-protocol.v1"
PROJECTION = "carbon.scorelab.battery-v3.band-deadzone-projection.guard419.v1"
EVAL_OBSERVER = "carbon.scorelab.battery-v3.guarded419-eval-observer.v1"
REGISTRATION_SHA256 = "d6f395fd815eb59392f51cab4b6a401a7c94a5f667a80ddc1bc099f88147ace8"
PARENT_SHA256 = "c3997852ea0ca66e392ebc4849c76f34b7e3d929bf35eb9a5c2f605e114b8c4e"
DIRECTORY = (
    Path(__file__).resolve().parents[3]
    / "Business/research/score-lab-campaign-01/n1-diagnostic-guard419-v1"
)
_TOKEN = object()
_REPLACED = frozenset(
    {"schema", "id", "job", "train_sha256", "train_scale_receipt_sha256"}
)
_ADDED = frozenset(
    {
        "parent_registration_sha256",
        "context_id",
        "protocol_id",
        "guarded_owner_approval_original_sha256",
        "guarded_approved_document_original_sha256",
        "reference_acceptance",
        "training_normalization",
        "historical_models_compatible",
        "normalization_source",
    }
)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _check_registration(registered, parent):
    """Semantic delta check in addition to the independent exact byte pins."""
    if (
        type(registered) is not dict
        or type(parent) is not dict
        or set(registered)
        != (set(parent) - _REPLACED) | {"schema", "id", "job"} | _ADDED
        or any(
            registered[key] != value
            for key, value in parent.items()
            if key not in _REPLACED
        )
        or registered["schema"]
        != "carbon.scorelab.battery-v3.n1-diagnostic-registration.guard419.v1"
        or registered["id"] != "battery-v3-n1-diagnostic-guard419-dev-v1"
        or registered["job"] != JOB
        or registered["context_id"] != ID
        or registered["protocol_id"] != PROTOCOL
        or registered["parent_registration_sha256"] != PARENT_SHA256
        or registered["normalization_source"]
        != {
            "role": "EXTERNAL_ORIGINAL42_SCORING_CONSTANTS_ONLY_NOT_TRAIN_OR_TRUTH",
            "registration_sha256": PARENT_SHA256,
            "train_sha256": parent["train_sha256"],
            "scale_receipt_sha256": parent["train_scale_receipt_sha256"],
        }
        or registered["training_normalization"] != "NEW_ACCEPTED_CONSTRUCTION_ONLY"
        or registered["historical_models_compatible"] is not False
        or registered["reference_acceptance"]
        != "NEW_COMPATIBLE_GUARDED419_CAL_AND_EVAL_RECEIPTS_REQUIRED"
        or registered["guarded_owner_approval_original_sha256"]
        != "e4a7dd4d8f51e3aaac38d75d5e763dfbc6061cc59715d65a3bdad94e3c8c4696"
        or registered["guarded_approved_document_original_sha256"]
        != "fc731a4ad5f5a700d0855f5763dce9f73b09fe2646f92fdc6988c0711b16e123"
    ):
        raise tasks.TaskError(
            "guarded context must preserve exact approved N1 constants and roles"
        )


class Context:
    """Nominal immutable registration loaded only from the committed byte pins.

    This is a provenance boundary inside cooperating Python, not a hostile
    in-process sandbox. It grants no reference, execution or score authority.
    """

    __slots__ = ("_raw",)

    def __new__(cls, *, _token=None, raw=None):
        if _token is not _TOKEN:
            raise tasks.TaskError("use guarded419_context.load")
        obj = super().__new__(cls)
        object.__setattr__(obj, "_raw", raw)
        return obj

    def __setattr__(self, name, value):
        raise AttributeError("guarded context is immutable")


def load(*, expected_sha256):
    if expected_sha256 != REGISTRATION_SHA256:
        raise tasks.TaskError("guarded registration digest differs")
    raw = (DIRECTORY / "registration.json").read_bytes()
    parent_dir = DIRECTORY.parent / "n1-diagnostic-v1"
    parent_raw = (parent_dir / "registration.json").read_bytes()
    if _sha(raw) != REGISTRATION_SHA256 or _sha(parent_raw) != PARENT_SHA256:
        raise tasks.TaskError("guarded or historical registration bytes differ")
    registered, parent = json.loads(raw), json.loads(parent_raw)
    _check_registration(registered, parent)
    for name, key in (
        ("APPROVED_PROPOSAL.md", "proposal_sha256"),
        ("OWNER_APPROVAL.json", "approval_sha256"),
        ("TRAIN_SCALE_RECEIPT.json", "train_scale_receipt_sha256"),
    ):
        if _sha((parent_dir / name).read_bytes()) != parent[key]:
            raise tasks.TaskError("approved original N1 provenance differs")
    if (
        _sha((DIRECTORY / "OWNER_GUARDED_APPROVAL.json").read_bytes())
        != registered["guarded_owner_approval_original_sha256"]
    ):
        raise tasks.TaskError("guarded owner approval bytes differ")
    return Context(_token=_TOKEN, raw=raw)


def validate(context):
    if type(context) is not Context or _sha(context._raw) != REGISTRATION_SHA256:
        raise tasks.TaskError("authenticated nominal guarded419 context required")
    return json.loads(context._raw)


def task_identity(registered, context):
    """Check new identities; never mutate/relabel an old registered task."""
    validate(context)
    if registered["identity"]["contract_version"] != JOB or any(
        row["task"]["identity"]["contract_version"] != JOB
        or row["task"]["identity"]["observer_version"] != EVAL_OBSERVER
        for row in registered["indices"]
    ):
        raise tasks.TaskError("guarded task and observer context differs")


def metadata(context):
    registered = validate(context)
    return {
        "context_id": ID,
        "registration_sha256": REGISTRATION_SHA256,
        "protocol_id": PROTOCOL,
        "normalization_source": registered["normalization_source"],
        "training_normalization": registered["training_normalization"],
    }
