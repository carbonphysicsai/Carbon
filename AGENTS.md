# Carbon — Agent Engineering Instructions

This repository contains the implementation of **Carbon**, a competitive scientific-computing system for discovering, independently evaluating, and qualifying methods for constructing fast physical models for engineering simulation.

**Current implementation scope:** P0 is intentionally narrower than that durable system identity. It begins with neural-operator training strategies, validator-controlled fresh retraining, and protected scientific evaluation. Coding agents must implement the current normative specifications and must **not** broaden P0 merely because future architecture documents describe additional model families or reconstruction methods.

This file defines the default engineering rules for any coding agent working in this repository.

The goal is not to generate as much code as possible.

The goal is to produce **small, testable, reviewable changes that faithfully implement Carbon's specifications without inventing science or weakening its safety boundaries.**

---

# 1. Mission

Build Carbon incrementally according to the repository's authoritative design specifications and implementation plan.

Agents may implement software, tests, interfaces, infrastructure, mocks, deterministic fixtures, and explicitly specified scientific logic.

Agents must **not independently decide scientific truth, production thresholds, qualification criteria, or launch readiness.**

When a required decision belongs to a human scientist, subnet operator, security reviewer, or protocol owner:

**stop, mark it as blocked, and state exactly what decision is required.**

Do not guess.

---

# 2. Authority of Repository Documents

Before implementing a ticket, identify and read the documents relevant to that ticket.

The repository specifications govern implementation.

In general:

1. Domain-specific specifications define **semantic behaviour**.
2. `Design_Specs/Build_Out.md` defines **implementation sequencing, ownership, dependencies, and acceptance gates**.
3. `.agent/` tickets (or `agent_pack/.agent/tickets/`) translate the Build Out into bounded implementation work.
4. `AGENTS.md` defines how agents must work inside the repository.

Relevant specifications may include:

- `SPEC.md`
- `Design_Specs/System_Identity_and_Roadmap.md` for architecture/communication context only;
- `Design_Specs/Miner_MCP.md`
- `Design_Specs/Scoring.md`
- generator / science specifications
- validation / qualification specifications
- `Design_Specs/Launch_Bar.md`
- `Design_Specs/Build_Out.md`

**Important:** `System_Identity_and_Roadmap.md`, Gate simulation documents, the Scientific Reference Canon, and preliminary-decision review files may describe future architecture, but they do not override current P0 wire contracts unless their decisions are ratified into the relevant normative domain specification.

Do not rely on memory of a specification when the repository version is available.

### If documents conflict

Do not silently choose an interpretation.

Determine whether one document clearly governs the relevant semantic domain.

If the conflict remains material:

1. stop the affected implementation;
2. record the conflict;
3. identify the exact files/sections involved;
4. request a human decision.

Do not resolve scientific, economic, security, or protocol ambiguity by invention.

---

# 3. Start With Repository Orientation

Before substantial implementation, understand what already exists.

Inspect at minimum:

- repository structure;
- `Design_Specs/`;
- existing `poc/`;
- existing `Carbon_Logic/`;
- existing `neurons/` or Bittensor components;
- tests;
- CI configuration;
- `.agent/` / `agent_pack/`;
- package/dependency configuration;
- existing schemas, interfaces, and public APIs.

If `.agent/ORIENTATION.md` exists, read it first and verify that it is still reasonably current.

If orientation has not been completed, perform it before major implementation.

### Existing code is not disposable

Never assume existing AI-generated or prototype code should be replaced merely because a new architecture exists.

Classify relevant existing code using:

**KEEP → WRAP → REPAIR → REPLACE**

Prefer, in order:

1. **KEEP** working compliant code.
2. **WRAP** working code behind the required interface.
3. **REPAIR** code that is close to the specification.
4. **REPLACE** only where the existing implementation materially conflicts with the specification or creates unnecessary risk.

Do not perform large rewrites without a clear technical reason.

Do not force directory renames simply to make the repository resemble a proposed architecture diagram.

---

# 4. Never Invent Science

This is a hard constraint.

Agents must not invent production values for:

- physical thresholds;
- acceptance envelopes;
- solver tolerances;
- scientific pass/fail boundaries;
- robustness thresholds;
- challenge distributions;
- qualification criteria;
- dataset ranges;
- scoring coefficients requiring scientific approval;
- production hyperparameters presented as scientifically validated;
- any other value requiring domain judgement.

Where a human scientific decision is required, use an explicit placeholder such as:

- `HUMAN_INPUT`
- `None`
- `null`
- `BLOCKED_FOR_LIVE_UNTIL_SET`

