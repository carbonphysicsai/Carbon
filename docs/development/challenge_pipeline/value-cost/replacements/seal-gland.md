# Static seal-gland contact and support — f08 candidate 2

**Strongest cheap baseline first:** Parker/Trelleborg standard gland calculators,
squeeze/fill/extrusion charts, a calibrated axisymmetric response surface and
exact lookup. Catalogue O-ring selection alone is **not** a useful Carbon
Challenge if those tools already settle it. DEVELOPMENT / SPECIFIED;
[common boundaries](README.md). No replacement adoption or physical seal claim.

## V1 — buyer and existing workflow

Buyer role: industrial valve/pump sealing engineer revising a compact gland
and back-up support geometry under specified pressure and manufacturing gaps.
Select a low-assembly-force geometry without losing the registered contact/
deformation margin; not a prediction of leakage or lifetime from contact alone.

[Parker's engineering brochure, PDF p5](https://www.parker.com/content/dam/Parker-com/Literature/Praedifa/Brochures/OilGas_SGE07-EN.pdf)
describes nonlinear FEA for seal geometry and support refinement.
[Trelleborg's simulation article](https://www.trelleborg.com/seals/-/media/tss-media-repository/tss_website/services-and-tools/technical-library/technical-articles/pdfs/simulations-fluid-power-components.pdf?rev=b279b12297314941bfbccfe8e1e7e8be)
independently describes seal/material simulation. The cited severe industrial
examples establish a workflow, **not** authorization to claim this small open
reference supports those pressures, compounds or safety applications.

## V2 / V3 — buyer-unit scenarios

ASSUMPTION low/base/high: 2 / 5 / 12 engineer-h per gland revision at
60 / 90 / 120 EUR/h = **120 / 450 / 1,440 EUR** gross effort at stake.
A conditional cohort of 5 / 20 / 50 teams making 10 / 40 / 100 in-scope
revisions/team/year yields **50 / 800 / 5,000 decisions/year**. Sources support
revisiting geometry/material/support, not these frequencies. Do not count every
seal manufactured or maintenance replacement as another design decision.
Observed volume and actual savings unknown; realized commercial floor zero.
Wrong picks mean renewed geometry/tooling review and verification; no leaked-
fluid, environmental, injury or avoided shutdown dollars are assumed.

## Task/reference and buyer give-up

Propose an axisymmetric static gland/back-up-ring family with groove dimensions,
gap and support actions, over three buyer-specified pressure/temperature/
material-condition strata. Report assembly force, contact distribution and
extrusion displacement through the gap. Minimum contact pressure **is not a
universal leakage certificate**. Numeric acceptances/material calibration,
chemical compatibility, strains and P/Q/w remain HUMAN_INPUT. No limit is
weakened; dynamic wear, scratches, gas decompression, ageing and lifetime are
excluded and still need the buyer's normal tests.

Open route: [CalculiX](https://www.dhondt.de/) axisymmetric nearly incompressible
hyperelastic/contact deck. Acquisition owner must establish supported element/
material/contact formulation, source/build/image digest and force/contact
extractor; otherwise HOLD. Existing f08 modal packaging does not qualify this
nonlinear route. Independently matched Abaqus or the buyer's nonlinear FE
tool is a **Tier 2 target**, not an earned tier or field reliability.

## C1 / C2 hypotheses

Complete case includes squeeze/assembly then pressure ramp for one geometry/
condition, all increments, meshing and extraction. Hypothesis CPU-h
0.015 / 0.05 / 0.15 (0.9 / 3 / 9 CPU-min), RAM 0.5 / 2 / 6 GiB.
24 designs × 3 strata = 72 primary; 24 twice-cost refined; 15 charged failures;
8 two-tool witness pairs => 151 equivalents. C2 **20.21 / 28.83 / 53.45 EUR**
in the [common scenario](scenarios.json), not measured quantiles or a grant.

## Incremental utility and stop rule

Plausible advantage is supported custom gap/back-up geometry near contact/
extrusion changes, not beating a standard squeeze calculator by hiding its
inputs. Compare a well-calibrated ordinary surrogate on whole-gland holdouts.
Reject if charts or that surrogate reach the same picks, material law is not
credible, or geometric contact margins cannot answer a buyer-recognizable
decision without unaffordable laboratory evidence. Second for f08: low nominal
cost, but material credibility and translating deformation to buyer utility
are larger risks than the bill.
