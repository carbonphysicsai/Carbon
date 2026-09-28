# Carbon protocol specification

Carbon coordinates research into fast physical models and independent evaluation of the submitted construction methods. This specification describes the architecture and points to the contracts that own its detailed behavior.

For a plain-language introduction, read the [README](README.md). For the current implementation and research record, read [Project status](docs/publications/PROJECT_STATUS.md). Carbon is in development and testnet work; architectural descriptions below do not establish production readiness.

## Current scope and interpretation

The initial protocol uses constrained construction recipes and producer-independent reconstruction. The repository now includes the Burgers development testbed, battery-specific development contracts, and reserved launch directions for cold plates, motors, and photonics. Each challenge has its own inputs, outputs, reference, and evaluation contract.

`OWNER-C0-REWARD-01` supersedes older mandatory-treasury and temporary-direct-only payment routing: the current direction is persistent **DIRECT_WINNER_PLUS_BURN**, with treasury optional. Scientific comparison, frontier/finality, security, qualification, and deployment requirements remain unchanged. `OWNER-C-W1-DEV-TESTNET-01` authorizes only its separately bounded development scenario; it does not establish official or mainnet readiness.

The P0 45/30/25 profile is a particular scoring contract. It is not a universal scoring formula for the launch portfolio. Exact scoring mathematics remain with [Scoring](Design_Specs/Scoring.md) and each registered challenge's applicable contract.

## 1. Mechanism

A researcher submits a method the evaluator can reconstruct. Evaluators build and test candidates under pinned contracts, data roles, environments, and resources. Mandatory physical checks precede ranking; a candidate cannot offset a mandatory failure with better average accuracy.

The scientific record identifies the candidate, evaluation context, measurements, and limitations. Public projections disclose permitted evidence while preserving protected evaluation material. A qualified official exam requires more than successful code execution: its population, reference, measurements, and decision rules need supporting evidence and review.

The intended network separates three decisions:

- Whether a candidate satisfies the challenge's scientific requirements.
- Whether the evidence supports a qualifying improvement under the registered comparison policy.
- How an eligible result enters the network reward and settlement policy.

A research result does not qualify a customer deployment. Commercial qualification needs evidence for the exact artifact, runtime, operating conditions, and engineering use.

## 2. Responsibilities and technical references

Model builders provide candidates and recipes. Reference solvers or measurements provide the comparison basis. Carbon defines the evaluation contracts and independent reconstruction process. Bittensor supplies network participation and incentive transport; chain consensus does not define physical truth.

Landscape, broader construction programs, private deployment modes, and commercial specialists remain governed by their own implementation and qualification requirements. A planned interface or architecture does not make one available.

| Document | Responsibility |
|---|---|
| [Scoring](Design_Specs/Scoring.md) | P0 scoring mathematics, gates, and Score Packs |
| [Data management](Design_Specs/Data_Management.md) | Data roles and protected evaluation material |
| [Trustless verification](Design_Specs/Trustless_Verification.md) | Commitments, seeds, and evaluation boundaries |
| [Generator validation](Design_Specs/Generator_Validation.md) | Reference and exam qualification |
| [Launch requirements](Design_Specs/Launch_Bar.md) | Qualification and stop-ship requirements |
| [Miner MCP](Design_Specs/Miner_MCP.md) | Miner-facing contract |
| [Research service contract](Design_Specs/Miner_MCP_Wave_B_Research_Contract.md) | Separate research-plane architecture and controls |
| [Current MCP implementation guide](carbon/miner_mcp/README.md) | Available client interfaces and development limits |
| [Specialist Bank](Design_Specs/Specialist_Bank.md) | Separate product qualification path |
| [Landscape](Design_Specs/Landscape_Agent.md) | Knowledge and evidence reuse architecture |
| [Implementation](Design_Specs/Implementation.md) | Code-level patterns |
| [Launch path v1.0.7](launch/Carbon_Testnet_to_Mainnet_Launch_Path_v1.0.7.md) | Current launch amendments and development-testnet boundaries |
| [Constitutional overlay](Design_Specs/Build_Out_Constitutional_Overlay.md) | Interpretation of older sequencing against later decisions |

