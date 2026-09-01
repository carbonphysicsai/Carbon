# Carbon Master Open Design Questions

**Status:** OWNER-REVIEW QUEUE — canonical compilation of unresolved design questions on `main`  
**Purpose:** provide one authoritative, de-duplicated register of unresolved scientific, protocol, security, governance, treasury, network, agentic, product, legal, commercial, investor, and publication decisions.  
**Rule:** every open question must have a recommended disposition or a recommended evidence-generating decision method. Recommendations are not ratified decisions unless explicitly moved into the relevant decision/canon/specification document.  
**Relationship:** this file compiles and supersedes the *queueing function* of `docs/context/Open_Questions.md`, `Business/Design_Questions.md`, and `docs/context/REVIEW_THESE_PRELIMINARY_DECISIONS_DEFENSIBILITY.md`. Those files remain domain history/deeper context and should point here for canonical open status.

---

# 0. Decision discipline

For each question, Carbon should distinguish:

```text
RECOMMENDATION
what the architecture currently favors
        !=
RATIFIED DECISION
human owner has accepted it
        !=
IMPLEMENTATION
code/process exists
        !=
QUALIFICATION / EVIDENCE
it has survived the required proof
```

Where a numerical, legal, security, or market answer cannot responsibly be invented, the architect recommendation is the **method for deriving the answer**, including acceptance criteria and stop conditions.

Status values:

- `OPEN` — decision not yet ratified;
- `EVIDENCE_REQUIRED` — architecture is directionally decided but the value/policy must be derived empirically;
- `COUNSEL_REQUIRED` — business recommendation exists but legal/tax/regulatory language requires counsel;
- `SECURITY_REVIEW_REQUIRED` — design direction exists but adversarial qualification is required;
- `READY_TO_RATIFY` — recommendation is mature enough for owner approval, subject only to explicit sign-off.

---

# A. First LIVE scientific Challenge

## MQ-001 — First authoritative Challenge identity

**Source aliases:** OQ-001, OQ-014, DQ-001.  
**Question:** What should Carbon use as the first authoritative LIVE scientific Challenge?

**Architect recommendation:** ratify **1D periodic viscous Burgers with fixed viscosity `ν = 5×10⁻³`** as the first authoritative Challenge, using the repaired causal-input architecture `(u0) -> u(T)` for this fixed-ν version. Do not vary viscosity until `ν` is an explicit candidate input. Keep forcing absent in v1.

**Rationale:** this removes the historical underdetermination defect, gives a nonlinear dissipative PDE with steep-gradient formation, supports strong analytic/semi-analytic truth, and keeps geometry/turbulence/model-form uncertainty out of the first trust proof.

**Do not:** broaden the first LIVE Challenge to variable-ν, multidimensional Burgers, turbulence, moving geometry, or multiphysics for narrative breadth.

**Owner:** Physics/SciML + protocol.  
**Proof required:** complete Validation Dossier and Launch Bar.  
**Status:** `READY_TO_RATIFY`.

---

## MQ-002 — Target population and SamplingPlan

**Source aliases:** OQ-001, DQ-002.  
**Question:** What exact population is Carbon making claims about, and how is finite evidence drawn from it?

**Architect recommendation:** register separately:

```text
TargetPopulation P(x)
SamplingPlan / proposal Q(x)
EvaluationWeighting w(x)
```

For Burgers v1, define a bounded family of smooth periodic initial conditions with explicit amplitude/spectral-complexity bounds and declared interior/edge/stress strata. The target population belongs to the scientific task. The generator implements a qualified realization; it does not define the population by accident.

Use stratified sampling so rare but decision-relevant in-envelope regimes receive enough finite evidence without falsely representing their natural prevalence. Any importance weighting must be explicit and prospective.

**Do not:** treat an envelope as a probability distribution; equate sampling frequency with target prevalence; or let `Q(x)` silently become `w(x)`.

**Owner:** Physics/SciML + statistics.  
**Proof required:** distribution-conformance tests, coverage evidence, finite-sample sufficiency study.  
**Status:** `EVIDENCE_REQUIRED`.

---

## MQ-003 — Generator Validation Dossier

**Source aliases:** OQ-002.  
**Question:** What evidence earns the right to use the first generator as an exam generator?

**Architect recommendation:** require the full D1–D12 Validation Dossier: physical-system fidelity, claim/envelope, target population, SamplingPlan, implementation, distribution conformance, truth, representation, measurement, statistical sufficiency, secrecy/role separation, and censoring/limitations.

For Burgers, include audit seeds spanning interior and hard strata,
coverage/degeneracy tests, generator-to-primary-reference discrepancy,
independent witness comparisons, numerical floors, exact artifact/environment
identity, and documented failure regions.

**Do not:** approve a generator because it is deterministic, because the code runs, or because one convergence plot looks acceptable.

**Owner:** Physics/SciML.  
**Proof required:** signed dossier for exact generator identity.  
**Status:** `EVIDENCE_REQUIRED`.

---

## MQ-004 — Reference hierarchy / ReferencePolicy

**Source aliases:** DQ-003, OQ-002.  
**Question:** What is the authoritative answer key and what role does an independent numerical solver play?

**Architect recommendation:** for fixed-ν Burgers, use a qualified periodic
**Cole–Hopf solution as the primary reference**, a separately implemented
high-resolution conservative numerical solver as a **corroborating witness**,
and treat the current/derived production generator as a **generator under
test**, never as truth by definition.

```text
PRIMARY: Cole–Hopf
      ↓ cross-check
SECONDARY: independent qualified numerical witness
      ↓ qualify
GENERATOR UNDER TEST
```

When references disagree beyond qualified uncertainty, the Challenge is
blocked/contested; do not average incompatible references into a convenient
answer.

**Owner:** Physics/SciML.  
**Proof required:** primary implementation tests, independent witness convergence study, disagreement policy.  
**Status:** `EVIDENCE_REQUIRED`.

---

## MQ-005 — MeasurementContracts and mandatory admissibility

**Source aliases:** OQ-003.  
**Question:** What exactly is measured, how, and which failures are disqualifying?

**Architect recommendation:** make measurement identity explicit. Burgers v1 should include at least:

- finite output;
- periodic mean/mass conservation within qualified tolerance;
- energy non-increase consistent with viscous unforced Burgers;
- maximum-principle consistency where applicable to the registered representation;
- field error versus Cole–Hopf truth;
- stress-stratum field error.

The historical final-state spatial-balance proxy remains diagnostic only; it is not a full PDE residual because `d_t(u)` is absent.

Mandatory gates should represent defensible scientific admissibility conditions. Soft field/stress error ranks only after admissibility.

**Owner:** Physics/SciML + scoring protocol.  
**Proof required:** measurement qualification and numerical uncertainty floors.  
**Status:** `EVIDENCE_REQUIRED`.

---

## MQ-006 — First LIVE Score Pack

**Source aliases:** OQ-003.  
**Question:** Which evidence is eligible, how is it used, and how is the Challenge ranking produced?

**Architect recommendation:** treat the Score Pack as a versioned **Evidence Use Contract**. Retain the current P0 0.45/0.30/0.25 physics/robustness/accuracy baseline only as a default design prior until the Burgers dossier supports or modifies it. Thresholds, strata, uncertainty treatment, estimands, measurement roles, transforms, and aggregation must be pack-owned and prospective.

A5 remains an execution engine; it must not parse `PhysicalSystemSpec` to invent thresholds or weights.

**Owner:** Physics + protocol.  
**Proof required:** dossier-derived values, sensitivity analysis, rank-stability study.  
**Status:** `EVIDENCE_REQUIRED`.

---

## MQ-007 — Scientific resolution and finite-evidence sufficiency

**Source aliases:** DQ-004, OQ-004.  
**Question:** How close can two candidates be before Carbon must say it cannot distinguish them?

**Architect recommendation:** establish a **minimum resolvable improvement**
from a reconstruction × whole-case/trajectory design stratified by the
registered stress plan. Construct the operative paired interval end to end
across separately realized, producer-independent incumbent and challenger
reconstruction replicates, common whole cases or trajectories, joint
reference-error realizations, representation, and execution roles. Registered
pairing or common random numbers are allowed, but shared dependencies remain
modeled. Diagnose reconstruction-by-case interaction explicitly. Component
uncertainty tables do not establish independence. The Dossier qualifies the
procedure and its applicability test; the exact incumbent-challenger evidence
must also satisfy that test before quadrature is permitted. Unidentified
material dependence widens the interval or returns `INDETERMINATE`.

