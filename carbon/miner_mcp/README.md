# Carbon research MCP

Carbon's Model Context Protocol interface lets an external agent or client inspect challenges, use research tools, and operate a development campaign. It shares campaign operations and records with the Miner Control Center. Start without a configuration to inspect the open onboarding and exam information; research execution needs a registered miner and a configured runtime.

This is a development interface. A submitted candidate is not a qualified engineering model or a production reward claim. [Project status](../../docs/publications/PROJECT_STATUS.md) explains the available challenges and evidence.

## Interface and admission

This optional adapter exposes one of the miner's existing research campaigns. It
uses the same principal, signed gateway, operation identity, task controller,
workspace and campaign ledger as Launchpad. Starting another client does not
create a campaign, change a budget or start the paid research loop.

Registration is the only admission gate (C-MLP-02-D11). A campaign is admitted
by the subnet registration its manifest records, and every research call
re-reads that registration from the chain. No grant exists on this door.

## Operator setup

Use the accepted Linux checkout and pinned environment:

```sh
CARBON_UV_GROUPS='chain archive science-jax mcp' ./scripts/dev/bootstrap.sh
python -m carbon.miner_mcp.standard_cli \
  --configuration /absolute/private/runner-profile.json \
  --campaign <campaign id under campaigns_root>
```

## Every operation, from your own client

With your runner profile and no `--campaign`, the server carries the whole
journey - nothing on it is issued by Carbon:

```sh
python -m carbon.miner_mcp.standard_cli \
  --configuration /absolute/private/runner-profile.json
```

- the four `carbon_onboarding_*` tools, reading Carbon's testnet;
- one tool per miner operation - `carbon_launch` (with `agent` `autonomous`
  or `none`; setup's names `carbon-autonomous` and `own-agent` are accepted
  as the same choices), `carbon_observe`, `carbon_practice`,
  `carbon_freeze_candidate`, `carbon_submit`, `carbon_halt`, `carbon_resume` -
  generated from the same operations table
  (`scripts/dev/miner_launchpad/operations.py`) as the browser's
  `/api/v1/operations` routes, with the same gates in the same order over the
  same campaign records. Their schemas state each field's closed values as
  enums and mark launch's `challenge` and `challenge_version` required.
  Launch's `idempotency_key` is optional on this door: omitted, the server
  generates `mcp-<32 hex>` and returns it as `idempotency_key`; send your own
  to make a retry after a lost response replay instead of launching a second
  campaign;
- `carbon_attach_campaign` and `carbon_detach_campaign`, which bind this
  session to one campaign for the deeper research tools (workspace,
  `run_python`, Julia). Attaching holds the campaign's ownership lock, so
  practice, freeze, submit, resume and halt `action=reconcile` on that
  campaign answer `campaign_busy` up front until you detach; observe,
  campaign view, messages, note and run output keep working. One attach or
  detach runs at a time (`attachment_busy`), and a detach is refused while
  this session's research calls are in flight (`research_calls_in_flight`).

Registration admits every operation that starts or extends work; observe and
halt only read or withdraw, so a miner can always see and stop their own
campaign. `carbon_submit` is the DEVELOPMENT submit: a signed message to the
local development service, with nothing written to the chain. Official
submission is not an operation on either door. A campaign an MCP session
launched with the autonomous agent runs while the session lasts; resume
continues it.

## Starting without a campaign

A miner who has not registered yet has no profile and no campaign, so
`--configuration` is optional. Omitted, the server carries the open tier alone:

```sh
python -m carbon.miner_mcp.standard_cli
```

That serves the four `carbon_onboarding_*` tools and the published validator
exam environment, and nothing else. The research tools are *absent* rather than
present-and-refusing, which is what the registration gate (C-MLP-02-D10) is
worth: the tier is a property of what exists, not a check inside each tool.
Nothing reachable here creates a campaign, consumes compute or touches the
ledger, and no tool signs or accepts key material.

`carbon.miner_mcp.open_tier.attach_campaign` adds the registered tier to a
running server, so a miner who registers mid-session keeps their connection
instead of tearing it down at the moment they have just done the one
irreversible thing. One server owns one campaign; a second attachment is
refused rather than replacing the first.

Two limitations worth knowing before building on this:

- **Onboarding reads Carbon's testnet.** Both doors default to
  `chain_onboarding.carbon_testnet_context` (subnet 567), so `status` and
  `confirm` answer from public chain state; `confirm` names what registration
  unlocks - the launch operation - rather than claiming an environment opened.
