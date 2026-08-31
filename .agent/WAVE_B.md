# Carbon Wave B Board

**Status:** active in bounded development scope only when the merged `.agent/WAVE.md` names Wave B and this file as its controlling register. This file does not self-activate.
**Version:** 0.7
**Activation gate:** Wave A is closed in bounded engineering scope; PR #54 independently reviewed, passed CI, and normally merged the version 0.4 governance tree; and `.agent/WAVE.md` names Wave B and this board as controlling. B-01's independently reviewed correction head `ea1d11f76db419775803e268b39eaa8b789eef29`, tree `9f767ea16ffb7185ab64acff2542c7a8dcc2e339`, passed exact-head CI `33308009899`, normally merged in PR #57 as `4ee58d56862d0441d5d151d79db1fe3036f1025d` with the exact reviewed tree preserved, and passed exact-main CI `33308165189`; B-01 is authoritatively `done`. Version 0.5 inserted the owner-directed B-01E infrastructure ticket. Version 0.6 recorded B-02A closeout and B-07R's delegated conditional transition. Version 0.7 records the satisfied B-07R predicate and selects B-02B `in_progress` for its contract-then-implementation flow. No multi-role approval bundle, exact-byte activation approval, or separate activation closeout is required before bounded development. B-07S still owns exact-protocol ratification before service-facing implementation.
**B-01E implementation evidence:** independently reviewed head `2025e235c83a994ed4f16c9a3a9d3c2766700061`, tree `4a506a1ae46cfcbf180eb5dbf68ed50caa0f1e09`, normally merged in PR #58 as `b4744a435e8bc7220c7dc03e6a993bb0a54c16a5` with the exact reviewed tree preserved; exact-main push run `33319267255` passed.
**B-02A closeout:** PR #60 normally merged reviewed head `f285399138ecfe95352d429bc26051b0a5fecbcf`, tree `61a4463ac459f7fe96545f2746511d6940246f57`, as `58ea866de52e3853b0b45e3217ee0625302aa663` with the same tree. Exact-head CI `33341717012`, Greptile 5/5 with no blocking failure and zero unresolved threads, and exact-main CI `33342015346` passed. B-02A is `done` only in bounded engineering scope.
**B-07R closeout:** PR #62 normally merged exact reviewed head `038aa3ffe51aaafe99803553380c396429144977` as `6e2a2640a6bd26755064acb0616382c8dcc0ba37` with exact reviewed/merge tree `5cf1aaf1fd11ef4775c170dd938c3190fa14145b`. Exact-head CI `33347664046`, Greptile 5/5 with zero unresolved threads, and exact-main CI `33347826166` passed. Issue #42 comment `5472621851` records completion. B-07R is authoritatively `done` in bounded engineering-architecture scope.
**Mission:** make one scientific exam authorable and make the miner research loop executable with fixtures, without claiming that the exam, practice signal, prior, backend, or network path is qualified.
**Primary contract:** `Design_Specs/Miner_MCP_Wave_B_Research_Contract.md`
**Codex entry point:** `.agent/WAVE_B_CODEX_HANDOFF.md`
**Program crosswalk:** `launch/Carbon_Testnet_to_Mainnet_Launch_Path_v1.0.3.md` §6.2 incorporates this board's decomposition and conditional effort rebaseline. This board remains the controlling ticket register.

Authority comes from the merged active `.agent/WAVE.md`, selected ticket, and
merged delegated-decision protocol, not this file alone or prior role
approval. B-01, B-01E, B-02A, and B-07R are authoritatively `done` in their
recorded bounded scopes. B-02B is the selected `in_progress` ticket. Working engineering decisions
may proceed after durable record and applicable notification without
affirmative lead response. A human-reserved value remains unavailable and
blocks its affected behavior, not unrelated bounded work.

---

## 1. Wave B outcome

Wave B closes only when Carbon can demonstrate this fixture-only chain:

```text
public scientific contracts
        ↓
ChallengeInteractionManifest
        ↓
Strategy + ParameterCatalog
        ↓
ResolvedConstructionPlan
        ↓
nominal practice task on mock-only rights
        ↓
ExperimentRecord + ResearchReceipt
        ↓
resolved-plan fixture-official reconstruction through unchanged v1 lifecycle
        ↓
PriorPack TEST_ONLY build; v2-backed public v1 projection remains unavailable
        ↓
Dossier / qualification manifest remains fail closed for LIVE
```

