# Codex handoff: Wave B miner research buildout

**Status:** prepared for future execution; inactive while `.agent/WAVE.md` names Wave A
**Board:** [`WAVE_B.md`](./WAVE_B.md) version 0.2
**Architecture candidate:** [`../Design_Specs/Miner_MCP_Wave_B_Research_Contract.md`](../Design_Specs/Miner_MCP_Wave_B_Research_Contract.md) version 0.2
**First ticket after activation:** [`tickets/B-01_orientation.md`](./tickets/B-01_orientation.md)

This handoff gives a fresh Codex session enough repository context to execute
Wave B one ticket at a time. It does not activate Wave B or ratify a scientific,
security, rights, economic, network, or launch decision.

## 1. Start gate

Codex must stop before implementation unless all conditions below hold at the
current checked-out commit:

1. A11 and A12 have merged and their checked Definition of Done supports their
   board status.
2. `.agent/WAVE_A_REPORT.md` exists and closes Wave A without an unresolved
   conditional state.
3. `.agent/DECISIONS.md` contains a dated activation record that names the
   approving protocol, science, security, rights, and technical roles and pins
   the exact reviewed commit plus SHA-256 hashes over the exact repository bytes
   of the board, contract, and handoff.
4. `.agent/WAVE.md` names Wave B prospectively, identifies the exact reviewed
   `.agent/WAVE_B.md` as its controlling register, and identifies B-01 as active.
5. The current board, contract, and handoff bytes match the SHA-256 values in
   the activation record. The activation change did not mutate those artifacts
   after their review.
6. A separate reviewed post-merge activation closeout in `.agent/DECISIONS.md`
   records the activation merge commit and tree, proves exact reviewed-head and
   merged-tree equality, records post-merge CI, and records named human owner
   acceptance. The closeout does not mutate the board, contract, or handoff.
7. The worktree starts clean, the branch starts from the verified current remote
   `origin/main` SHA, and Codex records the exact commit and tree.

If one condition fails, report the mismatch and stop. Reviewing the planning
package, merging it, or receiving this handoff does not satisfy the gate.

## 2. Required read order

Read the repository versions in this order before B-01 or any later ticket:

1. `CONSTITUTION.md`
2. `AGENTS.md`
3. `agent_pack/EXECUTION_PROTOCOL.md`
4. `.agent/INVARIANTS.md`
5. `.agent/WAVE.md`
6. `.agent/WAVE_B.md`
7. this handoff
8. `.agent/evidence/wave_b/README.md`
9. the current Wave B activation and ticket records in `.agent/DECISIONS.md`
10. `Design_Specs/Miner_MCP_Wave_B_Research_Contract.md`
11. the selected `.agent/tickets/B-*.md` file
12. `.agent/ORIENTATION.md`, treating its prior commit pins as historical
    evidence
13. every authority file named by the ticket
14. `Design_Specs/Build_Out.md`
15. `Design_Specs/Build_Out_Constitutional_Overlay.md`
16. the relevant sections of
    `Design_Specs/Agentic_Development_Master_Plan.md`
17. each Master Open Design Question cited by the ticket
18. `docs/context/SCIENTIFIC_REFERENCE_CANON_V4_MASTER.md` for scientific work
19. relevant implementation, tests, packaging configuration, and
    `.github/workflows/ci.yml`

After B-07S creates and owners ratify
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
| `.agent/WAVE.md` | Active-wave authority. It must activate Wave B before B-01 starts. |
| `.agent/WAVE_B.md` | Proposed Wave B ticket register, dependencies, effort, owners, and closeout gate. |
| `SPEC.md` | System/runtime doctrine. It preserves the current v1 service and records the gated migration to the separate Wave B research service. |
| `Design_Specs/Miner_MCP_Wave_B_Research_Contract.md` | Proposed behavioral and authority architecture for the local research service. B-07R ratifies it. |
| `Design_Specs/Miner_MCP.md` | Existing bounded Wave A v1 interface and pointer to the proposed v2 work. |
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
| `launch/Carbon_Testnet_to_Mainnet_Launch_Path_v1.0.2.md` | Program planning and workload view. It cannot activate a ticket or launch state. |