Preregister a `ReconstructionEvidencePolicy` that separates typed protocol and
resource admission, the Challenge-registered complete base reconstruction
evidence required for every scientifically scored or nominated candidate, and
repeat promotion evidence. A frozen reconstructed artifact may be reused
across its authorized evaluation cases. Before complete base evidence exists,
quality forecasts, partial builds, proxies, and screens affect scheduling only;
an uncompleted path returns typed `EVIDENCE_DEFERRED` and no scientific result.
After base evidence, official evidence may stop sequentially only at qualified
decision boundaries. A heuristic futility stop also returns only
`EVIDENCE_DEFERRED` and needs a calibrated false-elimination bound plus random
audits. If the registered budget is exhausted before the comparison resolves,
return `INDETERMINATE` with reason `INSUFFICIENT_EVIDENCE`.

Use more evidence where economically justified, but do not concentrate payout resolution more sharply than scientific resolution.

**Owner:** Statistics + Physics/SciML + protocol.  
**Proof required:** null/coverage/power and rank-stability simulation; empirical
reconstruction × whole-case/trajectory evidence stratified by stress regime;
exact-pair applicability diagnostics; and, when a
screen or sequential rule is used, false-elimination, audit, cost, latency, and
validator-capacity evidence.
**Status:** `EVIDENCE_REQUIRED`.

---

## MQ-008 — Backend reproducibility profile

**Source aliases:** OQ-004, OQ-012.  
**Question:** What hardware/software cohort and tolerances are qualified for authoritative evaluation?

**Architect recommendation:** start with a narrow homogeneous backend cohort. Separate R0 exact artifacts, R1 numerical reproducibility, and R2 decision reproducibility. Exact identities/seeds/configs must match exactly; numerical tolerance is measured; gate/rank decisions must remain stable outside the contested band.

Add hardware profiles only after each independently passes qualification. Never broaden hardware support by loosening scientific decision tolerances.

**Owner:** SciML + infrastructure.  
**Proof required:** repeated-run/soak/OOM/node-loss/cross-profile study.  
**Status:** `EVIDENCE_REQUIRED`.

---

# B. Frontier, portfolio, and scientific finality

## MQ-009 — LeaderReplacementPolicy v1

**Source aliases:** DQ-005.  
**Question:** What exact evidence creates a `FrontierAdvanceEvent`?

**Architect recommendation:** use two-stage promotion:

1. ordinary Challenge scoring nominates contenders;
2. incumbent and shortlisted contenders are reconstructed/evaluated on the **same fresh common promotion exam**;
3. apply a registered superiority test using the Challenge's resolution policy;
4. output `SUPERIOR`, `NOT_SUPERIOR`, or `INDETERMINATE`.

No event for a mere floating-point lead, incompatible evidence, unresolved ties, or an indeterminate comparison. Equivalent contenders remain unresolved in v1. Maximum one paid frontier event per Challenge settlement window is the preferred first policy.

**Owner:** Protocol + statistics + physics.  
**Proof required:** simulation under noise/order/timing/seed variation.  
**Status:** `READY_TO_RATIFY` structurally; numerical resolution remains evidence-derived.

---

## MQ-010 — Frontier baseline and self-improvement

**Source aliases:** DQ-005.  
**Question:** How is the initial frontier defined and can the same miner beat itself?

**Architect recommendation:** every LIVE Challenge must register a `FrontierBaseline` before rewards. A miner may beat its own incumbent if the new submission represents a genuinely new registered method identity and independently clears the same frontier-promotion rule. Incumbency earns no ongoing performance rent.

**Owner:** Protocol/economics.  
**Proof required:** identity/replay/progress-splitting tests.  
**Status:** `READY_TO_RATIFY`.

---

## MQ-011 — Multi-Challenge economic allocation

**Source aliases:** defensibility portfolio concerns.  
**Question:** How do 4–7 Challenges coexist without pretending scores are comparable?

**Architect recommendation:** use a prospectively frozen `ChallengeSetEpoch` with active Challenge membership and equal **notional** slot `1/N` for v1. Scores remain Challenge-local and non-comparable. Unused/withheld slots do not silently redistribute to other Challenges.

The initial C2 direct-weight testnet defaults to one Challenge. Before multiple
Challenges share direct testnet allocation, Carbon must either already use
treasury settlement or register fixed `TESTNET_ONLY` per-Challenge slices and
allocate each slice only to that Challenge's active test winner. Raw score
magnitude never determines cross-Challenge allocation. Production allocation
remains owned by `ChallengeSetEpoch` plus treasury/economic policy.

Do not confuse equal opportunity with equal computational cost or equal scientific difficulty.

**Owner:** Protocol/economics.  
**Proof required:** accounting simulation and chain/treasury mapping qualification.  
**Status:** `READY_TO_RATIFY`.

---

## MQ-012 — Scientific disputes and finality

**Source aliases:** DQ-013.  
**Question:** What is appealable, and when does a scientific result become final?

**Architect recommendation:** separate three dispute classes:

- **scientific evidence defect** — challenge/reference/measurement/reproducibility issue; may invalidate or quarantine the affected event prospectively/according to explicit incident rules;
- **operational incident** — infrastructure/availability/logistics; may trigger retry without rewriting science;
- **settlement dispute** — custody/payment execution; cannot recreate or erase scientific entitlement.

Allow appeals only on enumerated objective grounds within a finite evidence-preservation window. Never permit a governance vote to simply override physics because a result is unpopular.

**Owner:** Protocol + governance + legal.  
**Proof required:** written incident/appeal procedure and replay exercises.  
**Status:** `COUNSEL_REQUIRED` for legal details; architecture ready.

---

# C. Randomness, validator agreement, disclosure, and execution security

## MQ-013 — Production seed timing and randomness beacon

**Source aliases:** OQ-005, OQ-006, DQ-006.  
**Question:** How is official randomness unknowable at commitment time yet reproducible later?

**Architect recommendation:** bind immutable submission at block `h`, derive official randomness from a future finalized chain event after a configured delay, and strengthen production randomness with an independently operated verifiable distributed beacon where feasible:

```text
beacon = H(finalized_chain_randomness || external_verifiable_beacon)
```

Derive role-separated train/eval/stress seeds from one domain-separated exam identity. Fallback behavior must be registered in advance and fail closed rather than silently switching semantics.

The exact delay is determined from measured Subtensor finality/reorg behavior.

**Owner:** Protocol/security.  
**Proof required:** manipulation/reorg/withholding threat analysis.  
**Status:** `SECURITY_REVIEW_REQUIRED`.

---

## MQ-014 — Validator disagreement policy

**Source aliases:** OQ-007, DQ-007.  
**Question:** What happens when honest-looking validators disagree beyond qualified tolerance?

**Architect recommendation:** invalid/infra-failed attestations are excluded; valid attestations must reference the same exact exam identity. If a qualified quorum agrees within R1/R2 tolerance, aggregate using the registered robust rule. If disagreement exceeds tolerance, mark result `CONTESTED / NON-SETTLING`, rerun on qualified infrastructure; persistent disagreement quarantines the relevant Challenge/backend combination.

Median aggregation is not a substitute for an under-specified experiment.

**Owner:** Protocol + operations + statistics.  
**Proof required:** Byzantine/outlier/reproducibility simulations.  
**Status:** `EVIDENCE_REQUIRED`.

---

## MQ-015 — P0 execution capability / threat model

**Source aliases:** OQ-008, DQ-008.  
**Question:** What may a miner control in the first real backend?

**Architect recommendation:** P0 remains **declarative and bounded**. Accept only versioned `TrainingStrategy` objects interpreted through a Challenge-bound `ParameterCatalog`, `CandidateAssemblyContract`, and deterministic `StrategyCompiler`. The compiler produces one canonical `ResolvedConstructionPlan` or one typed rejection. It rejects unknown, unused, incompatible, coerced, silently defaulted, silently clamped, and unsupported fields.

