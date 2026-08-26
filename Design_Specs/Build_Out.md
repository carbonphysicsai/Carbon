# Carbon Build-Out Specification

> **Reconciliation:** sequencing authority only. Scoring: binary gates + weighted geometric; P0 baseline **0.45/0.30/0.25**.


> **Reconciliation (post-ratification):** `Build_Out.md` remains **sequencing authority**, not an alternate design spec. Reflect reconciled semantics only after higher-level docs (`Scoring.md`, `Trustless_Verification.md`, `Miner_MCP.md`, `Launch_Bar.md`) are treated as source of truth. Do not re-introduce sigmoid-hard-gates, raw soft-leg multiplication as normative aggregate, or mock-as-false-physics language in tickets.


**Audience:** Coding agents, lead engineers, SciML reviewers, contractors.  
**Version:** 1.4<br>
**Status:** Executable requirements contract  
**Companions:** `SPEC.md`, `Miner_MCP.md` (v2.2+), `Scoring.md`, `Generator_Creation.md`, `Generator_Validation.md`, `Evidence_and_Envelope_Standards.md`, `Data_Management.md`, `Launch_Bar.md`, `POC_Burgers_FNO.md`  
**Post-P0 companions:** `Landscape_Agent.md`, `Specialist_Bank.md`, `Customer_Bounds_Specialist.md`, `Use_Cases_by_Phase.md`

---

## 0. Normative authority (read first)

Authority is **domain-owned**, not a single global precedence ladder. When documents overlap, use the document that owns the semantic domain below. A higher-level document's example does not override the domain owner's normative rule.

| Domain | Canonical owner |
|--------|-----------------|
| System architecture / protocol doctrine / constitutional invariants | `SPEC.md` |
| Miner-facing behaviour, free vs paid loop, disclosure | `Miner_MCP.md` |
| Exact scoring mathematics, forbidden score inputs, Score Pack schema | `Scoring.md` |
| Official data, seed hierarchy, train/eval/stress separation | `Data_Management.md` + `Trustless_Verification.md` |
| Generator construction, scientific evidence, envelope qualification | `Generator_Creation.md`, `Generator_Validation.md`, `Evidence_and_Envelope_Standards.md` |
| Stop-ship and representation readiness | `Launch_Bar.md` |
| Commercial specialist qualification | `Specialist_Bank.md` |
| Landscape knowledge-layer behaviour | `Landscape_Agent.md` |
| Implementation sequencing, ownership, dependencies, Wave acceptance | **This file (`Build_Out.md`)** |

`Build_Out.md` does **not** override semantic behaviour owned by another domain document. If two documents within the same domain materially conflict, stop the affected implementation, record the exact conflict, and request a human decision rather than inventing a resolution.

**No historical version pointers.** Acceptance criteria live in the current documents — not in “v1.1 somewhere.”

## 1. Execution principle

**Coding agents build the full framework.**  
**Humans (SciML / protocol lead) fill science, thresholds, and launch judgment.**

Agents ship interfaces, loaders, fixtures with `HUMAN_INPUT` / `TODO(sciml)` markers, and tests that **fail closed** when human inputs are missing in LIVE mode. Agents never invent gate thresholds, envelope claims, or dossier pass/fail as production truth.

**P0 doctrine:** Prefer one vertical fixture loop over ten empty modules.

---

## 2. Cross-cutting invariants (never violate)

These rules bind every component. Tests must cover them where enforceable in code.

1. **No seed leakage.** Official seeds, derived seeds, draw IDs, or reversible identifiers never appear in EvaluationCard, leaderboard, MCP outputs, or miner-visible logs.
2. **Practice isolation.** Nominal practice/research execution never accesses
   official packs, official entropy/seeds, or protected exam data.
3. **Pinned evaluation.** Every scored submission is bound to immutable challenge / generator / Score Pack / backend (container digest) versions.
4. **Disclosure allow-list.** InternalResult / Model Card fields are never returned on miner-facing APIs unless explicitly allow-listed for the disclosure tier.
5. **LIVE requires qualification.** LIVE challenges require a complete signed human qualification manifest for that exact challenge version (not merely non-null YAML).
6. **Execution isolation.** Miner-supplied strategies run under enforced compute, network, filesystem, and wall-clock limits. Strategy execution isolation is a **P0 security invariant** (implementation may live in ops docs; requirement is here).
7. **Infra ≠ science.** Infrastructure failures (OOM policy kill, node death, queue loss) are never scored as scientific / physics failures and never grant emissions.
8. **Determinism.** Re-running an identical official evaluation under identical versions, seeds, and limits is deterministic within documented tolerances.
9. **No placeholder LIVE.** Placeholder, fixture, or mock values never enter LIVE configuration or emission weights.
10. **No silent rescore.** Historical evaluation records are never silently reinterpreted under newer packs; new pack ⇒ new scoring_version for future runs only.
11. **Forbidden score inputs.** Prior similarity/alignment, `estimate`,
    resource forecasts, practice/`light_*` metrics, research information value,
    exam fee, and mock metrics never enter `S_combined` / Yuma weights.
