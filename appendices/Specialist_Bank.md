# Specialist Bank — Landscape → Specialist Pipeline & Phase Customers

**Carbon Subnet**  
**Version:** 1.0 (July 2026)  
**Status:** Core Product & Engineering Appendix  
**Related:** [`appendices/Landscape_Agent.md`](./Landscape_Agent.md), `SPEC.md`, `docs/GTM.md`

---

## 1. Purpose

This document defines:

1. **How** Landscape Agent data becomes a banked specialist (select → specify → construct → verify → package → operate).
2. **What** a specialist is (and is not).
3. **Which regimes** specialists target.
4. **Who buys** (or adopts) specialists at each Carbon phase — customer and motivation.

The Specialist Bank is Port D of the Landscape Value Router: private causal/symbolic intelligence becomes versioned, re-verified artifacts for miner warm-start and commercial sale.

---

## 2. What a Specialist Is (and Is Not)

### Is

- A **regime-scoped**, reusable artifact encoding training methodology (and optionally weights).
- Built from **landscape evidence** (support density, causal stability, symbolic structure).
- **Re-verified** under fresh hidden stress + physics gates before bank entry.
- Versioned with **provenance** back to landscape artifact IDs and data cutoff.
- Usable as: miner warm-start, product SKU (ONNX + Model Card + gate certs), or sealed air-gap prior component.

### Is Not

- Yesterday’s challenge-winner checkpoint, rebranded.
- A substitute for full validator evaluation when re-entering competition.
- An open export of the causal graph or Model Card lake.
- Mandatory for miners to compete (submission remains free).

### Module types

| Type | Contents | Typical use |
|------|----------|-------------|
| **Loss pack** | Structured loss terms + default weight bands (+ optional MT snippets) | Highest early ROI |
| **Curriculum block** | Multi-fidelity / resolution / mode schedules with causal support | Training dynamics |
| **Init / prior policy** | Scaffold + high-impact field masks | Agent cold start |
| **Backbone adapter recipe** | Hyper ranges / patterns for a backbone family | FNO vs GINO vs … |
| **Composite specialist** | Locked combination of the above | Internal + product |
| **Full surrogate SKU** | ONNX + Model Card + gate certs from controlled retrain | Primary paid product |

**Default path:** causal evidence → loss pack + curriculum → composite recipe → controlled retrain → bank entry.

---

## 3. Regime Key

Specialists are aimed at **regimes**, not single leaderboard rows:

```text
regime = {
  physics_class,       # e.g. burgers, heat, elasticity, transonic_compressible
  challenge_family,    # e.g. poisson_2d, naca_transonic, turekhron_fsi
  backbone_family,     # fno | gino | wno | transolver | ...
  envelope,            # non-dimensional ranges, BC classes, stress families covered
  fidelity_class       # 2d_single | sequential_fsi | coupled_3d | ...
}
```

A specialist that only works on one fixed seed is a leaderboard artifact.  
A specialist that holds on a **family + envelope** is a product.

---

## 4. Landscape Value Signals → What to Build

The Landscape Agent ranks **regime × module_type** opportunities. It does not auto-publish specialists.

| Signal | Source | Role |
|--------|--------|------|
| Causal support | D3 | Levers that *cause* robustness / gate-pass |
| Support density | D1 | Enough verified cards |
| Stability | D3 across windows | Direction holds over time |
| Frontier residual / maturity | D5 | Productize vs keep searching |
| Failure concentration | D4 | Clean module targets |
| Transfer strength | D7 | Neighboring regimes |
| Commercial / phase priority | Product + roadmap | Demand and sequencing |
| Cost-to-serve | D9 / ops | Train + verify affordability |

**Opportunity score (v1):**

```text
opportunity(regime, module_type) =
  causal_clarity
  × support_density
  × stability
  × max(commercial_priority, phase_roadmap_priority)
  × (1 − pure_clone_saturation)
  / expected_distill_and_verify_cost
```

Governance / product sets commercial priority and approves the queue.

---

## 5. Pipeline — Landscape → Specialist Bank

```text
Model Cards (verified)
        │
        ▼
Landscape fitters (D2 symbolic, D3 causal, D4 failures, D5 frontier, D7 transfer)
        │
        ▼
Opportunity ranker  →  regime × module_type queue
        │
        ▼
Candidate Spec (recipe from causal bands + masks — not single-winner JSON)
        │
        ├──────────────────┬──────────────────┐
        ▼                  ▼                  ▼
  Construct recipe   Controlled retrain   Package artifacts
  (loss/curriculum/  (validator-grade     (strategy, ONNX,
   composite)         train + new stress    Model Card, certs)
                      + full gates)
        │                  │                  │
        └──────────────────┼──────────────────┘
                           ▼
                    Bank gate (held-out criteria)
                           ▼
                    Specialist Bank (versioned + lineage)
                           │
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
     Miner warm-start  Product SKU    Air-gap prior pack
```

