# Codex handoff: Wave B miner research buildout

**Status:** active session entry point for bounded Wave B development while `.agent/WAVE.md` names Wave B
**Governance version:** 1.1
**Board:** [`WAVE_B.md`](./WAVE_B.md) version 1.1
**Working engineering architecture:** [`../Design_Specs/Miner_MCP_Wave_B_Research_Contract.md`](../Design_Specs/Miner_MCP_Wave_B_Research_Contract.md) version 0.4, effective as the normally merged B-07R bounded engineering architecture
**Current ticket:** derive the selected ticket and status from the exact fetched
`origin/main` versions of `.agent/WAVE.md`, `.agent/WAVE_B.md`, and the ticket
file; require those merged records to agree. A pull-request branch may propose
a coordinated status transition for review, but it cannot authorize selection
or implementation of another ticket before the complete exact-head review,
normal-merge, exact-main, and external-receipt predicate in
`.agent/DELIVERY_PROTOCOL.md` passes. This handoff does not cache or
independently select ticket state.

This handoff gives a fresh Codex session enough repository context to execute
Wave B one ticket at a time. It does not activate Wave B or ratify a scientific,
security, rights, economic, network, or launch decision.

## 1. Completed foundations, B-04 contract, and B-01F delivery governance

B-01 is authoritatively `done` on exact main commit
`4ee58d56862d0441d5d151d79db1fe3036f1025d`, tree
`9f767ea16ffb7185ab64acff2542c7a8dcc2e339`. Executive-owner direction
inserted B-01E between B-01 and B-02A. B-01E's independently reviewed
implementation head `2025e235c83a994ed4f16c9a3a9d3c2766700061`, tree
`4a506a1ae46cfcbf180eb5dbf68ed50caa0f1e09`, normally merged in PR #58 as
`b4744a435e8bc7220c7dc03e6a993bb0a54c16a5` with the exact reviewed tree
preserved. Exact-main push run `33319267255` passed on that merge.

PR #59 normally merged the B-01E closeout as
`e10107644d5fb0c7d69b153c0c3b8a03b93b19bb`, tree
`0f6beb5b000e771fd7e050f150e1074ea2a6fb1f`; exact-main CI `33321131062`
passed and selected B-02A. Governance PR #61 independently reviewed exact
head `fb220c14966aa3505d95b199ce168bf31064d1ba`, normally merged as
`7bdf4971b7d0b3ee8ffde577595a49c6b5456961` with tree
`109bb59e117d25cbdfddcc4c4a8fe6e3f3f34cdb`, and passed exact-main CI
`33329693544`. Its `.agent/DELEGATED_DECISION_PROTOCOL.md` controls working-
contract implementation: record and notify material engineering decisions,
continue without affirmative lead response, and stop the affected change on
an observed `CHANGE`, `BLOCKED`, or `REQUEST_CHANGES`. Human-reserved values
remain fail closed. At that historical point B-02A was the only active ticket;
later tickets were unstarted.

PR #60 later normally merged exact reviewed B-02A head
`f285399138ecfe95352d429bc26051b0a5fecbcf`, tree
`61a4463ac459f7fe96545f2746511d6940246f57`, as
`58ea866de52e3853b0b45e3217ee0625302aa663` with the same tree. Exact-head
CI `33341717012`, Greptile 5/5 with no blocking failure and zero unresolved
threads, and exact-main CI `33342015346` passed. B-02A is `done` only in its
bounded engineering scope.

PR #62 normally merged exact reviewed B-07R head
`038aa3ffe51aaafe99803553380c396429144977` as
`6e2a2640a6bd26755064acb0616382c8dcc0ba37`, preserving exact tree
`5cf1aaf1fd11ef4775c170dd938c3190fa14145b`. Exact-head CI `33347664046`,
Greptile 5/5 with zero unresolved threads, and exact-main CI `33347826166`
passed; issue #42 comment `5472621851` records completion. B-07R is `done` in
bounded engineering-architecture scope. Version 0.7 selected B-02B.

