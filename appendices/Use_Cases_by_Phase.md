# Carbon Specialist Use Cases by Phase

**Purpose:** Teach *what a verified Carbon model is for* — regime by regime — without requiring a PDE background.

**Through-line:** Every phase ships the same object: a **learned solution map** (problem setup → physical fields) that has passed **trustless physics gates** on hidden procedural tests. Use cases change as the *physics envelope* gets closer to industry. Verification does not change in kind; only the stakes and buyers do.

**How to read each phase**

| Lens | Meaning |
|------|--------|
| **What the model answers** | Input → output in plain language |
| **Inverse design** | Search designs/parameters using thousands of cheap forward solves |
| **Plant model** | Stand-in for “how the system responds” in control, HIL, or twins |
| **Exploration / UQ** | Sweep many conditions; quantify spread of outcomes |
| **Who cares** | Realistic buyer or user at that maturity |
| **Trust role** | Why gated verification matters for *this* use |

---

## TL;DR

| Phase | Physics maturity | Flagship use case | Primary buyer energy |
|-------|------------------|-------------------|----------------------|
| **0** | Academic PDEs | Methods + teaching gym; prove gates work | Researchers, subnet agents |
| **1A** | Compressible / aero-like | Design sweeps on simplified aero loads | Aero tools teams, advanced hobbyist R&D |
| **1B** | Reacting / sequential FSI | Thermal–structural and flow–structure *screening* | Propulsion/structures screening groups |
| **2A** | Custom + LoRA + intelligence | Customer geometry/load adaptation under license | Engineering orgs wanting *their* envelope |
| **2B** | Air-gap ready | Same maps, deployable in restricted networks | Defense-adjacent, regulated IT |
| **3** | Coupled multi-physics | Joint fluid–structure / conjugate heat *campaigns* | Multi-physics design cells |
| **4** | 3D + turbulence production | Production-adjacent iteration inside certified envelopes | OEMs, primes, digital-twin programs |

Models are never “the full FAA/DoD certifier.” They are **fast, envelope-qualified physics maps** used to explore, screen, look ahead, and fill gaps between expensive truth runs.

---

## Phase 0 — Foundation (Academic PDEs)

**Envelope:** Poisson, Darcy, Burgers, laminar NS, heat, linear elasticity, thermo-elasticity (2D-focused, mesh-converged vs reference solvers).

**What the model answers**  
“Given this initial state / coefficient field / load pattern, what does the solution field look like?”

| Use pattern | Realistic Phase-0 use | Why it’s still valuable |
|-------------|----------------------|-------------------------|
| **Inverse design** | Optimize a conductivity map or source layout to match a target temperature field on a heat equation specialist | Teaches the *workflow* of inverse design on honest gates; publishes recipes agents rediscover |
| **Plant model** | Toy closed-loop demos: 1D/2D “process” whose next state comes from a Burgers or heat operator | Curriculum for control students; not industrial HIL |
| **Exploration / UQ** | Monte Carlo over random permeability fields (Darcy) or ICs (Burgers) | Stress-tests whether the specialist respects conservation under distribution shift |
| **Agentic Autoresearch** | Inner-loop fitness for strategy search (Carbon’s own miners) | Primary *economic* use of Phase-0 models: improve training strategies |
| **Teaching / benchmarks** | Shared gym for SciML methods papers | Comparable, gated leaderboards beat one-off GitHub demos |

**Who cares:** SciML researchers, Bittensor miners/agents, university labs.  
**Trust role:** Proves the exam is real (junk strategies → zero). Without this, later phases have no credibility.

**Pitch line:** *“Phase 0 is the flight-test range for the grading system — not the airliner.”*

---

## Phase 1A — Compressible / Aero-leaning

**Envelope:** Academic set + simplified compressible / transonic-style benchmarks (e.g. airfoil-class problems, wing-body *screening* fidelity — not full vehicle cert).

**What the model answers**  
“Given shape parameters / freestream conditions, what do pressure and approximate load fields look like inside this validated envelope?”

| Use pattern | Realistic use | Value |
|-------------|---------------|--------|
| **Inverse design** | Search airfoil or simple wing parameters for lift/drag/load targets under constraints | 10³–10⁵ evaluations that classical RANS cannot afford in an afternoon |
| **Plant model** | Real-time aero load proxy in a **desktop or HIL software** loop for control-law development (low–mid fidelity envelope) | Controllers get a physics-shaped plant without a wind-tunnel every iteration |
| **Exploration / UQ** | Sweep Mach, α, thickness; map buffet/load sensitivity bands | Early risk picture before heavy CFD campaigns |
| **Screening twin** | “What-if” on condition changes for a fixed simplified geometry | Engineer-in-the-loop, not autonomy |