12. **Practice is useful without revealing the realized exam.** Carbon measures
    leakage as incremental ability to infer protected official cases, realized
    stress composition, exact margins, or unresolved ordering after controlling
    for physics performance on evaluator-held shadow cases sampled from the
    declared distribution. Transferable rank improvement can reflect better
    physics and is not itself a leak. Practice remains declared-incomplete and
    outside official lifecycle, score, and scheduling authority.

---

## 3. Confidence matrix (who owns what)

| ID | Component | Agent confidence | Agent builds | Human fills |
|----|-----------|------------------|--------------|-------------|
| C0 | Monorepo / CI | **High** | All | Review |
| C1 | Challenge registry | **High** | All + LIVE gate enforcement | LIVE decision + qualification artifacts |
| C2 | Strategy schema | **High** | All | Rare field adds |
| C3 | Procedural generator | **Med** | Interface, roles, determinism harness, fixture generator | Envelope, sampling law, exclusions |
| C4 | Dossier | **Low** | Script skeleton, artifact layout, registry gate | Pass/fail, reference rank, calibration |
| C5 | Scoring engine + packs | **High** / **Low** | Engine, YAML schema, fail-closed, forbidden-input guards | Thresholds, weights |
| C6 | Seeding / roles | **High** | Domain separation + leakage tests | Seed derivation formula confirm |
| C7 | Validator neuron | **Med** | Composition harness across A7 FSM/pins, A8 execution, and A6 publication | Train backend quality, concrete A8 runtime qualification, BT ops |
| C8 | Miner neuron | **High** | Optional thin client | — |
| C9 | Miner MCP | **High** | Bounded control/disclosure tools + policy guards; later separately ratified practice/research service | Prior directive vocabulary/publication, scaffold body, production resource/query/authentication policy |
| C10 | Prior artifacts | **Med** | Immutable store, private TEST_ONLY staging, publisher schemas, ledger/redaction tests | Coarsen policy, first external prior |
| C11 | Practice packs / scaffolds | **Med** | Format, registry, nominal practice guards | Practice scope/ranges, scaffold body |
| C12 | Card store | **High** | Internal + budgeted paths | Disclosure tier confirm |
| C13 | Fees | **High** | Ledger, idempotency, fee≠score | Fee amount |
| C14 | Leaderboard | **High** | Public fields only | — |
| C15 | Bittensor | **Med** | Wiring + weight map | Mainnet params |
| C16 | Observability | **High** | Logs/metrics | Alert thresholds |
| C17–18 | Landscape / specialists | **Out P0** | Card schema hooks only in P0; Waves E–F in §18 | See `Landscape_Agent.md`, `Specialist_Bank.md` |
| C19 | Reference solvers | **Low** | Wrapper + pin skeleton | Convergence evidence |

---

## 4. Phase 0 waves

```text
WAVE A — infrastructure science cannot block
  C0 CI · C2 schema · C1 registry · C6 seeds/mock guards
  C5 scoring ENGINE + fixture pack schema (HUMAN_INPUT thresholds OK)
  C12 card store + Phase 0 disclosure filter
  C13 fees + submission_id + FSM skeleton
  C9 MCP: get_challenge_info, get_prior, get_mock_scaffold, dry_validate,
          structural-only estimate, submit, get_submission_result
  C14 leaderboard · C16 logging
  TrainEvalAPI STUB (deterministic synthetic fixture scalar material; never emission-capable)

WAVE B — science-ready skeletons
  B-02A physical-task / population / SamplingPlan / canonical-case contracts
  B-02B CandidateAssemblyContract + ParameterCatalog + StrategyCompiler
  C3 Generator API + Burgers fixture (HUMAN_INPUT ranges)
  C4 dossier layout + qualification manifest schema
  C19 ReferencePolicy / TruthAsset / primary-witness runner interfaces
  C5 MeasurementContract + Score Pack authoring bindings
  C9/C11 separately ratified nominal mock/practice research lane
  B-07R architecture ratification → B-07S exact bounded service protocol
  B-07A shared v2 nominal primitives → B-07G twelve-operation service integration
  C10 PriorPack v2 store + private TEST_ONLY staging + public-publication schemas
  ResearchTask + ExperimentRecord + ResearchReceipt fixture lifecycle
  Autoresearch utility / conditional-leakage gauntlet

WAVE C — vertical integration
  Real TrainEvalAPI behind nominally separate future qualified official and practice entry points
  C7 validator: queue → hidden data → run → score → cards
  MCP e2e: free loop then paid loop
  C15: actual Bittensor testnet path (not stub-only)

WAVE D — human qualification (not agent-owned)
  SciML: envelope, dossier Level-1, thresholds, practice incompleteness, scaffold mediocrity
  Protocol: Launch_Bar (+ MCP §2.4), fee value, qualification manifest signed, LIVE flip

POST-P0 (not required for P0; see §18)
  WAVE E — Landscape signals          → Landscape_Agent.md
  WAVE F — Specialist bank            → Specialist_Bank.md
  WAVE G — Customer bounds / sponsors → Customer_Bounds_Specialist.md
```

