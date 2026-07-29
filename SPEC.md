# Carbon -- A Physics Intelligence Subnet

**Spec alignment note (July 2026):** Productization uses a **dual threshold** (lean validator exams vs job-shaped product battery at Specialist Bank graduation). Landscape is a **four-port knowledge flywheel**, not a teacher-distillation step. Lean scoring formulas and challenge-bound Score Bank: [`appendices/Scoring.md`](./appendices/Scoring.md). **Launch Bar** ([`appendices/Launch_Bar.md`](./appendices/Launch_Bar.md)) must be green before Landscape L0 public prior publish — the flywheel must not compound unfinished labels. Canonical detail: `appendices/Landscape_Agent.md` (v1.2+), `appendices/Specialist_Bank.md` (v1.3+), `appendices/Use_Cases_by_Phase.md`.

---

## 1. Executive Summary

Carbon is a Bittensor subnet that operates a **decentralized verification layer for physics-informed neural operator surrogates**. It coordinates a network of miners and autonomous agents to discover optimal training strategies for Neural Operators (FNO, GINO, WNO, Transolver) under rigorous, trustless adversarial validation.

**Core Innovation**: Miners submit training strategies (loss configurations, curricula, architectures, data generation parameters). Validators execute full deterministic training from scratch on hidden, procedurally generated data, evaluating against hard physics gates. Verified **Model Cards** feed the Landscape Agent, which compounds symbolic and causal insight and routes it back as noisy search priors, eval efficiency signals, incentive proposals, and — only after a **verification gauntlet** — commercial specialists.

**Lead capability (raise / pre-launch):** trustless verification + dual threshold + sponsored path.  
**Landscape:** designed four-port compounding architecture (build-ordered) — not a pre-launch live brain. Public L0 priors only after Launch Bar green.

**What the network produces (product lens)**  
Envelope-qualified **solution maps** (problem setup → physical fields) for jobs engineers already run: **inverse design**, **plant-style / real-time response**, **exploration & UQ**, and **hybrid truth** (dense surrogate queries + sparse high-fidelity anchors). See `appendices/Use_Cases_by_Phase.md`.

**Dual threshold (non-negotiable)**

| Path | What it grades | Outcome |
|------|----------------|--------|
| **Miner → validator (lean)** | Physics gates, stress, short rollout, Model Card | Emissions / leaderboard — **search stays cheap** |
| **Landscape → Specialist Bank** | Effect-based recipe → controlled retrain → **product battery** (inverse-design bakeoff, deep rollout/plant suite, adversarial stress, latency, ONNX, escalation notes) | **Commercial SKU** — shelf credibility |

Leaderboard rank ≠ shelf product. No commercial full specialist ships without the product battery. No pay-to-compete.

**Knowledge flywheel (Landscape)**

```text
Model Cards (lean verified)
        → private graph (causal / symbolic / failures / promotion outcomes)
        → Port A: noisy priors to miners     (search compounds)
        → Port B: eval routing (validators)  (GPU compounds; floor rules)
        → Port C: challenge weight proposals (incentives aim where EV remains)
        → Port D: gauntlet-gated specialists (revenue + better priors from banked regimes)
        → more cards → …
```

**Epistemic line:** Hard gates (when Launch Bar green) are protocol truth. Causal bands are observational estimates — never spoken with gate-level certainty.

Export law for Port D: ***Ground truth in. Verified knowledge out.*** No teacher-checkpoint distillation; recipes from stable effects; re-execute; grounding gate or no ship.

**Carbon's Position in the Physics-AI Stack**:

```
┌─────────────────────────────────────────────────────────────────┐
│                    PHYSICS-AI STACK                             │
├─────────────────────────────────────────────────────────────────┤
│  COMPUTE LAYER          │ NVIDIA (H100, Blackwell, CUDA,        │
│                         │  TensorRT, Apollo, Cosmos)            │
│                         │ Demand generator — not competitor      │
├─────────────────────────┼───────────────────────────────────────┤
│  MODEL SUPPLY LAYER     │ **CARBON** (Decentralized, Verified,  │
│                         │  Compounding, Trustless)               │
│                         │ Lean exams + gauntlet-gated products   │
├─────────────────────────┼───────────────────────────────────────┤
│  TOOLING/DEPLOYMENT     │ Ansys, Siemens, Dyad, Dassault,      │
│                         │ nTop, Rescale                          │
│                         │ Consumers of Carbon's model supply    │
├─────────────────────────┼───────────────────────────────────────┤
│  END USERS              │ Aero/Auto/Energy/Defense — Digital    │
│                         │ Twins, HIL, Design Optimization,      │
│                         │ hybrid truth loops                    │
└─────────────────────────────────────────────────────────────────┘
```

*Implementation details: `IMPLEMENTATION.md`. Landscape / bank / scoring: appendices cited above.*

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    CARBON SUBNET ARCHITECTURE                   │
├─────────────────────────────────────────────────────────────────┤
│  MINERS / AGENTS                                                │
│  ├─ MCP Layer (Model Context Protocol)                          │
│  │  ├─ Estimation Mode (near-zero cost screening)               │
│  │  ├─ Light Training Mode (reduced budget + local eval)        │
│  │  └─ Full Submission (strategy JSON → validator)              │
│  └─ Miner Toolkit (Docker + Python SDK + cost estimation)      │
├─────────────────────────────────────────────────────────────────┤
│  VALIDATORS                            │
│  ├─ Trustless Procedural Data Generation (seeded by block hash) │
│  ├─ Multi-Fidelity Pipeline:                                    │
│  │  ├─ Tier 1: Fast stress filter                               │
│  │  └─ Tier 2: Full hidden adversarial + physics gates         │
│  ├─ Short rollout stability (lean plant signal)                 │
│  ├─ Score Pack load (challenge-bound; see Scoring.md)           │
│  └─ Model Card generation (provenance → Landscape ingest)      │
├─────────────────────────────────────────────────────────────────┤
│  GROUND TRUTH ORACLE (Julia/SciML Service)                     │
│  ├─ DifferentialEquations.jl / SciMLSensitivity.jl              │
│  ├─ ModelingToolkit.jl (symbolic loss terms)                    │
│  └─ NeuralPDE / MethodOfLines baselines as needed               │
├─────────────────────────────────────────────────────────────────┤
│  LANDSCAPE AGENT (Knowledge Flywheel — four ports)              │
│  ├─ Graph: cards, effects, failures, promotion/PB outcomes      │
│  ├─ Port A Search: noisy priors, masks, diagnostics             │
│  ├─ Port B Eval: progressive depth, adaptive stress (private)   │
│  ├─ Port C Economy: weight / bounty *proposals* only            │
│  └─ Port D Product: opportunity rank → Specialist Bank gauntlet │
├─────────────────────────────────────────────────────────────────┤
│  SPECIALIST BANK (Port D execution)                             │
│  ├─ Effect-synthesized recipes (not single-winner clones)       │
│  ├─ Controlled retrain + product battery                        │
│  └─ Dual egress: noisy miner derivatives | closed commercial SKU│
├─────────────────────────────────────────────────────────────────┤
│  INCENTIVES (Yuma Consensus + ChallengeWinnerTracker)           │
│  ├─ Winner-heavy + exponential decay (lean scores only)         │
│  ├─ Future: Breakthrough Bounties + Decaying Top stipends       │
│  └─ Treasury for unclaimed allocations                          │
└─────────────────────────────────────────────────────────────────┘
```

### 2.1 Dual Egress (Specialist artifacts)

| Path | Who | What they get |
|------|-----|---------------|
| **Public / miner** | Miners, agents | Noisy, lagged prior / warm-start **derivatives only** — never full weights or exact bank recipe |
| **Commercial** | Buyers | Closed SKU = ONNX + exact recipe + Model Card + **product-battery certs** + license + updates (+ optional air-gap) |

Competition scoring **never** depends on purchasing the commercial path.

### 2.2 Flywheel loop (why Landscape is real)

1. **Ingest** lean-verified Model Cards (and later promotion/PB outcomes).  
2. **Fit** symbolic (PySR→MT) and causal (Double ML) structure offline/batch.  
3. **Route**  
   - A: orient agent search without leaking the moat  
   - B: spend validator GPU where it matters (under Port B floor rules)  
   - C: aim emissions at unsaturated high-upside regimes  
   - D: queue regimes with dense causal support for **gauntlet productization**  
4. **Bank** only what re-trains and passes job-shaped tests.  
5. **Feed back** banked regimes into noisier priors and better challenge design — search quality rises without opening eval outcomes for sale.

Success metrics for the flywheel: post-gate progress, PB pass rates, commercial conversion — **not** guidance-API engagement. Landscape never overrides gates. **L0 public publish only after Launch Bar green.**

---

## 3. Trustless Verification & Data Generation System

### Core Principles

- **Procedural generation at runtime**: All evaluation data (stress testing and benchmark/held-out) is generated at runtime using open-source generators.
- **Public unpredictable seeding**: Generation seeded by `hash(challenge_id + block_hash + run_nonce)` (Phase 0); moving toward commit-reveal + drand in Phase 1B+.
- **Auditable by anyone**: Generator code is open-source; anyone can reproduce evaluation data given the seed.
- **Scientific credibility**: Generator parameter ranges have documented physical justification; validated against high-fidelity reference solvers (FEniCS, OpenFOAM, SU2, DPLR, US3D, **DifferentialEquations.jl**).
- **No fixed reference datasets**: Primary evaluation data is procedurally generated to preserve trustlessness; fixed datasets used only for generator validation.
- **Ground Truth Oracle**: **Julia/SciML Service** provides mathematically rigorous reference solutions via DifferentialEquations.jl, adjoint sensitivities via SciMLSensitivity.jl, and symbolic loss terms via ModelingToolkit.jl.

See `TRUSTLESS_VERIFICATION_AND_DATA_GENERATION.md` for the full design, including the Proprietary Data Handling Plan (Section 8).

---

## 4. Dual-Regime Architecture (DoD/Regulated Markets)

Carbon operates a **Dual-Regime Model Supply** for defense and regulated domains:

```
┌─────────────────────────────────────────────────────────────────┐
│  PUBLIC REGIME (Carbon Subnet)                                  │
│  ├─ Discovers strategies on public/synthetic data               │
│  ├─ Adversarial verification + physics gates                    │
│  ├─ Outputs: Strategy.json + Model Card + (after gauntlet) ONNX │
│  └─ Zero ITAR/controlled data                                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                    CROSS-DOMAIN SOLUTION / SECURE TRANSFER
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  CLASSIFIED REGIME (Prime Enclave IL5/IL6)                      │
│  ├─ Ingests architecture blueprint (strategy.json)              │
│  ├─ Fine-tunes on classified telemetry / proprietary geometry   │
│  ├─ Re-runs product battery policy where required               │
│  ├─ Deploys ONNX locally (HIL, edge, air-gapped)                │
│  ├─ Runs inference LOCALLY — zero network calls                 │
│  ├─ Applies ITAR/EAR classification (Prime's ECO)               │
│  └─ Packages DI-SESS-82483 deliverable + ATO artifacts          │
└─────────────────────────────────────────────────────────────────┘
```

**Data Handling Phases**:
- **Phase 0-1B**: Public + synthetic data only. No proprietary data enters the network.
- **Phase 2A**: Customer-controlled local fine-tuning with custom datasets (Abaqus ODB). Raw data never leaves customer control; commercial adapters **re-pass product battery** after adapt.
- **Phase 2B**: Air-Gapped Miner Toolkit v1 for classified enclaves (IL5/IL6). Zero network dependencies.
- **Phase 3+**: Confidential Computing (NVIDIA H100 TEEs) on validator side for sensitive workloads (as adopted).
- **Julia/SciML Service**: Deployable in both regimes (air-gapped Julia deployment for classified regime).

---

## 5. Miner Compute, Local Iteration & Submission Model

### Core Philosophy

- **Validator authority**: The validator always performs full deterministic training + hidden adversarial stress evaluation identically for every submission (**lean path**).
- **Miner autonomy**: Miners/agents run local iterative training loops on their own hardware to improve strategies before submission.
- **Zero-friction submission**: Submission is always free; local training is an *optional enhancement*, not a requirement.
- **Moat protection**: Only noisy priors are distributed (never the clean champion or full bank SKU). High-value Landscape knowledge (raw causal graphs, DML outputs, PB seeds) remains protected.

### Three-Tier Local System

| Tier | Compute Cost | Anchored To | Purpose | Required Before Submission? |
|------|-------------|-------------|---------|----------------------------|
| **Estimation Mode** | Near-zero | Noisy Prior | Rapid idea screening & filtering | No |
| **Light Training Mode** | Low | Noisy Prior | Main iterative improvement loop | No (recommended) |
| **Validator (Official)** | Network-paid | Full hidden data | Official scoring + emissions | Yes |

**Key Rule**: A miner can submit a strategy JSON at any time with zero local training.

### Data & Stress Separation (Critical Security Boundary)

| Aspect | Miner Local Loops | Validator Official Evaluation |
|--------|-------------------|-------------------------------|
| **Data** | Procedural + custom datasets; different seeds | Procedural (validator config only); hidden seeds |
| **Stress Tests** | Reduced, non-hidden variants | Full hidden stress variant set |
| **Physics Gates** | Optional, for learning signal | Mandatory; hard fail = zero score |
| **Data Visibility** | Miner controls | **Never exposed to miners** |

This separation preserves adversarial integrity: miners optimize for training distribution; validators evaluate on hidden, procedurally generated distribution with hard physics gates.

---

## 5b. Three-Tier Participation (MCP Layer)

| Mode | Compute | Purpose | Leaderboard Impact |
|------|---------|---------|-------------------|
| **Estimation Mode** | Near-zero (CPU, <100ms) | Rapid screening via linear sensitivity around noisy prior | None (logged, lower Landscape weight) |
| **Light Training** | Low (1-4 GPU-hrs) | Main iteration loop; gates on local data | None (logged, lower Landscape weight) |
| **Full Submission** | Network-paid | Official scoring + emissions | **Only path to emissions weight** |

*Implementation details in `IMPLEMENTATION.md`.*

---

## 6. Challenges by Phase (Capability-Gated)

### Phase Transition Criteria (All Gates Must Pass)

| Transition | Entry Gate (ALL Required) | Meaning |
|------------|---------------------------|---------|
| **0 → 1A** | 5 validators (99% uptime), 7 PDEs mesh-converged vs FEniCS/DifferentialEquations.jl, 3 backbones, Model Zoo / catalog path live, pilot demand signal | Subnet operational — verification layer live |
| **1A → 1B** | 2 defense benchmarks mesh-converged + turb UQ framework, Factory v1 live, 1+ Tier 2 LOI | Compressible flow verified — Factory revenue live |
| **1B → 2A** | 4 defense benchmarks (turb UQ + chem UQ), Factory hardened, Prime teaming, SBIR I submitted | Defense breadth + Factory hardened |
| **2A → 2B** | Schema v1.1 live (LoRA + Custom Data + MT Losses), Specialist Bank gauntlet path live, DML flowing, Tier 1 traction | Customization + Intelligence live |
| **2B → 3** | Air-Gap Toolkit v1 in 2+ enclaves, preCICE sidecar tested on sequential FSI, Coupling convergence validated | Classified-ready + Coupling architected |
| **3 → 4** | 3 coupled benchmarks live (coupling gates passing), preCICE production on validators, SBIR II / Tier 4 signal | Coupled physics supply chain live |
| **4 → 5** | 3D turbulence benchmarks live, curriculum proven, production contracts / ARR gate | Production-grade 3D turbulence |

> **Phase jumps are capability-gated, not calendar-gated.**

### Phase Overview

| Phase | Name | Physics Scope | Challenge Types | Schema | Revenue |
|-------|------|---------------|-----------------|--------|---------|
| **0** | **Foundation** | 7 Academic PDEs | Base (7) | v1.0 | Catalog specialists (Tier 1) |
| **1A** | **Compressible Flow** | 7 Academic + 2 Defense | Base + Hosted | v1.0 | Tier 1 + Tier 2 |
| **1B** | **Reacting Flow + Sequential FSI** | + 4 Defense | Base + Hosted | v1.0 | Tier 1–3 |
| **2A** | **Customization & Intelligence** | + Custom | + LoRA + Custom Data + MT | v1.1 | Tier 1–3 + adapters |
| **2B** | **Air-Gap + Coupling Prep** | + Custom | + Air-Gap + preCICE arch | v1.1 | Tier 4 pilot |
| **3** | **Multi-Physics Coupling** | Coupled | Composite v2.0 | v2.0 | Tier 4 + SBIR II |
| **4** | **Production** | 3D + Turbulence | All + 3D/Turb | v2.0+ | Production |

### Phase 0: Foundation (7 Academic PDEs)

| ID | Problem | Dimension | Key Physics |
|----|---------|-----------|-------------|
| 1 | Poisson | 2D/3D | Elliptic, source-driven |
| 2 | Darcy | 2D/3D | Elliptic, heterogeneous media |
| 3 | Burgers | 2D | Hyperbolic, shock formation |
| 4 | Navier-Stokes (laminar) | 2D/3D | Incompressible flow, div-free |
| 5 | Heat | 2D | Parabolic, transient conduction |
| 6 | Linear Elasticity | 2D | Vector mechanics, equilibrium |
| 7 | Thermo-Elasticity | 2D | Coupled thermal-mechanical |

**Mesh/Temporal Convergence Required**: 3-level h-refinement; validated vs FEniCS/DifferentialEquations.jl.

**Productization in Phase 0:** Catalog specialists still run the **product battery** (even on academic PDEs) so the gauntlet muscle exists before OEM regimes — credibility SKUs, not optional theater.

### Phase 1A–4

Physics additions, schema evolution, air-gap, coupling, and 3D/turbulence challenges remain as previously specified (NACA/CRM, HIFiRE, Turek/Hron sequential, store separation, CHT, preCICE composites, 3D turbulence). Sponsored challenges may **extend product-battery definitions** in the challenge brief (`product_jobs`: inverse_design, plant, uq, …).

---

## 7. Miner Controls (Strategy Schema Evolution)

| Schema | Phase | Key Fields | Backward Compatible |
|--------|-------|------------|---------------------|
| **v1.0** | Phase 0–1B | `backbone`, `training`, `loss` (enabled booleans), `curriculum`, `data` | Base |
| **v1.1** | Phase 2A–2B | + `lora`, `custom_dataset`, `structured_losses`, `data_generation` | ✅ optional |
| **v2.0** | Phase 3 | `composite`, `sub_strategies`, `coupling`, `coupling_gates` | ❌ new |
| **v2.0+** | Phase 4 | + turbulence / 3d curriculum fields | ✅ |

**Entropy floor** on miner `generator_params` remains mandatory (anti-gaming).

---

## 8. Validation Strategy (Lean Path)

### Scoring (canonical detail)

**Formulas, Score Pack schema, validator load path, per-challenge bank:** [`appendices/Scoring.md`](./appendices/Scoring.md).

Lean labels are the **trust root** for Landscape ingest. Unfinished gates/scores → no verified compounding claims (`Launch_Bar.md`).

| Component | Weight | Composition |
|-----------|--------|-------------|
| **Physics Fidelity** | 45% | Weighted gate **margins** (residual, conservation, short rollout, … per Score Pack) |
| **Robustness** | 30% | Stress categories: mean/tail blend + weakest-category pressure |
| **Accuracy** | 25% | Normalized held-out field error |

**Challenge binding:** Validator loads Score Pack + Generator Pack by registered `(challenge_id, scoring_version, generator_version)` content hashes — **no silent default exam**.

**Not in lean score:** training loss, product battery, Landscape similarity, prior distance.

### Physics Gates (Hard — Zero Score on Failure)

| Gate | Phase | Notes |
|------|-------|-------|
| Mass Conservation | 0+ | Hard |
| Energy Stability | 0+ | Hard |
| Boundary Satisfaction | 0+ | Hard |
| **Rollout Stability (short)** | 0+ | Lean multi-step / stability signal — **not** full HIL-horizon plant suite |
| Shock Capture / Turbulence UQ / Species / Chemistry / FSI / Coupling / 3D turb gates | 1A–4 | As regime requires |

**Hard Gate Rule**: Any mandatory FAIL → total score = 0.

**UQ policy (honest phasing)**  
- **Phase 0–1A lean path:** stress margins + failure atlas on cards; conformal/ensemble **not** a universal hard gate for every submission.  
- **Product / specialist tier:** KPI conformal or ensemble bands where `product_jobs` include UQ or safety-margin claims.  
- **Turbulence/Chemistry model-form UQ:** remains part of **regime gate margins** when those challenges are live (1A/1B+), separate from “every PoC card must ship 95% conformal fields.”

### ChallengeWinnerTracker

```text
weight = lean_score * exp(-blocks_since_win / half_life)
```

Emissions follow **lean validator outcomes only**. Product-battery status does not mint emissions and is not required to compete.

---

## 9. Data Generation Architecture

Seed map, train≠eval separation, stress categories (≥95% coverage), and custom dataset validation remain as specified. Critical invariant: `stress_seed` unknown to miners until evaluation; validator generator config ignores miner eval params. Score Pack robustness category IDs must align with Generator Pack categories (`Scoring.md` + `Data_Management.md`).

---

## 10. Landscape Agent (Knowledge Flywheel)

Canonical build guide: **`appendices/Landscape_Agent.md` (v1.2+)**.  
Launch prerequisites: **`appendices/Launch_Bar.md`**.  
Canonical product path: **`appendices/Specialist_Bank.md` (v1.3+)**.  
Scoring labels: **`appendices/Scoring.md`**.

### Role

Landscape is Carbon’s **batch intelligence system with four controlled ports** — not a live strategy oracle and not a teacher-distillation factory.

| Port | Consumer | Leaves the building |
|------|----------|---------------------|
| **A Search** | Miners / agents | Noisy priors, causal masks, diagnostics |
| **B Eval** | Validators only | Progressive depth, adaptive stress (private; **floor rules**) |
| **C Economy** | Governance | Challenge-weight / bounty *proposals* |
| **D Product** | OpCo / bank | Opportunity specs → gauntlet → closed SKUs / briefs / sealed packs |

**Epistemic split:** gates = protocol truth (when Launch Bar green); causal bands = observational estimates — never gate-level certainty language.

### What compounds

| Private asset | Flywheel effect |
|---------------|-----------------|
| Model Card lake (D1) | Reproducible feature store for fits |
| Symbolic library (D2) | Structured loss templates into priors / recipes |
| Causal effects (D3) | Masks + bands for search; module targets for bank |
| Failure atlas (D4) | Diagnostics + stress evolution |
| Frontier map (D5) | Emission proposals toward unsaturated boards |
| Promotion / PB graph (D11) | Repair loop; opportunity rank prefers regimes that graduate |

### Port D export law (SPEC-level)

```text
ship_commercial_full_sku =
    lineage(landscape evidence)
    AND controlled_retrain_pass
    AND product_battery_pass
    AND dual_egress_policy
```

Anti-patterns banned for commercial export: teacher weight copy, single-winner JSON as sole recipe, ship without PB report.

### Phasing (summary)

| Landscape phase | Unlock |
|-----------------|--------|
| L0 | Card lake + daily noisy priors (**after Launch Bar green**) |
| L1 | Symbolic + failure atlas |
| L2 | Causal core + opportunity ranker → bank queue |
| L3 | Eval + economy ports (Port B floors enforced) |
| L4 | Full Port D gauntlet integration + air-gap packs |

---

## 11. Specialist Bank & Commercial GTM

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

Detail and module-type exceptions: `Specialist_Bank.md`.

### Revenue engines

| Engine | Product | Notes |
|--------|---------|-------|
| **Tier 1 Specialist Bank** | Closed ONNX + recipe + card + **PB certs** + license | Catalog credibility → regime value |
| **Tier 2–4 Sponsored Challenges** | Open / IP-licensed / private | May define extra PB tests; creates regimes bank lacks |
| **DoD / SBIR path** | Evidence packages | Dual-regime; sealed packs |
| **Verification registry** | Attestation / card API | Artifact remains licensed |

**Conservative principle:** open the verification *standard* and coarse catalog; close the certified artifact and rights/ops around it.

---

## 12. Incentives & Tokenomics

ChallengeWinnerTracker on **lean scores**; participation dust; future bounties; treasury for unclaimed. Landscape similarity is **forbidden** as a direct score term.

---

## 13. Miner Toolkit & Submission Interface

Docker toolkit, `carbon-miner` CLI, and Async SDK patterns remain as specified. MCP exposes `get_noisy_prior` and diagnostics — **not** full specialist download.

---

## 14. Validator Operations & Economics

Hardware tables, health gates, and queue priority (sponsored > high rep > standard) remain operational guidance. Product-battery runs are **promotion-time** workloads scheduled by bank/OpCo, not unbounded per-submission defaults.

---

## 15. Security & Correctness Guarantees

| Invariant | Enforcement |
|-----------|-------------|
| Physics gates in fp32 | Context manager |
| Loss masks are booleans | Schema |
| Grad clip inside JIT | optax |
| Determinism | Pin jax stack; threefry; CUBLAS workspace |
| Eval seed unknown to miners | block-hash derivation |
| Eval generator immutable | Challenge Spec |
| Hard gates | Binary; zero score on fail |
| Train ≠ eval distribution | Extended stress envelope |
| Score Pack hash pinned | Challenge registry + `Scoring.md` |
| **No full SKU on miner API** | Dual egress |
| **No commercial SKU without PB** | Grounding gate |
| Landscape never overrides gates | Port law |
| **No L0 prior publish before Launch Bar** | `Launch_Bar.md` |

---

## 16. Phase Timeline Summary (Capability-Gated)

Estimates only; transitions follow §6 gates. Early revenue is catalog + sponsored; margin concentrates as regimes and license privacy increase.

---

## 17. Appendix: Key Schemas

Strategy schemas v1.0 / v1.1 / v2.0 remain as previously defined (`backbone`, boolean loss enables, optional LoRA/custom_dataset/structured_losses, composite coupling). Product-battery and Model Card extensions are versioned in Specialist Bank / Landscape contracts. Score Pack schema: `Scoring.md`.

---

## 18. Security Checklist (Launch)

fp32 gates, boolean loss masks, JIT grad clip, determinism lockfile, compile cache, validator queue, dual-egress audit, grounding-gate enforcement on commercial export path, **Launch Bar green before public prior compounding**, Score Pack hashes pinned, epistemic language review on external materials.

---

## 19. Related Documents

| Doc | Role |
|-----|------|
| `appendices/Scoring.md` | Lean formulas, Score Bank, validator load path |
| `appendices/Launch_Bar.md` | Stop-ship before Landscape L0 publish |
| `appendices/Landscape_Agent.md` | Four ports, epistemic status, Port B floors |
| `appendices/Specialist_Bank.md` | Gauntlet, dual egress, phase customers |
| `appendices/Use_Cases_by_Phase.md` | Inverse design / plant / UQ / hybrid truth teaching |
| `appendices/Data_Management.md` | Seeds, train≠eval |
| `IMPLEMENTATION.md` | Code-level patterns |
| Trustless verification appendix | Generators, seeds, proprietary data plan |

---

*This specification is scientifically rigorous and buildable. Lean exams keep search and emissions honest; Launch Bar keeps the flywheel from compounding bad labels; Landscape compounds under epistemic discipline; the Specialist Bank ships only gauntlet-verified products. Implementation must not collapse those layers into teacher-checkpoint distillation or pay-to-compete.*
