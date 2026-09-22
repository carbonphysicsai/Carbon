"""What the research server needs to survive a real client.

Four production gaps, and one principle shared with `mcp_onboarding`: a record
is built from a value that only validation can produce, never from what the
caller supplied. There the type was `PublicAddress`; here it is
`BoundPrincipal`, which cannot be constructed from a string at all. So a record
cannot attribute a call to a caller-named identity even by mistake - not because
a check rejects it, but because there is no way to express it.

**Records.** Per call: which operation, which bound principal, what happened,
how long it took. Never the arguments. A research argument carries a miner's
hypothesis, their strategy parameters and their file contents - their work,
which is the thing they came here to keep. The operation id is recorded as a
digest so retries still correlate without storing caller-controlled bytes.

**Capacity.** A bound on concurrent calls, and a deadline on *waiting* for
capacity.

The deadline deliberately does not cancel a call that has already started, and
that is the most important decision in this module. `adapter.call` reserves
against the campaign ledger. Cancelling it mid-flight would leave a reservation
whose outcome nobody knows, which is precisely the `requires_reconciliation`
state the campaign model exists to avoid - so a transport-level timeout would be
manufacturing the failure it was added to contain. Carbon already bounds the
work itself, through the `seconds` argument and task supervision. A call that
overruns its budget is therefore recorded as an overrun and allowed to finish.

Queue waiting is different: nothing has been dispatched, so refusing is free and
tells the caller something true. That is where the deadline bites.

**Refusals.** A stable slug a client can branch on, and the next usable step.
The slug is the enum value, so it cannot drift from the adapter's own vocabulary,
and the next action is a fixed sentence per slug rather than a provider message -
provider text is where unbounded internal detail reaches an external wire.
"""

from __future__ import annotations

import asyncio
import hashlib
import time

from carbon.miner_mcp.standard import AdapterCode

SCHEMA = "carbon.mcp.call-record.v1"
CATALOGUE = "carbon.mcp.catalogue.v1"
CATALOGUE_URI = "carbon://research/v1/catalogue"

#: Concurrent research calls. One client, one campaign, one owner: the ledger
#: serialises real consumption anyway, so this bounds how much work can be in
#: flight ahead of it rather than trying to be a scheduler.
MAX_CONCURRENT_CALLS = 4

#: Seconds a call may wait for capacity before being refused. Nothing has been
#: dispatched at this point, so refusing costs the caller nothing but a retry.
QUEUE_DEADLINE_SECONDS = 30.0

#: Seconds after which a running call is recorded as an overrun. It is not
#: cancelled - see the module docstring.
CALL_BUDGET_SECONDS = 900.0

#: What a client should do about each refusal. Fixed text per slug: a provider
#: message here is how unbounded internal detail reaches an external wire.
NEXT_ACTION = {
    AdapterCode.INVALID_ARGUMENT.value: (
        "Correct the arguments against the tool schema and call again with a "
        "new operation_id."
    ),
    AdapterCode.OWNER_BINDING.value: (
        "This server is bound to a different campaign owner. Reconnect with the "
        "profile that owns this campaign; do not retry."
    ),
    AdapterCode.OPERATIONAL_STOP.value: (
        "The campaign is not accepting work. Check task and reconciliation "
        "state before retrying; a retry now will be refused the same way."
    ),
    AdapterCode.INVALID_RESULT.value: (
        "The controller returned a result this server will not forward. Do not "
        "retry; report it with the operation_id you used."
    ),
    "CAPACITY_UNAVAILABLE": (
        "This server is at its concurrent-call bound. Nothing was dispatched. "
        "Retry the same operation_id shortly."
    ),
}

#: Reported outcomes. Closed, so a record cannot carry free text describing what
#: a caller supplied.
OUTCOMES = frozenset({"OK", "REFUSED", "OVERRAN", "CAPACITY_UNAVAILABLE"})


class BoundPrincipal(str):
    """The caller identity, derivable only from an owner-bound adapter.

    Constructing one *is* the check. `BoundPrincipal("alice")` is not a
    weaker path to the same value, it is a `TypeError`: the only argument
    accepted is an adapter, and the adapter is asked to re-verify its own
    binding before its principal is taken.

    That is what makes the record trustworthy. A record built from a string
    would attribute a call to whatever the string said; this one can only
    attribute it to the identity the campaign ledger already agrees with.
    """

    __slots__ = ()

    def __new__(cls, adapter):
        # Named before it is used. Passing a string here is the natural mistake,
        # and letting it fall through to a bare AttributeError on `.principal`
        # would report it as an internal error rather than as the mistake it is.
        if isinstance(adapter, str) or not hasattr(adapter, "principal"):
            raise TypeError(
                "BoundPrincipal is derived from an owner-bound adapter, not "
                "from a caller-supplied identity"
            )
        principal = adapter.principal  # Re-verifies the owner binding.
        if type(principal) is not str or not principal:
            raise TypeError("an owner-bound adapter principal is required")
        return super().__new__(cls, principal)


