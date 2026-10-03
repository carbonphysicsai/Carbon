"""Metered use of the miner's selected model provider; no hosted tools.

All request history and schemas count toward admission. Successful replay loads
the retained response. Unknown usage keeps its full reservation and never resends.

Provider failures are typed (`model_provider.ProviderOutcome`); LP-PROD-A set
how each is retried and settled (OWNER-LAUNCHPAD-PROD-01):

* a failure that incurred no charge (`model_provider.RETRY_SAFE`) - a rate
  limit or overload (429, 529), a server that answered 502 or 503 with no
  usage object, or a connection refused (or a name unresolved) before
  anything was sent - is recorded as its own finished operation, counted
  with no token charge, and the request is sent again under a *new* identity
  (`-rlN`) and a *new* reservation. The wait is exponential backoff with
  jitter (`retry_wait`), never shorter than the provider's Retry-After. Retries
  stop after `MAX_AUTOMATIC_RETRIES`, or once the next wait would take the
  call past `MAX_RETRY_WAIT_SECONDS` of waiting, and every attempt is still
  admitted by the ledger's ceilings. Replay walks the same identities, so a
  resume neither resends a finished attempt nor skips one;
* a quota or credential rejection - or a key file Carbon cannot read, found
  before anything is sent (`model_provider.CredentialUnavailable`) - is
  recorded the same way and is not retried at once: the miner has to fix the
  key or the balance. A later call - a resume - passes the recorded
  rejection and sends the request once more under the next identity, instead
  of replaying the rejection forever, as it does for retries that ran out. A
  context-limit or invalid-request rejection replays: the same request would
  get the same answer;
* a reply the provider ended early (its output limit, a pause, a refusal) is
  metered exactly. A caller that accepts one (`accept_incomplete`: the
  research loop) gets it back, described by `incomplete_reply`; any other
  caller gets the historical refusal;
* a transient server error after the request was sent, a timeout, a dropped
  connection, a reply without usable usage, a different model, a charge above
  the reservation or anything unrecognised may have been processed and
  charged: the full reservation stays, the operation stays unresolved, and
  nothing is resent. What is known is journalled beside the call
  (`uncertain.json`). An explicit settlement (`settle_uncertain_call`, reached
  through the campaign's reconcile action) books the full reservation as the
  call's charge - never less than the provider can have charged - and
  journals it; the next call of that turn then goes out under a fresh
  identity with its own reservation. Nothing settles a call automatically.
"""

from __future__ import annotations

import json
import random
import re
import time

from .data import write_once
from .model_provider import (
    _INCOMPLETE_REASONS,
    DEFAULT_SELECTION,
    RETRY_SAFE,
    ProviderFailure,
    ProviderOutcome,
    ProviderTransport,
    SelectionTransport,
    _code,
    classify,
    provider_report,
)
from .profile import canonical, digest

# The pinned model's published token prices, in integer nanodollars (source
# and date: `model_provider.GPT5_MINI_PRICING`). Each selection carries its own.
INPUT_NANO = DEFAULT_SELECTION.pricing.input_nano
CACHED_NANO = DEFAULT_SELECTION.pricing.cached_input_nano
OUTPUT_NANO = DEFAULT_SELECTION.pricing.output_nano
RESERVATION_NANO = DEFAULT_SELECTION.reservation_nano

#: Automatic resends, within one call, of a failure that incurred no charge
#: (`model_provider.RETRY_SAFE`), each under its own identity and reservation.
MAX_AUTOMATIC_RETRIES = 6
#: Exponential backoff between them: `BACKOFF_SECONDS * 2**k` seconds, at
#: most `MAX_BACKOFF_SECONDS`, with equal jitter (half fixed, half random) so
#: that callers refused together do not resend together.
BACKOFF_SECONDS = 2
MAX_BACKOFF_SECONDS = 60
#: The most one call waits on its retries, in seconds. A Retry-After longer
#: than what is left ends the call's retries at once, honoured rather than cut
#: short; a later call sends it again.
MAX_RETRY_WAIT_SECONDS = 300

#: Rejected before generation, and worth sending again on a later call: every
#: retry-safe failure, and the two the miner fixes outside Carbon (the key and
#: the balance).
RESUMABLE = RETRY_SAFE | {
    ProviderOutcome.AUTH_CREDENTIAL,
    ProviderOutcome.QUOTA_EXHAUSTED,
}
#: Possibly processed and charged: the reservation stays until a settlement.
UNCERTAIN = frozenset({ProviderOutcome.TRANSIENT_SERVER, ProviderOutcome.UNKNOWN})

