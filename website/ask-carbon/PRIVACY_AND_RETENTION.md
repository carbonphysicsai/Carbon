# Ask Carbon privacy and retention map

**Status:** proposed for staging review; not an accepted public privacy policy.

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
| Worker request | question, request ID, origin, network address | Validates size/schema and retrieves public passages; sends only current question and passages to OpenAI | Raw visitor text is not intentionally logged or placed in telemetry; platform-level logs need target verification |
| Abuse counter | HMAC-style SHA-256 of secret plus IP | Stable pseudonymous client key for hourly/concurrency control | Default example retains inactive client counters for 24 hours; this is pseudonymous, not anonymous |
| Budget ledger | attempt/request IDs, pseudonymous client ID, environment, month, model/pricing IDs, state and micro-USD exposure | No question or answer text | Retained durably for financial reconciliation; unresolved exposure cannot expire away. Final operational retention/deletion policy needs owner/security acceptance |
| OpenAI Responses API | current question, bounded reviewed passages, generated answer, usage metadata | `store:false`; no tools, URLs or prior transcript | OpenAI documentation says default abuse-monitoring logs may be retained up to 30 days. Zero Data Retention/Modified Abuse Monitoring require eligibility and approval; `store:false` alone is not zero retention. Actual project settings were not accessible in this delivery |
| Static/cache | approved manifest, component assets, citations | No visitor text | Release expiry/withdrawal and withdrawal epoch invalidate content; hosting cache purge must be tested in the actual target |
| Metrics | status, latency, request ID and aggregate usage only | Planned; raw transcript analytics and provider data sharing are off by policy | Exact hosting telemetry and retention need target verification |
| Feedback | none | No collection endpoint | Disabled unless separately designed and approved |

General chat never accepts files or confidential project intake. The future
authenticated Research Concierge is a separate system and gains no authority or
data path from this component.