Wave B does not include real miner training, production reconstruction, authenticated remote transport, official scientific evidence, LIVE activation, network weights, or learned public priors from official outcomes.

---

## 2. Decisions this board is designed to ratify

1. Wave B remains declarative. It accepts no arbitrary participant code.
2. Strategy v1 remains the input envelope; a public Challenge-bound `ParameterCatalog` and deterministic compiler supply executable semantics, including only registered `R_strategy` training policies inside Challenge-owned support.
3. Unknown, unused, coerced, silently defaulted, or silently clamped parameters fail closed.
4. Practice and official execution use separate nominal types and authority paths.
5. Paired practice comparison uses common fresh public cases and returns bounded aggregate evidence.
6. Research tasks are asynchronous, idempotent, lineage-bearing, and receipt-producing.
7. Structural prior alignment, resource forecasting, operational quote, and measured practice remain distinct.
8. Carbon publishes no official-score, rank, gate, or winner prediction.
9. Priors are immutable Challenge-level artifacts with identical bytes for every miner; personalization happens miner-side.
10. Wave B prior handling is mechanically limited to private `TEST_ONLY`
    staging and reviewed public-publication schemas/negative tests. Public-class
    activation and qualified learned publication remain later and fail closed.
11. A distinct test-only prior authorization receipt (exact type owned by
    B-07S) carries `TEST_ONLY / NOT_UTILITY_QUALIFIED`, permits only private
    exact-ref fixture retrieval, and cannot substitute for a public
    `PriorPublicationReceipt`.
12. The catalog may expose Challenge-owned, versioned, reconstructible
    structure-preserving components as optional construction levers. A
    component label or claimed invariant never satisfies a scientific gate;
    the reconstructed output remains subject to the same measurements and
    hidden stress evidence as every other candidate.
13. Resource-saving admission checks, staged reconstruction, and sequential
    evidence allocation may conserve compute, but no partial build, forecast,
    proxy, or screen can create `SUPERIOR`. Promotion-grade evidence preserves
    reconstruction-by-case dependence and fails closed when it cannot resolve
    the claim.

---

## 3. Ticket board

Statuses on this board use only `todo`, `in_progress`, `done`, and `blocked`.

