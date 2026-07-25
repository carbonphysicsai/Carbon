# Landscape Agent — Value Extraction, Architecture & Build-Out Guide

**Carbon Subnet**  
**Version:** 1.0 (July 2026)  
**Status:** Core Engineering Appendix  
**Audience:** Tech lead, Landscape implementers, protocol designers  
**Related:** `SPEC.md`, `appendices/Implementation.md`, `appendices/Data_Management.md`, `docs/SYMBOLIC_LAYER_DESIGN.md`

---

## 1. Purpose

The Landscape Agent is Carbon’s **compounding knowledge engine**. It consumes verified Model Cards and produces private intelligence that is routed back into:

1. **Miner search efficiency** (noisy priors, causal masks, diagnostics)
2. **Validator eval efficiency** (progressive depth, adaptive stress emphasis)
3. **Incentives & challenge design** (maturity signals, bounty assist)
4. **Commercial products** (specialists, sponsor briefs, air-gap prior packs)

**Non-negotiable rules**

- Gates remain the only judge of score.
- Full landscape state stays private; external surfaces are noisy, lagged, and incomplete.
- Learning the physics distribution is desired; memorizing stress draws is not.
- Every landscape feature must declare a **value port**, a **publish boundary**, and a **success metric**.

---

## 2. Value Extraction — How Landscape Data Returns Value

### 2.1 Landscape Data Products

| ID | Product | Private contents | Safe external form |
|----|---------|------------------|--------------------|
| **D1** | Model Card feature store | Strategy features, gate vector, stress metrics, dynamics, backbone, budget, seeds | Aggregates only |
| **D2** | Symbolic library | PySR → ModelingToolkit structured loss terms | Selected templates inside noisy priors / specialists |
| **D3** | Causal effect library | Double ML: treatment → robustness / gate-pass / accuracy + CIs | Coarse, noisy strategic guidance bands |
| **D4** | Failure-mode atlas | Gate failure clusters × regime × strategy pattern | Tiered diagnostic labels |
| **D5** | Frontier map | Per challenge×backbone: saturation, upside, difficulty, density | Coarse difficulty / maturity index |
| **D6** | Specialist Bank | Distilled modules + provenance | Licensed / emission-gated specialists |
| **D7** | Transfer graph | Cross-challenge / cross-regime strengths | Internal; optional coarse “related regime” hints |
| **D8** | Counterfactual briefs | Sponsor constraints → expected bottlenecks | Paid sponsored-challenge design only |
| **D9** | Eval-efficiency signals | P(Tier-1 fail), expected GPU-seconds, gate volatility | Validator routing only |
| **D10** | Prior lineage | Which facts produced which prior version | Internal audit |

**Moat boundary:** D1 rows, full D3 graph, fine D5, D7–D10 detail stay private.

### 2.2 Value Router (Four Ports)

```text
                 ┌──────────────────────────────────┐
  Model Cards ─► │     Landscape Agent               │
                 │  symbolic │ causal │ operational  │
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
                         specialists, sponsor briefs,
                         sealed air-gap packs, registry provenance
```

### 2.3 Port A — Miner / Agent Search

| Mechanism | Inputs | External surface | Value |
|-----------|--------|------------------|-------|
| Noisy priors | D2, D3, D6 | Daily perturbed strategy scaffolds per challenge×backbone | Cold-start quality |
| Causal guidance bands | D3 (lagged, thresholded) | Coarse “lever in band helps robustness in regime R” | Oriented search |
| Causal credit masks | D3 | Schema-field importance mask (not values) | Cut dead dimensions |
| Estimation Mode anchors | D3, D6 noisy | Proxy scores; never full champion weights | Cheap garbage reject |
| Diagnostics | D4 | Black-box failure class tiers | Faster repair |
| Specialist warm-starts | D6 | Optional modules; full validator path still required | Compositional search |

### 2.4 Port B — Validator Eval Efficiency

| Mechanism | Inputs | Behavior | Value |
|-----------|--------|----------|-------|
| Progressive routing | D9 | Predicted easy fails → shallow; frontier → full depth | GPU-seconds ↓ |
| Adaptive stress emphasis | D4, D3 | Bias stress mass toward live weak spots of *prior population* | Harder static gaming |
| Gate health | D1 aggregates | Unstable gates → more samples / stricter fp32 checks | Consensus quality |
| Near-prior detection | D6, D10 | Clones still gated; reduced exploration credit only | Anti-cloning |

