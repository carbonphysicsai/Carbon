"""The model provider a miner chooses for Carbon's research agent.

The provider is the **miner's** choice (owner decision, 2026-09-26). Carbon
neither imposes nor restricts one: the miner picks a provider adapter and a
model and supplies their own credential, so the data agreement is between the
miner and that provider. What Carbon owns is the agent application - the
research loop's prompt, tools, reservation and journal - and the honesty of
what it reports about cost.

Five things that used to be one hardwired transport are separate here:

* the **agent application**: `research_loop`, not configured here;
* the **provider adapter** (`ProviderAdapter`): a stable id, a wire protocol,
  an endpoint, the models it allows and the prices it knows, how it
  authenticates, how its errors are read and how it reports what it charged;
* the **model id**: an allowed id; a listed model carries a sourced price;
* the **model settings**: token ceilings, reasoning effort, timeout;
* the **credential reference**: the path of the miner's own key file. Never
  the key, never an environment variable. A transport reads the file at the
  point of use, sends the key in one header, and drops it.

Three wire protocols are implemented: OpenAI Responses (the loop's own
shape), OpenAI Chat Completions and Anthropic Messages, each translated to and
from the loop's one history format. Engy (Bittensor subnet 53) serves Messages
at https://api.engy.ai and Chat Completions at https://api.engy.ai/v1; the
Anthropic adapter is the same Messages transport at https://api.anthropic.com.

A campaign's choice is a `ModelSelection`, which only `select()` builds, so an
unvalidated combination cannot reach a transport. The one combination every
existing campaign was pinned to - OpenAI Responses with
`gpt-5-mini-2025-08-07` - is `DEFAULT_SELECTION`, and its manifest record is
byte-identical to the block those manifests carry.

**Cost.** Where a price is known - published by the provider, a declared list
with its source and date, or declared by the miner - each request reserves its
maximum possible cost before dispatch (the whole admitted context at the
uncached price plus the whole output ceiling). That is an *estimate* and stays
one. Where the provider reports what it actually charged (Engy's
`x_engy.charged_micro`), that number settles the call; a missing report keeps
the full reservation rather than falling back to the headline rate. Where the
price is unknown, no maximum is calculable: Carbon says so, reserves and meters
no money, records token usage only, and refuses a money ceiling it could not
enforce. Prices are never invented.

Replies other than a completed response are classified into
`ProviderOutcome`; see `research_agent` for which are retried and how.
"""

from __future__ import annotations

import enum
import json
import re
import socket
import threading
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

SELECTION_SCHEMA = "carbon.model-selection.v1"
PROVIDER_SUMMARY = "carbon.model-provider-summary.v1"

RESPONSES = "openai.responses.v1"
CHAT_COMPLETIONS = "openai.chat-completions.v1"
MESSAGES = "anthropic.messages.v1"
ANTHROPIC_VERSION = "2023-06-01"

UNKNOWN_SPEND = (
    "unknown: no price is known or declared for this model, so no maximum cost "
    "per request is calculable. Carbon reserves and meters no money for it and "
    "records token usage only; limit spend at your provider."
)

#: The output caps a selection may carry (`select`), inclusive.
OUTPUT_TOKEN_BOUNDS = (256, 131072)


@dataclass(frozen=True)
class Pricing:
    """USD per token in integer nanodollars, and where the numbers came from.

    `source` is `provider_published`, `declared_list` (a provider's price list
    recorded by the owner with its date) or `miner_declared`; there is no
    guessed kind.
    """

    input_nano: int
    cached_input_nano: int
    output_nano: int
    source: str
    reference: str
    observed: str
    note: str

    def per_million(self):
        return {
            "input_per_million": self.input_nano / 1000,
            "cached_per_million": self.cached_input_nano / 1000,
            "output_per_million": self.output_nano / 1000,
        }

    def record(self):
        return {
            "unit": "nanodollars per token",
            "input": self.input_nano,
            "cached_input": self.cached_input_nano,
            "output_including_reasoning": self.output_nano,
            "source": self.source,
            "reference": self.reference,
            "observed": self.observed,
            "note": self.note,
        }


@dataclass(frozen=True)
class Settings:
    max_input_tokens: int
    max_output_tokens: int
    #: None sends no reasoning parameter (for models that take none).
    reasoning_effort: str | None
    timeout_seconds: int
    max_response_bytes: int = 2 * 1024**2

    def record(self):
        return {
            "max_input_tokens": self.max_input_tokens,
            "max_output_tokens": self.max_output_tokens,
            "reasoning_effort": self.reasoning_effort,
            "timeout_seconds": self.timeout_seconds,
        }


@dataclass(frozen=True)
class OutputMaximum:
    """The most output tokens one reply may carry, as the provider documents
    it, and where that came from. Recorded like a price: sourced and dated,
    never guessed."""

    tokens: int
    reference: str
    observed: str
    note: str

    def record(self):
        return {
            "max_output_tokens": self.tokens,
            "reference": self.reference,
            "observed": self.observed,
            "note": self.note,
        }


@dataclass(frozen=True)
class CredentialReference:
    """Where the miner's own key file is. Never the key itself."""

    kind: str
    reference: str

    def record(self):
        # The path is local layout and is supplied again at run time.
        return {"kind": self.kind, "reference": None}


@dataclass(frozen=True)
class ErrorSemantics:
    """What a provider's HTTP rejections mean for money and retry.

    `unbilled_rejections` are statuses returned before any generation with no
    usage object; the attempt is counted and no token charge recorded. A
    status in `rate_limit_statuses`, or any response whose error code is in
    `overload_codes`, is a rate limit: rejected before generation and safe to
    retry under a new reservation. A status in `unavailable_statuses` whose
    body carries no usage object (and no provider charge report, Engy's
    `x_engy`) is a server that answered it could not take the request (502,
    503, 529): rejected before generation and retried the same way
    (OWNER-LAUNCHPAD-PROD-01, LP-PROD-A). Every other failure - any other
    5xx, a 5xx that reports usage or a charge, a timeout, a dropped
    connection, an unreadable body - keeps its full reservation, because the
    request may have been processed.
    """

    unbilled_rejections: tuple[int, ...]
    rate_limit_statuses: tuple[int, ...]
    overload_codes: tuple[str, ...]
    quota_codes: tuple[str, ...]
    context_codes: tuple[str, ...]
    basis: str
    unavailable_statuses: tuple[int, ...] = (502, 503, 529)


OPENAI_ERRORS = ErrorSemantics(
    unbilled_rejections=(400, 401, 402, 403, 404, 409, 413, 422, 429),
    rate_limit_statuses=(429,),
    overload_codes=(),
    quota_codes=("insufficient_quota",),
    context_codes=("context_length_exceeded",),
    basis=(
        "Carbon's recorded reading of OpenAI-style API error semantics "
        "(2026-09-26; 502, 503 and 529 added 2026-10-03 under "
        "OWNER-LAUNCHPAD-PROD-01): a 4xx rejection, and a 502, 503 or 529 whose "
        "body carries no usage object, is returned before generation, so the "
        "attempt is counted and no token charge is recorded. Not "
        "invoice-verified; any other 5xx, a 5xx that reports usage, or any "
        "unreadable outcome keeps the full reservation."
    ),
)
MESSAGES_ERRORS = ErrorSemantics(
    unbilled_rejections=(400, 401, 402, 403, 404, 413, 429, 529),
    rate_limit_statuses=(429, 529),
    overload_codes=("overloaded_error",),
    quota_codes=("billing_error",),
    context_codes=(),
    basis=(
        "Carbon's recorded reading of Anthropic Messages error semantics "
        "(2026-09-26; 502 and 503 added 2026-10-03 under "
        "OWNER-LAUNCHPAD-PROD-01): 429 rate_limit_error and 529 or "
        "overloaded_error are rejected before generation and retried as rate "
        "limits; a 502 or 503 whose body carries no usage object is rejected "
        "before generation and retried; other 4xx are counted with no token "
        "charge; any other 5xx keeps the full reservation. Messages has no "
        "context-limit code, so an over-long prompt is an invalid request."
    ),
)
ENGY_BASIS = (
    " Engy's rate limits are undocumented (owner order 2026-09-26); these "
    "semantics are the protocol's, not Engy-verified. Engy reports the actual "
    "charge per call in x_engy.charged_micro, which settles the call."
)
ENGY_MESSAGES_ERRORS = ErrorSemantics(
    **{
        **MESSAGES_ERRORS.__dict__,
        "basis": MESSAGES_ERRORS.basis + ENGY_BASIS,
    }
)
ENGY_CHAT_ERRORS = ErrorSemantics(
    **{
        **OPENAI_ERRORS.__dict__,
        "overload_codes": ("overloaded_error",),
        "basis": OPENAI_ERRORS.basis + ENGY_BASIS,
    }
)


