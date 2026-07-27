# Landscape Agent — Value Extraction, Architecture & Build-Out Guide

## TL;DR

**Job:** Turn verified Model Cards into private intelligence, then route it back without opening a gaming vector.

**Four ports**
| Port | Consumer | What leaves the building |
|------|----------|---------------------------|
| **A Search** | Miners / agents | Noisy priors, causal *masks*, diagnostic tiers (never full specialists) |
| **B Eval** | Validators only | Progressive depth, adaptive stress (private RPC) |
| **C Economy** | Governance | Challenge-weight / bounty *proposals* |
| **D Product** | OpCo / buyers | Specialists via **verification gauntlet**, sponsor briefs, sealed packs |

**Hard rules**
- Gates alone judge score — landscape never overrides them
- Full causal graph + card lake stay private
- Publish with noise + lag (daily or slower)
- Never sell eval outcomes; paid tiers buy search orientation or private challenge design only
- **Port D export law:** *Ground truth in. Verified knowledge out.* No teacher-checkpoint distillation; full commercial SKU requires product battery (see `Specialist_Bank.md`)

**Dual threshold**
| Path | Depth |
|------|--------|
| Miner → validator (feeds D1) | Lean gates + stress + short rollout |
| Landscape → Specialist Bank (Port D) | Effect-synthesized recipe → retrain → **product battery** → ship |

**Build order:** L0 card lake + daily noisy packs → L1 symbolic + failure atlas → L2 causal core + specialist *pipeline hooks* → L3 eval/economy → L4 product gauntlet / dual-regime

**Success metric:** post-gate progress and commercial conversion — not guidance-API engagement

---

**Carbon Subnet**  
**Version:** 1.1 (July 2026)  
**Status:** Core Engineering Appendix  
**Audience:** Tech lead, Landscape implementers, protocol designers  
**Related:** `SPEC.md`, [`appendices/Specialist_Bank.md`](./Specialist_Bank.md) (v1.3+), [`appendices/Use_Cases_by_Phase.md`](./Use_Cases_by_Phase.md), `appendices/Implementation.md`, `appendices/Data_Management.md`

---

## 1. Purpose

The Landscape Agent is Carbon’s **compounding knowledge engine**. It consumes verified Model Cards and produces private intelligence that is routed back into:

1. **Miner search efficiency** (noisy priors, causal masks, diagnostics)
2. **Validator eval efficiency** (progressive depth, adaptive stress emphasis)
3. **Incentives & challenge design** (maturity signals, bounty assist)
4. **Commercial products** (specialists via grounded gauntlet, sponsor briefs, air-gap packs)

**Non-negotiable rules**

- Gates remain the only judge of score.
- Full landscape state stays private; external surfaces are noisy, lagged, and incomplete.
- Learning the physics distribution is desired; memorizing stress draws is not.
- Every landscape feature must declare a **value port**, a **publish boundary**, and a **success metric**.
- Port D does **not** distill teacher weights; it multiplies graph evidence into recipes and product tasks, re-executes, and only then exports (see §2.8).

---

## 2. Value Extraction — How Landscape Data Returns Value

### 2.1 Landscape Data Products

| ID | Product | Private contents | Safe external form |
|----|---------|------------------|--------------------|
| **D1** | Model Card feature store | Strategy features, gate vector, stress metrics, dynamics, backbone, budget, seeds | Aggregates only |
| **D2** | Symbolic library | PySR → ModelingToolkit structured loss terms | Selected templates inside noisy priors / specialist *recipes* |
| **D3** | Causal effect library | Double ML: treatment → robustness / gate-pass / accuracy + CIs | Coarse, noisy strategic guidance bands |
| **D4** | Failure-mode atlas | Gate failure clusters × regime × strategy pattern | Tiered diagnostic labels |
| **D5** | Frontier map | Per challenge×backbone: saturation, upside, difficulty, density | Coarse difficulty / maturity index |
| **D6** | Specialist Bank interface | Opportunity queue, promotion attempts, PB outcomes, provenance | **Commercial:** closed SKUs via bank gauntlet; **Public:** noisy derivatives only |
| **D7** | Transfer graph | Cross-challenge / cross-regime strengths | Internal; optional coarse “related regime” hints |
| **D8** | Counterfactual briefs | Sponsor constraints → expected bottlenecks | Paid sponsored-challenge design only |
| **D9** | Eval-efficiency signals | P(Tier-1 fail), expected GPU-seconds, gate volatility | Validator routing only |
| **D10** | Prior lineage | Which facts produced which prior version | Internal audit |
| **D11** | Promotion / PB graph | `promotion_fail` records, PB-* vectors, product_jobs tags | Internal only; drives opportunity rank + repair loop |

