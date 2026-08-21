# Gate 10 — Agentic Construction Discovery

**Status:** design-forward simulation; no P0 runtime or arbitrary-code execution changes.  
**Objective:** Test whether Carbon can eventually let miners/agents propose model-construction algorithms that Carbon developers did not preimplement, while preserving producer independence, exam secrecy, reproducibility, safety, scientific comparability, and evidence quality.

---

## 1. Why Gate 10 exists

Gates 6–9 established `ModelConstructionStrategy`, `ReconstructionProtocol`, and `FastPhysicalModel` as durable long-term abstractions. A remaining ceiling is whether `ConstructionPolicy` only permits methods Carbon developers have already implemented.

If yes, Carbon can optimize a catalog but cannot genuinely discover new construction algorithms.

Gate 10 therefore asks:

> **Can a miner/agent submit the construction procedure itself, have Carbon independently execute it, and earn reward only from the resulting protected scientific evidence?**

The target is open-ended algorithm discovery, not arbitrary code execution for its own sake.

---

## 2. Discovery hierarchy

Carbon should distinguish four levels of search:

```text
parameter search
  ↓
recipe / strategy search
  ↓
architecture / composition search
  ↓
construction-algorithm discovery
```

Examples of the final level include a new basis-building procedure, a non-gradient fitting algorithm, a new symbolic reduction, a novel domain decomposition, a new closure-construction method, or a new hybrid reconstruction pipeline.

The scientific object is the **construction intervention**, not merely the final artifact.

---

## 3. Two reconstruction modes

### Mode A — Registered ReconstructionProtocol

Carbon supplies a reviewed executor and miners submit bounded parameters/recipes.

This is the appropriate P0/P1 posture.

```text
Strategy
  -> registered reconstruction method
  -> validator-controlled fresh reconstruction
  -> protected exam
```

### Mode B — Submitted ConstructionProgram

A future Challenge may permit the miner/agent to submit an executable construction algorithm.

```text
ConstructionProgram
  -> isolated construction sandbox
  -> authorized construction inputs only
  -> candidate artifact
  -> artifact boundary / sanitization
  -> separate official evaluation environment
  -> protected exam
```

**Core invariant:** the producer proposes the construction procedure but never controls the official reconstruction environment, official exam realization, or official grade.

---

## 4. Earned object: ConstructionProgram

```text
ConstructionProgram {
  program_id
  program_version
  source/content digest
  declared construction_family
  entrypoint
  dependency_manifest
  environment/base_image_ref
  required_authorized_inputs[]
  declared_outputs[]
  randomness_contract
  resource_request
  network_policy
  filesystem_policy
  provenance
}
```

This object is a hypothesis-bearing executable procedure, not a trusted artifact.

A `ConstructionProgram` may implement a known family or propose a novel one.

---

## 5. Earned object: ConstructionReceipt

Every official execution should produce a receipt independent of miner self-report:

```text
ConstructionReceipt {
  construction_program_ref
  challenge/version refs
  authorized_input_refs
  environment identity
  dependency resolution identity
  random-seed/randomness provenance
  resource consumption
  stdout/stderr digest or controlled logs
  produced artifact digests
  termination state
  policy violations
  reconstruction equivalence/repeat evidence?
}
```

This becomes part of the ExperimentRecord provenance.

---

## 6. Sandbox architecture

The construction sandbox and evaluation environment must be separate trust domains.

### Construction sandbox may receive

- public Challenge semantics;
- authorized training/reference data or generator access permitted by ConstructionPolicy;
- public PhysicalSystemSpec where disclosure allows;
- public registered libraries/toolchains;
- declared randomness source;
- bounded compute/storage.

### Construction sandbox must not receive

- official evaluation/stress seeds;
- official realized exam tensors;
- private validator state;
- raw protected Landscape evidence;
- credentials/network access unless a future tightly governed Challenge explicitly requires it;
- persistent cross-run state outside declared artifacts.

### Evaluation environment receives

Only the sanitized/content-addressed candidate artifact plus the registered interface/runtime needed to execute it. It does not execute the miner's construction process against official exam data.

