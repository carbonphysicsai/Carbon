# Specialist Bank — Landscape → Specialist Pipeline & Phase Customers

## TL;DR

**What this is:** How Landscape evidence becomes banked specialists, who buys them by phase, and the dual-egress product rule.

**Pipeline:** Model Cards → causal/symbolic fit → opportunity rank → recipe from *effects* (not single winners) → controlled retrain → fresh gates → bank entry.

**Dual egress (non-negotiable):**
- **Miners (free):** noisy, lagged prior/warm-start derivatives only — never full weights or exact bank recipe.
- **Customers (paid):** closed SKU = ONNX + exact recipe + Model Card + gate cert + license + updates (+ optional air-gap).

**Why closed sells:** buyers pay for deployable certified artifacts, assurance, license, and update channel — not a public weights dump. Competition never requires purchase.

**Customers by phase (hero):** 0 SciML baselines → 1A aero transonic → 1B propulsion/CHT/stores → 2A OEM adapters → 2B sealed dual-regime → 3 coupled twin programs → 4 fleet/extreme production.

**Read next:** §2 dual egress, §6 pipeline, §8 phase customers.

---

**Carbon Subnet**  
**Version:** 1.1 (July 2026)  
**Status:** Core Product & Engineering Appendix  
**Related:** [`appendices/Landscape_Agent.md`](./Landscape_Agent.md), `SPEC.md`, `docs/GTM.md`

---

## 1. Purpose

This document defines:

1. **How** Landscape Agent data becomes a banked specialist (select → specify → construct → verify → package → operate).
2. **What** a specialist is (and is not).
3. **Dual egress:** noisy public/miner path vs closed commercial SKU path.
4. **Which regimes** specialists target.
5. **Who buys** (or adopts) specialists at each Carbon phase — customer and motivation.

The Specialist Bank is Port D of the Landscape Value Router: private causal/symbolic intelligence becomes versioned, re-verified artifacts. Only **noisy derivatives** flow to miners; **full certified artifacts** are commercial products.

---

## 2. Dual Egress Rule (Non-Negotiable)

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
 Never: full weights,                          + gate certificate
        exact bank recipe,                     + license
        tight causal coefficients,             + update channel
        bank verify seeds                      (+ optional air-gap seal)

 Competition scoring NEVER depends on purchasing the commercial path.
