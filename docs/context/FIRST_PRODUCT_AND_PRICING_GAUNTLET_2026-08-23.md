# Carbon First Product + Pricing Gauntlet — 2026-08-23

**Status:** completed commercial/investor-design gauntlet.  
**Purpose:** attack Carbon's first sellable products, pricing units, sales motion, gross-margin structure, procurement objections, acceptance criteria, upsell path, recurring revenue, and network linkage as a standalone business.

---

## 1. Executive result

The strongest initial product pair is:

1. **Carbon Evidence Audit** — lowest dependency on a mature open network and strongest immediate fit to the judge/evidence architecture.
2. **Carbon Sponsored Discovery Pilot** — strongest demonstration of Carbon's differentiated network-backed R&D model and natural bridge into larger contracts.

They should not be priced as generic consulting days. They should be sold as bounded outcomes with explicit evidence/deliverable scopes.

The commercial sequence should be:

```text
EVIDENCE AUDIT
land with an existing customer model
        ↓
REMEDIATION / DISCOVERY
find a better method or repair failure modes
        ↓
QUALIFICATION
prove one exact candidate for one job
        ↓
DEPLOYMENT + LIFECYCLE
integrate, monitor, requalify
        ↓
ENTERPRISE PLATFORM
repeat across teams/models/programs
```

The Sponsored Discovery Pilot can enter at the second step directly when the customer already has a clearly defined modeling problem and truth source.

---

# 2. Product 1 — Carbon Evidence Audit

## Buyer problem

The customer already has a fast physical model or surrogate but lacks defensible independent evidence about:

- physical admissibility;
- hard failure modes;
- robustness by regime;
- hidden performance;
- operating envelope;
- reproducibility;
- suitability for a downstream engineering job.

## Likely buyers

- Head / Director of Simulation;
- Head of Digital Engineering / Digital Twin;
- SciML / AI-for-engineering lead;
- CAE product lead;
- Chief Engineer / technical authority;
- model V&V / validation group;
- CTO at a physics-AI company.

## Product promise

> **Give Carbon your fast physical model and the job it is supposed to support. We author and qualify an independent evaluation program, test the candidate, and return evidence about what survives, where it fails, and what would be required for a stronger claim.**

## Minimum customer inputs

- candidate artifact or callable endpoint;
- intended input/output semantics;
- claimed operating envelope;
- reference/truth access;
- intended use;
- privacy/security requirements.

## Standard deliverables

```text
Engagement definition / evidence plan
Qualified or qualified-with-limitations Challenge exam
Independent candidate evaluation
Regime / stratum performance report
Mandatory-admissibility results
Failure atlas / limitations
Reproducibility identity/provenance
Evidence bundle for technical diligence
Recommended next action:
  ACCEPT FOR FURTHER QUALIFICATION
  REMEDIATE
  NARROW ENVELOPE
  REJECT FOR STATED CLAIM
```

The Audit itself should not promise Product Qualification unless the engagement explicitly includes the Product Qualification Program.

## Acceptance criteria

Commercial delivery accepted when:

- agreed evidence program completed or transparently blocked for defined reasons;
- agreed candidate and truth interfaces exercised;
- evidence/report bundle delivered;
- all material limitations disclosed;
- customer acceptance tests for report/package completed.

Scientific failure by the customer's model is still successful delivery of an Audit.

## Pricing unit

Do **not** price per model score.

Primary commercial unit:

```text
BASE AUDIT PACKAGE
+
TRUTH / ADAPTER INTEGRATION
+
EVALUATION CAPACITY
+
OPTIONAL SECURITY / VPC / ON-PREM PREMIUM
```

This supports fixed-fee procurement while protecting Carbon from unbounded compute/integration scope.

### Recommended pricing structure for pilots

No universal dollar price is locked before real sales discovery. Instead quote through bands derived from:

```text
minimum expert authoring burden
+ expected truth integration burden
+ evaluation compute budget
+ security/deployment premium
+ commercial value / urgency
+ rights / exclusivity premium where applicable
```

Create three quote tiers:

