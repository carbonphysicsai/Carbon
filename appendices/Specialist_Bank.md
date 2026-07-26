# Specialist Bank — Landscape → Specialist Pipeline & Phase Customers

## TL;DR

**Job:** Productize landscape evidence into regime-scoped specialists without wrecking incentives or revenue.

**Dual threshold (product-first, search-safe)**

| Layer | Exam depth | Purpose |
|-------|------------|--------|
| **Miner → validator** | Lean: physics gates + stress + short rollout + card margins | Search strategies; high throughput; **get data** |
| **Landscape → Specialist Bank** | **Product battery** (mandatory for commercial SKU) | Inverse-design bakeoff, adversarial stress, plant/rollout depth, latency class, ONNX, escalation notes |

Leaderboard rank ≠ shelf product. **No commercial specialist ships without the product battery.**  
Heavy evals run rarely (promote candidates), not on every submission.

**Pipeline:** Model Cards → causal/symbolic fit → rank opportunities → recipe from *effects* (not single winners) → controlled retrain → **fresh** lean gates → **product battery** → bank.

**Dual egress (do not mix)**
| Path | Who | What they get |
|------|-----|---------------|
| **Public / miner (free)** | Miners, agents | Noisy, lagged prior / warm-start derivatives only — never full weights or exact bank recipe |
| **Commercial (paid)** | Buyers | Closed SKU = ONNX + exact recipe + Model Card + **product-battery certs** + license + updates (+ optional air-gap) |

Competition never requires purchase. Open the catalog and verification story; close the certified artifact.

**Why closed sells:** deployable certified artifact, assurance language, inverse-design/plant evidence, license, update channel — not a public weights dump.

**Phase buyers (hero):** 0 SciML baselines → 1A aero → 1B propulsion/CHT/stores → 2A OEM adapters → 2B sealed dual-regime → 3 coupled twins → 4 fleet/extreme.

---

**Carbon Subnet**  
**Version:** 1.2 (July 2026)  
**Status:** Core Product & Engineering Appendix  
**Related:** [`appendices/Landscape_Agent.md`](./Landscape_Agent.md), [`appendices/Use_Cases_by_Phase.md`](./Use_Cases_by_Phase.md), `SPEC.md`

---

## 1. Purpose

This document defines:

1. **How** Landscape Agent data becomes a banked specialist (select → specify → construct → verify → **product battery** → package → operate).
2. **What** a specialist is (and is not).
3. **Dual threshold:** lean miner→validator exam vs full product battery at bank graduation.
4. **Dual egress:** noisy public/miner path vs closed commercial SKU path.
5. **Which regimes** specialists target.
6. **Who buys** (or adopts) specialists at each Carbon phase — customer and motivation.

The Specialist Bank is Port D of the Landscape Value Router: private causal/symbolic intelligence becomes versioned, re-verified **product** artifacts. Only **noisy derivatives** flow to miners; **full certified artifacts** are commercial products.

---

## 2. Dual Threshold Strategy (Product-First, Search-Safe)

### 2.1 The problem this solves

Carbon’s value story is inverse design, plant-style response, UQ/exploration, and hybrid truth — not leaderboard screenshots.

If **every** product check runs on the miner→validator path:

- Validator compute explodes (inverse-design opts, long adversarial searches, latency benches).
- Throughput and participation drop.
- You tax every attempt the same as a ship candidate.

If **no** product check runs until after a sale conversation:

- Miners Goodhart terminal field error.
- “Winners” fail the first customer optimizer or HIL rollout.
- Credibility dies at the worst moment.

**Rule:** grade **search incentives** lean and continuous; grade **shelf credibility** heavy and rare.

```text
Every submission     →  lean physics exam + card margins
Top / promote path   →  product battery (inverse design, adversarial, plant depth, export, latency)
Ship commercial SKU  →  only if product battery passes
Landscape            →  learns from lean scores AND promotion pass/fail
```

### 2.2 Miner → validator (lean — always)

Purpose: **comparable search signal** and **telemetry volume**.

