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
import re
import time

from .data import write_once
from .model_provider import (
    DEFAULT_SELECTION,
    ProviderFailure,
    ProviderOutcome,
    ProviderTransport,
    SelectionTransport,
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
        "billing_basis": {
            "provider_published": "published token prices",
            "declared_list": "declared list prices (" + pricing.reference + ")",
            "miner_declared": "miner-declared token prices",
        }[pricing.source]
        + "; missing cache detail charged as uncached",
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
    report = provider_report(response, provider)
    charge = settled_charge(usage, report, provider)
    if priced and charge["nanodollars"] > provider.reservation_nano:
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
    operations (retries under a rate limit fold into their turn).

    Each turn states its charge basis. Where a call recorded no charge record
    (the historical pinned selection) the settled amount is the ledger's own
    actual, which is the metered usage.
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
