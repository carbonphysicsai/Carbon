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

import fcntl
import math
import os
import re
from contextlib import contextmanager
from dataclasses import dataclass, fields
from pathlib import Path

from carbon.reconstruction.accelerators import GPU_PROFILE, AcceleratorRole
from carbon.reconstruction.worker.accelerator_runtime import (
    HOST_ROOT,
    host_device,
    shared_host_lease,
)
from carbon.reconstruction.worker.model import (
    MEMORY_BYTES,
    OUTPUT_BYTES,
    PRODUCTIVE_DEADLINE_SECONDS,
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

REGISTERED_OPERATIONS = frozenset({"registered_trainer_fit"})

# Attempt outcomes. Two independent questions decide these, and conflating them
# is how an attempt journal starts lying: did the work produce a result, and are
# this launch's host resources known to be released?
#
#   RESERVED    in flight, or the controller died before it could reconcile.
#               Blocks, because an unfinished attempt may still hold the device.
#   COMPLETED   the work produced its result and cleanup was confirmed.
#   RECONCILED  the work did not succeed - it failed, or was cancelled - but
#               cleanup was confirmed. Distinct from COMPLETED on purpose: this
#               record must never read as science that did not happen.
#   AMBIGUOUS   cleanup could not be established. Blocks until an operator
#               reconciles it.
#
# Every one of these counts against the budget. None of them is a refund.
ATTEMPT_RESERVED = "RESERVED"
ATTEMPT_COMPLETED = "COMPLETED"
ATTEMPT_RECONCILED = "RECONCILED_NOT_SUCCESSFUL"
ATTEMPT_AMBIGUOUS = "AMBIGUOUS"

# The states that keep the single Carbon host slot closed to a new launch.
ATTEMPT_BLOCKING = frozenset({ATTEMPT_RESERVED, ATTEMPT_AMBIGUOUS})
ATTEMPT_TERMINAL = frozenset({ATTEMPT_COMPLETED, ATTEMPT_RECONCILED, ATTEMPT_AMBIGUOUS})

# Attempt markers carry what the attempt charged against the batch, so the
# schema that carries them is identified. A marker written under an older schema
# recorded no charge; it is read as *unknown* consumption rather than as zero,
# which keeps its historical meaning intact and fails towards refusing a launch.
ATTEMPT_SCHEMA = "carbon.accelerator-development-attempt.v2"
CHARGE_OUTPUT_BYTES = "charged_output_bytes"
OBSERVED_SECONDS = "observed_seconds"

# How a marker's output charge was arrived at. Only an observed charge may be
# lower than the reservation; the basis records which of the two this is.
CHARGE_RESERVED = "RESERVED_WORST_CASE"
CHARGE_OBSERVED = "OBSERVED"

# The two batch bounds are enforced differently because they mean different
# things. Output accumulates, so it is summed across attempts. Time does not
# accumulate the same way: the envelope bounds the batch at a fixed span *from
# first admission*, including the gaps between attempts, so idling between runs
# consumes the batch exactly as running does and neither a pause nor a restart
# rewinds it. Summing per-attempt durations would silently permit both.

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
        "operation",
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


def _charge_int(value: object) -> int:
    """A recorded charge. Zero is a real measurement; a bool or a float is not."""
    if type(value) is not int or isinstance(value, bool) or value < 0:
        raise WorkerFailure(WorkerCode.POLICY)
    return value


# Ceilings the worker implementation actually enforces, by limit name. An
# approval may ask for less than these; it can never ask for more, because these
# are what the container, the deadline owner and the export are built to apply.
#
# `training_steps` is deliberately absent: the implementation registers no
# independent step ceiling, so the approval's value is the controlling one and is
# carried to the worker rather than being clamped against an invented constant.
REGISTERED_CONTROL_CEILINGS = {
    "productive_seconds": PRODUCTIVE_DEADLINE_SECONDS,
    "output_bytes": OUTPUT_BYTES,
    "host_ram_bytes": MEMORY_BYTES,
}

# Limits that bound one invocation and must be represented as positive integers
# before anything is reserved.
_BOUNDED_CONTROLS = frozenset(
    {
        "productive_seconds",
        "cleanup_seconds",
        "attempt_seconds",
        "batch_seconds",
        "host_ram_bytes",
        "output_bytes",
        "batch_output_bytes",
        "training_steps",
    }
)


def effective_controls(limits: dict) -> dict:
    """Resolve the limits this run will actually be executed under.

    An approved limit that never reaches the container, the deadline owner or the
    export is not a limit; it is a claim in a record. This resolves one closed
    object, before any reservation, that satisfies *both* the installed approval
    and the registered implementation policy.

    Neither side may relax the other. Where the approval is tighter it wins, so a
    narrower approval genuinely narrows the run. Where the implementation's
    registered ceiling is tighter that ceiling wins, so an approval cannot widen
    what the worker is built to enforce - the existing 4 GiB worker memory cap
    stays controlling even against an 8 GiB approval.

    A limit that cannot be represented is refused here rather than rounded into
    something supportable. Rounding an unenforceable request up to a value the
    implementation happens to allow would be the precise failure this exists to
    prevent.
    """
    if type(limits) is not dict or set(limits) != REQUIRED_LIMITS:
        raise WorkerFailure(WorkerCode.POLICY)
    resolved: dict[str, object] = {}
    for name in sorted(_BOUNDED_CONTROLS):
        value = _positive_int(limits[name])
        ceiling = REGISTERED_CONTROL_CEILINGS.get(name)
        resolved[name] = value if ceiling is None else min(value, ceiling)
    network = limits["worker_network"]
    if network != "DISABLED":
        # The worker network is not a dial. The registered implementation runs
        # with no network, so an approval asking for anything else is asking for
        # a run this worker cannot perform.
        raise WorkerFailure(WorkerCode.POLICY)
    resolved["worker_network"] = network
    # Coherence, checked once here rather than assumed at each use.
    if (
        resolved["productive_seconds"] + resolved["cleanup_seconds"]
        > resolved["attempt_seconds"]
    ):
        raise WorkerFailure(WorkerCode.POLICY)
    if resolved["attempt_seconds"] > resolved["batch_seconds"]:
        raise WorkerFailure(WorkerCode.POLICY)
    if resolved["output_bytes"] > resolved["batch_output_bytes"]:
        raise WorkerFailure(WorkerCode.POLICY)
    return resolved


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
            or doc["device_uuid"] != host_device().device_uuid
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
        # The approved operation is part of the authority, not a caller choice.
        if doc["operation"] not in REGISTERED_OPERATIONS:
            raise WorkerFailure(WorkerCode.POLICY)
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

    @contextmanager
    def _accounting_lock(self):
        """Serialize count-then-create so the budget cannot be overspent.

        Per-nonce O_EXCL only stops the *same* nonce being created twice. Two
        different nonces could each observe the last free attempt and then both
        create their marker, taking five attempts from a budget of four. This
        lock closes that window.

        It guards accounting only. It is not a device slot, it never gates access
        to the GPU, and it is a different file from the shared host lease, so a
        caller that takes the lease afterwards cannot deadlock against it.
        """
        try:
            self.root.mkdir(mode=0o700, exist_ok=True)
            descriptor = os.open(self.root / ".lock", os.O_RDWR | os.O_CREAT, 0o600)
        except OSError:
            raise WorkerFailure(WorkerCode.UNAVAILABLE) from None
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            yield
        finally:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
            finally:
                os.close(descriptor)

    def consumed(self) -> int:
        """Every reserved attempt counts, including failed and ambiguous ones."""
        return len(self._markers())

    def _batch_state(self) -> tuple[float | None, int]:
        """When this batch was first admitted, and what its attempts have charged.

        Read from the markers rather than accumulated in memory, for the same
        reason the attempt count is: a new process, worktree or output directory
        must not be able to present a batch as less consumed than it is. The
        first admission is the earliest reservation on record, so a later
        process cannot restart the window by forgetting the earlier one.

        A marker this cannot read - an older schema, a missing or malformed
        field - raises rather than contributing zero. Treating an unreadable
        record as no consumption would let exactly the attempt that lost its
        accounting be the one that widens the batch.
        """
        first: float | None = None
        output = 0
        for marker in self._markers():
            document = self._read(marker)
            if document.get("schema") != ATTEMPT_SCHEMA:
                raise WorkerFailure(WorkerCode.POLICY)
            reserved = document.get("reserved_unix")
            if type(reserved) is not float or not math.isfinite(reserved):
                raise WorkerFailure(WorkerCode.POLICY)
            first = reserved if first is None else min(first, reserved)
            output += _charge_int(document.get(CHARGE_OUTPUT_BYTES))
        return first, output

    def batch_consumption(self) -> dict[str, object]:
        """What the batch has consumed. Output is worst case where unobserved."""
        first, output = self._batch_state()
        return {
            "first_admission_unix": first,
            CHARGE_OUTPUT_BYTES: output,
        }

    def blocking_attempt(self) -> dict[str, object] | None:
        """An unreconciled attempt blocks the next launch until an operator acts."""
        for path in self._markers():
            document = self._read(path)
            if document.get("state") in ATTEMPT_BLOCKING:
                return document
        return None

    def attempt(self, *, nonce: str) -> dict[str, object] | None:
        """The recorded marker for one nonce, or None if it was never reserved."""
        if type(nonce) is not str or not _NONCE.fullmatch(nonce):
            raise WorkerFailure(WorkerCode.POLICY)
        path = self.root / f"{nonce}.json"
        if not path.exists():
            return None
        return self._read(path)

    def reserve(
        self,
        *,
        nonce: str,
        plan_digest: str,
        budget: int,
        controls: dict,
        now: float,
    ) -> Path:
        """Atomically consume one attempt. Conservative: reserved before dispatch.

        Three separate allowances bind here, and an attempt must satisfy all of
        them: the attempt count, the batch's time window, and the batch's total
        output. The count alone never bounded the batch - four attempts each
        inside a per-attempt deadline can still run far past the whole-batch
        one, and each would have looked individually compliant.

        The output charge is the attempt's own worst case, taken before
        dispatch, because what the attempt will actually write is not knowable
        yet; ``settle`` reduces it to what was observed. The time bound needs no
        charge: it is the span since this batch was first admitted.
        """
        from carbon.development_session.profile import canonical

        if type(nonce) is not str or not _NONCE.fullmatch(nonce):
            raise WorkerFailure(WorkerCode.POLICY)
        if type(plan_digest) is not str or not _DIGEST.fullmatch(plan_digest):
            raise WorkerFailure(WorkerCode.POLICY)
        _positive_int(budget)
        if type(controls) is not dict or set(controls) != REQUIRED_LIMITS:
            # The resolved controls, not the raw approval: the batch must be
            # charged against the limits the run will actually execute under.
            raise WorkerFailure(WorkerCode.POLICY)
        attempt_seconds = _positive_int(controls["attempt_seconds"])
        charge_output = _positive_int(controls["output_bytes"])
        batch_seconds = _positive_int(controls["batch_seconds"])
        batch_output = _positive_int(controls["batch_output_bytes"])
        if type(now) is not float or not math.isfinite(now):
            raise WorkerFailure(WorkerCode.POLICY)

        try:
            self.root.mkdir(mode=0o700, exist_ok=True)
        except OSError:
            raise WorkerFailure(WorkerCode.UNAVAILABLE) from None

        path = self.root / f"{nonce}.json"
        payload = canonical(
            {
                "schema": ATTEMPT_SCHEMA,
                "nonce": nonce,
                "plan_digest": plan_digest,
                "reserved_unix": float(now),
                "state": ATTEMPT_RESERVED,
                CHARGE_OUTPUT_BYTES: charge_output,
                "charge_basis": CHARGE_RESERVED,
                OBSERVED_SECONDS: None,
            }
        )
        with self._accounting_lock():
            # Checked and created under one lock, so a concurrent caller with a
            # different nonce cannot also observe the last free attempt.
            if self.blocking_attempt() is not None:
                raise WorkerFailure(WorkerCode.CONFLICT)
            if self.consumed() >= budget:
                raise WorkerFailure(WorkerCode.POLICY)
            first, spent_output = self._batch_state()
            # Read and decided under the one lock that already serializes the
            # count, so two different nonces cannot each observe the same
            # remaining batch allowance and both take it.
            if spent_output + charge_output > batch_output:
                raise WorkerFailure(WorkerCode.POLICY)
            if first is not None:
                if now < first:
                    # The window is wall-clock, so a clock that moved backwards
                    # leaves it unestablished. Refusing is the only reading that
                    # cannot be used to rewind a batch that is already spent.
                    raise WorkerFailure(WorkerCode.POLICY)
                # Admitted only if the attempt can *finish* inside the window.
                # Admitting one that is still permitted to run for its full
                # deadline past the batch bound would leave that bound
                # unenforceable at exactly the moment it starts to bind.
                if now + attempt_seconds > first + batch_seconds:
                    raise WorkerFailure(WorkerCode.POLICY)
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

    def settle(
        self,
        *,
        nonce: str,
        state: str,
        observed_seconds: int | None = None,
        observed_output_bytes: int | None = None,
    ) -> None:
        """Record a terminal outcome. Never removes the attempt from the budget.

        Only a RESERVED attempt may be settled, so a settled record cannot be
        rewritten - in particular an AMBIGUOUS marker cannot be relabelled to
        obtain another launch.

        The reserved output charge is reduced to an observed one, and only to
        that. A value that was not observed stays at its worst case, so the safe
        direction is also the default: a caller that measures nothing, or a
        process that dies before settling, leaves the batch fully charged.

        An AMBIGUOUS attempt keeps its reservation whatever was measured. An
        uncertain cleanup has not established that the attempt stopped
        consuming, and a measurement taken while that is unresolved would be
        reporting a floor as a total.

        The observed duration is recorded as evidence about this attempt. It is
        deliberately not what bounds the batch: the batch's time bound is the
        span since first admission, which no per-attempt measurement can shorten.
        """
        from carbon.development_session.profile import canonical

        if state not in ATTEMPT_TERMINAL:
            raise WorkerFailure(WorkerCode.POLICY)
        if type(nonce) is not str or not _NONCE.fullmatch(nonce):
            raise WorkerFailure(WorkerCode.POLICY)
        path = self.root / f"{nonce}.json"
        document = dict(self._read(path))
        if document.get("state") != ATTEMPT_RESERVED:
            raise WorkerFailure(WorkerCode.POLICY)
        if document.get("schema") != ATTEMPT_SCHEMA:
            raise WorkerFailure(WorkerCode.POLICY)
        document["state"] = state
        if observed_seconds is not None:
            # Recorded as measured even when it exceeds the attempt's deadline.
            # An overrun is a fact about the run; rounding it back to the bound
            # it broke would erase the evidence that it did.
            document[OBSERVED_SECONDS] = _charge_int(observed_seconds)
        if state != ATTEMPT_AMBIGUOUS and observed_output_bytes is not None:
            document[CHARGE_OUTPUT_BYTES] = _charge_int(observed_output_bytes)
            document["charge_basis"] = CHARGE_OBSERVED
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


@dataclass(frozen=True, slots=True)
class LocalDiagnosticRequest:
    """Operator-only selector for the local development route.

    A typed object, deliberately not a Boolean or a string: a public, miner,
    customer or evaluator route has no way to construct one, so it cannot select
    the local entry by setting a flag on a request it controls. Holding one
    grants nothing on its own; the controller still verifies the private
    approval, and every identity here must equal the approved record.
    """

    plan_digest: str
    input_digest: str
    nonce: str

    def __post_init__(self) -> None:
        for value in (self.plan_digest, self.input_digest):
            if type(value) is not str or not _DIGEST.fullmatch(value):
                raise WorkerFailure(WorkerCode.POLICY)
        if type(self.nonce) is not str or not _NONCE.fullmatch(self.nonce):
            raise WorkerFailure(WorkerCode.POLICY)
        if self.plan_digest == self.input_digest:
            # Two distinct identities; one may never stand in for the other.
            raise WorkerFailure(WorkerCode.POLICY)


DIAGNOSTIC_PLAN_SCHEMA = "carbon.accelerator-development-diagnostic-plan.v1"


def diagnostic_plan_identity(
    *,
    construction_plan_digest: str,
    training_archive_digest: str,
    training_archive_provenance: str,
    training_archive_role: str,
    image: WorkerImageIdentity,
    profile_digest: str,
    role: AcceleratorRole,
    operation: str,
    limits: dict,
) -> tuple[str, dict]:
    """Derive the diagnostic-plan identity from the work itself.

    The digest is computed from validated execution content and the resolved
    controls, never from a caller-supplied string. A selector that merely echoes
    a well-formed digest cannot authorize work whose recipe, inputs, image, role,
    operation or limits differ, because a different body yields a different
    identity.

    This is deliberately distinct from the construction-plan digest, which
    identifies the scientific recipe, and from the approval-record digest, which
    identifies the authority. The construction-plan digest is an *input* here.
    """
    from carbon.development_session.profile import canonical

    if type(image) is not WorkerImageIdentity:
        raise WorkerFailure(WorkerCode.POLICY)
    if type(role) is not AcceleratorRole:
        raise WorkerFailure(WorkerCode.POLICY)
    if operation not in REGISTERED_OPERATIONS:
        raise WorkerFailure(WorkerCode.POLICY)
    for value in (construction_plan_digest, training_archive_digest, profile_digest):
        if type(value) is not str or not _DIGEST.fullmatch(value):
            raise WorkerFailure(WorkerCode.POLICY)
    if type(training_archive_provenance) is not str or not training_archive_provenance:
        raise WorkerFailure(WorkerCode.POLICY)
    if training_archive_role != "TRAIN":
        # A local diagnostic never reads an evaluation or protected cohort.
        raise WorkerFailure(WorkerCode.POLICY)
    if type(limits) is not dict or set(limits) != REQUIRED_LIMITS:
        raise WorkerFailure(WorkerCode.POLICY)

    body = {
        "schema": DIAGNOSTIC_PLAN_SCHEMA,
        "construction_plan_digest": construction_plan_digest,
        "training_archive": {
            "digest": training_archive_digest,
            "provenance": training_archive_provenance,
            "role": training_archive_role,
        },
        # The whole image identity, not a chosen subset: binding only image_id
        # would assume it already covers the component digests, and a record
        # carrying the same id with a different wheel or entrypoint would pass.
        "image": {
            field.name: getattr(image, field.name)
            for field in sorted(fields(image), key=lambda f: f.name)
        },
        "profile_digest": profile_digest,
        "role": role.value,
        "operation": operation,
        "limits": {key: limits[key] for key in sorted(limits)},
    }
    return tagged_sha256(canonical(body)), body