The detailed sections below include P0 and later architectural designs. Apply the current scope and domain-owned contracts above when reading older examples.

---

## 3. System architecture

```
MINERS / AGENTS
  ├─ Optional research loop: manifest → exact PriorPack → compile → paired practice → submit
  ├─ Strategy JSON (schema-versioned)
  └─ Toolkit: Docker + SDK + cost hints

VALIDATORS
  ├─ Procedural data (seeded; train ≠ eval ≠ stress)
  ├─ Registered mandatory exam pack + physics gates for every nonzero result
  ├─ Short rollout stability (lean plant signal)
  ├─ Challenge-bound Score Pack
  └─ Model Card (provenance → later Landscape ingest)

REFERENCE / QUALIFICATION SERVICES (as registered)
  ├─ DifferentialEquations.jl / SciMLSensitivity.jl
  ├─ ModelingToolkit.jl (structured losses)
  └─ Analytic, mesh-converged, cross-code, or experimental anchors as registered

LANDSCAPE AGENT (after Launch Bar)
  ├─ Private graph: cards, effects, failures, promotion / product-battery outcomes
  ├─ Port A Search: immutable evidence-labeled PriorPacks + falsification aids → miners
  ├─ Port B Eval: scheduling, prefetch, and capacity advice only; never candidate-specific grading depth
  ├─ Port C Economy: challenge-weight / bounty *proposals* only
  └─ Port D Product: opportunity rank → Specialist Bank gauntlet

SPECIALIST BANK (Port D execution)
  ├─ Candidate recipes (winning strategy allowed as candidate; rank/checkpoint ≠ qualification)
  ├─ Controlled retrain + product battery
  └─ Dual egress: coarsened public evidence | closed commercial SKU

INCENTIVES
  ├─ C2: eligible-leader event → expiring TESTNET_ONLY winner intent
  ├─ Reward direction: direct winner plus burn; treasury optional
  └─ Landscape similarity never a score term
```

### 3.1 Dual egress (specialist artifacts)

| Path | Who | What they get |
|------|-----|---------------|
| **Public / miner** | Miners, agents | Immutable, lagged, evidence-labeled PriorPacks with registered interventions, uncertainty, caveats, and falsification aids; never full weights or an exact bank recipe |
| **Commercial** | Buyers | Closed SKU = ONNX (or approved) + exact recipe + Model Card + **product-battery certs** + license + updates (+ optional air-gap) |

Competition scoring **never** depends on purchasing the commercial path.

### 3.2 Flywheel loop (why Landscape is real)

1. **Ingest** eligible, qualified official Model Card evidence (and later promotion / product-battery outcomes).
2. **Fit** symbolic structure and effect candidates offline or in batch, including Double ML only where its assumptions and identification design are registered.
3. **Route**  
   - A: orient agent search with versioned, evidence-labeled hypotheses while protecting realized exam information
   - B: spend validator GPU where it matters (under Port B floor rules)  
   - C: propose future Challenge-set/economic allocation under registered policy
   - D: queue regimes with dense replicated effect-candidate or experimentally
     supported evidence for **gauntlet productization**
4. **Bank** only what re-trains and passes job-shaped tests.  
5. **Feed back** qualified aggregate evidence into later immutable PriorPacks and prospective challenge design under rights, lag, and cumulative-disclosure controls.

Success metrics: post-gate progress, product-battery pass rates, commercial conversion — **not** guidance-API engagement. Landscape never overrides gates. **L0 public publish only after Launch Bar green.**

The subnet team builds a knowledge graph of these Model Cards and uses them to retrain/retest and harden specialist models built for industry deployment. This process is purposely more rigorous than the mining evaluation. We want (mine → validate → feedback) to be fast, but we want to build real thorough due diligence into the models we are selling.

---

## 4. Trust-minimized verification and data generation

### Core principles