def operation_digest(operation_id: str) -> str:
    """Correlate retries without storing caller-controlled bytes.

    The same operation_id digests the same way, so a retry is still visible as a
    retry, while the record holds nothing the caller chose the contents of.
    """
    return hashlib.sha256(operation_id.encode()).hexdigest()[:16]


def call_record(
    operation: str,
    *,
    principal: BoundPrincipal,
    operation_id: str,
    outcome: str,
    duration_ms: int,
    reason: str | None = None,
):
    """A record that cannot contain the caller's arguments.

    `arguments` is not omitted-by-convention, it is absent: there is no
    parameter for it, so no call site can pass one and no future edit can add
    one without changing this signature and failing its test.
    """
    if type(principal) is not BoundPrincipal:
        raise TypeError("call_record requires a BoundPrincipal, not a string")
    if outcome not in OUTCOMES:
        raise ValueError("unrecognised outcome")
    return {
        "schema": SCHEMA,
        "operation": operation,
        "principal": str(principal),
        "operation_digest": operation_digest(operation_id),
        "outcome": outcome,
        "duration_ms": duration_ms,
        "reason": reason,
        "arguments": "NOT_RECORDED",
    }


class Capacity:
    """A concurrency bound with a deadline on waiting, not on working."""

    def __init__(
        self,
        *,
        limit=MAX_CONCURRENT_CALLS,
        queue_deadline=QUEUE_DEADLINE_SECONDS,
        budget=CALL_BUDGET_SECONDS,
    ):
        if limit < 1:
            raise ValueError("a concurrency bound below one admits no work")
        self.limit = limit
        self.queue_deadline = queue_deadline
        self.budget = budget
        self._semaphore = None

    def _gate(self):
        # Built on first use: an asyncio primitive must bind to the loop that
        # will await it, and the server is constructed before that loop runs.
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self.limit)
        return self._semaphore

    async def acquire(self):
        """Wait for capacity, or refuse having dispatched nothing."""
        try:
            await asyncio.wait_for(self._gate().acquire(), self.queue_deadline)
        except TimeoutError:
            return False
        return True

    def release(self):
        self._gate().release()

    def overran(self, duration_ms: int) -> bool:
        return duration_ms > self.budget * 1000


def catalogue(*, operations, extensions, resources, capacity: Capacity, sdk_version):
    """A versioned description of this surface, for a client that must pin.

    Separate from `carbon://research/v1/capabilities`, which projects the
    scientific catalogue - what a miner may attempt. This describes the
    *server*: what it exposes, what it bounds, and which version of both, so a
    client can tell a surface change from a science change instead of
    rediscovering one as the other.
    """
    return {
        "schema": CATALOGUE,
        "sdk_version": sdk_version,
        "operations": sorted(operations),
        "extensions": sorted(extensions),
        "resources": sorted(resources),
        "limits": {
            "max_concurrent_calls": capacity.limit,
            "queue_deadline_seconds": capacity.queue_deadline,
            "call_budget_seconds": capacity.budget,
            "call_budget_enforcement": "RECORDED_NOT_CANCELLED",
            "call_budget_note": (
                "A call that has started is never cancelled to meet this "
                "budget: cancelling an in-flight ledger reservation would "
                "create the reconciliation-required state the budget exists to "
                "avoid. The work itself is bounded by the seconds argument."
            ),
        },
        "refusals": {
            slug: {"next_action": action}
            for slug, action in sorted(NEXT_ACTION.items())
        },
        "records": {
            "schema": SCHEMA,
            "arguments_recorded": False,
            "note": (
                "Per-call records carry the operation, the owner-bound "
                "principal, an operation_id digest, an outcome and a duration. "
                "Never the arguments: they carry the miner's own work."
            ),
        },
        "official_eligible": False,
    }


class timed:
    """Duration in milliseconds, whatever the call does on the way out."""

    def __enter__(self):
        self._start = time.monotonic()
        self.duration_ms = 0
        return self

    def __exit__(self, *_exception):
        self.duration_ms = int((time.monotonic() - self._start) * 1000)
        return False
