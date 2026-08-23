# Carbon Customer Request and Deliverable Taxonomy v1

**Status:** OWNER-RECOMMENDED commercial taxonomy for team review.  
**Purpose:** Give sales, product, scientific authoring, engineering, and partner teams one common language for what customers may ask Carbon to do, what they may want delivered, and what level of support exists.

---

# 1. Support-state vocabulary

Every request should be labeled one of:

```text
SUPPORTED_NOW_OR_NEAR_P0
SUPPORTED_BY_ARCHITECTURE_NOT_YET_PRODUCTIZED
REQUIRES_DEFINED_EXTENSION
OUTSIDE_INTENDED_ROLE
```

Do not use "supported" when the architecture exists but the implementation/security/evidence path has not been qualified.

---

# 2. Request families

| Request family | Example ask | Carbon mode | Status | Main dependency |
|---|---|---|---|---|
| Training-method discovery | "Find a better recipe for our neural operator" | Discovery Challenge | SUPPORTED_NOW_OR_NEAR_P0 | qualified Challenge |
| Existing-model evaluation | "Independently test our model" | Independent Evidence | SUPPORTED_BY_ARCHITECTURE_NOT_YET_PRODUCTIZED | customer candidate ingest |
| Model-family bakeoff | "Compare neural vs ROM vs hybrid" | Discovery Challenge | SUPPORTED_BY_ARCHITECTURE_NOT_YET_PRODUCTIZED | reconstruction adapters |
| Surrogate creation | "Build a fast replacement for our solver" | Model Development | SUPPORTED_BY_ARCHITECTURE_NOT_YET_PRODUCTIZED | truth access + delivery |
| Failure analysis | "Where does our model break?" | Independent Evidence | SUPPORTED_BY_ARCHITECTURE_NOT_YET_PRODUCTIZED | stress/population design |
| Robustness improvement | "Fix rare-regime failures" | Discovery Challenge | SUPPORTED_BY_ARCHITECTURE_NOT_YET_PRODUCTIZED | registered stress semantics |
| Latency optimization | "Make it 10x faster" | Discovery / Development | SUPPORTED_BY_ARCHITECTURE_NOT_YET_PRODUCTIZED | compute objective + runtime |
| Inverse-design surrogate | "Accelerate design optimization" | Development + Qualification | SUPPORTED_BY_ARCHITECTURE_NOT_YET_PRODUCTIZED | optimizer-shaped battery |
| Digital twin / control | "Real-time model with fallback" | Development + Qualification | SUPPORTED_BY_ARCHITECTURE_NOT_YET_PRODUCTIZED | rollout/answerability/lifecycle |
| Geometry generalization | "Handle new CAD/meshes" | Discovery / Development | REQUIRES_DEFINED_EXTENSION | representation adapters |
| Multi-fidelity modeling | "Use CFD plus tests" | Discovery / Evidence | SUPPORTED_BY_ARCHITECTURE_NOT_YET_PRODUCTIZED | truth hierarchy |
| Dataset-only challenge | "We only have historical simulations" | Evidence / Discovery | SUPPORTED_BY_ARCHITECTURE_NOT_YET_PRODUCTIZED | population/holdout qualification |
| Customer-hosted solver | "Our solver never leaves our VPC" | Private Discovery | REQUIRES_DEFINED_EXTENSION | truth RPC + private Challenge |
| Air-gapped work | "Nothing leaves our network" | Private Evidence/Qualification | REQUIRES_DEFINED_EXTENSION | offline deployment/security |
| Product qualification | "Can this exact model support this job?" | Product Qualification | SUPPORTED_BY_ARCHITECTURE_NOT_YET_PRODUCTIZED | Product Qualification Pack |
| Router / model portfolio | "Choose among specialists" | Product Qualification | SUPPORTED_BY_ARCHITECTURE_NOT_YET_PRODUCTIZED | system qualification |
| Deployment monitoring | "Tell us when it drifts" | Lifecycle | REQUIRES_DEFINED_EXTENSION | telemetry + requalification |
| Experiment allocation | "What should we simulate/test next?" | Physics Intelligence | REQUIRES_DEFINED_EXTENSION | prospective decision lift |
| Frontier bounty | "Pay only for a genuine breakthrough" | Sponsored Frontier Bounty | SUPPORTED_BY_ARCHITECTURE_NOT_YET_PRODUCTIZED | sponsor settlement policy |
| Universal certification | "Certify this model as safe everywhere" | — | OUTSIDE_INTENDED_ROLE | impossible/unbounded claim |
| Replace governing engineering authority | "Carbon decides regulatory approval" | — | OUTSIDE_INTENDED_ROLE | outside Carbon authority |

---

# 3. Customer inputs taxonomy

A commercial program may require some subset of:

## Scientific definition
- governing physics / model assumptions;
- desired inputs and outputs;
- operating envelope;
- target workload/population;
- important rare/high-consequence regimes;
- intended downstream job;
- answerability/escalation expectations.

