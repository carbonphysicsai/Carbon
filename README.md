<img width="1412" height="62" alt="image" src="https://github.com/user-attachments/assets/1d63753c-a391-44d9-a4b8-ee667545bcae" />

# Carbon

**Discovery + evidence for Physics AI**

Carbon pays people and agents to find better ways to build fast physics models, then independently tests what survives.

**P0 starts narrower:** neural-operator training strategies, validator-controlled fresh retraining, and protected physics / robustness / accuracy evaluation. The long-term architecture is broader; the launch implementation is deliberately not.

---

## The problem

High-fidelity simulation is foundational to engineering, but it is often too expensive for very large design searches, real-time loops, dense uncertainty studies, or increasingly agentic engineering workflows.

Fast learned or reduced models can change the economics of repeated physical prediction. But low average error does not establish that a candidate preserves required physics, remains robust in difficult regimes, survives independent reproduction, or is adequate for the engineering job in which it will be used.

Carbon attacks that gap at the level of the research system:

> **Better optimizers amplify whatever objective you give them. Carbon makes physics-surviving performance economically consequential and keeps the producer separate from the official grade.**

---

## What Carbon is

At the system level, Carbon is an incentivized experimental system for discovering, independently testing, learning from, and qualifying methods for constructing fast physical models.

The high-level workflow is:

```text
defined physical modeling problem
        ↓
registered Challenge
(task / envelope / scientific evidence contract)
        ↓
people + agents compete over how to build the fast model
        ↓
independent execution / reconstruction
        ↓
protected physics + robustness + accuracy exam
        ↓
evidence about what worked and where it failed
        ↓
selected candidates enter harder product qualification
```

Carbon standardizes the **job and the scientific exam**, not the terminal model ideology.

Neural operators are the first model class. Longer term, the architecture is intended to support other admissible construction families — such as hybrid, reduced-order, classical, symbolic/numeric, or composed methods — only when Carbon can compare them fairly under a common registered task/output contract and preserve independent evaluation.

> **Model class is a hypothesis. Registered external evidence is the judge.**

---

## P0: prove the judge first

The current launch path remains intentionally bounded.

1. **Miners / agents** submit a neural-operator training strategy.  
2. **Validators** independently train from scratch on validator-controlled data and evaluate on protected test/stress realizations.  
3. **Mandatory physics failures are disqualifying.** A required gate failure yields zero authoritative score.  
4. **Emissions** follow the registered independent score — not self-reported metrics.  
5. **Evidence** is recorded for the evaluated method and result.  
6. **Winning the subnet is not product qualification.** Selected methods face a separate, harder product path.

Current P0 scoring mathematics, challenge binding, data separation, disclosure, and validator behavior remain governed by the normative specifications, especially [`Scoring.md`](./Design_Specs/Scoring.md), [`Miner_MCP.md`](./Design_Specs/Miner_MCP.md), [`Data_Management.md`](./Design_Specs/Data_Management.md), and [`Trustless_Verification.md`](./Design_Specs/Trustless_Verification.md).

---

## Why the producer does not own the exam

| Failure mode | Carbon response |
|---|---|
| Producer grades its own work | Independent validators run the official exam |
| Good average error, bad physics | Challenge-specific hard physical admissibility gates |
| Repeated adaptation to a public benchmark | Protected realizations + disclosure discipline + Challenge lifecycle |
| One lucky checkpoint looks strong | Current learned-model path uses fresh independent retraining |
| Leaderboard winner treated as deployable product | **Rank nominates; evidence qualifies** |
| Experimental history becomes storytelling | Physics intelligence must earn value through better prospective decisions |

The exam hides the **realization**, not the science. The physical problem, declared envelope, generator logic, scoring mathematics, versions, and appropriate validation evidence are inspectable; protected official seeds/draws remain unavailable to participants before evaluation.

---

## How discovery can deepen

Carbon's discovery space can expand in levels without changing who controls the grade:

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