| ID | Deliverable | Status | Evidence | Driver | Accountable reviewer | Depends on | Master questions | Effort | Target |
|---|---|---|---|---|---|---|---|---|---|
| B-01 | Wave B orientation, exact authority pin, conflict ledger, and baseline evidence | done | `.agent/evidence/wave_b/b-01.md` | Codex / protocol lead | Tech lead | merged A11, merged A12, `.agent/WAVE_A_REPORT.md`, explicit Wave B activation | MQ-018 | S | WB-0 |
| B-01E | Canonical development environment, deterministic dependency lock, local/CI command parity, machine-enforced code-authority boundary, and legacy executable quarantine | done | `.agent/evidence/wave_b/b-01e.md` | Codex + SRE | Tech lead + SRE | B-01 | MQ-018 | L | WB-0/1 |
| B-02A | Physical task, candidate output, population, SamplingPlan, and canonical-case identities | done | `.agent/evidence/wave_b/b-02a.md` (PR #60 exact reviewed/merge tree, Greptile, exact-head and exact-main CI recorded; bounded engineering scope only) | Codex + SciML | SciML + statistics + protocol | B-01E | MQ-001, MQ-002 | L | WB-1 |
| B-02B | Candidate assembly, ParameterCatalog, optional structural-component refs, StrategyCompiler, and resolved-plan contracts | in_progress | `.agent/evidence/wave_b/b-02b.md` (working-contract phase; runtime implementation begins only after exact contract merge and exact-main CI) | Codex + SciML | Protocol + SciML + security | B-02A, B-07R, A2 | MQ-005, MQ-008, MQ-015, MQ-024 | L | WB-2 |
| B-02C | ResearchResourcePolicy, resource classes, ceilings, reconstruction-stage receipt seams, enforcement, and receipts | todo | — | Codex + SRE | Protocol + SRE + security + operations + economics | B-02B, B-07R | MQ-008, MQ-015, MQ-017, MQ-024 | M | WB-2 |
| B-03 | Generator API and fixed-viscosity Burgers fixture implementation | todo | — | Codex + SciML | SciML + statistics + protocol | B-02A | MQ-002, MQ-003 | L | WB-1/2 |
| B-04 | ReferencePolicy, TruthAsset, primary/witness runner interfaces, and typed reference failure | todo | — | Codex + SciML | SciML + statistics + protocol + independent reviewer | B-02A | MQ-004 | L | WB-1/2 |
| B-05 | MeasurementContract, ReconstructionEvidencePolicy, dependence-aware UncertaintyPolicy, and Score Pack authoring bindings | todo | — | Codex + SciML | SciML + statistics + protocol + SRE | B-02C, B-04 | MQ-005, MQ-006, MQ-007, MQ-008 | L | WB-2 |
| B-06 | D1-D12 Dossier, interval-coverage evidence, and qualification-manifest machinery | todo | — | Codex | SciML + statistics + protocol + security + independent reviewer | B-02A, B-03, B-04, B-05, A3 | MQ-003 through MQ-008, MQ-018 | M | WB-2/3 |
| B-07R | Ratify the miner research architecture and authority boundaries | done | `.agent/evidence/wave_b/b-07r.md` (PR #62 exact reviewed/merge tree, Greptile, exact-head and exact-main CI recorded; bounded architecture only) | Protocol lead + Codex | Protocol + science + security + rights | B-01, B-02A | MQ-015 through MQ-018, MQ-024 through MQ-026, MQ-045, MQ-051 | M | WB-1 |
| B-07S | Ratify the exact v2 wire, lifecycle, error, canonicalization, bound, and local-adapter contract | todo | — | Protocol lead + Codex | Protocol + science + security + rights/counsel | B-07R, B-02A, B-02B, B-02C | MQ-015 through MQ-018, MQ-024 through MQ-026, MQ-045 | M | WB-2 |
| B-07A | Shared v2 protocol primitives, ChallengeInteractionManifest, and public research-capability discovery | todo | — | Codex | Protocol + security | B-02A, B-02B, B-02C, B-05, B-07R, B-07S, A3, A9 | MQ-005, MQ-006, MQ-015, MQ-016, MQ-017, MQ-024 | L | WB-3 |
| B-07B | ResearchTask, ExperimentRecord, ResearchReceipt, evidence classes, and lineage | todo | — | Codex | Protocol + science + security + rights/counsel | B-02B, B-07R, B-07S, B-07A, A11 | MQ-016, MQ-026, MQ-045 | M | WB-3 |
| B-07C | Nominal mock/practice service, practice pack, scaffold, rehearsal, and paired comparison | todo | — | Codex + SciML | Science + statistics + security | B-02C, B-03, B-05, B-07A, B-07B, B-07S, A4, A8, A9 | MQ-002 through MQ-005, MQ-015, MQ-016 | L | WB-3/4 |
| B-07D1 | PriorPack schema, immutable store/index, estimands, receipts, and offline compatibility projection | todo | — | Codex + Landscape | Science + security + protocol | B-07A, B-07B, B-07S, A6, A9, A11 | MQ-016, MQ-018, MQ-025, MQ-026, MQ-045, MQ-051 | L | WB-3/4 |
| B-07D2 | TEST_ONLY publisher and persistent cumulative-disclosure ledger | todo | — | Codex + Landscape | Science + statistics + security + protocol + rights | B-07D1, B-07B | MQ-016, MQ-018, MQ-025, MQ-026, MQ-045, MQ-051 | L | WB-4 |
| B-07D3 | Static exact/active provider, historical retrieval, and deterministic prior alignment | todo | — | Codex + Landscape | Protocol + security | B-07D1, B-07D2, B-07S, A9 | MQ-016, MQ-017, MQ-025, MQ-026 | M | WB-4 |
| B-07E | Static resource analysis, calibrated forecast seam, and receipt separation | todo | — | Codex + SRE | Protocol + SRE + statistics | B-02B, B-02C, B-07A, B-07B, B-07C, B-07D3, B-07S | MQ-008, MQ-017, MQ-024 | M | WB-4 |
| B-07F | Resolved-plan fixture-official construction adapter behind unchanged v1 lifecycle | todo | — | Codex + SciML | Protocol + science + security | B-02B, B-02C, B-03, B-04, B-05, B-07S, A7, A8, A9 | MQ-004, MQ-005, MQ-008, MQ-015, MQ-024 | L | WB-3/4 |
| B-07G | Research-service composition, B-07S-ratified closed-operation dispatch, and conformance | todo | — | Codex | Protocol + science + security | B-02B, B-07A, B-07B, B-07C, B-07D3, B-07E, B-07S, A9 | MQ-015 through MQ-018, MQ-024 through MQ-026, MQ-045 | L | WB-4/5 |
| B-E1 | R0/R1/R2 reproducibility, dependence-aware reconstruction × whole-case interval, staged-evidence audit, and typed contested-outcome harness | todo | — | Codex + SciML | Statistics + SciML | B-02A, B-02B, B-02C, B-04, B-05 | MQ-007, MQ-008 | L | WB-2/3 |
| B-E2 | Julia/reference failure contract | todo | — | Codex + SciML | SciML | B-04 | MQ-004 | M | WB-2 |
| B-E3 | Credibility crosswalk and evidence manifest | todo | — | Codex + SciML | Independent reviewer | B-06 | MQ-003 through MQ-008 | S | WB-3 |
| B-E4 | Autoresearch workflow, utility, leakage, poisoning, and aligned-cheating gauntlet | todo | — | Codex + research + security | Research + security + science + statistics + protocol | B-07A, B-07B, B-07C, B-07D1, B-07D2, B-07D3, B-07E, B-07F, B-07G, B-07S, B-E1, A12 | MQ-005, MQ-015, MQ-016, MQ-024, MQ-025, MQ-026 | L | WB-5 |
| B-GATE | Fixture integration, invariant proof, closeout report, and no-placeholder-LIVE audit | todo | — | Codex | Tech lead + science + protocol + security + rights | B-01, B-01E, B-02A, B-02B, B-02C, B-03, B-04, B-05, B-06, B-07R, B-07S, B-07A, B-07B, B-07C, B-07D1, B-07D2, B-07D3, B-07E, B-07F, B-07G, B-E1, B-E2, B-E3, B-E4 | MQ-001 through MQ-008, MQ-015 through MQ-018, MQ-024 through MQ-026, MQ-045, MQ-051 | M | WB-5 |

Effort uses the launch-plan scale: S is at most one primary-lane day, M is two to three, and L is four to seven. Including the owner-directed B-01E insertion, the decomposed board totals roughly **76-127 primary-lane days if executed serially**. With two qualified non-overlapping implementation lanes and timely reviews, the dependency spine is approximately **49-83 elapsed engineering days (10-17 working weeks)**. A single lane is approximately **16-26 working weeks**. These are planning estimates, not calendar commitments; scientific/security/rights decisions, review queueing, and later qualification are additional.

`WB-0` through `WB-5` are dependency phases, not calendar promises: activation/orientation; scientific foundations; semantic and wire contracts; core research implementations; prior/practice/resource integration; gauntlet and closeout. Launch v1.0.3 records the conditional effort rebaseline; calendar dates remain unresolved until staffing is approved.

---

## 4. Dependency order

```text
B-01 → B-01E → B-02A
B-02A → B-03
B-02A → B-04
B-02A → B-07R
B-02A + B-07R + A2 → B-02B → B-02C → B-07S
B-02C + B-04 → B-05
B-02B + B-02C + B-07R + B-07S → B-07A → B-07B
B-07A + B-07B + B-07S → B-07D1 → B-07D2 → B-07D3
B-02C + B-03 + B-05 + B-07A + B-07B + B-07S → B-07C
B-02B + B-02C + B-07A + B-07B + B-07C + B-07D3 + B-07S → B-07E
B-02B + B-02C + B-03 + B-04 + B-05 + B-07S + A7/A8/A9 → B-07F
B-02B + B-07A + B-07B + B-07C + B-07D3 + B-07E + B-07S + A9 → B-07G

B-02A + B-02B + B-02C + B-04 + B-05 → B-E1
B-04 → B-E2
B-02A + B-03 + B-04 + B-05 + A3 → B-06 → B-E3
B-07A/B/C/D1/D2/D3/E/F/G/S + B-E1 + A12 → B-E4
all tickets → B-GATE
```

B-03, B-04, and B-02B may proceed in parallel only after their individual contracts are ratified and the implementation lanes do not touch overlapping authority. B-02C owns the resource-policy prerequisite; B-07E only inspects or forecasts against it. B-07A implements the ratified shared v2 nominal primitives once; downstream domain tickets consume rather than redefine them. B-07F owns resolved-plan fixture-official integration so B-E4 and B-GATE do not implement a hidden adapter. B-07G owns final research-service composition and conformance without absorbing domain or official-v1 authority. B-07D1/D2/D3 deliberately separate the prior's data contract, offline publisher, and request-time provider. The default repository execution rule remains one bounded ticket per implementation lane.

### Legacy launch-roadmap crosswalk

| Retired launch v1.0.1 umbrella | Controlling Wave B decomposition |
|---|---|
| `B-01` | B-01 |
| — owner-directed 2026-08-30 infrastructure insertion | B-01E |
| `B-02` | B-02A, B-02B, B-02C |
| `B-03` through `B-06` | B-03 through B-06 |
| `B-07` | B-07R, B-07S, B-07A, B-07B, B-07C, B-07D1, B-07D2, B-07D3, B-07E, B-07F, B-07G |
| `B-E1` through `B-E3` | B-E1 through B-E3 |
| Wave B integration/acceptance | B-07G, B-E4, B-GATE |

---

## 5. Human inputs do not block fixture schemas

Agents implement mechanisms, placeholders that fail closed, test fixtures, and evidence collection. Humans supply or approve the following before the corresponding real/public capability activates.

| Input | Owner | Required before | Fail-closed behavior |
|---|---|---|---|
| Named lane staffing and launch calendar rebaseline | Launch + tech lead | Any current testnet/mainnet date claim | Dependency phases only; dates unresolved |
| Burgers v1 physical identity and claim | SciML + protocol | Real Challenge authoring | Fixture-only identity |
| Target population, official SamplingPlan, strata, evidence weighting, and permitted training support | SciML + statistics | Qualified generator/exam and real compiler catalog | No LIVE manifest or production training policy |
| Primary/witness reference adequacy and uncertainty | SciML + independent reviewer | TruthAsset authority | Reference unavailable |
| Measurements, gates, transforms, and weights | SciML + protocol | Production Score Pack | Pack not ready |
| Executable catalog values, hybrid assembly, and allowed `R_strategy` policies | SciML + protocol + security | Real compiler catalog | Fixture catalog only |
| Structure-preserving component assumptions, exact implementations, applicability, and limitations | SciML + protocol + security | Any real structural-component catalog entry or prior guidance | Component unavailable; no architectural preference inferred |
| Runtime ceilings, hardware/resource classes, and enforcement rails | SRE + protocol + security | Real reconstruction | Fixture resource policy only |
| ReconstructionEvidencePolicy, family-specific complete-base evidence, scientific stopping/extension, typed deferral, heuristic-futility error control, and stability-audit rate | Statistics + SciML + protocol | Real scientific ranking or frontier promotion | Nomination/promotion unavailable or `INDETERMINATE` (`INSUFFICIENT_EVIDENCE`) |
| Validator capacity, reconstruction funding, queueing, and operational evidence budget | SRE + operations + economics | Operational availability of registered evidence | `EVIDENCE_DEFERRED`; no scientific outcome |
| Resource forecast calibration and unsupported-input rule | SRE + statistics | Any calibrated forecast claim | `UNRESOLVED` forecast |
| Practice scope, omissions, and disclosure policy | Science + statistics + security | External practice | In-process fixture only |
| Prior estimands, cohorts, lag, cadence, granularity, diversity metric/floor, and first content | Landscape + science + statistics + security | Any external prior activation | `TEST_ONLY` / unavailable |
| Prior release approvers, rights, and future signer/key custody | Governance + business + counsel + security | External activation/signing | Test-only seam / unavailable |
| Preregistered Wave B agent profiles, budgets, utility estimand/effect floor, uncertainty rule, diversity floor, and conditional-leakage limit | Research + science + statistics + security + protocol | B-E4 execution and any public agent claim | B-E4 blocked; gauntlet unresolved |
| Strategy/evidence reuse rights | Business + counsel | Unrestricted learned ingestion | Exclude evidence |
| Remote quotas, fees, and congestion policy | Operations + economics | Charged remote service | No remote charged path |

No ticket may invent these values to make a test pass.

---

## 6. Core acceptance invariants

Every applicable Wave B ticket must preserve and test:

- mock, practice, prior, scaffold, forecast, and structural-research outputs cannot enter A5 score or the A7 official lifecycle. A fixture-official result may exercise the unchanged A5/A7/A8-shaped fixture path only through B-07F, with fixture provenance and no LIVE, economic, or scientific authority;
- no public output contains official seed, draw, case, hidden mixture, exact margin, or protected reference material;
- the research service exposes exactly the B-07S-ratified closed operation set,
  delegates each operation to one named domain owner, and contains no
  official-v1 operation, lifecycle, or store;
- the same Strategy and compiler identities resolve to the same construction semantics in practice and official-shaped reconstruction;
- unsupported or unused parameters fail rather than disappear;
- a structural-component declaration, implementation test, or prior tag cannot
  satisfy a scientific gate or enter score as evidence; only registered
  measurements of reconstructed outputs can do so;
- only registered training sampling/curriculum/augmentation levers may resolve
  to `R_strategy`; raw/custom data, miner seeds, and official `P`, `Q`, `w`,
  stress, reference, gate, and scorer controls fail closed;
- reference or infrastructure failure cannot become candidate physics failure;
- no pre-base quality check, partial build, forecast, or screen can deny the
  registered complete base reconstruction or create any scientific outcome;
  uncompleted work is `EVIDENCE_DEFERRED`, never negative evidence;
  reconstruction × whole-case dependence, stratified by stress design, is
  preserved in every decision-resolution fixture and unresolved evidence
  remains indeterminate;
- a `TEST_ONLY` prior cannot be externally activated or rendered as bootstrap/learned guidance, and no v2-backed projection can enter the public v1 provider;
- a test-only authorization receipt cannot satisfy a public publication gate, and
  the exact pack/receipt remains frozen across B-E4 v2-prior replicates;
- the prior provider serves only approved stored bytes and never performs a private-data query;
- identical PriorPack reference produces identical bytes for every requester;
- public prior alignment is deterministic and uses no private evidence;
- per-requester and near-duplicate lineage disclosure accounting is composable across surfaces; Wave B related-requester resolution is fixture-only and makes no live Sybil-resistance claim;
- no Wave B artifact creates scientific, security, network, commercial, production, frontier, weight, emission, or settlement authority.

---

## 7. Ticket execution requirements

### Development decisions and lead notification

Development authorization comes from the active wave and selected ticket, not
from prior multi-role approval. A material decision changes or selects:

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

Routine implementation details within an already recorded working contract do not need
a separate lead notification. For every material-decision-affecting pull
request, record the durable decision in `.agent/DECISIONS.md` or the applicable
ticket, plan, or specification; include a pull-request section titled
`Lead notification` naming the decision ID or heading, affected ticket and
files, selected approach, alternatives rejected, invariant/interface/
sequencing effects, reversibility and migration effect, and notification
issue/comment; and post or update issue #42 mentioning designated SciML /
Technical Lead Harshdeep Sharma (`@harshaa765`).

Notification is evidence of delivery, not approval. No affirmative response,
reaction, approval, or waiting period is required. A lead `REQUEST_CHANGES`
review or explicit `BLOCKED` direction pauses the affected change but not
unrelated work. After merge, an adjustment uses a new bounded branch and later
normally merged repository decision; historical evidence is marked superseded,
not rewritten. Current merged repository authority controls until then.

The Accountable reviewer column remains technical/domain review and
notification routing. It creates no affirmative pre-approval or silence gate.
Independent technical review, repair of every valid finding, zero unresolved
review threads, required CI, and normal merge remain mandatory. A documented
invalid finding may be closed with rationale.

This non-blocking development rule does not allow an agent to invent or approve
scientific truth, thresholds, tolerances, population or SamplingPlan claims,
qualification, security acceptance, rights/legal policy, live economics,
launch or deployment authority, or production, `LIVE`, frontier, product,
settlement, chain, weight, or emission authority. An unresolved reserved human
decision leaves the affected capability stopped, explicit, bounded, and fail
closed; it does not block unrelated fixture, schema, interface, test, or
infrastructure development.

Before each ticket begins:

1. read `CONSTITUTION.md`, `AGENTS.md`, `.agent/INVARIANTS.md`, the active `.agent/WAVE.md`, this candidate board, and the ticket;
2. read the ticket's domain-owner specifications in full;
3. pin the current commit and authority set;
4. classify touched components `KEEP`, `WRAP`, `REPAIR`, `REPLACE`, or stop for `NEW_OWNER_DECISION_REQUIRED`;
5. run and record the ticket-specific baseline;
6. create a detailed `.agent/plans/` file for every multi-module ticket before implementation;
7. create and record the ticket's working contract before implementation when
   the ticket defines a new public or security boundary; obtain independent
   exact-head review before normal merge, while human-reserved values remain
   fail closed.

Each ticket writes `.agent/evidence/wave_b/<ticket-id>.md` using the evidence
README and links that record from its ticket file and board row before `done`.
Ordinarily the implementation change leaves merge fields pending for a later
governance transition. A ticket change may instead carry a conditional
completion record that becomes authoritative only after the exact reviewed tree
passes required CI/review, normally merges with tree equality, and exact-main
CI passes. Immutable PR/check/merge/Actions metadata and a post-merge issue
comment may carry identities the tracked commit cannot self-record. Do not
require a recursive closeout pull request merely to restate those facts. If a
record cannot carry another non-self-referential identity, fill only that
identity in the smallest later governance transition; do not reopen
implementation. An affirmative reviewer or lead response is not required.

Ticket completion must separately report:

```text
SPECIFIED
IMPLEMENTED
TESTED
SCIENTIFICALLY_QUALIFIED
SECURITY_QUALIFIED
NETWORK_QUALIFIED
COMMERCIALLY_VALIDATED
PRODUCTION_QUALIFIED
```

No later state is inferred from an earlier one.

---

## 8. Wave B closeout

`B-GATE` may propose this board `done` only after:

- every ticket has merged evidence and checked acceptance criteria;
- full CPU, focused, invariant, quality, and installed-wheel tests pass;
- the fixture autoresearch gauntlet completes end to end without undocumented repository knowledge;
- the preregistered B-E4 utility decision passes and the conditional-leakage
  decision does not find a protected-realization shortcut; a failed or
  indeterminate decision blocks closeout rather than being relabeled success;
- B-E1 demonstrates dependence-aware interval coverage on fixture scenarios
  with reconstruction-by-case interaction, heteroscedastic stress strata,
  exact-pair applicability checks, missing or censored cells, qualified
  scientific stopping, and heuristic deferral; unsupported independence or
  unresolved coverage fails closed;
- mock/practice isolation and protected-field canaries pass;
- a Strategy parameter cannot be accepted yet ignored by the compiler;
- the semantically responsive fixture-official consumer uses the same exact
  resolved-plan identity as practice while preserving separate rights and the
  unchanged v1 lifecycle;
- a prior fixture cannot be promoted above `TEST_ONLY`, and no v2-backed projection can enter the public v1 provider;
- the TEST_ONLY fixture-ledger append and private authorization-receipt/snapshot
  update are atomic and exact-ref reproducibility passes; the stronger public
  receipt/index graph passes schema and negative tests while public-class
  activation remains unavailable and fail closed;
- the Dossier and qualification manifest remain incomplete/fail closed for LIVE;
- `.agent/WAVE_B_REPORT.md` records exact evidence and remaining human inputs;
- independent correctness review, every valid finding repaired, zero unresolved
  review threads, normal merge,
  and exact-main CI are recorded. Human-reserved qualification and activation
  remain separate and fail closed; no affirmative closeout-response or silence
  gate applies to bounded engineering completion.

Wave C remains unauthorized until `.agent/WAVE.md` moves prospectively.
