# Causal Landscape Value Flows

**Carbon Subnet**  
**Version:** 1.0 (July 2026)  
**Status:** Design doctrine — how causal outputs from the Landscape Agent must drive value back into the subnet  
**Audience:** Core team, tech lead, investors reviewing the compounding-intelligence thesis

---

## 1. Purpose

The Landscape Agent’s **causal** layer (Double Machine Learning over Model Cards) estimates which strategy choices *cause* better verified outcomes after controlling for confounders.

This document answers a single question:

> **How should those causal estimates be converted into measurable value for miners, validators, customers, the treasury, and the long-term moat — without opening gaming vectors or giving away the landscape?**

Symbolic outputs (PySR → ModelingToolkit structured losses) are complementary. This document focuses on **causal** data and the closed-loop uses that justify building and protecting that capability.

---

## 2. What “Causal Data” Actually Is

Every full evaluation produces a Model Card. Over time the private stream supports estimates of the form:

$$
\tau(x) = \mathbb{E}[Y(1) - Y(0) \mid X = x]
$$

where:

| Symbol | Meaning in Carbon |
|--------|-------------------|
| **Treatment $T$** | A strategy lever (or coarse bin): loss-term enable/weight band, curriculum scale, mode budget, optimizer family, conditioning choice, backbone family, etc. |
| **Outcome $Y$** | Verified metrics: combined score, physics-fidelity component, stress-robustness component, gate-pass indicators, rollout horizon, residual tail quantiles |
| **Confounders $X$** | Physics class / challenge family, backbone, epoch budget band, data-seed family, phase, generator version, approximate compute tier |

**Primary causal products (internal):**

1. **Global and regime-conditional treatment effects** — “In transonic compressible + FNO-class, raising conservation weight from band A→B causes +Δ stress robustness (CI).”
2. **Heterogeneous effects** — effects that flip sign or magnitude by regime, mesh type, or stress family.
3. **Interaction effects** — curriculum × loss, backbone × gate-critical levers.
4. **Failure attribution** — which levers causally reduce specific gate-fail modes (mass, shock, separation, interface, …).
5. **Credibility metadata** — sample size, overlap diagnostics, CI width, stability across time folds (when the estimate is trustworthy enough to act on).

**Publishing rule (non-negotiable):**  
Full causal graphs, raw CATE tables, and high-resolution effect maps stay **proprietary**. External surfaces get **noisy, coarse, delayed, or productized** derivatives only.

---

## 3. Design Principles for Value Extraction

1. **Causal estimates are for allocation of search and product decisions — not a soft score term in emissions.** Feeding $\tau$ directly into miner scores creates a new gaming surface (optimize for looking causal, not for clearing gates).
2. **Value must close a loop the subnet already owns:** priors → submissions → verified Model Cards → better causal estimates → better priors / specialists / challenges.
3. **Prefer actions that raise the rate of *new verified bests* and *gate-clearing specialists*,** not actions that only increase submission volume.
4. **Heterogeneity is the product.** Average effects across all PDEs are weak. Regime-conditional effects are what miners and customers pay for implicitly.
5. **Uncertainty is first-class.** Low-confidence causal claims must not steer emissions, specialist promotion, or commercial SLAs.

---

## 4. Value Pathways (Detailed)

### 4.1 Noisy Strategic Priors (Core Operational Loop)

**Mechanism**  
Translate high-confidence, regime-conditional effects into coarse guidance embedded in daily/weekly noisy priors:

- Preferred weight *bands* (not point values) for gate-critical losses
- Curriculum scale ranges associated with positive robustness effects
- “Avoid” bands where effects are negative or unstable
- Optional ranked lever list: top-k treatments by lower-confidence-bound of $\tau$ on stress robustness

**Value returned**
- Higher EV local search for humans and agents
- Higher fraction of full submissions that clear Tier-1 filters and physics gates
- Faster time-to-new-best on active challenges
- Lower wasted validator GPU on hopeless strategies

**Innovation detail**  
Priors should be **effect-shaped**, not winner-cloned. A prior is a distribution over strategies whose mass is tilted by causal lower bounds, then noised. Cloning the champion encodes confounders; tilting by $\tau$ encodes mechanisms.