```text
AUDIT_STANDARD
single candidate, bounded truth path, Carbon-hosted

AUDIT_ADVANCED
multiple candidates / richer strata / custom adapter

AUDIT_ENTERPRISE
private infrastructure, VPC/on-prem, auditor bundle, enhanced SLA
```

The quote must contain explicit included evaluation budget and overage/change-order rules.

---

# 3. Product 2 — Carbon Sponsored Discovery Pilot

## Buyer problem

The customer has a physical modeling problem but does not know the best construction method, model family, training strategy, or approach.

## Product promise

> **Carbon turns the customer's defined physics problem into a qualified competitive discovery program, pays external researchers/agents to search, independently tests what survives, and delivers evidence on the strongest verified advances.**

## Commercial components

```text
Challenge Design / Feasibility fee
Truth integration fee
Program / platform fee
Evaluation usage budget
Sponsor-funded reward pool
Reward administration fee
Optional candidate-development fee
Optional qualification program
Optional deployment / lifecycle
```

The sponsor reward pool must be accounted as pass-through / participant capital, not automatically Carbon revenue.

## Commercial success semantics

The pilot is commercially deliverable even when no contender advances the frontier, provided Carbon ran the agreed qualified program and delivered the resulting evidence.

This prevents sales incentives from pressuring the scientific layer to manufacture a winner.

## Buyer protection

The contract should define:

- baseline/frontier identity;
- reward event;
- maximum sponsor reward pool;
- campaign duration / evaluation budget;
- rights in winning methods/artifacts;
- what happens if no advance occurs;
- whether unused sponsor reward is returned, expires, or follows a separate prospective policy;
- follow-on candidate/qualification options.

## Carbon revenue model

Carbon should earn independently of whether the sponsor reward is paid:

```text
AUTHORING / INTEGRATION REVENUE
+
PROGRAM PLATFORM REVENUE
+
EVALUATION / USAGE REVENUE
+
REWARD ADMINISTRATION REVENUE
+
FOLLOW-ON PRODUCT REVENUE
```

This makes the company economically resilient to scientifically honest `NO_FRONTIER_ADVANCE` outcomes.

---

# 4. Pricing red team

## Failure mode: consulting day rates

Risk: low ceiling, hard to compare value, customer buys labor instead of infrastructure.

Disposition: use internally for cost estimation, not primary external value metric.

## Failure mode: success-only pricing

Risk: pressure to create favorable scientific outcomes; volatile revenue; customer can externalize all failed-search cost.

Disposition: optional upside component only. Base program fees remain payable for legitimate scientific work.

## Failure mode: unlimited evaluation bundle

Risk: compute and truth costs destroy margin.

Disposition: every quote includes finite evaluation/truth budget and explicit expansion unit.

## Failure mode: price purely by compute

Risk: Carbon becomes a low-margin GPU intermediary and ignores the value of authoring, evidence, qualification, and decision leverage.

Disposition: compute is a cost/usage rail, not the complete price.

## Failure mode: force token purchase

Risk: enterprise procurement friction obscures product value.

Disposition: fiat-first commercial UX; network settlement abstracted behind Carbon where legally/operationally appropriate.

---

# 5. Unit-economics architecture

Every paid engagement should record:

```text
TCV / ACV
recognized revenue by rail
reward pass-through
expert labor hours
truth-source cost
GPU / evaluation cost
security / deployment cost
support cost
third-party license cost
gross contribution
custom-work fraction
reusable-work fraction
network-executed fraction
follow-on pipeline
renewal probability / state
```

Key business metric:

> **Gross margin should improve because each engagement leaves reusable adapters, templates, automation, and evidence workflows behind.**

The company should track `productization_ratio`:

```text
reusable workflow effort / total delivery effort
```

and aim for that ratio to rise cohort by cohort.

---

# 6. Sales-motion gauntlet

## Stage 1 — problem qualification

Do not lead with Bittensor or Alpha.

Lead with:

> **Do you already use or build fast physical models, and what stops you from relying on them more broadly?**

Qualify:
- expensive repeated simulation;
- credibility/robustness gap;
- existing surrogate/model;
- truth source;
- decision value;
- technical owner;
- budget owner;
- security/IP constraints.

## Stage 2 — low-friction wedge

Evidence Audit where possible.