```

### Why miner path must be noisy

Full specialist warm-start (exact recipe + weights + tight bands) recreates champion exposure:

- Search collapses onto one artifact  
- Cloning dominates exploration  
- Landscape moat leaks through the warm-start API  

**Subnet rule:** miners never pull a complete `specialist_bank_item`. Banked regimes may **inform** the daily noisy prior pack (same Port A path and noise/lag policy as `Landscape_Agent.md`). Warm-start ≠ SKU download.

### Why commercial path must be closed

If the full specialist (weights + exact strategy + certs) is open-sourced as a free dump, many buyers will not pay. Carbon sells a **verified surrogate distribution**, not a public folder of weights.

| Closed commercial asset | Why buyers pay |
|-------------------------|----------------|
| Deployable ONNX (or equiv.) from bank verification retrain | Ready to run; avoids re-train cost |
| Exact strategy recipe used in the certified run | Reproducible specialization / fine-tune start |
| Gate certificate + registry attestation for that artifact | Procurement / IV&V / partner checkbox |
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

Someone may approximate a specialist from noisy priors and publish a clone. That is acceptable: commercial value is **assurance, envelope, license, and ongoing verify** — not eternal secrecy of every loss weight.

---

## 3. What a Specialist Is (and Is Not)

### Is

- A **regime-scoped**, reusable artifact encoding training methodology (and optionally weights).
- Built from **landscape evidence** (support density, causal stability, symbolic structure).
- **Re-verified** under fresh hidden stress + physics gates before bank entry.
- Versioned with **provenance** back to landscape artifact IDs and data cutoff.
- **Commercially** usable as: closed product SKU (ONNX + Model Card + gate certs + license) or sealed air-gap pack.
- **Publicly** usable only via noisy derivatives in prior / warm-start packs.

### Is Not

- Yesterday’s challenge-winner checkpoint, rebranded.
- A substitute for full validator evaluation when re-entering competition.
- An open export of the causal graph or Model Card lake.
- A full-fidelity free download for miners.
- Mandatory for miners to compete (submission remains free).

### Module types

| Type | Contents | Typical use |
|------|----------|-------------|
| **Loss pack** | Structured loss terms + default weight bands (+ optional MT snippets) | Highest early ROI; commercial or (noisy) prior fuel |
| **Curriculum block** | Multi-fidelity / resolution / mode schedules with causal support | Training dynamics |
| **Init / prior policy** | Scaffold + high-impact field masks | **Noisy** agent cold start only |
| **Backbone adapter recipe** | Hyper ranges / patterns for a backbone family | FNO vs GINO vs … |
| **Composite specialist** | Locked combination of the above | Internal + **closed** product |
| **Full surrogate SKU** | ONNX + Model Card + gate certs from controlled retrain | Primary **paid** product |

**Default path:** causal evidence → loss pack + curriculum → composite recipe → controlled retrain → bank entry → dual egress.

---

## 4. Regime Key

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

## 5. Landscape Value Signals → What to Build

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

## 6. Pipeline — Landscape → Specialist Bank

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
           ┌───────────────┴───────────────┐
           ▼                               ▼
  PUBLIC EGRESS                      COMMERCIAL EGRESS
  Noisy prior / warm-start pack      Closed SKU + license
  (Port A; free)                     (+ optional air-gap seal)
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
  artifacts: [strategy_json, optional_onnx, mt_snippets]   # commercial only
  model_card_ref, gate_certificate
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
| **Product SKU** | Closed: ONNX + exact recipe + card + certs + license; inference / offline fine-tune |
| **Air-gap pack** | Sealed closed distribution; offline; one-way public → private |
| **Refresh** | Re-verify when landscape_version or gate taxonomy advances; commercial channel gets updates |
| **Retire** | Failed re-check or regime redefinition |

### Policy rules

- Recipes from **effects**, not single winners.  
- Bank verification seeds ≠ opportunity-supporting eval seeds.  
- **No pay-to-compete.**  
- **No full specialist on the miner API.**  
- No specialist score in emissions.  
- Prefer composable modules early; full SKUs when verify cost is justified.  
- Open catalog / noisy priors; close certified artifacts.

---

## 7. Worked Example (Phase 0)

**Signals:** On `physics_class=burgers`, `backbone_family=fno`: conservation-penalty weight band and a resolution curriculum scale show stable positive causal effects on stress robustness; n≈120 cards; Phase-0 catalog priority high.

**Candidate:** composite loss pack + curriculum for Burgers–FNO envelope.

**Construct:** scaffold with those terms enabled, band-center weights, curriculum phases from D3; other fields weakly defaulted.

**Verify:** multiple controlled retrains, new stress seeds, full gates; must improve robustness vs baseline prior without accuracy collapse.

**Bank:** `specialist_burgers_fno_conservation_v1` with Model Card, ONNX, causal_id provenance.

**Egress:**

- **Public:** noisy prior pack fields influenced by this regime (masks, coarse bands, no ONNX, no exact recipe).  
- **Commercial:** closed Tier-1 SKU for teams that want a verified Burgers-class operator baseline with certs and license.

---

## 8. Who Wants a Specialist at Each Phase

Customers differ by **physics maturity**, **regulatory pressure**, and **whether they need a method pack vs a deployable surrogate**. Below: primary buyer, secondary buyer, and *why this phase’s specialists matter*.

Miner “adoption” in every phase means **noisy warm-start only**, not free SKU access.

See full phase tables in the sections below (Phase 0–4). Hero buyers move from SciML baselines → aero design loops → propulsion/multiphysics campaigns → OEM specialization → sealed dual-regime → coupled system twins → fleet/extreme production infrastructure.

**Cross-cutting:** miners get free noisy warm-starts only; tooling platforms license SKUs; sponsors pay to create missing regimes (Tier 2–4).

---

## 9. Customer Summary Matrix

| Phase | Hero customer | Core job-to-be-done | Specialist shape |
|-------|---------------|---------------------|------------------|
| **0** | SciML / sim teams, labs | Trusted **certified** canonical baselines | Closed loss packs + simple SKUs |
| **1A** | Aero airframe & aeroelasticity | Transonic design-loop speed + evidence | Closed compressible composites + SKUs |
| **1B** | Propulsion, turbomachinery, stores | Cut cost of sequential multiphysics campaigns | Closed reacting / CHT / 6-DOF SKUs |
| **2A** | OEM methods groups | Specialize verified methods to *our* representation | Closed adapters + custom composites |
| **2B** | Primes, regulated energy | Offline, dual-regime deployable intelligence | Sealed closed packs + provenance |
| **3** | System digital-twin programs | Coupled multiphysics building blocks | Closed coupled composites + bundles |
| **4** | Fleet / extreme-environment programs | Production 3D turbulent & extreme surrogates | Program closed SKUs + evidence |

---

## 10. GTM Linkage

| Bank output | GTM engine | Open or closed |
|-------------|------------|----------------|
| Noisy prior derivatives | Miner MCP / Port A | Open (free, noisy) |
| Coarse catalog listing | Marketing / roadmap | Open |
| Phase-0/1 catalog SKUs | Specialist Bank Tier 1 | **Closed** |
| Customer geometry / envelope | Sponsored Challenges Tier 2–4 | **Closed** per tier IP |
| Sealed packs + dual-regime | DoD / regulated path | **Closed** |
| Registry-backed certs | Verification gas / partners | Attestation service; artifact remains licensed |

---

## 11. Success Metrics for the Pipeline

| Stage | Metric |
|-------|--------|
| Selection | % of queued candidates that pass bank verify |
| Construction | Time from opportunity rank → candidate spec |
| Verify | Gate all-pass rate; robustness vs baseline |
| Product | Attach rate, renewal, sponsored upsell from catalog |
| Network | Noisy warm-start users’ time-to-first-gate-pass (observational) |
| Moat | Bank quality under ablation of public prior detail; no miner API serving full SKUs |
| Commercial integrity | Zero requirement to purchase for competition eligibility |

---

## 12. Thesis

Specialists are how Carbon **turns private landscape intelligence into objects the market understands**: verified methods and surrogates for a named physics regime.

- Landscape decides **where evidence is strong enough to productize**.  
- The pipeline forces **fresh verification** so the bank does not launder leaderboard noise.  
- **Dual egress** protects incentives (noisy miner path) and revenue (closed SKU path).  
- Phase-by-phase customers move from “canonical baseline” → “OEM design loop” → “isolated dual-regime” → “coupled production twin.”  

That is the Landscape → Specialist system: evidence-ranked regimes, effect-synthesized recipes, mandatory re-gate, noisy public derivatives, and **closed certified artifacts** customers pay for because assurance, license, and deployability match the physics and the assurance level their phase of industry actually needs.

---

*Canonical reference for Specialist Bank construction, dual egress, and phase customer mapping. Implementation must enforce noisy-only miner derivatives and closed commercial SKUs as specified here and in `appendices/Landscape_Agent.md`.*

**Note:** Detailed Phase 0–4 customer tables (primary/secondary buyers and offer shapes) remain in the full design history of this appendix; the summary matrix in §9 is the operational view.
