# Carbon Scientific Reference Canon v3 — Symbolic-Numeric / Fast-Physical-Model Addendum

**Status:** Research/evidence map for team review; companion to `SCIENTIFIC_REFERENCE_CANON.md` v2.  
**Purpose:** Integrate the stable scientific consequences of the symbolic-numeric design-discovery program (Gates 1–9) before the whitepaper/litepaper/deck revision.  
**Authority:** This document does **not** define protocol behavior. Current code and normative Carbon specifications remain authoritative. External references support premises; they do not prove Carbon's mechanism works.  
**Reconciliation rule:** Where this addendum broadens language from neural-operator training to fast-physical-model construction, that is a **long-term scientific ontology**, not a P0 scope change.

---

# 1. Why the canon needs this addition

Canon v2 correctly establishes the case for neural operators, physics-aware objectives, protected evaluation, reproducibility, experimental memory, causal discipline, qualification, and Bittensor as an incentive substrate.

The symbolic-numeric design simulation surfaced a missing scientific premise:

> **Physical AI is not one model family, and the scientific object being optimized need not always be a neural network.**

Modern scientific computing spans equation-based symbolic-numeric models, numerical solvers, reduced-order models, hybrid mechanistic/data-driven models, learned closures, neural operators, and compositions of these. Carbon's scientific architecture should therefore preserve enough structure to compare model-construction interventions without making any representation or model family an oracle.

This addition deepens—not replaces—the existing thesis:

> **If credible physical generalization is the unresolved commercial target, make physics-surviving generalization the target of an open intelligence market.**

The long-term scientific object becomes:

```text
model-construction intervention
        ×
physical structure / regime
        ×
producer-independent reconstruction
        ×
exact measurement semantics
        ×
protected outcome / failure
        ×
reproducibility
        ×
qualification context
```

---

# 2. Pillar O — Symbolic-numeric scientific models separate physical semantics from numerical realization

## O1. ModelingToolkit: A Composable Graph Transformation System for Equation-Based Modeling

- **Citation:** Ma, Y., Gowda, S., Anantharaman, R., Laughman, C., Shah, V., Rackauckas, C. (2021), *ModelingToolkit: A Composable Graph Transformation System For Equation-Based Modeling*.
- **URL:** https://arxiv.org/abs/2103.05244
- **Tier / strength:** Tier I — PRIMARY SYSTEMS / SCIENTIFIC-COMPUTING WORK.
- **Supports:** Equation-based symbolic representation; composable model transformations; structural transformations such as index reduction; generation of numerical implementations; integration of data-driven surrogate generation within an acausal modeling framework.
- **Does not prove:** That a symbolic representation is physically correct; that a transformation preserves every engineering interpretation automatically; that Carbon should depend on ModelingToolkit; or that symbolic structure should determine Carbon gates/thresholds.
- **Use:** Whitepaper structured-physical-representation section; canon rationale for separating physical semantics, transformed symbolic representation, and numerical realization.

## O2. Modelica / equation-based acausal modeling tradition

- **Citation:** Fritzson, P., *Modelica — A Language for Equation-Based Physical Modeling and High Performance Simulation* (foundational Modelica literature; equation-based/acausal modeling).
- **URL:** https://modelica.org/papers/1998-06-fritzson-para98LNCS1541-equationbasedmodelingandHighPerformance.pdf
- **Tier / strength:** Tier II — FOUNDATIONAL TECHNICAL / MODELING-LANGUAGE WORK.
- **Supports:** Equation-based, non-causal physical modeling in which constitutive relations need not be encoded as one fixed input-output assignment; reusable physical components and composition are established scientific-computing concepts.
- **Does not prove:** Carbon's proposed `CouplingContract`, composition schema, or that acausal representation is required for every Challenge.
- **Use:** Whitepaper/canon support for future compositional physical semantics and for avoiding a universal causal-runtime ontology.

### O synthesis

Carbon should distinguish at least three levels of representation:

1. **authored physical semantics** — the scientific model/assumptions being claimed;
2. **transformed symbolic semantics** — algebraic/structural transformations used to prepare computation;
3. **numerical realization** — discretization, solver, coupling schedule, implementation and execution details.

These levels can be related without being treated as identical.

> **Symbolic equivalence is not automatically numerical equivalence, and numerical equivalence is not automatically operational equivalence.**

---

# 3. Pillar P — Hybrid mechanistic/data-driven models make model construction a legitimate search space

## P1. Universal Differential Equations for Scientific Machine Learning

- **Citation:** Rackauckas, C. et al. (2020), *Universal Differential Equations for Scientific Machine Learning*.
- **URL:** https://arxiv.org/abs/2001.04385
- **Tier / strength:** Tier I/II — FOUNDATIONAL FRONTIER PRIMARY for hybrid SciML.
- **Supports:** Mechanistic differential equations can be combined with universal approximators/data-driven components; scientific priors and learned components can coexist within one computational model; hybrid construction is broader than choosing one monolithic neural surrogate.
- **Does not prove:** Hybrid models are universally better than neural operators; learned internal terms are mechanistically true; or Carbon should privilege hybrid models in scoring.
- **Use:** Whitepaper future model-construction search; canon support for `ModelConstructionStrategy` as broader than training recipe.

