# B-02A scientific authoring contracts — contract-ratification plan

**Ticket:** B-02A, `Scientific authoring and canonical-case contracts`
**Phase:** prerequisite contract ratification only
**Status:** owner-review contract candidate in progress; implementation prohibited
**Exact authority base:** `e10107644d5fb0c7d69b153c0c3b8a03b93b19bb`
**Base tree:** `0f6beb5b000e771fd7e050f150e1074ea2a6fb1f`
**Branch:** `agent/b-02a-contract-ratification`
**Worktree:** `C:/Users/Ryan_/Documents/Codex/2026-08-30/live-main-remains-at-the-b`
**Contract target:** `Design_Specs/Scientific_Challenge_Authoring_Contract.md` version 0.1, `OWNER-REVIEW CONTRACT CANDIDATE`

This plan is limited to proposing, validating as documentation, delivering,
and requesting independent review of the B-02A scientific authoring contract.
It does not authorize runtime schemas, loaders, canonicalizers, stores,
generators, reference runners, measurements, tests of an implementation,
package changes, qualification, or any later ticket.

## 1. Start gate and exact base

The pre-edit gate established:

- saved repository root `C:/Users/Ryan_/source/Carbon`;
- preserved existing checkout `agent/b-01e-closeout` at
  `f08f2f2f03d10fce41833679cfd89c85838b9b54`, clean;
- one pre-existing worktree only, with no local modification, relocation,
  stash, reset, clean, or deletion;
- `git fetch origin --prune` completed without `git pull`;
- fetched `origin/main` exactly equals the authority base and base tree above;
- PR #59 is the normal two-parent B-01E closeout merge, with ordered parents
  `b4744a435e8bc7220c7dc03e6a993bb0a54c16a5` and
  `f08f2f2f03d10fce41833679cfd89c85838b9b54`;
- exact-main CI run `33321131062` completed successfully on the authority base;
- B-01 and B-01E are `done`, and B-02A is selected next, `todo`, and
  unstarted in the fetched base records;
- no local branch, remote branch, worktree, or open pull request matched the
  retired `B-02` umbrella shorthand or exact B-02A before or after fetch;
- issue #42 contains no explicit B-02A `BLOCKED` or `REQUEST_CHANGES`
  direction; its `WAITING_DEPENDENCY` reviewer-queue state is not a start
  prohibition; and
- open PR #40 remains non-authoritative research-candidate material. Its
  fixed-versus-variable-viscosity seam is noted, but no code, dependency,
  proposed value, Cole–Hopf witness, or other implementation is copied or
  adopted.

If `origin/main` moves before delivery, the branch base is not silently
changed. Any rebase, reset, force-push, or new-base continuation requires new
authorization and is outside this plan.

## 2. Authority set and maturity

The contract is reconciled against the following exact-base authority, in the
required read order:

1. `CONSTITUTION.md`;
2. `AGENTS.md`;
3. `agent_pack/EXECUTION_PROTOCOL.md`;
4. `.agent/INVARIANTS.md`;
5. `.agent/WAVE.md`;
6. `.agent/WAVE_B.md` version 0.5;
7. `.agent/WAVE_B_CODEX_HANDOFF.md`;
8. `.agent/evidence/wave_b/README.md`;
9. current Wave B records in `.agent/DECISIONS.md`;
10. `.agent/tickets/B-02A_scientific_authoring_contracts.md`;
11. `.agent/CODE_AUTHORITY.toml`;
12. `docs/development/ENVIRONMENT.md`;
13. `docs/history/LEGACY_CODE_INDEX.md`;
14. `.agent/ORIENTATION.md`, with historical pins treated as evidence;
15. `Design_Specs/Build_Out.md`;
16. `Design_Specs/Build_Out_Constitutional_Overlay.md`, especially §8;
17. `Design_Specs/Agentic_Development_Master_Plan.md`;
18. `docs/context/MASTER_OPEN_DESIGN_QUESTIONS.md`;
19. `docs/context/SCIENTIFIC_REFERENCE_CANON_V4_MASTER.md`, where v4 remains
    owner-canonical and v4.1 additions remain candidate amendments;
20. `Design_Specs/Science_GTM_Wave_Integration_Plan.md`;
21. `docs/context/SCIENCE_GTM_OWNER_DECISION_RECORD_2026-08-27.md`;
22. `Design_Specs/Science_GTM_Engineering_Ticket_Delta.md`;
23. `Design_Specs/Miner_MCP_Wave_B_Research_Contract.md` version 0.3,
    `OWNER-REVIEW CONTRACT CANDIDATE`, not ratified B-07R authority;
