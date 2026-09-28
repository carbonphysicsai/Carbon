# Carbon: business and market

Carbon is building **discovery and evidence infrastructure for Physics AI**. Its opportunity lies in helping engineering teams choose better fast models, test their physical behavior, and maintain evidence as their designs and models change.

This document describes the investment thesis and its remaining tests. [Project status](../docs/publications/PROJECT_STATUS.md) records implementation and research evidence as of 28 September 2026. The commercial plan does not establish customer traction or forecast revenue.

## The engineering problem

An engineer may use a fast model to evaluate thousands of cooling designs or charging protocols before running expensive simulations on the finalists. That acceleration is useful only if the model preserves the behavior that matters to the decision.

Average prediction error leaves several questions open: performance near a physical limit, behavior outside familiar training conditions, reproducibility, and the effect of changing a solver, model, or runtime. Engineering teams must answer those questions before they can expand a model's use.

Carbon aims to make that work reusable. The company combines a defined engineering task, a defensible reference, independent reconstruction, and an evaluation program with explicit limits on what the evidence supports.

## First customer engagement

The **Carbon Evidence Audit** starts with a customer's existing model. Carbon and the customer agree the decision, operating range, reference source, and evaluation scope. The intended deliverable is an evidence package identifying supported behavior, failures, and the next work needed.

| Audit finding | Potential next engagement |
|---|---|
| The model fails in important conditions | Remediation or Sponsored Discovery |
| The model shows promise within a narrower range | Qualification for that defined use |
| The customer changes the model or operating conditions | Re-evaluation and lifecycle support |
| Multiple teams repeat the same evaluation workflow | Enterprise evidence software or API integration |

This sequence lets Carbon learn the customer's workflow before building a broad platform. Repeat purchases and lower delivery cost would provide evidence that the approach can scale.

## How Carbon can compete

Carbon's position is compatible with customers continuing to use their existing CAE tools and model providers. A model builder can supply candidates, a simulation vendor can supply reference calculations, and Carbon can organize independent comparison and further research.

| Adjacent category | Carbon's intended role |
|---|---|
| CAE and high-fidelity simulation | Integrate trusted reference calculations into model evaluation |
| Physics AI and engineering-AI model builders | Evaluate candidates and organize research on unmet requirements |
| Engineering validation and data platforms | Add challenge-specific reconstruction, physical checks, and evidence records |
| Compute and orchestration providers | Use their infrastructure for research and evaluation |

Well-funded model builders can also develop evaluation capabilities. Carbon's competitive case rests on execution: evaluation across suppliers, a producer-independent grading process, and access to external research through the subnet. Capital raised by another company does not prove or disprove those advantages.

Carbon does not claim that other companies lack validation. The intended distinction is the combination of competitive discovery, independent reconstruction and testing, and evidence tied to a specific engineering use.

## Research network

Carbon is developing its network on Bittensor. Researchers and agents explore supported methods; evaluators determine whether a candidate meets the challenge's requirements and improves on the comparison baseline.

The potential benefit is access to a wider range of approaches without hiring each specialist into the company. Carbon still has to measure whether that produces better results per dollar, faster progress, or capabilities an internal team would struggle to supply. The repository does not establish a proven network advantage over centralized research.

The company plans to treat the subnet as a research team and pay for useful output through Alpha buyback and burn. That plan remains separate from the implemented development reward-routing work. See [Network and Alpha](Network_and_Alpha_Value.md) for status and boundaries.

## Revenue and expansion

The initial revenue design combines scoped evaluation services, reference integration, and finite research programs. As customers repeat those workflows, Carbon plans to add qualification, lifecycle support, subscriptions, usage fees, and API or OEM distribution.

The company must demonstrate that repeat work requires fewer custom engineering hours. Reusable adapters and evidence workflows matter economically only when they reduce cost or improve delivery for a subsequent customer.

Longer-term research products could use permitted experiment records to recommend methods and allocate experiments. Carbon must demonstrate that those recommendations improve future decisions before treating Physics Intelligence as a validated product.

## Initial markets

The initial direct-sales focus remains aerospace, space and defense, followed by energy, turbomachinery and industrial physics. The partner track includes CAE vendors, engineering-AI platforms, and simulation infrastructure providers.

The engineering launch portfolio is battery fast charging and ageing, AI-chip cold plates, electric motors, and silicon photonics. Those are selected research directions at different stages of readiness. They are not evidence of four commercial products or customers in those industries.

Carbon's market model uses target enterprises, relevant model programs, and addressable evaluation and research spend. A simulation-market total would provide category context, not Carbon's obtainable revenue. A credible near-term model needs named opportunities, procurement evidence, delivery costs, and repeat demand.

## What could compound

Each completed engagement could leave Carbon with reusable reference integrations, evaluation workflows, reproduced method knowledge, and a better understanding of customer requirements. Customer rights determine which records and methods Carbon can reuse.

Over time, those assets could shorten setup, support repeat evaluation, and give external researchers better-defined problems. Their value remains a thesis until Carbon demonstrates repeat use and improved economics.

## Milestones and risks

| Milestone | Evidence an investor can inspect | Main risk it tests |
|---|---|---|
| Reliable battery development journey | Retained research, reconstruction, evaluation, recovery, and resource records | A working interface may still fail to support useful research |
| Qualified challenge and deployment | Reference, scientific, security, and operating evidence for the exact configuration | Correct software may still apply an inadequate exam |
| First paid Evidence Audit | An agreed scope, delivered evidence, and payment | Engineering interest may not convert to budget |
| Repeat delivery and expansion | Further engagements with measured effort and margin | Carbon may remain dependent on bespoke services |
| Useful network research | Comparison of cost, quality, and time against credible alternatives | The subnet may add more overhead than value |
| Recurring evidence software | Renewals and repeated workflow usage | Customers may need occasional projects rather than a platform |

Carbon's long-term ambition is to give engineers and engineering agents access to better fast models with an inspectable record of where they work. The near-term task is to prove that sequence with bounded physics challenges and customer evidence.
