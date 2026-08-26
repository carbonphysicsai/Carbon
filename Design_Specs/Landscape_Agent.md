# Landscape Agent — Value Extraction, Architecture & Build-Out Guide

## TL;DR

**Job:** Turn eligible qualified evidence into private intelligence, then route
it back without opening a gaming vector.

**Four ports**
| Port | Consumer | What leaves the building |
|------|----------|---------------------------|
| **A Search** | Miners / agents | Evidence-labeled coarsened priors, search-attention hints, diagnostic tiers (never full specialists) |
| **B Eval** | Validators only | Scheduling, prefetch, and capacity hints (private RPC); never exam changes |
| **C Economy** | Governance | Challenge-weight / bounty *proposals* |
| **D Product** | OpCo / buyers | Specialists via **verification gauntlet**, sponsor briefs, sealed packs |

**Hard rules**
- Gates alone judge score — landscape never overrides them
- A conclusive mandatory hard failure is zero; every nonzero candidate completes the same registered mandatory pack
- Novelty, similarity, priors, and Landscape forecasts never change candidate score or exam depth
- Full effect-candidate graph + card lake stay private
- Publish immutable, coarsened, suppressed, lagged snapshots on fixed epochs;
  use randomized noise only under a formal privacy policy with measured utility
- Never sell eval outcomes; paid tiers buy search orientation or private challenge design only
- **Port D export law:** *Qualified evidence in. Independently re-tested
  capability out.* No teacher-checkpoint distillation; full commercial SKU
  requires product battery (see `Specialist_Bank.md`)
- **Launch Bar:** no external miner-visible prior activation or “verified card” compounding claim until `Launch_Bar.md` is green and the exact artifact is owner-approved
- **Epistemic split:** hard gates create registered protocol decisions when the bar is green; public association guidance is decision support, never causal or grading authority

**Dual threshold**
| Path | Depth |
|------|--------|
| Miner → validator (feeds D1) | Lean gates + stress + short rollout |
| Landscape → Specialist Bank (Port D) | Effect-synthesized recipe → retrain → **product battery** → ship |

**Build order:** L0 card lake + fixed-epoch coarsened prior snapshots → L1 symbolic + failure atlas → L2 effect-candidate core + specialist *pipeline hooks* → L3 eval operations/economy → L4 product gauntlet / dual-regime
**At raise / pre-bar:** Landscape is architecture and build order — not a live intelligence product.

**Success metric:** post-gate progress and commercial conversion — not guidance-API engagement

---

**Carbon Subnet**  
**Version:** 1.3 (August 2026)
**Status:** Core Engineering Appendix  
**Audience:** Tech lead, Landscape implementers, protocol designers  
**Related:** `SPEC.md`, [`Launch_Bar.md`](./Launch_Bar.md), [`Scoring.md`](./Scoring.md), [`Specialist_Bank.md`](./Specialist_Bank.md), [`Use_Cases_by_Phase.md`](./Use_Cases_by_Phase.md)

---

## 1. Purpose

The Landscape Agent is Carbon’s **compounding knowledge engine**. It consumes verified Model Cards and produces private intelligence routed into search, eval efficiency, incentives, and (via gauntlet) commercial products.

**Non-negotiable rules**

- Gates remain the only judge of score.
- Full landscape state stays private; external surfaces are coarsened,
  suppressed, lagged, and incomplete.
- Learning the physics distribution is desired; memorizing stress draws is not.
- Every landscape feature must declare a **value port**, a **publish boundary**, and a **success metric**.
- Port D does **not** distill teacher weights; it multiplies graph evidence into recipes and product tasks, re-executes, and only then exports (see §2.8).
- **Cards are not “verified” for compounding until Launch Bar is green** (`Launch_Bar.md`).

---

## 1b. Epistemic Status (Do Not Collapse)

| Artifact | Status | How to speak about it |
|----------|--------|----------------------|
| Hard physics gates + lean `S_combined` | Registered protocol result **when Launch Bar green** | “Passed / failed the registered exam” |
| Score Pack margins / category vectors | Deterministic functions of predictions + pack | Auditable components of the exam |
| Effect-candidate library (D3) | Observational estimates (selection, confounding, non-random miner behavior) | “Band suggests association under stated confounders; CI hygiene required” — **not** “proven causes” |
| Prior snapshots / masks | Decision-support scaffolds | Orientation for search — not guarantees |
| Product battery | Separate promotion exam | Shelf truth ≠ leaderboard truth |