- **Procedural generation at runtime:** Primary evaluation and stress data are generated at runtime with open-source generators.
- **Typed unpredictable entropy:** Official evaluation consumes an exact 32-byte `OfficialEntropy` from a registered `BeaconProvider`. Role seeds are derived with RFC 5869 HKDF-SHA-256 domain separation. The production provider, observation timing, finality rule, and outage policy remain unresolved owner decisions and cannot be invented by an implementation.
- **Auditable after disclosure:** Generator code and derivation rules are open. An authorized audit can reproduce a draw once its committed entropy and protected realization material are disclosed under policy.
- **Scientific credibility:** Parameter ranges need documented physical justification; generators validated against high-fidelity references (FEniCS, OpenFOAM, SU2, DPLR, US3D, **DifferentialEquations.jl**, and peers).
- **No fixed public benchmark as the live exam:** Fixed datasets may validate generators; they are not the miner-facing answer key.
- **Train/eval/stress role separation:** Randomness roles and realized samples
  are separated; the Challenge declares their physical-distribution
  relationship. Miner local loops must not see validator evaluation entropy or
  realized draws.

### Qualified reference path

Each Challenge registers a primary reference used to produce the operational answer key for its realized exam conditions. That reference earns bounded authority through analytic, refined-solver, cross-code, manufactured-solution, experimental, or other independent evidence recorded in its Validation Dossier. Julia/SciML may implement one reference or witness capability, but it is not a universal oracle. If a required reference is unavailable or its uncertainty cannot resolve the decision, Carbon returns a typed infrastructure or indeterminate outcome rather than scoring through the failure.

Full design including proprietary-data handling: [`Trustless_Verification.md`](./Design_Specs/Trustless_Verification.md).

### Data generation invariants

- Official entropy and its role-derived seeds remain unavailable to miners before commitment and evaluation.
- Validator generator config ignores miner-supplied eval params.
- Score Pack robustness category IDs must align with Generator Pack categories ([`Scoring.md`](./Design_Specs/Scoring.md) + [`Data_Management.md`](./Design_Specs/Data_Management.md)).
- Stress category coverage targets remain as specified in Data Management (≥95% where defined).

---

## 5. Miner participation and local iteration

### Philosophy

- **Validator authority:** Every official score-bearing path is a full lean exam on hidden data with hard gates. Only exact real C2 provenance may create a temporary non-settling testnet event; production economics require the applicable scientific, frontier, reward-policy, and launch authority.
- **Miner autonomy:** Local iteration is encouraged, never required.
- **Zero-friction submit:** Strategy JSON can be submitted with **no** local training.
- **Information boundary:** Publish the registered physics target, strategy
  surfaces, practice scope, evidence-use policy, and approved scientific memory.
  Protect realized official cases, seeds, stress composition, references, exact
  margins, private records, and champion recipes.

Mining supports agentic research. The research service gives each miner the same
exact approved PriorPack, public executable strategy surfaces, deterministic
compilation, bounded resource information, and an optional declared-incomplete
practice path. A miner chooses hypotheses, runs experiments, and keeps its
private research state. Carbon does not predict the miner's official score,
rank, gate margins, or winner status.

### Three tiers (local → official)

| Tier | Compute | Anchored to | Purpose | Economic authority? |
|------|---------|-------------|---------|------------|
| **Static research** | Near zero | Public manifest, exact PriorPack, compiler, and resource models | Check validity, prior alignment, and resource feasibility without executing or predicting score | No |
| **Practice research** | Bounded optional compute | Fresh public practice cases under a declared incomplete PracticeMeasurementPack | Test one or more hypotheses with paired common-case evidence | No |
| **Full submission** | Network-paid eval | Full hidden validator data | Official score | **Eligible evidence only**; no automatic weight/frontier/settlement authority |

**Key rule:** A miner can submit at any time with zero local training. Paid or heavy local train is optional enhancement, not a gate to compete.

### Data and stress separation (critical security boundary)

| Aspect | Miner local loops | Validator official evaluation |
|--------|-------------------|-------------------------------|
| **Data** | Fresh practice cases from the declared practice scope; no official assets | Procedural official cases from validator-controlled realized draws |
| **Stress tests** | Published, declared-incomplete practice strata | Registered official stress sampling with protected realized composition |
| **Physics checks** | PracticeMeasurementPack only; no official thresholds or winner claim | Registered mandatory gates; hard fail → score 0 |
| **Data visibility** | Miner controls | **Never exposed to miners** |