#: What a miner does next after each typed failure (`ProviderCallFailed.report`).
NEXT_STEPS = {
    ProviderOutcome.RATE_LIMITED: (
        "The provider is rate-limiting this key. Carbon retried with backoff and "
        "charged nothing for the refused attempts. Resume later: the call is "
        "sent again under a new identity."
    ),
    ProviderOutcome.SERVER_UNAVAILABLE: (
        "The provider answered that it is unavailable (502, 503 or 529, no "
        "usage). Carbon retried with backoff and charged nothing for the refused "
        "attempts. Resume later: the call is sent again under a new identity."
    ),
    ProviderOutcome.UNREACHABLE: (
        "Carbon could not connect to the provider: the connection was refused or "
        "its name did not resolve, so nothing was sent. Check your network and "
        "the provider's endpoint, then resume."
    ),
    ProviderOutcome.AUTH_CREDENTIAL: (
        "The provider refused the key, or Carbon could not read this provider's "
        "key file. Put a valid key in that file, then resume: the call is sent "
        "again under a new identity."
    ),
    ProviderOutcome.QUOTA_EXHAUSTED: (
        "The provider reports no balance or quota left. Add balance or raise the "
        "quota at your provider, then resume: the call is sent again under a new "
        "identity."
    ),
    ProviderOutcome.CONTEXT_LIMIT: (
        "The request is longer than the model's context. Sending it again would "
        "fail the same way."
    ),
    ProviderOutcome.INVALID_REQUEST: (
        "The provider refused the request as invalid. Sending it again would "
        "fail the same way; check the model and endpoint you selected."
    ),
    ProviderOutcome.TRANSIENT_SERVER: (
        "The provider failed after the request was sent, so it may have been "
        "processed and charged. Reconcile the campaign: Carbon books the call at "
        "its full reservation, and the next resume sends it under a new identity."
    ),
    ProviderOutcome.UNKNOWN: (
        "The call's outcome is unknown (no reply in time, a dropped connection "
        "or a reply Carbon could not read), so it may have been processed and "
        "charged. Reconcile the campaign: Carbon books the call at its full "
        "reservation, and the next resume sends it under a new identity."
    ),
}

FAILURE_REPORT = "carbon.autoresearch.provider-failure.v1"


class ProviderCallFailed(ValueError):
    """A provider call ended without a usable response, with its typed outcome.

    The message never contains provider text; `outcome` and `record` are the
    typed facts a caller may show, and `report()` says what happens next.
    """

    def __init__(self, message, *, outcome, record=None):
        super().__init__(message)
        self.outcome, self.record = outcome, record

    @property
    def resumable(self):
        """A later call sends the request again under a new identity."""
        return self.outcome in RESUMABLE

    @property
    def requires_settlement(self):
        """The call may have been charged; its reservation stays until the
        campaign is reconciled (`settle_uncertain_call`)."""
        return self.outcome in UNCERTAIN

    def report(self):
        """The failure as a miner-facing record with its closed code and next
        step; never provider text."""
        return {
            "schema": FAILURE_REPORT,
            "code": "provider_" + self.outcome.value,
            "outcome": self.outcome.value,
            "resumable": self.resumable,
            "requires_settlement": self.requires_settlement,
            "next_step": NEXT_STEPS[self.outcome],
        }


class _Passed(Exception):
    """An attempt the walk passes to the next identity: a failure that
    incurred no charge (`fresh` when it happened now, so the walk may wait and
    retry), or a recorded rejection or settlement a later call sends again."""

    def __init__(self, failure, fresh):
        self.failure, self.fresh = failure, fresh


def attempt_identity(identity, attempt):
    """The ledger identity of a call's attempt: the first keeps `identity`, a
    later one adds `-rlN` (named for the rate-limit retries it first marked)."""
    return identity if attempt == 0 else f"{identity}-rl{attempt}"


def retry_wait(retries, retry_after=None, jitter=random.random):
    """Seconds to wait before automatic retry `retries` (0 for the first):
    exponential backoff with equal jitter, never under one second and never
    shorter than the provider's Retry-After."""
    ceiling = min(MAX_BACKOFF_SECONDS, BACKOFF_SECONDS * 2**retries)
    spread = jitter()
    if type(spread) not in (int, float) or not 0 <= spread <= 1:
        raise ValueError("jitter must be a number in [0, 1]")
    return max(1, ceiling / 2 + spread * ceiling / 2, retry_after or 0)


