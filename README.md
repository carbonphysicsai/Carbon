# Carbon

**Decentralized Incentive System for Physics-Informed Neural Operator Surrogates**

Carbon is a Bittensor subnet that builds a decentralized, agentic system where miners and autonomous agents collaboratively discover fast, robust, and physics-respecting training strategies for high-fidelity engineering surrogates. It combines an **MCP-powered participation layer with built-in testing loops**, a **rigorous hidden adversarial validation mechanism**, and a **Landscape Agent that compounds symbolic and causal knowledge** into a real flywheel — noisy search priors, smarter eval routing, better challenge design, and **gauntlet-gated commercial specialists**.

**Product lens:** Carbon ships envelope-qualified **solution maps** (problem setup → physical fields) for jobs engineers already run — **inverse design**, **plant-style / real-time response**, **exploration & UQ**, and **hybrid truth** (dense surrogate queries + sparse high-fidelity anchors). See [`appendices/Use_Cases_by_Phase.md`](./appendices/Use_Cases_by_Phase.md).

---

## Vision

A self-improving decentralized intelligence layer for physical modeling — where competitive search, trustless exams, and a Landscape knowledge flywheel together produce reusable, physics-grounded surrogates that accelerate engineering design, digital twins, real-time simulation, and scientific discovery.

**Carbon occupies the Verification + Model-Supply Layer in the Physics-AI stack**: NVIDIA owns the compute engine; Dyad/Ansys/Siemens own the tooling; Carbon owns the decentralized, trustlessly verified supply of models — **lean exams for search, product battery for the shelf**.

---

## Dual Threshold (How Productization Stays Real)

| Path | What it grades | Outcome |
|------|----------------|--------|
| **Miner → validator (lean)** | Physics gates, stress, short rollout, Model Card | Emissions / leaderboard — search stays cheap |
| **Landscape → Specialist Bank** | Effect-based recipe → controlled retrain → **product battery** (inverse-design bakeoff, deep plant/rollout, adversarial stress, latency, ONNX, escalation notes) | **Commercial SKU** — shelf credibility |

**Leaderboard rank ≠ shelf product.** No commercial full specialist ships without the product battery. Competition never requires purchase.

**Dual egress**

| Path | Who | What they get |
|------|-----|---------------|
| **Public / miner** | Miners, agents | Noisy, lagged priors / warm-start **derivatives only** — never full weights or exact bank recipe |
| **Commercial** | Buyers | Closed SKU = ONNX + exact recipe + Model Card + **product-battery certs** + license (+ optional air-gap) |

Export law: ***Ground truth in. Verified knowledge out.*** No teacher-checkpoint distillation. Canonical detail: [`appendices/Specialist_Bank.md`](./appendices/Specialist_Bank.md).

---

## Landscape Knowledge Flywheel

```text
Model Cards (lean verified)
        → private graph (causal / symbolic / failures / promotion outcomes)
        → Port A: noisy priors to miners          (search compounds)
        → Port B: eval routing (validators only)  (GPU compounds)
        → Port C: challenge weight proposals      (incentives aim where EV remains)
        → Port D: opportunity → Specialist Bank gauntlet → closed SKUs
        → banked regimes inform better noisy priors → more cards → …
```

| Port | Consumer | Leaves the building |
|------|----------|---------------------|
| **A Search** | Miners / agents | Noisy priors, causal masks, diagnostics |
| **B Eval** | Validators only | Progressive depth, adaptive stress (private) |
| **C Economy** | Governance | Weight / bounty *proposals* only |
| **D Product** | OpCo / buyers | Gauntlet-gated specialists, sponsor briefs, sealed packs |

Gates alone judge score — Landscape never overrides them. Full causal graph stays private; publish with noise + lag. Success = post-gate progress and commercial conversion — not guidance-API engagement.

Full architecture: [`appendices/Landscape_Agent.md`](./appendices/Landscape_Agent.md).

---

## Value Proposition & Market Opportunity

Traditional high-fidelity simulation is too slow and expensive for large design spaces or real-time use. Pure data-driven ML surrogates are fast but often violate fundamental physical constraints.

Carbon delivers **physics-informed neural operator surrogates** that are fast, robust, and physically trustworthy by leveraging decentralized parallel discovery at scale:

- **Superior training methodologies at network scale** — thousands of strategies in parallel under hidden stress + hard physics gates.
- **Adversarially validated robustness** — not just public-benchmark accuracy.
- **Compounding collective intelligence** — Landscape turns evaluations into better priors, eval efficiency, challenge design, and product candidates.
- **Trustless verification** — independent, auditable exams; open procedural generators with public unpredictable seeds.
- **Productization with teeth** — commercial specialists must re-train and pass job-shaped tests (inverse design, plant depth, adversarial), not merely win a leaderboard row.
- **Zero data risk (early tiers)** — public/synthetic data only for core network operation.

**Target applications**: CAE acceleration, HIL / real-time plant models, multi-physics screening, digital twins, high-stakes energy systems, hybrid truth loops (dense surrogate + sparse CFD/test).

---

