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
    retry under a new reservation. Every other failure - a 5xx, a timeout, a
    dropped connection, an unreadable body - keeps its full reservation,
    because the request may have been processed.
    """

    unbilled_rejections: tuple[int, ...]
    rate_limit_statuses: tuple[int, ...]
    overload_codes: tuple[str, ...]
    quota_codes: tuple[str, ...]
    context_codes: tuple[str, ...]
    basis: str


OPENAI_ERRORS = ErrorSemantics(
    unbilled_rejections=(400, 401, 402, 403, 404, 409, 413, 422, 429),
    rate_limit_statuses=(429,),
    overload_codes=(),
    quota_codes=("insufficient_quota",),
    context_codes=("context_length_exceeded",),
    basis=(
        "Carbon's recorded reading of OpenAI-style API error semantics "
        "(2026-09-26): a 4xx rejection is returned before generation and carries "
        "no usage object, so the attempt is counted and no token charge is "
        "recorded. Not invoice-verified; a 5xx or any unreadable outcome keeps "
        "the full reservation."
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
        "(2026-09-26): 429 rate_limit_error and 529 or overloaded_error are "
        "rejected before generation and retried as rate limits; other 4xx are "
        "counted with no token charge; 5xx keep the full reservation. Messages "
        "has no context-limit code, so an over-long prompt is an invalid request."
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
    errors: ErrorSemantics = OPENAI_ERRORS

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

#: The historical settings every pinned campaign ran with.
DEFAULT_SETTINGS = Settings(
    max_input_tokens=65536,
    max_output_tokens=2048,
    reasoning_effort="low",
    timeout_seconds=120,
)

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


def select(
    *,
    provider_id,
    model_id=None,
    credential,
    endpoint=None,
    settings=None,
    declared_pricing=None,
):
    """Validate a miner's choice into a `ModelSelection`.

    `credential` is {"kind": "file", "reference": path}. `model_id` may be
    omitted for an adapter with a default model (Engy's is
    deepseek-v4-flash-0731). `settings` may override max_input_tokens,
    max_output_tokens, reasoning_effort and timeout_seconds.
    `declared_pricing` is the miner's own statement of price for a model with
    no listed price; a listed price is never overridden.
    """
    adapter = ADAPTERS.get(provider_id)
    if adapter is None:
        raise ModelSelectionRefused("unknown provider adapter")
    if model_id is None:
        model_id = adapter.default_model
    if type(model_id) is not str or not _MODEL_ID.fullmatch(model_id):
        raise ModelSelectionRefused("a model id is required")
    if adapter.allowed_models is not None and model_id not in adapter.allowed_models:
        raise ModelSelectionRefused("model id not allowed for this provider")
    chosen = dict(DEFAULT_SETTINGS.record())
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
            chosen["max_output_tokens"], 256, 131072, "max_output_tokens"
        ),
        reasoning_effort=chosen["reasoning_effort"],
        timeout_seconds=_int(chosen["timeout_seconds"], 10, 600, "timeout_seconds"),
    )
    listed = adapter.priced_models.get(model_id)
    if listed is not None and declared_pricing is not None:
        raise ModelSelectionRefused("this model's price is listed; do not declare one")
    pricing = (
        listed
        if listed is not None
        else (None if declared_pricing is None else _declared_pricing(declared_pricing))
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
    declared = None
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
    )
    if selection.record() != record:
        raise ModelSelectionRefused("provider record does not re-validate exactly")
    return selection


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


class ProviderHTTPError(Exception):
    """A provider HTTP rejection reduced to what classification needs.

    Only the status, the provider's machine-readable error code and a bounded
    Retry-After survive; the message text, which can echo request or
    credential material, is discarded here.
    """

    def __init__(self, status, *, code=None, retry_after=None):
        super().__init__("provider HTTP status " + str(status))
        self.status, self.code, self.retry_after = status, code, retry_after


class NotDispatched(ValueError):
    """The request could not be expressed in the provider's protocol and was
    never sent. Safe: nothing was processed, so nothing can have been billed."""


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


def _post(selection, body, opener=None):
    """POST `body` to the selection's endpoint, reading the key here and
    nowhere else. Rejections become `ProviderHTTPError` with no text."""
    adapter, settings = selection.adapter, selection.settings
    headers = {"Content-Type": "application/json"}
    if adapter.protocol == MESSAGES:
        headers["anthropic-version"] = ANTHROPIC_VERSION
    if adapter.auth == "x-api-key":
        headers["x-api-key"] = read_credential(selection.credential)
    else:
        headers["Authorization"] = "Bearer " + read_credential(selection.credential)
    outgoing = urllib.request.Request(
        selection.endpoint, data=body, headers=headers, method="POST"
    )
    del headers
    opener = opener or urllib.request.build_opener(_NoRedirect())
    limit = settings.max_response_bytes
    try:
        with opener.open(outgoing, timeout=settings.timeout_seconds) as response:
            payload = response.read(limit + 1)
    except urllib.error.HTTPError as rejected:
        code = None
        try:
            parsed = json.loads(rejected.read(64 * 1024))
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
            rejected.code, code=code, retry_after=retry_after
        ) from None
    finally:
        del outgoing
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


def chat_request(request):
    """Translate the loop's Responses-shaped request into Chat Completions.

    The loop keeps one history format; this adapter maps it onto chat
    messages. Reasoning items and the reasoning setting have no portable chat
    equivalent and are not sent; `store` is a Responses-only field.
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
            messages.append(
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": item["call_id"],
                            "type": "function",
                            "function": {
                                "name": item["name"],
                                "arguments": item["arguments"],
                            },
                        }
                    ],
                }
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
    reads: one message item and/or function_call items, and token usage."""
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
    return {
        "model": response.get("model"),
        "status": (
            "completed"
            if choice.get("finish_reason") in ("stop", "tool_calls")
            else "incomplete"
        ),
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
    provider adds it.
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
        read = _count(usage.get("cache_read_input_tokens")) or 0
        written = _count(usage.get("cache_creation_input_tokens")) or 0
        translated = {
            "input_tokens": None if fresh is None else fresh + read + written,
            "output_tokens": usage.get("output_tokens"),
            "input_tokens_details": {
                "cached_tokens": read,
                "cache_creation_tokens": written,
            },
        }
        details = usage.get("output_tokens_details")
        reasoning = (
            details.get("reasoning_tokens")
            if type(details) is dict
            else usage.get("reasoning_tokens")
        )
        if reasoning is not None:
            translated["output_tokens_details"] = {"reasoning_tokens": reasoning}
    return {
        "model": response.get("model"),
        "status": (
            "completed"
            if response.get("stop_reason") in ("end_turn", "tool_use", "stop_sequence")
            else "incomplete"
        ),
        "output": output,
        "usage": translated,
        "provider_protocol": MESSAGES,
        "provider_stop_reason": response.get("stop_reason"),
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
    before anything is sent, and anything else propagates unchanged,
    classifying as UNKNOWN. `opener` replaces urllib's for fixture tests only.
    """

    def __init__(self, selection: ModelSelection, *, opener=None):
        if type(selection) is not ModelSelection:
            raise ModelSelectionRefused("a validated ModelSelection is required")
        self.selection, self.opener = selection, opener

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
        response = _post(self.selection, canonical(body), self.opener)
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
