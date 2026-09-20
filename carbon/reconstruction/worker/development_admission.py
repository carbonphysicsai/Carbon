"""Operator-installed LOCAL DEVELOPMENT approval. Deliberately not a strict grant.

This record exists because the strict accelerator contract cannot be satisfied on
a host whose compute-process enumeration is unestablished. Rather than assert
untrue things in a strict grant, a development run carries its own separately
typed authority that asserts *less*:

* It uses a distinct schema and a distinct private file. It is never written to,
  read from, or derived from ``grant.json``.
* It claims no exclusivity, no dedicated host use and no device memory
  enforcement. Its allocation and host-use values say so explicitly.
* Strict consumers reject it. ``AcceleratorHostAdmission.verify`` requires the
  strict schema, so this document fails there on its own terms, and
  ``require_development_approval`` symmetrically refuses a strict grant.
* It is operator-installed. Nothing a participant can reach issues one, and the
  approving authority is recorded rather than inferred from a commit author.

Attempt accounting is durable and atomic: each attempt reserves an ``O_EXCL``
marker before any container can be created, so a crash, a restart, a changed
output directory or a concurrent caller cannot reset the budget or replay a
nonce. An ambiguous outcome stays ambiguous and blocks further launches; it is
never cleared here, and it never becomes a verified whole-device release.
"""

from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass
from pathlib import Path

from carbon.reconstruction.accelerators import GPU_PROFILE, AcceleratorRole
from carbon.reconstruction.worker.accelerator_runtime import (
    HOST_ROOT,
    shared_host_lease,
)
from carbon.reconstruction.worker.model import (
    WorkerCode,
    WorkerFailure,
    WorkerImageIdentity,
    exact_digest,
    tagged_sha256,
)

DEVELOPMENT_SCHEMA = "carbon.accelerator-development-approval.v1"
DEVELOPMENT_RECORD = "development-approval.json"
ATTEMPT_DIRECTORY = "development-attempts"

# This approval asserts the opposite of the strict grant's host claims. The
# strings differ deliberately so a strict comparison can never match them.
DEVELOPMENT_ALLOCATION = "TASK_OWNED_NOT_EXCLUSIVE"
DEVELOPMENT_HOST_USE = "SHARED_HOST_EXCLUSIVITY_UNESTABLISHED"
DEVELOPMENT_CLEANUP = "TASK_OWNED_RESOURCE_REMOVAL_ONLY"

ATTEMPT_RESERVED = "RESERVED"
ATTEMPT_COMPLETED = "COMPLETED"
ATTEMPT_AMBIGUOUS = "AMBIGUOUS"

_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
_NONCE = re.compile(r"[0-9a-f]{32}")

REQUIRED_FIELDS = frozenset(
    {
        "schema",
        "status",
        "authority",
        "approval_id",
        "approving_owner",
        "approval_provenance",
        "host_root",
        "controller_root",
        "principal",
        "roles",
        "device_uuid",
        "execution_profile_digest",
        "environment_lock_digest",
        "image_id",
        "plan_digest",
        "input_digest",
        "expires_unix",
        "attempt_budget",
        "limits",
        "allocation",
        "host_use",
        "cleanup",
    }
)

REQUIRED_LIMITS = frozenset(
    {
        "productive_seconds",
        "cleanup_seconds",
        "attempt_seconds",
        "batch_seconds",
        "host_ram_bytes",
        "output_bytes",
        "batch_output_bytes",
        "training_steps",
        "worker_network",
    }
)


def _positive_int(value: object) -> int:
    if type(value) is not int or isinstance(value, bool) or value <= 0:
        raise WorkerFailure(WorkerCode.POLICY)
    return value