### Step A — Select

1. Compute opportunity scores.  
2. Filter on minimum support, causal stability, non-saturation.  
3. Apply commercial / phase priority; approve queue.

### Step B — Specify

```text
specialist_candidate_v1:
  regime: { physics_class, challenge_family, backbone_family, envelope, fidelity_class }
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
  provenance: { landscape_version, data_cutoff_block }
```

### Step C — Construct

- **Loss pack:** enable causally positive terms; weights at band centers; attach MT snippets if available.  
- **Curriculum:** encode scales from positive treatments.  
- **Composite:** union + schema-valid strategy JSON.  
- **Weights (optional):** controlled validator-equivalent trains under fixed budget policy.

### Step D — Verify (mandatory)

1. Fresh train from recipe (not upload-only weights).  
2. Hidden stress + full physics gates with **new** seeds (not the cards that justified the opportunity).  
3. Beat or match agreed baseline (e.g. noisy prior scaffold).  
4. Record components and gate vector on the bank Model Card.

Failure → do not bank; feed negative evidence back to landscape.

### Step E — Package

```text
specialist_bank_item_v1:
  specialist_id, version, regime, module_type
  artifacts: [strategy_json, optional_onnx, mt_snippets]
  model_card_ref, gate_certificate
  provenance:
    landscape_version, causal_ids[], symbolic_ids[],
    supporting_card_count, data_cutoff_block
  intended_use: [miner_warmstart, product_sku, airgap_prior]
  retirement_policy
```

### Step F — Operate

| Channel | Rule |
|---------|------|
| Miner warm-start | Optional; full competition eval still required |
| Product SKU | ONNX + card + certs; inference / offline fine-tune |
| Air-gap pack | Sealed, offline; one-way public → private |
| Refresh | Re-verify when landscape_version or gate taxonomy advances |
| Retire | Failed re-check or regime redefinition |

### Policy rules

- Recipes from **effects**, not single winners.  
- Bank verification seeds ≠ opportunity-supporting eval seeds.  
- No pay-to-compete.  
- No specialist score in emissions.  
- Prefer composable modules early; full SKUs when verify cost is justified.

---

## 6. Worked Example (Phase 0)

**Signals:** On `physics_class=burgers`, `backbone_family=fno`: conservation-penalty weight band and a resolution curriculum scale show stable positive causal effects on stress robustness; n≈120 cards; Phase-0 catalog priority high.

**Candidate:** composite loss pack + curriculum for Burgers–FNO envelope.

**Construct:** scaffold with those terms enabled, band-center weights, curriculum phases from D3; other fields weakly defaulted.

**Verify:** multiple controlled retrains, new stress seeds, full gates; must improve robustness vs baseline prior without accuracy collapse.

**Bank:** `specialist_burgers_fno_conservation_v1` with Model Card, optional ONNX, causal_id provenance.

**Use:** agent warm-start; Tier-1 catalog SKU for teams needing a verified Burgers-class operator baseline.

---

## 7. Who Wants a Specialist at Each Phase

Customers differ by **physics maturity**, **regulatory pressure**, and **whether they need a method pack vs a deployable surrogate**. Below: primary buyer, secondary buyer, and *why this phase’s specialists matter*.

---

### Phase 0 — Core single-physics PDEs  
*(Poisson, Darcy, Burgers, laminar NS, Heat, Elasticity, Thermo-elasticity)*

| Role | Who | Why they want it |
|------|-----|------------------|
| **Primary** | Simulation / SciML teams inside mid-size CAE users and startups | Cheap, verified baselines for canonical operators; replace ad-hoc PINN/NO notebooks with something that has gate evidence |
| **Primary** | University labs & national-lab pilot groups | Teaching, benchmarking, and “known-good” warm starts without building a training methodology from scratch |
| **Secondary** | Tooling vendors (early design partners) | Embed a verified heat / elasticity / Darcy surrogate in demos and tutorials; low ITAR risk |
| **Secondary** | Serious miners / agent operators | Warm-start quality; faster path to first gate-pass (optional, not required) |

**Why Phase 0 specialists sell:**  
Trust is earned on problems domain experts already understand. A Burgers or Heat specialist with conservation and stability gates is the **credibility SKU**. Revenue is smaller per unit; strategic value is proof that the bank and Model Cards are real.

**Typical offer:** Full surrogate SKU + loss pack; subscription or per-model list price at the low end of Tier-1.

---

