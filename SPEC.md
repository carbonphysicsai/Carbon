# Carbon — Protocol Specification

**A Bittensor subnet for trustless verification of physics-informed neural operator training strategies**

**Status:** Phase 0 foundations + offline PoC. Landscape and commercial layers are **build-ordered** — not assumed live at launch.

**Canonical companions**

| Doc | Role |
|-----|------|
| [`Design Specs/Scoring.md`](./Design Specs/Scoring.md) | Lean formulas, Score Bank, validator load path |
| [`Design Specs/Launch_Bar.md`](./Design Specs/Launch_Bar.md) | Stop-ship before public prior publish |
| [`Design Specs/Landscape_Agent.md`](./Design Specs/Landscape_Agent.md) | Four-port knowledge architecture (v1.2+) |
| [`Design Specs/Specialist_Bank.md`](./Design Specs/Specialist_Bank.md) | Product gauntlet, dual egress (v1.3+) |
| [`Design Specs/Use_Cases_by_Phase.md`](./Design Specs/Use_Cases_by_Phase.md) | Inverse design / plant / UQ / hybrid truth |
| [`Design Specs/Data_Management.md`](./Design Specs/Data_Management.md) | Seeds, train ≠ eval |
| [`Design Specs/Trustless_Verification.md`](./Design Specs/Trustless_Verification.md) | Generators, seeds, proprietary data plan |
| [`Design Specs/Implementation.md`](./Design Specs/Implementation.md) / `IMPLEMENTATION.md` | Code-level patterns |
| [`Design Specs/Compute_Optimization.md`](./Design Specs/Compute_Optimization.md) | Compute strategy |
| [`Design Specs/JAX_Optimization.md`](./Design Specs/JAX_Optimization.md) | Validator JAX efficiency |
| [`Design Specs/Operations.md`](./Design Specs/Operations.md) | Deploy / ops |

---

## 1. Executive summary

Carbon coordinates miners and agents to discover training strategies for neural operators (FNO, GINO, WNO, Transolver, and successors). Validators retrain and evaluate those strategies on hidden, procedurally generated data under hard physics gates. Emissions follow that independent score — not self-reported metrics.

**Core loop:** Miners submit training strategies (loss configurations, curricula, architectures, data-generation parameters). Validators execute deterministic training from scratch on hidden procedural data, evaluate against hard physics gates and challenge-bound Score Packs, and emit Model Cards. Verified cards later feed a knowledge layer that compounds insight under strict publish rules and, only after a verification gauntlet, commercial specialists.

Traditional neural operators are dominated by accuracy-driven objectives. They may solve overfitting, but the objective still drives them toward accuracy and learning data, which is why they struggle with real physics in deployment. Carbon changes the optimization target because physics gates, fidelity, and model robustness are weighted more than pure training loss accuracy in the final score. We are driving miners at training strategies that survive a different objective, and learning from them. That is the valuable work Carbon is paying for and that the validators are pressure-testing. It is plausible that the Pareto front of methods under hard physics + stress differs from those under pure accuracy, and Bittensor miners are the right tool for finding it.

The training data and evaluation criteria are generated in real time, seed-triggered, impossible for the miners to know ahead of time, challenge-specific, fully auditable, and verified against real physics and real simulation tools. Every training run generates a Model Card that has every valuable piece of data from how it was trained, how accurate it was, and how it scored on the real physics testing. The data is used to return value to miners, improve the evaluation, improve challenge design, and develop industry deployable models.

**What the network optimizes for**  
Training methods that survive stress and physical constraints — not low loss on a fixed public set.

**What the network eventually supplies**  
Envelope-qualified solution maps (problem setup → physical fields) for jobs engineers already run: inverse design, plant-style / real-time response, exploration & UQ, and hybrid truth (dense surrogate queries + sparse high-fidelity anchors). See [`Use_Cases_by_Phase.md`](./Design Specs/Use_Cases_by_Phase.md).