| Include | Role |
|---------|------|
| Physics gates (conservation, residual, finite, challenge-specific) | Core trust |
| Stress category suite + coverage threshold | OOD robustness |
| **Short rollout stability** (cheap multi-step; not full HIL horizon) | Stops pure one-shot maps that cannot serve plant-shaped jobs |
| Envelope statement + stress margins on Model Card | Hybrid-truth teaching; zero train cost |
| Strategy-only handoff; seed isolation | Unchanged security boundary |

| Explicitly **not** on the default path | Why |
|--------------------------------------|-----|
| Full inverse-design bakeoff (large query budgets) | Cost; product-shaped |
| Heavy adversarial optimizer-vs-model | Cost; product-shaped |
| ONNX export + latency SLA measurement | Packaging |
| Full conformal UQ suites | Later tier / product option |

Validator answers: *“Did this strategy learn physics that survives hidden stress and basic time behavior?”*  
Not: *“Is this ready for an OEM design loop?”*

### 2.3 Landscape → Specialist (product battery — mandatory for commercial SKU)

Purpose: **credibility for the jobs we sell** (see `Use_Cases_by_Phase.md`).

Promotion / bank entry for a **full surrogate SKU** requires **all** of the following (module-only packs may use a reduced subset — see §2.5).

#### Product battery checklist

| Gate ID | Test | Pass criterion (v1 policy; tune per regime) |
|---------|------|---------------------------------------------|
| **PB-PHYS** | Fresh controlled retrain + full physics gates + stress suite on **new** seeds | All hard gates pass; robustness ≥ baseline prior policy |
| **PB-ROLL** | Plant/rollout suite at product depth (multi-step / Δt map as defined by regime) | Rollout error and stability within regime τ; no blow-up |
| **PB-INV** | Inverse-design bakeoff: fixed targets + constraints + fixed query budget | Constraint satisfaction rate ≥ policy; improves vs noisy-prior scaffold |
| **PB-ADV** | Adversarial stress: short optimizer under box constraints maximizing violation / residual | Max found violation ≤ policy; document residual holes on card |
| **PB-LAT** | Batch inference latency class on reference hardware profile | p95 latency ≤ declared class (e.g. L1 interactive / L2 batch) |
| **PB-ART** | Export deployable artifact (ONNX or approved equiv.) + I/O schema | Round-trip numeric parity within ε vs training framework |
| **PB-ESC** | Escalation notes on Model Card | Written envelope edges + “call hi-fi when…” tied to observed failures |

**Failure on any mandatory PB-* → do not bank as commercial full SKU.**  
Negative evidence returns to Landscape (promotion_fail records). Rank alone never overrides a PB fail.

#### Why inverse design and adversarial belong here (not on every miner)

- Customer inverse design **is** an adversary: it searches for in-envelope inputs that break constraints.
- Random stress ≠ directed search.
- Running that battery on every submission is the wrong place to spend validator GPU; running it on **graduates** is how the shelf stays honest.

#### Why short rollout stays on the lean path

Without *any* time signal on-chain, search collapses to snapshot matching and the product battery inherits a population that never optimized rollout. A **cheap** multi-step gate on validators is incentive alignment; **deep** plant suites stay in PB-ROLL.

### 2.4 What Landscape learns (extra definition = good)

| Signal | Source |
|--------|--------|
| Lean gate/stress/rollout vectors | Every Model Card |
| PB pass/fail by gate ID | Promotion attempts |
| INV failure modes (which constraints break) | PB-INV |
| ADV hole locations (envelope edge patterns) | PB-ADV |
| Latency class feasibility | PB-LAT |

These are **high-value, low-frequency** labels. They improve opportunity ranking (“this regime’s winners die on inverse design”) without charging every miner for the OEM exam.

### 2.5 Module-type vs full SKU battery

| Module type | Battery |
|-------------|--------|
| Loss pack / curriculum / backbone recipe (method modules) | PB-PHYS required; PB-INV/ROLL/ADV optional or smoke-level |
| **Full surrogate SKU** (deployable ONNX product) | **All PB-*** mandatory |
| Air-gap sealed pack | All PB-* + offline install verification |

### 2.6 Phase timing