**Moat boundary:** D1 rows, full D3 graph, fine D5, D7–D11 detail stay private. Full specialist artifacts never traverse Port A.

### 2.2 Value Router (Four Ports)

```text
                 ┌──────────────────────────────────┐
  Model Cards ─► │     Landscape Agent               │
  (+ PB outcomes)│  symbolic │ causal │ operational  │
                 └────────────────┬─────────────────┘
                                  │
       ┌──────────────────────────┼──────────────────────────┐
       ▼                          ▼                          ▼
 Port A: Search              Port B: Eval              Port C: Economy
 noisy priors                progressive depth         challenge weights
 causal schema masks         adaptive stress           bounty assist flags
 diagnostics                 gate health               difficulty index
       │                          │                          │
       └──────────────────────────┼──────────────────────────┘
                                  ▼
                         Port D: Product
                         graph → multiply → retrain → product battery
                         → closed SKUs, sponsor briefs, sealed packs
```

### 2.3 Port A — Miner / Agent Search

| Mechanism | Inputs | External surface | Value |
|-----------|--------|------------------|-------|
| Noisy priors | D2, D3, D6 *derivatives* | Daily perturbed strategy scaffolds per challenge×backbone | Cold-start quality |
| Causal guidance bands | D3 (lagged, thresholded) | Coarse “lever in band helps robustness in regime R” | Oriented search |
| Causal credit masks | D3 | Schema-field importance mask (not values) | Cut dead dimensions |
| Estimation Mode anchors | D3, D6 noisy only | Proxy scores; never full champion / bank weights | Cheap garbage reject |
| Diagnostics | D4 | Black-box failure class tiers | Faster repair |
| Warm-start orientation | D6 **noisy derivatives only** | Masks / coarse bands influenced by banked regimes — **never** full `specialist_bank_item` | Compositional search without SKU leak |

**Port A law:** Competition never requires purchase. Full Specialist Bank items are Port D only (`Specialist_Bank.md` dual egress).

### 2.4 Port B — Validator Eval Efficiency

| Mechanism | Inputs | Behavior | Value |
|-----------|--------|----------|-------|
| Progressive routing | D9 | Predicted easy fails → shallow; frontier → full depth | GPU-seconds ↓ |
| Adaptive stress emphasis | D4, D3 | Bias stress mass toward live weak spots of *prior population* | Harder static gaming |
| Gate health | D1 aggregates | Unstable gates → more samples / stricter fp32 checks | Consensus quality |
| Near-prior detection | D6 noisy lineage, D10 | Clones still gated; reduced exploration credit only | Anti-cloning |

Port B remains **lean-exam aligned**. Full product battery (INV/ADV/latency) is **not** a default validator path.

### 2.5 Port C — Incentives & Challenges

| Mechanism | Inputs | Effect | Value |
|-----------|--------|--------|-------|
| Challenge weight proposals | D5 | More emissions to unsaturated high-upside boards | Search where EV remains |
| Breakthrough assist | D3, D1 | Flag new-best + novel causal region (gov final) | Bounty quality |
| Decay tuning hints | D5 | Faster decay on flat frontiers | Stale winner pressure |
| Stress / challenge evolution | D4, D5, D7, D11 | Versioned stress catalogs; gap-driven challenge ideas; PB failure modes → new stress families | Adversarial roadmap |

**Forbidden:** landscape similarity as a direct score term.

### 2.6 Port D — Commercial & Dual-Regime

Canonical pipeline detail lives in [`Specialist_Bank.md`](./Specialist_Bank.md). Landscape owns **graph + opportunity + repair routing**; the bank owns **gauntlet execution + dual egress**.

