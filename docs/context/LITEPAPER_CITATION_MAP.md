# Carbon Litepaper Citation Map v1

**Status:** Editorial evidence map — team review  
**Depends on:** `docs/context/SCIENTIFIC_REFERENCE_CANON.md`  
**Purpose:** Apply the Scientific Reference Canon to the condensed Carbon litepaper without turning the litepaper into an academic review.

---

## Editorial rule

The litepaper should use approximately **12–16 external citations**, concentrated where Carbon makes claims about the external world. Carbon-specific architecture should cite or link the normative Carbon specifications rather than external literature.

Recommended rhetorical pattern:

> established external evidence -> unresolved problem -> Carbon design response

Do not attach academic citations to Carbon's own protocol choices as if the papers validated those choices.

---

## Proposed citation sequence

### [1] Operator-learning opportunity
**Place after:** statement that neural operators / learned surrogates can make repeated physical-system evaluation dramatically cheaper after training.

**Canon:** A1 + A2.  
Li et al., FNO; Kovachki et al., Neural Operator.

**Claim strength:** "demonstrated in canonical PDE settings," not universal speedup.

---

### [2] Operator learning as a general paradigm
**Place after:** explanation that Carbon competes on methods for learning families of PDE solution operators rather than isolated solves.

**Canon:** A2 + optional A3.

---

### [3] Physics-aware learning motivation
**Place after:** "data fit is not identical to physical generalization" / introduction of physics as a first-class objective.

**Canon:** B1 + B2.

**Wording discipline:** These papers show that incorporating governing physics is a serious and useful SciML research direction. They do not prove Carbon's exact hard-gate design.

---

### [4] Structure/conservation matters
**Place near:** explanation that low prediction error can coexist with physically undesirable behavior and that some requirements may warrant admissibility semantics.

**Canon:** B3 + B4 (or B5 in the whitepaper only).

---

### [5] Need for holistic SciML evaluation
**Place after:** criticism of relying on one held-out field-error number.

**Canon:** C1 PDEBench.

**Preferred litepaper use:** one citation can support the need for broad tasks/metrics and the continuing difficulty of SciML evaluation.

---

### [6] Generalization / OOD / uncertainty remains open
**Place after:** discussion of trustworthiness at hard regimes and distribution shifts.

**Canon:** C2 + C3.

**Important:** Carbon's score-bearing stress stays inside its declared envelope; cite these sources to establish deployment/generalization difficulty, not to justify arbitrary OOD scoring.

---

### [7] Context of use and bounded credibility
**Place after:** "a bounded claim about model behavior, tied to independent evidence" and/or Qualification Record explanation.

**Canon:** D1 ASME VVUQ 1 + D2 ASME V&V 40.

**Preferred wording:** "Engineering V&V practice treats credibility as evidence- and context-of-use-dependent." Do not claim ASME certification or endorsement.

---

### [8] Model/simulation lifecycle credibility
**Place near:** evidence trail, provenance, limitations, escalation, and requalification discussion.

**Canon:** D3 NASA-STD-7009B + D4 NASA-HDBK-7009B.

**Optional stronger bridge:** D5 specifically discusses application of NASA-STD-7009 concepts to surrogate/statistical models.

---

### [9] Agentic / closed-loop scientific research
**Place after:** MCP miner loop / "competitive automated scientific research."

**Canon:** E1 A-Lab + E4 AI Scientist.

**Reason for pairing:** A-Lab supplies a real closed-loop scientific system; AI Scientist supplies evidence that computational agents can automate meaningful portions of a research loop.

---

### [10] Learning from failed experiments / active experimental design
**Place after:** Landscape future direction where evidence may guide more informative experiments.

**Canon:** E1/F1 + F2 or F3.

**Wording:** Future direction; not current Carbon capability.

---

### [11] Bittensor as incentive substrate
**Place in:** "Carbon sets the target; Bittensor creates the search pressure."

**Canon:** G1 + G3.

**Claim:** Bittensor supplies a network in which subnet incentive mechanisms can define a commodity, miners produce it, and validators score it. Carbon's scientific definition of the commodity remains Carbon-specific.

---

### [12] Surrogate credibility bridge
**Place in product section, optional:** where Carbon argues that learned surrogates need model-use evidence rather than only benchmark performance.

**Canon:** D5 NASA surrogate-model application.

This is particularly useful in the whitepaper; the litepaper can omit it if the bibliography becomes crowded.

---

## Carbon-native references that should appear separately

These are not academic references. The litepaper should point readers to the repository/specification for:

1. Strategy schema and miner submission semantics.
2. Challenge / Score Pack / Generator Pack versioning.
3. Hard-gate authoritative-zero semantics.
4. Current P0 `0.45 / 0.30 / 0.25` baseline.
5. Hidden evaluation and seed/disclosure boundaries.
6. EvaluationReceipt / Model Card / EvaluationCard evidence semantics.
7. Landscape four-port authority boundaries.
8. Product Battery and Qualification Record semantics.
9. Current maturity status.

A compact note can state that the protocol specification is normative and the litepaper explanatory.

---

## Recommended litepaper bibliography (12-source core)

1. Li et al. — *Fourier Neural Operator for Parametric Partial Differential Equations*.
2. Kovachki et al. — *Neural Operator: Learning Maps Between Function Spaces*.
3. Raissi, Perdikaris & Karniadakis — *Physics Informed Deep Learning*.
4. Li et al. — *Physics-Informed Neural Operator for Learning Partial Differential Equations*.
5. Takamoto et al. — *PDEBench*.
6. Mouli et al. — *Using Uncertainty Quantification to Characterize and Improve Out-of-Domain Learning for PDEs*.
7. ASME VVUQ 1-2022.
8. ASME V&V 40-2018.
9. NASA-STD-7009B.
10. Szymanski et al. — *An autonomous laboratory for the accelerated synthesis of inorganic materials*.
11. Lu et al. — *The AI Scientist*.
12. Rao — *Bittensor: A Peer-to-Peer Intelligence Market* / current Bittensor docs.

Optional 13–16 for a more technical litepaper: DeepONet; Hamiltonian Neural Networks; NASA surrogate-model application; AlphaFlow.

---

## What citations should accomplish in the litepaper

The citations should let a skeptical reader independently verify five external premises:

1. **The opportunity is real:** fast learned PDE operators exist in demonstrated settings.
2. **The gap is real:** physical structure and generalization are not reducible to one predictive-loss number.
3. **The engineering standard is stricter:** credibility is bounded by use, evidence, validation, and limitations.
4. **The agentic loop is plausible:** closed-loop scientific automation and computational research agents exist.
5. **The market substrate exists:** Bittensor can economically reward a subnet-defined commodity.

Everything after those premises is Carbon's thesis and must ultimately be validated by Carbon's own experiments.