| Phase | Lean validator | Product battery |
|-------|----------------|-----------------|
| **0** | Physics + stress + short rollout + card margins | Full PB suite on **catalog credibility SKUs** (even academic PDEs) — rehearse the muscle |
| **1A–1B** | Same + regime gates | PB mandatory for any commercial aero/thermal SKU; sponsored challenges may **define** extra PB tests in the challenge brief |
| **2A+** | Same | PB + customer envelope adaptation must **re-pass** PB after fine-tune/LoRA |
| **2B** | Same | PB + sealed-pack offline checks |
| **3–4** | Same + coupling gates | PB + coupling-specific INV/ROLL definitions |

Do not wait for the first OEM to invent the battery. Do not put the OEM battery on every Phase-0 miner attempt.

### 2.7 Non-negotiable incentives

- **No pay-to-compete** — product battery is not a toll to submit strategies.
- **No emissions weight** from specialist purchase or PB status.
- **No full SKU on miner API** — dual egress unchanged (§3).
- Leaderboard / emissions remain functions of **lean validator** outcomes only.

---

## 3. Dual Egress Rule (Non-Negotiable)

The bank has **exactly two egress paths**. Mixing them destroys either incentives or revenue.

```text
Specialist Bank
       │
       ├──────────────────────────────────────────────┐
       ▼                                              ▼
 PUBLIC / MINER (free)                         COMMERCIAL (paid)
 Noisy, lagged, incomplete                     Closed specialist SKU
 derivatives → prior packs                     = certified weights
 and warm-start API only                       + exact bank recipe
                                               + Model Card
 Never: full weights,                          + product-battery certs
        exact bank recipe,                     + license
        tight causal coefficients,             + update channel
        bank verify / PB seeds                 (+ optional air-gap seal)

 Competition scoring NEVER depends on purchasing the commercial path.
```

### Why miner path must be noisy

Full specialist warm-start (exact recipe + weights + tight bands) recreates champion exposure:

- Search collapses onto one artifact  
- Cloning dominates exploration  
- Landscape moat leaks through the warm-start API  

**Subnet rule:** miners never pull a complete `specialist_bank_item`. Banked regimes may **inform** the daily noisy prior pack (same Port A path and noise/lag policy as `Landscape_Agent.md`). Warm-start ≠ SKU download.

### Why commercial path must be closed

If the full specialist (weights + exact strategy + certs) is open-sourced as a free dump, many buyers will not pay. Carbon sells a **verified surrogate distribution** with **job-shaped evidence** (inverse design, plant depth), not a public folder of weights.

| Closed commercial asset | Why buyers pay |
|-------------------------|----------------|
| Deployable ONNX (or equiv.) from bank verification retrain | Ready to run; avoids re-train cost |
| Exact strategy recipe used in the certified run | Reproducible specialization / fine-tune start |
| Gate certificate + **product-battery report** | Procurement / IV&V / “will it survive my optimizer?” |
| Version channel (re-verify when gates/generators move) | Artifact does not silently rot |
| Commercial / IP / private license | Legal clarity for productization |
| Air-gap / sealed packs | Dual-regime offline install |
| Support / SLA / integration | What enterprises put on a PO |

| May stay open (network health, not the SKU) | Role |
|---------------------------------------------|------|
| Coarse regime catalog (“Burgers–FNO specialist exists”) | Marketing + orientation |
| Noisy priors derived from banked regimes | Free search orientation |
| Public Model Card *summaries* / marketing evidence | Trust without full recipe |
| Descriptions of method *classes* | Scientific credibility |

**Open the verification standard and the coarse catalog. Close the certified artifact and the rights/ops around it.**

Phase-0 catalog SKUs are partly a credibility wedge; margin concentrates as regimes get harder (1A→4) and licenses get more private (Tier 3/4, dual-regime).

Someone may approximate a specialist from noisy priors and publish a clone. That is acceptable: commercial value is **assurance, envelope, job-shaped tests, license, and ongoing verify** — not eternal secrecy of every loss weight.

---

## 4. What a Specialist Is (and Is Not)

### Is

- A **regime-scoped**, reusable artifact encoding training methodology (and optionally weights).
- Built from **landscape evidence** (support density, causal stability, symbolic structure).
- **Re-verified** under fresh hidden stress + physics gates before bank entry.
- For **full SKUs:** passed the **product battery** (inverse design, adversarial, plant depth, latency, export).
- Versioned with **provenance** back to landscape artifact IDs and data cutoff.
- **Commercially** usable as: closed product SKU (ONNX + Model Card + gate + PB certs + license) or sealed air-gap pack.
- **Publicly** usable only via noisy derivatives in prior / warm-start packs.

