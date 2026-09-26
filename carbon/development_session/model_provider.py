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
  a fixed or miner-supplied endpoint, the models it knows prices for, its
  credential requirement and how its errors are read;
* the **model id**: any id the miner names; a listed model carries a sourced
  price, any other has an unknown price unless the miner declares one;
* the **model settings**: token ceilings, reasoning effort, timeout;
* the **credential reference**: a local file path or an environment variable
  name. Never the key. Nothing here reads a key except a transport, at dispatch.

A campaign's choice is a `ModelSelection`, which only `select()` builds, so an
unvalidated combination cannot reach a transport. The one combination every
existing campaign was pinned to - OpenAI Responses with
`gpt-5-mini-2025-08-07` - is `DEFAULT_SELECTION`, and its manifest record is
byte-identical to the block those manifests carry.

**Cost.** Where the price is known (listed with its source and observation
date, or declared by the miner with theirs), each request reserves its maximum
possible cost before dispatch - the whole admitted context at the uncached
price plus the whole output ceiling - and settles to the metered usage. Where
the price is unknown, no maximum is calculable: Carbon says so, reserves and
meters no money for that selection, records token usage only, and refuses to
pair it with a miner spend limit in money, which it could not enforce. Prices
are never invented.

Replies other than a completed response are classified into
`ProviderOutcome`; see `research_agent` for which are retried and how.
"""

from __future__ import annotations

import enum
import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

SELECTION_SCHEMA = "carbon.model-selection.v1"
PROVIDER_SUMMARY = "carbon.model-provider-summary.v1"

RESPONSES = "openai.responses.v1"
CHAT_COMPLETIONS = "openai.chat-completions.v1"

UNKNOWN_SPEND = (
    "unknown: no price is known or declared for this model, so no maximum cost "
    "per request is calculable. Carbon reserves and meters no money for it and "
    "records token usage only; limit spend at your provider."
)


@dataclass(frozen=True)
class Pricing:
    """USD per token in integer nanodollars, and where the numbers came from.

    `source` is `provider_published` for a listed model or `miner_declared`
    for a price the miner states; there is no third, guessed kind.
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
    """Where the miner's own key is: a file path or an environment variable
    name. Never the key itself."""

    kind: str
    reference: str

    def record(self):
        # A path is local layout and is supplied again at run time; only an
        # environment variable's *name* is recorded.
        return {
            "kind": self.kind,
            "reference": self.reference if self.kind == "env" else None,
        }


@dataclass(frozen=True)
class ErrorSemantics:
    """What this provider's HTTP rejections mean for money and retry.

    `unbilled_rejections` are statuses returned before any generation with no
    usage object; the attempt is counted and no token charge recorded. Every
    other failure - a 5xx, a timeout, a dropped connection, an unreadable body
    - keeps its full reservation, because the request may have been processed.
    """

    unbilled_rejections: tuple[int, ...]
    quota_codes: tuple[str, ...]
    context_codes: tuple[str, ...]
    basis: str