- **List changes are announced by this server, best effort.** The pinned
  SDK's own `add_tool` sends nothing, so the open-tier server advertises
  `listChanged` for tools, resources and prompts on its handshake, and every
  call that adds or removes tools announces it (`open_tier.announce`): as
  `notifications/tools/list_changed` (and the resources and prompts
  equivalents) on a handshake-era session, and on the `subscriptions/listen`
  stream of a 2026-07-28 client. Whether a client re-lists is the client's,
  so each such result also names the tools in `tools_added` and reports
  `list_changed_announced`; a client that ignores notifications sees the new
  tools on its next `tools/list`.

## Automate setup with your agent

Your own agent can set up the miner's environment for them, from nothing to
launch, over the same setup records as the Control Center
(OWNER-MINER-SETUP-AGENT-FIRST-01). Start the server with no profile:

```sh
python -m carbon.miner_mcp.standard_cli            # add --state-dir if the Control Center uses another
```

- **One loop.** `carbon_setup_status` returns the steps done, the next step,
  what it is missing (closed codes) and the exact next call with its
  arguments schema. Call it, make the call, repeat until `next.step` is
  `launch`. The prompt `carbon_setup_workflow_v1` states the loop.
- **One table, two doors.** The `carbon_setup_<step>` tools and the
  Control Center's `/api/v1/setup/<step>` routes (and `GET
  /api/v1/setup/status`) are generated from
  `scripts/dev/miner_launchpad/setup_operations.py` and call the same
  operation, with the same gates in the same order. The page shows the
  agent's progress and the agent's status shows the page's.
- **The order:** start your signer, register on the subnet, who researches
  (`carbon-autonomous`, `own-agent` or `hermes`), inference (skipped for
  `own-agent`: it uses its own model), compute, review and launch.
- **The tiers grow, absent before they are present (C-MLP-02-D10).**
  `carbon_setup_status`, `carbon_setup_signer` and `carbon_setup_begin` are in
  the open tier. The later steps appear once setup has confirmed the
  registration; launch and the research operations once `carbon_setup_review`
  writes the runner profile, in the same session, and at once in a session
  that reconnects after review. A result that adds tools lists them in
  `tools_added` (the server also announces the change): list the tools
  again. At the launch step, `next.call.in_this_session` says whether
  `carbon_launch` is in this session; when it is not, `next.call` says
  why - the written profile did not load here (call `carbon_setup_review`
  again), or a reconnect command with your profile and state directory.
- **The miner's own steps.** Starting the signer and signing the registration
  answer a closed `human_action_required` result with the exact instruction
  or command. Nothing here accepts, returns or logs a private key, seed
  phrase, mnemonic or password; the only hotkey value is the public address.
- **The model key is a file.** `carbon_setup_inference` takes `model_key_file`, the
  absolute path to an owner-only file the miner made (a regular file they own,
  with no group or other access). A key passed as a value is refused.
- Refusals are closed JSON: `error`, `field` and `next_step`.

The Control Center's step 3 shows the command for its machine with snippets
for Claude Code, Codex and Hermes, from each client's documentation, read
2026-10-02. UNVERIFIED: Carbon has not run those clients against this server.

## The prepared-campaign profile

The installed console command is `carbon-mcp` with the same arguments. The
profile is the miner's private Launchpad runner profile (v2), and `--campaign`
names one of the prepared, frozen, unfinished campaigns under its
`campaigns_root`. The campaign must have been admitted by registration and must
match the profile's principal, accepted implementation, role roots and image
identities. A campaign launched under the retired development grant is not
attached here; the Launchpad reconciles it. A campaign is created by the launch
operation, from either door. Normal attachment rejects completed or
expired campaigns; the cleanup-only mode below does not reopen research. The
operator host needs the accepted checkout;
an external MCP client needs only its configured command or private connection.

Configure a stdio MCP client to launch the Python executable from that environment
with the module and configuration arguments above. Keep private paths and tokens
out of research prompts, artifacts and exported client examples. The CLI obtains
the existing exclusive campaign owner lock and runs normal interruption cleanup
on disconnect. An interrupted task may remain reconciliation-required until
resource release and consumption are established.

## What this server bounds, records and refuses

Read `carbon://research/v1/catalogue`. It describes the *server* - operations,
bounds, refusal vocabulary and record policy, with its own schema version - as
distinct from `carbon://research/v1/capabilities`, which projects the scientific
catalogue of what a miner may attempt. Keeping them apart is what lets a client
tell a surface change from a science change instead of rediscovering one as the
other.

