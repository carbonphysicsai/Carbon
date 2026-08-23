# Carbon Go-To-Market Plan v1

**Status:** OWNER-CANONICAL GTM architecture.  
**Purpose:** define who Carbon sells to, how products enter accounts, how opportunities are qualified, and how accounts expand.

---

# 1. GTM principle

Do not sell “a subnet.” Do not lead with Alpha. Lead with a concrete engineering pain involving fast physical models.

Opening question:

> **Do you already build or use fast physical models, and what prevents you from relying on them more broadly?**

Carbon's four commercial motions are:

```text
DIAGNOSTIC / EVIDENCE
R&D / DISCOVERY
QUALIFICATION / LIFECYCLE
PLATFORM / CHANNEL
```

---

# 2. Initial vertical focus

## Direct-sales vertical 1 — Aerospace / space / defense

Target pains:
- expensive repeated CFD/FEA/simulation;
- surrogate credibility;
- optimization-loop acceleration;
- high-consequence regime coverage;
- private/on-prem evidence requirements;
- model V&V and change control.

Target roles:
- VP/Director Simulation;
- Chief Engineer;
- Digital Engineering leader;
- SciML/AI Engineering leader;
- V&V/modeling authority;
- R&D program manager.

## Direct-sales vertical 2 — Energy / turbomachinery / industrial physics

Target pains:
- repeated thermal/flow/structural simulation;
- rare-regime robustness;
- design optimization;
- real-time models / digital twins;
- expensive model updates and revalidation.

Target roles:
- simulation/CAE lead;
- R&D engineering lead;
- digital twin/control lead;
- AI/SciML lead;
- engineering platform owner.

## Strategic partner track — CAE / engineering software / engineering-AI

Potential motions:
- independent evidence for platform-generated models;
- qualification API/OEM;
- solver/truth integration;
- joint customer programs;
- sponsored research marketplace.

---

# 3. Opportunity routing

```text
Customer already has a fast model?
    yes → credibility problem? → Evidence Audit
          deployment claim? → Qualified Model Program

Customer lacks satisfactory model?
    problem ill-defined? → Challenge Feasibility
    problem ready? → Sponsored Discovery or Model Development

Many models / versions / teams?
    → Lifecycle / Enterprise Evidence Platform

Software vendor?
    → API / OEM

Recurring sponsor of research problems?
    → Frontier Market

Evidence corpus + prospective decision lift proven?
    → Physics Intelligence
```

---

# 4. Sales stages

```text
S0 TARGET
S1 DISCOVERY
S2 TECHNICAL QUALIFICATION
S3 COMMERCIAL QUALIFICATION
S4 PROPOSAL
S5 SECURITY / LEGAL / PROCUREMENT
S6 CONTRACTED / PILOT
S7 DELIVERED
S8 EXPANSION IDENTIFIED
S9 RECURRING / PLATFORM
```

A lead should not advance solely because it is technically interesting.

---

# 5. Discovery qualification

Required discovery questions:

1. What engineering decision/job is the fast model intended to support?
2. Does the customer already have a candidate?
3. What are required inputs and outputs?
4. Which physical regimes matter most?
5. What is the truth/reference source?
6. Can Carbon access it directly, remotely, or through customer-hosted execution?
7. What is the cost of the current workflow?
8. What happens if the fast model is wrong?
9. Who owns the technical decision?
10. Who owns the budget?
11. What privacy/IP/security constraints exist?
12. What deliverable does the customer believe it is buying?
13. Is the expected claim compatible with Carbon's evidence scope?
14. What is the timeline and procurement path?
15. What happens if the evidence is negative or no frontier advance occurs?

---

# 6. First-wedge motion — Evidence Audit

## Trigger

Customer has an existing model but lacks independent evidence or cannot confidently expand its use.

## Sales promise

> **Carbon independently tests what the model can actually support, where it fails, and what stronger evidence or remediation would be needed.**

## Why low-friction

- customer keeps its current model-development stack;
- no need to outsource R&D immediately;
- negative findings are still valuable;
- finite scoped pilot;
- natural path into follow-on work.

## Expansion signals

```text
model fails → remediation / discovery
model promising → qualification
model deployed → lifecycle
many models → enterprise platform
```

---

# 7. Sponsored Discovery motion

## Trigger

Customer has a valuable, authorable physical-modeling problem and wants broader search than its internal team can supply.

## Sales promise

> **Carbon turns the problem into a qualified competitive R&D program and independently verifies whether anyone genuinely advances the frontier.**

Commercial success is delivery of the agreed program and evidence, not guaranteed frontier improvement.

---

# 8. Qualification/lifecycle motion

## Trigger

Customer wants an exact candidate to support a defined operational or engineering use.

## Buyer value

- bounded evidence package;
- versioned artifact identity;
- limitations and answerability;
- change/requalification plan;
- auditable lifecycle.

This naturally supports recurring revenue because evidence must be revisited when the system changes materially.

---

# 9. Enterprise platform motion

Trigger platform conversation when:

- same customer has multiple models/programs;
- customer repeats Audits/qualifications;
- shared truth adapters can be standardized;
- customer needs governance/evidence registry across teams;
- annual usage becomes predictable.

Sell:
- private workspace;
- model/evidence registry;
- evaluation capacity;
- truth adapters;
- lifecycle/requalification;
- API/export;
- support;
- VPC/on-prem where required.

---

# 10. Objection handling

## “Why not validate internally?”

Carbon must prove value through independent evidence, protected evaluation, standardized provenance, broader competitive search, or reduced time/cost. Do not assume independence alone is sufficient.

## “Why not hire a consultant?”

Carbon's answer is repeatable infrastructure, evidence objects, qualification/lifecycle, software, and eventually scalable research supply—not advice alone.

## “Why Bittensor?”

It is the external research/optimizer market behind eligible discovery work. It is not required as the first sentence of an enterprise sale.

## “What if the model fails?”

Failure is useful evidence; the commercial product is the evidence program, not a guaranteed positive answer.

## “Our solver cannot leave our VPC.”

Use customer-hosted truth or private deployment once qualified. Do not promise unimplemented security topologies.

## “Who owns the method?”

Rights are specified prospectively in the commercial contract; sales may not improvise ownership.

## “Is this certification?”

No universal certification claim. Carbon can support bounded evidence/qualification for an exact context; governing engineering/regulatory authority remains external.

---

# 11. CRM evidence fields

Every opportunity should capture:

```text
vertical
buyer_role
budget_owner
product_motion
existing_model_yes_no
truth_access_mode
privacy_mode
technical_pain
business_pain
current_cost_or_delay
claim_requested
estimated_program_scope
security_complexity
rights_complexity
network_eligibility
next_step
decision_date
expansion_hypothesis
```

---

# 12. Design-partner criteria

Best early design partners:

- real expensive physics workflow;
- accessible technical buyer;
- real model or authorable problem;
- defensible truth path;
- willingness to share enough evidence to improve productization;
- manageable privacy/security scope;
- credible path to second engagement;
- meaningful reference value if successful;
- no requirement for Carbon to overclaim scientific authority.

---

# 13. GTM success metrics

Early:
- number of qualified interviews;
- repeated pain themes;
- willingness-to-pay evidence;
- proposal conversion;
- first paid Audit.

Then:
- repeatable Audit delivery;
- expansion rate;
- qualification/lifecycle attach rate;
- sales-cycle length;
- ACV;
- recurring share;
- platform conversion;
- partner/OEM pipeline.

---

# 14. GTM rule

> **Sell the customer's engineering outcome first, Carbon's evidence system second, and the network only where it materially improves the customer proposition.**