@dataclass(frozen=True)
class ProviderAdapter:
    adapter_id: str
    display_name: str
    protocol: str
    #: The full request URL, or None where the miner supplies it.
    endpoint: str | None
    #: The base URL a person configures a client with, for display.
    base_url: str | None = None
    #: Models with a known price, by id.
    priced_models: dict = field(default_factory=dict)
    #: None: any model id; otherwise only these.
    allowed_models: tuple | None = None
    default_model: str | None = None
    #: "bearer" (Authorization) or "x-api-key".
    auth: str = "bearer"
    #: Where the provider reports what it charged, if it does.
    reported_charge: str | None = None
    #: Anthropic prompt-cache breakpoints on the stable prefix.
    cache_breakpoints: bool = False
    #: The public model list, readable without a key.
    models_url: str | None = None
    #: Prices are read from `models_url` when a selection is made
    #: (`published_pricing`) rather than listed in Carbon.
    live_pricing: bool = False
    errors: ErrorSemantics = OPENAI_ERRORS
    #: Each model's own documented maximum output, by id (`OutputMaximum`).
    output_maxima: dict = field(default_factory=dict)
    #: The provider's documented maximum for every model it serves, where it
    #: states one and no model's own is recorded.
    output_maximum: OutputMaximum | None = None

    def summary_models(self):
        ids = (
            self.allowed_models
            if self.allowed_models is not None
            else tuple(sorted(self.priced_models))
        )
        return [
            {
                "model_id": model,
                "default": model == self.default_model,
                "pricing": (
                    self.priced_models[model].record()
                    if model in self.priced_models
                    else None
                ),
            }
            for model in ids
        ]


GPT5_MINI = "gpt-5-mini-2025-08-07"
GPT5_MINI_PRICING = Pricing(
    input_nano=250,
    cached_input_nano=25,
    output_nano=2000,
    source="provider_published",
    reference="OpenAI official model and API pricing pages",
    observed="2026-09-17",
    note=(
        "Recorded when the model was pinned: input 0.25, cached input 0.025, "
        "output (including reasoning) 2.00 USD per million tokens. Not "
        "re-verified since; reconcile against your provider's usage export."
    ),
)
GPT5_MINI_OUTPUT = OutputMaximum(
    tokens=128000,
    reference=(
        "OpenAI model page, https://developers.openai.com/api/docs/models/gpt-5-mini"
    ),
    observed="2026-10-03",
    note=(
        "400,000 context window, 128,000 max output tokens; gpt-5-mini-2025-08-07 "
        "is the page's default snapshot. Reasoning counts against the output."
    ),
)


def _engy(input_nano, output_nano, cached_nano, context):
    return Pricing(
        input_nano=input_nano,
        cached_input_nano=cached_nano,
        output_nano=output_nano,
        source="declared_list",
        reference="Engy published list, observed 2026-09-26",
        observed="2026-09-26",
        note=(
            f"Headline rate; context {context}. An estimate for the reservation "
            "only: each call is settled from x_engy.charged_micro."
        ),
    )


#: The owner's model ladder (order of 2026-09-26, section 3), cheapest first.
#: Escalate one rung only on an observed research failure. deepseek-v4.1-flash
#: is deliberately absent: its 327,680 context would confound comparison.
ENGY_MODELS = {
    "deepseek-v4-flash-0731": _engy(45, 90, 9, "1.05M"),
    "qwen3.8-27b": _engy(45, 320, 15, "1.00M"),
    "glm-5.3-flash": _engy(135, 450, 27, "262K"),
    "glm-5.2": _engy(680, 1500, 180, "262K"),
    "kimi-k3": _engy(1950, 9750, 195, "1.05M"),
}
ENGY_LADDER = tuple(ENGY_MODELS)
ENGY_DEFAULT_MODEL = "deepseek-v4-flash-0731"
ENGY_MODELS_URL = "https://api.engy.ai/v1/models"
ENGY_OUTPUT = OutputMaximum(
    tokens=OUTPUT_TOKEN_BOUNDS[1],
    reference="Engy published list, " + ENGY_MODELS_URL,
    observed="2026-10-03",
    note=(
        "Engy states no output maximum apart from each model's context: every "
        "ladder model's max_model_len equals its context_length, 262,144 tokens "
        "or more. After the default 65,536-token input that leaves more than "
        "131,072, Carbon's highest output cap, so a reply may use all of it. A "
        "larger input setting leaves less room; set max_output_tokens to fit."
    ),
)

#: Chutes (Bittensor subnet 64): OpenAI Chat Completions with a bearer key.
#: Its public model list carries each model's price in USD per million tokens
#: (`pricing.prompt`, `pricing.completion`, `pricing.input_cache_read`).
#: Provider facts, read 2026-10-02.
CHUTES_MODELS_URL = "https://llm.chutes.ai/v1/models"
CHUTES_ERRORS = ErrorSemantics(
    **{
        **OPENAI_ERRORS.__dict__,
        "basis": OPENAI_ERRORS.basis
        + " Chutes' rate limits and charge reporting are not verified; these "
        "semantics are the protocol's. No charge report is read, so a call is "
        "metered at the published price.",
    }
)

ADAPTERS = {
    adapter.adapter_id: adapter
    for adapter in (
        ProviderAdapter(
            adapter_id="openai-responses",
            display_name="OpenAI Responses API",
            protocol=RESPONSES,
            endpoint="https://api.openai.com/v1/responses",
            base_url="https://api.openai.com/v1",
            priced_models={GPT5_MINI: GPT5_MINI_PRICING},
            output_maxima={GPT5_MINI: GPT5_MINI_OUTPUT},
        ),
        ProviderAdapter(
            adapter_id="engy-anthropic",
            display_name="Engy (subnet 53), Anthropic Messages",
            protocol=MESSAGES,
            endpoint="https://api.engy.ai/v1/messages",
            base_url="https://api.engy.ai",
            priced_models=ENGY_MODELS,
            allowed_models=ENGY_LADDER,
            default_model=ENGY_DEFAULT_MODEL,
            auth="x-api-key",
            reported_charge="x_engy.charged_micro",
            models_url=ENGY_MODELS_URL,
            errors=ENGY_MESSAGES_ERRORS,
            output_maximum=ENGY_OUTPUT,
        ),
        ProviderAdapter(
            adapter_id="engy-chat",
            display_name="Engy (subnet 53), OpenAI Chat Completions",
            protocol=CHAT_COMPLETIONS,
            endpoint="https://api.engy.ai/v1/chat/completions",
            base_url="https://api.engy.ai/v1",
            priced_models=ENGY_MODELS,
            allowed_models=ENGY_LADDER,
            default_model=ENGY_DEFAULT_MODEL,
            reported_charge="x_engy.charged_micro",
            models_url=ENGY_MODELS_URL,
            errors=ENGY_CHAT_ERRORS,
            output_maximum=ENGY_OUTPUT,
        ),
        ProviderAdapter(
            adapter_id="chutes",
            display_name="Chutes (subnet 64), OpenAI Chat Completions",
            protocol=CHAT_COMPLETIONS,
            endpoint="https://llm.chutes.ai/v1/chat/completions",
            base_url="https://llm.chutes.ai/v1",
            models_url=CHUTES_MODELS_URL,
            live_pricing=True,
            errors=CHUTES_ERRORS,
        ),
        ProviderAdapter(
            adapter_id="anthropic",
            display_name="Anthropic Messages API",
            protocol=MESSAGES,
            endpoint="https://api.anthropic.com/v1/messages",
            base_url="https://api.anthropic.com",
            auth="x-api-key",
            cache_breakpoints=True,
            errors=MESSAGES_ERRORS,
        ),
        ProviderAdapter(
            adapter_id="openai-compatible-responses",
            display_name="Any service implementing the OpenAI Responses API",
            protocol=RESPONSES,
            endpoint=None,
        ),
        ProviderAdapter(
            adapter_id="openai-compatible-chat",
            display_name="Any service implementing OpenAI Chat Completions",
            protocol=CHAT_COMPLETIONS,
            endpoint=None,
        ),
    )
}