**Stub policy:** Wave A may use the fixture-official A8 stub for bounded
lifecycle/contract CI. Wave B may add nominal practice/research plumbing only
after its separate request/resource/disclosure contract is ratified. **Synthetic
stub material must never write emission weights or LIVE leaderboard ranks.**
Wave C requires a separately qualified real backend before testnet acceptance.

### 4.1 Bounded A9 Wave-A split

A9 Wave A is an in-process control/disclosure boundary, not an execution
surface. It registers exactly the seven names above under schema `"1.0"`, with
no aliases and no network server. `light_compare`, `light_train`, and
`list_my_submissions` are unavailable. The first two names remain retired;
Wave B practice uses B-07S-ratified `start_research_task` task kinds. The third
has no Wave-A implementation authority.

The Wave-A `estimate` is a provider-derived structural/prior projection only.
It performs no execution, imports/calls no A4/A5/A8 path, uses no mock,
fixture-official, or official context/pack, and returns no quality score,
official-score prediction, rank, card/gate prediction, weight, or emission
value. Missing prior/scaffold/estimate providers fail closed; Wave A adds no
production provider, prior content, scaffold body, or default limit/query
policy. See `Miner_MCP.md` and A9-R1--A9-R15 for the exact contract.

---

## 5. TrainEvalAPI (critical shared contract)

TrainEval remains the single architectural owner of official-shaped execution
and the future MCP practice-task execution family. Historical
`light_compare` / `light_train` names are not authority for the Wave B v2
surface. Data rights are
not selected by a string mode. Fixture-official, future production, and mock
execution use nominally separate request/result types and entry points. The
exact bounded contract is governed by ratified decisions A8-R1--A8-R15 in
`.agent/DECISIONS.md`, together with current A4--A7 types; this section records
the sequencing-level contract.

Historical ratification-era snapshot (retained as process evidence, not
current live maturity):

```text
A8 SPECIFIED / RATIFIED: YES only after this documentation candidate is independently reviewed, explicitly human-authorized, and merged
A8 IMPLEMENTED: NO
A8 TESTED: NO
A8 PRODUCTION-QUALIFIED: NO
A8 WAVE STATUS: todo
```

Current bounded maturity and closeout condition:

```text
A8 SPECIFIED / RATIFIED: YES

A8 IMPLEMENTED:
YES on current main for the bounded fixture-official,
deterministic, process-local stub scope, including the reviewed conformance
repair

A8 TESTED:
YES only for the exact recorded CPU/security/import/wheel/quality scope

A8 SCIENTIFICALLY_QUALIFIED: NO
A8 SECURITY_QUALIFIED: NO
A8 NETWORK_QUALIFIED: NO
A8 COMMERCIALLY_VALIDATED: NO
A8 PRODUCTION_QUALIFIED: NO

A8 WAVE STATUS:
done only after this documentation-only closeout is independently reviewed,
explicitly human-authorized, and merged
```

### 5.1 First bounded implementation: fixture-official only

```text
FixtureTrainEvalService.run_fixture(
  envelope: exact FixtureExecutionEnvelope
) -> private FixtureRunOutcome
```

Trusted composition constructs the service with an immutable exact
`FixtureStubProfile`, an exact A4 `DeterministicFixtureProvider`, an exact
verified A5 `LoadedScorePack`, trusted fixture runtime configuration, an exact
declared execution-environment identity, and the deterministic
`FixtureStubBackend`.

The fixture runtime policy is an exact immutable fixture-only composition
value. It carries safe environment-identity fields and a total closed-cause to
retry-class table for fixture lifecycle tests, but no production/numeric
runtime values, generic mode, fallback, backend selector, or emission Boolean.
Its retry table is trusted fixture test policy, not A7 permission/budget or a
production default.

A7 supplies the exact fixture envelope and `ExecutionAttemptHandle`. The run
call accepts no independently caller-selected Strategy, StrategyHash, batch,
mode, runtime limit, attempt number, ChallengeKey, SeedPin, environment pin,
context, seed, Score Pack, or backend identity. A8 does not repeat A2 schema
validation or A3 challenge/backbone admission.

