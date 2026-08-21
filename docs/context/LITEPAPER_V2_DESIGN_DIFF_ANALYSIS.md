# Litepaper v2 — Design-Diff Analysis

**Purpose:** Decide which discoveries from symbolic-numeric / agentic design simulation belong in the litepaper, which belong only in the whitepaper/canon, and which should remain implementation-internal.

## Decision principle

The litepaper should explain **what Carbon is**, **why it matters**, **how the core mechanism works**, and **why the system can compound**. It should not teach the internal schema or every future protocol object.

A design discovery belongs in the litepaper when it materially changes at least one of:

1. Carbon's category or identity;
2. the reader's understanding of what is being searched;
3. the reason independent evaluation matters;
4. the compounding/value-accrual thesis;
5. the product/engineering end state;
6. the distinction between current P0 and long-term architecture.

A discovery stays out when it is primarily an implementation mechanism, schema detail, security control, or scientific-authoring primitive whose inclusion would obscure the core story.

---

# 1. MUST INTEGRATE — identity-level discoveries

## A. Neural operators are Carbon's first model class, not its scientific ontology

**Source discoveries:** D-045, D-074, D-075, D-081.

**Why it belongs:** This changes the reader's answer to "what is Carbon?" The old litepaper repeatedly equates Carbon with neural-operator training search. The durable architecture is broader: Carbon searches for better ways to construct fast physical models, beginning with neural operators.

**Litepaper expression:**

> Carbon incentivizes better ways to build fast physical models — starting with neural operators — and independently tests what survives.

Use examples sparingly: learned operators, hybrid models, reduced models, symbolic/numeric approximations.

**Do not include:** `FastPhysicalModel` schema, component graphs, ConstructionPolicy internals.

---

## B. The search space has levels

**Source discoveries:** D-045, D-092.

**Why it belongs:** The discovery ladder explains why agentic mining can become progressively more scientifically interesting without changing the constitutional role of the validator.

**Litepaper expression:**

```text
parameters -> strategies -> architectures/compositions -> construction algorithms
```

Add the sentence:

> Carbon can widen what participants are allowed to discover without changing who controls the grade.

**Maturity boundary:** P0 is bounded strategy search. Architecture/composition search is later. Open construction-algorithm submissions are a long-term research direction, not a live capability.

---

## C. Producer-independent reconstruction is the general principle behind retraining

**Source discoveries:** D-072, D-079.

**Why it belongs:** This explains *why* fresh validator retraining is important and lets the litepaper remain coherent when describing future non-neural methods.

**Litepaper expression:**

> In P0, validators independently retrain neural strategies from scratch. More generally, Carbon's invariant is producer-independent reconstruction: the participant proposes a reproducible method, while an independent evaluator rebuilds the candidate before the protected exam.

**Do not include:** `ReconstructionProtocol` field definitions.

---

## D. Physics intelligence should be prospective, not merely accumulated memory

**Source discoveries:** D-036–D-044, especially D-043.

**Why it belongs:** The old litepaper already introduces Landscape and experimental memory, but the simulation gave the term "physics intelligence" a much stronger scientific test.

**Litepaper definition:**

> Physics intelligence is provenance-bearing knowledge about how modeling interventions interact with physical structure, regime, measurement, and engineering context, demonstrated by better prospective scientific or engineering decisions.

Then simplify immediately:

> A database of runs is not physics intelligence. It becomes intelligence only if it helps Carbon choose better methods, experiments, qualification candidates, or escalation decisions later.

**Do not include:** ContextFeatureSet, selection-provenance enum, temporal feature-role schemas.

---

## E. Agentic Exploration Zone

**Source discoveries:** Gate 10 / D-082–D-092; Canon v3 role update.

**Why it belongs:** This materially changes the long-term research thesis. The canon is not only documentation; it becomes a bounded scientific prior for agents. This is an intuitive and differentiated explanation of how autonomous research can compound.

**Litepaper expression:**

> Carbon's scientific canon can serve as an Agentic Exploration Zone: agents may use literature, Challenge semantics, permitted Landscape evidence, and registered construction methods to generate hypotheses. The canon informs what agents try; it does not determine what Carbon accepts as true.

Key line:

> **Canon informs hypotheses. Carbon experiments adjudicate them.**

**Do not include:** arbitrary-code sandbox controls, dependency-policy details, ConstructionProgram schema.

---

# 2. SHOULD INTEGRATE — compounding and product-level discoveries

## F. Carbon compounds more than models

**Source discoveries:** D-043, D-090, D-092.

The old litepaper's Models -> Evidence -> Physics Intelligence story should be expanded carefully.

Recommended hierarchy:

```text
Fast physical models
        ↓
Verified experimental evidence
        ↓
Physics intelligence
        ↓
Reusable construction methods
```

This should not imply all runs automatically create intelligence or all novel methods graduate into a reusable library.

Preferred prose:

> Successful experiments can produce immediate model candidates; the larger asset is the evidence linking modeling interventions to outcomes. If that evidence improves future decisions, it becomes physics intelligence. Reproduced discoveries may eventually become reusable construction methods available to future agents.

---

## G. Model-family neutrality should be explicit