**Records.** Each call records the operation, the owner-bound principal, a
digest of the operation id, an outcome and a duration. It never records the
arguments. A research argument carries the miner's hypothesis, their strategy
parameters and their file contents - their work - so `call_record` has no
parameter for them and no call site can supply one. The principal is a
`BoundPrincipal`, derivable only from an adapter that re-verifies its own owner
binding, so a record cannot attribute a call to a caller-named identity even by
mistake. Records go wherever the operator injects them, and nowhere by default.

**Refusals** carry a stable slug and the next usable step. The slug is the
adapter's own enum value so it cannot drift, and the next action is fixed text
per slug rather than a provider message, because provider text is how
unbounded internal detail reaches an external wire. Arguments that do not
match a tool's schema are refused first by the MCP SDK's own validation
message; every refusal after that is one of the forms below, after the SDK's
`Error executing tool <name>: ` prefix.

- Research tools, and a negotiated Tasks start, answer one line:
  `CODE; dispatch_may_have_occurred=true|false; [field=<schema field>;]
  next_action=...`. `field` is only ever a field the schema declares, never a
  key the caller invented. `dispatch_may_have_occurred=false` is reported only
  where it is a fact: a typed pre-dispatch refusal, a signer failure before
  any signature, or a refusal raised at one of the two sites that run before
  anything is signed - the operation-id binding of a numerical start, and the
  campaign's admission check. Those sites have their own codes:
  `CAMPAIGN_ELAPSED_BUDGET_REACHED` (the campaign's time limit - the elapsed
  budget set at launch or a development grant's expiry - is reached, or the
  host clock moved backwards), `CAMPAIGN_ADMISSION_STOPPED` (paused, stopped,
  completed, awaiting reconciliation, or its control taken by another
  holder) and `OPERATION_ID_REUSED` (the operation_id already names a
  different numerical start). Any other failure there is an
  `OPERATIONAL_STOP` that started nothing; the same text raised anywhere
  else keeps the conservative `dispatch_may_have_occurred=true`.
- The operation, attach and setup tools answer closed JSON:
  `{"error": <code>, "field": <field to correct, when one is to blame>,
  "next_step": ...}`.

A registered pre-dispatch correction from the research SDK (a
`REJECTED_BEFORE_DISPATCH` result with `correction_code`, `field` and
`correction`) reaches the client in this wire's object terms (`arguments.name`,
not `arguments_json.name`), and only when the adapter can rebuild its exact
text from the registered code and field.

**Results.** A research result over 1 MiB is cut to fit rather than refused:
its largest strings and lists are shortened, never below 1024 characters or
16 elements, and a `truncation` record names each cut (`cut`, the first 16;
`cut_total`). Only a value over 16 MiB, or one that cannot be cut to fit, is
`INVALID_RESULT`. `carbon_run_output` returns a run's raster images as MCP
image content; the JSON names each by its content index.

**Capacity.** Concurrent calls are bounded, and waiting for capacity has a
deadline: exceeding it returns `CAPACITY_UNAVAILABLE` with
`dispatch_may_have_occurred=false`, because nothing was dispatched.

A call that has already started is never cancelled to meet its budget; it is
recorded as `OVERRAN` and allowed to finish. Cancelling an in-flight
`adapter.call` would abandon a ledger reservation whose outcome nobody knows,
which is the `requires_reconciliation` state the campaign model exists to
prevent - a transport timeout would be manufacturing the failure it was added to
contain. The work itself is bounded by the `seconds` argument and task
supervision.

## Client workflow

Read `carbon://research/v1/capabilities` and
`carbon://research/v2/guidance`, or request the
`carbon_research_workflow_v2` prompt. Tools have typed object arguments and
structured results with text fallback. Clients do not supply the principal or
wrap arguments in undocumented JSON strings.