#: The historical settings every pinned campaign ran with. They stay exactly
#: as they are: the pinned default resolves to them, and every plan frozen
#: before OUTPUT_DEFAULT_V2 recorded its output cap from them.
DEFAULT_SETTINGS = Settings(
    max_input_tokens=65536,
    max_output_tokens=2048,
    reasoning_effort="low",
    timeout_seconds=120,
)

#: How a new plan's output cap is chosen when the miner sets none
#: (OWNER-LAUNCHPAD-PROD-02, decision 1: no Carbon-imposed output cap). Its
#: default is the selected model's own maximum output (`output_maximum`), and
#: only a cap the miner sets binds below it. Every call is still reserved and
#: metered at that cap against the miner's own ceilings. A selection built
#: without it (None, the historical rule) keeps `DEFAULT_SETTINGS`' 2,048, so
#: what an earlier plan recorded, and every caller that is not a new plan
#: (Graphite, a development grant), is unchanged. A plan records its cap, so
#: it replays the same under either rule.
OUTPUT_DEFAULT_V2 = "carbon.model-selection.output-default.v2"
OUTPUT_DEFAULTS = (None, OUTPUT_DEFAULT_V2)

_MODEL_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/@-]{0,127}")
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
EFFORTS = (None, "minimal", "low", "medium", "high")


class ModelSelectionRefused(ValueError):
    """A provider/model/settings/credential combination Carbon cannot use."""


@dataclass(frozen=True)
class ModelSelection:
    """One campaign's validated choice. Build with `select()`, never directly:
    the constructor refuses anything that did not come through it."""

    adapter: ProviderAdapter
    model_id: str
    endpoint: str
    settings: Settings
    #: None: unknown price, no calculable maximum (see UNKNOWN_SPEND).
    pricing: Pricing | None
    credential: CredentialReference
    _token: object = field(default=None, repr=False, compare=False)

    def __post_init__(self):
        # Each ticket admits one construction, so neither a direct call nor
        # `dataclasses.replace` on a validated selection yields another.
        try:
            _TICKETS.remove(self._token)
        except (KeyError, TypeError):
            raise ModelSelectionRefused(
                "build a ModelSelection with select()"
            ) from None

    @property
    def provider_id(self):
        return self.adapter.adapter_id

    @property
    def errors(self):
        return self.adapter.errors

    @property
    def reservation_nano(self):
        """The most one request can cost, or None when no maximum exists."""
        if self.pricing is None:
            return None
        return (
            self.settings.max_input_tokens * self.pricing.input_nano
            + self.settings.max_output_tokens * self.pricing.output_nano
        )

    @property
    def is_historical_default(self):
        return self.record() == DEFAULT_SELECTION.record()

    def record(self):
        """The selection as a campaign manifest records it; no key, no path."""
        return {
            "schema": SELECTION_SCHEMA,
            "provider_id": self.provider_id,
            "protocol": self.adapter.protocol,
            "endpoint": self.endpoint,
            "model": self.model_id,
            "settings": self.settings.record(),
            "pricing": None if self.pricing is None else self.pricing.record(),
            "spend_bound": (
                UNKNOWN_SPEND
                if self.pricing is None
                else "estimate reserved per request before dispatch from "
                + self.pricing.source
                + " pricing; settled to "
                + (
                    "the provider-reported charge ("
                    + self.adapter.reported_charge
                    + ")"
                    if self.adapter.reported_charge
                    else "metered usage at that price"
                )
            ),
            "credential": self.credential.record(),
            "data": (
                "between the miner and their chosen provider under the miner's own "
                "account; Carbon sends public synthetic and the miner's own "
                "permitted research material only"
            ),
        }

    def manifest_record(self):
        """The manifest's `provider` block. The historical pinned selection
        keeps the exact block every earlier manifest carries."""
        if self.is_historical_default:
            return {
                "model": self.model_id,
                **self.pricing.per_million(),
                "store": False,
                "data": "public synthetic and own permitted research only; standard API abuse monitoring may retain up to 30 days",
            }
        return self.record()


_TICKETS = set()


def _int(value, low, high, name):
    if type(value) is not int or not low <= value <= high:
        raise ModelSelectionRefused(f"{name} must be an integer in [{low}, {high}]")
    return value


def _declared_pricing(value):
    if type(value) is not dict or set(value) != {
        "input_nano",
        "cached_input_nano",
        "output_nano",
        "observed",
        "note",
    }:
        raise ModelSelectionRefused(
            "declared pricing needs input_nano, cached_input_nano, output_nano, "
            "observed (YYYY-MM-DD) and note"
        )
    prices = [
        _int(value[k], 0, 10**9, k)
        for k in ("input_nano", "cached_input_nano", "output_nano")
    ]
    if type(value["observed"]) is not str or not _DATE.fullmatch(value["observed"]):
        raise ModelSelectionRefused("declared pricing needs an observed date")
    if type(value["note"]) is not str or not 1 <= len(value["note"]) <= 512:
        raise ModelSelectionRefused("declared pricing needs a bounded note")
    return Pricing(
        *prices,
        source="miner_declared",
        reference="stated by the miner",
        observed=value["observed"],
        note=value["note"],
    )


_OBSERVED_AT = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")


def _published_pricing(adapter, value):
    """A provider-published price, as `published_pricing` read it.

    Only an adapter whose prices are live (`live_pricing`) takes one, and it
    must name that adapter's own public list as its reference.
    """
    if not adapter.live_pricing:
        raise ModelSelectionRefused("this adapter's prices are not published live")
    fields = {
        "unit",
        "input",
        "cached_input",
        "output_including_reasoning",
        "source",
        "reference",
        "observed",
        "note",
    }
    if type(value) is not dict or set(value) != fields:
        raise ModelSelectionRefused("published pricing record malformed")
    if (
        value["unit"] != "nanodollars per token"
        or value["source"] != "provider_published"
        or value["reference"] != adapter.models_url
        or type(value["observed"]) is not str
        or not _OBSERVED_AT.fullmatch(value["observed"])
        or type(value["note"]) is not str
        or not 1 <= len(value["note"]) <= 512
    ):
        raise ModelSelectionRefused("published pricing record malformed")
    prices = [
        _int(value[k], 0, 10**9, k)
        for k in ("input", "cached_input", "output_including_reasoning")
    ]
    return Pricing(
        *prices,
        source="provider_published",
        reference=adapter.models_url,
        observed=value["observed"],
        note=value["note"],
    )


def _nano_per_token(usd_per_million):
    if (
        type(usd_per_million) not in (int, float)
        or isinstance(usd_per_million, bool)
        or not 0 <= usd_per_million <= 10**6
    ):
        raise ValueError("published price malformed")
    return round(usd_per_million * 1000)