Reason: customer can evaluate Carbon without outsourcing the core model-development program first.

## Stage 3 — expansion

Audit identifies:

```text
failure -> remediation/discovery
promising model -> qualification
multiple teams/models -> platform
deployment -> lifecycle
hard search problem -> sponsored discovery
```

## Stage 4 — enterprise conversion

Repeated programs should trigger a commercial conversation around:

- annual platform/usage commitment;
- private workspace;
- standard truth adapters;
- qualification registry;
- API/OEM;
- support SLA.

---

# 7. Procurement and objection red team

## “Why not validate this internally?”

Answer architecture: independent evidence, protected evaluation, repeatable qualified process, external research supply, and evidence/qualification infrastructure. Carbon must prove this saves time, reduces bias, improves decision quality, or expands search beyond the internal team.

## “Why not hire a consultant?”

Carbon must show a reusable platform, standardized evidence objects, repeatable qualification/lifecycle, and eventually network-scale discovery—not bespoke advice only.

## “Why Bittensor?”

Investor/customer answer: it is the scalable external optimizer/research market behind eligible discovery programs. It is not required as the first sentence of every enterprise sale.

## “What if the model fails?”

That is useful evidence. Audit/program delivery is not contingent on manufacturing success.

## “What if our data/solver cannot leave?”

High-priority product extension: customer-hosted truth RPC, VPC/on-prem, later air-gap.

## “Who owns the winning method?”

Must be defined before the program through CommercialRightsPolicy. This is a current commercialization dependency, not something sales may improvise.

## “Is this a certification?”

No universal claim. Carbon can issue bounded evidence/qualification under a defined context; customer's governing engineering/regulatory authority remains external.

---

# 8. Investor-grade business model test

An investor should be able to understand Carbon without understanding the scientific internals.

### Problem

Fast physical models can unlock enormous simulation/optimization throughput, but organizations face a credibility, discovery, and lifecycle bottleneck.

### Product wedge

Independent evidence and sponsored discovery.

### Expansion

Qualification, deployment, requalification, enterprise evidence platform.

### Scale

External research network, APIs/OEM, marketplace, licensed methods/models.

### Recurrence

Lifecycle, requalification, support, platform subscriptions, usage.

### Moat

- qualified evidence workflows;
- proprietary evaluation/qualification infrastructure;
- reusable truth/representation adapters;
- accumulating rights-permitted experiment evidence;
- network supply of researchers/agents;
- customer workflow integration;
- later prospectively validated physics intelligence.

### Business-model resilience

Carbon OpCo can generate revenue even before the full network marketplace is mature. The subnet is a scaling and differentiation layer, not the only source of company viability.

---

# 9. What must be proven before investor claims

Do not claim demonstrated economics until evidence exists.

Investor evidence ladder:

```text
DESIGN
clear products / pricing architecture
        ↓
CUSTOMER DISCOVERY
repeated pain + willingness-to-pay evidence
        ↓
PAID PILOT
real customer pays
        ↓
REPEATABLE SERVICE
similar scope delivered twice+
        ↓
EXPANSION
customer buys second product / larger scope
        ↓
RECURRING
renewal / usage commitment
        ↓
PLATFORMIZATION
lower custom effort and improving gross margin
        ↓
NETWORK LEVERAGE
network materially improves cost/search/output
```

---

# 10. Gauntlet verdict

**PASS architecturally, not yet commercially validated.**

Carbon now has a coherent first-product architecture capable of becoming a standalone enterprise business.

Highest-value validation sequence:

1. conduct structured buyer discovery around Evidence Audit;
2. design one standard Audit statement of work and evidence deliverable;
3. secure first paid Audit pilot;
4. use it to measure delivery cost and willingness to pay;
5. attach remediation/discovery or qualification;
6. package repeated workflow into platform primitives;
7. run a sponsored discovery pilot with explicit network economics.

The next architecture gauntlet should focus on **Investor Business Model + Financial Engine**: market segmentation, buyer/budget centers, ACV architecture, revenue mix, margin progression, CAC/payback logic, services-to-software transition, scenario economics, capital requirements, milestones, and investor objections—without inventing market traction or financial results that do not yet exist.
