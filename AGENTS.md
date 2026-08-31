# Carbon — Agent Engineering Instructions

This repository contains the implementation of **Carbon**, an incentivized experimental system for discovering, independently testing, learning from, and qualifying methods for constructing fast physical models.

The first bounded implementation searches neural-operator `TrainingStrategy` objects. That is a P0 subtype of Carbon's broader long-term construction-method architecture; coding agents must not widen execution freedom merely because the long-term ontology is broader.

This file defines the default engineering behavior for coding agents and human executors. Repository-wide authority is mapped in [`CONSTITUTION.md`](./CONSTITUTION.md).

The goal is not maximum code volume. The goal is:

> **small, testable, reviewable changes that faithfully implement Carbon's current specifications, preserve future constitutional boundaries, and never invent science, economics, security guarantees, or commercial traction.**

---

# 1. Mandatory authority read

Before every new ticket or major wave, read:

1. `CONSTITUTION.md`;
2. `.agent/INVARIANTS.md`;
3. `.agent/WAVE.md`;
4. the active ticket under `.agent/tickets/`;
5. for development tickets, `docs/development/carbon_hub/orientation/AGENT_MAINTENANCE_CONTRACT.md`;
6. ticket-referenced domain specifications;
7. `Design_Specs/Build_Out.md`;
8. for A8 onward, `Design_Specs/Build_Out_Constitutional_Overlay.md`;
9. `Design_Specs/Agentic_Development_Master_Plan.md` only for relevant future-compatibility constraints.

Scientific constitutional reference:

- `docs/context/SCIENTIFIC_REFERENCE_CANON_V4_MASTER.md`.

If work touches customer/product/business semantics, also read the relevant `Business/` authority, beginning with `Business/Business_Canon.md`.

If work touches public claims, also read `docs/publications/README.md`.

Do not rely on memory when the repository version is available.

---

# 2. Authority and conflict handling

Authority is domain-owned.

- `CONSTITUTION.md` defines repository-wide authority boundaries and durable doctrine.
- Scientific canon controls scientific constitutional interpretation.
- Domain specifications define current semantic behavior.
- `Build_Out.md` defines current detailed sequencing.
- `Build_Out_Constitutional_Overlay.md` prevents stale sequencing shorthand from violating the integrated constitution.
- `.agent/` tickets define bounded active work.
- `Business/` governs commercial strategy outside the scientific judge.
- Publications explain; they do not define runtime truth.

If documents materially conflict:

1. identify the semantic domain;
2. determine the domain owner;
3. check the constitutional overlay;
4. classify the seam as `NO_CONFLICT`, `DOCUMENTATION_LAG`, `IMPLEMENTATION_LAG`, `MIGRATION_REQUIRED`, or `NEW_OWNER_DECISION_REQUIRED`;
5. if a material decision remains unresolved, stop the affected change and
   request human/owner input.

An engineering decision within the active ticket's delegated authority is no
longer unresolved for this rule once the executor selects and records the
recommended working decision and sends any required lead notification under
`.agent/DELEGATED_DECISION_PROTOCOL.md`. A human-reserved decision remains
unresolved: the affected behavior or sub-scope must stop and stay fail closed,
but unrelated authorized ticket work may continue. Stop the whole ticket only
when no correct bounded implementation can proceed without that reserved
decision.

Do not silently choose the convenient interpretation.

---

# 3. Mission and human ownership

Agents may implement software, tests, interfaces, infrastructure, deterministic fixtures, mocks, schemas, adapters, and explicitly specified scientific logic.

Agents must not independently decide:

- physical/scientific truth;
- production thresholds or tolerances;
- Challenge population/envelope claims;
- qualification pass/fail;
- launch readiness;
- live economic policy;
- security acceptance;
- customer rights/IP policy;
- production deployment authority;
- investor traction claims.

Humans retain final authority over scientific qualification, security acceptance, live economics, launch, legal/commercial rights, and material company decisions.

When owner input is required: **stop the affected behavior or sub-scope, mark
it blocked, and state the smallest decision required.** Unrelated authorized
ticket work may continue only where the unresolved value remains explicit and
fail closed. Stop the whole ticket when no correct bounded implementation can
proceed without that owner decision.

---

# 4. Orientation and reuse

Before substantial implementation, inspect relevant:

- repository structure;
- `Design_Specs/`;
- current canonical `carbon/` implementation;
- tests and CI;
- `.agent/` / `agent_pack/`;
- schemas, persistence, public APIs;
- current authority/maturity map;
- `.agent/CODE_AUTHORITY.toml`; and
- `docs/history/LEGACY_CODE_INDEX.md`.

Inspect archived PoC, Julia, neuron/Bittensor, or other quarantined executable
components only when the active ticket explicitly owns their deliberate reuse
or migration. Use the exact archive ref recorded in the legacy index. Archive
presence grants no current implementation authority and is not part of normal
test discovery, packaging, orientation, or ticket acceptance.

If `.agent/ORIENTATION.md` exists, treat it as historical orientation evidence and verify whether it is stale relative to the current constitution.

Classify existing code:

**KEEP → WRAP → REPAIR → REPLACE**

Prefer in that order. Do not perform large rewrites or directory churn just to match an architecture diagram.

---

# 5. Never invent science

Agents must not invent production values for:

- physical thresholds;
- solver tolerances;
- scientific gates;
- target populations or sampling laws;
- uncertainty floors;
- qualification criteria;
- challenge distributions;
- production scoring coefficients requiring science approval;
- claims of physical validity.

Use explicit blocked placeholders such as `HUMAN_INPUT`, `None`, `null`, or equivalent where the schema permits.

Synthetic fixture values are allowed only when clearly non-production and structurally unable to enter LIVE scientific/economic authority.

Preserve the distinction:

> code that **implements** a scientific decision

versus

> code that **makes** the scientific decision.

Agents may do the former, not the latter.

---

# 6. Core implementation invariants

These bind all current Wave-A work.

1. **No hidden-evaluation leakage.** Official seeds, derived seeds, draw IDs, reversible IDs, protected samples, private metadata, or reconstruction-sensitive hidden state never appear in miner/public surfaces.
2. **Mock isolation.** Mock/light/estimate/scaffold/free execution never accesses official packs, seeds, protected exam data, or private validator state.
3. **Pinned official evaluation.** Official results bind immutable material versions/identities required by the active spec.
4. **Disclosure is allow-listed.** Internal fields remain private unless explicitly authorized for the target audience.
5. **LIVE requires human qualification.** No agent flips LIVE, signs qualification, or declares production scientific readiness.
6. **Untrusted execution is hostile.** Production miner-controlled workloads require explicit compute/memory/filesystem/network/process/wall-clock isolation.
7. **Infrastructure failure is not scientific failure.** Preserve typed `FAILED_INFRA`, retry, refund, and non-scientific semantics.
8. **Determinism / bounded reproducibility.** Identical registered execution should reproduce within documented tolerances.
9. **No placeholder LIVE.** Fixture/mock/stub values never become LIVE evidence, production ranking, frontier entitlement, or settlement.
10. **Historical evidence is versioned.** No silent rescore/reinterpretation under newer scientific contracts.
11. **Forbidden score inputs.** Prior similarity, estimate/light/mock metrics, exam fee, customer payment, or sponsor size never enter official score unless a future registered scientific contract explicitly gives a metric a legitimate scientific role.
12. **The free loop cannot become the official exam.** Practice signal stays intentionally incomplete.
13. **A8 fixture execution is not production authority.** Fixture/stub execution cannot create frontier, treasury, product, or production claims.
14. **A5 scoring does not own frontier/treasury policy.**
15. **A7 submission lifecycle does not own frontier/treasury state.**

See `.agent/INVARIANTS.md` for the always-on expanded list.

---

# 7. Integrated scientific invariants

Future work must preserve these even when current types do not yet implement them fully.

## 7.1 Exam qualification first

> **The exam must be qualified before it may qualify candidates.**

Generator determinism, successful execution, or a non-null config is not scientific adequacy.

## 7.2 Population semantics

The scientific task owns the population. `P(x)`, proposal/sampling `Q(x)`, and evidence/score weighting `w(x)` are separate where applicable.

Seed separation does not prove semantic decontamination.

## 7.3 Admissibility before ranking

> **Mandatory scientific failure cannot be compensated by soft performance.**

## 7.4 Measurement authority

Measurement definition, qualification, applicability, and score use are separate. A governing equation or symbolic representation does not certify a measurement implementation.

## 7.5 Reference failure separation

Reference/truth/generator failure must not be collapsed into candidate failure.