**Who cares:** Aircraft concept teams, aero tool vendors, university aero + startup eVTOL analysis groups.  
**Trust role:** Hidden stress on shocks/separation-like regimes; gate failures kill “pretty” models that violate conservation or blow up in edge conditions.

**Pitch line:** *“Not replacing the cert CFD deck — multiplying the concept sweeps that happen before you spend that deck.”*

---

## Phase 1B — Reacting flow + sequential FSI-style

**Envelope:** Added reacting / thermal / one-way coupled structure-style challenges (sequential FSI, conjugate-heat-like, high-speed thermal screening).

**What the model answers**  
“Given operating condition and simplified geometry, how do temperature, species (where in scope), and structural response fields evolve or settle *within this sequential coupling story*?”

| Use pattern | Realistic use | Value |
|-------------|---------------|--------|
| **Inverse design** | Cooling channel or liner parameter search under peak-temp and mass constraints | Thermal design iteration without a full conjugate solve each time |
| **Plant model** | Engine/ECU or thermal-protection **HIL** plant at reduced physics: commanded condition → approximate thermal/load state | Hardware tests need a clock-friendly plant; full CFD is too slow |
| **Exploration / UQ** | Chemistry or thermal-boundary uncertainty bands (where UQ gates exist) | Honest spread, not a single optimistic curve |
| **Sequential campaign** | One-way fluid → structure screening before true two-way coupling budget is spent | Filters hopeless designs early |

**Who cares:** Propulsion thermal teams, structures screening, defense-adjacent concept shops (still not full weapon-system authority).  
**Trust role:** Species/energy-style gates and sequential interface checks — where fakes usually break.

**Pitch line:** *“Screen the coupled problem before you pay for the fully coupled truth.”*

---

## Phase 2A — Customization & intelligence

**Envelope:** Same physics families, but **customer-shaped**: LoRA / fine-tune paths, optional structured losses, sponsored challenge geometries — public core + private adaptation patterns (raw proprietary data stays with customer where required).

**What the model answers**  
“Given *our* part family and load deck (inside an agreed envelope), fields and KPIs we care about — with evidence trail.”

| Use pattern | Realistic use | Value |
|-------------|---------------|--------|
| **Inverse design** | Customer optimizer on *their* parameterization (CAD variables, thickness maps) using a specialist adapted to their regime | Design search on the geometry class they actually ship |
| **Plant model** | Plant tuned to their actuator/sensor rates for software-in-the-loop | Closer match to their control lab |
| **Exploration / UQ** | Production variability (tolerance, material bands) on the adapted model | Quality and robustness stories tied to *their* drawings |
| **Sponsored challenges** | OEM funds a challenge; network searches strategies; sponsor gets licensed specialist | Aligns subnet emissions with paid demand |

**Who cares:** Mid-size engineering orgs, tool partners, innovation groups inside primes.  
**Trust role:** Same gate philosophy; adaptation must **re-pass** envelope tests — fine-tune cannot silently void verification.

**Pitch line:** *“Public competition finds the recipe; your envelope and license make it yours — still gated.”*

---

## Phase 2B — Air-gap / regulated deployment

**Envelope:** Physics as in 1–2A; **deployment** in restricted networks (air-gap toolkit, pre-provisioned seeds, no phone-home inference).

**What the model answers**  
Same maps as before — **runnable where the data cannot leave.**

| Use pattern | Realistic use | Value |
|-------------|---------------|--------|
| **Inverse design** | Design exploration entirely on-prem / IL-style environments | No upload of geometry to a vendor cloud |
| **Plant model** | HIL benches in secure labs using local specialists | Matches how defense and regulated industries actually test |
| **Exploration / UQ** | Same, offline | Compliance-compatible workflow |
| **Verification story** | Model card + gate evidence travels with the artifact; inference stays local | Procurement-friendly “what is this binary?” narrative |

**Who cares:** Defense contractors, regulated energy, anyone with ITAR/EAR-like constraints.  
**Trust role:** Trustless *training/exam* on public regimes; **deployment trust** is isolation + evidence pack, not “the blockchain sees your geometry.”

**Pitch line:** *“Compete and verify in the open; deploy closed.”*

---

## Phase 3 — Multi-physics coupling