The fixture path consumes only an exact `FixtureOfficialContext` acquired
through `acquire_fixture_official_context` and derives only through
`derive_fixture_official_seed`. It never accepts `MockContext`, provider-origin
`OfficialContext`, qualification context, raw entropy, or a caller-provided
derived seed. Current process-local envelopes and handles are correctness
values, not authenticated capabilities; exact-type checks are not a sandbox.

### 5.2 Reserved practice/research lane

Build Out and the A9 intent still require an honest non-authoritative practice
path, but a generic `mock | official` mode is forbidden. Its domain runner is a
separate nominal entry point, conceptually:

```text
MockTrainEvalService.run_mock(
  request: exact future MockExecutionRequest
) -> MockRunOutcome
```

The exact practice request, resource, disclosure, and research-task contract
requires B-07R architecture ratification and B-07S wire-protocol ratification
before implementation. A9's separately ratified Wave-A `StructuralEstimate`
does not cross this gate because it performs no execution and uses no
A8/A4/A5 surface.

The owner-review candidate for that later ratification is
`Miner_MCP_Wave_B_Research_Contract.md`. It proposes an explicit
`ChallengeInteractionManifest`, Challenge-bound `ParameterCatalog`, semantic
compiler, nominal practice tasks, evidence classes, research receipts, and a
versioned PriorPack. It is planning input only until independently reviewed,
explicitly human-authorized, normally merged, and activated on the Wave board.
It does not modify the current A8 or A9 contract.

The nominal practice runner may use only mock context/data rights. Its
`MockRunOutcome` is not an A5 `InternalResult`, cannot enter A7's official
submission lifecycle or A6, cannot create a card, and cannot affect fees,
official score, leaderboard rank, weights, or emissions. It is mechanically
non-emission-capable.

### 5.3 Private fixture outcome and A7 mapping

The closed private fixture outcome is one of:

```text
CompletedFixtureRun(exact handle, exact A5 InternalResult)
StrategyFailedRun(exact handle, closed StrategyFailureCause)
InfrastructureFailedRun(
  exact handle,
  closed InfrastructureRetryClass,
  closed InfrastructureCause
)
```

Pairing a handle and result is process-local trusted composition, not
authenticated execution provenance. A7 revalidates the handle and A4/A5 pin
projection, but substitution-resistant provenance remains later receipt/
evidence work.

Only exact A5 `SCORED` and `MANDATORY_GATE_FAILED` results may appear in a
completion. `PACK_NOT_READY`, missing/non-finite/partial execution material,
pack/input/computation failure, backend/reference failure, and infrastructure
failure are operational and cannot become a failed scientific gate or zero.
A8 never returns `invalid_strategy`; A2/A3 rejection occurred before A7 queue
admission. Strategy failure is permitted only when positively attributable to
the Strategy; ambiguity defaults to infrastructure. Because the bounded
synthetic stub ignores Strategy and executes no miner code, its service cannot
emit `StrategyFailedRun`; the closed variant is reserved for a separately
ratified real backend. The later implementation task must test its A7 mapping
at the private composition seam without making the fixture service fabricate
Strategy blame.

Trusted later composition, not A8 storage and not an A7 import of A8, maps a
completion to `complete_and_publish`, a Strategy failure to `fail_strategy`, a
retry-classified infrastructure failure to `retry_infrastructure`, and a
non-retryable infrastructure failure to `fail_infrastructure`. A7 alone owns
current-handle authority, retry budget, terminalization, refund, cancellation,
and A6 publication. Wrong, subclassed, cross-kind, malformed, or internally
contradictory untrusted boundary objects produce stable non-echoing typed
errors and do not authorize an A7 mutation. A stale callback is rejected by
A7 without mutation.

### 5.4 Runtime resources and execution identity

A7 `SubmissionResourceLimits` govern hostile submission capture and retained
record capacity. They are not runtime limits. A7's immutable
`ExecutionEnvironmentPin` is safe attempt-identity metadata, not runtime
configuration or qualification proof.

A8 owns trusted runtime policy, actual CPU/GPU/backend selection, concrete
memory/time/process/filesystem/network controls, backend/container launch and
shutdown, output materialization limits, shape/type/finiteness validation, and
exception conversion/redaction. The first synchronous fixture stub has no
cancellation API; a future real adapter must separately ratify transient
cooperative and hard shutdown. The A8 configuration reconstructs its declared
environment pin and must match the handle pin exactly before execution.
Production values and real sandbox/container/backend qualification remain
human-owned later work.

### 5.5 A5 and disclosure boundary

