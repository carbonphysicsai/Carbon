"""Model access for a Graphite session: scripted for tests, live only under a grant.

The research loop calls a *transport*: one closed Responses-shaped request in,
one Responses-shaped reply out (`research_agent.request_model`). Metering,
reservation, settlement, replay without resending and typed failures all
happen there; model access only supplies the transport.

- `ScriptedModel` is a deterministic test double. It replays a script of
  replies (text, one tool call, several tool calls), injected provider
  failures, and process deaths, and records every request it receives. Its
  charges are synthetic numbers in the shape Engy reports them
  (`x_engy.charged_micro`). It never touches a network.
- `LiveModel` is the only route to real inference. It cannot be constructed
  without an exact `SpendingGrant` for this provider (whose loader refuses
  any `HUMAN_INPUT` value), a priced Engy selection and a credential *file*
  reference; it never reads the key itself (the transport reads it at the
  point of use). Phase 1 tests never construct a working one, and nothing in
  phase 1 calls it.
"""

from __future__ import annotations

import copy
import datetime

from carbon.development_session.model_provider import (
    ENGY_LADDER,
    ModelSelection,
    ProviderHTTPError,
    SelectionTransport,
)

from ..controller import SimulatedCrash
from ..grant import SpendingGrant

#: The Engy adapters a Graphite session may use (plan §2: Engy first).
ENGY_ADAPTERS = ("engy-anthropic", "engy-chat")


class ModelAccessRefused(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


class ScriptExhausted(RuntimeError):
    """The scripted model was asked for more replies than its script holds."""


def text(message):
    return {"text": message}


def tool(name, arguments):
    return {"tool": name, "arguments": arguments}


def tools(*calls):
    """Several tool calls in one reply (each a `tool(...)`)."""
    return {"tools": list(calls)}


def fail(status, code=None, retry_after=None):
    """An injected provider rejection (`model_provider.ProviderHTTPError`)."""
    return {"fail": (status, code, retry_after)}


def crash():
    """A process death while the request is in flight."""
    return {"crash": True}


class ScriptedModel:
    """Replays `script` in order; one step per model request.

    Each step is a `text`, `tool`, `tools`, `fail` or `crash` step, optionally
    with `"hook"`: a callable run before the reply (for example to cancel the
    run mid-call). `charged_micro` is the synthetic charge reported per reply.
    """

    live = False
    credential_reference = "scripted-model-no-credential"

    def __init__(self, script, *, charged_micro=100, input_tokens=1000):
        self.script = list(script)
        self.charged_micro = charged_micro
        self.input_tokens = input_tokens
        self.requests = []
        self.position = 0

    def transport_for(self, selection):
        if type(selection) is not ModelSelection:
            raise ModelAccessRefused("validated_selection_required")
        return self

    def __call__(self, request):
        if self.position >= len(self.script):
            raise ScriptExhausted("scripted model has no reply left")
        step = self.script[self.position]
        self.position += 1
        self.requests.append(copy.deepcopy(request))
        if step.get("hook") is not None:
            step["hook"]()
        if step.get("crash"):
            raise SimulatedCrash("model call in flight")
        if "fail" in step:
            status, code, retry_after = step["fail"]
            raise ProviderHTTPError(status, code=code, retry_after=retry_after)
        index = self.position
        output = []
        if "text" in step:
            output.append(
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": step["text"]}],
                }
            )
        calls = step.get("tools") or ([step] if "tool" in step else [])
        for number, call in enumerate(calls):
            output.append(
                {
                    "type": "function_call",
                    "call_id": f"script-{index:03d}-{number}",
                    "name": call["tool"],
                    "arguments": _arguments(call["arguments"]),
                }
            )
        return {
            "model": request["model"],
            "status": "completed",
            "output": output,
            "usage": {
                "input_tokens": self.input_tokens,
                "output_tokens": 50,
                "input_tokens_details": {"cached_tokens": 0},
                "output_tokens_details": {"reasoning_tokens": 0},
            },
            "x_engy": {
                "charged_micro": self.charged_micro,
                "request_id": f"scripted-{index:03d}",
                "miner": None,
                "worker": None,
            },
        }

    @property
    def remaining(self):
        return len(self.script) - self.position


def _arguments(value):
    import json

    return value if type(value) is str else json.dumps(value, sort_keys=True)


class LiveModel:
    """Real inference through `model_provider`, only under an owner grant."""

    live = True

    def __init__(self, *, grant, credential_file, provider, now=None):
        if type(grant) is not SpendingGrant:
            # A document, a template full of HUMAN_INPUT or None: no grant.
            raise ModelAccessRefused("spending_grant_required")
        if grant.provider != provider:
            raise ModelAccessRefused("grant_provider_mismatch")
        if grant.currency != "USD":
            raise ModelAccessRefused("grant_currency_must_be_usd")
        moment = now or datetime.datetime.now(datetime.UTC)
        if moment >= grant.expires_at:
            raise ModelAccessRefused("grant_expired")
        if type(credential_file) is not str or not credential_file:
            raise ModelAccessRefused("credential_file_reference_required")
        self.grant = grant
        self.credential_reference = credential_file

    def transport_for(self, selection):
        if type(selection) is not ModelSelection:
            raise ModelAccessRefused("validated_selection_required")
        if selection.provider_id not in ENGY_ADAPTERS:
            raise ModelAccessRefused("engy_adapter_required")
        if selection.model_id not in ENGY_LADDER or selection.pricing is None:
            raise ModelAccessRefused("priced_ladder_model_required")
        if selection.credential.reference != self.credential_reference:
            raise ModelAccessRefused("credential_reference_mismatch")
        return SelectionTransport(selection)