Carbon may register a fixed hybrid backbone or learned-component slot when the
Challenge owns the outer assembly workflow. It may expose a closed set of
Challenge-bounded training sampling, curriculum, and augmentation levers. The
compiler materializes those selections into one canonical
`ResolvedTrainingSamplingPolicy`, denoted `R_strategy`, plus its
content-addressed `TrainingSamplingPolicyRef` under a Challenge-owned
training-support contract, while validators derive the actual train seeds and
draws. Where scientifically applicable, the closed catalog may also expose
versioned, exact implementations of optional structure-preserving components
(for example conservative or monotone operators, positive-semidefinite
dissipation, divergence-free projections, equivariant layers, or
Hamiltonian/dissipative structures). Each entry binds its mathematical
assumptions, applicability envelope, implementation identity, interfaces, and
falsification tests. Selecting or unit-testing such a component is never
scientific gate evidence and never enters score; only registered measurements
of the reconstructed candidate on protected cases can do that. This does not
authorize participant-defined composition graphs. In Wave B, forbid arbitrary
imports, Python/JAX/PyTorch code, subprocesses, custom
executables, filesystem paths or URIs, network access, arbitrary
dependencies/deserialization, raw or custom dataset uploads, miner-selected
seeds, official target population `P`, official proposal/SamplingPlan `Q`,
evidence weights `w`, evaluation/stress/reference controls, and scorer/gate
overrides.

Practice reconstruction and official construction must use the same semantic compiler identity. Real execution runs in a locked environment with no network, scratch-only filesystem, CPU/GPU/RAM/VRAM/wall-clock/step/output limits, immutable image/dependency identity, process isolation, and redacted logs.

Arbitrary participant code belongs only to a later `ConstructionProgram` threat model.

**Owner:** Security + protocol + Physics/SciML.
**Proof required:** compiler-escape and catalog-confusion tests, malicious-Strategy tests, reconstruction-receipt tests, structural-component applicability and anti-self-certification tests, formal threat model, sandbox review, and abuse tests.
**Status:** `SECURITY_REVIEW_REQUIRED`.

---

## MQ-016 — Disclosure budget / hidden-exam reconstruction

**Source aliases:** OQ-009, DQ-009.  
**Question:** How much feedback can miners receive without turning it into an oracle?

**Architect recommendation:** maximize useful physics feedback subject to a registered Evaluation Information Policy. Low raw correlation between practice and official performance is not a safety objective because a genuine physics improvement should transfer. The prohibited leak is material incremental ability to infer protected case realizations, hidden stress composition, exact margins, or unresolved near-frontier ordering after controlling for performance on evaluator-held shadow cases sampled from the declared public distribution and unavailable to the attacking agent.

Expose only budgeted coarse outcome information: overall score, coarse component/band information, gate pass/fail, controlled tags, safe diagnostics, and version identities. Withhold seeds, draw IDs, per-draw metrics, exact margins, exact worst-case samples, fine stress breakdowns, references, and reconstruction-sensitive internals.

The policy accounts jointly for EvaluationCards, leaderboards, prior versions, practice results, diagnostics, errors, timing, queue behavior, resource estimates, Strategy lineages, related requesters, and coordinated batches. Wave B tests an injected fixture-only disclosure-subject resolver; live cross-requester linkage requires later authentication plus privacy/legal, false-merge, appeal, and enforcement decisions. Build adaptive red-team agents for near-duplicate search, Sybil splitting, timing inference, prior differencing/poisoning, hidden-mixture inference, and cross-surface composition. Carbon owns any high-score/low-physics or protected-realization shortcut as an exam vulnerability.

**Owner:** Security + agent engineering.  
**Proof required:** prospective agent attack campaign reporting both search utility and conditional hidden-exam leakage; production ceiling approved by human security owners.
**Status:** `SECURITY_REVIEW_REQUIRED`.

---

## MQ-017 — Submission rate limits and exam fee

**Source aliases:** OQ-010, OQ-011.  
**Question:** How should paid official exams be priced and rate-limited?

**Architect recommendation:** testnet begins zero/nominal while measuring actual validator cost. Production fee formula should be transparent expected resource cost plus anti-spam/congestion margin, versioned and independent of score. Use per-hotkey active-exam limits plus rolling quotas and emergency backpressure. Duplicate open identity returns the same submission rather than charging twice.

Separate exact static resource inspection, a non-binding calibrated resource forecast, a binding execution quote, and the final observed resource receipt. Forecasts report model identity, calibration window, support status, hardware/resource scope, and uncertainty; unsupported Strategies return `UNRESOLVED`. Official quotes disclose no protected case count, stress mixture, strong-anchor frequency, or evaluator topology. Practice and official execution use separate quota and pricing policies.

Do not set permanent token amounts/quotas without telemetry. Infrastructure failure gets the registered refund/retry treatment.

**Owner:** Ops + economics.  
**Proof required:** load/queue/cost/abuse telemetry.  
**Status:** `EVIDENCE_REQUIRED`.

---

# D. Governance and treasury

## MQ-018 — Governance authority matrix

**Source aliases:** OQ-013, DQ-012.  
**Question:** Who can approve or change each class of decision?

**Architect recommendation:** define named roles and keys at minimum for Physics/SciML, Protocol, Security, Infrastructure, Product/Qualification, Treasury/Custody, Commercial, and Launch. Require separation of duties for production actions where team size permits; where one person temporarily holds multiple roles, disclose it explicitly.

The matrix must also name the science, security, protocol, and rights approvers for activating or withdrawing any external miner-visible PriorPack, including curated bootstrap guidance. A publisher process or coding agent cannot approve its own release.

No coding agent is an approver. No treasury signer can create scientific merit. No commercial approver can weaken the registered exam.

**Owner:** Founder/team governance.  
**Proof required:** signed authority matrix + key inventory + rotation/revocation process.  
**Status:** `READY_TO_RATIFY` structurally.

---

## MQ-019 — Treasury custody architecture

**Source aliases:** DQ-010.  
**Question:** What holds network-side funds and what authorizes release?

**Ratified structural disposition:** mainnet network allocation routes first to
a registered `TreasuryReceiverSet`, then through a separately governed
vault/custody boundary and immutable accrual ledger. Release settles only
exact registered `SettlementObligation`s bound to `FrontierAdvanceEvent`
identity. Treasury and scientific entitlement stay separate.

The exact receiver count, controller/vault split, on-chain/off-chain custody
topology, threshold/multisig scheme, signers, recovery powers, and key design
remain human/security/economic-owner decisions; the former “treasury neuron”
shorthand is not a selected custody implementation.

**Owner:** Protocol/economics/security.  
**Proof required:** localnet/testnet custody, duplicate-prevention, accounting, key-compromise exercises.  
**Status:** receiver/obligation direction `RATIFIED_ROADMAP`; exact custody
`SECURITY_REVIEW_REQUIRED`.

---

## MQ-020 — Treasury outage, recovery, censorship, and duplicate settlement

**Source aliases:** DQ-011.  
**Question:** What happens when settlement cannot or should not immediately execute?

**Architect recommendation:** scientific event state is append-only and survives treasury outage. Settlement obligations have stable unique IDs, exactly-once release semantics, and observable states such as pending/blocked/settled. An unavailable signer cannot erase entitlement; an admin refusal must be observable and governed by recovery/escalation policy. Duplicate payout attempts must fail mechanically.

Emergency pause may halt custody release, not rewrite a finalized scientific event.

**Owner:** Treasury governance + security + protocol.  
**Proof required:** fault injection, replay/double-pay tests, key-loss/runbook exercise.  
**Status:** `SECURITY_REVIEW_REQUIRED`.

---

# E. Network economics and Alpha

## MQ-021 — Network-versus-centralized falsification experiment

**Source aliases:** DQ-014.  
**Question:** What evidence would justify saying Bittensor improves Carbon's R&D economics?

**Architect recommendation:** run matched-budget comparisons where centralized search and network search receive the same Challenge definition, evidence rules, compute/resource budget accounting, and time window. Measure:

- useful unique hypotheses per dollar;
- method diversity;
- best verified frontier performance;
- time to verified advance;
- validator/orchestration overhead;
- participation concentration and robustness.

Repeat across multiple Challenges before generalizing. If centralized search wins for a workload, use that evidence honestly.

**Owner:** Research + economics.  
**Proof required:** prospective controlled experiments.  
**Status:** `EVIDENCE_REQUIRED`.

---

## MQ-022 — First direct Alpha/network utility

