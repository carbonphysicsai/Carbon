# Symbolic-Numeric Design Simulation — Gate 8: Carbon Without Neural Networks

**Status:** abstraction crash test; no current protocol or P0 changes.  
**Objective:** Remove neural networks entirely and test whether Carbon still has a coherent scientific/economic object to search, independently evaluate, learn from, qualify, and commercialize.

## Why this test matters

Current `SPEC.md` is explicitly framed around "physics-informed neural operator training strategies," neural-operator backbones, validator retraining, Model Cards, and commercial neural-model artifacts. That is correct for the current implementation direction. Gate 6/7 suggest the deeper architecture may be broader. Gate 8 tests that claim rather than assuming it.

## Non-neural competitor set

Assume a future Challenge permits several candidate construction families with **no neural networks**:

1. **Projection/reduced-order model** — POD/Galerkin-style reduced dynamics or another basis-reduced numerical model.
2. **Symbolically reduced model** — equations transformed/reduced under stated assumptions into a cheaper executable representation.
3. **Analytical/asymptotic approximation** — closed/semi-closed approximation valid in a bounded regime.
4. **Adaptive coarse solver** — lower-fidelity numerical method with error-control/routing logic.
5. **Response surface / classical surrogate** — polynomial/rational/Gaussian-process or other non-neural approximant where allowed.
6. **Piecewise model portfolio** — several fast models plus a routing rule and high-fidelity escalation.

All must satisfy the same registered task/output contract and be independently reconstructed/executed by validators.

## Core-loop test

### 1. Can miners submit a reproducible hypothesis?
Yes, if the submission is generalized from "training recipe" to **construction recipe**.

Examples:

```text
ROM:
  basis construction method
  rank selection rule
  calibration procedure
  integrator

symbolic reduction:
  source model ref
  allowed transformation family
  approximation order
  parameterization

adaptive solver:
  discretization family
  refinement/error-control policy
  tolerances within Challenge limits
```

**Result:** hypothesis/strategy abstraction survives; neural training is not essential.

### 2. Can validators independently reproduce it?
Yes, but "retrain from scratch" is too narrow.

The general operation is:

> **independent reconstruction under a registered execution contract.**

For a neural model, reconstruction means fresh training. For a ROM it may mean rebuilding the basis from authorized training/reference data. For a symbolic approximation it may mean rerunning the registered reduction/transformation. For an adaptive solver it may mean rebuilding/configuring the executable numerical method.

**Discovery:** `retrain` is one subtype of a broader reproducibility operation.

### 3. Can Carbon run protected independent exams?
Yes.

The exam consumes the common CandidateOutputContract and qualified MeasurementContracts. It does not require the candidate to contain learned weights.

Hard physics gates, hidden draws, stress distributions, evaluation-information governance, and Score Packs remain coherent.

**Result:** the verification mechanism is technology-agnostic at its strongest boundary.

### 4. Can Bittensor reward competition?
Yes, provided the Challenge prospectively defines admissible construction families/resources and validators can deterministically execute them.

The optimization target remains external scientific performance under Carbon's score, not "neuralness".

### 5. Can Landscape learn from the experiments?
Yes.

Interventions become model-construction interventions such as:

- basis rank;
- reduction family;
- closure assumption;
- asymptotic order;
- solver tolerance/refinement policy;
- routing policy;
- architecture/training choices when neural models are present.

The intervention-outcome graph actually becomes scientifically broader.

### 6. Can Product qualification work?
Yes.

Qualification binds the exact assembled FastPhysicalModel artifact + execution environment + context of use + evidence. A product need not contain weights.

### 7. Can Carbon commercialize it?
Yes, if the artifact provides useful acceleration/decision economics and passes the product-specific evidence bar.

The commercial SKU may be a library, executable solver, reduced model, model portfolio, service/API, or other controlled artifact rather than ONNX.

**Discovery:** current ONNX/weights language is implementation-specific product packaging, not the long-term product ontology.

## Where current Carbon language breaks

The architecture survives, but several current terms do not.

### `training strategy`
Breaks for analytical/reduced/adaptive numerical methods.

General term: `ModelConstructionStrategy`.

### `retrain from scratch`
Breaks when no training occurs.

General term: `independent reconstruction` or `independent build-and-execute`.