### 2.5 Port C — Incentives & Challenges

| Mechanism | Inputs | Effect | Value |
|-----------|--------|--------|-------|
| Challenge weight proposals | D5 | More emissions to unsaturated high-upside boards | Search where EV remains |
| Breakthrough assist | D3, D1 | Flag new-best + novel causal region (gov final) | Bounty quality |
| Decay tuning hints | D5 | Faster decay on flat frontiers | Stale winner pressure |
| Stress / challenge evolution | D4, D5, D7 | Versioned stress catalogs; gap-driven challenge ideas | Adversarial roadmap |

**Forbidden:** landscape similarity as a direct score term.

### 2.6 Port D — Commercial & Dual-Regime

| Product | Fuel | Notes |
|---------|------|-------|
| Specialist Bank | D2, D3, D6 | Distill causal drivers, not raw winner clones |
| Sponsored challenges | D8, D5, D4 | Counterfactual briefs are paid design aids |
| Evidence language | D3, D4 | Conservative, testable claims in Model Cards |
| Sealed air-gap prior packs | Noisy D2/D3/D6 + D4 checklist | One-way public → private; no live landscape API in enclave |
| Registry provenance | D10 | Stronger attestation for tooling vendors |

### 2.7 Anti-Gaming Rules

1. Gates never overridden by landscape.  
2. No row-level D1, exact D3, or live D9 for miners.  
3. Publish with noise + lag (daily or slower).  
4. Train data ≠ eval data forever; landscape is not a stress side channel.  
5. Causal models versioned and withdrawable.  
6. Paid tiers buy search orientation or private challenge design — never eval outcomes.  
7. Success = post-gate progress + commercial conversion, not guidance-API engagement.

---

## 3. Recommended Architecture

### 3.1 Design Principles

1. **Batch over online** for causal/symbolic fits — stability > recency theater.  
2. **Append-only Model Card lake** — reproducible reprocessing.  
3. **Feature contracts versioned** — schema evolution without silent breaks.  
4. **Separate serve path from train path** — prior pack publisher ≠ research notebook.  
5. **Julia where symbolic/MT is strongest; Python/JAX where subnet glue is strongest.**  
6. **Every served artifact carries `landscape_version` + `data_cutoff_block`.**

### 3.2 Logical Component Diagram

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                        LANDSCAPE AGENT SERVICE                          │
├─────────────────────────────────────────────────────────────────────────┤
│  INGEST                                                                 │
│  ├─ ModelCardIngestor          (validator → queue → lake)               │
│  ├─ SchemaValidator            (reject incomplete cards)                │
│  └─ FeatureExtractor           (strategy flatten + gate vector encode)  │
├─────────────────────────────────────────────────────────────────────────┤
│  STORAGE                                                                │
│  ├─ CardLake (object store)    append-only JSON/Parquet by challenge    │
│  ├─ FeatureStore (columnar)    training tables for PySR / DML           │
│  ├─ ArtifactRegistry           models, graphs, prior packs, specialists │
│  └─ MetadataDB                 versions, cutoffs, CI summaries          │
├─────────────────────────────────────────────────────────────────────────┤
│  FITTERS (scheduled)                                                    │
│  ├─ SymbolicFitter             PySR batch → expression library          │
│  ├─ MTBridge                   expressions → MT.jl → JAX loss snippets  │
│  ├─ CausalFitter               Double ML / orthogonalized learners      │
│  ├─ FailureAtlasBuilder        cluster gate failures                    │
│  ├─ FrontierMapper             saturation / difficulty / density        │
│  └─ SpecialistDistiller        module extraction + provenance           │
├─────────────────────────────────────────────────────────────────────────┤
│  ROUTER / SERVER                                                        │
│  ├─ PriorPackBuilder           noise + lag + schema masks               │
│  ├─ DiagnosticMapper           gate vector → failure tier labels        │
│  ├─ EvalSignalService          D9 for validators only (private RPC)     │
│  ├─ EconomySignalService       D5 proposals for governance / tracker    │
│  └─ ProductExporter            specialists, sealed packs, sponsor brief │
├─────────────────────────────────────────────────────────────────────────┤
│  CONTROL PLANE                                                          │
│  ├─ Scheduler                  batch cadences (hourly cards, daily fit) │
│  ├─ VersionGovernor            promote / rollback artifacts             │
│  └─ Metrics & KillSwitches     post-gate KPIs; auto-withdraw guidance   │
└─────────────────────────────────────────────────────────────────────────┘
         │                    │                      │
         ▼                    ▼                      ▼
   MCP / Prior API      Validator private       Product / Air-gap
   (miners, agents)     RPC (D9, routing)       export channels