P0 is bounded strategy search. Open-ended construction-algorithm discovery is a long-term research direction, not a live launch capability.

The proposed generalized `ReconstructionProtocol` is currently under tech/science-lead review. **P0 remains fresh validator-controlled neural retraining unless and until that abstraction is explicitly ratified and implemented.**

---

## Agent-friendly miner loop

Carbon's miner surface is specified in [`Design_Specs/Miner_MCP.md`](./Design_Specs/Miner_MCP.md).

**Free / practice loop**

1. `get_prior` — bounded, noisy, lagged guidance.  
2. `get_mock_scaffold` — versioned runnable practice baseline.  
3. `estimate` — non-binding screening only.  
4. `light_compare` / `light_train` — mock/practice execution only.

**Official path**

5. `submit` — protected authoritative evaluation.  
6. `get_submission_result` — budgeted result disclosure sufficient to guide research without becoming a high-bandwidth answer-key oracle.

Mock/practice metrics never enter emissions.

---

## What compounds

Every authoritative experiment can add structured evidence. That does **not** mean every run automatically makes Carbon smarter.

The intended hierarchy is:

```text
candidate fast physical models
        ↓
verified experimental evidence
        ↓
experimental memory
        ↓
physics intelligence — only if future decisions improve
        ↓
reusable construction methods — only after sufficient reproduction/evidence
```

Carbon uses **physics intelligence** to mean provenance-bearing knowledge about how model-construction interventions interact with physical structure, regime, measurement, and engineering context, demonstrated by improved prospective scientific or engineering decisions.

A card lake, graph, embedding, or ontology is not automatically physics intelligence merely because it exists.

The scientific canon also has a bounded **Agentic Exploration Zone** role: literature, Challenge semantics, permitted Landscape evidence, and registered methods may inform what agents try.

> **Canon informs hypotheses. Carbon experiments adjudicate them.**

---

## From subnet to engineering product

Discovery and qualification answer different questions.

```text
DISCOVERY
Which method survives the registered independent exam?

QUALIFICATION
Can this exact artifact or system support this exact engineering use?
```

A selected candidate is freshly constructed/retrained as required, tested more deeply against a job-shaped Product Battery, and bound to a stated context of use, known limitations, and escalation/requalification conditions.

A future qualified product may be one fast model or, where evidence supports it, a portfolio/router that chooses among models and escalates unsupported cases to higher-fidelity simulation, experiment, or engineering review.

Component qualification does not automatically imply system qualification.

---

## Commercial position

Carbon does not aim to replace high-fidelity solvers, CAE platforms, scientific-computing frameworks, or GPU vendors.

```text
PHYSICS / SIMULATION / MODELING TOOLING
        ↓
CARBON — DISCOVERY + EVIDENCE
        ↓
FAST PHYSICAL MODELS / QUALIFIED SYSTEMS
        ↓
ENGINEERING WORKFLOWS
```

The first commercial value can be **discovery** rather than a finished product:

> A partner defines a physical modeling problem, target envelope, required inputs/outputs, and truth/evidence path. Carbon runs a competitive discovery program and independently determines which construction approaches survive.

Commercial value can then deepen through independent evidence, bounded qualification, and — only if demonstrated prospectively — physics intelligence and reusable construction-method knowledge.

Typical early commercial forms remain sponsored Challenges and qualified specialists under appropriate open, licensed, or private terms.

---

## Roadmap doctrine

Carbon has three separate expansion axes:

```text
PHYSICS DEPTH
simple PDE -> harder regimes -> geometry -> coupled/multiphysics

MODEL FREEDOM
bounded neural family -> mixed construction families -> open construction research

COMMERCIAL REALISM
academic problem -> engineering-like problem -> partner Challenge -> qualified product
```

The roadmap should avoid increasing all three at once because failures become difficult to interpret.