PR #64 normally merged exact reviewed B-02B head
`68189e7068715a5d8054f0f7e64dc981ae1c37aa` as
`b10b6e74fb3f8ab8a7427a6763c7db4f41341083`, preserving exact reviewed tree
`45273c527684b94afeb2f01b66a774b5426b6e0e` and ordered parents
`1c012468545f448aa758daf7dec17e409bb13bbc`,
`68189e7068715a5d8054f0f7e64dc981ae1c37aa`. Exact-head CI `33362051770`,
Greptile 5/5 on exact-head check `99413062552` with zero unresolved threads,
and exact-main CI `33368352662` passed. B-02B is `done` in bounded engineering
scope. Version 0.8 selected B-02C.

PR #66 normally merged repaired exact reviewed B-02C head
`a30865d2349f1cc6e725f1ea15e923f8d7893e4c` as
`1dc41288e2d0e516de21d05dc168b188791c39f5`, preserving exact reviewed tree
`eb9b0c9b899cc4be9c8e9b22c16a5a3a48406a12` and ordered parents
`319a765860ac6e93018124bd57a84bfd6679672e`,
`a30865d2349f1cc6e725f1ea15e923f8d7893e4c`. Repaired exact-head CI
`33388174967`, Greptile 5/5 on exact-head check `99475440630` with zero
comments, annotations, or unresolved threads, and exact-main CI `33388595061`
passed. B-02C is `done` in bounded engineering scope. Version 0.9 selected
B-03.

PR #69 normally merged exact reviewed B-03 head
`702bf274b1a0c4bfefa075d8da08d3e7217a53d1` as
`d5d1372f1311132ed9d60e10e36c4fb7d43a2473`, preserving exact reviewed tree
`65dc9f5da4368482ad8ece155a63ff24ef46bf24` and ordered parents
`b86daa5d8b0f8b3e86bb82c2661f405747a200df`,
`702bf274b1a0c4bfefa075d8da08d3e7217a53d1`. Exact-head CI
`33452836347`, Greptile check `99686337091` with all 36 files reviewed and
zero comments or unresolved threads, and exact-main push CI `33460078744`
passed. Issue #42 closeout comment `5487728238` records completion. B-03 is
`done` only in bounded merged engineering scope. Version 1.0 selects B-04
`in_progress` for working-contract authoring only. B-04 implementation remains
prohibited until the exact contract tree normally merges and exact-main CI
succeeds.

PR #72's external completion receipt establishes that the exact reviewed B-04
bounded engineering contract passed required exact-head checks and Greptile,
normally merged with reviewed-tree preservation, and passed exact-main checks.
B-04 is `SPECIFIED` and its engineering contract is ratified; it remains
unimplemented and unqualified. `OWNER-DX-01` inserts B-01F before runtime and
queues B-01G as non-blocking `todo`. Version 1.1's B-01F `done` and B-04
runtime selection are conditional: they become effective only after the exact
B-01F candidate passes exact-head `Merge gate` and Greptile with zero
unresolved threads; normally merges with reviewed-tree preservation; passes
exact-main `Merge gate`; and has its completed normalized external receipt
posted. Until then B-04 runtime is paused.

## 2. Required read order

Read the repository versions in this order before B-01 or any later ticket:

1. `CONSTITUTION.md`
2. `AGENTS.md`
3. `agent_pack/EXECUTION_PROTOCOL.md`
4. `.agent/DELIVERY_PROTOCOL.md`
5. `.agent/DELEGATED_DECISION_PROTOCOL.md`
6. `.agent/INVARIANTS.md`
7. `.agent/WAVE.md`
8. `.agent/WAVE_B.md`
9. this handoff
10. `.agent/evidence/wave_b/README.md`
11. the current Wave B governance and ticket records in `.agent/DECISIONS.md`
12. `Design_Specs/Miner_MCP_Wave_B_Research_Contract.md`
13. the selected `.agent/tickets/B-*.md` file
14. `.agent/CODE_AUTHORITY.toml`,
    `docs/development/ENVIRONMENT.md`, and
    `docs/history/LEGACY_CODE_INDEX.md` when present