24. the current domain owners `Data_Management.md`,
    `Generator_Creation.md`, `Generator_Validation.md`,
    `Evidence_and_Envelope_Standards.md`, `Trustless_Verification.md`,
    `Scoring.md`, `Strategy_Schema.md`, and `Launch_Bar.md`, preserving each
    document's ratified-versus-candidate maturity; and
25. current canonical registry, digest, validation, canonicalization,
    protected-projection, packaging, import-boundary, and CI patterns.

Additional controlling or materially relevant sources are the locked,
owner-ratified `Design_Specs/Challenge_Instance_Distribution.md`,
`Business/Business_Canon.md` §13 for explicit rights, and A3 registry/LIVE
gate code. The immutable legacy archive was not inspected because no authority
file requires a deliberate migration of an archived component.

The phase ceiling is `SPECIFIED: PROPOSED OWNER-REVIEW CONTRACT CANDIDATE`.
`RATIFIED`, `IMPLEMENTED`, `TESTED` for B-02A implementation,
`SCIENTIFICALLY_QUALIFIED`, `SECURITY_QUALIFIED`, `NETWORK_QUALIFIED`,
`COMMERCIALLY_VALIDATED`, `PRODUCTION_QUALIFIED`, and every `LIVE`, launch,
frontier, product, settlement, chain, weight, or emission state remain false.

## 3. MQ classification and fail-closed consequence

| Question | Handoff class | Value/conflict class | Treatment in this phase |
|---|---|---|---|
| MQ-001 | `DEFERRED_FAIL_CLOSED` | `NEW_OWNER_DECISION_REQUIRED` for the first real physical identity and values | Define exact physical/candidate contract shapes and unresolved state. Fixed-viscosity Burgers and `nu = 5e-3` remain labeled recommendations or fixtures only, never defaults, qualification, or LIVE truth. |
| MQ-002 | `DEFERRED_FAIL_CLOSED` | `NEW_OWNER_DECISION_REQUIRED` for real `P`, `Q`, `w`, estimand/reporting use, strata, allocations, finite design, support, and censoring policy | Define distinct identities, claims, roles, and unavailable states. Select no production distribution, count, allocation, weight, tolerance, stopping rule, or sufficiency threshold. |

Neither question is `OWNER_BLOCKING` for a contract-only candidate because the
contract can be correct while real authoring remains unavailable. Missing
human values fail closed; they are not defaulted from examples, open pull
requests, generator behavior, sampling frequency, or planning prose.

## 4. Conflict ledger