def usage_cost(usage, selection=DEFAULT_SELECTION):
    """Metered usage and its charge. A selection with no known price records
    tokens and `nanodollars: None` - unknown, never zero."""
    if type(usage) is not dict:
        raise ValueError("usage missing; retain reservation")
    incoming, outgoing = usage.get("input_tokens"), usage.get("output_tokens")
    if (
        type(incoming) is not int
        or type(outgoing) is not int
        or not 0 <= incoming <= selection.settings.max_input_tokens
        or not 0 <= outgoing <= selection.settings.max_output_tokens
    ):
        raise ValueError("token usage unavailable or exceeds reservation")
    input_details = usage.get("input_tokens_details")
    output_details = usage.get("output_tokens_details")
    cached = input_details.get("cached_tokens") if type(input_details) is dict else None
    reasoning = (
        output_details.get("reasoning_tokens") if type(output_details) is dict else None
    )
    if cached is not None and (type(cached) is not int or not 0 <= cached <= incoming):
        raise ValueError("invalid cached token accounting")
    if reasoning is not None and (
        type(reasoning) is not int or not 0 <= reasoning <= outgoing
    ):
        raise ValueError("invalid reasoning accounting")
    pricing = selection.pricing
    if pricing is None:
        return {
            "input_tokens": incoming,
            "cached_input_tokens": cached,
            "output_tokens": outgoing,
            "reasoning_tokens": reasoning,
            "nanodollars": None,
            "billing_basis": "price unknown for this model; tokens recorded, spend not metered by Carbon",
        }
    # Missing cache detail is conservatively priced as entirely uncached.
    charge = (
        (incoming - (cached or 0)) * pricing.input_nano
        + (cached or 0) * pricing.cached_input_nano
        + outgoing * pricing.output_nano
    )
    return {
        "input_tokens": incoming,
        "cached_input_tokens": cached,
        "output_tokens": outgoing,
        "reasoning_tokens": reasoning,
        "nanodollars": charge,
        "billing_basis": {
            "provider_published": "published token prices",
            "declared_list": "declared list prices (" + pricing.reference + ")",
            "miner_declared": "miner-declared token prices",
        }[pricing.source]
        + "; missing cache detail charged as uncached",
    }


#: Input tokens held back from the model's max_input_tokens for its reply.
CONTEXT_RESERVE_TOKENS = 4096


def input_token_bound(request_bytes, anchor):
    """An upper bound, in tokens, on a request's input.

    Every token covers at least one byte, so a request's canonical byte count
    bounds its tokens whatever the tokenizer. Once a turn has reported its
    input tokens, the next request only appends to that one (the instructions
    and tools are fixed and the history only grows), so its tokens are bounded
    by the reported count plus the bytes appended since. Without an anchor the
    bound is the byte count itself, as before.
    """
    if anchor is None:
        return request_bytes
    if (
        type(anchor) is not tuple
        or len(anchor) != 2
        or any(type(v) is not int or v < 0 for v in anchor)
        or anchor[1] > request_bytes
    ):
        raise ValueError("token anchor must precede an appended request")
    tokens, anchored_bytes = anchor
    return tokens + request_bytes - anchored_bytes


def request_model(
    ledger,
    *,
    owner,
    identity,
    request,
    credential_file,
    phase="research",
    transport=None,
    provider=DEFAULT_SELECTION,
    sleep=None,
    anchor=None,
    accept_incomplete=False,
    jitter=None,
):
    """One model call, with bounded automatic retries of failures that
    incurred no charge, each under a new identity and reservation.

    The walk replays every attempt already recorded under this call - a
    success or a replayable rejection ends it; a recorded failure that a
    later call sends again (`RESUMABLE`) or a settled call is passed to the
    next identity - and makes new attempts only past them. Only new attempts
    wait or count toward `MAX_AUTOMATIC_RETRIES` and `MAX_RETRY_WAIT_SECONDS`.

    `accept_incomplete` returns a reply the provider ended early, metered;
    without it such a reply raises, as it always has. `sleep` and `jitter`
    default to `time.sleep` and `random.random`, read at call time.
    """
    sleep = time.sleep if sleep is None else sleep
    jitter = random.random if jitter is None else jitter
    attempt = retries = 0
    waited = 0
    while True:
        try:
            return _request_once(
                ledger,
                owner=owner,
                identity=attempt_identity(identity, attempt),
                request=request,
                credential_file=credential_file,
                phase=phase,
                transport=transport,
                provider=provider,
                anchor=anchor,
                accept_incomplete=accept_incomplete,
            )
        except _Passed as passed:
            attempt += 1
            if not passed.fresh:
                # Recorded by an earlier call, which did its own waiting.
                continue
            failure = passed.failure
            wait = retry_wait(retries, failure.retry_after_seconds, jitter)
            if (
                retries == MAX_AUTOMATIC_RETRIES
                or waited + wait > MAX_RETRY_WAIT_SECONDS
            ):
                raise ProviderCallFailed(
                    "provider "
                    + failure.outcome.value
                    + " persisted after bounded retries; each attempt counted, "
                    "no token charge recorded; a later call sends it again",
                    outcome=failure.outcome,
                    record=failure.record(),
                ) from None
            sleep(wait)
            waited += wait
            retries += 1


