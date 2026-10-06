## 2026-10-06 — GRAPHITE-SPUR-PROVIDER-01: SPUR Compute as Graphite's second model provider

**Authority:** the owner's direction of 2026-10-06, relayed by the Test Lead:
"go, queue the model connector" for SPUR Compute (https://ai.spuric.com), an
OpenAI-compatible `/v1` endpoint serving GLM-5.2, DeepSeek V4, Qwen and
Llama models. Owner clarification the same day: SPUR is only for Carbon's
own Graphite testing, on the owner's credits; it is never offered to miners.
Credits are unconfirmed. No value is chosen here: no rate, no context window,
no ladder order and no grant amount.

**Base:** `origin/main`, branch `claude/spur-model-provider`.

### SPUR-D1 — A Graphite-only provider registry

`carbon/agent_campaign/graphite/model_providers.py` registers the inference
providers a Graphite run may pay: `engy` (the default) and `spur`. Each is a
`GraphiteModelProvider` with the same parts: adapters, a rate table
(`Pricing`, sourced and dated), a ladder (the rate table's order, as
`ENGY_LADDER` is `ENGY_MODELS`' order), recorded context windows, the
expected key file and typed refusals. SPUR's adapter (`spur-chat`, OpenAI
Chat Completions at `https://ai.spuric.com/v1/chat/completions`, bearer key)
lives only there. `model_provider.ADAPTERS`, which the Launchpad, miner
setup and every miner-facing provider list read, is unchanged byte for
byte; a miner launch naming `spur` or `spur-chat` is refused as an unknown
provider. Pinned by `test_graphite_spur_provider.py`.

### SPUR-D2 — One path for both providers (owner's consistency rule)

Shared, not duplicated: `model_provider.select` and `selection_from_record`
take an optional adapter registry (default `ADAPTERS`, so every miner caller
is unchanged); `research_agent.settled_charge` reads a new adapter field,
`unreported_charge`; `ladder.Ladder` takes its provider's models; roles'
whole-context settings are built by `roles.model_settings_for` from a
provider's own contexts; `LiveModel` admits a selection through the
provider's `admission_refusal`; `GraphiteProvider` takes `model_provider`.
Reservation, settlement, admission, the call deadline and
`SelectionTransport` are the same code for both. The tests run the same
assertions for Engy and SPUR.

### SPUR-D3 — Identity

A model is recorded as provider and model: `spur:glm-5.2`. Same-name models
from different providers are separate run conditions: separate adapters,
rates, contexts (SPUR's `glm-5.2` never takes Engy's 262,144 tokens), ladder
stores (`ladder-spur`) and selection records. A new SPUR session records
`model_provider` (`carbon.graphite.model-provider.v1`: provider and
identity); an Engy session records nothing new, so every recorded session
keeps its bytes. A session resumes only on the provider that opened it
(`model_provider_changed`).

### SPUR-D4 — Pricing: an empty table, fail closed

The Test Engineer checked SPUR's site on 2026-10-06: `/pricing` and `/models`
load text-model rates dynamically and `/v1/models` answers 401, so no
per-token rate was readable. `SPUR_RATES` and `SPUR_CONTEXT_TOKENS` ship
empty. A model with no recorded rate is refused `spur_rate_unrecorded`
before any reservation or call. No charge report is documented, so a SPUR
call books its full reservation (`unreported_charge="reservation"`), as an
Engy call whose report is missing does; never the headline estimate. When
SPUR documents a charge report, it is recorded like a rate.

To record a rate later, the owner adds one `SPUR_RATES` entry per model, in
ladder order (cheapest first), through `_spur_rate(input_nano, output_nano,
cached_nano, source_url, observed, note)`: the model id as SPUR's API names
it, the input, output and cached-input rates in nanodollars per token (USD
per million x 1000), the source URL and the observed date; and the model's
context window in `SPUR_CONTEXT_TOKENS`.

### SPUR-D5 — Spend: the grant names its provider

The grant format names its campaign provider (`graphite`), not the inference
provider it pays, so the binding is registered beside the Challenge binding:
`grant_binding.MODEL_PROVIDER_GRANTS`, empty. An unlisted grant pays Engy
(every grant approved so far). A SPUR run refuses any grant that does not
name SPUR, and an Engy run any grant bound elsewhere:
`grant_does_not_name_the_model_provider`, before any key, pod, reservation
or call. No grant file is written; the owner approves amounts later.

### SPUR-D6 — Key custody

By file path only: `~/.config/carbon/spur-api-key`, a regular file the
operator owns, mode 0600, checked by `phase4.owner_only_file` (the Engy
key's rule). The phase-3 runner takes `--model-provider spur` with
`--credential-file` only (`model_provider_key_by_file_only` otherwise).
The key is read only inside the transport at the point of use and never
printed, logged or stored; no agent sees or asks for it.

### SPUR-D7 — Ladder and runs

A run picks its provider explicitly (`--model-provider`, default `engy`, on
`phase3 run`; `model_provider=` on `GraphiteProvider` and `LiveModel`). Engy's
ladder, R3, R4 and every recorded session are unchanged; a role starts on
the rung holding its own start model, which on Engy's ladder is exactly
`RoleSpec.start_rung`. Phase 4 and the level planner stay Engy-only until a
grant binds SPUR.

### Follow-up (owner)

1. Record SPUR rates and contexts with sources and dates.
2. Approve a SPUR grant and bind it in `MODEL_PROVIDER_GRANTS`.
3. A first keyed call verifies the chat path and SPUR's error semantics.

Maturity: implemented and tested with stub transports only. No live call,
no security acceptance.