When two documents disagree, apply `AGENTS.md` section 2. Record one of
`NO_CONFLICT`, `DOCUMENTATION_LAG`, `IMPLEMENTATION_LAG`,
`MIGRATION_REQUIRED`, or `NEW_OWNER_DECISION_REQUIRED`. Stop on the last class.

## 4. Ticket selection

Start B-01 after activation. For each later session:

1. With current user authorization, fetch `origin main`, record the remote SHA,
   verify it against the intended base, and create the ticket branch/worktree
   from that exact SHA. Do not use `git pull`.
2. If the user names a ticket, verify its readiness. Otherwise select the first
   ready `todo` row in Wave B board order.
3. Use one reviewable branch and worktree for that ticket.
4. Do not combine tickets because they share files or concepts.
5. Run parallel lanes only when `.agent/WAVE_B.md` permits them, their
   dependencies have merged, and the lanes do not edit the same authority.
6. Stop after the ticket's bounded implementation and evidence package.

B-07R must ratify the research architecture before dependent implementation.
B-07S must ratify the exact wire protocol before service-facing code. B-07A
then implements the shared nominal v2 protocol primitives once; downstream
domain tickets consume those types, and B-07G alone owns final twelve-operation
service composition and conformance. B-GATE closes the fixture wave only after
every named predecessor has merged.

A ticket qualifies as ready only when each dependency shows authoritative
`done` status with merged evidence, each applicable contract-ratification gate
has closed, no owner question changes the implementation semantics, and every
deferred owner input has an explicit fail-closed fixture behavior. Do not skip a
blocked ticket by starting one of its dependents.

## 5. Per-ticket execution protocol

Before editing:

1. Verify branch, HEAD, tree, worktree state, dependency commits, and CI state.
2. Read the ticket and its cited authority in full.
3. Inspect current code, tests, schemas, persistence, public interfaces, PoC,
   Julia, MCP, and Landscape components relevant to the ticket.
4. Classify reuse as `KEEP`, `WRAP`, `REPAIR`, `REPLACE`, or
   `NEW_OWNER_DECISION_REQUIRED`.
5. Run the relevant pre-change baseline.
6. Classify each cited Master Open Question as `RESOLVED`,
   `DEFERRED_FAIL_CLOSED`, or `OWNER_BLOCKING`.
7. Map each Definition-of-Done item to a file, test, and evidence artifact.
8. Create `.agent/plans/<ticket>.md` before multi-module, protocol, scientific,
   persistence, concurrency, or security-sensitive work.

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
2. Run the full CPU suite, invariant suite, quality gate, package/wheel checks,
   and applicable PoC or Julia checks required by the ticket.
3. Run `git diff --check` and inspect the complete diff.
4. Record exact commands, exit codes, counts, tool versions, base/head hashes,
   artifact hashes, inherited failures, before/after deltas, and maturity claims
   in `.agent/evidence/wave_b/<ticket-id>.md`.
5. Report implementation, reuse, tests, invariants, maturity, risks, and human
   input under the headings required by `AGENTS.md`.
6. Link the evidence file from the ticket and Wave B board.
7. Bind independent review to the exact head SHA and tree. Any reviewed-tree
   change invalidates the review. The implementer cannot act as the independent
   reviewer, and independent technical review does not replace acceptance from
   the board's Accountable reviewer.
8. Leave later tickets untouched. Update board status only through the
   repository's review, authorization, and merge process.

Use board states with these meanings:

- `todo`: no authorized ticket work has started.
- `in_progress`: readiness passed and an owner authorized ticket execution.
- `blocked`: a named dependency, contract, environment, or owner decision
  prevents correct completion.