**Subnet feedback**  
Track: gate-pass rate of prior-conditioned submissions vs baseline; delta in blocks-to-new-best; validator GPU per verified improvement.

---

### 4.2 Estimation Mode Calibration (Zero-Cost Miner Loop)

**Mechanism**  
Estimation Mode today approximates outcomes from noisy priors. Causal data upgrades the approximator:

- Use regime-conditional effects to adjust estimated score *deltas* when a miner changes one lever at a time
- Provide a cheap “causal sensitivity” readout: “this edit is in a historically positive band for stress robustness on this challenge family”
- Still never expose full CATE tables or champion weights

**Value returned**
- Agents run more informative free iterations before paying for light training or waiting on full eval
- Better correlation between Estimation Mode ranking and eventual validator outcomes (reduces cynicism and spam)

**Innovation detail**  
**Counterfactual sketch mode:** miner proposes $S$ and $S'$ differing in one treatment; Estimation Mode returns a noisy $\widehat{\Delta Y}$ grounded in $\tau(x)$ plus uncertainty — not a simulated full train. This is the closest thing to “causal autocomplete” that still protects the landscape.

---

### 4.3 Specialist Bank Promotion Criteria

**Mechanism**  
Do not promote specialists only because they won once. Require:

- Verified gate-pass under current generator version
- Strategy features aligned with **stable positive causal levers** for that regime (or explicit ablation showing the specialist captures those mechanisms)
- Hold-out stress families where causal failure modes were previously concentrated

**Value returned**
- Specialists that customers buy are robust for *reasons*, not leaderboard accidents
- Model Cards can cite “aligned with network-estimated drivers of robustness in regime R” without publishing the full causal model
- Higher renewal / lower return rate on Tier-1 specialists

**Innovation detail**  
**Causal fitness score (internal only):** a specialist’s promotion rank combines verified metrics with coverage of high-$\tau$ levers. Used for Bank curation and bundling — never as miner emission weight.

---

### 4.4 Stress & Challenge Design (Adversarial Curriculum for the Network)

**Mechanism**  
Causal failure attribution identifies levers and regimes where the network is weak:

- Gates that fail often *despite* miners optimizing the obvious losses → stress family under-weighted or gate threshold mis-set
- Treatments with large positive $\tau$ on accuracy but near-zero on robustness → stress set too easy on the dimensions that matter
- Empty regions of treatment space with high outcome variance → under-explored frontiers worth a bounty or a sponsored challenge

**Value returned**
- Stress generators evolve toward the true difficulty frontier
- Public challenges stay informative instead of saturating
- Sponsored challenges can be priced and scoped using evidence of where discovery is still hard

**Innovation detail**  
**Causal gap bounties:** treasury posts a temporary emission or alpha bounty for the first strategy that (a) clears gates and (b) moves a designated weak lever band into a stable positive effect region. Pays for *closing a knowledge gap*, not for cosmetic score ticks.

---

### 4.5 Validator Queue & Compute Allocation

**Mechanism**  
Validator GPU is the binding constraint. Causal data informs **priority**, not scores:

- Boost queue priority for submissions that explore high-uncertainty, high-potential treatment regions (active learning for the landscape)
- Boost priority for strategies that stress-test a commercial specialist’s claimed regime (protect product quality)
- Deprioritize near-duplicates of densely sampled, low-$\tau$ regions unless they claim a new best on a live challenge

**Value returned**
- More information per GPU-hour
- Faster improvement of the causal model itself (exploration where variance is high)
- Sponsored and high-reputation traffic still respected via existing Priority enum; causal boost is an additional signal inside Standard/High-reputation bands

**Innovation detail**  
**Information-value bidding (internal):** each submission gets an approximate expected information gain for the Landscape Agent (reduction in CI width on priority treatments). Combined with estimated score upside for queue order. Does not change Yuma weights.

---

### 4.6 MCP Diagnostics (Black-Box but Causal-Aware)

**Mechanism**  
Diagnostics stay black-box on hidden data, but can become *mechanism-aware*:

- Tiered messages: “failure correlates with conservation residual tail” (already planned) upgraded to “edits in band B have historically improved this failure class on similar challenges” when confidence is high
- Never reveal stress instance IDs, seeds, or full effect tables
- Rate-limit and noise the guidance so it cannot reverse-engineer the landscape

