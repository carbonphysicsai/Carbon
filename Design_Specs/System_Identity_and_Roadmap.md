# Carbon System Identity and Roadmap Reconciliation

**Status:** architecture/communication reconciliation for review.  
**Scope:** clarifies Carbon's durable identity, P0 instantiation, roadmap sequencing, commercial progression, and public explanation.  
**Does not override:** current P0 wire contracts, `Scoring.md`, `Miner_MCP.md`, `Build_Out.md`, LIVE Challenge semantics, or product qualification rules.  
**Related review queue:** `docs/context/REVIEW_THESE_PRELIMINARY_DECISIONS_POST_SIMULATION.md`.

---

## 1. Canonical system-level explanation

Carbon's durable scientific identity is:

> **Carbon is an incentivized experimental system for discovering, independently testing, learning from, and qualifying methods for constructing fast physical models.**

A simpler public expression is:

> **Carbon pays people and agents to find better ways to build fast physics models, then independently tests what survives.**

For partner conversations:

> **Give Carbon a defined physical modeling problem, a target operating envelope, and what the fast model needs to do. Carbon turns that into a competitive model-discovery program, independently evaluates the contenders, and produces evidence about what works and where it fails.**

These formulations describe the long-term system. They do **not** imply arbitrary model types or arbitrary submitted code are enabled at P0.

---

## 2. P0 is an implementation slice, not Carbon's terminal ontology

P0 remains deliberately narrow:

```text
academic PDE Challenge
        +
registered neural-operator strategy surface
        ↓
miner/agent TrainingStrategy
        ↓
validator-controlled fresh retraining
        ↓
protected physics / robustness / accuracy exam
        ↓
score + evidence
```

Neural operators are the **first model class**. `TrainingStrategy` is the **first construction-strategy subtype**. Fresh validator retraining is the **first producer-independence mechanism**.

P0 must not be broadened merely because the long-term ontology is broader.

---

## 3. What enters Carbon

The high-level input is not an unconstrained real-world physical system and not a request for Carbon to autonomously discover scientific truth.

The system starts from a **defined physical modeling problem**:

```text
physical system / engineering intent
        +
scientifically authored operating envelope
        +
required candidate inputs and outputs
        +
reference / truth sources
        +
registered evidence requirements
        ↓
Carbon Challenge
```

The scientific-authoring path remains human/evidence governed. Carbon may increasingly assist with authoring, but no generator, symbolic representation, compiler, miner, agent, or Landscape layer may silently decide scientific truth.

### Public-language rule

Prefer:

> **Carbon turns a defined physical modeling problem into an independently judged model-discovery competition.**

Avoid:

> "Carbon takes any physical system and automatically deconstructs it."

The latter overstates current scientific authority and automation.

---

## 4. Standardize the job, not the solution

The durable cross-family comparison principle is:

> **Carbon standardizes the task and the scientific exam, not the model architecture.**

Conceptually:

```text
TASK / I-O CONTRACT
required inputs
required outputs
query semantics
envelope
        ↓
-----------------------------------
 neural operator
 reduced-order model
 hybrid model
 classical surrogate
 symbolic/numeric approximation
 future construction method
-----------------------------------
        ↓
COMMON REGISTERED EXAM
```

This is the purpose of the future `CandidateOutputContract` abstraction.

Model-family neutrality does not mean all model families are accepted today. It means the protocol's scientific identity should not require one implementation ideology forever.

> **Model class is a hypothesis. Registered external evidence is the judge.**

---

## 5. Construction and evaluation

The durable authority boundary is:

```text
participant / agent
proposes how to construct the candidate
        ↓
producer-independent construction/reconstruction
        ↓
candidate artifact
        ↓
protected official evaluation
```

For current neural Challenges, producer-independent reconstruction means **fresh validator-controlled retraining**.

The proposed `ReconstructionProtocol` is under tech/science-lead review. Until accepted and implemented, documentation must not imply that P0 has a generalized reconstruction runtime.

### If S11 is accepted

The preferred evolutionary approach is:

1. define a small reconstruction interface;
2. keep exactly one registered neural-training implementation at first;
3. add additional registered reconstruction families only after the evaluator is proven;
4. permit participant-supplied construction programs only much later, in a hardened construction security domain separate from official evaluation.