**Envelope:** True coupled challenges (FSI, conjugate heat, multi-field) with coupling gates (interface continuity, iteration convergence).

**What the model answers**  
“Given a coupled setup, how do the linked fields co-evolve under the coupling rules we gated on?”

| Use pattern | Realistic use | Value |
|-------------|---------------|--------|
| **Inverse design** | Joint shape + structure parameters under interface and stress constraints | Coupled objectives without waiting on every full co-simulation |
| **Plant model** | Multi-domain plant for control of systems where structure and flow interact on the timescale of interest | Still envelope-limited; higher realism than sequential-only |
| **Exploration / UQ** | Coupled uncertainty (e.g. flexible structure under variable flow) | Finds failure modes sequential screens miss |
| **Campaign planning** | Decide which designs deserve full preCICE / proprietary co-sim | Portfolio tool for simulation budgets |

**Who cares:** Multi-physics design cells in auto, aero, energy.  
**Trust role:** Coupling gates are the product; single-physics accuracy is not enough.

**Pitch line:** *“Cheap coupled screening with interface-level failure modes, not just pretty separate fields.”*

---

## Phase 4 — Production-adjacent 3D / turbulence

**Envelope:** 3D, turbulence-aware benchmarks with production-oriented gates (separation, spectra, wall metrics — as specified). Still **not** auto-certification.

**What the model answers**  
“Inside a production-declared envelope, high-dimensional fields fast enough for iteration and twins.”

| Use pattern | Realistic use | Value |
|-------------|---------------|--------|
| **Inverse design** | Production geometry families; many-query optimization under realistic constraints | Sustained design throughput |
| **Plant model** | Vehicle/process twins and HIL at fidelity the program accepts for *that* envelope | Real-time or near-real-time where classical 3D is impossible |
| **Exploration / UQ** | Operational envelopes, off-design, manufacturing scatter | Safety and performance margins with volume |
| **Hybrid truth loop** | Surrogate proposes; sparse DNS/LES/test anchors | Best economics: dense search, sparse truth |

**Who cares:** OEMs, primes, digital-twin programs with budget and process maturity.  
**Trust role:** Model card + gate history + envelope statement become part of the engineering evidence pack; humans and regulators still own airworthiness/safety decisions.

**Pitch line:** *“Production iteration fuel — always with an envelope label and a gate receipt.”*

---

## Cross-phase teaching map (same model, four jobs)

Use this slide repeatedly; only the *envelope* changes.

```text
                    ┌─────────────────────────┐
   Design params    │  Verified Carbon map    │  Fields / KPIs
   BCs / ICs   ──►  │  (solution operator)    │ ──►  stress, flow, T, …
   Materials        │  gated + model-carded   │
                    └─────────────────────────┘
                              │
         ┌────────────────────┼────────────────────┐
         ▼                    ▼                    ▼
  Inverse design      Plant / real-time      UQ & exploration
  (search params)     (next-state / loads)   (many conditions)
```

| Job | Question the user is really asking |
|-----|-------------------------------------|
| **Inverse design** | What should we build/set to hit targets? |
| **Plant model** | If we act now, how does the system respond? |
| **Exploration / UQ** | How wide is the outcome band? |
| **Truth hybrid** | Where must we still run full CFD/FEA or test? |

---

## Coherent narrative for pitches

1. **Object:** Always a gated solution map — not a chatbot, not a full certifier.  
2. **Progression:** Academic gym → aero/thermal screening → customer envelopes → secure deploy → coupled → production-adjacent.  
3. **Value:** Multiply the number of honest physics queries per dollar; spend scarce high-fidelity runs on shortlists.  
4. **Trust:** Same exam structure at every phase; harder physics and coupling gates as you climb.  
5. **Money:** Early — research + subnet demand; later — sponsored challenges and licensed specialists.

---

## What not to promise per phase

| Phase | Don’t claim |
|-------|-------------|
| 0 | Industrial design sign-off |
| 1A | Full aircraft certification CFD replacement |
| 1B | Complete engine digital twin for release |
| 2A | “Send us all proprietary data to the chain” |
| 2B | Automatic ATO |
| 3 | Solved general multiphysics |
| 4 | Regulator-accepted sole authority |

---

## One-sentence curriculum

> **Carbon models are envelope-qualified physics maps: use them to search designs, drive real-time plant approximations, and explore uncertainty — and use trustless gates so those maps earn their place between expensive simulations, not instead of engineering judgment.**

---

*Aligned with SPEC phase structure. Update regime names as challenge IDs freeze; keep the four jobs stable for teaching.*