15. `.agent/ORIENTATION.md`, treating its prior commit pins as historical
    evidence
16. every authority file named by the ticket
17. `Design_Specs/Build_Out.md`
18. `Design_Specs/Build_Out_Constitutional_Overlay.md`
19. the relevant sections of
    `Design_Specs/Agentic_Development_Master_Plan.md`
20. each Master Open Design Question cited by the ticket
21. `docs/context/SCIENTIFIC_REFERENCE_CANON_V4_MASTER.md` for scientific work
22. relevant implementation, tests, packaging configuration, and
    `.github/workflows/ci.yml`

After B-07S creates, ratifies, and normally merges
`Design_Specs/Miner_MCP_Wave_B_Service_Protocol.md`, read it before any ticket
that uses wire-visible v2 behavior.

Read `Business/Business_Canon.md` and the ticket-relevant business documents
before work involving contributor rights, publication rights, fees, or customer
evidence. Read `docs/publications/README.md` before changing a public claim.

Do not rely on chat history, this handoff's summary, or historical sketches when
the domain owner provides a current repository contract.

## 3. Reconciled document roles

| File | Role after this planning reconciliation |
|---|---|
| `.agent/WAVE.md` | Active-wave and current-ticket-selection authority. Read its current wave, state, controlling register, selected ticket, and selected-ticket status; require the matching board and ticket records to agree rather than inferring current state from this handoff or a historical summary. |
| `.agent/WAVE_B.md` | Controlling Wave B ticket register, dependencies, effort, review routing, and closeout gate. |
| `.agent/CODE_AUTHORITY.toml` | Machine-readable current implementation/test roots, exact archive identities, and retired runtime/path boundary. |
| `docs/development/ENVIRONMENT.md` | Sole ordinary developer/evidence environment and command guide after B-01E. |
| `docs/history/LEGACY_CODE_INDEX.md` | Retrieval map for quarantined executable prototypes. Archive presence grants no current authority. |
| `SPEC.md` | System/runtime doctrine. It preserves the current v1 service and records the gated migration to the separate Wave B research service. |
| `Design_Specs/Miner_MCP_Wave_B_Research_Contract.md` | B-07R agent-selected working behavioral/authority architecture for the local research plane; merged engineering authority only after its conditional completion gate. B-07S owns exact protocol mechanics. |
| `Design_Specs/Miner_MCP.md` | Existing bounded Wave A v1 interface and pointer to the separate Wave B research architecture. |
| `Design_Specs/Strategy_Schema.md` | Strategy v1 envelope. B-02B supplies Challenge-bound executable meaning through the catalog, assembly contract, and compiler. |
| `Design_Specs/Data_Management.md` | Owns TRAIN/EVAL/STRESS data roles, nominal entropy contexts, and the rule that a resolved training policy binds abstract purposes rather than seed authority. |
| `Design_Specs/Trustless_Verification.md` and `Evidence_and_Envelope_Standards.md` | Own reference qualification, uncertainty-bearing evidence, decision resolution, and the bounded trust-minimized claim. No solver or validator earns truth authority by reputation. |
| `Design_Specs/Landscape_Agent.md` | Prior evidence semantics, publication boundaries, and later learned-prior direction. |
| `Design_Specs/Physics_Intelligence_System.md` | Epistemic labels and compounding-knowledge architecture. It does not grant a prior, agent, or fixture scientific authority. |
| `Design_Specs/Scoring.md` and `Scoring_Formulas.md` | Official score authority and forbidden research/prior/practice/resource inputs. |
| `Design_Specs/Launch_Bar.md` | External activation and qualification gates. Fixture success cannot bypass them. |
| `Design_Specs/Build_Out.md`, its constitutional overlay, and `Agentic_Development_Master_Plan.md` | Detailed sequencing interpreted through the Wave B board and repository constitution. The board owns the bounded ticket decomposition. |
| `Design_Specs/POC_Burgers_FNO.md` | Historical lean-loop source and prospective official TrainEval shape. It requires nominally separate practice rights and must pass the B-01 reuse audit before implementation. |
| `Design_Specs/Compute_Optimization.md` and `JAX_Optimization.md` | Compute guidance. Scheduling cannot vary the registered exam, and practice uses separate workers and quotas. |
| `Design_Specs/Operations.md` | Target operations contract. Its maturity notice prevents desired-state infrastructure from becoming deployment evidence. |
| `Design_Specs/Runtime_Julia_Truth_Oracle.md` | Historical-path, reconciled target for a Challenge-bound Julia reference capability. It grants no solver authority and remains subordinate to B-04's ratified contract. |
| `Design_Specs/Specialist_Bank.md` | Product-plane authority. It cannot define miner-prior, research-service, official-score, or wire semantics. |
| `docs/context/MASTER_OPEN_DESIGN_QUESTIONS.md` | Human and evidence decisions. A ticket may implement a fail-closed seam but cannot invent an answer. |
| `docs/context/IMPLEMENTED_VS_SPECIFIED_CURRENT.md`, `Implemented_vs_Specified`, `DEFENSIBILITY_REGISTER.md`, `Carbon_Context.md`, and `Open_Questions.md` | Current maturity and terminology projections reconciled to the same reference, practice, prior, and Wave B authority boundaries. They do not supersede domain owners. |
| `Design_Specs/Implementation.md` | Historical illustrative code under its authority notice. It cannot restore retired noisy-prior, score-estimation, generic-mode, or simulated-authority behavior. |
| `examples/llm_agent_prompt.md` | Non-normative current-v1 and gated candidate-v2 mining-agent examples using registered operation names. |
| `launch/Carbon_Testnet_to_Mainnet_Launch_Path_v1.0.3.md` | Program planning and workload view. It cannot activate a ticket or launch state. |

