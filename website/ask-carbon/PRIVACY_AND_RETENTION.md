# Ask Carbon privacy and retention map

**Status:** owner-approved visitor privacy posture for the bounded release
candidate. This approval covers public Q&A and local/AI-guided pilot drafting;
it does not authorize inquiry collection, confidential/customer-data
processing, provider-retention overstatement, production activation, or a
security qualification.

## Exact visitor notice

Notice version `ask-carbon-notice-v2-2026-09-26` (supersedes the OpenAI-era
notice, SHA-256 `f98d0302…`, approved under WEB-QA-08-D1).

> Ask Carbon answers from reviewed public Carbon sources. Live answers are on
> by default: Carbon's server sends your current question and the matching
> reviewed passages to Chutes, which runs the model inside hardware-isolated
> confidential computing. Chutes states that it does not log, store or train on
> request or response content, and keeps only usage metadata such as token
> counts for billing. You can switch to saved explanations, which send nothing
> to any AI provider.
>
> Pilot guidance stays off until you enable it in the Pilot Designer.
>
> Do not include confidential engineering, customer, personal, credential,
> export-controlled or protected-evaluation information.
>
> The reviewed-draft download saves an unencrypted local file. The encrypted
> download seals the same draft in your browser to Carbon's intake key. Neither
> download submits an inquiry, promises staff follow-up, qualifies a model,
> approves a Challenge or authorizes scientific work.

**Basis, verified 2026-09-26.** `GET https://llm.chutes.ai/v1/models` lists the
configured model `google/gemma-4-31B-turbo-TEE` with `confidential_compute:
true`. The Chutes privacy policy (<https://chutes.ai/privacy>, last updated
2026-03-16) states: "We do not log, store, or persist the content of your API
requests or responses"; content "is never written to a database, log file, or
other persistent storage"; it "is not used for model training"; the
confidential models "run inside trusted execution environments backed by Intel
TDX and NVIDIA Protected PCIe", where "the Chutes API relays ciphertext to the
target instance and cannot decrypt"; and usage metadata (timestamps, durations,
token counts, model identifiers, stop reasons) "is retained for billing,
accounting, and support." These are the provider's statements. Carbon has not
independently audited the attestation chain, which is why the notice says
"Chutes states".

**What the notice deliberately does not say.** It does not repeat the Pilot
Designer's own disclosure: that page carries its own notice, owned by the
client-intake lane, and it must name the same provider before this candidate
is published (see `PUBLIC_RELEASE_CANDIDATE.json`,
`required_before_production_mutation`).

## Processing and retention

| Surface | Data | Current behavior | Retention/control |
| --- | --- | --- | --- |
| Browser saved mode | question and selected card | Used in page memory only; no AI request | Cleared on new chat, close/navigation or page lifecycle; no Web Storage/cookie |
| Browser live mode | question and opaque continuation | On by default for Q&A when the Worker reports active health; the visitor can switch to saved explanations. Sent only to same-origin Worker | Continuation stays in memory; signed, source-versioned, withdrawal-bound, 15-minute expiry; contains card IDs, not visitor text or prior answers |
| Browser pilot-design mode | high-level draft brief, pilot outline except its operating envelope and requested targets, unresolved assumptions and up to ten explicitly included conversation turns | Sent only after the visitor enables AI guidance; local form-only drafting remains available | Held in page memory. Abandoned raw conversation is not persisted by this implementation; optional inclusion in a locally exported review package is off by default |
| Worker request | question, request ID, origin, network address | Validates size/schema and retrieves public passages; sends only current question and passages to Chutes | Raw visitor text is not intentionally logged or placed in telemetry; platform-level logs need target verification |
| Worker pilot-design request | schema-bounded draft context, prior turns, retrieved public passages and pseudonymous session ID | Treats visitor fields as untrusted context; returns proposed edits requiring explicit client acceptance | No raw visitor text enters the budget ledger or intentional telemetry. Hosting logs and any future inquiry receiver need separate target verification |
| Abuse counter | HMAC-style SHA-256 of secret plus IP | Stable pseudonymous client key for hourly/concurrency control | Default example retains inactive client counters for 24 hours; this is pseudonymous, not anonymous |
| Budget ledger | attempt/request IDs, pseudonymous client ID, environment, month, model/pricing IDs, state and micro-USD exposure | No question or answer text | Retained durably for financial reconciliation; unresolved exposure cannot expire away. Final operational retention/deletion policy needs owner/security acceptance |
| Chutes chat completions (`google/gemma-4-31B-turbo-TEE`) | current question, bounded reviewed passages, generated selection, usage metadata | No tools or model-selected URLs; strict JSON-schema output; pilot mode may include up to ten disclosed conversation turns | Provider statement (chutes.ai/privacy, 2026-03-16): content is not logged, stored, persisted or used for training; the model runs in a TEE (Intel TDX, NVIDIA Protected PCIe) and the API relays ciphertext; usage metadata is retained for billing. Not independently audited by Carbon. Does not authorize customer-data processing. |
| OpenAI Responses API (retired for production 2026-09-26) | — | Retained only for the historical `gpt-5.6-*` evaluation profiles | Historical: `store:false`, no Zero Data Retention or Modified Abuse Monitoring; prompts and responses potentially retained up to 30 days. Applies to evidence gathered before this candidate. |
| Static/cache | approved manifest, component assets, citations | No visitor text | Release expiry/withdrawal and withdrawal epoch invalidate content; hosting cache purge must be tested in the actual target |
| Metrics | status, latency, request ID and aggregate usage only | Evaluation telemetry is staging-only; raw transcript analytics and provider data sharing are off by policy | Production candidate disables evaluation telemetry; Cloudflare platform logging remains an operator verification item |
| Feedback | none | No collection endpoint | Disabled unless separately designed and approved |

General chat never accepts files or confidential project intake. The future
authenticated Research Concierge is a separate system and gains no authority or
data path from this component.

The combined proposed notice and exact activation decisions are in
`PUBLIC_RELEASE_DECISION_PACKET.md`. Inquiry submission remains unavailable;
local export is not receipt, persistence, or staff notification.
