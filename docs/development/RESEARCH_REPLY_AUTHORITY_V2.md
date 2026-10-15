# Prospective research reply authority (PLT-19)

Newly frozen battery and generic campaign provider plans record
`research_reply: carbon.autoresearch.research-reply.v2`. Plans without that field
retain their original six-field public reply and stored/journal interpretation.
An unknown rule refuses before dispatch; callers cannot select a rule in a tool
request. The twelve-operation nominal `carbon_research_v2` protocol is unchanged.

The versioned wrapper adds `schema` and a short `current_task` before bulk content
(also first under sorted JSON). `current_task` contains state, revision, source,
reply_task_revision and reply_task_role. It is null when the operation returned
no task. The governing source is `terminal_task` when present, otherwise
`reply.result.task`. Despite its historical name, terminal_task may be QUEUED,
RUNNING or CANCEL_REQUESTED for native asynchronous start/observation. The source
names the observation returned by this call; it does not promise an uncached
live query. Existing poll_sequence replay semantics stay intact.

`reply_task_role: RETAINED_PROTOCOL_OBSERVATION` explains why the nested protocol
receipt may show a different revision/state. Its bytes are not overwritten. For
example, a QUEUED revision0 receipt and SUCCEEDED revision2 observation produce
`current_task.state=SUCCEEDED`, revision2, source terminal_task and
reply_task_revision0. State is task progress, not accounting: independently read
requires_reconciliation, including FAILED_INFRA with a reserved ledger operation.

Both views must bind the same public task identity, Challenge, creation time and
immutable bindings. A backwards revision or disagreeing same-revision views
refuse. The object adapter requires the campaign-selected wrapper and checks the
summary against its actual views before bounded truncation; status remains short
and uncut while bulk content retains the existing explicit truncation record.
Pre-dispatch refusals and unavailable operations keep their existing closed
shapes and registered field corrections. No new private fields are projected.

Migration is prospective: old campaign manifests, original start receipts,
durable task histories, poll cursors, journals and nominal protocol encodings are
not rewritten. New synchronous SDK and object/native task surfaces consume the
same selected wrapper. Native observe/cancel retains original operation identity.
This is software coherence only, not scientific/security/production qualification.