as appropriate to the schema.

Mocks and fixtures may use synthetic values **only when clearly labelled as non-production test data and structurally incapable of entering LIVE evaluation.**

The distinction between:

> code that implements a scientific decision

and

> code that makes the scientific decision

must always be preserved.

Agents may do the former.

Agents may not autonomously do the latter.

---

# 5. Core Carbon Invariants

The following invariants must never be weakened for convenience.

## 5.1 No hidden-evaluation leakage

Official seeds, derived seeds, draw IDs, hidden sample identifiers, reversible identifiers, private evaluation metadata, or other information capable of exposing the hidden exam must never appear in:

- Evaluation Cards;
- public Model Cards;
- leaderboards;
- miner-facing MCP responses;
- miner-visible logs;
- error messages;
- telemetry accessible to miners.

Add regression tests where practical.

---

## 5.2 Mock isolation

Mock, light, estimate, scaffold, preview, or free-loop execution must not access:

- official evaluation packs;
- official seeds;
- hidden exam datasets;
- hidden evaluation configuration;
- private validator state.

Mock/free execution must be structurally separated from official evaluation.

Do not rely solely on naming conventions for this isolation.

---

## 5.3 Pinned official evaluation

Every official scored evaluation must be bound to immutable versions of all material evaluation components defined by the specifications.

This may include:

- challenge version;
- generator version;
- scoring version / Score Pack;
- backend/container digest;
- model/training environment;
- other required execution identifiers.

Historical results must remain attributable to the exact evaluation configuration under which they were produced.

---

## 5.4 Disclosure is allow-listed

Internal results are private by default.

Miner-facing or public APIs may return only fields explicitly allowed for the relevant disclosure tier.

Never expose an internal field merely because it is convenient for debugging.

---

## 5.5 LIVE requires human qualification

No agent may autonomously:

- flip a challenge to LIVE;
- sign a qualification manifest;
- declare scientific qualification complete;
- approve a challenge for emissions.

LIVE status must require the human qualification artefacts specified by the repository and must be bound to the **exact challenge version** being activated.

Presence of non-null configuration values alone is not sufficient proof of qualification.

---

## 5.6 Untrusted execution must be isolated

Miner-supplied strategies and other untrusted workloads must eventually execute under the limits defined by the relevant specifications.

Treat miner-controlled input as hostile.

Where applicable enforce:

- compute limits;
- memory limits;
- filesystem isolation;
- network restrictions;
- wall-clock limits;
- process limits;
- explicit input validation.

Do not weaken isolation merely to make a test pass.

---

## 5.7 Infrastructure failure is not scientific failure

Infrastructure failures must remain distinguishable from scientific/model failures.

Examples include:

- node loss;
- queue loss;
- infrastructure OOM;
- container startup failure;
- orchestration failure;
- validator-side infrastructure fault.

Do not score infrastructure failure as model incompetence.

Do not grant scientific success because infrastructure failed.

Preserve the required `FAILED_INFRA`, retry, refund, or equivalent semantics defined by the authoritative specification.

---

## 5.8 Determinism

Official evaluation should be reproducible under identical:

- inputs;
- versions;
- seeds;
- execution limits;
- backend configuration;

within documented tolerances.

Sources of nondeterminism should be controlled or documented rather than ignored.

---

## 5.9 No placeholder LIVE values

Fixture, placeholder, development, stub, mock, or guessed values must never flow into:

- LIVE challenge configuration;
- official scientific qualification;
- emission calculations;
- production ranking.

---

## 5.10 Historical scoring is immutable

Do not silently reinterpret historical evaluations under newly released scoring or challenge versions.

A materially new pack/version applies prospectively unless the specification explicitly defines otherwise.

---

## 5.11 Forbidden score inputs

Unless an authoritative specification is explicitly changed, inputs such as the following must never enter official scientific score or emission calculation:

- prior similarity;
- `estimate`;
- `light_*` results;
- mock metrics;
- exam fee/payment amount.

**Fee ≠ score.**

---

## 5.12 The free loop must not become the official exam

The free/miner exploration path may provide useful directional feedback.

It must remain intentionally incomplete relative to the hidden official evaluation.

Do not accidentally reproduce the private exam through public tooling.

---

# 6. Stub and Mock Backends Never Emit

Any stubbed, mocked, synthetic, or incomplete TrainEval backend must be explicitly non-emission-capable.

Where the architecture supports it, enforce this mechanically with something equivalent to:

`emission_capable = False`

Do not rely solely on documentation.

