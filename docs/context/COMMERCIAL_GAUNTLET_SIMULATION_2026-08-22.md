# Carbon Commercial Gauntlet Simulation — 2026-08-22

**Status:** OWNER/ARCHITECT commercial design gauntlet for team review.  
**Purpose:** Test whether Carbon's current scientific, product, security, economic, and operational architecture can answer the full range of commercially plausible customer asks without overclaiming, silently changing authority, or forcing every engagement into one product shape.

---

# 1. Executive conclusion

Carbon's scientific architecture is broad enough to support a coherent commercial system, but the commercial interface is not yet fully specified.

The strongest conclusion is:

> **Carbon should not sell one product. It should expose a small set of engagement modes built on one common evidence architecture.**

Recommended commercial modes:

1. **Discovery Challenge** — find better model-construction approaches.
2. **Independent Evidence Program** — independently evaluate an existing model or method.
3. **Model Development Program** — discover, reconstruct, and deliver a strong candidate.
4. **Product Qualification Program** — assess one exact artifact/system for one bounded job.
5. **Lifecycle / Physics-Intelligence Program** — use accumulated evidence to improve future search, monitoring, experiment allocation, requalification, and escalation.
6. **Sponsored Frontier Bounty** — fund a defined scientific frontier and pay only for independently verified advancement.

The current architecture supports the **scientific logic** of all six. The largest commercial gaps are not fundamental scientific gaps; they are interface/governance gaps around privacy, IP, customer truth access, deliverable identity, deployment integration, commercial contracts, and private/auditor disclosure.

---

# 2. Gauntlet method

We simulated requests from:

- CAE / solver vendors;
- aerospace and automotive OEMs;
- energy / turbomachinery / industrial operators;
- digital-twin / controls teams;
- internal SciML teams;
- engineering-software platforms;
- government / defense labs;
- autonomous engineering companies;
- academic/research groups;
- public or private scientific sponsors;
- procurement, security, legal, V&V, engineering, data/IP, and finance stakeholders.

Every request was classified:

```text
SUPPORTED BY CURRENT ARCHITECTURE
SUPPORTED IN PRINCIPLE, IMPLEMENTATION NEEDED
REQUIRES A DEFINED EXTENSION
OUTSIDE CARBON'S INTENDED ROLE
```

The gauntlet deliberately treats a precise "not yet" or "outside scope" as a stronger result than a false universal "yes".

---

# 3. Demand-side task gauntlet

## 3.1 "Build us a fast surrogate for this expensive solver"

**Disposition:** SUPPORTED IN PRINCIPLE, IMPLEMENTATION NEEDED.

Carbon path:

```text
customer job
-> CandidateOutputContract
-> target population / operating envelope
-> truth access policy to customer solver
-> qualified Challenge
-> competitive construction search
-> independent evidence
-> candidate
-> optional Product Qualification Program
```

Required additions:
- private truth-access adapter;
- commercial Challenge authoring workflow;
- customer disclosure tier;
- deliverable/IP terms.

No architecture rewrite required.

## 3.2 "We already have a surrogate. Test it independently."

**Disposition:** SUPPORTED BY CURRENT ARCHITECTURE.

Carbon does not need discovery to provide value. A customer-provided artifact can be treated as a candidate and independently examined under a qualified Challenge or Product Qualification Pack.

Commercial product mode: **Independent Evidence Program**.

Important rule:

> **Carbon's value is not contingent on Carbon having trained the model.**

## 3.3 "Compare FNO, DeepONet, ROM, symbolic, hybrid, and classical approaches"

**Disposition:** SUPPORTED BY LONG-TERM ARCHITECTURE; REQUIRES MODEL-FAMILY IMPLEMENTATION.

The scientific architecture already standardizes task/output/evidence rather than model ideology. Practical support requires qualified reconstruction/materialization paths per family.

No family receives score privilege by label.

## 3.4 "Find a better training method for our existing neural architecture"

**Disposition:** DIRECTLY ALIGNED WITH P0.

This is the narrowest commercial translation of the initial subnet.