Carbon wants improvements on the declared physics distribution to transfer from
practice to official evaluation. Security analysis therefore measures the
incremental ability to infer protected realized cases, mixtures, or margins
after controlling for performance on evaluator-held shadow cases. Low
practice-to-official correlation is not a safety objective. Practice evidence
never replaces, prequalifies, schedules, or scores the official exam.

Implementation patterns: `IMPLEMENTATION.md` / [`Design_Specs/Implementation.md`](./Design_Specs/Implementation.md).

---

## 6. Lean validation and scoring

Canonical formulas, Score Pack schema, validator load path, per-challenge bank: **[`Design_Specs/Scoring.md`](./Design_Specs/Scoring.md)**.

Lean labels are the **trust root** for Landscape ingest. Unfinished gates or scores → no verified compounding claims ([`Launch_Bar.md`](./Design_Specs/Launch_Bar.md)).

### Score composition (default lean weights)

| Component | Weight | Composition |
|-----------|--------|-------------|
| **Physics fidelity** | 45% | Weighted gate **margins** (residual, conservation, short rollout, … per Score Pack) |
| **Robustness** | 30% | Stress categories: mean/tail blend + weakest-category pressure |
| **Accuracy** | 25% | Normalized held-out field error |

**Challenge binding:** Validator loads Score Pack + Generator Pack by registered `(challenge_id, scoring_version, generator_version)` content hashes — **no silent default exam**.

**Not in lean score:** training loss, product battery, Landscape similarity, prior distance.

### Physics gates (hard — zero score on failure)

| Gate | Phase | Notes |
|------|-------|-------|
| Mass conservation | 0+ | Hard |
| Energy stability | 0+ | Hard |
| Boundary satisfaction | 0+ | Hard |
| **Rollout stability (short)** | 0+ | Lean multi-step / stability signal — **not** full HIL-horizon plant suite |
| Shock capture / turbulence UQ / species / chemistry / FSI / coupling / 3D turb | 1A–4 | As regime requires |

**Hard gate rule:** Any mandatory FAIL → total score = 0.

### UQ policy (honest phasing)

- **Phase 0–1A lean path:** Stress margins + failure atlas on cards; conformal/ensemble **not** a universal hard gate for every submission.
- **Product / specialist tier:** KPI conformal or ensemble bands where `product_jobs` include UQ or safety-margin claims.
- **Turbulence / chemistry model-form UQ:** Part of **regime gate margins** when those challenges are live (1A/1B+), separate from “every PoC card must ship 95% conformal fields.”

### Scientific-result to network-policy mapping

```text
scientific result
→ Carbon policy event
→ nominal typed chain intent
→ ChainAdapter / WeightPublisher
→ Bittensor
```

The former raw/lean-score-magnitude-to-weight formula is superseded. During
C2, Challenge-local score/rank determines only whether a new eligible leader
exists; an expiring `TestnetWeightEligibilityEvent` may create a
`TestnetWinnerWeightIntent`, and an explicit non-paying sink applies when no
active winner exists. Mainnet uses `FrontierAdvanceEvent` →
`SettlementObligation` → `TreasuryRoutingWeightIntent` → per-Challenge
settlement. Product-battery status does not create scientific or economic
merit and is not required to compete.

---

## 7. Challenges by phase (capability-gated)

> **Phase jumps are capability-gated, not calendar-gated.** All listed entry gates must pass.

### Phase transition criteria