**Constitutional rule:**

> **Construction and official evaluation are separate security domains.**

This is the agentic-construction generalization of Carbon's existing mock/train/eval separation.

---

## 7. Simulation A — novel non-gradient PINN-like construction

An agent proposes a method using fixed/random features, a decomposition, and direct coefficient solving rather than conventional gradient descent.

Carbon developers did not preimplement the exact method.

### Required behavior

1. ConstructionProgram declares dependencies and authorized inputs.
2. Validator executes it in the construction sandbox.
3. Program emits a candidate satisfying CandidateOutputContract.
4. Candidate crosses artifact boundary.
5. Official evaluator runs the same protected measurements/gates as comparable candidates.
6. ExperimentRecord stores program + receipt + artifact + outcome.

### Discovery

Carbon can evaluate a novel construction algorithm without having preimplemented it **if** it can execute it safely and bind its provenance.

No special score credit is given for novelty.

---

## 8. Simulation B — new ROM/reduction method

An agent proposes a new basis selection/reduction method.

The method needs authorized high-fidelity snapshots during construction.

### Pressure point

Reference access can become a hidden source of unfair advantage or leakage.

### Decision

ConstructionPolicy must define **ConstructionInputPolicy** prospectively:

- what data/generator calls are allowed;
- fidelity/rank of truth source;
- query budget;
- whether adaptive queries are allowed;
- whether outputs are cached/shared;
- whether access cost counts toward resource admissibility.

Two candidates cannot be scientifically compared if one silently receives richer truth access.

---

## 9. Simulation C — hybrid solver + learned component

Program composes a registered physical scaffold, a new learned closure, and a solver.

### Decision

The program may only modify slots allowed by ConstructionPolicy. Fixed components remain content-addressed. ConstructionReceipt records exact assembled graph.

This preserves Gate-6/7 component identity and qualification semantics.

---

## 10. Simulation D — malicious construction program

Program attempts network exfiltration, fork bombs, GPU abuse, filesystem probing, hidden persistence, timing side channels, or output smuggling.

### Decision

Submitted-program mode requires a hardened execution substrate, not merely ordinary Docker conventions.

Conceptual controls include:

- network disabled by default;
- syscall/process restrictions;
- read-only base filesystem;
- ephemeral writable workspace;
- strict CPU/GPU/RAM/time/process quotas;
- no host credentials/devices except explicitly assigned compute;
- deterministic input mounts;
- output allow-list + size limits;
- no persistence across official runs;
- construction/evaluation separation;
- receipt/audit logging;
- dependency provenance/scanning.

Exact sandbox technology is an implementation/security decision and is not specified by this design simulation.

### Discovery

Open-ended algorithm discovery has a materially larger attack surface than JSON strategy search. It should be a later Challenge capability, never a silent widening of P0.

---

## 11. Simulation E — generator exploitation

A program reverse-engineers quirks of the public training generator and builds a lookup/interpolant that performs well locally.

### Decision

This is not unique to neural methods. Protected official realizations, stress diversity, generator versioning, anti-memorization design, and Evaluation Information Budget remain essential.

If the method genuinely generalizes under the hidden registered envelope, Carbon should not reject it merely because its construction is unconventional.

---

## 12. Simulation F — new dependency/toolchain

Agent proposes a method requiring a package not present in the standard environment.

### Options

1. reject unless dependency is pre-approved;
2. permit content-addressed dependencies from an allow-listed registry/cache;
3. permit a reviewed base image/toolchain class;
4. later allow broader reproducible builds under stronger sandboxing.

### Decision

Dependency freedom should be **tiered**, not binary. Early submitted-program Challenges should use constrained, pinned dependency environments. Novel dependencies can graduate through review rather than being fetched live during official construction.

Live internet dependency resolution is incompatible with reproducibility and a strong isolation boundary by default.

---

## 13. Simulation G — nondeterministic algorithm

Program uses stochastic search, random initialization, Monte Carlo basis selection, or evolutionary search.

### Decision