## P2. Learning physics-based models from data: perspectives from inverse problems and model reduction

- **Citation:** Ghattas, O., Willcox, K. (2021), *Learning physics-based models from data: perspectives from inverse problems and model reduction*, Acta Numerica 30, 445–554.
- **URL:** https://doi.org/10.1017/S0962492921000064
- **Tier / strength:** Tier I — REVIEW / FOUNDATIONAL SYNTHESIS.
- **Supports:** Data can be integrated into physics-based models through inverse problems and model reduction; low-dimensional physical structure can be exploited to build predictive models for design, control, and decision-making; scientific-model construction is broader than deep-learning surrogacy.
- **Does not prove:** Any one reduction/inference method is appropriate for Carbon or that reduced models automatically satisfy qualification requirements.
- **Use:** Whitepaper scientific-model-construction section; long-term technology-neutral positioning.

### P synthesis

Carbon's long-term scientific question should not be:

> Which neural architecture should win?

It should be:

> **Which permitted model-construction intervention produces the strongest evidence-bounded fast physical model for the registered task?**

Neural operators remain the first search class. Hybrid models, learned closures, reduced models, and future representations are hypotheses to be tested—not preferred ideologies.

---

# 4. Pillar Q — Reduced-order modeling establishes a mature non-neural fast-physical-model tradition

## Q1. A Survey of Projection-Based Model Reduction Methods for Parametric Dynamical Systems

- **Citation:** Benner, P., Gugercin, S., Willcox, K. (2015), *A Survey of Projection-Based Model Reduction Methods for Parametric Dynamical Systems*, SIAM Review 57(4), 483–531.
- **URL:** https://doi.org/10.1137/130932715
- **Tier / strength:** Tier I — REVIEW / FOUNDATIONAL MODEL-REDUCTION SOURCE.
- **Supports:** Model reduction explicitly seeks cheaper/faster computational models that retain relevant behavior of large-scale systems; parametric reduced models are useful for repeated simulation, design, control, optimization, and UQ.
- **Does not prove:** A reduced model is credible outside its tested regime; that ROMs should be admitted to current Carbon P0; or that reduced order alone guarantees useful acceleration.
- **Use:** Whitepaper support for technology-neutral `FastPhysicalModel`; canon evidence that fast physical representations predate and extend beyond neural surrogates.

### Q synthesis

The Carbon abstraction should not require learning when a non-learned reduction wins under the registered task.

> **The protocol should reward evidence-bounded physical utility, not the presence of machine learning.**

This supports the long-term `FastPhysicalModel` concept while leaving current neural-operator implementation unchanged.

---

# 5. Pillar R — Measurement is a scientific object distinct from the property being measured

## R1. Verification and Validation in Scientific Computing

- **Citation:** Oberkampf, W. L., Roy, C. J. (2010), *Verification and Validation in Scientific Computing*, Cambridge University Press.
- **URL:** https://www.cambridge.org/core/books/verification-and-validation-in-scientific-computing/0F0D3C8B79AEEA0BFEAA1CFC8472A42B
- **Tier / strength:** Tier I — AUTHORITATIVE TECHNICAL FOUNDATION.
- **Supports:** Code verification, solution verification, model validation, uncertainty, predictive capability, and quantitative assessment are distinct parts of computational credibility; the mathematical model, its computer implementation, numerical error, experimental comparison, and predictive claim should not be conflated.
- **Does not prove:** Carbon's `MeasurementContract` schema or any specific threshold.
- **Use:** Whitepaper measurement/evidence architecture; support for separating physical relation, numerical measurement, reference evidence, and qualification.

## R2. Measures of agreement between computation and experiment: validation metrics

- **Citation:** Oberkampf, W. L., Barone, M. F. (2006), *Measures of agreement between computation and experiment: Validation metrics*, Journal of Computational Physics 217(1), 5–36.
- **URL:** https://doi.org/10.1016/j.jcp.2006.03.037
- **Tier / strength:** Tier I/II — PRIMARY METHODOLOGICAL.
- **Supports:** Quantitative comparison between computational predictions and observations requires explicitly defined validation metrics; a physical claim and its computable measure are not interchangeable.
- **Does not prove:** One universal metric, Carbon's hard-gate hierarchy, or automatic derivation of thresholds from symbolic equations.
- **Use:** Whitepaper support for `MeasurementContract` and metric identity/calibration discipline.

### R synthesis

The design simulation's strongest evidence-architecture addition is scientifically well motivated:

```text
physical relation / property
        ↓
MeasurementContract
        ↓
reference + calibration evidence
        ↓
Validation Dossier
        ↓
Score Pack use
```

Carbon should treat:

> **measurement definition ≠ measurement qualification ≠ measurement use.**

A symbolic PDE does not define how its residual is discretized, sampled, normalized, aggregated, calibrated, or thresholded.

---

# 6. Pillar S — Composition creates interface-level evidence and non-compositional qualification