| Product | Fuel | Notes |
|---------|------|-------|
| Specialist Bank | D2, D3, D6, D11 | Effect-synthesized recipes; **controlled retrain**; **product battery** mandatory for full SKU |
| Sponsored challenges | D8, D5, D4 | Counterfactual briefs; may define extra PB tests in challenge brief |
| Evidence language | D3, D4, D11 | Conservative claims; PB report on commercial cards |
| Sealed air-gap prior packs | Noisy D2/D3/D6 + D4 checklist | One-way public → private; no live landscape API in enclave |
| Registry provenance | D10 | Attestation for tooling vendors |
| Optional UQ tier (later) | D1 ensembles / conformal on KPIs | Product add-on for design/safety jobs — **not** L0 Port A surface |

### 2.7 Anti-Gaming Rules

1. Gates never overridden by landscape.  
2. No row-level D1, exact D3, live D9, or D11 for miners.  
3. Publish with noise + lag (daily or slower).  
4. Train data ≠ eval data forever; landscape is not a stress side channel.  
5. Causal models versioned and withdrawable.  
6. Paid tiers buy search orientation or private challenge design — never eval outcomes.  
7. Success = post-gate progress + commercial conversion, not guidance-API engagement.  
8. **No full specialist on miner API.**  
9. **No commercial full SKU without product battery pass** (grounding gate).

### 2.8 Export Doctrine (Port D alignment)

> **Ground truth in. Verified knowledge out.**

Landscape must not implement Port D as “export last week’s winner weights.”

| Gauntlet stage | Landscape role |
|----------------|----------------|
| **Sources** | Ingest lean-verified Model Cards (+ later PB outcomes) |
| **Connected graph** | Cards ↔ regimes ↔ effects ↔ failures ↔ promotion_fail |
| **Multiply** | Opportunity rank → candidate specs from **effects**; `product_jobs` → PB task definitions |
| **Execute** | Hand off to bank controlled retrain (not landscape-side weight copy) |
| **Judge → repair** | Consume PB pass/fail into D11; re-rank / de-prioritize regimes |
| **Decontaminate** | Enforce seed/cutoff policy in opportunity vs bank verify metadata |
| **Grounding gate** | Refuse product export signals unless bank reports required PB pass |
| **Export** | ProductExporter emits only bank-approved artifacts; Port A gets noisy derivatives only |

**Anti-distillation:** teacher-logit / checkpoint mimicry is not a specialist construction path. See Specialist Bank §3.

**Dual threshold reminder**

```text
Lean validator path     → volume telemetry (D1) → search quality (Port A)
Promotion / bank path   → product battery (D11) → commercial SKUs (Port D)
```

Job-shaped tests (inverse design, plant depth, adversarial) belong on the **promotion** path so search stays affordable and the shelf stays honest (`Use_Cases_by_Phase.md`).

---

## 3. Recommended Architecture

### 3.1 Design Principles

1. **Batch over online** for causal/symbolic fits — stability > recency theater.  
2. **Append-only Model Card lake** — reproducible reprocessing.  
3. **Feature contracts versioned** — schema evolution without silent breaks.  
4. **Separate serve path from train path** — prior pack publisher ≠ research notebook.  
5. **Julia where symbolic/MT is strongest; Python/JAX where subnet glue is strongest.**  
6. **Every served artifact carries `landscape_version` + `data_cutoff_block`.**  
7. **Port D construction follows Specialist Bank contracts** — Landscape does not fork a second distillation policy.