## Truth/reference access
- solver API;
- executable/container;
- precomputed simulations;
- experimental observations;
- third-party truth service;
- partner goldens;
- multi-fidelity sources.

## Representation
- structured grids;
- unstructured meshes;
- CAD/geometry parameters;
- point clouds;
- graph topology;
- sensor time series;
- scalar QoIs;
- fields/trajectories.

## Commercial/security
- data classification;
- IP requirements;
- exclusivity;
- publication restrictions;
- on-prem/VPC/air-gap constraints;
- budget/timeline;
- deployment target;
- support/SLA.

---

# 4. Deliverable families

| Deliverable | Description | Qualification meaning |
|---|---|---|
| Discovery report | Ranked independent method evidence | Search result only |
| ExperimentRecord bundle | Provenance-rich authoritative evaluations | Evidence, not product certificate |
| Failure atlas | Failure modes by physical context/stratum | Evidence/diagnostic |
| Candidate construction method | Reproducible method/strategy | Candidate knowledge |
| Candidate artifact | Trained/reconstructed fast model | Not automatically qualified |
| Model Card | Artifact/construction/evidence identity | Provenance object |
| Validation Dossier | Evidence that the Challenge exam is fit for stated search use | Exam qualification |
| Product Battery Record | Result of a job-shaped qualification attempt | Qualification evidence |
| Qualification Record | Bounded claim for exact artifact/system/context | Product-plane claim |
| Executable package | ONNX/container/API/etc. | Deployment object; claim comes from evidence |
| Router/portfolio package | Multiple models + selection/escalation logic | Requires system-level qualification |
| Customer evidence report | Human-readable diligence package | Projection of authoritative evidence |
| Auditor bundle | Rich controlled evidence for independent review | Not public by default |
| Lifecycle plan | Drift/requalification/escalation policy | Operational control |
| Physics-intelligence brief | Evidence-informed recommendations | Must state epistemic maturity |

---

# 5. Commercial evidence levels

Recommended shorthand for customer conversations:

```text
E0 — FEASIBILITY
Problem and truth path appear authorable; no qualified claim.

E1 — QUALIFIED EXAM
Challenge/Dossier/measurements sufficient for the stated search use.

E2 — INDEPENDENT CANDIDATE EVIDENCE
Candidate has completed registered independent evaluation.

E3 — FRONTIER ADVANCE
Candidate/method has independently advanced the registered Challenge frontier.

E4 — PRODUCT QUALIFICATION
Exact artifact/system has a bounded Qualification Record for one context of use.

E5 — LIFECYCLE-SUPPORTED
Deployment monitoring, drift, escalation, and requalification path are operating.
```

These are commercial communication aids, not replacements for canonical scientific states.

---

# 6. Privacy / deployment matrix

| Mode | Customer data exposed to public/miners? | Carbon evaluator access | Customer infrastructure required | Status |
|---|---|---|---|---|
| Public Challenge | Only registered public semantics | Yes | No | architecture mature |
| Private sponsor, Carbon-hosted | No by policy | Authorized only | Optional | needs implementation/security |
| Customer-hosted truth RPC | No raw solver | Cases/answers through authenticated interface | Yes | high-priority extension |
| Customer VPC deployment | No | Controlled within VPC | Yes | extension |
| Air-gapped | No | Local authorized deployment | Yes | extension |
| Precomputed dataset | Depends on disclosure policy | Dataset access | No/optional | feasible with evidence limitations |

---

# 7. Sales qualification questions

A commercial lead should not advance to proposal until Carbon can answer:

1. What decision/job is the fast model intended to support?
2. What are the candidate inputs and outputs?
3. What population/regimes matter?
4. What truth/reference access is actually available?
5. How sensitive/private are data, geometry, solver, and methods?
6. Does the customer want discovery, evidence, delivery, qualification, or lifecycle support?
7. What exact artifact/report does the customer expect to receive?
8. What rights/exclusivity do they expect?
9. What deployment environment must be supported?
10. What scientific claim do they expect Carbon to make?
11. Who is the customer's final engineering authority?
12. What timeline/budget is available for truth generation and independent evaluation?
13. What happens commercially if no method advances the baseline?

---

# 8. "Can Carbon do X?" answer pattern

Preferred response template for the team:

```text
1. State whether the request is inside Carbon's intended role.
2. Identify the commercial mode.
3. State the scientific evidence path.
4. State what Carbon can deliver today vs what requires implementation.
5. State the strongest bounded claim available.
6. State any blocker: truth, privacy, adapter, rights, qualification, or runtime.
```

Avoid generic "yes, Carbon can do any physics problem" language.

---

# 9. Strategic implication

This taxonomy supports a broader but more disciplined commercial identity:

> **Carbon is not merely a subnet that produces neural operators. It is a configurable discovery, independent-evidence, frontier-reward, and qualification system for fast physical models.**

The product surface can widen while the scientific constitution remains fixed.
