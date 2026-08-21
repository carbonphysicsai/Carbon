# Carbon Specialist Use Cases by Phase

**Purpose:** Teach what a Carbon-qualified fast physical model or system can be used for, regime by regime, without requiring a PDE background.

**Scope note:** This document describes Carbon's **current learned-model / specialist product track** and illustrative physics progression. It is not Carbon's terminal scientific ontology and is not a commitment that every future Challenge or product must be a neural solution map. The broader system identity is defined in `System_Identity_and_Roadmap.md`.

**Current through-line:** In the early learned-model track, the primary artifact is a fast solution map (problem setup → physical fields/KPIs) that has survived registered independent evaluation and, for product claims, a separate qualification path. As Carbon matures, equivalent jobs may also be served by hybrid, reduced-order, classical, symbolic/numeric, composed, or routed fast-model systems if those construction families are admitted and independently evidenced.

**How to read each phase**

| Lens | Meaning |
|------|--------|
| **What the candidate answers** | Input → output in plain language |
| **Inverse design** | Search designs/parameters using thousands of cheap forward solves |
| **Plant model** | Stand-in for “how the system responds” in control, HIL, or twins |
| **Exploration / UQ** | Sweep many conditions; quantify spread of outcomes |
| **Who cares** | Realistic buyer or user at that maturity |
| **Evidence role** | Why independent evaluation / qualification matters for this use |

---

## TL;DR

| Phase | Physics maturity | Flagship use case | Primary buyer energy |
|-------|------------------|-------------------|----------------------|
| **0** | Academic PDEs | Methods + teaching gym; prove gates work | Researchers, subnet agents |
| **1A** | Compressible / aero-like | Design sweeps on simplified aero loads | Aero tools teams, advanced R&D |
| **1B** | Reacting / sequential FSI | Thermal–structural and flow–structure *screening* | Propulsion/structures screening groups |
| **2A** | Custom + adaptation + intelligence | Customer geometry/load adaptation under license | Engineering orgs wanting *their* envelope |
| **2B** | Air-gap ready | Same jobs, deployable in restricted networks | Defense-adjacent, regulated IT |
| **3** | Coupled multi-physics | Joint fluid–structure / conjugate heat *campaigns* | Multi-physics design cells |
| **4** | 3D + turbulence production-adjacent | Production-adjacent iteration inside qualified envelopes | OEMs, primes, digital-twin programs |

These models/systems are never “the full FAA/DoD certifier.” They are **fast, evidence-bounded physical approximations** used to explore, screen, look ahead, and fill gaps between expensive truth runs.

**Important roadmap note:** The phase table is a use-case curriculum, not the only sequencing authority. Carbon's strategic roadmap now separates three axes — physics depth, model freedom, and commercial realism. The preferred doctrine is: **first prove the judge, then deepen the physics, then widen the search, while bringing industry in throughout.**

---

## Phase 0 — Foundation (Academic PDEs)

**Envelope:** Poisson, Darcy, Burgers, laminar NS, heat, linear elasticity, thermo-elasticity (2D-focused, mesh-converged vs reference solvers where/when qualified).

**What the model answers**  
“Given this initial state / coefficient field / load pattern, what does the solution field look like?”

| Use pattern | Realistic Phase-0 use | Why it’s still valuable |
|-------------|----------------------|-------------------------|
| **Inverse design** | Optimize a conductivity map or source layout to match a target temperature field on a heat equation specialist | Teaches the workflow of inverse design on honest gates; publishes methods agents can test |
| **Plant model** | Toy closed-loop demos: 1D/2D “process” whose next state comes from a Burgers or heat operator | Curriculum for control students; not industrial HIL |
| **Exploration / UQ** | Monte Carlo over random permeability fields (Darcy) or ICs (Burgers) | Stress-tests whether the specialist preserves required behavior under distribution shift |
| **Agentic autoresearch** | Inner-loop fitness for strategy search (Carbon’s own miners) | Primary economic use of Phase-0 models: improve construction/training hypotheses |
| **Teaching / benchmarks** | Shared gym for SciML methods papers | Comparable, gated leaderboards beat one-off GitHub demos |

**Who cares:** SciML researchers, Bittensor miners/agents, university labs.  
**Evidence role:** Proves the exam is real (junk strategies → zero where mandatory gates apply). Without this, later phases have no credibility.

**Pitch line:** *“Phase 0 is the flight-test range for the grading system — not the airliner.”*

---

## Phase 1A — Compressible / Aero-leaning

**Envelope:** Academic set + simplified compressible / transonic-style benchmarks (e.g. airfoil-class problems, wing-body screening fidelity — not full vehicle certification).

**What the model answers**  
“Given shape parameters / freestream conditions, what do pressure and approximate load fields look like inside this qualified envelope?”

