"""The inference providers Carbon's own Graphite sessions may pay, by name.

Graphite-only (owner, 2026-10-06): this registry is Carbon's development
path, on the owner's credits. No miner surface reads it. The Launchpad, miner
setup and every miner-facing provider list read `model_provider.ADAPTERS`,
which this module never changes; a miner launch naming SPUR is refused there
as an unknown provider.

Each `GraphiteModelProvider` carries the same parts, so every provider runs
through one path (GRAPHITE-SPUR-PROVIDER-01, the owner's consistency rule):
its adapters, its rate table (`Pricing`, sourced and dated, never guessed),
its ladder (the rate table's order, cheapest first, as `ENGY_LADDER` is
`ENGY_MODELS`' order), its recorded context windows, the key file it expects
and its typed refusals. Selection (`select`), reservation and settlement
(`research_agent`), admission (`LiveModel`), the deadline
(`model_provider.call_deadline_seconds`) and the transport
(`model_provider.SelectionTransport`) are shared.

**Identity.** A model is recorded as provider and model together:
`identity("spur", "glm-5.2")` is `spur:glm-5.2`. Engy's `glm-5.2` and SPUR's
`glm-5.2` are separate run conditions: separate adapters, rates, contexts,
ladders and ladder stores, and their selection records differ.

**Engy** is the default and is unchanged: the same adapters, rate table,
ladder, contexts and refusal codes as before, and a session that picks it
records nothing new, so every recorded session keeps its bytes.

**SPUR Compute** (https://ai.spuric.com, observed by the Test Engineer on
2026-10-06): an OpenAI-compatible `/v1` endpoint serving GLM-5.2, DeepSeek
V4, Qwen and Llama models. Its `/pricing` and `/models` pages load text-model
rates dynamically and `/v1/models` answers 401 without a key, so no
per-token rate was readable: `SPUR_RATES` ships EMPTY. A model with no
recorded rate is refused `spur_rate_unrecorded` before any reservation or
call. No charge report is documented, so a SPUR call books its full
reservation (`ProviderAdapter.unreported_charge`). The chat path is the
OpenAI convention under the observed `/v1` base; it is unverified until a
keyed call.

**Recording a SPUR rate (owner).** Add one `SPUR_RATES` entry per model, in
ladder order (cheapest first), with `_spur_rate(input_nano, output_nano,
cached_nano, source_url, observed, note)`: the model id exactly as SPUR's API
names it, the input and output rate (and cached input; the input rate when
SPUR states none) in nanodollars per token (USD per million x 1000), the
source URL the rate was read from and the date it was observed. Add the
model's context window to `SPUR_CONTEXT_TOKENS` the same way (a whole-context
role is refused `model_context_not_recorded` without it). Then bind a grant
to SPUR in `grant_binding.MODEL_PROVIDER_GRANTS`; until a grant names SPUR,
every SPUR run is refused `grant_does_not_name_the_model_provider`.

**SPUR key custody.** By file path only, never an environment variable:
`~/.config/carbon/spur-api-key`, a regular file owned by the operator with
mode 0600 (`phase4.owner_only_file`, the Engy key's rule). Carbon checks its
metadata, reads it only at the point of use inside the transport, and never
prints, logs or stores it. No agent sees or asks for its value.

Nothing here grants or spends anything. Not security acceptance.
"""

from __future__ import annotations

import dataclasses
import types

from carbon.development_session.model_provider import (
    ADAPTERS,
    CHAT_COMPLETIONS,
    ENGY_LADDER,
    ENGY_MODELS,
    OPENAI_ERRORS,
    ErrorSemantics,
    Pricing,
    ProviderAdapter,
)
from carbon.development_session.model_provider import (
    select as select_model,
)

from .roles import ENGY_CONTEXT_TOKENS, model_settings_for

MODEL_PROVIDER_SCHEMA = "carbon.graphite.model-provider.v1"
DEFAULT_MODEL_PROVIDER = "engy"
UNKNOWN_MODEL_PROVIDER = "unknown_model_provider"