Scientific/engineering systems are frequently compositions of subsystems rather than one monolithic PDE. Equation-based modeling literature supports component composition; V&V/qualification literature supports bounded credibility rather than automatic inheritance.

The Carbon design consequence is a research hypothesis rather than an externally proven protocol rule:

> **If independently qualified components are assembled, system credibility still requires evidence about their interfaces, joint operating envelope, numerical coupling, and assembled behavior.**

The canon should therefore distinguish:

- component physical semantics;
- coupling/interface semantics;
- numerical coupling realization;
- component measurements;
- interface measurements;
- assembled-system measurements;
- product-context measurements.

**Does not prove:** The exact `CouplingContract` or `CompatibilityEnvelope` schema.

**Use:** Whitepaper future multiphysics/qualification discussion; product architecture rationale.

---

# 7. Pillar T — Physics intelligence must demonstrate prospective decision value

The existing canon already supports active learning, adaptive experimentation, causal discipline, and the distinction between observation and intervention. Symbolic-numeric integration adds a sharper test for the phrase **physics intelligence**.

Recommended definition:

> **Physics intelligence is provenance-bearing knowledge about how model-construction interventions interact with physical structure, regime, measurement, and engineering context, demonstrated by improved prospective decisions rather than retrospective narrative alone.**

This definition implies several falsifiable requirements:

1. physical-context representations must be evaluated against baselines;
2. authored, derived, and learned physical features require provenance;
3. measurement-version changes cannot silently masquerade as physical outcome changes;
4. selection provenance matters because performance-market experiments are adaptively chosen;
5. failures, censoring, and infrastructure failures must remain distinguishable;
6. a knowledge graph or embedding is not a moat unless it improves future search, experiment allocation, qualification prediction, or decision economics.

### T1. H16 — Structured physical context improves prospective transfer prediction

Compare:

```text
baseline:
intervention + Challenge identity + ordinary metadata

vs.

physical-context model:
intervention + structured physical context + exact measurement identity + ordinary metadata
```

Evaluate prospectively on held-out Challenge versions/systems.

**Support criterion:** better calibrated prediction or better downstream experiment/search decisions.

**Rejection criterion:** no meaningful prospective improvement after controlling for complexity and leakage.

---

# 8. Updated Carbon research hypotheses

Append the following to Pillar N's existing research program.

### H19 — Structured physical context

Does a provenance-bearing physical-context representation improve prospective intervention-transfer prediction relative to Challenge identity and ordinary metadata alone?

### H20 — Scientific authoring efficiency

Does structured physical representation + typed evidence requirements reduce Challenge-authoring time, semantic drift, or scientific-definition errors without weakening human scientific review?

### H21 — Measurement-contract integrity

Does explicit versioned measurement identity reduce threshold/metric drift and improve reproducibility of evaluation across implementations and Challenge versions?

### H22 — Hybrid model-construction search

For suitable Challenges, does competition across permitted learned, hybrid, and reduced construction families produce better evidence-bounded outcomes or decision economics than restricting search to one architecture family under matched resource/admissibility constraints?

### H23 — Producer-independent reconstruction

Does generalizing producer-independent verification from fresh neural retraining to family-appropriate independent reconstruction preserve/reduce reproducibility and gaming failures across heterogeneous model classes?

### H24 — Context-aware portfolio value

Can a qualified portfolio/router/escalation system achieve better engineering decision economics than a single universal fast model while preserving bounded answerability and system-level qualification?

### H25 — Challenge-authoring product value

Can an evidence-aware Challenge authoring workflow convert partner/domain models into scientifically reviewable experimental programs faster or with fewer semantic/evidence defects than an unstructured bespoke process?

These are Carbon hypotheses. External literature motivates them; it does not establish their truth.

---

# 9. Updated whitepaper argument map

Canon v2's 14-chapter map remains structurally sound. Integrate the new material without turning the whitepaper into an implementation manual.

## Part I — Why physics intelligence is needed

Add to the commercial-gap argument:

- physical-model acceleration is broader than neural surrogates;
- credible generalization includes both artifact behavior and evidence-bounded claims about where that behavior holds.

## Part II — Why Carbon uses an incentivized scientific system

Retain `physics > loss` and protected evaluation.

Clarify:

> physics-weighted evaluation is **technology-neutral**. A model need not encode explicit symbolic physics to survive an external physics exam.

## Part III — How competition becomes intelligence

Deepen independent retraining into the general principle of **producer-independent reconstruction**, while stating that neural-operator Challenges use fresh retraining.

Add:

- structured physical context;
- exact measurement identity;
- selection provenance;
- prospective decision lift as the standard for physics intelligence.

## Part IV — How intelligence becomes engineering value

Add:

- model-construction search beyond one architecture family;
- bounded answerability/abstention/escalation;
- component qualification does not automatically compose;
- qualified portfolios/routing as a future product hypothesis.

## Part V — What Carbon must prove

Add H19–H25 and preserve explicit rejection criteria.

---

# 10. Updated litepaper subset

The new canon should have **minimal** effect on the litepaper