### Is Not

- Yesterday’s challenge-winner checkpoint, rebranded.
- A substitute for full validator evaluation when re-entering competition.
- An open export of the causal graph or Model Card lake.
- A full-fidelity free download for miners.
- Mandatory for miners to compete (submission remains free).
- “Passed lean gates only” without PB — that is a **leaderboard artifact**, not a commercial specialist.

### Module types

| Type | Contents | Typical use |
|------|----------|-------------|
| **Loss pack** | Structured loss terms + default weight bands (+ optional MT snippets) | Highest early ROI; commercial or (noisy) prior fuel |
| **Curriculum block** | Multi-fidelity / resolution / mode schedules with causal support | Training dynamics |
| **Init / prior policy** | Scaffold + high-impact field masks | **Noisy** agent cold start only |
| **Backbone adapter recipe** | Hyper ranges / patterns for a backbone family | FNO vs GINO vs … |
| **Composite specialist** | Locked combination of the above | Internal + **closed** product |
| **Full surrogate SKU** | ONNX + Model Card + gate + **PB certs** from controlled retrain | Primary **paid** product |

**Default path:** causal evidence → loss pack + curriculum → composite recipe → controlled retrain → lean re-gate → **product battery** → bank entry → dual egress.

---

## 5. Regime Key

Specialists are aimed at **regimes**, not single leaderboard rows:

```text
regime = {
  physics_class,       # e.g. burgers, heat, elasticity, transonic_compressible
  challenge_family,    # e.g. poisson_2d, naca_transonic, turekhron_fsi
  backbone_family,     # fno | gino | wno | transolver | ...
  envelope,            # non-dimensional ranges, BC classes, stress families covered
  fidelity_class       # 2d_single | sequential_fsi | coupled_3d | ...
  product_jobs         # optional tags: inverse_design | plant | uq | hybrid_truth
}
```

A specialist that only works on one fixed seed is a leaderboard artifact.  
A specialist that holds on a **family + envelope** and passes **job-shaped PB tests** is a product.

Sponsored challenges should declare `product_jobs` in the brief so PB-INV / PB-ROLL definitions match what the sponsor will use.

---

## 6. Landscape Value Signals → What to Build

The Landscape Agent ranks **regime × module_type** opportunities. It does not auto-publish specialists.

| Signal | Source | Role |
|--------|--------|------|
| Causal support | D3 | Levers that *cause* robustness / gate-pass |
| Support density | D1 | Enough verified cards |
| Stability | D3 across windows | Direction holds over time |
| Frontier residual / maturity | D5 | Productize vs keep searching |
| Failure concentration | D4 | Clean module targets |
| Transfer strength | D7 | Neighboring regimes |
| **Promotion / PB outcomes** | Bank pipeline | Job-shaped failure modes |
| Commercial / phase priority | Product + roadmap | Demand and sequencing |
| Cost-to-serve | D9 / ops | Train + verify + **PB** affordability |

**Opportunity score (v1):**

```text
opportunity(regime, module_type) =
  causal_clarity
  × support_density
  × stability
  × max(commercial_priority, phase_roadmap_priority)
  × (1 − pure_clone_saturation)
  × (1 + pb_historical_pass_rate_bonus)   # regimes that graduate cleanly rank up
  / expected_distill_and_verify_and_pb_cost
```

Governance / product sets commercial priority and approves the queue.

---

## 7. Pipeline — Landscape → Specialist Bank

```text
Model Cards (lean verified)
        │
        ▼
Landscape fitters (D2 symbolic, D3 causal, D4 failures, D5 frontier, D7 transfer, PB outcomes)
        │
        ▼
Opportunity ranker  →  regime × module_type queue
        │
        ▼
Candidate Spec (recipe from causal bands + masks — not single-winner JSON)
        │
        ▼
Construct recipe + controlled retrain (validator-grade, new stress seeds)
        │
        ▼
Lean re-gate (PB-PHYS core)
        │
        ▼
PRODUCT BATTERY (full SKU: PB-ROLL, PB-INV, PB-ADV, PB-LAT, PB-ART, PB-ESC)
        │
        ▼
Bank gate (all required PB pass) ──fail──► landscape negative evidence
        │ pass
        ▼
Specialist Bank (versioned + lineage + PB report)
        │
        ├──────────────────────┐
        ▼                      ▼
PUBLIC EGRESS            COMMERCIAL EGRESS
Noisy prior pack         Closed SKU + license + PB certs
```

