# C-CORE-10: negotiated MCP Tasks and research Skills

Programme #209 / MCP #210. Owner authority: integrated v3 execution mandate
in `.agent/plans/CARBON_CORE_PLATFORM_EXECUTION.md`. Dependency C-CORE-07
PR #224, starting head `49e418d3aa639558095aeea26b39205d55678238`;
main at ticket start `cfd4a4bc5ed6ce108e5ea61db449b24f663d952b`.
Status: implemented with local diagnostics; canonical acceptance and delivery pending.
Primary Hub map_ref `SYSTEM/AGENT-EXECUTION`; `map_structural` impact,
affecting WAVE-C/C-08, SYSTEM/PROTOCOL-AUTHORITY and SYSTEM/CI.

## Contract and C-CORE-10-D1

KEEP the existing authenticated research service, durable task provider,
CampaignLedger, admission, worker controller, private ownership and cancellation.
WRAP the standard MCP 2.2.0 server with the official Tasks and Skills extensions
for protocol revision 2026-07-28. Preserve the existing twelve fallback tools,
their closed arguments and old request/task identities. A client capability is
protocol negotiation, never execution permission. No second scheduler, ledger,
research loop, evaluator or grant is introduced.

The current SDK supports additive Extension/MethodBinding and tools/call
interception. C-CORE-02's fallback-only choice remains historical evidence;
this prospective ticket implements the protocol layer over that working path.
Use only released upstream schema/specification and the pinned installed SDK.
References verified 2026-09-17:

- https://tasks.extensions.modelcontextprotocol.io/specification/2026-07-28/tasks
- https://github.com/modelcontextprotocol/ext-tasks/blob/main/schema/2026-07-28/schema.ts
- https://github.com/modelcontextprotocol/ext-skills/blob/main/specification/stable/skills.mdx
- https://py.sdk.modelcontextprotocol.io/advanced/extensions/

An authenticated acknowledged-start mode returns only after the existing task
is durably stored and findable. Its execution remains owned by the current
supervisor. Maintain a strong bounded ownership record for dispatched work;
shutdown/cancellation uses the existing controller and waits for observed
cleanup. Reconnect/replay must not resubmit a RUNNING or uncertain attempt.
Do not create detached execution with no accountable owner or claim process
exit proves release. The synchronous fallback retains its existing behavior.

MCP task IDs identify the same Carbon task. Task reads and cancellation recheck
the current principal, grant/generation and authenticated service binding,
including direct requests. Adapt the provider's persisted global poll sequence
atomically so concurrent clients and fallback polling cannot manufacture stale
snapshots or extra work. Reuse the accepted cancellation identity on retries.
Any required projection metadata belongs beside existing task/operation state;
it may not become an alternative source of lifecycle or accounting truth.

Return flat CreateTaskResult only when the current request declares the Tasks
extension. Implement tasks/get, tasks/cancel and tasks/update with bounded
typed inputs and Streamable HTTP routing metadata. Cancellation acknowledgement
expresses intent; expose completion only from observed domain state. Preserve
Carbon FAILED_INFRA and other typed outcomes inside the ordinary tool result;
MCP failed is for JSON-RPC failure, not scientific/candidate classification.
Unknown or already-satisfied input responses are acknowledged only after task
ownership checks; this implementation does not invent human input requests.

Publish one versioned research Skill through skills/list, skills/get and
resources/read with an exact byte-size/SHA-256 manifest and immutable URI.
Reuse the current workflow objectives, methods, budget/stopping guidance and
text/prompt fallbacks. No arbitrary file path, nested skill activation,
protected content, executable instruction or request-time package installation.
Direct skill/resource requests require the same authorization as tool access.
Client loading and approval behavior remain the client's responsibility.

Alternatives rejected: an independent task store/scheduler; fake completed
Tasks wrapping blocking calls; protocol cancellation reported as verified
cleanup; weakening B-07 sequence/ownership checks; inventing protocol fields;
requiring optional extensions for clients that already work. Reversal removes
the prospective extension registration while preserving existing task records,
fallback behavior and historical evidence. Root owns shared integration.
Material lead notification remains pending the existing external-message
approval; this does not suspend authorized engineering under OWNER-DX-03.

## Plan and acceptance

1. Existing standard stdio and authenticated HTTP baseline: 20 tests passed,
   69.04 seconds, native WSL diagnostic, no paid calls.
2. Add the bounded acknowledged-start/atomic observation seam in the existing
   controller and provider; test lifecycle, replay, concurrency and cleanup.
3. Add negotiated Tasks/Skills with strict schemas, authorization and versioned
   guidance; retain no-extension and legacy behavior.
4. Exercise real external SDK stdio and authenticated HTTP, independent client
   wire behavior, restart/reconnect, cross-owner rejection and actual worker
   cancellation. Keep deterministic interoperability separate from paid agent
   learning and hardware acceptance.
