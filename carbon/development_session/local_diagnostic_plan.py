"""PROPOSED development-only local GPU diagnostic plan. No dispatch authority.

This module validates a *proposed* bounded diagnostic run plan against exactly
pinned identities. It is preparation only: `require_local_diagnostic_dispatch`
refuses unconditionally, so merging this file cannot start work, cannot install
a grant and cannot admit an accelerator.

Three separations are deliberate and must survive any later activation:

* A development diagnostic observation is **not** the strict exclusivity claim.
  The strict path requires established compute-process enumeration; no source is
  established, so this plan records exclusivity as UNESTABLISHED rather than
  asserting an empty foreign-process list.
* Evidence produced under this plan is development-only. `official_eligible` is
  fixed False and there is no promotion path into strict acceptance.
* Nothing here supplies a role, device, host path, image, grant or tolerance
  from a caller. Every identity must equal a value pinned by the repository.

Import and validation never initialize a numerical backend or touch a device.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

SCHEMA = "carbon.gpu-development-diagnostic-plan.v1"
STATUS = "PROPOSED_NOT_ACTIVATED"

# Exclusivity is not claimed by a development diagnostic.
EXCLUSIVITY = "UNESTABLISHED_DEVELOPMENT_OBSERVATION"

# Conservative DEVELOPMENT proposals. These are not ratified tolerances, not
# enforceable VRAM quotas and not production criteria.
MAX_TRAINING_STEPS = 32
MAX_PROCESS_WALL_SECONDS = 600
MAX_TASK_WALL_SECONDS = 1800
MAX_INVOCATIONS = 1
MAX_RETRIES = 0
MAX_OUTPUT_BYTES = 64 * 1024 * 1024

_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_NONCE = re.compile(r"^[0-9a-f]{32}$")

# A development plan may name exactly one registered operation.
PERMITTED_OPERATIONS = frozenset({"registered_trainer_fit"})

# Input phases that a development diagnostic may never select.
FORBIDDEN_INPUT_PHASES = frozenset(
    {"exam", "final", "evaluation", "customer", "protected", "live"}
)

# The exact field set. Identity fields are echoed by the caller only so they can
# be compared against the repository's pinned values; a wrong value is refused.
REQUIRED_FIELDS = (
    "schema",
    "operation",
    "source_commit",
    "source_tree_digest",
    "image_id",
    "environment_lock_digest",
    "profile_digest",
    "input_phase",
    "input_digest",
    "training_steps",
    "invocations",
    "retries",
    "process_wall_seconds",
    "task_wall_seconds",
    "max_output_bytes",
    "nonce",
)

# Execution controls a caller must never supply. An unexpected field is refused
# regardless; naming these gives an unambiguous reason for an injection attempt
# rather than a generic shape error. Disjoint from REQUIRED_FIELDS by
# construction, so an echoed identity can never be mistaken for injected control.
FORBIDDEN_FIELDS = frozenset(
    {
        "command",
        "args",
        "entrypoint",
        "shell",
        "script",
        "url",
        "mounts",
        "volumes",
        "binds",
        "devices",
        "device_requests",
        "gpus",
        "privileged",
        "network",
        "env",
        "environment",
        "packages",
        "pip",
        "image",
        "role",
        "grant",
        "grant_digest",
        "host_root",
        "controller_root",
        "tolerance",
        "official_eligible",
        "score",
    }
) - set(REQUIRED_FIELDS)


class LocalDiagnosticRefused(RuntimeError):
    """A proposed plan is not an approved run and never an admitted execution."""


@dataclass(frozen=True, slots=True)
class PinnedIdentities:
    """Repository-pinned identities a plan must match exactly."""

    source_commit: str
    source_tree_digest: str
    image_id: str
    environment_lock_digest: str
    profile_digest: str
    input_phase: str
    input_digest: str

    def __post_init__(self) -> None:
        for value in (
            self.source_tree_digest,
            self.image_id,
            self.environment_lock_digest,
            self.profile_digest,
            self.input_digest,
        ):
            if type(value) is not str or _DIGEST.fullmatch(value) is None:
                raise LocalDiagnosticRefused("exact sha256 identity required")
        if (
            type(self.source_commit) is not str
            or re.fullmatch(r"[0-9a-f]{40}", self.source_commit) is None
        ):
            raise LocalDiagnosticRefused("exact source commit required")
        if type(self.input_phase) is not str or not self.input_phase:
            raise LocalDiagnosticRefused("exact input phase required")
        if self.input_phase.strip().lower() in FORBIDDEN_INPUT_PHASES:
            raise LocalDiagnosticRefused("protected input phase refused")


@dataclass(frozen=True, slots=True)
class OwnerApproval:
    """Host-owned approval of one exact plan. Never self-issued by a caller."""

    plan_digest: str
    expires_unix: float
    nonce: str

    def __post_init__(self) -> None:
        if (
            type(self.plan_digest) is not str
            or _DIGEST.fullmatch(self.plan_digest) is None
        ):
            raise LocalDiagnosticRefused("approval must bind an exact plan digest")
        if type(self.expires_unix) not in (int, float) or not math.isfinite(
            self.expires_unix
        ):
            raise LocalDiagnosticRefused("approval requires a finite expiry")
        if type(self.nonce) is not str or _NONCE.fullmatch(self.nonce) is None:
            raise LocalDiagnosticRefused("approval requires an exact nonce")


@dataclass(frozen=True, slots=True)
class LocalDiagnosticPlan:
    """A validated *proposal*. Holding one grants no execution authority."""

    operation: str
    identities: PinnedIdentities
    training_steps: int
    invocations: int
    retries: int
    process_wall_seconds: int
    task_wall_seconds: int
    max_output_bytes: int
    nonce: str

    @property
    def status(self) -> str:
        return STATUS

    @property
    def exclusivity(self) -> str:
        return EXCLUSIVITY

    @property
    def official_eligible(self) -> bool:
        # Development evidence never becomes official or strict acceptance.
        return False

    def document(self) -> dict[str, object]:
        return {
            "schema": SCHEMA,
            "status": STATUS,
            "operation": self.operation,
            "source_commit": self.identities.source_commit,
            "source_tree_digest": self.identities.source_tree_digest,
            "image_id": self.identities.image_id,
            "environment_lock_digest": self.identities.environment_lock_digest,
            "profile_digest": self.identities.profile_digest,
            "input_phase": self.identities.input_phase,
            "input_digest": self.identities.input_digest,
            "training_steps": self.training_steps,
            "invocations": self.invocations,
            "retries": self.retries,
            "process_wall_seconds": self.process_wall_seconds,
            "task_wall_seconds": self.task_wall_seconds,
            "max_output_bytes": self.max_output_bytes,
            "nonce": self.nonce,
            "exclusivity": EXCLUSIVITY,
            "device_memory_cap": "NOT_ENFORCED_BY_THIS_PLAN",
            "official_eligible": False,
            "score": None,
            "hardware_acceptance": "NOT_EXECUTED",
        }


def _bounded_int(document: dict, key: str, maximum: int, *, minimum: int = 0) -> int:
    value = document[key]
    if type(value) is not int or isinstance(value, bool):
        raise LocalDiagnosticRefused(f"{key} must be an exact integer")
    if not minimum <= value <= maximum:
        raise LocalDiagnosticRefused(f"{key} outside the development bound")
    return value


def validate_plan(document: object, *, pinned: PinnedIdentities) -> LocalDiagnosticPlan:
    """Validate a proposed plan against repository-pinned identities.

    Every field is checked for exact type and bound. Any caller-supplied
    execution control is a rejection rather than something to sanitize.
    """
    if type(document) is not dict:
        raise LocalDiagnosticRefused("exact plan document required")
    if type(pinned) is not PinnedIdentities:
        raise LocalDiagnosticRefused("repository-pinned identities required")

    present = set(document)
    forbidden = present & FORBIDDEN_FIELDS
    if forbidden:
        raise LocalDiagnosticRefused(
            "caller-supplied execution control refused: " + ",".join(sorted(forbidden))
        )
    if present != set(REQUIRED_FIELDS):
        raise LocalDiagnosticRefused("exact plan field set required")

    if document["schema"] != SCHEMA:
        raise LocalDiagnosticRefused("unregistered plan schema")
    if document["operation"] not in PERMITTED_OPERATIONS:
        raise LocalDiagnosticRefused("unregistered diagnostic operation")

    for field in (
        "source_commit",
        "source_tree_digest",
        "image_id",
        "environment_lock_digest",
        "profile_digest",
        "input_phase",
        "input_digest",
    ):
        if document[field] != getattr(pinned, field):
            raise LocalDiagnosticRefused(f"{field} does not match the pinned identity")

    steps = _bounded_int(document, "training_steps", MAX_TRAINING_STEPS, minimum=1)
    invocations = _bounded_int(document, "invocations", MAX_INVOCATIONS, minimum=1)
    retries = _bounded_int(document, "retries", MAX_RETRIES)
    process_wall = _bounded_int(
        document, "process_wall_seconds", MAX_PROCESS_WALL_SECONDS, minimum=1
    )
    task_wall = _bounded_int(
        document, "task_wall_seconds", MAX_TASK_WALL_SECONDS, minimum=1
    )
    output_bytes = _bounded_int(
        document, "max_output_bytes", MAX_OUTPUT_BYTES, minimum=1
    )
    if process_wall > task_wall:
        raise LocalDiagnosticRefused(
            "per-process deadline cannot exceed the whole-task deadline"
        )

    nonce = document["nonce"]
    if type(nonce) is not str or _NONCE.fullmatch(nonce) is None:
        raise LocalDiagnosticRefused("exact run nonce required")

    return LocalDiagnosticPlan(
        operation=document["operation"],
        identities=pinned,
        training_steps=steps,
        invocations=invocations,
        retries=retries,
        process_wall_seconds=process_wall,
        task_wall_seconds=task_wall,
        max_output_bytes=output_bytes,
        nonce=nonce,
    )


def check_owner_approval(
    plan: LocalDiagnosticPlan,
    approval: object,
    *,
    plan_digest: str,
    now: float,
    consumed_nonces: frozenset[str] = frozenset(),
) -> None:
    """Require an unexpired host-owned approval bound to this exact plan."""
    if type(plan) is not LocalDiagnosticPlan:
        raise LocalDiagnosticRefused("validated plan required")
    if approval is None:
        raise LocalDiagnosticRefused("owner approval is missing")
    if type(approval) is not OwnerApproval:
        raise LocalDiagnosticRefused("exact owner approval record required")
    if type(plan_digest) is not str or _DIGEST.fullmatch(plan_digest) is None:
        raise LocalDiagnosticRefused("exact plan digest required")
    if approval.plan_digest != plan_digest:
        raise LocalDiagnosticRefused("approval does not bind this plan")
    if approval.nonce != plan.nonce:
        raise LocalDiagnosticRefused("approval nonce does not bind this run")
    if type(now) is not float or not math.isfinite(now):
        raise LocalDiagnosticRefused("exact current time required")
    if now >= approval.expires_unix:
        raise LocalDiagnosticRefused("owner approval has expired")
    if type(consumed_nonces) is not frozenset:
        raise LocalDiagnosticRefused("exact consumed-nonce set required")
    if plan.nonce in consumed_nonces:
        raise LocalDiagnosticRefused("replayed run nonce refused")


def check_previous_cleanup(outcome: object) -> None:
    """An ambiguous previous cleanup blocks the next diagnostic.

    This never clears, reuses or reinterprets strict quarantine state, and it
    never reports a device as released.
    """
    if outcome not in ("CLEAN", "NONE"):
        raise LocalDiagnosticRefused(
            "previous diagnostic cleanup is unreconciled; operator reconciliation "
            "is required and strict quarantine is never cleared here"
        )


def require_local_diagnostic_dispatch(plan: object) -> None:
    """Always refuses. Preparation never becomes execution by being merged.

    Activation needs a separate owner decision on the proposed development
    contract, an approved run plan, and host controls that do not yet exist.
    Nothing in this module may be read as that decision.
    """
    raise LocalDiagnosticRefused(
        "local_diagnostic.dispatch_disabled: the development contract is PROPOSED, "
        "no owner-approved run plan exists, and no established observation source "
        "or host grant is present"
    )
