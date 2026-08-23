# Carbon Litepaper Citation Map v2

**Status:** editorial evidence map for Academic Litepaper v3.1 review.  
**Scientific basis:** `docs/context/SCIENTIFIC_REFERENCE_CANON.md` plus later explicitly identified owner-recommended scientific architecture reflected in the v3.x paper generation.  
**Business basis:** `Business/Business_Canon.md` and the canonical `Business/` documentation.  
**Publication control:** `docs/publications/PUBLICATION_RECONCILIATION_2026-08-23.md`.  
**Purpose:** apply evidence and authority discipline to the condensed Carbon litepaper without turning it into an academic review or an investor deck.

---

## Editorial rule

External citations belong where Carbon makes claims about the external scientific/engineering world.

Carbon-specific mechanism statements should point to Carbon specifications/design records where useful, while business strategy should point to the business canon rather than external academic literature.

Recommended rhetorical pattern:

> established external evidence → unresolved problem → Carbon design response → explicit maturity boundary

Do not attach academic citations to Carbon's protocol or business choices as if the cited papers validated Carbon's exact mechanism, pricing, GTM, or network economics.

---

## Scientific citation sequence

### [1] Operator-learning opportunity

Place after the statement that neural operators / learned surrogates can make repeated physical-system evaluation dramatically cheaper after training.

**Canon:** FNO + Neural Operator.

**Claim strength:** demonstrated in canonical PDE settings; not universal speedup or deployment fitness.

### [2] Operator learning as a general paradigm

Place after the explanation that Carbon begins with methods for learning families of physical-system mappings rather than isolated solves.

**Canon:** Neural Operator + optional DeepONet.

### [3] Physics-aware learning motivation

Place after the statement that data fit is not identical to physical generalization.

**Canon:** physics-informed ML / PINNs / PINO.

**Discipline:** these sources support physics-aware learning as a serious research direction; they do not prove Carbon's hard-admissibility architecture.

### [4] Structure / conservation matters

Place near the argument that low predictive error can coexist with physically undesirable behavior.

**Canon:** structure-preserving / conservation-aware learning.

### [5] Need for broader SciML evaluation

Place after criticism of relying on one held-out field-error number.

**Canon:** PDEBench.

### [6] Generalization / uncertainty remains open

Place near robustness, regime shift, uncertainty, or deployment limitations.

**Canon:** SciML UQ sources.

**Discipline:** Carbon's score-bearing stress semantics are Challenge-specific; external UQ/OOD literature does not justify arbitrary hidden extrapolation.

### [7] Context of use and bounded credibility

Place after explanation that a model claim is bounded by intended use and evidence.

**Canon:** ASME VVUQ 1 + ASME V&V 40.

Do not claim ASME certification or endorsement.

### [8] Model/simulation lifecycle credibility

Place near provenance, limitations, change, escalation, and requalification.

**Canon:** NASA-STD-7009B + NASA-HDBK-7009B; optional surrogate-model application source.

### [9] Agentic / closed-loop research

Place after discussion of agents participating in scientific search.

**Canon:** autonomous-lab and computational-research-agent sources.

**Discipline:** supports plausibility of automated scientific loops, not Carbon's performance.

### [10] Learning from experiments / active experimental design

Place in the future Physics Intelligence / experimental-memory discussion.

**Wording:** future research direction; not present commercial capability.

### [11] Bittensor as incentive substrate

Place where Carbon distinguishes its scientific objective from Bittensor's economic search substrate.

**Claim:** Bittensor supports subnet-defined incentive mechanisms and miner/validator competition. Carbon-specific scientific truth and frontier semantics remain Carbon design choices.

### [12] Surrogate credibility bridge

Optional where the litepaper connects learned surrogates to engineering model-use evidence.

Use NASA surrogate/statistical-model credibility material where appropriate.

---

## Carbon-native scientific references

