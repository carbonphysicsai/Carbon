"""Metered use of the existing pinned Responses adapter; no hosted tools.

All request history and schemas count toward admission. Successful replay loads
the retained response. Unknown usage keeps its full reservation and never resends.
"""

from __future__ import annotations

import json

from .agent import MAX_INPUT_TOKENS, MAX_OUTPUT_TOKENS, MODEL, ResponsesTransport
from .data import write_once
from .profile import canonical, digest

# Official model/pricing pages checked 2026-09-17. USD per token in integer
# nanodollars: input .25/M, cached .025/M, output (including reasoning) 2/M.
INPUT_NANO = 250
CACHED_NANO = 25
OUTPUT_NANO = 2000
RESERVATION_NANO = MAX_INPUT_TOKENS * INPUT_NANO + MAX_OUTPUT_TOKENS * OUTPUT_NANO


def usage_cost(usage):
    if type(usage) is not dict:
        raise ValueError("usage missing; retain reservation")
    incoming, outgoing = usage.get("input_tokens"), usage.get("output_tokens")
    if (
        type(incoming) is not int
        or type(outgoing) is not int
        or not 0 <= incoming <= MAX_INPUT_TOKENS
        or not 0 <= outgoing <= MAX_OUTPUT_TOKENS
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
    # Missing cache detail is conservatively priced as entirely uncached.
    charge = (
        (incoming - (cached or 0)) * INPUT_NANO
        + (cached or 0) * CACHED_NANO
        + outgoing * OUTPUT_NANO
    )
    return {
        "input_tokens": incoming,
        "cached_input_tokens": cached,
        "output_tokens": outgoing,
        "reasoning_tokens": reasoning,
        "nanodollars": charge,
        "billing_basis": "published token prices; missing cache detail charged as uncached",
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
):
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
        request["model"] != MODEL
        or request["store"] is not False
        or request["parallel_tool_calls"] is not False
        or request["max_output_tokens"] != MAX_OUTPUT_TOKENS
    ):
        raise ValueError("pinned model and bounded request required")
    if type(request["tools"]) is not list or any(
        type(t) is not dict or t.get("type") != "function" for t in request["tools"]
    ):
        raise ValueError("only local supervised functions allowed; no hosted tools")
    payload = canonical(request)
    if len(payload) > MAX_INPUT_TOKENS - 4096:
        raise ValueError("cumulative history/schema token reservation exhausted")
    # The existing transport has a 120-second timeout. A new request must fit
    # the remaining elapsed envelope; replay remains permitted after expiry.
    with ledger.db() as db:
        old = db.execute("SELECT id FROM operations WHERE id=?", (identity,)).fetchone()
        campaign = db.execute("SELECT started FROM campaign WHERE id=1").fetchone()
    if old is None and campaign is not None and campaign[0] is not None:
        from .research_ledger import ELAPSED_SECONDS

        if ledger.clock() + 120 > campaign[0] + ELAPSED_SECONDS:
            raise ValueError("provider timeout cannot fit remaining campaign time")
    request_digest = digest(payload)
    directory = ledger.root / ("model-" + digest(canonical([owner, identity]))[7:])
    reservation = {
        "provider_attempts": 1,
        "provider_nanodollars": RESERVATION_NANO,
        "retained_bytes": 3 * 1024**2,
    }
    admission = ledger.reserve(
        identity, owner=owner, phase=phase, request=request, resources=reservation
    )
    if not admission["dispatch"]:
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
        response = (
            transport if transport is not None else ResponsesTransport(credential_file)
        )(request)
    except Exception:  # noqa: BLE001
        # Never print provider errors: they may contain request/credential text.
        raise ValueError(
            "provider outcome uncertain; full reservation retained"
        ) from None
    body = canonical(response)
    write_once(directory / "response.json", body)
    usage = usage_cost(response.get("usage"))
    if response.get("model") != MODEL:
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
            "provider_nanodollars": usage["nanodollars"],
            "retained_bytes": len(payload) + len(body),
        },
        result={
            "request_digest": request_digest,
            "response_digest": digest(body),
            "usage": usage,
            "provider_status": response.get("status"),
        },
    )
    if status != "SUCCEEDED":
        raise ValueError("incomplete provider response; retained accounting, no retry")
    return response
