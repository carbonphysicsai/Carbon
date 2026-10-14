# Graphite argument events (PLT-14)

New sessions freeze `argument_logging: carbon.graphite.argument-events.v1` and
`agent_identity`: the Graphite implementation, registered role, actual model,
inference provider and live/scripted mode. The opening event repeats that identity.
Changing or removing its logging identity refuses the run before a model call.
This describes the selected agent/model; it grants no inference or spending right.

The loop's optional trusted observer runs for every function call in a retained
model response, before validation/dispatch. It includes engine selections,
compaction replies, malformed or truncated calls, parallel refusals and calls
not run after a terminal result. It receives immutable name/JSON primitives,
not the mutable call used for dispatch. Other loop callers default to no observer;
prompts, requests, budgets and historical epoch-plan bytes are unchanged.

Each `call_arguments` event has an engine-generated identity, owning `run_id`,
public tool name (or `UNKNOWN_TOOL`), an argument snapshot and its digest. The
same projection is attached to ordinary `tool_answered`/`tool_refused` events.
Successful calls no longer omit arguments, and refusals no longer retain raw
arguments. Unknown result-status text is redacted. A replay emits no duplicate;
conflicting public argument projections at the same identity refuse the run.

The snapshot contains `schema`, `shape`, `fields` and `unknown_fields`. Its shape
describes an object, empty argument spelling, or malformed/unrepresentable input;
it is not a declaration that the tool request was valid. Unknown field names
are never copied. Field counts and redaction markers report what was omitted.

The positive projection retains public `kind`/workspace `action` selectors,
`used_feedback` Booleans, and bounded integer `seconds`, `count`, `offset` and
`limit`. Limits are telemetry representation bounds, not compute permissions or
scientific thresholds. It decodes one `arguments_json` layer. A `public_material`
request may retain its registered material category; file/task/card names and
paths remain redacted. Free text, source code, strategies, files, reasons,
summaries, unknown fields and malformed JSON have no raw-string fallback.
Named protected material redacts the whole object. Digests bind only the
redacted snapshot; they are never raw-input or canary-token hashes.

An optional logging-only structured `expected_effect` JSON object may retain
`metric` (`score`, `latency_seconds`, `memory_bytes`, `error`), `direction`
(`increase`, `decrease`, `unchanged`) and one finite bounded `target` or `delta`.
Plain-text forecasts remain redacted. A record's presence is not numerical
forecast evidence, successful execution, scientific comparison or qualification.

The controller still matches exactly its configured canaries. For a redacted
refusal, the provider's Boolean `event_canary_hit` checks the refused call's
already-retained private intent. It creates no private archive and returns no
token, token digest, input or path. Missing, malformed, ambiguous, symlinked or
cross-run evidence is unavailable and fails closed, rather than meaning no
exposure. The existing finding/stop ordering and other providers' scans remain.

Historical logs/intents are not rewritten, scrubbed or backfilled. A historical
session without the new policy keeps its old plan and has no complete engine-call
coverage claim. Existing operator-private journals may still contain raw data;
this feature does not qualify their storage or claim hostile-Python isolation.

Tests use scripted models, public protocol metadata and synthetic tripwires.
No real protected material, host execution, training, spend or LIVE operation is
part of this implementation. Graphite Testing Manager reviews test discrimination;
Carbon Validator reviews disclosure. Owner security acceptance remains separate.