| Transition | Entry gate (ALL required) | Meaning |
|------------|---------------------------|---------|
| **0 → 1A** | Validator reliability floor (e.g. 5 validators, high uptime); 7 PDEs mesh-converged vs FEniCS/DifferentialEquations.jl; 3 backbones; Model Zoo / catalog path live; pilot demand signal | Subnet operational — verification layer live |
| **1A → 1B** | 2 defense benchmarks mesh-converged + turb UQ framework; Factory v1 live; 1+ Tier 2 LOI | Compressible flow verified — sponsored path live |
| **1B → 2A** | 4 defense benchmarks (turb UQ + chem UQ); Factory hardened; Prime teaming; SBIR I submitted | Defense breadth + Factory hardened |
| **2A → 2B** | Schema v1.1 live (LoRA + custom data + MT losses); Specialist Bank gauntlet path live; DML flowing; Tier 1 traction | Customization + intelligence live |
| **2B → 3** | Air-gap toolkit v1 in 2+ enclaves; preCICE sidecar tested on sequential FSI; coupling convergence validated | Classified-ready + coupling architected |
| **3 → 4** | 3 coupled benchmarks live (coupling gates passing); preCICE production on validators; SBIR II / Tier 4 signal | Coupled physics supply chain live |
| **4 → 5** | 3D turbulence benchmarks live; curriculum proven; production contracts / ARR gate | Production-grade 3D turbulence |

### Phase overview

| Phase | Name | Physics scope | Challenge types | Schema | Revenue posture |
|-------|------|---------------|-----------------|--------|-----------------|
| **0** | Foundation | 7 academic PDEs | Base (7) | v1.0 | Catalog path after exam is real |
| **1A** | Compressible flow | + 2 defense | Base + hosted | v1.0 | Tier 1 + Tier 2 |
| **1B** | Reacting flow + sequential FSI | + 4 defense | Base + hosted | v1.0 | Tier 1–3 |
| **2A** | Customization & intelligence | + custom | + LoRA + custom data + MT | v1.1 | Tier 1–3 + adapters |
| **2B** | Air-gap + coupling prep | + custom | + air-gap + preCICE arch | v1.1 | Tier 4 pilot |
| **3** | Multi-physics coupling | Coupled | Composite v2.0 | v2.0 | Tier 4 + SBIR II |
| **4** | Production | 3D + turbulence | All + 3D/turb | v2.0+ | Production |

### Phase 0: Foundation (7 academic PDEs)

| ID | Problem | Dimension | Key physics |
|----|---------|-----------|-------------|
| 1 | Poisson | 2D/3D | Elliptic, source-driven |
| 2 | Darcy | 2D/3D | Elliptic, heterogeneous media |
| 3 | Burgers | 1D/2D | Hyperbolic, shock formation |
| 4 | Navier–Stokes (laminar) | 2D/3D | Incompressible flow, div-free |
| 5 | Heat | 2D | Parabolic, transient conduction |
| 6 | Linear elasticity | 2D | Vector mechanics, equilibrium |
| 7 | Thermo-elasticity | 2D | Coupled thermal–mechanical |

**Mesh/temporal convergence:** Multi-level h-refinement; validated vs FEniCS / DifferentialEquations.jl (and peers).

**Productization in Phase 0:** Catalog specialists still run the **product battery** (even on academic PDEs) so gauntlet discipline exists before OEM regimes — credibility SKUs, not optional theater.

### Phase 1A–4

Physics additions remain as previously specified (NACA/CRM, HIFiRE, Turek/Hron sequential, store separation, CHT, preCICE composites, 3D turbulence). Sponsored challenges may **extend product-battery definitions** in the challenge brief (`product_jobs`: inverse_design, plant, uq, …). Challenges will progress from simple PDEs to more complex physics regimes that are targeted at valuable Engineering fields and use cases (Aerospace, Auto, Robotics, Propulsion, UAV/Drones). The subnet is designed from day one so competition produces evidence that can later support the development of valuable commercial specialists. Carbon will use Bittensor to enable industry players to sponsor their own challenge that’s targeted at their specific physics envelope. Custom surrogate development and verification service without exposing proprietary data will prove valuable for major engineering players.

---

## 8. Strategy schema evolution

| State | Wire envelope | Executable meaning | Authority |
|---|---|---|---|
| **Implemented Wave A Strategy v1.0** | Exactly `schema_version`, `challenge_id`, scalar `backbone`, and `parameters` | `parameters` remains bounded inert JSON; the schema rejects executable material, dependencies, paths, datasets, seeds, official controls, and unsupported backbones | `carbon/schema/strategy.py`, A2 decisions/tests, and `Miner_MCP.md` |
| **Wave B candidate** | Keeps the same four-field v1.0 envelope | A public Challenge-bound `ParameterCatalog`, `CandidateAssemblyContract`, and deterministic `StrategyCompiler` produce one canonical `ResolvedConstructionPlan` or a typed rejection | B-02B after B-07R; B-07S owns wire-visible v2 behavior |
| **Later construction expansion** | New version required | Broader model composition or participant code requires a new threat model, isolation contract, reconstruction protocol, and owner ratification | Future authorized wave only |