OPENAI_ERRORS = ErrorSemantics(
    unbilled_rejections=(400, 401, 403, 404, 409, 413, 422, 429),
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


@dataclass(frozen=True)
class ProviderAdapter:
    adapter_id: str
    display_name: str
    protocol: str
    #: None: the miner supplies the endpoint (an OpenAI-compatible service).
    endpoint: str | None
    #: Models with a provider-published price, by id.
    priced_models: dict = field(default_factory=dict)
    default_env: str | None = None
    errors: ErrorSemantics = OPENAI_ERRORS

    def summary_models(self):
        return [
            {"model_id": model, "pricing": pricing.record()}
            for model, pricing in sorted(self.priced_models.items())
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

ADAPTERS = {
    adapter.adapter_id: adapter
    for adapter in (
        ProviderAdapter(
            adapter_id="openai-responses",
            display_name="OpenAI Responses API",
            protocol=RESPONSES,
            endpoint="https://api.openai.com/v1/responses",
            priced_models={GPT5_MINI: GPT5_MINI_PRICING},
            default_env="OPENAI_API_KEY",
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
_ENV_NAME = re.compile(r"[A-Z_][A-Z0-9_]{0,63}")
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
                else "reserved per request before dispatch from "
                + self.pricing.source
                + " pricing; settled to metered usage"
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
    kind, reference = value["kind"], value["reference"]
    if kind == "file":
        if type(reference) is not str or not 1 <= len(reference) <= 4096:
            raise ModelSelectionRefused("a credential file path is required")
    elif kind == "env":
        if type(reference) is not str or not _ENV_NAME.fullmatch(reference):
            raise ModelSelectionRefused("an environment variable name is required")
    else:
        raise ModelSelectionRefused("credential kind is file or env")
    return CredentialReference(kind, reference)


def select(
    *,
    provider_id,
    model_id,
    credential,
    endpoint=None,
    settings=None,
    declared_pricing=None,
):
    """Validate a miner's choice into a `ModelSelection`.

    `credential` is {"kind": "file"|"env", "reference": path or variable name}.
    `settings` may override max_input_tokens, max_output_tokens,
    reasoning_effort and timeout_seconds. `declared_pricing` is the miner's own
    statement of price for a model with no listed price; a listed price is
    never overridden.
    """
    adapter = ADAPTERS.get(provider_id)
    if adapter is None:
        raise ModelSelectionRefused("unknown provider adapter")
    if type(model_id) is not str or not _MODEL_ID.fullmatch(model_id):
        raise ModelSelectionRefused("a model id is required")
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
    re-validated through `select()`; a file credential's path is not recorded,
    so it is supplied again at run time.
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
    credential = record.get("credential") or {}
    reference = (
        credential.get("reference")
        if credential.get("kind") == "env"
        else (None if credential_file is None else str(credential_file))
    )
    if reference is None:
        raise ModelSelectionRefused("the credential file must be supplied again")
    adapter = ADAPTERS.get(record.get("provider_id"))
    selection = select(
        provider_id=record.get("provider_id"),
        model_id=record.get("model"),
        credential={"kind": credential.get("kind"), "reference": reference},
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


def _credential_state(reference, environ):
    """Whether a credential is configured, from metadata alone; never read."""
    if reference is None:
        return "credential_not_configured"
    if reference.kind == "env":
        return None if environ.get(reference.reference) else "credential_not_configured"
    path = Path(reference.reference)
    try:
        if path.is_symlink() or not path.is_file():
            return "credential_not_configured"
        size = path.stat().st_size
    except OSError:
        return "credential_not_configured"
    return None if 0 < size <= 1024 else "credential_file_unusable"


def provider_summary(credentials=None, *, environ=None):
    """Every provider adapter, its listed models and prices, and whether the
    miner has a credential configured for it.

    `credentials` maps adapter id to {"kind": "file"|"env", "reference": ...}.
    An adapter with a default environment variable (OPENAI_API_KEY for OpenAI)
    counts as configured when that variable is set. Availability is judged
    from file metadata or variable presence only: no key is read and no
    provider is contacted, so `available` means a credential is configured, not
    that the provider accepts it.
    """
    environ = os.environ if environ is None else environ
    credentials = credentials or {}
    rows = []
    for adapter in ADAPTERS.values():
        given = credentials.get(adapter.adapter_id)
        reference = (
            _credential(given)
            if given is not None
            else (
                CredentialReference("env", adapter.default_env)
                if adapter.default_env
                else None
            )
        )
        reason = _credential_state(reference, environ)
        rows.append(
            {
                "schema": PROVIDER_SUMMARY,
                "provider_id": adapter.adapter_id,
                "display_name": adapter.display_name,
                "protocol": adapter.protocol,
                "endpoint": adapter.endpoint,
                "endpoint_required": adapter.endpoint is None,
                "listed_models": adapter.summary_models(),
                "model_policy": (
                    "Name any model id. A listed model carries its sourced price; "
                    "any other has an unknown price unless you declare one."
                ),
                "spend_bound_for_unlisted_models": UNKNOWN_SPEND,
                "credential": {
                    "kinds": ["file", "env"],
                    "default_env": adapter.default_env,
                    "owner": "the miner; Carbon never issues or holds a provider key",
                },
                "default_settings": DEFAULT_SETTINGS.record(),
                "available": reason is None,
                "reason": reason,
                "availability_basis": (
                    "credential file metadata or environment variable presence "
                    "only; no key was read and no provider was contacted"
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
    if type(error) is not ProviderHTTPError:
        return ProviderFailure(ProviderOutcome.UNKNOWN, None, None, None, False, False)
    status, code = error.status, _code(error.code)
    unbilled = status in errors.unbilled_rejections
    retry_after = _retry_after(error.retry_after)
    if status == 429 and code not in errors.quota_codes:
        return ProviderFailure(
            ProviderOutcome.RATE_LIMITED, status, code, retry_after, unbilled, unbilled
        )
    if status == 429:
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


def read_credential(reference: CredentialReference, environ=None):
    """The key, read only at dispatch by a transport."""
    if reference.kind == "env":
        key = (os.environ if environ is None else environ).get(reference.reference)
        if not key:
            raise ValueError("credential environment variable is not set")
        key = key.strip()
    else:
        path = Path(reference.reference)
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 1024:
            raise ValueError("operator API credential file required")
        key = path.read_text().strip()
    if not key or "\n" in key or "\r" in key:
        raise ValueError("invalid API credential")
    return key


def _post(endpoint, body, key, timeout, limit, opener=None):
    outgoing = urllib.request.Request(
        endpoint,
        data=body,
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
        method="POST",
    )

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    opener = opener or urllib.request.build_opener(NoRedirect())
    try:
        with opener.open(outgoing, timeout=timeout) as response:
            payload = response.read(limit + 1)
    except urllib.error.HTTPError as rejected:
        code = None
        try:
            parsed = json.loads(rejected.read(64 * 1024))
            error = parsed.get("error") if type(parsed) is dict else None
            code = error.get("code") if type(error) is dict else None
        except Exception:  # noqa: BLE001 - an unreadable body has no code
            code = None
        headers = rejected.headers
        raise ProviderHTTPError(
            rejected.code,
            code=code,
            retry_after=None if headers is None else headers.get("Retry-After"),
        ) from None
    if len(payload) > limit:
        raise ValueError("provider response exceeds bound")
    return json.loads(payload)


def _responses_body(request):
    """The Responses request as sent: a null reasoning setting is omitted."""
    return {k: v for k, v in request.items() if not (k == "reasoning" and v is None)}


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
            text = "".join(
                part.get("text", "")
                for part in item.get("content") or []
                if type(part) is dict and part.get("type") == "output_text"
            )
            messages.append({"role": item.get("role", "assistant"), "content": text})
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
            raise ValueError("history item has no chat translation")
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
    }


class SelectionTransport:
    """POST one closed request to the selected provider.

    No redirect is followed and nothing is retried here; a rejection is raised
    as `ProviderHTTPError` and anything else propagates unchanged, classifying
    as UNKNOWN. `opener` replaces urllib's for fixture tests only.
    """

    def __init__(self, selection: ModelSelection, *, opener=None, environ=None):
        if type(selection) is not ModelSelection:
            raise ModelSelectionRefused("a validated ModelSelection is required")
        self.selection, self.opener, self.environ = selection, opener, environ

    def __call__(self, request: dict[str, object]):
        from .profile import canonical

        s = self.selection
        key = read_credential(s.credential, self.environ)
        chat = s.adapter.protocol == CHAT_COMPLETIONS
        body = chat_request(request) if chat else _responses_body(request)
        response = _post(
            s.endpoint,
            canonical(body),
            key,
            s.settings.timeout_seconds,
            s.settings.max_response_bytes,
            self.opener,
        )
        return chat_response(response) if chat else response


class ProviderTransport(SelectionTransport):
    """The historical pinned OpenAI Responses selection, reading its key from
    the operator's credential file - the signature every caller already uses."""

    def __init__(self, credential_file: Path):
        super().__init__(_default(credential_file))
        self.credential_file = credential_file