### Step A — Select

1. Compute opportunity scores.  
2. Filter on minimum support, causal stability, non-saturation.  
3. Apply commercial / phase priority; approve queue.

### Step B — Specify

```text
specialist_candidate_v1:
  regime: { physics_class, challenge_family, backbone_family, envelope, fidelity_class, product_jobs[] }
  module_type: loss_pack | curriculum | composite | full_surrogate
  causal_support: [effect_ids...]
  symbolic_support: [expr_ids...]          # optional
  recipe:
    strategy_scaffold: { ... }             # from bands/masks, not raw winner JSON
    frozen_fields: [...]
    free_fields: [...]
  success_criteria:
    min_gate_all_pass_rate
    min_robustness_component
    max_regression_vs_baseline_prior
    product_battery: [PB-PHYS, PB-ROLL, ...]   # required set by module_type
  provenance: { landscape_version, data_cutoff_block }
```

### Step C — Construct

- **Loss pack:** enable causally positive terms; weights at band centers; attach MT snippets if available.  
- **Curriculum:** encode scales from positive treatments.  
- **Composite:** union + schema-valid strategy JSON.  
- **Weights:** controlled validator-equivalent trains under fixed budget policy.

### Step D — Verify lean + product battery (mandatory)

1. Fresh train from recipe (not upload-only weights).  
2. Hidden stress + full physics gates with **new** seeds (not the cards that justified the opportunity).  
3. Beat or match agreed baseline (e.g. noisy prior scaffold).  
4. **If full_surrogate:** run complete product battery (§2.3); record per-gate vectors.  
5. Record components, lean gates, and PB report on the bank Model Card.

Failure → do not bank; feed negative evidence back to landscape.

### Step E — Package

```text
specialist_bank_item_v1:
  specialist_id, version, regime, module_type
  artifacts: [strategy_json, onnx, mt_snippets]   # commercial only
  model_card_ref, gate_certificate, product_battery_report
  latency_class, io_schema_ref
  provenance:
    landscape_version, causal_ids[], symbolic_ids[],
    supporting_card_count, data_cutoff_block
  egress:
    public_derivative_policy: noisy_prior_pack_v1   # required
    commercial_license_class: tier1_catalog | tier3_ip | tier4_private | airgap
  retirement_policy
```

Public derivative generation applies the same noise + lag rules as Landscape prior packs (`noise_manifest`, daily lag, no exact weights).

### Step F — Operate

| Channel | Rule |
|---------|------|
| **Miner warm-start** | **Noisy derivatives only** via prior/warm-start API; full competition eval still required; never full bank item |
| **Product SKU** | Closed: ONNX + exact recipe + card + lean certs + **PB report** + license; inference / offline fine-tune |
| **Air-gap pack** | Sealed closed distribution; offline; one-way public → private |
| **Refresh** | Re-verify lean + PB when landscape_version or gate taxonomy advances; commercial channel gets updates |
| **Retire** | Failed re-check, PB regression, or regime redefinition |

### Policy rules

- Recipes from **effects**, not single winners.  
- Bank verification seeds ≠ opportunity-supporting eval seeds ≠ PB seeds where feasible.  
- **No pay-to-compete.**  
- **No full specialist on the miner API.**  
- No specialist score in emissions.  
- Prefer composable modules early; full SKUs when verify + PB cost is justified.  
- Open catalog / noisy priors; close certified artifacts.  
- **Full SKU ⇒ product battery pass.**

---

## 8. Worked Example (Phase 0)

**Signals:** On `physics_class=burgers`, `backbone_family=fno`: conservation-penalty weight band and a resolution curriculum scale show stable positive causal effects on stress robustness; n≈120 cards; Phase-0 catalog priority high; `product_jobs: [inverse_design, plant]`.