def _rejected(failure, *, fresh):
    """A rejection before generation: retried now when it is retry-safe;
    passed by a later call when the miner can have fixed it; otherwise typed
    and final."""
    if failure.retry_safe or (not fresh and failure.outcome in RESUMABLE):
        raise _Passed(failure, fresh)
    raise ProviderCallFailed(
        "provider rejected the request ("
        + failure.outcome.value
        + "); attempt counted, no token charge recorded, no retry"
        + (
            "; a later call sends it again once the miner fixes it"
            if failure.outcome in RESUMABLE
            else ""
        ),
        outcome=failure.outcome,
        record=failure.record(),
    )


def _uncertain(directory, identity, reason, failure=None):
    """Journal what is known about a call left unresolved, beside it, for the
    settlement and the views. Best effort: the call's own failure is what the
    caller raises, and a settlement without this record reads it as unknown."""
    try:
        write_once(
            directory / "uncertain.json",
            canonical(
                {
                    "schema": UNCERTAIN_CALL,
                    "identity": identity,
                    "reason": reason,
                    "provider_failure": None if failure is None else failure.record(),
                }
            ),
        )
    except (OSError, ValueError):
        pass


def _retained(directory, retained):
    body = (directory / "response.json").read_bytes()
    if digest(body) != retained["response_digest"]:
        raise ValueError("retained provider response changed")
    return json.loads(body)


def _replay(admission, directory, provider, accept_incomplete):
    """The recorded outcome of an attempt that already ran."""
    retained = admission["result"] or {}
    if admission["state"] == "FAILED_INFRA":
        if retained.get("provider_settlement") is not None:
            # Settled at its full reservation: the turn goes on under the
            # next identity.
            raise _Passed(None, fresh=False)
        if retained.get("provider_rejection") is not None:
            _replayed_rejection(retained["provider_rejection"], provider)
        if accept_incomplete and retained.get("response_digest") is not None:
            # A reply the provider ended early, metered when it came back.
            return _retained(directory, retained)
    if admission["state"] != "SUCCEEDED":
        raise ValueError(
            "provider outcome uncertain; reconciliation required, no resend"
        )
    return _retained(directory, retained)


