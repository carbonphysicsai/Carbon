# Codex handoff: Wave B miner research buildout

**Status:** active session entry point for bounded Wave B development while `.agent/WAVE.md` names Wave B
**Governance version:** 0.5
**Board:** [`WAVE_B.md`](./WAVE_B.md) version 0.5
**Architecture candidate:** [`../Design_Specs/Miner_MCP_Wave_B_Research_Contract.md`](../Design_Specs/Miner_MCP_Wave_B_Research_Contract.md) version 0.3
**Current ticket:** derive the selected ticket and status from the exact fetched
`origin/main` versions of `.agent/WAVE.md`, `.agent/WAVE_B.md`, and the ticket
file; require those merged records to agree. A pull-request branch may propose
a coordinated status transition for review, but it cannot authorize selection
or implementation of another ticket before that exact tree normally merges and
its exact-main push CI succeeds. This handoff does not cache or independently
select ticket state.

This handoff gives a fresh Codex session enough repository context to execute
Wave B one ticket at a time. It does not activate Wave B or ratify a scientific,
security, rights, economic, network, or launch decision.

## 1. B-01E insertion and readiness gate

B-01 is authoritatively `done` on exact main commit
`4ee58d56862d0441d5d151d79db1fe3036f1025d`, tree
`9f767ea16ffb7185ab64acff2542c7a8dcc2e339`. Executive-owner direction
inserts B-01E between B-01 and B-02A. B-01E may begin only after a fresh
`origin/main` verification proves that B-01 completion and a clean base.

B-02A and every later ticket remain unready until B-01E has normally merged
its exact reviewed tree, exact-main CI has passed, and a separate reviewed
closeout has recorded B-01E `done`. A B-01E branch, draft PR, green PR CI, or
checked implementation criteria do not satisfy that dependency.

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
9. the current Wave B governance and ticket records in `.agent/DECISIONS.md`
10. `Design_Specs/Miner_MCP_Wave_B_Research_Contract.md`
11. the selected `.agent/tickets/B-*.md` file
12. `.agent/CODE_AUTHORITY.toml`,
    `docs/development/ENVIRONMENT.md`, and
    `docs/history/LEGACY_CODE_INDEX.md` when present
13. `.agent/ORIENTATION.md`, treating its prior commit pins as historical
    evidence
14. every authority file named by the ticket
15. `Design_Specs/Build_Out.md`
16. `Design_Specs/Build_Out_Constitutional_Overlay.md`
17. the relevant sections of
    `Design_Specs/Agentic_Development_Master_Plan.md`
18. each Master Open Design Question cited by the ticket
19. `docs/context/SCIENTIFIC_REFERENCE_CANON_V4_MASTER.md` for scientific work
20. relevant implementation, tests, packaging configuration, and
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
| `launch/Carbon_Testnet_to_Mainnet_Launch_Path_v1.0.3.md` | Program planning and workload view. It cannot activate a ticket or launch state. |

When two documents disagree, apply `AGENTS.md` section 2. Record one of
`NO_CONFLICT`, `DOCUMENTATION_LAG`, `IMPLEMENTATION_LAG`,
`MIGRATION_REQUIRED`, or `NEW_OWNER_DECISION_REQUIRED`. Stop on the last class.

## 4. Current-ticket state and selection

Section 1 owns only the initial B-01 `todo` to `in_progress` transition. At the
start of every session:

1. Fetch `origin/main` without using `git pull`, record its exact commit and
   tree, and read the current wave, wave state, controlling register, selected
   ticket, and selected-ticket status from the files at that exact ref (for
   example with `git show origin/main:<path>`). Require the matching
   `origin/main` row in `.agent/WAVE_B.md` and ticket file to agree. Stop on a
   disagreement. Working-tree or pull-request-branch status fields are
   candidate review content only: even when they agree on `done`, they cannot
   select or start a dependent ticket until that exact reviewed tree normally
   merges and exact-main push CI succeeds. The one narrow exception to stopping
   is continuation or review of an already-authorized, bounded correction
   branch whose documented sole purpose is to reconcile that exact merged-main
   disagreement. Under that exception, do only the correction; the disagreement
   still prohibits selecting or implementing every other ticket.
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
6. Use one reviewable branch/worktree per ticket, do not combine tickets, run
   parallel lanes only when the board permits and their authority/files do not
   overlap, and stop after the bounded implementation and evidence package.

B-07R must ratify the research architecture before dependent implementation.
B-07S must ratify the exact wire protocol before service-facing code. B-07A
then implements the shared nominal v2 protocol primitives once; downstream
domain tickets consume those types, and B-07G alone owns final twelve-operation
service composition and conformance. B-GATE closes the fixture wave only after
every named predecessor has merged.