## Validator & Miner Workflows

Carbon is designed for fast iteration by humans and agents while keeping hidden validation rigorous.

**From day one:**

- **Black-box diagnostics with clear tiers** — useful signal without leaking the exam.
- **Noisy priors + Estimation Mode** — near-zero-cost screening anchored to noisy priors (never clean champions).
- **ModelingToolkit.jl path** — symbolic structure from Landscape becomes actionable loss terms over time.

**Trustless Verification and Data Generation**: evaluation data is generated procedurally at runtime from open generators seeded by public, unpredictable information — fresh, hidden, auditable.

Miners may submit a strategy at any time with **zero local training**. Optional Estimation / Light Training loops help; they use different data and stress than the validator’s hidden set.

### Validator workflow (lean path)

Reproducible container; strategy JSON in; backbone + deterministic data mixture; train from scratch; multi-fidelity filter → full hidden stress + **physics gates** + **short rollout** stability signal; **Model Card** out → Landscape ingest. Hard gate fail → score zero.

Deep plant suites, inverse-design bakeoffs, and latency certification are **product-battery** work at Specialist Bank graduation — not unbounded cost on every submission.

### Miner / agent workflow (MCP)

- Estimation Mode — rapid screening  
- Light Training — local iteration  
- Full Submission — only path to emissions  

Warm starts are **noisy derivatives only**. Full specialist SKUs are commercial egress, not a free miner download.

---

```
┌─────────────────────────────────────────────────────────────────┐
│                    CARBON SUBNET ARCHITECTURE                   │
├─────────────────────────────────────────────────────────────────┤
│  MINERS / AGENTS                                                │
│  ├─ MCP: Estimation → Light Training → Full Submission          │
│  └─ Toolkit (Docker + SDK + cost estimates)                     │
├─────────────────────────────────────────────────────────────────┤
│  VALIDATORS                                                     │
│  ├─ Procedural data (block-hash seeds)                          │
│  ├─ Hidden stress + hard physics gates + short rollout          │
│  └─ Model Cards → Landscape                                     │
├─────────────────────────────────────────────────────────────────┤
│  LANDSCAPE AGENT (four-port flywheel)                           │
│  ├─ A Search: noisy priors / masks / diagnostics                │
│  ├─ B Eval: progressive depth / adaptive stress (private)       │
│  ├─ C Economy: challenge weight proposals                       │
│  └─ D Product: opportunity rank → Specialist Bank               │
├─────────────────────────────────────────────────────────────────┤
│  SPECIALIST BANK                                                │
│  ├─ Effect-synthesized recipes (not winner clones)              │
│  ├─ Controlled retrain + product battery                        │
│  └─ Dual egress: noisy miner path | closed commercial SKU       │
├─────────────────────────────────────────────────────────────────┤
│  INCENTIVES                                                     │
│  └─ ChallengeWinnerTracker on lean scores + decay               │
└─────────────────────────────────────────────────────────────────┘
```

---

## How the Engine Works

### 1. Participation via MCP
Persistent sessions, local/remote testing, Estimation and Light modes, full submission for emissions. Agents get fast loops; the network keeps the exam hidden.

### 2. Challenges by phase
- **Phase 0**: 7 academic PDEs (Poisson, Darcy, Burgers, laminar NS, Heat, Elasticity, Thermo-elasticity) — also where **catalog specialists rehearse the product battery**.  
- **1A**: Compressible / aero-leaning (e.g. NACA 0012, CRM-class).  
- **1B**: Reacting / sequential FSI / CHT / 6-DOF-class.  
- **2A**: LoRA, custom data paths, MT structured losses.  
- **2B**: Air-gap toolkit + coupling prep.  
- **3**: Coupled multi-physics (preCICE-class).  
- **4**: Production-adjacent 3D / turbulence.

Phase jumps are **capability-gated** (see `SPEC.md`).

### 3. Validation (lean path — heart of robustness)
Benchmark + hidden stress + hard physics gates + short rollout; **45 / 30 / 25** fidelity / robustness / accuracy. Fail a hard gate → zero. Emissions follow lean combined scores only.

### 4. Landscape + Specialist Bank
Cards feed the graph. Symbolic + causal fits run batch. Ports A–C improve search, eval cost, and incentives. Port D only productizes after **controlled retrain + product battery**. Promotion failures feed the graph (repair loop). That is the compounding moat — not “distill last week’s winner weights.”

### 5. Emissions
`weight ≈ lean_score × exp(−blocks_since_win / half_life)` with participation dust; future bounties. Landscape similarity is **not** a score term.

---

## Why This Design Matters

The space for Neural Operators in engineering is still early. Carbon explores *how* to train trustworthy maps in parallel under adversarial pressure, then productizes only what survives job-shaped tests.

- Hidden adversarial validation hard to game at scale  
- Trustless, auditable procedural exams  
- Knowledge flywheel (four ports) compounds private intelligence without selling eval outcomes  
- Dual threshold keeps miner friction low and commercial claims honest  
- Agent-friendly MCP iteration without collapsing incentives  

---

## Competitive Positioning