**Source aliases:** BQ-028, DQ-015.  
**Question:** What should create the first defensible commercial demand for network activity?

**Architect recommendation:** first utility should be **commercially valuable network-backed Sponsored Discovery / Frontier Market work**, including sponsor-funded frontier rewards. Keep enterprise UX fiat-first; OpCo translates eligible customer programs into network work where qualified.

Do not begin with forced customer Alpha purchases, buyback/burn, revenue share, or speculative token choreography. Additional Alpha-native service utility can be considered after legal/economic review and demonstrated product benefit.

**Owner:** Business + economics + legal.  
**Proof required:** first commercial network-backed program and NetworkUtilityConversion metrics.  
**Status:** `EVIDENCE_REQUIRED`.

---

## MQ-023 — Workload migration to network

**Source aliases:** BQ-026.  
**Question:** When does a commercial workload become `NETWORK_ELIGIBLE` or `NETWORK_REQUIRED`?

**Architect recommendation:** require objective gates across scientific parity, privacy/security, cost, latency, participant liquidity, operational reliability, and customer rights. Public Sponsored Discovery/Frontier Market can become network-required first. Evidence Audits and private programs may remain off-chain until the network path is demonstrably better and qualified.

**Owner:** Business + protocol + security.  
**Proof required:** per-product qualification checklist and economics comparison.  
**Status:** `EVIDENCE_REQUIRED`.

---

# F. Agentic construction and Landscape

## MQ-024 — Construction search expansion

**Source aliases:** agentic-plan open direction.  
**Question:** How does Carbon widen beyond `TrainingStrategy` without surrendering evaluator control?

**Architect recommendation:** evolve through explicit typed interfaces:

```text
TrainingStrategy
+ ParameterCatalog
+ CandidateAssemblyContract
→ ResolvedConstructionPlan
→ ReconstructionProtocol
```

Future search-type expansion is separate:

```text
TrainingStrategy
→ ModelConstructionStrategy
→ ConstructionProgram (later)
```

Wave B remains on `TrainingStrategy`. It may support registered hybrid
backbones or learned-component slots only through a Challenge-owned assembly
contract. It may select from cataloged levers, including optional versioned
structure-preserving components where their assumptions and applicability are
registered, that the compiler resolves into one canonical construction plan.
Structural-component labels do not certify physics or satisfy gates; hidden
output evidence remains authoritative. Training-data levers resolve into one
canonical `R_strategy` object and its `TrainingSamplingPolicyRef`, with
validator-derived train draws. It does not authorize raw/custom datasets,
participant-defined construction graphs, arbitrary code, or official
evaluation controls. Expand hypothesis freedom incrementally; every broader
capability gets a new threat model and qualification identity. The construction
producer never controls the official measurement/evaluation environment.

**Owner:** Architecture + security + scientific protocol.  
**Proof required:** wave-specific threat models and reconstruction evidence.  
**Status:** `READY_TO_RATIFY` as long-term direction.

---

## MQ-025 — Landscape leakage / Goodhart policy

**Source aliases:** DQ-027.  
**Question:** What can Landscape expose without teaching miners the hidden exam?

**Architect recommendation:** Landscape remains a hypothesis/routing layer, never scientific authority. Publish immutable, Challenge-bound prior snapshots that every miner receives on equal terms. Personalization happens miner-side. The provider serves approved stored bytes and never queries private evidence during a miner request.

Each prior item references one public executable lever and a public estimand that fixes the baseline/comparison, population/scope, direction, aggregation functional, independence/resampling unit, and uncertainty method. It also declares exact intervention anchors, public applicability, evidence origin, epistemic status, support, uncertainty, stability, replication, limitations, cutoff, and aggregate-only provenance. Publish negative, null, mixed, and `INSUFFICIENT_EVIDENCE` findings as well as positive guidance. Do not echo raw Strategy fields, unique candidate information, exact support counts/effect sizes, protected contexts, hidden frequencies, current-frontier recipes, or private IP.

Use deterministic aggregation, lineage/contributor influence caps, coarsening,
joint-cell suppression, lag, fixed release epochs, and a persistent atomic
cumulative-disclosure ledger. Add randomized or differential-privacy noise
only under a formal privacy budget with measured utility. For any external
activation, require cutoff plus minimum lag; evidence generated during an
active window cannot influence the prior consumed in that window.

Wave B may implement private `TEST_ONLY` staging with an exact-hash delegated
structural authorization receipt carrying `NOT_UTILITY_QUALIFIED`, plus
reviewed public-publication schemas and negative tests. That receipt authorizes
only exact-byte private fixture staging; it is not science, statistics,
security, rights, utility, or publication acceptance. The frozen TEST_ONLY
bytes then enter the preregistered B-E4 utility/leakage gauntlet; the staging
receipt is not a public publication receipt or utility claim. Carbon-derived learned public priors
require Launch-Bar-grade source evidence, rights, poisoning resistance,
prospective utility evidence, and security approval. Any output that provides
protected-realization advantage beyond transferable physics is a leakage
candidate and must be coarsened, delayed, withdrawn, or prospectively
versioned.

**Owner:** Landscape + security + protocol.  
**Proof required:** prospective utility plus leakage/Goodhart, membership, version-differencing, poisoning, Sybil/lineage, and decontamination tests.
**Status:** `SECURITY_REVIEW_REQUIRED` before score-adjacent use.

---

## MQ-026 — Physics Intelligence proof standard

**Source aliases:** DQ-026.  
**Question:** When can Carbon call accumulated evidence “Physics Intelligence” rather than descriptive analysis?

**Architect recommendation:** require a prospective held-out decision task. Example: predict which construction intervention/method to try for a new registered Challenge/regime, or allocate a finite experiment budget. Compare against reasonable baselines such as no-memory, recency/frequency heuristics, nearest-task retrieval, and domain-expert/manual baseline where feasible.

The first prior-specific test should compare matched-budget research agents using no prior, a generic static prior, the Wave A directive prior, and the proposed evidence-rich PriorPack. Use a semantically responsive toy physics fixture in Wave B and later a held-out Challenge version or public regime. Measure best held-out physics result per compute, attempts to first candidate passing declared non-authoritative practice checks, semantic compilation/reconstruction success, invalid-run rate, transfer to evaluator-held shadow cases, and diversity of tested interventions. Evaluate protected-realization leakage separately under MQ-016.

Claim Physics Intelligence only when it improves prospective scientific/engineering decisions under decontaminated evaluation and survives replication. Retrospective explanatory narratives alone do not qualify.

**Owner:** Research + product science.  
**Proof required:** prospective trials with preregistered metrics.  
**Status:** `EVIDENCE_REQUIRED`.

---

# G. Product qualification and lifecycle

## MQ-027 — Product Qualification Pack v1

**Source aliases:** OQ-015, BQ-008.  
**Question:** How should Carbon qualify an exact candidate for a commercial job?

**Architect recommendation:** sell qualification as an exact identity-bound package, not a universal certificate. Product qualification should bind artifact hash, reconstruction/deployment environment, operating envelope, evidence battery, limitations, answerability/escalation, and requalification triggers. Base commercial structure: qualification program fee + evidence/compute + lifecycle attachment.

Qualification thresholds are job/pack-owned and derived from the customer's intended use and relevant scientific evidence; never inherit generic P0 miner-ranking thresholds automatically.

**Owner:** Product + Physics/SciML + protocol.  
**Proof required:** first real Product Qualification Pack for a concrete SKU/use.  
**Status:** `EVIDENCE_REQUIRED`.

---

## MQ-028 — Qualification vs certification / legal claim language

**Source aliases:** DQ-020.  
**Question:** What may Carbon legally and technically say a Qualification means?

**Architect recommendation:** preferred public language: **bounded evidence-backed qualification for an exact artifact, operating envelope, and intended context of use**. Explicitly state that Carbon does not by itself confer universal certification, regulatory approval, warranty of safety, or replace the customer's governing engineering authority.

Use terms such as `QUALIFIED_FOR_STATED_CLAIM`, `QUALIFIED_WITH_LIMITATIONS`, `NOT_QUALIFIED`, and exact evidence identities; avoid “certified safe” unless a later formal certification regime legally supports it.

**Owner:** Product + counsel + technical authority.  
**Proof required:** counsel-reviewed standard language/MSA/SOW.  
**Status:** `COUNSEL_REQUIRED`.