### 3.2 Logical Component Diagram

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                        LANDSCAPE AGENT SERVICE                          │
├─────────────────────────────────────────────────────────────────────────┤
│  INGEST                                                                 │
│  ├─ ModelCardIngestor          (validator → queue → lake)               │
│  ├─ PromotionOutcomeIngestor   (bank PB results → D11)                  │
│  ├─ SchemaValidator            (reject incomplete cards)                │
│  └─ FeatureExtractor           (strategy flatten + gate vector encode)  │
├─────────────────────────────────────────────────────────────────────────┤
│  STORAGE                                                                │
│  ├─ CardLake (object store)    append-only JSON/Parquet by challenge    │
│  ├─ FeatureStore (columnar)    training tables for PySR / DML           │
│  ├─ ArtifactRegistry           models, graphs, prior packs, specialists │
│  └─ MetadataDB                 versions, cutoffs, CI summaries, PB logs │
├─────────────────────────────────────────────────────────────────────────┤
│  FITTERS (scheduled)                                                    │
│  ├─ SymbolicFitter             PySR batch → expression library          │
│  ├─ MTBridge                   expressions → MT.jl → JAX loss snippets  │
│  ├─ CausalFitter               Double ML / orthogonalized learners      │
│  ├─ FailureAtlasBuilder        cluster gate failures                    │
│  ├─ FrontierMapper             saturation / difficulty / density        │
│  └─ SpecialistOpportunityRanker  effects + D11 → queue for bank         │
├─────────────────────────────────────────────────────────────────────────┤
│  ROUTER / SERVER                                                        │
│  ├─ PriorPackBuilder           noise + lag + schema masks               │
│  ├─ DiagnosticMapper           gate vector → failure tier labels        │
│  ├─ EvalSignalService          D9 for validators only (private RPC)     │
│  ├─ EconomySignalService       D5 proposals for governance / tracker    │
│  └─ ProductExporter            bank-approved SKUs, sealed packs, briefs │
├─────────────────────────────────────────────────────────────────────────┤
│  CONTROL PLANE                                                          │
│  ├─ Scheduler                  batch cadences (hourly cards, daily fit) │
│  ├─ VersionGovernor            promote / rollback artifacts             │
│  └─ Metrics & KillSwitches     post-gate KPIs; auto-withdraw guidance   │
└─────────────────────────────────────────────────────────────────────────┘
         │                    │                      │
         ▼                    ▼                      ▼
   MCP / Prior API      Validator private       Product / Bank / Air-gap
   (miners, agents)     RPC (D9, routing)       (gauntlet-gated exports)
```

### 3.3 Repository Layout (Recommended)

```text
carbon/landscape/
  contracts/
    model_card_v1.py
    features_v1.py
    prior_pack_v1.py
    promotion_outcome_v1.py      # PB vectors, product_jobs
  ingest/
    consumer.py
    promotion_consumer.py
    validate_card.py
    extract_features.py
  storage/
    lake.py
    feature_store.py
    artifact_registry.py
  fitters/
    symbolic_pysr.py
    mt_bridge.py
    causal_dml.py
    failure_atlas.py
    frontier.py
    opportunity_ranker.py        # feeds Specialist Bank queue
  serve/
    prior_pack_builder.py
    noise.py
    diagnostic_map.py
    eval_signals.py              # private
    economy_signals.py
    product_export.py            # only bank-approved artifacts
  pipeline/
    daily.py
    promote.py                   # orchestrate handoff to bank gauntlet
  metrics/
    kpis.py
    kill_switches.py
```

Specialist **gauntlet execution** (controlled retrain, PB-INV/ROLL/ADV, ONNX) lives with the Specialist Bank / validator-grade workers — not inside Landscape fit notebooks. Landscape ranks and records; the bank **grounds and ships**.

### 3.4 Model Card → Feature Contract (Minimum)

```text
model_card_v1:
  meta: { card_id, challenge_id, backbone, block_height, validator_set_hash,
          generator_version, landscape_ingest_version }
  strategy_features:
    loss_enables: { data_mse, physics_residual, boundary_mse, conservation_penalty, ... }
    loss_weights: { ... }
    curriculum: [{ phase, epochs, spatial_resolution_scale, mode_budget_scale }]
    optimizer: { name, lr, schedule_family, grad_clip, weight_decay }
    budget: { max_epochs, effective_epochs, wall_time_s }
  outcomes:
    combined_score
    accuracy_component
    robustness_component
    physics_fidelity_component
    gate_results: [{ gate_id, status, value, threshold }]
    tier1_passed: bool
    full_eval_completed: bool
  dynamics (optional):
    loss_curves_summary, residual_summaries, early_stop_reason
```

**Promotion outcome contract (D11, from bank):**

```text
promotion_outcome_v1:
  candidate_id, regime, module_type
  product_jobs: [inverse_design, plant, ...]
  pb_results: [{ gate_id, pass, value, threshold }]
  lean_retrain_pass: bool
  banked: bool
  landscape_version, data_cutoff_block