5. Run affected tests, all invariants, strict quality, package/outside-tree and
   required canonical classification/CI; update the existing programme and Hub.

Expected files: new `carbon/miner_mcp` extension modules/guidance, narrow edits
to `standard_server.py`, `standard.py`, `research.py`, existing research SDK,
durable provider and service composition; new focused CPU/service tests and
required test manifest entries. Coordinate any shared research file changes
with C-CORE-08 before editing. No changes to scientific eligibility, protected
evaluation, grants, runtime images, cloud allocations, paid campaigns, chain
operations or public deployment. Completion requires the unchanged tested head
to pass applicable checks and merge normally under OWNER-DX-03; no scientific,
security or production qualification is earned by this ticket.

## Implementation and observed acceptance

The adapter now acknowledges existing durable starts before supervised execution
ends. Current task observations use the same provider, ownership lock and store;
they retain the original operation identity and do not advance the legacy poll
sequence. A missing adjunct row after a crash or a pre-extension operation is
derived from the retained request/task with created=False, without new dispatch.
Concurrent polling is bounded at 10,000 observations. Cancellation reuses its
accepted domain identity. Graceful shutdown stops admission, cancels owned work
and joins cleanup before releasing the owner lease; transport cancellation is
shielded while cleanup finishes. Cleanup-only CLI attachment rejects new work.

MCP Tasks uses released 2026-07-28 flat handles, direct authorized get/cancel/update
and typed bounded inputs. FAILED_INFRA remains inside a completed tool result.
Skills uses one fixed two-file SHA-256/byte-size manifest, private zero-TTL
metadata and guarded resource reads. Current v2 guidance/resource prompt shares
the Skill workflow; historical v1 guidance remains available with historical
discovery metadata. Optional SDK imports remain outside the package root.

Local diagnostic tests: 21 standard SDK stdio/HTTP/extension cases passed in
72.45 seconds; 121 affected signed-service, task lifecycle, durable provider and
adapter/supervisor cases passed in 72.96 seconds; 101 package/optional import and
C-08 boundary cases passed in 46.79 seconds. The new extension wire case checks
actual HTTP envelopes, task/name headers, reconnect, bounded/foreign updates,
fallback negotiation, private direct access and exact Skill bytes/digests.
The original TypeScript baseline remains separate from Tasks-client acceptance.

Eight signed supervisor cases plus one actual Julia standard-CLI Tasks case
passed in 102.63 seconds. The native case returned task handles in 133 ms and
77 ms across connections, then used real Julia execution. A squares calculation
charged 2,488 measured numerical milliseconds, one trial and 3,464 retained bytes;
its completed result and operation identity were identical after reconnect.
Separate Tasks cancellation and active stdio EOF both stopped Julia and its child
process, persisted CANCELLED and observed exact container cleanup. Each retained
an unknown 120,000 ms/270,598,144-byte reservation; these are not measured work
or a refund. The ledger total is three trials, 242,488 ms and 541,199,752 bytes
including those reservations, with zero provider/reference calls. Six existing
ledger rows (trial plus numerical per execution) remained, none RESERVED.

This native diagnostic used image
`sha256:6ff4bcfcce65d258f9ec957cbd1d31841f92a4e7f58401da03d8a859f1699f8b`,
the same immutable Julia parent/bootstrap with a locally distinct raw builder
source pin from Windows CRLF bytes. Its normalized LF source equals the C-CORE-07
builder; no runtime/source Git change or old-image relabeling is claimed.
External signing/registration and public fixture composition are explicit
engineering fixtures; CLI main, admission, grant freeze, owner lock, task store,
SDK, real carrier, image checks and cleanup execute normally. This is not an
agent-host learning campaign or production authentication acceptance.

Required CI runs the supervisor and protocol cases through `scripts/dev/ci.sh`
and the actual native Tasks case through `scripts/dev/julia_worker_service.sh`.
Working operator and external-client commands are in `carbon/miner_mcp/README.md`.
Canonical checks and normal tested-head delivery remain required. GPU/TPU,
protected use, scientific/security qualification and paid agent usefulness remain
outside this ticket's earned maturity.

At source head `4ca8722fba8ef50274ca87ac50f54263e6ce0f4a`, an isolated LF
checkout passed all 276 invariants in 36.66 seconds, collected all 6,557 tests
across every test directory, and passed strict Python 3.10 Ruff and Black checks
for all 18 changed Python files. A fresh offline wheel imported the new Tasks
and Skills modules outside the checkout while optional MCP/AnyIO/Pydantic/
Starlette/Uvicorn/httpx2 imports were actively rejected. The existing miner_mcp
namespace still requires Cryptography and NumPy through its established source
owners; this is not a zero-dependency claim for that namespace. The final current
guidance passed three stdio tests in 61.64 seconds and the independent locked
TypeScript client passed in 38.36 seconds. These are native diagnostics, not
substitutes for required canonical CI or paid real-agent learning evidence.