### Phase 1A — Compressible flow  
*(NACA 0012 transonic flutter-class, NASA CRM wing-body-class)*

| Role | Who | Why they want it |
|------|-----|------------------|
| **Primary** | Aerospace airframe & aeroelasticity groups | Fast surrogates for transonic separation, shock-boundary interaction, buffet-adjacent exploration — where full CFD is the bottleneck in design loops |
| **Primary** | Defense / UAV airframe contractors (unclassified programs) | Early digital-twin and loads screening with **verification evidence**, not just a Kaggle-style error number |
| **Secondary** | Wind-tunnel & flight-test correlation teams | Surrogate as interpolant / emulator between expensive test points |
| **Secondary** | CAE ISVs | OEM-facing demos on CRM-like geometry with Carbon gate certs |

**Why Phase 1A specialists sell:**  
This is the first phase where **OEM-shaped geometry and compressible physics** show up. Buyers care about shock capture, stability, and envelope limits. Specialists become “design-loop accelerators,” not academic curiosities.

**Typical offer:** Composite + full SKU; higher Tier-1 pricing; natural lead-in to sponsored challenges on customer geometry (Tier 2/3).

---

### Phase 1B — Reacting flow + sequential FSI + CHT + 6-DOF  
*(HIFiRE-class, Turek/Hron sequential FSI, store separation, turbine blade heat transfer)*

| Role | Who | Why they want it |
|------|-----|------------------|
| **Primary** | Propulsion & hypersonics groups | Species/energy-aware surrogates and boundary-layer transition-related screening where every full-fidelity run is extremely expensive |
| **Primary** | Turbomachinery / heat-transfer teams | Conjugate heat transfer and film-cooling-adjacent surrogates for design of experiments |
| **Primary** | Weapons / stores integration (unclassified or dual-use) | 6-DOF store separation emulators for envelope exploration |
| **Secondary** | Multiphysics platform teams | Sequential FSI specialists as stepping stones before tightly coupled Phase 3 |

**Why Phase 1B specialists sell:**  
Problems are **multi-physics sequential and high-cost**. Customers pay for reduced campaign cost and for Model Cards that speak conservation, interface, and stability language. Sponsored challenges become a major revenue path alongside catalog SKUs.

**Typical offer:** Regime SKUs + sponsored open/IP-licensed challenges; loss packs for reacting and interface-heavy training.

---

### Phase 2A — Customization & intelligence  
*(LoRA / adapters, Abaqus-class custom data paths, MT structured losses in product form)*

| Role | Who | Why they want it |
|------|-----|------------------|
| **Primary** | OEM methods groups with **existing FEA/CFD libraries** | Adapter-style specialists that specialize a Carbon backbone to *their* mesh/parameterization style without handing over full proprietary corpora to the open net |
| **Primary** | Digital-thread / PLM integration teams | Specialists that plug into existing model trees with structured loss / Model Card metadata |
| **Secondary** | Carbon product itself | Higher-margin “specialize this backbone to my regime” services using landscape opportunity scores |

**Why Phase 2A specialists sell:**  
The buyer shifts from “give me a Burgers model” to “**specialize the verified methodology to my representation**.” Landscape signals which adapter/loss modules have causal support before expensive custom work.

**Typical offer:** Adapter recipes + composite specialists; professional services attached to Tier-2/3 challenges.

---

### Phase 2B — Air-gap + coupling prep  
*(Air-gapped toolkit, sequential multiphysics ladder, preCICE-ready architecture)*

| Role | Who | Why they want it |
|------|-----|------------------|
| **Primary** | Defense primes & regulated energy (nuclear, propulsion) | **Sealed prior packs and specialists** that install offline; public discovery, private fine-tune |
| **Primary** | Security / accreditation offices | Artifacts that fit dual-regime evidence stories (public gates → enclave fine-tune) |
| **Secondary** | Coupling infrastructure teams | Specialists designed as components in a sequential multiphysics ladder |

**Why Phase 2B specialists sell:**  
The product is not only accuracy — it is **deployability under isolation**. Customers pay for sealed packs, clear provenance, and failure checklists aligned with public gate taxonomy.

**Typical offer:** Sealed air-gap specialist packs; dual-regime professional services; Tier-4 private challenge prep.

---

### Phase 3 — Coupled multiphysics  
*(preCICE FSI, CHT, thermo-elasticity multi-field)*

| Role | Who | Why they want it |
|------|-----|------------------|
| **Primary** | Full-vehicle / full-system digital twin programs | Coupled surrogates where single-physics SKUs are no longer enough |
| **Primary** | Primes running integrated aero-thermal-structural loops | Verified coupled components with interface and convergence-related gate evidence |
| **Secondary** | Platform vendors (Ansys/Siemens/Dyad-class partners) | Carbon-verified coupled blocks inside their orchestration environments |

