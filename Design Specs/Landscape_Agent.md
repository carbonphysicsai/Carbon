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
- **Launch Bar:** no L0 public prior publish / “verified card” compounding claims until `appendices/Launch_Bar.md` is green
- **Epistemic split:** hard gates = protocol truth (when bar green); causal bands = observational estimates — never spoken with gate-level certainty

**Dual threshold**
| Path | Depth |
|------|--------|
| Miner → validator (feeds D1) | Lean gates + stress + short rollout |
| Landscape → Specialist Bank (Port D) | Effect-synthesized recipe → retrain → **product battery** → ship |

**Build order:** L0 card lake + daily noisy packs → L1 symbolic + failure atlas → L2 causal core + specialist *pipeline hooks* → L3 eval/economy → L4 product gauntlet / dual-regime  
**At raise / pre-bar:** Landscape is architecture and build order — not a live intelligence product.

**Success metric:** post-gate progress and commercial conversion — not guidance-API engagement

---

**Carbon Subnet**  
**Version:** 1.2 (July 2026)  
**Status:** Core Engineering Appendix  
**Audience:** Tech lead, Landscape implementers, protocol designers  
**Related:** `SPEC.md`, [`Launch_Bar.md`](./Launch_Bar.md), [`Scoring.md`](./Scoring.md), [`Specialist_Bank.md`](./Specialist_Bank.md), [`Use_Cases_by_Phase.md`](./Use_Cases_by_Phase.md)

---

## 1. Purpose

The Landscape Agent is Carbon’s **compounding knowledge engine**. It consumes verified Model Cards and produces private intelligence routed into search, eval efficiency, incentives, and (via gauntlet) commercial products.

**Non-negotiable rules**

- Gates remain the only judge of score.
- Full landscape state stays private; external surfaces are noisy, lagged, and incomplete.
- Learning the physics distribution is desired; memorizing stress draws is not.
- Every landscape feature must declare a **value port**, a **publish boundary**, and a **success metric**.
- Port D does **not** distill teacher weights; it multiplies graph evidence into recipes and product tasks, re-executes, and only then exports (see §2.8).
- **Cards are not “verified” for compounding until Launch Bar is green** (`Launch_Bar.md`).

---

## 1b. Epistemic Status (Do Not Collapse)

| Artifact | Status | How to speak about it |
|----------|--------|----------------------|
| Hard physics gates + lean `S_combined` | Protocol ground truth **when Launch Bar green** | “Passed / failed the registered exam” |
| Score Pack margins / category vectors | Deterministic functions of predictions + pack | Auditable components of the exam |
| Causal effect library (D3) | Observational estimates (selection, confounding, non-random miner behavior) | “Band suggests association under stated confounders; CI hygiene required” — **not** “proven causes” |
| Noisy priors / masks | Decision-support scaffolds | Orientation for search — not guarantees |
| Product battery | Separate promotion exam | Shelf truth ≠ leaderboard truth |

**Carbon applies its own standard to its own brain:** gate-level certainty language is reserved for gates. Causal publish requires overlap, stability windows, and withdrawable versioning — and still remains decision-support.

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
| Warm-start orientation | D6 **noisy derivatives only** | Masks / coarse bands — **never** full `specialist_bank_item` | Compositional search without SKU leak |

**Port A law:** Competition never requires purchase. Full Specialist Bank items are Port D only.  
**L0 publish** only after `Launch_Bar.md` green; L0 priors are aggregates/noise — not causal bands.

### 2.4 Port B — Validator Eval Efficiency (Safety-Sensitive)

| Mechanism | Inputs | Behavior | Value |
|-----------|--------|----------|-------|
| Progressive routing | D9 | Predicted easy fails → shallow; frontier → full depth | GPU-seconds ↓ |
| Adaptive stress emphasis | D4, D3 | Bias stress mass toward live weak spots of *prior population* | Harder static gaming |
| Gate health | D1 aggregates | Unstable gates → more samples / stricter fp32 checks | Consensus quality |
| Near-prior detection | D6 noisy lineage, D10 | Clones still gated; reduced exploration credit only | Anti-cloning |

Port B remains **lean-exam aligned**. Full product battery is **not** a default validator path.

#### Port B floor rules (mandatory)

Progressive depth influences *how hard the exam looks*. Misrouting can create blind spots the gates never fully stress.

**Force full depth when any of the following hold:**

1. Hotkey has insufficient full-depth history on this `challenge_id` (threshold in validator policy)  
2. Random audit draw (fixed fraction per tempo — not miner-predictable)  
3. Submission is near record / top-K threat on that board  
4. Rank movement after a prior shallow path exceeds policy delta  
5. Launch Bar not yet green → **all** evals full depth (no progressive routing)

**Hard constraints**

- Routing signals are **validator-private RPC only** — never miner-reachable  
- Routing **never** writes into `S_combined` or gate pass/fail  
- Gates still judge; shallow path may only reduce *volume* of stress samples within registered pack bounds — not disable mandatory gates  
- Red-team priority: adversary who models D9 to farm shallow paths  

### 2.5 Port C — Incentives & Challenges

| Mechanism | Inputs | Effect | Value |
|-----------|--------|--------|-------|
| Challenge weight proposals | D5 | More emissions to unsaturated high-upside boards | Search where EV remains |
| Breakthrough assist | D3, D1 | Flag new-best + novel causal region (gov final) | Bounty quality |
| Decay tuning hints | D5 | Faster decay on flat frontiers | Stale winner pressure |
| Stress / challenge evolution | D4, D5, D7, D11 | Versioned stress catalogs; PB failure modes → new stress families | Adversarial roadmap |

