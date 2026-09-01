# Agent decisions log

## 2026-09-01 — OWNER-NET-01: post-Wave-B Bittensor wiring and treasury-before-mainnet roadmap

**Exact decision base.** This prospective roadmap decision is authored from
`origin/main` commit `7161fe3c4a04821b7f676ab006bd5d313d0442d2`,
tree `619e366dead2288ccfd312f54ad09f17f86a1c62`, under
`GOV-NET-01`. It leaves B-04 selected `in_progress`, preserves the current
Wave-B implementation order and completion predicates, and creates no
implementation authority for Waves C, H, or I.

**Owner-selected launch-critical sequence.** Real Bittensor integration begins
after Wave B:

```text
Wave B unchanged
→ Wave C0 Bittensor/network foundation
→ G2 LOCALNET_READY
→ Wave C1 real scientific vertical
→ Wave C2 temporary winner-triggered direct testnet weights
→ G3 TESTNET_ALPHA_DIRECT_WEIGHTS
→ Wave D first exact scientifically qualified Challenge
→ G4 QUALIFIED_TESTNET
→ Wave H frontier promotion and finality
→ Wave I treasury routing, scientific-economic ledger, and settlement
→ G6 TREASURY_SETTLEMENT_QUALIFIED
→ G7 MAINNET_MECHANISM_COMPLETE
```

G5 `MAINNET_DEPLOYABLE` may establish infrastructure, key, custody, operator,
and release readiness while economic activation stays off. Waves E, F, and G
may begin after Wave D in parallel and do not block H/I. A direct
score-to-weight mainnet beta is no longer an authorized preferred branch.
Mainnet economic activation requires the Wave-H/I treasury path.

**Ownership boundary.** Bittensor owns hotkey/coldkey identity, UID
registration, metagraph discovery, validator/miner presence, stake/network
state, chain transactions, weight publication, and eventual emissions rails.
Carbon owns Challenge identity, Miner MCP semantics, candidate commitments,
research protocol, official evaluation and hidden exam, producer-independent
reconstruction, reference/truth, measurements, scientific score, leader
determination, frontier promotion, economic entitlement, and per-Challenge
settlement. This extends the compatible A0 adapter decision and B-07R-D1/D6
service-boundary decisions; it does not reopen them.

The permitted dependency direction is:

```text
Carbon scientific result
→ Carbon policy event
→ nominal typed chain intent
→ ChainAdapter / WeightPublisher
→ Bittensor
```

A Bittensor SDK/metagraph/extrinsic object may not enter scientific scoring
authority. The future publisher may not accept arbitrary score dictionaries,
raw scientific result objects, or a caller-selected authority Boolean such as
`emission_capable=True`.

**Miner and validator wiring.** Bittensor identity/discovery and
hotkey-authenticated application transport wrap the Carbon Miner MCP; they do
not replace or redefine the MCP. Miner-facing surfaces remain practice,
research, submit, and result only; official exam material remains
inaccessible. The validator path is authenticated intake → commitment and
identity verification → durable queue/state → producer-independent
reconstruction → protected official exam → MeasurementContracts → Score Pack
→ signed EvaluationReceipt → Carbon policy decision → typed chain intent.
Validator orchestration hosts and coordinates the exam without defining
scientific merit.

**Wave-C decomposition.** C0 reconciles the future NET family as NET-0
topology/threat model/policy; NET-1 pinned ChainAdapter, metagraph,
wallet/UID, and classified errors; NET-2 authenticated transport and replay
protection; NET-3 candidate commitment, availability, and hotkey binding;
NET-4A nominal localnet/testnet/treasury intents; NET-4B bounded compiler,
chain constraints, no-winner sink, readback, and receipts; NET-5 reproducible
localnet E2E; and NET-6 node/runtime/images/secrets/recovery/observability.
C1 owns the real declarative scientific vertical, isolation, protected truth,
measurements/scoring, receipts, orchestration, authenticated MCP E2E,
secondary execution/disagreement, and free-riding simulation. C2 owns C-W1
`TestnetWeightEligibilityEvent`; C-W2 winner-only expiry, supersession, and
no-winner policy; C-W3 chain publication, agreement, readback, and recovery;
and C-W4 the complete Testnet Alpha Report.

**Temporary testnet policy.** Raw score magnitude never maps to Bittensor
weight magnitude. A Challenge-local score/rank determines only whether a new
eligible leader exists. For the initial one-Challenge testnet, a new eligible
leader creates a bounded, expiring `TestnetWeightEligibilityEvent`. The event
binds at least network identity, netuid/mechanism, Challenge identity/version,
candidate and method identity, miner hotkey/UID, source EvaluationReceipt
commitment, test-policy version, previous leader, valid-from chain/tempo, and
valid-through chain/tempo or equivalent expiry. It is explicitly `NON_LIVE`,
`NON_SETTLING`, and `TESTNET_ONLY`.

An active eligible winner activates only the winner participant allocation
and zeroes other participant miners. With no active winner, an approved
non-paying sink allocation is active and every participant miner is zero.
No eligible leader, expiry, contest, indeterminacy, validator disagreement,
candidate unavailability, identity mismatch, reference or infrastructure
failure, supersession, or invalid chain binding must move to that non-paying
state; omitted or invalid weights are not the policy. The exact sink chain
identity/custody and reward-window duration remain owner-selected inputs.

The sink must be registered and bound to the exact network,
netuid/mechanism, and test-policy version; auditable and readback-verifiable;
incapable of conferring participant, miner, or validator benefit, scientific
merit, frontier standing, settlement entitlement, or redistribution to
participants; and fail-closed/non-paying through expiry, recovery, and
invalid-readback handling. Those are required properties, not a selected
production identity or custody topology.

Only exact real C2 provenance may create the event. Fixture, mock, practice,
estimate, PriorPack, scaffold, partial reconstruction, failed infrastructure,
failed reference, cancelled/deferred work, indeterminate/contested comparison,
unbound candidate bytes, wrong hotkey/UID, and stale/superseded receipt
identities are ineligible. The nominal intent families are
`StructuralLocalnetWeightIntent`, `TestnetWinnerWeightIntent`, and
`TreasuryRoutingWeightIntent`; none can substitute for another.

Before Wave D, G3 proves network integration only and remains
`NOT_FRONTIER_QUALIFIED` and `NOT_MAINNET_ELIGIBLE`. After Wave D, qualified
Challenge ranking may feed the same temporary testnet policy, but it still cannot create a
`FrontierAdvanceEvent`. Multiple Challenges may share direct testnet
allocation only under a registered fixed `TESTNET_ONLY` per-Challenge slice,
or after treasury settlement exists. Cross-Challenge allocation never derives
from score magnitude.

**Frontier, treasury, and validator economics.** Wave H alone owns
`FrontierBaseline`, `FrontierRecord`, `LeaderReplacementPolicy`,
`FrontierPromotionExam`, `FrontierAdvanceEvent`, `ChallengeSetEpoch`, appeals,
and finality, preserving `SUPERIOR`, `NOT_SUPERIOR`, and `INDETERMINATE` plus
the registered one-event-per-Challenge-settlement-window direction. Wave I is
mainnet-critical: I-00 treasury receiver/custody/economic contract; I-01
immutable accrual/scientific-economic ledger and `SettlementObligation`; I-02
`TreasuryRoutingWeightIntent` and treasury publication; I-03 exactly-once
miner settlement; I-04 validator execution/audit economics; and I-05
direct-testnet-to-treasury migration plus settlement soak.

Production chain vectors contain no raw candidate score, hidden measurement,
Challenge-specific score magnitude, scientific threshold, or winner payout
amount. The scientific-economic path is qualified Challenge evidence → fresh
frontier promotion → `FrontierAdvanceEvent` → `SettlementObligation` →
treasury settlement. The roadmap reserves `ValidatorAssignment`,
`ValidatorExecutionReceipt`, `ValidatorAuditReceipt`,
`ValidatorServiceObligation`, and `ValidatorServiceSettlement` so a copier
cannot claim Carbon-controlled validator-service compensation without valid
execution/audit evidence.

**Migration rehearsal.** Before mainnet, stop new direct-winner events; let
active events expire or revoke them under registered policy; confirm the
no-winner sink; activate treasury-routing weights; verify accrual; exercise
test frontier events and obligations; settle and reconcile. Evidence must
show no direct/treasury overlap, no double benefit, science survives treasury
outage, retries do not duplicate payouts, UID/key rotation preserves
accounting, chain failure cannot rewrite merit, rollback is non-paying, and
there is no automatic mainnet fallback to direct-winner weights.

**Superseded lower-authority statements.** The following are prospectively
superseded rather than erased: network implementation in parallel with Wave B;
raw/lean score magnitude → weight/emission magnitude; a generic `WeightIntent`
or raw-score publisher; optional direct-weight mainnet beta / old
`G6 MAINNET_BETA`; Wave H gated by E/F/G; omission/invalid weights as
no-winner behavior; treasury settlement as optional before mainnet; and an
absolute “all non-LIVE receipts can never cause any test weight” shorthand.
The last is narrowed only for exact real C2 `TESTNET_ONLY`, `NON_SETTLING`
integration; non-LIVE evidence remains incapable of production emissions,
frontier authority, settlement, or mainnet activation.

**Alternatives rejected.** Start network code before Wave B closes; make
Bittensor the MCP; import SDK objects into scoring; publish raw scores;
continue paying a stale winner when no eligible winner exists; accept fixture
or incomplete provenance; derive cross-Challenge allocations from scores;
let a testnet event create frontier state; activate mainnet direct-winner
weights; or compensate validators without execution/audit evidence.

**Reserved inputs and evidence.** Exact reward-window duration; exact sink
identity/custody; validator quorum, stake, assignment, and audit rate;
treasury custody/topology; payout/compensation values; operational SLOs;
security acceptance; Challenge qualification; and chain deployment/activation
remain human/evidence owned and fail closed. No value is invented here.

**Implementation, review, and reversibility.** The decision is implemented as
planning/governance only by `GOV-NET-01` and the authority paths in its exact
manifest. The issue #42 lead notification and PR/final receipt are dynamic
external evidence. A later prospective reviewed decision may revise the
roadmap; it may not rewrite this history or infer implementation from it.

```text
SPECIFIED: YES
OWNER_DIRECTION / RATIFIED_ROADMAP: YES after merge under current governance
BITTENSOR_IMPLEMENTED: NO
TESTNET_WEIGHTS_IMPLEMENTED: NO
NETWORK_QUALIFIED: NO
SCIENTIFICALLY_QUALIFIED: NO
TREASURY_IMPLEMENTED: NO
ECONOMICALLY_QUALIFIED: NO
LIVE: NO
MAINNET: NO
PRODUCTION_QUALIFIED: NO
```

## 2026-09-01 — OWNER-DX-01: Carbon development throughput hardening

**Affected ticket and sequence.** Insert B-01F after PR #72's merged B-04
contract and before B-04 runtime implementation:

```text
B-04 bounded engineering contract ratified
→ B-01F development throughput hardening
→ B-04 runtime implementation
```

B-01G is a future non-blocking tooling proof. This sequencing decision does
not reopen, demote, or amend B-04-D1 through B-04-D10 or
`Design_Specs/Reference_and_TruthAsset_Contract.md`.

**Problem.** Carbon's prior process required repeated owner prompts, separate
contract merges without a substantive reason, commits used only to retrigger a
corrected PR declaration or store external completion facts, full expensive CI
for every authority-only change, host-specific validation paths, and broad
generated-Hub churn. Those costs did not add scientific, security, rights,
protocol, or production assurance.

**Owner-selected approach.** Make repository authority and machine enforcement
implement the normal lifecycle:

```text
working contract and decisions
→ vertical implementation slices
→ canonical validation
→ exact-head scope-required CI and Merge gate
→ exact-head Greptile Review
→ valid-finding repair and zero unresolved threads
→ normal exact-expected-head merge
→ ordered-parent/reviewed-tree/exact-main verification
→ completed normalized external receipt posted
→ bounded closeout and next ready ticket
```

Greptile is the routine correctness review Carbon waits for. Human and domain-
lead oversight is asynchronous unless current authority explicitly reserves a
value or acceptance decision to a human. Human silence is not a gate. An
explicit applicable `CHANGE`, `BLOCKED`, or `REQUEST_CHANGES` pauses the
affected change; every human-reserved science, security acceptance, rights,
economics, qualification, `LIVE`, launch, deployment, and production decision
remains unavailable and fail closed.

Unless owner direction explicitly says to stop before merge, an end-to-end
ticket session normally merges an unchanged clean reviewed candidate with an
exact expected-head guard, verifies exact main, posts the completed normalized
external receipt, closes the bounded ticket, and continues to the next ready
ticket without another owner prompt solely for the merge. Normal merge commits
are required; squash, rebase-merge, auto-merge, and routine bypasses are
prohibited.

**Delivery and evidence model.** One pull request per ticket is the default:
working contract/decisions/plan first, coherent vertical implementation/test
slices later, and final-tree review over all of them together. A separate
contract PR is allowed only for a contract-only ticket, a real concurrent
downstream immutable-contract need, an established cross-domain public-
interface freeze, or another concrete reason recorded by current sequencing.
Ticket size alone is not a reason. Material contract changes are prospective
and the final tree is reviewed again.

Stable scope, authority, base, decisions, contracts, expected manifest,
commands, invariants, maturity ceiling, and conditional predicate remain
tracked. Final head/tree, checks, Greptile, threads, merge topology, exact-main
checks, notification, maturity, and next-ticket facts use the normalized
external completion receipt. No commit may exist merely to record/retrigger
those dynamic facts.

**Machine-enforced implementation.** B-01F adds delivery hygiene, one canonical
cross-host wrapper, strict changed-path scopes with unknown paths failing to
full runtime acceptance, an always-present `Merge gate`, live PR-body/head Hub
validation, bounded semantic Hub fan-out, a versioned main ruleset and admin
`--dry-run`/apply tool, a concise launcher, and the normalized PR declaration.
The live ruleset is applied only with repository-administration permission;
otherwise the artifact and smallest manual owner action remain explicit.

**Alternatives rejected.** Preserve prompt-only merge permission; wait for
routine human approval or silence; continue one contract PR plus one
implementation PR by default; commit external check/merge identities; use
empty commits as validation events; call native host output canonical; run full
runtime CI for every derived/document-only change; trust an unclassified path;
or suppress legitimate Hub changes with an arbitrary count.

**Interfaces, invariants, and downstream effect.** Repository governance, CI,
Hub validation/rendering, PR declarations, and developer commands change.
Carbon runtime and domain canonical bytes do not. Runtime-bearing changes keep
full acceptance; explicit contract and derived-document scopes receive only
their appropriate gates; unknown paths fail closed. B-04 resumes only after
B-01F's exact reviewed normal merge, exact-main `Merge gate`, and posting of the
completed normalized external receipt. B-01G does not block it.

**Reversibility and migration.** Delivery scripts, classifiers, workflows, and
protocol prose are prospectively reversible through a later normally reviewed
ticket. Merged ticket history and external receipts are not rewritten. A
future scope optimization must add evidence rather than silently weaken the
fail-closed classifier or runtime gate.

**Implementation and notification.** Implemented by the B-01F single-ticket
candidate under `.agent/tickets/B-01F_development_throughput_hardening.md`,
`.agent/plans/B-01F_development_throughput_hardening.md`, and the paths in its
exact final manifest. The issue #42 lead notification and final PR identity are
dynamic external evidence. A lead change supersedes this decision through the
same files and a new reviewed repository decision; an explicit
`DEFER_TO_OWNER` routes the complete package to issue #41.

**Reserved inputs.** Live GitHub ruleset application requires repository-
administration permission. B-01F supplies no human-reserved scientific,
security, legal/rights, economic, qualification, `LIVE`, launch, deployment,
or production value.

## 2026-09-01 — B-04 decision-series status

> **B-04-D1 through B-04-D10 status: RATIFIED BOUNDED ENGINEERING-CONTRACT
> DECISIONS.** PR #72's external completion receipt establishes exact-head
> checks and Greptile, normal reviewed-tree-preserving merge, and exact-main
> checks without copying their dynamic identities into this tracked decision.
> `OWNER-DX-01` pauses runtime behind B-01F but does not amend these decisions.
> Every real reference choice and qualification remains reserved and fail
> closed.

## 2026-09-01 — B-04-D1: Keep the canonical evaluation package and one-way ownership

**Recommendation.** `KEEP + WRAP` the existing reserved `carbon.evaluation`
namespace as B-04's future package boundary. A later implementation may depend
one way on explicit `carbon.authoring` canonical/cases/evidence/errors/model/
primitives/refs submodule seams, `carbon.registry.model.ChallengeKey`, and the
Python standard library. It must not use the registry root, lifecycle, store,
gate, or artifact-I/O APIs. It must
not import B-03 generators, scoring, TrainEval, cards, fees, MCP, leaderboard,
qualification, retired namespaces, optional numerical dependencies, or dynamic
I/O. This contract PR adds no production module and does not freeze the later
module split.

**Rationale.** `carbon.evaluation` is already a canonical code-authority root,
an installed-wheel import seam, a B-01 `KEEP` boundary, and the repository's
recorded owner for reference, measurement, uncertainty, Dossier, and later
orchestration work. Its current one-line package marker proves location only,
not B-04 capability. B-03's invariant suite also requires every other Carbon
package to avoid reverse-importing generators.

**Rejected alternatives.** A new `carbon.reference` or `carbon.references`
top-level package would duplicate the existing owner and require an unnecessary
authority migration. Putting truth under `carbon.generators` would let a
generator certify itself. Putting it under scoring, TrainEval, registry,
qualification, Julia, or a retired namespace would collapse separate owners.

**Interfaces and invariants.** Future B-04 types live below
`carbon.evaluation`; exact `CanonicalChallengeCase` composition crosses by
B-02A value/ref, never by a generator import. Reference code cannot construct
score input, mutate lifecycle/registry state, activate qualification, or use a
generic runtime/service boundary. The future package must define a curated
`__all__` exposing only audience-safe policy/role/outcome/projection contracts;
B-04-D11 freezes its exact names and order before runtime code. Until then no
exact root-export claim exists. Protected case refs, requests, resolution
records, grants, runs, comparisons, artifacts, assets, and admission
capabilities remain submodule-only.

**Downstream.** B-05 may add separately owned measurement behavior under the
same top-level namespace; B-06 owns Dossier/qualification; B-07F consumes only
fixture reference assets; B-E2 exercises implementations and failures.

**Reversibility and migration.** The documentation choice is cheap to revise
before implementation. Moving implemented canonical objects later would be a
high-cost identity/import/history migration and requires a prospective
decision. Retired Julia/PoC paths remain quarantined until wrapped.

**Exact change path.** Authority commit A changes the coordinated eleven-file
B-03 closeout/B-04 transition: Wave, board, handoff, decisions, B-03 ticket/
plan/evidence, B-04 ticket/plan/evidence, and
`Design_Specs/Reference_and_TruthAsset_Contract.md`. Development Hub source and
generated output follow separately in commit H under the merged maintenance
rule.

**Reserved inputs.** Exact future module layout, runtime dependencies,
provider/service topology, resource values, security, operations, and every
real reference method remain unavailable.

## 2026-09-01 — B-04-D2: Requirements for B-04 canonical identity, refs, and prospective history

**Recommendation.** Reserve the closed B-04 v1 top-level identity/ref inventory
for precomputed source manifest, policy and entry, policy composition,
primary/witness request, resolution, nominal primary/witness grant, run,
comparison, reference artifact, fixture asset, admission-grant issuance,
admission grant/decision, and `TruthAsset`. Fix schema
version `1.0`, profile `carbon_reference_truth_canonical_v1`, and domain header
`carbon.reference-truth.canonical.v1\x00`. Inherit B-02A's exact primitive,
NFC/control/surrogate, Int64/UInt64, finite/positive-zero Float64, strict
ordering/duplicate, unknown-tag, and decoder-ceiling semantics without
widening its top-level registry. Material meaning changes create a prospective
version/supersession; history is never reinterpreted.

This decision establishes canonical requirements and reserved ref names, not
implemented bytes. Before the first runtime model, a separately recorded and
notified B-04-D11 decision must freeze every v1 record's complete field
order/type registry, exact outcome/reason compatibility matrices, and the
exact ordered `carbon.evaluation.__all__` tuple. Only then may implementation
claim exact canonical identity or root export surface.

**Rationale.** A policy or asset must bind the exact Challenge, case, physical
job, population, role, implementation, environment, method/configuration,
artifact, applicability, uncertainty, provenance, and qualification meaning.
Syntactic IDs or a successful process cannot carry that graph.

**Rejected alternatives.** Generic dictionaries/JSON dumps, authoring-registry
widening, generator-profile reuse, caller-supplied hashes, mutable aliases,
implicit defaults, schema coercion, and latest-version lookup all permit
identity confusion or silent historical change.

**Prospective/runtime graph rule.** A policy entry or composition binds only
prospective scope, source/method/environment constraints, expected artifact
schema, and required evidence policies. A request adds the exact case,
answer-key target, and role-specific primary/witness execution target. On an
issued path a grant adds the authorized implementation/environment/
configuration, then the resolution record points backward to that completed
grant ref; a non-issued resolution carries typed grant absence. A run points
backward to the request, grant, and resolution and adds the terminal outcome,
realized artifact digest, provenance, and resource receipt. A resolver's
pre-existing issuer/capability identity is never the later resolution-record
ref. An entry or composition never binds its future request, run, or realized
artifact, so the content-addressed graph is acyclic.

**Interfaces and invariants.** Fixed field order; exact built-in types;
subclass, Boolean-as-integer, non-finite, missing/extra/duplicate/trailing,
oversized, and over-deep input rejection; deterministic set ordering; explicit
resource bounds; constant-time digest comparison; defensive reconstruction;
no hostile `repr`, `str`, pickle, reflection, mapping, URI, path, or callable.
A ref proves shape and content identity only, not authority.

**Downstream.** B-05/B-06 consume stable refs; B-E2 tests stale/cross-binding
responses; future registry integration adds only a prospective Challenge
binding.

**Reversibility and migration.** New schema versions are additive and
prospective. Re-encoding historical objects or changing a digest meaning is
forbidden; migration issues new refs and preserves the old graph.

**Exact change path.** The contract's identity/canonicalization sections and
the later `carbon.evaluation` implementation boundary.

**Reserved inputs.** The inherited 16,777,216-byte document, 65,535-byte
payload, 65,535-item, and depth-64 maxima are hostile-input engineering decoder
ceilings, not production policy. Tighter service limits, storage, retention,
signatures, authentication, cache, and migration policy remain owner inputs.

## 2026-09-01 — B-04-D3: Separate evidence kind, authority function, and source class

**Recommendation.** Reuse B-02A's exact payload-bearing
`EvidenceRoleBinding` as the evidence-kind axis, including the mandatory
`hybrid_role_ref` only for `REGISTERED_HYBRID`. Add
an orthogonal closed B-04 authority-function axis (`PRIMARY`,
`CORROBORATING_WITNESS`, `VERIFICATION_ANCHOR`, `VALIDATION_ANCHOR`,
`REGISTERED_COMPONENT`) and a closed source-class axis (`DIRECT_REGISTERED_SOURCE`,
`EXPERIMENTAL_DATASET_OR_INSTRUMENT`,
`INDUSTRIAL_OR_CUSTOMER_HOSTED_REFERENCE`,
`QUALIFIED_SURROGATE_OR_ACCELERATOR`). A separate target-level composition
kind is `SINGLE_ENTRY` or `REGISTERED_HYBRID_POLICY`; a hybrid is an ordered
composition of at least two distinct `REGISTERED_COMPONENT` entries whose
closed composition authority is `PRIMARY` or `CORROBORATING_WITNESS`. Every
prospective entry binds exactly one value on all three axes. Named roles are
exact profiles over the tuple, so an industrial primary, surrogate witness, or
experimental validation anchor is expressible. Compared primary/witness
targets have disjoint entry refs. Labels never self-authorize.

Every target is closed within one exact policy version. The policy's ordered
entry, composition, and registered-witness-target inventories and every
expanded target are duplicate-free by canonical semantic identity. Single
targets occur exactly once in that policy's entry tuple; composition targets
occur exactly once in its composition tuple; and each distinct composition
member occurs exactly once in both its member tuple and the same policy's entry
tuple. All cross-bind the same Challenge and scientific scope. Expanded
primary and compared-witness entry sets are disjoint; external, duplicate,
cross-policy, cross-version, cross-scope, or role-mismatched refs reject.

**Rationale.** Analytic, semi-analytic, manufactured, numerical, experimental,
industrial, and hybrid describe evidence form, not primary/witness authority.
The three-axis model preserves what each source supports and cannot support;
separate composition preserves how several registered components jointly act.

B-02A `REGISTERED_HYBRID(hybrid_role_ref)` remains the exact evidence binding
of one B-04 entry and cannot create B-04 `REGISTERED_HYBRID_POLICY`. Conversely,
a B-04 composition does not synthesize a B-02A hybrid role or owner ref. A
single-member composition rejects and must use `SINGLE_ENTRY`; D11 freezes the
payload/cross-binding compatibility rules.

**Rejected alternatives.** One scalar “reference rank,” a mixed enum that
places authority and delivery classes in one slot, source-category authority,
source-count voting, `primary=True`, arbitrary strings, and a generic hybrid
list would allow relabeling or unsupported promotion.

**Interfaces and invariants.** Witnesses cannot replace/promote themselves;
agreement cannot qualify a source; a generator-under-test is never a reference
role; MMS normally supports verification/convergence only and cannot stand in
for target-population relevance, physical validation, customer context,
engineering qualification, or product fitness. Primary and witness requests
bind closed single-entry or composition execution targets; a witness also
cross-binds the policy's primary answer-key target. Only `PRIMARY` and
`CORROBORATING_WITNESS` targets use the nominal answer-key runners.
Computational composition members are `REGISTERED_COMPONENT`; anchor entries
are evidence-only unless a distinct prospective entry assigns and qualifies a
primary/witness function. Any anchor adapter has a non-answer-key boundary.

**Downstream.** B-05 consumes evidence meaning without widening it; B-06
records non-substitution; B-E2 and B-E3 test/render role boundaries.

**Reversibility and migration.** Adding a role requires a versioned contract
and policy migration. Historical combined “analytic or manufactured” and
“reference rank” wording is `DOCUMENTATION_LAG`, not a reason to collapse the
model.

**Exact change path.** Contract role model, B-04 ticket/plan/evidence, and
future B-04 model/canonical modules under `carbon.evaluation`.

**Reserved inputs.** The actual primary/witness/anchor assignment, industrial
or customer rights, and hybrid composition are `NEW_OWNER_DECISION_REQUIRED`.

## 2026-09-01 — B-04-D4: Policy-issued nominal primary and witness runner grants

**Recommendation.** Define separate nominal primary and witness requests,
grants, runners, and outcomes. Trusted policy resolution issues a grant bound
to the exact case, policy, answer-key target, role-specific single-entry or
composition execution target, role, implementation, environment,
method/configuration, representation, request/idempotency, resource, and
disclosure identities. The runner validates that exact grant before its
provider boundary. There is no generic `truth_mode`.

Resolution produces an exact content-addressed record with one closed
outcome: primary grant issued, witness grant issued, policy incomplete, role
unavailable, not applicable, unsupported, applicability unresolved,
qualification unavailable, resource authorization unavailable, or
identity/provenance failure. On an issued path the resolver constructs the
one-use nominal grant from its pre-existing issuance identity and then records
that completed grant ref; every other record contains typed grant absence and
no fabricated run. A closed subordinate reason distinguishes missing
primary, incomplete entry, unregistered role, case applicability/support,
unavailable applicability assessment, qualification, resource policy versus
capacity, identity, and provenance, with exact outcome/reason compatibility
reserved for B-04-D11.

Resolution reason precedence is total, in this exact order:
`RESOLUTION_IDENTITY_MISMATCH`, `RESOLUTION_PROVENANCE_INVALID`,
`POLICY_PRIMARY_MISSING`, `POLICY_ENTRY_INCOMPLETE`, `ROLE_NOT_REGISTERED`,
`CASE_NOT_APPLICABLE`, `CASE_UNSUPPORTED`,
`APPLICABILITY_ASSESSMENT_UNAVAILABLE`,
`QUALIFICATION_BINDING_UNAVAILABLE`, `RESOURCE_POLICY_UNAVAILABLE`,
`RESOURCE_CAPACITY_UNAVAILABLE`, then
`RESOLUTION_REQUIREMENTS_SATISFIED`.

**Rationale.** A caller-selectable mode, solver, or tolerance lets execution
choose scientific authority. Nominal types make primary/witness confusion and
unregistered method selection mechanically rejectable.

**Rejected alternatives.** `run(mode, solver, tolerance, payload)`, arbitrary
PDE strings, callables, code, paths, URIs, package requests, executable names,
fixture/production flags, cache bypass, and caller-selected fallback/retry.

**Interfaces and invariants.** A runner computes only its registered role; it
does not choose cases, population, fidelity, qualification, comparison,
measurement, score, or disclosure. Process success, language, library, solver
name, cost, speed, and nominal tolerance grant no authority.

Only exact primary or witness entries/compositions enter these runner
interfaces. Composition members remain registered components.
Verification/validation anchors require separately owned nominal evidence
adapters and cannot alias an answer-key runner. The resolver's issuance
identity is a pre-existing issuer/capability identity and token, never the
resolution-record ref, so a record-to-grant cycle is impossible.

**Downstream.** The later B-04 implementation supplies the minimal standard-
library deterministic primary/witness fixture runners and fixture assets that
B-07F consumes. B-E2 owns Julia/service adapters and expanded runtime, timeout,
version-mismatch, transport, process, and failure injection. C-04 later owns
protected real adapters.

**Reversibility and migration.** New runner families require new nominal types
and policy versions, not aliases or enum members accepted by existing calls.

**Exact change path.** Contract runner section and later B-04 protected runner
interfaces under `carbon.evaluation`.

**Reserved inputs.** Solver choice, method/configuration, grid, timestep,
tolerance, precision, hardware, timeout, retry, resource, and service topology
remain unavailable.

## 2026-09-01 — B-04-D5: Total run/comparison outcomes and failure attribution

**Recommendation.** A run records exactly one of `SUPPORTED`,
`UNCERTAINTY_UNRESOLVED`, `CONDITIONING_UNRESOLVED`,
`APPLICABILITY_UNRESOLVED`, `NOT_APPLICABLE`, `UNSUPPORTED`,
`NUMERICAL_FAILURE`, `MALFORMED_OR_PROVENANCE_FAILURE`,
`INFRASTRUCTURE_FAILURE`, or `CANCELLED`. A separate comparison records
`AGREEMENT_WITHIN_REGISTERED_POLICY`, `CONTESTED_DISAGREEMENT`, or
`COMPARISON_INDETERMINATE`. Neither runner self-declares comparison or
independence.

Each non-supported post-grant run also binds one closed subordinate reason
covering not-applicable/unsupported, uncertainty/conditioning, invalid
request/grant, numerical nonconvergence/invalidity, malformed result,
provenance/version/identity mismatch, dependency/transport/process failure,
capacity/resource limit, timeout, or trusted cancellation. Run-reason
precedence is total in this exact order: `REQUEST_OR_GRANT_INVALID`,
`VERSION_OR_IDENTITY_MISMATCH`, `PROVENANCE_INVALID`,
`TRUSTED_CANCELLATION`, `TIMEOUT`, `RESOURCE_LIMIT`, `CAPACITY_UNAVAILABLE`,
`DEPENDENCY_UNAVAILABLE`, `TRANSPORT_FAILURE`, `PROCESS_FAILURE`,
`PROVIDER_RESULT_MALFORMED`, `NUMERICAL_NONCONVERGENCE`,
`NUMERICAL_INVALID_RESULT`, `POLICY_ENTRY_NOT_APPLICABLE`,
`POLICY_ENTRY_UNSUPPORTED`, `APPLICABILITY_ASSESSMENT_UNAVAILABLE`,
`CONDITIONING_EVIDENCE_UNRESOLVED`, `UNCERTAINTY_EVIDENCE_UNRESOLVED`, then
`SUPPORTED` with no failure reason. One atomic terminal claim applies. Missing
primary or another pre-run failure stays in the separate resolution record.

Comparison uses the closed subordinate reasons
`COMPARISON_REQUIREMENTS_SATISFIED`,
`PRIMARY_OR_WITNESS_NOT_SUPPORTED`, `COMPARISON_INPUT_IDENTITY_MISMATCH`,
`COMPARISON_PROVENANCE_INVALID`, `COMPARISON_APPLICABILITY_MISMATCH`,
`COMPARISON_METHOD_UNAVAILABLE`, `COMPARISON_UNCERTAINTY_UNRESOLVED`,
`COMPARISON_DEPENDENCE_UNRESOLVED`, and
`REGISTERED_DISAGREEMENT_EXCEEDED`. Their total precedence is input identity,
provenance, unsupported input, applicability mismatch, method availability,
uncertainty, dependence, registered disagreement, then
`COMPARISON_REQUIREMENTS_SATISFIED`. The record binds the exact primary
answer-key target and disjoint witness target as well as both runs.

**Rationale.** Total typed outcomes preserve missing, uncertain, contested,
scientific-method, malformed, and operational states without fabricating
candidate evidence or a partial answer.

**Rejected alternatives.** `None`, Boolean success, exception-text taxonomy,
one generic failure, failed `TruthAsset`, partial-result success, disagreement
averaging, candidate zero, failed gate, easier-case replacement, or settlement
event.

**Interfaces and invariants.** Every record binds exact request/grant/case/
policy/answer-key target/role-specific execution target/implementation/
environment/artifact/applicability/conditioning/uncertainty/provenance/
resource facts, including ordered component identities for a composition.
Failures expose fixed, typed,
non-echoing, unchained errors and no partial solution payload. Ambiguity
defaults to infrastructure, never candidate science.

**Downstream.** B-02A may consume eligible reference-trigger facts under its
own censoring policy; B-05 rejects non-supported material; B-E2 proves the
runtime matrix; A7/A5 remain unchanged.

The exact eligibility map preserves B-02A's five reasons: contested maps to
disputed; numerical failure to numerical; timeout to timeout; an exact
capacity/limit fact maps to resource limit; a missing resource policy maps to
unavailable; remaining unavailable/inapplicable/malformed/operational facts
map to unavailable; cancellation has no automatic censoring eligibility.
Only an exact terminal record/ref is eligible. Bare absence of the admission-
grant issuer or configured admission authority, and malformed issuer input,
supplies no B-02A trigger unless a separately registered infrastructure
failure ref exists. Because the issuer performs no substantive admission
checks, contested comparison remains a decision-level disputed fact rather
than being collapsed into issuance unavailability.

**Reversibility and migration.** A new terminal meaning requires a contract
version and exhaustive consumer update; unknown values fail closed.

**Exact change path.** Contract outcome/comparison/failure sections and future
B-04 outcome records.

**Reserved inputs.** Real comparison method, acceptable discrepancy,
cancellation/retry mechanics, and owner failure policy remain unavailable.

## 2026-09-01 — B-04-D6: Positive-only TruthAsset admission and distinct fixture assets

**Recommendation.** Treat a structurally valid output as a
`ReferenceArtifact`. Only a separately configured admission authority may
construct a `TruthAsset`, and only from an exact `SUPPORTED` run plus every
eligible artifact, comparison, and qualification binding required by the same
policy. `SUPPORTED` plus artifact absence/ineligibility is an exact rejection,
not an asset. Failed,
uncertain, contested, unsupported, and infrastructure states remain outcomes,
not assets. Fixture output uses a distinct nominal `FixtureReferenceAsset`
that cannot be admitted or relabeled as `TruthAsset`.

Before admission, a distinct trusted grant issuer performs only exact
canonical/cross-binding, issuer-scope, and intended-authority capability
checks over one structurally bound attempted graph. It emits a
content-addressed `TruthAssetAdmissionGrantIssuanceRecord`; a positive record
authorizes a one-use `TruthAssetAdmissionGrant` that binds backward to it, and
the record contains no grant ref. The issuer does not decide run/artifact,
comparison, qualification, provenance/rights, or use/disclosure sufficiency.
The separate authority decides those substantive questions and then emits a
content-addressed
`TruthAssetAdmissionDecisionRecord` with `ADMITTED`, `REJECTED`, `UNAVAILABLE`,
or `INDETERMINATE`; only `ADMITTED` can construct an asset, and the asset binds
the exact issuance, grant, and decision refs. The issuer and admission
authority are distinct; runners, adapters, generators, callers, artifacts, and
the admission authority cannot issue their own admission grant, and the issuer
cannot decide admission.

Issuance reason precedence is exactly
`ADMISSION_GRAPH_CROSS_BINDING_MISMATCH`,
`ADMISSION_GRANT_SCOPE_UNAVAILABLE`,
`ADMISSION_AUTHORITY_BINDING_UNAVAILABLE`, then
`ADMISSION_GRANT_REQUIREMENTS_SATISFIED`. Substantive admission precedence is
exactly `GRANT_INVALID_OR_CONSUMED`, `POLICY_OR_IDENTITY_MISMATCH`,
`RUN_NOT_SUPPORTED`, `ARTIFACT_ABSENT_OR_INELIGIBLE`,
`REQUIRED_COMPARISON_CONTESTED`,
`REQUIRED_COMPARISON_INDETERMINATE`, `QUALIFICATION_UNAVAILABLE`,
`PROVENANCE_OR_RIGHTS_INVALID`, `USE_OR_DISCLOSURE_UNAVAILABLE`, then
`ADMISSION_REQUIREMENTS_SATISFIED`.
Each sequence selects one closed reason before its success state; D11 fixes
compatibility, not implementation-dependent order.

Malformed/noncanonical/unreconstructable issuer input returns a fixed
non-echoing boundary error with no record or grant. Only reconstructable
cross-binding mismatches receive the closed issuance reason. Bare absence of
the issuer or configured admission authority creates no self-issued terminal
ref or B-02A eligibility; a separately registered infrastructure observer/ref
is required. An available admission authority alone records substantive
decisions over the complete submitted attempt graph, including typed artifact
absence.

**Rationale.** This preserves the difference between solver output and an
authority-bounded answer key. It also resolves documentation shorthand that
could imply `TruthAsset` itself carries a failure state.

**Rejected alternatives.** Constructor Booleans, asset-presence success,
self-admission by a runner, Dossier-field completeness, fixture provenance
plus `is_live=False`, failed/empty `TruthAsset`, and subclass/wrapper promotion.

**Interfaces and invariants.** Admission consumes an exact positive authority
echo and binds Challenge/case/policy/answer-key target/primary execution
target/role/run/comparison/implementation/
environment/artifact/applicability/conditioning/uncertainty/correlation/
provenance/rights/disclosure/qualification/limitations plus the exact issuance
record, grant, and decision record. A `TruthAsset` creates no score, LIVE,
frontier, product, network, or economic authority.

**Downstream.** B-06 later owns qualification evidence and signer slots; B-05
may consume only admitted refs; B-07F consumes fixture assets; B-E2 cannot fake
admission.

**Reversibility and migration.** Positive-only semantics are intentionally
strict. Widening admission later requires a high-cost security/science review
and prospective schema version; existing failures remain non-assets.

**Exact change path.** Contract artifact/admission sections and future B-04
admission/fixture models.

**Reserved inputs.** Admission criteria, authorities, qualification evidence,
signatures, keys, and production asset eligibility are `EVIDENCE_REQUIRED` /
`NEW_OWNER_DECISION_REQUIRED`.

## 2026-09-01 — B-04-D7: Explicit support, applicability, conditioning, and uncertainty

**Recommendation.** Bind case-level support/applicability and conditioning
status to exact policy evidence. Bind uncertainty to its quantity, units,
representation, method, implementation/environment, coverage meaning,
applicability, component/dependence disclosures, evidence refs, limitations,
and downstream-use restrictions. Set no numeric floor or acceptance threshold.

**Rationale.** An envelope label, converged run, small residual, solver
tolerance, mesh size, or witness difference is not by itself applicability,
conditioning, or uncertainty evidence.

**Rejected alternatives.** Omitted applicability, universal support, tolerance
as uncertainty, fixed default floor, independent component summation,
quadrature without evidence, or transfer across a PDE/regime/geometry/BC/
implementation/environment/precision/hardware path.

**Interfaces and invariants.** Unsupported/not-applicable cases remain visible;
no silent replacement or fallback. Named uncertainty components do not imply
independence. Missing assessment is typed unavailable/unresolved.

**Downstream.** B-05 owns measurement floors, propagation and decision use;
B-06 qualifies applicability/coverage/dependence; B-E1 tests joint decision
resolution.

**Reversibility and migration.** Changing a support or uncertainty meaning
creates a new policy/object version and may invalidate later evidence; history
remains immutable.

**Exact change path.** Contract support/uncertainty sections and later B-04
assessment/uncertainty records.

**Reserved inputs.** Every real support boundary, conditioning/sensitivity
method, uncertainty representation/value/floor/coverage/dependence, and
acceptance rule remains reserved.

## 2026-09-01 — B-04-D8: Correlation disclosure, contested disagreement, and no fallback

**Recommendation.** Record material shared/distinct equations, closures,
discretizations, meshes, transforms, libraries, generated/copied code,
calibration/data, personnel, floating-point/runtime, and hardware paths for
every comparison. Preserve disagreement as contested or indeterminate; never
average incompatible sources. Missing/failed primary remains typed unavailable.
A future fallback is legal only when the same immutable prospective policy
names and qualifies it; this contract registers none.

**Rationale.** “Independent implementation” and multi-code agreement can hide
common bias. An implicit witness or stale cache fallback changes the answer-key
contract after failure.

**Rejected alternatives.** Majority vote, average/median truth, source
reputation, zero-covariance assumption, correlated agreement as qualification,
fallback by convenience/cost/availability, mock/fixture/candidate/generator
output, or stale cached output.

**Interfaces and invariants.** Neither runner self-certifies independence.
Agreement cannot promote an unqualified source. Disagreement cannot become
candidate failure. A fallback, if later approved, must have exact role,
applicability, uncertainty, provenance, comparison, and historical bindings.

**Downstream.** B-06 owns Dossier evidence and limitations; B-05/B-E1 own
dependence-aware scientific use; B-E2 tests disagreement and failure.

**Reversibility and migration.** New evidence can prospectively strengthen or
narrow a role but cannot rewrite a historical comparison. Adding fallback
requires a new policy version and requalification.

**Exact change path.** Contract independence/disagreement/no-fallback sections
and later B-04 comparison/policy records.

**Reserved inputs.** Independence findings, correlation adequacy,
disagreement threshold/resolution, fallback source/order, and qualification
are owner decisions.

## 2026-09-01 — B-04-D9: Complete provenance, cache identity, and protected disclosure

**Recommendation.** Bind every meaning-bearing Challenge/case/policy/
answer-key target/role-specific execution target/composition member/role/
source/implementation/dependency/method/configuration/precision/environment/
hardware/artifact/applicability/conditioning/uncertainty/provenance/rights/
qualification/disclosure identity into a run and any cache key. Revalidate the
complete graph on a cache hit. Keep requests, runs, comparisons, artifacts,
and assets internal/protected by default; public projection is positive
allow-list reconstruction only.

**Rationale.** Precomputed bytes are meaningful only under the exact contract
that produced them. Hashing or redacting a protected value does not
automatically make it public-safe.

**Rejected alternatives.** Case-plus-solver cache keys, mutable tags, latest
environment, path/URI identity, stale/partial hits, generic serialization,
serialize-then-redact, exception/log diagnostics, and public raw solution or
case refs.

**Interfaces and invariants.** Cross-case/role/policy/environment/configuration
substitution rejects. Unknown/partial/stale/revoked cache state fails closed.
No public error/log/card/MCP/prior/practice/leaderboard surface exposes
protected cases, answers, seeds/draws, exact discrepancies/margins,
conditioning internals, topology, paths, credentials, or customer material.

**Downstream.** B-06 later owns retained qualification evidence; B-07F gets
fixture-only projections; C-04 and operations own real cache/service behavior.

**Reversibility and migration.** Public projection can grow only by explicit
versioned allow-list review. Cache-key meaning cannot change in place.

**Exact change path.** Contract provenance/cache/disclosure sections and later
B-04 canonical/disclosure code.

**Reserved inputs.** Cache implementation/retention, public fields, access,
rights, privacy, authentication, network, process isolation, secrets,
operations, and resource limits remain unavailable.

## 2026-09-01 — B-04-D10: Preserve B-02A censoring and downstream owner boundaries

**Recommendation.** B-04 supplies exact reference facts for B-02A's existing
reference censoring reasons but does not create a second case state,
disposition, replacement, or accounting object. B-05 consumes only admitted
asset refs and uncertainty; B-06 owns Dossier/qualification; B-07F consumes
fixture assets behind the unchanged v1 fixture lifecycle; B-E2 implements
Julia/service adapters and expanded runtime-failure fixtures. A3 integration,
if later required, is prospective.

**Rationale.** Existing B-02A and B-03 boundaries already separate canonical
case generation, intended/realized accounting, and reference-trigger
censoring. Downstream tickets have explicit owners; B-04 should not absorb
their behavior.

**Rejected alternatives.** A B-04 case lifecycle, generator retry, direct A5
scalar, mandatory-gate mapping, Dossier signoff, A3 LIVE mutation, fixture
official promotion, transport, artifact store, leaderboard, frontier, product,
or settlement behavior.

**Interfaces and invariants.** Reference/infrastructure failure is never
candidate physics failure, score zero, rank loss, or economic event. B-02A
continues to own `CensoringRecord` and SamplingPlan/denominator semantics.
Only exact closed B-04 terminal record/reason refs may be proposed; bare
component absence is not a censoring fact. Raw run success cannot enter B-05.
Fixtures cannot enter LIVE.

**Downstream.** B-05, B-06, B-07F, B-E1, B-E2, B-E3, C-04, and later A3
integration consume only their named seams after their own authorization.

**Reversibility and migration.** The one-way seams are extendable
prospectively. Collapsing owners later would be a high-cost migration requiring
new identities, compatibility tests, and evidence review.

**Exact change path.** Contract downstream/censoring sections; B-04 ticket,
plan, evidence, and Wave-B candidate transition. No downstream ticket file or
runtime is changed.

**Reserved inputs.** Measurement/score/Dossier values, exact LIVE activation,
security/operations, real fixture composition, network, product, frontier,
economics, settlement, weight, and emission authority remain unavailable.

## 2026-08-31 — HUB-D1: Static-first Development Hub and maintenance gate

**Primary map ref:** `SYSTEM/DEVELOPMENT-HUB`

**Status:** agent-selected engineering-governance decision for independent
review; no scientific or production authority.

**Problem.** Carbon's wave, ticket, decision, evidence, and recurring-change
routes are distributed across authoritative repository records. The supplied
v2 orientation package also used an empty JavaScript shell, so restricted
previews showed a blank page. Without a repository maintenance contract, any
copied map would predictably drift.

**Selected approach and agent recommendation.** Integrate a public-safe,
data-first Development Hub under `docs/development/carbon_hub/`. Make complete
semantic, zero-script `index.html` the primary surface; retain the richer
application only as optional `interactive.html`. Treat JSON event/map records
as editable source and deterministically generate the HTML, Markdown, YAML,
and explainer outputs. Add scoped and root executor instructions, exactly-one
PR impact declaration, read-only drift/authority/event validation, real-browser
JavaScript-on/off smoke coverage, and optional Pages publication for authorized
repository maintainers. Keep one primary `map_ref` per material event and
preserve history through prospective `supersedes` records. The workflow does
not itself enforce owner approval; any required reviewer on the `github-pages`
environment is separate human-controlled repository configuration.

**Rationale.** Static-first output fixes the observed blank-page failure while
remaining usable through `file://`, restricted previews, and simple static
hosting. Data-first generation makes a 14-wave/39-ticket map reviewable.
Ticket-start placement, closeout reconciliation, PR declaration, and CI give
the hub a bounded maintenance path without moving implementation authority out
of repository tickets, contracts, decisions, reviews, tests, and evidence.

**Alternatives rejected.** Copying the v2 ZIP unchanged would preserve the
blank-page defect and undeclared Python dependencies. Keeping a manually
edited map without drift enforcement would not meet the living-navigation
contract. Removing the interactive application would discard a useful
optional search/filter surface. Automatically enabling public Pages, changing
repository variables, or adding secrets would exceed this task and owner
authority.

**Implementation location.** `docs/development/carbon_hub/`, root `README.md`
and `AGENTS.md`, `agent_pack/EXECUTION_PROTOCOL.md`, the root PR template, and
the two Development Hub workflows. Map events `HUB-BUG-001`, `HUB-ADJ-001`,
and `HUB-ADJ-002` record the blank-page repair, maintenance integration, and
review-driven validation-protocol repair.

**Downstream effects.** Development PRs must select a primary map location,
classify hub impact, update source/events only when a material map trigger
applies, regenerate, validate, and complete exactly one impact declaration.
Map-structural changes require semantic source plus an event; mapped-detail
changes may use a specific no-impact declaration when orientation meaning is
unchanged; unmapped authority paths fail until an explicit owner is recorded.

**Reversibility and migration cost.** Documentation and CI changes are
revertible as one bounded integration. Stable IDs and event history should not
be rewritten; a future schema or routing change uses a versioned renderer and
superseding event. Changing the primary static-first contract requires a
prospective decision, browser/accessibility regression evidence, and migration
of generated outputs and CI.

**Reserved inputs and authority ceiling.** This decision sets no physical
value, qualification result, security acceptance, rights policy, live
economics, launch, production, `LIVE`, frontier, settlement, network, weight,
or emission state. Pages remains disabled unless an authorized maintainer
manually dispatches the workflow or `CARBON_HUB_PUBLISH=true` enables automatic
publication; enabling Pages makes the hub public. The workflow does not itself
enforce owner approval, and this integration changes no repository setting.
Future internal-only content requires an access-controlled host.

**Lead notification.** The durable SciML / Technical Lead route is issue #42
and must receive the complete implementation/PR package with `@harshaa765`.

## 2026-08-31 — B-03 decision-series status

> **B-03-D1 through B-03-D8 status: RATIFIED BOUNDED ENGINEERING-CONTRACT
> DECISIONS.** Contract PR #67 passed exact-head CI and clean 5/5 Greptile
> correctness review with zero unresolved threads, normally merged the exact
> reviewed tree as `b86daa5d8b0f8b3e86bb82c2661f405747a200df`, and passed
> exact-main CI. This reconciliation does not expand the decisions beyond the
> bounded engineering contract. Any implementation-tree change still requires
> exact-head CI and Greptile review. Notification requested `KEEP`, `CHANGE`,
> `BLOCKED`, or `DEFER_TO_OWNER`; no affirmative response or silence gate
> applied, and no owner deferral arose. MQ-002/MQ-003 production and scientific
> inputs remain `DEFERRED_FAIL_CLOSED`.

## 2026-08-31 — B-03-D1: Generator package ownership and one-way boundary

**Selected approach and agent recommendation.** Implement one
standard-library-only `carbon.generators` package with the structural Burgers
fixture under `carbon.generators.burgers`. Depend one way on exact B-02A
authoring/case/ref seams, A4 fixture-only seeding APIs, and at most registry
identity/digest primitives. Permit explicit internal imports from
`carbon.authoring.cases` and `carbon.authoring.refs` for the trusted producer
without widening the authoring root export surface. Keep trusted requests,
authorities, grants, artifacts, services, codecs, and raw-ref issuance in
explicit protected/private modules; the package root exports only the curated
safe descriptor/environment/configuration/role/outcome/unavailable-input and
public-projection surface fixed by the contract.

**Rationale.** `Generator_Creation.md` already maps this responsibility to
`carbon/generators/`, and the plural domain is unambiguous next to the existing
authoring and seeding owners. B-02A intentionally keeps protected case types
off its convenience exports while still supplying the exact construction
boundary B-03 needs. A separate downstream package prevents generation from
acquiring authoring, entropy, lifecycle, reference, score, or service
authority.

**Alternatives rejected.** Singular `carbon.generator` or
`carbon.generation`; putting generator code in `carbon.authoring` or
`carbon.seeding`; reviving retired `carbon.challenges`, `carbon.data`,
`carbon.physics`, `poc`, or archived code; importing registry gate/store/LIVE;
adding future reference, measurement, dossier, service, or empty placeholder
modules.

**Downstream impact.** Implementation adds the exact package root/modules to
code authority, installed-wheel/outside-tree inventories, and reverse-import
and no-leakage invariants. B-04/B-05/B-06/B-07F may later consume the public
surface but cannot redefine it or reverse dependency direction. No dependency
or lock-file change is expected.

**Migration cost and exact supersession path.** Moving public nominal types or
reversing an import edge is a high-cost API/authority change. It requires a
prospective B-03 contract/schema version, normally merged superseding
decision, import/wheel/authority/invariant migration tests, and exact-head and
exact-main review. Package-private file splits remain low cost if exports and
semantics do not change.

**Reserved inputs.** Production runtime, deployment, network, persistence,
reference, measurement, scoring, qualification, and LIVE integration remain
with their owning tickets and human/domain gates. Their absence does not block
a pure fixture package.

## 2026-08-31 — B-03-D2: Reuse B-02A identity and bind a complete event

**Selected approach and agent recommendation.** Reuse exact B-02A
`CanonicalChallengeCase`, `.canonical_bytes()`, `.to_ref()`, and existing
owner-ref kinds for generator, generation event, generation failure,
distribution conformance, payload, case source, fixture registration,
provenance, and accounting. Define distinct exact B-03 environment,
fixed-configuration, request, replay, accounting-directive, pending-attempt,
final-decision, result, attempt, accounting, conformance, duplicate-comparison,
and post-accounting fact-set refs plus a non-self-referential
`GeneratorImplementationManifest`. The manifest digest, not the descriptor
digest, equals A4 `SeedPin.generator_digest`. Define an acyclic canonical
`GenerationSourceEvent` before support/censoring/outcome decisions; use the
externally issued protected attempt commitment's object id/version for every
attempt-scoped B-02A owner pin. Exact-recompute every object/ref pair and bind
the event through `CaseSourceBinding(GENERATED, GeneratedCaseSource(...))`.

**Rationale.** B-02A already owns the physical case and its content identity,
but a case has no explicit generation-role, replay, attempt, or fixture-context
field. A complete protected event binds those facts without altering case
identity. Exact recomputation is necessary because a digest-valid owner ref
proves bytes, not that the authorized B-03 service created or semantically
validated them.

**Alternatives rejected.** A second B-03 `GeneratorRef`, generic strings,
parallel case/reference/canonicalizer types, caller-supplied digest-only refs,
self-issued provenance, mutable latest aliases, extending B-02A's closed
authored-object/history registry, or putting protected role/attempt fields in
a public case projection.

**Downstream impact.** Consumers resolve the exact manifest/environment/
descriptor/configuration/request/event/payload/result object/ref graph and
retain Challenge equality and full dependency bindings. The source event
contains no terminal decision/result, so B-04/B-05/B-06 can refer to it without
cycles or changing historical case bytes. Public consumers receive only an
externally authorized B-02A projection, never a raw protected case ref.

**Migration cost and exact supersession path.** Changing ref scope, descriptor
or event field order, canonical profile/header, or case-source binding is a
high-cost identity change requiring a new prospective B-03 schema/profile,
normally merged superseding decision, dual-version read/migration tests where
bytes exist, and immutable preservation of all historical refs.

**Reserved inputs.** Production generator identity registration,
implementation attestation, environment qualification, durable stores,
signatures, and public case-projection authority remain unavailable and
externally owned.

## 2026-08-31 — B-03-D3: Closed role mapping and A4-owned random material

**Selected approach and agent recommendation.** Bind exact B-02A
`SamplingRole`, resolved `SamplingPlan`/ref, A4 `SeedDomain`, fixed A4
`RoleKey("generator_sampling")`, and exact A4 `SeedPin` in one closed
compatibility check. Permit
only fixture mappings `OFFICIAL_EVALUATION → OFFICIAL_EVAL`,
`STRESS → OFFICIAL_STRESS`, and `PRACTICE → OFFICIAL_TRAIN`, with the last
explicitly meaning entropy segregation rather than evidentiary equivalence.
Accept exact `FixtureOfficialContext`, private UInt64 draw, exact
`FixtureAuthoringCapability`, and `FixtureOrigin` only through a nominal
nonserializable `FixtureGenerationGrant`; bind its replay preimage to A4's
value-only fixture projection/commitment and the exact request commitments
inside the authority's private issuance record. Treat the request replay ref as
a capability-issued opaque protected B-03 commitment ref, never a B-02A owner
ref or a B-03 digest of raw draw material.
Derive with A4 inside the trusted adapter, permit exactly one ephemeral
`DerivedSeed.as_backend_bytes()` copy in the private sampler, and return no
reachable material, context, provider, grant, or draw.

**Rationale.** B-02A and A4 role vocabularies are intentionally different and
cannot be equated by a caller label. `DerivedSeed` does not itself embody its
origin/domain after derivation, so accepting it publicly would erase the
critical fixture provenance proof. A4 already owns entropy acquisition,
domain separation, pins, and derivation; B-03 needs only a tightly verified
consumer capability.

**Alternatives rejected.** Public `seed`, `DerivedSeed`, bytes, RNG, callback,
draw, or free-form role inputs; B-03 seed derivation; ambient `random` or
process/hash state; treating PRACTICE as official training evidence;
supporting authoring qualification/verification/evidence-campaign roles
without an owning contract; caller Booleans for fixture/official mode.

**Downstream impact.** Every request validates Challenge and generator
version/digest against `SeedPin` before derivation, and one attempt consumes at
most one derivation. No request/result/event/public/error surface leaks seed,
provider, context, draw, slot, hidden stratum, mixture, or reversible input.
No upstream package imports B-03.

**Migration cost and exact supersession path.** Adding a role/domain mapping,
production context, or externally supplied material changes security and
scientific boundaries and requires an owning A4/B-03 prospective contract,
normally merged superseding decision, leakage/threat-model review, migration
tests, and exact-head/exact-main gates. Existing fixture events remain
fixture-only.

**Reserved inputs.** Production entropy source, custody, unpredictability,
provider authentication, domain policy, role authorization, security
acceptance, and official operations remain A4/security/operations-owned and
unavailable.

## 2026-08-31 — B-03-D4: Six nominal terminal outcomes

**Selected approach and agent recommendation.** Define exactly
`VALID_GENERATED`, `REGISTERED_EXCLUSION`, `GENERATOR_NONCONFORMANCE`,
`INVALID_CONSTRUCTION`, `CENSORED_CASE`, and `INFRASTRUCTURE_FAILURE`.
Require an exact case/case-ref pair for both valid and censored variants and no
disposition-facing case for the other four; post-case infrastructure failure
retains only an audit-protected constructed case/artifact. Normatively map
valid to B-02A `VALID`, censored to
`CENSORED` with an exact finalized `CensoringRecord`/ref, registered exclusion
to attempt-bound no-case `EXCLUDED`, and generator nonconformance to attempt-
bound `GENERATION_FAILURE`. Invalid construction and infrastructure failure
have exact B-03 reason/attempt records but fabricate no B-02A disposition.

**Rationale.** These outcomes answer different causal and accounting
questions. A registered exclusion is not a generator bug; generator
nonconformance is not malformed authored input; censoring is not
infrastructure failure; and none of them is adverse scientific candidate
evidence. A closed nominal union makes invalid substitutions and denominator
loss observable.

**Alternatives rejected.** Success/failed Boolean, open strings, a generic
exception result, treating exclusion/censoring as valid cases, converting any
failure into candidate evidence, adding `REFERENCE_FAILURE`, or caller-settable
official/production/qualified/LIVE flags.

**Downstream impact.** Attempt and intended-realized accounting partitions
every unit by the exact six outcomes. B-04 owns reference failure; B-05 owns
measurement/uncertainty evidence; B-06 owns qualification aggregation.
Consumers must not infer scientific quality from the terminal kind. Censored
cases remain non-valid evidence and are never exposed publicly without the
separate external B-02A projection authority.

A protected `PENDING_SUCCESSOR` invocation output is an orchestration state
that retains one of these same six provisional outcomes while B-02A execution
lineage is unresolved; it is not a seventh terminal outcome, disposition, or
accounting row.

**Migration cost and exact supersession path.** Adding, merging, splitting, or
reinterpreting a terminal kind changes persisted event/result/accounting
semantics and requires a prospective B-03 schema and normally merged
superseding decision with exhaustive variant migration and historical-reader
tests. Existing outcome bytes retain their meaning.

**Reserved inputs.** Scientific acceptance, evidence use, reference failure,
measurement failure, qualification, scoring, operational remediation, and
production incident policy remain externally owned.

## 2026-08-31 — B-03-D5: One derivation per attempt and visible replacement

**Selected approach and agent recommendation.** Make each B-03 invocation one
protected attempt with distinct intended-slot and intended-evidence-unit
commitments and at most one A4 derivation. Prohibit internal silent retry.
Record whether the current attempt is itself a replacement with the exact prior
pending-attempt/ref and current-lineage ref. Only after the provisional terminal
outcome does the nominal accounting authority return an exact closed
`AttemptAccountingDirective`. A direct final directive records an unexecuted
B-02A replacement decision. A successor directive instead returns a protected
pending-attempt record and deliberately defers the immutable B-02A replacement,
censoring/disposition, final attempt, and result records. Only after the exact
authorized successor invocation exists does a pure finalizer bind that same
lineage in B-02A, validate `executed=True`, and finalize the predecessor. A
pre-issued fallback constructs the exact owner-unavailable path if the
accounting authority fails, so terminalization cannot recurse. The denominator
binding must equal the registered plan's exact denominator-effect ref whenever
the registered trigger applies. Separate pure trusted builders derive
`IntendedUnitAccounting` from complete attempt/link/accounting-decision pairs
and `GenerationAccountingSummary` from complete intended-unit pairs. Select no
production retry ceiling.

**Rationale.** Silent replacement changes the sampled population and removes
difficult units from denominators. Existing B-02A replacement and censoring
types already own prospective policy semantics; B-03 records their exact
decisions only after the cause exists rather than creating an implicit retry
loop or construction cycle. Deferring the predecessor's B-02A record is
necessary because B-02A canonically defines a bound lineage as an executed
replacement; it must never remain permanently marked unexecuted after a real
successor exists. Per-attempt derivation also prevents provider errors from
consuming an unknown number of draws.

**Alternatives rejected.** `while retry`, a default maximum-attempt count,
dropping failed units, reusing one attempt/draw after failure, replacing on a
generator-owned heuristic, inferring intended-unit grouping from equal labels
or digests without the exact external link decision, or reporting only
realized valid cases.

**Downstream impact.** Conformance/evidence consumers receive separate
intended and realized terminal partitions and complete protected lineage.
Failures, exclusions, and censoring stay visible by cause and protected
stratum. Public projections omit protected attempt/slot/stratum identities.

**Migration cost and exact supersession path.** Any retry budget, replacement
trigger, censoring policy, or denominator rule requires its owner's exact
registered policy plus a prospective B-03/B-02A contract revision, normally
merged decision, migration/accounting proof, and review. Historical attempted
units cannot be deleted or relabeled.

**Reserved inputs.** Real replacement/censoring policy, retry ceilings,
sampling-unit/stratum identity, failure remediation, and evidence-denominator
rules remain human statistics/SciML/operations-owned.

## 2026-08-31 — B-03-D6: Nominal authority echoes and fact-only conformance

**Selected approach and agent recommendation.** Inject exact nominal
support/exclusion, censoring, attempt-accounting, near-duplicate, and external-
distribution authorities. Support returns nominally separate primary-case and
selection-materialization assessments bound to each population's own support/
exclusion contracts; primary evidence supplies `ValidCasePayload`, while an
external terminal resolution selects any effective exclusion. Require exact
full-request echoes and closed decisions; fail closed on stale, cross-
Challenge, forged, subclassed, partial, exception, or non-echoing results.
Detect exact canonical-case duplicates by case-ref equality and physical
collisions by an attempt-independent protected payload fingerprint under the
same Challenge/representation/configuration; never compare the deliberately
attempt-scoped payload owner pins. Every admitted path emits exact
`GeneratorConformanceFacts` whose case/payload/support fields use
closed bound/not-applicable/owner-unavailable variants and whose current replay
identity is always exact-bound, allowing an early
no-case generation failure to still supply B-02A's required distribution-
conformance ref. Exact and physical-duplicate plus externally owned near-
duplicate decisions live in a separate post-result
`DuplicateConformanceFacts`, never in per-attempt conformance. Post-accounting external fact sets, rather than per-attempt
facts, consume completed accounting for protected strata/tails and marginal/
joint/conditional summaries. Deterministic replay comparison uses a distinct
nominal non-accounting fixture probe from the already-bound private replay
reservation; it reconstructs audit-only protected payload/event/case bytes
under the baseline identities and proves exact case-ref equality, but issues no
second provenance event, generated case, attempt, result, or accounting row.

**Rationale.** B-02A support/exclusion contracts store rule and authority refs
but do not execute predicates. Raw callbacks or Booleans would let generator
code invent registered population meaning. Exact equality is available and
deterministic; semantic nearness and adequacy require externally owned policy
and evidence.

**Alternatives rejected.** Treating a rule ref as executable; raw callbacks,
Booleans, duck types, or unverified authority responses; Python `hash` for
identity; built-in numeric distance/tolerance; a generator-selected support,
exclusion, diversity, invalid-rate, collision, or conformance threshold; using
reference agreement as distribution validation.

**Downstream impact.** B-06 and human reviewers may evaluate exact fact
records under their own thresholds without B-03 conferring a verdict. An
unavailable near-duplicate policy remains typed unavailable. None of the facts
is a QualificationManifest or candidate scientific evidence.

**Migration cost and exact supersession path.** A new authority protocol,
estimand, summary definition, distance, threshold, or acceptance decision
requires its owning contract and a prospective normally merged B-03 adapter/
schema decision with parity and adversarial echo tests. Historical facts are
not reinterpreted.

**Reserved inputs.** Primary/selection support (including official P/Q only
when the exact plan binds them), exclusion rules, estimands,
strata/tails, duplicate/near-duplicate policy, conformance thresholds,
adequacy evidence, and qualification remain SciML/statistics/protocol-owned.

## 2026-08-31 — B-03-D7: Structural fixed-viscosity Burgers fixture only

**Selected approach and agent recommendation.** Implement one immutable
`BurgersFixtureConfiguration`: id `b03_burgers_structural_fixture`, version
`1.0`, `PERIODIC_1D`, period `1.0`, grid `8`, mechanical fixture viscosity
`1.0`, and codec `carbon.b03.burgers.fixture-latent.v1`. The private sampler
reads the first two big-endian UInt64 words, maps each modulo 2001 into
`[-1000,1000]`, and combines exact bases `(0,1,1,0,-1,-1,0,0)` and
`(1,1,0,-1,-1,0,1,0)` divided by `4096.0`. Bind the configuration ref into
the non-self-referential implementation manifest, descriptor, request, replay,
event, and protected payload. Leave every production range/law/value and
scientific adequacy input in the separate closed `HUMAN_INPUT_REQUIRED`
report. Construct only a physical input case; do not solve the PDE or emit
truth/reference/candidate output.

**Rationale.** The ticket needs a mechanical fixture to exercise case
construction and conformance plumbing. Current generator specification
amendments propose numerical values but do not have authority to select real
population truth. Structural provenance prevents a deterministic, plausible
fixture from being mistaken for a production generator.

**Alternatives rejected.** Adopting proposed viscosity/range/tolerance values
as canonical truth; a random configurable production-looking generator;
hashing `HUMAN_INPUT` strings into complete production objects; importing a
solver, NumPy/JAX/Julia, archived PoC code, data files, or network resources;
emitting reference solutions, scores, or qualification evidence.

**Downstream impact.** Fixture tests obtain deterministic exact case bytes,
payload refs, and fact records. Real production bindings remain unavailable
and cannot be upgraded by caller label or config mutation. B-04 later owns
reference behavior and B-05 measurement behavior.

**Migration cost and exact supersession path.** Any real population,
configurable physical law, numerical backend, or production generator is a
new qualified implementation/version requiring owner-supplied values,
prospective B-03 contract and generator identity, conformance evidence,
security/operations review, and normal review/merge gates. It cannot reuse or
upgrade fixture identities.

**Reserved inputs.** Real viscosity, forcing, initial-condition law, domain,
grid, horizon, ranges, strata, mixture, exclusions, sampling law, physical
validation, solver/reference, and production environment remain unavailable.

## 2026-08-31 — B-03-D8: Structural fixture provenance and safe disclosure

**Selected approach and agent recommendation.** Preserve exact B-02A
`FixtureOrigin` as loader metadata (not case-provenance data), retain the exact
loaded case and complete loaded dependency tuple in a protected
`GeneratedFixtureArtifact`, and call `compose_authoring_graph_origin`, so every
generated fixture graph is `FIXTURE_DERIVED` and A3 fails closed with
`scientific_authoring.fixture_derived`. Retain the protected artifact on a
post-case infrastructure failure without creating a B-02A disposition or
public case identity. The public factory accepts the exact `GeneratorResult`,
derives its fixture marker only from that exact artifact graph origin, and calls the external
`CaseProjectionAuthority.require_pairing` for any case projection. Expose a closed
`PublicGenerationProjection` containing only Challenge, public generator id/
version, fixture-only marker, coarse outcome, and an already-authorized B-02A
public case projection. Use redacted protected representations and stable,
non-echoing, cause-free errors.

**Rationale.** A fixture Boolean on a record is insufficient: provenance must
survive the complete graph and least-authority join. B-02A deliberately
separates protected case identity from a public projection issued by an
external `CaseProjectionAuthority`; B-03 cannot self-authorize that
disclosure. Error, `repr`, serializer, and reachability paths are common seed
and hidden-population leakage channels.

**Alternatives rejected.** A caller-settable fixture/official/production/LIVE
flag; `RegisteredOrigin`; creating a `QualificationManifest`; importing or
calling `activate_live`; exposing canonical case/payload/event refs, seed,
draw, attempt, slot, stratum, mixture, reversible inputs, provider/context,
raw exceptions, or automatic projection authority.

**Downstream impact.** A3 LIVE integration tests must load the actual generated
artifact, compose graph provenance, and observe structural rejection. Public
and exception allowlists are mechanically tested, including object
reachability and outside-wheel imports. Fixture evidence cannot be promoted
in place.

**Migration cost and exact supersession path.** Widening disclosure or
changing provenance/LIVE behavior is a high-risk security/scientific change
requiring the owning B-02A/A3 prospective contract, normally merged
superseding decision, leakage and lifecycle threat review, migration of public
projections, and exact-head/exact-main gates. Existing fixture artifacts stay
fixture-derived forever.

**Reserved inputs.** Public identity disclosure, projection authority,
registered origin, qualification manifests, production provenance, security
acceptance, privacy policy, and LIVE activation remain externally and
human-owned.

## 2026-08-31 — B-02C decision-series status and B-02B completion

> **B-02C-D1 through B-02C-D8 status: SATISFIED AGENT-SELECTED BOUNDED
> ENGINEERING DECISIONS.** The series became bounded engineering-contract
> authority only
> if the exact independently reviewed B-02C contract tree passes exact-head
> CI, receives clean exact-head Greptile correctness review with every valid
> finding repaired and zero unresolved threads, normally merges with exact
> tree preservation, and passes exact-main CI. Any tree change requires
> rereview. Applicable lead/domain notification requests `KEEP`, `CHANGE`,
> `BLOCKED`, or `DEFER_TO_OWNER`; no affirmative response or silence gate
> applies. Explicit owner deferrals route to issue #41.

That version 0.1 predicate is satisfied: contract PR #65 reviewed exact head
`a0eb5cf946d5aca33aec166a9a7a0d85d0c7602a` and tree
`0079a96700f6804d33fdd29c6ec852fbc70d765c`; exact-head CI run
`33373378456` and Greptile check `99430113590` at 5/5 with zero unresolved
threads passed; normal merge `319a765860ac6e93018124bd57a84bfd6679672e`
preserved the reviewed tree; and exact-main CI run `33374037602` passed. The
version 0.2 fail-closed clarification then reached repaired reviewed head
`a30865d2349f1cc6e725f1ea15e923f8d7893e4c`, passed exact-head CI
`33388174967` and Greptile check `99475440630` at 5/5 with zero unresolved
threads, normally merged as `1dc41288e2d0e516de21d05dc168b188791c39f5`
with exact tree `eb9b0c9b899cc4be9c8e9b22c16a5a3a48406a12` preserved, and passed
exact-main CI `33388595061`.

The earlier B-02B-D1 through B-02B-D8 conditional predicates are satisfied.
Contract PR #63 normally merged exact reviewed head
`569db72e0768d882c39d895e5f69a816cb8ca227` as
`1c012468545f448aa758daf7dec17e409bb13bbc`, preserving tree
`635d06d6cbf0178b87d75fdc4b320d463b47a7c9`; exact-head CI
`33353607675`, Greptile check `99371479556` at 5/5 with zero unresolved
threads, and exact-main CI `33353848363` passed. Implementation PR #64 then
normally merged exact reviewed head
`68189e7068715a5d8054f0f7e64dc981ae1c37aa` as
`b10b6e74fb3f8ab8a7427a6763c7db4f41341083`, preserving tree
`45273c527684b94afeb2f01b66a774b5426b6e0e`; exact-head CI
`33362051770`, ready-state Greptile check `99413062552` at 5/5 with zero
unresolved threads, and exact-main CI `33368352662` passed. B-02B is `done`
only in its recorded bounded engineering scope.

## 2026-08-31 — B-02C-D1: Resource-policy package ownership and no store

**Selected approach and agent recommendation.** Add one standard-library-only
`carbon.resource_policy` package. Its dependencies point one way into exact
public `carbon.construction`, reusable `carbon.authoring` canonical/primitives/
refs, and `carbon.registry.ChallengeKey`; none of those packages may import it.
Produce canonical bytes and refs but no persistence layer.

**Rationale.** B-02B expressly emits policy-agnostic facts and must not gain a
policy verdict. No current generic store owns the new nominal types:
B-02A history is closed to authored objects, A3 registry state is replaceable,
and the card store is process-local. A separate package also prevents B-07E
forecast or Wave-C quote authority from entering construction.

**Alternatives rejected.** Extending `carbon.construction`; a generic
`carbon.resource` namespace; reusing A7 submission limits, A7 execution pins,
A8 fixture runtime policy, or `carbon.audit`; adding a latest-policy registry
or backend/store in this ticket.

**Downstream impact.** B-07E, B-07S, B-07F, B-05, and later operations may
consume exact B-02C values prospectively. Package/code-authority and installed-
wheel inventories gain one root; dependencies and lock files remain unchanged.

**Migration cost and exact supersession path.** Package-private splits are low
cost. Moving public nominal types, reversing dependency direction, or adding a
store is a medium/high persisted API change requiring a new prospective B-02C
contract/schema version, normally merged superseding decision, migrations for
stored bytes if any exist, and import/authority/invariant tests. Historical
refs may not be reinterpreted.

**Reserved inputs.** Persistence operations, retention, authentication,
security acceptance, deployment, and production operations remain unavailable
and human/domain-owned; their absence does not block pure fixture code.

## 2026-08-31 — B-02C-D2: Domain-separated identity, scoped refs, and graph

**Selected approach and agent recommendation.** Reuse exact A3/B-02A
Challenge/id/version/UInt64/finite-Float64/canonical-value/tagged-digest
grammar under the closed profile `carbon_resource_policy_canonical_v1` and
header `carbon.resource_policy.canonical.v1\0`. Define exact distinct frozen,
slotted `ResearchResourcePolicyRef` and `ResourceClassRef`; policy refs are
Challenge-bound and v1 class refs are also exactly Challenge-bound. Derived
assessment, decision, cancellation, and receipt refs are distinct exact
Challenge-bound digest refs. Keep the content graph acyclic.

**Rationale.** Reuse prevents a second generic identity system while a new
domain/profile avoids widening the closed B-02A or B-02B registries. Exact
Challenge scope makes every fixture class/provenance mismatch fail closed;
future reusable hardware identity belongs in a prospective owner contract.
Staleness is an expected valid exact-ref mismatch, never digest tamper,
inferred version ordering, or “not latest.”

**Alternatives rejected.** Adding object kinds to upstream closed registries;
string/generic refs; a premature global class variant; name aliases; semantic version
ordering; mutable latest lookup; self-referential digests; interchanging refs
that happen to carry the same fields.

**Downstream impact.** Every consumer must verify exact object/ref pairs,
Challenge, profile, digest, and expected active pins. B-07S later owns
wire projection and cannot rename these semantics by alias.

**Migration cost and exact supersession path.** Adding a new optional object
kind is medium; changing scope, field order, profile, digest preimage, or ref
meaning is high. Either requires a prospective schema/profile and normally
merged B-02C superseding decision with dual-version read/migration tests where
historical bytes exist. Existing digest identities remain immutable.

**Reserved inputs.** Production class registries, signatures, attestation,
key management, lifecycle activation, and security qualification remain
unavailable. Fixture provenance is structural and non-authoritative.

## 2026-08-31 — B-02C-D3: Exact immutable B-02B plan consumption

**Selected approach and agent recommendation.** Accept exact
`ResolvedConstructionPlan` plus `ResolvedConstructionPlanRef`, recompute and
verify the pair, and consume exact copied B-02B `StaticResourceRequirement`
and impact-tag tuples. Verify Challenge, assembly, catalog, compiler, and
environment bindings against the exact policy/class before evaluation. Prove
the plan and nested values remain byte-identical before and after every
B-02C operation.

**Merged implementation hardening (version 0.2 clarification).** A content
address proves exact bytes but does not prove that the
owning semantic operation produced them. Readiness accepts the exact plan/ref
in addition to its assessment pair, and downstream services recompute every
supplied assessment, decision, enforcement result, and cancellation record
from their exact authoritative inputs before use. This is the fail-closed
implementation of the selected exact-consumption approach, not a new
authority or policy value.

The terminal observed-receipt builder returns its exact receipt/ref pair only
after semantic validation. Its public verifier requires the full dependency
set and recomputes that pair; unguarded structural receipt-ref issuance is not
part of the public API.

**Rationale.** B-02B owns construction semantics and identity. B-02C owns only
support, admissibility, enforcement, and resource facts under a selected exact
policy. Preserving the input means a policy revision can change an assessment
without changing a Strategy, compiler result, plan, or plan hash.

**Alternatives rejected.** Recompiling or normalizing in B-02C; clamping,
unit conversion, tag inference, requirement deletion/addition/reordering;
copying the B-02B codec; accepting a caller-provided digest without the exact
object; writing policy/class/context into plan identity.

**Downstream impact.** B-07E may forecast from the same immutable plan facts;
B-07F may later bind execution; B-05 may consume registered receipt facts.
None can use B-02C to rewrite construction meaning.

**Migration cost and exact supersession path.** New B-02B plan fields or
semantics require their owning prospective B-02B compiler/schema version.
B-02C support for that exact version requires a normally merged B-02C
superseding decision/adapter and parity tests. Historical plan bytes and refs
remain unchanged.

**Reserved inputs.** Real resource dimensions, units, construction values,
components, environments, and scientific applicability remain with their
existing owners and unavailable unless exactly registered.

## 2026-08-31 — B-02C-D4: Four nominal epistemic resource layers

**Selected approach and agent recommendation.** Keep (1) B-02B static
construction requirements/B-02C static assessment, (2) future B-07E calibrated
forecast, (3) future Wave-C binding execution quote/admission, and (4) B-02C
observed receipt as distinct nominal types with fixed authority/layer markers.
B-02C v1 implements only layers 1 and 4 plus fixture readiness; exact-type
checks reject cross-layer substitution.

**Rationale.** A deterministic declared requirement, a probabilistic forecast,
an operational/economic commitment, and a factual observation answer different
questions. Conflation would permit prediction to authorize spending or a
receipt to masquerade as scientific evidence.

**Alternatives rejected.** One resource estimate/result union; a shared
numeric record distinguished by a caller string; deriving admission from
forecast; treating quote as observed use; treating latency/cost telemetry as
quality, evidence, score, or price.

**Downstream impact.** B-07E owns forecast model/calibration/support/
uncertainty. Wave C owns real admission, quote, price, quota, charging, and
capacity commitments. B-05/B-E1 own scientific evidence sufficiency and use.
B-07S owns future wire-visible names and envelopes.

**Migration cost and exact supersession path.** Adding later nominal layers is
medium and prospective in the owning ticket. Altering a B-02C v1 union or
relabeling historical values is high and requires a new schema/profile plus a
normally merged cross-owner superseding contract. No adapter may silently
convert among layers.

**Reserved inputs.** Calibration data/eligibility, operational capacity,
binding quotes, prices, quotas, funding, and scientific-evidence rules remain
unavailable and owner-controlled.

## 2026-08-31 — B-02C-D5: Fixture classes, ceilings, contexts, and assessment

**Selected approach and agent recommendation.** Define exact fixture-only
`ResourceClass` values with Challenge-bound identity, B-02B environment pins,
supported static dimensions, exact class observation metrics, and structural
provenance. Bind the complete class-ref set in an exact Challenge-bound
`ResearchResourcePolicy` with a ceiling for every static dimension, explicitly
supported impact tags, point/mode-specific runtime limits, per-context readiness
law, exact assembly/catalog/compiler, and one nominal
`FixturePracticeResourceContext` or distinct
`FixtureOfficialShapedResourceContext`. A pure assessment returns typed
`ADMISSIBLE`, unsupported, over-limit, or valid-ref stale/mismatch outcomes
with deterministic safe issues; malformed/tampered inputs hard-reject without
issuing an assessment. Full policy-bundle validation verifies every named
class before policy-ref issuance or use.

**Rationale.** Missing dimensions/tags must be unsupported rather than
unlimited, and dormant invalid bindings cannot hide behind a selected class.
Inclusive exact static/runtime limits test the policy boundary without choosing
real hardware values. Nominal fixture contexts preserve practice/official-
shaped separation without granting official authority or contaminating plan
identity.

**Alternatives rejected.** Host inspection; class-name inference; dynamic
hardware discovery; real/default classes; implicit unlimited ceilings;
floats/coercion/clamping/conversion; caller-selected `official=True`; inferring
support from impact tags; declaring static admissibility to be execution
permission.

**Downstream impact.** B-07F later consumes an exact policy result only behind
its own lifecycle and execution authority. B-07E may use the exact class and
policy as forecast inputs. Fixture official-shaped parity never becomes
official qualification.

**Migration cost and exact supersession path.** Adding a production provenance
variant, dimension, context, or new outcome is medium/high and requires owner-
supplied values, a prospective B-02C schema/policy version, normally merged
superseding decision, and exact negative/security/compatibility tests. Existing
fixture objects cannot be upgraded in place.

**Reserved inputs.** Real hardware classes, ceilings, environments,
enforcement rails, production contexts, operational approval, and security
acceptance remain human/domain-owned and fail closed.

## 2026-08-31 — B-02C-D6: Capacity, funding, queue, and evidence deferral

**Selected approach and agent recommendation.** Model exact fixture-only
per-context `REQUIRED | NOT_APPLICABLE(reason)` laws for validator capacity,
reconstruction funding, queue, and evidence budget. A provided fixture carrier
uses exact `AVAILABLE | UNAVAILABLE | NOT_APPLICABLE` states; an exact
`NO_AVAILABILITY_INPUT` union binds omission into decision identity. A separate
pure readiness operation accepts only an exact admissible static assessment
and returns `FIXTURE_ADMISSIBLE` or `EVIDENCE_DEFERRED` with every unavailable
required cause.

**Rationale.** Operational readiness is not static fit or a binding quote.
Explicit not-applicable states prevent practice fixtures from pretending that
scientific reconstruction funding exists; explicit unavailability and no-input
identity prevent optimistic defaults. A separate result allows unrelated
engineering to proceed without lowering scientific evidence or manufacturing
economics.

**Alternatives rejected.** Boolean/truthy flags; missing means available;
partial-cause precedence; queue rank; money/amount fields; sponsor/stake/
reputation priority; translating deferral into B-05 `INDETERMINATE`, candidate
failure, or a lower evidence threshold.

**Downstream impact.** B-05/B-E1 retain scientific sufficiency and stopping.
Wave C later owns commitments, real scheduling, funding, and admission.
Operations can bind later exact providers without changing plan identity.

**Migration cost and exact supersession path.** Replacing fixture facts with
real commitments is high and requires exact owner-issued commitment types,
security/economic/operations review, a prospective schema and normally merged
superseding decision. New readiness kinds require a new closed version and
complete missing/combined-cause tests.

**Reserved inputs.** Real validator capacity, funding, queue policy, evidence
budgets, quotas, prices, and operational commitments remain unavailable and
human/domain-owned.

## 2026-08-31 — B-02C-D7: Enforcement, cancellation, and resource receipts

**Selected approach and agent recommendation.** Keep enforcement pure: compare
one exact class metric to one point/mode-specific inclusive runtime limit and
return an exact continue/prevent-start/prevent-next/stop/fail-closed event;
launch/kill no process. Immutable stop/cancellation records enforce a complete
actor × reason × event × resulting-state matrix and bind policy/class/plan/
context, enforcement point, work-started bit, and observations so far.
Immutable receipts bind exact assessment/readiness, truthful unstarted/
incomplete/complete build, bounded frozen-artifact reuse, Challenge-bound
replicate applicability, class-bound consumption, required observed-or-
unavailable cost/latency, declared resource stage, stop cause, and exact
stop/event cross-laws.

**Rationale.** Exact provenance lets later owners audit resource behavior
without pretending it is execution authority or candidate physics evidence.
Complete-build, reuse, and replicate identities are computed independently,
avoiding a receipt cycle and false identities for partial work. Cost means
measured resource quantity, never currency/price.

**Alternatives rejected.** Raw actor strings or authorized Booleans; side-
effectful process control; silent clamping/continuation; exception fallback;
mapping resource failure to candidate failure; partial build labeled complete;
receipt-driven ranking/screening/score/promotion; monetary receipt fields.

**Downstream impact.** B-07S retains wire cancellation and task-state races;
A7 retains official lifecycle; B-07F later performs execution integration;
B-05/B-E1 may consume only explicitly registered factual resource fields and
retain all scientific evidence semantics.

**Migration cost and exact supersession path.** Connecting a real enforcer,
official lifecycle, or wire cancellation is high cross-owner work requiring a
prospective integration contract, exact authority/capability types, normally
merged decisions in the owning tickets, and race/idempotency/security tests.
Receipt-field changes require a new schema; historical receipts stay factual.

**Reserved inputs.** Real process authority, monitor trust, cancellation
issuance, backend failure policy, execution identity, accounting authority,
and operations/security acceptance remain unavailable.

## 2026-08-31 — B-02C-D8: Fixture, privacy, economics, and maturity ceiling

**Selected approach and agent recommendation.** Ship no default policy/class
and no production provenance variant. Tests build closed values carrying exact
fixture registration/source provenance and fixed non-production markers.
Public models omit protected case/stratum/seed/reference and protected
evaluator-reconstruction identity, evaluator topology/concurrency/allocation,
score/rank/margin, paths/URIs/code/credentials, and monetary/economic fields.
They permit only the explicit fixture resource-accounting build/reuse/replicate
ids and digests required by B-02C receipts. Errors are
bounded, fixed, deterministic, and non-echoing. Contract merge earns only
bounded `SPECIFIED/RATIFIED`; the exact reviewed and normally merged
implementation earns only bounded `IMPLEMENTED/TESTED/GREPTILE_REVIEWED/
MERGED`.

**Rationale.** Real limits and telemetry can disclose official topology, while
placeholder production/economic branches are easily mistaken for authority.
Structural fixtures support hostile-input and role-confusion tests without
creating production defaults or false qualification.

**Alternatives rejected.** Placeholder `PRODUCTION`, `REGISTERED`, or `LIVE`
variants; fixture-upgrade flags; public raw telemetry/logs; hidden case counts
or queue positions; price/currency/quota fields; success probability, score,
gate, frontier, settlement, weight, or emission claims.

**Downstream impact.** B-07S/disclosure owners later decide safe projection;
security/operations/economics owners must supply and qualify every real rail;
B-05/B-E1 preserve evidence/science ownership. Fixture success conveys no
scientific, security, operational, commercial, or production claim.

**Migration cost and exact supersession path.** Production activation is high
and cannot widen fixture v1 in place. It requires owner-supplied values and
evidence, privacy/threat/economic review, prospective exact schemas/authority
types, a normally merged superseding decision, and qualification gates. Any
wire projection belongs to B-07S; historical fixture bytes remain permanently
non-production.

**Reserved inputs.** Protected disclosure policy, real topology/allocation,
security acceptance, operational rails, economics, prices/quotes/quotas,
rights, qualification, LIVE, launch, production, frontier, settlement, chain,
weight, and emission authority remain unavailable and human-owned.

## 2026-08-31 — B-02B-D1: Construction package and exact A7 Strategy identity reuse

> **B-02B-D1 through B-02B-D8 status: CONDITIONAL AGENT-SELECTED WORKING
> DECISIONS.** The series becomes bounded engineering authority only if the
> exact independently reviewed B-02B working-contract tree normally merges and
> exact-main CI passes. Notification requests `KEEP`, `CHANGE`, `BLOCKED`, or
> `DEFER_TO_OWNER`; no affirmative response or silence gate applies. Human-
> reserved science, security acceptance, rights, economics, qualification,
> LIVE, launch, and production values remain unavailable and fail closed.

**Recommendation and rationale.** Add standard-library-only
`carbon.construction` above A2/B-02A and consume one explicit public
`carbon.fees.strategy_identity` seam. Extract, without changing bytes, A7's
existing accepted-Strategy snapshot and `carbon.strategy.identity.v1` hash
algorithm into that A7-owned submodule. `StrategyHash` stays the exact class in
`carbon.fees.model`; A7 private entrypoints remain compatibility delegates.
This preserves A2's validation-only boundary, A7's persistent-identity
ownership, every golden hash, and one-way dependency into construction.

**Rejected alternatives.** A second compiler hash; using B-02A document bytes
as Strategy identity; moving A7 semantics or `StrategyHash` into A2;
construction importing A7 service/store/fee policy; placing assembly semantics
in the mutable backbone registry or retired training namespace.

**Downstream impact.** A7 gains a tested explicit submodule but no public root
surface or behavior change. B-02B compiles only the returned detached accepted
snapshot and hash, never the caller graph or a caller-provided hash. B-07F may
compose these exact outputs later; A2, B-02A, and A7 never import construction.

**Reversibility and exact change path.** Module splitting and private shim
placement are reversible while the public explicit-submodule API, exact
`StrategyHash` class, hash header/frames, and persisted values remain stable.
A future identity change requires its owning prospective A7 migration and a
new identity version; B-02B cannot reinterpret existing hashes.

## 2026-08-31 — B-02B-D2: Exact nominal refs, Challenge binding, and acyclic identity

**Recommendation and rationale.** Give `CandidateAssemblyContract` and
`ParameterCatalog` distinct long-lived nominal refs using B-02A/A3 field
grammar. Give `ResolvedTrainingSamplingPolicy` and
`ResolvedConstructionPlan` digest-only nominal refs. Reuse B-02A canonical
values under the domain-separated `carbon.construction.canonical.v1` frame.
Bind full exact `ChallengeKey` out of band because Strategy v1 carries only its
family id. Keep the graph acyclic: assembly → authoring/pins/components;
catalog → assembly/support/compiler; policy → catalog/support; plan → all.
Require a capability-issued B-02A `AuthoringGraphOrigin`, verify exact graph
membership, and bind its existing scientific-authoring graph fingerprint into
the plan; raw refs alone do not preserve origin.

**Rejected alternatives.** Adding B-02B kinds to B-02A's closed six-kind
registry; a global latest registry; version ordering; self/cyclic hashes;
implicit Challenge version; digest-only trust without exact object/ref
verification.

**Downstream impact.** B-02C/B-07A/B-07F consume exact immutable refs and
cannot silently substitute a version. Historical exact bytes remain
verifiable; `stale` means mismatch, invalid lifecycle, or failed expected pin,
not merely “not latest.”

**Reversibility and exact change path.** New optional semantics require new
prospective schema/object/compiler versions. Ref kind, Challenge scope, field
order, profile, or digest-preimage changes are persisted migrations and must
not reinterpret historical refs.

## 2026-08-31 — B-02B-D3: Flat surfaces, strict types, defaults, and applicability

**Recommendation and rationale.** Interpret executable Strategy v1 parameters
only as an exact flat `surface_id -> exact scalar SurfaceValue` dictionary.
Each `ParameterCatalogEntry` binds input source, unique consumer target, exact
type/unit/domain, dependencies, applicability, compatibility, semantic owner,
lifecycle, static resources, and `REQUIRED` or literal `EXPLICIT_DEFAULT`.
Resolve every surface exactly once to `SELECTED`, `DEFAULTED`, or
`NOT_APPLICABLE`; a supplied non-applicable value rejects as unused. Materialize
default origin/value into plan identity.

Applicability is exactly `ALWAYS` or acyclic `WHEN_SURFACE_IN`, evaluated in
topological order with canonical-id tie-breaking. Entries carry closed
training-lever and component-slot bindings so the compiler never infers
`R_strategy` or component meaning from a consumer name.

**Rejected alternatives.** Nested free-form parameter paths; aliases;
dict/list/null values; bool/int or int/float equivalence; coercion, unit
conversion, clamping, computed/environment defaults, ignored unknowns, and
callable compatibility predicates. Duplicate raw JSON names are B-07S parser
work because they are unobservable after dict materialization.

**Downstream impact.** Catalog construction rejects duplicate surface ids,
selector aliases, and consumer collisions before lookup-map creation. B-07S
must reject duplicate wire members. Real values/ranges/units remain unavailable;
B-02B ships no production/default catalog.

**Reversibility and exact change path.** A later closed record-valued surface
or nested grammar requires a new catalog/schema/compiler version and complete
collision/consumption tests. Existing flat catalogs remain exact.

## 2026-08-31 — B-02B-D4: `R_strategy` isolation and context-owned randomness

**Recommendation and rationale.** Materialize one exact
`ResolvedTrainingSamplingPolicy` (`R_strategy`) and
`TrainingSamplingPolicyRef` inside the exact B-02A
`TrainingSupportContractRef`. Permit only registered `SAMPLING`, `CURRICULUM`,
and `AUGMENTATION` bindings plus abstract purpose ids/role-key labels. Always
emit an explicit base/no-override policy. Execution contexts, not Strategy or
plan, own entropy domains, seeds, and realized draws.

**Rejected alternatives.** Treating `R_strategy` as `P`, `Q`, or `w`; custom
data/loaders/distributions; seed, nonce, RNG, draw/case, EVAL/STRESS,
reference, measurement, gate, score, or qualification control; implicit policy
absence; shared practice/official entropy authority.

**Downstream impact.** Data Management and B-02A separation remain exact.
Practice and official-shaped consumers may share policy semantics while their
nominal context and A4 authority remain distinct. B-07F is not implemented.

**Reversibility and exact change path.** Adding a policy family requires a new
registered catalog/compiler version and owning science/security decision. Any
official-evidence authority requires its separate owner and cannot widen this
ref in place.

## 2026-08-31 — B-02B-D5: Fixed assembly and closed component compatibility

**Recommendation and rationale.** The Challenge owns one fixed outer assembly
workflow and closed component slots. Preserve distinct exact roles
`WARM_START`, `PRECONDITIONER_ACTION`, `COARSE_CORRECTION`,
`RESIDUAL_CORRECTION`, `SUBDOMAIN_OPERATOR`, and
`NONLINEAR_INITIAL_GUESS`. Each option binds consumer, I/O interfaces, state,
side-effect policy, fixed/trainable boundary, implementation/environment/
dependency pins, applicability/assumption refs, limitations, resources, and
public falsification refs. Fixture v1 fallback is `FAIL_CLOSED` only.

**Rejected alternatives.** Participant nodes/edges/graphs/code; role aliases;
choosing raw refs or implementations; dynamic registry lookup; silent or
participant-selected fallback; treating component labels/tests as scientific
or product qualification.

**Downstream impact.** B-07F can later reconstruct only registered fixed
semantics. B-05 gates/scoring remain dependent on protected output evidence,
not component metadata. Post-launch assembled-system/product qualification
remains owner-reserved.

**Reversibility and exact change path.** A new role, slot, option, interface,
or fallback produces a prospective assembly version and exact plan identity.
Historical assemblies are not mutated.

## 2026-08-31 — B-02B-D6: Policy-free static resource metadata

**Recommendation and rationale.** The assembly owns an exact closed resource-
dimension registry. Catalog/backbone/component entries may emit
only closed nonnegative UInt64 `FIXED` or `DISCRETE_LOOKUP` contributions.
Aggregate by exact `(dimension_id, unit_ref)` with checked addition and bind
quantities, sources, and impact tags in plan identity. Reject overflow,
unknown dimensions, missing lookup cases, or conflicting units.

**Rejected alternatives.** Arbitrary formulas/callables; runtime measurement;
ceilings, fit/admit/deny, price, quota, scheduling, kill rails, forecast
calibration, success probability, or policy receipts; silent saturation or
clamping.

**Downstream impact.** B-02C may consume the exact metadata but alone decides
policy/admission/enforcement and may not rewrite compiler semantics or plan
identity. MQ-008 qualification remains fail closed.

**Reversibility and exact change path.** New contribution algebra requires a
new construction schema/compiler version. B-02C policy changes require no
B-02B identity change when the compiled metadata is unchanged.

## 2026-08-31 — B-02B-D7: Complete plan identity and consumer-neutral parity

**Recommendation and rationale.** Bind StrategyHash, full ChallengeKey,
B-02A refs, assembly/catalog/compiler, exact backbone/components, all resolved
surface values and default origins, `R_strategy`, dependency/environment/
implementation pins, static resources/tags, the exact authoring-origin
binding, and separate assembly/catalog construction provenance into one
canonical `ResolvedConstructionPlan`. Exclude consumer mode, entropy, runtime
policy verdict, evidence, gates, scores, and qualification. Prove two nominal
fixture consumers receive byte-identical plan/ref values while retaining
different context types.

**Rejected alternatives.** A partial or ambiguous plan; hidden defaults;
consumer-specific compilation; practice/official mode in identity; seed/draw
binding; treating parity as scientific or execution qualification.

**Downstream impact.** B-07F/B-GATE can later prove composition parity without
duplicating compiler semantics. B-07F remains untouched here; identical bytes
do not grant shared authority or randomness.

**Reversibility and exact change path.** Any semantic input added or removed
requires a new plan/compiler schema version. Nominal wrappers may evolve
without changing plan identity only when they do not alter construction
semantics.

## 2026-08-31 — B-02B-D8: Hostile-input and all-or-nothing rejection boundary

**Recommendation and rationale.** Snapshot hostile Strategy input once through
the exact A7 seam, compile only the owned snapshot, and return either one
complete policy+plan package or `CompileRejected`. `CompileIssue` uses a closed
code, safe path, and fixed non-echoing message; issues sort deterministically.
Reject negative zero before B-02A canonical encoding. Reject imports, code,
executables, graphs, arbitrary dependencies, paths/URIs/network,
deserialization, custom data, seeds, official controls, and unregistered
composition. The compiler performs no dynamic I/O or runtime construction.

**Rejected alternatives.** Rereading/mutating caller input; trusting a
caller-provided StrategyHash; `repr`/value echo; partial outputs; exception-
driven fallback; dynamic import/registry/filesystem/network/environment
inspection; best-effort normalization.

**Downstream impact.** Required tests cover mutation/alias/concurrency,
catalog confusion, stale/cross-Challenge refs, authority escape, component
role/gate bypass, canonical tamper, wheel/import direction, and unchanged A7
goldens. MQ-015 production security remains `SECURITY_REVIEW_REQUIRED`.

**Reversibility and exact change path.** Adding a capability or error-visible
semantic is prospective contract/compiler work with adversarial tests. Human-
reserved production inputs remain unavailable; a bounded fixture path may
continue without issue #41 deferral.

## 2026-08-31 — B-07R-D1: Separate service planes and future transport

> **B-07R-D1 through B-07R-D8 status: CONDITIONAL WORKING ARCHITECTURE
> DECISIONS.** The whole series is effective only after the exact B-07R
> reviewed tree passes CI, every valid Greptile finding is repaired, zero
> Greptile threads remain unresolved, it normally merges, and exact-main CI
> passes. A documented invalid finding may be closed with rationale; any tree
> change requires rereview. Notification is not qualification.

**Selected approach and rationale.** Preserve the exact Wave-A seven-tool
official service and add a distinct local/in-process research plane. This
prevents research aliases or stores from acquiring official authority. B-07S
chooses exact identifiers/negotiation; Wave C owns remote transport, identity,
quotas, and quotes.

**Rejected alternatives.** Mutating v1, merging planes, a generic mode flag,
or preselecting network/authentication behavior in Wave B.

**Affected tickets; migration/change path.** A9, B-07S, B-07A, B-07G, B-07F,
B-E4, and Wave C. Migration is low before B-07S and high after clients exist.
Supersede through a normally merged change to research-contract §§6.5/8.1 and
this record; exact protocol changes belong in the B-07S contract.

**Remaining reserved input.** Production security, transport, identity, and
economics remain unavailable; local fixture work may continue.

## 2026-08-31 — B-07R-D2: Construction chain and P/Q/w/R_strategy law

**Selected approach and rationale.** Compile Strategy plus the Challenge-bound
catalog/assembly contract into one resolved plan; keep P, Q, w, and
`R_strategy` distinct; derive randomness in the authorized execution context.
This gives executable semantics without miner exam or seed authority.

**Rejected alternatives.** Inert/ignored parameters, arbitrary code/data,
miner seeds, or using `R_strategy` to control P/Q/w, stress, reference,
measurement, gates, or score.

**Affected tickets; migration/change path.** B-02A, B-02B, B-02C, B-03, B-05,
B-07S, B-07C, and B-07F. Migration is medium and prospective. Amend research-
contract §§4–5 plus B-02B's compiler contract; B-07S owns the wire projection.

**Remaining reserved input.** Real catalogs, components, backbones, training
sources, units, domains, and policies remain unavailable.

## 2026-08-31 — B-07R-D3: Research lineage and practice/official isolation

**Selected approach and rationale.** Pin each research execution to a task,
private immutable experiment record, and bounded receipt; practice remains
non-authoritative, and B-07F later consumes the same plan through unchanged
fixture-official v1. This preserves reproducibility without a second official
lifecycle.

**Rejected alternatives.** Uploading all miner history, protected per-case
returns, a caller mock/official mode, practice-to-A5/A6/A7 conversion, or a
second official store.

**Affected tickets; migration/change path.** B-07S, B-07A, B-07B, B-07C,
B-07F, B-07G, and B-GATE. Migration is medium. Amend research-contract §§6–7;
B-07S owns protocol, B-07B records, B-07C practice, and B-07F v1 consumption.

**Remaining reserved input.** Real practice science, disclosure, rights, and
security acceptance keep external practice disabled.

## 2026-08-31 — B-07R-D4: Immutable same-bytes prior

**Selected approach and rationale.** Use immutable Challenge-level packs,
exact history, atomic active resolution, publication-class ceilings, persistent
disclosure accounting, and identical bytes for every requester; personalize
only miner-side. This provides shared memory without a private oracle.

**Rejected alternatives.** Request-time private queries/LLM answers, per-miner
bytes, implicit latest, fixture promotion, or a production v2-backed v1 prior.

**Affected tickets; migration/change path.** B-07S, B-07D1–B-07D3, B-E4,
Landscape, and Wave C. Migration is medium/high because history is immutable.
Amend research-contract §9 and later prior contracts; B-07S owns wire mechanics.

**Remaining reserved input.** Estimands, cohorts, lag/cadence/coarsening,
content, rights, public approvals, and signing custody keep activation closed.

## 2026-08-31 — B-07R-D5: Conditional protected-realization leakage objective

**Selected approach and rationale.** Test incremental transcript-enabled
inference of protected realizations, stress composition, margins, or ordering
after controlling for transferable held-out physics. Genuine learning should
transfer; the protected shortcut is the threat.

**Rejected alternatives.** Minimizing practice/official correlation, isolated
endpoint review, informal noise, or claiming fixture tests qualify security.

**Affected tickets; migration/change path.** B-07S, B-07C, B-07D2, B-07E,
B-E4, and Waves C/D. Migration is low before preregistration and high after
releases. Amend research-contract §§9.6/10/12.2 and B-E4; production changes
require the later security contract.

**Remaining reserved input.** Identity/privacy basis, adversary model, utility
and diversity floors, and leakage limit remain human-owned.

## 2026-08-31 — B-07R-D6: Evidence/resource/authority ladder

**Selected approach and rationale.** Keep structural prior alignment, static
resource analysis, calibrated forecast, operational quote/admission, practice
measurement, official evidence, score, frontier, and settlement separate; use
typed deferral/indeterminacy and prohibit score/winner prediction. This prevents
resource or proxy results from becoming scientific authority.

**Rejected alternatives.** Pre-base quality denial, proxy promotion,
scientific-zero coercion, score prediction, or inferring frontier/settlement.

**Affected tickets; migration/change path.** B-02C, B-05, B-07E, B-07F, B-E1,
B-E4, A5, A6, and A10. Migration is high after persistence. Amend research-
contract §§8.2/11 and owning B-05/B-02C/B-E1 contracts prospectively.

**Remaining reserved input.** Budgets, coverage/stopping, calibration,
admission/pricing, frontier, and settlement policy stay absent.

## 2026-08-31 — B-07R-D7: B-07S delegation and implementation layering

**Selected approach and rationale.** B-07R fixes capabilities/authority only.
B-07S exclusively fixes exact objects, names, lifecycle, request/response,
errors, canonical bytes, bounds, pagination, idempotency, providers, adapter,
negotiation, and disclosure. B-07A implements shared primitives once, domain
tickets own semantics, and B-07G composes the ratified closed set.

**Rejected alternatives.** Exact B-07R wire/protocol literals, duplicated domain wire types,
B-07G semantic ownership, or implementation before B-07S.

**Affected tickets; migration/change path.** B-07S, B-07A–B-07G, B-02B,
B-02C, A2, and A9. Migration is low now/high after implementation. Architecture
changes return through research-contract §8.1; exact protocol changes stay in
B-07S's contract.

**Remaining reserved input.** None for bounded protocol engineering; external
security/rights/economics remain fail closed.

## 2026-08-31 — B-07R-D8: Delegated engineering ratification

**Selected approach and rationale.** Ratify bounded engineering architecture
after durable record/notification, applicable validation, exact-head CI,
repair of every valid Greptile finding with zero Greptile threads unresolved,
normal exact-tree merge, and exact-main CI. A documented invalid finding may
be closed with rationale; any tree change requires rereview. Silence is no
gate. This matches delegated governance while preserving human-reserved
authority.

**Rejected alternatives.** Multi-human preapproval, notification-as-approval,
architecture-as-qualification, or a recursive PR solely to restate merge data.

**Affected tickets; migration/change path.** B-07R, B-02B, B-07S, all later
Wave-B tickets, and B-GATE. Migration is low. Amend this record, contract,
Wave/board/handoff, ticket, plan, and evidence together by normal merge; keep
historical evidence and record later supersession.

**Remaining reserved input.** Science/values, security acceptance, rights,
economics, qualification, LIVE, launch, settlement, weight, emission, and
production remain unavailable.

## 2026-08-30 — B-02A-D1: Authored objects, exact refs, canonical bytes, and prospective history

> **B-02A-D1 through B-02A-D11 closeout.** PR #60 normally merged exact
> reviewed head `f285399138ecfe95352d429bc26051b0a5fecbcf`, tree
> `61a4463ac459f7fe96545f2746511d6940246f57`, as
> `58ea866de52e3853b0b45e3217ee0625302aa663` with the same tree. Greptile was
> 5/5 with no blocking failure and zero unresolved threads; exact-head CI
> `33341717012` and exact-main CI `33342015346` passed. Any candidate,
> pending-review, pending-CI, or pending-merge wording preserved inside the
> historical D1–D11 narratives describes their recording time and is
> superseded by this bounded engineering closeout. No named domain-review
> completion or reserved qualification is inferred.

> **Status: IMPLEMENTED WORKING DECISION.** This decision was first recorded
> on `agent/b-02a-contract-ratification` from exact base/tree
> `e10107644d5fb0c7d69b153c0c3b8a03b93b19bb` /
> `0f6beb5b000e771fd7e050f150e1074ea2a6fb1f`. Governance PR #61 normally
> merged as `7bdf4971b7d0b3ee8ffde577595a49c6b5456961` and removed the affirmative
> pre-implementation approval gate for agent-authorized engineering choices.
> B-02A has implemented this working decision as a bounded candidate;
> independent exact-head
> SciML/statistics/protocol review, blocking-finding resolution, validation,
> and normal merge remain required for final ticket acceptance.

**Selected approach.** Define five distinct immutable authored-contract
families plus one immutable, capability-created canonical-case realization
record, with six distinct final nominal ref types. Every top-level object carries an exact
Challenge key, object kind, canonical ID, semantic version, schema version,
canonicalization profile, and prospective same-kind supersession binding. A
ref carries the exact kind, Challenge key, ID, version, schema, profile, and
tagged SHA-256 digest. The digest is not self-embedded in authored bytes.
Authored contract or realized-case content, exact ref, trusted loader result,
structural origin, qualification state, mutable runtime events, and derived
disposition/censoring/realized-evidence records remain separate. Derived
records use distinct domain framing and external digest refs, so no record
self-embeds its digest.

Reuse A3's exact Challenge/identifier/version/digest grammar and verified-byte
reader. Because no public generic Carbon semantic serializer exists, propose
the schema-local `carbon_scientific_authoring_canonical_v1` binary profile:
an exact domain header, object-kind separation, tagged exact primitives,
big-endian fixed-width integers/binary64, strict already-NFC UTF-8, closed
records whose exact field-name/value pairs sort by UTF-8 field-name bytes,
explicit tagged unions including exact empty payloads, ordered tuples,
canonical-byte sorting for set-like tuples, a closed subordinate schema/union
registry, SHA-256, and exact engineering bounds. It is
independent of `repr`, object identity, insertion order, locale, path, time,
environment, and host endianness. Every accepted zero is canonical positive
zero. Boolean, integer, and float remain distinct.

Historical lookup is exact and content-addressed. A material change is a new
version/digest; same-kind, same-Challenge, same-object-ID acyclic supersession
is prospective only. Cross-Challenge/cross-ID supersession is forbidden in v1. No
evidence-bearing `latest`, overwrite, alias, or silent historical
reinterpretation exists.

**Controlling authority.** `CONSTITUTION.md`; `AGENTS.md`; A3 registry identity,
digest, store, and LIVE-gate owners; the scientific canon's exact identity and
prospective-change laws; locked
`Design_Specs/Challenge_Instance_Distribution.md`; the B-02A ticket's explicit
content-addressing, validation, equality, supersession, and history criteria;
and current A4/A5/A7 schema-local canonicalization precedents.

**Alternatives rejected.** A second Challenge/version/SHA grammar; path/URI or
logical-ID-only identity; digest-only cross-kind equality; a self-referential
digest field; Python `repr`, pickle, object identity, dict insertion order,
ambient JSON defaults, current filesystem/time/environment, or another
owner's private encoder; silently Unicode-normalizing input; conflating
authored content with source provenance, fixture status, qualification, or
runtime objects; mutable `latest`; open record/enum vocabularies; a
self-referential derived-record digest; and in-place historical repair.

**Affected contracts and later tickets.** All B-02A objects/refs/loaders;
B-02B compiler inputs; B-03 generator/case results; B-04 evidence refs; B-05
measurement inputs; B-06 dossier pins; B-07R/B-07S public/protocol
consumption; A3 qualification binding; later storage, package, export, wheel,
and canonicalization tests.

**Invariant effects.** Strengthens exact identity, closed-world parsing,
hash-pin, immutable history, mutation isolation, and no-authority-by-label
invariants. It creates no qualification. Exact digest verification precedes
parse, and ref/object equality is exact nominal equality.

**Migration and compatibility.** The bounded candidate adds the new
`carbon.authoring` implementation and narrowly extends A3 with the D8
fingerprint/verifier seam; no existing identity grammar is replaced. A3 is
`KEEP`; its public primitives are `WRAP/COMPOSE`. A4/A5/A7 private encoders are
pattern-only. Legacy generic loaders remain
`MIGRATION_REQUIRED` historical material and are not ported. The profile is
prospective; a later profile preserves all v1 bytes and refs.

**Reversibility.** Review may amend this working decision by normal commit. After
normal merge, semantic changes require a new prospective contract and
profile/object version; historical refs remain exact. The engineering bounds
are reviewable here but cannot be silently tuned after implementation.

**Unresolved human input.** No human scientific value is required for this
engineering identity decision. D6-D11 select package, history, A3, graph,
semantic-owner verification, and external-authority seams.
Final technical review may require prospective schema/profile amendments.

**Maturity ceiling.** `SPECIFIED: AGENT-SELECTED WORKING DECISION`.
Bounded `IMPLEMENTED` and `TESTED` candidate evidence now exists on PR #60;
final acceptance remains pending exact-head independent review, canonical CI,
and normal merge. Scientific/security/network/
commercial/production qualification, LIVE, frontier, settlement, weight, and
emission authority remain `NO`.

## 2026-08-30 — B-02A-D2: Population-role, training-support, rights, and `R_strategy` separation

> **Status: IMPLEMENTED WORKING DECISION.** It follows the delegated timing
> stated by B-02A-D1. Implementation may proceed without affirmative lead
> response; final exact-head independent review and normal merge remain due.

**Selected approach.** Represent target/workload `P`, official proposal `Q`,
and evidence weighting `w` as exact role-tagged, content-addressed contracts.
State expressly that `w` is not necessarily a probability distribution. Q
binds exact P and gains no prevalence authority; executable Q requires a
complete probability/finite-enumeration law. A set-only P owns membership but
no prevalence/expectation authority; set-only Q cannot execute a plan. w binds
exact P and binds Q whenever design-dependent under a closed role matrix, and
is never inferred from sampling frequency, allocation, or retained cases.

Give stress, practice, product-qualification, deployment, query, observation,
and evidence-campaign roles distinct identities. Keep realized valid evidence
out of the authored population enum: a protected accounting capability creates
a separate exact derived record/ref only after execution, without authority to
rewrite P/Q/w, denominators, or applicability. Every authored role binds its
claim, support/membership, law/weight semantics, collection-level stratification,
applicability, exclusions, exact rights-profile ref, permitted uses,
restrictions, provenance, disclosure contract, allowed consumers, and
prospective supersession. Common support, PDE, generator, seed family, range,
representation, storage, or rows cannot confer role identity or authority.
Applicability is always represented by a nonempty exact owner-ref set, including
an owner-issued no-additional-applicability ref when needed. Allowed consumption
uses a closed capability union; downstream-owner use additionally requires its
exact pinned consumer-contract ref. Unknown or unlisted consumers reject.

Define `TrainingSupportContract` separately with exact membership, physical
and representation invariants, permitted source/generator refs, provenance,
rights, uses, restrictions, and disclosure. Reserve `R_strategy` exclusively
for B-02B's later `ResolvedTrainingSamplingPolicy`; it operates only inside
exact Challenge-owned support and cannot redefine any official population,
draw, reference, measurement, gate, score, or qualification. Determinism and
reconstructibility provide no scientific authority.

**Controlling authority.** Scientific canon §§5–6; locked distribution
architecture §§3–5, 9, 11–13, 16, 18–20, 23–25; B-02A ticket; Data Management;
Build Out Constitutional Overlay §8; owner-approved Science/GTM integration;
Business Canon §13 rights doctrine; and B-02B ownership on the Wave B board.

**Alternatives rejected.** One generic dataset/population identity; an
author-created realized-evidence population; treating set membership as
prevalence or an executable proposal; treating Q as P/prevalence; deriving w from Q or observed frequency; representing w as
necessarily a probability law; treating training support, search data,
stress, practice, product, deployment, query, campaign, or realized retained
cases as P; allowing R_strategy to choose official cases/seeds/reference/
measurements/scores; free-text rights; rights inferred from possession or
commercial use; and untyped caller role labels.

**Affected contracts and later tickets.** `InstanceDistributionContract`,
`SamplingPlan`, `TrainingSupportContract`, `CanonicalChallengeCase`; B-02B
compiler; B-03 generation; B-04 reference/evidence campaign; B-05
estimand/weighting; B-06 qualification; B-07R public research; product and
business rights owners.

**Invariant effects.** Makes population-role confusion a closed role-tag and
expected-role-ref validation failure;
preserves target/proposal/weighting, train/eval/stress, rights, query, and
intended/realized evidence boundaries. Unknown membership, provenance, rights,
permitted use, or required scientific input rejects rather than defaults.

**Migration and compatibility.** The stale `carbon/challenges`,
`carbon/data`, and `carbon/physics` suggestions are `DOCUMENTATION_LAG` under
B-01E code authority and grant no package permission. Strategy Schema and
Miner MCP candidate examples remain unratified compatibility input. No data,
population, generator, compiler, or archive migration occurs.

**Reversibility.** Working review may revise roles and fields. A
post-merge material population/support/rights change is prospective,
versioned, requalified as required, and cannot reinterpret historical
evidence.

**Unresolved human input.** MQ-002 real P/Q/w, estimands, support, laws, strata/
stratification,
allocations, exclusions, provenance, rights, sources, uses, restrictions, and
adequacy evidence; B-02B's exact policy/compiler objects. Missing inputs leave
production authoring unavailable.

**Maturity ceiling.** Agent-selected working type/authority semantics only; no real
population, training permission, compiler, official draw, scientific
qualification, or LIVE authority is selected.

## 2026-08-30 — B-02A-D3: Physical/candidate contracts, SamplingPlan, canonical case, and disposition/censoring

> **Status: IMPLEMENTED WORKING DECISION.** Bounded B-02A implementation is
> authorized under the merged delegated protocol. Implementation evidence is
> present; DoD acceptance remains pending final independent review and normal
> merge.

**Selected approach.** Use an acyclic graph: `CandidateOutputContract` binds
exact `PhysicalSystemSpec`; physical spec does not back-reference the
candidate contract. The physical spec binds governing job/laws, assumptions,
all causal inputs, physical quantities, units, representation/shape/precision,
geometry/domain, BC/IC, time/horizon, exact envelope, exact claim, and
fail-closed missing-input behavior. The candidate contract binds every
applicable causal input and totally binds every required physical quantity to
exactly one candidate output without changing physical meaning. Missing,
substituted, extra, or unregistered-derived outputs reject. Format conformance
is not scientific evidence.

The candidate contract owns one authoritative declared candidate-input
vocabulary. Causal, BC, IC, and time/horizon bindings resolve exact IDs into
that vocabulary; v1 rejects orphan/duplicate/cross-family targets and
cross-source packing. Candidate and physical geometry/domain refs are exactly
equal in v1 because no identity-bearing geometry adapter is defined.

Only an `OFFICIAL_EVALUATION` `SamplingPlan` binds exact P/Q; every other plan
role uses the closed role matrix and acquires no official authority. Each plan
binds its base selection law, complete finite-design law, exact estimand or
reporting use, sampling/analysis unit, fixed or registered-sequential evidence
design, collection-level stratification/crosswalk/allocation,
query/observation and reference-fidelity allocations, dependence/replication,
uncertainty/tail/subgroup objectives, stopping/extension, explicit compatible
w or an exact no-w branch limited to non-aggregation or fully specified
non-official role reporting with no P/Q/w/score authority, replacement,
near-/duplicate,
inclusion/exclusion, censoring, public/protected facts, provenance, fail-closed
outcomes, and later statistics-owned qualification evidence.
It contains no realized draw, seed, protected case, or hidden stratum.

`CanonicalChallengeCase` is an immutable representation-neutral realization
record binding exact physical/candidate/population/plan, a closed generated/
observed/experimental/industrial/analytic/MMS source, representation,
query/observation/campaign/intended-slot/prospective-censoring refs, and an
identity-bearing disclosure class. Later events do not mutate it. A separate
immutable, exact evidence-use-scoped `CanonicalCaseDisposition` defines closed
`VALID`, `CENSORED`, `EXCLUDED`, and `GENERATION_FAILURE` shapes. Censoring
binds an exact scoped evidence unit, closed reason/typed-trigger matrix,
actor/policy authority, population, plan, campaign-applicability binding,
query/observation,
missingness, replacement, intended/realized accounting, audit, and use
restrictions. Its campaign binding must exactly equal the evidence scope's
binding, including exact inapplicability for a campaign-free scope. A candidate
timeout cannot be censored. Post-draw exclusion
requires preregistered screening and inclusion-probability accounting.
Fixed/sequential outcome-access branches are exact, adaptive access is gated by
complete base evidence and matching coverage/full-design refs, and replacement
decisions must exactly reconcile the plan's NEVER/registered policy,
state/reason trigger, lineage, and accounting.
Generation, reference, candidate, measurement, authoring, exclusion, and
infrastructure failures remain distinct.

**Controlling authority.** Locked distribution architecture §§4–10, 13–19,
24–26; B-02A ticket; Physical/Generator Creation and Validation owners;
Evidence and Envelope Standards; scientific canon; MQ-001/MQ-002
fail-closed classifications; and A3/A4 identity/protection boundaries.

**Alternatives rejected.** A generator-defined physical job/population;
physical↔candidate digest cycle; optional/ambient causal inputs; unbound
required physical outputs; implicit
units/shapes/horizon; unapproved Burgers defaults; one SamplingPlan object
that mixes P/Q/w or realized draws; mutating a case after reference/censoring;
one ambiguous `failed` state; treating reference/infrastructure failure as
candidate failure or score zero; silent retry/easy-case selection; and
dropping censored attempts from intended accounting; ad hoc stopping or
extension; treating Q alone as the full finite design; and global censoring of
a case because one evidence scope failed.

**Affected contracts and later tickets.** All six B-02A object/ref families;
B-03 generator requests/results and runtime disposition production; B-04
reference outcomes; B-05 measurements; B-06 Dossier statistics; A4 protected
draw/seed boundary; B-E1 later dependence/reconstruction evidence.

**Invariant effects.** Complete causal inputs and exact physical meaning;
envelope/claim pinning; generator/population separation; intended-versus-
realized accounting; explicit exclusion/censoring/replacement; and no
candidate punishment for Carbon reference/infrastructure failure.

**Migration and compatibility.** Missing exact B-02A runtime objects were
`IMPLEMENTATION_LAG` at the original contract base and are resolved by the
bounded candidate. The absent referenced
`Physical_System_Representation.md` is inherited `DOCUMENTATION_LAG`; locked
distribution/canon/current domain owners control the seam. PR #40's viscosity
issue is recorded but no value, JAX code, dependency, or reference witness is
adopted.

**Reversibility.** Fields/state taxonomy may be amended in working review. After
normal merge, material physical/population/plan/censoring changes are new
versions and prospective. Historical case/disposition/evidence bindings stay
exact.

**Unresolved human input.** MQ-001 first physical/candidate identity and
values; envelope/claim; MQ-002 P/Q/w/estimand/strata/counts/allocations;
sampling units, dependence/replication, query/observation and fidelity
allocation, statistical objectives, stopping/extension, duplicate,
replacement, exclusion/censoring/missingness, denominator, sensitivity, and
sufficiency rules; source/generator/representation owners. Missing values
leave production authoring unavailable.

**Maturity ceiling.** Agent-selected working authored schema and failure
semantics. No real/registered/production physical value, plan, generator, case,
evidence, qualification, or LIVE exam has been created; fixture and derived
records exercise only the bounded engineering contract.

## 2026-08-30 — B-02A-D4: Evidence-role isolation, protected case identity, and fixture/LIVE separation

> **Status: IMPLEMENTED WORKING DECISION.** Implementation proceeded under
> PR #61 governance. Independent final technical review remains pending; no
> human-reserved evidence, security, qualification, or LIVE value is supplied.

**Selected approach.** Bind analytic, semi-analytic, manufactured-solution,
numerical, experimental, industrial, and prospectively registered hybrid
evidence through exact `CaseEvidenceBinding` records. Each carries its own
authoritative protected case ref, separate optional public projection,
campaign, evidence-population, artifact, claim/applicability,
query/observation, B-04 policy, provenance, disclosure, and use restrictions.
A public projection never substitutes for authoritative case identity. No role
transfers authority to another because it shares a case.

Require MMS and other verification campaigns to have distinct campaign and
verification-population identities. MMS may verify implementation but cannot
be relabeled as target/workload prevalence, physical model validation,
deployment/context-of-use, product qualification, or LIVE evidence.

Make raw `CanonicalChallengeCaseRef` internal/protected. Define distinct
protected, internal, and public nominal projections. Public projection uses
only an A4/security-owned opaque nonreversible handle and a closed, versioned
fact-binding enum under exact disclosure/issuance refs;
it exposes no raw case digest, reversible draw/slot ID, seed, entropy, hidden
stratum, exam order, replacement chain, protected composition, or sensitive
generator input.

Keep fixture/draft/registered origin in a non-caller-constructible trusted
loader provenance union with exact registration/authority/provenance refs,
not authored bytes or a Boolean. A closed graph join makes any fixture node
fixture-derived, any draft/unresolved/unverified node nonregistered, and a graph
registered only when every node/evidence pin verifies. Fixture provenance
propagates and is not cleansed by hashing, copying, renaming, supersession,
registration, or reconstruction. Later revocation blocks prospective use but
does not rewrite historical pins. No fixture-authored object/ref/case can
satisfy A3 LIVE.

**Controlling authority.** B-02A ticket; Science/GTM Integration Plan §4;
locked distribution architecture §§14–16, 19, 23–26; Data Management;
Trustless Verification; A3 fixture/LIVE gate; A4 nominal origin/protected
projection patterns; B-04 ownership.

**Alternatives rejected.** One evidence label with inherited authority;
relabeling MMS; case identity as evidence qualification; public raw content
hash or reversible/truncated draw ID; caller-controlled audience redaction;
embedding seed/entropy/hidden strata; caller Boolean/string fixture or LIVE
status; an open-ended projection allow-list; public projection as authoritative
case identity; treating a digest as authenticated origin; and letting B-02A define
B-04 qualification or A4 opaque-handle cryptography.

**Affected contracts and later tickets.** Canonical case/ref/projections;
case evidence/censoring records; B-04 truth/reference qualification; B-06
Dossier; B-07R public research surfaces; A3 LIVE; A4 protected entropy and
public commitment/handle owners.

**Invariant effects.** Strengthens no-leakage, no-self-qualification,
evidence-role isolation, MMS non-transfer, fixture non-promotion, and
public/internal/protected separation. Errors/logs/repr/serialization must not
echo protected identity.

**Migration and compatibility.** Current A3/A4 mechanisms remain `KEEP`; B-02A
composes their public boundaries without importing private helpers. The narrow
A3 persistent fingerprint/verifier gate changes under D8; no Challenge
identity, qualification owner, seed scheme, A4 private helper, or archive
component changes.

**Reversibility.** Working review may change projection fields. After normal
merge, disclosure/handle/evidence-role changes are prospective
versions; historical disclosure and evidence authority do not expand
retroactively.

**Unresolved human input.** B-04 evidence qualification; later hybrid role;
A4/security opaque public-handle design and qualification; disclosure policy;
rights; and final independent technical review. These values remain fail
closed while unrelated B-02A implementation proceeds.

**Maturity ceiling.** Identity and prohibition semantics only. No reference
is qualified, no handle is security-qualified, no fixture is official, and
no LIVE, public research, product, or production authority exists.

## 2026-08-30 — B-02A-D5: Downstream ownership, implemented test contract, and ticket stop

> **Status: IMPLEMENTED WORKING DECISION.** The original contract-delivery
> stop was valid when recorded, then superseded prospectively by governance PR
> #61. The downstream ownership and test boundaries remain controlling.

**Selected approach.** B-02A supplies only immutable scientific authoring
objects, exact refs, canonical identity, case/provenance/disclosure seams, and
the implemented B-02A test matrix. B-02B owns assembly/compiler/
R_strategy; B-03 generation; B-04 reference policy; B-05 measurement/scoring;
B-06 Dossier; B-07R research architecture; B-07S wire protocol; A3 LIVE; A4
entropy/seeds/protected handle security.

The implementation execution plan selects package, history, A3, graph,
semantic-owner verification, and external-authority seams through delegated
decisions D6-D11. The implementation matrix covers exact
types, malformed input, canonical bytes/hash pins, equality,
immutability, supersession/history, physical/candidate consistency,
population/R_strategy confusion, query/observation/campaign binding,
censoring/accounting, MMS, protected disclosure, fixture inability to satisfy
LIVE, exports/dependencies, clean wheel, and isolated imports.

The same branch and draft PR continue through bounded implementation. Issue
#42 receives D1-D11 working-decision notification. The final candidate requires
independent SciML/physics, statistics, and protocol review. This session stops
before B-02A merge and does not begin another ticket.

**Controlling authority.** B-02A ticket/DoD; Wave B dependency board and
accountable-review routes; B-01E code authority; evidence README; execution
protocol; AGENTS reservation of human science/security/rights/production
decisions; and non-blocking lead-notification governance.

**Alternatives rejected.** Selecting a retired or merely empty package;
putting all objects into A3 registry or A2 schema by convenience; importing
later owners upward; changing dependencies, lock, workflow, or environment;
treating implementing agents as independent reviewers; making notification or
silence into approval; checking the first DoD box before its review/merge
clauses; merging B-02A without authority; and beginning another ticket.

**Affected contracts and later tickets.** B-02A implementation plan and test
surface; package/code-authority/CI integration; all downstream Wave B
consumers; issue #42 notification; draft PR review route.

**Invariant effects.** Preserves dependency direction, one-ticket scope,
review independence, exact manifest, unearned maturity, and fail-closed human
authority. Test results are recorded only after they exist.

**Migration and compatibility.** No retired/archive migration is authorized.
D6-D11 add a prospective canonical package, immutable store, A3 verifier,
exact graph, owner-verification, and external-authority seams while preserving
A2–A9 authority and zero undeclared dependencies.

**Reversibility.** The working contract and implementation may be amended by
normal commits and reviewed prospectively. A later semantic change creates a
new version/ref; no branch or evidence history is rewritten.

**Unresolved human input.** Final reviewer findings, normal merge authority,
and all reserved scientific/rights/security values. Package/storage/A3/graph/
owner-verification engineering choices are selected in D6-D11 and remain
changeable by an observed
lead direction or final review finding.

**Maturity ceiling.** `SPECIFIED: AGENT-SELECTED WORKING DECISION`; bounded
`IMPLEMENTED` and `TESTED` candidate evidence is present on PR #60. Final
repository acceptance still requires exact-head review, canonical CI, and
normal merge. No downstream qualification or LIVE authority is earned.

## 2026-08-30 — B-02A-D6: Canonical `carbon.authoring` package and export boundary

> **Status: IMPLEMENTED WORKING DECISION.** Selected under the normally
> merged delegated-decision governance at exact main
> `7bdf4971b7d0b3ee8ffde577595a49c6b5456961`, tree
> `109bb59e117d25cbdfddcc4c4a8fe6e3f3f34cdb`. Lead notification is required;
> affirmative response is not a pre-implementation gate.

**Selected approach.** Add `carbon/authoring` as a new canonical role package.
It owns B-02A exact types, canonicalization, loading, graph-origin composition,
history, and controlled projection/result factories. The package root exposes
an ordered allow-list of public-safe contracts, refs, enums, errors, and
operations. Protected case refs, origin issuers, raw storage primitives, and
capability constructors remain in explicit internal modules and are not root
convenience exports. Dependency direction is `carbon.authoring` to the standard
library and minimal public A3 identity/digest primitives only. Add
`carbon/authoring` to `.agent/CODE_AUTHORITY.toml` and installed-wheel/import
coverage; `pyproject.toml` stays unchanged because `carbon*` already includes
the package.

**Controlling authority.** B-01E code authority; B-02A ticket and working
contract §§4, 12, 14–15; constitutional overlay package guidance; current A3,
A4, A2, package, wheel, and import-boundary ownership.

**Alternatives rejected.** Retired `carbon/challenges`, `carbon/data`,
`carbon/physics`, or `carbon/sciml`; overloading A2 `carbon.schema`; placing
immutable B-02A history in A3 `carbon.registry`; using downstream
`evaluation`, `qualification`, or `audit`; a flat top-level module; exporting
protected internals; adding a dependency; or changing package metadata merely
for discovery.

**Affected contracts and later tickets.** All B-02A public imports; B-02B–B-06
consumption; B-07R/B-07S safe surfaces; A3/A4 seams; code-authority, wheel, and
outside-tree tests.

**Invariant effects.** Preserves retired-path quarantine, owner dependency
direction, exact public/protected disclosure, no undeclared optional-heavy
imports, and one-ticket scope.

**Migration and compatibility.** Prospective package addition only. No current
package is renamed or replaced, no legacy/archive code is migrated, and no
existing top-level Carbon export is changed.

**Reversibility.** Before normal merge, a review or observed `CHANGE` may move
the package by normal commit. After consumers bind it, relocation requires a
prospective compatibility/migration change; historical refs remain unaffected.

**Unresolved human input.** None for package placement. Real scientific,
rights, disclosure-security, and qualification values remain separately
reserved.

**Maturity ceiling.** Engineering package selection only. It confers no
scientific, security, network, commercial, production, LIVE, or launch state.

## 2026-08-30 — B-02A-D7: Append-only exact-ref history and immutable origin

> **Status: IMPLEMENTED WORKING DECISION.** Selected under the same delegated
> authority and intervention rules as B-02A-D6.

**Selected approach.** Implement a B-02A-owned create-only filesystem store
indexed by the complete exact ref and bounded canonical bytes. A store write
uses exclusive creation and rejects conflicting bytes, refs, origin, or
supersession. Exact historical retrieval never resolves through `latest`,
alias, object ID alone, or a newer version. Supersession is same kind,
Challenge, and object ID only; the predecessor must exist and cycles reject.
Origin is an immutable, separately stored registration bound to the exact ref.
The effective graph origin is the least-authoritative join: any fixture node
makes the graph fixture-derived; any draft, missing, revoked-for-new-use, or
unverified node makes it unresolved. Copying, hashing, superseding, or
re-registering cannot upgrade origin. Prospective revocation blocks new use
without deleting or rewriting historical content or origin evidence.

**Controlling authority.** Constitution immutable-evidence doctrine; B-02A
working contract §§4.4, 12.3–12.4, 13, 15.4–15.5; scientific canon prospective
change; A3 store analysis showing draft/fixture replacement semantics are not
B-02A history semantics.

**Alternatives rejected.** Reusing `RegistryStore.save`; mutable latest;
overwrite-in-place; logical-ID-only lookup; origin embedded in authored bytes;
caller fixture/registered Booleans; allowing a later registration to cleanse a
fixture digest; deleting old bytes on supersession/revocation; ambient
filesystem/network resolution; or an unbounded parser/read.

**Affected contracts and later tickets.** All authored and case refs, loader
results, graph origin, A3 verifier D8, B-02B–B-06 exact pins, dossier/history
evidence, and fixture/LIVE tests.

**Invariant effects.** Strengthens immutable history, exact pinning, mutation
isolation, no placeholder LIVE, structural fixture propagation, and no silent
reinterpretation.

**Migration and compatibility.** New prospective store only. A3's existing
store remains unchanged in ownership and continues to serve A3 lifecycle
records. There is no legacy data migration.

**Reversibility.** Storage layout may change before merge while tests preserve
exact semantics. After exact refs are stored, layout migrations must preserve
every canonical byte, ref, immutable origin, and historical lookup.

**Unresolved human input.** Real registration authority, provenance evidence,
rights, retention policy, and production storage operations remain human-owned
or later-owned. Their absence leaves origins draft/unresolved; fixture tests
remain available.

**Maturity ceiling.** Bounded local storage/history implementation only. It is
not authenticated provenance, security qualification, production operations,
scientific qualification, or LIVE authority.

## 2026-08-30 — B-02A-D8: A3-owned scientific-authoring verifier seam

> **Status: IMPLEMENTED WORKING DECISION.** Selected under the same delegated
> authority and intervention rules as B-02A-D6.

**Selected approach.** A3 defines an exact `ScientificAuthoringVerifier`
provider protocol and exact eligibility result/reason grammar. Every
production `assess_live_eligibility`, `can_go_live`, `activate_live`, and
`is_effectively_live` path requires the configured verifier to return a valid
exact result for the exact `ChallengeKey`. A missing provider, exception,
wrong result type, key mismatch, incomplete graph, fixture-derived origin,
draft/unresolved origin, or prospective revocation is ineligible. B-02A
implements a store-backed provider that resolves a prospectively bound exact
authoring graph and reports eligibility only after full origin and Challenge
agreement. A3 never imports `carbon.authoring`; the dependency remains
B-02A-to-A3. Fixture-mode diagnostics are explicitly non-production and cannot
activate LIVE.

**Controlling authority.** A3 owns lifecycle and LIVE; B-02A owns structural
authoring origin; A4 owns entropy/seeds and future opaque-handle security;
working contract §§13–14 and the ticket's direct fixture-to-LIVE rejection
criterion; repository fail-closed provider patterns.

**Alternatives rejected.** A caller `fixture`, `qualified`, or `live` Boolean;
trusting an artifact digest without graph-origin verification; making B-02A
activate or qualify a Challenge; importing B-02A from A3; an optional bypass
for production activation; checking only initial activation but not later
effective-LIVE reads; or treating fixture-mode readiness as production LIVE.

**Affected contracts and later tickets.** A3 registry constructor and LIVE
diagnostics; B-02A graph/store adapter; B-06 qualification evidence; A4
protected identity; every consumer that relies on effective LIVE.

**Invariant effects.** Directly enforces LIVE-requires-human-qualification
without allowing fixture origin, preserves A3 ownership, fails closed on
provider faults, and prevents post-activation authoring-origin drift from being
silently ignored.

**Migration and compatibility.** `ChallengeRecord` and
`QualificationManifest` add the optional exact tagged-SHA-256 field
`scientific_authoring_graph_fingerprint`, so legacy/fixture records remain
parseable. Production eligibility, activation, and effective-LIVE reads require
both pins, require them to be equal, pass that exact fingerprint to the
configured verifier, and require the exact result echo to match. Missing,
malformed, mismatched, failing, or substituted provider results fail closed;
absence is never a legacy production allow path. No existing record is
silently promoted or rewritten.

**Reversibility.** The provider interface may be amended before merge. After
adoption, changes must preserve fail-closed activation/revalidation and require
a prospective interface/version migration.

**Unresolved human input.** Scientific qualification evidence and the decision
to activate any real Challenge remain A3/human-owned. Real registration and
security acceptance remain unavailable. The seam itself needs no scientific
value.

**Maturity ceiling.** Structural eligibility integration only. A successful
graph-origin check is necessary, never sufficient, for A3 LIVE; all existing
human qualification slots still control and no real activation is performed.

## 2026-08-30 — B-02A-D9: Exact authoring-graph manifest and peer-root connectivity

> **Status: IMPLEMENTED WORKING DECISION.** Selected under the same delegated
> authority and intervention rules as B-02A-D6. The bounded implementation and
> focused exact tests are present on PR #60; final exact-head review, CI, and
> normal merge remain pending.

**Selected approach.** Treat an `AuthoringGraphBinding` as one exact, externally
pinned composition manifest: `root_ref` plus the sorted, duplicate-free
`required_refs` are the complete allowed node set. Resolve every bound member
by exact ref; require every member's declared top-level dependency to be in
that set; reject omitted dependencies, undeclared additions, cross-Challenge
nodes, cycles that exceed bounded traversal, and any member that is not in the
root's connected component when dependency edges are considered undirected.
The undirected connectivity rule is deliberate: top-level authoring contracts
are peer roots that may share exact candidate/physical dependencies without
claiming that training support, an official SamplingPlan, or a canonical case
owns the other. Validate the complete loaded set with the closed B-02A domain
dispatcher. Bind the root, complete sorted ref set, joined structural origin,
origin-evidence set, and composition-audit ref into the exact graph
fingerprint supplied to A3.

**Controlling authority.** B-02A working contract §§3–4 and §§13–14; D1 exact
identity, D2 population/training-support separation, D7 immutable loading, D8
A3 ownership; the contract's closed six-kind top-level registry; A3 exact-pin
and fail-closed invariants.

**Alternatives rejected.** Directed reachability from one authored object,
which cannot include the peer `TrainingSupportContract` without changing its
semantic owner; inventing a seventh authored composition-root kind outside the
v1 closed registry; seeding arbitrary required refs without a connectivity
check; adding a training-support ref to each case or SamplingPlan; trusting a
caller-declared completeness Boolean; or fingerprinting only the root.

**Affected contracts and later tickets.** B-02A store-backed verification and
A3 fingerprint pinning; B-02B compiler inputs; B-03 case generation; B-04/B-05
evidence bindings; B-06 exact dossier manifests; B-07R/B-07S safe protocol
projection.

**Invariant effects.** Preserves exact complete-graph pinning, nominal
Challenge separation, P/Q/w/training-support ownership, fixture propagation,
no silent graph injection or omission, and one-way B-02A-to-A3 dependency.
Connectivity is structural only and confers no scientific adequacy.

**Migration and compatibility.** Prospective v1 implementation only; no stored
B-02A graph exists to migrate. A later change to graph membership or semantics
requires a new exact manifest/fingerprint and cannot reinterpret a historical
qualification or evidence event.

**Reversibility.** Low before normal merge. After A3 qualification manifests
pin fingerprints, changing membership semantics requires a prospective
versioned migration while retaining historical resolution.

**Unresolved human input.** The actual registered graph, composition audit,
registration authority, scientific qualification evidence, and LIVE decision
remain human/owner supplied. Their absence leaves the graph draft/unresolved
or A3-ineligible.

**Maturity ceiling.** Structural manifest composition and test evidence only;
no scientific, security, network, commercial, production, or LIVE authority.

## 2026-08-30 — B-02A-D10: Exact SciML/statistics verification at cyclic semantic joins

> **Status: IMPLEMENTED WORKING DECISION.** Selected under the same delegated
> authority and intervention rules as B-02A-D6. The bounded implementation and
> focused exact tests are present on PR #60; final exact-head review, CI, and
> normal merge remain pending.

**Selected approach.** Keep the six authored identities acyclic and require
separate, non-serialized owner verifiers where correctness depends on content
owned outside B-02A. A configured SciML verifier receives an exact immutable
request binding the physical/candidate refs, full transient `TimeContract`,
full candidate-input tuple, and `TimeHorizonBinding`; its exact nominal result
must echo the request and map time coordinate, horizon, and endpoint exactly
once to distinct bound candidate IDs and the three pinned equivalence refs. A
configured statistics verifier receives the exact `SamplingPlanRef`, complete
plan, resolved primary/selection and optional P/Q/w population objects. The
complete plan transitively binds the estimand/reporting ref, full-design ref,
and every finite-design control; they are not separately omittable request
fields. Its exact nominal result must echo the complete request and select only
`EXACT_W_ADMITTED`, `NO_W_NONAGGREGATING_AUTHORIZED`, or
`NO_W_NONOFFICIAL_REPORTING_AUTHORIZED` in the role-compatible branch. Missing,
throwing, wrong-type, subclass, Boolean, mapping, stale, cross-plan, or
one-field-mismatched results fail the complete graph closed. Structural
validation still runs first and rejects contradictions no owner can waive.

**Controlling authority.** B-02A working contract §§5, 8, 12, and 15; D1 exact
identity, D2 P/Q/w separation, D3 causal and SamplingPlan ownership, D8 A3
fail-closed verification, and D9 complete-graph composition; SciML owns
semantic equivalence and statistics owns estimand/design/weight adequacy.

**Alternatives rejected.** Mutual content-addressed plan↔w refs; role-only
consumer admission; unit equality as time/horizon equivalence; accepting one
correct time field plus unrelated fields; inferring unit weights from P=Q or
frequency; caller Booleans/labels; embedding a scientific judgment in the
codec; or making B-02A select production values.

**Affected contracts and later tickets.** B-02A graph validation and A3
eligibility; B-02B plan compilation; B-03 generator inputs; B-04/B-05 evidence
and estimand semantics; B-06 qualification evidence. No later-ticket runtime
is implemented.

**Invariant effects.** Prevents P/Q/w and full-design substitution, implicit
weighting, causal time-semantic loss, stale authority replay, and circular
hash identities. Owner verification is necessary but does not qualify science
or authorize LIVE.

**Migration and compatibility.** The verifier results are external
composition evidence and do not enter v1 authored canonical bytes. A changed
plan, full-design law, estimand, candidate, physical contract, or equivalence
mapping creates a different request and cannot reuse the earlier result.

**Reversibility.** Low before merge. A later durable registry or signed receipt
can implement the same exact protocols without changing authored identities;
changing admitted semantics requires prospective contract/version work.

**Unresolved human input.** Real equivalence findings, the first full design,
estimand/reporting authority, w/no-w decision, statistical qualification, and
production registration remain SciML/statistics/human inputs. Missing providers
leave only the affected production graph incomplete.

**Maturity ceiling.** Typed fail-closed owner seams and deterministic tests;
no scientific qualification, evidence sufficiency, security acceptance, or
LIVE authority.

## 2026-08-30 — B-02A-D11: Exact external authority for projections and realized evidence

> **Status: IMPLEMENTED WORKING DECISION.** Selected under the same delegated
> authority and intervention rules as B-02A-D6. The bounded implementation and
> focused exact tests are present on PR #60; final exact-head review, CI, and
> normal merge remain pending.

**Selected approach.** Treat raw case projections, `CaseEvidenceBinding`, and
accounting inputs as authored claims, not authority. Package-internal adapters
accept explicit A4/protocol, B-04/history, and statistics/history provider
objects—not callbacks or caller Booleans—and require exact immutable nominal
echo records. Projection authorization echoes the exact issuance authority,
case ref, and projection. Evidence-binding authorization echoes every case,
artifact, role, campaign, population, claim, applicability, provenance,
qualification, disclosure, and restriction field, so a role/campaign/claim
copy is a different unauthorised claim. Evidence accounting first verifies the
exact intended-unit manifest and plan/P/Q/w/estimand/policy pins, then requires
a final authority result binding the complete canonical disposition set and
every exact loaded censoring record. Only that finalized capability may create
`RealizedValidEvidenceRecord`; historical loading revalidates the expected
digest/ref and the same final composition. Raw callables, mappings, tuples,
wrong nominal types, subclasses, missing/extra/substituted dispositions, and
fabricated censor refs fail closed.

**Controlling authority.** B-02A working contract §§9–13 and §15; D3
case/censoring semantics, D4 evidence-role and protected-identity separation,
D7 immutable history, A4 protected identity ownership, and B-04/B-06 future
qualification/history ownership.

**Alternatives rejected.** Module-private names plus self-affirming lambdas;
caller `fixture`, `qualified`, `valid`, or `complete` flags; reusable
pre-final capabilities; accepting digest-pinned realized bytes without exact
disposition/censor history; exposing raw protected case refs at package root;
globally banning legitimate separately registered evidence; or inventing a
signature, credential, B-04 policy, or production registry inside B-02A.

**Affected contracts and later tickets.** Case projections and safe protocol
surfaces; B-04 reference evidence; B-05 measurement/evidence consumption;
B-06 dossier history; A3 LIVE inputs; A4 protected identity; B-07R/B-07S
disclosure. Their semantic owners remain unchanged.

**Invariant effects.** Prevents callback-created authority, evidence-role
relabel, protected case mispairing, silent disposition substitution, fabricated
censor history, and fixture/LIVE authority transfer. Infrastructure/provider
failure remains non-scientific and fails the affected composition closed.

**Migration and compatibility.** New prospective non-root adapters and the
new closed owner-ref kind `evidence_binding_authority`; no historical B-02A
record exists to migrate. Exact authored and derived canonical bytes remain
versioned; later durable authority systems can satisfy these seams without
rewriting history.

**Reversibility.** Medium: internal provider/result APIs may change before
merge; once downstream owners register evidence, changes require prospective
compatibility while preserving exact historical receipts and records.

**Unresolved human input.** Real projection issuance, evidence registration,
accounting manifest, disposition/censor history, authentication/signatures,
rights, retention, security qualification, and scientific qualification remain
external owner inputs. Their absence prevents authoritative production use but
not fixture/schema tests.

**Maturity ceiling.** Trusted in-process authority separation and exact
verification only. It is not cryptographic authentication, durable production
registry, B-04 qualification, security qualification, or LIVE authority.

## 2026-08-30 — B-01E-D1: Canonical development environment and legacy quarantine

> **Authority timing.** Executive-owner direction on 2026-08-30 authorized
> this bounded candidate after B-01's authoritative closeout. The final
> independently reviewed implementation head
> `2025e235c83a994ed4f16c9a3a9d3c2766700061`, tree
> `4a506a1ae46cfcbf180eb5dbf68ed50caa0f1e09`, normally merged in PR #58 as
> `b4744a435e8bc7220c7dc03e6a993bb0a54c16a5`, and exact-main run
> `33319267255` passed. The separate documentation closeout now proposes
> B-01E `done` and B-02A as the next selected `todo`; it makes no new material
> decision. Until that exact closeout head is independently reviewed with
> blocking findings and threads resolved, passes required PR CI, normally
> merges under separate authorization with the reviewed tree preserved, and
> passes exact-main closeout CI, B-01E's prior authoritative status remains
> `in_progress` despite any prospective closeout token on a branch or newly
> merged main; B-02A and every later ticket remain `todo` and unstarted.

**Affected scope and sequencing.** Insert B-01E between B-01 and B-02A:

```text
B-01 → B-01E → B-02A
```

This changes Wave sequencing, development-environment authority, and
cross-ticket reuse dispositions only. It does not modify public runtime or
scientific interfaces and creates no scientific, security, economic, network,
`LIVE`, frontier, product, settlement, weight, emission, launch, commercial,
or production authority.

**Selected environment.** Ordinary Carbon evidence uses Linux, Ubuntu 24.04
LTS with glibc, bash, one repository-pinned CPython 3.11 patch, pinned `uv`,
and committed `uv.lock`. The dev container pins its base/tooling images.
Native Windows Python is not a canonical evidence platform; Windows and macOS
are editor/container hosts. A WSL2 clone should live in the Linux filesystem.
Local and GitHub acceptance share `./scripts/dev/ci.sh` rather than duplicating
test semantics. A later Python version or compatibility matrix requires a new
explicit ticket.

**Dependencies.** The default locked environment includes only core Carbon
and the `dev` group. `science-jax`, `science-torch`, and `chain` are explicit
optional groups. JAX, Torch, neuraloperator, PhysicsNeMo, Bittensor, Julia,
CUDA, NVIDIA, and GPU packages are not ordinary documentation, protocol,
schema, fixture, or core-engineering prerequisites.

**Selected archive model.** Preserve exact pre-quarantine main commit
`4ee58d56862d0441d5d151d79db1fe3036f1025d`, tree
`9f767ea16ffb7185ab64acff2542c7a8dcc2e339`, under immutable annotated tag
`archive/pre-wave-b-legacy-2026-08-30` and browsable branch
`archive/legacy-prototypes`. Both remote refs must be verified before active-
main removal and must not be force-updated during B-01E.

**Disposition rule.** B-01 remains historical audit input; its classifications
are not rewritten into retroactive deletion authority. B-01E applies:

- `KEEP` → `KEEP_MAIN`;
- `WRAP` → keep only when an authorized active/future ticket needs the source
  directly, otherwise archive;
- `REPAIR` → keep only when the near-term owner should repair it in place,
  otherwise archive;
- `REPLACE` or explicit historical/excluded → `ARCHIVE_REMOVE_MAIN` after
  dependency proof; and
- `NEW_OWNER_DECISION_REQUIRED` → `DEFER_OWNER_DECISION`.

Before removal, each path/component must be proven unnecessary to canonical
implementation, CPU/invariant tests, packaging, default CI, current fixtures,
active scripts, and current authority files as executable input. A historical
text reference does not require executable bytes on main. Authoritative or
evidentiary documents stay when their authority notices remain correct.
Mixed directories are decided at file/component granularity. No physical
value, population, threshold, measurement weight, or qualification rule is
copied, blessed, or reinterpreted by this decision.

**Code-authority invariant.** A repository-native machine-readable record
names canonical implementation/test roots, exact archive identities, retired
runtime namespaces, retired executable paths, and exceptions. A semantic
test fails closed if canonical code/tests import retired namespaces, packaging
contains retired modules, default CI invokes archived code, or a retired path
reappears without an owning migration ticket. Existing A12 invariants are not
weakened.

**Alternatives rejected.** The owner rejected native host Python as equivalent
evidence; a default multi-Python matrix; independent local and GitHub setup
logic; default heavy scientific/network/GPU stacks; deletion without archive
provenance; wholesale removal based only on directory names; retaining all
historical executables on active main; and repairing obsolete code merely to
keep it active.

**Reversibility and retrieval.** Removed bytes remain available by exact
`git show archive/pre-wave-b-legacy-2026-08-30:<path>` or by inspecting branch
`archive/legacy-prototypes`. A later owner ticket may deliberately port only a
justified component under then-current authority. Archive presence alone
grants no implementation authority. Environment evolution requires an
explicit reviewed change and regenerated lock.

**Lead notification.** Issue #42 is the durable route and mentions designated
lead `@harshaa765`. Delivery is non-blocking; a lead `REQUEST_CHANGES` review
or explicit `BLOCKED` direction pauses the affected change. The exact comment
and draft PR are recorded in `.agent/evidence/wave_b/b-01e.md` when created.

## 2026-08-29 — Executive Wave B development governance and lead notification

> **Authority timing.** This documentation-only governance candidate changes
> repository authority only after its exact head is independently reviewed, its
> required CI is green, and it normally merges. Until that merge, current main
> remains at Wave A closed in bounded engineering scope, Wave B inactive, B-01
> `todo` and unauthorized, and no active implementation wave. This candidate
> does not start B-01.

**Executive authority and designated lead.** Ryan Bequette (`@jbequ5`), acting
as Carbon's executive owner, has removed prior role approval as a prerequisite
to begin, continue, or normally merge bounded development authorized by the
active wave and selected ticket. Harshdeep Sharma (`@harshaa765`) is Carbon's
designated SciML / Technical Lead. Development authorization comes from the
current merged `.agent/WAVE.md`, its controlling ticket register, the selected
ticket, applicable specifications and invariants, and the repository's normal
branch, test, CI, technical-review, and merge process.

After this governance change normally merges, development requires neither an
eight-role approval set, an exact-byte approval bundle, a prospective
activation-approval record, nor a separate activation closeout before B-01.
The absence of a lead response, reaction, or affirmative approval does not
block authorized development. This governance change itself activates only
Wave B's bounded development authority and selects B-01 as the next `todo`
ticket; B-01 begins only through its own later ticket branch.

**Material development decision.** A material decision changes or selects any
of the following:

- architecture or domain ownership;
- a contract or invariant;
- a public interface or persisted schema;
- a scientific assumption or evidence interpretation;
- a security or disclosure boundary;
- a rights or data-use policy;
- an operational or resource policy;
- Wave or ticket sequencing; or
- a `KEEP`, `WRAP`, `REPAIR`, or `REPLACE` disposition with cross-ticket
  impact.

Routine implementation details within an already ratified contract do not
require a separate lead notification.

**Non-blocking lead-notification and amendment model.** For each pull request
that makes or changes a material decision, the executor must:

1. record the durable decision in this log or the applicable ticket, plan, or
   specification;
2. include a pull-request section titled `Lead notification` naming the
   decision ID or heading, affected ticket and files, selected approach,
   alternatives rejected, invariant/interface/sequencing effects,
   reversibility and migration effect, and notification issue/comment; and
3. post or update a notification in issue #42 mentioning `@harshaa765`.

The notification is evidence of delivery, not approval. No affirmative
response, reaction, approval, or waiting period is required. The lead may
adjust a decision before merge through review or an explicit direction. A lead
`REQUEST_CHANGES` review or explicit `BLOCKED` direction pauses the affected
change but does not stop unrelated work. A post-merge adjustment uses a new
bounded branch and a later normally merged repository decision that marks the
earlier decision superseded; historical evidence is not rewritten. Current
merged repository authority remains controlling until that superseding change
normally merges.

The Accountable reviewer assignments in the Wave B board route technical and
domain review and notification. They do not create an affirmative pre-approval
or silence gate. Independent technical review, resolution of blocking review
findings, required CI, and normal merge remain mandatory.

**Reserved human decisions remain reserved.** This decision does not authorize
an agent to invent or approve physical or scientific truth, thresholds,
tolerances, Challenge populations or SamplingPlan claims, scientific
qualification, security acceptance, rights or legal policy, live economics,
launch readiness, production deployment authority, or any production, `LIVE`,
frontier, product, settlement, chain, weight, or emission authority. Material
company decisions that `AGENTS.md` reserves to humans also remain human-owned.
When correct implementation requires an unresolved reserved decision, the
affected capability must stop or remain explicit, bounded, and fail closed.
That blocker does not prevent unrelated fixture, schema, interface, test, or
infrastructure development.

**Supersession and historical evidence.** All earlier entries below that
require named or multi-role approval, an exact-byte or hash-bound approval
bundle, a prospective activation-approval record, or a separate activation
closeout before B-01 are retained as point-in-time historical provenance but
are superseded for development authorization after this decision normally
merges. Those earlier gates are not deemed satisfied, and their historical
approval evidence is not upgraded. This supersession does not reach later
scientific qualification, security acceptance, rights/legal, live-economic,
launch/deployment, Wave closeout, or other reserved-human gates.

Issue #53 remains open while this candidate is reviewed. After normal merge it
should be closed as `superseded by executive governance decision`, not as a
completed approval bundle, and its comments remain historical coordination
evidence. Issues #41, #42, and #43 should then be synchronized separately;
issue #42 becomes the durable lead-notification route rather than a blocking
approval queue for development.

```text
Proposed state after this exact governance change normally merges:
Current wave: B
Wave B state: active in bounded development scope
Controlling register: .agent/WAVE_B.md version 0.4
Next selected ticket: B-01
B-01 status: todo
B-01 development: authorized to begin on its own later branch
Wave B IMPLEMENTED: NO
Wave B TESTED: NO
SCIENTIFICALLY_QUALIFIED: NO
SECURITY_QUALIFIED: NO
NETWORK_QUALIFIED: NO
COMMERCIALLY_VALIDATED: NO
PRODUCTION_QUALIFIED: NO
LIVE / launch / frontier / product / settlement / chain / weight / emission authority: NO
```

## 2026-08-29 — A12 and Wave A bounded engineering closeout candidate

> **Documentation-only closeout authority gate.** The merged A12 contract and
> implementation are current-main engineering evidence. The checked A12
> ticket criteria, A12 `done` status, Wave A `closed` status, and final closure
> ruling in this exact eight-file candidate are proposed administrative state
> only. They become repository authority only after the exact closeout head is
> independently reviewed, explicitly human-authorized, and normally merged.
> A branch, draft pull request, or green pull-request CI is not that authority.
> Until that merge, current-main administrative authority remains A12 `todo`,
> Wave A incomplete, and Wave B inactive.

**Exact merged authority.** PR #50 ratified the A12 contract at independently
reviewed head `6695c279728438befd6404fb81c4f7a27e382a67` and normal signed merge
`746e56e42c412bc8ba2eeb4d85ed83396e1a084c`, tree
`651c568631465a4902d69036a06c937104660d37`. PR #51 then implemented the
bounded invariant judge and CI lane from that base at independently reviewed
final head `33b4626a1ffe7d0c65336336a870a8f4a73ab92f`. It merged normally as
current main `2a8b273a1167588efb4a11159da5224264d5b37a`, tree
`cb7b23d32e3663bbf00704f1e28c16020bfb9226`, with ordered parents
`746e56e42c412bc8ba2eeb4d85ed83396e1a084c` and
`33b4626a1ffe7d0c65336336a870a8f4a73ab92f`; GitHub records
`verified=true`, `reason=valid`. The PR #51 base-to-merge manifest is exactly
the dedicated workflow lane and six `tests/invariants/` implementation paths.

**Ratification, implementation, and repair chronology.** A12-CI-1 superseded
the initial ratification candidate at head
`4e85e3cd4b1c0ee9ef4910db24cad60e4b7c397e`, tree
`181530a32c69edd36c868600f930751bc8df15e1`, because its bare marker command
could not discover `tests/invariants/` under the repository's `tests/cpu`
default. The repaired contract at reviewed head
`6695c279728438befd6404fb81c4f7a27e382a67` made the explicit-directory
command canonical and merged normally in PR #50. The initial implementation
candidate at superseded head `18d4f02895533d3a850217824e44b0d6d587c1b0`
then established the seven-file invariant-judge/CI shape and a 22-test lane
(run `33240409328`). Close review identified three acceptance-evidence gaps:
A12-TEST-1 required direct behavioral exercise of the real fail-closed pytest
guard; A12-XWALK-1 required exact machine locks for proof kinds, ceilings, and
node resolution; and A12-R11-1 required the dedicated forbidden-input proof to
cover both numeric and Boolean A5 channels. Their replacement head
`bf978b6e073c7b431b2fcb68cf9826bf582903a9` passed 27 invariant tests in run
`33243707714`. Greptile then identified A12-XWALK-2, a valid canonical-path
containment gap for parent traversal and symlink aliases. The final reviewed
head `33b4626a1ffe7d0c65336336a870a8f4a73ab92f` repaired that gap with strict
resolved containment and traversal/symlink canaries, bringing the exact lane
to 28 tests before normal merge. These were closed implementation-acceptance
evidence defects; the closeout audit found no owner implementation defect and
no `NEW_OWNER_DECISION_REQUIRED` condition.

**Exact closeout audit.** Every one of the 24 ticket criteria passes: the
twelve ratified A12-R1 through A12-R12 criteria, six dedicated-suite/CI
criteria, and six failure/closeout-governance criteria are **24 PASS / 0
FAIL**. The machine crosswalk is exactly ordered A12-R1 through A12-R12 and is
text-equal to `Design_Specs/Build_Out.md` section 2. It maps twelve unique
dedicated row proofs and sixteen unique infrastructure proofs, for exactly
`12 + 16 = 28` marked invariant tests, with canonical node containment,
supporting owner nodes below `tests/cpu`, and no unmapped or prohibited
greenwashing path.

The twelve-case entrypoint matrix also passes exactly: marked-pass control,
ordinary marked failure, missing target, empty target, only-unmarked target,
zero marker matches, complete deselection, partial deselection, runtime skip,
expected xfail, non-strict xpass, and collection-time module skip. The passing
control exits green; every prohibited or invalid case fails closed. No skip,
`skipif`, xfail, deselection, exception swallowing, imported-owner-test,
private-state manufacture, or weakened-proof route can make the canonical lane
green.

The exact nine `Design_Specs/Build_Out.md` section 12 Wave A acceptance bullets
are **9 PASS / 0 FAIL** against current owner source and tests. The board audit
retains the bounded merged evidence for A-1 and A0 through A11 and adds A12
only after all closeout gates pass, yielding a proposed **14 done / 0 todo / 0
in_progress / 0 blocked**. That proposed board result is not current-main
authority until this closeout candidate is reviewed, authorized, and merged.

**Pre-edit local validation evidence.** Fresh closeout-branch validation ran
the canonical command `python -m pytest tests/invariants -m invariant -q` with
`28 passed in 3.98s`; the unfiltered invariant run reported the identical 28
nodes and `28 passed in 3.96s`, with zero deselected, skipped, xfailed, or
xpassed outcomes. The exact ten-file A3-A11 supporting-owner regression
reported `2052 passed in 35.62s`, and the complete default CPU suite reported
`2310 passed in 36.10s`. The repository quality ratchet against exact base
`2a8b273a1167588efb4a11159da5224264d5b37a` passed with Ruff `757` checked
against a `776` baseline, Black `62` checked against a `68` baseline, removed
debt `19/6`, zero changed Python files, and no new debt. This is pre-edit
evidence; the exact final closeout head must pass the same gates before push.

Exact post-implementation main push run `33250521376` completed successfully
on `2a8b273a1167588efb4a11159da5224264d5b37a`: invariant job `99095290077`
reported `28 passed in 4.22s`; CPU job `99095290170` reported `2310 passed in
59.52s`; and Code-quality job `99095290146` retained `Ruff 757/776`, `Black
62/68`, removed debt `Ruff 19, Black 6`, five changed Python files clean, and
no new debt.

**Exact closeout manifest.** This candidate changes only:

```text
.agent/DECISIONS.md
.agent/WAVE.md
.agent/WAVE_A_REPORT.md
.agent/plans/A12_invariant_ci.md
.agent/tickets/A12_invariant_ci.md
Design_Specs/Build_Out_Constitutional_Overlay.md
agent_pack/README.md
docs/context/IMPLEMENTED_VS_SPECIFIED_CURRENT.md
```

It makes no source, invariant-test, CPU-test, fixture, workflow, quality
baseline, constitution, Build-Out sequencing, Wave-B artifact, activation, or
launch change.

**Bounded maturity ruling.** The implementation proves a repository-owned,
fail-closed invariant judge over the present Wave A owner surfaces. In
particular, A12-R6 remains a negative absence proof with no sandbox or workload
isolation claim; A12-R8 remains exact pinned-fixture reproducibility with no
selected scientific tolerance; and A12-R12 remains a declared-incomplete,
non-executing absence proof with no usefulness, leakage-threshold, or
shadow-case adequacy claim. Wave A closure is an engineering process
milestone, not scientific qualification, security acceptance, network
qualification, commercial validation, production qualification, LIVE or
launch authority, frontier authority, or emission authority.

```text
A12 SPECIFIED / RATIFIED: YES
A12 IMPLEMENTED: YES, bounded invariant-judge/CI scope
A12 TESTED: YES, bounded engineering evidence
A12 SCIENTIFICALLY_QUALIFIED: NO
A12 SECURITY_QUALIFIED: NO
A12 NETWORK_QUALIFIED: NO
A12 COMMERCIALLY_VALIDATED: NO
A12 PRODUCTION_QUALIFIED: NO

Candidate branch before closeout merge:
A12 WAVE STATUS: proposed done; authoritative main remains todo
Wave A: proposed closed in bounded engineering scope; authoritative main remains incomplete
Wave B: inactive

After exact-head independent review, explicit human authorization, and normal merge:
A12 WAVE STATUS: done
Wave A: closed in bounded engineering scope
Wave B: inactive
```

Closing Wave A does not activate Wave B. No Wave-B controlling register,
ticket, owner approval, activation hash, handoff, or B-01 work is changed or
authorized here.

## 2026-08-29 — A12 exact Wave-A invariant-manifest contract candidate

> **Documentation-only ratification gate.** This six-file candidate proposes
> the exact A12 manifest and future invariant-CI acceptance contract. It does
> not implement A12, add or mark a test, change CI, create the Wave-A report,
> update `.agent/WAVE.md`, close Wave A, activate Wave B, authorize launch, or
> authorize merge. A12 becomes `SPECIFIED / RATIFIED: YES` only after the
> exact candidate head is independently reviewed, explicitly human-authorized,
> and normally merged. Until then A12 remains `todo`, Wave A remains
> incomplete, and Wave B remains inactive.

**Verified starting authority.** A fresh remote resolution found
`origin/main` unchanged at exact signed merge
`37074e9f0663d36ce1f7655aaedfc7ad4fb6a3c1`, tree
`8848085952115672a9f90d255e5feb9bee8116db`, subject `Merge pull request #49
from carbonphysicsai/agent/a11-closeout`, with ordered parents
`e2496e92eeae31befdaa430501bb9f00b0e6339e` and
`0daafae840e920f2e3abd63bc26d7321a13f32da`. GitHub verification is
`verified=true`, `reason=valid`; PR #49 is normally merged at that exact
commit.

Exact-main push run `33207423717` completed successfully. CPU job
`98971914859` recorded `2310 passed in 63.74s`. Code-quality job
`98971915133` recorded `Ruff 757/776`, `Black 62/68`, removed debt `Ruff 19,
Black 6`, zero changed Python files, and no new debt. The starting worktree was
clean and no remote A12 branch or pull request existed.

This contract candidate changes exactly:

```text
.agent/DECISIONS.md
.agent/plans/A12_invariant_ci.md
.agent/tickets/A12_invariant_ci.md
Design_Specs/Build_Out_Constitutional_Overlay.md
agent_pack/README.md
docs/context/IMPLEMENTED_VS_SPECIFIED_CURRENT.md
```

It preserves `.agent/WAVE.md`, `.agent/INVARIANTS.md`,
`Design_Specs/Build_Out.md`, every Python/test/fixture path,
`.github/workflows/ci.yml`, `pyproject.toml`, dependencies, packaging,
`.ci/quality-baseline.json`, the absent `.agent/WAVE_A_REPORT.md`, and every
Wave-B artifact.

**Conflict classification.** The exact twelve numbered cross-cutting
invariants in `Design_Specs/Build_Out.md` section 2 are `NO_CONFLICT` with the
bounded A3–A11 owner contracts and current fail-closed maturity ceiling. They
are the sole A12 `12/12` denominator.

The short A12 ticket and overlay theme list are `DOCUMENTATION_LAG`: by
themselves they omit separate rows for execution isolation, no silent rescore,
and declared-incomplete practice, while presenting A11 redaction, fee/payment
isolation, and A8 non-emission as additional current themes. This candidate
restores the exact twelve rows and folds those themes into R1/R4, R11, and R9
without dropping or adding an invariant.

The absent `tests/invariants/`, unselected registered marker, absent dedicated
CI lane, and absent Wave-A report are expected `IMPLEMENTATION_LAG`. No current
owner migration is required. No source repair or `NEW_OWNER_DECISION_REQUIRED`
was found for this bounded manifest. If later branch-head implementation
exposes one, A12 must stop and preserve the failing rule rather than inventing
a resolution.

**Exact A12 manifest.** The complete normative wording is preserved in
`.agent/plans/A12_invariant_ci.md` and the unchecked ticket criteria. Its exact
order is:

1. **A12-R1 — No seed leakage.** A11 positive-construction redaction is
   evidence under R1/R4, not a thirteenth invariant.
2. **A12-R2 — Practice isolation.** Current Wave A proves only the
   fail-closed absence of nominal practice execution with official material.
3. **A12-R3 — Pinned evaluation.** A3/A4/A5/A7/A8 immutable identities and
   pin rejection provide the current bounded proof surface.
4. **A12-R4 — Disclosure allow-list.** A6/A9/A10 public projection and A11
   primitive-only positive construction provide the current proof surface.
5. **A12-R5 — LIVE requires qualification.** Tests establish fail-closed
   exact-version evidence binding, not scientific acceptance or signer/key
   qualification.
6. **A12-R6 — Execution isolation.** No miner-controlled production runtime
   exists in Wave A. Only the negative capability boundary can pass; no
   sandbox, security qualification, or production isolation is claimed.
7. **A12-R7 — Infra ≠ science.** A5/A7/A8 preserve
   typed scientific-versus-infrastructure meanings, retry/refund, and no
   infra-granted emission.
8. **A12-R8 — Determinism.** Current executable proof is exact pinned fixture
   reproducibility; scientific tolerances and production reproducibility are
   not claimed.
9. **A12-R9 — No placeholder LIVE.** A8 remains a non-production,
   false-emission fixture stub and A10 remains fixture-only. Missing future
   frontier/product/receipt/settlement/weight types stay reserved.
10. **A12-R10 — No silent rescore.** Immutable identities, no overwrite, and
    prospective pack versioning preserve historical meaning; no
    production-qualified durable history is claimed.
11. **A12-R11 — Forbidden score inputs.** A5 guards and A7 fee isolation keep
    the exact forbidden set outside `S_combined`/Yuma weights. Fee/payment is a
    subcase, not a separate invariant.
12. **A12-R12 — Practice is useful without revealing the realized exam.**
    Current proof is limited to declared-incomplete, non-executing surfaces
    outside official lifecycle/score/scheduling. Leakage methodology,
    shadow-case science, thresholds, and practice usefulness remain unearned.

The broader invariants in `AGENTS.md` and `.agent/INVARIANTS.md` remain
binding repository authority but do not change this exact twelve-row A12
denominator. Protocol-extension receipt/hash/signature and future
frontier/product/treasury themes remain reserved mappings under the numbered
rows until their owner types exist.

**Feasibility evidence and maturity ceiling.** An exact twelve-row current-main
audit passed `12/12` with no implementation repair or new owner decision. The
supporting ten-suite A3–A11 owner regression passed `2052` tests. These results
prove only that the contract has a current bounded implementation path; they
do not implement or test the dedicated A12 lane.

The `invariant` marker is registered, but no current test is marked and
`tests/invariants/` does not exist. Current `pyproject.toml` roots default
pytest discovery at `tests/cpu`, so the future A12 implementation entrypoint
must name the dedicated directory explicitly:
`python -m pytest tests/invariants -m invariant -q`. The explicit path is
required for discovery without changing the default CPU configuration, and
the command cannot be reported as a green contract-ratification result.

After ratification and separate implementation authorization, A12 must create
dedicated marked tests and a dedicated CI entrypoint running exactly
`python -m pytest tests/invariants -m invariant -q`, plus a machine-auditable
R1–R12 crosswalk and separately reviewed Wave-A report/board evidence. It must
retain the full CPU and quality jobs; fail with no dedicated tests, a missing
or empty `tests/invariants/`, zero `invariant` marker matches, or complete
deselection; and never use skip, xfail, deselection, exception swallowing,
imported owner tests, private-state manufacture, or test weakening to obtain
green.

```text
A12 SPECIFIED / RATIFIED:
YES only after exact-head independent review, explicit human authorization,
and normal merge of this documentation contract

A12 IMPLEMENTED: NO
A12 TESTED: NO
A12 SCIENTIFICALLY_QUALIFIED: NO
A12 SECURITY_QUALIFIED: NO
A12 NETWORK_QUALIFIED: NO
A12 COMMERCIALLY_VALIDATED: NO
A12 PRODUCTION_QUALIFIED: NO
A12 WAVE STATUS: todo
Wave A: incomplete
Wave B: inactive
```

## 2026-08-28 — A11 bounded operational-observability implementation closeout

> **Draft PR #49 closeout authority gate.** The merged A11 implementation and
> the recorded `66/66` audit are current-main engineering evidence. The checked
> ticket criteria, A11 `done` status, "closeout" or "independently closed out"
> wording, and any identification of A12 as the next move in this branch are
> proposed administrative state only. They become repository authority only
> after the exact PR #49 head containing this gate is independently reviewed,
> explicitly human-authorized, and normally merged. Until then, current-main
> administrative authority remains A11 `in_progress` in `.agent/WAVE.md`, the
> A11 ticket remains at `66 unchecked / 0 checked`, A12 remains `todo` and
> unstarted, Wave A remains incomplete, and Wave B remains inactive. This draft
> does not authorize A12 or any later-wave work.

**Current-main implementation truth.** PR #46 merged normally as signed merge
commit `e2496e92eeae31befdaa430501bb9f00b0e6339e`, tree
`3d6682803422497efc6bff26451c12d9c306f96c`, with ordered parents prior main
`98865dd04c5a4018c8077517cb79aabd6045a468` and independently reviewed head
`e5ed60c4043abb3bfd2af945b5dd45b8e1996fcb`. The reviewed head and merge tree
are identical and their diff is empty. The prior-main-to-merge manifest is
exactly `.agent/WAVE.md`, the four `carbon/observability/` source files, and
`tests/cpu/test_observability.py`. A11-R1 through A11-R18 are ratified; no new
owner decision or semantic amendment is introduced by this closeout.

**Review and post-merge evidence.** Greptile's exact-head review records
`Confidence Score: 5/5`, no actionable defect, zero review threads, and zero
formal change requests. Push run `33199541335` checked out the exact merge and
completed successfully: CPU job `98945235783` reported `2310 passed in
62.62s`; Code-quality job `98945235938` reported `Ruff 757/776`, `Black
62/68`, removed debt `19/6`, five changed Python files clean, and no new debt.

**Independent closeout audit.** A fresh exact-current-main audit mapped all 66
ticket criteria to production source, canonical tests, and CI, wheel, import,
quality, or topology evidence as applicable: **66 PASS / 0 FAIL**. Fresh
Python 3.11 Linux validation reported focused `337 passed`, the related
A5/A7/A9/A10/A11 owner boundaries `1330 passed`, and complete CPU regression
`2310 passed`. A fresh no-dependency wheel installed with `--no-deps` and
imported in isolated mode outside the source tree as
`carbon-0.9.0-py3-none-any.whl`, SHA-256
`ea686e933f6f93c72df281e79a3baebcb05f6789b25d4499ff81e937980e94fe`.
Strict Ruff and Black passed the five A11 Python/test paths. The repository
quality gate against exact closeout base `e2496e92...` retained `Ruff
757/776`, `Black 62/68`, removed debt `19/6`, changed Python files `0`, and no
new debt; `git diff --check` passed.

**Implemented boundary and maturity.** The final implementation uses private
identity-bound weak allocation eligibility: exact snapshot `__new__` registers
one weak reference for that exact object, exact `__init__` atomically consumes
the one-shot eligibility before validation, abandoned allocations are
collectible, and failed, partial, repeated, donor, alternate, `object.__new__`,
or concurrent construction cannot restore eligibility. Sink snapshots contain
only the ratified built-in primitive fields and each admitted call receives a
distinct snapshot. A11 is `SPECIFIED / RATIFIED: YES`, `IMPLEMENTED: YES`, and
`TESTED: YES` only for this bounded in-process engineering scope. It remains
`SCIENTIFICALLY_QUALIFIED: NO`, `SECURITY_QUALIFIED: NO`,
`NETWORK_QUALIFIED: NO`, `COMMERCIALLY_VALIDATED: NO`, and
`PRODUCTION_QUALIFIED: NO`. A12 remains separately owned and `todo`; Wave A is
not complete and Wave B remains inactive.

## 2026-08-26 — Wave B v0.3 scientific-hardening amendment candidate

**Candidate only; no activation.** This amendment proposes version 0.3 of
`.agent/WAVE_B.md` and
`Design_Specs/Miner_MCP_Wave_B_Research_Contract.md`, plus the matching
tickets and launch roadmap v1.0.3. It supersedes the v0.2 candidate planning
package only if independently reviewed, explicitly accepted by the named
owners, and normally merged. The historical v0.2 decision below is preserved
unchanged. Wave A remains authoritative and Wave B remains inactive.

**Scientific changes proposed.** Optional Challenge-owned
structure-preserving components may be exposed only as exact reconstructible
catalog levers; a component name, claimed invariant, or unit test cannot
self-certify physics, satisfy a gate, or enter score. A prospective
`ReconstructionEvidencePolicy` gives every scientifically scored or nominated
candidate its Challenge/family-registered complete base reconstruction evidence
(one or more builds), permits frozen-build reuse across authorized cases, and
may allocate repeat promotion evidence sequentially under qualified error
control. Pre-base forecasts, partial builds, proxies, and heuristic screens
schedule work only; an uncompleted path is typed `EVIDENCE_DEFERRED`, not
negative scientific evidence. Decision intervals preserve reconstruction ×
whole-case/trajectory dependence, stratified stress, joint reference
uncertainty, and shared dependencies. Quadrature or zero covariance is allowed
only when the Dossier qualifies both the procedure and its applicability test
and the exact incumbent-challenger evidence satisfies that test.

**Authority and ratification.** Changes to the owner-canonical scientific
canon, locked generator/validation
architecture, evidence/audit specification, and Launch Bar are explicit
owner-ratification proposals. Before merge they require Physics/SciML,
statistics, and protocol-owner acceptance; security/SRE/operations approval is
also required where the affected ticket assigns it. Nothing here changes an
active Wave-A ticket, implements a runtime, qualifies a Challenge, mandates a
Port-Hamiltonian architecture, or creates scientific, security, network,
commercial, production, LIVE, frontier, weight, emission, or settlement
authority.

## 2026-08-26 — Wave B miner-research architecture and execution-board candidate

**Candidate only; no activation.** The proposed governing artifacts are
`.agent/WAVE_B.md` version 0.2 and
`Design_Specs/Miner_MCP_Wave_B_Research_Contract.md` version 0.2, together
with `.agent/WAVE_B_CODEX_HANDOFF.md`, the B-01 through B-GATE ticket
decomposition, and the per-ticket `.agent/evidence/wave_b/` convention. They
are documentation and planning candidates until independently reviewed,
explicitly authorized by the human protocol, science, security, rights, and
technical owners, and normally merged. Merge of this candidate does not itself
activate Wave B.

**Prospective activation rule.** Wave A remains authoritative. Wave B ticket
execution may begin only after A11 and A12 are merged/closed,
`.agent/WAVE_A_REPORT.md` exists, the Wave B planning package is independently
reviewed, and one prospective activation change is independently reviewed and
human-authorized. That change records named owner-role approval with the exact
reviewed commit and SHA-256 hashes over the unchanged repository bytes of the
board, contract, and handoff, then makes `.agent/WAVE.md` name Wave B and that
exact board as its controlling register. It does not mutate the board,
contract, or handoff. Before B-01, a separate independently reviewed post-merge
activation closeout must record the activation merge commit/tree, prove exact
reviewed-head and merged-tree equality, record post-merge CI, and record named
human owner acceptance without changing the three hashed artifacts. B-07R and
B-07S then ratify behavior and the exact service protocol before dependent
implementation. B-07A implements the ratified shared v2 nominal primitives;
B-07G later composes the completed domain implementations into the exact local
twelve-operation service.
Launch v1.0.2 records the conditional rebaseline; the former v1.0.1 umbrella
B-02/B-07 IDs are retired aliases and `.agent/WAVE_B.md` owns the proposed
ticket decomposition.

**Fixed candidate architecture.** Strategy v1 stays declarative. A public
Challenge-bound `ParameterCatalog`, `CandidateAssemblyContract`, and
deterministic compiler produce one exact `ResolvedConstructionPlan` or fail
closed. A closed catalog may expose Challenge-bounded training sampling,
curriculum, and augmentation levers that resolve to `R_strategy`; validators
derive the actual train seeds and draws. Raw/custom data and all official
evaluation controls remain outside Wave B. Practice is nominally separate and
non-authoritative. The local miner topology pairs the separately namespaced v2
research service with the unchanged v1 official service; v2 neither exposes
nor delegates v1 operations and does not duplicate its lifecycle or store.
PriorPack is immutable, estimand-bearing, evidence-labeled, equal-by-reference,
statically served, lagged, and governed by persistent cumulative disclosure.
`TEST_ONLY` cannot enter external activation, and no v2-backed projection can
enter the public v1 provider.

**Authority ceiling.** This candidate can become `SPECIFIED / RATIFIED` only.
It implements nothing and creates no scientific, security, network, commercial,
production, LIVE, frontier, weight, emission, or settlement authority.

**Unresolved human/evidence inputs.** The real physical population and
SamplingPlan; primary/witness reference adequacy; measurements and decision
resolution; executable catalog/backbones/training-support/resource rails; practice scope;
resource calibration; prior estimands, cohort, lag, cadence, bands,
search-diversity policy, utility/leakage thresholds, content and approvers;
evidence/IP rights; signer/key custody; live identity linkage; and remote
quotas/fees remain fail-closed owner decisions mapped to the Master Open Design
Questions and the Wave B board. Named implementation-lane staffing and the
testnet/mainnet calendar rebaseline are also unresolved launch-owner inputs.

## 2026-08-27 — A11 bounded operational-observability contract and immutable sink-snapshot amendment candidate

**Current repository truth and ratification topology.** Current `origin/main` is
`644c6c38139e9215e5ccc8d3c8e8bc62e843dbb3`, tree
`15637ab89613daeec20f2f46bdefd045cb0ed7c6`, subject `Merge pull request #48
from carbonphysicsai/agent/science-gtm-wave-integration`, with ordered parents
`bf6e2e8910f90b345ded44bdebb63fca73646b0d` and
`dec7ba8f1ac5d98c48c492abbdbeb8816e25e25e`. Its GitHub merge signature is
`verified=true`, `reason=valid`.

The immediately preceding PR #45 merge is
`bf6e2e8910f90b345ded44bdebb63fca73646b0d`, tree
`b6365e31b09339826b7568565bb28c7c32007fac`, with ordered parents
`4e4a66d29566a2a62a82188adddac76e6e0fb8b8` and
`74f8edb04b3b806f4edc75de3ba8c4c6273815fb`; its signature is also verified
and valid. Historical PR #39 merge
`4e4a66d29566a2a62a82188adddac76e6e0fb8b8` remains the normal A11-R1 through
A11-R17 ratification merge, the original PR #47 base, PR #45's first parent,
and an ancestor of current main. It is historical authority, not current main.
A11-R1 through A11-R17 therefore remain ratified; their record below remains
authoritative except for the exact sink-facing clauses conditionally
superseded by the A11-R18 candidate after its future ratification.

Exact current-main `push/main` run `33093494970` completed successfully. CPU
job `98592266955` recorded `1973 passed in 44.41s`. Code-quality job
`98592266774` recorded `Ruff 757/776`, `Black 62/68`, removed Ruff debt `19`,
removed Black debt `6`, changed Python files `0`, and no new debt. Current main
contains no `carbon/observability/` package and no
`tests/cpu/test_observability.py`. Current-main `.agent/WAVE.md` is exact blob
`6369a373630392955ea2d58f258f06482173578c`: A10 is `done`; A11 and A12 are
`todo`; Wave A remains controlling and incomplete; Wave B remains inactive.

Current main now includes the candidate-only Wave B v0.3 scientific-hardening
planning merged by PR #45 and the Science-GTM future-ticket integration merged
by PR #48. Those merges do not widen A11-R18, activate Wave B, implement A11,
or create scientific, security, network, commercial, or production authority.
PR #45 changes only this decisions file among PR #47's six paths and leaves
A11-R18 untouched; PR #48 changes none of the six paths.

**PR #47 synchronization and rebaseline ledger.** PR #47 began from historical
base `4e4a66d29566a2a62a82188adddac76e6e0fb8b8`; its initial R18 commit is
`9de896dea92e5378d99ef205cd21a29ef9f57fd3`, and its corrected reviewed head is
`76ef2b194132bd2e07677d4ac1cf6baa83509faf`. Synthetic merge
`7ab62b646ba1dee248e090cbd2490511a4b1d87a` and run `33039977702` are retained
only as stale old-base evidence against `4e4a66d...`; they are not current-base
integration evidence.

The following block records the required starting-state recovery
classification before synchronization and rebaseline:

```text
CURRENT_BASE_DRIFT:
CONFIRMED

A11-R18 semantic conflict:
NO

new owner decision:
NO

branch synchronization required:
YES

current-state documentation repair required:
YES
```

The two `YES` recovery actions are now satisfied by synchronization merge
`cf9a773520645053e6d745c28aede15356fef80a` and this single current-state
rebaseline commit; the classification remains provenance, not pending work.

The normal synchronization merge is
`cf9a773520645053e6d745c28aede15356fef80a`, tree
`b06e2aa7a0bf28700449010d320d09317201d155`, subject `merge: synchronize
A11-R18 with current main`, with ordered parents
`76ef2b194132bd2e07677d4ac1cf6baa83509faf` and
`644c6c38139e9215e5ccc8d3c8e8bc62e843dbb3`. This rebaseline is the single
documentation commit `docs: rebaseline A11-R18 against current main`, whose
sole parent is that synchronization merge. Its generated commit SHA and tree
are recorded after creation in PR #47 publication metadata rather than as
impossible self-referential fields inside its own tree. Its sequential and
cumulative current-main manifest is exactly:

```text
M .agent/DECISIONS.md
M .agent/plans/A11_logging.md
M .agent/tickets/A11_logging.md
M Design_Specs/Build_Out_Constitutional_Overlay.md
M agent_pack/README.md
M docs/context/IMPLEMENTED_VS_SPECIFIED_CURRENT.md
```

This synchronization and current-state repair leave the corrected A11-R18
semantic contract unchanged.

**Blocked draft implementation truth.** Draft PR #46 is not current repository
implementation or test authority. Its unchanged head is
`5b0b4927f8a4d2e6438b20a8201da43ae2a0645e`, tree
`3a84d98d95e53afaace00d500116cce91e66089e`, on
`agent/a11-observability`. It remains draft and unmerged. The earlier
`P1_GENERIC_DATACLASS_SERIALIZATION_BYPASS` is repaired on that draft branch,
but the repair does not resolve its shared enum-singleton boundary. The
previous PR #46 `66 PASS / 0 FAIL` audit claim is withdrawn and superseded as a
current readiness claim; it is not replaced by a new numeric total.

Exact-source review confirms that the draft's A11 enums and the A5/A7 owner
enums are ordinary direct `str, Enum` classes; its enum copy helpers return the
canonical member singleton; its event values retain those canonical members;
and its service passes canonical enum members, plus an A7 `SubmissionId`
nominal inside a submission event, to sink code. That conflicts with the
ratified requirement that every sink argument be fresh, immutable, sink-safe,
A11-owned, and isolated from caller, sink, retained, concurrent, and later A11
mutation.

```text
P1_MUTABLE_ENUM_SINGLETON_BOUNDARY_BYPASS:
CONFIRMED

implementation defect:
YES

current main defect:
NO

contract-preserving implementation under current owner types:
NO

classification:
NEW_OWNER_DECISION_REQUIRED
```

Option A, an immutable A11-owned sink snapshot representation, is the only
prepared amendment. Option B requires a separate A5/A7 owner migration and is
outside this decision. Option C would weaken the security boundary and is not
authorized. This documentation candidate implements none of the options and
does not modify or synchronize the PR #46 branch; its existing blocker body,
including withdrawal of the stale audit claim, remains unchanged.

```text
A11-R1 through A11-R17:
RATIFIED

A11-R18:
SPECIFIED as the exact synchronized and rebaselined draft candidate;
not RATIFIED until independent exact-head review, explicit human authorization,
and normal merge

A11 IMPLEMENTED:
NO on current main

A11 TESTED:
NO on current main

PR #46:
draft, blocked, non-authoritative, and unchanged

A11 SCIENTIFICALLY_QUALIFIED:
NO

A11 SECURITY_QUALIFIED:
NO

A11 NETWORK_QUALIFIED:
NO

A11 COMMERCIALLY_VALIDATED:
NO

A11 PRODUCTION_QUALIFIED:
NO

A11 WAVE STATUS:
todo on current main

A12:
todo

Wave A:
incomplete

Wave B:
inactive
```

Draft publication, documentation regression evidence, and PR #46 tests are
not ratification, current-main implementation, current-main A11 test evidence,
Wave-A closeout, Wave-B activation, or launch authority.

**Conflict classification and correction.** The bounded typed primitive is
`NO_CONFLICT` with current A5 scoring authority, A6 disclosure/failure-tag
authority, A7 identity/lifecycle authority, A8 private-outcome ownership,
A9/A10 fixed public-error boundaries, infrastructure/science separation,
positive disclosure, no-seed leakage, and later evidence/economic authority.

Review finding `P1_UNENFORCEABLE_EVENT_PROVENANCE_CLAIM` is
`DOCUMENTATION_LAG`, not an A11 implementation defect. Public A7
`SubmissionId` validates an exact built-in string, canonical UUID rendering,
UUID version 4, and RFC-4122 variant, but does not
prove Carbon minted the value, a retained record exists, a supplied state is
current, a transition occurred, or A5/A7 provenance is authenticated. The old
claim that every event projects an existing record, and that A11 itself can
exclude an open duplicate, is therefore withdrawn. No store lookup, private
record import, capability token, signature, receipt, second identity, or new
submission-event field is authorized as a repair.

Current main's A11 ticket requirement for A9/A10 provider and public-error
telemetry is reconciled through one closed error-kind enum and one one-field
event. It does not authorize raw exception capture, production A9/A10 imports,
or owner instrumentation. The ticket's generic logger helper, pattern-first
redaction, generic failure tags, and implied direct instrumentation remain
`DOCUMENTATION_LAG`: structural positive construction replaces those unsafe
shorthands. A0's `carbon/logging_utils` remains an inert compatibility marker
under KEEP + REPLACE; `carbon/observability` becomes the sole future A11 owner.
`carbon/audit` remains reserved for evaluation receipts and authorized
re-execution.

Production sinks, latency/timeout policy, persistence/retention, dashboards,
alerts/thresholds, authentication, public APIs, incident management,
timestamps, additional categories, direct owner-service hooks, evidence,
receipts, Challenge health, adaptive-query detection, official/LIVE operation,
frontier/Product Qualification, commercial acceptance, settlement, chain,
weights, and emissions remain `NEW_OWNER_DECISION_REQUIRED` and fail closed.

**A11-R1 — Exact paths and module ownership.** The sole future owner and
focused test path are exactly:

```text
carbon/observability/__init__.py
carbon/observability/model.py
carbon/observability/providers.py
carbon/observability/service.py
tests/cpu/test_observability.py
```

`model.py` owns `EventKind`, `MetricKind`, `DurationStage`,
`BoundaryErrorKind`, `ObservabilityEvent`, `BoundaryErrorEvent`,
`ObservabilityResourceLimits`, the four A11 error types, and only private exact
copy/validation helpers. `providers.py` owns only `StructuredEventSink` and
`MetricSink`, with no concrete/default/global sink. `service.py` owns only
`ObservabilityService` and private shared-capacity, same-service reentrancy,
sink lookup/invocation/return validation, and exception translation.
`__init__.py` performs only the exact local re-exports in A11-R2. No root
`carbon` export, alias, private helper export, or owner-type re-export exists.

**A11-R2 — Exact nominal surface and enum values.** The exact ordered
`carbon.observability.__all__` tuple is:

```python
(
    "EventKind",
    "MetricKind",
    "DurationStage",
    "BoundaryErrorKind",
    "ObservabilityEvent",
    "BoundaryErrorEvent",
    "ObservabilityResourceLimits",
    "StructuredEventSink",
    "MetricSink",
    "ObservabilityService",
    "ObservabilityError",
    "ObservabilityRequestError",
    "ObservabilityResourceError",
    "ObservabilityIntegrationError",
)
```

The four enums have these exact direct bases, declaration order, names, and
literal values:

```python
class EventKind(str, Enum):
    SUBMIT = "SUBMIT"
    SCORE = "SCORE"
    REJECT = "REJECT"
    FAILED_STRATEGY = "FAILED_STRATEGY"
    FAILED_INFRA = "FAILED_INFRA"


class MetricKind(str, Enum):
    SUBMIT_COUNT = "SUBMIT_COUNT"
    SCORE_COUNT = "SCORE_COUNT"
    REJECT_COUNT = "REJECT_COUNT"
    FAILED_INFRA_COUNT = "FAILED_INFRA_COUNT"
    STAGE_DURATION_NS = "STAGE_DURATION_NS"


class DurationStage(str, Enum):
    SUBMIT = "SUBMIT"
    SCORE = "SCORE"


class BoundaryErrorKind(str, Enum):
    MCP_REQUEST = "mcp.request.invalid"
    MCP_RESOURCE = "mcp.resource_limit_exceeded"
    MCP_TOOL_UNAVAILABLE = "mcp.tool_unavailable"
    MCP_CHALLENGE_UNAVAILABLE = "mcp.challenge_unavailable"
    MCP_SUBMISSION_UNAVAILABLE = "mcp.submission_unavailable"
    MCP_QUERY_BUDGET = "mcp.query_budget_exceeded"
    MCP_INTEGRATION = "mcp.integration_failure"
    LEADERBOARD_REQUEST = "leaderboard.request.invalid"
    LEADERBOARD_RESOURCE = "leaderboard.resource.exhausted"
    LEADERBOARD_UNAVAILABLE = "leaderboard.fixture.unavailable"
    LEADERBOARD_INTEGRATION = "leaderboard.integration.failed"
```

There are no aliases, `auto()` values, integers, alternative lowercase
values, or extra members. `ObservabilityEvent` is frozen, slotted,
representation-safe, and has exactly ordered fields `kind`, `submission_id`,
`submission_state`, `score_status`. `BoundaryErrorEvent` has exactly one field,
`error_kind`. `ObservabilityResourceLimits` has only required exact positive
u64 `max_concurrent_calls`. All nominal values reject subclasses, coercion,
forged enum members, generic lookalikes, generic serialization/copying, and
caller-controlled representation.

**A11-R3 — Three capabilities only.** Construction is exactly
`ObservabilityService(event_sink, metric_sink, resource_limits)`, with every
argument mandatory and no `None`, default, environment selection, registry,
singleton, global sink, backend selector, or production numeric policy. The
only operations are:

```python
emit_event(event: ObservabilityEvent | BoundaryErrorEvent) -> None
increment_counter(metric: MetricKind) -> None
observe_duration(stage: DurationStage, duration_ns: int) -> None
```

Success returns exact `None`. There is no fourth operation, generic logger,
free-form message, mapping event, metadata/label bag, generic record/metric,
serializer, exporter, batch, flush, retry, queue, background worker, or sink
selection. A generic `logging.Logger` is not an A11 sink.

**A11-R4 — Submission observations and honest provenance ceiling.** The only
owner-shaped kind/state/status consistency matrix is:

| EventKind | exact A7 SubmissionState | exact A5 ScoreStatus |
|---|---|---|
| `SUBMIT` | `RECEIVED` | `None` |
| `SCORE` | `SCORED` | `SCORED` or `MANDATORY_GATE_FAILED` |
| `REJECT` | `REJECTED` | `None` |
| `FAILED_STRATEGY` | `FAILED_STRATEGY` | `None` |
| `FAILED_INFRA` | `FAILED_INFRA` | `None` |

`ObservabilityEvent` is an owner-shaped, process-local operational observation
request. A11 validates only exact nominal types and this closed consistency
matrix. It does not verify A7 record existence, read the current retained A7
state, prove an owner transition, distinguish a new submit from an open
duplicate, or authenticate A5/A7 provenance. Trusted composition alone
supplies the factual relationship to an owner transition. Exact nominal
values are correctness values, not authenticated capabilities. A syntactically
valid but unbound UUIDv4 has no lifecycle, scientific, audit, receipt, public,
security, settlement, or economic authority. Production provenance and
evidence remain separately deferred.

An absent ID cannot satisfy the four-field shape, but that structural fact is
not provenance. A11 imports/queries no `SubmissionService`, private A7 store or
record, fee/store internal, A8 outcome, receipt, or evidence store. Mismatched
pairs, `VALIDATED`, `QUEUED`, `RUNNING`, `PUBLISHED`, `CANCELLED`, retryable
infrastructure, `PACK_NOT_READY`, and unsupported future categories reject
without remapping.

**A11-R5 — Exact A9/A10 safe boundary-error projection.** The complete mapping
from exact current public owner error classes to closed A11 values is:

| Exact owner error type | BoundaryErrorKind | Exact literal value |
|---|---|---|
| `McpRequestError` | `MCP_REQUEST` | `mcp.request.invalid` |
| `McpResourceError` | `MCP_RESOURCE` | `mcp.resource_limit_exceeded` |
| `McpToolUnavailableError` | `MCP_TOOL_UNAVAILABLE` | `mcp.tool_unavailable` |
| `McpChallengeUnavailableError` | `MCP_CHALLENGE_UNAVAILABLE` | `mcp.challenge_unavailable` |
| `McpSubmissionUnavailableError` | `MCP_SUBMISSION_UNAVAILABLE` | `mcp.submission_unavailable` |
| `McpQueryBudgetError` | `MCP_QUERY_BUDGET` | `mcp.query_budget_exceeded` |
| `McpIntegrationError` | `MCP_INTEGRATION` | `mcp.integration_failure` |
| `LeaderboardRequestError` | `LEADERBOARD_REQUEST` | `leaderboard.request.invalid` |
| `LeaderboardResourceError` | `LEADERBOARD_RESOURCE` | `leaderboard.resource.exhausted` |
| `LeaderboardUnavailableError` | `LEADERBOARD_UNAVAILABLE` | `leaderboard.fixture.unavailable` |
| `LeaderboardIntegrationError` | `LEADERBOARD_INTEGRATION` | `leaderboard.integration.failed` |

`BoundaryErrorEvent` receives only exact `BoundaryErrorKind`. It contains no
SubmissionId, ChallengeKey, requester, request value, tool payload, cursor, provider,
exception object/text/message/cause/context/traceback, owner payload, private
field, hidden identifier, seed/draw, arbitrary string, or mapping. It is a
closed owner-shaped observation request and does not authenticate that an owner
error occurred.

Production `carbon.observability` imports no A9 or A10 module and exposes no
mapper or classifier. Trusted later composition may map only exact public
classes by exact type; every raw provider error must first be translated by its
A9/A10 owner boundary. Generic base errors, subclasses, lookalike/unknown
codes, arbitrary exceptions, and raw provider failures fail closed and cannot
construct a boundary event. A test-local composition harness may import the
public owner errors to prove the exact table without creating a production
dependency. Owner fixed messages are never copied into A11.

Reference, generator, reconstruction, retry, evidence, treasury, settlement,
commercial-acceptance, and Challenge-health kinds remain unrepresented until
their exact public owner types and integration seams are separately ratified.
Omission is not collapse.

**A11-R6 — Metrics, duration dimensions, and cardinality.** Metric order is
exactly `SUBMIT_COUNT`, `SCORE_COUNT`, `REJECT_COUNT`, `FAILED_INFRA_COUNT`,
`STAGE_DURATION_NS`. Only the first four are counter inputs and each call means
exactly one increment with no caller-supplied delta/value. The duration metric
exists only through `observe_duration`; `STAGE_DURATION_NS` is invalid for
`increment_counter`. No `FAILED_STRATEGY_COUNT`, gauge, arbitrary histogram,
dynamic name, decrement, or reset exists.

Metric labels and arbitrary metadata are exactly absent. `DurationStage` is a
closed typed argument, not a label map. Cardinality is structurally bounded by
four counter members and two duration stages. No identity, Challenge, score,
rank, cursor, provider, exception material, or arbitrary value becomes a
dimension.

**A11-R7 — Submission correlation only.** A11 creates no second correlation,
trace, span, request, receipt, or result identity. It reconstructs an owned
exact public A7 `SubmissionId` only as
`ObservabilityEvent.submission_id`. Copying provides mutation isolation, not
record or transition provenance. SubmissionId is forbidden from metrics,
labels, errors, free-form text, representations, generic serialization, and
public/miner/customer observability. This does not revoke A7/A9's separate
owner-controlled opaque ID interfaces. `RequesterIdentity` never crosses or is
imported.

**A11-R8 — Owner meanings remain distinct.** `REJECT` remains A7
request/admission semantics. `FAILED_STRATEGY` and `FAILED_INFRA` remain the
corresponding terminal A7 vocabulary; retryable/ambiguous infrastructure is
not collapsed. `SCORE` preserves exact A7 lifecycle `SCORED` and exact A5
scientific `SCORED` versus `MANDATORY_GATE_FAILED`. `PACK_NOT_READY` remains
non-scientific unavailability and cannot satisfy the matrix or be relabeled as
a current failure event. These are compatibility meanings, not A11-verified
owner state or provenance. A8 private outcomes/causes remain private and
unimported; A6 public failure tags are not widened.

**A11-R9 — No score, rank, or adaptive-oracle telemetry.** No raw/combined/
component score, gate, margin, stress, diagnostic, delta, rank/history, prior,
estimate, scaffold, practice result, feedback, or query history is accepted or
emitted. Exact A5 `ScoreStatus` is only a closed owner-vocabulary field. A5
remains sole scoring authority. A11 creates no adaptive-exam oracle,
Challenge-health decision, scientific evidence, or official/LIVE meaning.

**A11-R10 — Positive construction.** Exact outer-type validation precedes
declared-order positive extraction, exact owner/closed-enum validation,
structural prohibited-data exclusion, fresh immutable owned reconstruction,
non-blocking resource/reentrancy acquisition, and one sink access. There is no
arbitrary mapping/iterable/descriptor/object-graph traversal, reflection,
generic serializer, recursive sanitizer, serialize-then-redact path, or
hostile `repr`/`str`. With no allow-listed free-form text, CR/LF, Unicode,
oversized text, and secret-pattern threats are eliminated structurally; no
pattern redactor is shipped. Unsafe material rejects rather than being
silently transformed.

**A11-R11 — Forbidden material.** Events, metrics, durations, errors,
representations, and sink arguments exclude seeds, draws, roles, domains,
context, entropy, nonces, commitments, preimages, and hidden packs; Strategy,
parameters, weights, and artifacts; requester, hotkey, wallet, customer,
credentials, fees, payments, and rewards; results, receipts, cursors, and
provider values; prior, estimate, scaffold, practice, and query history;
scores, gates, margins, stress, diagnostics, and ranks; and exception objects,
text, stacks, paths, commands, environment values, and runtime configuration.
The exact closed `BoundaryErrorKind` token is not arbitrary exception material.
Sink failure handling and a forbidden fallback logger cannot reintroduce any
excluded value.

**A11-R12 — Duration and clock.** Duration stages are exactly `SUBMIT` and
`SCORE`. `duration_ns` is an exact built-in integer in `0..2**64-1`; boolean,
subclass, coercion, negative, float, and overflow reject. A11 emits no timestamp
and reads no wall, monotonic, date, timezone, sleep, deadline, or other
current-time source. Caller-supplied duration is descriptive only. Additional
stages require later owner ratification.

**A11-R13 — Protocol seams only.** The exact structural protocols are:

```python
class StructuredEventSink(Protocol):
    def emit_event(
        self,
        event: ObservabilityEvent | BoundaryErrorEvent,
        /,
    ) -> None: ...


class MetricSink(Protocol):
    def increment_counter(self, metric: MetricKind, /) -> None: ...

    def observe_duration(
        self,
        stage: DurationStage,
        duration_ns: int,
        /,
    ) -> None: ...
```

Concrete sinks are structural, not runtime-checkable Protocols, and receive no
runtime introspection. Every method must return exact `None`; missing or
call-incompatible methods and wrong returns are integration failures.
Test-local recording sinks are permitted but not exported. No concrete
production exporter, OpenTelemetry, Prometheus, StatsD, logging backend, HTTP,
filesystem, database, network, global/default sink, environment selection,
dashboard, or alerting is added.

**A11-R14 — Sink failure, capacity, and domain-result preservation.** One
shared finite per-service non-blocking capacity applies across all three
operations. Same-service sink reentrancy rejects before a second sink call. A
public operation makes at most one corresponding synchronous sink call; there
is no batch, queue, retry, fallback, background work, timeout, or exactly-once
durability claim. Capacity releases in `finally` after every exit class.

An ordinary sink-origin `Exception`, including a sink-raised public A11 error,
descriptor/hook failure, invocation failure, or wrong return, maps to one fresh
fixed `ObservabilityIntegrationError` without text/value/payload or
cause/context chaining. A non-`Exception` `BaseException`, including
`KeyboardInterrupt`, `SystemExit`, and `GeneratorExit`, propagates unchanged.
A synchronous hostile sink can block its caller; finite capacity is not a
timeout or preemption claim.

Trusted composition calls A11 outside owner locks and only after the domain
result that must survive is determined. A11 accepts, returns, stores, or
mutates no domain result; instruments no A5--A10 owner initially; and never
retries, suppresses, reorders, or reinterprets domain behavior. Telemetry
failure cannot alter an already-determined scientific, lifecycle, publication,
or economic result.

**A11-R15 — Exact errors.** The hierarchy is exactly:

```text
ObservabilityError(Exception)

ObservabilityRequestError(ObservabilityError)
  observability.request.invalid / Observability request is invalid.

ObservabilityResourceError(ObservabilityError)
  observability.resource.exhausted / Observability resource limit was exceeded.

ObservabilityIntegrationError(ObservabilityError)
  observability.integration.failed / Observability sink failed.
```

The three concrete errors are direct subclasses; there is no fourth public
error. They are fixed, immutable, non-echoing, representation-safe, unchained,
non-serializable, and carry no diagnostic payload. Malformed caller/event/
resource construction maps to request; acquired capacity or reentrancy
exhaustion maps to resource; sink integration maps to integration.

**A11-R16 — Exact acyclic dependencies and initial non-integration.** The
per-module dependency direction is exactly:

```text
model.py
  -> Python standard library
  -> exact public SubmissionId and SubmissionState from carbon.fees
  -> exact public ScoreStatus from carbon.scoring

providers.py
  -> Python standard-library typing
  -> A11 model types only

service.py
  -> Python standard library
  -> A11 model types
  -> A11 provider Protocols

__init__.py
  -> explicit local re-exports from model, providers, service
```

There is no production A6, A8, A9, or A10 import; no direct A5 engine/result,
A7 service/private-store/record/fee-internal, A8 private-outcome, A9/A10, audit,
evidence, `carbon.logging_utils`, exporter, filesystem/network/environment/
time, Landscape, neuron, Bittensor, chain, settlement, weight, or emission
source import or call. No owner package imports `carbon.observability`, and no
owner behavior or service changes merely to satisfy A11. Direct
instrumentation remains later trusted composition work. No third-party
dependency is added, and installed-wheel/outside-tree import remains required.

Current public package initialization is an explicit caveat, not a hidden
exception to the dependency rule: importing exact public A7 types through
`carbon.fees` transitively initializes its existing service dependencies, and
importing `ScoreStatus` through `carbon.scoring` initializes that package's
existing engine/pack exports. Consistent with existing authority, the
prohibition is on direct A11 source imports/calls; absence of those transitive
modules from `sys.modules` is not an attainable isolation claim. Production
A11 can and must remain free of A9/A10 imports and loads caused by A11 itself.

**A11-R17 — A12, maturity, and authority ceiling.** A11 may expose closed
source/runtime invariants for later A12 tests but creates no
`tests/invariants/`, marker, workflow/CI change, quality-baseline change, A12
status change, Wave-A report/closeout, or launch change. A11 is not an
EvaluationCard, evidence, receipt, transcript, audit, re-execution, durable
ledger, lifecycle, scoring, Challenge-health, information-budget,
adaptive-query, authentication, public-API, production-monitoring, incident,
alert, frontier/product/commercial, settlement, chain, Bittensor, weight,
emission, or LIVE authority.

Wave A remains controlling and incomplete. Wave B remains candidate planning
only and inactive. Wave B execution still requires implemented/reviewed/merged/
closed A11 and A12, `.agent/WAVE_A_REPORT.md`, independent review and normal
merge of the Wave B board/contract/handoff, a prospective exact-head-reviewed
and human-authorized activation change recording named owner-role approval,
the exact reviewed commit and SHA-256 hashes of the unchanged three artifacts,
and a separate reviewed post-merge activation closeout recording merge/tree
equality, CI, and named owner acceptance before B-01. B-07R/B-07S still gate
behavioral and exact service-protocol ratification. This candidate satisfies
none of those activation conditions.

**A11-R18 — Immutable A11-owned sink snapshot boundary.** This exact
documentation candidate selects Option A to resolve
`P1_MUTABLE_ENUM_SINGLETON_BOUNDARY_BYPASS`. It specifies future immutable
A11-owned sink snapshots; it does not implement them. A11-R18 supersedes only
the sink-facing portions of A11-R1, A11-R2, A11-R3, A11-R10, A11-R13,
A11-R14, and A11-R16. Every other A11-R1 through A11-R17 behavior and authority
ceiling remains in force. The effective amended contract becomes A11-R1
through A11-R18 only after independent review, explicit human authorization,
and normal merge of the exact amendment candidate. While its PR remains draft,
A11-R18 is specified by this candidate and is not ratified.

The corrective review of parent `9de896dea92e5378d99ef205cd21a29ef9f57fd3`
records:

```text
P1_SNAPSHOT_TYPE_MUTATION_SCOPE_OVERCLAIM
taxonomy: CONTRACT_DEFECT
current main defect: NO
PR #47 candidate defect at that parent: YES

P2_PUBLIC_SNAPSHOT_CONSTRUCTION_AMBIGUITY
taxonomy: CONTRACT_PRECISION_DEFECT
```

```text
P1_SNAPSHOT_TYPE_MUTATION_SCOPE_OVERCLAIM:
CORRECTED

P2_PUBLIC_SNAPSHOT_CONSTRUCTION_AMBIGUITY:
CORRECTED
```

The corrected supplied-instance scope below is not Option C. Option C would
permit mutation of shared owner/request/enum state or weaken isolation of the
supplied snapshot instance and its fields. Precisely excluding deliberate
class/module/global mutation, which requires a stronger isolation boundary,
does neither.

The public service request API remains exactly:

```python
ObservabilityService.emit_event(
    event: ObservabilityEvent | BoundaryErrorEvent,
) -> None

ObservabilityService.increment_counter(
    metric: MetricKind,
) -> None

ObservabilityService.observe_duration(
    stage: DurationStage,
    duration_ns: int,
) -> None
```

`ObservabilityEvent`, `BoundaryErrorEvent`, `MetricKind`, and `DurationStage`
are validated request values only. They are not sink arguments and are not
sink-safe snapshots after A11-R18. Public construction continues to accept
exact canonical A11/A5/A7 enums. A11 continues to make no record, provenance,
authentication, evidence, or authority claim.

The four future public sink-snapshot nominal types are exactly:

```python
SubmissionEventSnapshot(
    kind: str,
    submission_id: str,
    submission_state: str,
    score_status: str | None,
)

BoundaryErrorSnapshot(
    error_code: str,
)

CounterMetricSnapshot(
    metric_name: str,
)

DurationMetricSnapshot(
    stage: str,
    duration_ns: int,
)
```

These classes are future implementation requirements only and are not created
by this documentation decision. `SubmissionEventSnapshot` has exactly ordered
fields `kind`, `submission_id`, `submission_state`, and `score_status`.
`kind` is an exact built-in `str` from `SUBMIT`, `SCORE`, `REJECT`,
`FAILED_STRATEGY`, or `FAILED_INFRA`. `submission_id` is an exact built-in
`str`, exactly 36 ASCII characters in canonical UUIDv4 spelling already
validated through a fresh reconstruction by the public A7 `SubmissionId`
constructor, and is internal correlation only. `submission_state` is an exact
built-in `str` from the current event matrix: `RECEIVED`, `SCORED`, `REJECTED`,
`FAILED_STRATEGY`, or `FAILED_INFRA`. `score_status` is exact `None` or an exact
built-in `str` equal to `SCORED` or `MANDATORY_GATE_FAILED`. The exact existing
event matrix remains authoritative. The snapshot contains no `EventKind`,
`SubmissionState`, `ScoreStatus`, `SubmissionId`, or any other owner or A11 enum
or nominal object.

`BoundaryErrorSnapshot` has exactly one field, `error_code`, which is an exact
built-in `str` drawn only from the existing eleven `BoundaryErrorKind` literal
values:

```text
mcp.request.invalid
mcp.resource_limit_exceeded
mcp.tool_unavailable
mcp.challenge_unavailable
mcp.submission_unavailable
mcp.query_budget_exceeded
mcp.integration_failure
leaderboard.request.invalid
leaderboard.resource.exhausted
leaderboard.fixture.unavailable
leaderboard.integration.failed
```

It contains no `BoundaryErrorKind` member, owner error, exception, payload,
request value, provider value, identity, seed, draw, or arbitrary metadata.

`CounterMetricSnapshot` has exactly one field, `metric_name`, which is an exact
built-in `str` from `SUBMIT_COUNT`, `SCORE_COUNT`, `REJECT_COUNT`, or
`FAILED_INFRA_COUNT`. No labels, delta, dynamic name, boundary-error counter,
gauge, reset, or decrement exists. `DurationMetricSnapshot` has exactly ordered
fields `stage` and `duration_ns`. `stage` is an exact built-in `str` equal to
`SUBMIT` or `SCORE`; `duration_ns` is an exact built-in `int` in
`0..2**64-1`. No clock, timestamp, label map, or arbitrary dimension exists.

Each snapshot must be an exact manual slotted non-dataclass nominal class; a
fresh outer object per admitted service operation; free of an instance
`__dict__`; immutable through normal assignment and deletion;
representation-safe; non-copyable through `copy.copy` and `copy.deepcopy`;
non-pickleable; rejected by `dataclasses.asdict`, `dataclasses.astuple`, and
`dataclasses.replace`; and composed only of exact immutable built-in `str`,
`int`, or `None` fields. It contains no arbitrary mapping, iterable,
descriptor, object graph, owner object, enum member, exception, or metadata.
It is authority-free and is never accepted as a service request.

Direct public construction of all four snapshot classes is allowed. Each has
exactly the displayed parameter names and order, and every displayed parameter
is required. The constructors accept only the exact built-in field types,
literal sets, canonical UUIDv4 spelling, event-matrix combinations, and integer
range stated above. They reject `bool`, field-type subclasses, coercible or
malformed values, extra positional or keyword fields, constructor re-entry,
and partially initialized values. Construction always creates an exact manual
slotted non-dataclass instance with no instance `__dict__`, a fixed safe
representation, and the assignment, deletion, copy, deepcopy, pickle, and
dataclass-operation rejections stated above. No hidden token, private-factory
requirement, alternate constructor, or subclass construction is permitted; the
service uses these same public constructors after deriving exact primitive
fields. Directly constructed snapshots prove only exact closed shape and
create no provenance, owner transition, lifecycle, scientific, audit, receipt,
public, security, settlement, or economic authority. The service rejects all
four snapshot types as request values.

The effective future ordered `carbon.observability.__all__` tuple is exactly:

```python
(
    "EventKind",
    "MetricKind",
    "DurationStage",
    "BoundaryErrorKind",
    "ObservabilityEvent",
    "BoundaryErrorEvent",
    "ObservabilityResourceLimits",
    "SubmissionEventSnapshot",
    "BoundaryErrorSnapshot",
    "CounterMetricSnapshot",
    "DurationMetricSnapshot",
    "StructuredEventSink",
    "MetricSink",
    "ObservabilityService",
    "ObservabilityError",
    "ObservabilityRequestError",
    "ObservabilityResourceError",
    "ObservabilityIntegrationError",
)
```

This is exactly eighteen names. The previous fourteen-name surface is
superseded only after A11-R18 normally merges. No owner type is re-exported; no
generic logger, serializer, provider, mapper, or extra error is exported.

Future effective module ownership is exactly:

```text
model.py
  EventKind
  MetricKind
  DurationStage
  BoundaryErrorKind
  ObservabilityEvent
  BoundaryErrorEvent
  ObservabilityResourceLimits
  SubmissionEventSnapshot
  BoundaryErrorSnapshot
  CounterMetricSnapshot
  DurationMetricSnapshot
  ObservabilityError
  ObservabilityRequestError
  ObservabilityResourceError
  ObservabilityIntegrationError
  private exact request validation and public-constructor invocation helpers only

providers.py
  StructuredEventSink
  MetricSink
  no concrete/default/global sink

service.py
  ObservabilityService
  request-to-snapshot conversion
  shared capacity and same-service reentrancy accounting
  sink lookup/invocation/return validation
  exception translation
  no owner instrumentation

__init__.py
  exact ordered eighteen-name re-export tuple only
```

The future exact structural, non-runtime-checkable Protocols are:

```python
class StructuredEventSink(Protocol):
    def emit_event(
        self,
        event: SubmissionEventSnapshot | BoundaryErrorSnapshot,
        /,
    ) -> None: ...


class MetricSink(Protocol):
    def increment_counter(
        self,
        metric: CounterMetricSnapshot,
        /,
    ) -> None: ...

    def observe_duration(
        self,
        metric: DurationMetricSnapshot,
        /,
    ) -> None: ...
```

Concrete sinks subclass neither Protocol. No production sink is added. The
three public `ObservabilityService` operations remain unchanged. These
Protocols are trusted in-process integration seams. Only trusted composition
supplies sinks at mandatory service construction; miner-controlled or service-
request input cannot choose or supply a sink implementation.

The future service performs this exact order:

1. Before capacity acquisition or sink access, validate the exact outer request
   type.
2. Validate exact canonical enum type, identity, name, and literal value.
3. Validate the existing event matrix or metric/duration boundary.
4. Reconstruct and validate `SubmissionId` through the public A7 constructor
   where applicable.
5. Map validated semantic values to A11-owned hard-coded literal strings.
6. Use the same direct public exact constructor to construct a fresh snapshot
   containing no request object, owner object, or enum reference.
7. Acquire capacity and same-service reentrancy permission.
8. Make at most one sink call.

The service must never pass `EventKind`, `MetricKind`, `DurationStage`,
`BoundaryErrorKind`, `SubmissionState`, `ScoreStatus`, `SubmissionId`,
`ObservabilityEvent`, or `BoundaryErrorEvent` to a sink. It must not carry a
mutable enum member forward to derive sink fields and must not traverse or copy
an enum member `__dict__`. Caller-added enum attributes are never consulted,
copied, retained, rendered, or emitted. Corrupted `_name_` or `_value_` state
rejects before capacity and sink access. Snapshot fields come from A11
module-owned fixed literal tables after exact validation. Mutation of a request
enum after snapshot construction cannot alter the snapshot. No
sanitize-and-restore mutation of shared enum state is permitted, and no global
lock is held across sink code.

The exact supplied-snapshot-instance isolation scope is:

```text
Mutation of the supplied snapshot instance and its declared primitive fields,
including normal assignment and object.__setattr__, cannot alter caller,
owner, retained, concurrent, another-service, or later A11 state.
```

Each sink receives one fresh per-call snapshot instance. A sink may use Python
escape hatches to alter that distinct instance, but the retained instance
cannot affect another call because its declared fields are exact immutable
built-in primitives, it contains no shared mutable owner or enum reference,
and A11 never reuses a snapshot object.

A11 does not defend against sink code that deliberately retrieves and mutates
the snapshot class, A11 module globals, owner classes/modules, or any other
process global.

Such class/global mutation is outside the trusted in-process sink contract and
requires process isolation or capability restriction, neither of which Wave A
implements or claims.

This exclusion does not permit A11 to pass a shared enum, owner nominal,
request object, mapping, exception, metadata, or other mutable shared instance.
Caller-added enum attributes remain excluded; no shared enum sanitize/restore
occurs; and no ordinary mutex is held across sink code. Production-sink
hardening, process isolation, plugin capability restriction, and hostile-sink
qualification remain separately deferred. A11 claims no resistance to
arbitrary malicious Python executing in the same process. `SECURITY_QUALIFIED`
and `PRODUCTION_QUALIFIED` remain `NO`.

The unchanged `agent_pack/README.md` phrase "mutation through an A11-supplied
sink value" is non-normative shorthand for mutation of the supplied snapshot
instance and its declared primitive fields only. It does not extend the
guarantee to a class, module, or global object reachable through that instance;
this A11-R18 text controls.

The current service-request dependency direction remains exactly:

```text
model.py
  -> Python standard library
  -> public SubmissionId and SubmissionState from carbon.fees
  -> public ScoreStatus from carbon.scoring
```

Snapshot classes depend only on Python built-ins and local A11 validation. No
A5/A7 owner source changes occur. No A9/A10 production import occurs. No owner
package imports `carbon.observability`, and no owner service instrumentation
occurs. A11-R18 adds no third-party dependency and changes no owner authority.

This amendment changes specification only. A11 remains unimplemented and
untested on current main; all scientific, security, network, commercial, and
production qualification states remain `NO`; A11 and A12 remain `todo`; Wave A
remains incomplete; and Wave B remains candidate planning only and inactive.
The implementation ticket remains exactly 66 unchecked criteria and zero
checked criteria, and the plan remains at zero checkbox markers.

The required next moves are exactly:

1. Independently review and ratify exact A11-R18.
2. Normally merge the exact reviewed amendment only after explicit human
   authorization.
3. Synchronize PR #46 with the amendment merge.
4. Repair PR #46 to implement the snapshot boundary.
5. Independently review the repaired implementation before ready or merge.

**Canonical future proof and review gate.** The amended future contract is
recorded in `.agent/plans/A11_logging.md` and exactly 66 unchecked
implementation criteria in `.agent/tickets/A11_logging.md`, with zero checked
boxes and zero checkbox markers in the plan. The canonical future focused path
remains `tests/cpu/test_observability.py`; it is not created here.

In addition to every unchanged A11-R1 through A11-R17 proof obligation, the
later repaired implementation must prove in both source-tree and
installed-wheel tests that:

- every request enum may carry an arbitrary caller-added canary attribute
  without that attribute reaching a snapshot;
- no sink receives any enum member or `SubmissionId` object;
- every snapshot field is an exact built-in primitive;
- request `_name_` or `_value_` corruption rejects;
- mutation of a request enum after snapshot creation cannot alter the sink
  snapshot;
- normal or `object.__setattr__` mutation of a supplied snapshot instance and
  its declared primitive fields cannot affect the caller, owner enums, another
  service, concurrent operations, or later calls;
- a retained snapshot-instance mutation cannot affect later calls;
- each call receives a distinct outer snapshot;
- no snapshot-and-restore global mutation occurs;
- no lock is held across sink execution;
- deliberate mutation of a snapshot class, A11 module global, owner
  class/module, or other process global is outside the trusted in-process sink
  contract and is not claimed as an instance-isolation proof;
- all four exact public snapshot constructors accept their required displayed
  parameters directly and reject malformed, extra, re-entry, partial,
  coercible, bool, field-subclass, and snapshot-subclass construction;
- the previous dataclass correction remains intact;
- public service method signatures remain unchanged;
- Protocol signatures match A11-R18;
- the exact eighteen-name export tuple appears;
- no A5/A7 owner source changes occur; and
- no owner instrumentation, A12 action, or Wave B activation occurs.

Proof must also retain the exact enum definitions and request shapes; complete
exact-type A9/A10 mapping in a test-local composition harness;
raw/unknown/subclass rejection; the honest provenance ceiling; owner meanings;
leakage exclusions; bounded cardinality; duration/clock boundaries; call,
blocking, capacity, reentrancy, failure, and domain-result behavior; direct
source-dependency guards; A9/A10 production-import absence; full CPU
regression; Ruff; Black; and no-new-debt. No process-sandbox guarantee is added.
Documentation and existing regression evidence do not make A11 IMPLEMENTED or
TESTED. Independent exact-head review, explicit human authorization, and
normal merge remain mandatory before A11-R18 ratification.

## 2026-08-26 — A10 bounded fixture-leaderboard implementation and conditional closeout

**Decision and authority boundary.** The A10-R1 through A10-R17 contract was
ratified by normal PR #36 merge
`f4ad756a994a9bf21d919fccc4f164fc9719f4e6`, tree
`17140d76d8c50d0c78880a95c00f9b75f3be8ee1`, with ordered parents
`f308281e69580216d5ebf5ec94a9d6c069cf1a56` and
`aca22b4727e9e571a95745294004f733aa419e14`. The dated 2026-08-25 entry below
is preserved as the historical ratification record; its pending and
future-state statements are not rewritten into false history.

Current main is exact implementation merge
`3b2d96e287f06c24cc4d57b46dfc418359a9e97f`, tree
`6a6e95262773b9b2e22ad5c43837194f06e070a6`, subject `Merge pull request
#37 from carbonphysicsai/agent/a10-leaderboard`, with a valid GitHub signature
and ordered parents `bc95ef09910014ff3d08d3f0a9fbfaf6999c2d79` then reviewed
implementation head `6f505d5cffd69f0c3d4d0e6d71bb91233c0ce6b1`. The reviewed head has the
same exact tree, is ancestral to current main, and has an empty file diff to
the merge. PR #37 merged normally at `2026-08-26T07:14:59Z`; auto-merge was
never enabled and its source branch remains present at the reviewed head.

The exact five-commit implementation and corrective history is:

1. `d69b5ec77e630914fce4068abe2dc5303876cd12` — `feat: implement bounded A10 fixture leaderboard`;
2. `1c5196a5a48caeb6c9a14f90cef3c00fd6cfd7b9` — `merge: synchronize A10 implementation with current main`, with ordered parents `d69b5ec77e630914fce4068abe2dc5303876cd12` then `bc95ef09910014ff3d08d3f0a9fbfaf6999c2d79`;
3. `bd263c44fa955f32a28a6afd1c56ed8b9334cf11` — `fix: bound A10 challenge identity before reconstruction`;
4. `6be31d10272ac18b580a4733079318f7d3d69309` — `fix: bound A10 provider identifiers before validation`;
5. `6f505d5cffd69f0c3d4d0e6d71bb91233c0ce6b1` — `fix: enforce A10 UTF-8 byte capacities`.

The exact parent-one-to-merge delta is the following six paths and
`+5125/-3`; no merge-time edit, conflict resolution, or seventh path entered
the merge:

| Path | Status | Additions | Deletions | Merged blob |
|---|---:|---:|---:|---|
| `.agent/WAVE.md` | M | 2 | 2 | `9f95f658ba22e801290e3a770db2106249c83734` |
| `carbon/leaderboard/__init__.py` | M | 45 | 1 | `67823bc69da8591f5d2729e79fc679443a42e5ce` |
| `carbon/leaderboard/model.py` | A | 781 | 0 | `2450cc8f3487bb8a1a9b258445900aafa36e82f4` |
| `carbon/leaderboard/providers.py` | A | 24 | 0 | `000aebd1b0eced4122c2a0496d8ecc5b434a9d78` |
| `carbon/leaderboard/service.py` | A | 905 | 0 | `ca7bfa97f126fab2b251f729ede2254da078d36f` |
| `tests/cpu/test_leaderboard.py` | A | 3368 | 0 | `23480fb2dc6e4d59ecf16c5207c105cf4274dd81` |

**Review findings and repairs.** Greptile's first substantive finding required
Challenge identity capacity to precede ASCII validation and A3
reconstruction. Commit `bd263c44fa955f32a28a6afd1c56ed8b9334cf11`
made that gate explicit for request, snapshot, and candidate Challenges. Its
second substantive finding required `SubmissionId`, `result_id`, and
scoring-pack capacity to precede A7/A3 construction or validation; commit
`6be31d10272ac18b580a4733079318f7d3d69309` repaired all three identifier
families. Final follow-up required exact valid-Unicode UTF-8 byte accounting
and both incoming-cursor byte limits before ASCII validation; commit
`6f505d5cffd69f0c3d4d0e6d71bb91233c0ce6b1` closed that family.

Final Greptile check `98088524053` succeeded on the exact reviewed head and
reported six files reviewed with zero comments and zero annotations. Summary
comment `5420464156` records confidence `5/5` and no blocking failure. Both
substantive threads are resolved and outdated; unresolved substantive count is
zero. All four formal reviews remain `COMMENTED`, not `APPROVED`; this record
does not claim a formal GitHub approval. The stale historical sentence in the
closed PR #37 body was not edited and does not override current thread state.

**Merged and fresh engineering evidence.** Exact post-merge push run
`32941840184` is `push/main` on current main and completed successfully. CPU
job `98094221825` recorded `1973 passed in 53.86s`. Quality job
`98094221851` recorded `Ruff 757/776`, `Black 62/68`, removed Ruff debt `19`,
removed Black debt `6`, five changed Python files, no new debt, and every
changed Python file clean.

The independent closeout audit used Python `3.11.11` in a fresh isolated
environment over exact current main. Focused A10 passed `246` tests in
`6.05s`; the exact related suite passed `1530` in `29.62s`; the full default
suite passed `1973` in `30.61s`. Ruff `0.16.3` passed and Black `26.5.1`
would leave the four A10 modules and sole focused test unchanged. Fresh wheel
`carbon-0.9.0-py3-none-any.whl` is `183340` bytes with SHA-256
`e39008b41550ecd3d198a1a2e01548178f72cc4f0aa722c99aa185ba538153d7`.
It installed into a second fresh environment with `--no-deps --no-index`.
Outside-checkout `python -I` proved site-packages resolution, distribution
`carbon==0.9.0`, zero mandatory dependencies, the exact ordered sixteen-name
root export tuple, representative public construction and fixture ranking, and
zero attempted or newly loaded blocked optional-heavy, A8, A9, A11+, web,
HTML, filesystem, environment, current-time, Landscape, neuron, Bittensor,
chain, weight, settlement, or emission modules.

Every one of the 57 unchanged A10 ticket criteria was independently traced to
its controlling A10-R decision or owner boundary, exact current source symbol,
canonical test evidence, applicable A3/A5/A6/A7/A8/A9 owner evidence, and
bounded exclusion. Result: `57 PASS / 0 FAIL`. Checking those criteria in the
documentation-only closeout records already-merged implementation truth; the
closeout adds no implementation or test evidence.

**Exact bounded maturity.** The decision records only this ceiling:

~~~text
A10 SPECIFIED / RATIFIED: YES
A10 IMPLEMENTED: YES on current main only for the exact bounded in-process fixture leaderboard
A10 TESTED: YES only for the exact recorded CPU, hostile-input, resource, concurrency, leakage, dependency, import, wheel, and quality engineering scope, including all reviewed repairs
A10 SCIENTIFICALLY_QUALIFIED: NO
A10 SECURITY_QUALIFIED: NO
A10 NETWORK_QUALIFIED: NO
A10 COMMERCIALLY_VALIDATED: NO
A10 PRODUCTION_QUALIFIED: NO
A10 WAVE STATUS: done only after this closeout is independently reviewed, explicitly human-authorized, and normally merged
A11: todo
A12: todo
~~~

This closeout does not provide or authorize a production provider or
publication feed; an official or LIVE leaderboard; public identity,
authentication, hotkey publication, anonymization, or timestamp publication;
durable persistence; HTTP, REST, GraphQL, HTML, or network transport; official
score precision or cadence; adaptive-query security qualification;
cross-Challenge or global ranking; `FrontierRecord`, `FrontierAdvanceEvent`,
or frontier nomination authority beyond informational rank; Product
Qualification; commercial ranking; settlement or treasury; chain, Bittensor,
weights, or emissions; A11 logging or metrics; A12 aggregate-invariant work;
or scientific, security, network, commercial, or production qualification.

The board and ticket may therefore propose A10 `done`, but that state becomes
repository authority only after this documentation-only closeout receives
independent review, fresh explicit human authorization, and a normal merge.
Draft publication alone is not review, authorization, readiness, or merge.
Wave A is not claimed closed; A11 and A12 remain `todo`.

## 2026-08-25 — A10 bounded fixture-leaderboard contract candidate

**Repository truth, status, and scope.** A fresh fetch/prune resolved
origin/main to exact commit
f308281e69580216d5ebf5ec94a9d6c069cf1a56, tree
a2875c0b12caf7d4c07316626c218c55f3eb77ea, and subject
“Merge pull request #35 from carbonphysicsai/agent/a9-closeout”. Its ordered
parents are 0099a198bf19845390a0a12825eac0eeef06ffd2 and exact A9 closeout
head 3ed12f1c3f993da29955a6b2db7a2b38ee9e2575. The second parent matches
origin/agent/a9-closeout. The starting worktree was clean.

All GitHub pull requests, fetched branches, commits outside current main,
plans, tickets, and current source were searched for A10, leaderboard,
orientation, ratification, implementation, and repair work. No open pull
request, A10 branch, A10 plan, A10 test, A10 implementation, or other active
A10 candidate exists. The sole fetched branch not merged into origin/main is
unrelated symbolic-numeric design work. The current carbon/leaderboard package
contains only its one-line A0 deferred marker. A10, A11, and A12 are todo, and
all five legacy A10 ticket boxes were unchecked before this candidate.

This eight-path documentation candidate adds the A10 plan and reconciles only
the decision log, A10 ticket, constitutional overlay, agent-pack guidance,
current and historical maturity ledgers, and defensibility register. It
changes no WAVE board, Python, test, fixture, dependency, packaging, workflow,
CI, quality baseline, A0--A9 ticket/plan/behavior/maturity, or A11/A12 file. It
implements and tests nothing.

~~~text
A10 SPECIFIED / RATIFIED: pending merge of PR #36
A10 IMPLEMENTED: NO
A10 TESTED: NO
A10 SCIENTIFICALLY_QUALIFIED: NO
A10 SECURITY_QUALIFIED: NO
A10 NETWORK_QUALIFIED: NO
A10 COMMERCIALLY_VALIDATED: NO
A10 PRODUCTION_QUALIFIED: NO
A10 WAVE STATUS: todo
A11: todo
A12: todo
~~~

**Conflict classification.** The current A3 ChallengeKey, A5 ScoreStatus and
sole-score-authority boundary, A6 disclosure boundary, A7 SubmissionId,
constitutional invariants, and fixture/non-emission maturity ceiling are
NO_CONFLICT. The pre-ratification A10 ticket's alternative list/get operation,
hotkey-or-anonymized identity, timestamp, old test path, and ambiguous
fixture-or-official mode, together with the absent detailed A10 plan, are
DOCUMENTATION_LAG and are replaced only for A10 by A10-R1--A10-R17 below. The
absent A10 implementation and tests are IMPLEMENTATION_LAG, not evidence that
the legacy script implements A10.

The former overbroad provider-failure wording is also DOCUMENTATION_LAG. It
does not authorize catching or translating a non-Exception BaseException and
changes no A10 architecture, public API, maturity, or owner boundary.

The undefined `max_response_utf8_bytes` accounting procedure identified by the
stopped ready-review gate is likewise DOCUMENTATION_LAG. The limit is an exact
logical successful-page UTF-8 occurrence budget, not a wire-format contract.
Defining it changes no A10 field, architecture, public API, maturity, or owner
boundary.

The historical scripts/generate_leaderboard.py, validator/neuron code,
Landscape material, direct score-to-emission language, and generic public
leaderboard prose are archaeology or superseded whenever they conflict with
this contract. They are neither imported nor repaired here. A production
publication source, official identity/disclosure policy, official score
precision/cadence, adaptive-query policy, and every frontier, Product
Qualification, settlement, chain, weight, and emission decision are
NEW_OWNER_DECISION_REQUIRED for later separately authorized work. No migration
is required for this documentation-only candidate because no A10
implementation exists. Production remains fail closed.

**A10-R1 — Bounded fixture-only scope and maturity ceiling.** Wave-A A10 is
only a bounded, in-process projection over an injected fixture publication
snapshot. It provides no HTTP, REST, GraphQL, web UI, HTML, filesystem
publication, network server, chain access, Bittensor access, persistence,
scheduler, background refresh, or current-time behavior.

A10 publishes no official or LIVE leaderboard. An absent official publication
feed means that an official board is unavailable; it must never be represented
as an empty authoritative board. A future official publication feed, provider,
service, request, row, page, cursor, identity policy, precision policy, and
cadence require a separate owner-ratified contract and nominal types.

**A10-R2 — Nominal types and single service operation.** The future
implementation uses nominal A10 fixture-only request, service, provider,
candidate, snapshot, row, page, sequence, cursor, resource, and error types.
It must not accept a caller-controlled mode string such as
mode="fixture|official" and must not make fixture/official selection a field,
flag, enum branch, or alias.

The only operation is:

~~~text
FixtureLeaderboardService.list_entries(
    request: ListFixtureLeaderboardRequest,
) -> FixtureLeaderboardPage
~~~

Construction is exactly:

~~~text
FixtureLeaderboardService(
    provider: FixtureLeaderboardProvider,
    resource_limits: FixtureLeaderboardResourceLimits,
)
~~~

Both arguments are mandatory. There is no default or None substitute and no
global, registry, environment, singleton, network, or server lookup. The exact
A10 resource-limits value is copied and validated during construction.

The nominal value fields are exact:

~~~text
PublicationSequence(value: exact built-in int in 0..2**64-1)
LeaderboardSnapshotSequence(value: exact built-in int in 0..2**64-1)
LeaderboardCursor(value: exact built-in ASCII str)
ListFixtureLeaderboardRequest(
    challenge_key: exact ChallengeKey,
    page_size: exact built-in int in 1..2**64-1,
    cursor: exact LeaderboardCursor | None,
)
~~~

The cursor string is opaque and resource bounded. The request has no requester,
identity, mode, search, or filter field.

The exact ordered carbon.leaderboard.__all__ tuple is:

~~~python
(
    "PublicationSequence",
    "LeaderboardSnapshotSequence",
    "LeaderboardCursor",
    "ListFixtureLeaderboardRequest",
    "FixtureLeaderboardCandidate",
    "FixtureLeaderboardCandidateSnapshot",
    "FixtureLeaderboardRow",
    "FixtureLeaderboardPage",
    "FixtureLeaderboardResourceLimits",
    "FixtureLeaderboardProvider",
    "FixtureLeaderboardService",
    "LeaderboardError",
    "LeaderboardRequestError",
    "LeaderboardResourceError",
    "LeaderboardUnavailableError",
    "LeaderboardIntegrationError",
)
~~~

No alias, generic service/provider type, official type, store, serializer, or
extra error is exported.

A10 does not ratify get(submission_id), global listing, cross-Challenge
listing, identity filtering, hotkey lookup, participant lookup,
score-threshold search, timestamp search, total-count lookup, or any alias for
those operations.

**A10-R3 — Injected publication-provider seam.** FixtureLeaderboardProvider is
a standard-library typing.Protocol supplied only by trusted composition. A
concrete provider satisfies it structurally and need not subclass it. The
service must not require type(provider) to be the Protocol, use
runtime_checkable or isinstance-style protocol introspection, or expose the
provider as caller-controlled public input. The exact future seam is:

~~~python
FixtureLeaderboardProvider.get_snapshot(
    challenge_key: ChallengeKey,
    snapshot_sequence: LeaderboardSnapshotSequence | None,
) -> FixtureLeaderboardCandidateSnapshot | None
~~~

The provider receives the request's exact ChallengeKey and either no snapshot
sequence for the first page or the exact cursor-bound snapshot sequence for a
continuation. Exact None is the sole normal unavailable result: on a first-page
call it means there is no current retained fixture snapshot, while on a
continuation it means the exact cursor-bound snapshot is absent or stale. Both
map to the fixed LeaderboardUnavailableError. A returned exact snapshot,
including one whose candidates tuple is empty, is available.

A missing or call-incompatible method and any non-None malformed or wrong
return map to one fixed LeaderboardIntegrationError. Every ordinary exception
`error` raised by provider-controlled behavior for which
`isinstance(error, Exception)` is true, whether encountered during method
lookup, a descriptor or hook, invocation, or access to provider-controlled
values during result validation, maps to one new fixed
LeaderboardIntegrationError.

A provider must not pass a public A10 error through this boundary. Because
LeaderboardRequestError, LeaderboardResourceError,
LeaderboardUnavailableError, and LeaderboardIntegrationError inherit from
Exception, a provider-raised instance of any of them is translated into one new
fixed LeaderboardIntegrationError without passthrough or chaining. Translation
uses only the exact integration code and message; no provider text, value,
payload, cause, or context and no partial response escapes.
A10-created public failures retain their exact A10-R12 mappings; this
provider-origin rule does not reclassify them.

A BaseException value that is not an Exception instance propagates unchanged.
A10 never catches or translates KeyboardInterrupt, SystemExit, or
GeneratorExit and must not use `except BaseException` around provider method
lookup, invocation, result validation, or the top-level public-error translation
boundary. A hostile provider descriptor or hook raising such a value also
propagates unchanged. Once acquired, the bounded concurrency permit is released
in `finally` after success, public failure, translated ordinary Exception, and
propagated non-Exception BaseException alike. For a valid snapshot, A10
validates and copies the entire projection; it does not discover, construct,
repair, or publish candidate records.

The provider, not A10, owns selecting published candidates; excluding
unpublished, cancelled, withdrawn, superseded, and stale records; consulting
A3 fixture eligibility; copying only separately authorized A5/A6/A7 fields;
assigning fixture publication and snapshot sequences; and retaining the exact
bounded snapshots required by active cursors.

A10 must not inspect or enumerate A5 InternalResult, A6 CardStore or private
records, A7 private store or private records, A8 private execution outcomes,
or any A9 priors, estimates, scaffolds, mock outputs, or result feedback. It
does not modify A6 or A7. A future official provider/feed is unratified.

**A10-R4 — Closed provider-candidate projection.** The exact provider-only
candidate fields are:

~~~text
submission_id: exact A7 SubmissionId
result_id: exact bounded A6 result identifier
challenge_key: exact A3 ChallengeKey
scoring_pack_hash: exact A6 public score-pack hash
score_status: exact A5 ScoreStatus
overall_score: exact finite built-in float
mandatory_gates_passed: exact built-in bool
fixture_origin: exact built-in bool
eligible_for_emission: exact built-in bool
publication_sequence: exact PublicationSequence
~~~

The exact snapshot fields are:

~~~text
challenge_key: exact ChallengeKey
scoring_pack_hash: exact canonical tagged SHA-256
snapshot_sequence: exact LeaderboardSnapshotSequence
candidates: exact tuple of FixtureLeaderboardCandidate values, possibly empty
~~~

Integration validation reuses the owners' public primitives: construct
ChallengeKey and SubmissionId values through their public nominal constructors,
validate result_id with validate_version, validate scoring_pack_hash with
is_sha256_digest, and require exact ScoreStatus. A10 does not duplicate any
version-token, digest, Challenge-key, UUID, or score-status grammar.

SubmissionId and result_id exist only to validate provider integration and
snapshot uniqueness. Neither may appear in any public row, page, cursor,
error, representation, or other observable A10 object.

This candidate projection is not a second SubmissionId type, lifecycle, score
engine, card schema, result store, or publication store. A10 gives it no write
authority and persists none of it.

**A10-R5 — Exact public row and page allow-lists.** A future fixture row
contains exactly these public values and no others:

~~~text
rank
challenge_key: exact ChallengeKey
scoring_pack_hash
overall_score
mandatory_gates_passed
publication_sequence
fixture_origin
eligible_for_emission
~~~

The row's ChallengeKey is the exact A3 value bound to the request and snapshot.
Its mandatory_gates_passed is always True, fixture_origin is always True, and
eligible_for_emission is always False.

The page contains only schema_version exactly "1.0", exact ChallengeKey, exact
scoring_pack_hash, exact LeaderboardSnapshotSequence, immutable tuple of the
allow-listed rows, next opaque cursor or None, fixture_origin=True, and
eligible_for_emission=False. It exposes no total row count.

Rows, pages, cursors, errors, and representations omit requester, hotkey,
wallet, public participant ID, anonymized ID, SubmissionId, result_id,
timestamp, component scores, gate IDs, gate counts, failure tags, private
diagnostics, margins, stress values, fee/payment fields, rank delta,
improvement history, submission count, win rate, data-source labels, and
provider metadata.

**A10-R6 — Identity boundary.** Where surrounding trusted composition already
uses RequesterIdentity, it remains only a structural requester binding, not
authentication proof and not a public hotkey. A10 neither imports it nor puts
it in the list request. Wave A publishes no participant field and performs no
anonymization. It invents no anonymization key, stability period, rotation
policy, or cross-Challenge correlation policy. Identity creates no
lookup/filter/grouping semantics. There is one row per provider-approved
published submission, not one row per requester, identity, wallet, or hotkey.

**A10-R7 — Provider-owned sequence, no time.** Wave A exposes no timestamp and
must not access current time. PublicationSequence and
LeaderboardSnapshotSequence are distinct nominal provider-owned values. Each
contains one exact built-in int in 0..2**64-1; bool and int subclasses are
rejected. Each is monotonic only within one exact fixture Challenge publication
stream. Neither has wall-clock, chain-height, finality, A7 lifecycle,
settlement, rank-improvement, or duration meaning. A10 never generates either
sequence.

**A10-R8 — Eligibility is closed and fail-closed.** A provider candidate may
rank only when all of the following hold:

- score_status is exactly ScoreStatus.SCORED;
- mandatory_gates_passed is exact True;
- overall_score is an exact finite built-in float;
- overall_score is in the closed interval 0.0 through 1.0;
- if overall_score == 0.0, math.copysign(1.0, overall_score) == 1.0;
- fixture_origin is exact True;
- eligible_for_emission is exact False;
- ChallengeKey exactly equals the request and snapshot ChallengeKey;
- scoring_pack_hash exactly equals the snapshot score-pack hash; and
- submission_id, result_id, and publication_sequence are each unique within
  the whole snapshot.

MANDATORY_GATE_FAILED, PACK_NOT_READY, unpublished, cancelled, withdrawn,
superseded, infrastructure-incomplete, mock, prior, estimate, and scaffold
values are excluded. Fees, payments, sponsor values, and customer values are
never eligibility or rank inputs. A mandatory-gate failure must never become
an ordinary ranked zero. No current result is eligible for an official board.

The provider normally excludes non-published/ineligible lifecycle state before
return. If malformed provider output nevertheless contains any candidate that
violates this closed contract, A10 rejects the whole snapshot as an integration
failure. It must not silently filter malformed provider output into an
apparently authoritative partial page.

Negative zero is non-canonical malformed provider output. A10 rejects -0.0 as
an integration failure and never normalizes it to +0.0.

**A10-R9 — A5 remains sole score and gate authority.** A10 consumes the exact
provider-projected overall_score and scoring_pack_hash. It must not recompute,
normalize, aggregate, rescale, round, quantize, predict, estimate, or otherwise
transform a score.

The only public gate summary is mandatory_gates_passed=True. Gate IDs,
optional-gate outcomes, failed-gate counts, margins, stress values, component
scores, failure tags, and diagnostics remain private and absent. Fixture
scores retain their exact finite built-in-float precision. Official score
precision, publication cadence, and adaptive-query controls are deferred.

**A10-R10 — Deterministic order, ties, ranks, and duplicates.** Whole-snapshot
order is overall_score descending. Exact built-in-float equality creates a
tie. Tied rows share competition rank, so ranks follow 1, 1, 3.
PublicationSequence ascending provides deterministic order within an exact
tie without changing the shared rank.

A duplicate SubmissionId, result_id, or PublicationSequence fails the entire
snapshot. Mixed ChallengeKey or scoring_pack_hash values also fail the entire
snapshot. The complete bounded snapshot is validated, duplicate-checked,
sorted, and competition-ranked before any page is sliced. Ranks are therefore
stable across pages and page-size changes. No partial page survives malformed
provider output.

A10 performs no best-per-requester, best-per-hotkey, participant aggregation,
decay, win-rate, submission-count, rank-delta, improvement-history, or
fee-based ordering. The provider owns retry, republication, withdrawal, and
supersession selection.

**A10-R11 — Bounded snapshot pagination.** The exact request fields and bounds
are defined in A10-R2. FixtureLeaderboardResourceLimits has exactly these six
required, non-defaulted fields:

~~~text
max_page_size
max_snapshot_rows
max_cursor_utf8_bytes
max_string_utf8_bytes
max_response_utf8_bytes
max_concurrent_calls
~~~

Every field is an exact built-in int in 1..2**64-1; bool and subclasses are
rejected. No default, None value, production numeric value, global, registry,
environment lookup, or adaptive rate policy is ratified.

LeaderboardCursor contains one exact built-in ASCII str and remains opaque and
bounded to callers. Its private logical payload has exactly:

~~~text
schema_version: "1.0"
board_kind: "fixture_leaderboard"
challenge_key: exact ChallengeKey
scoring_pack_hash: exact canonical tagged SHA-256
snapshot_sequence: exact LeaderboardSnapshotSequence
next_offset: exact built-in int in 0..2**64-1
~~~

It contains no SubmissionId, result_id, requester, identity, seed, draw, role,
domain, context, entropy, hidden pack material, timestamp, path, provider
metadata, provider reference, or provider object. The public cursor exposes no
decoded mapping or generic mode/official discriminator and no hostile value in
its representation.

The service owns no durable cache, database, filesystem store, scheduler,
background refresh, or wall-clock expiry. The provider owns bounded in-process
fixture snapshot retention. A missing or stale cursor snapshot maps to the
same fixed unavailable error. Continuations must bind the exact immutable
snapshot, ChallengeKey, score-pack hash, and next offset; they cannot drift to
a later snapshot or another Challenge. The offset is absolute. A continuation
may use any otherwise valid page_size because page_size is not cursor-bound;
changing it cannot change the snapshot, order, tie relation, or rank. A cursor
is emitted only when next_offset is strictly before the snapshot end, never at
or beyond it.

An available empty snapshot produces a successful page with rows=(),
next_cursor=None, and the exact snapshot ChallengeKey, scoring_pack_hash, and
snapshot sequence. Provider None is unavailable and is never conflated with
that empty success. No page exposes a total count.

`max_response_utf8_bytes` is the exact logical public-response UTF-8 occurrence
budget for a candidate successful FixtureLeaderboardPage. It is evaluated only
after complete validation, ordering, competition ranking, pagination, and
optional cursor construction, but before any page, row tuple, or cursor is
released. It is not Python heap size, object size, repr length, JSON size,
field-name size, serialized wire size, HTTP response size, transport framing,
or a future network protocol. The exact formula is:

~~~text
response_utf8_bytes(page) =
    utf8(page.schema_version)
  + utf8(page.challenge_key.challenge_id)
  + utf8(page.challenge_key.version)
  + utf8(page.scoring_pack_hash)
  + sum(
        utf8(row.challenge_key.challenge_id)
      + utf8(row.challenge_key.version)
      + utf8(row.scoring_pack_hash)
      for row in page.rows
    )
  + (
        utf8(page.next_cursor.value)
        if page.next_cursor is not None
        else 0
    )

utf8(value) = len(value.encode("utf-8"))
~~~

The meter charges exactly those public string occurrences. It traverses the
candidate page in exact declared page-field order, page.rows in final tuple
order, and each row in exact declared row-field order. Equal strings are
charged once per public field occurrence; shared object identity and string
interning never deduplicate the charge. Every chargeable value is already
required to be an exact built-in ASCII str. After exact ASCII validation, the
implementation may use len(value) because each ASCII code point is one UTF-8
byte.

Every chargeable string occurrence other than the optional cursor separately
satisfies max_string_utf8_bytes before entering the total. When next_cursor is
present, its exact emitted ASCII value must separately satisfy both
max_cursor_utf8_bytes and max_string_utf8_bytes and is then charged exactly
once. An incoming request cursor is not a response occurrence. The decoded
private logical cursor fields are not charged again. The incoming cursor
remains subject to the existing request and cursor validation and limits.

The meter does not charge field names; nominal class/type names; tuple or
container structure; hypothetical serialization delimiters or punctuation;
rank, snapshot-sequence, publication-sequence, or cursor-offset integers except
as an offset is already encoded in next_cursor.value; overall_score floats;
Boolean fields; None; Python object overhead; repr or str output; provider-only
SubmissionId or result_id; private candidate fields; private cursor payload
fields separately; private provider objects; or hidden/forbidden values. A
syntactically malformed, subclassed, or non-ASCII provider-derived value is an
integration failure under A10-R3/A10-R13 and is never normalized for metering.

A candidate page is permitted when response_utf8_bytes(page) is less than or
equal to max_response_utf8_bytes. A total greater than the limit raises the
exact fixed LeaderboardResourceError before any success value escapes; no
partial page survives. Fixed public error codes and messages are constants,
not candidate successful pages, and are excluded from this meter. An available
empty page still charges schema_version, the page Challenge ID/version, and the
page scoring-pack hash, but no row string or cursor. Exact-at-limit succeeds;
one-byte-over fails. A resource failure never recursively constructs another
metered success response.

If a separately ratified future schema adds a public string field, that
ratification must explicitly update this formula before implementation. No
field enters the meter through reflection, generic serialization, dataclass
conversion, object introspection, or default-public behavior. This closed
occurrence-sum rule follows the bounded A9 logical-response-meter principle
without copying A9's larger graph/node model or adding an A9 dependency.

**A10-R12 — Fixed public error hierarchy.** The only future public hierarchy,
codes, and messages are:

~~~text
LeaderboardError(Exception)

LeaderboardRequestError(LeaderboardError)
    code: leaderboard.request.invalid
    message: Leaderboard request is invalid.

LeaderboardResourceError(LeaderboardError)
    code: leaderboard.resource.exhausted
    message: Leaderboard resource limit was exceeded.

LeaderboardUnavailableError(LeaderboardError)
    code: leaderboard.fixture.unavailable
    message: Fixture leaderboard is unavailable.

LeaderboardIntegrationError(LeaderboardError)
    code: leaderboard.integration.failed
    message: Leaderboard provider response is invalid.
~~~

Each of the four concrete public errors is a direct LeaderboardError subclass;
there is no intermediate error class.

Every instance uses its exact fixed code and message. Errors never echo user
or provider values, invoke hostile repr or str, or expose a cause/context
chain. A10 exposes no NotFound distinction or existence oracle. Absent, stale,
unpublished, and ineligible fixture-provider state reported without a returned
snapshot collapse to the same unavailable class. If a provider instead
returns a purported snapshot containing any such candidate, that snapshot is
malformed and fails the whole operation as the fixed integration class; A10
never silently filters it. A response_utf8_bytes(page) total greater than
max_response_utf8_bytes remains the fixed resource class and fails before any
page escapes. Fixed public error objects are excluded from successful-page
metering.

**A10-R13 — Hostile input, provider output, and mutation isolation.** Exact-type
and subclass rejection applies to ChallengeKey, both sequences, request,
cursor, snapshot, candidate, row, page, resource limits, and every nested
field/built-in value. It does not require the trusted concrete provider object
to subclass or be the Protocol, and A10 performs no runtime-checkable protocol
introspection. Missing/call-incompatible methods and malformed returns are
provider integration failures. Hostile descriptors, hooks, and call failures
map to integration only when they raise an ordinary Exception; a non-Exception
BaseException propagates unchanged under A10-R3. Provider output is hostile or
malformed until the entire bounded snapshot has been validated.

The constructor captures an immutable validated copy of the exact resource
limits. The service makes immutable positive copies of the exact allow-listed
values.
Caller/provider mutation before, during, or after a call must not alter a
validated returned page or retained cursor binding. No generic serializer may
traverse A5, A6, A7, or provider objects.

Bounded concurrent-call accounting releases its acquired permit in `finally`
on every service exit, including success, an A10-created public error, ordinary
Exception translation, and propagation of a non-Exception BaseException.

Seeds, draws, roles, domains, contexts, entropy, hidden pack material, margins,
stress values, diagnostics, fees, paths, private timestamps, hidden identity,
and every other non-allow-listed field are forbidden through rows, pages,
cursors, errors, caches, debug output, and representations.

**A10-R14 — Minimal dependency boundary.** The smallest recommended future
layout is:

~~~text
carbon/leaderboard/
    __init__.py
    model.py
    providers.py
    service.py
~~~

Allowed imports are exactly the Python standard library plus:

~~~python
from carbon.registry import (
    ChallengeKey,
    is_sha256_digest,
    validate_version,
)
from carbon.scoring import ScoreStatus
from carbon.fees import SubmissionId
~~~

Forbidden imports include A5 InternalResult or ScoreEngine; A6 EvaluationCard
as an input, CardStore, or private records; A7 private store, private records,
or enumeration; A8
execution objects; A9 service, providers, estimates, priors, scaffolds, mock
outputs, or result models; Landscape; emission or chain packages; Bittensor;
optional scientific dependencies; web or HTML frameworks; and filesystem,
environment, or current-time modules.

A10 preserves zero mandatory package dependencies and must import from an
installed wheel outside the checkout. The provider-integration identifiers do
not authorize private-store access from A10.

**A10-R15 — Future test and acceptance contract, not current evidence.** The
canonical future focused test path is tests/cpu/test_leaderboard.py. This
documentation candidate creates or changes no test and runs no implementation
test as evidence.

The future implementation must prove the exact ordered root exports, exact
constructor and resource-limit fields, exact nominal fields/u64 bounds, exact
schema literals, Protocol/concrete-provider distinction, provider None
unavailability, ordinary-Exception integration collapse, non-Exception
BaseException propagation, and empty-snapshot success. It must prove
RuntimeError translation, provider-raised public A10 error translation into a
new exact integration error, preservation of A10-created public-error mappings,
no exception text/value/payload/cause/context leakage, unchanged
KeyboardInterrupt/SystemExit propagation, unchanged
GeneratorExit propagation where practical, no `except BaseException` in A10
source, and concurrency-capacity release after translated Exception and
propagated non-Exception BaseException. It must also prove
public-validator/constructor reuse, canonical-zero
rejection, whole-snapshot validation/ranking before slicing, continuation
page_size variation, no end cursor, hostile-input and subclass rejection,
stable error inheritance/codes/messages/chains, exact Challenge and score-pack
isolation, closed eligibility, fixture/official separation, deterministic
descending order, competition ties, duplicate rejection, bounded pagination
and cursor binding, snapshot mutation isolation, no existence oracle, complete
leakage exclusions, and no private A5--A9 access.

It must prove the exact response_utf8_bytes(page) formula and explicit
chargeable/uncharged field manifests; declared page-field, final row-tuple, and
declared row-field traversal order; per-occurrence charging for equal or
identity-shared strings; per-string and dual cursor limits; exactly-once emitted
cursor charging without private-payload duplication; incoming-cursor exclusion;
empty-page accounting; exact-at-limit success; one-byte-over resource failure;
fixed-error exclusion; and no partial response. Source tests must lock the
explicit field manifest and forbid repr, generic serialization, dataclass
conversion, JSON, HTTP, REST, GraphQL, wire-format, or network dependencies in
the accounting path.

It must also prove no optional-heavy, web, HTML, filesystem, current-time,
Landscape, neuron, Bittensor, chain, weight, or emission dependency; installed
wheel import; full CPU regression; Ruff; Black; and no new quality debt. Every
implementation DoD box remains unchecked until separate implementation,
tests, independent review, explicit human authorization, and merge produce
actual evidence.

**A10-R16 — Explicit deferrals and fail-closed production boundary.** This
contract does not ratify or implement a production publication feed, official
or LIVE leaderboard, public identity, anonymization, timestamps, official
score precision/cadence, frontier nomination or promotion, FrontierRecord,
FrontierAdvanceEvent, Product Qualification, commercial rank, settlement,
chain, weights, emissions, A11 logging/metrics, or A12 aggregate invariants.

No fixture row or page is official, LIVE, emission-eligible, frontier evidence,
Product Qualification, commercial ranking, settlement authority, chain input,
weight input, or emission authority. Without separately ratified and qualified
production components, production remains unavailable and fail closed.

**A10-R17 — Ratification and sequencing gate.** These decisions become current
repository authority only after PR #36 receives independent
review, fresh explicit human authorization, and normal merge. Draft
publication is not ratification, implementation, testing, readiness, or merge
authorization.

A10 remains todo in .agent/WAVE.md and no implementation box is checked.
A11 remains todo. A12 remains todo. Both are untouched. A later A10
implementation must begin in a separate bounded task/branch after merge and
fresh orientation; it may not
infer any deferred official, identity, security, frontier, commercial,
network, chain, weight, or emission policy from this fixture-only contract.

## 2026-08-24 — A9 bounded Miner MCP Wave-A control-plane contract candidate

**Repository truth, status, and scope.** A fresh fetch/prune resolved
`origin/main` to exact commit
`adcf0578052bba2c0cf9aa24e7a07ebfe87ca46d`, tree
`c41119356ce811b2186a19dd2906e29e443fecf2`, and subject `Merge pull request
#31 from carbonphysicsai/agent/a8-closeout`. Its ordered parents are
`b30c3f5fc2a53df0611d5e8b80120fbf4b64531c` and exact PR head
`7ab627f027675960622c2e147095ce92822f15c2`. The second-parent and merge trees
are exactly equal and their diff is empty. Exact push run `32690165406` is
`completed / success` on that head; both CPU and quality jobs succeeded, with
`1584 passed in 40.72s`, `Ruff 757/776; Black 62/68`, removed debt `Ruff 19,
Black 6`, zero changed Python files, and no new debt.

GitHub exposes no formal PR #31 review objects, review comments, issue
comments, or non-empty review decision. The exact PR-head/second-parent/tree
relationship is verified; this record does not fabricate a formal GitHub
review event that the API does not report.

A8 is `done` with twenty-five checked and zero unchecked bounded criteria.
A9--A12 remain `todo`. All pull requests, remote refs/unmerged commits, and
current source were searched for A9/MCP/prior/scaffold/estimate/light/mock and
submission-transport work. No competing A9 branch, PR, implementation, test,
plan, or ratification candidate exists. The starting worktree was clean;
`carbon/mcp/__init__.py` was only the A0 marker. Legacy miner/client/HTTP and
prior/Landscape material is archaeology, not an existing A9 implementation.

This seven-path documentation candidate adds the A9 plan and reconciles the
decision log, ticket, Miner MCP domain spec, Build Out sequencing, and both
current maturity ledgers. It changes no `.agent/WAVE.md`, Python, test,
fixture, dependency, lockfile, packaging, CI, quality baseline, A0--A8 code or
test, A10+ ticket/implementation, business, or publication file. It implements
and tests nothing.

```text
A9 EXACT BOUNDED CONTRACT: specified and ratified only after independent
review, explicit human authorization, and merge of this candidate
A9 IMPLEMENTED: NO
A9 TESTED: NO
A9 SCIENTIFICALLY_QUALIFIED: NO
A9 SECURITY_QUALIFIED: NO
A9 NETWORK_QUALIFIED: NO
A9 COMMERCIALLY_VALIDATED: NO
A9 PRODUCTION_QUALIFIED: NO
A9 WAVE STATUS: todo
A10--A12: todo
```

**Conflict classification.** Current A2--A8 owner APIs, the constitution,
invariants, constitutional overlay, and A8-R15 are `NO_CONFLICT`. The flat ten-tool
Miner MCP table, stale A9 aliases/dependencies/test path, rich Challenge-info
fields, executable-scaffold language, queue/fee receipt shorthand, and coupled
`estimate/light` wording in Build Out/A9 prose are `DOCUMENTATION_LAG`.
A8-R15 remains semantically binding: it blocks execution-dependent
estimate/light work until a separate mock contract exists. It does not block
the distinct, non-executing structural estimate below. Legacy miner,
agent-tools, client, neuron, HTTP, prior-publisher,
Landscape, and old Strategy-schema code is `REPLACE/EXCLUDE` as A9 authority.
Actual publications, policies, authentication, mock execution, and security
evidence remain owner inputs; fail-closed absence means no unresolved owner
decision blocks this bounded contract.

**A9-R1 — Bounded ownership and Wave split.** Wave-A A9 owns only an in-process
control/disclosure boundary: exact Challenge information, public prior/scaffold
provider seams, exact A2 dry validation, a pure structural/prior estimate,
exact A7 submission intake/status/publication delegation, result-poll query
budget, stable errors, resource capture, and positive public projections.

Wave A registers exactly, in order:

```text
get_challenge_info
get_prior
get_mock_scaffold
dry_validate
estimate
submit
get_submission_result
```

No `info`, `prior`, `scaffold`, `validate_strategy`, `submit_strategy`, or
other alias is registered. `light_compare`, `light_train`, and
`list_my_submissions` are unavailable and excluded from Wave A.

The exact future `MockExecutionRequest`, `MockRunOutcome`,
`MockTrainEvalService.run_mock`, mock pack identity, mock resource/isolation
policy, mock execution/disclosure, `light_compare`, `light_train`, and
adaptive-query security evidence remain one deferred Wave-B A8/A9 contract.
That mock outcome is not A5 `InternalResult`, cannot enter A7/A6, creates no
card, and affects no fee, official score, rank, weight, or emission.

**A9-R2 — Exact service and owner delegation.** The only future public service
is:

```text
McpService(
    registry: exact ChallengeRegistry,
    submission_service: exact SubmissionService,
    resource_limits: exact McpResourceLimits,
    query_budget_gate: QueryBudgetGate,
    prior_provider: PriorProvider | None,
    scaffold_provider: ScaffoldProvider | None,
    estimate_provider: EstimateProvider | None
)

McpService.call(
    call: exact McpCall,
    requester_identity: exact out-of-band RequesterIdentity
) -> (
    ChallengeInfo | PublishedPrior | PublishedScaffold |
    DryValidateResponse | StructuralEstimate | SubmitReceipt |
    SubmissionResult
)
```

Every constructor slot is explicit and required. `None` in any provider slot
selects stable fail-closed unavailability; there is no default/global provider,
registry, A7 service, query gate, resource policy, or server. The exact
tool-to-response mapping is `ChallengeInfo`, `PublishedPrior`,
`PublishedScaffold`, `DryValidateResponse`, `StructuralEstimate`,
`SubmitReceipt`, and `SubmissionResult`, respectively. No raw mapping,
iterator, stream, or network response is returned.

Trusted composition must supply the same exact `ChallengeRegistry` instance
used to construct the injected `SubmissionService`. A9 does not inspect A7's
private registry and cannot repair a mismatched composition. Successful calls
return only the closed union above; failures raise exactly one of the seven
fixed public A9 errors.

A9 may use only current public A2, A3, A6 model, and A7 APIs. A9 does not own
or repeat A2 schema logic; A3 record/admission truth; A6 storage/projection;
A7 identity, lifecycle, fee/retry/cancel/execution/publication; A8 context,
backend, execution or scoring; or A10+ behavior.

**A9-R3 — Exact call schema, ordered fields, and requests.** `McpTool` is the
exact closed string enum corresponding to the seven R1 names. The first
untrusted boundary is never a raw dictionary:

```text
McpField(name: exact built-in str, value: object)
McpCall(
    schema_version: exact built-in str,
    tool: exact built-in str,
    fields: exact tuple[McpField, ...]
)
```

`McpField` and `McpCall` are storage-only raw-envelope nominals. Construction
freezes the supplied references but intentionally performs no eager type,
schema, field-name, duplicate, resource, or semantic validation. An exact
outer call can therefore carry malformed internal framing into
`McpService.call` without object forging; the service alone owns exact outer
checks, concurrency admission, framing, and capture order.

The raw tool stays an exact string so unknown, alias, and deferred names can
map to stable tool-unavailable. Ordered fields remain intact through
structural/name/duplicate/resource validation and exact tool dispatch; only a
known tool then receives missing/unknown semantic-field validation. A unique
field map may be constructed only after those checks. Exact call and every
top-level response schema version is `"1.0"`; no default, alias, normalization,
or negotiation exists.

Wire fields are exact: Challenge info/prior require `challenge_id` and
`challenge_version`; scaffold adds optional `scaffold_id`; dry validation
requires `strategy`; estimate and submit require `challenge_id`,
`challenge_version`, and `strategy`; result retrieval requires
`submission_id`. No call may contain RequesterIdentity.

Exact frozen/slotted decoded types are:

```text
GetChallengeInfoRequest(exact ChallengeKey)
GetPriorRequest(exact ChallengeKey)
GetMockScaffoldRequest(exact ChallengeKey, exact str | None)
DryValidateRequest(fresh owned supported exact-built-in graph)
EstimateRequest(exact ChallengeKey, fresh owned supported exact-built-in graph)
SubmitRequest(exact ChallengeKey, fresh owned supported exact-built-in graph)
GetSubmissionResultRequest(exact SubmissionId)
```

Estimate capture accepts the same freshly owned resource-admissible supported
exact-built-in graph as dry validation and submit; A9 does not independently
require a dictionary root. After both required providers, exact public
Challenge visibility, and the exact public prior succeed, every such estimate
graph reaches exact A2 once. A2-invalid graphs take only the A9-owned R8
response path; only an exact A2-valid dictionary can reach the estimate
provider. Every resource-admissible decoded submit graph reaches exact A7 after
the receipt resource preflight in A9-R10. Dry validation accepts every
resource-admissible captured root. Transport-inexpressible types fail at A9
rather than being relabelled as A2/A7 science or lifecycle behavior.

**A9-R4 — Mandatory resource policy and ownership.** Exact frozen/slotted,
non-defaulted `McpResourceLimits` has these positive finite integer fields:

```text
max_call_fields
max_total_request_value_nodes
max_request_object_members
max_request_list_items
max_request_string_utf8_bytes
max_request_object_key_utf8_bytes
max_request_integer_bits
max_total_request_utf8_bytes
max_total_response_value_nodes
max_response_sequence_items
max_response_string_utf8_bytes
max_response_integer_bits
max_total_response_utf8_bytes
max_concurrent_calls
```

Every field is an exact built-in positive unsigned-64-bit-representable int.
No numeric value is ratified. No query count, fee, quota, rolling window, rate,
retry delay, or retry-after is hidden in this model.

Capture is iterative/non-recursive and accepts only exact built-in `None`,
`bool`, `int`, finite `float`, `str`, `list`, and `dict`. Dict keys may be
exact built-in scalars so A2/A7 retain non-string-key rejection authority;
MCP field names remain exact strings. Capture rejects subclasses, tuple/set
containers, arbitrary mappings/iterables, unstable containers, non-finite
numbers, and hostile objects without rendering them. It creates a detached
built-in graph while preserving shared references and cycles so owner
semantics are not normalized. Visited-node accounting remains bounded.

Responses are fresh bounded positive projections. Frozen/slotted wrappers do
not pretend nested Python dict/list graphs are deeply immutable or authenticated.
A9 retains no external caller or provider alias while preserving valid
internal graph topology in the detached projection.

Resource accounting is exact. Only exact top-level `McpCall` and requester
type checks precede concurrency admission; wrong/subclassed outer values are
request errors without attribute access. Every exact-top-level call then
acquires one permit before framing/tool/field/value/provider/owner work,
including internally malformed and unknown-tool calls, and holds it through
response projection/error translation with `finally` release. Inside the
permit, exact schema/tool types and the fields-tuple type are checked first;
`len(fields)` is then bounded by `max_call_fields` before any entry scan.
Schema/tool strings are metered before use, after which the schema value must
equal exact `"1.0"`. Each bounded tuple entry is checked in order for exact
`McpField` type, exact string name, name UTF-8 meters, and only then duplicate
identity, so no unbounded scan or overlong-string hash/equality occurs. An
exact-string unknown/deferred tool is then unavailable without a semantic
field schema, value capture, or a downstream call.
Missing/unknown semantic field names are checked only for a known tool before
its values are captured.

Each call-field value root is one request node. On first expansion of each
distinct exact list/dict, each list item or dict member value adds one node;
alias/cycle edges are charged by their containing cardinality, but a seen
container's children are not expanded twice. Dict keys are not nodes.
Object/list limits apply per first-seen container. Exact
`int.bit_length(value)` applies to every exact int occurrence, including scalar
keys and excluding bool. Per-string request width covers schema/tool/field
names, graph strings, and string keys; the key limit additionally covers each
string dict key; the total UTF-8 meter sums logical occurrences. A strict
code-point scan charges a surrogate one byte solely to stay bounded and marks
the request invalid; a resource breach encountered first remains resource.

Response accounting starts with one top-level node and adds one for every
nominal field, sequence item, and dict member value on first container
expansion; dict keys are not nodes. Only exact closed A9/owner nominals/enums
and exact permitted `None`/bool/int/finite-float/string/tuple/list/dict field
values are traversable; any other type/subclass is integration failure. The
sequence limit applies per exact tuple/list, response string width covers
string values and dict keys, response
integer width is exact `int.bit_length` for every exact int value or scalar
dict key, excluding bool, and total response UTF-8 is the logical-occurrence
sum. Each exact string enum is one value node and its exact `.value` is charged
as a response string. The same bounded one-byte surrogate handling marks
response text invalid. A response dict must fit the remaining node meter
before copy. Response-meter breach is resource; within the meters,
malformed/subclassed/unstable/invalid-UTF-8/cross-bound provider output is
integration. Traversal uses exact call-field-tuple, list/tuple-index, built-in
dict-insertion, declared nominal-field, and provider-sequence order; the first
condition encountered controls.

**A9-R5 — Exact Challenge projection and visibility.** `ChallengeInfo` has
response framing `schema_version="1.0"` and exactly five Challenge fields:

```text
challenge_key
lifecycle_status
fixture_origin
effectively_live
allowed_backbones
```

Lookup is exact-key only; A9 never scans/lists records. A loaded `draft` record
is unavailable and maps to `McpChallengeUnavailableError`. A `fixture` record
is visible only when the exact loaded record has exact lifecycle status
`fixture`, `fixture_origin is True`, and exact A3
`ChallengeRegistry.assess_live_eligibility(challenge_id, version,
fixture_mode=True).eligible is True`; its `effectively_live` is exact `False`.
A false fixture assessment is unavailable without exposing its reasons. A
`live` record is visible and obtains `effectively_live` only from exact A3
`is_effectively_live(challenge_id, version)`, including visible `live/False`
when revalidation fails. Successful `lifecycle_status` is therefore exact
`fixture` or `live`. `fixture_origin` and `allowed_backbones` are copied facts,
not provenance authentication, scientific qualification, runtime support, or
admission. Missing, malformed, internally inconsistent (including an
inconsistent fixture), or unknown-lifecycle records are unavailable.

No artifact path/digest, qualification reference/evidence/reason, backend-
profile evidence, receipt evidence, fee, Score Pack/generator hash, active mock
pack, mock range, tag/disclosure catalog, seed, or context is exposed.

**A9-R6 — Exact prior model and provider.** Exact frozen/slotted identity and
directive values are:

```text
PriorRef(
    challenge_key: exact ChallengeKey,
    prior_id: exact canonical token,
    prior_version: exact version token,
    content_hash: exact tagged lowercase SHA-256
)

PriorDirectiveKind =
    STRUCTURAL_STEER="structural_steer" |
    AVOID="avoid" |
    EXPLORE="explore" |
    NOT_INCLUDED="not_included"

PriorDirective(
    kind: exact PriorDirectiveKind,
    subject: exact bounded canonical token,
    tokens: exact tuple[bounded canonical token, ...]
)

PublishedPrior(
    schema_version="1.0",
    prior_ref: exact PriorRef,
    directives: exact provider-ordered duplicate-free
                tuple[PriorDirective, ...]
)
```

Every `canonical token` is an exact built-in `str` accepted without
normalization by public A3
`validate_canonical_identifier(value, field_name)`; the applicable MCP string
and aggregate UTF-8 limits bound it. Every `version token` is an exact built-in
`str` accepted without normalization by public A3 `validate_version`.

Subject/tokens are closed publication-vocabulary identifiers, never free
text, numbers, weights, parameter values, or executable instructions. Actual
vocabulary/content remains an owner input. The hash is provider-owned
publication identity; A9 validates exact digest syntax/cross-binding but does
not invent canonical publisher bytes or a store.

A prior is coarse, public, versioned, hashed, non-executable, non-binding,
one-channel, and closed-directive-only. It has no Strategy, free text, numeric
weight vector, hyperparameter recipe, champion identity/weights, official
score, rank, fee, seed, pack identity, or emission field.

```text
PriorProvider.get_prior(ChallengeKey) -> PublishedPrior
```

The provider receives no requester. The service checks provider presence
before A3 visibility and provider invocation. Absence is stable
tool-unavailable. Exceptions or malformed, subclassed, unstable, or
cross-bound output within response meters are stable integration failure;
response-meter breach is stable resource failure. A9 adds no production
provider or prior publication.

**A9-R7 — Exact declarative scaffold.** Exact frozen/slotted values are:

```text
ScaffoldRef(
    challenge_key: exact ChallengeKey,
    scaffold_id: exact canonical token,
    scaffold_version: exact version token,
    content_hash: exact tagged lowercase SHA-256
)

PublishedScaffold(
    schema_version="1.0",
    scaffold_ref: exact ScaffoldRef,
    strategy: fresh owned exact built-in A2-valid Strategy,
    informed_by_prior: exact PriorRef | None,
    execution_deferred: exact True
)

ScaffoldProvider.get_scaffold(
    ChallengeKey,
    scaffold_id: exact canonical str | None
) -> PublishedScaffold
```

The Strategy `challenge_id` must equal the exact ChallengeKey challenge ID.
Optional prior metadata must bind the same ChallengeKey. A9 validates/copies
but never supplies a body, calls the prior provider, fills a prior omission,
derives from a prior, interprets inert A2 parameters, calls A8, or claims the
scaffold scientifically valid, Challenge-compatible, mediocre, or non-champion
from type checks. Execution is deferred throughout Wave A.

The service checks scaffold-provider presence before A3 visibility and calls
the provider once. It then calls canonical `carbon.schema.dry_validate`
exactly once on the detached returned Strategy and requires exact `ok=True`;
non-`ok` is malformed provider output and maps to integration failure. If the
request supplies `scaffold_id`, exact equality with
`PublishedScaffold.scaffold_ref.scaffold_id` is mandatory; without a selector,
the provider owns selection of the returned canonical ID. Positive
reconstruction detaches provider ownership while preserving valid internal
graph topology.

**A9-R8 — Exact pure structural estimate and A8-R15 reconciliation.** Exact
frozen/slotted output is:

```text
StructuralEstimate(
    schema_version="1.0",
    challenge_key: exact ChallengeKey,
    prior_ref: exact PriorRef,
    validation: exact owned A2 ValidationResult,
    applicable_directives: exact tuple[PriorDirective, ...],
    disclaimer="non_binding_structural_prior_only"
)
```

Applicable directives are an order-preserving duplicate-free subset of the
exact public prior and there is no arbitrary text field. The handler first
checks both provider slots, then resolves the exact Challenge record,
obtains/validates the public prior, and calls public
`carbon.schema.dry_validate` exactly once on the fresh owned supported graph.

When the exact owned A2 result has `ok=False`, the provider is not called. A9
returns its own bounded `StructuralEstimate` with the exact ChallengeKey,
exact public `PriorRef`, exact owned A2 result, exact empty
`applicable_directives=()`, and exact disclaimer
`"non_binding_structural_prior_only"`. It performs no execution or additional
structural interpretation on this path.

If and only if the exact A2 result has `ok=True`, the Strategy is an exact
A2-valid dictionary and A9 calls the estimate provider exactly once:

```text
EstimateProvider.estimate(
    ChallengeKey,
    PublishedPrior,
    owned exact A2-valid Strategy dict,
    exact ValidationResult with ok=True
) -> StructuralEstimate
```

The provider never receives a non-object, A2-invalid, cyclic, invalid-key, or
invalid-value Strategy, or a ValidationResult with `ok=False`. Its positive
output must preserve the exact `ok=True` result, ChallengeKey, PriorRef,
directive-subset order, disclaimer, response bounds, and every existing
non-execution/non-oracle rule. Missing prior or estimate provider is
unavailable before A2.

The provider uses only declarative structure, validation, and public prior. It
performs no execution; uses no MockContext; calls no A8; uses no fixture-
official context, official or fixture Score Pack; constructs no ScoreInput or
InternalResult; and returns no float quality score, predicted official score,
rank, predicted card status, predicted gate result, weight, or emission value.
A8-R15 therefore continues to block all execution-dependent estimate/light
work while permitting only this separately ratified structural estimate.

**A9-R9 — Exact A2 dry validation.** `DryValidateResponse` contains only
`schema_version="1.0"` and a fresh exact A2 `ValidationResult`. A9 calls public
`carbon.schema.dry_validate` exactly once on the captured graph and preserves
exact `ok`, ordered issues, codes, paths, and fixed messages. It adds no
normalization, challenge lookup, provider, admission, execution, score, or
status. An A2-invalid value is a successful validation response, not an MCP
error, when it passed A9 transport/resource capture.

**A9-R10 — Exact A7 submit intake and acknowledgement.** Trusted composition
supplies exact RequesterIdentity out of band. After its non-mutating resource
preflight, submit's only owner calls are:

```text
submission_id = SubmissionService.submit(
    exact RequesterIdentity,
    exact ChallengeKey,
    fresh owned request Strategy value
)
status = SubmissionService.get_status(
    exact SubmissionId,
    exact RequesterIdentity
)
SubmitReceipt(schema_version="1.0", status=exact SubmissionStatusView)
```

The receipt is an A7 lifecycle acknowledgement, never proof of queueing,
acceptance, payment, provenance, execution, official score, scientific
validity, rank, weight, or emission. A9 performs no preliminary A2/A3
admission and never calls `mark_validated`, admission, fee-start, retry,
cancellation, execution, completion, publication, or A6 storage methods.

Before any A7 method, A9 preflights the maximum valid canonical receipt against
all response meters. The finite envelope is derived only from its closed
nominal topology, `"1.0"`, the fixed 36-byte UUIDv4 SubmissionId, and the
longest closed SubmissionState value. It mints no ID and reads no owner state.
If every canonical receipt cannot fit, A9 raises resource before mutation; a
well-formed post-submit canonical status therefore cannot fail a response
meter.

Resource-admissible invalid input reaches A7 and preserves exact `REJECTED`
when A7 retained-record capacity permits; valid accepted intake begins exact
`RECEIVED` when that capacity permits. Accepted open duplicates retain A7's
exact same-SubmissionId/no-new-record/transition/fee semantics. Terminal and
rejected resubmission behavior remains A7-owned. A failure in the status read
or projection after submit—including not-found/authorization for the internally
returned ID/requester pair—is a stable integration error; A9 performs no retry
or compensation. That trusted-integration case is distinct from response
capacity, which the preflight rejects before mutation. Submission-unavailable
collapse is reserved for the caller-supplied ID in result polling.

**A9-R11 — Exact result polling and A7-mediated A6 card.** Exact output is:

```text
SubmissionResult(
    schema_version="1.0",
    status: exact SubmissionStatusView,
    card: exact EvaluationCard | None
)
```

Every structurally valid poll first calls
`QueryBudgetGate.consume(exact RequesterIdentity,
McpTool.GET_SUBMISSION_RESULT)` after request/resource validation and before
any A7 lookup. Then it calls `SubmissionService.get_status` first. Only exact
`SubmissionState.PUBLISHED` permits `SubmissionService.read_published`; every
other current A7 state returns exact status with no card. A9 never reaches A6
directly. Not-found and wrong-requester A7 errors collapse to the same public
submission-unavailable error.

The response contains no StrategyHash, private stored ChallengeKey, attempt
history, fee record, retry count, execution handle, SeedPin, environment pin,
private failure cause, InternalResult, A6/A7 record, fine score detail, margin,
stress breakdown, private/free-form diagnostic content, or timestamp not
supplied by an owner API. The exact A6 `public_diagnostics` field remains
present and canonically empty. There is no retry-after, queue position, or
completion-time estimate.

**A9-R12 — Requester/authentication and query gate.** RequesterIdentity is not
an MCP field. The service exact-type checks and reconstructs it before passing
it to the query gate/A7. Current A7 RequesterIdentity supplies structural
equality and requester binding only; it is not authentication, hotkey proof,
signature verification, session authority, or a network capability. A future
network adapter must authenticate before trusted composition supplies it.

```text
QueryBudgetGate.consume(RequesterIdentity, McpTool) -> None
```

Wave A mandates this gate for every result poll. It sets no query budget,
quota, rate, window, or retry policy. An exact gate-raised
`McpQueryBudgetError` is translated without chaining to a fresh public
`McpQueryBudgetError` containing only the fixed literals; any other gate
failure is an integration failure. The service captures the protocol return,
requires it to be exact `None`, and treats any other value as an integration
failure before any A7 lookup. Once exact consume succeeds, no later outcome is
refunded, including unavailable/nonterminal status or a response-meter,
projection, or integration failure.

**A9-R13 — Stable errors, retention, and replay.** Every error is a distinct
exact nominal, slot-declared exception type with a frozen public contract
payload: zero-argument construction, literal-backed read-only
code/message/argument values, and no supported diagnostic fields. Public
translation constructs no subclass and suppresses chaining. The immutability
claim excludes interpreter-owned `BaseException` runtime traceback, context,
cause, and inherited implementation-dictionary state:

```text
McpRequestError
  mcp.request.invalid / MCP request is invalid.
McpResourceError
  mcp.resource_limit_exceeded / MCP resource limit was exceeded.
McpToolUnavailableError
  mcp.tool_unavailable / MCP tool is unavailable.
McpChallengeUnavailableError
  mcp.challenge_unavailable / Challenge is unavailable.
McpSubmissionUnavailableError
  mcp.submission_unavailable / Submission is unavailable.
McpQueryBudgetError
  mcp.query_budget_exceeded / MCP query budget was exceeded.
McpIntegrationError
  mcp.integration_failure / MCP integration failed.
```

No error renders an untrusted value, object, provider/owner exception, path,
secret, seed, context, pack, private state, configured limit, observed size,
quota, stack, or exception object. Unknown/alias/deferred tool and missing
tool-specific provider map to unavailable; malformed calls map to request;
invalid boundary challenge/version/scaffold/submission/requester scalar syntax
also maps to request; and limit/capacity exhaustion maps to resource. A
syntactically valid missing/malformed Challenge, draft record, inconsistent
fixture, unknown lifecycle, or other internally inconsistent Challenge maps to
Challenge unavailable; A7 not-found/authorization during
`get_submission_result` maps to submission unavailable; all other trusted
integration/output failures map to integration failure.

Only a wrong/subclassed outer call or requester is rejected before concurrency
admission. Every exact-top-level call acquires a permit before all remaining
validation; concurrency exhaustion is therefore resource before an internal
framing/tool/field condition. Within an admitted call, request and response
meter breaches are resource, including valid-shaped provider output that
exceeds response bounds.

A9 retains zero request, response, provider, result, or polling history/cache
and creates no second submission store. Provider publications remain
versioned/provider-owned. A7 alone retains its current process-local state and
idempotence. Transient concurrency accounting and mandatory query consume are
not a history store.

**A9-R14 — Exact modules, exports, and future tests.** The only future A9
layout is:

```text
carbon/mcp/
    __init__.py
    model.py
    providers.py
    service.py
```

A9 may source-import standard library plus minimum public A2, A3, A6 model,
and A7 APIs. It must not source-import A4 context/secret types, A5 models or
engine, A6 stores, A7 stores, A8, A10--A12, legacy miner/Landscape, PoC,
neurons, MCP SDKs, HTTP frameworks, Bittensor, Torch, JAX, NumPy, or optional-
heavy dependencies. No network server exists.

Future `carbon.mcp.__all__` is exactly the ordered surface recorded in
`.agent/plans/A9_mcp_skeleton.md`: all ratified A9 nominal types and errors,
the four provider/gate protocols, and `McpService`; it contains no alias and
re-exports no A2--A8 owner type.

The sole canonical focused test is `tests/cpu/test_mcp_skeleton.py`. Its
future matrix covers exact types/subclass rejection; fields/duplicates/schema;
resource/capture/concurrency/response bounds; hostile rendering and stable
errors; exact A2 delegation and positive result reconstruction in standalone
`DryValidateResponse`; exact A2 delegation inside `StructuralEstimate` for
resource-admissible supported exact-built-in non-object roots and invalid-
field/key/value/cyclic estimate graphs; zero estimate-provider calls and empty
directives for every captured A2-invalid graph; one provider call only for
exact A2-valid Strategy; A3 draft unavailability,
fixture visibility only with exact `fixture_origin is True` and exact true A3
fixture assessment, loadable-but-false fixture-assessment unavailability,
effective-live true/false, and no enumeration; provider
absence/malformed output; prior/scaffold leakage and deferred execution;
structural estimate and light rejection; fixture/mock/official crossing; A7
submit/idempotence/no duplicate lifecycle or fee; requester-bound polling/all
states/query ordering; published-only exact A6 card; authorization/not-found
collapse; private-data exclusions; retention; source/root/import isolation;
installed wheel; full CPU; Ruff/Black/no debt.
Documentation and existing regressions are not A9 test evidence.

**A9-R15 — Implementation and maturity gate.** No A9 source/test work may begin
until this exact candidate is independently reviewed, explicitly human-
authorized, and merged. A separate task must re-fetch the merge, verify exact
main/tree/status/CI and no competing A9 work, and only then mark A9
`in_progress`. This candidate leaves every A9 implementation criterion
unchecked and A9/A10/A11/A12 `todo`.

No provider publication, prior content/vocabulary, scaffold body, resource
value, query/fee/quota/concurrency/rate value, authentication, network server,
mock pack, mock/light execution, real training, production context/backend,
LIVE science/Score Pack, adaptive-query qualification, evidence/receipt/
signature, leaderboard/logging/invariant implementation, frontier, Product
Qualification, treasury/settlement, Bittensor/chain, weight, emission,
scientific qualification, security qualification, network qualification,
commercial validation, or production qualification is included.

## 2026-08-25 — A9 ratification, bounded implementation, test-proof repair, and administrative closeout candidate

**Conditional closeout authority.** This documentation-only record preserves
and does not renumber, weaken, or reinterpret A9-R1 through A9-R15. It records
the independently audited A9 evidence and proposes the bounded A9 status as
`done`; that status becomes repository authority only after independent review
of this closeout candidate, explicit human authorization, and its normal merge.
It authorizes no A10 work.

**Ratification topology.** PR #32 began with candidate
`9d80d33dbe6fa4b07d303d50b6b9d16b18f29a3e`, tree
`f6038050441b76089500efb2be381332209ab1fe`, subject `docs: ratify bounded A9
MCP control-plane contract`, and sole parent
`adcf0578052bba2c0cf9aa24e7a07ebfe87ca46d`; its sequential delta was seven
files, `+2499/-429`. Repair `6be14bf2400985f805906a74d987deadf321be54`,
tree `4f55d28d06ef6f06cf521fd8f04bbf3881e58379`, subject `docs: repair A9
validation and visibility contract`, has sole parent `9d80d33...` and a
five-file sequential delta of `+214/-92`. PR #32 merged normally as
`47a62b2397b4125bb608eb69bf0e3dc6360c519d`, with ordered parents
`adcf0578052bba2c0cf9aa24e7a07ebfe87ca46d` and exact reviewed head
`6be14bf2400985f805906a74d987deadf321be54`. Its tree is
`4f55d28d06ef6f06cf521fd8f04bbf3881e58379`, exactly equal to the reviewed-head
tree, and the reviewed-head-to-merge diff is empty. The exact first-parent
manifest is modified `.agent/DECISIONS.md`; added
`.agent/plans/A9_mcp_skeleton.md`; modified
`.agent/tickets/A9_mcp_skeleton.md`, `Design_Specs/Build_Out.md`,
`Design_Specs/Miner_MCP.md`,
`docs/context/IMPLEMENTED_VS_SPECIFIED_CURRENT.md`, and
`docs/context/Implemented_vs_Specified`: seven files, `+2620/-428`. That
human-authorized merge ratified A9-R1 through A9-R15.

**Implementation topology and exact public surface.** Original implementation
`c9c324d1192c9c52009b15970e371d076a0b3e89`, tree
`46e8a2d96e15f8bec58e3fb7b9fd28f0684f00b6`, subject `feat: implement bounded
A9 MCP control plane`, has sole parent the exact ratification merge
`47a62b2397b4125bb608eb69bf0e3dc6360c519d`. PR #33 merged it normally as
`97d835f495cb7e3f194364cb4e674e2416531936`, with ordered parents
`47a62b2397b4125bb608eb69bf0e3dc6360c519d` and exact reviewed head
`c9c324d1192c9c52009b15970e371d076a0b3e89`; reviewed-head and merge trees are both
`46e8a2d96e15f8bec58e3fb7b9fd28f0684f00b6`, and their diff is empty. Its exact
first-parent manifest is modified `.agent/WAVE.md` and
`carbon/mcp/__init__.py`; added `carbon/mcp/model.py`,
`carbon/mcp/providers.py`, `carbon/mcp/service.py`, and
`tests/cpu/test_mcp_skeleton.py`: six files, `+5407/-3`.

The bounded service registers exactly seven tools: `get_challenge_info`,
`get_prior`, `get_mock_scaffold`, `dry_validate`, `estimate`, `submit`, and
`get_submission_result`. `carbon.mcp.__all__` contains exactly 34 ordered
exports: `ChallengeInfo`, `DryValidateRequest`, `DryValidateResponse`,
`EstimateProvider`, `EstimateRequest`, `GetChallengeInfoRequest`,
`GetMockScaffoldRequest`, `GetPriorRequest`, `GetSubmissionResultRequest`,
`McpCall`, `McpChallengeUnavailableError`, `McpField`, `McpIntegrationError`,
`McpQueryBudgetError`, `McpRequestError`, `McpResourceError`,
`McpResourceLimits`, `McpService`, `McpSubmissionUnavailableError`, `McpTool`,
`McpToolUnavailableError`, `PriorDirective`, `PriorDirectiveKind`,
`PriorProvider`, `PriorRef`, `PublishedPrior`, `PublishedScaffold`,
`QueryBudgetGate`, `ScaffoldProvider`, `ScaffoldRef`, `StructuralEstimate`,
`SubmissionResult`, `SubmitReceipt`, and `SubmitRequest`.

**Independent proof repair and synchronization.** The complete ordered repair
line after PR #33 is:

1. `aea3f5db86dde5851f5ea02994e5f91866f477d1`, tree
   `c252f2808238fafddfc6d0128d12363e567b99fd`, subject `test: complete A9
   closure evidence`, sole parent
   `97d835f495cb7e3f194364cb4e674e2416531936`, changed only
   `tests/cpu/test_mcp_skeleton.py` by `+414/-20`, and produced test blob
   `776035155b286620d098da70132182636b6e5eb0`. This closed the original
   structural-estimate and dependency-boundary evidence gaps.
2. `1f921c1223f94cad87b9e52a0773c1299d2980a5`, tree
   `55f5a5edab62dd82c42d8d02a46cd64d74635aa9`, subject `chore: synchronize A9
   test proof repair with current main`, has ordered parents
   `aea3f5db86dde5851f5ea02994e5f91866f477d1` and then-current main
   `a5ddf7912818c55e9d89a0343e8d9570bdf6af9e`; relative to its second parent it
   changed only the canonical A9 test by `+414/-20`.
3. `0830f479ec765905a016e86ea6a366bbc136e873`, tree
   `92b7c8d7af9a0721a1714a8b6b0f2b01ab9f5b67`, subject `test: close computed
   dynamic-import guard gap`, sole parent
   `1f921c1223f94cad87b9e52a0773c1299d2980a5`, changed only the A9 test by
   `+167/-29`, and produced test blob
   `7ef7e1d9bd09b3d70dc5fd1806c8e2fb43099376`.
4. `ddca0d3c7c71361b80aacb5489c56e7f36e0783e`, tree
   `222ca383b38a486d43ed1c74824fcbf2cdb75582`, subject `test: cover
   variable-bound dynamic-import keys`, sole parent
   `0830f479ec765905a016e86ea6a366bbc136e873`, changed only the A9 test by
   `+104/-4`, and produced final test blob
   `f2f5d35dafa88b56f3beb50f24cc565c32bddec1`.
5. Exact reviewed head `dc88336f5edb544af5d4f4a82661f3f031de7603`, tree
   `f934ea4f3c4f63b26e890a26f4c941f73519b73b`, subject `chore: resynchronize
   A9 test proof repair with current main`, has ordered parents
   `ddca0d3c7c71361b80aacb5489c56e7f36e0783e` and then-current main
   `3d193eeec7d2d8ae3a4beea31ac2de06a2bc5329`;
   relative to its second parent it changed only the A9 test by `+652/-20` and
   preserved final test blob
   `f2f5d35dafa88b56f3beb50f24cc565c32bddec1`.

**Repair merge topology and unchanged runtime.** PR #34 merged normally as
`0099a198bf19845390a0a12825eac0eeef06ffd2`, tree
`f934ea4f3c4f63b26e890a26f4c941f73519b73b`, with ordered parents current main
`3d193eeec7d2d8ae3a4beea31ac2de06a2bc5329` and exact reviewed head
`dc88336f5edb544af5d4f4a82661f3f031de7603`. The merge tree equals the
reviewed-head tree, their diff is empty, and the exact first-parent manifest is
one modified file, `tests/cpu/test_mcp_skeleton.py`, `+652/-20`; no authority,
design, context, dependency, packaging, CI, or production source path changed.
The final test blob is
`f2f5d35dafa88b56f3beb50f24cc565c32bddec1`. Current production blobs remain
exactly the PR #33 implementation blobs: `carbon/mcp/__init__.py`
`66d52c20fbcdfea6e8d3b28bab681ff111ef0dc5`, `carbon/mcp/model.py`
`f14160662bf61e22a98256ee183279d0424a3d83`, `carbon/mcp/providers.py`
`0234e25978662bc0ccf04ef0e5f875c2d32e26fa`, and `carbon/mcp/service.py`
`9491b8fef03320c19581a12ce43a67c80dc3ab4f`.

**External review state.** Greptile's exact-head summary targeted
`dc88336f5edb544af5d4f4a82661f3f031de7603` and states `Confidence Score:
5/5` and `No blocking failure remains.` The computed-key thread
`discussion_r3848212639` and variable-bound-key thread
`discussion_r3848373091` are both resolved; unresolved substantive thread
count is zero. All four formal review submissions remain `COMMENTED`, and the
formal review decision is empty; no `APPROVED` review is claimed.

**Recorded verification.** PR #32 post-merge run `32713700257` at
`47a62b2397b4125bb608eb69bf0e3dc6360c519d` completed successfully: CPU job
`97390378123` passed `1584` tests
in `39.35s`; quality job `97390377669` retained `Ruff 757/776; Black 62/68`,
recorded removed debt `Ruff 19, Black 6`, had zero changed Python files, and
reported no new debt. PR #33 post-merge run `32733665726` at
`97d835f495cb7e3f194364cb4e674e2416531936` completed successfully: CPU job
`97451392550` passed `1697` in `41.70s`; quality job `97451392342` retained the
same inventory, found all five changed Python files clean, and reported no new
debt. PR #34 post-merge run `32809955531` at
`0099a198bf19845390a0a12825eac0eeef06ffd2` completed successfully: CPU job
`97687282709` passed `1727` in `49.19s`; quality job `97687282932` retained the
same inventory, found its one changed Python file clean, and reported no new
debt. Fresh closeout runs passed focused A9 `143` in `4.08s`,
related `935` in `17.45s`, combined `1078` in `20.98s`, and full CPU
`1727` in `28.58s`.

Recorded wheel SHA-256
`71cb3706e4bad091b5a5290210a666fccb07d296d83274548288a29a422d18fd` and fresh
closeout wheel SHA-256
`0f33d38334e9de15b7a28188e856180c55934129b9c92d473330326285359263` both
support the bounded installed-artifact evidence. The fresh wheel used Python
3.11.11 and an isolated outside-tree wheel `site-packages` import under `-I`;
it exposed the exact 34 exports and loaded zero forbidden optional-heavy or
later-wave modules.

**Criteria, maturity, and exclusions.** Independent final audit records all
`29/29` bounded A9 implementation criteria as `PASS` and zero as `FAIL`.
`SPECIFIED / RATIFIED: YES`. `IMPLEMENTED: YES` only for the bounded,
process-local, in-process Wave-A control/disclosure skeleton.
`TESTED: YES` only for the exact recorded CPU, hostile-input, resource,
concurrency, disclosure, dependency, import, wheel, and quality engineering
scope. `SCIENTIFICALLY_QUALIFIED: NO`.
`SECURITY_QUALIFIED: NO`. `NETWORK_QUALIFIED: NO`.
`COMMERCIALLY_VALIDATED: NO`. `PRODUCTION_QUALIFIED: NO`.

No production provider, content, or policy; prior publication; scaffold body;
mock pack; resource/query/fee/quota/concurrency/rate value; authenticated or
cryptographic requester identity; production requester authorization; network
server, transport, or MCP SDK; mock/light execution; real training or miner
code; production context or backend; LIVE science or Score Pack; workload or
sandbox containment; arbitrary malicious-Python detection; adaptive-query
qualification; official-exam replay resistance for an integrated deployment;
evidence, receipt, or signature implementation; leaderboard/A10+, logging/A11,
invariant/A12, frontier, Product Qualification, treasury/settlement,
Bittensor/chain, weight, or emission authority is included. A10, A11, and A12
remain `todo`.

## 2026-08-24 — A8 implementation, conformance repair, and administrative closeout candidate

**Ratified contract.** PR #28, `docs: ratify bounded A8 TrainEval stub
contract`, preserved the five-file documentation candidate at reviewed head
`b354c4df4f559b90df2d53f28c06bed3ec0df87f` and merged normally as
`872be272fe80df19c28611388fc4e1ebcd7b4900`. The merge has ordered parents
`6a3fe0f8e34602af5a4eaeaa8ae145d967537724` and
`b354c4df4f559b90df2d53f28c06bed3ec0df87f`; the reviewed-head and merge tree
are both `925191f711daaafb3fa33d58c0bd8c53efc74141`, with an empty diff. That
human-authorized merge ratified A8-R1 through A8-R15 below; this closeout does
not renumber, weaken, or reinterpret them.

**Implementation topology.** The bounded implementation began from the exact
ratification merge. Original implementation commit
`e16677b54e6523b1203d09c7807a736909041ac9`, tree
`e29e4874c72fc0bcbee101e2063773f244dd640b`, has sole parent
`872be272fe80df19c28611388fc4e1ebcd7b4900`. Synchronization commit
`872736cdee0b4149856a68229b34c69e2b2f0490` has ordered parents
`e16677b54e6523b1203d09c7807a736909041ac9` and
`f8c211602191a10c9a59f1e6f68fb60918f70882`, and tree
`9d7f5ee3e78edbc72dc75391fafb87373ae3019d`. PR #29 merged that synchronized
head normally as `d0011e959622b65f6ae737db7477062104bafa33`, with ordered
parents `f8c211602191a10c9a59f1e6f68fb60918f70882` and
`872736cdee0b4149856a68229b34c69e2b2f0490`; its merge tree is the same
`9d7f5ee3e78edbc72dc75391fafb87373ae3019d` and the synchronized-head-to-merge
diff is empty.

The exact PR #29 implementation manifest was:

```text
.agent/WAVE.md
carbon/traineval/__init__.py
carbon/traineval/model.py
carbon/traineval/service.py
carbon/traineval/stub.py
tests/cpu/test_traineval_stub.py
```

Post-implementation push run `32676389502` was `completed / success` on exact
merge head `d0011e959622b65f6ae737db7477062104bafa33`: `1562 passed in
41.34s`; quality remained `Ruff 757/776; Black 62/68`, removed debt
`Ruff 19, Black 6`, five changed Python files clean, and no new debt.

**Independent closeout audit and corrective repair.** Administrative closeout
stopped when independent review found two `IMPLEMENTATION_LAG` defects. A8
directly reconstructed A5 `InternalResult` despite A8-R7, and a low-level
mutated exact `SeedPin.seed_scheme` was silently normalized during ownership
copying while the A8 identity matrix omitted that seventh field. The same
review found the A5-construction source guard covered only `service.py`.

Corrective head `eb1af294edc35b25ea36a699968092470e5d2afa`, parent
`d0011e959622b65f6ae737db7477062104bafa33`, has tree
`db94ca592af2ee808976c615b97065dbcbeb7f24`. PR #30 merged it normally as
`b30c3f5fc2a53df0611d5e8b80120fbf4b64531c`, with ordered parents
`d0011e959622b65f6ae737db7477062104bafa33` and
`eb1af294edc35b25ea36a699968092470e5d2afa`. The corrective-head and merge
tree are both `db94ca592af2ee808976c615b97065dbcbeb7f24`, the
head-to-merge diff is empty, and the reviewed head is the second parent.

The exact PR #30 corrective manifest was:

```text
.agent/WAVE.md
carbon/scoring/model.py
carbon/seeding/model.py
carbon/traineval/model.py
tests/cpu/test_scoring_engine.py
tests/cpu/test_seeding.py
tests/cpu/test_traineval_stub.py
```

A5 now owns recursive validated `InternalResult` copying, A4 rejects malformed
current `SeedPin.seed_scheme` identity without rendering it, A8 delegates the
copy, and the scientific-construction source guard covers every A8 Python
module plus direct, qualified, import-alias, and assignment-alias forms. PR
#30 added owner regression tests at the A4/A5 seam but weakened no existing
A0--A7 behavior or test expectation and changed no fixture, dependency,
packaging, CI, or quality baseline.

Post-corrective push run `32686140393` was `completed / success` on exact
current-main head `b30c3f5fc2a53df0611d5e8b80120fbf4b64531c`: `1584 passed in
42.19s`; quality remained `Ruff 757/776; Black 62/68`, removed debt
`Ruff 19, Black 6`, six changed Python files clean, and no new debt. Recorded
candidate evidence also includes focused `649 passed in 7.08s`, related `1197
passed in 29.66s`, full `1584 passed in 34.33s`, and the unchanged independent
oracle/golden/identity/retry/concurrency selection `17 passed in 0.16s`. All
nine literal synthetic scalars, literal leg scores, and exact combined score
`0.8947523571654831` remain unchanged. A fresh Python 3.11.11 wheel installed
with `--no-deps` and imported under `-I` outside the repository with the exact
six A8 root exports, zero blocked optional-heavy/later modules, and SHA-256
`a37f4d0f1545582ae42a2a4de0a1d56276de4c64fbd5b9bc547fd63cfb408f25`.

**Bounded acceptance and proposed administrative closeout.** Every one of the
existing twenty-five implementation criteria maps to current code and
canonical tests. This documentation-only closeout checks those criteria and
proposes A8 `done`; that status becomes authoritative only after independent
review, explicit human authorization, and merge of this closeout. The
closeout changes exactly the current A8 decisions, tracker, plan, ticket,
Build Out status block, agent-pack status, and three maturity ledgers. It
changes no Python, test, fixture, dependency, packaging, CI, quality baseline,
scientific/business canon, historical reconciliation snapshot, or A9+ file.

```text
A8 SPECIFIED / RATIFIED: YES
A8 IMPLEMENTED: YES on current main for the bounded fixture-official,
deterministic, process-local stub scope, including the reviewed conformance repair
A8 TESTED: YES only for the exact recorded CPU/security/import/wheel/quality scope
A8 SCIENTIFICALLY_QUALIFIED: NO
A8 SECURITY_QUALIFIED: NO
A8 NETWORK_QUALIFIED: NO
A8 COMMERCIALLY_VALIDATED: NO
A8 PRODUCTION_QUALIFIED: NO
A8 WAVE STATUS: done only after this documentation-only closeout is independently reviewed, explicitly human-authorized, and merged
```

No mock/light adapter, production adapter/context/resource policy, real
training or miner-code execution, sandbox/container qualification,
authenticated provenance, scientific/reference/backend qualification, LIVE
Challenge or Score Pack, evidence/receipt/signature, A6 bypass, leaderboard,
frontier, Product Qualification, treasury/settlement, commercial validation,
Bittensor/chain, weight, or emission authority is conferred. A9--A12 remain
unstarted and `todo`; A9 requires its own orientation and contract
reconciliation after this closeout is reviewed and merged.

## 2026-08-23 — A8 pre-implementation TrainEval fixture-stub contract candidate

**Repository truth, status, and scope.** A fresh fetch resolved `origin/main`
to exact commit `6a3fe0f8e34602af5a4eaeaa8ae145d967537724`
and exact tree `b5052df524b43ef07ece953757a74fe0e84da1e8`.
That commit is the normal PR #27 merge with ordered parents
`5b7b38a4db3b0a7bbf2d97ae872a28a3d885d77d` and
`2d192a10475568af092df74bb0afff3e9dece6a8`; the reviewed second-parent tree
equals the merge tree. Post-merge push run `32630014802` completed
successfully with `1423 passed in 30.36s`, unchanged
`Ruff 757/776; Black 62/68`, zero changed Python files, and no new debt. A7 is
`done`, A8--A12 are `todo`, and the A7 ticket retains twenty checked and zero
unchecked bounded criteria. Remote branch and open/closed PR searches found no
competing A8/TrainEval implementation, test, plan, or lifecycle.

At the verified base, `carbon/traineval/__init__.py` was the one-line A0 package
marker and there was no A8 source, canonical test, fixture, dependency, or
prior plan. This five-file documentation candidate adds the pre-implementation
plan and repairs the conflicting generic contract in
`Design_Specs/Build_Out.md` and the stale A8 ticket. It does not implement or
test A8, modify `.agent/WAVE.md`, start A9+, or authorize its own merge.

```text
A8 SPECIFIED / RATIFIED: YES only after this documentation candidate is independently reviewed, explicitly human-authorized, and merged
A8 IMPLEMENTED: NO
A8 TESTED: NO
A8 PRODUCTION-QUALIFIED: NO
A8 WAVE STATUS: todo
```

**A8-R1 — Bounded ownership and upstream authority.** A8 owns trusted
execution-profile/runtime configuration, actual backend selection and launch,
private A4 context acquisition/seed conversion, concrete execution controls,
backend-output validation, prediction/reference/metric materialization for a
future real backend, complete pack-authorized scalar-input construction,
current A5 engine invocation, operational attribution, exception redaction,
and one minimum private execution outcome. A8 does not own or duplicate A2
schema validation; A3 challenge/LIVE/backbone admission; A4 context/seed
semantics; A5 pack, input, gate, transform, aggregate, status, or result
semantics; A6 storage/projection; or A7 submission identity, accepted Strategy
snapshot/hash, ChallengeKey/EvaluationBinding, attempts, current-handle
authority, FSM, retry budget, fee/refund, cancellation state, or publication.
A9 owns miner-facing transport/disclosure for the later mock/light surface,
while A8 retains mock execution under a later joint contract; A10 leaderboard; A11
logging/metrics; A12 invariant aggregation; later evidence and chain owners
retain transcripts, receipts, signatures, provenance, weights, and emissions.

A2 and A3 are prior admission authorities already consumed by A7. A8 never
calls `dry_validate`, repeats challenge eligibility, or repeats allowed-
backbone rejection after queue admission. Runtime failure positively
attributable to the accepted Strategy is `StrategyFailedRun`, never A2/A3
`REJECTED`. A7 has no dependency on A8 and later composition must not reverse
that direction.

**A8-R2 — First entry point and trusted construction.** The first bounded
implementation is fixture-official only:

```text
FixtureTrainEvalService.run_fixture(
    envelope: exact FixtureExecutionEnvelope
) -> private FixtureRunOutcome
```

Trusted composition constructs the service with one immutable exact
`FixtureStubProfile`, exact A4 `DeterministicFixtureProvider`, exact verified
A5 `LoadedScorePack`, trusted fixture runtime configuration, exact declared
execution-environment identity, and exact deterministic
`FixtureStubBackend`. The run call accepts no independent Strategy,
StrategyHash, batch, generic mode, runtime limit, attempt number, ChallengeKey,
SeedPin, environment pin, context, seed, Score Pack, or backend identity. No
generic `run(strategy, batches, mode, limits, pin)` compatibility overload or
relabel path exists.

The exact frozen/slotted `FixtureRuntimePolicy` is a trusted fixture-only
composition value with literal policy ID `a8_fixture_stub_policy_v1`, exact
`backend_profile_id`, exact `container_digest`, and an immutable total tuple
mapping every exact `InfrastructureCause` once to an exact
`InfrastructureRetryClass`. It has no generic mode, runtime numeric limit,
production control/value, fallback, backend selector, or caller-settable
emission field. The service reconstructs an `ExecutionEnvironmentPin` from the
policy's two safe environment identifiers and requires equality with both the
separately declared fixture environment identity and the handle pin. Exact
`FixtureStubBackend` capability metadata must match the same identifiers and
has constant false emission capability. The retry table is injected trusted
fixture test policy, not an infrastructure fact, retry permission, A7 budget,
or production default.

The service is a trusted private integration object. Its ability to be
constructed or imported does not confer production, scientific, publication,
or emission authority. The completed A5 result-bearing surface is not a
miner-facing API, A9 response, A6 card, leaderboard/log record, generic
serialization, or broad convenience export.

**A8-R3 — Boundary validation, envelope trust, and immutable science
identity.** The fixture call first requires the exact built-in
`FixtureExecutionEnvelope` type, reconstructs exact owned handle and safe
identity values, requires `AdmissionKind.FIXTURE`, and requires the envelope
ChallengeKey to equal the handle `SeedPin.challenge_key`. Wrong type,
subclass, production/mock/cross-kind value, malformed copied handle/pin, or an
internally contradictory untrusted envelope raises one stable non-echoing A8
boundary error without A7 mutation based on that object. Errors never echo a
value, object `repr`, configured value, path, measurement, or exception text.

The fixture stub deliberately ignores both mutable `envelope.strategy` and
independently presented `envelope.strategy_hash` when deriving synthetic
material. A4 derivation through the exact handle `SeedPin` already binds A7's
opaque `EvaluationBinding`, which A7 constructed from its stored SubmissionId,
canonical StrategyHash, and ChallengeKey/version. Attempt number is excluded
from this scientific identity and remains in the returned handle. A7's
current envelopes, handles, frozen values, and exact-type checks are
process-local correctness boundaries, not authenticated capabilities or a
sandbox. Equivalent forged values cannot be authenticated in same-process
Python. A future real backend that must interpret the Strategy requires a
separately ratified immutable/verifiable A7 snapshot handoff; the Wave-A stub
does not invent it.

Trusted composition must construct and preflight the exact service and its
mandatory dependencies before asking A7 to start an attempt. A construction
failure is therefore a pre-start integration error, not an outcome without a
handle. After trusted composition supplies the envelope returned directly by
A7 start and A8 establishes only its structurally exact owned fixture boundary,
any trusted
profile/configuration, pack, context/provider, environment, backend,
materialization, A5-input, or A5-scoring integration failure becomes a closed
infrastructure outcome carrying that owned handle. It does not fall back to a
boundary error that could strand a real current A7 attempt in `RUNNING`.
Only A7 can determine at callback that the handle is authentic and current;
A8 makes no such claim. If composition violates the required preflight-before-start
ordering, that layer remains responsible for resolving the original A7
attempt through an authorized operation.

**A8-R4 — Exact A7 outcome mapping and stale authority.** A8 returns facts and
trusted policy classifications; it never invokes or imports
`SubmissionService`, writes an A7 store, creates an attempt, retries,
terminalizes, refunds, cancels, or publishes. Trusted composition applies:

```text
CompletedFixtureRun
  -> SubmissionService.complete_and_publish(handle, internal_result)
StrategyFailedRun
  -> SubmissionService.fail_strategy(handle)
InfrastructureFailedRun(RETRYABLE, ...)
  -> SubmissionService.retry_infrastructure(handle)
InfrastructureFailedRun(NON_RETRYABLE, ...)
  -> SubmissionService.fail_infrastructure(handle)
malformed untrusted boundary object
  -> no A7 mutation based on that object
stale/wrong callback
  -> A7 rejects the exact handle with no mutation
```

`RETRYABLE` is a trusted backend/policy classification that another execution
could be attempted; it is not permission, budget, or a retry operation. A7
alone applies its immutable retry policy, increments the attempt, preserves
scientific identity, rejects stale handles, and either requeues or reaches its
own `FAILED_INFRA`. `NON_RETRYABLE` is likewise an A8 operational
classification, not an A8 lifecycle state. `FAILED_INFRA` and
`FAILED_STRATEGY` remain exclusively A7 states.

**A8-R5 — Exact context and data-right separation.** Fixture execution
acquires only exact `FixtureOfficialContext` through
`acquire_fixture_official_context(exact DeterministicFixtureProvider, exact
handle.seed_pin)`, then requires `context.pin == handle.seed_pin` and derives
only with `derive_fixture_official_seed`. It never accepts `MockContext`,
provider-origin `OfficialContext`, `QualificationContext`, raw entropy, a
private root, or a caller-provided derived seed. A7 receives no context,
entropy, private root, official/master/derived seed, role/domain/draw identity,
hidden realization, or runtime payload.

A future production adapter is nominally separate, consumes only an exact A7
`ProductionExecutionEnvelope`, and acquires only provider-origin
`OfficialContext` after OQ-005/OQ-006 and every A3/backend/A5/A6/evidence/
security gate is separately resolved and ratified. There is no provider,
timing, fallback, resource, backend, or production Score Pack default now;
production remains fail closed.

**A8-R6 — Exact deterministic fixture profile.** The only supported first
profile is exact `a8_fixture_stub_v1`, conspicuously synthetic and bound to the
current verified A5 fixture pin:

```text
ChallengeKey:              (a5_fixture, fixture-1.0)
scoring_version:           fixture-1.0
scoring_digest:            sha256:255923831905a84f55a88d8575e8ebcab42f3351676d6cf5ac9038dcc495fb57
generator_version_required: fixture-1.0
generator_digest_required: sha256:1111111111111111111111111111111111111111111111111111111111111111
schema_version:             1.0
numerical_profile:          python_binary64_v1
fixture_origin:             true
```

The profile accepts no other pin and derives no arbitrary input-key set. Its
exact profile-private keys are the current pack's numeric
`gate_error`, `diagnostic_error`, `physics_error`, `robust_mean_a`,
`robust_tail_a`, `robust_mean_b`, `robust_tail_b`, `accuracy_error_a`, and
`accuracy_error_b`, plus exact Boolean `finite_ok`. These names are not a
general TrainEval protocol or scientific metric vocabulary.

The profile derives three independent A4 outputs, all at exact draw index `0`:

```text
OFFICIAL_TRAIN  + RoleKey("a8_fixture_train")
OFFICIAL_EVAL   + RoleKey("a8_fixture_eval")
OFFICIAL_STRESS + RoleKey("a8_fixture_stress")
```

The exact HMAC phase-label bytes are ASCII `official_train`, `official_eval`,
and `official_stress`, respectively. `diagnostic_error` uses the train
derivation; `gate_error`, `physics_error`, and both accuracy inputs use the
eval derivation; the four
robustness inputs use the stress derivation. Each numeric key uses HMAC-SHA-256
with that phase's exact 32 derived bytes as key. The message begins with exact
ASCII `carbon.a8.fixture-stub.scalar.v1`; each following field is framed as an
unsigned four-byte big-endian byte length followed by exact ASCII bytes, in
this order: profile ID, phase label, input key, exact scoring digest, exact
generator digest, configured backend-profile ID, and configured container
digest. No generic serializer or platform-native integer encoding is used.

For each HMAC digest, `n = int.from_bytes(digest[0:8], "big") >> 11` and
`u = n / 2**53` in built-in binary64. For `gate_error`, the conspicuous
synthetic value is evaluated in exact operation order `0.5 + (1.0 * u)`; for
every other numeric key it is `0.125 + (0.5 * u)`. `finite_ok` is exact
`True` and consumes no derived bytes. These values exercise current fixture scoring structure only. They are
not predictions, references, relative errors, validated metrics, thresholds,
tolerances, qualification evidence, or production science.

Attempt number, mutable Strategy, independently presented StrategyHash, time,
Python `hash()`, `random`, filesystem/order, network, environment variables,
mutable backend registry/global state, and call order are absent. Environment
identity is bound through the trusted configured values and separately checked
against the handle pin; the pin is not treated as configuration. Independent
literal golden vectors and a straight-line oracle must use no implementation
encoder/helper and must not expose entropy/derived bytes. Perturbation must
cover every SeedPin field through A4, the opaque EvaluationBinding, configured
environment fields, profile, phase, and input key. Retry attempt changes must
change only the returned handle, not synthetic scalar material.

**A8-R7 — A5-exclusive scientific result construction.** A8 validates that
its exact loaded pack pin agrees with the projection available in the handle
SeedPin: `ScorePackPin.challenge_key == SeedPin.challenge_key`, scoring version
and digest equality, and `generator_version_required`/
`generator_digest_required` equality with the SeedPin generator version/
digest. A5 has no EvaluationBinding or seed-scheme field, so wholesale pin
equality is neither possible nor claimed. A8 separately requires the exact
A8-R6 schema/numerical/fixture profile. A8 builds the
complete exact ordered scalar input only through
`LoadedScorePack.fixture_score_input` and invokes current
`ScoreEngine.score`. A8 never calls the private `ScoreInput` factory directly,
constructs `InternalResult`, adds a score/status/result model, or selects a
threshold, gate, transform, weight, tolerance, metric, production pack, or
eligibility value.

Only exact A5 `SCORED` and `MANDATORY_GATE_FAILED` results may construct
`CompletedFixtureRun`. `PACK_NOT_READY` is an operational infrastructure
outcome and never a completion or A6 input. The sole ready A8-R6 profile does
not normally produce it; the cause is retained defensively for an exact A5
integration result and future ratified profiles, never as fallback. Pack mismatch, context failure,
missing/extra/malformed/non-finite/partial execution material, input
construction error, scoring integration/computation error, backend/reference
failure, or infrastructure-derived scalar creates no authoritative
`ScoreInput`, gate, scientific zero, completed `InternalResult`, or card.
Mandatory-gate failure is a completed A5 fixture scoring result only when A5
receives complete valid input and constructs that exact status; the synthetic
stub confers no scientific authority.

**A8-R8 — Closed private errors, outcomes, and causes.** The exact private sum
is:

```text
FixtureRunOutcome =
  CompletedFixtureRun(
    exact ExecutionAttemptHandle,
    exact InternalResult
  )
| StrategyFailedRun(
    exact ExecutionAttemptHandle,
    exact StrategyFailureCause
  )
| InfrastructureFailedRun(
    exact ExecutionAttemptHandle,
    exact InfrastructureRetryClass,
    exact InfrastructureCause
  )

InfrastructureRetryClass = RETRYABLE | NON_RETRYABLE

StrategyFailureCause =
  STRATEGY_RUNTIME_FAILURE
| STRATEGY_TRAINING_FAILURE
| STRATEGY_NUMERICAL_FAILURE

InfrastructureCause =
  CONFIGURATION_UNAVAILABLE
| SCORE_PACK_MISMATCH
| SCORE_PACK_NOT_READY
| CONTEXT_UNAVAILABLE
| ENVIRONMENT_MISMATCH
| BACKEND_UNAVAILABLE
| BACKEND_STARTUP_FAILURE
| EXECUTION_TIMEOUT
| RESOURCE_VIOLATION
| BACKEND_NUMERICAL_FAILURE
| REFERENCE_FAILURE
| INCOMPLETE_EXECUTION_MATERIAL
| SCORE_INPUT_FAILURE
| SCORE_COMPUTATION_FAILURE
```

Boundary errors are exact stable `FixtureRunRequestError` and
`FixtureRunIdentityError` with closed non-echoing codes for wrong type,
subclass, cross-kind, malformed reconstructed nominal, and internally
contradictory untrusted envelope. They carry no handle-based transition
authority. Cause enums are the only failure diagnostic in an outcome; there
is no arbitrary message, raw exception, value, path, configured/observed
limit, measurement, object, stack trace, or backend payload.

`FixtureRunRequestError` has exact code
`traineval.fixture_request_invalid` and exact message `Fixture execution
request is invalid.`; wrong envelope type, subclass, and cross-kind request map
only to it. `FixtureRunIdentityError` has exact code
`traineval.fixture_identity_invalid` and exact message `Fixture execution
identity is invalid.`; malformed reconstructed handle/pin/envelope identity
and internal contradictions map only to it. Constructors copy only those
literal values, exception chaining is suppressed at the boundary, and neither
class accepts caller diagnostic arguments.

**A8-R9 — Attribution and operational completeness.** Strategy failure is
permitted only when the trusted adapter can positively attribute a
runtime/training/numerical failure to the accepted declarative Strategy under
a ratified backend contract. An unknown exception type, ambiguous numerical
failure, backend/reference failure, output-validation failure, hostile
exception/repr, or uncertain attribution defaults to infrastructure. A8 never
uses `invalid_strategy` and never converts operational absence/failure into a
mandatory gate or scientific zero.

The bounded deterministic `FixtureStubBackend` ignores Strategy and executes
no miner code, so `FixtureTrainEvalService` has no positive-attribution path
and never emits `StrategyFailedRun`. The variant is retained in the closed
TrainEval integration contract for a future separately ratified real backend;
the later implementation task must test its mapping to A7 at the private
outcome/composition seam, never by fabricating Strategy blame in the fixture
service.

For the structurally exact envelope supplied directly by trusted composition
from A7 start, every run-time integration cause in A8-R8 returns
`InfrastructureFailedRun`; no such path raises a request error and
leaves the attempt silently running. The immutable trusted fixture policy
uses the exact total fixture classification table from A8-R2.
Production cause-to-retry policy, retry count/budget, time/resource values,
and fallback remain human-owned; no fixture classification is relabelled as
production policy.

**A8-R10 — Resource, environment, launch, and shutdown separation.** A7
`SubmissionResourceLimits` govern hostile input capture and retained-record
capacity. A7's `ExecutionEnvironmentPin` and attempt number are immutable safe
identity. A8's separately injected runtime policy owns actual CPU/GPU/backend
selection, memory/time/process/filesystem/network controls, launch, private
materialization bounds, type/shape/finiteness validation, exception
conversion, and shutdown. The A8 configuration reconstructs its exact
`ExecutionEnvironmentPin` from trusted declared values and compares it with
the handle pin before backend invocation; it never treats caller or handle pin
values as executable configuration or qualification proof.

The in-process Wave-A stub executes no miner code, performs no network or
filesystem operation, and imports no heavy/dynamic backend. Its first bounded
synchronous contract has no cancellation API. Current A7 owns its bounded
requester cancellation policy; a later real A8 adapter must separately ratify
transient cooperative and hard shutdown without creating a second lifecycle.
Hard
wall-clock/process/GPU/memory/disk/network enforcement, container supervision,
credential isolation, timeout-evasion resistance, reproducibility tolerances,
and production shutdown are later backend/security/operations qualification.
No production value is supplied here.

**A8-R11 — Minimum result, retention, and disclosure.** The private outcome
contains only an exact owned attempt handle, one exact closed variant,
one exact cause/retry class where applicable, and the exact completed A5
`InternalResult` where applicable. Backend/environment identity appears only
through the handle's existing safe pin; runtime configuration is not copied.
Values are frozen/slotted, freshly reconstructed without retained caller
aliases, and refuse generic serialization/copying where it would broaden the
boundary. These supported-API properties are not tamperproof against arbitrary
same-process `object.__setattr__`; A7 revalidates the callback handle and
remains the mutation authority.

Pairing the exact handle with an exact A5 result is process-local trusted
integration only, not authenticated or substitution-resistant execution
provenance. That assurance remains later receipt/evidence work.

Context and derived bytes exist only ephemerally inside the service call and
are not retained after use. Outcomes, errors, post-run retained state, test
diagnostics, and reachable public graphs exclude context objects;
entropy/private roots; raw official/
master/derived seeds; role/domain/draw identity; raw predictions/references; raw
metric/category/percentile vectors; `ScoreInput`; checkpoints/model weights;
exception text/stack traces; filesystem paths; environment variables;
credentials; fee data; A6 cards; public diagnostic text; transcripts,
receipts, evidence, signatures; emission weights; and eligibility overrides.
A11 may later observe only separately ratified closed redacted fields. Later
evidence needs do not expand the Wave-A result.

**A8-R12 — Mechanical non-emission capability.** Exact fixture backend
capability metadata, exact fixture service capability, and exact fixture
outcome expose `emission_capable = False` mechanically with no caller argument
or mutable field. A5 independently enforces `eligible_for_emission = False`
and A6 copies exact fixture origin/false eligibility through its allow-list.
The fixture outcome cannot write A6, leaderboard, weights, chain, or emissions.

Negative capability is defense in depth, not positive production provenance.
A later official leaderboard/weight/chain consumer must require exact positive
qualified production origin, backend/profile, pack, and required receipt/
evidence rather than accept an arbitrary Boolean. That refusal integration is
later-owned and is not implemented by this ticket or documentation.

**A8-R13 — Hostile-input boundary and archaeological disposition.** The
accepted A2/A7 Strategy remains hostile. The stub interprets none of its
parameters and executes no supplied code, which meaningfully avoids path
traversal, arbitrary import, environment/credential access, network/filesystem
exfiltration, fork bombs, miner-controlled/unbounded runtime allocation, and timeout evasion in the
bounded synthetic path. It still exact-type checks/reconstructs safe envelope
identity, validates bounded outputs, never renders hostile exceptions, and
uses no caller-controlled backend selection. Frozen Python values and private
attributes are not security isolation.

KEEP the empty `carbon.traineval` seam and A4/A5/A7 exact boundaries. KEEP and
later WRAP the A1 lazy optional-backend loading idea only behind qualified
trusted configuration; its mutable registry is not a trust root. Preserve
PoC NumPy/JAX kernels, generators, and relative-error ideas as archaeology for
later scientific/backend review. REPAIR/WRAP them only after separate
qualification. REPLACE or exclude historical `carbon/training`, validator,
defaulting gate/score, raw-seed/card, direct weight, Julia service, deployment,
random/time/hash, and mock-fallback behavior for A8. No legacy/PoC/neurons/
Julia/deployment/emission component is imported by the fixture stub.

Real untrusted execution still requires a separately qualified process/
container boundary for network/filesystem/credential/PID/memory/disk/time/GPU
controls, backend reproducibility, hostile outputs, and audited redaction.
Wave-A tests cannot production-qualify any of those properties.

**A8-R14 — Small module, dependency, and test boundary.** The smallest future
layout is:

```text
carbon/traineval/
  __init__.py
  model.py
  service.py
  stub.py
```

`model.py` owns immutable fixture profile/policy, private closed outcomes and
stable errors; it may source-import only standard library and the minimum A5/A7
identity/result types. `stub.py` owns deterministic dependency-free synthetic
material and imports only standard library plus private A8 model. `service.py`
owns envelope/config/pin/context validation, profile execution, A5 validated
input construction and scoring; it may import exact A4, A5, and A7 model
types, never A7 service/store. The exact future root `__all__` is limited to
`FixtureRunIdentityError`, `FixtureRunRequestError`, `FixtureRuntimePolicy`,
`FixtureStubBackend`, `FixtureStubProfile`, and `FixtureTrainEvalService`.
Cause/retry enums, backend material, and all result-bearing outcome variants
remain explicit trusted imports from A8-private modules and are not broad root
exports; `InternalResult` is never re-exported. No `integration.py` is needed:
composition stays outside A8.

Forbidden direct source imports/calls are A2 validation, A3 admission calls, `carbon.cards`,
`carbon.fees.service`/store internals, A9--A12, legacy training/validator/
emission, PoC, neurons, Julia, network clients, mutable/dynamic backend
selection, and eager Torch/JAX/PhysicsNeMo/neural-operator imports. No new
dependency is justified. Canonical future tests live at
`tests/cpu/test_traineval_stub.py` and cover every unchecked ticket criterion,
installed-wheel/outside-tree import, the full CPU suite, Ruff/Black, and the
no-new-debt ratchet. Current `carbon.fees.__init__` transitively initializes
its existing service/card dependencies when A7 model types are imported; A8
does not treat `sys.modules` absence as an attainable isolation property or
add a source dependency/call to those owners. Documentation and proposed tests
are not current test evidence.

**A8-R15 — Reserved mock lane, production failure closure, and implementation
gate.** Build Out and A9 still require a mock/light free path under the same
architectural TrainEval owner, but it is structurally separate rather than a
mode:

```text
MockTrainEvalService.run_mock(
    request: exact future MockExecutionRequest
) -> MockRunOutcome
```

The exact mock request/resource/disclosure contract remains deferred to a
later A8/A9 documentation ratification. A mock outcome is not A5
`InternalResult`, cannot enter A7's official lifecycle or A6, creates no card,
and affects no fee, official score, leaderboard rank, weight, or emission. It
is mechanically non-emission-capable. This candidate neither edits A9 nor
authorizes estimate/light implementation; A9 must wait for that separate
contract.

No real neural-operator training, production backend/container/sandbox,
scientific threshold/tolerance/metric, production runtime/provider/fallback,
LIVE pack/challenge, authenticated provenance, transcript/receipt/evidence/
signature, A6 bypass, MCP/mock implementation, leaderboard, logging/metrics,
A12 invariant work, Bittensor/chain, weights, or emissions is included.
Future A8 implementation may begin only after this exact documentation is
independently reviewed, explicitly human-authorized and merged, followed by a
fresh main/tree/status/concurrency check proving A8 remains `todo` and
unimplemented. That implementation requires a separate bounded task and must
leave every production and mock path fail closed.

## 2026-08-23 — A7 implementation and administrative closeout

**Implementation topology and review.** A7 implementation started from exact
base `f8cf1a030415778f519d55b85d8e287f09cdeba2`, was independently reviewed at
head `f5ec1315a5ae501c2726fc0fbd6d0fa85c56b4b9`, and merged normally by PR #26
as `5b7b38a4db3b0a7bbf2d97ae872a28a3d885d77d`. The merge's ordered parents are
the exact base followed by the reviewed head. The reviewed head is ancestral
to current `main`; its tree and the merge tree are both
`803fcf53ed99399c141e73d050f962847aeb36f8`, and their diff is empty. GitHub
reports PR #26 `MERGED`, with the expected head, base, and merge commit and no
auto-merge configuration. The review evidence is the preserved reviewed head,
independent source/test audit, and passing CI; no formal submitted GitHub
approval object is claimed.

The exact implementation delta was:

```text
.agent/WAVE.md
carbon/fees/__init__.py
carbon/fees/identity.py
carbon/fees/integration.py
carbon/fees/model.py
carbon/fees/service.py
carbon/fees/store.py
tests/cpu/test_submission_fsm.py
```

The seven-file runtime/test surface is the six `carbon/fees/` modules and
`tests/cpu/test_submission_fsm.py`. It implements the bounded fixture-capable,
process-local A7 contract: permanent nominal submission identity; explicit
eleven-field resource limits and bounded detached hostile-input capture before
unchanged A2 authority; exact structural challenge/A4/A5 pin checks,
current-handle/environment binding, and A6 record/requester-key binding;
guarded open-submit idempotency and capacity accounting; the closed submission
FSM; append-only fee-event, retry, refund, and requester-cancellation
mechanics; and exclusive A6 publication sequencing. Separate fixture and
production admission paths keep production fail closed. The twenty ticket DoD
criteria were verified against the merged source and canonical focused tests
without weakening their text.

**Validation and CI evidence.** At the reviewed implementation head, focused
A7 (`319` in `8.26s`), related A2–A6 (`1077` in `14.57s`), package/import (`18`
in `0.92s`), fresh-wheel/outside-tree (`1` in `8.48s`), and full CPU (`1423` in
`20.05s`) checks passed. PR CI run `32621325895` passed all `1423` CPU tests in
`31.33s` and the unchanged quality ratchet (`Ruff 757/776; Black 62/68`) with
seven changed Python files clean and no new debt. Post-merge push run
`32622988239` on exact merge `5b7b38a4db3b0a7bbf2d97ae872a28a3d885d77d`
completed successfully: `1423 passed in 26.75s`, the same quality inventory,
seven changed Python files clean, and no new debt.

**Closure and residual boundary.** This administrative closeout modifies only
`.agent/DECISIONS.md`, `.agent/WAVE.md`, `.agent/plans/A7_fees_fsm.md`,
`.agent/tickets/A7_fees_fsm.md`, and
`docs/context/Implemented_vs_Specified`. It adds no code, test, fixture,
dependency, packaging, CI, quality-baseline, design-specification, or A8+ work.
A8–A12 remain unstarted and `todo`.

A7 remains explicitly non-production. Its store is in-memory and
process-local, not durable, restart-safe, interprocess, distributed, or
production-concurrency-qualified. Requester binding is structural equality,
not authentication. The ledger is not payment authorization, reservation,
transfer, or settlement. Production resource-limit values, fee values, retry
policy, backend qualification, official-context/provider policy, production
A5/A6 completion/publication seams, authentication, durable recovery,
transcript, receipt, evidence, signatures, transport, observability,
leaderboard, chain/Bittensor, score-to-weight mapping, emission authority, and
every other production gate remain unresolved or later-owned.

```text
A7 SPECIFIED / RATIFIED: YES
A7 IMPLEMENTED: YES on current main for the bounded fixture-capable, process-local scope
A7 TESTED: YES only for the recorded CPU/security/concurrency/import/wheel/quality scope
A7 PRODUCTION-QUALIFIED: NO
A7 WAVE STATUS: done only after this closeout is reviewed and merged
```

A7-R1 through A7-R15 below remain unchanged and continue to govern the bounded
contract and its later-owned limitations. This closeout supersedes only their
historical pre-implementation maturity snapshot; it does not rewrite,
renumber, weaken, or reinterpret any ratified decision.

## 2026-08-23 — A7 pre-implementation fees, submission-identity, and FSM ratification

**Repository truth, status, and scope.** A fresh fetch resolved `origin/main`
to the expected exact commit
`ba0b2b3dffd114d02fd5f6a71af08052a3e0a1ed`, with exact tree
`e3718deceef355936cdf427bb04b68fa3d98c760`. The commit is the normal merge of
the A6 closeout. At the pre-publication check, GitHub reported no other open
pull request and the remote contained no competing A7-named branch. A7 is still `todo`;
`carbon/fees/` contains only
its A0 package marker, and there is no canonical A7 source, focused test, or
runtime dependency. This entry proposes documentation-only ratification. It
does not implement or test A7, start A8+, change A0–A6 closure, or authorize a
merge.

```text
A7 SPECIFIED / RATIFIED: YES only after this ratification is explicitly human-authorized and merged
A7 IMPLEMENTED: NO
A7 TESTED: NO
A7 PRODUCTION-QUALIFIED: NO
A7 WAVE STATUS: todo
```

The human policy authorization recorded by the 2026-08-23 amendment selects
`REFUND` as the terminal `FAILED_INFRA` default and requester-bound
cancellation from `RECEIVED`, `VALIDATED`, and `QUEUED` under A7-R12/A7-R13.
It also moves the sole exam `CHARGE` to the first atomic
`QUEUED -> RUNNING` material-start transition. The hostile-input amendment
also requires an injected immutable A7 submission-resource policy before any
full Strategy validation/copy/hash work. Those selections do not authorize
implementation or make this candidate ratified before review and merge.

**A7-R1 — Bounded ownership.** A7 owns permanent submission identity,
canonical Strategy identity/hash and an owned accepted-Strategy snapshot,
independent submission-resource admissibility, exact A3 challenge-version
binding, the concrete A4 evaluation binding, structural requester binding,
process-local submission persistence, the core submission FSM, open-submit
idempotency, minimal execution-attempt identity and history, fee-event
mechanics, infrastructure retry/refund mechanics, requester-bound cancellation
policy/mechanics, and the A6 publication adapter. A7 does not own
TrainEval/backend execution or metric construction; MCP transport;
leaderboard; logging/metrics; invariant aggregation; execution transcripts,
receipts, evidence, signatures, or durable evidence storage; Bittensor,
score-to-weight mapping, or emissions. A8–A12 and later owners retain those
responsibilities. Later validator/C7 work integrates execution with this A7
FSM rather than defining a competing lifecycle.

**A7-R2 — Permanent `SubmissionId`.** `SubmissionId` is a new frozen, slotted
nominal A7 type. Carbon alone generates its value as the exact canonical
lowercase hyphenated string form of an RFC 4122 UUID version 4. The value is
miner-facing, opaque, non-sequential, and contains no requester/hotkey,
challenge, time, state, or attempt data. Callers cannot select it. Creation
generates exactly one candidate and checks it against the A7 store atomically;
a collision never overwrites or rebinds an existing record and instead raises
a typed fail-closed store error without record creation or regeneration.
Reuse, rebinding, normalization, and overwrite are prohibited and no such API
exists. The Wave-A store enforces collision rejection against its retained
process-local records;
across restarts, fresh UUIDv4 generation makes accidental reuse negligible but
does not provide a durable global collision registry. Retries retain one
`SubmissionId`; a resource-admissible later submit after a terminal record
receives a fresh one when new-record capacity remains.
“Permanent” means immutable protocol identity, not restart durability in the
Wave-A store.

The store retains an owned reconstruction of the generated nominal value and
returns a separate fresh `SubmissionId` wrapper, so low-level mutation of a
caller-held frozen wrapper cannot corrupt stored identity.

**A7-R3 — Resource-bounded, A2-authoritative Strategy identity.** Every
executable A7 store/service requires one immutable `SubmissionResourceLimits`
at construction. It is an A7 submission-security/operations input, not
scientific policy, fee policy, or attacker input. Human protocol/security/
operations owners supply production values; A7 has no default, fallback,
environment-derived, or guessed production values. A bounded Wave-A fixture
must inject conspicuous finite fixture-only values. A9 may later impose
stricter transport limits, but A7 remains independently bounded and never
depends on A9 for this protection. The policy is admission-kind-neutral because
identity processing precedes fixture/production queue admission. A store built
with fixture-only values is not production-capable and cannot be relabelled;
human-approved production values require a new store.

The closed minimum policy fields are:

```text
max_total_value_nodes
max_object_members
max_list_items
max_string_utf8_bytes
max_object_key_utf8_bytes
max_strategy_identity_bytes
max_challenge_id_bytes
max_concurrent_identity_builds
max_retained_submission_records
max_retained_value_nodes
max_retained_strategy_identity_bytes
```

Every field is an exact positive built-in integer; Boolean, coercion, absent,
unbounded/sentinel, mutable, or greater-than-unsigned-64 values reject store
construction. `max_challenge_id_bytes` is additionally at most unsigned-32.
These are accounting/format domains, not production values; human owners must
still choose materially finite explicit limits. A value node is the root or
any value position in a list/object, including a container; object keys are
bounded separately. Object/list limits are per container. No separate nesting-
depth field is exposed: accepted-tree depth cannot exceed total value positions,
while one-expansion memoization bounds shared/cyclic capture and current A2
traversal without inventing unfolded depth. String/key limits are exact
strict-UTF-8 byte counts. The Strategy
identity-byte limit covers the complete canonical preimage—the fixed domain
header plus root frame, all child frames, keys, and payloads—and thus bounds
aggregate accepted Strategy identity bytes, including integer magnitudes.
For an A3-valid challenge identifier, `max_challenge_id_bytes` counts its exact
ASCII/TLV payload bytes; the capped scan may reject work before making any A3
validity claim.
The final four fields cap simultaneous request-local candidate builds and the
store's aggregate retained record, accepted-value-node, and accepted-identity-
byte footprint. No eviction is implied; exact duplicates remain reads of an
existing record, while a new accepted or permanently rejected submission must
fit before UUID allocation. None of these numeric values enters scientific
identity or the minimum submission record.

Before touching an attacker-sized challenge/Strategy value, A7 non-blockingly
acquires one bounded identity-build permit; exhaustion returns A7-R11's
constant capacity error rather than waiting or starting partial work. After
constant-bounded exact-type wrapper-shape checks, it reads each required
requester/challenge nominal scalar exactly once into request-local primitives.
The captured challenge-ID value is capped before A3 regex validation or fresh
`ChallengeKey` reconstruction, and every later validation, comparison, and
binding step uses those same locals rather than rereading a caller wrapper.

A7 then performs one iterative, non-semantic resource-metered traversal that
constructs a request-local owned, topology-preserving candidate. A memo maps
each exact built-in dict/list identity to one fresh exact built-in container,
so cycles and shared DAG edges survive for A2 while each source container is
expanded at most once. The root and every enumerated item/member value position
consume node budget; a repeated edge consumes its position but is not expanded
again. Container cardinality is checked before enumerating children. Strict-
UTF-8/identity bytes are scanned incrementally with overflow checks without an
unbounded encoded duplicate. A bounded exact string/key that cannot encode as
strict UTF-8 is preserved in the candidate and records a later A7 identity
failure. Invalid UTF-8 alone does not stop capture; a provable configured
resource overrun during that scan may.
An integer `bit_length` precheck rejects when the
complete tag/length/sign/magnitude frame cannot fit the remaining identity
budget, before materializing the exact minimal unsigned big-endian magnitude.
Every counter is checked before the next allocation or expansion, and traversal
stops at the first exceeded limit.

The capture never hashes, compares, displays, or invokes a method on an
attacker-controlled non-string dict key or non-JSON leaf. It represents an
invalid key with a fresh inert A7-owned non-string key plus inert value, and an
invalid leaf with an inert A7-owned value at the same string-key/list position.
These request-local sentinels preserve current A2 type-issue code/path behavior
and can never be accepted, hashed, stored, or exposed. Observed source size,
iteration, or exact built-in access instability fails closed. Concurrent
same-cardinality replacement cannot always be detected: if bounded capture
completes, that detached candidate is authoritative and no later pass rereads
the caller graph; later caller mutation cannot change it.

This operational gate can reject work but cannot declare a Strategy valid.
Only after the bounded detached candidate exists does A7 call the current
`carbon.schema.dry_validate` once on that topology. A2 therefore retains its
fields, validation, issue ordering, and semantics: a copied cycle reaches its
existing `json.cycle` result, and a copied shared DAG remains A2-valid. After an
A2-success result, A7 applies its separately recorded repeated-container and
strict-UTF-8 identity rules; a bounded lone surrogate therefore reaches A2
first, and a shared DAG is rejected by A7 rather than A2.
Only an A2-valid candidate with no repeated container can proceed, so the owned
candidate is then an alias-free tree and is the sole snapshot candidate without
another caller read. It is retained only by the later atomic accepted-record
commit. The copy, frame-size pass, and encoder are iterative; the total-node
limit bounds even deep work. Request-local counters, sentinels, rejected raw input,
and rejected candidates are never retained.

After a complete identity is available, the guarded store resolves an exact
open duplicate before capacity. A new accepted record must fit all three
retention caps; a within-budget semantic/identity rejection must fit the record
cap. Capacity checking, one-candidate UUID generation/collision checking,
record/index insertion, and aggregate-accounting commit are atomic; injected
failure leaves maps and counters unchanged. The identity-build permit is
released on every exit. These caps bound A7's own concurrent and retained
submission memory; later A9 authentication/rate limiting may be stricter but
is not their substitute.

`StrategyHash` is a separate frozen, slotted nominal type exposing only exact
`sha256:<64 lowercase hexadecimal characters>`. Its preimage is the exact
ASCII header `carbon.strategy.identity.v1` followed by one root frame. Every
frame is one tag octet, one unsigned eight-byte big-endian payload length, and
the payload. The tags and payloads are closed:

| Tag | Value | Payload |
|---:|---|---|
| `0x00` | null | empty |
| `0x01` | false | empty |
| `0x02` | true | empty |
| `0x03` | integer | sign octet (`0x00` non-negative, `0x01` negative) then the minimal unsigned big-endian magnitude; zero is sign `0x00` with no magnitude |
| `0x04` | float | exactly eight bytes, IEEE-754 binary64, big-endian |
| `0x05` | string | exact strict UTF-8 bytes, without normalization |
| `0x06` | list | unsigned eight-byte item count followed by each framed item in list order |
| `0x07` | object | unsigned eight-byte member count followed by framed string key and framed value pairs, sorted by each key's exact UTF-8 byte sequence |

Dict insertion order therefore cannot change identity; list order remains
significant. Null, Boolean, integer, float, string, list, and object are
distinct. `1` and `1.0` differ, and the exact binary64 rule also preserves the
distinction between positive and negative zero. A2 already rejects non-finite
floats, cycles, and non-JSON types. An iterative bottom-up pass computes exact
payload lengths with checked unsigned-64-bit arithmetic, then the encoder
checks the configured identity-byte budget before emitting, and streams the
document into one SHA-256 calculation without materializing a second complete
serialized copy. A `StrategyHash` is constructed only after the complete
bounded stream succeeds; no partial digest is stored, exposed, or usable as an
open key. If an otherwise A2-valid Python string cannot be strictly UTF-8
encoded, A7 rejects it safely at the identity boundary; A7 does not invent
WTF-8/surrogate-pass semantics or claim A2 changed. A7 hashes neither `repr`,
generic objects, `json.dumps`, arbitrary serialization, nor transport/raw
request bytes. Encoding failures expose only bounded stable codes/messages,
never submitted values. The injected limits decide whether processing may
finish; for every accepted value they do not change one canonical byte, the
tagged SHA-256, or A4 binding. A2's separate parser/transport resource-limit
policy remains unresolved without weakening this independent A7 boundary.

**A7-R4 — Exact challenge and A4 evaluation binding.** A7 accepts the current
exact `carbon.registry.ChallengeKey` and reconstructs a fresh owned key from
its validated fields before lookup/storage; it creates no weaker
challenge/version type and performs no implicit/default/“latest” resolution.
The validated Strategy's exact `challenge_id` must equal
`ChallengeKey.challenge_id`. The complete key is immutable after acceptance
and every downstream result/pin must match it. As A7-R8 specifies, each new
queue admission through the distinct production or fixture orchestration seam
must consume current A3 admission eligibility. A7 never copies qualification
slots, artifacts, or gate logic and is not another LIVE authority.

A7 supplies A4's missing concrete 32-byte `EvaluationBinding`. The sole
canonical binding-input document starts with exact ASCII
`carbon.a7.evaluation-binding.v1`, followed in order by four safe identity
fields: tag `0x01` `SubmissionId.value`, `0x02` StrategyHash tagged value,
`0x03` challenge ID, and `0x04` exact challenge version. Each field uses A4's
one-octet tag plus unsigned four-byte big-endian payload length framing and
exact ASCII payload. This document is not hidden evaluation content and
contains or derives from no A4 entropy/context/private root, official/master/
derived seed, domain/role/draw, hidden sample/exam ID, or realization. The
binding is the 32 raw bytes of SHA-256 over that versioned identity document,
deliberately adapted into A4 `EvaluationBinding`. It is stable
across retries and changes for a terminal resubmission. Requester/validator
identity, attempt number, retry count, fee, state, time, and randomness do not
enter it. A4 continues to bind generator/scoring pins and future beacon
material separately; this structural adapter does not settle OQ-005/OQ-006 or
production randomness policy. A7 retains it only inside its private safe A4
identity pin; it never stores or exposes a later context, derived seed, draw,
or evaluation realization.

Before full A3 challenge-ID validation/reconstruction, A7 applies the injected
`max_challenge_id_bytes` with a capped no-retained-copy scan. Exceeding it is
A7 resource inadmissibility under A7-R11, not an A3 validity decision. A value
within that budget must still pass A3's unchanged exact grammar; resource
admissibility never makes a key valid. The configured maximum itself may not
exceed `4_294_967_295`, and binding construction still verifies every payload
is representable by the unsigned-32 field length. Canonical UUID, tagged hash,
and A3 version remain otherwise bounded. The injected practical cap does not
alter the accepted `ChallengeKey` or any evaluation-binding byte.

Because `SubmissionId` enters the binding, one logical Carbon intake allocates
the canonical ID exactly once. Every validator evaluating that submission must
receive the same immutable ID and derived binding; validator-local instances
must not independently mint replacement IDs for the same logical submission.
Wave A proves only the single process-local seam. Replication/distribution of
that canonical envelope and multi-validator qualification remain later-owned,
but may not change these bytes.

This reconciles root SPEC's “shared exam identity” with the later Trustless/OQ
submission-binding addendum: validators share the same pinned exam contract,
pack/domain, and one submission-specific A7 binding for a given logical
submission. When combined later with separately governed A4 inputs it
participates in reproducible derivation, but A7 neither selects, contains,
constructs, persists, exposes, nor proves the realization. Different
submissions do not receive an identical realization merely because they share
challenge/generator/scoring versions. The binding remains submission-specific
through `SubmissionId` and StrategyHash; provider/timing/finality policy
remains unresolved under OQ-005/OQ-006.

**A7-R5 — Requester/authentication boundary.** `RequesterIdentity` is a
separate frozen, slotted nominal type wrapping a validated opaque principal
label. Wave A reuses A3 `validate_version`: exact built-in string, 1–64 ASCII
characters under `[A-Za-z0-9]+(?:[._-][A-Za-z0-9]+)*`, with no normalization,
trimming, coercion, aliasing, or case folding. A7 reconstructs a fresh owned
wrapper from the validated value before lookup/storage. Equality supplies
structural binding and idempotency only. It is not production authentication,
a credential/private key, Bittensor address proof, signature verification,
metagraph membership, or chain-registration proof. Those remain later-owned.
This clarification does not rewrite A6's historical pre-A7 language into an
authentication claim.

**A7-R6 — Process-local store, minimum private record, and atomicity.** The
bounded Wave-A store is per-instance, process-local, in-memory, and guarded so
submission creation/open-key lookup, state transition, attempt update, and
fee-event operations are atomic within the process. It makes no database,
restart/crash recovery, migration, retention, interprocess/distributed, or
production-concurrency claim. One private record contains only:

```text
record_schema_version = "1.0"
submission_id
requester_identity
challenge_key
strategy_hash?             # absent until/when identity succeeds
owned_strategy_snapshot?   # accepted submissions only; private, no caller alias
state
admission_kind?             # PRODUCTION | FIXTURE; set with first queue admission
terminal_infra_disposition? # REFUND; fixed at first queue
terminal_infra_operation_key? # reserved with first RUNNING/CHARGE
current_attempt_number?
a4_seed_pin?                 # safe exact A4 SeedPin identity; no seed/context material
execution_environment_pin?   # safe A7 profile/digest reference; no runtime state
running_attempt_handle?      # exact private A7 handle with both owned pins
attempt_history
fee_events
```

The record never contains raw or derived official seeds, entropy, draw IDs,
hidden sample/exam identifiers, hidden evaluation realization, an A4 private root,
duplicated A5 result or scientific values, `ScoreInput`, predictions/references,
backend metrics, A8 runtime result/status/error payloads, stack traces, private
keys/credentials, receipt
signatures/evidence,
leaderboard/logging/metrics/emission fields, or unbounded diagnostics. It does
not expose a public raw-Strategy getter. Stored accepted payloads and private
error details remain private. Operations may return only bounded stable
codes/messages; those are not minimum-record fields. Invalid raw input and
attacker-controlled representations are neither retained nor echoed.

`SubmissionResourceLimits` is immutable store/service configuration, not a
per-submission record field. The store may maintain only constant-size
aggregate permit/record/value-node/identity-byte accounting required by that
policy. Per-request counters, observed sizes, offending category/value, and
attacker-controlled diagnostics are discarded on success or failure. No
per-record resource-policy identifier or mutable counter is justified: the
policy only gates whether identity processing/retention may complete and never
changes an accepted identity or later lifecycle. Operational audit of the
human-supplied configuration remains at the bounded service boundary.

Every caller-supplied nominal boundary value—including `SubmissionId` on
lookup, `RequesterIdentity`, `ChallengeKey`, `FeePolicyKey`, and
`FeeOperationKey`—is exact-type validated and reconstructed field by field
before comparison, dict-key use, or retention. Stored wrappers and returned
wrappers/views/events are separate owned reconstructions. No caller alias can
mutate a record key, open index, challenge/evaluation binding, requester
binding, fee history, or result-read authorization, even through low-level
mutation of a nominally frozen object.

**A7-R7 — Open-submission idempotency.** The exact key is the value tuple
`(RequesterIdentity, ChallengeKey, StrategyHash)`. Open states are exactly
`RECEIVED`, `VALIDATED`, `QUEUED`, `RUNNING`, and `SCORED`. A7 applies the
configured challenge/Strategy resource boundary before A2 validation, owned
snapshot construction, binding representability, and canonical hashing. Only
a safe, complete hash may form the normal key. It then atomically looks up the
open key; an exact open duplicate returns the existing `SubmissionId` and
creates no record, transition, attempt, charge, or other fee event. Only when
the key is absent does A7 generate and collision-check a new ID and insert its
`RECEIVED` record. Within-budget invalid input for which no key can be formed
takes A7-R11's permanent-rejection path only if record capacity remains. An
over-budget or over-capacity request has no new complete stored identity and
neither forms nor occupies an open key, ID, or record. An already-open exact
duplicate returns its existing ID even when new-record capacity is exhausted.
Terminal states are exactly `PUBLISHED`, `REJECTED`, `FAILED_INFRA`,
`FAILED_STRATEGY`, and `CANCELLED`. Terminal records do not block a later
capacity-permitted submit, which creates a new ID. A6 exact duplicate card
writes are post-result storage idempotence and remain wholly separate from
this pre-execution rule.

**A7-R8 — Closed FSM and terminality.** The only structural transitions are:

```text
create                 -> RECEIVED
RECEIVED               -> VALIDATED | REJECTED | CANCELLED
VALIDATED              -> QUEUED | REJECTED | CANCELLED
QUEUED                 -> RUNNING | FAILED_INFRA | CANCELLED
RUNNING                -> SCORED | FAILED_STRATEGY | FAILED_INFRA
RUNNING                -> QUEUED  # explicit infrastructure retry only
SCORED                 -> PUBLISHED | FAILED_INFRA
PUBLISHED              -> <none>
REJECTED               -> <none>
FAILED_INFRA           -> <none>
FAILED_STRATEGY        -> <none>
CANCELLED              -> <none>
```

`RUNNING -> QUEUED` is legal only as one atomic retry operation that closes
the old attempt and creates the next attempt number. `FAILED_INFRA -> QUEUED`
is forbidden: terminal history is never erased. A7-R13 enables all three
cancellation edges only for the exact stored requester binding and denies
every other source state. A7 lifecycle `SCORED` is not A5
`ScoreStatus.SCORED` and means a scientific result is complete. A5 `SCORED` and
`MANDATORY_GATE_FAILED` may satisfy that completion; A5 `PACK_NOT_READY`, pack
or input errors, and computation/infrastructure failures may not.

`RECEIVED -> REJECTED` is structural/identity rejection under A7-R11.
Submission-resource rejection precedes `create`, is not an FSM state or edge,
and therefore never enters this table.
`VALIDATED -> REJECTED` is the closed trusted pre-queue denial seam required by
Build Out. Wave A A7 invokes it only for A3 challenge admission. Later-owned
authenticated payment/authentication adapters may use that existing edge for
an exact denial, but they are not implemented here and may not become a generic
caller-selected reason or transition API. Missing later queue-admission
fee/retry/pin or production-seam configuration is not proof of nonpayment and
instead leaves `VALIDATED` unchanged. This does not include the mandatory
construction-time `SubmissionResourceLimits`. A7 stores
closed `AdmissionKind.PRODUCTION` or `AdmissionKind.FIXTURE` and both exact
safe identity pins atomically with successful first queue admission. The
production operation calls current
`ChallengeRegistry.is_effectively_live(challenge_id, version)` with the stored
exact key fields. The structurally separate fixture-only operation calls
`ChallengeRegistry.assess_live_eligibility(challenge_id, version,
fixture_mode=True).eligible` and requires visibly fixture-only/non-emission
fee/retry values and safe-pin policy. There is no generic mode Boolean,
fallback, or fixture/production relabel path.

A new queue-admission operation first requires exact `VALIDATED`, then checks
eligibility and calls current
`ChallengeRegistry.is_backbone_allowed` with the stored exact key and the
accepted Strategy's exact backbone. A false eligibility or compatibility
result performs `VALIDATED -> REJECTED` before any
attempt/charge/A5/A6 artifact and returns only bounded stable code
`admission.challenge_not_live`, `admission.challenge_not_fixture_eligible`, or
`admission.backbone_not_allowed`. A false eligibility result deliberately
includes a typed A3 registry/artifact failure that the current fail-closed A3
eligibility API catches and converts to false or an ineligible assessment; A7
neither reclassifies A3 reason codes nor copies its gate/allow-list logic.
The terminal state is an admission denial at that exact intake, not requester,
infrastructure-attempt, or scientific blame; a later submit after A3 recovery
gets a fresh ID when record capacity remains. The minimum private record stores
only `REJECTED`, not a reason/diagnostic field. A `RegistryError`/exception
escaping the compatibility call, or any exception escaping eligibility,
mutates nothing and leaves the record `VALIDATED` and uncharged.

Successful admission atomically stores the kind, both safe identity pins,
attempt `1`, and `QUEUED`, but appends no fee event. The only initial exam
charge is coupled to the later first `QUEUED -> RUNNING` material-start
transaction under A7-R10. Therefore an initial queued cancellation that wins
the store race is wholly uncharged; if first start commits first, cancellation
is denied from `RUNNING` and the charge is already recorded.

**A7-R9 — Minimal attempt identity/history.** The initial queue admission
creates attempt number `1`. `QUEUED -> RUNNING` retains that number. The
record keeps only ordered, append-only attempt events sufficient to show the
attempt number and lifecycle event (`QUEUED`, `RUNNING`, `RETRYABLE_INFRA`,
`SCORED`, `FAILED_STRATEGY`, `FAILED_INFRA`, or `CANCELLED`). An explicit
retry appends `RETRYABLE_INFRA` for attempt `n` and `QUEUED` for attempt
`n + 1` atomically; the `SubmissionId`, Strategy hash, ChallengeKey, and A4
binding do not change. Pre-queue rejection/cancellation has no attempt; an
authorized requester-bound queued cancellation closes its attempt with
`CANCELLED`.
Attempt history contains no seeds, predictions, references, scalar metrics,
backend diagnostics, A8 raw runtime result/status/error payloads, or stack
traces. Production retryable
classes/count/budget remain protocol/operations policy, not an A7 constant.

`ExecutionEnvironmentPin` is a narrow private A7 wrapper/comparison of safe
identity references, not ownership of an environment or execution
implementation: a frozen/slotted exact pair of `backend_profile_id` and
`container_digest`. The profile is an exact built-in 1–128-character ASCII
token under `[A-Za-z0-9]+(?:[._-][A-Za-z0-9]+)*`; the digest is exact
`sha256:<64 lowercase hex>`. A7 neither selects nor launches a backend. A8
owns concrete backend selection/configuration, execution/runtime resource
limits, invocation, runtime objects, and raw runtime result/status/error
semantics. No path, mutable configuration, runtime object, metric, runtime
resource limit, or A8 payload enters the pin or attempt record. This is
separate from A7-R3's submission-input resource boundary.

The exact A4 `SeedPin` stored beside it is likewise safe identity metadata,
not seed material: it contains only the owned ChallengeKey, generator/scoring
versions and digests, the A7 EvaluationBinding, and fixed scheme identifier.
It contains no context, entropy, private root, domain/role/draw, derived seed,
or realization.

`ExecutionAttemptHandle` is a private, frozen/slotted, non-serializable A7
handoff containing an owned `SubmissionId`, exact positive built-in integer
attempt number, exact stored `AdmissionKind`, an owned exact A4 `SeedPin`, and
an owned exact `ExecutionEnvironmentPin`. Before the first fixture
queue commit, A7 constructs and validates both pins from the stored
challenge/binding and conspicuous trusted fixture-only generator, Score Pack,
backend-profile, and exact container-digest identity inputs. The same atomic
commit stores both pins, `AdmissionKind.FIXTURE`, attempt `1`, and `QUEUED`
without a fee event. This supplies immutable comparison references without
implementing execution, selecting a runtime, or claiming provenance.

A production caller/orchestrator may not self-assert either pin. After an A3
LIVE result but before production queue/attempt, all production seams
must resolve successfully: an A3-owned adapter binding the exact key to
qualified generator, Score Pack, and backend-profile identities; a
human-qualification-owned backend-evidence adapter binding that profile to an
exact container digest; a separately ratified A5 production-origin/result
path; an A8 handle-aware adapter declaring the exact profile/container it will
execute; and a ratified/configured A4 official-context acquisition policy under
OQ-005/OQ-006. Production completion additionally requires a separately
ratified production-capable A6 private-store/projection path and a later-owned
valid submission/pin-bound evidence/receipt adapter; integrating those changes
requires contract re-ratification. A7 cross-checks the A3, backend-evidence,
and A8 profile values and the qualified/declared container digests, then
constructs both pins before the atomic first queue commit. Although A6 and
receipt checks occur after execution, their ratified configured capability is
required before queue/start so production cannot be knowingly stranded. A8
execution configuration alone is not qualification authority. Actual official
entropy/context is later acquired by the later A8/orchestration adapter through
A4 and is never selected, received, or stored by A7.

Current A3/backend-qualification/A4-policy/A5/A6/A8/evidence surfaces do not
provide that complete set, so bounded Wave-A production remains fail-closed in
`VALIDATED`, uncharged and without an attempt. These prerequisites do not move
qualification, randomness, scoring, or execution into A7. `QUEUED -> RUNNING`
reconstructs the current handle from the retained pins. On attempt `1` only,
the same guarded transaction also appends the sole `CHARGE`, reserves the
distinct terminal-refund operation key, records `RUNNING`, and returns the
kind-specific envelope. A failed precommit first start remains `QUEUED` and
uncharged. A retry start reuses the existing charge and appends no second one.
Both owned pins are immutable for the submission; every retry reuses them
exactly.

A7 stores one owned current handle while `RUNNING` and returns a separate
fresh private, kind-specific `ProductionExecutionEnvelope` or
`FixtureExecutionEnvelope` containing another handle reconstruction, fresh
alias-free Strategy tree, StrategyHash, and ChallengeKey. Separate start
operations reject admission-kind crossing and expose no generic mode switch;
a retry-start envelope changes only the attempt number and never charges.
The stored running handle adds no payload beyond the exact state, attempt,
kind, and safe pins already retained in the record. Retry/terminalization
clears the running handle but retains both pins; history retains only the
number/events above. Every `RUNNING` callback—completion, retryable/terminal
infrastructure failure, or strategy failure—must present the matching current
handle. A wrong/stale handle is a typed no-mutation rejection and cannot alter
a later attempt. That rule governs first application. A7-R10 permits exact
no-mutation replay of a recorded handle-bearing callback only after binding the
supplied historical handle to the event's source attempt. Its separate initial-
start replay is generated-handle aware and returns no envelope or relaunch
authority. The handle proves
only that the trusted adapter returned the current structural context; because
bare A5 `InternalResult` has no submission field, authenticated result
provenance remains later receipt/evidence work.
The envelope/handle is A7-owned plumbing, not execution or an A8
implementation, and neither has a public serialization/projection path.

**A7-R10 — Fee events and score isolation.** Production fee amount, asset,
schedule, and policy version are human/protocol-owned. A7 has no built-in,
fallback, or environment-derived production fee value. Future Wave-A tests
may inject visibly fixture-only policies and amounts. Every amount is an
exact built-in integer number of the supplying policy's minor units; Boolean,
float, coercion, and negative values reject.

The fee-event vocabulary is closed to `CHARGE`, `REFUND`, and
`RETRY_CREDIT`. Its coupled operation context is separately closed to
`INITIAL_RUN_START`, `RETRY`, `TERMINAL_INFRA`, and `PUBLICATION_INFRA`.
`RETRY_CREDIT` and `RETRY` remain representable for a future separately
ratified policy; the bounded Wave-A default defined here never selects them as
the terminal remedy or appends them during retry.
`FeePolicyKey` and `FeeOperationKey` are separate frozen,
slotted nominal types using the exact A3 `validate_version` grammar without
normalization or coercion; A7 reconstructs fresh owned values before event
lookup or retention. The supplying policy key identifies the
human-owned denomination/asset, schedule, and version meaning; A7 does not
invent that meaning. A trusted economic/orchestration adapter—not the raw
miner submit payload—supplies a stable `FeeOperationKey` for each logical
economic operation so transport retries can reuse it. Events are append-only
and monotonically sequenced per submission: the first event has exact built-in
integer sequence `1`, and each next event increments it by exactly one. The
minimum event is sequence, operation key, policy key, kind, exact positive
source-attempt number, exact `AdmissionKind`, exact operation context, integer
minor-unit amount, and an absent-for-charge/required-for-adjustment
charge-operation key. Operation idempotency is scoped to
`(SubmissionId, FeeOperationKey)`: an exact replay of the same
kind/context/admission-kind/source-attempt/amount/policy/linkage returns the
existing event, while reuse of the key with a different payload is a typed
conflict. The `CHARGE` records the existing queued attempt `1`. A submission
has at most one `CHARGE`, appended atomically only with its first
`QUEUED -> RUNNING` material-start transition. Queue admission, cancellation,
and retry start never append a charge. `REFUND` and `RETRY_CREDIT` must
identify that exact charge and use its policy key; neither may exist without
it, and their aggregate adjustments may not exceed its charged amount. The
distinct terminal-infrastructure operation key reserved atomically with the
first charge cannot be used for any other event/context and is consumed only
by the fixed `REFUND` under `TERMINAL_INFRA` or internal
`PUBLICATION_INFRA`. Duplicate open submit and repeat result read never
charge. A7's process-local ledger event does not prove or imply production
payment authorization, reservation, transfer, or settlement; those remain
later-owned. `Miner_MCP.md`'s paid-loop/SubmitReceipt ordering is product and
transport shorthand for that later settlement path; it neither moves A7's
ledger `CHARGE` before material start nor turns the fixture ledger into a
payment receipt. Fee policy/events have no dependency, argument, field, or
conversion path into A5 `ScoreInput`, `ScoreEngine.score`, `InternalResult`,
or later score-to-weight/emission calculation. Fee is never score.

For a transaction that appends a fee event, after safe boundary/submission/key
reconstruction, lookup of an existing `(SubmissionId, FeeOperationKey)` and
replay/conflict resolution precedes policy/configuration, source state,
current handle, and every other fallible operation prerequisite. A3 assessment
belongs to the earlier no-fee queue admission. Only a new operation key reaches
source-state validation; after the required source state is confirmed,
operation-specific handle/policy checks run. Exact
kind/context/admission-kind/source-attempt/amount/policy/linkage replay returns
the already-completed event and makes no state, index, attempt, or fee mutation
even if the record has since advanced or terminalized. If the original operation
required an `ExecutionAttemptHandle`, replay must also supply the exact
historical handle reconstructed from the event's attempt number and the
record's immutable submission/admission/scientific/environment-pin fields; a
different attempt, handle, or payload is a typed conflict without mutation.
Thus a first application still requires the current handle, while a trusted-
adapter exact replay may present its now-historical handle only to retrieve the
prior event.

The initial kind-specific start is the one exception to the
supplied-historical-handle rule because it generates the handle. Its private
result is a closed sum: `STARTED(FeeEvent, ExecutionEnvelope)` on first
application or `ALREADY_STARTED(FeeEvent, SubmissionState)` on exact replay;
the latter has no envelope. The immutable store policy supplies the exact
`FeePolicyKey` and integer amount; the trusted
start adapter supplies a stable charge operation key and a distinct stable
terminal-refund operation key. First application requires exact `QUEUED`,
attempt `1`, no existing charge, and both retained safe pins, then atomically
stores the current handle/refund key, appends `RUNNING` and the
`INITIAL_RUN_START` `CHARGE`, transitions to `RUNNING`, and returns closed
`STARTED` with the fee event plus private execution envelope. A failed
precommit check leaves `QUEUED` unchanged and uncharged.

Exact replay of that start additionally compares the retained refund key,
A4 `SeedPin`, and `ExecutionEnvironmentPin`. It returns closed
`ALREADY_STARTED` with only the prior event/current status and never returns an
execution envelope or authorizes another A8 launch, even if attempt `1` is
still current. A changed key, pin, policy, amount, kind, context, or attempt is
a conflict. Retry starts are no-fee lifecycle operations that reuse the
existing charge and pins. Queue admission and requester cancellation also
append no fee event and therefore have no fee-operation replay claim. No
standalone fee-adjustment operation exists. `complete_and_publish` is not a
fee-operation replay surface even if its single call internally terminalizes
after A6 failure and consumes the reserved refund; repeated completion remains
A7-R14's typed terminal-state error, and the atomic internal event uses
distinct `PUBLICATION_INFRA` context and cannot be retrieved through a
`TERMINAL_INFRA` callback or duplicated.

**A7-R11 — Invalid Strategy and safe rejection.** Resource policy failure is
a pre-identity request/configuration boundary, deliberately distinct from the
permanent FSM rejection below. Missing or invalid mandatory limits fail A7
store/service construction with typed `SubmissionResourcePolicyError` and
constant code
`submission.resource_policy_unavailable`; no production submit path may start
with a guessed fallback. Exceeding any configured Strategy or challenge limit
stops immediately with typed `SubmissionResourceError` and constant code
`submission.resource_limit_exceeded`. Exhausted identity-build or retained
store capacity returns the same typed error with constant code
`submission.resource_capacity_exceeded`. Neither error exposes a category,
limit, observed count/bytes, path, value, or `repr`. A limit overrun allocates
no `SubmissionId` and creates no retained snapshot, complete or partial
`StrategyHash`, open-key entry, or record. A capacity failure may occur after a
bounded complete request-local identity is needed to resolve an open duplicate,
but stores none of it and allocates no ID. Both create no attempt, fee event,
queue admission, A5 result, or A6 card. Neither is `FAILED_STRATEGY`,
`FAILED_INFRA`, A5
`PACK_NOT_READY`, a mandatory gate, scientific zero, or emission blame.

For a resource-admissible request with a valid structural requester, exact
`ChallengeKey`, and available record capacity, every non-duplicate new request
receives a new `SubmissionId` and begins at `RECEIVED`; A7-R7 open duplicates
instead return their existing ID without a new record. If A2 validation,
bounded owned-candidate capture, post-A2 repeated-container identity,
strict-UTF-8 or
frame/binding-representability identity, or Strategy/ChallengeKey challenge-ID
comparison fails before an open key can be formed or found, A7 generates and
collision-checks an ID, atomically inserts `RECEIVED`, and transitions that
record to terminal `REJECTED`. Hash/snapshot remain absent when no accepted
identity can be formed, and the record is not placed in the open-idempotency
index. Rejection occurs before queue admission and before `CHARGE`; it creates
no A6 record/card, A5 result, failed physics gate, scientific zero, attempt, or
emission disposition. Only bounded stable issue codes/messages may cross the
boundary; no raw input, submitted value, `repr`, or unbounded diagnostic is
retained or echoed. Malformed requester/ChallengeKey wrappers are request-
boundary errors before a safely bound submission can be created.

**A7-R12 — Infrastructure retry and terminal `REFUND`.** A retryable
infrastructure fault while `RUNNING` may atomically close the current attempt,
append `RETRYABLE_INFRA`, increment the attempt, and requeue the same
submission. Retry never creates a new SubmissionId, changes scientific
identity, or creates a second exam charge. The bounded Wave-A policy appends
no retry fee event. `RETRY_CREDIT` remains a supported schema vocabulary item
only for a future separately ratified policy; it is not the current retry or
terminal default. Retryable classes/count/budget remain human-owned rather
than an A7 constant.

If recovery is not performed, is unavailable, or that explicit retry budget
is exhausted, the submission terminalizes as `FAILED_INFRA`. The ratified
terminal economic default is **`REFUND`** for exactly the full remaining
charge balance: original charge minus any prior adjustment authorized by a
future ratification. A terminal failure from initial `QUEUED` before any
`RUNNING` start has no charge and therefore appends no refund event. A
terminal failure from charged retry-`QUEUED`, `RUNNING`, or `SCORED` appends
the linked `REFUND` atomically with terminalization; A6 publication failure
uses `PUBLICATION_INFRA`, while the other paths use `TERMINAL_INFRA`.

The A7 store's injected fee/retry policy and fixed terminal default are
immutable for that store's lifetime; reconfiguration requires a new store.
First queue admission requires complete fee/retry configuration, both valid
kind-specific pins, and, for production, every A7-R9 production seam, but it
remains uncharged. First start validates the supplied stable charge and
distinct refund operation keys before atomically storing the refund key,
charging, and entering `RUNNING`; missing configuration/key material leaves
the record `QUEUED` and uncharged. No charged `RUNNING`/`SCORED` record can be
stranded by missing terminal economics. The `.agent/WAVE.md` parenthetical
“FAILED_INFRA refund” now agrees with this selected default but does not imply
implementation.

No infrastructure path constructs a physics gate, scientific zero, A5
scientific failure, EvaluationCard, or emission blame. Partial/private
operational evidence remains with its authorized later owner and is never
stored as A7 science.

**A7-R13 — Requester-bound, no-event cancellation.** `CANCELLED` is terminal.
The bounded Wave-A cancel operation exact-type validates and reconstructs the
supplied `SubmissionId` and `RequesterIdentity`, then under the A7 guard
requires structural equality with the submitting requester. Only that stored
requester binding may request cancellation, and only from `RECEIVED`,
`VALIDATED`, or `QUEUED`. Cancellation from `RUNNING`, `SCORED`, `PUBLISHED`,
`REJECTED`, `FAILED_INFRA`, `FAILED_STRATEGY`, or `CANCELLED` is denied without
mutation. No validator/operator cancellation path exists.

Cancellation appends no fee event: it creates neither `CHARGE` nor `REFUND`.
An initial queued attempt that has never entered `RUNNING` is therefore
cancelled wholly uncharged. A retry-queued submission already has the sole
material-start charge; cancellation creates no new fee event and leaves that
prior charge unchanged. If infrastructure terminalization wins the guard
instead, A7-R12's `FAILED_INFRA` refund applies. A queued cancellation may
append only the minimal `CANCELLED` attempt event.

Start, terminalization, and cancellation race atomically under the same store
guard: whichever legal transition commits first wins. A stale cancellation
request fails safely and cannot regress state; if initial start wins, its
charge and `RUNNING` state commit together and cancellation is denied. If
cancellation wins, start observes terminal `CANCELLED` and creates no charge.

This structural requester comparison is the complete bounded Wave-A policy,
not production authentication, signature/Bittensor proof, payment
authorization, reservation, transfer, or settlement. Any later external
production cancellation surface must first bind an authenticated actor to the
stored requester under its separately owned adapter; the policy does not make
structural equality a production credential.

**A7-R14 — A6 publication adapter.** Each A7 store exclusively owns the
dedicated A6 `CardStore` containing its cards, exposes no direct store
reference, and performs every A6 read/write under the same A7 guard. A
production caller cannot inject or retain a side reference; an internal
failure-test seam must transfer exclusive ownership. This closes the otherwise
observable interval between A6 insertion and A7 `PUBLISHED`.

`SubmissionId.value` is deliberately reconstructed into a new
`CardRecordKey`, and `RequesterIdentity.value` into a new
`RequesterAuthorizationKey`; none of those nominal types is aliased. The sole
scientific-completion operation is conceptually
`complete_and_publish(ExecutionAttemptHandle, InternalResult)`. It first
requires the matching stored current handle; a wrong/stale handle returns a
typed safe error without state or A6 mutation. With a matching handle, A7
explicitly reconstructs one fresh, recursively owned exact A5 graph through
current A5 model constructors and retains it only for this call.

Before lifecycle `SCORED`, A7 verifies all available structural attribution:
the result `ScorePackPin.challenge_key`, scoring version/digest, and required
generator version/digest must equal the stored handle's A4 `SeedPin` fields;
that pin already contains the stored ChallengeKey and A7-derived
EvaluationBinding. The matching handle must also retain the exact stored
`ExecutionEnvironmentPin`; no lifecycle score exists without both pins.
Fixture admission additionally requires the exact A5 fixture-origin result;
production admission cannot relabel that fixture result as production. A
matching-handle reconstruction/pin/integration failure is operational while
`RUNNING` and follows the retryability decision or `RUNNING -> FAILED_INFRA`;
it never becomes `FAILED_STRATEGY`, a physics gate, or a scientific zero.

Current A5 constructors accept only fixture-origin pins/results. The narrow A7
environment pin permits a structurally bound fixture happy path with
conspicuous non-emission inputs, but does not claim that execution occurred or
authenticate provenance. Current A6 is likewise fixture-only, and authoritative
production results require a valid later-owned submission/pin-bound receipt.
Therefore this two-argument `complete_and_publish` is fixture-only. Production
completion/publication remains unavailable and fail-closed until every A7-R9
production seam exists and a future contract re-ratifies a receipt-gated,
production-capable A6 operation. A7 must not fabricate any seam or publish a
fixture result as production.

Only completed A5 `SCORED` or `MANDATORY_GATE_FAILED` may record
`RUNNING -> SCORED`. A5 `PACK_NOT_READY` and pack/input/computation errors use
the same retry/infrastructure path and cannot be published. A7 exposes no
independent mark-scored operation, later publish method accepting another
result, or record field containing a duplicate result/digest/token. With the
same reconstructed completed result and while still holding the guard, A7
records `SCORED`, clears the running handle, and calls
`CardStore.write_internal`. `INSERTED` and exact `ALREADY_PRESENT` permit
`SCORED -> PUBLISHED`; only A6 conflict/store failure after that point follows
`SCORED -> FAILED_INFRA` and appends the fixed remaining-balance `REFUND` under
`PUBLICATION_INFRA`. A published result and `FAILED_STRATEGY` retain the sole
material-start charge; neither receives an infrastructure refund. A repeated
completion call after any terminal state is a typed no-mutation terminal-state
error; callers use the status/read seams. The in-memory contract makes no
cross-store crash-transaction claim.

The bounded status seam is
`get_status(SubmissionId, RequesterIdentity) -> SubmissionStatusView`. It
reconstructs both lookup values, verifies structural requester equality, and
returns fresh owned values containing only `submission_id` and current
`state`; it exposes no Strategy/hash, attempt/history, fee, rejection reason,
result, pin, or diagnostic. Terminal records therefore remain safely
queryable. The bounded card seam is
`read_published(SubmissionId, RequesterIdentity) -> EvaluationCard`. It
requires exact `PUBLISHED`, deliberately adapts fresh A6 keys, and delegates
to `CardStore.read_budgeted`. Both repeat operations are fee-free. A7 never
bypasses A6 authorization/projection or returns `InternalResult`; A9 later
owns transport.

**A7-R15 — Reconciliation, dependency boundary, and implementation gate.**
The stale ticket API is repaired from bare `hotkey`/`challenge_id` to
`RequesterIdentity` plus exact `ChallengeKey`, and its focused path is
`tests/cpu/test_submission_fsm.py`. Future A7 core has no dependency on A8,
A9, A10, A11, Bittensor, an optional scientific backend, or a new runtime
package. Standard-library dataclasses/enums, `hashlib`, `struct`, `uuid`, and
process-local synchronization are preferred. Current A2–A6 types are kept and
wrapped; legacy timestamp IDs, `carbon.protocol.StrategySynapse`,
`carbon/common/model_card.py` hashing/storage, PoC hashing, and historical
queue sketches are not promoted as A7 authority.

Existing A3/A5 fixtures cannot form the A7 happy path unchanged: the registry
fixture's `synthetic_backbone` is outside A2's accepted backbone vocabulary and
the A5 fixture has a different challenge identity. Future A7 tests must build
an in-test or A7-owned conspicuous non-emission fixture whose exact
ChallengeKey, A2-valid backbone, Score Pack pin, both A7 pins, and A5 result
align. That test data must not change A2–A6 semantics or masquerade as LIVE.

The untouched A8 ticket still proposes a generic `mock|official` mode and raw
status vocabulary without A7 handles. Before A8 integration, its own
pre-implementation ratification must reconcile to A7's kind-specific envelopes,
current-handle callbacks, immutable A7 environment pin, and exact
mapping into `FAILED_STRATEGY`, retry, or `FAILED_INFRA`. This is a recorded
future interface dependency, not A8 work in this ratification. In particular,
A8 `invalid_strategy` may not reclassify schema or exact-key backbone
compatibility that A7 must deny before queue.
A later A8 adapter serving `AdmissionKind.FIXTURE` may consume only A4
`FixtureOfficialContext` through the fixture-official derivation path—never
MOCK or provider-official context. A later A8 adapter serving
`AdmissionKind.PRODUCTION` may consume only provider-acquired
`OfficialContext` through official derivation after OQ-005/OQ-006 resolution.
A7 receives neither context nor any derived seed/runtime payload.

The untouched A12 invariant ticket also omits its necessary A7 dependency even
though it promises fee-versus-score coverage. Its own later ratification must
depend on completed A7 and reuse A7's fee-isolation contract/tests rather than
inventing another fee path. This records a future ticket repair only; it does
not start or edit A12.

Implementation may begin only after this documentation is independently
reviewed, explicitly human-authorized, merged, and a fresh
main/concurrency/status check confirms A7 remains `todo` and unstarted. A
production-capable path necessarily requires explicit human-owned
`SubmissionResourceLimits`, fee amount/denomination/schedule/version, and
retryable classes/count/budget. Missing resource limits prevent executable
production store construction rather than falling back. The A7-R12 `REFUND`
default and A7-R13 requester-bound cancellation policy are now fixed by human
authorization. The remaining human inputs are not sufficient without the
complete A3/backend-qualification/
A4-OQ-005/OQ-006/A5/A6/A8/evidence production seams and required
re-ratification recorded above. A bounded Wave-A implementation may instead
use conspicuous injected finite fixture-only submission limits and fee/retry
values under those fixed terminal/cancellation semantics and keep every
production path fail-closed. No A7 checkbox, `.agent/WAVE.md` status, Python,
test, fixture, dependency, package, or A8+ implementation changes through this
ratification alone.

## 2026-08-22 — A6 closure after reviewed merge

**Implementation topology and review.** The bounded implementation started from
exact base `bfb8412d9aae3782d59e9814fc5b3a8c6379f86f` and was independently
reviewed at exact commit `569d450cce5943089874ad89f62f80ab5182d97a`.
It was synchronized with current main at exact head
`20a1d2f74f10b24ddb8922c6b87c7325828299b3`, then PR #23 merged normally as
`5c7c3a924d305a386ed92d6f054981761d5c74b7`. The merge has ordered parents
`40c58a1578c6d16ded4ec147561455df66859697` then
`20a1d2f74f10b24ddb8922c6b87c7325828299b3` and exact tree
`d302aaf46f211030faf81920deee4dff27eac4a4`. Both reviewed heads are ancestral
to current `main`; the synchronized-head tree is exactly the merge tree. The
implementation blobs remained exact through synchronization and merge:

- `.agent/WAVE.md` — `726b0316c0d569277eec6e2afde62a092bf1723b`;
- `carbon/cards/__init__.py` —
  `adee9ea56d32327abfc51c5fc9567dff2789d275`;
- `carbon/cards/model.py` —
  `82cdd5d790b41cfb4d1824d83a58dbf4ab29d897`;
- `carbon/cards/store.py` —
  `f91f84dd3c596fb6de4feee733dc26e9d794f005`; and
- `tests/cpu/test_card_store.py` —
  `b9a02f03eb40af35d57304d8e48c3d8721b8167b`.

GitHub contains no formally submitted approval object, and this record does not
claim one. Independent exact-head audits found no P0, P1, or P2 issue, and the
human ready-and-merge authorization expressly covered the exact synchronized
head. No amendment, conflict resolution, repair commit, squash, or rebase was
made or required.

**Exact implementation scope and bounded behavior.** The implementation delta
was exactly `.agent/WAVE.md`, `carbon/cards/__init__.py`,
`carbon/cards/model.py`, `carbon/cards/store.py`, and
`tests/cpu/test_card_store.py`. It provides the separate opaque A6 record and
requester-binding types, recursively owned exact-A5 snapshots, one four-field
process-local insert-only private record, exact duplicate/conflict behavior,
authorization before projection, typed safe errors, and a frozen positive
Phase-0 disclosure allow-list for all three A5 statuses. All eleven ticket DoD
items are materially satisfied. No generic private-object serialization,
private getter, rich Model Card, receipt/evidence layer, or A7+ implementation
entered the boundary.

**Validation and CI evidence.** Python 3.11 passed the focused A6 suite at
`181 passed`, the related scoring/leakage/package boundaries at `499 passed`,
the complete default CPU suite at `1104 passed`, and the isolated fresh
no-dependency wheel/outside-tree proof at `1 passed`. Strict Ruff and Black
checks passed for all four implementation Python files. The quality ratchet
reported `Ruff 757/776; Black 62/68`, removed debt `Ruff 19, Black 6`, four
clean changed Python files, and no new debt. PR CI run `32550337528` completed
successfully on the synchronized head: CPU passed `1104` tests in `21.97s`,
and Code quality reported the same inventory and clean/no-new-debt result.
Post-merge push CI run `32551173696` completed successfully on exact merge
`5c7c3a924d305a386ed92d6f054981761d5c74b7`: CPU passed `1104` tests in
`18.65s`, with the same quality inventory, four changed Python files, and no
new debt.

**Closure and residual boundary.** A6 is done only for the bounded process-local
Wave-A scope. The store remains in-memory and non-durable, with no restart/crash
recovery or production concurrency qualification. Same-process Python is not a
security sandbox; requester equality is not production authentication; and the
fixture-origin label is not authenticated ScoreEngine provenance. Current
fixture results remain non-LIVE, non-production, and non-emission-authoritative.
Permanent submission identity/authentication, fees/FSM/retry/refund, execution,
receipts/evidence, MCP transport, leaderboard, logging/metrics, Bittensor, and
emission behavior remain A7–A12 or later work.

```text
A6 SPECIFIED / RATIFIED: YES
A6 IMPLEMENTED: YES on current main
A6 TESTED: YES only to the bounded recorded CPU/security/import scope
A6 PRODUCTION-QUALIFIED: NO
A6 WAVE STATUS: done after this closeout is merged
```

A6-R1 through A6-R12 below remain unchanged; this closure supersedes only their
pre-implementation maturity snapshot.

## 2026-08-22 — A6 pre-implementation card-store/disclosure ratification

**Repository truth and maturity.** A fresh fetch and independent remote read
resolved `origin/main` to exact commit
`dfd9bcc74434d2ddb5fc1862a9bdfd7ba5c64450`; the initial checkout and local
`main` matched it. GitHub reported no open pull request, and the fetched remote
had no competing A6 branch. A6 and A7–A12 were `todo`, `carbon/cards/` contained
only its A0 marker, and there was no A6 plan, source, test, fixture, or
dependency. This entry is documentation, not implementation. The resulting
contract has exactly this maturity:

```text
A6 SPECIFIED / RATIFIED: YES only after this ratification is merged
A6 IMPLEMENTED: NO
A6 TESTED: NO
A6 PRODUCTION-QUALIFIED: NO
A6 WAVE STATUS: todo
```

**A6-R1 — Bounded ownership.** A6 owns only private exact-A5-result storage,
the requester-authorization binding, storage conflict behavior, the immutable
miner-facing `EvaluationCard`, and its Phase-0 disclosure projection. A7 owns
permanent `submission_id`, strategy identity/hash, authenticated
requester/hotkey integration, fees, FSM, retry/refund, concrete evaluation
binding, and submission idempotency. A8+ owns execution/backend semantics; A9
MCP transport; A10 leaderboard; A11 logging/metrics; and A12 invariant-CI
integration. Receipt, signature, execution transcript/evidence, durable
evidence ledger, Bittensor, score-to-weight, and emission work remain
later-owned.

**A6-R2 — Opaque pre-A7 identity seam.** A6 uses two separate frozen nominal
types, `CardRecordKey` and `RequesterAuthorizationKey`. Each wraps an exact
built-in string accepted without normalization by A3's bounded 1–64 ASCII
`validate_version` token contract. Neither type claims to be A7's production
`submission_id`; the requester type is an opaque binding label, not a
credential/private key, signature proof, Bittensor address validator, or
production hotkey-authentication protocol. A7 may later supply its validated
permanent identifier and authenticated requester through this boundary.

**A6-R3 — Wave-A persistence.** The ratified A6 store is per-instance,
process-local, in-memory, and insert-only. It makes no production-durability
claim. Filesystem/SQLite/database storage, retention, migration, restart/crash
recovery, corruption recovery, interprocess/distributed operation, and
production concurrency qualification are deferred.

**A6-R4 — Exact private record.** One frozen private record has exactly
`record_schema_version = "1.0"`, the `CardRecordKey`, the
`RequesterAuthorizationKey` binding, and the exact recursively valid A5
`InternalResult`. A6 stores that result rather than duplicating any status,
pin, score, gate, component, fixture, or eligibility field into another
scoring schema. It stores no strategy, seed/draw/private-evaluation-binding
material, prediction/reference, fee/FSM state, receipt/evidence, separate
backend/internal diagnostic source, timestamp, or later-owner field. The exact
result's evaluated gate decisions remain intact. A successful first write
explicitly reconstructs a fresh, recursively independent exact-value graph and
retains no caller-owned mutable object reference; no private-record/result
getter exists.

**A6-R5 — Insert and conflict semantics.** The first valid write returns the
inserted disposition. Repeating the same key with the value-equal exact
requester binding and exact A5 result is a storage-idempotent no-op. Reusing
the key with any different requester binding or result raises typed
`CardConflictError` and leaves the first record unchanged. A6 exposes no
overwrite, update, delete, rollback, rebind, mutation, or supersession API.
This post-result duplicate rule neither hashes strategies nor finds/creates a
submission and is explicitly distinct from A7 submission idempotency.

**A6-R6 — Positive immutable projection.** Authorization succeeds before any
public projection is constructed. The projection creates frozen, recursively
immutable public values by naming and copying each approved field directly.
It must not use generic `dataclasses.asdict`, model/dict/JSON serialization,
`__dict__`/introspection, private-object dumps followed by deletion, or any
other deny-after-serialization operation on a private/store object to create
that projection. Unknown/new private fields default to private until an
explicit reviewed public-schema change. A9 may later encode an already-public
card under its separately owned transport contract.

**A6-R7 — Exact Phase-0 public schema.** `EvaluationCard` has exact public
`schema_version = "1.0"` and exact `disclosure_tier = "phase0_budgeted"`.
Its remaining allow-list is:

- `result_id`: the successfully authorized `CardRecordKey.value`, the sole
  allowed storage-identity projection and never named `submission_id`;
- `status`: the exact stored A5 status value;
- `scoring_pack_hash`: exact stored
  `InternalResult.pack_pin.scoring_digest`, the external tagged SHA-256, never
  a recomputed or generator/internal-pin value;
- `overall_score`: exact stored `combined_score` when present, else `None`;
- `component_scores`: only an immutable `physics`/`robustness`/`accuracy`
  object built from the three top-level `LegScore.score` values for `SCORED`,
  else `None`; never fine `ScalarScore` components;
- `gate_results`: the complete evaluated A5 vector in stored order, with only
  `gate_id` and `passed` per item;
- `failure_tags`: `("mandatory_gate_failed",)` only for
  `MANDATORY_GATE_FAILED`, otherwise `()`;
- `fixture_origin`: exact stored `pack_pin.fixture_origin`;
- `eligible_for_emission`: exact stored A5 value; and
- `public_diagnostics`: the exact empty tuple required by A6-R8.

**A6-R8 — Diagnostics and failure tags.** Bounded Wave A has no authorized
public diagnostic source. `public_diagnostics` is always `()`; exception text,
backend diagnostics, result representations, and arbitrary strings are never
promoted. The only currently approved failure tag is the status-derived exact
literal `mandatory_gate_failed`. There is no severity, free text, per-regime
tag, or `PACK_NOT_READY` failure tag. Any richer diagnostic/tag source requires
a separately reviewed, versioned disclosure decision.

**A6-R9 — Scientific statuses versus operational errors.** A6 preserves only
A5 `SCORED`, `MANDATORY_GATE_FAILED`, and `PACK_NOT_READY` as public card
statuses. `PACK_NOT_READY` has no score, components, gates, or failure tag and
is not scientific failure. Malformed/tampered input, not-found, authorization
denial, store conflict/infrastructure error, and projection error use the
respective typed `CardRequestError`, `CardNotFoundError`,
`CardAuthorizationError`, `CardConflictError`, `CardStoreError`, and
`CardProjectionError`, with safe non-echoing codes/messages. They do not create
a card, failed gate, scientific zero, or A5 status. A6 does not introduce
`FAILED_INFRA`; A7/A8 own that FSM/backend disposition.

**A6-R10 — Private retention, forbidden disclosure, and default-private rule.**
The exact private record necessarily retains its schema/key/requester fields
and the full nested A5 result, including private pin, gate, and fine component
metadata; A6 never duplicates those values into parallel fields. The public
path is a closed positive allow-list. Of the A6 storage/authorization metadata,
it exposes only authorized `CardRecordKey.value` as `result_id`; of the full
private A5 pin, it exposes only `scoring_digest` as `scoring_pack_hash` and
`fixture_origin` as the same-named public field. It does not expose their
wrappers or surrounding metadata. It never discloses raw/derived seeds,
entropy, draw/sample/exam IDs, private evaluation binding, raw strategy/model/
predictions/references, `ScoreInput` values or
keys, thresholds, margins, fine `ScalarScore` vectors, per-stress/per-regime
numeric breakdowns, generator digest or other internal pin metadata beyond
those two approved pin projections, internal/backend diagnostics or
exceptions, requester/authorization/storage metadata,
receipt/signature/evidence internals, fees/FSM/retry state, private keys/
credentials/secrets, or later-owner metadata. Unknown/new private fields stay
private. Public exceptions and later logs never include hostile keys or
private result representations.

**A6-R11 — Fixture and emission boundary.** `fixture_origin` and
`eligible_for_emission` are copied only from the stored exact A5 result. There
is no caller override, fallback, relabel, or A6 eligibility computation.
Current A5 accepts only fixture-origin packs and mechanically produces false
eligibility; A6 therefore cannot describe a current result as production,
LIVE, authenticated provenance, emission-authoritative, or eligible.

**A6-R12 — Hostile-input, reconciliation, and implementation gate.** Treat
record keys, requester keys, stored input, and public requests as hostile:
require exact nominal/canonical types, recursively enforce current A5
invariants, construct a safe owned candidate before any lookup or comparison,
compare only owned validated values, retain no caller-mutable aliases,
authorize before projection, fail closed, and never invoke attacker-controlled
display hooks in errors. `Build_Out.md` rich Model Card language is future
shorthand, not the A6 record; `Miner_MCP.md` A7/A9 metadata
is later response-envelope enrichment; and transcript/receipt/evidence designs
remain later architecture rather than optional A6 scope. Historical Model
Card/PoC/result stores are non-authoritative archaeology and cannot be wrapped
to bypass this contract. A6 implementation may begin only after this
documentation is independently reviewed, human-authorized, merged, and a
fresh main/concurrency/status check confirms A6 is still `todo` and unstarted.
No checkbox or Wave status changes through ratification alone.

## 2026-08-22 — A5 closure after reviewed merge

**Merge topology and review.** The bounded implementation started from exact
base `af43d68ec3b9dcfd8818a61ab219759b2c859d78` and was independently reviewed
at exact head `fc2f27a7150d5ed0e374e7cd79eea40ef7ede556`. PR #20 merged normally as
`6f813e979ef6edde2b8f1821d1ac26f62938633a`, with tree
`54e3472e34731b64d796f8db7d091da70c6afd43` and ordered parents
`af43d68ec3b9dcfd8818a61ab219759b2c859d78` then
`fc2f27a7150d5ed0e374e7cd79eea40ef7ede556`. The reviewed head is ancestral to
current `main`, and its tree is exactly the merge tree. GitHub contains no
formally submitted approval object, and this record does not claim one;
independent reviews and explicit human authorization are the process evidence.
No amendment or repair commit was made or required.

**Exact-head review evidence.** PR CI run `32474141634` completed successfully
for reviewed head `fc2f27a7150d5ed0e374e7cd79eea40ef7ede556`. Its CPU job passed
`923` tests in `9.57s`; Code quality reported `Ruff 757/776; Black 62/68`,
removed debt `Ruff 19, Black 6`, eight changed Python files, no new debt, and
all changed Python files clean.

**Post-merge evidence.** Push CI run `32494936120` completed successfully for
the exact merge commit. The CPU job passed `923` tests in `10.23s`. Code quality
reported `Ruff 757/776; Black 62/68`, removed debt `Ruff 19, Black 6`, eight
changed Python files, and no new debt, with every changed Python file clean.
The sole canonical fixture remains
`tests/fixtures/score_packs/a5_fixture_v1.json`, exactly 2,126 bytes, with
external digest
`sha256:255923831905a84f55a88d8575e8ebcab42f3351676d6cf5ac9038dcc495fb57`.

**Closure and boundary.** A5 is **SPECIFIED / RATIFIED: YES**,
**IMPLEMENTED: YES on current `main`**, and **TESTED: YES only to the bounded
fixture CPU scope**; it remains **PRODUCTION-QUALIFIED: NO**. **WAVE STATUS:
`done` after this closeout is merged.** The merge and this documentation-only
closeout added no dependency or lockfile, A6 or later behavior, LIVE or
production-origin pack, or emission-authoritative path. Passing regression CI
is evidence for the merged bounded implementation, not LIVE, scientific,
emission, or production qualification. A5-R1 through A5-R14 remain unchanged.

## 2026-08-21 — A5 bounded fixture implementation evidence

**Scope and disposition.** The authorized implementation branch
`agent/a5-scoring-engine` starts from exact main
`af43d68ec3b9dcfd8818a61ab219759b2c859d78`. It preserves A5-R1 through
A5-R13 and implements the maintainer-authorized A5-R14 clarification in this
same branch. The implementation **KEEPS / WRAPS** A3 identity validation and
descriptor-relative secure artifact access, **REPAIRS** that public boundary
narrowly to return one bounded digest-verified byte sequence, and **REPLACES**
legacy scoring only as canonical authority without modifying legacy files.
No A6+ owner, dependency, production-origin pack, LIVE path, or emission path
is added.

**Bounded artifact and behavior.** The branch contains the init-closed
fixture-only pack/input/result models, strict digest-first schema-1.0 JSON
loader, clarified `ScoreEngine.score(ScoreInput | None, LoadedScorePack)` entry,
complete declared-order gates, exact scalar transforms, and fixed-order
`python_binary64_v1` log-space aggregate. The sole runtime fixture is exactly
2,126 bytes at `tests/fixtures/score_packs/a5_fixture_v1.json`; its required
external digest is
`sha256:255923831905a84f55a88d8575e8ebcab42f3351676d6cf5ac9038dcc495fb57`.
The digest is absent from the JSON, all values/identities are visibly
synthetic, and every result is structurally false-eligible.

**Acceptance and maturity.** Python 3.11.11 passed the focused A5 suite at
`279 passed in 0.45s`, the related registry/package/leakage suite at
`195 passed in 4.07s`, and the complete default CPU suite at
`923 passed in 5.04s`. Compilation, eight-file Ruff/Black checks, the repository
quality ratchet, built-wheel outside-tree import/scoring isolation, and diff
hygiene passed. Independent final review found no remaining P0/P1/P2 issue.
Therefore A5 is **SPECIFIED / RATIFIED: YES**, **IMPLEMENTED: YES on the bounded
draft branch head**, **TESTED: YES only for the recorded fixture CPU scope**,
and **PRODUCTION-QUALIFIED: NO**. Wave status remains `in_progress`; merge,
`done`, closeout, A6, and later work require separate authorization.

## 2026-08-21 — A5 pre-implementation scoring contract ratification

**Status, base, and scope.** An independent GitHub read and a fresh local
fetch both resolved `origin/main` to exact commit
`3d80e09549964251833b0d8a70093cfceb51a501`. At that point GitHub reported no
open pull request and no remote branch matching A5 or scoring work. The
canonical `carbon/scoring/` package contained only its A0 marker; no A5
engine, model, loader, runtime Score Pack, default-CPU A5 test, or A5 plan
existed. On that repository truth, the maintainer ratifies A5-R1 through
A5-R13 below as the bounded implementation contract for future A5 work.

This entry is documentation, not implementation. A5 remains `todo`, not
`in_progress`; every A5 Definition-of-Done item remains unchecked. No Python,
fixture artifact, test, or dependency is added by this ratification. A5 is
**SPECIFIED / RATIFIED**, but it is **NOT IMPLEMENTED**, **NOT TESTED**, and
**NOT PRODUCTION-QUALIFIED**. A6 and all later tickets remain out of scope.

**A5-R1 — Canonical runtime artifact.** The canonical runtime Score Pack is
one strict UTF-8 JSON byte sequence. The runtime loader accepts no YAML and
adds no YAML dependency. YAML may be used only before publication as an
authoring or documentation form; a separately reviewed conversion must
produce the JSON bytes that are actually pinned and loaded. Runtime validation
rejects a UTF-8 BOM, invalid UTF-8, duplicate object keys, non-JSON numeric
constants, trailing data, a non-object top level, missing required members,
unknown members, and type-invalid members. Parsing or reserialization never
redefines the artifact identity.

**A5-R2 — Exact bytes and external digest.** Pack identity is the exact source
bytes together with a required external tagged SHA-256 in A3's only accepted
form, `sha256:<64 lowercase hexadecimal characters>`. The expected digest is
not read from or trusted to a field inside the bytes. It is checked against
SHA-256 of the untouched bytes before UTF-8 decoding and JSON parsing.
Whitespace, line endings, member order, and every other byte therefore affect
identity. There is no self-reported `content_hash`, content-hash stub,
path-only identity, hash of parsed/normalized content, fallback pack, or
missing-digest fallback.

**A5-R3 — Complete exact pin.** One immutable A5 pack pin binds all of:

- exact A3 `ChallengeKey` — challenge ID and exact challenge version;
- exact scoring version and the A5-R2 external scoring digest;
- exact required generator version and tagged generator digest;
- exact Score Pack schema version;
- exact numerical-profile identifier `python_binary64_v1`; and
- exact Boolean `fixture_origin`.

Every field is required, exact-match, and non-defaultable. Generator and
scoring versions reuse A3 `validate_version`; tagged digests reuse A3's exact
digest contract. A5 adds no separate `gate_version`: hard-gate definitions and
thresholds are already bound by the exact Score Pack bytes. The loaded pack,
external registry/loader expectation, and `ScoreInput` pin must agree exactly
before any scientific gate is evaluated.

**A5-R4 — Closed validator-authorized scalar input.** A5 accepts only an
immutable, validator-authorized `ScoreInput` whose schema is closed and whose
payload contains the exact A5-R3 pin plus the complete scalar values required
by that pack. Expected gate/component keys must match exactly; missing,
duplicate, extra, aliased, or unknown keys reject. Free-form metric mappings,
arrays, tensors, predictions, references, raw draws, raw percentiles, and
miner-supplied values are not `ScoreInput`. Prior similarity,
`estimate`/`light_*`, exam fee, mock-only metrics, product-battery results, and
any other forbidden field are rejected rather than ignored. A8 or later
validator-owned metric operators own model execution, predictions,
references, relative-error generation, raw percentile computation, and
construction of an authoritative scalar `ScoreInput`.

**A5-R5 — Binary mandatory hard gates.** Hard-gate decisions are binary.
Resolved threshold gates pass if and only if the validated binary64 actual is
strictly less than the validated binary64 threshold; equality fails. A
validator-authorized Boolean predicate gate passes only on exact `True`.
Before decision, the mandatory gate set and its actuals must be complete. Any
actual failure of a mandatory gate atomically requires both
`combined_score = 0.0` and `eligible_for_emission = False`. A sigmoid may be a
non-emission diagnostic or a soft-leg transform, but it never determines an
official hard-gate pass. A zero soft leg is distinguishable from a mandatory
gate failure even though both can yield a zero combined score.

**A5-R6 — Configuration/input/infra is not scientific failure.** A missing or
malformed pack, absent/mismatched external digest or pin, malformed or
incomplete `ScoreInput`, unknown field, and infrastructure/reference failure
are non-scientific failures. They create no synthetic failed gate and no
scientific zero. Infra/reference statuses cannot construct authoritative
`ScoreInput` or enter `ScoreEngine.score`. Those cases return or propagate a
typed non-scoring error with no combined score and a non-emitting disposition;
they do not produce `MANDATORY_GATE_FAILED`.

**A5-R7 — Weighted-geometric top level and exact weights.** The only A5
top-level aggregate is the weighted geometric mean. The pack is the sole
source of the weight map. Every weight is a strictly positive JSON number;
the original JSON number values are validated with exact decimal arithmetic
to sum exactly to decimal `1` before binary64 conversion. The key set must
match the score-bearing top-level legs exactly. Missing, extra, zero,
negative, non-finite-after-conversion, or non-unit-sum weights reject. The
engine never normalizes, renormalizes, clamps, defaults, or substitutes
weights. The same no-default rule applies to required within-leg weights where
the pack schema uses a unit-sum weight map. Decimal unit-sum validation uses
`decimal.Decimal` source lexemes and exact common-base-10 integer coefficient
addition derived from `Decimal.as_tuple()`; it is independent of ambient
decimal context and never uses a binary64 tolerance. The 0.45/0.30/0.25 values
are a pack example/baseline only, never engine constants.

**A5-R8 — Wave A numerical profile.** The exact A5 profile identifier is
`python_binary64_v1`. It uses the Python standard library and built-in
binary64 `float` only for scientific gate and score arithmetic; NumPy, JAX,
Torch, alternate dtypes, and dependency-specific math are outside this
profile. Pack JSON numbers are first retained as exact standard-library
decimal values for schema/range/sum validation, then explicitly converted to
binary64. Conversion must remain finite and must preserve required positivity.
Runtime numeric `ScoreInput` slots require exact built-in `float` values;
Boolean, integer, string, subclassed, coerced, NaN, and infinite values reject
where a number is required. Thresholds are finite and strictly positive; gate
error actuals are finite and non-negative; authorized component scores are in
the closed interval `[0.0, 1.0]`. No epsilon floor, clipping, coercion,
rounding, or silent range repair is permitted.

After all mandatory gates pass, a component score equal to binary64 zero takes
an exact zero branch and returns `combined_score = 0.0` without evaluating its
log. Otherwise, in fixed top-level order `(physics, robustness, accuracy)`, the
engine evaluates each term as binary64
`weight * math.log(component_score)`, combines that materialized three-term
tuple with `math.fsum`, and applies `math.exp` exactly once. JSON object source
order has no arithmetic effect. Within-leg weighted sums use `math.fsum` in
their declared array order; the exact scalar-transform operation order and
stable logistic branches are recorded in `Design_Specs/Scoring.md` §§6–7. The
result is not rounded or clamped. Any non-finite or out-of-range
intermediate/output is a non-scientific scoring error, not a gate failure.
Exact cross-runtime/libm reproducibility remains a later backend qualification
claim; this ratification fixes the Wave A execution behavior but does not
production-qualify a platform.

**A5-R9 — Explicit unresolved states.** The only explicit unresolved
scientific-value states are the exact JSON strings `HUMAN_INPUT` and
`BLOCKED_FOR_LIVE_UNTIL_SET`. They are states, not numeric values, passes,
zeroes, or defaults. JSON `null`, omission, and malformed values are not
aliases for either state. If any mandatory threshold or other score-bearing
required pack value is in either explicit state, the valid pack is
`PACK_NOT_READY`: no gates are evaluated, `combined_score` is absent/`None`,
and `eligible_for_emission = False`. That outcome is not a scientific gate
failure. An unresolved optional, strictly non-score-bearing diagnostic may be
retained only when exact `mandatory = false` marks it as such. While unresolved
it is unevaluated, contributes no expected `ScoreInput` key, creates no gate
result, is omitted from `InternalResult`, and cannot affect readiness, status,
a score, or eligibility.

**A5-R10 — Fixture-only origin.** A5 implements only a structurally
non-emission-authoritative fixture origin. Its runtime pack must bind exact
`fixture_origin = true`; missing or false origin rejects in A5. That field is
part of the exact pin and result, cannot be defaulted or relabelled by the
engine, and is structural labeling rather than authenticated provenance.
Every A5 fixture result has `eligible_for_emission = False`, including a
resolved pass with a non-zero combined score. An actual mandatory failure
still additionally enforces the A5-R5 zero-score invariant. Supporting a
production-origin pack or an emission-authoritative result requires separate
later implementation, qualification, and human authorization.

**A5-R11 — Private `InternalResult`.** A5's stable private result contains
only the scoring status, exact A5-R3 pack pin, fixture-origin state, evaluated
gate decisions/authorized scalar components as applicable, optional combined
score, and `eligible_for_emission`. It does not copy pack weights into the
result. It also excludes raw or derived seeds, seed roles, draw/sample/exam
IDs, evaluation binding, strategy/submission/miner/validator identity, fees,
block/decay/tie-break fields, public-card or disclosure behavior, receipt or
signature behavior, persistence, logging, and weight-writing. A6 owns storage
and public projection; later receipt/evidence, observability, FSM, and
economic owners consume only explicitly authorized fields.

**A5-R12 — Scoring authority and supersession.** `Design_Specs/Scoring.md`
remains the sole mathematical and A5 runtime-contract authority.
`Design_Specs/Scoring_Formulas.md` is subordinate. Its historical
0.40/0.35/0.25 example, sigmoid-as-official-hard-gate description, arithmetic
top-level aggregate, fp32/JAX runtime implication, and missing-input
fail-or-zero language are explicitly superseded and must not be implemented.
Historical PoC/legacy scorers and tests using linear/arithmetic/defaulted
semantics are archaeology, not A5 implementation or test evidence. The
active-looking historical `Design_Specs/Implementation.md` scoring appendix
and the proposed/unratified tuple in `Design_Specs/Strategy_Schema.md` are
likewise superseded for A5 artifact, input, gate, math, and result behavior.

**A5-R13 — Ticket repair and implementation gate.** The A5 ticket is repaired
to require both zero score and false eligibility on actual mandatory failure;
to require rejection rather than “ignored or rejected”; to require exact
bytes plus the external tagged digest rather than a content-hash stub; to use
strict runtime JSON rather than YAML; and to place the future test at the
current default-CPU path `tests/cpu/test_scoring_engine.py`. The new A5 plan is
a pre-implementation ratification plan only. Future implementation may begin
only after this documentation PR is independently reviewed, human-authorized,
merged, and followed by a fresh main/concurrency/status check. This decision
does not itself authorize a merge, start A5, or begin A6 or later work.

**A5-R14 — Literal schema and engine-entry completion.** During the authorized
A5 implementation, the maintainer resolved the remaining literal contract
gaps without changing A5-R1 through A5-R13. Score Pack schema version is the
exact required string `"1.0"`; every other schema token rejects. Every hard-gate
and soft-leg operator record has the exact required discriminator member
`"operator"`. The only accepted values remain `less_than`, `boolean_true`,
`quadratic_barrier`, `tail_logistic`, and `reciprocal_error`; `"type"`, `"kind"`,
omission, aliases, duplicates, and unknown values reject. Schema 1.0 makes
within-leg `weighted_sum` implicit, so nested `"aggregation"` is forbidden;
only top-level `"combination": "weighted_geometric_logspace"` is explicit.

The exact engine entry is
`ScoreEngine.score(score_input: ScoreInput | None, pack: LoadedScorePack)`.
For a valid `PACK_NOT_READY` pack, exact Python `None` returns a result with
empty gate and leg vectors, no combined score, and false eligibility; a
non-`None` input rejects. A ready pack rejects `None` and accepts only the exact
closed, pin-matched `ScoreInput`. Malformed or mismatched packs remain typed
configuration errors and produce no `InternalResult`; Python `None` does not
make JSON `null` valid.

After a ready pack and complete input are fully validated, the engine evaluates
every resolved gate in declared array order without short-circuiting, retains
the full ordered vector, includes resolved optional diagnostics, and omits
unresolved optional diagnostics. Mandatory failure is decided only after the
vector is complete; it returns the full gate vector, canonical `0.0`, false
eligibility, and no soft-leg evidence. Optional-only failure does not affect
scoring. After mandatory pass, an exact zero soft leg remains `SCORED` with
combined score `0.0`. This clarification belongs to the same implementation PR,
does not authorize A6+, and does not production-qualify A5.

## 2026-08-21 — A4 closure after reviewed merge

**Closure topology and review.** A4 implementation began from exact base
`e13baf312b811e2fd6784856c56d851a15f153fd`. Independent review approved exact
implementation head `b0f79cf96b7cd489a97a7a4dd49285d762c962aa` for the bounded A4
ticket, with no unresolved blocking finding. GitHub records no formally
submitted review object, review thread, or PR comment for PR #17, so this entry
does not claim a formal GitHub approval. Exact-head pull-request CI run
`32440327141` completed successfully: the CPU job reported `622 passed in
7.80s`, and Code quality passed at `Ruff 757/776; Black 62/68`, with eight
changed Python files, no new debt, and every changed Python file clean.

PR #17 then merged normally as
`120eab02e406bda280d9c361bbbb7d8ef7a08330`. Its ordered parents are exact base
`e13baf312b811e2fd6784856c56d851a15f153fd` and exact reviewed head
`b0f79cf96b7cd489a97a7a4dd49285d762c962aa`; the reviewed head is ancestral to
current `main`. Exact-merge push CI run `32444857456` completed successfully on
`main`: its CPU job reported `622 passed in 8.68s`, and Code quality again
reported `Ruff 757/776; Black 62/68`, eight changed Python files, no new debt,
and every changed Python file clean.

**Bounded acceptance evidence.** The implementation's focused command for
`tests/cpu/test_seeding.py` and `tests/cpu/test_no_leakage.py` reported `230
passed in 3.55s`; its complete local CPU command reported `622 passed in
4.35s`. The standard-library implementation and acceptance tests also passed
compilation, strict Ruff/Black, and the exact-base no-new-debt gate. A fresh
no-dependency `carbon-0.9.0-py3-none-any.whl` with SHA-256
`4bd58cc8b0e503cd127dd5c64f67970899ecabebd1554860121de8086028c511`
installed into a new environment and exercised the public A4 API from outside
the checkout under CPython `3.11.11` with `python -I`; golden seed and
commitment values passed, the official provider was observed exactly once, and
the blocked optional/consumer import attempted and loaded lists were both
empty.

**Maturity and preserved boundaries.** A4-R1 through A4-R11 remain
**SPECIFIED**; their bounded seeding, provider/fixture, commitment, leakage, and
isolation boundary is now **IMPLEMENTED** on `main` and **TESTED** to the
recorded CPU, deterministic-derivation, canonical-encoding, leakage,
public-projection, mock/fixture-isolation, and import-isolation scope. The exact
head was independently reviewed, merged, ancestry-verified, and post-merge-CI
verified. A4 is therefore `done` for this bounded ticket. This closeout
supersedes only the historical maturity language in the pre-implementation
ratification; it does not alter A4-R1 through A4-R11.

**PRODUCTION-QUALIFIED: NO.** A4 does not implement or qualify a real beacon
provider, provider authentication, entropy quality, chain timing, finality,
nonce lifecycle, reorg/replay handling, fallback policy, or retention and
post-evaluation disclosure policy. It does not define A7's concrete evaluation
binding, submission, fee, or FSM semantics; later receipt/signing semantics; A8
backend/TrainEval conversion; A6 Card-store disclosure integration; A9 MCP
transport; A10 leaderboard; A11 logging; or any scientific, LIVE, security,
operations, production, permanent same-process secrecy, weight-writing, or
emission claim. OQ-005 and OQ-006 remain unresolved, and A5 and all later
tickets remain `todo` and unstarted.

## 2026-08-21 — A4 pre-implementation seeding architecture ratification

**Status, base, and scope.** On exact `origin/main`
`c5f2dfbda64e4375e3d3f26f7a463ca98cabd07a`, the maintainer ratifies
A4-R1 through A4-R11 below as the implementation decision for A4 seeding,
isolation, and the unsigned public exam-commitment boundary. This is a
ratified implementation decision, not implementation: no A4 implementation
source or A4 tests exist beyond the A0 package marker, A4 remains `todo`, and
no Definition-of-Done item is complete. The decision does not select seed
timing or a production beacon, does not change A3, and establishes no
scientific, LIVE, backend, security, operations, production, or emission
qualification.

**A4-R1 — Entropy and provider boundary.** The former A4 helper sketch based
on a Carbon-operated long-lived `master_secret` is superseded. A4 accepts
opaque root material only through the separate exact types `OfficialEntropy`,
`MockEntropy`, `QualificationEntropy`, and `FixtureOfficialEntropy`.
Provider-origin official material crosses a narrow `BeaconProvider` boundary
as exactly 32 opaque bytes. A4 may define that protocol and a deterministic,
separately typed fixture provider, but it does not implement or select a real
Bittensor/Subtensor provider, block delay, finality rule, nonce lifecycle,
reorg policy, production hybrid/drand design, or production fallback. Missing,
malformed, conflicting, or unavailable official entropy fails closed; it never
falls back to zero, wall-clock time, process state, mock material, or a local
default. Those production choices remain protocol-owned under OQ-005 and
OQ-006.

**A4-R2 — Exact domains and typed entry points.** The complete top-level domain
set is exactly `mock`, `official_train`, `official_eval`, `official_stress`,
`reference`, and `dossier`. Initialization, augmentation, shuffle, dropout,
batch order, generator sampling, and similar functions may later be canonical
internal role keys beneath one of those domains; they are not peer domains.
Mock, official, qualification/reference, and fixture-official derivation use
separate typed contexts and public entry points. A4 must not expose a generic
`mode="mock" | "official"` switch or `local_mode` Boolean.

**A4-R3 — Official identity binding.** Every official derivation binds the
exact A3 `ChallengeKey` (`challenge_id` and exact challenge `version`), exact
`generator_version`, exact tagged `generator_digest`, exact
`scoring_version`, exact tagged `scoring_digest`, seed-scheme
identifier/version, an opaque 32-byte `evaluation_binding`, the exact official
domain, a canonical internal role key, and an explicit draw index. The
evaluation binding is only an A4 structural slot: A7 or later supplies its
concrete immutable value. A4 does not define `submission_id`, strategy hashing,
A7 idempotency, fee identity, or receipt identity. It accepts no raw Strategy
mapping or miner hyperparameters, so later Strategy mutation cannot alter an
already-created context.

Validator or miner identity is not scientific entropy. Official derivation
also excludes miner-controlled seeds, nonces, block hashes, draw IDs, and exam
IDs; wall-clock time; process ID; environment variables; thread scheduling;
call order; mutable global RNG state; and retry count. Validator identity must
not influence the scientific exam.

**A4-R4 — HKDF-SHA-256 contract.** A4 uses RFC 5869 HKDF with SHA-256. The
seed-scheme identifier is exactly `carbon.seed.hkdf-sha256.v1`; the Extract
salt is the exact ASCII bytes
`carbon/a4-seeding/hkdf-sha256/v1`; and the applicable typed 32-byte entropy is
the input keying material. Expand `info` is the A4-R5 canonical encoding and
the retained output is exactly 32 bytes. A4 does not reduce the result modulo
an integer range, truncate it to a 32- or 63-bit seed, centrally convert it to
a NumPy/JAX/Torch key, or reuse one value across roles. Backend-specific
conversion belongs behind later A8 TrainEval/backend adapters and must use
further role separation or a documented adapter conversion. The context-kind
values `official`, `mock`, `qualification`, and `fixture_official` are distinct
inputs, so identical root bytes do not collide across context kinds.

**A4-R5 — Canonical seed-info encoding.** A seed `info` document starts with
the exact ASCII header `carbon.seed.info.v1`. The header is followed by the
fields below in exactly this order. Each field is one unsigned one-byte tag,
one unsigned four-byte big-endian payload length, and the exact payload bytes.

| Tag | Field |
|---|---|
| `0x01` | context kind |
| `0x02` | seed-scheme identifier |
| `0x03` | challenge ID |
| `0x04` | challenge version |
| `0x05` | generator version |
| `0x06` | generator digest |
| `0x07` | scoring version |
| `0x08` | scoring digest |
| `0x09` | evaluation binding |
| `0x0A` | seed domain |
| `0x0B` | role key |
| `0x0C` | draw index |

String fields are exact validated ASCII bytes: implementations do not
Unicode-normalize, case-fold, alias, trim, or coerce them. Challenge identity
reuses A3 validation and `ChallengeKey`, not a weaker duplicate parser. Tagged
digests use A3's exact `sha256:<64 lowercase hexadecimal characters>` form.
The evaluation-binding payload is exactly 32 raw bytes. The draw-index payload
is exactly one unsigned 64-bit big-endian integer; Boolean, negative,
overflowing, and non-integer values reject. Unknown or duplicated fields,
invalid order, length, or text encoding, and all malformed values reject.
Delimiter-concatenated strings are not canonical A4 documents.

A4-R10 and A4-R11 below complete the generator/scoring-version and role-key
validation contracts required by this schema.

**A4-R6 — Private exam root and unsigned public commitment.** A4 derives a
32-byte private exam root from the same HKDF PRK through an independent Expand
domain. Its `info` document starts with the exact ASCII header
`carbon.exam-root.info.v1`, uses the A4-R5 TLV framing, and binds context kind,
seed-scheme identifier, exact `ChallengeKey`, generator version and digest,
scoring version and digest, and the 32-byte evaluation binding. It includes no
train/eval/stress domain, role key, or draw index.

The public value is an opaque, unsigned `ExamCommitment` in exact tagged form:
`sha256:` plus the lowercase hexadecimal SHA-256 digest of a canonical
commitment document. That document begins with the exact ASCII header
`carbon.exam-commitment.v1`, uses the same TLV framing, and binds the same
context/scheme/challenge/generator/scoring/evaluation fields followed by the
32-byte private exam root. The public value retains no Python reference to the
private context, root, entropy, or derived seeds. A public exam projection may
contain only the commitment, explicitly public challenge/generator/scoring
pins, and explicit fixture status where applicable. It never contains entropy,
the private root, raw or derived seeds, draw or sample IDs, a run nonce, hidden
sample order, a reconstruction-enabling block hash, per-role seed hashes, or
generated-payload hashes.

A4 does not create an EvaluationReceipt, receipt ID, validator signature,
timestamp, score commitment, prediction/reference root, Merkle/MMR log, or
audit record. A4-R9 below completes the exact exam-document tag contract.

**A4-R7 — Bounded security and disclosure claim.** A4 guarantees the interface
and derivation boundary: official entropy, raw or derived official seed
material, draw IDs, and reconstruction-sensitive exam identifiers do not cross
miner/public interfaces or get embedded directly in the public commitment;
official, mock, qualification, and fixture namespaces are distinct; identical
official inputs reproduce identical seeds and commitments across validators;
and validator identity does not affect the scientific exam. This is not an
unconditional mathematical hiding theorem. Resistance to recovery depends on
SHA-256 preimage resistance, HKDF-SHA-256 security, sufficient provider
entropy, and some relevant entropy remaining unavailable to an attacker for
the protocol-required hiding interval. A4 does not decide between
pre-submission unpredictability and permanent post-evaluation secrecy;
operational disclosure and retention remain protocol-owned.

**A4-R8 — Fixture, mock, and qualification isolation.** Fixture entropy is a
different non-coercible type from provider-origin official entropy.
Fixture-official derivation uses `context_kind="fixture_official"`; provider
origin uses `context_kind="official"`. Fixture public projections are
unmistakably fixtures, and fixture/mock identities must remain mechanically
non-emission-capable when emission paths exist. A4 itself adds no emission or
weight writer.

Mock derivation cannot request an official domain, accept official entropy,
access an official context, alter official counters or state, or affect later
official output through query count or call order. Qualification derivation is
limited to `reference` and `dossier`, cannot request mock or official domains,
and remains separate from the live official miner exam. Fixture material
cannot be relabelled or coerced into provider-origin material.

**A4-R9 — Exam-document TLV tag contract.** The exact document headers
`carbon.seed.info.v1`, `carbon.exam-root.info.v1`, and
`carbon.exam-commitment.v1` establish three separate versioned schemas. TLV
tags are interpreted within the schema selected by that exact header, not as
globally unique field identifiers. The `carbon.seed.info.v1` tags and payload
contracts remain unchanged from A4-R5.

`carbon.exam-root.info.v1` reuses the A4-R5 common identity tags and payload
contracts exactly:

| Tag | Field |
|---|---|
| `0x01` | context kind |
| `0x02` | seed-scheme identifier |
| `0x03` | challenge ID |
| `0x04` | challenge version |
| `0x05` | generator version |
| `0x06` | generator digest |
| `0x07` | scoring version |
| `0x08` | scoring digest |
| `0x09` | evaluation binding |

It has no additional fields and ends after `0x09`; it contains no seed domain,
role key, draw index, or private exam root.

`carbon.exam-commitment.v1` reuses those same `0x01` through `0x09` meanings
and payload contracts, then adds exactly `0x0A` — private exam root, whose
payload is exactly 32 raw bytes. Its field order is exactly `0x01` through
`0x0A`, with no additional fields. Reusing `0x0A` for seed domain in
`carbon.seed.info.v1` and private exam root in
`carbon.exam-commitment.v1` is intentional and unambiguous because the header
selects the schema. Implementations must not assign global meanings to tags,
introduce a `0x0D` private-root tag, or reserve unused seed-document tags for
cross-schema uniqueness. Unknown, duplicate, reordered, malformed-length,
malformed-payload, and trailing unrecognized fields reject.

**A4-R10 — Generator and scoring version validation.** A4 creates no second
version grammar. Both `generator_version` and `scoring_version` call and reuse
`carbon.registry.model.validate_version`; implementation must not copy its
regular expression into `carbon/seeding`. The current contract requires an
exact built-in Python `str`, returns its exact spelling without normalization,
trimming, coercion, case folding, or alias resolution, and permits at most 64
characters under the ASCII grammar
`[A-Za-z0-9]+(?:[._-][A-Za-z0-9]+)*`. Tokens begin and end with an
alphanumeric character; empty segments and adjacent separators without an
intervening alphanumeric segment reject. `1.0` and `burgers1d_v0.1` are valid
examples. If A3's authoritative validator changes before A4 implementation,
the implementation uses the then-current contract and re-evaluates its golden
vectors before coding.

**A4-R11 — Canonical role-key validation.** A4 `RoleKey` is a distinct
semantic type that reuses A3's canonical-identifier grammar. A role key must be
an exact built-in Python `str`, encode as ASCII, be non-empty and at most 64
encoded ASCII bytes, preserve exact spelling without normalization, trimming,
case folding, coercion, or alias resolution, and match
`[a-z][a-z0-9]*(?:[_-][a-z0-9]+)*`. A4 first enforces its own 64-byte bound,
then calls
`carbon.registry.model.validate_canonical_identifier(value, "role_key")`;
it does not duplicate the regular expression. Valid examples include
`generator`, `generator_sampling`, `parameter_init`, `batch_shuffle`,
`dropout`, and `augmentation_1`. Empty, uppercase, leading-digit,
leading/trailing/repeated-separator, dotted, spaced, slashed, non-ASCII, and
over-64-byte values reject. Role keys remain subordinate to one of the six
ratified domains and do not alter any A3 or other identity domain.

**Protocol deferrals and maturity.** OQ-005 and OQ-006 remain unresolved in
their owning protocol/security domains. In particular, this ratification does
not select a chain event, delay, finality/reorg rule, nonce lifecycle, real
provider, hybrid/drand construction, or fallback. Separately, A4-R7 leaves
operational entropy retention and post-evaluation disclosure policy to their
protocol owner. A4 remains `todo`; none of the behavior above is
**IMPLEMENTED**, **TESTED**, or **PRODUCTION-QUALIFIED** by this documentation
entry.

## 2026-08-21 — A3 closure after reviewed merge

**Closure evidence.** A3 began from exact base
`e6fb20b1dc361ded442fcf41d118cea5f2c775cd`. Independent review identified
the fixture-relabel provenance gap, missing production-backbone requirement,
and quality-attribution correction; the same A3 branch repaired them, and
independent rereview approved final head
`149f9a74351b02a9b615d0015c22b74187ab0f55`. Repaired-head PR CI run
`32377387086` passed both CPU tests and Code quality. PR #14 then merged
normally as `69b938d1c4fd0aca58276940d15df50b1b68e5d1`, whose parents are exact A3
base `e6fb20b1dc361ded442fcf41d118cea5f2c775cd` and reviewed head
`149f9a74351b02a9b615d0015c22b74187ab0f55`; the reviewed head is ancestral to
current `main`. Exact-merge push CI run `32379421897` completed successfully on
`main`: CPU job `96458664242` reported 392 passing tests, and Code quality job
`96458663684` passed with inventory unchanged from the A3 base at
`Ruff 757/776; Black 62/68`, no new debt, and all changed Python files clean.

**Maturity and preserved boundaries.** A3 is therefore `done` and may be
described as **SPECIFIED**, **IMPLEMENTED**, **TESTED**, independently reviewed,
merged, and post-merge-CI verified for the structural challenge registry/LIVE
gate only. Canonical identity remains exact `(challenge_id, version)`; the gate
hashes actual artifact bytes against tagged SHA-256 bindings; fixture-origin
evidence remains structurally blocked from production; and production LIVE
requires at least one allowed canonical backbone. `fixture_origin` is
structural, not authenticated, provenance; signer/authentication mechanisms
remain future work. No real challenge was made LIVE, and A3 does not establish
scientific, backend, security, operations, production, or emission
qualification. No thresholds or approvals were invented. A4 remains `todo`
and has not started; all A4+ behavior remains outside this closeout.

## 2026-08-20 — A3 exact-version registry and structural LIVE gate

**Base, authority, and scope.** A3 began on `agent/a3-challenge-registry` from
exact `origin/main` commit
`e6fb20b1dc361ded442fcf41d118cea5f2c775cd`, after the reviewed A2 merge and
post-merge CI closure. `Design_Specs/Build_Out.md` C1 and §8 define the core
registry and LIVE-manifest contract; the ratified
`Design_Specs/Build_Out_Protocol_Extension.md` reserves receipt-schema and
backend-profile identities. No authoritative source changes the exact
ChallengeKey, tagged SHA-256, eight-slot, or fixture-isolation requirements,
and no qualification-manifest signature algorithm is ratified. A3 remains
`in_progress`. Initial PR #14 review found a fixture-relabel provenance gap, a
missing production-backbone requirement, and incorrect quality attribution;
the same-branch repair is recorded below, while independent rereview/approval,
merge, and post-merge CI are not established by this entry.

**Canonical boundary (REPLACE/RETIRE).** `carbon.registry` is the canonical A3
authority. It replaces historical mutable challenge record/loader semantics
for this boundary. `carbon/challenges/*` is RETIRE/defer evidence, remains
untouched, and does not become registry authority. The mutable runtime backbone
registry remains independent; A3 stores only exact declarative compatibility
identifiers and imports no backend. PoC hashing contributes only the raw-byte
SHA-256 concept and is not reused as an authority for scoring, execution, or
qualification.

**Exact identity and persistence.** One immutable `ChallengeKey` is the exact
pair `(challenge_id, version)`, stored only at
`<registry_root>/<challenge_id>/<version>.json`; embedded and file-location
identities must match. Strict JSON rejects duplicate keys, unknown fields,
non-JSON constants, malformed types, and duplicate embedded keys during scans.
Registry and artifact files are opened descriptor-relatively with symbolic
links disallowed and regular-file checks applied. Writes serialize
deterministically and use a per-key interprocess lock, a fsynced temporary file
in the destination directory, descriptor-relative atomic replacement, and a
directory fsync where available. These mechanics provide the A3 file boundary;
they are not a general distributed transaction or remote-filesystem guarantee.
No ratified A2/A3 source supplies a maximum length for the shared canonical
identifier syntax, so A3 does not invent one in this correction; a protocol
limit remains explicitly deferred.

**Qualification gate.** The exact ordered requirements are
`generator_envelope=APPROVED`, `generator_validation=PASSED`,
`dossier_level_1=APPROVED`, `score_pack=APPROVED`,
`mock_incompleteness=APPROVED`, `train_backend=QUALIFIED`,
`launch_bar=SIGNED`, and `mcp_readiness=SIGNED`. Every slot also needs a
human-owned reference and a known artifact identifier. Every declared artifact
uses only canonical `sha256:<64 lowercase hex>` and is re-hashed from the bytes
of the same securely opened regular file. An effective-LIVE query re-runs the
gate, and only checked production activation may persist `live`; ordinary save
cannot create or mutate LIVE state. Production LIVE also requires at least one
allowed backbone, without restricting that declarative list to today's A2
backbone names.

**Fixture and protocol-extension boundaries.** Fixture eligibility requires
four independent barriers: fixture lifecycle status, fixture manifest mode, a
required `fixture_origin=true` record provenance bit, and an explicit
fixture-mode API call. Fixture labels require that origin at model validation,
and ordinary save cannot change it for an existing `ChallengeKey`. Production
assessment rejects fixture origin even after status and mode are relabelled;
activation has no fixture bypass. This is structural provenance, not an
authenticated or signed origin claim. The record's ordered allowed-backend-
profile binding and required selection are structurally bound to
`train_backend` evidence; the receipt schema version is structurally bound to
`mcp_readiness` evidence. Equality of those identifiers never approves a
backend or environment, makes evidence scientifically correct, verifies a
signer, or proves that a receipt is signed.

**Public API and unclaimed maturity.** A configured `ChallengeRegistry` exposes
exact-version `load`, `save`, diagnostic/boolean eligibility,
effective-LIVE, checked activation, and backbone-compatibility operations plus
deterministic `scan()`. The focused path is
`tests/cpu/test_registry.py`, with structure-only static data under
`tests/fixtures/registry/`. Local repair verification passed 134 focused tests
in 0.33s and 392 complete default CPU tests in 0.74s, with strict Ruff/Black on
all six changed Python files. The CI-equivalent gate introduced no new debt and
left inventory unchanged from the exact A3 base at
`Ruff 757/776; Black 62/68`; `git diff --check` and a fresh no-dependency
outside-tree wheel/import boundary also passed. The inherited PoC
smoke still exits 2 on its pre-existing missing `role_seed` collection import.
A3 does not ship a production-LIVE record or real
scientific hashes and does not implement scientific/backend qualification,
receipt signing, Score Pack semantics, official seeding, scoring, model cards,
execution, MCP transport, Bittensor operation, or any A4+ capability.

## 2026-08-20 — A2 closure after reviewed merge

**Closure evidence.** The initial A2 implementation received independent
review, and its findings were corrected at final reviewed head
`d73f697ebd9df9b8c96b7a46fd4c9986444f0928`. Independent rereview found no
remaining blockers. PR #12 then merged normally as
`bfc0b97e1b16625141de3950428bc2fdf69f42ea`; the reviewed head is ancestral to
current `main`. Post-merge push CI run `32360050671` passed: the default CPU
suite reported 258 passing tests and the code-quality gate succeeded. A2 is
therefore `done`. A3 remains `todo` and unstarted.

**Maturity and remaining boundaries.** A2 is **IMPLEMENTED and TESTED** only
for its Strategy schema/`dry_validate` boundary. This closure does not claim
production qualification, end-to-end hostile execution isolation, LIVE
qualification, scientific validation, challenge-registry binding, persistent
strategy hashing, parameter execution semantics, MCP integration, or
Bittensor integration. OQ-008 remains broader and unresolved beyond A2's
declarative validation boundary.

## 2026-08-20 — A2 canonical Strategy v1.0 and pure dry validation

**Base, authority, and scope.** A fresh remote read verified both
`origin/main` and the dedicated `agent/a2-strategy-schema` starting point at
`e696cc43ace96a963f00bb28394da03d35eb267e`. A1 and its PR #9 cold-start
registry repair are ancestral and complete, the sequencing hold is closed,
the supported pre-edit CPU baseline passed 27 tests, and no canonical A2
implementation had landed. The ratified A2 instruction resolves conflicting
historical text: `schema_version` supersedes this ticket's old
`strategy_version` wording; rich top-level training/loss/curriculum/data
examples were not the A2 contract. The Miner MCP scaffold is reconciled to the
A2 envelope; the pending Strategy Schema v1.1 proposal remains design input,
not implementation truth. For OQ-008, the ratified instruction settles only
the narrow A2 declarative schema/validation boundary; it does not close the
broader execution threat model or qualify execution isolation.

**Canonical contract (REPLACE).** Strategy v1.0 has exactly four required
top-level fields: exact `schema_version: "1.0"`, canonical-string
`challenge_id`, canonical-string `backbone`, and exact-object `parameters`.
The recognized schema-level backbone set is the immutable
`deeponet`/`fno`/`physicsnemo_fno`/`uno` set; validation never imports or calls
the mutable runtime registry. Both identifiers must already match ASCII
`[a-z][a-z0-9]*(?:[_-][a-z0-9]+)*`. No aliases, defaults, case folding,
coercion, clamping, semantic dropping, document rewriting, or protocol hash is
provided. The legacy `carbon/common/strategy_schema.py` remains untouched for
historical callers but is not canonical A2 behavior.

**Pure hostile-input boundary.** `carbon.schema.dry_validate` returns frozen,
slotted `ValidationResult` and `ValidationIssue` values with stable codes,
JSON-Pointer-like paths, deterministic sorting, and generic messages that do
not echo submitted values or representations. Exact built-in JSON types are
validated iteratively. Active-ancestor and completed-container identity sets
reject cycles while bounding traversal work for shared DAGs; non-finite
numbers, non-string keys, subclasses, bytes, tuples, sets, callables, and
arbitrary objects fail closed without `repr` or user display methods. A small,
explicit, versioned reserved-key vocabulary rejects the ratified capability
and official-control fields; only case/camel-case differences and hyphen,
ASCII-space, or underscore separators (including compact spellings) are
matched.
Arbitrary English meaning and string contents are not interpreted: unknown
keys and URL/path/code-looking strings remain inert. This denylist is defense
in depth, not comprehensive executable-intent detection. Later execution must
use positive parameter handlers, never execute/import/fetch from unknown
fields, never pass arbitrary parameters blindly into constructors, and never
silently drop unknown fields.

**Explicitly unresolved.** OQ-008 remains open beyond declarative validation:
the permitted execution surface, sandbox/process isolation, immutable execution
environment, parser and runtime resource limits, kill policy, audit controls,
and production security/operations qualification still require their owning
later tickets and human approval. A2 uses no fabricated production numbers and
keeps iterative frames suitable for adding ratified parser limits later.
Persistent canonicalization and `strategy_hash` remain A7 work. Challenge
lookup/LIVE qualification, official seeding, scoring, cards, fees/FSM,
TrainEval/model construction, MCP transport, leaderboard, production
observability, Bittensor operation, and all other A3+ behavior remain absent.

**Local evidence.** The focused A2 suite passed 181 tests and the full default
CPU lane passed 208. Ruff and Black passed strictly for all three changed
Python files. The repository no-new-debt gate passed at Ruff 757/776 and Black
62/68, unchanged from the A2 base; A2 added no Ruff or Black debt. The 19 Ruff
and six Black reduction is cumulative from older baseline work, not attributable
to A2. `git diff --check` passed. A fresh no-dependency wheel imported
`carbon.schema.strategy` from `site-packages` outside the checkout and returned
a valid result with every optional scientific/Bittensor and non-schema Carbon
boundary blocked; attempted and loaded sensitive-module lists were empty. An
initial local adversarial pass drove shared-DAG and path-ambiguity regressions.
Independent review on draft PR #12 subsequently identified the broad semantic
classifier, generic string-value heuristics, non-ASCII public paths,
specification/status drift, and quality-attribution error addressed by the
focused correction on the same A2 branch. Independent rereview of the
correction remains outstanding.

The existing `POC_FAST=1 bash poc/scripts/smoke.sh` completed its oracle and
three protocol fixture runs, then exited 2 during collection at the unchanged
inherited `ImportError` for `poc.generators.burgers1d.role_seed`. That defect is
not widened into A2. A2 is locally **IMPLEMENTED and TESTED** for its narrow
schema boundary only. It is not scientifically validated, end-to-end
execution-isolated, LIVE-qualified, production-qualified, or
Bittensor-integrated. The Wave item remains `in_progress` until external review
and merge.

**Draft PR #12 review-fix evidence.** The focused A2 suite passes 231 tests and
the full default CPU lane passes 258 after replacing semantic inference with
the explicit v1.0 reserved-key vocabulary and making public paths fixed-ASCII.
Ruff and Black pass strictly for the two correction Python files;
`git diff --check` passes. The repository quality inventory remains Ruff
757/776 and Black 62/68 from the exact A2 base, so this correction adds no
debt; the gate's reported 19 Ruff and six Black removal remains cumulative
against the older committed baseline. A fresh non-editable, no-dependency
wheel imported from `site-packages` outside the checkout. With every optional
scientific/Bittensor and non-schema Carbon boundary blocked, no blocked import
was attempted or loaded; neutral URL/code-looking strings remained inert, a
reserved `OfficialSeed` key failed closed, and a Greek key produced the
fixed-ASCII path `/parameters/~u0003b1`. Independent rereview remains pending.

## 2026-08-20 — Post-merge A1 cold-start backbone registry correction

**Historical correction and status.** A1 PR #5 was reviewed at
`c4d0a9210aaacad077287c2ca14e20b2bb6d396e` and merged as
`5f810a57379a608119aa9cc9bbd6fc78a48baf13` before a subsequent independent
review's optional-backend blocker was repaired. At that merged head, a cold
`carbon.backbones` import had no known adapters, the CPU tests imported adapter
modules before exercising lookup, and `carbon.backbones.registry` owned a
second disconnected mapping. This corrects the registry-path implementation
and test claim in the 2026-08-19 A1 decision below; it does not rewrite the
original install, CPU CI, quality-ratchet, or PoC evidence.

**Corrective decision (WRAP/REPAIR).** The initial fetch found the expected
post-PR-#6/PR-#7 `main` at
`3e29fef703d4b60c97ff4873cb395d2436cdad0a`. Before publication, `main`
advanced through PR #8, which changed only the scientific-reference canon and
did not overlap this repair. The branch was fast-forwarded, so its actual repair
base is `7f499e589b86ed127745831ccacdc1c8e4ffb677`. `carbon.backbones` remains
the package-facing API and is now the sole registry state owner. An explicit
map links `physicsnemo_fno`, `fno`, `deeponet`, and `uno` to their local Carbon
adapter modules. Listing names imports no adapter, and resolving a built-in
imports only its local adapter. The compatibility API in
`carbon.backbones.registry` delegates registration, listing, and resolution to
the package registry while preserving its historical construct-with-keywords
behavior; it no longer owns a second mapping.

Fresh isolated subprocess tests block `physicsnemo`, `neuralop`, and `torch`,
prove all four names are cold-discoverable without loading those packages, and
exercise extra-specific construction failures through the registry for both
backend families. Separate cold-registry tests prove a transitive
`ModuleNotFoundError` is re-raised unchanged. Installed-backend API
compatibility, model behavior, and scientific or production qualification
remain untested and unclaimed. This correction introduces no A2+ behavior.

**Local corrective evidence.** In a fresh Python 3.11.11 virtual environment,
the literal `python -m pip install -e ".[dev]"` exited 0 and installed
`carbon==0.9.0`; `python -m pytest -q` exited 0 with 27 passed and no skipped,
xfailed, or failed tests. The nine optional-backend tests passed individually,
including both registry-path missing-extra cases and both transitive-error
cases. An isolated cold-process diagnostic listed all four built-ins, resolved
their local wrapper classes, and found no `physicsnemo`, `neuralop`, or `torch`
module loaded. The quality gate passed at Ruff 757/776 and Black 62/68 with all
three changed Python files strict-clean. Compared with untouched repair base
`main` at Ruff 769/776 and Black 64/68, the patch removes 12 Ruff and two Black
fingerprints and adds none. `git diff --check` exited 0. With the explicit PoC
extra installed, `POC_FAST=1 bash poc/scripts/smoke.sh` exited 2 at the unchanged
inherited import failure for absent `poc.generators.burgers1d.role_seed`.

At the corrective branch's pre-merge record, A1 remained `in_progress` until
the draft PR received independent rereview and was merged. A2 remained `todo`
behind that temporary sequencing gate. Local and GitHub Actions evidence for
the final corrective head was recorded in the corrective PR because a commit
cannot record its own SHA or subsequent run IDs.

**Corrective merge and A1 closure.** The independently rereviewed PR #9 final
head `a247bb189d44ddf18de504572ef620cf5d501d10` passed final-head CI run
`32326384939`: the CPU job ran the default suite with 27 passing tests, and the
code-quality job passed the existing no-new-debt ratchet. PR #9 then merged as
`819da3c163c2fb9476a6881aab8740cc6984066e`. That merge is ancestral to the
closure base `fb6bbf393f77ae80d76abf3eda0e53a7dfd12f17`; intervening PR #10 added
only non-conflicting specification and context documents. The cold-start
registry gap is therefore repaired on current `main`, and A1 is `done`. A2 is
the next Build_Out ticket and remains `todo`; no A2 implementation begins in
this closure. Installed-backend API compatibility, scientific correctness, and
scientific or production qualification remain untested and unclaimed.

## 2026-08-19 — A1 truthful CPU CI and pytest baseline

**Base, branch, and scope.** A fresh fetch verified `origin/main` at the
authorized `0b2eec30250f1767cc434836e189cca219154d4d`, which is also merged PR
#4's merge commit. A1 started from that exact commit on
`agent/a1-ci-skeleton`. This decision implements engineering infrastructure
only; it does not promote or qualify A2+ schemas, registries, seeding, scoring,
cards, fees, TrainEval, MCP, leaderboard, logging, invariants, Bittensor
transport, or scientific behavior.

**Inherited baseline and actual Actions stages.** The local baseline used an
isolated detached worktree, CPython 3.11.11, and pip 24.0. Exact results:

| Command | Base result |
|---|---|
| `python -m pip install -e ".[dev]"` | Exit 1: no matching `physicsnemo` distribution. |
| `python -m pytest -q` | Forced diagnostic, exit 2: 22 collection errors from unavailable PoC/scientific and legacy dependencies. |
| `pytest tests/ -q --tb=no` | Forced exact-workflow diagnostic, exit 2: five legacy collection errors; first material signature is missing `neurons`. |
| `ruff check .` | Exit 1: 776 findings, 544 fixable. |
| `black --check .` | Exit 123: 66 files would reformat, 70 unchanged, and parse failures at `carbon/challenges/navier_stokes_2d.py:34:61` and `carbon/validator/sciml_validation.py:37:8`. |
| `POC_FAST=1 bash poc/scripts/smoke.sh` | Exit 2 after the oracle and three JAX fixture runs; final pytest collection cannot import `role_seed` from `poc.generators.burgers1d`. |
| Editable `--no-deps` install plus isolated imports from outside the tree | Exit 0 for `carbon==0.9.0`, `carbon`, and all 14 A0 role packages. |
| `git diff --check` | Exit 0. |

Base Actions run `32244438188` is the authoritative workflow record. Test job
`96041796858` failed installation and **skipped** its pytest step. Quality job
`96041796669` installed tools, failed Ruff on 776 findings, and skipped Black.
The forced commands above are diagnostics, not descriptions of skipped Actions
stages.

**Dependency decision (REPAIR).** The canonical root and 14 A0 role packages
import with every inherited third-party dependency blocked, so the truthful
core dependency set is empty. The supported `dev` extra pins pytest 9.1.1,
Ruff 0.16.3, and Black 26.5.1. Bittensor is retained only behind optional
`chain`, `validator`, and `miner` aliases; the aliases use plain Bittensor
because upstream has no `validator` or `miner` extras. NeuralOperator,
PhysicsNeMo, and the historical PoC each have explicit optional extras.
PhysicsNeMo uses the actual `nvidia-physicsnemo` distribution and its documented
`physicsnemo.models.fno` import boundary; that extra is Python 3.11+ upstream.
The retained NeuralOperator model-argument compatibility remains explicitly
deferred and unqualified.

Both backend adapters now register lazily without importing their scientific
packages. Direct or registry-based construction without an extra raises an
actionable extra-specific error. A missing transitive module in an installed
backend is re-raised rather than mislabeled as an absent backend. No fake or
vendored scientific package was introduced.

**Test classification (WRAP).** The default `python -m pytest -q` lane is
`tests/cpu/`: 22 tests cover `carbon`, all 14 A0 roles, distribution identity,
isolated outside-tree imports, optional-dependency absence, and backend failure
contracts. Five inherited root tests were moved with assertions preserved to
`tests/legacy/`; they target retired `neurons` APIs or superseded
scoring/schema/seeding behavior and contain collection/API failures not solved
by installing heavyweight dependencies. The 67 PoC tests remain in place and
are marked `poc`; 32 are additionally integration, two JAX-backend, and one
gold. The `invariant` marker is registered for A12, but no A12 tests or behavior
were added.

**Quality debt decision (WRAP/REPAIR).** Full cleanup is not appropriate in A1:
the base has 776 Ruff findings across legacy code, 66 Black reformat candidates,
and two files Black cannot parse. A complete normalized fingerprint inventory
is committed at `.ci/quality-baseline.json` and anchored to the authorized base.
The blocking gate enumerates Python files explicitly, runs pinned isolated
Ruff, runs Black with the empty `/dev/null` configuration, validates Black's
full-file summary, rejects diagnostics absent from the base inventory, and
strictly checks every added/touched Python file. It permits debt removal, not
new debt, and uploads the complete current report. This converts a permanently
red inherited job into a meaningful ratchet without deleting, excluding, or
making quality controls non-blocking. Running the committed generator against
a second clean detached checkout of the starting SHA reproduced the baseline
JSON byte-for-byte: 776 Ruff diagnostics and 68 Black debt entries.

**Local clean-candidate result.** In a detached candidate worktree, `python -m
pip install -e ".[dev]"` exited 0 and installed `carbon==0.9.0`; `python -m
pytest -q` exited 0 with 22 passed. Isolated imports from `/private/tmp` passed
for the package and all 14 roles. A separate wheel build/install contained 69
files, included all 14 roles, and imported `carbon` from `site-packages`. The
quality gate exited 0 at Ruff 769/776 and Black 64/68, with seven Ruff and four
Black baseline entries removed, no additions, and 12 changed Python files
strict-clean. Raw audits remain visibly red at 769 Ruff findings (537 fixable)
and Black exit 123 with 62 reformat candidates, 79 unchanged files, and the same
two parse failures. `git diff --check` exited 0.

The post-change `POC_FAST=1 bash poc/scripts/smoke.sh` again exited 2 at the
same missing-`role_seed` collection error after completing its oracle/fixtures.
This is an unchanged inherited PoC failure, not a passed A1 stage or scientific
claim.

**Authoritative draft-PR result.** Draft PR #5 run `32250522522` completed
successfully on Ubuntu/Python 3.11.15. CPU tests job `96060233144` passed the
supported development install, reached the actual `python -m pytest -q` step,
and reported 22 passed in 0.13 seconds. Code-quality job `96060233203` passed at
Ruff 769/776 and Black 64/68 with all 12 changed Python files strict-clean, then
uploaded complete report artifact `9364221072`. No blocking step was skipped.

A1 is now **IMPLEMENTED and TESTED** for its CPU engineering-infrastructure
scope. Scientific, security, LIVE, emissions, and production qualification
remain unclaimed. The exact final PR head and its post-evidence Actions run are
maintained in the draft PR body because a commit cannot record its own SHA.

## 2026-08-19 — A0 canonical package layout

**Base and scope.** A0 started from clean `main`/`origin/main` at
`ab765b07bc8c41106194ce6d06b4a2bd1c03f9a1` on branch
`agent/a0-repo-layout`. The root `.agent/` directory remains the runtime board:
`.agent/WAVE.md`, `.agent/tickets/`, and `.agent/INVARIANTS.md` are canonical;
`agent_pack/` contains protocol documentation only.

**Package-root decision.** Keep the existing root-layout `carbon/` package as
the sole canonical namespace. It is already selected by
`[tool.setuptools.packages.find] where = ["."]` and `include = ["carbon*"]`, so
introducing `src/carbon/` would create a second mapping without A0 benefit.
`carbon/__init__.py` already makes `python -c "import carbon"` succeed. A0 adds
only the required package boundaries: `schema`, `registry`, `seeding`,
`scoring`, `cards`, `fees`, `traineval`, `mcp`, `leaderboard`, `logging_utils`,
`evaluation`, `audit`, `chain`, and `qualification`. The empty `evaluation`
and `chain` boundaries reserve the adapter seam: future scientific/evaluation
code remains independent of Bittensor SDK objects, while SDK implementations
belong behind `carbon.chain`. No chain, receipt, audit, qualification, scoring,
or scientific behavior is implemented by A0.

**Current-tree mapping.** The current base differs from the older A-1 tree
snapshot: a 51-file legacy `carbon/` tree is present, while `Carbon_Logic/` is
absent. No legacy module is thereby promoted as current-spec compliant.

| Current root | A0 mapping |
|---|---|
| `carbon/` | Canonical import/package root; legacy modules remain audit inputs until later scoped tickets promote, wrap, repair, or replace them. |
| `poc/` | First Burgers TrainEval promotion source only; its current science, scoring, seed disclosure, and fixed values are not qualified. |
| `Carbon_Logic/` | Legacy selective-promotion source named by the maintainer disposition, but absent at this base; it is not recreated or supported as a namespace. |
| `neurons/` | Preserved legacy Bittensor reference; A0 found no import/layout acceptance need to reuse it. |
| `Julia/` | Preserved v0 generator-verification path; inclusion is not repair, scientific validation, or qualification. |
| `Design_Specs/` | Domain-owned semantic authority. |
| `.agent/` | Canonical runtime board, tickets, decisions, and invariants. |
| `agent_pack/` | Execution protocol/templates only, never a competing board. |

**Import inventory and migration decision.** The audit found 40 lowercase
`carbon` import statements, 21 `hydrogen` statements, one uppercase `Carbon`
statement, and no `Carbon_Logic` import statement. No import migration is
required for A0 acceptance because the canonical root import already succeeds;
changing legacy callers would broaden A0 into implementation repair. Migrated
callers: **none**. Deferred retired-namespace callers:

- `hydrogen`: `carbon/base/validator.py`;
  `carbon/challenges/{burgers,darcy_2d,heat,navier_stokes_2d}.py`;
  `carbon/data/__init__.py`; `carbon/landscape/agent.py`;
  `carbon/specialist/distillation.py`; `carbon/symbolic/pysr_evolver.py`;
  `carbon/training/{physicsnemo_trainer,trainer}.py`; and
  `carbon/validator/validator.py` (21 statements total).
- uppercase `Carbon`: `scripts/generate_leaderboard.py` (one statement).
- `Carbon_Logic`: none in the current Python import inventory.

These callers are explicitly unsupported/deferred, not compatibility promises.

**Pre-change baseline (Python 3.11.11).** These commands were run on the clean
A0 branch before package-boundary edits. The inherited baseline is red.

| Exact command | Exit/result before A0 |
|---|---|
| `python -m pytest tests/ -q --tb=no` | Exit 2: three collection errors (`test_physics_gates.py`, `test_reproducibility.py`, `test_scorer.py`). |
| `python -m pytest tests/ -q` | Exit 2: the same three collection errors, rooted in missing `torch`. |
| `POC_FAST=1 PYTHONPATH=. python -m pytest poc/tests -q` | Exit 2: one collection error; `poc.generators.burgers1d` does not export `role_seed`. |
| `POC_FAST=1 ./poc/scripts/smoke.sh` | Exit 126: tracked script is not executable. |
| `POC_FAST=1 bash poc/scripts/smoke.sh` | Exit 2 after three protocol-only `numpy_fd` cases; its final PoC pytest step has the same missing-`role_seed` collection error. Generated artifacts were removed after capture. |
| `python -m compileall -q Carbon_Logic neurons poc tests scripts examples` | Exit 0 with `Can't list 'Carbon_Logic'`; all existing requested roots compiled. |
| `ruff check .` | Exit 127: `ruff` is not installed. |
| `black --check .` | Exit 127: `black` is not installed. |
| `julia --version` | Exit 127: `julia` is not installed. |

**A0 implementation plan / DoD mapping.** Retain the existing canonical root;
add only the fourteen required package markers; use `evaluation/` and `chain/`
as the SDK-independent seam; migrate no caller not needed by the import/layout
test; preserve all current PoC, neurons, Julia, specifications, tests, and
legacy code; then re-run the exact table above plus `python -c "import carbon"`
and `git diff --check`. A0 may be marked done only if the package inventory,
before/after signatures, and focused diff evidence every listed DoD item.

**Post-change validation and delta.** Every exact baseline command above was
re-run. Exit codes and failure signatures were unchanged: root pytest still has
the same three missing-`torch` collection errors; PoC pytest and the Bash smoke
path still stop at the same missing `role_seed`; direct smoke remains exit 126;
compileall remains exit 0 with the absent-`Carbon_Logic` notice; and
Ruff/Black/Julia remain unavailable at exit 127. Therefore A0 introduced zero
new baseline failures, but the inherited repository baseline remains red.
`python -c "import carbon"` passed at exit 0. `git diff --check` passed at exit
0. Generated smoke/test artifacts and bytecode caches were removed and are not
part of the change.

### Blocking-review follow-up: installability and CI-equivalent evidence

**Compared states and isolation.** The review follow-up compared detached,
clean Git worktrees created with `git worktree add --detach`: base
`ab765b07bc8c41106194ce6d06b4a2bd1c03f9a1` at
`/private/tmp/carbon-a0-base.Mxz8U8` and the pre-follow-up A0 head
`e2f91a428c91a963caf261747f2ffd05ea0e1821` at
`/private/tmp/carbon-a0-head.ZWnuEh`. Each workflow path used a separate clean
virtual environment. Local comparisons used CPython 3.11.11 on macOS arm64
with virtual-environment pip 24.0. Neither worktree was dirty.

**No-dependency editable-install proof (A0 head).** From a clean virtual
environment, the actual project build configuration succeeded without a
packaging-metadata change:

```text
python -m pip install --no-deps -e /private/tmp/carbon-a0-head.ZWnuEh
exit 0; built and installed distribution carbon==0.9.0
```

Build isolation was left enabled; `--no-build-isolation` was not necessary.
From `/private/tmp` (outside the repository), the installed interpreter
`/private/tmp/carbon-a0-venvs.pRnWzd/head-editable/bin/python` imported
`carbon` and all fourteen required role packages at exit 0. Resolved paths
were:

```text
carbon              -> /private/tmp/carbon-a0-head.ZWnuEh/carbon/__init__.py
carbon.schema       -> /private/tmp/carbon-a0-head.ZWnuEh/carbon/schema/__init__.py
carbon.registry     -> /private/tmp/carbon-a0-head.ZWnuEh/carbon/registry/__init__.py
carbon.seeding      -> /private/tmp/carbon-a0-head.ZWnuEh/carbon/seeding/__init__.py
carbon.scoring      -> /private/tmp/carbon-a0-head.ZWnuEh/carbon/scoring/__init__.py
carbon.cards        -> /private/tmp/carbon-a0-head.ZWnuEh/carbon/cards/__init__.py
carbon.fees         -> /private/tmp/carbon-a0-head.ZWnuEh/carbon/fees/__init__.py
carbon.traineval    -> /private/tmp/carbon-a0-head.ZWnuEh/carbon/traineval/__init__.py
carbon.mcp          -> /private/tmp/carbon-a0-head.ZWnuEh/carbon/mcp/__init__.py
carbon.leaderboard  -> /private/tmp/carbon-a0-head.ZWnuEh/carbon/leaderboard/__init__.py
carbon.logging_utils -> /private/tmp/carbon-a0-head.ZWnuEh/carbon/logging_utils/__init__.py
carbon.evaluation   -> /private/tmp/carbon-a0-head.ZWnuEh/carbon/evaluation/__init__.py
carbon.audit        -> /private/tmp/carbon-a0-head.ZWnuEh/carbon/audit/__init__.py
carbon.chain        -> /private/tmp/carbon-a0-head.ZWnuEh/carbon/chain/__init__.py
carbon.qualification -> /private/tmp/carbon-a0-head.ZWnuEh/carbon/qualification/__init__.py
```

This proves only editable installation and import discovery for A0. It does
not prove that application dependencies, scientific behavior, CI, or any
backend is healthy or production-qualified.

**Exact current-workflow base/head comparison.** The authoritative workflow is
`.github/workflows/ci.yml`. It uses Python 3.11, a test job with
`pip install -e ".[dev]"` followed by `pytest tests/ -q --tb=no`, and a lint
job with `pip install ruff black pytest`, `ruff check .`, then
`black --check .`.

| Workflow command / stage | Base `ab765b07` | A0 head `e2f91a42` | Delta |
|---|---|---|---|
| `pip install -e ".[dev]"` | Exit 1 while resolving declared dependencies: `No matching distribution found for physicsnemo` | Exit 1 at the same stage with the same first material error | No new A0 failure; the workflow test command was not reached in either sequential job. |
| `pytest tests/ -q --tb=no` (forced in the isolated lint-tool environment because the test-job install cannot complete) | Exit 2; five collection errors; first material signatures are missing `neurons`, then `carbon` | Exit 2 with the same five files and signatures | No delta. This forced run is not represented as a successful or reached test-job stage. |
| `pip install ruff black pytest` | Exit 0 | Exit 0 | No delta. |
| `ruff check .` | Exit 1; 776 errors, 544 fixable | Exit 1; 776 errors, 544 fixable | Identical inherited lint failure. |
| `black --check .` (forced after Ruff for comparison; Actions skips it after Ruff fails) | Exit 123; 66 files would reformat, 56 unchanged, and two legacy parse failures | Exit 123; 66 files would reformat, 70 unchanged, and the same two parse failures | Same failure stage/signatures; the fourteen new one-line package markers account for the additional unchanged files. |

GitHub Actions corroborates the local comparison. Base run
`32232686102` and PR-head run `32234794106` both fail the test job at
`pip install -e ".[dev]"` on unavailable `physicsnemo`, skip the test step,
install lint tools successfully, and fail Ruff with the same 776 findings;
Black is skipped in both actual runs. These are inherited CI failures, not A0
regressions.

**Maturity statement.** The lowercase namespace and fourteen behavior-free
package boundaries are **IMPLEMENTED**. Editable installation and outside-tree
imports are **TESTED** by the isolated proof above. Full dependency resolution,
the inherited test/lint baseline, scientific semantics, backend behavior,
Bittensor integration, LIVE readiness, and production qualification are not
green and are not claimed. No packaging defect was found, so A0 changes no
packaging metadata or dependency declaration. The evidence supports retaining
A0 as `done`: installation/import acceptance is proven, exact base/head
workflow failures are non-regressing, and the base-to-head diff remains solely
A0 layout, mapping, evidence, and status work.

After this evidence-only documentation update, the no-dependency editable
install and all outside-tree imports passed again; the full workflow install,
forced test/Ruff/Black comparisons, and every original A0 baseline command
retained the signatures recorded above. `git diff --check` also passed. No
generated smoke artifacts, bytecode, or editable-install metadata is included.

## 2026-08-19 — Evaluation evidence / validator audit extension

- `Design_Specs/Evaluation_Evidence_and_Validator_Audit.md` is the normative owner for execution evidence, receipts, reproducibility qualification, validator audit/re-execution, and scientific-vs-emission separation.
- `Design_Specs/Build_Out_Protocol_Extension.md` is an additive sequencing extension pending fold-in to the next `Build_Out.md` revision.
- **Do not reorder Wave A.** Continue A0 → A12 in the current board order.
- Fold receipt/evidence hooks into existing Wave A tickets only where the extension explicitly assigns them.
- JAX is the first P0 backend targeted for qualification; other backend adapters are non-emission-capable until separately qualified.
- Do not expose raw official seeds/draw IDs in receipts, cards, logs, MCP, leaderboard, or public evidence.
- No ZK/proof-of-training work is required for P0.

## 2026-08-18 — A-1 maintainer dispositions for A0

These decisions govern A0 planning; they do not implement A0 or qualify any scientific behavior.

- Establish lowercase `carbon/` as the canonical package. Support only import paths that remain necessary; do not preserve `Carbon_Logic`, `hydrogen`, or `Carbon` as canonical namespaces.
- Use the Burgers PoC as the first vertical promotion source, without treating its current science, fixed values, scoring, or disclosure behavior as qualified.
- Retire the legacy `Carbon_Logic`, `hydrogen`, and `Carbon` namespaces; reuse `neurons/` only where an A0 audit finds it useful.
- Include Julia in the first build as the verification path for the v0 data generator. Repair and scientific validation remain explicitly owned work, not implied by inclusion.
- Normalize the `docs/context/` filenames in the appropriate scoped ticket. Treat the proposal appendix in `Open_Questions.md` as the v0 direction, subject to team audit; it does not override domain-owned specifications or authorize LIVE values.

## 2026-08-17 — Canonical .agent path

- Root `/.agent/` is the only board/ticket location.
- `agent_pack/` holds protocol docs only; Hermes notes under `agent_pack/executors/hermes/`.
- Build_Out pin: **v1.4**.

## 2026-08-14 — Pack bootstrap (historical)

- Early path used Hermes + Engy; execution is now executor-agnostic.
- Scope lock: Wave A only until WAVE.md checklist is done.
- Existing repo dirs (`poc/`, `neurons/`, `Design_Specs/`) are mapped, not deleted.

## Escalate / spend log (agent fills)

| Date | Ticket | Why stop/escalate | Outcome |
|------|--------|-------------------|---------|
| | | | |