def _request_once(
    ledger,
    *,
    owner,
    identity,
    request,
    credential_file,
    phase,
    transport,
    provider,
    anchor=None,
    accept_incomplete=False,
):
    settings = provider.settings
    priced = provider.reservation_nano is not None
    if type(request) is not dict or set(request) != {
        "model",
        "instructions",
        "input",
        "tools",
        "parallel_tool_calls",
        "store",
        "max_output_tokens",
        "reasoning",
    }:
        raise ValueError("closed stateless request required")
    # `parallel_tool_calls` is the campaign's frozen rule's: False under the
    # historical and v1 rules, True under `PARALLEL_CALLS_V2`, which runs every
    # call of a turn (LP-PROD-A). Either way it is a Boolean.
    if (
        request["model"] != provider.model_id
        or request["store"] is not False
        or type(request["parallel_tool_calls"]) is not bool
        or request["max_output_tokens"] != settings.max_output_tokens
    ):
        raise ValueError("pinned model and bounded request required")
    if type(request["tools"]) is not list or any(
        type(t) is not dict or t.get("type") != "function" for t in request["tools"]
    ):
        raise ValueError("only local supervised functions allowed; no hosted tools")
    payload = canonical(request)
    if (
        input_token_bound(len(payload), anchor)
        > settings.max_input_tokens - CONTEXT_RESERVE_TOKENS
    ):
        raise ValueError("cumulative history/schema token reservation exhausted")
    # A new request must fit the provider timeout in the remaining elapsed
    # envelope; replay remains permitted after expiry.
    with ledger.db() as db:
        old = db.execute("SELECT id FROM operations WHERE id=?", (identity,)).fetchone()
        campaign = db.execute(
            "SELECT started,manifest FROM campaign WHERE id=1"
        ).fetchone()
    if old is None and campaign is not None and campaign[0] is not None:
        from .research_ledger import NO_BUDGET, _elapsed

        elapsed = _elapsed(json.loads(campaign[1]))
        if (
            elapsed is not NO_BUDGET
            and ledger.clock() + settings.timeout_seconds > campaign[0] + elapsed
        ):
            raise ValueError("provider timeout cannot fit remaining campaign time")
    request_digest = digest(payload)
    directory = ledger.root / ("model-" + digest(canonical([owner, identity]))[7:])
    # A known price reserves the request's maximum cost before dispatch. An
    # unknown one has no calculable maximum: attempts and bytes are reserved,
    # money is neither reserved nor metered (the selection says so).
    reservation = {
        "provider_attempts": 1,
        **({"provider_nanodollars": provider.reservation_nano} if priced else {}),
        "retained_bytes": 3 * 1024**2,
    }
    unbilled_actual = {
        "provider_attempts": 1,
        **({"provider_nanodollars": 0} if priced else {}),
    }
    admission = ledger.reserve(
        identity, owner=owner, phase=phase, request=request, resources=reservation
    )
    if not admission["dispatch"]:
        return _replay(admission, directory, provider, accept_incomplete)
    ledger.check_storage(3 * 1024**2)
    directory.mkdir(mode=0o700)
    write_once(directory / "request.json", payload)
    try:
        if transport is None:
            transport = (
                ProviderTransport(credential_file)
                if provider.is_historical_default
                else SelectionTransport(provider)
            )
        response = transport(request)
    except Exception as error:  # noqa: BLE001
        # Never print provider errors: they may contain request/credential text.
        failure = classify(error, provider.errors)
        if not failure.unbilled:
            _uncertain(directory, identity, "transport_outcome_unknown", failure)
            message = (
                "provider transient server error; outcome uncertain, full "
                "reservation retained, no automatic resend"
                if failure.outcome is ProviderOutcome.TRANSIENT_SERVER
                else "provider outcome uncertain; full reservation retained"
            )
            raise ProviderCallFailed(
                message, outcome=failure.outcome, record=failure.record()
            ) from None
        rejection = canonical(failure.record())
        write_once(directory / "rejection.json", rejection)
        ledger.finish(
            identity,
            owner=owner,
            state="FAILED_INFRA",
            actual={
                **unbilled_actual,
                "retained_bytes": len(payload) + len(rejection),
            },
            result={
                "request_digest": request_digest,
                "provider_rejection": failure.record(),
                "billing_basis": provider.errors.basis,
            },
        )
        _rejected(failure, fresh=True)
    body = canonical(response)
    write_once(directory / "response.json", body)
    try:
        usage = usage_cost(response.get("usage"), provider)
    except ValueError:
        _uncertain(directory, identity, "usage_unavailable")
        raise
    reported = response.get("model")
    # The pinned model must come back exactly. A model the miner named may come
    # back as a dated snapshot of that name, which is recorded.
    if reported != provider.model_id and (
        provider.is_historical_default
        or type(reported) is not str
        or not reported.startswith(provider.model_id + "-")
    ):
        _uncertain(directory, identity, "model_mismatch")
        raise ValueError(
            "different provider model; retained usage needs reconciliation"
        )
    # A reply the provider ended early stays FAILED_INFRA, as it always was
    # recorded, with its exact metered charge; `incomplete` says how it ended.
    status = "SUCCEEDED" if response.get("status") == "completed" else "FAILED_INFRA"
    report = provider_report(response, provider)
    charge = settled_charge(usage, report, provider)
    if priced and charge["nanodollars"] > provider.reservation_nano:
        _uncertain(directory, identity, "charge_exceeds_reservation")
        raise ValueError(
            "provider-reported charge exceeds the reservation; retained for "
            "reconciliation"
        )
    result = {
        "request_digest": request_digest,
        "response_digest": digest(body),
        "usage": usage,
        "provider_status": response.get("status"),
    }
    if status != "SUCCEEDED":
        result["incomplete"] = incomplete_reply(response, settings.max_output_tokens)
    if not provider.is_historical_default:
        # Campaign evidence for every call: the estimate and the provider's
        # own charge side by side, and who served it.
        result.update(
            provider_model=reported,
            provider_id=provider.provider_id,
            charge=charge,
            provider_report=report,
        )
        write_once(directory / "call.json", canonical({"identity": identity, **result}))
    ledger.finish(
        identity,
        owner=owner,
        state=status,
        actual={
            "provider_attempts": 1,
            **({"provider_nanodollars": charge["nanodollars"]} if priced else {}),
            "retained_bytes": len(payload) + len(body),
        },
        result=result,
    )
    if status != "SUCCEEDED" and not accept_incomplete:
        raise ValueError("incomplete provider response; retained accounting, no retry")
    return response


def _replayed_rejection(record, provider):
    outcome = ProviderOutcome(record["provider_outcome"])
    _rejected(
        ProviderFailure(
            outcome,
            record["http_status"],
            record["provider_code"],
            record["retry_after_seconds"],
            record["unbilled"],
            outcome in RETRY_SAFE,
        ),
        fresh=False,
    )