```

### 3.3 Repository Layout (Recommended)

```text
carbon/landscape/
  __init__.py
  contracts/
    model_card_v1.py          # pydantic / JSON schema
    features_v1.py            # flattened feature spec
    prior_pack_v1.py
  ingest/
    consumer.py               # queue consumer from validators
    validate_card.py
    extract_features.py
  storage/
    lake.py
    feature_store.py
    artifact_registry.py
  fitters/
    symbolic_pysr.py
    mt_bridge.py              # HTTP client to Julia MT service or subprocess
    causal_dml.py
    failure_atlas.py
    frontier.py
    specialist_distill.py
  serve/
    prior_pack_builder.py
    noise.py
    diagnostic_map.py
    eval_signals.py           # private
    economy_signals.py
    product_export.py
  pipeline/
    daily.py                  # orchestrate fit → register → publish
    promote.py
  metrics/
    kpis.py
    kill_switches.py
```

Align Julia MT / SciML helpers with existing `SciMLClient` patterns in `appendices/Implementation.md` (port 8083 family), but keep **Landscape fit jobs** on a schedule separate from per-submission validation latency.

### 3.4 Model Card → Feature Contract (Minimum)

Every accepted card must provide enough structure for causal identification:

```text
model_card_v1:
  meta: { card_id, challenge_id, backbone, block_height, validator_set_hash,
          generator_version, landscape_ingest_version }
  strategy_features:
    loss_enables: { data_mse, physics_residual, boundary_mse, conservation_penalty, ... }
    loss_weights: { ... }          # continuous
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
  dynamics (optional but valuable):
    loss_curves_summary, residual_summaries, early_stop_reason
```

**Confounder set (v1 causal):** `physics_class / challenge_id`, `backbone`, `log_budget`, `generator_version`, calendar/block bucket.  
**Treatments (v1):** loss enables, loss weights (winsorized), curriculum scales, schedule family.  
**Primary outcomes:** stress robustness component, gate-pass vector (per-gate and all-pass), combined score (secondary).

### 3.5 Symbolic Path (D2)

```text
FeatureStore slice (successful + failed cards)
        │
        ▼
   PySR batch jobs (per challenge family or pooled with physics_class indicator)
        │
        ▼
   Expression filter (dimensional sanity, complexity cap, stability across restarts)
        │
        ▼
   MTBridge: JSON expression → ModelingToolkit → callable / JAX snippet
        │
        ▼
   ArtifactRegistry: symbolic_lib@vN
        │
        ▼
   PriorPackBuilder may embed 0–k structured loss templates (not full lib)
```

**Build notes**

- Prefer fewer stable expressions over a zoo of fragile ones.  
- Always store recovery metadata: PySR config hash, random seeds, data cutoff.  
- MT bridge failures must not block causal or prior pipelines.

### 3.6 Causal Path (D3) — Recommended Method

**Default v1:** Double / orthogonalized ML (cross-fitted nuisance models) for continuous and binary treatments.

```text
For each treatment family T in {weights, enables, curriculum_scales, schedule}:
  1. Define eligible sample (min n per challenge family; drop incomplete cards)
  2. Cross-fit outcome model m̂(X) and treatment model ê(X) / ĝ(X)
  3. Form orthogonalized scores; estimate ψ̂ with CI (bootstrap or analytic)
  4. Gate on diagnostics: overlap, n effective, stability across folds
  5. Register only effects that pass identification checks