**Candidate:** composite loss pack + curriculum for Burgers–FNO envelope → full surrogate SKU track.

**Construct:** scaffold with those terms enabled, band-center weights, curriculum phases from D3; other fields weakly defaulted.

**Lean verify:** multiple controlled retrains, new stress seeds, full gates, short rollout; must improve robustness vs baseline prior without accuracy collapse.

**Product battery:**

- PB-INV: hit target late-time mean energy / shape metrics under viscosity box constraints within query budget.  
- PB-ADV: short Adam search maximizing residual under envelope; record worst case on card.  
- PB-ROLL: multi-step rollout τ.  
- PB-LAT / PB-ART: ONNX + latency class on reference GPU.  
- PB-ESC: document low-ν edge behavior.

**Bank:** `specialist_burgers_fno_conservation_v1` with Model Card, ONNX, causal_id provenance, **PB report**.

**Egress:**

- **Public:** noisy prior pack fields influenced by this regime (masks, coarse bands, no ONNX, no exact recipe).  
- **Commercial:** closed Tier-1 SKU for teams that want a verified Burgers-class operator baseline with certs, **job-shaped evidence**, and license.

---

## 9. Who Wants a Specialist at Each Phase

Customers differ by **physics maturity**, **regulatory pressure**, and **whether they need a method pack vs a deployable surrogate**. Below: primary buyer, secondary buyer, and *why this phase’s specialists matter*.

Miner “adoption” in every phase means **noisy warm-start only**, not free SKU access.  
Buyers care that commercial SKUs list **product-battery evidence**, not only lean gate screenshots.

---

### Phase 0 — Core single-physics PDEs  
*(Poisson, Darcy, Burgers, laminar NS, Heat, Elasticity, Thermo-elasticity)*

| Role | Who | Why they want it |
|------|-----|------------------|
| **Primary (buy)** | Simulation / SciML teams inside mid-size CAE users and startups | Cheap, **certified** baselines for canonical operators; replace ad-hoc PINN/NO notebooks with gate + PB evidence and a deployable artifact |
| **Primary (buy)** | University labs & national-lab pilot groups that need procurement-friendly artifacts | Benchmarking and known-good deployables with license clarity |
| **Secondary (buy)** | Tooling vendors (early design partners) | Embed a verified heat / elasticity / Darcy surrogate in demos; low ITAR risk |
| **Secondary (free noisy)** | Serious miners / agent operators | Noisy warm-start quality; faster path to first gate-pass (optional, not required) |

**Why Phase 0 specialists sell:**  
Trust is earned on problems domain experts already understand. A Burgers or Heat specialist with conservation gates **and** a thin inverse-design / rollout PB report is the **credibility SKU**. Revenue is smaller per unit; strategic value is proof that the bank, Model Cards, and product battery are real.

**Typical offer:** Closed full surrogate SKU + PB report + optional support; low Tier-1 list price.

---

### Phase 1A — Compressible flow  
*(NACA 0012 transonic flutter-class, NASA CRM wing-body-class)*

| Role | Who | Why they want it |
|------|-----|------------------|
| **Primary (buy)** | Aerospace airframe & aeroelasticity groups | Fast **certified** surrogates for design sweeps with INV-style evidence |
| **Primary (buy)** | Defense / UAV airframe contractors (unclassified programs) | Loads screening with verification + plant-depth evidence |
| **Secondary (buy)** | Wind-tunnel & flight-test correlation teams | Licensed emulator between expensive test points |
| **Secondary (buy)** | CAE ISVs | OEM-facing demos with Carbon gate + PB certs under commercial terms |

**Why Phase 1A specialists sell:**  
OEM-shaped geometry and compressible physics. Buyers pay for shock/stability evidence **and** a closed artifact that survives their design optimizer under license.

**Typical offer:** Closed composite + full SKU; higher Tier-1; lead-in to sponsored challenges (Tier 2/3) with sponsor-defined PB tests.

---

### Phase 1B — Reacting flow + sequential FSI + CHT + 6-DOF  
*(HIFiRE-class, Turek/Hron sequential FSI, store separation, turbine blade heat transfer)*

