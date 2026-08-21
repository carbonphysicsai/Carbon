# Symbolic-Numeric Design Discovery Ledger

**Branch:** `design/symbolic-numeric-integration`  
**Status:** active design-forward simulation ledger; non-runtime and non-scoring.  
**Purpose:** Capture architecture discoveries surfaced by implementation pressure before updating Carbon's canon, papers, or Summit deck.

## Classification

- **KEEP** — confirms current design.
- **HARDEN** — current concept is right but needs another invariant/boundary.
- **EXTEND** — a new capability has been earned by a concrete design need.
- **REVISE** — an existing design is materially suboptimal.
- **DEFER** — plausible but not yet justified.
- **REJECT** — tempting idea that would weaken Carbon.

## Ledger status

Discoveries D-001 through D-071 remain active as recorded in prior revisions. Gate 8 adds:

| ID | Discovery | Source gate | Class | Design consequence | Canon/paper/pitch consequence | Confidence |
|---|---|---|---|---|---|---|
| D-072 | Producer-independent reconstruction is the invariant; fresh retraining is the neural subtype. | No-neural-networks test | REVISE/EXTEND | Future validator abstraction uses ReconstructionProtocol; neural Challenges retain mandatory fresh retraining. | Major canon/whitepaper terminology improvement; litepaper can remain simple. | Very high |
| D-073 | Model Card is not the universal scientific evidence object. | No-neural-networks test | EXTEND/HARDEN | Preserve P0 Model Card; future experimental-memory superclass supports trained and non-trained artifacts. | Whitepaper/canon architecture addition. | Very high |
| D-074 | FastPhysicalModel is genuinely technology-agnostic. | No-neural-networks test | KEEP/CONFIRM | ROMs, symbolic reductions, adaptive solvers, classical surrogates and portfolios fit the evidence/task abstraction. | Major long-term positioning confirmation. | Very high |
| D-075 | Carbon should not require learning when a non-learned method wins. | No-neural-networks test | KEEP/HARDEN | No ML ideology term; registered scientific outcome remains authority. | Strong credibility line for canon/whitepaper. | Very high |
| D-076 | Computational admissibility can be separated from scientific ranking. | No-neural-networks test | EXTEND/HARDEN | Future acceleration Challenges may hard-constrain latency/memory/build budget/interface before scientific ranking, without contaminating physics score. | Important scoring/economic distinction. | Very high |
| D-077 | Answerability/coverage is part of the registered task contract. | No-neural-networks test | EXTEND/HARDEN | Abstention, partial coverage and escalation semantics must be prospective to prevent selective answering. | Strong product/qualification addition. | Very high |
| D-078 | Product value may live at the qualified system/portfolio level. | No-neural-networks test | EXTEND/HARDEN | Router + multiple fast models + high-fidelity escalation may be the qualified product. | Potentially major commercial/product thesis. | High |
| D-079 | Reproducibility semantics are construction-family dependent. | No-neural-networks test | EXTEND/HARDEN | Define family-appropriate reproducibility evidence under one producer-independent reconstruction invariant. | Scientific-method detail. | Very high |
| D-080 | Commercial packaging must generalize beyond weights/ONNX. | No-neural-networks test | REVISE/EXTEND | Long-term SKU is qualified executable FastPhysicalModel/system package; ONNX remains one option. | Product/market positioning update. | Very high |
| D-081 | Carbon's durable abstraction is experimental search over fast physical representations. | No-neural-networks test | KEEP/CONFIRM | Full loop survives removal of neural networks. | Core final-review candidate for canon/whitepaper and restrained litepaper/deck wording. | Very high |

## Gate 8 terminology stress-test

Current P0 terminology remains valid for the implementation now being built. Long-term generalization candidates are:

| Current narrow term | Long-term superclass/generalization |
|---|---|
| training strategy | ModelConstructionStrategy |
| retrain from scratch | independent reconstruction / ReconstructionProtocol |
| neural model/checkpoint | FastPhysicalModel / assembled artifact identity |
| Model Card | ExperimentRecord superclass, with Model Card as learned-model view/subtype |
| backbone | construction family/component graph |
| ONNX product | qualified executable FastPhysicalModel/system package |

These are architecture discoveries, **not instructions to rename current P0 wire contracts**.

## Gate 8 objective decomposition

Future mixed-family acceleration Challenges may distinguish:

```text
scientific admissibility
  physical gates / finite behavior / required coverage

computational admissibility
  registered latency / memory / build-resource / interface constraints

ranking among admissible candidates
  registered scientific Score Pack
```

This preserves interpretability while preventing the original high-fidelity solver from trivially winning a Challenge whose purpose is acceleration.

## Remaining simulated gates

1. ~~Structural validator execution/hardening.~~ **PASS**
2. ~~ModelingToolkit adapter.~~ **PASS WITH ARCHITECTURE EXTENSIONS**
3. ~~Physics Evaluation Primitive Library.~~ **PASS — MEASUREMENT CONTRACT DISCOVERED**
4. ~~Challenge Compiler / dossier authoring integration.~~ **PASS — MEASUREMENT IDENTITY + EVIDENCE REQUIREMENT**
5. ~~Landscape physical-context integration.~~ **PASS AS TESTABLE INTELLIGENCE ARCHITECTURE**
6. ~~Hybrid model-construction search.~~ **PASS — MODEL-CONSTRUCTION ABSTRACTION EARNED**
7. ~~Coupled/multiphysics crash test.~~ **PASS — COMPOSITION LAYER REQUIRED**
8. ~~Carbon-without-neural-networks test.~~ **PASS — DURABLE ABSTRACTION CONFIRMED**
9. Final system-level design review.

**Publication rule:** do not edit the canon/papers/deck from individual findings. Complete Gate 9 final system review, classify stable discoveries by destination/maturity, then integrate them in one reconciled pass.