`operation_id` is optional on every research tool. Omitted, the server
generates `mcp-auto-<32 hex>` and returns it as `operation_id`; its schema
states the bounds (16 to 114 letters, digits, `.`, `_`, `:` or `-`). What it
does depends on the tool. On `start_research_task` it is the task's
idempotency key: send your own and retain it across reconnects, and the same
id with the same arguments returns the original task instead of starting
another; a changed request under a used id is a conflict, refused as
`OPERATION_ID_REUSED` before anything starts for a numerical start (practice,
`run_python`, `run_julia`). On `cancel_research_task` it is the cancellation's
identity: omitted, it is `mcp-cancel-<task_id>`, the identity `tasks/cancel`
uses too, so a retried cancel is accepted again; a task holds one
cancellation identity, so a cancel under a different id while the first is
pending is refused. Other tools only record it. Use the returned task
identity for status/result/cancel. Polling and display do not create another
numerical attempt. A client may propose hypotheses and stop within its
campaign's own limits; no second proposal or improvement is required.

Python `mcp==2.2.0` and TypeScript `@modelcontextprotocol/client==2.0.0` are the
tested independent client implementations. Versioned start/status/result/cancel
tools retain Carbon's durable identity and cleanup semantics. The prospective
C-CORE-10 Tasks extension uses the released 2026-07-28 schema with Python SDK
2.2.0; the existing TypeScript baseline does not establish Tasks support in that
client or an agent host.

## Negotiated Tasks and Skills

Clients declaring `io.modelcontextprotocol/tasks` on a 2026-07-28 request receive
a flat `resultType: "task"` handle for an admitted `start_research_task` before
its supervised work finishes. `taskId` is Carbon's existing durable task ID.
Use `tasks/get` with `{ "taskId": "rtsk_..." }`; a completed task contains the
same typed tool result in `result`, including a `FAILED_INFRA` outcome when
applicable. The original `operation_id` survives reconnects. Neither polling
nor reconnecting redispatches uncertain work or consumes another trial.

Use `tasks/cancel` with the same ID to request domain cancellation. Its empty
acknowledgement is an intent, not proof of allocation release. Poll for observed
state and retain unresolved accounting.

A failed `tasks/get` or `tasks/cancel` is a JSON-RPC error. `-32602
TASK_NOT_FOUND; retry=false; next_action=...` means this campaign holds no
task with that ID: an unknown ID and another miner's task are deliberately
indistinguishable. Every other failure is `-32603 <CODE>; retry=true|false;
next_action=...` under its own code, and never claims the task is missing:
`retry=true` only where the same observation may succeed later (a stopped or
slow signer, a campaign not admitting, an operational stop), and `retry=false`
for the rest - among them `INVALID_RESULT` (the task's state could not be put
on the wire; after a cancel it may already be accepted, so do not start the
task again), `OWNER_BINDING`, and `OBSERVATION_LIMIT_REACHED` (the provider's
bound on observing one task; `get_research_result` still reads it). `tasks/update` accepts typed responses
but requests no client approval/grant values; responses to nonexistent input
requests are ignored after ownership checks. These verbs require the extension
on each request; HTTP clients must send `Mcp-Name: <taskId>` and the correct
`Mcp-Method`. SDK requests should declare `name_param = "taskId"`. The original
fallback tools and shared legacy `poll_sequence` remain available and unchanged;
Tasks polling uses a separately bounded observation count in the same provider.

Graceful server shutdown stops admission, requests cancellation of its owned
workers and joins their supervised cleanup before the CLI closes its lease.
Process loss cannot certify cleanup. The miner may reattach using the same
command plus `--cleanup-only` after a stop, a pause or an exhausted budget;
this permits owned status/cancel access, rejects new execution, and still
requires valid external authentication. It admits no new work.

The `io.modelcontextprotocol/skills` extension implements `skills/list` and
`skills/get`. Its fixed entry is
`skill://carbon/carbon-research-v1/SKILL.md`; the complete manifest includes
`references/workflow.md`, exact UTF-8 byte sizes and SHA-256 digests. Read files
through `resources/read`. Direct lookups require authorization even without
prior discovery. Listings use private, zero-TTL caching. Directory reads,
arbitrary filesystem access and nested activation are unavailable. Client
hosts retain responsibility for verifying the originating server, manifests
and skill-loading consent; reading guidance confers no execution authority.