Do **not** equate "reconstruction protocol" with "run arbitrary miner code inside the validator."

---

## 6. Discovery ladder

Carbon's search freedom can expand in levels:

```text
parameters
    ↓
recipes / training strategies
    ↓
architectures / model compositions
    ↓
model-construction methods
    ↓
new construction algorithms
```

The central invariant is:

> **Carbon can widen what participants are allowed to discover without changing who controls the grade.**

P0 is bounded strategy search. Open-ended construction-algorithm discovery is a long-term research direction, not a launch capability.

---

## 7. Roadmap doctrine: vary one major axis at a time

Carbon has three major expansion axes:

```text
PHYSICS DEPTH
simple PDE -> harder regimes -> geometry -> coupled/multiphysics

MODEL FREEDOM
one bounded family -> multiple neural families -> mixed families -> open construction

COMMERCIAL REALISM
academic problem -> engineering-like problem -> partner Challenge -> qualified product
```

Expanding all three simultaneously makes failures hard to interpret. Carbon's own roadmap should behave like a controlled experiment.

### Recommended scientific sequence

#### Stage 1 — Prove the judge

One narrow physical problem, one bounded construction family, end-to-end independent evaluation.

Required proof: the Challenge is unambiguous; evaluator is reproducible; hidden evaluation is protected; physics gates discriminate; scores and evidence are traceable.

#### Stage 2 — Prove physics depth

Keep the construction family bounded while moving across materially different physical systems/regimes.

Goal: show that Carbon's scientific-authoring/evaluation method survives changing physics rather than only one benchmark.

#### Stage 3 — Prove model agnosticism

Freeze a well-understood Challenge and widen the construction families.

Goal: test whether heterogeneous candidates can compete fairly through the same registered task/output contract and scientific evidence standard.

This is the experiment that earns the claim that Carbon is practically model-agnostic.

#### Stage 4 — Prove commercial discovery

Run a partner-defined engineering Challenge with bounded construction freedom and independently generated evidence.

The first industry Challenge does **not** require support for every model family.

#### Stage 5 — Prove qualification

Take a selected exact artifact/system through a deeper job-shaped Product Battery, bounded context of use, answerability/escalation policy, and lifecycle identity.

#### Stage 6 — Expand discovery freedom

Only after the judge, evidence pipeline, execution isolation, and commercial usefulness are demonstrated should Carbon expand toward hybrid decomposition, portfolios, and submitted construction-algorithm discovery.

### Roadmap slogan

> **First prove the judge. Then deepen the physics. Then widen the search. Bring industry in throughout.**

---

## 8. Industry engagement is parallel, not terminal

Do not wait for the entire generalized architecture to be complete before talking to industry.

Use two coupled tracks:

```text
SCIENTIFIC PROOF TRACK
prove judge -> physics depth -> model-family comparison -> qualification

COMMERCIAL DISCOVERY TRACK
partner interviews -> recurring problems -> required I/O -> envelopes -> truth sources -> pilot Challenge design
```

Commercial discovery begins immediately. A serious sponsored discovery pilot becomes appropriate when the lean exam is reliable enough to produce defensible evidence.

The first commercial question Carbon can answer is narrower than production deployment:

> **What construction approach should we try for this physical modeling problem, and which candidates survive independent evidence?**

Production qualification is a later, stronger claim.

---

## 9. Commercial value progression

Carbon can create value at multiple stages of the same experimental infrastructure:

| Layer | Customer question | Carbon value |
|---|---|---|
| Discovery | What should we try? | Competitive model-construction R&D |
| Evidence | Which approaches actually survive independently? | Reproducible comparison and failure evidence |
| Qualification | Can this exact artifact/system be used for this job? | Bounded evidence + Product Battery + lifecycle |
| Physics intelligence | What should we try or test next? | Prospective decision improvement from accumulated evidence |
| Construction methods | Which reproduced methods should be reused? | Evidence-bearing method library |

The commercial category is therefore stronger than "neural-operator verification."

Preferred stack framing:

> **Discovery + Evidence for Physics AI**