---

## MQ-029 — Lifecycle and requalification triggers

**Source aliases:** DQ-024.  
**Question:** What changes invalidate or reopen qualification?

**Architect recommendation:** classify changes as `NO_MATERIAL_CHANGE`, `LIMITED_REEVIDENCE`, or `NEW_QUALIFICATION_IDENTITY`. A new identity is required for material changes to model weights/source/recipe, construction method, training/data provenance, runtime numerical behavior, truth/reference semantics, operating envelope, coupling/system composition, answerability policy, or adaptation/fine-tuning.

Hardware/runtime changes may use limited re-evidence only if previously qualified equivalence bounds apply. Adaptation should default to a new qualification identity.

**Owner:** Product + physics + infrastructure.  
**Proof required:** change-control policy tested on representative updates.  
**Status:** `READY_TO_RATIFY` structurally.

---

## MQ-030 — Multiphysics/system composition qualification

**Source aliases:** DQ-025.  
**Question:** When do qualified components support a qualified coupled system claim?

**Architect recommendation:** **never by automatic composition**. Require explicit `CouplingContract`, interface semantics, cross-component conservation/consistency checks, timing/numerical coupling behavior, propagation/failure tests, and system-level intended-use battery. Component certificates are evidence inputs, not system certification.

**Owner:** Multiphysics science + product qualification.  
**Proof required:** first coupled-system dossier/battery.  
**Status:** `READY_TO_RATIFY` principle; implementation later.

---

# H. Commercial product, GTM, pricing, and operations

## MQ-031 — First sellable SKU

**Source aliases:** BQ-002.  
**Question:** Should Carbon Evidence Audit be the first sellable product?

**Architect recommendation:** yes. It monetizes the independent judge before requiring a mature network marketplace, creates value even when the customer model fails, and naturally expands into remediation/discovery, qualification, lifecycle, and platform.

**Owner:** Business lead.  
**Proof required:** buyer interviews and first paid pilot.  
**Status:** `READY_TO_RATIFY`.

---

## MQ-032 — Evidence Audit tiers and standard deliverable

**Source aliases:** BQ-004, BQ-005, DQ-016.  
**Question:** What exactly do Standard, Advanced, and Enterprise contain?

**Architect recommendation:** define tiers primarily by evidence/integration/security burden, not artificial feature gating:

- **STANDARD:** one candidate, one bounded truth path, standard Carbon-hosted evaluation, core strata, executive + technical evidence report;
- **ADVANCED:** multiple candidates and/or richer strata/robustness, custom adapter/truth integration, expanded evidence/failure atlas;
- **ENTERPRISE:** private/VPC/customer-hosted truth topology, enhanced security/diligence package, SLA/support, auditor/export bundle.

Every paid Audit should include problem/claim definition, candidate identity, evidence plan, independent results, mandatory-admissibility outcomes, regime/stratum findings, limitations, provenance manifest, and recommended next action.

**Owner:** Business + product + science.  
**Proof required:** first three delivery retrospectives.  
**Status:** `READY_TO_RATIFY` as initial packaging hypothesis.

---

## MQ-033 — Evidence Audit pricing hypotheses

**Source aliases:** BQ-009, DQ-017.  
**Question:** What prices should Carbon test first?

**Architect recommendation:** do **not** lock universal dollar amounts yet. Create three quote bands from a bottom-up model:

```text
floor = expected direct expert + truth + compute + security cost
base = floor / target gross-margin complement
value ceiling = customer avoided cost / decision value / urgency-adjusted willingness to pay
```

Test Standard/Advanced/Enterprise bands in buyer interviews and proposals. Include finite evaluation capacity and explicit overage/change-order rules. Treat first pilots as pricing experiments, not precedents.

**Owner:** Business lead + finance.  
**Proof required:** measured delivery cost + willingness-to-pay evidence.  
**Status:** `EVIDENCE_REQUIRED`.

---

## MQ-034 — Challenge Feasibility commercial treatment

**Source aliases:** BQ-006.  
**Question:** Paid SKU or free sales engineering?

**Architect recommendation:** default **paid** when material scientific authoring, truth feasibility, rights/security design, or integration work is required. For a qualified strategic opportunity, Carbon may credit part of the feasibility fee toward a larger contracted program. Keep truly lightweight discovery free.

**Owner:** Business lead.  
**Proof required:** sales conversion and delivery-cost data.  
**Status:** `READY_TO_RATIFY` as default policy.

---

## MQ-035 — Model Development delivery mix

**Source aliases:** BQ-007.  
**Question:** How much model development should OpCo do directly versus external/network supply?

**Architect recommendation:** early phase should be **hybrid with OpCo accountable for integration/evidence and using internal or tightly controlled external specialists where necessary**. Do not force immature network execution into private/critical engagements. As network economics and security qualify, migrate eligible search effort outward while OpCo retains customer contract, integration, evidence, rights, qualification, and lifecycle accountability.

Track internal expert hours and network substitution explicitly to prevent services lock-in.

**Owner:** Business/product engineering.  
**Proof required:** delivery economics and network comparison.  
**Status:** `EVIDENCE_REQUIRED`.

---

## MQ-036 — Sponsored Discovery commercial structure and timing

**Source aliases:** BQ-003, BQ-010, BQ-011, BQ-027.  
**Question:** How should Sponsored Discovery be sold before full production network settlement?

**Architect recommendation:** permit controlled/off-chain or testnet-backed paid pilots **only if** scientific event semantics, participant rights, reward custody, and no-advance treatment are prospective and explicit. Standard fees should separate authoring, truth integration, program/platform operation, evaluation usage, reward administration, sponsor-funded reward pool, and optional qualification/deployment.

Base Carbon revenue does not depend solely on a frontier advance. Sponsor reward principal is separately accounted. Do not represent pilot settlement as production treasury functionality.

**Owner:** Business + protocol + finance/legal.  
**Proof required:** pilot SOW, custody/legal structure, first program.  
**Status:** `COUNSEL_REQUIRED` before material sponsor funds.

---

## MQ-037 — Gross-margin and productization targets

**Source aliases:** BQ-012, BQ-013, DQ-029.  
**Question:** What proves Carbon is becoming infrastructure rather than consulting?

**Architect recommendation:** use milestone-based targets rather than invented calendar forecasts. Track gross contribution by product, custom hours/engagement, reusable-work fraction, automated-evidence share, recurring/software/usage share, revenue per technical FTE, and platform conversion.

Do not claim escape from consulting economics until at least several comparable deliveries show declining custom effort and improving contribution margin, plus genuine recurring/usage revenue. Set numeric internal targets after the first 3–5 paid deliveries establish a cost baseline.

**Owner:** Business + finance/product.  
**Proof required:** cohort unit economics.  
**Status:** `EVIDENCE_REQUIRED`.

---

## MQ-038 — Initial vertical focus

**Source aliases:** BQ-001.  
**Question:** Which sectors should direct sales focus on first?

**Architect recommendation:** validate **aerospace/space/defense** and **energy/turbomachinery/industrial physics** as the two direct-selling tracks; maintain CAE/engineering-software vendors as a partner/OEM track. Do not spread direct GTM across automotive, robotics, climate, biotech, etc. until repeated buyer evidence justifies it.

**Owner:** Business lead.  
**Proof required:** 20–30 interviews and qualified pipeline comparison.  
**Status:** `READY_TO_RATIFY` as discovery focus.

---

## MQ-039 — Design-partner account strategy

**Source aliases:** BQ-020.  
**Question:** Which accounts qualify as first-wave design partners?

**Architect recommendation:** build a named 20–30-account universe split across the two direct verticals plus strategic CAE/software partners. Prioritize real expensive simulation workflows, accessible technical champions, existing fast-model pain or authorable problem, defensible truth path, manageable security scope, expansion potential, and willingness to provide product-learning evidence.

Avoid prestige-only logos whose first engagement requires impossible security, export-control, or procurement scope.

**Owner:** Business lead.  
**Proof required:** scored target-account list and interviews.  
**Status:** `EVIDENCE_REQUIRED`.

---

## MQ-040 — Pilot timebox and customer acceptance

**Source aliases:** BQ-022, DQ-016.  
**Question:** How long should pilots run and what counts as successful delivery?