A8 privately validates complete execution material and constructs the exact
pack-authorized scalar input only through
`LoadedScorePack.fixture_score_input`, then invokes current
`ScoreEngine.score`. A5 remains the sole owner of `ScoreInput`, pack readiness,
gate semantics, scalar transforms, aggregation, `ScoreStatus`, and
`InternalResult`. A8 does not construct `InternalResult` directly or invent a
metric, threshold, gate, weight, transform, tolerance, or production Score
Pack. A8 never calls A6 or publishes a card.

The fixture backend capability, fixture service, fixture outcome, A5 result,
and A6 fixture projection are all mechanically non-emission-capable. No caller
supplies an `emission_capable` Boolean. Beyond the safe `SeedPin` and
`ExecutionEnvironmentPin` already carried by the exact handle, the private
outcome carries no context, entropy/private root, raw official/master/derived
seed, role/domain/draw identity, prediction, reference, raw metric vector,
`ScoreInput`, checkpoint, model weight, exception text, stack trace, path,
runtime configuration or environment-variable value, credential, fee, card,
public diagnostic, transcript, receipt, evidence, signature, emission weight,
or eligibility override. A later production consumer must require positive
qualified provenance; a negative Boolean alone is not provenance.

---

## 6. Submission lifecycle

This section is sequencing shorthand. Current `carbon/fees/` code and
A7-R1--A7-R15 control exact identity, state, fee, retry, refund, cancellation,
and publication behavior; this section cannot authorize a second A8 lifecycle
or revive historical selectable defaults.

Every created submission record has a permanent **`SubmissionId`**. A malformed
or over-limit request may fail before a safe record/ID exists.

### 6.1 States

```text
RECEIVED → VALIDATED → QUEUED → RUNNING → SCORED → PUBLISHED
```

Exceptional:

```text
REJECTED          # A7 records prior A2/schema or identity failure, or trusted A3 denial
FAILED_STRATEGY   # train/numerical attributable to strategy
FAILED_INFRA      # Carbon/validator infrastructure
CANCELLED         # exact requester-bound A7 cancellation edges only
```

### 6.2 Fee & idempotency semantics

| Event | Current A7 fee/lifecycle behavior | Notes |
|-------|-----------------------------------|-------|
| Pre-record request/resource failure | No record, charge, or refund | Typed boundary failure, not an FSM state |
| `REJECTED` before queue | No charge and no refund | A7-R8/R11; no attempt or A5/A6 artifact |
| Infrastructure retry from `RUNNING` | No new charge, refund, or `RETRY_CREDIT` | A7-R12 preserves identity and alone applies attempt budget |
| Terminal `FAILED_INFRA` | No refund if never charged; otherwise fixed full remaining-balance `REFUND` | A7-R10/R12; never a physics zero or gate failure |
| `FAILED_STRATEGY` or completed score | Initial material-start charge remains | Fee never enters A5 or score/emission calculation |
| Exact open `(RequesterIdentity, ChallengeKey, StrategyHash)` duplicate | Return the existing `SubmissionId` | A7-R7; no new record, attempt, transition, charge, or fee event |
| A7 read used by A9 `get_submission_result` | A7 read-only; A9 consumes its injected query budget before lookup | Repeatable; no re-charge, queue/time estimate, or retry-after invention |
| Trusted infrastructure callback | Composition maps A8 `RETRYABLE`/`NON_RETRYABLE` to `retry_infrastructure`/`fail_infrastructure` | A7 checks the handle, applies budget/terminalization and prevents stale mutation; no partial science |

Fee amount is human-set; **fee is never a score input**.

---

## 7. Seeding (C6)

### 7.1 Seed domains (must not collide)

Separate namespaces for:

```text
mock | official_train | official_eval | official_stress | reference | dossier
```

Derivation formulas are human-confirmed; **domain separation is agent-enforced**.

### 7.2 Required tests

- Role split: train ≠ eval ≠ stress draws  
- Leakage: no official seed / draw id / reversible identifier in EvaluationCard, leaderboard, MCP, miner logs  
- Mock path cannot derive official domain seeds  

---

## 8. LIVE qualification manifest

Non-null thresholds are **necessary but not sufficient**.

LIVE requires a **qualification manifest** bound to the exact challenge version, with artifact hashes, e.g.:

```text
generator_envelope:     APPROVED  + content_hash
generator_validation:   PASSED    + dossier_hash
dossier_level_1:        APPROVED  + signoff
score_pack:             APPROVED  + pack_hash
mock_incompleteness:    APPROVED  + mock_pack_ids
train_backend:          QUALIFIED + env_digest
launch_bar:             SIGNED    + checklist_ref
mcp_readiness:          SIGNED    + Launch_Bar §2.4
```