## 3.5 "Reduce inference latency while keeping credibility"

**Disposition:** SUPPORTED WITH EXPLICIT TASK/OBJECTIVE DESIGN.

Latency/resource objectives must remain distinct from scientific admissibility. A Challenge may include compute constraints or soft resource objectives if prospectively registered.

Product qualification must bind the deployment hardware/runtime.

## 3.6 "Find where our model fails"

**Disposition:** SUPPORTED.

Possible outputs:
- failure atlas;
- stratum-specific performance;
- answerability boundary;
- robustness evidence;
- recommended higher-fidelity escalation regions.

Do not convert discovered failures into retroactive score-rule changes for the same live Challenge.

## 3.7 "Build a model for inverse design / optimization"

**Disposition:** SUPPORTED IN PRINCIPLE; JOB-SHAPED QUALIFICATION REQUIRED.

The optimizer itself changes the risk because it may exploit surrogate error. Qualification should include task-specific optimization/decision tests and truth escalation.

## 3.8 "Build a millisecond plant/control/digital-twin model"

**Disposition:** SUPPORTED IN PRINCIPLE.

Requires prospective answerability, latency, rollout/stability, deployment-environment, escalation, and drift semantics.

A continuously responding model is not automatically preferable to a system that abstains or escalates when evidence is weak.

## 3.9 "Handle changing geometry / mesh / CAD"

**Disposition:** ARCHITECTURALLY SUPPORTED; ADAPTER LAYER NEEDED.

Required commercial abstraction: `CustomerRepresentationAdapter` / representation qualification.

Geometry is part of the task population, not merely a file format problem.

## 3.10 "Use our proprietary simulation data but never expose it to miners"

**Disposition:** REQUIRES PRIVATE CHALLENGE ARCHITECTURE.

The existing disclosure constitution supports this direction, but production design needs explicit private truth/data execution modes.

Possible modes:
- customer-hosted truth service;
- Carbon-hosted sealed/private evaluator;
- air-gapped customer deployment;
- privacy-preserving precomputed evidence packs where scientifically valid;
- sponsor-only auditor disclosure.

This is a major commercial implementation priority.

## 3.11 "We cannot give you the solver; only historical simulation results"

**Disposition:** POSSIBLE WITH CLAIM LIMITATIONS.

Carbon can define a dataset-backed Challenge if the dataset and selection process support the intended population/claim.

It must not pretend a finite historical dataset automatically represents future operation.

Validation Dossier must address selection, missingness, coverage, population shift, and reuse/holdout contamination.

## 3.12 "We have sparse experiments plus simulation"

**Disposition:** SUPPORTED BY MULTI-FIDELITY ARCHITECTURE; IMPLEMENTATION NEEDED.

Truth hierarchy and fidelity-allocation policy must be authored explicitly. Experimental and numerical evidence remain typed rather than silently merged.

## 3.13 "Tell us what experiment or simulation to run next"

**Disposition:** FUTURE PHYSICS-INTELLIGENCE MODE.

This crosses from evidence storage into prospective experiment allocation. Carbon should claim this only after measured prospective decision lift.

## 3.14 "Validate our model for safety-critical production"

**Disposition:** PARTIALLY SUPPORTED; DO NOT OVERCLAIM.

Carbon can provide bounded evidence and qualification under a stated context of use. It cannot unilaterally provide universal safety certification or replace customer/regulatory engineering authority.

Correct commercial language:

> Carbon can produce an evidence-bounded qualification record for a defined job; the customer's governing engineering/regulatory process determines whether and how that evidence may be relied upon.

## 3.15 "Monitor model drift after deployment"

**Disposition:** REQUIRES LIFECYCLE EXTENSION.

Architecture already supports append-only qualification lifecycle and requalification triggers. Needed implementation:
- deployment telemetry contract;
- drift measurements;
- requalification policy;
- incident/escalation workflow.

## 3.16 "Build us a router across several specialists"

**Disposition:** SUPPORTED BY LONG-TERM PRODUCT ONTOLOGY.