**Architect recommendation:** use a bounded SOW with milestone-based duration rather than one universal elapsed-time promise. Initial Evidence Audit target should be designed around a procurement-friendly short engagement, but the exact default is set only after dry-run delivery. Acceptance should be delivery of the agreed evidence package and operational artifacts, **not a favorable scientific result**.

Sponsored Discovery acceptance similarly means the qualified program/evidence was delivered, not that a frontier advance was guaranteed.

**Owner:** Business/product.  
**Proof required:** internal dry run + first paid delivery.  
**Status:** `EVIDENCE_REQUIRED`.

---

## MQ-041 — Platform trigger and pricing architecture

**Source aliases:** BQ-024, BQ-025.  
**Question:** When should Carbon build/sell the Enterprise Evidence Platform and how should it price?

**Architect recommendation:** invest materially only after repeated workflows demonstrate demand: multiple Audits/qualifications in one account, shared adapters, recurring lifecycle, multi-team registry/governance need, or customers asking for self-service/API. Preferred pricing is **base annual platform commitment + usage/evaluation + deployment/support premium**, not compute-only pricing.

**Owner:** Product + business.  
**Proof required:** repeated-account behavior and willingness to commit annually.  
**Status:** `EVIDENCE_REQUIRED`.

---

## MQ-042 — Founder-led sales and first commercial hires

**Source aliases:** BQ-021, BQ-032.  
**Question:** When should Carbon hire sales and what hire comes first?

**Architect recommendation:** founders/business lead should own early discovery until a repeatable ICP, 2–3 paid engagements, recurring objections/procurement path, and repeatable SOW/pricing exist. First incremental commercial hire should usually be a **technical solutions/enterprise BD hybrid** capable of translating simulation/science into enterprise workflow, not a high-volume SaaS AE. Security/compliance and customer-success hires follow observed bottlenecks.

**Owner:** Founder/business lead.  
**Proof required:** pipeline and delivery bottleneck evidence.  
**Status:** `EVIDENCE_REQUIRED`.

---

## MQ-043 — Customer reference / publication incentives

**Source aliases:** BQ-023.  
**Question:** What may Carbon trade for logo/case-study/reference rights?

**Architect recommendation:** create a standardized reference-value menu rather than ad hoc discounts. Prefer limited discounts/credits tied to specific rights: anonymized case evidence < investor reference call < named logo/case study < jointly publishable technical result. Never trade away necessary data/IP/security protections or bias scientific reporting for a reference.

**Owner:** Business + legal.  
**Proof required:** template clauses and approval bands.  
**Status:** `COUNSEL_REQUIRED`.

---

# I. Rights, privacy, legal, and enterprise trust

## MQ-044 — Default customer data and evidence rights

**Source aliases:** BQ-014, BQ-015, DQ-018.  
**Question:** What should Carbon request by default?

**Architect recommendation:** customer retains ownership of customer data and proprietary solver assets. Carbon receives only the rights necessary to execute the engagement. Evidence should be classified prospectively, with a preferred negotiation ladder:

1. customer-confidential operational evidence;
2. anonymized/aggregated reuse where permitted;
3. method-level generalized learning where explicitly permitted;
4. public research only by explicit approval.

No silent cross-customer reuse. Metadata needed for audit/provenance may be retained only under the contract/data policy.

**Owner:** Business + counsel + privacy/security.  
**Proof required:** MSA/DPA/evidence-reuse schedule.  
**Status:** `COUNSEL_REQUIRED`.

---

## MQ-045 — Miner / external researcher IP

**Source aliases:** BQ-016, BQ-017, DQ-019.  
**Question:** Who owns submitted/winning/generalized methods and reconstructed artifacts?

**Architect recommendation:** default to a **rights-splitting model** rather than blanket assignment: participant retains background/generalized IP; Carbon/sponsor receives the prospectively agreed license required for the program; customer-specific trained artifact/weights may have different rights from the generalized method. Offer stronger exclusivity/assignment only where reward economics compensate for it and the participant explicitly accepts it.

Carbon may license a reusable method library only where chain of title/license rights are clear. Submission alone should not magically transfer all IP.

Terms must state separately whether Carbon may retain a Strategy, retain its ExperimentRecord, derive private aggregate knowledge, and publish a de-identified/coarsened prior item. Missing rights exclude the affected record from that use rather than silently expanding Carbon's license.

**Owner:** Business/economics + counsel.  
**Proof required:** contributor terms + sponsor rights schedule.  
**Status:** `COUNSEL_REQUIRED`.

---

## MQ-046 — Liability, warranty, indemnity, and insurance

**Source aliases:** DQ-021.  
**Question:** Who bears responsibility if a customer relies on a Carbon evidence/qualified model and suffers loss?

**Architect recommendation:** Carbon should contract as an evidence/model-development/qualification provider with bounded deliverables and explicit context-of-use limitations; final engineering/regulatory authority remains customer-side unless separately assumed by contract. Avoid broad warranties of correctness/safety. Use liability caps appropriate to contract value/risk, negotiated carve-outs for confidentiality/IP/security as counsel advises, and obtain professional/cyber insurance appropriate to actual exposure.

Do not sell a “guaranteed safe model.”

**Owner:** Founder/business + counsel/insurance broker.  
**Proof required:** counsel-approved MSA/SOW and insurance program.  
**Status:** `COUNSEL_REQUIRED`.

---

## MQ-047 — First private deployment / customer-hosted reference topology

**Source aliases:** BQ-018, DQ-022.  
**Question:** Which private architecture should Carbon productize first?

**Architect recommendation:** prioritize a **customer-hosted reference
service/RPC** first, then customer VPC. Keep the customer's proprietary solver
and source data inside its control plane; Carbon sends authorized case
specifications and receives only the reference outputs/metadata needed by the
registered evidence path. Authenticate requests, bind cases to
engagement/Challenge identity, minimize returned data, and define
retention/logging explicitly.

Full air-gap comes later unless a design partner funds the additional product/security burden.

**Owner:** Product/security + business.  
**Proof required:** threat model, reference implementation, penetration/security review.  
**Status:** `SECURITY_REVIEW_REQUIRED`.

---

## MQ-048 — Enterprise security/compliance roadmap

**Source aliases:** BQ-019, DQ-023.  
**Question:** What security certifications/controls should Carbon pursue and when?

**Architect recommendation:** derive the roadmap from the first target buyers rather than collecting badges. Build baseline enterprise controls now: identity/access management, secrets, encryption, logging, incident response, data classification/retention, vulnerability/dependency management, backup/recovery, secure SDLC, vendor management. Pursue SOC 2 and/or ISO 27001 when buyer/procurement evidence justifies it. Defense/export-controlled/CUI workflows require a separate eligibility/control program and should not be implied by generic SOC 2 readiness.

**Owner:** Security + business.  
**Proof required:** buyer requirements matrix and gap assessment.  
**Status:** `EVIDENCE_REQUIRED`.

---

# J. Investor, market, finance, and company scaling

## MQ-049 — Bottom-up TAM/SAM/SOM

**Source aliases:** BQ-031, DQ-028.  
**Question:** What market model can withstand investor diligence?

**Architect recommendation:** do not sum overlapping CAE/industrial-AI/V&V markets. Use top-down markets only as category evidence. Build SAM from named target enterprises × relevant model/simulation programs × addressable annual spend by Evidence/Discovery/Qualification/Lifecycle/Platform. Build SOM from named accounts × qualified opportunity rate × close rate × initial ACV × expansion/renewal.

Every external number should have source/date; every internal assumption should be visibly labeled.

**Owner:** Business/finance.  
**Proof required:** named-account model and sourced workbook.  
**Status:** `EVIDENCE_REQUIRED`.

---

## MQ-050 — Fundraising timing and capital ask

**Source aliases:** BQ-029, BQ-030.  
**Question:** When should Carbon raise and how much?

**Architect recommendation:** raise against de-risking milestones, not architecture breadth. Where runway permits, maximize evidence before the next institutional raise: validated buyer pain → first paid Audit → repeatable delivery → account expansion/recurrence. Calculate round size bottom-up from team, compute, security/private deployment, legal/IP, GTM, network/testnet, and runway needed to reach the next valuation-inflecting proofs.

Do not select a fashionable round size first and backfill the use-of-funds story.