Released upstream contracts:
[Tasks schema](https://github.com/modelcontextprotocol/ext-tasks/blob/main/schema/2026-07-28/schema.ts),
[Skills stable specification](https://github.com/modelcontextprotocol/ext-skills/blob/main/specification/stable/skills.mdx),
[Python SDK extensions](https://py.sdk.modelcontextprotocol.io/advanced/extensions/).
The original v1 guidance resource/prompt remains available for compatibility.
Current plain-client guidance is `carbon://research/v2/guidance` and the
`carbon_research_workflow_v2` prompt; both serve the same current workflow as
the Skill. No Skills support is needed to read them.

## Native Julia public study

The prospective `julia_burgers_study_v1` public material requires an exact
`scientific_tasks` extension in the campaign's pinned runtime/grant. The operator
builds its reviewed Julia image with `bash scripts/dev/julia_worker_image.sh`.
`julia_burgers_scope(image, role_root)` describes the required bytes; calling it
does not authorize the grant. Existing campaigns are not amended automatically.

This first task runs a coarse/fine periodic viscous Burgers study on the first
permitted public TRAIN case using Julia 1.13.0 through the existing C-04
controller. It exports dimensionless float64 little-endian solution arrays and
bounded conservation, horizon, refinement and resource diagnostics. Two
trajectories/invocations and their numerical time are charged to the existing
ledger. Cancellation propagates to the controller and verified worker cleanup.

It is a DEVELOPMENT diagnostic. Its output is not training support, accepted
truth, a certified error bound or qualification. It cannot select hidden cases,
a grader, arbitrary scripts or acceptance tolerances. The existing primary
reference stays intact. The bounded envelope task and authored research below
retain their separate registered scopes and evidence-use limits.

### Registered material selection

The standard launcher checks the campaign's exact retained `scientific_tasks`
documents against the registered factories before constructing a consumer.
The following are the supported combinations; list order is part of the contract.
These are operator-side grant bindings, not client-supplied task arguments.

| Retained scientific scopes | Selected public material |
| --- | --- |
| Field absent | Existing legacy public material |
| One exact `julia_burgers_scope(image, role_root)` | `julia_burgers_study_v1` |
| Exact Burgers scope followed by `julia_envelope_scope(image, role_root)` | Burgers plus `julia_burgers_envelope_v2` |
| One exact `advection_scope(authored_image)` | `julia_advection_study_v1` |

An empty list, unknown or modified scope, reordered companion, extra scope or
mixed task combination rejects attachment. Factories are defined in
`carbon.development_session.julia_research`, `julia_envelope` and
`advection_research`, respectively. A matching schema name alone is insufficient.

Advection also requires the exact `authored_research` scope and the separately
loaded `JuliaResearchImageIdentity` from the private authored-image record. That
image must have the admitted public analysis image as its parent, and that
analysis image must retain its accepted C-03 worker binding. The same authored
image supplies the advection material and research executor; public reference and
practice consumers keep their separately bound worker image. The advection study
is public self-reported DEVELOPMENT evidence, with no validator or Workbench
qualification implied by availability here.

The envelope task reserves its complete bounded sequence before dispatch and
retains uncertain claimed consumption during cancellation. Cleanup-only
attachment can construct either consumer using the exact retained owner,
generation, runtime and image after expiry. Every new capability/study call still
checks fresh admission; cleanup attachment does not extend the grant.

For isolated miner-authored `run_julia`, use the separate
[authored Julia operator and client guide](../../docs/development/AUTHORED_JULIA_RESEARCH.md).
Installing its image or starting an MCP client does not amend an existing grant.

## Private Streamable HTTP composition

`standard_http.create_http_app(adapter, verifier)` creates an ASGI application
over the same adapter; it starts no listener or deployment. A trusted operator
supplies `HttpPrincipalBinding` with the exact HTTPS resource, issuer, audience,
client, subject and Carbon principal, then constructs
`BoundTokenVerifier(binding, public_keys=...)` with reviewed RSA public keys. The existing
grant still controls each operation. The caller cannot set any of these bindings.

Bearer token verification covers signature, issuer, audience, expiry and scope.
Direct tools, resources and prompts all recheck authorization; sessions are
principal-bound. Configure the private service's TLS/authentication boundary
under its existing deployment authority. No dynamic issuer or key URL is loaded
from a request. Authorization-server deployment and real remote-host acceptance
are not established by the in-process HTTP tests.

## Acceptance and limits

CPU tests cover adapters, closed inputs, replay, expiry and rights rejection.
Service tests use real independent client processes; the dedicated Julia miner
test additionally executes the real registered Julia worker and persists its
result across reconnects. Fixture signing/registration and grants are explicitly
engineering-only and cannot enter LIVE authority.

Canonical CI runs these tests plus package and isolated-service acceptance.
Local WSL runs are diagnostic evidence. A real agent-host research session,
GPU/TPU execution, numerical cross-backend calibration and production security
qualification remain open. Never interpret client interoperability as those
later states.