def published_pricing(adapter_id, model_id, *, opener=None, now=None):
    """The price `adapter_id` publishes for `model_id` now, as a record.

    Reads the provider's public model list (no key). A model the list does not
    carry, or carries without a price, has no published price: ValueError.
    The record names the list and the time it was read; `select` takes it as
    `published_pricing`.
    """
    import datetime

    adapter = ADAPTERS[adapter_id]
    if not adapter.live_pricing:
        raise ValueError("this provider publishes no live prices")
    items = _model_list(adapter, opener)
    item = next((i for i in items if type(i) is dict and i.get("id") == model_id), None)
    if item is None:
        raise ValueError("model not in the published list")
    pricing = item.get("pricing")
    if type(pricing) is not dict or not {"prompt", "completion"} <= set(pricing):
        raise ValueError("model has no published price")
    input_nano = _nano_per_token(pricing["prompt"])
    observed = (now or datetime.datetime.now(datetime.UTC)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    return {
        "unit": "nanodollars per token",
        "input": input_nano,
        "cached_input": _nano_per_token(
            pricing.get("input_cache_read", pricing["prompt"])
        ),
        "output_including_reasoning": _nano_per_token(pricing["completion"]),
        "source": "provider_published",
        "reference": adapter.models_url,
        "observed": observed,
        "note": (
            "Read from the provider's public model list when this selection "
            "was made. Prices change; reconcile against your provider's usage."
        ),
    }


def _endpoint(adapter, endpoint):
    if adapter.endpoint is not None:
        if endpoint not in (None, adapter.endpoint):
            raise ModelSelectionRefused("this adapter's endpoint is fixed")
        return adapter.endpoint
    if (
        type(endpoint) is not str
        or len(endpoint) > 512
        or not re.fullmatch(r"https://[A-Za-z0-9.-]+(:\d{1,5})?(/[^\s?#]*)?", endpoint)
    ):
        raise ModelSelectionRefused(
            "an https endpoint URL (no query or fragment) is required for this adapter"
        )
    return endpoint


def _credential(value):
    if type(value) is not dict or set(value) != {"kind", "reference"}:
        raise ModelSelectionRefused("credential needs kind and reference")
    if value["kind"] != "file":
        # Owner order 2026-09-26 section 8: the key lives in its file and is
        # read at the point of use, never from an environment variable.
        raise ModelSelectionRefused("the credential is a key file path")
    reference = value["reference"]
    if type(reference) is not str or not 1 <= len(reference) <= 4096:
        raise ModelSelectionRefused("a credential file path is required")
    return CredentialReference("file", reference)


#: Where a new plan's default output cap came from (`output_maximum`).
OUTPUT_FROM_MODEL = "model_documented_maximum"
OUTPUT_FROM_PROVIDER = "provider_documented_maximum"
OUTPUT_CONSERVATIVE = "no_documented_maximum"


def output_maximum(provider_id, model_id):
    """The selected model's own maximum output, as Carbon records it:
    `{"max_output_tokens", "basis", "source"}`.

    1. The model's own documented maximum (`ProviderAdapter.output_maxima`).
    2. Otherwise the provider's documented maximum for the models it serves
       (`ProviderAdapter.output_maximum`).
    3. Otherwise Carbon knows none, and never guesses one. A cap above a
       model's real maximum is refused by its provider as an invalid request,
       which replays and stops the campaign, so the conservative historical
       cap (`DEFAULT_SETTINGS`, 2,048 tokens) is reserved until the miner sets
       their own.

    Never outside `OUTPUT_TOKEN_BOUNDS`.
    """
    adapter = ADAPTERS.get(provider_id)
    if adapter is None:
        raise ModelSelectionRefused("unknown provider adapter")
    documented = adapter.output_maxima.get(model_id)
    basis = OUTPUT_FROM_MODEL
    if documented is None:
        documented, basis = adapter.output_maximum, OUTPUT_FROM_PROVIDER
    if documented is None:
        return {
            "max_output_tokens": DEFAULT_SETTINGS.max_output_tokens,
            "basis": OUTPUT_CONSERVATIVE,
            "source": None,
        }
    low, high = OUTPUT_TOKEN_BOUNDS
    return {
        "max_output_tokens": min(max(documented.tokens, low), high),
        "basis": basis,
        "source": documented.record(),
    }


def select(
    *,
    provider_id,
    model_id=None,
    credential,
    endpoint=None,
    settings=None,
    declared_pricing=None,
    published_pricing=None,
    output_default=None,
):
    """Validate a miner's choice into a `ModelSelection`.

    `credential` is {"kind": "file", "reference": path}. `model_id` may be
    omitted for an adapter with a default model (Engy's is
    deepseek-v4-flash-0731). `settings` may override max_input_tokens,
    max_output_tokens, reasoning_effort and timeout_seconds.
    `declared_pricing` is the miner's own statement of price for a model with
    no listed price; a listed price is never overridden. `published_pricing`
    is a live-priced provider's own price as `published_pricing()` read it.
    `output_default` is how an unset max_output_tokens is chosen: None, the
    historical 2,048, or `OUTPUT_DEFAULT_V2` for a new plan, the model's own
    maximum (`output_maximum`). A max_output_tokens in `settings` binds
    either way.
    """
    adapter = ADAPTERS.get(provider_id)
    if adapter is None:
        raise ModelSelectionRefused("unknown provider adapter")
    if output_default not in OUTPUT_DEFAULTS:
        raise ModelSelectionRefused("unknown output default")
    if model_id is None:
        model_id = adapter.default_model
    if type(model_id) is not str or not _MODEL_ID.fullmatch(model_id):
        raise ModelSelectionRefused("a model id is required")
    if adapter.allowed_models is not None and model_id not in adapter.allowed_models:
        raise ModelSelectionRefused("model id not allowed for this provider")
    chosen = dict(DEFAULT_SETTINGS.record())
    if output_default == OUTPUT_DEFAULT_V2:
        chosen["max_output_tokens"] = output_maximum(provider_id, model_id)[
            "max_output_tokens"
        ]
    if settings is not None:
        if type(settings) is not dict or not set(settings) <= set(chosen):
            raise ModelSelectionRefused("unknown model setting")
        chosen.update(settings)
    if chosen["reasoning_effort"] not in EFFORTS:
        raise ModelSelectionRefused("unsupported reasoning effort")
    resolved = Settings(
        max_input_tokens=_int(
            chosen["max_input_tokens"], 16384, 1048576, "max_input_tokens"
        ),
        max_output_tokens=_int(
            chosen["max_output_tokens"], *OUTPUT_TOKEN_BOUNDS, "max_output_tokens"
        ),
        reasoning_effort=chosen["reasoning_effort"],
        timeout_seconds=_int(chosen["timeout_seconds"], 10, 600, "timeout_seconds"),
    )
    listed = adapter.priced_models.get(model_id)
    if listed is not None and declared_pricing is not None:
        raise ModelSelectionRefused("this model's price is listed; do not declare one")
    if published_pricing is not None and declared_pricing is not None:
        raise ModelSelectionRefused("a price is published or declared, not both")
    if published_pricing is not None:
        pricing = _published_pricing(adapter, published_pricing)
    elif listed is not None:
        pricing = listed
    else:
        pricing = (
            None if declared_pricing is None else _declared_pricing(declared_pricing)
        )
    endpoint, credential = _endpoint(adapter, endpoint), _credential(credential)
    ticket = object()
    _TICKETS.add(ticket)
    try:
        return ModelSelection(
            adapter, model_id, endpoint, resolved, pricing, credential, _token=ticket
        )
    finally:
        _TICKETS.discard(ticket)


def selection_from_record(record, *, credential_file=None):
    """The selection a manifest's `provider` block records.

    The historical block (every campaign pinned before selection existed)
    resolves to the pinned default and must match it exactly. A newer block is
    re-validated through `select()`; the credential file's path is not
    recorded, so it is supplied again at run time.
    """
    if type(record) is not dict:
        raise ModelSelectionRefused("provider record required")
    if "schema" not in record:
        if record != DEFAULT_SELECTION.manifest_record():
            raise ModelSelectionRefused("historical provider record differs")
        return _default(credential_file)
    if record.get("schema") != SELECTION_SCHEMA:
        raise ModelSelectionRefused("unknown provider record schema")
    pricing = record.get("pricing")
    declared = published = None
    if pricing is not None and pricing.get("source") == "provider_published":
        adapter = ADAPTERS.get(record.get("provider_id"))
        if adapter is not None and adapter.live_pricing:
            published = pricing
    if pricing is not None and pricing.get("source") == "miner_declared":
        declared = {
            "input_nano": pricing["input"],
            "cached_input_nano": pricing["cached_input"],
            "output_nano": pricing["output_including_reasoning"],
            "observed": pricing["observed"],
            "note": pricing["note"],
        }
    if credential_file is None:
        raise ModelSelectionRefused("the credential file must be supplied again")
    adapter = ADAPTERS.get(record.get("provider_id"))
    selection = select(
        provider_id=record.get("provider_id"),
        model_id=record.get("model"),
        credential={"kind": "file", "reference": str(credential_file)},
        endpoint=None if adapter is None or adapter.endpoint else record["endpoint"],
        settings=record.get("settings"),
        declared_pricing=declared,
        published_pricing=published,
    )
    if selection.record() != record:
        raise ModelSelectionRefused("provider record does not re-validate exactly")
    return selection


def selection_spec(selection, *, settings=None):
    """The `select()` arguments (credential aside) that rebuild `selection`.

    The launch path hands a validated selection to a campaign as these, so an
    endpoint, a declared price or a published price chosen in setup travels
    with it rather than being dropped.
    """
    spec = {"provider_id": selection.provider_id, "model_id": selection.model_id}
    if settings is not None:
        spec["settings"] = dict(settings)
    if selection.adapter.endpoint is None:
        spec["endpoint"] = selection.endpoint
    pricing = selection.pricing
    if pricing is not None and pricing.source == "miner_declared":
        spec["declared_pricing"] = {
            "input_nano": pricing.input_nano,
            "cached_input_nano": pricing.cached_input_nano,
            "output_nano": pricing.output_nano,
            "observed": pricing.observed,
            "note": pricing.note,
        }
    elif (
        pricing is not None
        and pricing.source == "provider_published"
        and selection.adapter.live_pricing
    ):
        spec["published_pricing"] = pricing.record()
    return spec


def check_budget(selection, ceilings):
    """A miner spend limit in money needs a price to enforce it against."""
    if (
        selection.pricing is None
        and type(ceilings) is dict
        and ceilings.get("provider_nanodollars") is not None
    ):
        raise ModelSelectionRefused(
            "a provider spend limit needs a listed or declared price for this model"
        )


def _default(credential_file):
    return select(
        provider_id="openai-responses",
        model_id=GPT5_MINI,
        credential={
            "kind": "file",
            "reference": "unset" if credential_file is None else str(credential_file),
        },
    )


DEFAULT_SELECTION = _default(None)

# The names the research loop and the legacy Burgers session have always used.
MODEL = DEFAULT_SELECTION.model_id
MAX_INPUT_TOKENS = DEFAULT_SETTINGS.max_input_tokens
MAX_OUTPUT_TOKENS = DEFAULT_SETTINGS.max_output_tokens


def _credential_state(path):
    """Whether a key file is configured, from metadata alone; never read."""
    if path is None:
        return "credential_not_configured"
    path = Path(path)
    try:
        if path.is_symlink() or not path.is_file():
            return "credential_not_configured"
        size = path.stat().st_size
    except OSError:
        return "credential_not_configured"
    return None if 0 < size <= 1024 else "credential_file_unusable"


def provider_summary(credentials=None):
    """Every provider adapter, its models and prices, and whether the miner
    has a key file configured for it.

    `credentials` maps adapter id to the path of the miner's key file.
    Availability is judged from the file's metadata only: no key is read and
    no provider is contacted, so `available` means a key file is configured,
    not that the provider accepts it.
    """
    credentials = credentials or {}
    rows = []
    for adapter in ADAPTERS.values():
        reason = _credential_state(credentials.get(adapter.adapter_id))
        rows.append(
            {
                "schema": PROVIDER_SUMMARY,
                "provider_id": adapter.adapter_id,
                "display_name": adapter.display_name,
                "protocol": adapter.protocol,
                "endpoint": adapter.endpoint,
                "base_url": adapter.base_url,
                "endpoint_required": adapter.endpoint is None,
                "models": adapter.summary_models(),
                "model_policy": (
                    "only the listed models"
                    if adapter.allowed_models is not None
                    else "Name any model id. A listed model carries its sourced "
                    "price; any other has an unknown price unless you declare one."
                ),
                "spend_bound_for_unpriced_models": UNKNOWN_SPEND,
                "charge_settled_from": adapter.reported_charge
                or "metered usage at the model's price",
                "credential": {
                    "kind": "file",
                    "owner": "the miner; Carbon never issues or holds a provider key",
                },
                "default_settings": DEFAULT_SETTINGS.record(),
                "available": reason is None,
                "reason": reason,
                "availability_basis": (
                    "key file metadata only; no key was read and no provider "
                    "was contacted"
                ),
            }
        )
    return rows


class ProviderOutcome(enum.Enum):
    RATE_LIMITED = "rate_limited"
    QUOTA_EXHAUSTED = "quota_exhausted"
    AUTH_CREDENTIAL = "auth_credential"
    CONTEXT_LIMIT = "context_limit"
    INVALID_REQUEST = "invalid_request"
    TRANSIENT_SERVER = "transient_server"
    UNKNOWN = "unknown"
    #: A 502, 503 or 529 whose body carries no usage object and no provider
    #: charge report (LP-PROD-A).
    SERVER_UNAVAILABLE = "server_unavailable"
    #: The connection was refused or the provider's name did not resolve:
    #: nothing was sent (LP-PROD-A).
    UNREACHABLE = "unreachable"


#: Rejected before generation, so the attempt incurred no charge, and safe to
#: send again at once under a new identity and reservation, after a backoff
#: (`research_agent.request_model`).
RETRY_SAFE = frozenset(
    {
        ProviderOutcome.RATE_LIMITED,
        ProviderOutcome.SERVER_UNAVAILABLE,
        ProviderOutcome.UNREACHABLE,
    }
)


class ProviderHTTPError(Exception):
    """A provider HTTP rejection reduced to what classification needs.

    Only the status, the provider's machine-readable error code, a bounded
    Retry-After and whether the body carried a usage object or a provider
    charge report (`usage_reported`) survive; the
    message text, which can echo request or credential material, is
    discarded here.
    """

    def __init__(self, status, *, code=None, retry_after=None, usage_reported=False):
        super().__init__("provider HTTP status " + str(status))
        self.status, self.code, self.retry_after = status, code, retry_after
        self.usage_reported = usage_reported


class NotDispatched(ValueError):
    """The request could not be expressed in the provider's protocol and was
    never sent. Safe: nothing was processed, so nothing can have been billed."""


class CredentialUnavailable(ValueError):
    """The miner's key file is missing, unreadable or malformed, found before
    anything was sent: a credential failure the miner fixes, with nothing
    processed or billed. Carries no path or key text."""


class ProviderUnreachable(ConnectionError):
    """The connection to the provider was refused, or its name did not
    resolve, before any byte of the request was sent: nothing was processed,
    so nothing can have been billed. Carries no provider or network text. An
    `OSError`, so a caller that catches network failures still catches it."""


@dataclass(frozen=True)
class ProviderFailure:
    outcome: ProviderOutcome
    http_status: int | None
    provider_code: str | None
    retry_after_seconds: int | None
    #: Rejected before generation: attempt counted, no token charge. False
    #: means the full reservation stays.
    unbilled: bool
    #: Only a rate limit rejected before generation may be retried, and only
    #: under a new reservation.
    retry_safe: bool

    def record(self):
        return {
            "provider_outcome": self.outcome.value,
            "http_status": self.http_status,
            "provider_code": self.provider_code,
            "retry_after_seconds": self.retry_after_seconds,
            "unbilled": self.unbilled,
        }


def _retry_after(value):
    if value is None:
        return None
    try:
        seconds = int(str(value).strip())
    except ValueError:
        return None  # an HTTP-date is not trusted as a clock; use backoff
    return seconds if 0 <= seconds <= 3600 else None


def _code(value):
    if type(value) is not str or not re.fullmatch(r"[a-z0-9_]{1,64}", value):
        return None
    return value


def classify(error, errors=OPENAI_ERRORS):
    """The typed outcome of a failed provider call. Anything not recognised is
    UNKNOWN, which keeps the full reservation and is never resent."""
    if type(error) is NotDispatched:
        return ProviderFailure(
            ProviderOutcome.INVALID_REQUEST, None, None, None, True, False
        )
    if type(error) is ProviderUnreachable:
        return ProviderFailure(
            ProviderOutcome.UNREACHABLE, None, None, None, True, True
        )
    if type(error) is CredentialUnavailable:
        return ProviderFailure(
            ProviderOutcome.AUTH_CREDENTIAL, None, None, None, True, False
        )
    if type(error) is not ProviderHTTPError:
        return ProviderFailure(ProviderOutcome.UNKNOWN, None, None, None, False, False)
    status, code = error.status, _code(error.code)
    retry_after = _retry_after(error.retry_after)
    if code in errors.overload_codes or (
        status in errors.rate_limit_statuses and code not in errors.quota_codes
    ):
        return ProviderFailure(
            ProviderOutcome.RATE_LIMITED, status, code, retry_after, True, True
        )
    if (
        status in errors.unavailable_statuses
        and error.usage_reported is False
        and code not in errors.quota_codes
    ):
        # The server answered it could not take the request, and reported no
        # usage: rejected before generation (OWNER-LAUNCHPAD-PROD-01).
        return ProviderFailure(
            ProviderOutcome.SERVER_UNAVAILABLE, status, code, retry_after, True, True
        )
    unbilled = status in errors.unbilled_rejections
    if status == 402 or code in errors.quota_codes:
        outcome = ProviderOutcome.QUOTA_EXHAUSTED
    elif status in (401, 403):
        outcome = ProviderOutcome.AUTH_CREDENTIAL
    elif status == 400 and code in errors.context_codes:
        outcome = ProviderOutcome.CONTEXT_LIMIT
    elif status in (400, 404, 409, 413, 422):
        outcome = ProviderOutcome.INVALID_REQUEST
    elif status in (500, 502, 503, 504):
        outcome = ProviderOutcome.TRANSIENT_SERVER
    else:
        outcome = ProviderOutcome.UNKNOWN
    if outcome in (ProviderOutcome.TRANSIENT_SERVER, ProviderOutcome.UNKNOWN):
        unbilled = False
    return ProviderFailure(outcome, status, code, retry_after, unbilled, False)


def read_credential(reference: CredentialReference):
    """The key, read from its file only at the point of use. Callers pass it
    straight into one request header and hold it nowhere else."""
    path = Path(reference.reference)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 1024:
        raise ValueError("operator API credential file required")
    key = path.read_text().strip()
    if not key or "\n" in key or "\r" in key:
        raise ValueError("invalid API credential file")
    return key


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


#: Added to a selection's `timeout_seconds` to form each provider call's hard
#: total wall-clock deadline (GRAPHITE-D27). urllib applies `timeout_seconds`
#: to each socket operation separately - connect, the TLS handshake, the proxy
#: CONNECT, every read - so a reply that trickles, or headers or a body that
#: arrive in pieces each inside the timeout, never ends the call. The margin
#: admits the connect, handshake and send that precede the reply wait, so a
#: call that completed historically within its per-read timeout still does.
DEADLINE_MARGIN_SECONDS = 10


def call_deadline_seconds(settings):
    """The hard total wall-clock bound on one provider call, in seconds."""
    return settings.timeout_seconds + DEADLINE_MARGIN_SECONDS


class ProviderDeadlineExceeded(Exception):
    """A provider call passed its hard total deadline and was abandoned.

    The request may have been processed, so this classifies as UNKNOWN: the
    full reservation stays and nothing is resent. Carries no provider text."""


class _Call:
    """The sockets one call opens, so its deadline can shut them."""

    def __init__(self):
        self.lock, self.sockets, self.aborted = threading.Lock(), [], False

    def register(self, sock):
        with self.lock:
            self.sockets.append(sock)
            aborted = self.aborted
        if aborted:
            _shut(sock)
            raise ProviderDeadlineExceeded("provider call deadline passed")
        return sock

    def track(self, connection_class):
        """`connection_class`, recording its TCP socket when created and its
        TLS socket before the handshake, so a stalled connect, proxy CONNECT,
        handshake or read can each be shut (urllib drops `sock` from the
        connection once headers arrive, so the sockets are kept here)."""
        call = self

        class Tracked(connection_class):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                create = self._create_connection
                self._create_connection = lambda *a, **k: call.register(create(*a, **k))
                if getattr(self, "_context", None) is not None:
                    self._context = _TrackedContext(self._context, call)

        return Tracked

    def abort(self):
        """Shut every socket the call opened; a read blocked on one returns."""
        with self.lock:
            self.aborted = True
            sockets = list(self.sockets)
        for sock in sockets:
            _shut(sock)


class _TrackedContext:
    """An SSL context whose sockets are registered before their handshake."""

    def __init__(self, context, call):
        self._wrapped, self._call = context, call

    def wrap_socket(self, sock, **kwargs):
        wrapped = self._wrapped.wrap_socket(
            sock, do_handshake_on_connect=False, **kwargs
        )
        self._call.register(wrapped)
        wrapped.do_handshake()
        return wrapped

    def __getattr__(self, name):
        return getattr(self._wrapped, name)


def _shut(sock):
    if sock is None:
        return
    try:
        # The plain-socket shutdown, also for a TLS socket: it unblocks a read
        # in the worker without touching the TLS state that read is using.
        socket.socket.shutdown(sock, socket.SHUT_RDWR)
    except OSError:
        pass


class _TrackedHandler:
    def __init__(self, call):
        super().__init__()
        self._call = call

    def do_open(self, http_class, req, **kwargs):
        return super().do_open(self._call.track(http_class), req, **kwargs)


class _TrackedHTTPHandler(_TrackedHandler, urllib.request.HTTPHandler):
    pass


class _TrackedHTTPSHandler(_TrackedHandler, urllib.request.HTTPSHandler):
    pass


#: Connection failures that happen before any byte of the request is written:
#: a refused TCP connect (only `connect` returns it) and a name that did not
#: resolve. urllib wraps both in `URLError` from the connect inside
#: `HTTPConnection.request`, before the request line is sent.
_NOT_SENT = (ConnectionRefusedError, socket.gaierror)


def _exchange(opener, outgoing, timeout, limit):
    """Send the request and read the bounded reply; the network half of
    `_post`, run in its worker thread. Rejections become `ProviderHTTPError`,
    and a connection refused or a name unresolved before anything was sent
    becomes `ProviderUnreachable`."""
    try:
        with opener.open(outgoing, timeout=timeout) as response:
            return response.read(limit + 1)
    except urllib.error.HTTPError as rejected:
        code, usage = None, False
        try:
            parsed = json.loads(rejected.read(64 * 1024))
            if type(parsed) is dict:
                # A body that reports usage, or a provider charge (Engy's
                # `x_engy`), may have been generated and billed.
                usage = (
                    parsed.get("usage") is not None or parsed.get("x_engy") is not None
                )
            error = parsed.get("error") if type(parsed) is dict else None
            if type(error) is dict:
                # OpenAI names it `code`; Anthropic Messages names it `type`.
                code = error.get("code") or error.get("type")
        except Exception:  # noqa: BLE001 - an unreadable body has no code
            code = None
        retry_after = (
            None if rejected.headers is None else rejected.headers.get("Retry-After")
        )
        raise ProviderHTTPError(
            rejected.code, code=code, retry_after=retry_after, usage_reported=usage
        ) from None
    except urllib.error.URLError as failed:
        if isinstance(failed.reason, _NOT_SENT):
            raise ProviderUnreachable("provider unreachable; nothing sent") from None
        raise


def _post(selection, body, opener=None, deadline=None):
    """POST `body` to the selection's endpoint, reading the key here and
    nowhere else. Rejections become `ProviderHTTPError` with no text.

    The exchange runs in a daemon worker joined for at most `deadline` seconds
    (default `call_deadline_seconds`). Past it the call's sockets are shut and
    `ProviderDeadlineExceeded` is raised; whatever the worker later receives
    is discarded, and a daemon thread never holds up process exit."""
    adapter, settings = selection.adapter, selection.settings
    if deadline is None:
        deadline = call_deadline_seconds(settings)
    headers = {"Content-Type": "application/json"}
    if adapter.protocol == MESSAGES:
        headers["anthropic-version"] = ANTHROPIC_VERSION
    try:
        key = read_credential(selection.credential)
    except (OSError, ValueError):
        # Nothing has been sent: a typed credential failure, never an
        # outcome to reconcile (LP-PROD-A).
        raise CredentialUnavailable("provider key file unusable") from None
    if adapter.auth == "x-api-key":
        headers["x-api-key"] = key
    else:
        headers["Authorization"] = "Bearer " + key
    del key
    outgoing = urllib.request.Request(
        selection.endpoint, data=body, headers=headers, method="POST"
    )
    del headers
    call = _Call()
    opener = opener or urllib.request.build_opener(
        _NoRedirect(), _TrackedHTTPHandler(call), _TrackedHTTPSHandler(call)
    )
    limit = settings.max_response_bytes
    outcome = {}

    def work(request):
        try:
            outcome["payload"] = _exchange(
                opener, request, settings.timeout_seconds, limit
            )
        except BaseException as error:  # noqa: BLE001 - re-raised by the caller
            outcome["error"] = error

    worker = threading.Thread(
        target=work, args=(outgoing,), name="carbon-provider-call", daemon=True
    )
    del outgoing
    worker.start()
    worker.join(deadline)
    if worker.is_alive():
        call.abort()
        raise ProviderDeadlineExceeded("provider call deadline passed")
    if "error" in outcome:
        raise outcome.pop("error")
    payload = outcome["payload"]
    if len(payload) > limit:
        raise ValueError("provider response exceeds bound")
    return json.loads(payload)


def _responses_body(request):
    """The Responses request as sent: a null reasoning setting is omitted."""
    return {k: v for k, v in request.items() if not (k == "reasoning" and v is None)}


def _text(item):
    return "".join(
        part.get("text", "")
        for part in item.get("content") or []
        if type(part) is dict and part.get("type") == "output_text"
    )


def _refuse_constant(name):
    raise ValueError("not a JSON number: " + name)


def _chat_arguments(arguments):
    """A history tool call's arguments as Chat Completions receives them: the
    model's own string when it is one JSON object, otherwise "{}"."""
    if type(arguments) is str:
        try:
            value = json.loads(arguments, parse_constant=_refuse_constant)
        except (ValueError, RecursionError):
            value = None
        if type(value) is dict:
            return arguments
    return "{}"


#: How a protocol names a reply cut off at its output limit, read as the
#: Responses API's `incomplete_details.reason`.
_INCOMPLETE_REASONS = {"length": "max_output_tokens", "max_tokens": "max_output_tokens"}


def _incomplete(status, stop_reason):
    """The Responses-shaped `incomplete_details` of a translated reply that
    did not complete, from the protocol's own stop reason (a closed code, or
    `unknown`); nothing for a completed one."""
    if status == "completed":
        return {}
    # Untrusted: a stop reason that is not a string is `unknown`, never a
    # lookup that raises.
    reason = (
        _INCOMPLETE_REASONS.get(stop_reason, stop_reason)
        if type(stop_reason) is str
        else None
    )
    return {"incomplete_details": {"reason": _code(reason) or "unknown"}}


def chat_request(request):
    """Translate the loop's Responses-shaped request into Chat Completions.

    The loop keeps one history format; this adapter maps it onto chat
    messages. Reasoning items and the reasoning setting have no portable chat
    equivalent and are not sent; `store` is a Responses-only field.

    A turn's function calls, and any text the model wrote before them, become
    one assistant message carrying all of them, as the model returned it and
    as Chat Completions requires before their tool replies (a turn with
    several calls, LP-PROD-A). A call whose arguments are not one JSON object
    - none, blank, cut off by the output limit, or otherwise malformed - is
    sent back as "{}" (`_chat_arguments`): a chat endpoint may parse the
    arguments in its history and refuse the whole request, which would wedge
    the epoch on the model's own mistake. The loop has already answered such
    a call with a typed result naming the problem. The loop journals the
    Responses-shaped request, never this translation, so a replay is
    unaffected.
    """
    messages = [{"role": "system", "content": request["instructions"]}]
    for item in request["input"]:
        kind = item.get("type") if type(item) is dict else None
        if kind is None and item.get("role") in ("user", "assistant"):
            messages.append({"role": item["role"], "content": item["content"]})
        elif kind == "message":
            messages.append(
                {"role": item.get("role", "assistant"), "content": _text(item)}
            )
        elif kind == "function_call":
            call = {
                "id": item["call_id"],
                "type": "function",
                "function": {
                    "name": item["name"],
                    "arguments": _chat_arguments(item.get("arguments")),
                },
            }
            previous = messages[-1]
            if previous["role"] == "assistant":
                previous.setdefault("tool_calls", []).append(call)
            else:
                messages.append(
                    {"role": "assistant", "content": None, "tool_calls": [call]}
                )
        elif kind == "function_call_output":
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": item["call_id"],
                    "content": item["output"],
                }
            )
        elif kind == "reasoning":
            continue
        else:
            raise NotDispatched("history item has no chat translation")
    return {
        "model": request["model"],
        "messages": messages,
        "tools": [
            {
                "type": "function",
                "function": {
                    key: tool[key]
                    for key in ("name", "description", "parameters", "strict")
                    if key in tool
                },
            }
            for tool in request["tools"]
        ],
        "parallel_tool_calls": request["parallel_tool_calls"],
        "max_tokens": request["max_output_tokens"],
    }