> **First prove the judge. Then deepen the physics. Then widen the search. Bring industry in throughout.**

That means:

1. prove one complete independent exam end to end;  
2. deepen physics while keeping the construction family bounded;  
3. on a well-understood Challenge, deliberately test mixed model families through a common task/output contract;  
4. engage industry throughout and run narrowly scoped partner discovery pilots once lean evidence is credible;  
5. prove harder context-specific qualification;  
6. only later expand toward broader compositional and construction-algorithm discovery.

This strategic sequencing does **not** modify current Build-Out Waves or P0 tickets.

See [`Design_Specs/System_Identity_and_Roadmap.md`](./Design_Specs/System_Identity_and_Roadmap.md) for the reconciled architecture/communication version.

---

## Bittensor's role

Bittensor supplies the persistent open market of optimizers. Carbon defines the scientific objective and registered evaluation contract.

```text
Carbon:     what counts as better?
Bittensor:  who can find it?
```

Bittensor consensus does not determine physical truth.

---

## Current status

**Phase 0:** foundations and offline proof-of-concept — strategy → seeded data → train → physics checks → score → evaluation card (`poc/`).

The project has detailed protocol, scoring/data, generator/Validation Dossier, product qualification, Landscape, security, and build sequencing specifications. The current implementation target remains the narrow academic-PDE foundation needed to prove the lean exam before broader search freedom is introduced.

```bash
git clone https://github.com/carbonphysicsai/Carbon.git
cd Carbon
python -m pip install -e ".[dev]"
python -m pytest -q
```

The supported default is the Python 3.11 CPU development lane. Scientific and chain backends are optional and are not qualified by that test result. See [`docs/DEVELOPMENT.md`](./docs/DEVELOPMENT.md).

---

## Documentation map

| Document | Role |
|---|---|
| [Design_Specs/System_Identity_and_Roadmap.md](./Design_Specs/System_Identity_and_Roadmap.md) | **System identity, roadmap, and communication reconciliation** |
| [SPEC.md](./SPEC.md) | Current protocol architecture / P0 system specification |
| [Design_Specs/Build_Out.md](./Design_Specs/Build_Out.md) | Implementation sequencing and Phase-0 waves |
| [Design_Specs/Miner_MCP.md](./Design_Specs/Miner_MCP.md) | Miner/agent free + official interfaces |
| [Design_Specs/Scoring.md](./Design_Specs/Scoring.md) | Normative scoring mathematics |
| [Design_Specs/Generator_Creation.md](./Design_Specs/Generator_Creation.md) | Challenge generator authoring |
| [Design_Specs/Generator_Validation.md](./Design_Specs/Generator_Validation.md) | Validation Dossier / generator qualification |
| [Design_Specs/Physical_System_Representation.md](./Design_Specs/Physical_System_Representation.md) | Proposed descriptive physical-system semantics |
| [Design_Specs/Landscape_Agent.md](./Design_Specs/Landscape_Agent.md) | Evidence-learning architecture |
| [Design_Specs/Specialist_Bank.md](./Design_Specs/Specialist_Bank.md) | Separate product qualification path |
| [docs/context/SCIENTIFIC_REFERENCE_CANON_V3_MASTER.md](./docs/context/SCIENTIFIC_REFERENCE_CANON_V3_MASTER.md) | Scientific evidence / claim-control canon |
| [docs/context/REVIEW_THESE_PRELIMINARY_DECISIONS_POST_SIMULATION.md](./docs/context/REVIEW_THESE_PRELIMINARY_DECISIONS_POST_SIMULATION.md) | Tech/science-lead S1-S18 review queue |
| [docs/context/DOCUMENT_COHERENCY_AUDIT_2026-08-21.md](./docs/context/DOCUMENT_COHERENCY_AUDIT_2026-08-21.md) | Cross-document coherency audit |

---

*Carbon: define the job, open the search, keep the producer out of the official grade, and qualify only what the evidence supports.*
