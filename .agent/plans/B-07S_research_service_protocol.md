# B-07S exact research-service protocol plan

**Ticket:** B-07S — Exact miner research service protocol
**Branch:** `agent/b-07s-research-service-protocol`
**Starting base:** `f42b9b191bc414ebfd4d3e6e93afd4e0f608e936`
**Starting tree:** `51d183cde06cf4da8f55170137d2d9f5c360326d`
**Primary Hub map:** `WAVE-B/B-07S`
**Scope:** protocol specification, ratification evidence, conformance validation,
status/Hub reconciliation, and delivery only; no B-07A–G runtime implementation.

## Authority and eligibility

Current `origin/main` is the normal merge of B-E3 PR #90. Its accepted head
passed Delivery preflight, the pinned canonical environment, Development Hub
validation, and `Merge gate`. The merged Wave register records B-E3 and B-06
`done` in their bounded scopes, preserves B-05's historical `in_progress`
delivery record with no active work, and names B-07S next, `todo`, and
unstarted. Open PRs #40, #83, and #84 do not change this sequence.

The applied authority set is root `AGENTS.md`, `CONSTITUTION.md`,
`.agent/INVARIANTS.md`, `.agent/WAVE.md`, `.agent/WAVE_B.md`, the B-07S ticket,
`DELIVERY_PROTOCOL.md`, `DELEGATED_DECISION_PROTOCOL.md`, the B-07R research
contract, B-02A/B/C contracts and decisions, A2/A3/A9 public contracts,
`Build_Out.md`, its constitutional overlay, the current maturity ledger, and
the Development Hub maintenance contract and data sources.

## KEEP / WRAP / REPAIR / REPLACE

| Classification | Disposition |
|---|---|
| A2 `TrainingStrategy`, `ValidationResult`, A7 `StrategyHash` | KEEP exact identities and owner semantics. |
| B-02A authored refs, especially `TrainingSupportContractRef` | KEEP and bind their existing field/profile grammar directly. |
| B-02B compiler results, `TrainingSamplingPolicyRef`, and `ResolvedConstructionPlanRef` | KEEP; the v2 protocol wraps them without redefining compilation. |
| B-02C `ResearchResourcePolicyRef`, `ResourceClassRef`, and static assessment | KEEP; B-07E wraps them for inspection/forecast wire projection. |
| A9 `McpService` and official `submit`/`get_submission_result` | KEEP unchanged in `carbon_protocol_v1`; never import them into v2. |
| B-07R architecture prose | WRAP with one exact v2 protocol; do not rewrite its semantic ownership. |
| Missing exact v2 wire/lifecycle/provider contract | IMPLEMENTATION_LAG owned by this specification ticket; no conflicting runtime type exists. |
| Real science, security, rights, signing, identity, quotas, economics, transport, and production values | NEW_OWNER_DECISION_REQUIRED for their later capability; represent them as explicit unavailable seams. |

No repository definition requires `REPLACE`. `PublicScorePolicyRef` and the
v2-only manifest/prior/task refs are new shared protocol nominals because no
current exact owner type exists; they do not replace an existing authority.

## Delivery slices

1. Author one normative service protocol with exact namespaces, operations,
   type/ref registry, canonical profile, bounds, errors and precedence.
2. Freeze the task lifecycle, idempotency, cancellation races, polling,
   infrastructure failure, retries, and immutable terminal receipt behavior.
3. Freeze prior exact/active lookup, atomic snapshots, genesis sentinel,
   acyclic transition identity, and context/capability separation.
4. Add a machine-readable conformance index inside the normative Markdown and
   a repository invariant test covering the important negative boundaries.
5. Record B-07S material decisions and notify issue #42 without waiting.
6. Reconcile the ticket/evidence, Wave/Wave-B state, maturity ledger, Hub source
   and generated projections. B-07A becomes next only after the B-07S delivery
   predicate normally merges.
7. Run focused document/invariant/Hub diagnostics, inspect the complete diff,
   then push one ready PR for one applicable GitHub acceptance and guarded
   normal merge.

## Validation and maturity

Local canonical execution is unavailable: the host has no Docker executable
and does not have the repository-pinned Python 3.11.16 installed. This will not
be retried. Native system-Python checks are diagnostic only; GitHub's pinned
environment supplies canonical acceptance.

B-07S can earn only `SPECIFIED / RATIFIED` for the engineering protocol.
`IMPLEMENTED`, `SCIENTIFICALLY_QUALIFIED`, `SECURITY_QUALIFIED`,
`NETWORK_QUALIFIED`, `COMMERCIALLY_VALIDATED`, `PRODUCTION_QUALIFIED`, and
`LIVE` remain `NO`.