```

**Confounder set (v1 causal):** `physics_class / challenge_id`, `backbone`, `log_budget`, `generator_version`, calendar/block bucket.  
**Treatments (v1):** loss enables, loss weights (winsorized), curriculum scales, schedule family.  
**Primary outcomes:** stress robustness component, gate-pass vector, combined score (secondary).

### 3.5 Symbolic Path (D2)

Unchanged in method: PySR → filter → MTBridge → registry → optional templates in prior packs. Prefer few stable expressions; MT failures must not block causal/prior paths.

### 3.6 Causal Path (D3)

Unchanged in method: Double / orthogonalized ML with overlap and stability publish gates. Publish **bands** only when CI excludes zero and direction is stable across consecutive windows.

### 3.7 Failure Atlas & Frontier (D4, D5)

Unchanged. Additionally: fold **PB failure modes** (from D11) into atlas labels when present (e.g. `pb_inv_constraint`, `pb_roll_blowup`) for Port C challenge evolution.

### 3.8 Specialist Path (D6) — Opportunity, Not Silent Distill

Landscape **ranks opportunities** and may propose module *specs* from causal-positive regions. It does **not**:

- copy winner checkpoints into the bank  
- serve full specialists on Port A  
- mark a commercial SKU without bank grounding-gate attestation  

```text
opportunity(regime, module_type) =
  causal_clarity
  × support_density
  × stability
  × max(commercial_priority, phase_roadmap_priority)
  × (1 − pure_clone_saturation)
  × (1 + pb_historical_pass_rate_bonus)
  / expected_verify_and_pb_cost
```

Each handoff to the bank carries provenance: `landscape_version`, causal_ids[], symbolic_ids[], card_cutoff, `product_jobs`.

Held-out validation metrics for modules remain required; **full surrogate SKUs** additionally require the Specialist Bank product battery.

### 3.9 Prior Pack Publisher (Port A)

```text
prior_pack_v1:
  challenge_id, backbone
  data_cutoff_block
  landscape_version
  strategy_scaffold: { ... noisy JSON ... }
  causal_masks: { field → {impact: high|low|unknown, conf: low|med} }
  guidance_bands: [ { field, lo, hi, claim_id } ]   # optional, sparse
  structured_loss_templates: [ ... ]                # optional, ≤k
  diagnostic_codebook_version
  noise_manifest: { seed, noise_scale, lag_hours }