**Carbon applies its own standard to its own brain:** gate-level certainty language is reserved for gates. Public `causal_candidate` status requires a registered identification argument, overlap and sensitivity evidence, stability windows, and withdrawable versioning—and still remains decision support, not a causal claim.

---

## 2. Value Extraction — How Landscape Data Returns Value

### 2.1 Landscape Data Products

| ID | Product | Private contents | Safe external form |
|----|---------|------------------|--------------------|
| **D1** | Model Card feature store | Strategy features, gate vector, stress metrics, dynamics, backbone, budget, and opaque registered exam/pack pins | Aggregates only |
| **D2** | Symbolic library | PySR → ModelingToolkit structured loss terms | Selected reviewed templates referenced by coarsened prior guidance / specialist *recipes* |
| **D3** | Effect-candidate library | Double ML: treatment → robustness / gate-pass / accuracy + CIs under declared identification assumptions | Coarsened, evidence-labeled association guidance or explicitly labeled `causal_candidate` items |
| **D4** | Failure-mode atlas | Gate failure clusters × regime × strategy pattern | Tiered diagnostic labels |
| **D5** | Frontier map | Per challenge×backbone: saturation, upside, difficulty, density | Coarse difficulty / maturity index |
| **D6** | Specialist Bank interface | Opportunity queue, promotion attempts, PB outcomes, provenance | **Commercial:** closed SKUs via bank gauntlet; **Public:** approved coarsened derivatives only |
| **D7** | Transfer graph | Cross-challenge / cross-regime strengths | Internal; optional coarse “related regime” hints |
| **D8** | Counterfactual briefs | Sponsor constraints → expected bottlenecks | Paid sponsored-challenge design only |
| **D9** | Eval-operations signals | Expected GPU-seconds, queue demand, prefetch/cache opportunities, and capacity pressure | Validator scheduling only |
| **D10** | Prior lineage | Which facts produced which prior version | Internal audit |
| **D11** | Promotion / PB graph | `promotion_fail` records, PB-* vectors, product_jobs tags | Internal only; drives opportunity rank + repair loop |

**Moat boundary:** D1 rows, full D3 graph, fine D5, D7–D11 detail stay private. Full specialist artifacts never traverse Port A.

### 2.2 Value Router (Four Ports)