Wave B rejects unknown, unused, incompatible, coerced, silently defaulted,
silently clamped, and unsupported parameters. A registered hybrid backbone may
expose a learned slot only inside Carbon-owned assembly. Strategy v1 does not
permit participant-defined graphs or code.

The Challenge owns the target population `P`, official proposal and SamplingPlan
`Q`, evidence weights `w`, generators, official entropy, realized evaluation
draws, Score Packs, and gates. It also owns the allowed training support and a
closed family of training policies. A miner may select only catalog-registered,
Challenge-bounded training sampling, curriculum, or augmentation levers. Those
choices compile into one canonical `ResolvedTrainingSamplingPolicy`, denoted
`R_strategy`, and its content-addressed `TrainingSamplingPolicyRef`; both are
pinned in the `ResolvedConstructionPlan`. The validator derives the actual
training draws in a role-separated seed domain. `R_strategy` cannot alter `P`, `Q`, `w`, the
official evaluation or stress distribution, reference process, or scorer.
Wave B accepts no raw or custom dataset upload, path, URI, or miner-selected
seed. Future custom-data or generalized-construction capability requires a
prospective schema, rights, security, reconstruction, and scientific contract.

---

## 9. Landscape agent (knowledge flywheel)

Canonical build guide: **[`Design_Specs/Landscape_Agent.md`](./Design_Specs/Landscape_Agent.md) (v1.2+)**.  
Launch prerequisites: **[`Design_Specs/Launch_Bar.md`](./Design_Specs/Launch_Bar.md)**.  
Product path: **[`Design_Specs/Specialist_Bank.md`](./Design_Specs/Specialist_Bank.md) (v1.3+)**.  
Scoring labels: **[`Design_Specs/Scoring.md`](./Design_Specs/Scoring.md)**.

### Role

Landscape is Carbon’s batch intelligence system with four controlled ports — not a live strategy oracle and not a teacher-distillation factory.

| Port | Consumer | Leaves the building |
|------|----------|---------------------|
| **A Search** | Miners / agents | Immutable evidence-labeled PriorPacks, registered interventions, caveats, and falsification aids |
| **B Eval** | Validators only | Scheduling, prefetch, and capacity proposals; never candidate-specific exam depth, stress, or gates |
| **C Economy** | Governance | Challenge-weight / bounty *proposals* |
| **D Product** | OpCo / bank | Opportunity specs → gauntlet → closed SKUs / briefs / sealed packs |

**Epistemic split:** Gates are registered protocol decisions when the Launch Bar is green. Association and effect-candidate bands are decision support; causal claims require registered identification and promotion.

### What compounds (private)

| Private asset | Flywheel effect |
|---------------|-----------------|
| Model Card lake (D1) | Reproducible feature store for fits |
| Symbolic library (D2) | Structured loss templates into priors / recipes |
| Epistemically typed effect candidates (D3) | Evidence-labeled interventions and bands for search; module targets for bank |
| Failure atlas (D4) | Diagnostics + stress evolution |
| Frontier map (D5) | Emission proposals toward unsaturated boards |
| Promotion / PB graph (D11) | Repair loop; opportunity rank prefers regimes that graduate |

### Port D export law

```text
ship_commercial_full_sku =
    lineage(landscape evidence)
    AND controlled_retrain_pass
    AND product_battery_pass
    AND dual_egress_policy
```

**Banned for commercial export:** Teacher weight copy; shipping a single-winner strategy/JSON **without** fresh independent qualification (retrain + product battery); ship without product-battery report. A winning strategy **may** be a candidate seed.

### Landscape phases