Requires system-level qualification. Component qualification does not automatically compose.

## 3.17 "Run a scientific prize/bounty for a hard modeling problem"

**Disposition:** STRONGLY SUPPORTED.

This maps cleanly to a sponsored Challenge / Frontier Bounty, with sponsor funds separate from base subnet performance reward if needed.

The sponsor may define the problem and economics, but scientific contract changes remain prospective and independently governed.

---

# 4. Deliverable gauntlet

Customers may want different outputs from the same underlying engagement.

## 4.1 Deliverables Carbon can coherently support

| Deliverable | Architectural status | Notes |
|---|---|---|
| Ranked method comparison | Supported | Challenge-bound, not universal |
| Independent evaluation report | Supported | Must bind exact exam identity |
| Failure / robustness atlas | Supported | Disclosure controlled |
| Model Card / provenance record | Supported | Audience-specific projection |
| Validation Dossier | Supported | Qualifies exam, not product |
| Reproducible construction recipe | Supported for permitted families | IP/disclosure terms needed |
| Trained candidate model | Supported in product path | Winner is candidate, not automatically product |
| Product Battery Record | Supported architecture | Exact job-shaped qualification attempt |
| Qualification Record | Supported architecture | Bounded context-of-use claim |
| ONNX / executable/container | Supported conceptually | Artifact + runtime identity required |
| API/service | Requires product/runtime implementation | Still qualification-bound |
| Air-gapped package | Requires deployment implementation | High commercial priority for sensitive customers |
| Portfolio/router | Supported long term | Requires system qualification |
| Escalation policy | Supported architecture | Must bind truth source/fallback |
| Ongoing monitoring/requalification | Requires lifecycle implementation | Architecture supports it |
| Construction Method Library access | Future | Reproduction/evidence gates required |
| Physics-intelligence brief | Future | Must demonstrate prospective value |
| Public leaderboard | Supported for public Challenges | Not required for private engagement |
| Private sponsor dashboard | Requires commercial interface | Strongly recommended |

---

# 5. Customer stakeholder gauntlet

## 5.1 Chief engineer / technical authority

Likely asks:
- What exact job is this model qualified for?
- What evidence says it works?
- What are the known failure regimes?
- What is the truth source?
- What happens outside the evidence envelope?
- Can I reproduce the evidence?
- Does the optimizer exploit it?

**Carbon response readiness:** STRONG ARCHITECTURE.

Best artifacts:
- Challenge identity;
- Validation Dossier;
- ExperimentRecords;
- Product Battery Record;
- Qualification Record;
- limitations / answerability / escalation.

## 5.2 V&V / modeling-and-simulation reviewer

Likely asks:
- Was the generator verified?
- What is the target population?
- What is the finite sampling plan?
- What is the numerical uncertainty?
- Are measurements independently qualified?
- How are versions/configurations controlled?

**Carbon response readiness:** STRONG, because the new Challenge/Dossier/Score Pack architecture was built for this.

## 5.3 Security officer

Likely asks:
- Who can see our data/solver/geometry?
- Can the work run on-prem or air-gapped?
- Can miners exfiltrate data?
- Are validators trusted?
- What is logged?
- How are credentials and private truth sources isolated?

**Carbon response readiness:** ARCHITECTURAL PRINCIPLES GOOD; COMMERCIAL IMPLEMENTATION GAP MATERIAL.

Stop-ship for sensitive engagements until private execution architecture is explicitly specified and tested.

## 5.4 Data / IP counsel

Likely asks:
- Who owns customer data?
- Who owns miner strategy IP?
- Who owns the trained artifact?
- Can a winning construction method be reused on another customer?
- What is public by default?
- Can the sponsor demand exclusivity?

**Carbon response readiness:** INCOMPLETE.

This is one of the largest nontechnical gaps.

Need explicit `CommercialRightsPolicy` and engagement-level IP profiles.

## 5.5 Procurement / finance

Likely asks:
- What do we buy?
- Fixed price, bounty, subscription, success fee, compute pass-through?
- What happens if nobody wins?
- Can spend be capped?
- Are miner rewards separate from Carbon fees?