**Why Phase 3 specialists sell:**  
This is **system-level** value. Buyers are programs, not individual analysts. Pricing tracks sponsored coupled challenges and multi-SKU bundles. Landscape transfer graphs (D7) matter: which single-physics modules compose.

**Typical offer:** Coupled composite SKUs; high-end Tier-3/4 challenges; verification-registry-backed bundles.

---

### Phase 4 — Production 3D + turbulence + extreme regimes  
*(3D FSI/CHT/thermo-elasticity + turbulence; hypersonic 6-DOF + reacting + ablation-class)*

| Role | Who | Why they want it |
|------|-----|------------------|
| **Primary** | Production digital-twin and fleet digital-thread owners | 3D turbulent multiphysics surrogates for operations, maintenance, and design-to-fleet feedback |
| **Primary** | Hypersonics / extreme-environment programs | Ablation- and reacting-aware specialists where test data is sparse and simulation is extreme-cost |
| **Secondary** | Insurers / certification support orgs (long tail) | Evidence-rich Model Cards for risk and assurance narratives |

**Why Phase 4 specialists sell:**  
Highest willingness to pay; longest sales cycles; heaviest evidence requirements. Specialists are **program infrastructure**, not tools. Landscape opportunity ranking focuses on regimes where residual upside and commercial priority remain high despite cost-to-verify.

**Typical offer:** Program-priced SKUs; multi-year specialist maintenance; Tier-4 private + DoD evidence packages.

---

## 8. Customer Summary Matrix

| Phase | Hero customer | Core job-to-be-done | Specialist shape |
|-------|---------------|---------------------|------------------|
| **0** | SciML / sim teams, labs | Trusted canonical operator baselines | Loss packs + simple SKUs |
| **1A** | Aero airframe & aeroelasticity | Transonic design-loop speed + evidence | Compressible composites + SKUs |
| **1B** | Propulsion, turbomachinery, stores | Cut cost of sequential multiphysics campaigns | Reacting / CHT / 6-DOF SKUs |
| **2A** | OEM methods groups | Specialize verified methods to *our* data/representation | Adapters + custom composites |
| **2B** | Primes, regulated energy | Offline, dual-regime deployable intelligence | Sealed packs + provenance |
| **3** | System digital-twin programs | Coupled multiphysics building blocks | Coupled composites + bundles |
| **4** | Fleet / extreme-environment programs | Production 3D turbulent & extreme surrogates | Program SKUs + evidence |

**Cross-cutting buyers at every phase**

- **Agent miners:** optional warm-starts (efficiency, not access rights).  
- **Tooling platforms:** embed or call verified SKUs; verification gas / registry.  
- **Sponsors:** pay to *create* regimes the bank does not yet cover (Tier 2–4).

---

## 9. GTM Linkage

| Bank output | GTM engine |
|-------------|------------|
| Phase-0/1 catalog SKUs | Specialist Bank Tier 1 subscription / per-model |
| Customer geometry / envelope | Sponsored Challenges Tier 2–4 |
| Sealed packs + dual-regime | DoD / regulated path |
| Registry-backed certs | Verification gas / partner integrations |

Landscape opportunity scores should be visible to **product** (what to distill next) and optionally as a **coarse public catalog roadmap** (what regimes are maturing) — never as raw causal coefficients.

---

## 10. Success Metrics for the Pipeline

| Stage | Metric |
|-------|--------|
| Selection | % of queued candidates that pass bank verify |
| Construction | Time from opportunity rank → candidate spec |
| Verify | Gate all-pass rate; robustness vs baseline |
| Product | Attach rate, renewal, sponsored upsell from catalog |
| Network | Warm-start users’ time-to-first-gate-pass (observational) |
| Moat | Bank quality under ablation of public prior detail |

---

## 11. Thesis

Specialists are how Carbon **turns private landscape intelligence into objects the market understands**: verified methods and surrogates for a named physics regime.

- Landscape decides **where evidence is strong enough to productize**.  
- The pipeline forces **fresh verification** so the bank does not launder leaderboard noise.  
- Phase-by-phase customers move from “canonical baseline” → “OEM design loop” → “isolated dual-regime” → “coupled production twin.”  

That is the Landscape → Specialist system: evidence-ranked regimes, effect-synthesized recipes, mandatory re-gate, and customers who pay because the artifact matches the physics and the assurance level their phase of industry actually needs.

---

*Canonical reference for Specialist Bank construction and phase customer mapping. Implementation should follow the candidate schema, verify protocol, and opportunity scoring boundaries defined here and in `appendices/Landscape_Agent.md`.*