**Value returned**
- Agents improve without full landscape access
- Perceived fairness: feedback feels actionable, not random
- Still defensible against “oracle leakage” critiques

**Innovation detail**  
**Diagnostic tiers tied to causal confidence:**  
- Tier A (always): scores, gate pass/fail categories  
- Tier B (medium confidence): coarse lever-family hints  
- Tier C (high confidence + rate-limited): noisy band suggestions  
Tier C is a privilege surface for sustained contributors or light-training users — not a free full dump.

---

### 4.7 Cross-Challenge and Cross-Phase Transfer

**Mechanism**  
Estimate which effects transfer:

- Poisson/Darcy → elasticity (shared elliptic structure)
- Laminar NS → transitional regimes (what breaks)
- Single-physics levers that remain causal under sequential FSI / CHT coupling

Publish only coarse transfer priors (“elliptic family: conservation-style penalties remain positive drivers of boundary gates”). Keep fine transfer graphs internal.

**Value returned**
- Phase transitions do not reset the network to zero intelligence
- New challenges bootstrapping from related causal structure reach useful priors faster
- Specialist bundles can be marketed as “regime families” with transfer evidence

**Innovation detail**  
**Transfer certificates (commercial):** when selling a specialist into an adjacent regime, attach an internal transfer score derived from cross-regime causal stability. Externally: qualitative regime card + verified metrics on the target challenge — not the raw transfer model.

---

### 4.8 Commercial Packaging

#### 4.8.1 Tier-1 Specialists
Causal fitness (internal) + verified gates → Bank membership. Marketing claims stay limited to measured metrics and audit artifacts; causal language is optional and conservative (“optimized under network-wide robustness drivers”).

#### 4.8.2 Sponsored Challenges (Tiers 2–4)
Causal gaps define **what is worth sponsoring**:

- Customer cares about separation / shock / interface → package a challenge whose stress family and gates align with those failure modes
- Pricing reflects difficulty: wider CIs and negative/null effects in the region ⇒ higher discovery value ⇒ higher challenge fee
- IP-licensed and private tiers can include a **private causal addendum** for the sponsor (regime-specific effect summary), while the global landscape remains Carbon’s

#### 4.8.3 Verification / Evidence Products
Beyond Model Cards:

- **Robustness driver summary** (coarse): which mechanism classes were critical to gate-pass for this model
- Useful for primes building IV&V narratives without exposing subnet internals

#### 4.8.4 Tooling Partners (Verification Gas)
Partners query registry proofs. Optional premium: “mechanism class tags” on a model_id (conservation-critical, shock-stable, …) derived from causal attribution — still not full $\tau$ tables.

**Value returned**  
Direct revenue, better packaging, differentiation from “another ONNX file on a leaderboard.”

---

### 4.9 Incentive Design (Careful, Indirect)

**Do use causal data to shape the environment of rewards:**

| Mechanism | Role of causal data |
|-----------|---------------------|
| ChallengeWinnerTracker | Unchanged scoring; causal data does not enter weight formula |
| Stress evolution | Makes “true” difficulty track real weaknesses → rewards genuine robustness |
| Causal gap bounties | Discrete, time-boxed alpha/emission bonuses for closing designated gaps |
| Exploration credits | Optional dust or queue priority for submissions in high-uncertainty treatment regions (information value), capped and auditable |
| Specialist adoption bonus | Small, delayed credit when a miner’s strategy features are distilled into a promoted specialist (attribution via strategy hash lineage) |

**Do not:**
- Add a “causal alignment” term to the combined score
- Let miners optimize against published fine-grained $\tau$
- Pay for estimated effects without verified gate-pass

**Value returned**  
Emissions buy both **performance** and **knowledge coverage**, without turning the landscape into a second public objective to game.

---

### 4.10 Governance of Gates and Generators

**Mechanism**  
Causal diagnostics for the *evaluation system itself*:

- If no treatment predicts gate-pass above noise → gate may be random or broken
- If a single cheap lever perfectly predicts pass → gate may be too weak or collinear with a trivial trick
- If effects flip after a generator version bump → version impact report for validators and governance

**Value returned**  
Protects long-term credibility of trustless verification — the asset institutional buyers actually underwrite.

