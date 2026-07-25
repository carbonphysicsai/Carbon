# Carbon

**Decentralized Incentive System for Physics-Informed Neural Operator Surrogates**

Carbon is a Bittensor subnet that builds a decentralized, agentic system where miners and autonomous agents collaboratively discover fast, robust, and physics-respecting training strategies for high-fidelity engineering surrogates. It combines an **MCP-powered participation layer with built-in testing loops**, a **rigorous hidden adversarial validation mechanism**, and a **Landscape Agent that compounds symbolic and causal knowledge** over time. The result is an accelerating engine that has a real chance to outperform centralized players in this still-nascent space.

---

## Vision

A self-improving decentralized intelligence layer for physical modeling — where agents and a central Landscape Agent together create a compounding library of reusable, physics-grounded surrogates and specialists that accelerate engineering design, digital twins, real-time simulation, and scientific discovery. Long-term, this evolves toward foundational models of physics that are fast, robust, and interpretable across domains.

**Carbon occupies the Verification Layer in the Physics-AI stack**: NVIDIA owns the compute engine; Dyad/Ansys/Siemens own the tooling; Carbon owns the decentralized, trustlessly verified supply of models.

---

## Value Proposition & Market Opportunity

Traditional high-fidelity simulation is too slow and expensive for large design spaces or real-time use. Pure data-driven ML surrogates are fast but often violate fundamental physical constraints, limiting their reliability in engineering.

Carbon delivers **physics-informed neural operator surrogates** that are fast, robust, and physically trustworthy by leveraging decentralized parallel discovery at scale. Its core value lies in producing higher-quality surrogates than centralized platforms can achieve on their own, through these key mechanisms:

- **Superior Training Methodologies at Network Scale**: Agents and miners explore thousands of strategies in parallel. Hidden adversarial stress testing combined with hard physics gates creates strong selection pressure, surfacing training approaches (loss formulations, curricula, conditioning, architectures) that outperform what any single centralized team can discover linearly.

- **Adversarially Validated Robustness**: High-performing surrogates are not just accurate on public benchmarks — they are rigorously tested under hidden stress conditions with physics-class-specific gates. This provides a level of verifiable robustness and generalization that is extremely difficult for centralized systems to match at scale.

- **Compounding Collective Intelligence**: The Landscape Agent continuously extracts symbolic features and causal relationships from every evaluation. This turns individual discoveries into improving priors, reusable specialist components, and better future strategies for the entire network — creating accelerating returns over time.

- **Trustless Verification**: Carbon produces models through a decentralized competitive network with independent, auditable verification. This is structurally difficult for any single company to replicate at scale.

- **Zero Data Risk (Tier 1/2)**: Public/synthetic data only — no proprietary data required to deliver verified surrogates.

- **DI-SESS-82483 Alignment**: Model Cards export directly to DoD Digital Twin Description schema for IV&V/ATO acceleration.

These capabilities make Carbon particularly valuable for producing reliable surrogates that power **Software Defined Machines** and **Living Digital Twins** — where models must remain physically trustworthy while being fast enough for real-time use, predictive maintenance, and over-the-air updates.

**Target Markets & Applications**:
- Core CAE and simulation acceleration (aerospace, automotive, energy, manufacturing)
- Real-time simulation and Hardware-in-the-Loop (HIL)
- Multi-physics problems (FSI, CHT, thermo-elasticity)
- Digital twins and predictive maintenance
- High-stakes domains (fusion, nuclear, advanced energy systems)
- Long-term foundational physics modeling

The **Landscape Agent** and Specialist Bank create a compounding moat by continuously improving the quality of strategies and components available to the network.

---

## Validator & Miner Workflows

Carbon is intentionally designed to make fast, scalable iteration accessible to both humans and autonomous agents. By lowering the barrier to running effective local search loops while maintaining rigorous hidden validation, the subnet creates the conditions for iteration at scale — turning decentralized participation into a powerful engine for discovering better Neural Operator training methodologies.

Three capabilities are prioritized from the start to enable this vision:

- **Black-box diagnostics with clear tiers**: MCP feedback is deliberately limited to objective scores and high-level categories to protect the hidden evaluation data while still providing useful signal.
- **Noisy priors + Estimation Mode**: Only noisy versions of strong strategies are shared. A near-zero-cost Estimation Mode allows rapid screening of new ideas using approximations anchored to these noisy priors.
- **ModelingToolkit.jl integration**: Symbolic constraints discovered by the Landscape Agent will be turned into structured, usable loss terms early, making feedback significantly more actionable for local training loops.

A core architectural feature is the **Trustless Verification and Data Generation System**. All evaluation data (stress and benchmark) is generated procedurally at runtime using an open generator seeded by public, unpredictable information. This keeps the data fresh and hidden while remaining fully auditable. Benchmark data quality is proven through scientific justification of the generator and validation against high-fidelity reference solvers.

Miners can submit a strategy at any time with zero local training required — the validator will always perform full training and hidden adversarial evaluation. Optional low-friction local tools (Estimation Mode and Light Training) are available to help miners arrive at stronger submissions. Local loops use different data and stress conditions than the validator's hidden set. Miner training is an enhancement, not a requirement.

### Validator Workflow

The validator runs in a reproducible Docker container and accepts structured strategy JSON. It dynamically selects the correct neural operator backbone, assembles a deterministic data mixture, trains the model, and evaluates it through a **multi-fidelity pipeline**:

- **Tier 1 (Fast Filter)**: Low-cost stress testing quickly eliminates weak strategies.
- **Tier 2 (Full Evaluation)**: Only promising candidates proceed to full hidden stress testing with physics gates.

During training, the validator performs **online physics residual monitoring** with configurable adaptive responses (such as dynamic loss re-weighting within defined bounds). Every run automatically generates a rich **Model Card** containing the exact strategy configuration, training dynamics, held-out metrics, stress results, gate violations with physics explanations, and extracted symbolic features. **The Model Card and its cryptographic proof are written to the Verification Registry (on-chain) for immutable provenance.** These cards feed the Landscape Agent and provide strong auditability and provenance.

This design delivers high throughput while preserving the adversarial strength of hidden stress testing.

### Miner/Agent Workflow (MCP)

The MCP layer supports multiple modes so both human miners and autonomous agents can iterate rapidly while receiving **genuine, physics-constrained feedback**:

- **Simulated / Cached Approximation**: For very early prototyping.

- **Light Training + Gated Evaluation** (recommended test mode): Reduced training budget followed by held-out evaluation + hidden stress testing + **full physics gates**. Produces a real test score quickly. Does not affect the official leaderboard but is logged and can contribute (with lower weight) to the Landscape Agent.

- **Full Production Submission**: Strategy submitted to validators for complete training + full adversarial stress testing. Only these submissions can set new best combined scores and earn strong emissions weight.

Additional capabilities include:
- **Noisy Prior-Informed Warm Starts** from the Landscape Agent (using current best priors or distilled specialists).
- **Explainable Failure Diagnostics** (locations and types of high residuals or gate violations, spectral issues, uncertainty hotspots, and comparisons to recent successful strategies).
- **Pareto / Multi-Objective Reporting** in test mode (optional) to surface interesting trade-offs.

All runs remain fully deterministic. Test modes are rate-limited and clearly separated from production submissions. This combination enables fast, high-signal iteration without compromising the subnet's adversarial integrity or incentive alignment.

**Why These Design Choices Matter**:
- They dramatically increase iteration speed for both humans and autonomous agents.
- They generate richer data for the Landscape Agent, accelerating collective intelligence.
- They maintain strong defensibility through determinism, provenance, physics gates, and clear separation of test vs. production paths.
- They position Carbon as one of the most agent-friendly yet rigorously validated subnets, enabling faster discovery of superior Neural Operator methodologies than centralized platforms can achieve.