**Carbon response readiness:** ECONOMIC ARCHITECTURE PARTIAL.

Need customer-facing economic modes separated from subnet treasury economics.

## 5.6 CTO / platform owner

Likely asks:
- Can this integrate with our solver/CAE stack?
- REST? Python? C++? ONNX? FMU?
- Where does it run?
- What are latency/SLA/observability requirements?

**Carbon response readiness:** REQUIRES integration/product runtime taxonomy.

## 5.7 Legal / risk / regulator-facing team

Likely asks:
- Is this a certification?
- Who is liable?
- Can we use it in regulated/safety-critical decisions?
- What standards does this comply with?

**Carbon response:** must remain bounded.

Carbon can provide evidence and crosswalks. It must not represent its Qualification Record as universal regulatory approval.

---

# 6. Customer archetype simulations

## A. Proprietary CFD vendor

**Ask:** "Discover a surrogate construction method for our solver, but neither solver nor training data may be public."

**Carbon can deliver:** private Discovery Challenge + customer-controlled truth service + independent evidence + candidate model.

**Current blockers:** private Challenge execution, rights policy, customer-hosted truth adapter, private miner disclosure model.

**Architecture verdict:** PASS WITH IMPLEMENTATION GAP.

## B. Aerospace OEM

**Ask:** "Fast aerodynamic model for geometry/AoA/Mach design optimization; evidence must survive chief-engineer review."

**Carbon path:** author geometry/workload population -> qualified truth hierarchy -> discovery -> optimizer-shaped Product Battery -> bounded Qualification Record + escalation.

**Blockers:** geometry adapters, expensive truth budget, private challenge, job-shaped Product Battery.

**Architecture verdict:** PASS.

## C. Industrial digital twin

**Ask:** "Millisecond prediction, continuous operation, confidence about when not to answer."

**Carbon path:** task includes latency + answerability -> candidate/router -> qualification includes rollout, coverage, escalation -> lifecycle monitoring.

**Blockers:** runtime product stack, deployment telemetry, lifecycle automation.

**Architecture verdict:** PASS WITH PRODUCT IMPLEMENTATION GAP.

## D. Existing SciML team

**Ask:** "Independent adversarial evaluation of our existing neural operator."

**Carbon path:** no discovery required; treat supplied artifact/method as candidate under a qualified exam.

**Architecture verdict:** STRONG PASS. This should be an early commercial offering because it needs the least new economic machinery.

## E. Government / defense laboratory

**Ask:** "Air-gapped, no public data, full auditability, reproducible evidence."

**Carbon path:** private/offline Challenge deployment; signed evidence chain; local controlled participant/evaluator set; customer-held truth; product evidence package.

**Blockers:** air-gapped deployment spec, key/governance model, private participant economics.

**Architecture verdict:** POSSIBLE, NOT YET PRODUCTIZED.

## F. Engineering software platform

**Ask:** "Use Carbon behind our existing CAE UI as discovery/evidence infrastructure."

**Carbon path:** API-first Challenge authoring/evidence services; external platform remains workflow/UI owner.

**Architecture verdict:** STRONG STRATEGIC FIT.

This validates the "Discovery + Evidence for Physics AI" positioning.

## G. Autonomous engineering company

**Ask:** "Our agents will exploit every surrogate error. Give us safe acceleration."

**Carbon path:** qualification of model + router + truth escalation; optimizer-specific adversarial battery; answerability is a first-class product semantic.

**Architecture verdict:** STRONG FIT, technically demanding.

## H. Public research sponsor

**Ask:** "We want the community to move a scientific frontier and only pay for genuine progress."

**Carbon path:** sponsored Challenge / Frontier Bounty + qualified baseline + frontier promotion + sponsor-funded settlement.

**Architecture verdict:** VERY STRONG FIT.

---

# 7. Commercial product architecture emerging from the gauntlet

## Mode 1 — Discovery Challenge

Customer question:

> What should we try?