A stub may exercise:

- lifecycle;
- schemas;
- persistence;
- APIs;
- deterministic test fixtures;
- state transitions;
- disclosure behaviour.

A stub must never generate real emission weights or be treated as evidence of scientific qualification.

---

# 7. Ticket-Based Development

Work on **one bounded ticket at a time** unless a human explicitly authorizes parallel work.

Before editing:

1. read the ticket;
2. read its referenced specifications;
3. inspect the existing implementation;
4. identify dependencies;
5. identify existing tests;
6. run the relevant baseline tests.

Implement the smallest coherent change that satisfies the ticket's Definition of Done.

Avoid unrelated refactors.

Avoid opportunistic architecture redesign.

Avoid formatting entire files unless required.

Keep the diff understandable to the next engineer.

---

# 8. Plan Before Complex Changes

Straightforward tickets can be implemented directly.

For complex work involving multiple modules, protocol semantics, persistence, security boundaries, validator behaviour, or substantial refactoring, create a short implementation plan before editing.

The plan should identify:

- relevant specifications;
- existing implementation being reused;
- files expected to change;
- interfaces affected;
- tests to add or update;
- security/scientific risks;
- unresolved decisions.

Do not use planning as permission to redesign Carbon.

The specification remains authoritative.

(See also `agent_pack/PLANS.md` template.)

---

# 9. Testing Is Part of the Implementation

A ticket is not complete because code was written.

### Before making material changes

Run the relevant existing baseline tests.

Record pre-existing failures rather than attributing them to the new work.

### During implementation

Add or update tests that demonstrate the required behaviour.

Prefer tests for:

- public contracts;
- invariants;
- failure behaviour;
- state transitions;
- deterministic behaviour;
- leakage boundaries;
- disclosure boundaries;
- mock/official isolation;
- malformed/untrusted input.

### Before declaring the ticket complete

Run:

1. the ticket-specific tests;
2. relevant subsystem tests;
3. the required baseline/regression suite;
4. lint/type/static checks if the repository requires them.

Do not delete or weaken a test simply because the implementation fails it.

If the specification intentionally changes behaviour, update the test and document why.

---

# 10. Definition of Done

A ticket is `done` only when:

- the specified behaviour exists;
- acceptance criteria are satisfied;
- required tests pass;
- existing relevant behaviour has not regressed;
- no Carbon invariant has been weakened;
- no unresolved scientific decision was invented;
- code is scoped to the ticket;
- relevant documentation/schema changes are included;
- evidence of completion is recorded.

Where `.agent/WAVE.md` or another tracker is in use, update it with concrete evidence.

Examples:

- test command;
- test file;
- implementation path;
- generated artefact;
- relevant commit.

Do not mark work complete based only on subjective inspection.

---

# 11. Git and Change Hygiene

Use a dedicated branch/worktree for bounded implementation work where the development environment supports it.

Prefer:

**one ticket → one reviewable diff**

Do not directly push unreviewed major changes to production/main branches.

Do not:

- rewrite unrelated history;
- mass-delete existing implementation;
- rename large areas of the repository without need;
- alter public interfaces silently;
- introduce unnecessary dependencies;
- commit secrets;
- commit credentials;
- commit API keys;
- commit local environment configuration containing secrets.

Changes should be easy for a human developer to understand and revert.

---

# 12. Dependency Discipline

Prefer existing repository dependencies when they are fit for purpose.

Before introducing a new dependency, consider:

- whether the standard library or an existing dependency suffices;
- maintenance burden;
- security surface;
- determinism;
- licensing;
- reproducibility;
- deployment implications.

Do not add large frameworks to solve small problems without justification.

Pin versions where reproducibility/security requirements demand it.

---

# 13. Public Interfaces and Schemas

Treat established schemas and public interfaces as contracts.

Do not casually change:

- MCP tool names;
- request/response fields;
- challenge identifiers;
- submission identifiers;
- evaluation card fields;
- status values;
- scoring fields;
- public leaderboard fields;
- validator/miner protocol behaviour.

When the specification requires a contract change:

1. implement it explicitly;
2. update tests;
3. update documentation;
4. consider compatibility/migration behaviour.

Do not silently simplify required state-machine semantics.

---

# 14. Submission and Evaluation State

Submission/evaluation lifecycle semantics must follow the current authoritative specification exactly.

Do not collapse distinct states merely because they appear similar.

In particular, preserve explicit handling for states such as:

- cancellation;
- infrastructure failure;
- scientific/evaluation failure;
- successful completion;