```
┌─────────────────────────────────────────────────────────────────┐
│                    PHYSICS-AI STACK                             │
├─────────────────────────────────────────────────────────────────┤
│  COMPUTE LAYER          │ NVIDIA — demand generator             │
├─────────────────────────┼───────────────────────────────────────┤
│  MODEL SUPPLY LAYER     │ **CARBON** — verified, compounding,   │
│                         │ lean exams + gauntlet-gated products  │
├─────────────────────────┼───────────────────────────────────────┤
│  TOOLING/DEPLOYMENT     │ Ansys, Siemens, Dyad, nTop, Rescale   │
├─────────────────────────┼───────────────────────────────────────┤
│  END USERS              │ Aero / Auto / Energy / Defense        │
└─────────────────────────────────────────────────────────────────┘
```

NVIDIA owns the engine. Tooling platforms own workflows. Carbon owns **decentralized discovery + independent verification + productization with receipts**.

---

## Model Lifecycle

```
1. TRAIN & VERIFY (lean)
   Strategy → validator train + hidden stress + gates → Model Card
   → Landscape ingest; lean score → emissions eligibility

2. PRODUCTIZE (optional, Port D)
   Opportunity from causal support → controlled retrain
   → product battery → bank → closed SKU (ONNX + certs + license)

3. DEPLOY (customer)
   Local inference; optional registry attestation; air-gap packs where required

4. REFRESH
   Re-verify when generators/gates advance; commercial channel gets updates
```

---

## Dual-Regime Model Supply (DoD / Regulated)

```
PUBLIC REGIME (Carbon Subnet)
  Discover strategies on public/synthetic data
  Lean adversarial verification + physics gates
  Gauntlet-gated catalog / sponsored outputs
  Zero ITAR/controlled data on-network
              │
              ▼ secure transfer / cross-domain
CLASSIFIED REGIME (Prime enclave)
  Ingest strategy blueprint
  Fine-tune on controlled data locally
  Re-apply product policy as required
  ONNX inference local — zero phone-home
```

---

## Go-to-Market

| Engine | Product | Buyer |
|--------|---------|-------|
| **Tier 1 Specialist Bank** | Closed ONNX + recipe + card + **PB certs** + license | Sim / SciML teams |
| **Tiers 2–4 Sponsored Challenges** | Open / IP-licensed / private regimes | OEMs, primes, labs |
| **DoD / SBIR path** | Evidence packages, sealed packs | Primes / programs |
| **Verification registry** | Attestation / card API | Tooling platforms |

Open the verification standard and coarse catalog; close the certified artifact.

---

## Documentation

| Document | Purpose |
|----------|---------|
| [`SPEC.md`](./SPEC.md) | Protocol: phases, scoring, dual threshold, flywheel |
| [`appendices/Landscape_Agent.md`](./appendices/Landscape_Agent.md) | Four ports, graph, build-out |
| [`appendices/Specialist_Bank.md`](./appendices/Specialist_Bank.md) | Gauntlet, dual egress, phase customers |
| [`appendices/Use_Cases_by_Phase.md`](./appendices/Use_Cases_by_Phase.md) | Inverse design / plant / UQ / hybrid truth |
| [`appendices/POC_Burgers_FNO.md`](./appendices/POC_Burgers_FNO.md) | Burgers×FNO full-loop PoC build guide |
| [`docs/TRUSTLESS_VERIFICATION_AND_DATA_GENERATION.md`](./docs/TRUSTLESS_VERIFICATION_AND_DATA_GENERATION.md) | Procedural generation & verification |
| [`appendices/Data_Management.md`](./appendices/Data_Management.md) | Seeds, train/eval separation |
| [`appendices/JAX_Optimization.md`](./appendices/JAX_Optimization.md) | Validator JAX efficiency |
| [`appendices/Compute_Optimization.md`](./appendices/Compute_Optimization.md) | Compute strategy |
| [`appendices/Implementation.md`](./appendices/Implementation.md) | Gates, toolkit, SciML, MCP |
| [`appendices/Operations.md`](./appendices/Operations.md) | Deploy / ops |
| [`docs/GTM.md`](./docs/GTM.md) | GTM detail |

---

## Current State

**Phase 0** foundations and offline PoC path: strategy → seeded data → train → gates → score → Model Card (`poc/`, [`POC_Burgers_FNO.md`](./appendices/POC_Burgers_FNO.md)).

Package namespace: **`carbon/`** (`pip install -e .`).

---

## Getting Started

```bash
git clone https://github.com/jbequ5/Carbon--Decentralized-Physics-AI.git
cd Carbon--Decentralized-Physics-AI
pip install -e .
# PoC smoke (protocol path; JAX optional for train-quality claims)
./poc/scripts/smoke.sh
```

---

## Contributing

Stress testing, determinism, symbolic/causal Landscape, MCP, multi-physics composition, product-battery harnesses, and docs are all welcome.

---

*Carbon: lean exams for discovery, a Landscape flywheel for compounding intelligence, and gauntlet-gated specialists for product — trustworthy physical maps with receipts.*