def identity(provider, model_id):
    """A model's provider-model identity, for example `spur:glm-5.2`."""
    return f"{provider}:{model_id}"


@dataclasses.dataclass(frozen=True)
class GraphiteModelProvider:
    """One inference provider a Graphite session may pay."""

    name: str
    display_name: str
    #: `{adapter_id: ProviderAdapter}`; the first is the default.
    adapters: types.MappingProxyType
    #: `{model_id: Pricing}`, cheapest first; empty: nothing is callable.
    rates: types.MappingProxyType
    #: `{model_id: context tokens}`, recorded like a rate.
    context_tokens: types.MappingProxyType
    #: Where the operator keeps the key file, for documentation only.
    credential_path: str
    #: The typed refusal of an adapter that is not this provider's.
    adapter_refused: str
    #: The typed refusal of a model with no recorded rate.
    rate_refused: str

    @property
    def ladder(self):
        return tuple(self.rates)

    @property
    def default_adapter(self):
        return next(iter(self.adapters))

    @property
    def is_default(self):
        return self.name == DEFAULT_MODEL_PROVIDER

    @property
    def registry(self):
        """The adapters `select` validates this provider's selections
        against: the miner list plus this provider's own."""
        return types.MappingProxyType({**ADAPTERS, **self.adapters})

    @property
    def ladder_directory(self):
        """The ladder store's directory name under a provider root: Engy's
        historical `ladder`; another provider's rungs are kept apart."""
        return "ladder" if self.is_default else "ladder-" + self.name

    @property
    def model_settings(self):
        """`roles.MODEL_SETTINGS`' table on this provider's contexts."""
        return model_settings_for(self.context_tokens)

    def adapter_refusal(self, adapter_id):
        return None if adapter_id in self.adapters else self.adapter_refused

    def rate_refusal(self, model_id):
        """None when `model_id` has a recorded rate on this provider."""
        return None if model_id in self.rates else self.rate_refused

    def admission_refusal(self, selection):
        """The typed refusal of a live call on `selection`, or None: this
        provider's adapter, a model on its ladder, priced at exactly its
        recorded rate (never a declared or published one)."""
        refused = self.adapter_refusal(selection.provider_id)
        if refused is not None:
            return refused
        if (
            self.rate_refusal(selection.model_id) is not None
            or selection.model_id not in self.ladder
            or selection.pricing is None
            or selection.pricing != self.rates[selection.model_id]
        ):
            return self.rate_refused
        return None

    def select(self, *, adapter_id, model_id, credential_reference, settings=None):
        """A validated selection of `model_id` on this provider. Raises
        `ValueError(code)` with `rate_refused` before anything is built when
        no rate is recorded; `model_provider.ModelSelectionRefused`
        otherwise, as `select` does."""
        refused = self.adapter_refusal(adapter_id) or self.rate_refusal(model_id)
        if refused is not None:
            raise ValueError(refused)
        return select_model(
            provider_id=adapter_id,
            model_id=model_id,
            credential={"kind": "file", "reference": credential_reference},
            settings=settings,
            adapters=self.registry,
        )

    def record(self, model_id):
        """What a session that picked this provider records about it."""
        return {
            "schema": MODEL_PROVIDER_SCHEMA,
            "provider": self.name,
            "identity": identity(self.name, model_id),
        }

    def with_recorded(self, rates, context_tokens):
        """This provider with `rates` and `context_tokens` recorded, its
        adapters' price lists following. For tests' synthetic fixtures; the
        owner records real rates in the tables above."""
        adapters = {
            key: dataclasses.replace(
                adapter, priced_models=dict(rates), allowed_models=tuple(rates)
            )
            for key, adapter in self.adapters.items()
        }
        return dataclasses.replace(
            self,
            adapters=types.MappingProxyType(adapters),
            rates=types.MappingProxyType(dict(rates)),
            context_tokens=types.MappingProxyType(dict(context_tokens)),
        )