@dataclass(frozen=True, slots=True)
class DevelopmentHostApproval:
    """Immutable reference to an operator-installed, revocable local approval."""

    document: dict[str, object]
    digest: str

    @classmethod
    def load(cls) -> DevelopmentHostApproval:
        from carbon.development_session.profile import canonical
        from carbon.development_session.research_admission import private_json

        try:
            document = private_json(HOST_ROOT / DEVELOPMENT_RECORD)
        except (OSError, ValueError):
            raise WorkerFailure(WorkerCode.UNAVAILABLE) from None
        if type(document) is not dict or document.get("schema") != DEVELOPMENT_SCHEMA:
            # A strict grant, or anything else, is not a development approval.
            raise WorkerFailure(WorkerCode.POLICY)
        return cls(document, tagged_sha256(canonical(document)))

    def verify(
        self,
        *,
        principal: str,
        state_root: Path,
        image: WorkerImageIdentity,
        role: AcceleratorRole,
        plan_digest: str,
        input_digest: str,
        now: float,
    ) -> None:
        """Bind this approval to the exact run about to be attempted."""
        fresh = self.load()
        if (HOST_ROOT / "device-quarantined").exists():
            # A strict quarantine blocks local work too, and is never cleared here.
            raise WorkerFailure(WorkerCode.QUARANTINED)
        if fresh.document != self.document or fresh.digest != self.digest:
            raise WorkerFailure(WorkerCode.POLICY)

        doc = self.document
        if set(doc) != REQUIRED_FIELDS:
            raise WorkerFailure(WorkerCode.POLICY)
        if type(plan_digest) is not str or not _DIGEST.fullmatch(plan_digest):
            raise WorkerFailure(WorkerCode.POLICY)
        if type(input_digest) is not str or not _DIGEST.fullmatch(input_digest):
            raise WorkerFailure(WorkerCode.POLICY)
        if type(role) is not AcceleratorRole:
            raise WorkerFailure(WorkerCode.POLICY)
        if type(image) is not WorkerImageIdentity:
            raise WorkerFailure(WorkerCode.POLICY)

        if (
            doc["schema"] != DEVELOPMENT_SCHEMA
            or doc["status"] != "APPROVED"
            or type(doc["authority"]) is not str
            or not doc["authority"]
            or type(doc["approval_id"]) is not str
            or not doc["approval_id"]
            or type(doc["approving_owner"]) is not str
            or not doc["approving_owner"]
            or type(doc["approval_provenance"]) is not str
            or not doc["approval_provenance"]
            or doc["host_root"] != str(HOST_ROOT)
            or doc["controller_root"] != str(state_root)
            or state_root.resolve() != state_root
            or doc["principal"] != principal
            or type(doc["roles"]) is not list
            or not doc["roles"]
            or any(v not in [r.value for r in AcceleratorRole] for v in doc["roles"])
            or role.value not in doc["roles"]
            or doc["device_uuid"] != GPU_PROFILE.device_uuid
            or doc["execution_profile_digest"] != GPU_PROFILE.digest
            or doc["environment_lock_digest"] != GPU_PROFILE.environment_lock_digest
            or image.lock_digest != GPU_PROFILE.environment_lock_digest
            or doc["image_id"] != image.image_id
            or doc["plan_digest"] != plan_digest
            or doc["input_digest"] != input_digest
            # This approval must never carry strict host assertions.
            or doc["allocation"] != DEVELOPMENT_ALLOCATION
            or doc["host_use"] != DEVELOPMENT_HOST_USE
            or doc["cleanup"] != DEVELOPMENT_CLEANUP
        ):
            raise WorkerFailure(WorkerCode.POLICY)

        exact_digest(doc["plan_digest"])
        exact_digest(doc["input_digest"])
        _positive_int(doc["attempt_budget"])

        limits = doc["limits"]
        if type(limits) is not dict or set(limits) != REQUIRED_LIMITS:
            raise WorkerFailure(WorkerCode.POLICY)
        for key in REQUIRED_LIMITS - {"worker_network"}:
            _positive_int(limits[key])
        if limits["worker_network"] != "DISABLED":
            raise WorkerFailure(WorkerCode.POLICY)
        if (
            limits["productive_seconds"] + limits["cleanup_seconds"]
            > limits["attempt_seconds"]
        ):
            raise WorkerFailure(WorkerCode.POLICY)
        if limits["attempt_seconds"] > limits["batch_seconds"]:
            raise WorkerFailure(WorkerCode.POLICY)

        expiry = doc["expires_unix"]
        if (
            type(now) is not float
            or not math.isfinite(now)
            or type(expiry) not in (float, int)
            or not math.isfinite(expiry)
            or now >= expiry
            # Remaining validity must cover the attempt and its cleanup reserve.
            or now + limits["attempt_seconds"] > expiry
        ):
            raise WorkerFailure(WorkerCode.DEADLINE)

    def exclusive_lease(self):
        """Take the one shared Carbon device slot, not a parallel local one."""
        return shared_host_lease()


