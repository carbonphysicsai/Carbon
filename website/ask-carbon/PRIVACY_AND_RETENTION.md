# Ask Carbon privacy and retention map

**Status:** proposed public-release input; not an accepted public privacy
policy. The owner approved the bounded private guidance-quality packet, not
this notice, provider-processing posture, public collection, or security.

## Exact visitor notice

> Ask Carbon uses reviewed public Carbon sources. Live questions, a pseudonymous
> abuse-control identifier and bounded technical metadata may be processed by
> Carbon's hosting and AI providers. Do not include confidential engineering,
> customer, personal, credential, model, solver or protected-evaluation data.
> Saved explanations stay in your browser and are clearly labelled. Live
> answers can be unavailable when evidence, privacy, safety or budget gates are
> not satisfied.

The owner must accept or replace those exact words before public live answers.

## Processing and retention

| Surface | Data | Current behavior | Retention/control |
| --- | --- | --- | --- |
| Browser saved mode | question and selected card | Used in page memory only; no AI request | Cleared on new chat, close/navigation or page lifecycle; no Web Storage/cookie |
| Browser live mode | question and opaque continuation | Sent only to same-origin Worker | Continuation stays in memory; signed, source-versioned, withdrawal-bound, 15-minute expiry; contains card IDs, not visitor text or prior answers |
| Browser pilot-design mode | high-level draft brief, pilot outline, unresolved assumptions and up to ten explicitly included conversation turns | Sent only after the visitor enables AI guidance; local form-only drafting remains available | Held in page memory. Abandoned raw conversation is not persisted by this implementation; optional inclusion in a locally exported review package is off by default |
| Worker request | question, request ID, origin, network address | Validates size/schema and retrieves public passages; sends only current question and passages to OpenAI | Raw visitor text is not intentionally logged or placed in telemetry; platform-level logs need target verification |
| Worker pilot-design request | schema-bounded draft context, prior turns, retrieved public passages and pseudonymous session ID | Treats visitor fields as untrusted context; returns proposed edits requiring explicit client acceptance | No raw visitor text enters the budget ledger or intentional telemetry. Hosting logs and any future inquiry receiver need separate target verification |
| Abuse counter | HMAC-style SHA-256 of secret plus IP | Stable pseudonymous client key for hourly/concurrency control | Default example retains inactive client counters for 24 hours; this is pseudonymous, not anonymous |
| Budget ledger | attempt/request IDs, pseudonymous client ID, environment, month, model/pricing IDs, state and micro-USD exposure | No question or answer text | Retained durably for financial reconciliation; unresolved exposure cannot expire away. Final operational retention/deletion policy needs owner/security acceptance |
| OpenAI Responses API | current question, bounded reviewed passages, generated answer, usage metadata | `store:false`; no tools or model-selected URLs; pilot mode may include up to ten disclosed conversation turns | The private synthetic staging project showed API call logging enabled per call. No approved Zero Data Retention/Modified Abuse Monitoring control was established, so treat prompts and responses as potentially retained up to 30 days under default abuse monitoring. This observation does not authorize customer-data processing. |
| Static/cache | approved manifest, component assets, citations | No visitor text | Release expiry/withdrawal and withdrawal epoch invalidate content; hosting cache purge must be tested in the actual target |
| Metrics | status, latency, request ID and aggregate usage only | Planned; raw transcript analytics and provider data sharing are off by policy | Exact hosting telemetry and retention need target verification |
| Feedback | none | No collection endpoint | Disabled unless separately designed and approved |

General chat never accepts files or confidential project intake. The future
authenticated Research Concierge is a separate system and gains no authority or
data path from this component.

The combined proposed notice and exact activation decisions are in
`PUBLIC_RELEASE_DECISION_PACKET.md`. Inquiry submission remains unavailable;
local export is not receipt, persistence, or staff notification.