def incomplete_reply(response, max_output_tokens):
    """How a reply the provider ended early ended, or None for a completed one.

    `reason` is a closed code: `max_output_tokens` for a reply cut off at its
    output limit, otherwise the provider's own stop reason (`pause_turn`,
    `refusal`, `content_filter`, ...), or `unknown`. A reply retained before
    the translators recorded `incomplete_details` is read from its Messages
    stop reason where it has one. `max_output_tokens` is the request's limit;
    `output_tokens` the provider's count, where it gave one."""
    if type(response) is not dict or response.get("status") == "completed":
        return None
    details = response.get("incomplete_details")
    reason = details.get("reason") if type(details) is dict else None
    if reason is None:
        reason = response.get("provider_stop_reason")
    reason = _code(_INCOMPLETE_REASONS.get(reason, reason)) or "unknown"
    usage = response.get("usage")
    produced = usage.get("output_tokens") if type(usage) is dict else None
    return {
        "reason": reason,
        "output_tokens": produced if type(produced) is int and produced >= 0 else None,
        "max_output_tokens": max_output_tokens,
    }


# -- settling a call whose outcome is unknown (LP-PROD-A) ----------------------

#: What `_request_once` journals beside a call it leaves unresolved.
UNCERTAIN_CALL = "carbon.autoresearch.provider-uncertain.v1"
#: The journal of a call's explicit settlement.
PROVIDER_SETTLEMENT = "carbon.autoresearch.provider-settlement.v1"
#: Why a settlement was refused, each with the next step. The operation stays
#: as it was.
SETTLEMENT_REFUSALS = {
    "operation_unavailable": "this owner has no such operation",
    "not_a_provider_call": (
        "this operation is not a model call; reconcile it through its own path"
    ),
    "not_uncertain": "this call's outcome is known; there is nothing to settle",
    "request_changed": (
        "the retained request differs from the one reserved; keep the campaign "
        "as it is and report it"
    ),
    "charge_exceeds_reservation": (
        "the provider reported a charge above the call's reservation, which the "
        "ledger cannot book; reconcile it against the provider's own usage "
        "record before this campaign makes another call"
    ),
}
SETTLEMENT_ACCOUNTING = (
    "The call's outcome is unknown, so its full reservation is booked as its "
    "charge: never less than the provider can have charged. The provider's own "
    "charge, which may be lower or nothing, is not known to Carbon."
)
SETTLEMENT_RESEND = (
    "Nothing is resent by this settlement. The next model call of this turn goes "
    "out under a fresh identity with its own reservation."
)


class SettlementRefused(ValueError):
    """A call Carbon will not settle, with a closed `code` and the next step."""

    def __init__(self, code):
        super().__init__(code + ": " + SETTLEMENT_REFUSALS[code])
        self.code = code


def _call_directory(ledger, owner, identity):
    return ledger.root / ("model-" + digest(canonical([owner, identity]))[7:])


def _read_record(path, schema):
    if not path.is_file() or path.is_symlink() or path.stat().st_size > 65536:
        return None
    try:
        value = json.loads(path.read_bytes())
    except ValueError:
        return None
    return value if type(value) is dict and value.get("schema") == schema else None


def _reported_above(path, reservation):
    """Whether a retained reply reports a provider charge above the call's
    money reservation (Engy's `x_engy.charged_micro`)."""
    reserved = reservation.get("provider_nanodollars")
    if reserved is None or not path.is_file() or path.is_symlink():
        return False
    try:
        response = json.loads(path.read_bytes())
    except ValueError:
        return False
    report = response.get("x_engy") if type(response) is dict else None
    charged = report.get("charged_micro") if type(report) is dict else None
    return type(charged) is int and charged * 1000 > reserved