Registry transition to `live` **fails** unless all required slots are present and hashes match the artifacts being activated. Agents implement the gate; humans produce the approvals.

---

## 9. Model Card vs EvaluationCard

| Record | Audience | Contents |
|--------|----------|----------|
| **A5 InternalResult** | Trusted private scoring/orchestration only | Exact A5 closed result fields; no context, seed, role/domain/draw identity, raw execution material, or broad diagnostic payload |
| **Future rich Model Card** | Ops, CI, later Landscape | Later evidence-owned allow-listed record; it is not the bounded A5 `InternalResult` or an A8 outcome |
| **EvaluationCard** | Submitting miner (MCP) | Current A6 positive allow-list: overall, coarse components, gate pass/fail and failure tags; bounded Wave-A `public_diagnostics` is exactly empty. Richer diagnostics require later ratification — **no** seeds, draw ids, fine margins or per-stress breakdowns |

Landscape (future) compounds **only** from Launch-Bar-grade Model Cards — never from free-path mock metrics.

---

## 10. Pack format (per challenge)

One challenge = one pack directory (name flexible; contents mandatory):

```text
packs/<challenge_id>/
  generator/          # code + version
  ranges/             # MOCK_RANGES + official envelope refs
  scoring/            # Score Pack YAML + hash
  dossier/            # Level-1 artifacts + signoff slots
  mock/               # mock pack ids + missing_stress_tags
  scaffolds/          # versioned mediocre baselines
  qualification.json  # manifest slots for LIVE
```

Challenge #2 should add a pack, not fork the subnet.

---

## 11. What “running Carbon” means (P0)

```text
Miner/agent → MCP free loop → optional submit
Validator  → hidden data → future qualified production TrainEval entry point → gates → Score Pack → cards
Network    → weights from lean scores only (testnet in P0)
Public     → leaderboard + budgeted EvaluationCard
Ops        → priors/scaffolds from verified cards (after Launch_Bar)
```

**P0 acceptance includes actual Bittensor testnet path** (scores → weights visible).  
**Agent Wave C deliverable** includes wiring; **P0 done** ≠ “testnet stub only.”

**Out of P0:** Landscape graph, specialist SKUs, automated cross-surface
conditional protected-realization leakage monitoring, commercial CAE, mainnet.

**PoC handoff:** `POC_Burgers_FNO.md` is historical lean-loop evidence without
MCP. Audit its primitives under KEEP → WRAP → REPAIR → REPLACE before any
Wave-C reuse. PoC green alone does not promote a TrainEval backend, prove
isolation, or establish scientific/production qualification.

**Layout:** Prefer mapping `poc/` + `Carbon_Logic/` over forced rename. Interfaces > directory cosmetics.

---

## 12. Wave acceptance checklists

### Wave A done when

- [ ] CI green on schema, seed/mock guards, scoring engine unit tests  
- [ ] Registry blocks LIVE without qualification manifest  
- [ ] Exact seven A9 tools respond; aliases and deferred light/list tools reject
- [ ] A9 `dry_validate` delegates to A2 and estimate remains non-executing/structural only
- [ ] A9 `submit` returns exact A7 lifecycle status; fee≠score and duplicate-open idempotence tested
- [ ] Result polling consumes query budget before A7 lookup and returns an exact A6 card only for `PUBLISHED`
- [ ] Card store: budgeted read allow-list tested; unauthorized hotkey denied  
- [ ] Fixture-official TrainEvalAPI **stub** only; cannot mark emission-ready
- [ ] Leakage tests for EvaluationCard/leaderboard fields  

### Wave B done when

- [ ] Physical task, population, SamplingPlan, candidate-output, assembly, and canonical-case identities exist with fixtures
- [ ] Generator, reference, measurement, and mock/practice interfaces are callable with fixtures
- [ ] ParameterCatalog + StrategyCompiler produce one exact resolved plan or typed rejection; no accepted parameter is ignored
- [ ] ResearchResourcePolicy exists with enforced fixture ceilings and keeps
      static inspection, calibrated forecast, future execution quote, and
      observed receipt nominally and epistemically separate
- [ ] Practice requests reject non-mock contexts/packs and cannot enter A5-A7 or any official/economic path
- [ ] Paired practice uses common fresh public cases and returns only policy-allowed aggregate evidence
- [ ] A semantically responsive fixture-official consumer uses the same exact
      resolved-plan identity as practice behind the unchanged v1 lifecycle,
      while fixture rights and provenance cannot create official or economic
      authority
- [ ] ResearchTask, ExperimentRecord, ResearchReceipt, and evidence-class boundaries exist
- [ ] Shared v2 nominal wire primitives are implemented once; the in-process
      `ResearchMcpService` exposes exactly the twelve ratified research
      operations, delegates each to its named domain owner, and neither exposes
      nor delegates v1 official operations