### Dual threshold (non-negotiable)

| Path | What it grades | Outcome |
|------|----------------|--------|
| **Miner → validator (lean)** | Physics gates, stress, short rollout, Model Card | Emissions / leaderboard — **search stays cheap** |
| **Promotion → commercial (Specialist Bank)** | Effect-based recipe → controlled retrain → **product battery** (inverse-design bakeoff, deep rollout/plant suite, adversarial stress, latency, ONNX, escalation notes) | **Commercial SKU** — shelf credibility |

Leaderboard rank ≠ shelf product. No commercial full specialist ships without the product battery. No pay-to-compete.

**Lead capability (raise / pre-launch):** trustless verification + dual threshold + sponsored path.  
**Knowledge layer (Landscape):** designed four-port compounding architecture — **build-ordered**, not a pre-launch live brain. Public L0 priors only after [`Launch_Bar.md`](./Design Specs/Launch_Bar.md) is green.

**Epistemic line:** Hard gates (when Launch Bar is green) are protocol truth. Causal bands are observational estimates — never spoken with gate-level certainty.

**Port D export law:** *Ground truth in. Verified knowledge out.* No teacher-checkpoint distillation; recipes from stable effects; re-execute; grounding gate or no ship.

---

## 2. Position in the physics-AI stack

```
COMPUTE LAYER       NVIDIA (CUDA, TensorRT, PhysicsNeMo / Apollo-class stacks)
                      → demand generator — not Carbon’s product

MODEL SUPPLY LAYER  **CARBON**
                      → decentralized strategy search
                      → independent exams (lean)
                      → gauntlet-gated commercial artifacts (later)

TOOLING/DEPLOYMENT  Ansys, Siemens, Dyad, Dassault, nTop, Rescale, …
                      → consumers of verified supply / export paths

END USERS           Aero / auto / energy / defense — digital twins, HIL,
                      design optimization, hybrid truth loops
```

Carbon does not replace the GPU vendor or the CAE seat. It owns discovery of training methods under an exam the producer does not control, with a hard line between competition results and sold artifacts. Bittensor works because the Carbon objective is mathematical and fail-closed, validation can be independent of the incentivized producer, and agentic search can scale discovery without a single lab owning both the training and the answer key. It enables an intelligence flywheel by re-feeding miners winning strategy clues. The Bittensor mechanism allows Carbon to provide trustless verification for surrogate models that must be trusted in high-risk environments where physics breakdowns are very expensive and not optional. The open source and auditable training and evaluation mechanism is exactly what a chief engineer needs to defend the deployment of Carbon’s physics models.

---

## 3. System architecture

```
MINERS / AGENTS
  ├─ Optional local loop: noisy leader insight → estimate → light train → submit
  ├─ Strategy JSON (schema-versioned)
  └─ Toolkit: Docker + SDK + cost hints

VALIDATORS
  ├─ Procedural data (seeded; train ≠ eval ≠ stress)
  ├─ Multi-fidelity path: fast stress filter → full hidden exam + physics gates
  ├─ Short rollout stability (lean plant signal)
  ├─ Challenge-bound Score Pack
  └─ Model Card (provenance → later Landscape ingest)

GROUND TRUTH ORACLE (as needed)
  ├─ DifferentialEquations.jl / SciMLSensitivity.jl
  ├─ ModelingToolkit.jl (structured losses)
  └─ Mesh-converged references (FEniCS, OpenFOAM, SU2, …) for generator validation

LANDSCAPE AGENT (after Launch Bar)
  ├─ Private graph: cards, effects, failures, promotion / product-battery outcomes
  ├─ Port A Search: noisy priors, masks, diagnostics → miners
  ├─ Port B Eval: progressive depth, adaptive stress → validators (private; floor rules)
  ├─ Port C Economy: challenge-weight / bounty *proposals* only
  └─ Port D Product: opportunity rank → Specialist Bank gauntlet

SPECIALIST BANK (Port D execution)
  ├─ Effect-synthesized recipes (not single-winner clones)
  ├─ Controlled retrain + product battery
  └─ Dual egress: noisy miner derivatives | closed commercial SKU

INCENTIVES
  ├─ Lean scores only → weights / emissions (winner-heavy decay)
  └─ Landscape similarity never a score term
```

