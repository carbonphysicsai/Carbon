# Products and revenue

**Commercial focus updated 20 November 2026:** [custom model discovery and design](../.agent/decisions/2026-11-20-OWNER-CUSTOM-MODEL-DISCOVERY-DESIGN-01.md).

Carbon's commercial focus is custom model discovery and design. Customers bring an engineering problem and the model capability they need; Carbon scopes discovery and development around that job, with independent evaluation built into the work. Customers can retain their existing solvers and engineering tools.

The offerings below describe product design and the intended delivery sequence. They are not a list of production services or evidence of sales. See [Project status](../docs/publications/PROJECT_STATUS.md) for the implementation record.

## Start with the customer's engineering problem

Define the decision, required inputs and outputs, operating conditions, reference access and constraints before proposing a program. **Challenge Feasibility / Design** establishes whether the work is supportable and what the customer must supply.

**Sponsored Discovery** searches for useful model-building approaches. **Model Development** designs and develops a reproducible candidate around the agreed requirements. These are the primary product families for custom model discovery and design; a customer may need one or both.

The intended deliverables are the agreed candidate or construction method, reproducibility material and independent evaluation findings. Scope must define rights, limitations and treatment of a negative or unresolved result. Qualification for a particular deployment remains a separate decision.

**Evidence Audit** is a complementary option when a customer specifically needs an existing model evaluated. It is not the default first product or a prerequisite for discovery and development.

## Product families

The existing P1–P11 identifiers remain the commercial planning taxonomy, not a purchase order. P3 and P4 lead the current offer; P2 supports feasibility and scoping. Their identifiers and revenue rails are unchanged.

| ID | Product | Customer need and intended deliverable | Revenue design |
|---|---|---|---|
| P1 | Evidence Audit | Assess an existing model for a defined use; deliver an evidence and failure report | Scoped audit, integration, and evaluation fees |
| P2 | Challenge Feasibility / Design | Establish whether a problem supports a defensible evaluation or discovery program | Authoring and feasibility fee |
| P3 | Sponsored Discovery | Search for a better method against agreed requirements; deliver research outcomes and evidence | Program, integration, evaluation, and reward-administration fees |
| P4 | Model Development | Design and develop a reproducible candidate for the agreed engineering problem, with independent evaluation findings | Development and integration fees |
| P5 | Qualified Model Program | Assess one exact model or system for a bounded engineering use | Qualification, evidence, and deployment fees |
| P6 | Model Lifecycle | Revisit evidence after changes to a model, reference, runtime, or operating range | Recurring support, lifecycle, and requalification fees |
| P7 | Enterprise Evidence Platform | Manage repeated evaluations across teams and model portfolios | Subscription, usage, private deployment, and support |
| P8 | Evidence / Qualification API and OEM | Embed Carbon's evidence workflows in another engineering platform | License, usage, OEM royalty, and support |
| P9 | Sponsored Frontier Market | Run recurring research competitions for defined scientific improvements | Platform, authoring, evaluation, and administration fees |
| P10 | Model / Method Licensing | Obtain permitted rights to reproduced or qualified work | License or royalty, subject to Carbon's rights |
| P11 | Physics Intelligence / Experiment Allocation | Use accumulated evidence to choose better future experiments | Future project, subscription, or API fees after prospective validation |

P3 and P4 are the primary commercial focus, supported by P2 and the necessary reference integration. P1 remains complementary. P5–P11 depend on the customer need, implementation, evidence and rights required for each offering. This ordering does not establish production availability or sales.

## Sponsored Discovery

A sponsor brings a physical-modeling problem and a reference path. Carbon defines the program, establishes the evaluation contract, and organizes research. Evaluators determine whether candidates meet the requirements and improve on the comparison baseline.

The commercial deliverable is the agreed research and evidence program. Carbon does not guarantee a frontier advance. A candidate from the competition still needs separate evidence for a customer's deployment.

The contract separates Carbon's fees from any sponsor-funded participant reward pool. Participant rewards are not automatically company revenue.

## Expansion within an account

| Customer situation | Next potential engagement |
|---|---|
| Discovery identifies a promising method | Further model design and development |
| Customer needs another output, operating range or related model | A further scoped discovery or development program |
| An optional audit identifies important failure regions | Discovery or model development where appropriate |
| Candidate supports further investigation | Qualification for a defined use |
| Customer deploys or changes a model | Lifecycle support and requalification |
| Teams repeat evaluation across a portfolio | Enterprise software and APIs |
| An engineering platform needs the workflow | OEM or embedded API partnership |

Customers need not buy each stage. Carbon's aim is to reuse the reference integration and evidence workflow when further work makes sense.

## Pricing and delivery economics

Carbon plans to price the engineering outcome and evidence burden. Scope includes expert work, reference calculations, evaluation compute, integration, and any qualified private deployment. Contracts specify finite capacity and change-order terms.

The pricing principles remain:

- Base fees cover legitimate work even when the evidence is negative. Any success fee is additional.
- Customer payments cannot change the scientific standard for the same claim.
- Rights, exclusivity, support, and private deployment need explicit scope and authority.
- Enterprise procurement can use fiat without a mandatory Alpha purchase.

The accounting system retains separate revenue identifiers: `AUTHORING_FEE`, `TRUTH_INTEGRATION_FEE`, `PROGRAM_PLATFORM_FEE`, `EVALUATION_USAGE_FEE`, `SPONSORED_REWARD_ADMIN_FEE`, `MODEL_DEVELOPMENT_FEE`, `QUALIFICATION_FEE`, `DEPLOYMENT_INTEGRATION_FEE`, `SOFTWARE_SUBSCRIPTION`, `ON_PREM_LICENSE`, `MODEL_LICENSE`, `METHOD_LICENSE`, `OEM_ROYALTY`, `SUPPORT_SLA_FEE`, `LIFECYCLE_SUBSCRIPTION`, `REQUALIFICATION_FEE`, and `PHYSICS_INTELLIGENCE_FEE`.

Per engagement, Carbon tracks contracted and collected value, recurring value, reward pass-through, direct labor, reference and compute costs, integration, support, gross contribution, custom versus reusable work, network activity, reuse rights, and expansion. These commercial fields do not enter scientific scoring.

## Product maturity

Commercial progression remains `CONCEPT` → `DESIGN_SPECIFIED` → `INTERNAL_PILOT` → `PAID_PILOT` → `REPEATABLE_SERVICE` → `PRODUCTIZED` → `ENTERPRISE_QUALIFIED` → `SCALE_READY`. Each promotion requires evidence for that product; a software test or a research result cannot substitute for a customer purchase.

Each offering needs a buyer, deliverable, cost model, rights agreement, bounded evidence claim, and a reason to repeat or expand it. [Financial model](Financial_Engine.md) and [Commercial operating model](Commercial_Operating_Model.md) retain the delivery and accounting controls.

## Research services

Research Concierge / Copilot remains a candidate workflow offering under `OWNER-EVIDENCE-RESEARCH-01`. `G-PR0` freezes the pilot; `G-PR1..5` govern entitlement and rights, campaign memory, non-official execution, billing and spend, and the commercial decision. Custom model discovery and design is the primary commercial focus; Evidence Audit remains complementary. Free and paid miners receive official-derived scientific content on equal release terms. Interest or a stated budget does not establish revenue or authorize spending.
