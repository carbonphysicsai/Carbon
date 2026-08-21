# Carbon Document Coherency Audit — 2026-08-21

**Branch:** `design/symbolic-numeric-integration`  
**Purpose:** Audit Carbon's current repository documentation for consistency after symbolic-numeric / agentic design simulations, Canon v3, whitepaper v2, litepaper v2 design-diff work, and roadmap reconciliation.  
**Scope:** identity, P0 vs long-term ontology, authority boundaries, reconstruction language, physics intelligence, commercial framing, product qualification, roadmap sequencing, and stage-language consistency.

---

# 1. Executive judgment

The repository is **scientifically coherent at the deep-design level but narratively split across generations of documentation**.

The most mature design documents agree on the following durable thesis:

> **Carbon is an incentivized experimental system for discovering, independently testing, learning from, and qualifying methods for constructing fast physical models.**

The current implementation documents remain intentionally P0-specific:

> bounded neural-operator training-strategy search + validator-controlled fresh retraining + protected physics/robustness/accuracy evaluation.

Those two statements are compatible. The incoherency arises when P0-specific wording is used as the **company/system identity** rather than explicitly as the first implementation slice.

### Master correction

All high-level docs should distinguish:

```text
CARBON'S DURABLE IDENTITY
model-construction discovery + independent evidence

!=

CARBON P0 IMPLEMENTATION
neural-operator training strategies + fresh validator retraining
```

The long-term ontology must not silently broaden P0.

---

# 2. Sources reviewed

Primary reviewed sources include:

- `README.md`
- `SPEC.md`
- `AGENTS.md`
- `Design_Specs/Build_Out.md`
- `Design_Specs/Physical_System_Representation.md`
- `Design_Specs/Use_Cases_by_Phase.md`
- `Design_Specs/Industry_Validation.md`
- `Design_Specs/Landscape_Agent.md`
- `Design_Specs/Specialist_Bank.md`
- `docs/context/SYMBOLIC_NUMERIC_GATE_9_FINAL_SYSTEM_REVIEW.md`
- `docs/context/SYMBOLIC_NUMERIC_SIMULATION_GATE_10_AGENTIC_CONSTRUCTION_DISCOVERY.md`
- `docs/context/SCIENTIFIC_REFERENCE_CANON_V3_MASTER.md`
- `docs/context/LITEPAPER_V2_DESIGN_DIFF_ANALYSIS.md`
- `docs/context/REVIEW_THESE_PRELIMINARY_DECISIONS.md`
- `docs/context/REVIEW_THESE_PRELIMINARY_DECISIONS_POISSON.md`
- `docs/context/REVIEW_THESE_PRELIMINARY_DECISIONS_POST_SIMULATION.md`

The audit does not reinterpret current score mathematics or runtime implementation beyond what those sources support.

---

# 3. Coherency finding A — system identity

## Deep-design state

Gate 9 and Canon v3 define Carbon around **methods for constructing fast physical models**, not around one model family.

Neural operators are the first model class, not the terminal ontology.

## Older/high-level state

`README.md`, `SPEC.md`, `AGENTS.md`, `Industry_Validation.md`, and parts of `Use_Cases_by_Phase.md` still describe Carbon principally as:

- verification of physics-informed neural-operator training strategies;
- decentralized training-method discovery;
- a supplier of learned solution maps;
- a competitive independent exam specifically for training strategies.

These are accurate descriptions of P0 or early product assumptions, but are too narrow when presented as the system's durable identity.

## Disposition

**REVISE high-level identity wording; preserve P0 mechanics.**

Canonical public system language:

> **Carbon pays people and agents to find better ways to build fast physics models, then independently tests what survives.**

Canonical technical identity:

> **Carbon is an incentivized experimental system for discovering, independently testing, learning from, and qualifying methods for constructing fast physical models.**

---

# 4. Coherency finding B — what enters Carbon

The newer physical-semantics work supports a stronger abstraction than "pick a PDE benchmark and train an FNO."

Carbon's high-level input is a **defined physical modeling problem** containing, at minimum conceptually:

```text
physical-system semantics / engineering intent
+ operating envelope
+ required candidate inputs and outputs
+ truth/reference sources
+ registered scientific evidence requirements
```

This becomes a registered Challenge.

## Important guardrail

Do **not** say Carbon autonomously "deconstructs any physical system." Scientific authoring remains a governed act. `PhysicalSystemSpec` is descriptive and does not certify physics.

## Disposition

**ADD as canonical architecture/communication framing.**

---

# 5. Coherency finding C — task contract / I-O contract

Gate 6/9 introduced `CandidateOutputContract` because cross-family comparison requires a common externally observable job.

This yields a valuable simple explanation:

> **Carbon standardizes the job, not the solution.**

A Challenge defines what candidate inputs/outputs and behavior matter; future model families can compete underneath that interface.

## Disposition

**USE as long-term explanation.**  
**DO NOT claim the generalized runtime contract exists at P0.**

---

# 6. Coherency finding D — reconstruction

Current P0 docs correctly specify fresh validator-controlled retraining.

Gate 8/9 generalized the scientific invariant to producer-independent reconstruction. S11 currently proposes `ReconstructionProtocol` as a future abstraction.

The user/owner has not yet committed to implementing generalized reconstruction at P0.

## Required language discipline

Use:

> **P0 uses fresh independent retraining. Producer-independent reconstruction is the proposed general invariant under tech/science-lead review.**

Do not use:

> "All submissions already include a reconstruction protocol."

Do not redesign validators around arbitrary submitted executable rebuild logic without explicit S11/S18 ratification and security review.

## Disposition

**KEEP P0 retraining normative.**  
**KEEP ReconstructionProtocol provisional.**

---

# 7. Coherency finding E — technology neutrality

New design correctly separates `physics > loss` from model ideology.

The protocol may eventually compare neural, reduced, classical, hybrid, symbolic/numeric, or composed candidates if they satisfy the same registered task and evidence contract.

This does not mean all model families are supported at launch.

## Canonical phrasing

> **Model class is a hypothesis. Registered external evidence is the judge.**

> **Carbon starts with neural operators because it is proving the judge before widening the search space.**

## Disposition

**ADD to high-level explanation; retain explicit P0 scope.**

---

# 8. Coherency finding F — discovery ladder

Gate 10 gives a coherent hierarchy:

```text
parameters
-> recipes / strategies
-> architectures / compositions
-> construction methods
-> construction algorithms
```

This belongs in public long-term framing because it explains why Carbon can compound with research agents without changing scientific authority.

## Canonical line

> **Carbon can widen what participants are allowed to discover without changing who controls the grade.**

## Disposition

**USE in litepaper / Q&A / roadmap / selected stage material.**  
Do not imply open arbitrary-code construction is live.

---

# 9. Coherency finding G — physics intelligence

Older docs often imply that Model Cards / Landscape / a knowledge graph automatically create compounding intelligence.

Canon v3 and Gate 5 sharpened this significantly.

Canonical definition:

> **Physics intelligence is provenance-bearing knowledge about how model-construction interventions interact with physical structure, regime, measurement, and engineering context, demonstrated by improved prospective scientific or engineering decisions.**

A card lake, graph, symbolic library, or causal model is not automatically physics intelligence.

## Required claim hierarchy

```text
experiment
-> evidence
-> experimental memory
-> scientific knowledge
-> physics intelligence only if prospective decision lift is demonstrated
```

## Disposition

**HARDEN language in Landscape/commercial/public docs.**

---

# 10. Coherency finding H — Landscape authority

`Landscape_Agent.md` contains useful architecture but still uses phrases such as "causal effects" and "causal core" prominently. Its own epistemic section correctly qualifies these as observational estimates.

The later canon is stricter:

- Landscape proposes/informs;
- registered contracts decide;
- independent experiments adjudicate;
- observation is not intervention;
- structured intelligence must earn prospective value.

## Disposition

**KEEP architecture.**  
Future normative cleanup should replace casual "causal" shorthand with `causal candidate` / observational estimate language where ambiguity remains.