Fresh retraining remains the required neural subtype.

### `Model Card`
Partially breaks semantically because a non-learned artifact may have no training history.

General evidence object should be closer to an **Experiment Record / Artifact Evidence Record**, with Model Card retained as a neural/learned-model profile or familiar rendering.

### `weights/checkpoint`
Breaks completely as universal identity.

General identity: content-addressed assembled artifact graph + construction provenance.

### `backbone`
Breaks as universal strategy field.

General: construction family/component graph under ConstructionPolicy.

### `ONNX commercial SKU`
Breaks as universal product form.

General: qualified executable FastPhysicalModel package; ONNX is one packaging option.

### `model`
Still works if defined broadly as a computational representation of physical behavior. However, where ambiguity matters Carbon should use `FastPhysicalModel` or `computational physical model` rather than implying ML.

## Adversarial simulations

### A. Exact solver enters competition
A miner submits the original high-fidelity solver and trivially wins physics/accuracy but defeats acceleration intent.

**Decision:** CandidateOutputContract alone is insufficient. The Challenge must define **decision/resource constraints** or admissibility goals when acceleration is part of the task. However, resource economics should remain separate from physics score unless explicitly part of the registered Challenge objective.

This suggests a Challenge may define hard resource admissibility (e.g., latency/memory ceiling) before scientific ranking, analogous to physics gates but semantically distinct.

### B. Cheap approximation abstains on hard cases
A piecewise analytical approximation answers only easy regimes and refuses others.

If the Challenge permits abstention/routing, coverage becomes part of the task contract. If it requires universal response inside the envelope, abstention is failure.

**Discovery:** answerability/coverage semantics belong in CandidateOutputContract/Challenge contract, not inferred after evaluation.

### C. Portfolio routes hard cases to high-fidelity truth
A fast model answers 95% and escalates 5%.

For engineering this may dominate a universally approximate model even if per-query latency is higher on escalations.

**Discovery:** the product optimization target can be **decision economics of a qualified system**, not raw surrogate speed or one-model accuracy. This is distinct from subnet scientific score.

### D. Symbolic reduction is interpretable but wrong outside asymptotic assumptions
The formula looks mechanistic and transparent.

**Decision:** interpretability does not expand the envelope. Same evidence-bounded qualification applies.

### E. Classical surrogate wins
Carbon must allow it.

**Decision:** no model-family ideology. If a polynomial/rational/GP/ROM beats neural approaches under the registered objective and admissibility constraints, it deserves the scientific result.

### F. Miner submits a hand-coded lookup/interpolant exploiting generator regularity
This may perform well without representing useful transferable physics.

**Decision:** protected stress/evaluation design, envelope diversity, anti-memorization/gaming controls, and construction policy remain necessary independent of ML.

### G. Non-neural strategy has no stochastic training variance
Its reproducibility profile differs fundamentally from neural training.

**Discovery:** reproducibility evidence should be construction-family aware. Repeat-training dispersion is not a universal metric; deterministic reconstruction equivalence may be the relevant test.

### H. Symbolic transformation produces a simpler exact equivalent
If genuinely equivalent and much cheaper, Carbon should reward the outcome if admissible.

This is a feature, not a loophole: Carbon's scientific objective should not require learning when mathematics can solve the acceleration problem better.

## Earned abstraction: ReconstructionProtocol

Generalize the validator-side producer-independence operation:

```text
ReconstructionProtocol {
  protocol_id
  construction_family
  source_inputs/data refs
  environment
  build/reduction/training procedure
  randomness semantics
  resource limits
  artifact outputs
  reproducibility checks
}
```

Examples:

- neural: fresh retraining;
- ROM: rebuild basis/operator from authorized data;
- symbolic: rerun reduction/transformation;
- adaptive solver: rebuild/configure numerical executable;
- portfolio: reconstruct components + routing policy.

Producer-independent reconstruction remains the invariant; training is one implementation.

## Earned abstraction: ExperimentRecord

Current Model Cards remain useful and should not be casually renamed in P0. Long term, the scientific evidence superclass should support artifacts with or without training:

```text
ExperimentRecord {
  intervention_ref
  reconstruction_protocol_ref
  physical_context_refs
  artifact_identity
  measurement_results
  score/gate results
  resource evidence
  execution provenance
  reproducibility evidence
  result/censoring state
  qualification lineage?
}
```

