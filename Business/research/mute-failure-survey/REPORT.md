# RES-14: remaining discarded diagnostics

**DEVELOPMENT STATIC RESEARCH, 2026-10-13.** One ranked document; no runtime
changes. The highest-return work is forwarding diagnostic information Carbon
already constructed, through the last wrapper that loses it. Improving a
message must not alter admission, dispatch, retry, accounting or disclosure
authority.

## Readout and ranking rule

Start with final bundle admission, Launchpad's adapter-error projection, remote
output reconciliation and Graphite's pod-create wrapper. In each, structured
information exists before the refusal reaches its consumer. The caller could
correct a specific field or distinguish a request fault from infrastructure
or reconciliation work instead of repeating the entire flow.

Rank is an engineering recommendation: caller-facing miner/agent paths first;
within that group, later failure after preparation or execution first; then
whether the correction is already available and needs only forwarding. No
invented incident frequency, time saved, money saved or scientific threshold.
The ordinal ranks are priorities, not measured severity scores. **Cheap** below
means forwarding an existing, bounded diagnostic or labeling an existing
branch; it is not a cost estimate or permission to change a public schema.

All source links below pin the same public main commit:
`bf2494ef478a96ea6403f86aea8d96e3e345482d`. They describe that tree, not a live
deployment or a future merged fix.

| Rank | Site / consumer | Flow position | Diagnosis already in hand? | Cheapest bounded action |
|---:|---|---|---|---|
| 1 | Bundle admission / builder preparing miner submission | Completed bundle, before conversion to submission record | Yes: whole design verdict, including field/rebuild reasons | Preserve the relevant public verdict diagnostics |
| 2 | Launchpad task door / miner or their agent | Task start, then observation/cancel after work may exist | Yes: adapter correction, field, code and dispatch flag | Forward the existing public correction; preserve typed observation failures |
| 3 | Remote output / miner controller and reconciliation consumer | After remote execution and output fetch | Yes: archive constraint and stage-specific failure detail | Preserve a bounded Carbon-authored output reason through reconciliation |
| 4 | Graphite pod launch / agent and operator | Compiled proposal and reserved launch attempt | Yes: structured provider HTTP/execution/recovery fields | Carry a safe structured error projection through PodFailure |
| 5 | Workbench App request / miner | Request validation; some errors before dispatch | Yes: declared field and local branch, or ValidationError locations | Separate correctable input failures from operational stop |
| 6 | Metered model-call summaries / Graphite agents and operators | After a provider attempt | Yes: closed provider report; incomplete reason retained in ledger | Preserve existing public next-step report and bounded incomplete metadata |
| 7 | Remote status polling / miner controller | Startup and completion polling | Yes: last HTTP status or parse/transport failure category | Retain last observation category when reporting deadline expiry |
| 8 | Remaining adapter argument branches / miner or agent | Request validation, after caller has composed the request | Yes: field/range or JSON-bound branch | Extend named corrections to the still-bare branches |

## Ranked evidence and what the caller would do differently

### 1. Final bundle admission throws away the design explanation