No immediate P0 impact.

---

# 11. Coherency finding I — product path

The strongest existing product principle remains correct:

> **Leaderboard rank != product qualification.**

New design generalizes this further:

> **Rank nominates. Evidence qualifies.**

A future product may be one artifact or a qualified portfolio/router + escalation system.

Component qualification does not automatically compose into system qualification.

## Disposition

**KEEP dual threshold. GENERALIZE product nouns over time.**

Do not force all future products to be ONNX neural checkpoints in system-level language, while preserving current Specialist Bank implementation assumptions until changed normatively.

---

# 12. Coherency finding J — commercial category

Older commercial framing centers on:

- verified neural models;
- training + verification supplier/platform;
- licensed specialists.

The broader design strengthens the category to:

> **Discovery + Evidence for Physics AI**

Potential customer value layers are now clearer:

1. discovery — what construction approach should we try?
2. evidence — which approaches survive independent testing?
3. qualification — can this exact artifact/system be used for this job?
4. physics intelligence — what should we try/test next?
5. construction-method library — which reproduced methods should be reusable?

This is not permission to pitch five products at once. It is the commercial architecture behind a simple stage story.

## Disposition

**UPDATE high-level commercial framing.**

---

# 13. Coherency finding K — engineering ecosystem position

Older stack diagrams sometimes place Carbon as `MODEL SUPPLY` or `TRAINING + VERIFICATION SUPPLIER / PLATFORM`.

The model-agnostic architecture is better represented as:

```text
PHYSICS / SIMULATION / MODELING TOOLING
        ↓
CARBON — DISCOVERY + EVIDENCE
        ↓
FAST PHYSICAL MODELS / QUALIFIED SYSTEMS
        ↓
ENGINEERING WORKFLOWS
```

Carbon should remain ecosystem-neutral and should not try to replace solvers, CAE, PhysicsNeMo, SciML, or customer workflows.

## Disposition

**UPDATE public/strategic diagrams over time.**

---

# 14. Coherency finding L — roadmap conflict

Existing `SPEC.md` / `Use_Cases_by_Phase.md` contains a detailed phase progression dominated by increasing physics complexity and named use cases. The newer design raises a second independent axis: model-family freedom.

A coherent roadmap must distinguish three axes:

```text
physics depth
model freedom
commercial realism
```

The system should avoid increasing all three at once because failures become uninterpretable.

## Reconciled roadmap doctrine

> **First prove the judge. Then deepen the physics. Then widen the search. Bring industry in throughout.**

Recommended sequence:

1. prove one end-to-end judge;
2. deepen physics with a bounded model/construction family;
3. freeze known physics and deliberately test mixed model families;
4. run partner-defined discovery Challenges once lean evidence is credible;
5. prove context-specific qualification;
6. only later expand to open construction-algorithm discovery.

Commercial interviews/pilot design run in parallel rather than waiting for Stage 3 or Stage 5.

## Disposition

**ADD as strategic roadmap overlay.**  
Do not silently rewrite Build-Out Waves A–D or current Phase-0 tickets.

---

# 15. Coherency finding M — Bittensor role

Older docs sometimes rely on phrases such as "physics is deterministic" or imply Bittensor provides trust/verification directly.

Canonical division:

> **Bittensor supplies persistent economic selection pressure. Carbon supplies the scientific objective and independent evaluation.**

Bittensor consensus does not determine physical truth.

## Disposition

**STANDARDIZE in public docs.**

---

# 16. Coherency finding N — absolute trust language

Retire/qualify:

- "models engineers can trust";
- "trustless truth";
- "physics is a deterministic objective";
- "fully auditable and verified against real physics" where no exact evidence scope is given;
- "every run makes the next one better" as automatic compounding.

Prefer:

- independently tested;
- evidence-bounded;
- qualified for a stated context;
- protected scientific exam;
- mandatory physical failure is disqualifying;
- every authoritative experiment can add evidence;
- compounding must be demonstrated through better future decisions.