def _settlement(ledger, owner, identity):
    """The settlement of an unresolved model call, as it would be journalled,
    with what the ledger needs to book it; or the recorded settlement of one
    already settled. Refuses with `SettlementRefused`; changes nothing."""
    with ledger.db() as db:
        row = db.execute(
            "SELECT owner,state,request_digest,reservation,result FROM operations "
            "WHERE id=?",
            (identity,),
        ).fetchone()
    if row is None or row[0] != owner:
        raise SettlementRefused("operation_unavailable")
    reservation = json.loads(row[3])
    if reservation.get("provider_attempts") != 1:
        raise SettlementRefused("not_a_provider_call")
    result = json.loads(row[4]) if row[4] else None
    if (
        row[1] == "FAILED_INFRA"
        and type(result) is dict
        and result.get("provider_settlement") is not None
    ):
        return None, result["provider_settlement"]
    if row[1] != "RESERVED":
        raise SettlementRefused("not_uncertain")
    directory = _call_directory(ledger, owner, identity)
    request_file = directory / "request.json"
    response_file = directory / "response.json"
    if request_file.exists() and digest(request_file.read_bytes()) != row[2]:
        raise SettlementRefused("request_changed")
    known = _read_record(directory / "uncertain.json", UNCERTAIN_CALL) or {}
    reason = _code(known.get("reason")) or "outcome_unknown"
    if reason == "charge_exceeds_reservation" or _reported_above(
        response_file, reservation
    ):
        raise SettlementRefused("charge_exceeds_reservation")
    return row[2], {
        "schema": PROVIDER_SETTLEMENT,
        "identity": identity,
        "reason": reason,
        "provider_failure": known.get("provider_failure"),
        "request_retained": request_file.exists(),
        "response_retained": response_file.exists(),
        "booked": reservation,
        "accounting": SETTLEMENT_ACCOUNTING,
        "resend": SETTLEMENT_RESEND,
        "retry_dispatched": False,
    }


def settle_uncertain_call(ledger, *, owner, identity):
    """Settle one model call whose outcome is unknown; returns its settlement.

    The explicit, journalled end of a call left `RESERVED` (a timeout, a
    dropped connection, a 5xx after sending, a reply without usable usage, a
    different model): its full reservation is booked as its charge, so spend
    is never under-counted, and the operation finishes `FAILED_INFRA` with the
    settlement as its result. The settlement is journalled beside the call
    (`settlement.json`) before the ledger books it. Nothing is resent here;
    the next `request_model` of that turn passes the settled identity and
    sends the request under the next one, with its own reservation.

    Called only by the campaign's reconcile action, by its owner-lock holder
    under a fresh control generation; never automatically. Idempotent: a
    settled call returns its settlement. Refused (`SettlementRefused`, the
    operation unchanged): another owner's or a missing operation, one that is
    not a model call, a call whose outcome is known, a retained request that
    differs from the reserved one, and a provider-reported charge above the
    reservation, which the ledger cannot book.
    """
    fingerprint, settlement = _settlement(ledger, owner, identity)
    if fingerprint is None:
        return settlement
    directory = _call_directory(ledger, owner, identity)
    directory.mkdir(mode=0o700, exist_ok=True)
    write_once(directory / "settlement.json", canonical(settlement))
    ledger.finish(
        identity,
        owner=owner,
        state="FAILED_INFRA",
        actual=settlement["booked"],
        result={"request_digest": fingerprint, "provider_settlement": settlement},
    )
    return settlement


def uncertain_calls(ledger, *, owner):
    """This owner's model calls whose outcome is unknown, oldest first: what is
    known about each, what a settlement would book, and why one would be
    refused (`refusal`, a `SETTLEMENT_REFUSALS` code, or None)."""
    rows = []
    for op in ledger.status(owner=owner)["operations"]:
        if op["state"] != "RESERVED" or op["reservation"].get("provider_attempts") != 1:
            continue
        try:
            _, settlement = _settlement(ledger, owner, op["id"])
            refusal = None
        except SettlementRefused as refused:
            settlement, refusal = None, refused.code
        rows.append(
            {
                "identity": op["id"],
                "reason": None if settlement is None else settlement["reason"],
                "response_retained": (
                    None if settlement is None else settlement["response_retained"]
                ),
                "booked_on_settlement": op["reservation"],
                "refusal": refusal,
            }
        )
    return rows


def settle_uncertain_calls(ledger, *, owner):
    """Settle every model call of this owner whose outcome is unknown: the
    reconcile action's entry point. Returns the settlements made and each
    refusal with its code; a refused call stays unresolved."""
    settled, refused = [], []
    for row in uncertain_calls(ledger, owner=owner):
        try:
            settled.append(
                settle_uncertain_call(ledger, owner=owner, identity=row["identity"])
            )
        except SettlementRefused as refusal:
            refused.append({"identity": row["identity"], "code": refusal.code})
    return {"settled": settled, "refused": refused}


def settled_charge(usage, report, selection):
    """What a call cost, and on what basis.

    The provider's own reported charge settles it where the adapter reports
    one; a missing report keeps the whole reservation (unknown, not the
    headline rate). Otherwise the metered usage at the selection's price. The
    token-price estimate is always kept beside it, never substituted for it.
    """
    estimate = usage["nanodollars"]
    if selection.adapter.reported_charge is not None:
        micro = None if report is None else report["charged_micro"]
        if micro is None:
            return {
                "nanodollars": selection.reservation_nano,
                "basis": "provider charge not reported; full reservation retained",
                "provider_reported_micro": None,
                "estimated_nanodollars": estimate,
            }
        return {
            "nanodollars": micro * 1000,
            "basis": "provider-reported " + selection.adapter.reported_charge,
            "provider_reported_micro": micro,
            "estimated_nanodollars": estimate,
        }
    return {
        "nanodollars": estimate,
        "basis": usage["billing_basis"],
        "provider_reported_micro": None,
        "estimated_nanodollars": estimate,
    }