---

### 4.11 Agent-Native Causal Tools (MCP)

**Mechanism**  
Structured tools for autonomous miners:

- `get_noisy_prior(challenge, backbone)`
- `estimate_lever_delta(challenge, backbone, lever, from_band, to_band)` → noisy $\widehat{\Delta}$, CI band, confidence tier
- `list_open_causal_gaps(challenge_family)` → coarse gap IDs eligible for bounties
- `get_failure_family_hint(submission_id)` → Tier B/C diagnostics only

**Value returned**  
Makes Carbon the path of least resistance for autoresearch-style agents: the environment *speaks causal strategy language* without exposing the proprietary landscape database.

---

### 4.12 Treasury & Token Value Capture

Causal quality compounds **real option value** of the network:

- Better priors → higher quality specialists → higher Tier-1 revenue
- Clearer gaps → more sellable sponsored challenges
- Stronger verification story → verification gas and prime deals
- Moat: the causal database is expensive to rebuild and is not published

**Treasury policy suggestion**  
A fixed fraction of sponsored-challenge revenue funds (a) Landscape compute, (b) causal gap bounties, (c) generator/gate audits. That makes the compounding loop economically self-sustaining rather than purely emission-funded.

---

## 5. Priority Order (What to Build First)

| Priority | Pathway | Why first |
|----------|---------|-----------|
| **P0** | Regime-conditional effects → noisy priors + Estimation Mode deltas | Immediate miner/agent EV; closes the main loop |
| **P0** | Failure-mode attribution → diagnostic tiers | High perceived value, low landscape leakage if coarse |
| **P1** | Causal fitness for Specialist Bank promotion | Direct commercial quality |
| **P1** | Stress/challenge design from gaps | Keeps evaluation meaningful; feeds GTM |
| **P2** | Queue information-value boost | Matters when validator load bites |
| **P2** | Causal gap bounties | Incentive innovation once effect estimates are stable |
| **P3** | Cross-regime transfer certificates | Phase 1B+ |
| **P3** | Premium registry mechanism tags | When partner API demand exists |

---

## 6. Anti-Patterns (Explicitly Rejected)

1. **Publishing full CATE tables or interactive landscape browsers** — destroys the moat and creates a meta-game.
2. **Causal score terms in Yuma weights** — optimizes for looking aligned with yesterday’s $\tau$.
3. **Acting on low-overlap / tiny-N effects** — ships folklore as science; undermines gate credibility.
4. **Winner-only regression called “causal”** — not causal; reintroduce confounders.
5. **Using causal hints to reconstruct hidden stress instances** — diagnostics must be aggregated and delayed enough to prevent this.
6. **Paying emissions for “novel treatments” with no verified outcome** — noise farming.

---

## 7. Success Metrics

| Metric | Intent |
|--------|--------|
| Gate-pass rate of prior-conditioned vs cold submissions | Priors help |
| Correlation(Estimation Mode rank, final combined score) | Calibration quality |
| Blocks-to-new-best on active challenges | Search efficiency |
| Validator GPU-hours per verified new best | Compute efficiency |
| Specialist hold-out stress pass rate post-promotion | Commercial quality |
| Fraction of stress-family updates driven by documented causal gaps | Evaluation stays adversarial |
| Sponsored-challenge attach rate in gap-rich regimes | Causal data → revenue |
| Stability of top effects across time folds / generator versions | Scientific integrity |

---

## 8. Summary Doctrine

Causal landscape data is not a dashboard. It is a **control signal** for:

- where the network searches,
- what it promotes to product,
- how hard evaluation stays,
- how agents are guided without being handed the moat,
- and where commercial energy is aimed.

The optimal system uses Double ML to estimate **regime-conditional drivers of verified robustness**, then routes those estimates into **noisy priors, Estimation Mode, specialist curation, stress evolution, selective incentives, and sponsored-challenge design** — while the fine-grained causal database remains proprietary infrastructure.

That is how causal intelligence pays rent to the subnet instead of becoming an expensive research side-quest.

---

*Related: `SPEC.md`, `docs/TRUSTLESS_VERIFICATION_AND_DATA_GENERATION.md`, `appendices/Implementation.md` (Landscape Agent), Specialist Bank and GTM sections in README.*