```

**Implementation choices (pragmatic)**

- Start with challenge-family pooled models + `challenge_id` fixed effects / indicators.  
- Use gradient boosting or ridge stacks in pure Python first; swap components later without changing contracts.  
- Publish **bands** only when CI excludes zero *and* effect direction stable across two consecutive fit windows.  
- Hard reject publishing effects with poor overlap (everyone uses the same weight).

### 3.7 Failure Atlas & Frontier (D4, D5)

**Failure atlas:** cluster on gate-fail binary vectors + residual magnitudes; label clusters with human-readable tier taxonomy used by MCP diagnostics.  
**Frontier map:** for each challenge×backbone:

- `n_cards`, `n_unique_strategy_hash`
- best combined score trajectory
- score variance in top decile
- fraction gate all-pass
- crude saturation score ∈ [0,1]

These feed Port B/C only; miners see at most a coarse difficulty index if governance approves.

### 3.8 Specialist Distillation (D6)

Distill **modules**, not full opaque checkpoints, when possible:

- Structured loss packs that repeatedly appear in causal-positive regions  
- Curriculum blocks with stable positive effects  
- Backbone-specific hyper ranges  

Each specialist artifact:

```text
specialist_v1:
  id, regime_tags, backbone_compat
  module_type: loss_pack | curriculum | init_policy | composite
  payload_ref
  provenance: { landscape_version, causal_ids[], symbolic_ids[], card_cutoff }
  validation: { held_out_gate_pass_rate, n_support }
```

Re-entry to subnet competition always requires full validator training/eval.

### 3.9 Prior Pack Publisher (Port A serve path)

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

**Noise recipe (v1)**

- Additive noise on continuous fields with scale ∝ field importance uncertainty  
- Occasional dropout of non-critical fields  
- Lag ≥ 24h behind latest cards  
- Rotate noise seed daily  

### 3.10 Private Eval Signals (Port B)

Validator-only service (mTLS / mesh internal):

```text
POST /v1/eval_signals
  { challenge_id, backbone, strategy_hash, strategy_features_digest }
→ { p_tier1_fail, suggested_depth: shallow|standard|full,
    stress_emphasis_version, landscape_version }