- [ ] Dossier + qualification manifest schemas exist and fixture evidence cannot satisfy LIVE
- [ ] PriorPack schema/store, TEST_ONLY staging/disclosure ledger, and static
      provider run on fixture evidence with redaction, lineage, atomic private
      approval-snapshot, history, and exact-ref retrieval tests; public
      publication remains unavailable
- [ ] Fixture prior evidence is mechanically limited to `TEST_ONLY`; it cannot activate bootstrap/learned guidance and no v2-backed projection enters the public v1 provider
- [ ] The preregistered autoresearch utility decision passes and the
      conditional-leakage decision finds no protected-realization shortcut on
      the fixture loop; failure or indeterminacy blocks Wave B closeout

### Wave C done when

- [ ] Real TrainEvalAPI behind nominally separate future qualified official and practice entry points
- [ ] Validator e2e: strategy → score → Model Card + EvaluationCard  
- [ ] MCP free then paid loop e2e  
- [ ] Gate fail → non-emitting  
- [ ] **Testnet:** lean scores → weights observable  
- [ ] FAILED_INFRA vs FAILED_STRATEGY distinguished  

### Wave D / LIVE done when

- [ ] Qualification manifest fully APPROVED/SIGNED for challenge version  
- [ ] Launch_Bar + MCP §2.4 green  
- [ ] Human thresholds/envelope/MOCK incompleteness/scaffold accepted  
- [ ] Registry `live` flip succeeds only with matching hashes  

---

## 13. Component notes (compact)

**C5 Engine:** Load pack by hash; hard gates fail-closed; forbidden inputs enforced in code. Weights (e.g. 45/30/25) are **Score Pack fields**, not engine constants.  
**C7:** Integrates the A7-owned FSM/current-handle operations with A8 execution;
A8 owns concrete runtime isolation limits and launch, while A7 owns safe pin
identity and lifecycle. Neither invents physics passes on infrastructure
failure.
**C9:** Exact bounded Wave-A control/disclosure per `Miner_MCP.md` and
A9-R1--A9-R15. Seven tools only; structural estimate never executes;
practice/research remains Wave B; submit/result remain exact A7/A6 delegation. The
Wave B contract candidate is `Miner_MCP_Wave_B_Research_Contract.md`; it keeps
the v1 service immutable and separates semantic compilation, prior alignment,
resource forecasting, quoting, and measured practice.
**C13:** Fee ledger with §6 semantics.  
**C15:** P0 = working testnet path; mainnet = human.  
**C17–C18:** Out of **Phase 0** SOW; preserve Model Card hooks in P0. Sequenced as Post-P0 Waves E–F (§18).  

---

## 14. Security / isolation (P0)

Strategy execution must enforce, at minimum:

- network deny-by-default  
- filesystem scratch-only  
- CPU/GPU/RAM and wall-clock limits  
- container/env pinning (`env_digest` on pin)  
- no access to validator secrets or official seed material  
- no path for hidden-data exfiltration via metrics/logs to miners  

Detail may live in Operations docs; **absence of isolation is a P0 blocker**, not a post-launch harden item.
The Wave-A in-process deterministic stub executes no miner code and is useful
only for bounded contract tests; it does not satisfy or claim these production
isolation controls.

---

## 15. Non-goals (Phase 0 / initial SOW)

These are **out of Phase 0 waves A–D**. They are not “never.” Post-P0 sequencing is §18.

- Landscape effect-candidate / symbolic stack → **Wave E** (`Landscape_Agent.md`)
- Specialist commercial SKU / product battery → **Wave F** (`Specialist_Bank.md`)  
- Customer bounds / sponsored-challenge GTM → **Wave G** (`Customer_Bounds_Specialist.md`)  
- Marketplace UI  
- cross-surface conditional protected-realization leakage monitoring and practice refresh service (track as P1 ops; §17)
- Full commercial CAE mesh pipeline  
- Hermes/Mira vendor plugins  
- Agent-invented LIVE physics thresholds (**permanent** non-goal)  
- Repo-wide rename as a deliverable  
- Major C8 investment unless subnet requires it  

---

## 16. Doctrine for coding agents

1. Build the stadium and the rules engine.  
2. Leave physics calibration to SciML.  
3. Fail closed when human inputs or qualification slots are missing.  
4. Prefer one vertical fixture loop over ten empty modules.  
5. Enforce cross-cutting invariants in tests.  
6. Never present placeholder thresholds as production truth.  
7. Never emit from stubs.  
8. When docs conflict, obey §0 domain ownership.  

---

## 17. Open opportunities (not blockers; track)

Items noticed in review that improve P0/P1 without changing architecture:

| Opportunity | Why | Phase |
|-------------|-----|-------|
| Free-path rate limits on remote practice tasks | Stop compute DoS of mock runner | P0 soft / P1 |
| Future authenticated binding execution quote | Miner UX; requires the Wave C transport, identity, quota, and economic contract; remains distinct from Wave B `forecast_resources` and A9 `StructuralEstimate` | P1 |
| Conditional leakage monitor and adaptive-agent campaign | Detect incremental protected-realization inference after controlling for evaluator-held shadow-case physics performance; account across practice, priors, cards, leaderboards, diagnostics, errors, timing, and versions | P1 |
| CI matrix: CPU-only unit vs GPU integration tags | Agents/CI without GPU | P0 |
| Hotkey↔submission binding tests | Fee and card authz | P0 |
| Pack content-addressed store | Pin verification | P1 |
| Well / external corpus hooks in dossier templates | Optional supporting evidence | P1 packs |
| Structured failure tag ontology shared MCP↔cards | Better avoid-atlas / priors | P0 schema, P1 richness |

Do **not** block Wave A on these.

---

## 18. Post-P0 waves (company + compounding product)

Phase 0 ends at **Wave D / LIVE** for at least one challenge and a working **testnet** path (Wave C).  
What follows is **not** required to claim P0 subnet readiness. It *is* required to claim Landscape intelligence, commercial specialists, or sponsored-challenge GTM.

**Hard rule:** Post-P0 waves **must not** weaken Phase 0 invariants (gates judge score; stubs never emit; no seed leakage; fee≠score). Landscape never overrides hard gates.

**Prerequisites before public product claims:**
- Wave C green (real TrainEval + validator e2e + testnet weights observable)
- Wave D green for the challenge versions that feed cards into Landscape
- `Launch_Bar.md` green before L0 “verified card” compounding or public prior-quality claims (`Landscape_Agent.md`)

```text
WAVE E — Landscape signals (C17)
  Card lake from Launch-Bar-grade Model Cards only
  L0: ingest + fixed-epoch coarsened prior snapshots
      (eligibility, suppression, lag, no full champion recipes)
  L1: failure atlas / symbolic hooks
  L2: effect-candidate core + specialist *pipeline hooks* (not full SKU)
  Ports: A search (miners) · B eval (validators only) · C economy proposals · D product hooks
  Authority: Landscape_Agent.md
  Human: coarsen policy, publish cadence, what may leave the building

WAVE F — Specialist bank (C18)
  Effect-synthesized recipes from Landscape → controlled retrain
  Product battery (verification gauntlet) before any commercial SKU
  Dual egress: coarsened public search path vs closed product path
  No teacher-checkpoint distillation as the product
  Authority: Specialist_Bank.md
  Human: which regimes to productize; battery pass/fail signoff

WAVE G — Customer bounds & sponsored challenges (GTM)
  Bounds intake: requirements / constraints / envelope (default: no customer proprietary trajectories)
  Match Landscape evidence → fulfill off-subnet when sufficient
  Sponsored / open / IP-licensed / private challenge tiers when network search is needed
  Customer-side adapt kit voids prior cert until re-qualification
  Authority: Customer_Bounds_Specialist.md, Use_Cases_by_Phase.md
  Human: pricing, contracts, which challenges to host
```

### 18.1 Post-P0 acceptance (directional)

| Wave | Done when (summary) |
|------|---------------------|
| **E** | Card lake + immutable coarsened prior publish path exist; gates still sole score authority; Launch_Bar respected |
| **F** | At least one regime can run recipe → retrain → **product battery** → closed artifact (fixture or real) |
| **G** | Bounds schema + fulfillment rules documented and demoed; one trial path without requiring customer secret data |

### 18.2 What stays human

- LIVE thresholds and dossier science (still Wave D discipline per challenge)
- Mainnet parameters and emission economics
- Commercial pricing, sponsorship terms, IP licenses
- Any claim that a specialist is “system certified” for a customer plant

### 18.3 Explicit non-coupling

| Do not | Why |
|--------|-----|
| Feed free-path mock metrics into Landscape as verified truth | Corrupts Port D |
| Sell eval outcomes or emission weight | Protocol integrity |
| Ship specialist without product battery | `Specialist_Bank.md` doctrine |
| Block Phase 0 on Waves E–G | P0 is subnet readiness, not OpCo scale |

---

*Build_Out v1.4 — Phase 0 waves A–D + Post-P0 waves E–G. **Sequencing authority only.** Domain ownership: SPEC (architecture), Scoring (mathematics), Trustless/Data (seeds/exam identity), Miner_MCP (miner surface), Launch_Bar (stop-ships), Specialist_Bank (productization). Post-P0 product docs as cited in §18.*