- `done`: every Definition-of-Done item has evidence, required reviewers
  accepted the exact head, the implementation merged with a tree identical to
  the reviewed head, post-merge CI passed, and a separate reviewed closeout
  change records the merge commit/tree, CI, evidence link, and Accountable
  reviewer acceptance in the board.

Code completion alone cannot produce `done`.

The implementation change prepares the evidence record with merge fields marked
pending. After merge and post-merge CI, a separate documentation closeout fills
those fields and proposes the board transition to `done`. The closeout requires
independent review and the board's Accountable reviewer.

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
identities around the unchanged v1 behavior:

- `carbon_protocol_v1` retains official submission and result authority.
- `carbon_research_v2` owns research discovery, compilation, practice, prior,
  record, and resource operations.

B-07A implements the B-07S-ratified shared refs, requests, results, resource
envelopes, errors, and service primitives. Domain tickets own their validation,
providers, stores, lifecycle, and execution semantics without redefining those
wire types. B-07G composes the completed dependencies into exactly twelve v2
operations; it neither exposes nor delegates v1 official operations.

Do not create a merged alias, network listener, credential system, production
signing system, or remote charged path in Wave B.

## 7. `get_prior` implementation target

Treat a prior as shared scientific memory, not an answer or score oracle.

An actionable `PriorGuidanceItem` targets exactly one public
`ParameterCatalog.surface_id`. It binds a public estimand, baseline and
comparison, population and scope, direction, aggregation functional,
measurement unit, resampling unit, uncertainty method, evidence origin,
epistemic type, applicability, support, stability, replication, caveats, and
cheap falsification references. Publish negative, null, mixed, and
`INSUFFICIENT_EVIDENCE` items with positive results.

`get_prior` serves either an exact approved pack reference or one atomically
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

Wave B fixtures can produce a structurally approved `TEST_ONLY` pack for the
private fixture provider. Its exact `TestOnlyPriorApprovalReceiptRef` and bytes
are pinned before B-E4, and the pack and dependent receipts retain
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

Use this prompt only after the start gate has passed. Replace `<TICKET>` with one
eligible ticket ID.

```text
In carbonphysicsai/Carbon, execute only Wave B ticket <TICKET>. With current
user authorization, fetch `origin main`, record the exact remote SHA, and create
the ticket branch/worktree from that SHA without using `git pull`. Read
CONSTITUTION.md, AGENTS.md, and `.agent/WAVE_B_CODEX_HANDOFF.md` in full, then
follow the handoff's authority order. Verify that `.agent/WAVE.md` activates
Wave B, the exact board/contract/handoff bytes match the activation record, and
every <TICKET> dependency has merged with evidence. If a check fails, stop and
report it.

Create a ticket-scoped branch and plan when required. Implement the smallest
change that satisfies the ticket Definition of Done. Do not invent scientific,
security, rights, economic, or launch values. Preserve mock/official isolation,
protected-field non-disclosure, v1 compatibility, and every applicable Carbon
invariant. Run and report the ticket's focused, subsystem, full CPU, invariant,
quality, package/wheel, and applicable PoC/Julia checks. Request independent
review and stop after this ticket. Do not begin a dependent ticket.
```

The current user instruction must authorize each fetch, commit, push, pull
request, or merge. Preserve existing changes and report git state. Do not pull,
reset, delete, commit, push, open a pull request, or merge based on this handoff
alone.

## 10. Wave closeout

B-GATE produces `.agent/WAVE_B_REPORT.md` only after every predecessor satisfies
its evidence and merge gate. Human reviewers then decide whether Wave B earned
its bounded `SPECIFIED`, `IMPLEMENTED`, and `TESTED` claims. Fixture success
cannot confer scientific, security, network, commercial, or production
qualification. Wave C starts only after `.agent/WAVE.md` changes prospectively.