| Seam | Class | Controlling source and disposition |
|---|---|---|
| Wave selection and prerequisite | `NO_CONFLICT` | Merged Wave B records and the B-02A ticket select B-02A only after satisfied B-01E closeout. |
| Contract before implementation | `NO_CONFLICT` | B-02A DoD requires independent SciML/statistics/protocol review, explicit human ratification, normal merge, and exact implementation-plan pin before code. |
| Locked distribution architecture versus absent exact runtime schema | `IMPLEMENTATION_LAG` | `Challenge_Instance_Distribution.md` locks the architecture and expressly defers exact serialization; B-02A may propose it, not implement it here. |
| Missing B-02A runtime objects, loader, canonicalizer, and immutable history | `IMPLEMENTATION_LAG` | Expected scope of a later separately authorized phase. No current-owner defect is inferred. |
| A3 Challenge ID/version/digest grammar | `NO_CONFLICT` | Reuse `ChallengeKey`, canonical identifier/version validation, and `sha256:<64 lowercase hex>`; do not create competing grammar. |
| Generic canonical serializer | `IMPLEMENTATION_LAG` | No public generic serializer exists. Specify a schema-local versioned byte profile; do not repurpose A3 stable JSON or A4/A5/A7 private owner-specific encoders. |
| Legacy generic Challenge loader/fallback | `MIGRATION_REQUIRED` | It remains retired historical material. No archived implementation is restored or copied. |
| `carbon/challenges`, `carbon/data`, `carbon/physics` package suggestions | `DOCUMENTATION_LAG` | `.agent/CODE_AUTHORITY.toml` and B-01E-D1 retire them. This phase selects no later implementation package. |
| Missing `Physical_System_Representation.md` referenced by generator docs | `DOCUMENTATION_LAG` | Locked distribution architecture, canon, and current domain specs provide the required seam. Do not broaden this manifest to repair the missing doc. |
| Structural `P`, `Q`, `w`, support, query, and role separation | `NO_CONFLICT` | Canon, locked distribution architecture, owner integration, and ticket agree. |
| Actual physical values, populations, envelope, estimands, strata, counts/budgets, dependence, objectives, stopping, weights, support, and rights | `NEW_OWNER_DECISION_REQUIRED` | Human inputs remain unresolved and production authoring unavailable. |
| Training support versus B-02B `R_strategy` | `NO_CONFLICT` | B-02A owns support semantics; B-02B owns compilation and `ResolvedTrainingSamplingPolicy`. |
| Canonical case versus B-03 generation result | `NO_CONFLICT` | B-02A owns the immutable realization-record schema and identity; controlled B-03 or other exact source capabilities later produce case records and runtime outcomes. Disposition is a separate scoped immutable evidence record, not mutation of the case. |
| Censoring/retry/replacement values | `NEW_OWNER_DECISION_REQUIRED` | B-02A defines typed seams and provenance only; science/statistics later choose policy and adequacy. |
| Reference roles and MMS | `NO_CONFLICT` | B-02A defines identity/authority separation only; B-04 owns truth qualification and runners. |
| Evidence weighting and score | `NO_CONFLICT` | B-02A distinguishes `w`; B-05 owns estimands, measurements, thresholds, and Score Pack authoring. |
| Dossier, qualification, and LIVE | `NO_CONFLICT` | B-06 owns dossier machinery and A3 owns lifecycle/LIVE gates; no B-02A object self-qualifies. |
| Fixture provenance | `NO_CONFLICT` | Structural provenance and controlled factories are required; a caller Boolean or label is never authority. |
| Public/protected case identity | `NO_CONFLICT` with `IMPLEMENTATION_LAG` for types | Data and security owners require explicit allow-listed projections and no reversible draw/seed/hidden-stratum disclosure. |
| Historical identity and supersession | `NO_CONFLICT` | Material changes are prospective, content-addressed, and historically retrievable; no `latest` reinterpretation. |
| Candidate amendments and stale numerical examples | `DOCUMENTATION_LAG` | Candidate canon/domain additions and historical strategy/scoring values are compatibility input only, not ratified values. |

No blocking material conflict remains for drafting. Every later human-value
decision is recorded as unresolved rather than averaged across sources.

## 5. Existing-code inspection and reuse disposition

| Current component | Classification | Contract consequence |
|---|---|---|
| A3 `ChallengeKey`, canonical identifier/version validators | `KEEP` | Reuse the existing Challenge identity grammar exactly. |
| A3 tagged SHA-256 validator and verified bounded byte reader | `KEEP` | Reuse exact digest grammar and digest-first artifact reads. |
| A3 registry lifecycle and LIVE gate | `KEEP` | Preserve owner semantics; B-02A cannot activate or qualify itself. |
| A4 protected entropy/seed domains and nominal projection pattern | `KEEP` | Keep seeds and reconstruction-sensitive case identity outside B-02A public surfaces. |
| A2/A5/A7/A8/A9 owner-local implementations | `KEEP` | Treat as downstream/adjacent owners, not generic authoring infrastructure. |
| A3 public primitives in each future B-02A ref | `WRAP/COMPOSE` | Reconstruct and revalidate exact nominal nested values at the B-02A boundary. |
| A3 verified byte reader in a future loader | `WRAP/COMPOSE` | Verify bytes before parse, parse a closed schema, and require internal/external ref equality. |
| A4/A5/A7 private canonicalizers | pattern only | Adopt properties, never private functions or owner types. |
| Current canonical implementation | `REPAIR: none` | Missing B-02A capability is implementation lag, not permission to change A2-A9. |
| Current canonical implementation | `REPLACE: none` | No active owner or package is displaced. |
| Retired/archive code | `MIGRATION_REQUIRED`, not selected | Archive presence grants no authority; no migration occurs. |
| Later package root and public exports | owner decision | Reconcile code authority, ownership, dependency direction, packaging, and exports in the later exact-pinned implementation plan. |
| Canonical-byte profile/version | owner ratification through this contract | The candidate proposes an exact procedure; implementation waits for contract review, ratification, and merge. |
| Immutable history/supersession store and A3 binding | owner decision for later implementation | A3's replaceable non-LIVE records are not silently treated as a B-02A history store. |