def _engy_report(response):
    """Engy's per-call report, carried through translation unchanged."""
    report = response.get("x_engy")
    return {"x_engy": report} if report is not None else {}


def chat_response(response):
    """Translate a Chat Completions reply into the Responses shape the loop
    reads: one message item and/or function_call items, and token usage.

    A reply that did not finish (`finish_reason` other than stop or
    tool_calls) is `incomplete`, with `incomplete_details.reason`:
    `max_output_tokens` for `length`, otherwise the finish reason as a closed
    code (LP-PROD-A)."""
    if type(response) is not dict or type(response.get("choices")) is not list:
        raise ValueError("chat response malformed")
    if len(response["choices"]) != 1 or type(response["choices"][0]) is not dict:
        raise ValueError("exactly one chat choice required")
    choice = response["choices"][0]
    message = choice.get("message")
    if type(message) is not dict:
        raise ValueError("chat response malformed")
    output = []
    if type(message.get("content")) is str and message["content"]:
        output.append(
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": message["content"]}],
            }
        )
    for call in message.get("tool_calls") or []:
        function = call.get("function") if type(call) is dict else None
        if type(function) is not dict:
            raise ValueError("chat tool call malformed")
        output.append(
            {
                "type": "function_call",
                "call_id": call.get("id"),
                "name": function.get("name"),
                "arguments": function.get("arguments"),
            }
        )
    usage = response.get("usage")
    translated_usage = None
    if type(usage) is dict:
        translated_usage = {
            "input_tokens": usage.get("prompt_tokens"),
            "output_tokens": usage.get("completion_tokens"),
        }
        details = usage.get("prompt_tokens_details")
        if type(details) is dict and "cached_tokens" in details:
            translated_usage["input_tokens_details"] = {
                "cached_tokens": details["cached_tokens"]
            }
        details = usage.get("completion_tokens_details")
        if type(details) is dict and "reasoning_tokens" in details:
            translated_usage["output_tokens_details"] = {
                "reasoning_tokens": details["reasoning_tokens"]
            }
    finished = choice.get("finish_reason")
    status = "completed" if finished in ("stop", "tool_calls") else "incomplete"
    return {
        "model": response.get("model"),
        "status": status,
        **_incomplete(status, finished),
        "output": output,
        "usage": translated_usage,
        "provider_protocol": CHAT_COMPLETIONS,
        **_engy_report(response),
    }


