"""Data-only Responses agent with a closed Carbon tool surface and spend gate.

The remote model has no terminal, filesystem, repository, wallet, evaluator or
arbitrary HTTP tool. API credentials are consumed only by this trusted transport.
"""

from __future__ import annotations

import asyncio
import json
import time
import urllib.request
from pathlib import Path

from carbon.mcp import McpTool

from .data import write_once
from .profile import canonical, digest, profile_digest

MODEL = "gpt-5-mini-2025-08-07"
MAX_CALLS = 12
MAX_INPUT_TOKENS = 65536
MAX_OUTPUT_TOKENS = 2048
INPUT_USD_PER_MILLION = 0.25
OUTPUT_USD_PER_MILLION = 2.0
MAX_CALL_USD = 0.02048
MAX_SESSION_USD = 0.25

PROMPT = """You are a restricted Carbon DEVELOPMENT miner. Discover the available
challenge through get_challenge_info, obtain its scaffold and permitted prior,
and propose a registered declarative TrainingStrategy. Use dry_validate and
estimate when useful. Submit a valid strategy, then retrieve its public result.
You may propose at most three distinct strategies, including invalid proposals.
Subsequent proposals may use only feedback returned by the tools. Choose only
supported backbones and parameter ranges. Do not request or infer evaluator
labels, case identities, seeds, secrets or files. Tools execute through an
authenticated supervisor. No arbitrary code execution is available. This is an
unqualified reduced Burgers development subset. It provides measurements, not
scientific qualification, an accepted winner or miner payment. Stop when the
budget is exhausted or the supervisor reports a failure. Finish with a concise
account of what you tried and whether feedback changed your strategy."""

PROMPT += """\nExact tool arguments: get_challenge_info and get_prior require
challenge_id and challenge_version. get_mock_scaffold requires those two fields
and optionally scaffold_id='starter'. dry_validate requires only strategy.
estimate and submit require challenge_id, challenge_version and strategy.
get_submission_result requires only submission_id from the submit response.
Use challenge_id='burgers-dynamics-v1' and challenge_version='1.0'."""

TOOLS = [
    {
        "type": "function",
        "name": "carbon_tool",
        "description": "Call one approved authenticated Carbon miner service tool.",
        "strict": True,
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "tool": {"type": "string", "enum": [item.value for item in McpTool]},
                "arguments_json": {
                    "type": "string",
                    "description": "JSON object containing the tool's arguments. Use challenge_id burgers-dynamics-v1 and challenge_version 1.0 where required.",
                },
            },
            "required": ["tool", "arguments_json"],
        },
    }
]


def proposal():
    return {
        "schema": "carbon.burgers-session.model-run-proposal.v1",
        "profile_digest": profile_digest(),
        "provider": "OpenAI Responses API",
        "model": MODEL,
        "endpoint": "https://api.openai.com/v1/responses",
        "max_calls": MAX_CALLS,
        "max_input_tokens_per_call": MAX_INPUT_TOKENS,
        "max_output_tokens_per_call": MAX_OUTPUT_TOKENS,
        "max_total_usd": MAX_SESSION_USD,
        "maximum_priced_usage_usd": MAX_CALLS * MAX_CALL_USD,
        "input_usd_per_million": INPUT_USD_PER_MILLION,
        "output_usd_per_million": OUTPUT_USD_PER_MILLION,
        "prompt": PROMPT,
        "tools": TOOLS,
        "max_proposals": 3,
        "max_wall_seconds": 10800,
        "automatic_retries": False,
        "ambiguous_call": "charge full reservation and stop; never resend",
        "pricing_source": "https://developers.openai.com/api/docs/models/gpt-5-mini",
        "approved": False,
    }


def check_authority(path: Path, *, now: float):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 16384:
        raise ValueError("bounded operator model-run approval required")
    authority = json.loads(path.read_bytes())
    expected = {
        "schema",
        "proposal_digest",
        "approved",
        "valid_from_unix",
        "valid_until_unix",
        "max_total_usd",
    }
    if (
        set(authority) != expected
        or authority["schema"] != "carbon.burgers-session.model-run-authority.v1"
    ):
        raise ValueError("exact operator model-run approval required")
    if authority["approved"] is not True or authority["proposal_digest"] != digest(
        canonical(proposal())
    ):
        raise ValueError("model-run approval does not bind this proposal")
    if (
        not authority["valid_from_unix"] <= now <= authority["valid_until_unix"]
        or authority["max_total_usd"] != MAX_SESSION_USD
    ):
        raise ValueError("model-run approval expired or cap differs")
    return authority


class ResponsesTransport:
    def __init__(self, credential_file: Path):
        self.credential_file = credential_file

    def __call__(self, request: dict[str, object]):
        path = self.credential_file
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 1024:
            raise ValueError("operator API credential file required")
        key = path.read_text().strip()
        if not key or "\n" in key or "\r" in key:
            raise ValueError("invalid API credential file")
        outgoing = urllib.request.Request(
            "https://api.openai.com/v1/responses",
            data=canonical(request),
            headers={
                "Authorization": "Bearer " + key,
                "Content-Type": "application/json",
            },
            method="POST",
        )

        # No retry, redirect or provider error body is propagated to the miner.
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None

        opener = urllib.request.build_opener(NoRedirect())
        with opener.open(outgoing, timeout=120) as response:
            payload = response.read(2 * 1024**2 + 1)
        if len(payload) > 2 * 1024**2:
            raise ValueError("provider response exceeds bound")
        return json.loads(payload)