_RETRY = re.compile(r"-rl\d+$")


def provider_turns(operations):
    """Cost, tokens and provenance per model turn, from the ledger's own
    operations (every later attempt, `-rlN`, folds into its turn).

    Each turn states its charge basis. Where a call recorded no charge record
    (the historical pinned selection) the settled amount is the ledger's own
    actual, which is the metered usage. A turn with a settled call lists it
    under `settled`, and a turn whose reply the provider ended early carries
    `incomplete` (`incomplete_reply`); a turn with neither has neither key, as
    before (LP-PROD-A).
    """
    turns = {}
    for op in operations:
        result = op.get("result")
        if type(result) is not dict or "request_digest" not in result:
            continue
        turn = turns.setdefault(
            _RETRY.sub("", op["id"]),
            {
                "turn": _RETRY.sub("", op["id"]),
                "attempts": 0,
                "state": None,
                "charge_nanodollars": 0,
                "charge_basis": [],
                "provider_reported_micro": None,
                "estimated_nanodollars": None,
                "input_tokens": None,
                "cached_input_tokens": None,
                "output_tokens": None,
                "reasoning_tokens": None,
                "provenance": [],
                "rejections": [],
            },
        )
        turn["attempts"] += 1
        turn["state"] = op["state"]
        actual = op.get("actual") or {}
        charge = result.get("charge")
        if charge is not None:
            amount, basis = charge["nanodollars"], charge["basis"]
            if charge["provider_reported_micro"] is not None:
                turn["provider_reported_micro"] = (
                    turn["provider_reported_micro"] or 0
                ) + charge["provider_reported_micro"]
            if charge["estimated_nanodollars"] is not None:
                turn["estimated_nanodollars"] = (
                    turn["estimated_nanodollars"] or 0
                ) + charge["estimated_nanodollars"]
        elif "provider_rejection" in result:
            amount, basis = 0, "rejected before generation; no token charge"
            turn["rejections"].append(result["provider_rejection"])
        elif "provider_settlement" in result:
            amount = actual.get("provider_nanodollars")
            basis = "outcome unknown; full reservation booked by settlement"
            turn.setdefault("settled", []).append(op["id"])
        else:
            amount = actual.get("provider_nanodollars")
            basis = (result.get("usage") or {}).get("billing_basis", "ledger actual")
        if amount is None:
            turn["charge_nanodollars"] = None
        elif turn["charge_nanodollars"] is not None:
            turn["charge_nanodollars"] += amount
        if basis not in turn["charge_basis"]:
            turn["charge_basis"].append(basis)
        usage = result.get("usage") or {}
        for key, name in (
            ("input_tokens", "input_tokens"),
            ("cached_input_tokens", "cached_input_tokens"),
            ("output_tokens", "output_tokens"),
            ("reasoning_tokens", "reasoning_tokens"),
        ):
            if usage.get(name) is not None:
                turn[key] = (turn[key] or 0) + usage[name]
        report = result.get("provider_report")
        if report is not None:
            turn["provenance"].append(
                {k: report[k] for k in ("request_id", "miner", "worker")}
            )
        if result.get("incomplete") is not None:
            turn["incomplete"] = result["incomplete"]
    return list(turns.values())


def caching_status(turns):
    """Whether the provider's prompt cache is working, from recorded counts.

    The first turn cannot hit a cache. If every later completed turn - at
    least two of them - reports zero cached input tokens, something in the
    prefix is varying and the campaign says CACHING_NOT_WORKING.
    """
    done = [t for t in turns if t["state"] == "SUCCEEDED"]
    later = done[1:]
    total = sum(t["input_tokens"] or 0 for t in done)
    cached = sum(t["cached_input_tokens"] or 0 for t in done)
    if len(later) < 2:
        status = "INSUFFICIENT_TURNS"
    elif any(t["cached_input_tokens"] is None for t in later):
        status = "CACHE_NOT_REPORTED"
    elif all(t["cached_input_tokens"] == 0 for t in later):
        status = "CACHING_NOT_WORKING"
    else:
        status = "CACHING_OBSERVED"
    return {
        "status": status,
        "turns_considered": len(done),
        "cached_input_fraction": None if total == 0 else cached / total,
        "basis": "recorded cached-input token counts per completed turn",
    }