### 3.1 Dual egress (specialist artifacts)

| Path | Who | What they get |
|------|-----|---------------|
| **Public / miner** | Miners, agents | Noisy, lagged prior / warm-start **derivatives only** — never full weights or exact bank recipe |
| **Commercial** | Buyers | Closed SKU = ONNX (or approved) + exact recipe + Model Card + **product-battery certs** + license + updates (+ optional air-gap) |

Competition scoring **never** depends on purchasing the commercial path.

### 3.2 Flywheel loop (why Landscape is real)

1. **Ingest** lean-verified Model Cards (and later promotion / product-battery outcomes).  
2. **Fit** symbolic (e.g. PySR → ModelingToolkit) and causal (Double ML) structure offline / batch.  
3. **Route**  
   - A: orient agent search without leaking the moat  
   - B: spend validator GPU where it matters (under Port B floor rules)  
   - C: aim emissions at unsaturated high-upside regimes  
   - D: queue regimes with dense causal support for **gauntlet productization**  
4. **Bank** only what re-trains and passes job-shaped tests.  
5. **Feed back** banked regimes into noisier priors and better challenge design — search quality rises without opening eval outcomes for sale.

Success metrics: post-gate progress, product-battery pass rates, commercial conversion — **not** guidance-API engagement. Landscape never overrides gates. **L0 public publish only after Launch Bar green.**

The subnet team builds a knowledge graph of these Model Cards and uses them to retrain/retest and harden specialist models built for industry deployment. This process is purposely more rigorous than the mining evaluation. We want (mine → validate → feedback) to be fast, but we want to build real thorough due diligence into the models we are selling.

---

## 4. Trustless verification and data generation

### Core principles

- **Procedural generation at runtime:** Primary evaluation and stress data are generated at runtime with open-source generators.
- **Public unpredictable seeding:** Phase 0 uses `hash(challenge_id + block_hash + run_nonce)`; Phase 1B+ moves toward commit-reveal + drand-class randomness where useful.
- **Auditable by anyone:** Generator code is open; anyone can reproduce a draw given the seed.
- **Scientific credibility:** Parameter ranges need documented physical justification; generators validated against high-fidelity references (FEniCS, OpenFOAM, SU2, DPLR, US3D, **DifferentialEquations.jl**, and peers).
- **No fixed public benchmark as the live exam:** Fixed datasets may validate generators; they are not the miner-facing answer key.
- **Train ≠ eval ≠ stress:** Distributions and seeds are separated; miner local loops must not see validator eval seeds.

### Ground truth oracle

Julia/SciML (DifferentialEquations.jl, SciMLSensitivity.jl, ModelingToolkit.jl, NeuralPDE / MethodOfLines as needed) supplies reference solutions, adjoints, and structured loss hooks — for generator validation and optional structured losses, not as a substitute for the adversarial exam.

Full design including proprietary-data handling: [`Trustless_Verification.md`](./Design Specs/Trustless_Verification.md).

### Data generation invariants

- `stress_seed` unknown to miners until evaluation.
- Validator generator config ignores miner-supplied eval params.
- Score Pack robustness category IDs must align with Generator Pack categories ([`Scoring.md`](./Design Specs/Scoring.md) + [`Data_Management.md`](./Design Specs/Data_Management.md)).
- Stress category coverage targets remain as specified in Data Management (≥95% where defined).

---

## 5. Miner participation and local iteration

### Philosophy