## 7.6 Challenge-bound score

A scalar Challenge score is not automatically comparable across Challenges.

## 7.7 Frontier promotion is separate

Leaderboard/rank may nominate. A future `FrontierAdvanceEvent` requires its own registered scientific evidence/policy.

> **A new leader is an evidence state, not a floating-point inequality.**

## 7.8 Science and settlement are separate

Treasury/network transport settles entitlement; it does not create scientific merit.

## 7.9 Construction and official evaluation are separate security domains

Future `ModelConstructionStrategy`, `ConstructionProgram`, reconstruction workers, or arbitrary participant code do not gain evaluator authority.

> **Carbon can widen what participants are allowed to discover without changing who controls the grade.**

## 7.10 Agent autonomy expands hypotheses, not authority

Landscape, priors, construction agents, or Physics Intelligence may propose. Registered contracts and independent experiments decide.

---

# 8. Maturity discipline and historical snapshot

The block below records the repository state at the 2026-08-23 constitutional
reconciliation. It is historical evidence, not the live ticket board, and must
not be used to select the next ticket.

For current ticket status and sequencing, read `.agent/WAVE.md` at the exact
current commit. If a WAVE status is explicitly conditional on independent
review, human authorization, or merge, treat the prior merged status as
authoritative until that gate is satisfied. Use the active ticket and
`docs/context/IMPLEMENTED_VS_SPECIFIED_CURRENT.md` to interpret the bounded
scope of any status.

At the 2026-08-23 constitutional reconciliation:

```text
A-1 done
A0–A7 done in recorded bounded scopes
A8 todo / not implemented
A9 todo
A10 todo
A11 todo
A12 todo
```

Never relabel a ticket merely because documentation describes its intended
design. A status changes only when the applicable ticket evidence and WAVE
review, authorization, and merge gate are satisfied.

A component may separately be:

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

Do not infer later states from earlier ones.

---

# 9. Ticket-based development

Work on one bounded ticket at a time unless explicitly authorized otherwise.

Before editing:

1. read current authority/ticket;
2. identify one primary Development Hub `map_ref` and classify hub impact;
3. inspect existing implementation;
4. identify dependencies/tests;
5. run relevant baseline tests;
6. create a plan for multi-module/security/protocol work.

During work, record a concise Development Hub event when a material decision,
adjustment, bug, blocker, risk, or evidence result changes team understanding,
purpose, placement, status, dependency, boundary, maturity, or primary links.
Do not duplicate routine PR detail in the map.

Implement the smallest coherent change satisfying the ticket DoD.

Avoid unrelated refactors, speculative future abstractions, and opportunistic architecture redesign.

Future waves in the Agentic Master Plan are compatibility context, not implementation permission.

---

# 10. Testing and evidence

A ticket is not complete because code exists.

Before declaring completion run:

1. ticket-specific tests;
2. relevant subsystem tests;
3. required baseline/regression suite;
4. lint/type/static checks required by the repo;
5. relevant security/leakage/invariant tests.

For development-ticket changes, also reconcile the hub source, regenerate its
derived outputs, and run the checks in
`docs/development/carbon_hub/orientation/AGENT_MAINTENANCE_CONTRACT.md`.
Repository authority remains controlling over the derived hub.

Prefer tests for:

- public contracts;
- exact identity/version behavior;
- state transitions;
- deterministic execution;
- failure classification;
- leakage/disclosure boundaries;
- mock/official isolation;
- malformed/untrusted input;
- idempotency/concurrency where relevant.

Do not delete/weaken a test merely because implementation fails it.

Record completion evidence in `.agent/WAVE.md` only when the ticket's review/merge rules are satisfied.

---

# 11. Stub and fixture policy

Stubbed, mocked, synthetic, or incomplete TrainEval/reconstruction backends may exercise:

- lifecycle;
- schemas;
- persistence;
- APIs;
- deterministic fixtures;
- state transitions;
- disclosure behavior.

They must not create:

- LIVE scientific authority;
- production rankings;
- frontier events;
- treasury obligations;
- product qualification;
- claims of secure arbitrary-code execution.

Prefer structural capability/provenance separation. Do not rely on a caller-supplied `emission_capable` Boolean as scientific authority.

---

# 12. Public interfaces and migration

Treat established schemas/public interfaces as contracts.

Do not casually change:

- MCP tools;
- request/response fields;
- Challenge/submission IDs;
- public card/leaderboard fields;
- status enums;
- scoring fields;
- validator/miner protocol behavior.

When a constitutional migration requires change:

1. specify it explicitly;
2. version/migrate prospectively;
3. update tests;
4. update docs;
5. preserve historical evidence interpretation.

---

# 13. Security-sensitive work

High-risk areas include:

- validator/reconstruction execution;
- container/sandbox isolation;
- miner-supplied input/code;
- authentication/hotkeys;
- fee/payment logic;
- Bittensor integration;
- treasury/settlement;
- secrets;
- hidden evaluation persistence;
- Challenge activation;
- official evaluation orchestration;
- private/customer-hosted truth;
- customer confidential data.

Tests do not constitute a production security audit. Surface such work for dedicated review.

---

# 14. Bittensor, treasury, and economics

Agents may implement/test network integration only where specified.

Agents must not autonomously:

- deploy production mainnet infrastructure;
- activate real economic settlement;
- alter live economic parameters;
- infer missing treasury policy;
- create a direct OpCo-revenue-to-Alpha mechanism;
- perform irreversible economic actions.

Current/legacy score-to-weight transport must not be mistaken for the long-term constitutional settlement design.

Target future separation:

```text
ScoreResult
→ contender nomination
→ frontier promotion
→ FrontierAdvanceEvent
→ SettlementObligation
→ treasury settlement
```

Implement only in the authorized future wave.

---

# 15. Business and commercial boundary

Business authority lives under `Business/`.

Agents may implement commercial systems when authorized, but business terms never alter scientific truth.

Hard rules:

- customer payment != score;
- commercial acceptance != scientific qualification;
- sponsor reward != scientific merit;
- OpCo revenue != Alpha value by declaration;
- customer/private evidence reuse only where rights permit;
- architecture-specified products are not commercial traction.

---

# 16. Publications and claim discipline

Papers, README, decks, websites, and investor materials are explanatory layers.

Never convert:

```text
DESIGN → IMPLEMENTED
IMPLEMENTED → SCIENTIFICALLY QUALIFIED
TESTED → PRODUCTION SECURE
BUSINESS DESIGN → PAID TRACTION
NETWORK DESIGN → PROVEN NETWORK ADVANTAGE
```

without evidence.

---

# 17. Failure and escalation

Stop and escalate when:

- specification/constitution conflict blocks correctness;
- required scientific/economic/security/legal input is absent for an affected
  behavior and cannot remain explicit and fail closed;
- implementation would weaken an invariant;
- required external credentials/infrastructure are unavailable;
- two materially different attempts fail for the same root reason;
- existing implementation materially contradicts the spec and replacement would be substantial;
- the ticket requires a later-wave architectural decision not yet authorized.

Report:

1. what was attempted;
2. what failed;
3. relevant files/tests/errors;
4. likely blocker;
5. smallest owner decision required.

A clean blocker is better than invented progress.

These stop conditions apply to the affected change or sub-scope. They stop the
whole ticket only when the blocker prevents every correct bounded continuation
under `.agent/DELEGATED_DECISION_PROTOCOL.md`.

---

# 18. Git/change hygiene

Prefer one ticket → one reviewable branch/diff.

Do not:

- mass-delete or mass-rename unrelated code;
- rewrite unrelated history;
- silently alter public interfaces;
- introduce unnecessary dependencies;
- commit secrets/credentials;
- push unreviewed major production changes merely for speed.

Changes should be understandable and revertible.

---

# 19. Completion report

At ticket end report:

### Implemented
What changed.

### Reused
KEEP/WRAP/REPAIR choices.

### Tests
Exact commands/results.

### Invariants
Relevant constitutional invariants exercised.

### Maturity
Which states are actually earned: specified / implemented / tested / qualified etc.

### Hub Impact
Primary `map_ref`; changed hub source/events and regeneration evidence, or the
specific reason the hub's purpose, placement, status, dependencies, boundaries,
maturity, and primary links remain accurate.

### Risks / Follow-up
Remaining work.

### Human Input Required
Only unresolved owner decisions.

Do not describe incomplete work as complete.

---

# 20. Core principle

When choosing between:

**moving faster by guessing**

and

**stopping because Carbon's current science, security, economics, business authority, or specification does not provide the answer**

always choose the second.

> **The search surface may widen. The authority boundary may not.**
