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
    ModelSelection,
    ProviderHTTPError,
    SelectionTransport,
)

from ..controller import SimulatedCrash
from ..grant import SpendingGrant
from . import model_providers

#: The Engy adapters a Graphite session may use (plan §2: Engy first).
ENGY_ADAPTERS = tuple(model_providers.ENGY.adapters)


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
    run mid-call). `charged_micro` is the synthetic charge reported per reply
    in Engy's report; a reply as another provider (`model_provider`) sends
    it carries no charge report, as that provider documents none.
    """

    live = False
    credential_reference = "scripted-model-no-credential"

    def __init__(
        self, script, *, charged_micro=100, input_tokens=1000, model_provider="engy"
    ):
        self.script = list(script)
        self.charged_micro = charged_micro
        self.input_tokens = input_tokens
        self.model_provider = model_providers.resolve(model_provider)
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
        reply = {
            "model": request["model"],
            "status": "completed",
            "output": output,
            "usage": {
                "input_tokens": self.input_tokens,
                "output_tokens": 50,
                "input_tokens_details": {"cached_tokens": 0},
                "output_tokens_details": {"reasoning_tokens": 0},
            },
        }
        if self.model_provider.is_default:
            reply["x_engy"] = {
                "charged_micro": self.charged_micro,
                "request_id": f"scripted-{index:03d}",
                "miner": None,
                "worker": None,
            }
        return reply

    @property
    def remaining(self):
        return len(self.script) - self.position


def _arguments(value):
    import json

    return value if type(value) is str else json.dumps(value, sort_keys=True)


class LiveModel:
    """Real inference through `model_provider`, only under an owner grant.

    `model_provider` is the inference provider the run picked
    (`model_providers`; Engy by default). The grant must name it
    (`grant_binding.model_provider_refusal`), and every selection must be on
    its adapter at exactly its recorded rate; the same checks for every
    provider."""

    live = True

    def __init__(
        self,
        *,
        grant,
        credential_file,
        provider,
        now=None,
        opener=None,
        model_provider="engy",
    ):
        from .grant_binding import model_provider_refusal

        try:
            chosen = model_providers.resolve(model_provider)
        except ValueError as refused:
            raise ModelAccessRefused(refused.args[0]) from None
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
        refused = model_provider_refusal(grant, chosen.name)
        if refused is not None:
            raise ModelAccessRefused(refused)
        if type(credential_file) is not str or not credential_file:
            raise ModelAccessRefused("credential_file_reference_required")
        self.grant = grant
        self.model_provider = chosen
        self.credential_reference = credential_file
        # Replaces urllib's opener at the network boundary (the phase-4
        # pre-live gate's fake HTTP transport); None in a live run.
        self.opener = opener

    def transport_for(self, selection):
        if type(selection) is not ModelSelection:
            raise ModelAccessRefused("validated_selection_required")
        refused = self.model_provider.admission_refusal(selection)
        if refused is not None:
            raise ModelAccessRefused(refused)
        if selection.credential.reference != self.credential_reference:
            raise ModelAccessRefused("credential_reference_mismatch")
        return SelectionTransport(selection, opener=self.opener)