Carbon sits between physics/simulation/modeling tooling and engineering deployment. It should not attempt to replace high-fidelity solvers, CAE platforms, PhysicsNeMo, SciML, or customer engineering workflows.

---

## 10. What compounds

A valid experimental run is not automatically intelligence.

The intended hierarchy is:

```text
fast physical models / candidates
        ↓
verified experimental evidence
        ↓
experimental memory
        ↓
physics intelligence, only if it improves prospective decisions
        ↓
reusable construction methods, only after sufficient reproduction/evidence
```

Physics intelligence means:

> **Provenance-bearing knowledge about how model-construction interventions interact with physical structure, regime, measurement, and engineering context, demonstrated by improved prospective scientific or engineering decisions.**

A graph, card lake, ontology, or embedding does not earn this label merely by existing.

---

## 11. Product end state

The subnet winner is a **candidate**, not a product.

> **Rank nominates. Evidence qualifies.**

The strongest engineering product may eventually be:

- one qualified fast physical model;
- a hybrid mechanistic/learned artifact;
- a portfolio of specialists;
- a router that selects among fast models;
- a system that escalates unsupported cases to a higher-fidelity solver, experiment, or engineering review.

Component qualification does not automatically compose into system qualification.

---

## 12. Bittensor's role

Do not describe Bittensor as the source of scientific truth.

Use:

> **Bittensor supplies the open market of optimizers. Carbon supplies the scientific objective and independent judge.**

Or:

```text
Carbon:     what counts as better?
Bittensor:  who can find it?
```

Bittensor provides persistent economic search pressure. Carbon's registered scientific contracts and independent evidence define scientific outcomes.

---

## 13. Communication ladder

### One sentence

> **Carbon pays people and agents to find better ways to build fast physics models, then independently tests what survives.**

### Thirty seconds

> Engineering simulation is powerful but often too expensive for thousands of design iterations, control loops, or autonomous engineering. Fast models can help, but accuracy alone does not tell you whether they survive the physics. Carbon defines a scientific modeling problem and lets people and agents compete over better ways to build the fast model. The producer does not own the exam: validators independently execute the registered method and test the resulting candidate on protected physics and stress cases. The strongest methods earn rewards, every authoritative experiment creates evidence, and only selected artifacts enter a harder qualification path for engineering use.

### Stage formulation

> **Give Carbon a physics problem. We define what a fast model has to do and how it will be tested. People and agents compete to find a better way to build it. Validators run an exam the producer doesn't control. Fail mandatory physics, score zero. Every valid experiment teaches us what worked and where it failed. The strongest methods get a shot at becoming qualified engineering products.**

### If asked whether Carbon is a neural-operator subnet

> **We start with neural operators because we are proving the scientific judge before widening the search space. Carbon's long-term scientific contract is model-family neutral.**

---

## 14. Language rules

Prefer:

- fast physical model;
- defined physical modeling problem;
- registered scientific contract;
- protected independent exam/evaluation;
- independent retraining for P0;
- producer-independent reconstruction as a proposed/general principle;
- bounded envelope / context of use;
- evidence-backed or independently tested;
- physics intelligence only when prospective decision lift is demonstrated;
- rank nominates; evidence qualifies.

Avoid or qualify:

- "physics is a deterministic objective";
- "trustless physics truth";
- "models engineers can trust" without scope;
- "Carbon automatically deconstructs any physical system";
- "Carbon is model agnostic" without saying P0 is still neural-focused;
- "reconstruction is implemented" before S11 is accepted/implemented;
- "every run makes the next one better" as an automatic claim;
- "Landscape is causal";
- "the winner is qualified";
- "symbolic structure proves physics."

---

## 15. Authority and implementation boundary

This document reconciles identity and roadmap. It does not convert preliminary design discoveries into runtime authority.

Until tech/science-lead review is complete:

- S1–S18 remain provisional decisions;
- `SPEC.md`, `Scoring.md`, `Miner_MCP.md`, `Build_Out.md`, and other domain owners remain normative for current implementation;
- P0 remains bounded neural-operator strategy search;
- fresh retraining remains the current execution path;
- arbitrary construction-program submission remains out of scope.

If S-items are accepted, they should be converted into targeted normative spec changes and implementation tickets rather than treated as implicitly implemented because this narrative document exists.
