# Fast physics models: competitive landscape

Research snapshot: 2026-10-09. This is a funding-meeting brief, not a market-size
model or a product qualification. Source IDs resolve in [evidence.json](evidence.json).
A named use is public adoption evidence; it does not establish contract size,
recurring revenue, or independent accuracy. Buyer roles below describe the
engineering functions served, not verified procurement titles.

## The competitive set

| Company / product | Offer and engineering buyers | Public traction and its limits |
| --- | --- | --- |
| **PhysicsX** | Enterprise AI engineering software and physics models spanning design, manufacture and operations; advanced-manufacturing engineering teams in aerospace, automotive, semiconductors, materials and energy. | Its financing announcement includes Siemens CTO Peter Koerte's account of an existing collaboration. It announced a Series B of **USD 135m**, sourced low/base/high **135/135/135m**. This is financing and a named partnership, not audited customer revenue. [L01: PhysicsX announcement](https://www.physicsx.ai/newsroom/physicsx-raises-135m-series-b-to-usher-in-a-new-era-of-ai-native-engineering-and-manufacturing). |
| **NVIDIA PhysicsNeMo** | Open-source PyTorch physics-ML framework, neural operators, graph models and training recipes; simulation developers, industrial AI teams and software vendors. Current comparison uses PhysicsNeMo; older Modulus material must be checked against current APIs. | NVIDIA describes integrations with Ansys and Luminary and applications at Shell and Siemens Energy. These establish vendor-reported use and an open construction route; they do not measure framework revenue or qualify Carbon's tasks. [L02: product and adoption stories](https://developer.nvidia.com/physicsnemo), [L03: official repository](https://github.com/NVIDIA/physicsnemo). |
| **Ansys SimAI, in Synopsys' Ansys portfolio** | Predictive models learned from simulation data for new design geometries; CAE analysts and component development teams. | A named Sumitomo Riko case describes simulation and experimental-analysis teams applying SimAI and related AI tools to component workflows. Treat the reported acceleration as a case result, not a universal end-to-end decision saving. Annual spend, total model-building cost and admissibility-equivalent accuracy are not supplied. [L04: product](https://ansys.synopsys.com/products/ai/simai), [L05: Sumitomo Riko](https://www.ansys.com/news-center/press-releases/10-8-25-ansys-ai-accelerates-sim-for-sumitomo-riko). |
| **Siemens Simcenter PhysicsAI** | Geometric deep-learning surrogates trained on historical simulation results; STAR-CCM+ CFD design exploration with retained high-fidelity validation. CAE and design teams are the users. Siemens' combined Altair portfolio belongs in this row. | Siemens announced the STAR-CCM+ add-on in May 2026. Kinetic Vision itself reports using PhysicsAI for packaging/design work. This is customer-side confirmation of use, not independently audited savings. Historical result reuse and integrated validation are already incumbent features. [L06: product release](https://news.siemens.com/en-us/siemens-simcenter-physicsai/), [L07: Kinetic Vision](https://kinetic-vision.com/kinetic-vision-recognized-for-ai-powered-simulation-leadership-at-siemens-realize-live/). |
| **Neural Concept** | CAD-native physics-aware engineering AI and design exploration; OEM and supplier design, CAE and manufacturing teams. | A Subaru case describes use with Cybernet in production engineering, including forming/material-thickness prediction. The company announced a Series C of **USD 100m**, sourced low/base/high **100/100/100m**. Named use and financing are stronger evidence than an uncited customer-logo slide, but neither is Carbon traction. [L08: Subaru](https://www.neuralconcept.com/customer-stories/subaru-introduces-neural-concept-to-revolutionize-automotive-development), [L09: financing](https://www.neuralconcept.com/press-release/neural-concept-closes-100m-funding-round). |
| **Luminary** | Physics AI Model Factory for building and deploying physics models; automotive, aerospace and industrial engineering teams. | Its announcement identifies Honda and Otto Aerospace model collaborations and names industrial customers. Its Series B was **USD 72m**, sourced low/base/high **72/72/72m**. Those are company-reported collaborations, customer names and financing, not independent proof of every model's operating envelope. [L10: platform and funding announcement](https://luminary.ai/resources/luminary-cloud-secures-72m-series-b-to-lead-the-physics-ai-era/). |

The identical funding endpoints reproduce announced point amounts; they are not
confidence intervals. This is a representative competitive set, not an exhaustive
vendor census. We do not infer total market size from financing, logos or
headline inference speed.

## Where Carbon could earn a different position

The **inference** from these sources is that speed, geometry generalization,
simulation-data reuse and engineering integration are crowded claims. NVIDIA
already provides open tooling; Siemens explicitly retains reference simulation.
Carbon should not claim exclusive ownership of openness, validation, optimization
or decision relevance.

The [Business Canon](https://github.com/carbonphysicsai/Carbon/blob/3a6dfdd8dffdfdaf241596033d5bf55b66abfcff/Business/Business_Canon.md)
defines Carbon as discovery and evidence infrastructure for Physics AI.
EvidenceAudit is the proposed initial commercial wedge; SponsoredDiscovery adds
open method competition. The distinguishing **design hypothesis** is the
combination of independent reconstruction, a registered population and
measurement contract, protected fresh evaluation, admissibility before ranking,
and evidence about the buyer's decision against its strongest affordable
baseline. Existing vendor models could be audited or entered where rights and
interfaces permit; vendor partnership and competition can coexist.

The [recorded project status](https://github.com/carbonphysicsai/Carbon/blob/3a6dfdd8dffdfdaf241596033d5bf55b66abfcff/docs/publications/PROJECT_STATUS.md)
is bounded software/development evidence. It does not establish signed paid
customers, recurring revenue, validated pricing, production qualification or a
proven network reward advantage. Those quantities remain `HUMAN_INPUT`,
low/base/high `null/null/null`; this brief does not assert that undisclosed
commercial activity is absent.

For funding meetings, describe the product hypothesis and then show the evidence
needed to test it: a sourced buyer workflow and decision volume; feasible,
contested questions; a qualified reference; superiority over cached FE,
response surfaces and other cheap models at matched admissibility; and full
construction/evaluation cost. The separate
[buyer-volume proposal](../../../docs/development/challenge_pipeline/discovery/buyer-volume/README.md)
records why public charging activity and within-study design counts cannot fill
the missing annual engineering-decision denominator.

**Recommended positioning:** Carbon intends to provide independently checkable
evidence that competing construction methods improve a specified physical
decision. Its commercial value and the benefit of open competition remain to be
demonstrated. This wording follows repository authority and avoids turning
competitors' fundraising into Carbon's market or revenue forecast.