Nondeterminism is permitted only under an explicit `RandomnessContract`.

It should define:

- randomness sources;
- seed ownership;
- whether repeated reconstruction is required;
- number of repeats/aggregation where qualified;
- acceptable reconstruction dispersion if relevant.

Miner-chosen official randomness must not become a hidden cherry-picking channel.

---

## 14. Simulation H — program emits many candidates and selects one

Agent's construction algorithm trains/builds 100 artifacts and internally selects the best using authorized construction data.

### Decision

This is legitimate **if prospectively allowed and resource-accounted**. Internal model selection is part of the construction algorithm.

However:

- selection cannot query official evaluation;
- all construction truth/data access is governed;
- compute/query budget includes the internal search;
- final artifact selection procedure is captured in provenance.

### Discovery

The experimental intervention includes the **inner search policy**, not merely the final architecture.

---

## 15. Simulation I — construction program calls high-fidelity solver adaptively

An agent uses the reference solver to choose where to sample/train.

### Decision

This can be scientifically valuable and should not be prohibited categorically.

But truth access becomes an experimental resource. ConstructionInputPolicy must specify:

- allowed solver/query interface;
- query budget;
- fidelity;
- adaptive/nonadaptive access;
- cost accounting;
- disclosure/provenance.

### Discovery

Carbon can eventually optimize **how to spend high-fidelity truth**, not only how to fit a model after data already exist.

This links model construction to active learning/experimental design.

---

## 16. Simulation J — agent invents a new measurement to justify its method

A submitted construction method says it should be evaluated by a new favorable metric.

### Decision

Reject automatic coupling.

ConstructionProgram may propose a `MeasurementHypothesis`, but the method producer cannot unilaterally change its official grade. Any new MeasurementContract follows the separate scientific qualification/governance path and only affects a future registered Challenge/Score Pack after review.

**Constitutional rule:**

> **The construction-method producer cannot define the official measurement that proves its own success.**

This is a direct extension of producer != judge.

---

## 17. Method graduation lifecycle

A successful novel program should not remain forever as opaque arbitrary code.

Provisional lifecycle:

```text
NOVEL / UNREGISTERED METHOD
        ↓
sandboxed official experiments
        ↓
independent reconstruction evidence
        ↓
reproduction across runs / regimes
        ↓
method-level evidence summary
        ↓
REGISTERED CONSTRUCTION METHOD
        ↓
reusable bounded primitive for future agents
```

Registration does **not** mean universal scientific endorsement. It means Carbon has a reviewed, reproducible implementation/contract that can be reused under stated scopes.

This creates a compounding **Construction Method Library**.

---

## 18. Earned object: ConstructionMethodRecord

```text
ConstructionMethodRecord {
  method_id
  method_version
  originating_program_refs[]
  supported construction families / scopes
  registered ReconstructionProtocol
  dependency/environment identity
  evidence summary refs
  known failure regimes
  reproducibility state
  allowed Challenge scopes
  epistemic/maturity status
}
```

This is not a universal certificate of superiority. It is a reusable, evidence-bearing method identity.

---

## 19. Landscape consequences

Landscape intervention identity becomes hierarchical:

```text
construction algorithm
  ↓
inner search / data-acquisition policy
  ↓
representation / architecture
  ↓
loss/objective / fitting method
  ↓
resource/truth-access policy
```

A future Landscape can ask:

- which construction algorithms transfer across physical contexts?
- which algorithms are sensitive to smoothness/stiffness/geometry/regime?
- when does adaptive truth querying pay for itself?
- which methods fail to reconstruct reproducibly?
- which novel methods should be reproduced or registered?

But all Gate-5 causal discipline remains: selection provenance, censoring, measurement identity, and deliberate experiments are required before causal promotion.

---

## 20. Incentive consequences

Novelty itself should **not** be rewarded directly in the primary performance market.

Why:

- novelty is hard to define;
- novelty bonuses encourage complexity theater;
- scientific value is demonstrated by evidence.

A novel algorithm earns primary reward by outperforming under the registered objective.