_CACHEABLE = ("text", "tool_result")


def messages_request(request, adapter):
    """Translate the loop's Responses-shaped request into Anthropic Messages.

    History items map one to one: user text and assistant text become text
    blocks; a function_call becomes an assistant `tool_use` block (its JSON
    arguments decoded to the `input` object); a function_call_output becomes a
    user `tool_result` block. Consecutive items of one role merge into one
    message, as Messages requires alternating turns. Thinking blocks a
    Messages model returned are carried back verbatim; reasoning items from
    another protocol have no Messages form and are dropped. `strict`,
    `store` and the reasoning effort have no Messages equivalent and are not
    sent. With `cache_breakpoints`, the tools, system prompt and the newest
    turn carry `cache_control` so the stable prefix is cached.
    """
    messages = []

    def push(role, block):
        if messages and messages[-1]["role"] == role:
            messages[-1]["content"].append(block)
        else:
            messages.append({"role": role, "content": [block]})

    for item in request["input"]:
        kind = item.get("type") if type(item) is dict else None
        if kind is None and item.get("role") in ("user", "assistant"):
            if type(item.get("content")) is not str:
                raise NotDispatched("message content must be text")
            push(item["role"], {"type": "text", "text": item["content"]})
        elif kind == "message":
            text = _text(item)
            if text:
                push(item.get("role", "assistant"), {"type": "text", "text": text})
        elif kind == "function_call":
            try:
                arguments = json.loads(item["arguments"])
            except (TypeError, ValueError):
                raise NotDispatched("tool call arguments are not JSON") from None
            if type(arguments) is not dict:
                raise NotDispatched("tool call arguments must be an object")
            push(
                "assistant",
                {
                    "type": "tool_use",
                    "id": item["call_id"],
                    "name": item["name"],
                    "input": arguments,
                },
            )
        elif kind == "function_call_output":
            push(
                "user",
                {
                    "type": "tool_result",
                    "tool_use_id": item["call_id"],
                    "content": item["output"],
                },
            )
        elif kind == "reasoning":
            for block in item.get("messages_blocks") or []:
                push("assistant", block)
        else:
            raise NotDispatched("history item has no Messages translation")
    if not messages or messages[0]["role"] != "user":
        raise NotDispatched("a Messages conversation starts with the user")
    tools = [
        {
            "name": tool["name"],
            "description": tool.get("description", ""),
            "input_schema": tool["parameters"],
        }
        for tool in request["tools"]
    ]
    system = [{"type": "text", "text": request["instructions"]}]
    if adapter.cache_breakpoints:
        mark = {"type": "ephemeral"}
        system[0]["cache_control"] = mark
        if tools:
            tools[-1]["cache_control"] = mark
        last = messages[-1]["content"][-1]
        if last.get("type") in _CACHEABLE:
            last["cache_control"] = mark
    body = {
        "model": request["model"],
        "system": system,
        "messages": messages,
        "max_tokens": request["max_output_tokens"],
    }
    if tools:
        body["tools"] = tools
        body["tool_choice"] = {
            "type": "auto",
            "disable_parallel_tool_use": request["parallel_tool_calls"] is False,
        }
    return body