**Source discoveries:** D-050, D-075.

**Why it belongs:** This is a strong scientific-credibility line and prevents the broader ontology from sounding like a pivot toward symbolic methods.

Recommended line:

> Carbon does not reward a method for being neural, symbolic, hybrid, or mechanistic; it rewards what survives the registered scientific objective.

Current P0 remains neural-operator-focused.

---

## H. Product value may be a qualified system, not one universal model

**Source discoveries:** D-053, D-077, D-078.

**Why it belongs:** The existing litepaper already has answerability and a higher-fidelity truth path, so the portfolio/routing insight is a natural extension rather than extra machinery.

Recommended addition:

> Over time, the strongest engineering product may be a qualified system that routes different operating regimes to different fast models and escalates unsupported cases to higher fidelity, rather than one universal surrogate.

**Do not claim:** such a portfolio is implemented or superior.

---

# 3. KEEP IN THE LITEPAPER BUT REFRAME

## I. "Methods, not checkpoints" -> "construction methods, not self-certified artifacts"

Current wording is neural-specific. Keep fresh retraining as the P0 example, then generalize the principle.

## J. "Model Cards" -> "verified experimental records" at thesis level

Model Cards remain the current learned-model evidence artifact. But litepaper-level compounding language should not imply all future experiments require a trained neural model.

Recommended phrasing:

> P0 Model Cards, and later generalized experimental records, preserve how a candidate was constructed, measured, and reproduced.

Use sparingly to avoid introducing another object.

## K. Engineering-stack position

Change from "open training-method discovery" toward:

> **Discovery + Evidence for Physics AI**

Carbon remains between scientific-model construction/tooling and engineering deployment; it does not replace solvers or CAE.

---

# 4. DO NOT INTEGRATE INTO THE LITEPAPER — whitepaper/canon only

These discoveries are scientifically important but too implementation-specific for a 10–12 page litepaper:

- `PhysicalSystemSpec` schema / Relation IR;
- `MeasurementContract` schema and calibration identity details;
- `CandidateOutputContract` schema;
- `ConstructionPolicy` fields;
- `ContextFeatureSet`;
- `CouplingContract` schema;
- symbol namespaces/aliasing;
- units/nondimensionalization mechanics;
- geometry/topology references;
- `AdapterReport`;
- `EvidenceRequirement`;
- Challenge Compiler object graph;
- `ConstructionProgram`, `ConstructionReceipt`, `RandomnessContract` schemas;
- sandbox syscall/network/filesystem implementation;
- exact compatibility-envelope semantics;
- detailed multiphysics composition machinery.

The litepaper may express the *lesson* behind these objects — e.g. "measurement and physical claims remain versioned and evidence-bounded" — without naming the machinery.

---

# 5. Do not import these tempting but harmful framings

1. **Do not reposition Carbon as a symbolic-computing company.** Symbolic/numeric modeling is one source of scientific structure and one future construction family.
2. **Do not call the canon an oracle.** It is a prior for exploration.
3. **Do not claim autonomous algorithm discovery is live.** It is a long-term research path.
4. **Do not reward novelty in the litepaper score story.** Novel methods win only if they produce better registered outcomes; information-value experiments remain separate.
5. **Do not imply model agnosticism means unrestricted arbitrary code today.** P0 remains bounded.
6. **Do not weaken physics > loss.** Technology neutrality makes the principle stronger: external scientific behavior matters more than implementation ideology.
7. **Do not collapse model discovery and product qualification.** Rank nominates; evidence qualifies.

---

# 6. Recommended litepaper narrative after integration

The updated litepaper should answer seven questions in order:

1. **Why now?** Fast physical prediction is getting cheap; engineering credibility is not.
2. **What is Carbon?** An incentivized system for discovering better ways to build fast physical models, starting with neural operators.
3. **What changes economically?** Carbon pays for methods that survive physics and robustness, not benchmark loss alone.
4. **How does discovery work?** Participants/agents propose reproducible methods; validators independently reconstruct and run protected exams.
5. **How can discovery deepen?** Parameters -> strategies -> architectures/compositions -> construction algorithms, while the judge remains independent.
6. **What compounds?** Verified experiments become evidence; evidence that improves future decisions becomes physics intelligence; reproduced discoveries can become reusable construction methods.
7. **What ships?** Only exact artifacts/systems that survive separate, bounded qualification with answerability and escalation.

---

# 7. Target magnitude of edit

Recommended change: **material thesis revision, not whitepaper expansion**.

- Keep the document near 10–12 pages.
- Preserve P0 scoring/evaluation detail because it demonstrates concrete mechanism.
- Add roughly 1–1.5 pages of long-term ontology / discovery hierarchy / Agentic Exploration Zone content.
- Replace neural-specific language where it incorrectly describes Carbon's terminal identity, but retain neural-specific language where it accurately describes P0.
- Add only a small number of citations for the broader model-construction claim: reduced-order modeling, hybrid SciML/UDEs, symbolic-numeric modeling, and optionally one frontier construction-method example.

**Bottom line:** the simulation should make the litepaper **broader in identity, deeper in compounding logic, and clearer about the agentic discovery ceiling — without making it more operationally complicated.**