A ticket qualifies as ready only when each dependency shows authoritative
`done` status with merged evidence, each applicable contract-ratification gate
has closed, no unresolved reserved-human decision is needed for correct bounded
implementation, and every deferred human input has an explicit fail-closed
fixture behavior. Non-reserved material decisions follow the record-and-notify
rule below. Do not skip a blocked ticket by starting one of its dependents.

B-02A and every later Wave B ticket remain unready until B-01E is
authoritatively `done` with its reviewed tree-identical merge, successful
exact-main CI, and separate reviewed closeout evidence. Checked B-01E
Definition-of-Done boxes, an `in_progress` record, candidate evidence, or an
open implementation pull request do not satisfy that dependency.
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
already ratified contract do not require a separate notification.

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
Independent technical review, resolution of blocking findings, CI, and normal
merge remain required.

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
2. Run `./scripts/dev/ci.sh` in the canonical Carbon environment, then run
   only additional dependency groups or archived-component checks explicitly
   owned by the selected ticket.
3. Run `git diff --check` and inspect the complete diff.
4. Record exact commands, exit codes, counts, tool versions, base/head hashes,
   artifact hashes, inherited failures, before/after deltas, and maturity claims
   in `.agent/evidence/wave_b/<ticket-id>.md`.
5. Report implementation, reuse, tests, invariants, maturity, risks, and human
   input under the headings required by `AGENTS.md`.
6. Link the evidence file from the ticket and Wave B board.
7. Bind independent review to the exact head SHA and tree. Any reviewed-tree
   change invalidates the review. The implementer cannot act as the independent
   reviewer. Resolve blocking technical findings before normal merge. The
   board's Accountable reviewer assignment routes review and notification but
   requires no affirmative response unless that reviewer submits a blocking
   review under the repository's normal process.
8. Leave later tickets untouched. Update board status only through the
   repository's review, authorization, and merge process.

Use board states with these meanings:

- `todo`: no ticket work has started.
- `in_progress`: the active wave selects the readiness-passed ticket and its
  bounded execution has begun.
- `blocked`: a named dependency, contract, environment, or reserved human decision
  prevents correct completion.
- `done`: every Definition-of-Done item has evidence, required reviewers
  completed exact-head technical review with blocking findings resolved, the
  implementation merged with a tree identical to the reviewed head, post-merge
  CI passed, and a separate reviewed closeout change records the merge
  commit/tree, CI, evidence link, review outcome, and lead-notification delivery
  when applicable in the board. Affirmative role or lead approval is not
  required.

Code completion alone cannot produce `done`.

The implementation change prepares the evidence record with merge fields marked
pending. After merge and post-merge CI, a separate documentation closeout fills
those fields and proposes the board transition to `done`. The closeout requires
independent review and resolution of blocking findings; Accountable-reviewer or
lead silence is not a gate.

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
In carbonphysicsai/Carbon, execute only Wave B ticket <TICKET>. Read
CONSTITUTION.md, AGENTS.md, and `.agent/WAVE_B_CODEX_HANDOFF.md` in full, then
follow the handoff's authority order. Verify that the merged `.agent/WAVE.md`
names Wave B active in bounded development scope, names `.agent/WAVE_B.md`
version 0.5 as the controlling register, and selects <TICKET> with the same
status recorded by the board and ticket file. If <TICKET> is `in_progress`,
continue only its recorded ticket branch after verifying the recorded base,
current remote HEAD/tree, evidence, CI, and review state. Use its existing
local worktree when available; otherwise fetch and create a local tracking
checkout/worktree from the exact existing remote ticket branch, never from
`origin/main`. If <TICKET> is `todo`, verify that every dependency is
authoritatively `done`, then, with current user authorization, fetch
`origin main`, record the exact remote SHA/tree, and create the dedicated
ticket branch/worktree from that SHA without using `git pull`.
Confirm that no reserved human decision is being invented. If a check fails,
stop and report it.

Create a ticket-scoped plan when required. Implement the smallest change that
satisfies the ticket Definition of Done. Do not invent scientific,
security, rights, economic, or launch values. Preserve mock/official isolation,
protected-field non-disclosure, v1 compatibility, and every applicable Carbon
invariant. Run and report `./scripts/dev/ci.sh` plus only ticket-owned optional-
group checks. Do not request native-Windows diagnostics or archived PoC,
Julia, JAX, chain, GPU, miner, validator, or other legacy validation unless
the selected ticket explicitly owns it. Request independent review and stop
after this ticket. Do not begin a dependent ticket.
For every material decision, record it, include the required `Lead notification`
section in the pull request, and notify issue #42 mentioning `@harshaa765`.
Notification is non-blocking unless the lead submits `REQUEST_CHANGES` or an
explicit `BLOCKED` direction for the affected change.
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