| Use pattern | Realistic use | Value |
|-------------|---------------|--------|
| **Inverse design** | Search airfoil or simple wing parameters for lift/drag/load targets under constraints | Many more evaluations than a full high-fidelity campaign can usually support |
| **Plant model** | Real-time aero load proxy in a desktop or HIL software loop for control-law development (low–mid fidelity envelope) | Controllers get a physics-shaped plant without a wind-tunnel every iteration |
| **Exploration / UQ** | Sweep Mach, α, thickness; map load sensitivity bands | Early risk picture before heavy CFD campaigns |
| **Screening twin** | “What-if” on condition changes for a fixed simplified geometry | Engineer-in-the-loop, not autonomy |

**Who cares:** Aircraft concept teams, aero tool vendors, university aero + startup eVTOL analysis groups.  
**Evidence role:** Protected stress on difficult regimes; mandatory physical failures disqualify attractive models that break required behavior.

**Pitch line:** *“Not replacing the cert CFD deck — multiplying the concept sweeps that happen before you spend that deck.”*

---

## Phase 1B — Reacting flow + sequential FSI-style

**Envelope:** Added reacting / thermal / one-way coupled structure-style challenges (sequential FSI, conjugate-heat-like, high-speed thermal screening).

**What the model answers**  
“Given operating condition and simplified geometry, how do temperature, species (where in scope), and structural response fields evolve or settle within this sequential coupling story?”

| Use pattern | Realistic use | Value |
|-------------|---------------|--------|
| **Inverse design** | Cooling channel or liner parameter search under peak-temp and mass constraints | Thermal design iteration without a full conjugate solve each time |
| **Plant model** | Engine/ECU or thermal-protection HIL plant at reduced physics: commanded condition → approximate thermal/load state | Hardware tests need a clock-friendly plant; full CFD is too slow |
| **Exploration / UQ** | Chemistry or thermal-boundary uncertainty bands (where UQ evidence exists) | Evidence-bounded spread, not a single optimistic curve |
| **Sequential campaign** | One-way fluid → structure screening before true two-way coupling budget is spent | Filters hopeless designs early |

**Who cares:** Propulsion thermal teams, structures screening, defense-adjacent concept shops (still not full weapon-system authority).  
**Evidence role:** Species/energy-style gates and sequential interface checks where the Challenge has qualified them.

**Pitch line:** *“Screen the coupled problem before you pay for the fully coupled truth.”*

---

## Phase 2A — Customization & intelligence

**Envelope:** Same physics families, but customer-shaped: fine-tune/adaptation paths, optional structured losses, sponsored Challenge geometries — public core + private adaptation patterns (raw proprietary data stays with customer where required).

**What the model answers**  
“Given our part family and load deck (inside an agreed envelope), fields and KPIs we care about — with an evidence trail.”

| Use pattern | Realistic use | Value |
|-------------|---------------|--------|
| **Inverse design** | Customer optimizer on their parameterization (CAD variables, thickness maps) using a specialist adapted to their regime | Design search on the geometry class they actually ship |
| **Plant model** | Plant tuned to their actuator/sensor rates for software-in-the-loop | Closer match to their control lab |
| **Exploration / UQ** | Production variability (tolerance, material bands) on the adapted model | Quality and robustness stories tied to their drawings |
| **Sponsored Challenges** | OEM funds a Challenge; network searches methods; sponsor gets licensed outputs under agreed terms | Aligns discovery with paid demand |

**Who cares:** Mid-size engineering orgs, tool partners, innovation groups inside primes.  
**Evidence role:** Adaptation must re-pass the relevant qualification path — modification cannot silently inherit the prior artifact's claim.

**Pitch line:** *“Public competition can find the method; your envelope and license make the deployment specific — still evidence-bounded.”*

---

## Phase 2B — Air-gap / regulated deployment

**Envelope:** Physics as in 1–2A; deployment in restricted networks (air-gap toolkit, no required phone-home inference).

**What the model answers**  
Same jobs as before — runnable where the data cannot leave.

| Use pattern | Realistic use | Value |
|-------------|---------------|--------|
| **Inverse design** | Design exploration entirely on-prem / restricted environments | No upload of geometry to a vendor cloud |
| **Plant model** | HIL benches in secure labs using local specialists | Matches how defense and regulated industries actually test |
| **Exploration / UQ** | Same, offline | Compliance-compatible workflow |
| **Evidence story** | Model/evidence package travels with the artifact; inference stays local | Procurement-friendly “what is this binary and what claim supports it?” narrative |

**Who cares:** Defense contractors, regulated energy, organizations with controlled data.  
**Evidence role:** Public/subnet evidence and private/customer qualification must remain clearly separated; the chain never becomes authority over classified/customer physics merely because it exists.

**Pitch line:** *“Compete and verify where appropriate; deploy closed where required.”*

---

## Phase 3 — Multi-physics coupling

**Envelope:** True coupled challenges (FSI, conjugate heat, multi-field) with explicit coupling/interface evidence.

