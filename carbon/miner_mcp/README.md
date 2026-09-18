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
`carbon://research/v1/guidance`, or request the
`carbon_research_workflow_v1` prompt. Tools have typed object arguments and
structured results with text fallback. Clients do not supply the principal or
wrap arguments in undocumented JSON strings.

Choose one stable `operation_id` per intended operation, retain it across
reconnects, and use the returned task identity for status/result/cancel. Reusing
an identity with changed inputs is a conflict. Polling and display do not create
another numerical attempt. A client may propose hypotheses and stop within its
grant; no second proposal or improvement is required.

Python `mcp==2.2.0` and TypeScript `@modelcontextprotocol/client==2.0.0` are the
tested independent client implementations. The server negotiates MCP rather
than pretending an unsupported Tasks extension exists. Versioned start/status/
result/cancel tools retain Carbon's durable identity and cleanup semantics.

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