| Role | Who | Why they want it |
|------|-----|------------------|
| **Primary (buy)** | Propulsion & hypersonics groups | Species/energy-aware certified surrogates; every full-fidelity run is extreme-cost |
| **Primary (buy)** | Turbomachinery / heat-transfer teams | CHT-adjacent licensed surrogates for DOE |
| **Primary (buy)** | Weapons / stores integration (unclassified or dual-use) | 6-DOF emulators under commercial license |
| **Secondary (buy)** | Multiphysics platform teams | Sequential FSI blocks as licensed components before Phase 3 |

**Why Phase 1B specialists sell:**  
High campaign cost + assurance language + job-shaped PB. Sponsored challenges carry more revenue mix; catalog SKUs stay closed.

**Typical offer:** Closed regime SKUs + Tier 2–4 sponsored challenges.

---

### Phase 2A — Customization & intelligence  
*(LoRA / adapters, Abaqus-class custom data paths, MT structured losses in product form)*

| Role | Who | Why they want it |
|------|-----|------------------|
| **Primary (buy)** | OEM methods groups with existing FEA/CFD libraries | Licensed adapters specialized to *their* representation; **re-PB after adapt** |
| **Primary (buy)** | Digital-thread / PLM integration teams | Specialists with commercial terms that plug into model trees |
| **Secondary** | Carbon product services | Higher-margin “specialize this backbone to my regime” |

**Why Phase 2A specialists sell:**  
Buyer wants **specialization under license**, not a public method note. Adaptation without re-PB is a credibility bug — policy forbids it for full SKUs.

**Typical offer:** Closed adapter recipes + composites; services on Tier-2/3 challenges.

---

### Phase 2B — Air-gap + coupling prep  
*(Air-gapped toolkit, sequential multiphysics ladder, preCICE-ready architecture)*

| Role | Who | Why they want it |
|------|-----|------------------|
| **Primary (buy)** | Defense primes & regulated energy | **Sealed closed packs** that install offline; public discovery, private fine-tune |
| **Primary (buy)** | Security / accreditation offices | Dual-regime evidence with controlled distribution |
| **Secondary (buy)** | Coupling infrastructure teams | Licensed components on the sequential multiphysics ladder |

**Why Phase 2B specialists sell:**  
Deployability under isolation. Open weights would defeat the product. PB reports travel with the sealed pack.

**Typical offer:** Sealed air-gap specialist packs; dual-regime services; Tier-4 private challenge prep.

---

### Phase 3 — Coupled multiphysics  
*(preCICE FSI, CHT, thermo-elasticity multi-field)*

| Role | Who | Why they want it |
|------|-----|------------------|
| **Primary (buy)** | Full-vehicle / full-system digital twin programs | Licensed coupled surrogates with interface/convergence + PB-INV on coupled targets |
| **Primary (buy)** | Primes on integrated aero-thermal-structural loops | Verified coupled blocks under program license |
| **Secondary (buy)** | Platform vendors | Carbon-verified coupled blocks under partner terms |

**Why Phase 3 specialists sell:**  
System-level, program-priced, closed bundles with coupling-aware product tests.

**Typical offer:** Closed coupled composites; Tier-3/4 challenges; registry-backed bundles.

---

### Phase 4 — Production 3D + turbulence + extreme regimes  
*(3D FSI/CHT/thermo-elasticity + turbulence; hypersonic 6-DOF + reacting + ablation-class)*

| Role | Who | Why they want it |
|------|-----|------------------|
| **Primary (buy)** | Production digital-twin and fleet digital-thread owners | Licensed 3D turbulent multiphysics surrogates for ops and design-to-fleet loops |
| **Primary (buy)** | Hypersonics / extreme-environment programs | Ablation- and reacting-aware specialists under strict license and evidence packages |
| **Secondary (buy)** | Certification / assurance support (long tail) | Evidence-rich closed Model Card + PB packages |

**Why Phase 4 specialists sell:**  
Program infrastructure. Highest willingness to pay; closed distribution and full PB assumed.

**Typical offer:** Program-priced closed SKUs; multi-year maintenance; Tier-4 private + DoD evidence packages.

---

## 10. Customer Summary Matrix