The prospective dependency direction is a later B-02A owner package to only
the standard library and minimal public A3 primitives, with B-02B/B-03/B-04/
B-05 consuming it. This plan does not choose that package or edit code
authority, exports, packaging, dependencies, or tests.

## 6. Contract-ratification phase manifest

The complete allowed base-to-head manifest is exactly:

```text
M .agent/DECISIONS.md
M .agent/WAVE.md
M .agent/WAVE_B.md
M .agent/tickets/B-02A_scientific_authoring_contracts.md
A .agent/plans/B-02A_scientific_authoring_contracts.md
A .agent/evidence/wave_b/b-02a.md
A Design_Specs/Scientific_Challenge_Authoring_Contract.md
```

No `carbon/`, `tests/`, `.devcontainer/`, `scripts/dev/`, workflow,
`pyproject.toml`, `uv.lock`, README, code-authority, environment, legacy-index,
archive, implementation, dependency, or package file may change.

## 7. Deliverables and order

1. Record the candidate `in_progress` transition while every DoD checkbox
   remains unchecked.
2. Create this plan and the evidence skeleton before substantive contract
   editing.
3. Propose version 0.1 of the owner-review contract with exact object, ref,
   closed canonical-byte/schema, validation, causal output, population,
   complete finite-design, case-source/state, scoped censoring/realized-
   evidence, fixture, ownership, and later-test semantics.
4. Record material decisions as the coherent B-02A-D1 through B-02A-D5
   series in `.agent/DECISIONS.md`.
5. Validate the exact documentation-only manifest, terminology, Markdown
   references, maturity ceilings, and absence of later work.
6. Make normal reviewable commits, push only the dedicated branch, and open a
   draft pull request with the mandated fourteen sections and exact `Lead
   notification` heading.
7. Post/update issue #42 mentioning `@harshaa765`, link the draft PR and
   decision series, and request independent SciML/physics, statistics, and
   protocol review. Delivery is not approval.
8. Stop. Do not mark ready, merge, enable auto-merge, check DoD, or begin
   implementation.

## 8. Definition-of-Done crosswalk

All DoD items remain unchecked in this phase.

| DoD area | Contract-phase evidence | Later implementation evidence |
|---|---|---|
| Contract review/ratification/merge | Candidate file, decision log, draft PR, requested three-role review; review, ratification, and merge remain pending | Exact merged contract commit must be pinned by a new authorized plan before code. |
| Immutable objects and refs | Field-level normative specification only | Exact nominal immutable types, loaders, closed schema tests. |
| `P`/`Q`/`w`/support/`R_strategy` separation | Closed role matrices, set-only fail-closed rules, and ownership boundaries | Confusion-rejection tests and downstream compiler integration. |
| Population roles, query, campaigns, censoring, MMS | Identity and authority-separation specification | Exact binding, rejection, protected-projection, and history tests. |
| Physical/candidate causal job | Closed field and fail-closed authoring contract with no real value selection | Runtime validation and fixture-only integration. |
| Case states and multi-role evidence | Closed source variants, scoped disposition/censoring, and separate capability-created realized-evidence record | Exact result/ref/capability types and negative tests. |
| Content addressing and canonicalization | Versioned canonical-byte profile candidate | Golden bytes, insertion-order independence, hash pin, mutation, and history tests. |
| Fixture cannot satisfy LIVE | Structural provenance and explicit A3 boundary | Direct negative A3 LIVE-gate tests. |

Contract creation alone cannot satisfy the first checkbox because independent
review, explicit human ratification, normal merge, and an exact later plan pin
are still missing.

## 9. Later implementation targets — explicitly deferred

A later separately authorized plan may implement, after pinning the normally
merged contract:

- exact immutable authored types and corresponding `*Ref` types;
- strict closed loaders and loader-result types;
- schema-local canonical bytes and content-addressed identity;
- immutable historical retrieval and prospective supersession;
- structural fixture provenance and nominal public/internal/protected case
  projections;
- typed case disposition/censoring/realized-evidence result/ref seams; and
- minimal A3 binding without weakening registry qualification.

The later plan must first ratify the package root, public exports, dependency
direction, storage/history model, A3 integration seam, and exact canonical
profile. It must not select a retired path by convenience.

## 10. Required later test matrix

The contract records, but this phase does not create, tests for:

- exact nominal types, Boolean/integer separation, scalar-subclass rejection,
  missing/extra/unknown fields, malformed identifiers and Unicode, non-finite
  numerics, and canonical positive zero;
- canonical golden bytes, insertion-order independence, hash pins, reference
  equality, defensive copies, immutable equality, and mutation isolation;
- prospective supersession, exact historical retrieval, and no silent
  reinterpretation;
- structural fixture provenance and inability of every fixture-authored
  object/ref/case to satisfy A3 LIVE qualification;
- population-role confusion, including explicit `P`, `Q`, `w`, training
  support, `R_strategy`, query/observation, stress/practice/product/deployment,
  evidence-campaign, and realized-evidence distinctions;
- total physical-quantity/candidate-output causality;
- each population and SamplingPlan role-matrix branch, estimand/reporting and
  w/no-w agreement, set-only rejection, full finite-design binding,
  stratification/crosswalk/allocation, dependence/replication, query/
  observation and reference-fidelity allocation, stopping/extension/
  sequential behavior, duplicate/replacement, and intended-versus-realized
  accounting;
- scoped censoring reason/typed-trigger/authority/plan/campaign/missingness
  provenance, capability-only realized-evidence construction, and rejection of
  candidate timeout/resource failure as censoring;
- MMS relabeling rejection and no evidence-role authority transfer;
- public/internal/protected projection non-disclosure of case identity,
  reversible draw identity, seed, hidden stratum realization, and sensitive
  reconstruction fields;
- package exports, dependency direction, code-authority updates, clean wheel,
  and isolated outside-tree imports.

## 11. Human input and fail-closed strategy

Humans must supply and ratify the first real physical task/candidate contract,
target population, official envelope, Q, w, intended estimand/reporting use,
stratification/crosswalks, sampling/analysis units, counts/budgets,
allocations, dependence/replication, query/observation and reference-fidelity
allocation, uncertainty/tail/subgroup objectives, stopping/extension,
sufficiency/missingness/sensitivity/denominator rules, training support and
rights, censoring/replacement/exclusion policy, canonicalization profile,
package/storage/A3 seams, and any later hybrid evidence role. Until then:

- production authoring is unavailable;
- an unresolved required reference is not a default;
- no generator, open PR, sampling frequency, fixture, recommendation,
  reconstructibility, or shared support supplies scientific authority;
- no fixture becomes qualified or LIVE; and
- historical evidence remains interpreted under its exact immutable pins.

## 12. Baseline and validation route

Exact-main run `33321131062` supplies successful canonical base evidence:

- Ubuntu 24.04 / glibc 2.39, linux/amd64;
- CPython 3.11.16, uv 0.12.7, Black 26.5.1, Ruff 0.16.3;
- canonical job: `28 passed in 3.44s`, `2323 passed in 47.08s`, package lane
  `28 passed in 4.85s`, authority lane `13 passed in 1.31s`;
- clean-image job: `28 passed in 2.78s`, `2323 passed in 38.85s`, package lane
  `28 passed in 3.98s`, authority lane `13 passed in 1.01s`;
- both quality and diff-hygiene gates passed.

The required pre-edit local commands were also attempted. Native Git Bash
correctly rejected `bootstrap.sh` and `doctor.sh` as unsupported with exit 2.
Docker client 25.0.3 was present, but Docker Desktop failed before engine
startup because its own local socket was inaccessible; no system files were
altered to repair that inherited host fault. `ci.sh` therefore could not enter
the canonical lane or collect local tests. Exact commands, timings, and
failures are preserved in `.agent/evidence/wave_b/b-02a.md`.

After editing, attempt `doctor.sh` and `ci.sh` again, run `git diff --check`,
verify links and terminology, and audit the exact manifest and forbidden
paths. Missing canonical local validation stays visible; draft-PR CI is the
repository-controlled clean Ubuntu acceptance route and must not be reported
as passing before it completes.

## 13. Review route and stop condition

The draft PR requests independent coverage of all three roles:

- SciML or physics;
- statistics; and
- protocol.

The implementer and collaborating drafting agents are not independent
reviewers. The notification in issue #42 mentions `@harshaa765`; silence is
not review, ratification, or approval. Any explicit `REQUEST_CHANGES` or
`BLOCKED` direction pauses the affected work.

Stop when the bounded branch is pushed, the PR remains draft, the lead
notification exists, and the three independent review roles have been
requested. Leave review, ratification, normal merge, post-merge CI, exact
implementation pin, and all implementation work pending.