class DevelopmentAttemptJournal:
    """Durable, atomic attempt accounting for the local diagnostic batch.

    One ``O_EXCL`` marker per attempt, created before anything can attach the
    device. Restart-safe by construction: the filesystem holds the record, not a
    caller-supplied set, so a new process, worktree or output directory cannot
    reset the budget or replay a nonce.
    """

    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or HOST_ROOT) / ATTEMPT_DIRECTORY

    def _markers(self) -> list[Path]:
        try:
            return sorted(self.root.glob("*.json"))
        except OSError:
            raise WorkerFailure(WorkerCode.UNAVAILABLE) from None

    def _read(self, path: Path) -> dict[str, object]:
        from carbon.development_session.research_admission import private_json

        try:
            return private_json(path)
        except (OSError, ValueError):
            raise WorkerFailure(WorkerCode.POLICY) from None

    def consumed(self) -> int:
        """Every reserved attempt counts, including failed and ambiguous ones."""
        return len(self._markers())

    def blocking_attempt(self) -> dict[str, object] | None:
        """An unreconciled attempt blocks the next launch until an operator acts."""
        for path in self._markers():
            document = self._read(path)
            if document.get("state") in (ATTEMPT_RESERVED, ATTEMPT_AMBIGUOUS):
                return document
        return None

    def reserve(self, *, nonce: str, plan_digest: str, budget: int, now: float) -> Path:
        """Atomically consume one attempt. Conservative: reserved before dispatch."""
        from carbon.development_session.profile import canonical

        if type(nonce) is not str or not _NONCE.fullmatch(nonce):
            raise WorkerFailure(WorkerCode.POLICY)
        if type(plan_digest) is not str or not _DIGEST.fullmatch(plan_digest):
            raise WorkerFailure(WorkerCode.POLICY)
        _positive_int(budget)
        if type(now) is not float or not math.isfinite(now):
            raise WorkerFailure(WorkerCode.POLICY)

        try:
            self.root.mkdir(mode=0o700, exist_ok=True)
        except OSError:
            raise WorkerFailure(WorkerCode.UNAVAILABLE) from None

        if self.blocking_attempt() is not None:
            raise WorkerFailure(WorkerCode.CONFLICT)
        if self.consumed() >= budget:
            raise WorkerFailure(WorkerCode.POLICY)

        path = self.root / f"{nonce}.json"
        payload = canonical(
            {
                "schema": "carbon.accelerator-development-attempt.v1",
                "nonce": nonce,
                "plan_digest": plan_digest,
                "reserved_unix": float(now),
                "state": ATTEMPT_RESERVED,
            }
        )
        try:
            descriptor = os.open(
                path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
            )
        except FileExistsError:
            # A replayed nonce never consumes a second attempt or dispatches.
            raise WorkerFailure(WorkerCode.CONFLICT) from None
        except OSError:
            raise WorkerFailure(WorkerCode.UNAVAILABLE) from None
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            directory = os.open(self.root, os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        except OSError:
            raise WorkerFailure(WorkerCode.UNAVAILABLE) from None
        return path

    def settle(self, *, nonce: str, state: str) -> None:
        """Record a terminal outcome. Never removes the attempt from the budget."""
        from carbon.development_session.profile import canonical

        if state not in (ATTEMPT_COMPLETED, ATTEMPT_AMBIGUOUS):
            raise WorkerFailure(WorkerCode.POLICY)
        if type(nonce) is not str or not _NONCE.fullmatch(nonce):
            raise WorkerFailure(WorkerCode.POLICY)
        path = self.root / f"{nonce}.json"
        document = dict(self._read(path))
        if document.get("state") != ATTEMPT_RESERVED:
            raise WorkerFailure(WorkerCode.POLICY)
        document["state"] = state
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_TRUNC | os.O_NOFOLLOW)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(canonical(document))
                handle.flush()
                os.fsync(handle.fileno())
        except OSError:
            raise WorkerFailure(WorkerCode.UNAVAILABLE) from None


def require_development_approval(approval: object) -> DevelopmentHostApproval:
    """Accept only a development approval; a strict grant can never pass here."""
    if type(approval) is not DevelopmentHostApproval:
        raise WorkerFailure(WorkerCode.POLICY)
    document = approval.document
    if (
        type(document) is not dict
        or document.get("schema") != DEVELOPMENT_SCHEMA
        or document.get("allocation") != DEVELOPMENT_ALLOCATION
        or document.get("host_use") != DEVELOPMENT_HOST_USE
    ):
        raise WorkerFailure(WorkerCode.POLICY)
    return approval