When two documents disagree, apply `AGENTS.md` section 2. Record one of
`NO_CONFLICT`, `DOCUMENTATION_LAG`, `IMPLEMENTATION_LAG`,
`MIGRATION_REQUIRED`, or `NEW_OWNER_DECISION_REQUIRED`. For the last class,
stop and route the affected human-reserved behavior; continue unrelated
authorized work only where the value remains explicit and fail closed.

## 4. Current-ticket state and selection

Section 1 records the proven B-02A, B-07R, and B-02B closeouts. At the
start of every session:

1. Fetch `origin/main` without using `git pull`, record its exact commit and
   tree, and read the current wave, wave state, controlling register, selected
   ticket, and selected-ticket status from the files at that exact ref (for
   example with `git show origin/main:<path>`). Require the matching
   `origin/main` row in `.agent/WAVE_B.md` and ticket file to agree. Stop on a
   disagreement. Working-tree or pull-request-branch status fields are
   candidate review content only: even when they agree on `done`, they cannot
   select or start a dependent ticket until the complete exact-head review,
   normal-merge, exact-main, and external-receipt predicate in
   `.agent/DELIVERY_PROTOCOL.md` passes. The one narrow exception to stopping is
   continuation or review of an already-authorized, bounded correction branch
   whose documented sole purpose is to reconcile that exact merged-main
   disagreement. Under that exception, do only the correction; the
   disagreement still prohibits selecting or implementing every other ticket.
2. If the selected ticket is `in_progress`, continue or review only that ticket
   from its recorded ticket branch. If its recorded local worktree exists,
   verify and use it. If that machine-local worktree is unavailable, fetch the
   exact existing remote ticket branch, verify its remote HEAD/tree against the
   current pull request and evidence record, and create a local tracking
   checkout/worktree at that exact head. Creating that local tracking checkout
   is continuation, not a replacement ticket branch. Do not branch from
   `origin/main`, reset/rebase the ticket branch, discard another worktree's
   uncommitted state, or duplicate the ticket. When item 1's bounded-correction
   exception applies, continue or review the exact documented correction branch
   instead and do not return to the superseded ticket branch. Stop if the
   applicable remote branch is absent or its identity cannot be reconciled.
   Before work, verify the recorded base, current HEAD/tree, evidence, CI, and
   blocking-review state.