| Landscape phase | Unlock |
|-----------------|--------|
| L0 | Card lake + qualified versioned PriorPack publication on fixed release epochs (**after Launch Bar green, rights review, and disclosure approval**) |
| L1 | Symbolic + failure atlas |
| L2 | Effect-candidate core + opportunity ranker → bank queue |
| L3 | Eval + economy ports (Port B floors enforced) |
| L4 | Full Port D gauntlet integration + air-gap packs |

---

## 10. Specialist Bank and commercial GTM

Canonical: **[`Design_Specs/Specialist_Bank.md`](./Design_Specs/Specialist_Bank.md)**.

### Product battery (full surrogate SKU — summary)

| ID | Test |
|----|------|
| PB-PHYS | Fresh retrain + physics gates + stress (new seeds) |
| PB-ROLL | Plant / rollout suite at product depth |
| PB-INV | Inverse-design bakeoff (targets, constraints, query budget) |
| PB-ADV | Adversarial optimizer under box constraints |
| PB-LAT | Latency class on reference hardware |
| PB-ART | ONNX (or approved) + I/O parity |
| PB-ESC | Escalation notes on Model Card |

Module-type exceptions and detail: `Specialist_Bank.md`.

### Revenue engines

| Engine | Product | Notes |
|--------|---------|-------|
| **Tier 1 Specialist Bank** | Closed ONNX + recipe + card + **PB certs** + license | Catalog credibility → regime value |
| **Tiers 2–4 sponsored challenges** | Open / IP-licensed / private | May define extra PB tests; creates regimes bank lacks |
| **DoD / SBIR path** | Evidence packages | Dual-regime; sealed packs |
| **Verification registry** | Attestation / card API | Artifact remains licensed |

**Conservative principle:** Open the verification *standard* and coarse catalog; close the certified artifact and rights/ops around it.

---

## 11. Dual-regime architecture (regulated / defense)

```
PUBLIC REGIME (Carbon subnet)
  ├─ Discovers strategies on public / synthetic data
  ├─ Adversarial verification + physics gates
  ├─ Outputs: strategy.json + Model Card + (after gauntlet) export artifact
  └─ Zero ITAR / controlled data on the open net

                    cross-domain transfer of blueprint / recipe only
                                    ▼
CLASSIFIED / CUSTOMER REGIME (enclave)
  ├─ Ingests architecture blueprint (strategy.json)
  ├─ Fine-tunes on classified telemetry / proprietary geometry
  ├─ Re-runs product battery policy where required
  ├─ Deploys ONNX locally (HIL, edge, air-gapped)
  ├─ Inference LOCAL — zero required network calls
  ├─ Customer owns classification (e.g. ITAR/EAR) and ATO artifacts
  └─ Packages program deliverables as required by the prime
```

### Data handling phases

| Phase | Posture |
|-------|---------|
| **0–1B** | Public + synthetic only. No proprietary data enters the network. |
| **2A** | Customer-controlled local fine-tuning with custom datasets (e.g. Abaqus ODB). Raw data never required on subnet; commercial adapters **re-pass product battery** after adapt. |
| **2B** | Air-gapped miner toolkit v1 for enclaves (IL5/IL6-class). Zero network dependencies. |
| **3+** | Confidential computing (e.g. H100 TEEs) on validator path for sensitive workloads as adopted. |
| **Oracle** | Julia/SciML deployable in both regimes (air-gapped Julia for classified). |

---

## 12. Incentives and tokenomics

- A Challenge-local eligible-leader tracker may nominate the temporary C2
  testnet event; it does not map score magnitude to weight magnitude.
- Participation dust, reward-window duration, exact no-winner sink, bounties,
  and settlement values remain human/economic policy. OWNER-C0-REWARD-01
  selects persistent direct-winner-plus-burn routing; treasury receivers are
  optional. This payment direction does not grant production authority.
- **Forbidden as direct score terms:** Landscape similarity, prior distance, product-battery status.

---

## 13. Miner toolkit and submission interface

- Docker toolkit, `carbon-miner` CLI, and async SDK patterns as specified in implementation docs.
- Wave A implements an unnamespaced, process-local seven-operation surface:
  `get_challenge_info`, `get_prior`, `get_mock_scaffold`, `dry_validate`,
  `estimate`, `submit`, and `get_submission_result` with bounded existing
  semantics.