# -- Engy (unchanged) ---------------------------------------------------------------------
ENGY = GraphiteModelProvider(
    name="engy",
    display_name="Engy (subnet 53)",
    adapters=types.MappingProxyType(
        {key: ADAPTERS[key] for key in ("engy-anthropic", "engy-chat")}
    ),
    rates=types.MappingProxyType(ENGY_MODELS),
    context_tokens=types.MappingProxyType(ENGY_CONTEXT_TOKENS),
    credential_path="an owner-only file named by --credential-file",
    adapter_refused="engy_adapter_required",
    rate_refused="priced_ladder_model_required",
)
if ENGY.ladder != ENGY_LADDER:  # pragma: no cover - a registry edit
    raise RuntimeError("Engy's ladder is its rate table's order")


# -- SPUR Compute (Graphite only; rates unrecorded) ---------------------------------------
SPUR_BASE_URL = "https://ai.spuric.com/v1"
SPUR_OBSERVED = "2026-10-06"
#: The expected key file (documentation; the runner takes the path given).
SPUR_CREDENTIAL_PATH = "~/.config/carbon/spur-api-key"
SPUR_CREDENTIAL_MODE = 0o600


def _spur_rate(input_nano, output_nano, cached_nano, source_url, observed, note):
    """One recorded SPUR list rate, in Engy's rate-table shape."""
    return Pricing(
        input_nano=input_nano,
        cached_input_nano=cached_nano,
        output_nano=output_nano,
        source="declared_list",
        reference="SPUR published list, " + source_url,
        observed=observed,
        note=note,
    )


#: SPUR's list rates by model id, cheapest first. EMPTY: no rate was readable
#: on 2026-10-06 (module docstring). Never filled with a guess.
SPUR_RATES = {}
#: SPUR's context window by model id. EMPTY for the same reason.
SPUR_CONTEXT_TOKENS = {}
SPUR_ERRORS = ErrorSemantics(
    **{
        **OPENAI_ERRORS.__dict__,
        "basis": OPENAI_ERRORS.basis
        + " SPUR's rate limits and charge reporting are undocumented; these "
        "semantics are the protocol's, not SPUR-verified. No charge report is "
        "read, so each call books its full reservation.",
    }
)
SPUR_ADAPTER = ProviderAdapter(
    adapter_id="spur-chat",
    display_name="SPUR Compute, OpenAI Chat Completions (Graphite only)",
    protocol=CHAT_COMPLETIONS,
    endpoint=SPUR_BASE_URL + "/chat/completions",
    base_url=SPUR_BASE_URL,
    priced_models=SPUR_RATES,
    allowed_models=tuple(SPUR_RATES),
    auth="bearer",
    unreported_charge="reservation",
    errors=SPUR_ERRORS,
)
SPUR = GraphiteModelProvider(
    name="spur",
    display_name="SPUR Compute",
    adapters=types.MappingProxyType({SPUR_ADAPTER.adapter_id: SPUR_ADAPTER}),
    rates=types.MappingProxyType(SPUR_RATES),
    context_tokens=types.MappingProxyType(SPUR_CONTEXT_TOKENS),
    credential_path=SPUR_CREDENTIAL_PATH,
    adapter_refused="spur_adapter_required",
    rate_refused="spur_rate_unrecorded",
)

#: Every provider a Graphite run may pick, by name.
MODEL_PROVIDERS = types.MappingProxyType({p.name: p for p in (ENGY, SPUR)})
#: The registry Graphite resolves a recorded selection against.
GRAPHITE_ADAPTERS = types.MappingProxyType(
    {**ADAPTERS, **{k: a for p in (ENGY, SPUR) for k, a in p.adapters.items()}}
)


def resolve(name):
    """The provider a run picked; `ValueError(UNKNOWN_MODEL_PROVIDER)` for
    any other value."""
    if type(name) is GraphiteModelProvider:
        return name
    if type(name) is not str or name not in MODEL_PROVIDERS:
        raise ValueError(UNKNOWN_MODEL_PROVIDER)
    return MODEL_PROVIDERS[name]