---

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
│  VALIDATORS (5+ for consensus)                                  │
│  ├─ Trustless Procedural Data Generation (seeded by block hash) │
│  ├─ Multi-Fidelity Pipeline:                                    │
│  │  ├─ Tier 1: Fast stress filter                               │
│  │  └─ Tier 2: Full hidden adversarial + physics gates         │
│  ├─ Online physics residual monitoring (adaptive loss re-weight)│
│  └─ Model Card generation (full provenance + diagnostics)      │
├─────────────────────────────────────────────────────────────────┤
│  LANDSCAPE AGENT (Compounding Intelligence)                     │
│  ├─ Symbolic extraction (PySR → ModelingToolkit.jl losses)     │
│  ├─ Causal analysis (Double ML for strategy → outcome)         │
│  ├─ Specialist Bank (distilled reusable components)            │
│  └─ Prior updates → noisy priors distributed to miners         │
├─────────────────────────────────────────────────────────────────┤
│  INCENTIVES (Yuma Consensus + ChallengeWinnerTracker)          │
│  ├─ Winner-heavy + exponential decay                           │
│  ├─ Future: Breakthrough Bounties + Decaying Top stipends      │
│  └─ Treasury for unclaimed allocations                         │
└─────────────────────────────────────────────────────────────────┘
```

## How the Engine Works — Clear Mechanism Walkthrough

### 1. Participation via MCP (Agent-Friendly with Built-in Testing Loop)
Miners and agents interact through MCP, which supports persistent sessions, streaming validation/results, and easy local or remote testing of strategies. This design makes participation seamless and gives agents a tangible fast-iteration advantage — they can quickly test ideas against the live system or subsets of challenges and receive immediate, actionable diagnostics.

### 2. Challenges by Phase

- **Phase 0**: 7 core single-physics PDE challenges (Poisson, Darcy, Burgers, Navier-Stokes laminar, Heat, Elasticity, Thermo-elasticity).

- **Phase 1A**: Compressible Flow (Months 4–8)
  Bridges academic PDEs to weapon-relevant physics:
  - **NACA 0012 Transonic Flutter** — Shock-boundary layer interaction, flutter onset (NASA TP-2001-211214)
  - **NASA CRM Wing-Body** — Transonic separation, buffet (DPW)

- **Phase 1B**: Reacting Flow + Sequential FSI (Months 8–14)
  Adds reacting flow, sequential FSI, 6-DOF, and conjugate heat transfer:
  - **HIFiRE-1 Scramjet Forebody** — Hypersonic boundary layer transition (AFRL)
  - **Turek/Hron FSI 3D (Sequential)** — Fluid-structure interaction (one-way)
  - **Store Separation (6-DOF)** — Moving boundaries, dynamic mesh
  - **Turbine Blade Heat Transfer** — Conjugate heat transfer, film cooling

- **Phase 2A**: Customization & Intelligence (Months 14–22)
  Adds LoRA adapters, custom datasets (Abaqus ODB), and ModelingToolkit.jl structured losses.

- **Phase 2B**: Air-Gap + Coupling Prep (Months 22–28)
  Adds air-gapped miner toolkit/validator, preCICE sidecar architecture, and sequential multi-physics ladder.

- **Phase 3**: Multi-Physics Coupling (Months 28–40)
  Verified multi-physics benchmarks with preCICE composition:
  - FSI (Turek/Hron 3D) — NS + Nonlinear Elasticity (preCICE implicit)
  - CHT (Conjugate Heat Transfer) — NS + Heat (preCICE explicit)
  - Thermo-Elasticity 3D — NS + Heat + Elasticity (preCICE multi-field)

- **Phase 4**: Production (Months 40–52)
  3D multi-physics with turbulence:
  - 3D FSI + Turbulence, 3D CHT + Turbulence, 3D Thermo-Elasticity + Turbulence
  - Hypersonic 6-DOF — Reacting NS + 6-DOF + Ablation

### 3. Validation Strategy (The Heart of Robustness)
Every submission goes through a rigorous, hidden validation process powered by the Trustless Verification and Data Generation System:

- **Benchmarking**: Performance on procedurally generated held-out data (accuracy component).
- **Hidden Stress Testing**: Adversarial evaluation under fresh, hidden conditions generated at runtime.
- **Physics Gates**: Hard gates (e.g., mass conservation, energy dissipation/stability, boundary satisfaction, rollout stability, UQ calibration, adjoint consistency, shock capture, species conservation, chemistry UQ, interface continuity, momentum/energy conservation, coupling convergence, vorticity preservation, boundary layer resolution, turbulence spectra, separation prediction, ablation recession) that zero the score on critical violations.
- **Multi-Objective Scoring (45/30/25)**:
  - Physics Fidelity (45%): Residuals, conservation laws, boundary conditions, stability.
  - Robustness (30%): Performance under hidden stress, long-term rollout, generalization.
  - Accuracy (25%): Benchmark/hold-out performance.

Only strategies that set a new best *combined score* on a challenge receive meaningful weight.

This combination ensures surrogates are not just accurate on known data but genuinely robust and physically trustworthy under unseen conditions.

### 4. Feedback, Landscape Agent & Knowledge Compounding
Agents receive detailed scores, gate outcomes, and diagnostics. All results are ingested by the **Landscape Agent**, which:
- Extracts symbolic features (conservation laws, symmetries, etc., via PySR and planned ModelingToolkit integration).
- Applies causal analysis (Double Machine Learning) to understand which strategy choices causally improve outcomes — for example, learning that certain loss-weight schedules causally improve long-term rollout stability under hidden stress variations.
- Updates a compounding knowledge base and priors.
- Drives specialist distillation and better future challenges.

**Phasing**: PySR symbolic regression (Phase 0) → ModelingToolkit.jl bridge (Phase 1) → Double ML causal inference (Phase 2A) → Cross-domain causal mapping (Phase 2B). ModelingToolkit.jl bridge via JSON serialization first, JuliaCall later. Full architecture and value-routing: [`appendices/Landscape_Agent.md`](./appendices/Landscape_Agent.md). Specialist pipeline and phase customers: [`appendices/Specialist_Bank.md`](./appendices/Specialist_Bank.md).

This creates accelerating returns: better data → better insights → better strategies → even richer data. The Specialist Bank and knowledge base form a self-reinforcing flywheel and long-term moat.

### 5. Emissions & Incentives
Current model uses standard Yuma Consensus with the **ChallengeWinnerTracker**:
- Per-challenge leader tracking with exponential decay on old performance: `weight = score × e^(-blocks_since_win / half_life)` (half_life = 30 days, tunable via governance).
- Winner-heavy weighting + participation dust for recent contributors.
- Only genuine new best combined scores drive strong rewards.
- Future phases add hybrid model with Breakthrough Bounties (record-setting improvements) and Decaying Top stipends, with unclaimed allocations rolling to treasury.

---

## Why This Design Matters

The space for AI-powered physics simulation and Neural Operators is still nascent. There is a tremendous amount left to discover in *how* to best build, train, and use these models for real engineering problems.

A properly aligned decentralized subnet like Carbon has a real chance to outperform centralized players (Neural Concept, PhysicsX, Dyad, etc.) — and do it for cheaper — by enabling massively parallel strategy exploration with strong selection pressure from hidden adversarial stress testing. Centralized teams explore this space linearly; Carbon explores it in parallel across thousands of strategies.

Key advantages:
- **Hidden Adversarial Validation**: Forces genuine robustness that is extremely hard to game.
- **Trustless & Verifiable Stress Testing**: The Trustless Verification and Data Generation System uses open procedural generation with public unpredictable seeding, making evaluation auditable by anyone.
- **Compounding Intelligence**: The Landscape Agent turns individual discoveries into collective knowledge that improves future priors and specialist quality.
- **Fast Agent Iteration**: MCP + built-in testing loop dramatically speeds discovery.
- **Aligned Incentives**: Winner-heavy tracking with decay keeps focus on continuous, genuine improvement.

This combination of decentralized exploration, rigorous hidden testing, and compounding knowledge gives Carbon a structural edge in this still-early field.

---

## Competitive Positioning

The broader industry is moving rapidly toward **Software Defined Machines** and **Living Digital Twins** — where models serve as the single source of truth across design, embedded control, deployment, and ongoing operation, continuously refined by real-world data.

**Carbon occupies a distinct layer in the stack**:

```
┌─────────────────────────────────────────────────────────────────┐
│                    PHYSICS-AI STACK                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  COMPUTE LAYER          │ NVIDIA (H100, Blackwell, CUDA,        │
│                         │  TensorRT, Apollo, Cosmos)            │
│                         │ Demand generator — not competitor      │
├─────────────────────────┼───────────────────────────────────────┤
│  MODEL SUPPLY LAYER     │ **CARBON** (Decentralized, Verified,  │
│                         │  Compounding, Trustless)               │
│                         │ ◄── NO DIRECT COMPETITOR              │
├─────────────────────────┼───────────────────────────────────────┤
│  TOOLING/DEPLOYMENT     │ Ansys, Siemens, Dyad, Dassault,      │
│                         │ nTop, Rescale                          │
│                         │ Consumers of Carbon's model supply    │
├─────────────────────────┼───────────────────────────────────────┤
│  END USERS              │ Aero/Auto/Energy/Defense — Digital    │
│                         │ Twins, HIL, Design Optimization,      │
│                         │ Certification                         │
└─────────────────────────────────────────────────────────────────┘
```

- **NVIDIA** owns the compute engine and is increasingly providing open physics foundation models (Apollo, Cosmos). This is largely a demand generator for Carbon, not a direct competitor.

- **Dyad, Ansys, Siemens, and similar platforms** own the modeling tools, environments, and deployment infrastructure. They consume and orchestrate models but generally produce them centrally and self-verify.

- **Carbon** owns the decentralized, independently verified model-supply layer. It produces physics-informed surrogates through competitive network participation with trustless verification — something no single company can replicate at scale. This layer is currently the weakest and most structurally defensible part of the stack.

Carbon's primary advantage is its ability to coordinate distributed discovery and independent verification at scale. Over time, it can also incorporate privacy-preserving signals from proprietary data using confidential computing and other techniques, but its core strength today lies in public and synthetic data regimes combined with strong collective intelligence.

In short: NVIDIA owns the engine. Dyad and Ansys own the tools. Carbon owns the decentralized, trustlessly verified supply of the models themselves.

---

```
┌─────────────────────────────────────────────────────────────────┐
│                    MODEL LIFECYCLE                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. TRAIN & VERIFY (Carbon Subnet)                              │
│     ├─ Miner submits strategy                                   │
│     ├─ Validator trains + runs hidden stress + physics gates    │
│     ├─ Model Card generated (JSON + ONNX)                       │
│     ├─ Evidence written to Verification Registry (on-chain)     │
│     │   model_id → {gate_results, generator_version,            │
│     │                operational_envelope, validator_set_hash}  │
│     └─ Model Card + ONNX delivered to customer                  │
│                                                                 │
│  2. DEPLOY (Customer / Prime / Partner)                         │
│     ├─ Downloads: ONNX model + Model Card + Registry proof      │
│     ├─ Verifies locally: Model Card hash = Registry hash        │
│     ├─ Deploys ONNX to target (HIL, edge, cloud, air-gapped)   │
│     └─ **Runs inference LOCALLY — zero network calls**          │
│                                                                 │
│  3. VERIFY (Optional, Periodic, Programmatic)                   │
│     ├─ CI/CD: "Has this model_id been revoked?" (daily build)   │
│     ├─ HIL Pre-flight: "Is envelope still valid for this run?"  │
│     ├─ Re-verification: "Generator v1.4 released — re-check?"   │
│     └─ Audit: "Show me the gate results for model X"            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Dual-Regime Model Supply (DoD/Regulated Markets)