**Owner:** Founder + finance/business.  
**Proof required:** milestone-based operating model/runway plan.  
**Status:** `EVIDENCE_REQUIRED`.

---

# K. Publication and public claim control

## MQ-051 — Publication release gate

**Source aliases:** DQ-030.  
**Question:** What must be true before v3.1 papers/decks are externally released as current Carbon materials?

**Architect recommendation:** require:

1. exact source files committed and version-pinned;
2. internal links/references pass;
3. citation audit against scientific canon;
4. scientific maturity/claim audit;
5. business traction/non-claim audit;
6. network/Alpha claim audit;
7. legal/commercial wording review where relevant;
8. generated PDFs rebuilt from exact committed source;
9. executive/owner approval of the release commit.

A successful PDF compile is not release approval.

**Owner:** Publication owner + science + business + founder.  
**Proof required:** signed/checklisted release record.  
**Status:** `READY_TO_RATIFY`.

---

# L. Post-Wave-B Bittensor launch and settlement

## MQ-052 — Launch taxonomy and direct-weight mainnet beta

**Source aliases:** launch v1.0.3 proposed MQ-052.
**Question:** Which launch gates are canonical, and may Carbon activate a
direct-winner mainnet beta?

**Ratified disposition:** use G2 `LOCALNET_READY`, G3
`TESTNET_ALPHA_DIRECT_WEIGHTS`, G4 `QUALIFIED_TESTNET`, G5
`MAINNET_DEPLOYABLE`, G6 `TREASURY_SETTLEMENT_QUALIFIED`, and G7
`MAINNET_MECHANISM_COMPLETE`. G5 may be deployment-ready with economics off.
The optional direct-score/direct-winner mainnet beta is superseded. Mainnet
economic activation requires treasury routing and per-Challenge settlement.

**Owner:** Carbon owner + protocol/economic owners.
**Decision evidence:** `OWNER-NET-01`; current launch path v1.0.4.
**Status:** `RATIFIED_ROADMAP`; implementation and qualification remain
unearned.

---

## MQ-053 — H/I sequencing after Wave D

**Source aliases:** launch v1.0.3 proposed MQ-053.
**Question:** Which post-D waves are launch-critical?

**Ratified disposition:** D → H → I is the launch-critical branch. Waves E,
F, and G may proceed in parallel after D and do not block H/I. H owns
frontier/finality; I is mainnet-critical for treasury routing and settlement.

**Owner:** Carbon owner.
**Decision evidence:** `OWNER-NET-01`.
**Status:** `RATIFIED_ROADMAP`; no future-wave implementation is selected.

---

## MQ-054 — Chain and application authority boundary

**Source aliases:** launch v1.0.3 proposed MQ-054.
**Question:** What does Bittensor own, and how does it connect to Carbon?

**Ratified structural disposition:** Bittensor owns network identity,
UID/metagraph/stake state, chain transactions, weight publication, and
eventual emissions rails. Carbon owns the Challenge, MCP semantics,
commitments, research, official evaluation, hidden exam, reconstruction,
truth, measurement, score, leader, frontier, entitlement, and settlement.
Authenticated Bittensor transport wraps the Miner MCP. Carbon policy emits
nominal typed intents through a narrow adapter; SDK objects never define
scientific merit.

**Still open:** exact SDK version/pinning, topology, threat-model acceptance,
transport profile, replay window, and privileged-action controls.
**Owner:** Network/security + protocol.
**Proof required:** NET-0 through NET-6 localnet evidence and security review.
**Status:** structural direction `RATIFIED_ROADMAP`; implementation details
`SECURITY_REVIEW_REQUIRED`.

---

## MQ-055 — Temporary direct-testnet winner and no-winner policy

**Source aliases:** launch v1.0.3 proposed MQ-055.
**Question:** How can testnet prove real weight setting without turning scores
into production economic authority or leaving a stale winner paid?

**Ratified structural disposition:** a new eligible Challenge-local leader may
create one expiring `TestnetWeightEligibilityEvent` from exact real C2
provenance. `TestnetWinnerWeightIntent` activates only the winner participant
allocation and zeroes other participants. With no active eligible winner, an
approved non-paying sink is active and every participant is zero. Raw score
magnitude does not determine weight magnitude. The event and intent are
`TESTNET_ONLY`, `NON_LIVE`, `NON_SETTLING`, `NOT_FRONTIER_QUALIFIED`, and
`NOT_MAINNET_ELIGIBLE`. The sink must be bound
to the exact network/mechanism/test-policy version, auditable and
readback-verifiable, non-benefiting to participants/miners/validators,
non-redistributive, and fail-closed/non-paying through recovery.

**Still open:** exact reward-window duration and exact sink chain
identity/custody. Neither may be invented by an implementation ticket.
**Owner:** Protocol/economics + network/security.
**Proof required:** C-W1 through C-W4, expiry/supersession/no-winner tests,
validator agreement, chain readback, recovery, and Testnet Alpha Report.
**Status:** structural direction `RATIFIED_ROADMAP`; values
`EVIDENCE_REQUIRED` / `SECURITY_REVIEW_REQUIRED`.

---

## MQ-056 — Testnet identity, quorum, stake, and key controls

**Source aliases:** launch v1.0.3 proposed MQ-056.
**Question:** Which network identity, validator agreement, stake, wallet, key,
rotation, and custody controls make chain intents acceptable?

**Architect recommendation:** bind every candidate/receipt/event/intent to the
exact hotkey/UID/network/netuid/mechanism identity and use explicit replay,
rotation, quorum, classified-error, readback, and recovery policy. Do not
infer any numeric quorum, stake floor, timing, or key topology here.

**Owner:** Network/security + economics.
**Proof required:** threat model, testnet exercises, key-rotation and
disagreement evidence, dedicated security acceptance.
**Status:** `SECURITY_REVIEW_REQUIRED`; quorum/stake values
`EVIDENCE_REQUIRED`.

---

## MQ-057 — Validator execution, audit, and service economics

**Source aliases:** launch v1.0.3 proposed MQ-057.
**Question:** How does Carbon ensure validators execute or audit expensive
scientific work instead of copying a treasury weight vector?

**Architect recommendation:** separate `ValidatorAssignment`,
`ValidatorExecutionReceipt`, `ValidatorAuditReceipt`,
`ValidatorServiceObligation`, and `ValidatorServiceSettlement`. A copier may
not claim Carbon-controlled service compensation without valid execution or
audit evidence. Weight similarity alone is not proof of misconduct.

**Still open:** assignment policy, validator quorum/stake, audit rate,
compensation formula, dispute treatment, and sustainable cost envelope.
**Owner:** Protocol/economics + security.
**Proof required:** free-rider simulation, secondary-execution experiments,
audit evidence, and settlement reconciliation.
**Status:** `EVIDENCE_REQUIRED`; security-sensitive elements require review.

---

## MQ-058 — Network and settlement operational SLOs

**Source aliases:** launch v1.0.3 proposed MQ-058.
**Question:** What availability, latency, recovery, readback, reorg, receipt,
and incident objectives are required at each launch gate?

**Architect recommendation:** measure each SLO on localnet/testnet and bind the
accepted values to the exact release/network profile. Do not treat chain
defaults or a successful demo as an SLO.

**Owner:** Operations/network/security.
**Proof required:** soak, failure injection, recovery drills, observability,
and owner-approved SLO register.
**Status:** `EVIDENCE_REQUIRED` / `SECURITY_REVIEW_REQUIRED`.

---

## MQ-059 — Strong-anchor audit operating policy

**Source aliases:** launch v1.0.3 proposed MQ-059.
**Question:** What strong-anchor audit frequency, budget, latency, custody,
and unavailable-anchor behavior are required for qualified operation?

**Still open:** every numeric or operational value, the custody design, and
the fail-closed response when an approved anchor is unavailable. This roadmap
does not infer them from the testnet weight path.
**Owner:** Science + operations + finance/security as applicable.
**Proof required:** Wave-D exact Challenge evidence, representative anchor
experiments, cost/latency evidence, custody review, and owner acceptance.
**Status:** `EVIDENCE_REQUIRED` / `SECURITY_REVIEW_REQUIRED`.

---

## MQ-060 — Incentive Alignment Dossier attack suite and pass rule

**Source aliases:** launch v1.0.3 proposed MQ-060.
**Question:** What minimum attack suite, evidence, and pass rule constitute an
acceptable Incentive Alignment Dossier?