In [bundle_submission.check_admitted, lines 227-243](https://github.com/carbonphysicsai/Carbon/blob/bf2494ef478a96ea6403f86aea8d96e3e345482d/carbon/agent_campaign/graphite/bundle_submission.py#L227),
`check_design(...)` returns a record, but the wrapper takes only `['verdict']`.
If it is not submittable, the caller gets `design_<verdict>`; a malformed
request becomes `design_malformed`. The discarded record can already contain
registered fields, positions, applicability reasons and compiler issues:
[design_check, lines 316-378](https://github.com/carbonphysicsai/Carbon/blob/bf2494ef478a96ea6403f86aea8d96e3e345482d/carbon/development_session/design_check.py#L316).
[convert](https://github.com/carbonphysicsai/Carbon/blob/bf2494ef478a96ea6403f86aea8d96e3e345482d/carbon/agent_campaign/graphite/bundle_submission.py#L315)
has already read and checked the completed bundle before this step. The later
compiler-exception branch does preserve a detail; the defect is specifically
the earlier verdict projection.

**Caller change:** correct the unsupported field/backbone or precise rebuild
issue, rather than regenerate or repeatedly re-freeze an unexplained bundle.
**Cheap:** select existing public diagnostics, not raw exception strings.
**Discriminating follow-up:** unsupported field, unsupported backbone and
compiler issue should yield distinguishable corrections while all remain
refused; the valid twin should still convert. No conversion was executed here.

### 2. Launchpad discards corrections the adapter already supplies

[tool_door._refusal, lines 203-210](https://github.com/carbonphysicsai/Carbon/blob/bf2494ef478a96ea6403f86aea8d96e3e345482d/scripts/dev/miner_launchpad/tool_door.py#L203)
formats only code, dispatch flag and the generic next action. It omits
`AdapterFailure.field` and `correction`, even though
[AdapterFailure explicitly defines a registered public correction](https://github.com/carbonphysicsai/Carbon/blob/bf2494ef478a96ea6403f86aea8d96e3e345482d/carbon/miner_mcp/standard.py#L117).
[start](https://github.com/carbonphysicsai/Carbon/blob/bf2494ef478a96ea6403f86aea8d96e3e345482d/scripts/dev/miner_launchpad/tool_door.py#L142)
also catches schema ValidationError as bare `INVALID_ARGUMENTS`.
[observe, lines 173-199](https://github.com/carbonphysicsai/Carbon/blob/bf2494ef478a96ea6403f86aea8d96e3e345482d/scripts/dev/miner_launchpad/tool_door.py#L173)
collapses AdapterFailure and projection errors into the same operator-reconcile
instruction. This is a wrapper gap after the adapter's named-refusal repair.

**Caller change:** fix the named input on start; on observation, distinguish a
correctable identity from a genuine operational stop. Do not resend a task
whose dispatch is uncertain. **Cheap:** the adapter projection already exists;
Pydantic locations need the existing registered-field filter.
**Discriminating follow-up:** two fields with the same INVALID_ARGUMENT code
must produce different named corrections; a post-dispatch failure must retain
its honest dispatch/reconciliation flag. Changing only adapter tests would
leave this browser-facing wrapper defect undetected.

### 3. Remote output loses its reason twice

[RemoteJob.output, lines 216-229](https://github.com/carbonphysicsai/Carbon/blob/bf2494ef478a96ea6403f86aea8d96e3e345482d/carbon/compute/remote_job.py#L216)
turns archive/JSON errors into the exception type. The
[archive reader, lines 88-114](https://github.com/carbonphysicsai/Carbon/blob/bf2494ef478a96ea6403f86aea8d96e3e345482d/carbon/compute/job_server.py#L88)
already distinguishes size, gzip completeness and flat-regular-file failures
with Carbon-authored messages. Subsequently
[remote_runner, lines 252-270](https://github.com/carbonphysicsai/Carbon/blob/bf2494ef478a96ea6403f86aea8d96e3e345482d/carbon/compute/remote_runner.py#L252)
records only `failure.code` or its type in reconciliation; even an output HTTP
status/detail can disappear from that record. The exception is re-raised, so
some direct callers may still see detail: this is a demonstrated loss in the
durable reconciliation projection, not a claim that every consumer is mute.

**Caller change:** fix archive packaging or retrieve/reconcile an existing
output instead of treating every post-execution failure as an unexplained
rerun. **Cheap:** forward bounded, classified Carbon-authored reasons, without
filenames, archive content or arbitrary exception text. **Discriminating
follow-up:** bad gzip, oversize archive and missing result record must leave
different durable reasons; none may become a scientific candidate failure or
automatic retry. A good archive is the positive twin.

### 4. Graphite loses HTTP and recovery facts from ComputeError

[ComputeError](https://github.com/carbonphysicsai/Carbon/blob/bf2494ef478a96ea6403f86aea8d96e3e345482d/scripts/dev/exam_design/runpod/operator_compute/errors.py#L25)
already holds operation, HTTP status, execution, resources-may-remain,
retry-safe and next-action fields. The
[RunPod create branch](https://github.com/carbonphysicsai/Carbon/blob/bf2494ef478a96ea6403f86aea8d96e3e345482d/scripts/dev/exam_design/runpod/operator_compute/runpod.py#L395)
sets HTTP status separately from `failed`.
[Graphite pods.launch, lines 838-843](https://github.com/carbonphysicsai/Carbon/blob/bf2494ef478a96ea6403f86aea8d96e3e345482d/carbon/agent_campaign/graphite/pods.py#L838)
keeps only `failure.failed` and a coarsened executed boolean. For an executed
launch failure,
[experiment, lines 2127-2176](https://github.com/carbonphysicsai/Carbon/blob/bf2494ef478a96ea6403f86aea8d96e3e345482d/carbon/agent_campaign/graphite/experiment.py#L2127)
tries recovery before constructing the detailed pre-dispatch refusal record.
The original structured launch diagnosis is not forwarded on that branch.

**Caller change:** distinguish request/quota/authentication rejection from an
ambiguous create requiring reconciliation, using facts already classified by
the compute layer. **Cheap:** a narrow projection of typed fields through the
wrapper. Do not blindly forward `as_dict`: `failed` can include provider text;
use only an approved bounded category and the safe typed fields. Do not change
retry policy or authorize a replacement pod. **Discriminating follow-up:**
definitive rejection and uncertain transport failure must retain distinct
HTTP/execution/recovery facts at the final Graphite consumer. A raw-body canary
must stay absent.

### 5. Workbench input mistakes can look like an operational stop

[mcp_apps.call, lines 94-104](https://github.com/carbonphysicsai/Carbon/blob/bf2494ef478a96ea6403f86aea8d96e3e345482d/carbon/miner_mcp/mcp_apps.py#L94)
knows whether capabilities requires a null request and whether the request
exceeds its bound. The wrapper's
[ValidationError handler and blanket catch, lines 189-195](https://github.com/carbonphysicsai/Carbon/blob/bf2494ef478a96ea6403f86aea8d96e3e345482d/carbon/miner_mcp/mcp_apps.py#L189)
discard locations; local ValueError branches instead reach `OPERATIONAL_STOP`
with a reconciliation instruction. The
[direct study callable](https://github.com/carbonphysicsai/Carbon/blob/bf2494ef478a96ea6403f86aea8d96e3e345482d/carbon/miner_mcp/mcp_apps.py#L113)
also merges input and authorization/service errors as request unavailable.

**Caller change:** fix `action`/`request` or reduce the request, rather than
seek operator reconciliation for a proven pre-dispatch input fault. **Cheap:**
label the local branches and use declared field names from ValidationError.
Keep authorization and unknown backend errors generically closed.
**Discriminating follow-up:** wrong action, capabilities-with-request and
oversized request differ from an actual backend failure; a valid request and
an unauthorized caller remain separate controls.

### 6. Metered-call summaries retain too little of an existing diagnosis

[ProviderCallFailed.report, lines 177-188](https://github.com/carbonphysicsai/Carbon/blob/bf2494ef478a96ea6403f86aea8d96e3e345482d/carbon/development_session/research_agent.py#L177)
already gives closed public next-step, resumability and settlement facts.
[Graphite provider, lines 1043-1058](https://github.com/carbonphysicsai/Carbon/blob/bf2494ef478a96ea6403f86aea8d96e3e345482d/carbon/agent_campaign/graphite/provider.py#L1043)
and [ClosedTask, lines 253-265](https://github.com/carbonphysicsai/Carbon/blob/bf2494ef478a96ea6403f86aea8d96e3e345482d/carbon/agent_campaign/graphite/closed_task.py#L253)
retain outcome but do not forward that report. Incomplete responses are now
[recorded with their bounded reason and token counts](https://github.com/carbonphysicsai/Carbon/blob/bf2494ef478a96ea6403f86aea8d96e3e345482d/carbon/development_session/research_agent.py#L758),
but a caller that does not accept incomplete replies receives a generic
ValueError. ClosedTask maps that through
[_stopped](https://github.com/carbonphysicsai/Carbon/blob/bf2494ef478a96ea6403f86aea8d96e3e345482d/carbon/agent_campaign/graphite/triage.py#L93)
to `provider_response_incomplete`, without the retained reason.

**Caller change:** tell a cap-truncated turn from a provider refusal or a
settlement problem; adjust the correct constraint or seek reconciliation.
**Cheap:** the rejected-call public report can be forwarded. Incomplete
metadata needs an explicit typed handoff from the call boundary; this is more
than copying arbitrary ValueError text. No actual ledger was read here.
**Discriminating follow-up:** output-cap termination, content filtering and
quota rejection must remain distinguishable, with original accounting and
no-new-dispatch guarantees unchanged.

### 7. Remote polling masks the last observation behind a deadline

[RemoteJob._call/state/wait_for, lines 167-199](https://github.com/carbonphysicsai/Carbon/blob/bf2494ef478a96ea6403f86aea8d96e3e345482d/carbon/compute/remote_job.py#L167)
reduces transport exceptions to a type, then `state()` discards that category
and all non-success HTTP statuses. Malformed JSON/state also becomes None.
`wait_for()` can only report that its deadline passed. HTTP, transport and
decode categories were available earlier; there may still be no deeper root
cause, so do not invent one.

**Caller change:** investigate reachability, authentication/protocol or a
genuinely slow job instead of extending every timeout. **Cheap:** retain the
last classified observation and phase; transport exception text stays out.
**Discriminating follow-up:** an unreachable endpoint, non-success HTTP,
malformed status and a slow-but-valid status must leave different timeout
diagnostics. Report the observation, not a guessed cause; retain deadline and
cleanup semantics.

### 8. Adapter named refusals do not cover every argument path yet

The new [field helper](https://github.com/carbonphysicsai/Carbon/blob/bf2494ef478a96ea6403f86aea8d96e3e345482d/carbon/miner_mcp/standard.py#L371)
does not replace every `_invalid()` call. In
[_arguments, lines 395-429](https://github.com/carbonphysicsai/Carbon/blob/bf2494ef478a96ea6403f86aea8d96e3e345482d/carbon/miner_mcp/standard.py#L395),
non-object input, `forecast_resources.seconds`, task identity and poll sequence
still reach the bare code. [_object_json](https://github.com/carbonphysicsai/Carbon/blob/bf2494ef478a96ea6403f86aea8d96e3e345482d/carbon/miner_mcp/standard.py#L301)
knows object-versus-size failure; [_snapshot](https://github.com/carbonphysicsai/Carbon/blob/bf2494ef478a96ea6403f86aea8d96e3e345482d/carbon/miner_mcp/standard.py#L258)
knows depth, non-finite/type and aggregate-bound branches but supplies no
classified correction.

**Caller change:** fix the known field or reduce the correct structural bound,
rather than guess across the entire request. **Cheap:** field-level scalar
branches can reuse the existing correction builder. Nested structural paths
need a deliberate registered-name/position projection; never echo an invented
key or supplied value. **Discriminating follow-up:** seconds, poll identity,
non-object JSON and size failures must be told apart, while unexpected keys
and secret-shaped values remain unreflected.

## Repaired motivating cases and useful counterexamples

The following are source evidence of discriminating paths, not newly executed
tests or host acceptance:

- Top-level miner-field mistakes now use a correction-bearing adapter error.
  [Existing tests](https://github.com/carbonphysicsai/Carbon/blob/bf2494ef478a96ea6403f86aea8d96e3e345482d/tests/cpu/test_miner_door_top_level_field.py#L46)
  assert the field/correction and keep unexpected keys unnamed. Rank 2 is the
  downstream Launchpad loss; rank 8 is the uncovered argument branches.
- [Level 4 shape validation](https://github.com/carbonphysicsai/Carbon/blob/bf2494ef478a96ea6403f86aea8d96e3e345482d/carbon/agent_campaign/graphite/experiment.py#L1295)
  now emits `level4_submission_shape` and the registered field, before the
  genuinely not-staged branch. [The test](https://github.com/carbonphysicsai/Carbon/blob/bf2494ef478a96ea6403f86aea8d96e3e345482d/tests/cpu/test_graphite_level4_carry.py#L76)
  explicitly guards against sending a staged wrong-shape case back to staging.
- [Proposal validation](https://github.com/carbonphysicsai/Carbon/blob/bf2494ef478a96ea6403f86aea8d96e3e345482d/carbon/agent_campaign/graphite/experiment.py#L1328)
  now reports field, problem and correction; [its tests](https://github.com/carbonphysicsai/Carbon/blob/bf2494ef478a96ea6403f86aea8d96e3e345482d/tests/cpu/test_graphite_proposal_arguments_named.py#L55)
  assert different faults. The bare reason code alone is no longer its reply.
- [The main research loop](https://github.com/carbonphysicsai/Carbon/blob/bf2494ef478a96ea6403f86aea8d96e3e345482d/carbon/development_session/research_loop.py#L2524)
  now records incomplete reasons, notes truncated calls and gives a typed
  repeated-truncation outcome. It is not the old blanket stalled diagnosis.
  Rank 6 concerns other wrappers, not that repaired loop.
- [MCP's registered-field filter](https://github.com/carbonphysicsai/Carbon/blob/bf2494ef478a96ea6403f86aea8d96e3e345482d/carbon/miner_mcp/mcp_extensions.py#L128)
  and [task refusal handler](https://github.com/carbonphysicsai/Carbon/blob/bf2494ef478a96ea6403f86aea8d96e3e345482d/carbon/miner_mcp/mcp_extensions.py#L240)
  demonstrate a safe existing alternative to printing Pydantic's full input.
- [Discovery's hostile-provider boundary](https://github.com/carbonphysicsai/Carbon/blob/bf2494ef478a96ea6403f86aea8d96e3e345482d/carbon/research/discovery.py#L218)
  deliberately closes arbitrary exception text. Do not rank every blanket
  catch as a defect. Unknown provider/authorization errors and secret-bearing
  exception messages need closed categories, not reflexive transparency.

## Method, limits and handoff

The public tracked-file index at the source commit was complete, not truncated.
A temporary source-only snapshot selected **360 Python/JavaScript files**
across miner MCP, Graphite, development-session, reconstruction-worker,
Launchpad, compute/operator-provider, authoring, transport, research,
orchestration, evaluation/reexecution, execution, qualification, product and
dashboard interfaces, plus selected public tests. This finite snapshot count
has low/base/high = **360/360/360**, not an uncertainty interval. Source was
searched with `rg`, then the ranked producers, consumers and cited branches
were read. No production imports, provider calls, remote jobs, models, solvers,
credentials, retained ledgers, holdout or protected material were opened or
executed. Numerical kernels, archived code and unrelated data were outside
this interface survey. This is not an exhaustive repository-wide defect count
or a measurement of user exposure on a live service.

Only this document changes. Recommendations and proposed negative controls
are **not implemented or run**. Native document checks cover UTF-8/LF,
whitespace, source-link anchors and delivery hygiene; canonical documentation
CI covers its classified repository acceptance. Neither establishes that a
runtime fix works. Future fixes need producer-to-final-consumer tests, with
the valid twin and distinct bad reasons, so a correct inner test cannot hide
a broken outer projection. Any new disclosure must follow the relevant
allow-list/Validator review; retry, reserved spend, failure typing and scientific
admission remain unchanged.

Suggested first repair batch is ranks 1-4, serialized with their owning lanes.
The live open-PR overlap check found no other PR for this survey or its new
document path. No edits to those runtime files or another lane's work are
included. This finding list is a dated snapshot; later repairs annotate its
status rather than rewriting what the pinned source did.

Delivery seam: the Test Lead is resolving the conflict between supplied
AGENTS delivery/Hub instructions and current-main OWNER-DX-03. Ordinary safe
research and a reviewable PR can proceed; final closeout/PR Head handoff and
merge remain held until that routing is resolved. No Hub files or authority
documents are changed here. Maturity is **DEVELOPMENT STATIC RESEARCH** only;
scientific, security and production acceptance are not earned. No PC work is
needed for this survey.