```
┌─────────────────────────────────────────────────────────────────┐
│  PUBLIC REGIME (Carbon Subnet)                                  │
│  ├─ Discovers architectures on public/synthetic data            │
│  ├─ Adversarial verification + physics gates                    │
│  ├─ Outputs: Strategy.json + Model Card + ONNX + Evidence       │
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
│  ├─ Deploys ONNX locally (HIL, edge, air-gapped)                │
│  ├─ Runs inference LOCALLY — zero network calls                 │
│  ├─ Applies ITAR/EAR classification (Prime's ECO)               │
│  └─ Packages DI-SESS-82483 deliverable + ATO artifacts          │
└─────────────────────────────────────────────────────────────────┘
```

- **Public Regime**: Subnet mechanics, evidence generation, zero ITAR
- **Transfer Layer**: Cross-domain solution, secure media, CDS
- **Classified Regime**: Air-Gapped Miner Toolkit, fine-tuning loop, ITAR classification, DI-SESS-82483 packaging, ATO evidence
- **Prime Onboarding Checklist**: Clearance, facility, contract vehicle
- **Evidence Package Schema**: Model Card → DI-SESS-82483 manifest

## Go-to-Market: Three Revenue Engines

| Engine | Product | Price | Buyer | Timeline |
|--------|---------|-------|-------|----------|
| **Specialist Bank (Tier 1)** | 7→50 certified specialists (ONNX + Model Card + Gate Certs) | $10–50k/yr per model / $100–200k/yr bundle | Sim teams (Aero/Auto/Energy) | Month 3 |
| **Sponsored Challenges (Tiers 2–4)** | Custom PDE/geometry challenges | T2: $150–300k (open)<br>T3: $400–800k (IP-licensed)<br>T4: $800k–2M+ (private/on-prem) | Primes, OEMs, Labs | Month 6–12 |
| **DoD Subcontract (SBIR/BAA)** | Evidence Package for IV&V/ATO | Phase I: $250k (6mo)<br>Phase II: $1.5–2M (24mo) | Primes (Shield AI, Anduril, etc.) | Month 12–18 |
| **Verification Gas/Registry** | Programmatic badge resolution, model card API | $0.001–0.01/query (USD-denominated, α-settled) | Tooling platforms (Dyad, Ansys, nTop, Rescale) | Month 12+ |