**Forbidden:** landscape similarity as a direct score term.

### 2.6 Port D — Commercial & Dual-Regime

Canonical pipeline: [`Specialist_Bank.md`](./Specialist_Bank.md). Landscape owns graph + opportunity + repair; bank owns gauntlet + dual egress.

### 2.7 Anti-Gaming Rules

1. Gates never overridden by landscape.  
2. No row-level D1, exact D3, live D9, or D11 for miners.  
3. Publish with noise + lag (daily or slower).  
4. Train data ≠ eval data forever; landscape is not a stress side channel.  
5. Causal models versioned and withdrawable.  
6. Paid tiers buy search orientation or private challenge design — never eval outcomes.  
7. Success = post-gate progress + commercial conversion, not guidance-API engagement.  
8. **No full specialist on miner API.**  
9. **No commercial full SKU without product battery pass.**  
10. **No L0 compounding publish until Launch Bar green.**  
11. **Causal language never inherits gate-level certainty.**

### 2.8 Export Doctrine (Port D alignment)

> **Ground truth in. Verified knowledge out.**

Landscape must not implement Port D as “export last week’s winner weights.” Gauntlet stages, anti-distillation, and dual threshold remain as in v1.1 — see Specialist Bank for execution.

---

## 3. Recommended Architecture

Design principles, component diagram, repo layout, feature contracts, symbolic/causal paths, opportunity ranker, prior pack publisher, cadence — **unchanged in substance from v1.1**.

**Additional control-plane rule:** `VersionGovernor` and prior publisher check `Launch_Bar` status (or equivalent CI flag) before marking a prior pack `public_publish=true`.

Confounder set, treatments, and publish gates for D3 remain as specified. Primary outcomes still emphasize stress robustness and gate-pass vectors — which is why **honest gates are prerequisite**.

---

## 4. Phased Build-Out Guide

### Phase L0 — Skeleton (parallel to subnet Phase 0)

**Objective:** Reliable card lake + publishable noisy priors from aggregates (no causal yet).

**Prerequisite:** `Launch_Bar.md` green for the challenge families that will emit public priors.

**Deliverables:** model_card schema; CardLake + FeatureStore; baseline PriorPackBuilder; coarse diagnostics; KPI dashboard.

**Exit criteria:** ≥95% full evals ingestible; daily priors for live Phase-0 pairs *only if Launch Bar green*; MCP priors without blocking validation.

**Until Launch Bar green:** ingest may run offline; **no** marketed prior surface.

### Phase L1 — Symbolic + Failure Atlas

As v1.1; still no causal certainty language.

### Phase L2 — Causal Core + Specialist Pipeline Hooks

**Objective:** D3 production with explicit observational framing; opportunity ranker; D11 schema.

**Exit criteria:** bands only with overlap/CI/stability; measurable search lift or faster time-to-gate-pass; zero Port A specialist payloads; **external docs still distinguish gates vs estimates**.

### Phase L3 — Eval & Economy Coupling

Port B live only with §2.4 floor rules enforced; GPU-seconds ↓ without rank instability; no miner path to D9.

### Phase L4 — Product Gauntlet & Dual-Regime

As v1.1; grounding gate mandatory.

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
| A | ↑ share clearing Tier-1; ↓ attempts to first all-gate pass |
| A | Estimation Mode rank correlation vs full eval (top quartile) |
| A | **Zero** full specialist payloads on miner API |
| B | ↓ GPU-seconds per ranking; stable agreement; **audit full-depth rate** in policy band |
| C | Emission share on unsaturated challenges |
| D | PB pass rate; zero SKUs without PB; anti-distillation |
| Graph | Promotion_fail repair latency |
| Moat | Ablation of public prior detail does not collapse internal quality |
| Goodhart | Lean rank vs later PB pass correlation monitored |
| Epistemic | Zero public materials equating causal bands with gate proof |

---

## 7. Implementation Checklist (Condensed)

**Pre-L0** — Launch Bar CI for first challenge family  
**L0** — card schema; lake; features; daily noisy priors *gated on bar*; MCP pull  
**L1** — PySR + registry; failure atlas; prior rollback  
**L2** — causal fitter + publish gates; masks; opportunity ranker; no Port A SKU leak  
**L3** — private eval RPC + Port B floors; frontier → gov  
**L4** — D11; ProductExporter grounding gate; sealed packs  

---

## 8. Thesis

Build the Landscape Agent as a **batch intelligence system with four controlled ports**, not as a live strategy oracle and not as a teacher-distillation factory.

- **Private richness** enables causal and symbolic compounding.  
- **Public poverty** preserves incentives and moat.  
- **Validator coupling** converts intelligence into cheaper, harder **lean** evaluation — under Port B floors.  
- **Product coupling** converts intelligence into specialists only through a **verification gauntlet**.  
- **Dual threshold** keeps search affordable and the commercial shelf honest.  
- **Launch Bar** keeps the flywheel from compounding dishonest labels.  
- **Epistemic discipline** keeps gates and causal estimates from being sold as the same thing.

---

*Canonical reference for Landscape Agent value routing and build order (v1.2). Port D with `Specialist_Bank.md`. Launch prerequisites: `Launch_Bar.md`. Scoring labels: `Scoring.md`.*
