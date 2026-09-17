# Standard Carbon research MCP

This optional adapter exposes the existing admitted CPU research campaign. It
uses the same principal, signed gateway, operation identity, task controller,
workspace and campaign ledger as Launchpad. Starting another client does not
create a grant, reset an allowance or start the paid research loop.

## Operator setup

Use the accepted Linux checkout and pinned environment:

```sh
CARBON_UV_GROUPS='chain archive science-jax mcp' ./scripts/dev/bootstrap.sh
python -m carbon.miner_mcp.standard_cli --configuration /absolute/private/runner-profile.json
```

The installed console command is `carbon-mcp` with the same arguments. The
profile is the existing private Launchpad runner profile for an already prepared,
frozen, unfinished campaign. It must match its existing owner, current grant,
accepted implementation, role roots and image identities. Preparation and
authorization remain operator actions. A completed or expired campaign cannot
be reopened by this command. The operator host needs the accepted checkout;
an external MCP client needs only its configured command or private connection.

Configure a stdio MCP client to launch the Python executable from that environment
with the module and configuration arguments above. Keep private paths and tokens
out of research prompts, artifacts and exported client examples. The CLI obtains
the existing exclusive campaign owner lock and runs normal interruption cleanup
on disconnect. An interrupted task may remain reconciliation-required until
resource release and consumption are established.

## Client workflow

Read `carbon://research/v1/capabilities` and
`carbon://research/v2/guidance`, or request the
`carbon_research_workflow_v2` prompt. Tools have typed object arguments and
structured results with text fallback. Clients do not supply the principal or
wrap arguments in undocumented JSON strings.

Choose one stable `operation_id` per intended operation, retain it across
reconnects, and use the returned task identity for status/result/cancel. Reusing
an identity with changed inputs is a conflict. Polling and display do not create
another numerical attempt. A client may propose hypotheses and stop within its
grant; no second proposal or improvement is required.

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
state and retain unresolved accounting. `tasks/update` accepts typed responses
but requests no client approval/grant values; responses to nonexistent input
requests are ignored after ownership checks. These verbs require the extension
on each request; HTTP clients must send `Mcp-Name: <taskId>` and the correct
`Mcp-Method`. SDK requests should declare `name_param = "taskId"`. The original
fallback tools and shared legacy `poll_sequence` remain available and unchanged;
Tasks polling uses a separately bounded observation count in the same provider.

Graceful server shutdown stops admission, requests cancellation of its owned
workers and joins their supervised cleanup before the CLI closes its lease.
Process loss cannot certify cleanup. The trusted operator may reattach using
the existing CLI command plus `--cleanup-only` after grant expiry or pause;
this permits owned status/cancel access, rejects new execution, and still
requires valid external authentication. It does not extend the grant.

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
reference stays intact. General parameter sweeps and miner-authored Julia scripts
remain separate implementation/containment work.

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