These are **not external scientific evidence**. They describe Carbon's mechanism or design state.

The litepaper should distinguish current runtime authority from later owner-recommended integrated architecture.

Relevant Carbon-native topics include:

1. P0 strategy schema and miner submission semantics;
2. hidden evaluation / seed / disclosure boundaries;
3. current Score Pack and binary hard-gate implementation;
4. qualified-exam doctrine: task, population, SamplingPlan, generator, truth, measurements, Validation Dossier;
5. Score Pack as Evidence Use Contract and admissibility-before-ranking doctrine;
6. Challenge-bound scores / no automatic cross-Challenge comparability;
7. common frontier-promotion evidence and `FrontierAdvanceEvent` design;
8. treasury settlement as a separate authority from scientific winner determination;
9. Product Battery / Qualification Record and lifecycle semantics;
10. Burgers repair lessons and the distinction between historical PoC behavior and a future authoritative Challenge;
11. explicit maturity states.

Because some integrated scientific architecture remains ahead of current runtime migration on `main`, the litepaper should not imply that an owner-recommended design object is already implemented merely because it is described in the paper.

---

## Business-native references for v3.1

The new commercial section is Carbon-authored business strategy. It should be grounded in the canonical business documents, principally:

- `Business/Business_Canon.md`;
- `Business/Business_Plan.md`;
- `Business/Product_and_Revenue_Architecture.md`;
- `Business/Go_To_Market.md`;
- `Business/Network_and_Alpha_Value.md`;
- `Business/Commercial_Operating_Model.md`.

Do **not** add academic citations to statements such as:

- Evidence Audit is the preferred first SKU;
- the hybrid services → platform → network → lifecycle model;
- fiat-first enterprise procurement;
- OpCo/network separation;
- the land-and-expand ladder.

Those are Carbon business-design choices, not established scientific results.

Any externally sourced market-size, competitor, funding, revenue, or enterprise-software statistic belongs in a separately dated investor source model, not in the academic litepaper unless it is genuinely necessary to the argument.

---

## Recommended scientific bibliography posture

The litepaper should remain selective rather than attempting to reproduce the full scientific canon. A core set should cover:

1. Fourier Neural Operator;
2. Neural Operator;
3. DeepONet or equivalent operator-learning foundation;
4. physics-informed machine learning / PINNs;
5. PINO or another operator/physics bridge;
6. PDEBench;
7. UQ/generalization literature;
8. ASME VVUQ terminology / credibility;
9. ASME V&V 40 where scoped carefully;
10. NASA model/simulation lifecycle guidance;
11. autonomous scientific systems / research agents;
12. Bittensor official mechanism references;
13. adaptive-data/leaderboard validity where protected evaluation is discussed;
14. reproducibility / model-card evidence literature where provenance is discussed;
15. model-reduction / hybrid scientific-modeling sources supporting the broader fast-model category.

The exact numbered bibliography must match the final committed v3.1 source before release.

---

## What citations should establish

A skeptical reader should be able to independently verify these external premises:

1. fast learned physical operators exist in demonstrated settings;
2. physical structure, robustness, uncertainty, and generalization are not reducible to one loss number;
3. engineering credibility is evidence- and context-of-use-dependent;
4. model credibility has a lifecycle and provenance burden;
5. repeated/adaptive evaluation can compromise naive holdout validity;
6. automated research loops are plausible;
7. Bittensor can provide an economic substrate for a subnet-defined commodity.

Everything beyond those premises is Carbon's design or business thesis and must be labeled accordingly.

---

## v3.1 business/traction non-claim

The commercial section must not use citations, wording, or formatting to imply that Carbon has already demonstrated:

- paid customers;
- repeatable service delivery;
- recurring revenue;
- validated pricing;
- proven gross margins;
- platform adoption;
- network commercial leverage;
- automatic OpCo-to-Alpha value transfer.

Those are separate commercial evidence states under the Business Canon.