3. If the selected ticket is `todo`, verify readiness, then, with current user
   authorization, fetch `origin main`, record its exact SHA/tree, and create
   the dedicated ticket branch/worktree from that exact base. Do not use
   `git pull`.
4. If the previously selected ticket is authoritatively `done` on the exact
   fetched `origin/main`, its required post-merge evidence is complete, and no
   ticket is `in_progress`, use a user-named ready ticket or otherwise the first
   ready `todo` row in Wave B board order. Record the new selection and status
   consistently in the wave, board, and ticket records on that ticket's branch
   before implementation.
5. A `blocked` ticket does not permit starting one of its dependents. An
   unrelated ticket may be selected only if its own dependency/readiness gate
   passes and the board permits that lane.
6. Use one reviewable branch/worktree and one PR per ticket by default. Write
   the working contract first, then coherent vertical implementation/test
   slices, and review the whole final tree together. A separate contract PR
   requires an exception in `.agent/DELIVERY_PROTOCOL.md`; ticket size alone
   is not one. Run parallel lanes only when the board permits and their
   authority/files do not overlap.

B-07R must ratify the research architecture before dependent implementation.
B-07S must ratify the exact wire protocol before service-facing code. B-07A
then implements the shared nominal v2 protocol primitives once; downstream
domain tickets consume those types, and B-07G alone owns final composition and
conformance for the B-07S-ratified closed operation set. B-GATE closes the
fixture wave only after every named predecessor has merged.

A ticket qualifies as ready only when each dependency shows authoritative
`done` status with merged evidence, its required working contract exists, no
unresolved reserved-human decision is needed for the affected bounded
behavior, and every deferred human input has an explicit fail-closed path.
Non-reserved material decisions follow the record-and-notify rule below. Do
not skip a blocked ticket by starting one of its dependents.

B-01E, B-02A, B-07R, B-02B, B-02C, and B-03 are complete at the identities in
section 1. B-04's bounded engineering contract is ratified, but its runtime is
paused behind B-01F. Version 1.1's B-01F `done` and B-04 runtime selection are
effective only after the exact B-01F reviewed candidate normally merges with
tree preservation, exact-main `Merge gate` succeeds, and the completed
normalized external receipt is posted. Then create a fresh
`agent/b-04-reference-truth` branch/worktree from that verified exact main. No
B-04 runtime, solver, fixture runner, Julia service, Cole–Hopf routine,
artifact store, transport, measurement, scoring, Dossier, package-authority,
or test implementation belongs in B-01F. B-01G remains `todo` and does not
block B-04.
`B-02` is retired umbrella shorthand only; B-02A, B-02B, and B-02C retain their
exact individual dependency rows.

## 5. Per-ticket execution protocol

### Development decisions and lead notification

Development authorization comes from the active wave and selected ticket, not
prior multi-role approval. A material decision changes or selects architecture
or domain ownership; a contract or invariant; a public interface or persisted
schema; a scientific assumption or evidence interpretation; a security or
disclosure boundary; a rights or data-use policy; an operational or resource
policy; Wave or ticket sequencing; or a `KEEP`, `WRAP`, `REPAIR`, or `REPLACE`
disposition with cross-ticket impact. Routine implementation details within an
already recorded working contract do not require a separate notification.

For each material-decision-affecting pull request:

1. record the durable decision in `.agent/DECISIONS.md` or the applicable
   ticket, plan, or specification;
2. add a pull-request section titled `Lead notification` that identifies the
   decision ID or heading, affected ticket, affected files, selected approach,
   alternatives rejected, invariant/interface/sequencing effects,
   reversibility and migration effect, and notification issue/comment; and
3. post or update issue #42 and mention designated SciML / Technical Lead
   Harshdeep Sharma (`@harshaa765`).