```text
                 ┌──────────────────────────────────┐
  Model Cards ─► │     Landscape Agent               │
  (+ PB outcomes)│  symbolic │ effects│ operational  │
                 └────────────────┬─────────────────┘
                                  │
       ┌──────────────────────────┼──────────────────────────┐
       ▼                          ▼                          ▼
 Port A: Search              Port B: Eval              Port C: Economy
 public prior snapshots      queue scheduling          challenge weights
 search-attention hints      safe prefetch             bounty assist flags
 diagnostics                 capacity planning         difficulty index
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
| Evidence-labeled priors | D2, D3, D6 *derivatives* | Immutable Challenge-level intervention guidance with applicability, epistemic status, uncertainty, limitations, and public falsification refs | Cold-start quality without recipe release |
| Association guidance bands | D3 (lagged, thresholded) | Coarse “lever is associated with robustness in public context R” plus epistemic label | Oriented search |
| Search-attention hints | D3 | Public schema-field relevance hint (not values) | Prior-guided experiment triage |
| Prior-alignment anchors | D3, D6 approved public items only | Structural applicability and public falsification refs; never quality/score prediction or champion weights | Prior-guided experiment triage |
| Diagnostics | D4 | Black-box failure class tiers | Faster repair |
| Warm-start orientation | D6 **approved coarsened derivatives only** | Masks / coarse bands — **never** full `specialist_bank_item` | Compositional search without SKU leak |

**Port A law:** Competition never requires purchase. Full Specialist Bank items are Port D only.  
**L0 publish** only after `Launch_Bar.md` green; L0 priors are coarsened
aggregates with explicit epistemic limits, not causal proof.

### 2.4 Port B — Validator Operations Only (Safety-Sensitive)

| Mechanism | Inputs | Behavior | Value |
|-----------|--------|----------|-------|
| Queue scheduling | D9 operational estimates | Orders admitted work without changing eligibility or evidence | Queue latency and utilization |
| Safe prefetch/cache planning | Public registered pack identities and D9 | Prepares immutable artifacts or kernels without selecting different cases | Startup and transfer cost |
| Capacity forecasting | Aggregate resource observations | Plans workers, reservations, and backpressure | Reliability and SLO planning |

Port B is an operations aid, not a scientific routing authority. Full product
battery work remains a separate promotion path and is not a default validator
path.

#### Port B invariants (mandatory)

- A conclusive registered mandatory hard-gate failure produces zero and may
  stop remaining work. No partial or shallow execution can produce a positive
  score.
- Every eligible candidate receiving a nonzero score completes the same
  registered mandatory lean pack under the same Challenge/exam identity.
- Landscape cannot change candidate-specific case count, stress mass,
  reference fidelity, measurement depth, gate allocation, thresholds, Score
  Pack weights, or disclosure.
- Predicted difficulty, frontier position, novelty, similarity, hotkey
  history, reputation, stake, sponsorship, prior alignment, and Landscape
  features cannot change score, exam depth, admission to a nonzero result, or
  the registered evidence.
- Operational hints are validator-private, fail closed to the ordinary
  registered execution path, and never write into `S_combined` or gate
  pass/fail.

### 2.5 Port C — Incentives & Challenges

| Mechanism | Inputs | Effect | Value |
|-----------|--------|--------|-------|
| Challenge weight proposals | D5 | More emissions to unsaturated high-upside boards | Search where EV remains |
| Breakthrough assist | D3, D1 | Flag new-best + novel underexplored association region (gov final) | Bounty quality |
| Decay tuning hints | D5 | Faster decay on flat frontiers | Stale winner pressure |
| Challenge evolution proposals | D4, D5, D7, D11 | Propose future stress families or task revisions | Prospective adversarial roadmap |

Landscape proposals do not modify a live exam. A material population,
`SamplingPlan`, stress, generator, truth, measurement, or Score Pack change
requires a new prospective Challenge/version and its full qualification gate.
Novelty and similarity may label research opportunities; they are never score
inputs or reasons to vary candidate exam depth.

### 2.6 Port D — Commercial & Dual-Regime

Canonical pipeline: [`Specialist_Bank.md`](./Specialist_Bank.md). Landscape owns graph + opportunity + repair; bank owns gauntlet + dual egress.

### 2.7 Anti-Gaming Rules

1. Gates never overridden by landscape.  
2. No row-level D1, exact D3, live D9, or D11 for miners.  
3. Publish with deterministic coarsening, suppression, lag, fixed release
   epochs, and cumulative version accounting. Add randomized noise only under
   a formal privacy budget with measured utility.
4. TRAIN/EVAL/STRESS entropy roles and realized samples remain separated;
   this does not require disjoint physical distributions, and Landscape is
   not a protected-realization side channel.
5. Effect/causal-candidate models versioned and withdrawable.
6. Paid tiers buy search orientation or private challenge design — never eval outcomes.  
7. Success = post-gate progress + commercial conversion, not guidance-API engagement.  
8. **No full specialist on miner API.**  
9. **No commercial full SKU without product battery pass.**  
10. **No L0 compounding publish until Launch Bar green.**  
11. **Public association guidance is never described as causal; `causal_candidate` remains an explicit limited epistemic label.**
12. **No candidate-specific official depth, stress, truth, measurement, gate, or weight allocation.**
13. **Challenge evolution is prospective, versioned, and qualified; Landscape never changes the ruler after observing candidates.**

### 2.8 Export Doctrine (Port D alignment)

> **Qualified evidence in. Independently re-tested capability out.**

Landscape must not implement Port D as “export last week’s winner weights.” Gauntlet stages, anti-distillation, and dual threshold remain as in v1.1 — see Specialist Bank for execution.

---

## 3. Recommended Architecture

Version 1.3 supersedes v1.1/v1.2 public cadence and privacy language: Port A uses immutable fixed-epoch packs, deterministic coarsening/suppression/lag, and cumulative disclosure accounting rather than informal daily perturbation. The private symbolic and effect-candidate research paths remain design inputs subject to the stricter publication contract.

**Additional control-plane rule:** `VersionGovernor` and prior publisher check `Launch_Bar` status (or equivalent CI flag) before marking a prior pack `public_publish=true`.

Confounder set, treatments, and publish gates for D3 remain as specified.
Primary outcomes still emphasize stress robustness and gate-pass vectors —
which is why **honest gates are prerequisite**. Those observations may guide
future research and prospective Challenge proposals, never candidate-specific
official evidence allocation.

---

## 4. Phased Build-Out Guide

### Phase L0 — Skeleton (parallel to subnet Phase 0)

**Objective:** Reliable card lake + publishable immutable, coarsened prior
snapshots from eligible aggregates (no causal certainty and no dynamic
request-time private-data query).

**Prerequisite:** `Launch_Bar.md` green for the challenge families that will emit public priors.

**Deliverables:** model_card schema; CardLake + FeatureStore; baseline PriorPackBuilder; coarse diagnostics; KPI dashboard.

**Exit criteria:** ≥95% full evals ingestible; fixed-epoch priors for live
Phase-0 pairs *only if Launch Bar green*; MCP retrieval of approved stored
artifacts without blocking validation.

**Until Launch Bar green:** ingest may run offline; **no** marketed prior surface.

### Phase L1 — Symbolic + Failure Atlas

As v1.1 for private symbolic/failure-atlas intent; public outputs follow the v1.3 evidence-origin, epistemic-label, and disclosure rules.

### Phase L2 — Effect-Candidate Core + Specialist Pipeline Hooks

**Objective:** D3 production with explicit observational framing; opportunity ranker; D11 schema.

**Exit criteria:** bands only with overlap/CI/stability; measurable search lift or faster time-to-gate-pass; zero Port A specialist payloads; **external docs still distinguish gates vs estimates**.

### Phase L3 — Eval Operations & Economy Coupling

Port B may provide scheduling, prefetch, and capacity hints only with §2.4
invariants enforced; no miner path to D9 and no pack/depth divergence.

### Phase L4 — Product Gauntlet & Dual-Regime

As v1.1; grounding gate mandatory.

---

## 5. Interface Summary

| Consumer | Interface | Artifacts |
|----------|-----------|-----------|
| Miners / agents (MCP) | Public pull | `PriorPack v2`; the existing bounded `PublishedPrior v1` service remains unchanged and is not v2-backed; diagnostic codebook |
| Validators | Private RPC | `schedule_hint`, `prefetch_hint`, `capacity_forecast` |
| ChallengeWinnerTracker / gov | Metrics API | frontier index, bounty assist flags |
| Specialist Bank workers | Queue / RPC | opportunity specs; returns `promotion_outcome_v1` |
| Product / OpCo | Export jobs | bank-approved specialists, briefs, sealed packs |
| Air-gapped toolkit | Offline pack | sealed prior + failure checklist |

---

## 6. Success Metrics (Landscape-Specific)

| Port | KPI |
|------|-----|
| A | ↑ share clearing Tier-1; ↓ attempts to first all-gate pass |
| A | Held-out physics progress per unit research compute versus no-prior and generic-prior baselines |
| A security | No material protected-realization inference lift after conditioning on evaluator-held shadow cases sampled from the declared public distribution and unavailable to the attacking agent |
| A | **Zero** full specialist payloads on miner API |
| B | Queue latency/utilization and prefetch hit rate improve; **zero** nonzero-pack divergence |
| C | Emission share on unsaturated challenges |
| D | PB pass rate; zero SKUs without PB; anti-distillation |
| Graph | Promotion_fail repair latency |
| Moat | Ablation of public prior detail does not collapse internal quality |
| Goodhart | Lean rank vs later PB pass correlation monitored |
| Epistemic | Zero public materials presenting association guidance or `causal_candidate` items as proven causal effects or gate proof |

---

## 7. Implementation Checklist (Condensed)

- **Pre-L0** — Launch Bar CI for first challenge family
- **L0** — card schema; lake; features; fixed-epoch coarsened priors *gated on bar*; static MCP pull
- **L1** — PySR + registry; failure atlas; prior rollback
- **L2** — effect-candidate fitter + epistemic publish gates; search-attention hints; opportunity ranker; no Port A SKU leak
- **L3** — private operations RPC for scheduling/prefetch/capacity only; prospective Challenge proposals → gov
- **L4** — D11; ProductExporter grounding gate; sealed packs

---

## 8. Thesis

Build the Landscape Agent as a **batch intelligence system with four controlled ports**, not as a live strategy oracle and not as a teacher-distillation factory.

- **Private richness** enables effect-candidate and symbolic compounding.
- **Public sufficiency** accelerates transferable search; protecting the realized exam and private evidence preserves integrity and moat.
- **Validator coupling** improves scheduling, prefetch, and capacity without changing the registered **lean** evaluation.
- **Product coupling** converts intelligence into specialists only through a **verification gauntlet**.  
- **Dual threshold** keeps search affordable and the commercial shelf honest.  
- **Launch Bar** keeps the flywheel from compounding dishonest labels.  
- **Epistemic discipline** keeps gates and effect estimates from being sold as the same thing.

---

*Canonical reference for Landscape Agent value routing and build order (v1.3). Port D with `Specialist_Bank.md`. Launch prerequisites: `Launch_Bar.md`. Scoring labels: `Scoring.md`.*
