# Carbon

**Decentralized Incentive System for Physics-Informed Neural Operator Surrogates**

Carbon is a Bittensor subnet for **trustless verification** of physics-informed neural operator training strategies. Miners submit strategies; validators retrain on hidden procedural data under hard physics gates; lean scores drive emissions. A **dual threshold** keeps search cheap and commercial products honest. A **Landscape** four-port architecture is designed to compound verified cards over time — **build-ordered**, not a pre-launch live brain.

**Lead story:** verification + dual threshold + sponsored challenges.  
**Second act:** Landscape flywheel (noisy priors → better search; gauntlet → specialists) once the lean exam is real ([`Launch_Bar.md`](./appendices/Launch_Bar.md)).

**Product lens:** envelope-qualified **solution maps** for **inverse design**, **plant-style / real-time response**, **exploration & UQ**, and **hybrid truth**. See [`appendices/Use_Cases_by_Phase.md`](./appendices/Use_Cases_by_Phase.md).

---

## Vision

A self-improving decentralized verification and model-supply layer for physical modeling — competitive search, trustless exams, and (as the network matures) a knowledge flywheel that routes private intelligence without opening eval outcomes for sale.

**Carbon occupies the Verification + Model-Supply Layer in the Physics-AI stack**: NVIDIA owns the compute engine; Dyad/Ansys/Siemens own the tooling; Carbon owns decentralized, trustlessly verified supply — **lean exams for search, product battery for the shelf**.

---

## Dual Threshold (How Productization Stays Real)

| Path | What it grades | Outcome |
|------|----------------|--------|
| **Miner → validator (lean)** | Physics gates, stress, short rollout, Model Card | Emissions / leaderboard — search stays cheap |
| **Landscape → Specialist Bank** | Effect-based recipe → controlled retrain → **product battery** | **Commercial SKU** — shelf credibility |

**Leaderboard rank ≠ shelf product.** No commercial full specialist ships without the product battery. Competition never requires purchase.

**Dual egress:** miners get noisy lagged priors only; buyers get closed ONNX + recipe + PB certs + license. Export law: ***Ground truth in. Verified knowledge out.***

Canonical: [`appendices/Specialist_Bank.md`](./appendices/Specialist_Bank.md).

---

## Landscape Knowledge Flywheel (Architecture)

```text
Model Cards (lean verified)
        → private graph
        → Port A: noisy priors to miners
        → Port B: eval routing (validators; floor rules)
        → Port C: challenge weight proposals
        → Port D: opportunity → Specialist Bank gauntlet → closed SKUs
```

Gates alone judge score. Causal bands are **observational estimates**, not gate-proof. Public L0 priors only after [`Launch_Bar.md`](./appendices/Launch_Bar.md) is green. Full architecture: [`Landscape_Agent.md`](./appendices/Landscape_Agent.md) (v1.2+).

---

## Value Proposition & Market Opportunity

Traditional high-fidelity simulation is too slow for large design spaces or real-time use. Pure ML surrogates are fast but often violate physical constraints.

Carbon delivers **physics-informed neural operator surrogates** via:

- **Network-scale strategy search** under hidden stress + hard physics gates  
- **Adversarially validated robustness**  
- **Trustless, auditable exams** (procedural generators, public seed derivation)  
- **Productization with teeth** — commercial specialists must pass job-shaped tests, not only win a leaderboard row  
- **Designed compounding** — Landscape routes private intelligence under publish boundaries (as the exam and card volume mature)  

**Target applications:** CAE acceleration, HIL / plant models, multi-physics screening, digital twins, hybrid truth loops.

---

## Validator & Miner Workflows

- **Black-box diagnostics**, **noisy priors + Estimation Mode**, optional Light Training  
- **Trustless data:** procedural generation at runtime; train ≠ eval ≠ stress  
- **Lean scoring:** challenge-bound Score Packs — [`Scoring.md`](./appendices/Scoring.md)  
- Submit anytime with zero local training; full submission is the only emissions path  
- Warm starts = **noisy derivatives only**

Hard gate fail → score zero. Deep plant / inverse-design / latency certs = **product battery** at Specialist Bank — not every submission.

---

## How the Engine Works (Short)

1. **MCP** — Estimation / Light / Full submission  
2. **Phases** — capability-gated 0→4 (academic → compressible → reacting/FSI → coupling → 3D)  
3. **Lean validation** — 45% physics margins / 30% stress robustness / 25% held-out accuracy (`Scoring.md`)  
4. **Landscape + Bank** — cards → private graph → noisy priors / gauntlet SKUs (after Launch Bar)  
5. **Emissions** — lean score × decay; Landscape similarity **not** a score term  

---

## Competitive Positioning

NVIDIA owns the engine. Tooling platforms own workflows. Carbon owns **decentralized discovery + independent verification + productization with receipts**.

---

## Go-to-Market

| Engine | Product |
|--------|---------|
| **Tier 1 Specialist Bank** | Closed ONNX + recipe + card + **PB certs** + license |
| **Tiers 2–4 Sponsored Challenges** | Open / IP-licensed / private regimes |
| **DoD / SBIR path** | Evidence packages, sealed packs |
| **Verification registry** | Attestation / card API |

---

## Documentation

| Document | Purpose |
|----------|---------|
| [`SPEC.md`](./SPEC.md) | Protocol: phases, dual threshold, flywheel |
| [`appendices/Scoring.md`](./appendices/Scoring.md) | Lean formulas, Score Bank, validator load path |
| [`appendices/Launch_Bar.md`](./appendices/Launch_Bar.md) | Stop-ship before Landscape L0 publish |
| [`appendices/Landscape_Agent.md`](./appendices/Landscape_Agent.md) | Four ports, epistemic status, Port B floors |
| [`appendices/Specialist_Bank.md`](./appendices/Specialist_Bank.md) | Gauntlet, dual egress |
| [`appendices/Use_Cases_by_Phase.md`](./appendices/Use_Cases_by_Phase.md) | Inverse design / plant / UQ / hybrid truth |
| [`appendices/POC_Burgers_FNO.md`](./appendices/POC_Burgers_FNO.md) | Burgers×FNO PoC build guide |
| [`appendices/Data_Management.md`](./appendices/Data_Management.md) | Seeds, train≠eval |
| [`docs/TRUSTLESS_VERIFICATION_AND_DATA_GENERATION.md`](./docs/TRUSTLESS_VERIFICATION_AND_DATA_GENERATION.md) | Procedural generation |
| [`appendices/JAX_Optimization.md`](./appendices/JAX_Optimization.md) | Validator JAX efficiency |
| [`appendices/Compute_Optimization.md`](./appendices/Compute_Optimization.md) | Compute strategy |
| [`appendices/Implementation.md`](./appendices/Implementation.md) | Gates, toolkit, SciML, MCP |
| [`appendices/Operations.md`](./appendices/Operations.md) | Deploy / ops |

---

## Current State

**Phase 0** foundations and offline PoC: strategy → seeded data → train → gates → score → Model Card (`poc/`). Package: **`carbon/`** (`pip install -e .`).

---

## Getting Started

```bash
git clone https://github.com/jbequ5/Carbon--Decentralized-Physics-AI.git
cd Carbon--Decentralized-Physics-AI
pip install -e .
./poc/scripts/smoke.sh
```

---

*Carbon: lean exams for discovery, a Launch-Bar-gated Landscape for compounding, and gauntlet-gated specialists for product — trustworthy physical maps with receipts.*