Notification proves delivery, not approval. Do not wait for an affirmative
response, reaction, approval, or waiting period. A lead `REQUEST_CHANGES`
review or explicit `BLOCKED` direction pauses the affected pull request but not
unrelated work. A post-merge adjustment uses a new bounded branch and later
normally merged repository decision; mark the old decision superseded rather
than rewriting historical evidence. Current merged authority controls until
that change merges.

The board's Accountable reviewer column routes technical/domain review and
notification. It creates no affirmative pre-approval or silence gate.
Greptile is the routine independent correctness review Carbon waits for.
Repair every valid finding, require zero unresolved Greptile threads, all
scope-required exact-head checks and `Merge gate`, and normal merge. Human and
domain review is asynchronous unless current authority explicitly reserves the
affected value or acceptance decision. A documented invalid finding may be
closed with rationale.

This rule does not authorize agents to invent or approve scientific truth,
thresholds, tolerances, population or SamplingPlan claims, qualification,
security acceptance, rights/legal policy, live economics, launch/deployment,
or production, `LIVE`, frontier, product, settlement, chain, weight, or
emission authority. Missing reserved human decisions remain explicit, bounded,
and fail closed; unrelated fixture, schema, interface, test, or infrastructure
development may continue.

Before editing:

1. Verify branch, HEAD, tree, worktree state, dependency commits, and CI state.
2. Read the ticket and its cited authority in full.
3. Inspect current canonical code, tests, schemas, persistence, and public
   interfaces relevant to the ticket. Consult
   `docs/history/LEGACY_CODE_INDEX.md` and the immutable archive only when the
   selected ticket explicitly owns reuse or migration of an archived
   component. Archive presence grants no current implementation authority.
4. Classify reuse as `KEEP`, `WRAP`, `REPAIR`, `REPLACE`, or
   `NEW_OWNER_DECISION_REQUIRED`.
5. Run the relevant pre-change baseline.
6. Classify each cited Master Open Question as `RESOLVED`,
   `DEFERRED_FAIL_CLOSED`, or `OWNER_BLOCKING`.
7. Map each Definition-of-Done item to a file, test, and evidence artifact.
8. Create `.agent/plans/<ticket>.md` before multi-module, protocol, scientific,
   persistence, concurrency, or security-sensitive work.
9. On macOS, Windows, or noncanonical Linux, use
   `./scripts/dev/canonical.sh`; never call native-host output canonical.

During implementation:

- Implement the ticket Definition of Done and no broader scope.
- Preserve existing v1 public behavior unless the ticket owns a prospective
  versioned change.
- Use typed fail-closed placeholders for missing human values.
- Keep mock, practice, prior, forecast, and structural-research evidence outside
  official score and lifecycle paths. Only B-07F may exercise the unchanged
  A5/A7/A8-shaped fixture-official path, and its provenance remains incapable
  of creating LIVE, frontier, network, settlement, or scientific authority.
- Add tests for malformed input, bounds, identity, disclosure, authority,
  determinism, concurrency, failure classification, and installed-package
  behavior where the ticket applies.

Before requesting review:

1. Run focused tests and the ticket's subsystem tests.
2. Run `./scripts/dev/ci.sh` in the canonical Carbon environment, through
   `./scripts/dev/canonical.sh` when outside it, then run
   only additional dependency groups or archived-component checks explicitly
   owned by the selected ticket.
3. Run `git diff --check` and inspect the complete diff.
4. Record stable scope, authority, starting base, decisions, expected manifest,
   commands, invariants, inherited failures, deltas, maturity ceiling, and the
   conditional predicate in `.agent/evidence/wave_b/<ticket-id>.md`. Put final
   head/tree/check/review/merge/exact-main identities in the external receipt.
5. Report implementation, reuse, tests, invariants, maturity, risks, and human
   input under the headings required by `AGENTS.md`.