A `ModelCard` can remain a learned-model-specific view/subtype if desired.

## Challenge objective decomposition

Gate 8 reveals a useful distinction between **admissibility** and **ranking**.

A future Challenge may have separate registered constraints:

```text
SCIENTIFIC ADMISSIBILITY
  finite / physical gates / required coverage

COMPUTATIONAL ADMISSIBILITY
  latency / memory / build budget / interface requirements

RANKING AMONG ADMISSIBLE CANDIDATES
  registered scientific Score Pack
```

This is not a recommendation to alter current P0 scoring. It is a future mixed-family design principle.

Why useful: the original high-fidelity solver can be scientifically perfect but fail the acceleration task's computational admissibility, without contaminating physics scoring with arbitrary cost weights.

## New architecture discoveries

### D-072 — Producer-independent reconstruction is the invariant; fresh retraining is the neural subtype
**Class:** REVISE/EXTEND.

Long-term validator semantics should generalize to `ReconstructionProtocol` while preserving mandatory fresh retraining for neural strategies where applicable.

### D-073 — Model Card is not the universal scientific evidence object
**Class:** EXTEND/HARDEN.

Retain current Model Card semantics for P0. Long-term experimental memory should have an `ExperimentRecord`/artifact-evidence superclass capable of non-trained models.

### D-074 — FastPhysicalModel is genuinely technology-agnostic
**Class:** KEEP/CONFIRM.

The object survives neural removal: ROMs, symbolic reductions, adaptive solvers, classical surrogates and portfolios can all fit if they satisfy the task/evidence contract.

### D-075 — Carbon should not require learning when a non-learned method wins
**Class:** KEEP/HARDEN.

The scientific objective is better fast physical modeling under registered evidence, not maximizing ML usage.

### D-076 — Computational admissibility can be separated from scientific ranking
**Class:** EXTEND/HARDEN.

For acceleration Challenges, use prospective hard resource/interface constraints where necessary, then rank scientifically among admissible candidates rather than silently mixing cost into physics score.

### D-077 — Answerability/coverage is part of the task contract
**Class:** EXTEND/HARDEN.

Abstention, partial coverage and escalation must be prospectively specified; otherwise models can game evaluation by declining hard cases.

### D-078 — Product value may live at the qualified system/portfolio level
**Class:** EXTEND/HARDEN.

A router + several FastPhysicalModels + high-fidelity escalation can outperform any single model in engineering decision economics. Qualification must bind the assembled decision system when sold as such.

### D-079 — Reproducibility semantics are construction-family dependent
**Class:** EXTEND/HARDEN.

Repeat-training variance is not universal. Define reproducibility evidence appropriate to reconstruction family while preserving producer independence.

### D-080 — Commercial packaging must generalize beyond weights/ONNX
**Class:** REVISE/EXTEND.

Long-term product ontology is a qualified executable FastPhysicalModel/system package. ONNX remains one learned-model packaging option.

### D-081 — Carbon's durable abstraction is experimental search over fast physical representations
**Class:** KEEP/CONFIRM.

The full loop survives removal of neural networks: propose construction -> independent reconstruction -> protected scientific evaluation -> evidence -> Landscape learning -> bounded qualification -> engineering use.

## System-level conclusion from Gate 8

The strongest long-term statement supported by the simulation is:

> **Carbon is an incentivized experimental system for discovering, independently testing, learning from, and qualifying methods for constructing fast physical models.**

Neural operators are a highly practical first model class and should remain the implementation focus. They are not the architecture's terminal ontology.

A second, more product-oriented formulation is:

> **Carbon searches for the fastest useful physical representations that survive the evidence required for their intended job.**

The first formulation is scientifically safer because "fastest" and "useful" depend on registered task constraints and product context.

## Gate verdict

**PASS — CARBON REMAINS COHERENT WITHOUT NEURAL NETWORKS.**

The abstraction test confirms the broader architecture. Do not broaden P0 implementation. Carry the terminology corrections and abstractions into Gate 9 final system-level review, where each discovery will be classified for: implementation now/later, canon, whitepaper, litepaper, Summit deck, product strategy, and explicit non-claims.
