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
    AdapterCode.NO_CAMPAIGN.value: (
        "This server has no campaign to account against, and no operation on it "
        "creates one. Reconnect to a server with a campaign attached, then "
        "retry with the same operation_id. Nothing was dispatched, so there is "
        "nothing to reconcile, and a budget is never what is missing here."
    ),
    AdapterCode.SIGNER_NOT_RUNNING.value: (
        "Your signer is not running. Start `carbon-miner-signer --wallet NAME "
        "--hotkey HOTKEY` in a terminal, leave it open, and retry the same "
        "operation_id. Carbon holds no key; your signer signs each request."
    ),
    AdapterCode.SIGNER_REFUSED.value: (
        "Your signer declined to sign; its terminal shows the reason. Correct "
        "that, then retry the same operation_id."
    ),
    AdapterCode.SIGNER_WRONG_HOTKEY.value: (
        "The signer running holds a different hotkey than this campaign's "
        "registered miner. Start the signer for the registered hotkey."
    ),
    AdapterCode.SIGNER_TIMEOUT.value: (
        "Your signer did not answer in time. Check its terminal, then retry "
        "the same operation_id."
    ),
    AdapterCode.SIGNER_INVALID_SIGNATURE.value: (
        "Your signer returned a signature that does not verify for the "
        "registered hotkey. Nothing signed by it was used. Restart the signer."
    ),
    AdapterCode.SIGNER_PROTOCOL.value: (
        "Something other than carbon-miner-signer answered on the signer "
        "socket. Stop it and start carbon-miner-signer."
    ),
    "CAPACITY_UNAVAILABLE": (
        "This server is at its concurrent-call bound. Nothing was dispatched. "
        "Retry the same operation_id shortly."
    ),
    # Pre-dispatch stops (LP-PROD-B): each names the limit, says nothing
    # started, and gives the step that lets a retry succeed.
    AdapterCode.CAMPAIGN_ELAPSED_BUDGET_REACHED.value: (
        "This campaign's time limit is reached: the elapsed budget set at "
        "launch, or a development grant's expiry - or the host clock moved "
        "backwards. Nothing was dispatched, so there is nothing to reconcile. "
        "If the clock moved, correct it; otherwise this campaign admits no "
        "more research, and a new campaign (with a larger elapsed budget, or "
        "none) continues it."
    ),
    AdapterCode.CAMPAIGN_ADMISSION_STOPPED.value: (
        "This campaign is not admitting work right now: it is paused, stopped, "
        "completed or awaiting reconciliation, or another holder took its "
        "control. Nothing was dispatched. Check its state (carbon_observe where "
        "offered, or the Control Center) and resume or reconcile it. If this "
        "session is attached to the campaign, call carbon_detach_campaign "
        "first, resume or reconcile, then attach again (carbon_attach_campaign) "
        "- an attachment whose control another holder took also needs that "
        "fresh attach, or a restart of a server started with --campaign. Then "
        "retry the same operation_id."
    ),
    AdapterCode.OPERATION_ID_REUSED.value: (
        "This operation_id already names a different request in this campaign, "
        "so this one was refused before anything started. Nothing was "
        "dispatched. To repeat the earlier request, send it unchanged with the "
        "same operation_id; for a new request use a new operation_id, or omit "
        "it and the server generates one."
    ),
    AdapterCode.TASK_NOT_FOUND.value: (
        "This campaign holds no task with that id; an id from another campaign "
        "or another miner is indistinguishable from an unknown one. Nothing "
        "changed. Use the taskId (task_id) your start returned."
    ),
    AdapterCode.OBSERVATION_LIMIT_REACHED.value: (
        "This task has been observed through tasks/get as many times as the "
        "task provider allows, so tasks/get on it is refused from now on. "
        "Nothing changed. Read its state with get_research_result (its own "
        "poll_sequence) or in the campaign's view."
    ),
}

#: How each code reads on a task observation (tasks/get, tasks/cancel): only
#: these mean the task itself is unavailable - an unknown id, or another
#: miner's, which the provider cannot tell apart either. One answer for both,
#: so there is no oracle. Nothing else is folded in: a failure that reached
#: the caller's own task (a result this server will not forward) or the
#: server's binding says nothing about whether the task exists.
TASK_UNAVAILABLE = frozenset(
    {
        AdapterCode.TASK_NOT_FOUND.value,
        AdapterCode.INVALID_ARGUMENT.value,
    }
)

#: The codes after which the same observation may succeed without the client
#: changing it: a transient stop, or a signer the miner can start or answer.
#: Every other failed observation is `retry=false` - fail closed, so a new
#: code never invites a polling loop by default.
OBSERVATION_RETRYABLE = frozenset(
    {
        AdapterCode.OPERATIONAL_STOP.value,
        AdapterCode.CAMPAIGN_ADMISSION_STOPPED.value,
        AdapterCode.SIGNER_NOT_RUNNING.value,
        AdapterCode.SIGNER_REFUSED.value,
        AdapterCode.SIGNER_TIMEOUT.value,
        "CAPACITY_UNAVAILABLE",
    }
)

#: The next action for a task observation that failed without saying anything
#: about the task: observing changes nothing, so retrying is safe.
OBSERVATION_RETRY = (
    "This observation did not complete and changed nothing; retry it. If it "
    "keeps failing, the campaign needs reconciliation through its operator."
)

#: Next actions that differ on a task observation. A result this server will
#: not forward may come after a cancellation was accepted, so it never says
#: nothing changed, and never invites starting the task again.
OBSERVATION_ACTION = {
    AdapterCode.OPERATIONAL_STOP.value: OBSERVATION_RETRY,
    AdapterCode.INVALID_RESULT.value: (
        "The task's current state could not be put on this wire. Do not take "
        "this as the task being gone or stopped - a cancellation may already "
        "have been accepted - and do not start it again. Check it in the "
        "campaign's view (the Control Center, or carbon_campaign_view where "
        "offered) and report it with its taskId."
    ),
}


def observation_action(code: str) -> str:
    """The fixed next action for a failed task observation. A task has no
    operation_id to retry, so the plain tools' wording is restated for it."""
    if code in OBSERVATION_ACTION:
        return OBSERVATION_ACTION[code]
    action = NEXT_ACTION.get(code)
    if action is None:
        return OBSERVATION_RETRY
    return action.replace(" with the same operation_id", "").replace(
        "the same operation_id", "this observation"
    )


def refusal(
    code: str, *, dispatch_may_have_occurred: bool, field=None, correction=None
) -> str:
    """The one refusal line every research door sends: a stable code, whether
    anything may have started, the field when one is to blame, and the fixed
    next action for the code. Never a provider message or a caller's value;
    `field` is only ever a name from a server-side schema.

    `correction`, when given, is `(correction_code, text)`: a registered
    correction Carbon wrote (AGENT-DOOR-USABILITY-01 A2), appended last so
    every earlier part reads as before. Only the door's own schema refusal
    passes one (`standard_server.validation_refusal`)."""
    parts = [
        code,
        "dispatch_may_have_occurred=" + str(dispatch_may_have_occurred).lower(),
    ]
    if field is not None:
        parts.append("field=" + field)
    parts.append("next_action=" + NEXT_ACTION[code])
    if correction is not None:
        correction_code, text = correction
        parts.append("correction_code=" + correction_code)
        parts.append("correction=" + text)
    return "; ".join(parts)


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
        #: Calls holding capacity now: what an attachment waits on before it
        #: lets a detach pull the campaign out from under them.
        self.in_flight = 0

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
        self.in_flight += 1
        return True

    def release(self):
        self.in_flight -= 1
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