6. Link the evidence file from the ticket and Wave B board.
7. Bind Greptile and all required checks to the exact head SHA and tree. Any
   reviewed-tree change invalidates that evidence. Resolve valid technical
   findings and require zero unresolved Greptile threads before normal merge.
   Accountable-reviewer routing requires no affirmative response unless that
   reviewer submits a blocking direction under the repository's process.
8. Unless owner direction explicitly says to stop before merge, normally merge
   the unchanged clean candidate with an exact expected-head guard, verify
   ordered parents/reviewed-tree/exact-main `Merge gate`, post the external
   receipt, and continue to the next ready ticket authorized by the session.

Use board states with these meanings:

- `todo`: no ticket work has started.
- `in_progress`: the active wave selects the readiness-passed ticket and its
  bounded execution has begun.
- `blocked`: a named dependency, contract, environment, or reserved human decision
  prevents correct completion.
- `done`: every Definition-of-Done item has evidence, exact-head `Merge gate`
  and Greptile passed with every valid finding repaired and zero unresolved
  threads, the implementation normally merged with a tree identical to the
  reviewed head, exact-main `Merge gate` passed, and the external receipt
  pointer records the merge, CI, review outcome, and lead-notification delivery
  when applicable. Affirmative role or lead approval is not required.

Code completion alone cannot produce `done`.

The implementation change may prepare a conditional completion record and
next-ticket selection. Conditional `done` becomes authoritative only when the
exact reviewed tree passes scope-required exact-head checks, `Merge gate`, and
Greptile with all valid findings repaired and zero unresolved threads; normally
merges with exact second-parent/tree identity; and exact-main `Merge gate`
passes; and the completed normalized external receipt is posted. Dynamic
identities use the external receipt. Do not open a recursive closeout PR or
commit merely to store/retrigger them. Accountable-reviewer or lead silence is
not a gate.

## 6. Miner research boundaries

Wave B keeps Strategy v1 declarative:

```text
TrainingStrategy
  + ParameterCatalog
  + CandidateAssemblyContract
  + deterministic StrategyCompiler
  = ResolvedConstructionPlan or typed rejection
```

Reject unknown, unused, incompatible, coerced, silently defaulted, silently
clamped, and unsupported fields. A registered hybrid backbone may expose a
learned slot inside Carbon-owned assembly. A closed catalog may expose
Challenge-bounded training sampling, curriculum, or augmentation levers. The
compiler materializes one canonical `ResolvedTrainingSamplingPolicy`, denoted
`R_strategy`; `TrainingSamplingPolicyRef` content-addresses those bytes, and the
validator derives the actual training seeds and draws. Wave B does not accept participant
code, imports, executables, dependencies, composition graphs, raw/custom data,
miner seeds, or official evaluation controls.

Subject to B-07S ratification, the Wave B local topology introduces two distinct
authority planes around the unchanged v1 behavior:

- the existing exact Wave-A service retains official submission/result
  authority; and
- a separate local/in-process research plane owns discovery, compilation,
  practice, prior, record, and resource capabilities.

B-07A implements the B-07S-ratified shared refs, requests, results, resource
envelopes, errors, and service primitives. Domain tickets own their validation,
providers, stores, lifecycle, and execution semantics without redefining those
wire types. B-07S owns exact service/version identifiers and operation names;
B-07G composes the completed dependencies into the B-07S-ratified closed operation
set and neither exposes nor delegates v1 official operations.

Do not create a merged alias, network listener, credential system, production
signing system, or remote charged path in Wave B.

## 7. Prior-retrieval implementation target

Treat a prior as shared scientific memory, not an answer or score oracle.

An actionable `PriorGuidanceItem` targets exactly one public
`ParameterCatalog.surface_id`. It binds a public estimand, baseline and
comparison, population and scope, direction, aggregation functional,
measurement unit, resampling unit, uncertainty method, evidence origin,
epistemic type, applicability, support, stability, replication, caveats, and
cheap falsification references. Publish negative, null, mixed, and
`INSUFFICIENT_EVIDENCE` items with positive results.