def _count(value):
    return value if type(value) is int and value >= 0 else None


def messages_response(response):
    """Translate a Messages reply into the Responses shape the loop reads.

    Text blocks become one message item, each `tool_use` a function_call item
    (its input re-encoded canonically, so the history stays byte-stable), and
    thinking blocks a reasoning item that carries them back next turn.
    Messages reports input excluding cache reads and writes; the loop's
    input_tokens is their sum, with the cache read as cached tokens.
    Messages has no reasoning-token count; one is recorded only if the
    provider adds it. A turn that did not finish (`max_tokens`, `pause_turn`,
    `refusal`) is `incomplete`, with `incomplete_details.reason`
    `max_output_tokens` for `max_tokens`, otherwise the stop reason
    (LP-PROD-A).
    """
    from .profile import canonical

    if type(response) is not dict or type(response.get("content")) is not list:
        raise ValueError("Messages response malformed")
    output, texts, thinking = [], [], []

    def flush():
        if texts:
            output.append(
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "".join(texts)}],
                }
            )
            texts.clear()
        if thinking:
            output.append({"type": "reasoning", "messages_blocks": list(thinking)})
            thinking.clear()

    for block in response["content"]:
        kind = block.get("type") if type(block) is dict else None
        if kind == "text":
            if thinking:
                flush()
            texts.append(block.get("text") or "")
        elif kind in ("thinking", "redacted_thinking"):
            if texts:
                flush()
            thinking.append(block)
        elif kind == "tool_use":
            flush()
            if type(block.get("input")) is not dict:
                raise ValueError("Messages tool_use input malformed")
            output.append(
                {
                    "type": "function_call",
                    "call_id": block.get("id"),
                    "name": block.get("name"),
                    "arguments": canonical(block["input"]).decode(),
                }
            )
        else:
            raise ValueError("unmapped Messages content block")
    flush()
    usage = response.get("usage")
    translated = None
    if type(usage) is dict:
        fresh = _count(usage.get("input_tokens"))
        # An absent cache count is unknown, never zero: a provider that omits
        # it (Engy's Messages endpoint did) must read as CACHE_NOT_REPORTED,
        # not as a cache that missed every turn. Pricing already treats an
        # unknown cached count as all uncached.
        read = _count(usage.get("cache_read_input_tokens"))
        written = _count(usage.get("cache_creation_input_tokens"))
        translated = {
            "input_tokens": (
                None if fresh is None else fresh + (read or 0) + (written or 0)
            ),
            "output_tokens": usage.get("output_tokens"),
        }
        if read is not None or written is not None:
            translated["input_tokens_details"] = {
                "cached_tokens": read,
                "cache_creation_tokens": written,
            }
        details = usage.get("output_tokens_details")
        reasoning = (
            details.get("reasoning_tokens")
            if type(details) is dict
            else usage.get("reasoning_tokens")
        )
        if reasoning is not None:
            translated["output_tokens_details"] = {"reasoning_tokens": reasoning}
    stopped = response.get("stop_reason")
    status = (
        "completed"
        if stopped in ("end_turn", "tool_use", "stop_sequence")
        else "incomplete"
    )
    return {
        "model": response.get("model"),
        "status": status,
        **_incomplete(status, stopped),
        "output": output,
        "usage": translated,
        "provider_protocol": MESSAGES,
        "provider_stop_reason": stopped,
        **_engy_report(response),
    }