- **Validator authority:** Every emissions path is a full lean exam on hidden data with hard gates.
- **Miner autonomy:** Local iteration is encouraged, never required.
- **Zero-friction submit:** Strategy JSON can be submitted with **no** local training.
- **Moat:** Public leader insight is **noisy and lagged** — not full champion weights, exact bank recipes, raw causal graphs, DML dumps, or product-battery seeds.

Mining is agentic auto research encouraged to lower the barrier to entry, raise the quality of submissions, and leverage network effects on the discovery end. An agent friendly front end (MCP) receives noisy feedback from the current challenge winner’s strategy (no full recipe or weights) to start with and provides estimated scoring impacts of the miner/agent’s local changes, allowing for AI solving at scale. Optional light training if miners want to pay to get an edge.

### Three tiers (local → official)

| Tier | Compute | Anchored to | Purpose | Emissions? |
|------|---------|-------------|---------|------------|
| **Estimation** | Near zero (CPU-class) | Noisy prior / last verified insight | Rapid screening (humans or agents) | No (may log at lower Landscape weight) |
| **Light training** | Low (optional GPU-hrs) | Same *kinds* of checks on **local** data | Main improve loop | No (may log at lower Landscape weight) |
| **Full submission** | Network-paid eval | Full hidden validator data | Official score | **Yes — only path** |

**Key rule:** A miner can submit at any time with zero local training. Paid or heavy local train is optional enhancement, not a gate to compete.

### Data and stress separation (critical security boundary)

| Aspect | Miner local loops | Validator official evaluation |
|--------|-------------------|-------------------------------|
| **Data** | Procedural + optional custom; different seeds | Procedural (validator config only); hidden seeds |
| **Stress tests** | Reduced, non-hidden variants | Full hidden stress variant set |
| **Physics gates** | Optional learning signal | Mandatory; hard fail → score 0 |
| **Data visibility** | Miner controls | **Never exposed to miners** |

Miners optimize against training distribution; validators grade on a hidden, procedural distribution with hard physics gates. Estimation never replaces the exam.

Implementation patterns: `IMPLEMENTATION.md` / [`Design Specs/Implementation.md`](./Design Specs/Implementation.md).

---

## 6. Lean validation and scoring

Canonical formulas, Score Pack schema, validator load path, per-challenge bank: **[`Design Specs/Scoring.md`](./Design Specs/Scoring.md)**.

Lean labels are the **trust root** for Landscape ingest. Unfinished gates or scores → no verified compounding claims ([`Launch_Bar.md`](./Design Specs/Launch_Bar.md)).

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

### Emissions mapping

```text
weight = lean_score * exp(-blocks_since_win / half_life)
```

Emissions follow **lean validator outcomes only**. Product-battery status does not mint emissions and is not required to compete.

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

| Schema | Phase | Key fields | Backward compatible |
|--------|-------|------------|---------------------|
| **v1.0** | Phase 0–1B | `backbone`, `training`, `loss` (enabled booleans), `curriculum`, `data` | Base |
| **v1.1** | Phase 2A–2B | + `lora`, `custom_dataset`, `structured_losses`, `data_generation` | Optional fields |
| **v2.0** | Phase 3 | `composite`, `sub_strategies`, `coupling`, `coupling_gates` | New major |
| **v2.0+** | Phase 4 | + turbulence / 3D curriculum fields | Additive |

**Entropy floor** on miner `generator_params` remains mandatory (anti-degenerate data gaming).

Full JSON field lists and training-image acceptance contracts live with implementation schema files / `IMPLEMENTATION.md`.

---

## 9. Landscape agent (knowledge flywheel)

Canonical build guide: **[`Design Specs/Landscape_Agent.md`](./Design Specs/Landscape_Agent.md) (v1.2+)**.  
Launch prerequisites: **[`Design Specs/Launch_Bar.md`](./Design Specs/Launch_Bar.md)**.  
Product path: **[`Design Specs/Specialist_Bank.md`](./Design Specs/Specialist_Bank.md) (v1.3+)**.  
Scoring labels: **[`Design Specs/Scoring.md`](./Design Specs/Scoring.md)**.

