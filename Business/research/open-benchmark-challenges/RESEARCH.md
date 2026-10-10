# Open benchmarks as Challenge evidence routes

Status: RESEARCH RECOMMENDATION / NOT RUN. Bounded ticket: OPEN-BENCHMARK-CHALLENGES-01. Authority snapshot: Carbon main e1ee386e774b87ca1aeb8d705ebc537a94111f26. Scope: new research files only. Sources were inspected on 2026-10-10; downloadable archives were not executed or treated as validated imports.

## What the benchmark would establish

A complete benchmark can anchor verification or comparison with measured data. It does not transfer physical validation to arbitrary new geometry, materials, operating conditions or decision thresholds. Under [reference-credibility.md](../../../docs/development/challenge_pipeline/round1/reference-credibility.md), agreement with an industry tool on both named benchmarks and matched task witnesses is needed for Tier 2; calibrated independent held-out physical evidence with uncertainty is needed for Tier 3. Neither is earned by this search. All executable agreements are NOT_RUN.

The owner's representative-case allowance is a separate evidence category. Do not label a published numerical example an earned buyer-tool Tier 1 merely because it is reproducible. P, proposal Q and score/evidence weights w remain separate and HUMAN_INPUT until the packet owner registers them. Published benchmark conditions are source facts, not invented customer safety limits.

## Ranking and uncertainty

The table is a research priority order, favoring evidence completeness and a plausible design family. It is not a monetary value-to-cost index or a cross-Challenge official score. There is no sourced annual buyer volume or measured gain for these families.

All scores are **ASSUMPTION ordinal low/base/high**, with the following common rubric:

- Shortcut difficulty: 0 = analytic/finite lookup suffices; 1 = standard formula or calibrated low-order model; 2 = plausible residual design frontier after those tools; 3 = a credible mechanism by which discontinuity, separation or coupled conditions could defeat shortcuts; 4 = measured matched-admissibility shortcut failure. Nobody earns 4 here.
- Equal-budget gain potential: 0 = no gain or worse remains plausible; 1 = narrow ranking benefit; 2 = plausible mechanism after charging bank/construction/screening costs; 3 = compelling hypothesis requiring a matched panel; 4 = Carbon measured positive complete-budget gain. Actual gain is null for every row.
- Buyer value potential: 0 = method control; 1 = plausible engineering exercise; 2 = a recognizable design decision; 3 = substantial decision stakes are plausible but not priced; 4 = sourced exact buyer volume and value. Buyer-role labels below are inferred engineering roles, not verified procurement or revenue claims.

| Priority | Candidate | Regime | Shortcut | Gain potential | Value potential | Startup low/base/high, ASSUMPTION |
|---|---|---|---|---|---|---|
| 1 | C1: Backward-facing-step separation | CFD | 2/3/3 | 0/2/3 | 1/2/3 | €1.32/17.54/175.36 |
| 2 | O2: 3D periodic metagrating | optics | 1/2/3 | 0/2/3 | 1/2/3 | €0.44/7.01/105.22 |
| 3 | O1: 2D waveguide mode converter | optics | 1/2/3 | 0/2/3 | 1/2/3 | €0.22/4.38/61.38 |
| 4 | C2: Wall-mounted hump separation | CFD | 2/3/3 | 0/2/3 | 1/2/3 | €2.19/30.69/350.72 |
| 5 | S1: Friction-damper contact round robin | nonlinear structures | 0/1/2 | 0/1/2 | 1/2/3 | €0.88/8.77/70.14 |
| 6 | A2: Theatre treatment / room-acoustics benchmark | acoustics | 0/1/2 | 0/1/2 | 1/2/3 | €0.44/10.52/140.29 |
| 7 | S2: Large-stiffness-ratio contact deck | nonlinear structures | 1/2/3 | 0/1/2 | 0/1/2 | €0.44/5.26/52.61 |
| 8 | A1: Rigid-sphere control leading to finite-baffle family | acoustics | 0/1/2 | 0/1/2 | 0/1/2 | €0.44/8.77/122.75 |

Scores are conservative hypotheses, not evidence of a passed filter. No row currently passes a complete launch acceptance record.

## Case routes, one decision family at a time

### C1 — backward-facing step

Buyer-role hypothesis: duct/diffuser aerodynamic engineer chooses expansion geometry to trade pressure loss against separation. NASA/TMBWG provides nested grids and experimental wall and velocity-profile data for a fixed step case [N1]. The experimental reattachment position is reported as x/H = 6.26 ± 0.10; reported-interval low/base/high = **6.16/6.26/6.36**, with no confidence level inferred. Preserve the supplied inlet definitions and measurement normalization; do not silently merge Reynolds-number conventions.