---

# 17. Document-by-document disposition

| Document | Current state | Action |
|---|---|---|
| `README.md` | P0-correct but company identity too neural/training-centric | **EDIT NOW** |
| `SPEC.md` | Strong P0 protocol; top-level identity narrower than later ontology | **KEEP P0 NORMATIVE; add/consume reconciliation after S-review** |
| `AGENTS.md` | Engineering rules excellent; opening mission neural-specific | **LOW-RISK FUTURE EDIT** after accepted system wording |
| `Build_Out.md` | Correct sequencing authority; P0 intentionally narrow | **NO SCOPE BROADENING** |
| `Physical_System_Representation.md` | Coherent and carefully scoped | **KEEP** |
| `Use_Cases_by_Phase.md` | Valuable examples; assumes every phase ships learned solution map | **REFRAME as current learned-model track / examples, not terminal ontology** |
| `Industry_Validation.md` | Strong verification evidence; training-strategy lane too narrow | **REFRAME commercial spine** |
| `Landscape_Agent.md` | Architecture useful; causality language needs continued discipline | **HARDEN LATER** |
| `Specialist_Bank.md` | Dual threshold strong; neural/ONNX artifact assumptions are current product implementation | **KEEP CURRENT, GENERALIZE ONLY WHEN PRODUCT SPEC CHANGES** |
| Gate 9 / Gate 10 | Coherent design discovery | **KEEP** |
| Canon v3 | Current scientific framing authority | **KEEP** |
| Litepaper v2 design diff | Coherent public integration plan | **KEEP** |
| Post-simulation review S1–S18 | Correct tech-lead ratification queue | **KEEP; S11 especially unresolved for implementation timing** |

---

# 18. Immediate repository actions from this audit

This audit establishes the following actions on the design branch:

1. Add `Design_Specs/System_Identity_and_Roadmap.md` as the canonical architecture/communication reconciliation.
2. Update `README.md` so top-level visitors see the durable identity and explicit P0 implementation slice.
3. Preserve `SPEC.md` / `Build_Out.md` as current P0 normative owners; do not let narrative reconciliation silently alter code contracts.
4. Treat `Use_Cases_by_Phase.md` as a learned-model/product track rather than proof that every future Carbon product is a neural solution map.
5. Treat `Industry_Validation.md` as support for discovery + independent evidence, not only training-strategy verification.
6. Keep generalized `ReconstructionProtocol` provisional until tech/science-lead decision S11.
7. After S1–S18 review, convert accepted items into targeted normative diffs rather than mass rewriting implementation docs.

---

# 19. Canonical explanation to practice

For the next few weeks, the team should rehearse one stable hierarchy.

### One sentence

> **Carbon pays people and agents to find better ways to build fast physics models, then independently tests what survives.**

### Mechanism

> **We define the physical modeling job and the exam. Participants compete over how to build the fast model. The producer does not control the official grade.**

### P0 clarification

> **We start with neural-operator training strategies and fresh validator retraining because we are proving the judge before widening the search space.**

### Long-term differentiation

> **Carbon can widen discovery from training recipes to architectures, model compositions, and eventually new construction algorithms without giving the producer control of the exam.**

### Commercial value

> **Carbon is the discovery + evidence layer: find better fast-model construction methods, independently determine what survives, and qualify only the exact artifacts/systems whose evidence supports a bounded engineering claim.**

---

# 20. Bottom line

The simulation work did not invalidate the original Carbon architecture. It revealed that the original architecture was a **specific implementation of a more durable scientific pattern**.

That pattern is now coherent:

```text
defined physical modeling problem
        ↓
registered task + scientific evidence contract
        ↓
competitive model-construction search
        ↓
producer-independent execution/reconstruction
        ↓
protected independent evaluation
        ↓
evidence
        ↓
learning / targeted experiments
        ↓
bounded qualification
```

The near-term engineering rule remains unchanged:

> **Keep P0 narrow. Prove the judge.**

The strategic rule is now clearer:

> **Do not mistake the first model family for the company.**