**What the model/system answers**  
“Given a coupled setup, how do the linked fields co-evolve under the coupling rules and interface conditions the registered contract requires?”

| Use pattern | Realistic use | Value |
|-------------|---------------|--------|
| **Inverse design** | Joint shape + structure parameters under interface and stress constraints | Coupled objectives without waiting on every full co-simulation |
| **Plant model** | Multi-domain plant for control of systems where structure and flow interact on the timescale of interest | Still envelope-limited; higher realism than sequential-only |
| **Exploration / UQ** | Coupled uncertainty (e.g. flexible structure under variable flow) | Finds failure modes sequential screens miss |
| **Campaign planning** | Decide which designs deserve full co-simulation | Portfolio tool for simulation budgets |

**Who cares:** Multi-physics design cells in auto, aero, energy.  
**Evidence role:** Component qualification does not automatically compose. Interfaces, joint envelope, numerical coupling, and assembled behavior require their own evidence.

**Pitch line:** *“Cheap coupled screening with interface-level evidence, not just good separate component scores.”*

---

## Phase 4 — Production-adjacent 3D / turbulence

**Envelope:** 3D, turbulence-aware benchmarks with production-oriented measurements as scientifically specified. Still not auto-certification.

**What the model/system answers**  
“Inside a production-declared envelope, return the required fields/KPIs fast enough for repeated engineering use.”

| Use pattern | Realistic use | Value |
|-------------|---------------|--------|
| **Inverse design** | Production geometry families; many-query optimization under realistic constraints | Sustained design throughput |
| **Plant model** | Vehicle/process twins and HIL at fidelity the program accepts for that envelope | Real-time or near-real-time where classical 3D is impossible |
| **Exploration / UQ** | Operational envelopes, off-design, manufacturing scatter | Decision support with bounded evidence |
| **Hybrid truth loop** | Fast model proposes; sparse DNS/LES/test anchors | Dense search, sparse high-fidelity truth |

**Who cares:** OEMs, primes, digital-twin programs with budget and process maturity.  
**Evidence role:** Qualification evidence + envelope statement become part of the engineering package; humans and regulators retain authority over airworthiness/safety decisions.

**Pitch line:** *“Production iteration fuel — always with an envelope label and evidence about where the fast model is entitled to operate.”*

---

## Cross-phase teaching map (current learned-model track)

Use this when explaining the early specialist path. It is intentionally a **use-case abstraction**, not a claim that every future Carbon candidate is a neural solution operator.

```text
                    ┌───────────────────────────┐
   Design params    │  Carbon-qualified fast    │  Fields / KPIs
   BCs / ICs   ──►  │  physical model / system  │ ──► stress, flow, T, …
   Materials        │  bounded by evidence       │
                    └───────────────────────────┘
                              │
         ┌────────────────────┼────────────────────┐
         ▼                    ▼                    ▼
  Inverse design      Plant / real-time      UQ & exploration
  (search params)     (next-state / loads)   (many conditions)
                              │
                              ▼
                        Truth / escalation
```

| Job | Question the user is really asking |
|-----|-------------------------------------|
| **Inverse design** | What should we build/set to hit targets? |
| **Plant model** | If we act now, how does the system respond? |
| **Exploration / UQ** | How wide is the outcome band and what uncertainty evidence exists? |
| **Truth hybrid** | Where must we still run full CFD/FEA, experiment, or engineering review? |

---

## Coherent narrative for pitches

1. **Job:** Define what the fast physical model must do inside a stated envelope.  
2. **Discovery:** Let people/agents compete over how to construct it; P0 starts with neural training strategies.  
3. **Evidence:** Independent evaluation determines what survives required physics, robustness, and accuracy checks.  
4. **Product:** The winner is a candidate; a harder context-specific qualification determines what can be used.  
5. **Progression:** Deepen physics first; prove mixed model families later on Challenges we already understand.  
6. **Money:** Partner discovery can start before the full generalized architecture is mature; production claims require stronger evidence.

---

## What not to promise per phase

| Phase | Don’t claim |
|-------|-------------|
| 0 | Industrial design sign-off |
| 1A | Full aircraft certification CFD replacement |
| 1B | Complete engine digital twin for release |
| 2A | “Send us all proprietary data to the chain” |
| 2B | Automatic ATO or automatic regulatory acceptance |
| 3 | Solved general multiphysics or automatic composition of qualification |
| 4 | Regulator-accepted sole authority |

---

## One-sentence curriculum

> **Carbon's early specialist track develops fast, evidence-bounded physical models for design search, real-time response, uncertainty exploration, and hybrid truth workflows — while the broader protocol remains free to admit other construction families when they can be compared and qualified under the same scientific discipline.**

---

*Aligned with the current SPEC phase examples, but subordinate to `System_Identity_and_Roadmap.md` for durable identity/roadmap framing and to domain-owned normative specifications for current implementation.*