Open route: OpenFOAM or SU2 RANS using a pinned source/build, then wall pressure, skin friction and velocity profiles. Build/container digest and output reductions: HUMAN_INPUT. The design bridge is a proposed step/diffuser family, with the published case kept as an anchor, not an exam full of memorized benchmark answers. Analytical loss correlations, coarse RANS, adjoint shape search and an amortized response map are mandatory competitors. Falsify the value hypothesis if they make the same admissible choices.

### C2 — wall-mounted hump

Buyer-role hypothesis: separation-control or internal-flow engineer chooses surface contour or a specified suction setting. The published hump case supplies geometry and experimental comparisons [N2]. NASA explicitly documents deficiencies of common turbulence predictions. This makes it a useful discrepancy witness, not a license to claim high physical accuracy.

Use an open RANS route with separate baseline and flow-control boundary contracts. Include endplate/blockage treatment, inlet development and model-form discrepancy in the evidence record. A geometry family may change the discrepancy. Industry correlations, coarse simulations, response surfaces and direct adjoint search are the cheap/solver-alone competition. No relabeling of a numerically converged but physically biased answer as physical truth.

### O2 — 3D periodic metagrating

Buyer-role hypothesis: diffractive-optics engineer chooses a periodic silicon pattern to maximize a desired transmitted diffraction order under fabrication and unwanted-order constraints. The MIT testbed includes patterns and a Meep FDTD script, and reports separate RETICOLO RCWA and Meep results [P2]. This is a genuine 3D periodic cell, even though its pattern is uniform through thickness.

Open reference route: Meep, with RCWA as the strongest cheap solver family. RETICOLO is a published comparator here; its redistributable executable rights are not established by the testbed license. Use an independently cleared open RCWA route before making it a required research-kit dependency. Grade normalized order-resolved flux, residual energy and convergence. Fabrication limits, dispersion, losses and applicable angle/wavelength ranges are HUMAN_INPUT. Published solver agreement does not establish fabrication agreement.

### O1 — 2D mode converter

Buyer-role hypothesis: integrated-photonics designer selects a pattern that trades transmitted mode power against reflection across a wavelength band. The MIT testbed defines the domain, dielectric constants, pixels, ports and graded quantities; its README and run script accompany design arrays [P1]. It is explicitly a 2D numerical job. Google's separate Ceviche challenge presets must not be mixed with these inputs [P3].

Meep/Ceviche provide open routes. Direct adjoint optimization is a formidable incumbent, and database designs or local response surfaces may dominate a narrow family. A fast model has to improve admissible designs after setup costs are charged, not merely approximate a field quickly. A 3D fabricated waveguide needs new thickness, dispersion, loss and manufacturing evidence.

### S1 — friction-contact round robin

Buyer-role hypothesis: turbomachinery joint/damper engineer chooses preload and contact layout for damping. The CC-BY article and dataset report contact hysteresis on steel specimens measured with independent rigs, and explain rig differences [S1]. This is measured contact-level evidence, not calibration of a full bolted assembly.

A CalculiX or PolyFEM route could reproduce representative contacts, but exact fixture reconstruction, material curves and file-level parsing are not established here. The article contains differing adjacent normal-load labels; freeze actual record metadata rather than silently correcting it. Jenkins/Iwan models and interpolation of measured loops are the strongest shortcut. If they settle the finite design grid, do not promote it as a neural-model Challenge. A nontrivial assembly bridge requires new justification.

### S2 — large-stiffness-ratio contact

Buyer-role hypothesis: compliant mechanism or contact-structure designer selects pad/part geometry under force and deformation requirements. The MIT PolyFEM data repository provides a contact JSON deck, inherited common settings and mesh paths [S2]. Its regression norms are numerical checks. A published systematic PolyFEM/FEBio comparison exists [S3], but this exact deck was not matched to its archived study results.

Pin the data and solver revisions, reconstruct free linear-solver dependencies, and preserve the deck's constitutive law and contact settings. Unit interpretation, buyer limits and an independent matched witness are HUMAN_INPUT. Contact FE alone is already an effective competitor. This is presently a verification rehearsal, not the requested complete physical validation family. FEBio TestSuite's asset license was not confirmed; do not inherit the solver license for its test data.

### A2 — theatre/room treatment

Buyer-role hypothesis: acoustic consultant chooses treatment placement and area for a named room. The CC-BY TCBO dataset advertises measured impulse responses, CAD and materials [A2]. The complete downloaded file inventory, source/receiver poses, absorption interpretation and parser are still HUMAN_INPUT; metadata alone does not establish a runnable benchmark.

An I-Simpa geometrical-acoustics route can be relevant in its stated frequency/geometry regime. Full-wave computation of the whole theatre is a materially different, potentially unaffordable job. Sabine/Eyring estimates, ray tracing and cached impulse/response maps are strong competitors. New treatments have no measured outcomes in the existing dataset. No claim about low-frequency wave behavior, transmission through structures or duct silencers follows.

### A1 — sphere control, then finite baffles