Information-value experiments may separately fund uncertain method reproduction or ablation through Port C without contaminating the performance score.

This preserves the two-market architecture:

- performance market rewards demonstrated outcome;
- information market may fund uncertainty-reducing experiments.

---

## 21. Agentic architecture discovery as a Carbon research program

The strongest long-term agentic loop is now:

```text
CANON + LANDSCAPE + CHALLENGE SEMANTICS
                 ↓
       research agent / miner
                 ↓
 proposes construction hypothesis
                 ↓
 recipe / architecture / algorithm / truth-use policy
                 ↓
 independent sandboxed reconstruction
                 ↓
 protected scientific exam
                 ↓
 ExperimentRecord
                 ↓
 Landscape + method library
                 ↓
 next hypothesis
```

The agent can progressively move from tuning known knobs to inventing new computational methods while Carbon retains the external scientific objective.

---

## 22. New discoveries

### D-082 — Open-ended construction discovery requires executable hypothesis submissions
**Class:** EXTEND.

A future ConstructionProgram mode lets agents propose algorithms Carbon did not preimplement.

### D-083 — Construction and official evaluation must be separate security domains
**Class:** HARDEN.

Never run miner construction code against official exam state. Only sanitized/content-addressed candidate artifacts cross the boundary.

### D-084 — ConstructionInputPolicy is first-class experimental governance
**Class:** EXTEND/HARDEN.

Truth/data/generator access, query budgets and adaptivity affect comparability and must be registered.

### D-085 — Dependency/toolchain freedom should graduate in tiers
**Class:** HARDEN.

Early arbitrary-program modes use pinned/allow-listed environments; broader reproducible builds require stronger controls.

### D-086 — Randomness semantics belong to the construction method
**Class:** EXTEND/HARDEN.

Nondeterministic methods require validator-owned/declarative RandomnessContracts and family-appropriate reproducibility evidence.

### D-087 — Inner search policy is part of the intervention
**Class:** EXTEND.

A method that constructs/selects among many candidates is scientifically different from the final artifact alone.

### D-088 — High-fidelity truth access is a construction resource
**Class:** EXTEND/HARDEN.

Carbon can compare strategies for spending truth/simulation budget, but access must be governed and provenance-bearing.

### D-089 — Method producers cannot define their own official measurement
**Class:** KEEP/HARDEN.

New measurement proposals follow independent qualification/governance and can only affect future registered scoring.

### D-090 — Successful novel algorithms can graduate into an evidence-bearing Construction Method Library
**Class:** EXTEND.

Carbon can compound not only models and experimental outcomes but reusable construction methods with known scopes/failure regimes.

### D-091 — Novelty should not be a primary score term
**Class:** KEEP/HARDEN.

Reward demonstrated scientific outcome; use the information market for uncertain reproduction/ablation value.

### D-092 — Agentic discovery can extend from model search into scientific-computing algorithm discovery
**Class:** KEEP/CONFIRM.

This is the highest-level discovery opportunity surfaced by the symbolic-numeric integration.

---

## 23. Security and implementation verdict

This design is **not P0 scope**.

Current bounded JSON Strategy submission is materially safer and should remain the launch design.

A submitted ConstructionProgram capability should not ship until Carbon has:

- proven the lean subnet;
- hardened A4-style secrecy boundaries;
- a mature isolated execution substrate;
- content-addressed environment/dependency provenance;
- ConstructionPolicy and CandidateOutputContract;
- clear resource accounting;
- artifact sanitization/egress controls;
- abuse/security review;
- evidence that broader search freedom creates enough value to justify the attack surface.

---

## 24. Whitepaper consequence

Gate 10 earns a **bounded long-term agentic-discovery thesis**:

> Carbon can begin with agents searching a registered strategy space, while its architecture admits a future path toward agents proposing new model-construction algorithms themselves. The producer would still not control the official reconstruction environment, hidden exam, or measurement authority.

Do not claim arbitrary-program mining exists today.

A stronger research hypothesis can be added:

> **H26 — Open construction discovery:** Under matched scientific and resource constraints, does allowing sandboxed