Inputs:
- defined physical problem;
- candidate I/O;
- operating envelope;
- target population;
- truth path;
- privacy/IP profile;
- budget.

Outputs:
- ranked independent evidence;
- frontier event(s);
- candidate method(s);
- failure evidence.

## Mode 2 — Independent Evidence Program

Customer question:

> Does our existing candidate survive a defensible independent exam?

Inputs:
- customer candidate or construction method;
- defined use/task;
- evidence requirements.

Outputs:
- independent evaluation;
- evidence package;
- failure/limitation map;
- recommendation for qualification or redesign.

## Mode 3 — Model Development Program

Customer question:

> Can Carbon discover and deliver the best candidate it can find for this problem?

Includes Discovery + selected controlled reconstruction + delivery packaging.

A delivered candidate still does not automatically carry a product qualification claim.

## Mode 4 — Product Qualification Program

Customer question:

> Can this exact artifact/system support this exact job?

Outputs:
- product-candidate identity;
- Product Battery Record;
- Qualification Record;
- limitations;
- answerability/escalation;
- requalification triggers.

## Mode 5 — Lifecycle / Physics Intelligence

Customer question:

> What should we test, retrain, avoid, or requalify next?

Only claimable when prospective decision lift is demonstrated.

## Mode 6 — Sponsored Frontier Bounty

Customer question:

> Can we put capital behind a difficult, measurable research frontier?

Sponsor funds are separate from Carbon's base subnet performance entitlement unless explicitly combined under a registered policy.

---

# 8. New commercial abstractions required

The gauntlet identifies the following missing or under-specified abstractions.

## C1 — CommercialEngagementSpec

Binds:
- customer/sponsor;
- engagement mode;
- Challenge(s);
- privacy classification;
- data/truth access mode;
- deliverables;
- rights/IP policy;
- commercial payment policy;
- publication policy;
- qualification target;
- acceptance and termination conditions.

## C2 — TruthAccessMode

Recommended enum family:

```text
CARBON_OPERATED_REFERENCE
CUSTOMER_HOSTED_SOLVER_SERVICE
CUSTOMER_PRECOMPUTED_DATASET
THIRD_PARTY_REFERENCE_SERVICE
EXPERIMENTAL_DATA_SOURCE
HYBRID_MULTI_FIDELITY
AIR_GAPPED_CUSTOMER_TRUTH
```

Scientific adequacy still comes from the Validation Dossier.

## C3 — CommercialRightsPolicy

Must distinguish rights to:
- customer source data;
- customer solver access;
- Challenge semantics;
- miner-submitted strategy;
- generalized construction method;
- reconstructed/trained artifact;
- experiment records;
- derived Landscape knowledge;
- publication/benchmarking;
- exclusivity and reuse.

## C4 — DeliverableContract

Defines exactly what customer receives:

```text
artifact(s)
source/weights/recipe rights
deployment representation
runtime environment
Model Card / ExperimentRecord package
Validation/Qualification artifacts
support/SLA
update/requalification terms
```

## C5 — CustomerDisclosurePolicy

At least:

```text
PUBLIC
MINER
SPONSOR
CUSTOMER_DILIGENCE
INDEPENDENT_AUDITOR
CARBON_PRIVATE
```

Transparency does not require universal disclosure.

## C6 — Representation / Integration Adapter registry

Future practical adapters may cover:
- arrays/grids;
- unstructured meshes;
- point clouds;
- graphs;
- CAD/geometry parameters;
- time series;
- sensor/telemetry inputs;
- field and QoI outputs;
- ONNX;
- container/API;
- Python/C++/FMU or customer-specific runtime interfaces.

An adapter must not silently change physical semantics.

## C7 — CustomerAcceptancePlan

Customer commercial acceptance is not identical to Carbon scientific qualification.

May bind:
- delivery acceptance;
- latency/runtime tests;
- integration tests;
- customer V&V handoff;
- security review;
- procurement/legal milestones.

---

# 9. Commercial stop-ship conditions

Do not sell an engagement as supported if:

1. the customer asks for a claim outside a qualifiable context of use;
2. required customer data/solver confidentiality cannot be technically enforced;
3. candidate I/O omits a causal variable required to define the task;
4. the truth path cannot support the claimed scientific resolution;
5. the customer expects a leaderboard win to equal production certification;
6. rights to data, methods, artifact, or derived knowledge are ambiguous;
7. a private Challenge would leak protected customer information to miners/publicly;
8. Carbon cannot identify what exact deliverable the customer will receive;
9. deployment/runtime changes would invalidate qualification but no requalification path exists;
10. the customer requires a regulatory/safety claim Carbon cannot legitimately make;
11. treasury/subnet economics are presented as equivalent to customer commercial payment terms;
12. commercial pressure would require changing scientific rules after observing candidate outcomes.

---

# 10. Deal-killer questions Carbon must be able to answer

Before a serious pilot, Carbon should have written answers to:

- What exactly is the physical job?
- What exactly is the candidate allowed to see?
- What is the target operating population?
- Who defines and qualifies the truth?
- Who sees customer data?
- Who can see miner methods?
- Where does customer IP go?
- What does the customer receive?
- Who owns the delivered artifact?
- Can Carbon reuse the winning method?
- Can the customer demand exclusivity?
- What is public?
- What remains private?
- What happens if no candidate improves the baseline?
- What happens if the exam is later found defective?
- What happens if the model fails after delivery?
- What does Carbon's qualification mean and not mean?
- Can the system abstain/escalate?
- What triggers requalification?
- How is customer spend bounded?
- How are miner/network rewards funded?
- What happens during treasury/chain failure?
- Can the work run customer-side or air-gapped?
- What external solver/tool integrations are needed?
- Can a skeptical third party reproduce the evidence without seeing protected answer keys?

---

# 11. Earliest credible commercial offers

The gauntlet suggests a maturity ordering.

## Earliest / lowest new architecture burden

1. **Independent Evidence Program for an existing model**
2. **Sponsored academic/engineering Discovery Challenge with non-sensitive truth**
3. **Private Discovery Challenge using customer-controlled truth service**

## Next

4. **Controlled model-development + delivery**
5. **Job-shaped Product Qualification Program**
6. **Private/air-gapped qualification**

## Later

7. **Continuous lifecycle monitoring**
8. **Prospective physics-intelligence / experiment allocation**
9. **Broad mixed-family / open-construction industrial discovery**

This sequencing fits the broader roadmap doctrine: prove the judge, then increase commercial realism without simultaneously maximizing physics depth and construction freedom.

---

# 12. Final gauntlet verdict

### Scientific/customer-value architecture
**PASS**

Carbon can coherently handle discovery, independent evidence, model development, qualification, and later lifecycle intelligence through one evidence architecture.

### Private industrial engagement architecture
**PASS IN PRINCIPLE / IMPLEMENTATION GAP**

Privacy and disclosure principles exist, but private Challenge, customer-hosted truth, air-gap, and sponsor-only evidence pathways need explicit design and testing.

### IP / rights architecture
**MATERIAL GAP**

This is the largest commercial-design gap exposed by the gauntlet.

### Deliverable architecture
**PARTIAL GAP**

Product qualification objects exist, but a customer-facing DeliverableContract is still needed.

### Integration architecture
**PARTIAL GAP**

Representation neutrality exists scientifically; practical CAE/mesh/CAD/runtime adapter taxonomy is not yet mature.

### Customer economics
**PARTIAL GAP**

Subnet performance reward is now coherent. Customer pricing/sponsor economics must remain a separate commercial contract layer.

### Commercial claim discipline
**STRONG**

Carbon's architecture already supports bounded claims, separate product qualification, evidence lineage, and explicit non-claims.

---

# 13. Core commercial principle learned

> **Carbon should be able to say yes to many shapes of physical-model discovery and evidence work without saying yes to claims the evidence cannot support.**

And the strongest commercial positioning remains:

> **Carbon is the discovery and evidence layer for fast physical models: define the job, qualify the exam, open the search, independently determine what survives, and deepen evidence only as the intended use demands.**