Buyer-role hypothesis for the proposed family: acoustic barrier/baffle engineer selects geometry for receiver-level attenuation. Mesh2HRTF/NumCalc supplies open BEM source, a rigid-sphere tutorial and analytical reference scripts [A1]. The tutorial and analytical script use different radii/source conventions; they are separate controls until explicitly reconciled. Some analytical scripts depend on an external toolbox/MATLAB; its rights and an open equivalent must be cleared rather than treating every supplied script as container-ready.

The sphere is analytically cheap and **fails the stand-alone design-value screen**. A finite-baffle family is a new proposal, with no physical witness identified here. Pressure phase/normal conventions, radiated power, energy balance, mesh convergence and treatment of resonances must precede value testing. This route cannot rescue f13's energy-accounting problem by assumption.

## Rights and completeness screen

| Route | Inspected evidence and rights | Remaining gap |
|---|---|---|
| NASA/TMBWG | Repository CC0; HTML cases, data text and nested-grid links inspected | Import and third-party asset attribution; executable witnesses NOT_RUN |
| Photonics testbed | MIT license; design/readme/script paths inspected | Mesh/time/flux convergence, open RCWA dependency, new-family validity |
| Friction round robin | CC-BY dataset/article; measurement description inspected | Archive-level checksums, fixture/material reconstruction |
| PolyFEM | MIT data; exact inherited deck inspected | Units and published independent witness for this deck |
| TCBO | CC-BY dataset metadata | Actual file manifest and reconstruction not inspected |
| NumCalc | EUPL-1.2 source/data repository | Analytical dependency rights and matched conventions |
| NAFEMS | Inspected catalog/member resource pages [R1] | No cleared unrestricted asset pack confirmed in this search |
| ERCOFTAC | Open-access classic collection descriptions [R2] | Each asset's license, inputs and reference data require inspection |

The last two rows are not claims that all NAFEMS or ERCOFTAC cases are unusable. Well-known and publicly viewable are insufficient rights tests. DTU's inspected room-impulse dataset is CC-BY-NC and the MIRACLE release is CC-BY-NC-SA [R3]; these are excluded from an unrestricted commercial research kit without additional permission. An analytically solved sphere or 1D wave control supplies verification value, not automatically commercial design value.

## First panel and bank-cost assumptions

Data Collection, if separately authorized, should first import each candidate's exact public benchmark, check source/license manifest and units, freeze all conventions and inspect a mesh/time/frequency refinement witness plus a physical/numerical reference comparison. Only then construct a small buyer decision panel, with interior feasible designs and boundary cases in every registered stratum. Counts, limits, accepted errors, sampling laws and k are HUMAN_INPUT. Do not relax them to generate feasible cases.

Separate fixed benchmark anchors from design-family holdouts. Split whole geometries/operating-condition groups before fitting cheap baselines. Record NONE_FEASIBLE, false feasible, false infeasible, selection regret and every reference failure separately. Compare the strongest source-based shortcuts at matched admissibility, then direct adaptive solver search against model-assisted search at equal total host cost using [equal-budget-design.md](../../../docs/development/challenge_pipeline/equal-budget-design.md). No solver runs are authorized by this document.

Startup estimate = equivalent complete-case count × allocated-host hours per complete case × hourly rate. All three inputs are **ASSUMPTION**. Count low/base/high = **32/64/128** including reference-bank and refinement/failure allowance; rate = **€1.37/1.37/1.37 per allocated host-hour**, retained as an owner planning basis, not a current vendor quote. Complete-case hours are:

| Candidate | Low/base/high host hours, ASSUMPTION |
|---|---|
| C1 | 0.03/0.2/1 |
| O2 | 0.01/0.08/0.6 |
| O1 | 0.005/0.05/0.35 |
| C2 | 0.05/0.35/2 |
| S1 | 0.02/0.1/0.4 |
| A2 | 0.01/0.12/0.8 |
| S2 | 0.01/0.06/0.3 |
| A1 | 0.01/0.1/0.7 |

Use whole panels rather than divide serial runtime by assumed cores. Scenario extremes are multiplied together, not probabilistic confidence intervals. Integration labor, file parsing, model training, the full equal-budget campaign and taxes are outside these startup-bank estimates. A cheaper numerical tier must be labeled as such. All base banks fit the assumed cap; several high banks do not. Measured C1/C2, image digests and buyer-value receipts are missing.

## Delivery and boundaries

KEEP: current packet/reference-credibility, value-bar and equal-budget contracts; existing negative evidence. No packet, optimizer, Challenge implementation, threshold, rights policy or launch status was edited. Research files and JSON were checked for structure, range arithmetic, source identifiers and whitespace; no scientific runtime result is earned. Hub impact: no authority, placement, dependency or maturity changes; the retired hub is not regenerated. Remaining adoption, population, tolerances and limits are owner/packet decisions.