| Phase | Hero customer | Core job-to-be-done | Specialist shape |
|-------|---------------|---------------------|------------------|
| **0** | SciML / sim teams, labs | Trusted **certified** canonical baselines | Closed SKUs + **PB report** |
| **1A** | Aero airframe & aeroelasticity | Design-loop speed + evidence | Closed compressible SKUs + INV/ROLL PB |
| **1B** | Propulsion, turbomachinery, stores | Cut cost of sequential multiphysics campaigns | Closed reacting / CHT / 6-DOF SKUs |
| **2A** | OEM methods groups | Specialize verified methods to *our* representation | Closed adapters; **re-PB after adapt** |
| **2B** | Primes, regulated energy | Offline, dual-regime deployable intelligence | Sealed packs + PB + provenance |
| **3** | System digital-twin programs | Coupled multiphysics building blocks | Closed coupled composites + PB |
| **4** | Fleet / extreme-environment programs | Production 3D turbulent & extreme surrogates | Program closed SKUs + full evidence |

**Cross-cutting**

- **Agent miners:** free **noisy** warm-starts only (efficiency, not SKU rights).  
- **Tooling platforms:** embed or call **licensed** SKUs; verification gas / registry.  
- **Sponsors:** pay to *create* regimes the bank does not yet cover (Tier 2–4), with IP terms that stay closed; may **extend PB definitions** in the challenge brief.

---

## 11. GTM Linkage

| Bank output | GTM engine | Open or closed |
|-------------|------------|----------------|
| Noisy prior derivatives | Miner MCP / Port A | Open (free, noisy) |
| Coarse catalog listing | Marketing / roadmap | Open |
| Phase-0/1 catalog SKUs | Specialist Bank Tier 1 | **Closed** (+ PB report) |
| Customer geometry / envelope | Sponsored Challenges Tier 2–4 | **Closed** per tier IP |
| Sealed packs + dual-regime | DoD / regulated path | **Closed** |
| Registry-backed certs + PB | Verification gas / partners | Attestation service; artifact remains licensed |

Landscape opportunity scores: visible to **product**; optional coarse public roadmap — never raw causal coefficients or full recipes.

---

## 12. Success Metrics for the Pipeline

| Stage | Metric |
|-------|--------|
| Selection | % of queued candidates that pass lean bank verify |
| Construction | Time from opportunity rank → candidate spec |
| Lean verify | Gate all-pass rate; robustness vs baseline |
| **Product battery** | PB pass rate by gate ID; INV constraint rate; ADV max violation |
| Product | Attach rate, renewal, sponsored upsell from catalog |
| Network | Noisy warm-start users’ time-to-first-gate-pass (observational) |
| Moat | Bank quality under ablation of public prior detail; no miner API serving full SKUs |
| Commercial integrity | Zero requirement to purchase for competition eligibility |
| **Goodhart guard** | Correlation of lean rank vs PB pass — monitor divergence; tighten lean rollout if rank≢PB |

---

## 13. Thesis

Specialists are how Carbon **turns private landscape intelligence into objects the market understands**: verified methods and surrogates for a named physics regime, tested for the **jobs** customers run (inverse design, plant response, hybrid truth).

- **Lean validator exams** keep search fast and produce volume telemetry.  
- **Product battery at graduation** keeps the shelf honest without taxing every miner.  
- Landscape decides **where evidence is strong enough to productize** and learns from **promotion failures**.  
- The pipeline forces **fresh verification** so the bank does not launder leaderboard noise.  
- **Dual egress** protects incentives (noisy miner path) and revenue (closed SKU path).  
- Phase-by-phase customers move from “canonical baseline” → “OEM design loop” → “isolated dual-regime” → “coupled production twin.”  

That is the Landscape → Specialist system: evidence-ranked regimes, effect-synthesized recipes, mandatory re-gate, **job-shaped product battery for full SKUs**, noisy public derivatives, and **closed certified artifacts** customers pay for because assurance, license, deployability, and optimizer-facing evidence match the physics and the assurance level their phase of industry actually needs.

---

*Canonical reference for Specialist Bank construction, dual threshold, dual egress, and phase customer mapping. Implementation must enforce: lean-only emissions path; noisy-only miner derivatives; closed commercial SKUs; **full SKU ⇒ product battery pass** — as specified here, in `Use_Cases_by_Phase.md`, and in `Landscape_Agent.md`.*