**Still open:** attack coverage, scenario parameters, statistical acceptance,
independent-review requirements, and the human/security pass decision.
**Owner:** Security + science + protocol.
**Proof required:** registered attack suite, adversarial simulations,
independent review, and explicit acceptance against the selected release.
**Status:** `EVIDENCE_REQUIRED` / `SECURITY_REVIEW_REQUIRED`.

---

## MQ-061 — Direct-testnet-to-treasury migration and custody

**Source aliases:** `OWNER-NET-01`; launch v1.0.4; MQ-019 and MQ-020.
**Question:** How does Carbon migrate without overlap, duplicate benefit, or a
fallback to direct-winner mainnet weights?

**Ratified structural disposition:** stop new direct-winner events; let active
events expire or revoke them under registered policy; confirm the non-paying
sink; activate `TreasuryRoutingWeightIntent`; verify accrual; exercise test
frontier events and obligations; settle and reconcile. Rollback must be
non-paying and mainnet must have no automatic direct-winner fallback.

**Still open:** exact `TreasuryReceiverSet` membership/count, chain
identities, implementation, vault/custody topology, signers, governance,
settlement amounts, and recovery policy. The structural receiver-set path is
ratified; those exact selections are not.
**Owner:** Treasury/economics + security + governance.
**Proof required:** I-00 through I-05 migration rehearsal and settlement soak,
including outage, retry, UID/key rotation, no-overlap, and exactly-once tests.
**Status:** structure `RATIFIED_ROADMAP`; custody
`SECURITY_REVIEW_REQUIRED`; values `EVIDENCE_REQUIRED`.

---

## MQ-062 — Testnet Alpha Report and mainnet evidence package

**Source aliases:** `OWNER-NET-01`; launch v1.0.4.
**Question:** Which evidence is required to move from G3 to G4, G5, G6, and
G7 without collapsing integration, science, security, and economics?

**Architect recommendation:** C-W4 must bind the exact G3 proof chain and
record the `NON_LIVE`, `NON_SETTLING`, `NOT_FRONTIER_QUALIFIED`, and
`NOT_MAINNET_ELIGIBLE` ceiling. G4 separately binds the complete Wave-D
Challenge/Launch-Bar evidence. G5 binds deployment readiness with economics
possibly off. G6 binds H/I frontier, treasury, validator-economics, migration,
and settlement-soak evidence. G7 requires explicit owner launch authority.

**Owner:** Network + science + security + economics + launch owner by gate.
**Proof required:** exact gate dossiers and independent review.
**Status:** `EVIDENCE_REQUIRED`; no gate is earned by this roadmap.

---

# 1. Priority closure sequence

## Gate 1 — before first authoritative Challenge / LIVE planning

`MQ-001` through `MQ-008`, plus `MQ-013` through `MQ-017`.

## Gate 2 — before frontier rewards / production settlement

`MQ-009` through `MQ-012`, plus `MQ-018` through `MQ-020` and `MQ-052`
through `MQ-062` as applicable to the intended gate. Ratified structural
directions do not close their explicitly evidence/security-owned subquestions.

## Gate 3 — before claiming the subnet is a superior business scaling layer

`MQ-021` through `MQ-023`.

## Gate 4 — before broad agentic-construction claims

`MQ-024` through `MQ-026`.

## Gate 5 — before first serious commercial qualification / private enterprise engagement

`MQ-027` through `MQ-048` as applicable to the product.

## Gate 6 — before investor-scale claims and external publication release

`MQ-049` through `MQ-051`.

---

# 2. Source-question crosswalk

This crosswalk ensures no previously registered question disappears merely because the master register de-duplicates it.

## `docs/context/Open_Questions.md`

| Source | Master |
|---|---|
| OQ-001 | MQ-001, MQ-002 |
| OQ-002 | MQ-003, MQ-004 |
| OQ-003 | MQ-005, MQ-006 |
| OQ-004 | MQ-007, MQ-008 |
| OQ-005 | MQ-013 |
| OQ-006 | MQ-013 |
| OQ-007 | MQ-014 |
| OQ-008 | MQ-015 |
| OQ-009 | MQ-016 |
| OQ-010 | MQ-017 |
| OQ-011 | MQ-017 |
| OQ-012 | MQ-008, MQ-017 |
| OQ-013 | MQ-018 |
| OQ-014 | MQ-001 plus Gate 1 closure |
| OQ-015 | MQ-027, MQ-029 |

## `Business/Design_Questions.md`

| Source | Master |
|---|---|
| BQ-001 | MQ-038 |
| BQ-002 | MQ-031 |
| BQ-003 | MQ-036 |
| BQ-004 | MQ-032 |
| BQ-005 | MQ-032 |
| BQ-006 | MQ-034 |
| BQ-007 | MQ-035 |
| BQ-008 | MQ-027 |
| BQ-009 | MQ-033 |
| BQ-010 | MQ-036 |
| BQ-011 | MQ-036, MQ-019–020 |
| BQ-012 | MQ-037 |
| BQ-013 | MQ-037 |
| BQ-014 | MQ-044 |
| BQ-015 | MQ-044 |
| BQ-016 | MQ-045 |
| BQ-017 | MQ-045 |
| BQ-018 | MQ-047 |
| BQ-019 | MQ-048 |
| BQ-020 | MQ-039 |
| BQ-021 | MQ-042 |
| BQ-022 | MQ-040 |
| BQ-023 | MQ-043 |
| BQ-024 | MQ-041 |
| BQ-025 | MQ-041 |
| BQ-026 | MQ-023 |
| BQ-027 | MQ-036, MQ-022 |
| BQ-028 | MQ-022 |
| BQ-029 | MQ-050 |
| BQ-030 | MQ-050 |
| BQ-031 | MQ-049 |
| BQ-032 | MQ-042 |

## `docs/context/REVIEW_THESE_PRELIMINARY_DECISIONS_DEFENSIBILITY.md`

| Source | Master |
|---|---|
| DQ-001 | MQ-001 |
| DQ-002 | MQ-002 |
| DQ-003 | MQ-004 |
| DQ-004 | MQ-007 |
| DQ-005 | MQ-009, MQ-010 |
| DQ-006 | MQ-013 |
| DQ-007 | MQ-014 |
| DQ-008 | MQ-015 |
| DQ-009 | MQ-016 |
| DQ-010 | MQ-019 |
| DQ-011 | MQ-020 |
| DQ-012 | MQ-018 |
| DQ-013 | MQ-012 |
| DQ-014 | MQ-021 |
| DQ-015 | MQ-022 |
| DQ-016 | MQ-032, MQ-040 |
| DQ-017 | MQ-033 |
| DQ-018 | MQ-044 |
| DQ-019 | MQ-045 |
| DQ-020 | MQ-028 |
| DQ-021 | MQ-046 |
| DQ-022 | MQ-047 |
| DQ-023 | MQ-048 |
| DQ-024 | MQ-029 |
| DQ-025 | MQ-030 |
| DQ-026 | MQ-026 |
| DQ-027 | MQ-025 |
| DQ-028 | MQ-049 |
| DQ-029 | MQ-037 |
| DQ-030 | MQ-051 |

## `launch/Carbon_Testnet_to_Mainnet_Launch_Path_v1.0.3.md`

| Source | Master |
|---|---|
| proposed MQ-052 | MQ-052 |
| proposed MQ-053 | MQ-053 |
| proposed MQ-054 | MQ-054 |
| proposed MQ-055 | MQ-055 |
| proposed MQ-056 | MQ-056 |
| proposed MQ-057 | MQ-057 |
| proposed MQ-058 | MQ-058 |
| proposed MQ-059 | MQ-059 |
| proposed MQ-060 | MQ-060 |

Roadmap-only migration and evidence-package questions introduced by
`OWNER-NET-01` are canonical MQ-061 and MQ-062; they are not aliases for the
historical proposed MQ-059/MQ-060 questions.

---

# 3. Master rule

> **No important Carbon decision should remain merely “open.” It should be open with a recommended disposition, an owner, a proof path, and a clear condition under which Carbon may rely on the resulting claim.**

When a master question is resolved, record the ratified decision in the relevant domain decision/spec/canon document and change the master status with a link/commit to the decision evidence. Do not leave resolved policy buried only in meeting notes or chat history.