The future prior-retrieval capability (exact operation name owned by B-07S)
serves either an exact authorized pack reference or one atomically
resolved active-channel snapshot. The same reference returns the same canonical
bytes to each requester. The service performs no requester-specific private
query or server-side personalization. Agents combine the pack with private
research records on their side.

Keep official seeds, cases, draw identities, realized stress composition,
reference outputs, exact margins, current-frontier recipes, private experiment
records, identifying counts, and protected context out of public packs.

The publisher must enforce source eligibility, rights, lineage influence caps,
coarsening, joint-cell suppression, lag, release epochs, and a persistent
cumulative-disclosure ledger. Use the acyclic publication graph:

```text
PreviousIndexSnapshotRef
        ↓
PriorPublicationReceipt
        ↓
NewIndexSnapshot
```

B-07S defines the genesis previous-index sentinel. The transition digest must
exclude the publication receipt and resulting-index reference. The ledger
compare-and-swap and index activation form one transaction. Any changed state
requires new authorization.

Wave B fixtures can produce a structurally authorized `TEST_ONLY` pack for the
private fixture provider. Its exact B-07S-ratified test-only authorization
receipt reference and bytes are pinned before B-E4, and the pack and dependent receipts retain
`TEST_ONLY / NOT_UTILITY_QUALIFIED` permanently. A passing preregistered
gauntlet creates separate evidence about the bounded Wave B mechanism; it does
not mutate or promote the fixture pack. This fixture gate is not a
`PriorPublicationReceipt`, public-channel activation, or utility claim. Wave B
cannot activate `BOOTSTRAP_PUBLIC` or `LEARNED_PUBLIC` or install a v2-backed
public v1 provider.

## 8. Evidence and human decisions

Codex may implement schemas, fixtures, validation, storage, adapters, test-only
signer seams, and evidence collection. The named human owners supply or approve:

- the physical population, SamplingPlan, reference adequacy, measurement
  policy, gates, transforms, weights, and decision resolution;
- catalog values, supported backbones, allowed `R_strategy` policies and
  training support;
- resource policy/rails, forecast calibration, and external practice scope;
- prior estimands, cohorts, lag, cadence, bands, diversity policy, release
  content, rights, approvers, and future key custody;
- utility and conditional-leakage limits, live identity linkage, quotas, fees,
  security acceptance, qualification, and launch.

The Wave B board maps each input to an owner, ticket, Master Open Question, and
fail-closed behavior. Missing input must leave the affected capability
unavailable or fixture-only.

## 9. Session prompt template

Use `agent_pack/CODEX_TICKET_LAUNCHER.md`. After B-01F's conditional
completion predicate passes, the complete B-04 launcher is only:

```text
Execute the current selected Carbon ticket end-to-end under
`agent_pack/CODEX_TICKET_LAUNCHER.md`. Use current repository authority,
exact-head CI, Merge gate and Greptile. Merge and advance when clean. Keep all
human-reserved authority fail closed.
```

The active user/session authorization defines the bounded external-write scope.
Preserve existing changes and report git state. Do not pull, reset, delete,
rewrite history, force-push, or expand beyond that scope. When the session is
authorized end to end and no explicit stop-before-merge direction exists, do
not ask for another prompt solely to commit, push, open the ticket PR, normally
merge its unchanged clean reviewed head, verify exact main, or advance to the
next ready ticket.

## 10. Wave closeout

B-GATE produces `.agent/WAVE_B_REPORT.md` only after every required predecessor
except explicitly non-blocking B-01G satisfies its evidence and merge gate.
Exact-head Greptile, required CI and `Merge gate`, normal merge, and exact-main
`Merge gate` decide whether bounded engineering evidence supports
`SPECIFIED`, `IMPLEMENTED`, and `TESTED` claims. Human-reserved scientific,
security, rights, economic, qualification, LIVE, launch, and production
authority remains separate and fail closed. Fixture success cannot confer
scientific, security, network, commercial, or production qualification. Wave C
starts only after `.agent/WAVE.md` changes prospectively.