---

## Documentation

| Document | Purpose |
|----------|---------|
| [`SPEC.md`](./SPEC.md) | Core architecture, phases, scoring, incentives |
| [`docs/TRUSTLESS_VERIFICATION_AND_DATA_GENERATION.md`](./docs/TRUSTLESS_VERIFICATION_AND_DATA_GENERATION.md) | Trustless procedural generation & verification |
| [`appendices/POC_Burgers_FNO.md`](./appendices/POC_Burgers_FNO.md) | **Build guide:** Burgers-1D × FNO-1D full-loop PoC |
| [`appendices/JAX_Optimization.md`](./appendices/JAX_Optimization.md) | Validator-side JAX training optimizations (canonical) |
| [`appendices/Data_Management.md`](./appendices/Data_Management.md) | Seed hierarchy, train/eval separation, stress data |
| [`appendices/Landscape_Agent.md`](./appendices/Landscape_Agent.md) | Landscape value routing, architecture, phased build-out |
| [`appendices/Specialist_Bank.md`](./appendices/Specialist_Bank.md) | Landscape→Specialist pipeline; phase-by-phase customers |
| [`appendices/Implementation.md`](./appendices/Implementation.md) | Physics gates, Miner Toolkit, SciML, contracts, MCP |
| [`appendices/Compute_Optimization.md`](./appendices/Compute_Optimization.md) | Compute efficiency strategy & prioritization |
| [`appendices/Operations.md`](./appendices/Operations.md) | Deployment, K8s, monitoring, incident response |
| [`docs/GTM.md`](./docs/GTM.md) | Go-to-market detail |
| [`docs/FUTURE_DOMAINS.md`](./docs/FUTURE_DOMAINS.md) | Longer-horizon domain roadmap |

---

## Current State

**Phase 0** foundations are advancing: scoring, stress testing across physics classes, determinism utilities, MCP basics, symbolic skeleton, integration of stress into scoring, and trustless data generation.

**Mechanism PoC (build target):** one PDE × one backbone vertical slice — Burgers-1D + FNO-1D — specified in [`appendices/POC_Burgers_FNO.md`](./appendices/POC_Burgers_FNO.md) (strategy → seeded data → train → gates → 45/30/25 → Model Card).

Code package paths still use the transitional `hydrogen/` namespace while product naming and documentation are fully Carbon. See `SPEC.md` and the appendices above for full technical detail.

---

## Getting Started

```bash
git clone https://github.com/jbequ5/Carbon--Decentralized-Physics-AI.git
cd Carbon--Decentralized-Physics-AI
python neurons/validator.py --dry_run true   # Explore in dry-run mode
```

See the `docs/` folder for agent usage, validator configuration, and design notes. Deep implementation detail lives in `appendices/`.

---

## Contributing

We welcome contributions in stress testing, determinism, symbolic integration, MCP enhancements, multi-physics composition, and testing infrastructure.

---

*Carbon is building the decentralized agentic infrastructure for trustworthy, compounding physical intelligence in engineering and science.*