async def run(connection, authority_file: Path, credential_file: Path):
    try:
        return await _run(connection, authority_file, credential_file)
    except BaseException:
        # Keep a bounded owner report even when inference or evaluation stops.
        # Provider/error text is deliberately not echoed into this projection.
        report = {
            "schema": "carbon.burgers-session.stopped.v1",
            "status": "STOPPED_RECONCILIATION_REQUIRED",
            "provider_responses_retained": len(
                list(connection.root.glob("provider-*-response.json"))
            ),
            "proposals_retained": len(connection.proposals),
            "completed_evaluations": len(connection.completed),
            "accounting": connection.budget.summary(),
            "automatic_retry": False,
            "chain_transactions": 0,
        }
        write_once(connection.root / "agent-stopped-report.json", canonical(report))
        raise


async def _run(connection, authority_file: Path, credential_file: Path):
    root = connection.root
    write_once(root / "model-run-proposal.json", canonical(proposal()))
    check_authority(authority_file, now=time.time())
    await connection.check_registration()
    # The existing A7 store is process-local. A second process cannot silently
    # create a replacement campaign after interruption; retained journals win.
    write_once(
        root / "model-session-dispatch.json",
        canonical(
            {
                "created_unix_ns": time.time_ns(),
                "proposal_digest": digest(canonical(proposal())),
            }
        ),
    )
    transport = ResponsesTransport(credential_file)
    conversation = [
        {
            "role": "user",
            "content": "Discover the challenge and run the bounded DEVELOPMENT strategy session.",
        }
    ]
    started = time.monotonic()
    outcomes = []
    for index in range(MAX_CALLS):
        if time.monotonic() - started > 10800:
            raise ValueError("agent session wall-time budget exhausted")
        check_authority(authority_file, now=time.time())
        request = {
            "model": MODEL,
            "instructions": PROMPT,
            "input": conversation,
            "tools": TOOLS,
            "parallel_tool_calls": False,
            "store": False,
            "max_output_tokens": MAX_OUTPUT_TOKENS,
            "reasoning": {"effort": "low"},
        }
        # Byte-level upper bound is deliberately conservative for byte-token
        # text: reserve the complete 65,536-token input allowance each call.
        # The 4,096-token margin covers message/tool framing; no built-in tools.
        if len(canonical(request)) > MAX_INPUT_TOKENS - 4096:
            raise ValueError("provider input budget exhausted")
        identity = f"provider-{index + 1}"
        connection.budget.reserve(
            identity, "provider_usd", MAX_CALL_USD, MAX_SESSION_USD, MAX_CALLS
        )
        write_once(root / f"{identity}-request.json", canonical(request))
        try:
            response = await asyncio.to_thread(transport, request)
        except Exception:  # noqa: BLE001 - provider errors may contain private data.
            # Leave the full reservation outstanding: timeout may be billed.
            raise ValueError(
                "provider outcome uncertain; retained reservation requires reconciliation"
            ) from None
        write_once(root / f"{identity}-response.json", canonical(response))
        usage = response.get("usage")
        if type(usage) is not dict or any(
            type(usage.get(name)) is not int
            for name in ("input_tokens", "output_tokens")
        ):
            raise ValueError("provider usage missing; keep full reservation and stop")
        input_tokens, output_tokens = usage["input_tokens"], usage["output_tokens"]
        if (
            not 0 <= input_tokens <= MAX_INPUT_TOKENS
            or not 0 <= output_tokens <= MAX_OUTPUT_TOKENS
        ):
            raise ValueError("provider usage exceeded reservation")
        cost = (
            input_tokens * INPUT_USD_PER_MILLION
            + output_tokens * OUTPUT_USD_PER_MILLION
        ) / 1_000_000
        connection.budget.finish(identity, cost, "COMPLETE")
        if response.get("model") != MODEL or response.get("status") != "completed":
            raise ValueError(
                "provider returned a different model or incomplete response; retain usage and stop"
            )
        outputs = response.get("output", [])
        if type(outputs) is not list:
            raise ValueError("invalid provider response")
        calls = [
            item
            for item in outputs
            if type(item) is dict and item.get("type") == "function_call"
        ]
        if len(calls) > 1:
            raise ValueError("parallel agent tool calls prohibited")
        conversation.extend(outputs)
        if not calls:
            outcomes.append(
                {
                    "provider_response_id": response.get("id"),
                    "usage": usage,
                    "estimated_usd": cost,
                }
            )
            break
        call = calls[0]
        if call.get("name") != "carbon_tool" or len(call.get("arguments", "")) > 16384:
            raise ValueError("unsupported agent tool request")
        arguments = json.loads(call["arguments"])
        if set(arguments) != {"tool", "arguments_json"}:
            raise ValueError("invalid agent tool envelope")
        fields = json.loads(arguments["arguments_json"])
        result = await connection.call(arguments["tool"], fields)
        safe = canonical(result).decode()
        conversation.append(
            {"type": "function_call_output", "call_id": call["call_id"], "output": safe}
        )
        outcomes.append(
            {
                "provider_response_id": response.get("id"),
                "usage": usage,
                "estimated_usd": cost,
                "tool": arguments["tool"],
                "result": result,
            }
        )
        write_once(root / f"{identity}-tool-result.json", canonical(result))
    report = {
        "schema": "carbon.burgers-session.agent-report.v1",
        "provider": "OpenAI",
        "model": MODEL,
        "real_inference": bool(outcomes),
        "calls": outcomes,
        "proposals": len(connection.proposals),
        "completed_evaluations": len(connection.completed),
        "accounting": connection.budget.summary(),
        "wall_seconds": time.monotonic() - started,
        "chain_transactions": 0,
    }
    write_once(root / "agent-report.json", canonical(report))
    return report