- After B-07R engineering ratification and B-07S exact-protocol ratification,
  the separate local topology retains the unchanged Wave-A official plane and
  adds a research plane for manifest discovery, exact PriorPack retrieval,
  compilation, prior alignment, resource inspection/forecasting, and
  asynchronous practice research. B-07S owns exact service/version and
  operation names. The research plane cannot duplicate official submission or
  result authority.
- Static resource inspection and calibrated forecasts may help miners plan
  optional local or rented compute. They never predict official score, disclose
  protected evaluator topology, or gate access to submission.

---

## 14. Validator operations and economics

- Hardware tables, health gates, fair admission, and isolated sponsored capacity remain operational guidance in [`Operations.md`](./Design_Specs/Operations.md). Reputation, stake, sponsorship, novelty, and practice results cannot change an eligible candidate's registered exam pack or scientific score.
- Product-battery runs are **promotion-time** workloads scheduled by bank/OpCo — not unbounded per-submission defaults.
- Compute efficiency strategy: [`Compute_Optimization.md`](./Design_Specs/Compute_Optimization.md), [`JAX_Optimization.md`](./Design_Specs/JAX_Optimization.md).

---

## 15. Security and correctness invariants

- **Shared exam identity:** all official score-bearing evaluations for a `(challenge_id, scoring_version, generator_version)` pin the same official exam identity (pack hashes + seed domain). Validators do not invent private alternate exams for scoring. Weight or treasury publication never changes that scientific identity.
- **Public physics / hidden realization:** the declared envelope, generator code, and validation dossier are public; official realization draws and seeds remain hidden.
- **Port B:** every scored nonzero submission completes the **same mandatory lean pack**; progressive depth must not change the graded identity of the lean exam.


| Invariant | Enforcement |
|-----------|-------------|
| Physics gates in fp32 | Context manager / policy |
| Loss masks are booleans | Schema |
| Grad clip inside JIT | optax / training policy |
| Determinism | Pin JAX stack; threefry; documented CUBLAS workspace policy |
| Official entropy unknown to miners pre-commit | Registered `BeaconProvider` supplies exact 32-byte `OfficialEntropy`; RFC 5869 HKDF-SHA-256 derives role seeds; production provider/timing/finality remain unresolved until ratified |
| Eval generator immutable per challenge version | Challenge registry |
| Hard gates | Binary; zero score on fail |
| Train ≠ eval distribution | Extended stress envelope |
| Score Pack hash pinned | Challenge registry + `Scoring.md` |
| **No full SKU on miner API** | Dual egress |
| **No commercial SKU without product battery** | Grounding gate |
| Landscape never overrides gates | Port law |
| **No L0 prior publish before Launch Bar** | `Launch_Bar.md` |

---

## 16. Launch checklist (abbrev.)

- [ ] fp32 gates enforced  
- [ ] Boolean loss masks  
- [ ] JIT grad clip  
- [ ] Determinism lockfile / pin set  
- [ ] Compile cache policy  
- [ ] Validator queue + health gates  
- [ ] Dual-egress audit  
- [ ] Grounding-gate enforcement on commercial export path  
- [ ] **Launch Bar green before public prior compounding**  
- [ ] Score Pack hashes pinned  
- [ ] Epistemic language review on external materials (gates vs estimates)

---

## 17. Schema and card contracts

Strategy schemas v1.0 / v1.1 / v2.0 as in §8. Product-battery and Model Card extensions are versioned in Specialist Bank / Landscape contracts. Score Pack schema: [`Scoring.md`](./Design_Specs/Scoring.md).

---

## 18. Related documents

See the table at the top of this specification.

---

*This specification is intended to be scientifically rigorous and buildable. Lean exams keep search and emissions honest. Launch Bar keeps the knowledge layer from compounding unfinished labels. Landscape compounds under explicit port law and epistemic discipline. The Specialist Bank ships only gauntlet-verified products. Implementation must not collapse these layers into teacher-checkpoint distillation or pay-to-compete.*