def provider_report(response, selection):
    """What the provider itself reported about this call: the charge (for an
    adapter that reports one) and the serving identity. Missing or malformed
    fields are None - unknown, never zero."""
    if selection.adapter.reported_charge is None:
        return None
    report = response.get("x_engy") if type(response) is dict else None
    report = report if type(report) is dict else {}

    def ident(value):
        if type(value) is int and value >= 0:
            return value
        if type(value) is str and 1 <= len(value) <= 256 and value.isprintable():
            return value
        return None

    charged = report.get("charged_micro")
    return {
        "source": selection.adapter.reported_charge,
        "charged_micro": charged if type(charged) is int and charged >= 0 else None,
        "request_id": ident(report.get("request_id")),
        "miner": ident(report.get("miner")),
        "worker": ident(report.get("worker")),
    }


class SelectionTransport:
    """POST one closed request to the selected provider.

    No redirect is followed and nothing is retried here; a rejection is raised
    as `ProviderHTTPError`, an untranslatable request as `NotDispatched`
    before anything is sent, a connection refused or a name unresolved before
    anything is sent as `ProviderUnreachable`, a call past its hard total
    deadline (`call_deadline_seconds`) as `ProviderDeadlineExceeded`, and
    anything else propagates unchanged; all but those first three classify
    as UNKNOWN. `opener` replaces urllib's, and `deadline_seconds` the
    deadline, for tests only.
    """

    def __init__(
        self, selection: ModelSelection, *, opener=None, deadline_seconds=None
    ):
        if type(selection) is not ModelSelection:
            raise ModelSelectionRefused("a validated ModelSelection is required")
        self.selection, self.opener = selection, opener
        self.deadline_seconds = deadline_seconds

    def __call__(self, request: dict[str, object]):
        from .profile import canonical

        protocol = self.selection.adapter.protocol
        if protocol == CHAT_COMPLETIONS:
            body = chat_request(request)
        elif protocol == MESSAGES:
            body = messages_request(request, self.selection.adapter)
        else:
            body = _responses_body(request)
        # Canonical bytes: sorted keys and no volatile fields, so the same
        # history always produces the same prefix for the provider's cache.
        response = _post(
            self.selection, canonical(body), self.opener, self.deadline_seconds
        )
        if protocol == CHAT_COMPLETIONS:
            return chat_response(response)
        if protocol == MESSAGES:
            return messages_response(response)
        return response


class ProviderTransport(SelectionTransport):
    """The historical pinned OpenAI Responses selection, reading its key from
    the operator's credential file - the signature every caller already uses."""

    def __init__(self, credential_file: Path):
        super().__init__(_default(credential_file))
        self.credential_file = credential_file


def fetch_models(adapter_id="engy-anthropic", *, opener=None):
    """The provider's live public model list (`GET /v1/models`, no key).

    For an operator's live check before configuring; Carbon's tests pass a
    fixture opener and never call it against the network.
    """
    adapter = ADAPTERS[adapter_id]
    items = _model_list(adapter, opener)
    listed = sorted(
        item["id"]
        for item in items
        if type(item) is dict and type(item.get("id")) is str
    )
    return {
        "source": adapter.models_url,
        "models": listed,
        "allowed_and_listed": [m for m in adapter.allowed_models or () if m in listed],
        "allowed_but_not_listed": [
            m for m in adapter.allowed_models or () if m not in listed
        ],
    }


def _model_list(adapter, opener=None):
    """The items of a provider's public model list (`GET /v1/models`)."""
    if adapter.models_url is None:
        raise ValueError("this provider publishes no public model list")
    opener = opener or urllib.request.build_opener(_NoRedirect())
    outgoing = urllib.request.Request(adapter.models_url, method="GET")
    with opener.open(outgoing, timeout=30) as response:
        payload = response.read(2 * 1024**2 + 1)
    if len(payload) > 2 * 1024**2:
        raise ValueError("model list exceeds bound")
    data = json.loads(payload)
    items = data.get("data") if type(data) is dict else None
    if type(items) is not list:
        raise ValueError("model list malformed")
    return items
