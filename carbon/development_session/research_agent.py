"""Metered use of the miner's selected model provider; no hosted tools.

All request history and schemas count toward admission. Successful replay loads
the retained response. Unknown usage keeps its full reservation and never resends.

Provider failures are typed (`model_provider.ProviderOutcome`):

* a rate limit (HTTP 429, not a quota) is rejected before generation. The
  attempt is recorded as its own finished operation - counted, with no token
  charge - and the request is sent again under a *new* identity and a *new*
  reservation, after the provider's Retry-After or a bounded backoff, at most
  `MAX_RATE_LIMIT_RETRIES` times. Replay walks the same identities, so a resume
  neither resends a finished attempt nor skips one;
* quota, credential, context-limit and invalid-request rejections are recorded
  the same way (counted, no token charge) and never retried;
* a transient server error, a timeout, a dropped connection or anything
  unrecognised may have been processed: the full reservation stays, the
  operation stays unresolved for reconciliation, and nothing is resent.
"""

from __future__ import annotations

import json
import time

from .data import write_once
from .model_provider import (
    DEFAULT_SELECTION,
    ProviderFailure,
    ProviderOutcome,
    ProviderTransport,
    SelectionTransport,
    classify,
)
from .profile import canonical, digest

# The pinned model's published token prices, in integer nanodollars (source
# and date: `model_provider.GPT5_MINI_PRICING`). Each selection carries its own.
INPUT_NANO = DEFAULT_SELECTION.pricing.input_nano
CACHED_NANO = DEFAULT_SELECTION.pricing.cached_input_nano
OUTPUT_NANO = DEFAULT_SELECTION.pricing.output_nano
RESERVATION_NANO = DEFAULT_SELECTION.reservation_nano

#: Automatic resends after a rate limit, each under its own reservation.
MAX_RATE_LIMIT_RETRIES = 2
#: Wait bounds between them, in seconds.
BACKOFF_SECONDS = 2
MAX_BACKOFF_SECONDS = 30


class ProviderCallFailed(ValueError):
    """A provider call ended without a usable response, with its typed outcome.

    The message never contains provider text; `outcome` and `record` are the
    typed facts a caller may show.
    """

    def __init__(self, message, *, outcome, record=None):
        super().__init__(message)
        self.outcome, self.record = outcome, record


class _RateLimited(Exception):
    def __init__(self, retry_after, fresh):
        self.retry_after, self.fresh = retry_after, fresh


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
        "billing_basis": (
            "published token prices; missing cache detail charged as uncached"
            if pricing.source == "provider_published"
            else "miner-declared token prices; missing cache detail charged as uncached"
        ),
    }


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
    sleep=time.sleep,
):
    """One model call, with bounded rate-limit retries under new reservations."""
    for attempt in range(MAX_RATE_LIMIT_RETRIES + 1):
        attempt_identity = identity if attempt == 0 else f"{identity}-rl{attempt}"
        try:
            return _request_once(
                ledger,
                owner=owner,
                identity=attempt_identity,
                request=request,
                credential_file=credential_file,
                phase=phase,
                transport=transport,
                provider=provider,
            )
        except _RateLimited as limited:
            if attempt == MAX_RATE_LIMIT_RETRIES:
                raise ProviderCallFailed(
                    "provider rate limit persisted after bounded retries; "
                    "each attempt counted, no token charge recorded",
                    outcome=ProviderOutcome.RATE_LIMITED,
                ) from None
            if limited.fresh:
                # A replayed rate limit already waited when it was received.
                wait = limited.retry_after
                if wait is None:
                    wait = BACKOFF_SECONDS * 2**attempt
                sleep(min(max(wait, 1), MAX_BACKOFF_SECONDS))
    raise AssertionError("unreachable")


def _rejected(failure, *, fresh):
    if failure.outcome is ProviderOutcome.RATE_LIMITED:
        raise _RateLimited(failure.retry_after_seconds, fresh)
    raise ProviderCallFailed(
        "provider rejected the request ("
        + failure.outcome.value
        + "); attempt counted, no token charge recorded, no retry",
        outcome=failure.outcome,
        record=failure.record(),
    )


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
    if (
        request["model"] != provider.model_id
        or request["store"] is not False
        or request["parallel_tool_calls"] is not False
        or request["max_output_tokens"] != settings.max_output_tokens
    ):
        raise ValueError("pinned model and bounded request required")
    if type(request["tools"]) is not list or any(
        type(t) is not dict or t.get("type") != "function" for t in request["tools"]
    ):
        raise ValueError("only local supervised functions allowed; no hosted tools")
    payload = canonical(request)
    if len(payload) > settings.max_input_tokens - 4096:
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
        retained = admission["result"] or {}
        if (
            admission["state"] == "FAILED_INFRA"
            and retained.get("provider_rejection") is not None
        ):
            _replayed_rejection(retained["provider_rejection"], provider)
        if admission["state"] != "SUCCEEDED":
            raise ValueError(
                "provider outcome uncertain; reconciliation required, no resend"
            )
        body = (directory / "response.json").read_bytes()
        if digest(body) != admission["result"]["response_digest"]:
            raise ValueError("retained provider response changed")
        return json.loads(body)
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
    usage = usage_cost(response.get("usage"), provider)
    reported = response.get("model")
    # The pinned model must come back exactly. A model the miner named may come
    # back as a dated snapshot of that name, which is recorded.
    if reported != provider.model_id and (
        provider.is_historical_default
        or type(reported) is not str
        or not reported.startswith(provider.model_id + "-")
    ):
        raise ValueError(
            "different provider model; retained usage needs reconciliation"
        )
    status = "SUCCEEDED" if response.get("status") == "completed" else "FAILED_INFRA"
    ledger.finish(
        identity,
        owner=owner,
        state=status,
        actual={
            "provider_attempts": 1,
            **({"provider_nanodollars": usage["nanodollars"]} if priced else {}),
            "retained_bytes": len(payload) + len(body),
        },
        result={
            "request_digest": request_digest,
            "response_digest": digest(body),
            "usage": usage,
            "provider_status": response.get("status"),
            **({} if provider.is_historical_default else {"provider_model": reported}),
        },
    )
    if status != "SUCCEEDED":
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
            outcome is ProviderOutcome.RATE_LIMITED,
        ),
        fresh=False,
    )