```

**Noise recipe (v1):** additive noise ∝ uncertainty; occasional field dropout; lag ≥ 24h; daily seed rotate.  
**Never include:** exact bank recipe, ONNX, PB seeds, tight causal coefficients.

### 3.10 Private Eval Signals (Port B)

Unchanged: validator-only RPC; never miner-reachable; never written into score.

### 3.11 Cadence

| Job | Cadence | Notes |
|-----|---------|-------|
| Card ingest | continuous | Queue from validators |
| Promotion / PB ingest | continuous | Queue from bank workers |
| Feature materialize | hourly | Incremental |
| Failure atlas refresh | daily | Includes PB labels when available |
| PySR batch | daily or every N new cards | Per family |
| Causal refit | daily | Only publish if diagnostics pass |
| Prior pack publish | daily | Freeze last good if fit skipped |
| Opportunity rank → bank queue | weekly or on streaks | Higher bar |
| Frontier / economy signals | daily | Governance consumes |

---

## 4. Phased Build-Out Guide

### Phase L0 — Skeleton (parallel to subnet Phase 0)

**Objective:** Reliable card lake + publishable noisy priors from aggregates (no causal yet).

**Deliverables:** model_card schema; CardLake + FeatureStore; baseline PriorPackBuilder; coarse diagnostics; KPI dashboard.

**Exit criteria:** ≥95% full evals ingestible; daily priors for live Phase-0 pairs; MCP priors without blocking validation.

### Phase L1 — Symbolic + Failure Atlas

**Objective:** D2/D4 online; structured loss templates enter priors sparingly.

**Exit criteria:** ≥1 stable template on ≥2 challenges; diagnostic tiers in MCP; rollback tested.

### Phase L2 — Causal Core + Specialist Pipeline Hooks

**Objective:** D3 production; causal masks + bands; **opportunity ranker** feeding Specialist Bank; D11 schema reserved even if PB volume is low.

**Deliverables**

1. Double ML fitter + publish gates  
2. Causal masks in prior packs  
3. OpportunityRanker v1 (effects → bank queue)  
4. Kill switches on post-gate KPIs  
5. Contract alignment with `Specialist_Bank.md` (no weight-copy export path)

**Exit criteria**

- Published bands only with passing overlap/CI  
- Measurable search lift among prior users *or* faster time-to-first gate-pass in A/B  
- Ablation: removing public bands does not collapse internal opportunity quality  
- Zero Port A responses containing full specialist payloads

### Phase L3 — Eval & Economy Coupling

**Objective:** Ports B and C live; PB failure modes optionally inform stress evolution.

**Exit criteria:** GPU-seconds per ranking ↓ without rank instability; no miner path to D9.

### Phase L4 — Product Gauntlet & Dual-Regime

**Objective:** Port D full with **grounding gate** enforced.

**Deliverables**

1. PromotionOutcome ingest (D11)  
2. ProductExporter only emits bank-approved SKUs + PB reports  
3. Sponsor brief tool  
4. Sealed air-gap packs  
5. Optional UQ product tier hooks (KPI conformal / ensemble) — not required for L4 exit

**Exit criteria**

- First paid specialist or brief with landscape provenance **and** PB attestation  
- Zero commercial full SKUs exported without product battery pass  
- Air-gap pack offline-installable  
- Port A still noisy-only under audit

---

## 5. Interface Summary

| Consumer | Interface | Artifacts |
|----------|-----------|-----------|
| Miners / agents (MCP) | Public pull | `prior_pack_v1`, diagnostic codebook |
| Validators | Private RPC | `eval_signals`, stress_emphasis_version |
| ChallengeWinnerTracker / gov | Metrics API | frontier index, bounty assist flags |
| Specialist Bank workers | Queue / RPC | opportunity specs; returns `promotion_outcome_v1` |
| Product / OpCo | Export jobs | bank-approved specialists, briefs, sealed packs |
| Air-gapped toolkit | Offline pack | sealed prior + failure checklist |

---

## 6. Success Metrics (Landscape-Specific)

| Port | KPI |
|------|-----|
| A | ↑ share of submissions clearing Tier-1; ↓ attempts to first all-gate pass |
| A | Estimation Mode rank correlation vs full eval (top quartile) |
| A | **Zero** full specialist payloads observed on miner API |
| B | ↓ GPU-seconds per finalized ranking; stable validator agreement |
| C | Emission share on unsaturated challenges; fewer stale single-winner plateaus |
| D | Specialist held-out gate-pass; **PB pass rate by gate ID**; sponsored brief → challenge conversion |
| D | **Zero** commercial full SKUs without PB report / grounding gate |
| D | Anti-distillation: zero bank entries that are weight copies without controlled retrain |
| Graph | Promotion_fail repair: time-to-requeue; fraction fixed vs abandoned |
| Moat | Internal routing/specialist quality survives ablation of public prior detail |
| Goodhart | Monitor lean leaderboard rank vs later PB pass correlation; tighten lean rollout if diverged |

---

## 7. Implementation Checklist (Condensed)

**L0** — card schema; lake; features; daily noisy priors; MCP pull; diagnostic map  
**L1** — PySR + registry; MTBridge best-effort; failure atlas; prior rollback  
**L2** — causal fitter + publish gates; masks in priors; opportunity ranker; no Port A SKU leak; kill switches  
**L3** — private eval RPC; adaptive stress hook; frontier → gov proposals  
**L4** — D11 promotion ingest; ProductExporter grounding gate; sealed packs; sponsor briefs; optional UQ tier hooks  

---

## 8. Thesis

Build the Landscape Agent as a **batch intelligence system with four controlled ports**, not as a live strategy oracle and not as a teacher-distillation factory.

- **Private richness** enables causal and symbolic compounding.  
- **Public poverty** (noise, lag, masks) preserves incentives and moat.  
- **Validator coupling** converts intelligence into cheaper, harder **lean** evaluation.  
- **Product coupling** converts intelligence into specialists only through a **verification gauntlet** (*ground truth in → verified knowledge out*).  
- **Dual threshold** keeps search affordable and the commercial shelf honest.

The optimal causal use case remains: *identify which training choices cause gated robustness in each regime — then orient search, evaluation, emissions, and gauntlet-gated commercial packaging accordingly.*

---

*Canonical reference for Landscape Agent value routing and build order (v1.1). Port D construction and dual egress are defined jointly with `Specialist_Bank.md`. Implementation must not bypass publish gates, moat boundaries, or the product-battery grounding gate for commercial full SKUs.*