### Role

Landscape is Carbon’s batch intelligence system with four controlled ports — not a live strategy oracle and not a teacher-distillation factory.

| Port | Consumer | Leaves the building |
|------|----------|---------------------|
| **A Search** | Miners / agents | Noisy priors, causal masks, diagnostics |
| **B Eval** | Validators only | Progressive depth, adaptive stress (private; **floor rules**) |
| **C Economy** | Governance | Challenge-weight / bounty *proposals* |
| **D Product** | OpCo / bank | Opportunity specs → gauntlet → closed SKUs / briefs / sealed packs |

**Epistemic split:** Gates = protocol truth (when Launch Bar green). Causal bands = observational estimates — never gate-level certainty language.

### What compounds (private)

| Private asset | Flywheel effect |
|---------------|-----------------|
| Model Card lake (D1) | Reproducible feature store for fits |
| Symbolic library (D2) | Structured loss templates into priors / recipes |
| Causal effects (D3) | Masks + bands for search; module targets for bank |
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

**Banned for commercial export:** Teacher weight copy; single-winner JSON as sole recipe; ship without product-battery report.

### Landscape phases

| Landscape phase | Unlock |
|-----------------|--------|
| L0 | Card lake + daily noisy priors (**after Launch Bar green**) |
| L1 | Symbolic + failure atlas |
| L2 | Causal core + opportunity ranker → bank queue |
| L3 | Eval + economy ports (Port B floors enforced) |
| L4 | Full Port D gauntlet integration + air-gap packs |

---

## 10. Specialist Bank and commercial GTM

Canonical: **[`Design Specs/Specialist_Bank.md`](./Design Specs/Specialist_Bank.md)**.

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

- **ChallengeWinnerTracker** on **lean scores** with winner-heavy exponential decay.
- Participation dust optional; future breakthrough bounties and decaying top stipends; treasury for unclaimed allocations.
- **Forbidden as direct score terms:** Landscape similarity, prior distance, product-battery status.

---

## 13. Miner toolkit and submission interface

- Docker toolkit, `carbon-miner` CLI, and async SDK patterns as specified in implementation docs.
- Exposes `get_noisy_prior` and diagnostics — **not** full specialist download.
- Cost estimation hooks for optional local / rented train paths (e.g. Chutes, Targon) without making pay-to-train mandatory.

---

## 14. Validator operations and economics

- Hardware tables, health gates, and queue priority (**sponsored > high rep > standard**) remain operational guidance in [`Operations.md`](./Design Specs/Operations.md).
- Product-battery runs are **promotion-time** workloads scheduled by bank/OpCo — not unbounded per-submission defaults.
- Compute efficiency strategy: [`Compute_Optimization.md`](./Design Specs/Compute_Optimization.md), [`JAX_Optimization.md`](./Design Specs/JAX_Optimization.md).

---

## 15. Security and correctness invariants

| Invariant | Enforcement |
|-----------|-------------|
| Physics gates in fp32 | Context manager / policy |
| Loss masks are booleans | Schema |
| Grad clip inside JIT | optax / training policy |
| Determinism | Pin JAX stack; threefry; documented CUBLAS workspace policy |
| Eval seed unknown to miners pre-commit | Block-hash / commit-reveal design |
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

Strategy schemas v1.0 / v1.1 / v2.0 as in §8. Product-battery and Model Card extensions are versioned in Specialist Bank / Landscape contracts. Score Pack schema: [`Scoring.md`](./Design Specs/Scoring.md).

---

## 18. Related documents

See the table at the top of this specification.

---

*This specification is intended to be scientifically rigorous and buildable. Lean exams keep search and emissions honest. Launch Bar keeps the knowledge layer from compounding unfinished labels. Landscape compounds under explicit port law and epistemic discipline. The Specialist Bank ships only gauntlet-verified products. Implementation must not collapse these layers into teacher-checkpoint distillation or pay-to-compete.*