where defined by the current Build Out/specifications.

Idempotency must use all identity/version inputs required by the current specification.

Do not create duplicate official exams through retry behaviour.

---

# 15. Security-Sensitive Work

Treat the following areas as high-risk:

- validator execution;
- container isolation;
- miner-submitted code/configuration;
- authentication/hotkeys;
- payment/fee logic;
- emission calculation;
- Bittensor network interactions;
- secrets;
- persistence of hidden evaluation information;
- challenge activation;
- official evaluation orchestration.

Agents may implement these systems according to specification.

Agents must **not declare them production-secure solely because tests pass.**

Security-sensitive implementation should be clearly surfaced for dedicated human/dev review before production deployment.

---

# 16. Bittensor and Emissions

Agents may build and test Bittensor integration where specified.

Agents must not autonomously:

- deploy Carbon to production mainnet;
- activate real emissions;
- alter live economic parameters;
- register/operate production validator infrastructure;
- execute irreversible economic actions;
- infer missing economic policy.

Production subnet/economic actions require explicit human authorization.

Testnet and mock infrastructure should remain visibly distinguishable from production.

---

# 17. Observability

Important workflows should produce structured, useful observability without leaking private evaluation data.

Where applicable capture:

- lifecycle state;
- failure category;
- runtime duration;
- backend/version identifiers;
- retry count;
- infrastructure vs scientific failure;
- ticket/test execution information.

Never log:

- secrets;
- private keys;
- official seeds;
- hidden exam identifiers;
- sensitive miner-visible evaluation internals.

Prefer explicit failure tags over unstructured error strings where the architecture supports them.

---

# 18. Failure and Escalation Rules

Do not burn unlimited retries.

If two materially different implementation attempts fail for the same underlying reason:

**stop and escalate.**

Also stop when:

- a specification conflict blocks correctness;
- a required scientific parameter is absent;
- security behaviour is ambiguous;
- implementation would weaken an invariant;
- required external credentials/infrastructure are unavailable;
- the ticket requires an architectural decision not already made;
- the existing implementation materially contradicts the specification and replacement would be substantial.

When blocked, report:

1. what you attempted;
2. what failed;
3. relevant files/tests/errors;
4. what you believe the blocker is;
5. the smallest human decision/input required to continue.

A clean blocker is better than invented progress.

---

# 19. Decision Logging

Record material implementation decisions when they are not obvious consequences of the specification.

Do not clutter the decision log with routine coding choices.

Record decisions such as:

- choosing to wrap rather than replace existing code;
- compatibility approaches;
- migration decisions;
- non-obvious architectural mapping;
- consciously deferred risk;
- interpretation confirmed by a human.

Where `.agent/DECISIONS.md` exists, use it.

Do not record secrets.

---

# 20. Code Quality

Prefer code that is:

- explicit;
- boring;
- deterministic;
- testable;
- typed where useful;
- modular without unnecessary abstraction;
- easy for another engineer to audit.

Avoid:

- speculative abstractions;
- enormous god objects;
- cleverness that obscures safety behaviour;
- duplication of existing functionality;
- unexplained magic constants;
- hidden global state;
- broad exception swallowing;
- silent failure.

Scientific and protocol-critical behaviour should be particularly easy to trace.

---

# 21. Human Ownership Boundaries

Agents may build a very large proportion of Carbon.

Humans retain final authority over:

### Scientific authority
Physics assumptions, challenge design, scientific thresholds, qualification criteria, and claims of scientific validity.

### Security authority
Production isolation, adversarial review, validator hardening, and acceptance of residual security risk.

### Economic authority
Emission behaviour, fees with economic consequence, live subnet parameters, and production deployment.

### Launch authority
Testnet → production decisions and LIVE qualification.

Code generation does not transfer these responsibilities to the agent.

---

# 22. Completion Report

At the end of a ticket, provide a concise report containing:

### Implemented
What changed.

### Reused
Important existing code that was kept/wrapped/repaired.

### Tests
Exact relevant commands executed and their results.

### Invariants
Any Carbon invariants directly exercised by the change.

### Risks / Follow-up
Anything requiring later review.

### Human Input Required
Only unresolved decisions actually blocking or qualifying future work.

Keep reports factual.

Do not describe incomplete work as complete.

---

# 23. Core Principle

When choosing between:

**moving faster by guessing**

and

**stopping because Carbon's specification or science does not provide the answer**

always choose the second.

The target is not autonomous code volume.

The target is a repository that a strong scientific-computing/Bittensor engineer can inherit, audit, understand, and safely continue toward production.