```

Must not be reachable from miner MCP. Log for audit; never write into score.

### 3.11 Cadence

| Job | Cadence | Notes |
|-----|---------|-------|
| Card ingest | continuous | Queue from validators |
| Feature materialize | hourly | Incremental |
| Failure atlas refresh | daily | |
| PySR batch | daily or every N new cards | Per family |
| Causal refit | daily | Only publish if diagnostics pass |
| Prior pack publish | daily | Even if fit skipped — freeze last good |
| Specialist distill | weekly or on new-best streaks | Higher bar |
| Frontier / economy signals | daily | Governance consumes |

---

## 4. Phased Build-Out Guide

### Phase L0 — Skeleton (parallel to subnet Phase 0)

**Objective:** Reliable card lake + publishable noisy priors from aggregates (no causal yet).

**Deliverables**

1. `model_card_v1` schema enforced at validator emit and landscape ingest  
2. CardLake + FeatureStore  
3. Baseline PriorPackBuilder: best-of-recent scaffolds + hand noise  
4. Coarse diagnostic map from gate_id → failure tier  
5. KPI dashboard: ingest lag, card reject rate, prior pack age

**Exit criteria**

- ≥95% of full evals produce ingestible cards  
- Daily prior packs for all live Phase-0 challenge×backbone pairs  
- Miners can pull priors via MCP without landscape downtime affecting validation

### Phase L1 — Symbolic + Failure Atlas

**Objective:** D2/D4 online; structured loss templates enter priors sparingly.

**Deliverables**

1. PySR batch pipeline with config lockfiles  
2. MTBridge best-effort integration  
3. Failure atlas + MCP diagnostic codebook  
4. Registry versioning + rollback

**Exit criteria**

- ≥1 stable symbolic template eligible for prior inclusion on ≥2 challenges  
- Diagnostic tiers used in MCP responses  
- Rollback tested

### Phase L2 — Causal Core (Primary Value Unlock)

**Objective:** D3 production; causal masks + guidance bands; specialist distillation v1.

**Deliverables**

1. Double ML fitter with confounder contract v1  
2. Identification diagnostics + publish gates  
3. Causal masks in prior packs  
4. SpecialistDistiller v1 driven by causal-positive modules  
5. Kill switches tied to post-gate KPIs

**Exit criteria**

- Published bands only with passing overlap/CI checks  
- Measurable lift: higher Tier-1 pass rate among prior-using serious miners *or* faster time-to-first gate-pass in controlled A/B  
- Ablation: removing public bands does not collapse internal specialist quality

### Phase L3 — Eval & Economy Coupling

**Objective:** Ports B and C.

**Deliverables**

1. EvalSignalService (private) for progressive depth  
2. Adaptive stress emphasis versions consumed by generators  
3. Frontier difficulty index → emission weight *proposals* (governance ratifies)  
4. Breakthrough assist flags for bounty workflow

**Exit criteria**

- GPU-seconds per finalized ranking decision ↓ without increase in post-hoc rank instability  
- No miner-reachable path to D9

### Phase L4 — Product & Dual-Regime

**Objective:** Port D full.

**Deliverables**

1. Counterfactual sponsor brief generator (operator-only)  
2. Sealed air-gap prior packs  
3. Specialist composition metadata + registry provenance  
4. Commercial export pipelines

**Exit criteria**

- First paid brief or specialist attachment using landscape provenance  
- Air-gap pack installable without network calls to landscape

---

## 5. Interface Summary

| Consumer | Interface | Artifacts |
|----------|-----------|-----------|
| Miners / agents (MCP) | Public pull | `prior_pack_v1`, diagnostic codebook |
| Validators | Private RPC | `eval_signals`, stress_emphasis_version |
| ChallengeWinnerTracker / gov | Metrics API | frontier index, bounty assist flags |
| Product / OpCo | Export jobs | specialists, sponsor briefs, sealed packs |
| Air-gapped toolkit | Offline pack | sealed prior + failure checklist |

---

## 6. Success Metrics (Landscape-Specific)

| Port | KPI |
|------|-----|
| A | ↑ share of full submissions that clear Tier-1; ↓ attempts to first all-gate pass among active miners |
| A | Estimation Mode rank correlation vs full eval in top quartile |
| B | ↓ GPU-seconds per finalized ranking; stable validator agreement |
| C | Emission share on unsaturated challenges; fewer long stale single-winner plateaus without new bests |
| D | Specialist held-out gate-pass; sponsored brief → challenge conversion |
| Moat | Internal routing/specialist quality survives ablation of public prior detail |

---

## 7. Implementation Checklist (Condensed)

**L0**

- [ ] Model Card schema v1 locked and emitted by validator  
- [ ] Ingest queue + CardLake  
- [ ] Feature extraction + reject metrics  
- [ ] Daily noisy prior packs per challenge×backbone  
- [ ] MCP `get_noisy_prior` serves packs  
- [ ] Basic gate→diagnostic tier map  

**L1**

- [ ] PySR job + artifact registry  
- [ ] MTBridge best-effort  
- [ ] Failure atlas v1  
- [ ] Rollback path for bad prior packs  

**L2**

- [ ] Causal fitter + confounder contract  
- [ ] Publish gates (overlap, CI, stability)  
- [ ] Causal masks in prior packs  
- [ ] Specialist distiller v1  
- [ ] Kill switches on post-gate KPIs  

**L3**

- [ ] Private eval signal RPC  
- [ ] Adaptive stress emphasis hook in generator config  
- [ ] Frontier index → governance proposal feed  

**L4**

- [ ] Sponsor brief tool (authz-restricted)  
- [ ] Sealed air-gap pack format + release pipeline  
- [ ] Registry provenance for specialists  

---

## 8. Thesis

Build the Landscape Agent as a **batch intelligence system with four controlled ports**, not as a live “strategy oracle.”

- **Private richness** enables causal and symbolic compounding.  
- **Public poverty** (noise, lag, masks) preserves incentives and moat.  
- **Validator coupling** converts intelligence into cheaper, harder evaluation.  
- **Product coupling** converts intelligence into specialists and paid discovery.  

The optimal causal use case remains: *identify which training choices cause gated robustness in each regime — then orient search, evaluation, emissions, and commercial packaging accordingly.*

---

*This appendix is the canonical reference for Landscape Agent value routing and build order. Implementation code should follow the contracts and phase exit criteria above; research experiments may run offline but must not bypass publish gates or moat boundaries.*
