# Landscape Agent — Value Extraction, Architecture & Build-Out Guide

## TL;DR

**What this is:** How verified Model Cards become private intelligence, and how that intelligence is routed back into the subnet without opening a gaming vector.

**Four ports (Value Router):**
- **A Search** — noisy priors, causal masks, diagnostics (miners)
- **B Eval** — progressive depth, adaptive stress (validators only)
- **C Economy** — challenge weights, bounty assist (governance)
- **D Product** — specialists, sponsor briefs, air-gap packs

**Moat rule:** estimate richly in private; publish sparsely (noise + lag). Full causal graph and card lake never go to miners. **Gates remain the only judge of score.**

**Optimal causal job:** which strategy choices *cause* gated robustness in a regime — then orient search, eval, emissions, and commercial packaging.

**Build phases:** L0 card lake + aggregate priors → L1 symbolic + failure atlas → L2 causal core + specialists → L3 eval/economy coupling → L4 product/dual-regime.

**Read next:** §2 value products / ports, §3 architecture, §4 phase L0–L4 checklist.

---

**Carbon Subnet**  
**Version:** 1.0 (July 2026)  
**Status:** Core Engineering Appendix  
**Audience:** Tech lead, Landscape implementers, protocol designers  
**Related:** `SPEC.md`, `appendices/Implementation.md`, `appendices/Data_Management.md`, `appendices/Specialist_Bank.md`

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

### 2.3–2.7 Ports, anti-gaming, metrics

See detailed tables in the remainder of this appendix for Port A–D mechanisms, anti-gaming rules, success metrics, and the phased L0–L4 build-out (architecture diagram, feature contracts, PySR/DML paths, prior pack format, private eval-signal RPC, and implementation checklist).

**Kill switch:** if any published surface correlates with pre-gate score inflation without post-gate gains, roll back noise scale, lag, or discontinue that surface.

---

## 3. Recommended Architecture (Summary)

Batch intelligence system: **Ingest → CardLake/FeatureStore → Fitters (symbolic, causal, atlas, frontier, specialist) → Serve (prior packs, diagnostics, private eval signals, product export) → Control plane (schedule, version, kill switches).**

Principles: batch over online for causal/symbolic fits; append-only card lake; versioned feature contracts; separate serve path from train path; every served artifact carries `landscape_version` + `data_cutoff_block`.

Full component diagram, repo layout under `carbon/landscape/`, Model Card feature contract, PySR→MT path, Double ML path, prior pack noise recipe, and private `/v1/eval_signals` RPC are specified in the detailed sections of this document’s canonical design (build against L0–L4 exit criteria).

---

## 4. Phased Build-Out (L0–L4)

| Phase | Focus | Exit bar (examples) |
|-------|--------|---------------------|
| **L0** | Card lake + aggregate noisy priors + diagnostics | ≥95% ingestible cards; daily packs |
| **L1** | Symbolic + failure atlas | Stable templates; MCP tiers; rollback |
| **L2** | Causal core + masks + specialists | CI/overlap gates; measurable search lift |
| **L3** | Eval routing + economy signals | Cheaper ranking; no miner path to D9 |
| **L4** | Sponsor briefs, air-gap packs, product export | Paid/provenance artifact shipped |

---

## 5. Thesis

Build the Landscape Agent as a **batch intelligence system with four controlled ports**, not as a live “strategy oracle.”

- **Private richness** enables causal and symbolic compounding.  
- **Public poverty** (noise, lag, masks) preserves incentives and moat.  
- **Validator coupling** converts intelligence into cheaper, harder evaluation.  
- **Product coupling** converts intelligence into specialists and paid discovery.  

The optimal causal use case remains: *identify which training choices cause gated robustness in each regime — then orient search, evaluation, emissions, and commercial packaging accordingly.*

---

*This appendix is the canonical reference for Landscape Agent value routing and build order. Implementation code should follow the contracts and phase exit criteria; research experiments may run offline but must not bypass publish gates or moat boundaries.*

**Implementation note:** For full code-level contracts (Model Card schema fields, prior_pack_v1 JSON, causal confounder set, cadence table, and condensed checklists), retain the detailed design from the Landscape Agent v1.0 appendix body in repo history if a section was condensed for readability—restore full subsections when implementing L0+.
