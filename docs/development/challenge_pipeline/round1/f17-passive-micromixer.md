# f17 — passive micromixer cartridge, customer round 1

Authority and numeric source: [index](README.md), [sheet](requirements.json).

## 1. Engineering job

Hypothetical lab-cartridge engineer: select a passive groove geometry maximizing
worst-condition outlet uniformity, targetM≥0.8, while pressure drop≤250 Pa and
mean hydraulic residence≤20 s. Wrong decisions yield inconsistent reagent
delivery or pump burden. No chemistry, reaction yield, cell viability, clinical
claim or manufacturing/reagent compatibility qualification.

## 2. Physical system

300×100-µm base channel,10 mm axial length, two equal-flow side-by-side inlets
concentrations0 and1. Bottom staggered-herringbone recessed grooves:
depth20–40 µm,width50 µm,pitch100–250 µm,45° angle, asymmetry corner at1/3 width;
reverse orientation every6–10 grooves (integer). Groove ends stop10 µm before
sidewalls. No-slip walls, zero solute wall flux, prescribed equal inlet flux,
outlet pressure0. Synthetic Newtonian rho998 kg/m³,mu0.001 Pa s; total flow
1,3,5 µL/min; D=0.5,1,2×10⁻¹⁰ m²/s. Independently solve and charge laminar
velocity before steady passive-scalar transport. No unpriced velocity oracle.

## 3. Population P, Q and w

Geometry is an action; reference-input geometry law is uniform valid parameters.
Exogenous `P_dev` is uniform over the3×3 flow/diffusivity conditions, w=1/9 for
a later complete decision panel, with worst condition separately mandatory.
Q feasibility: nominal groove geometry at all nine conditions plus controls
and refinement as caps permit. These shared conditions do not establish a
customer fluid distribution or population reliability. High-Peclet behavior
is explicitly reported, not filtered out as an inconvenient case.

### Prospective population of buyer design questions — `HUMAN_INPUT`

The three flows by three diffusivities are one cartridge operating panel.
A future `P_job` can vary supported outlet-mixing, pressure-drop or residence
limits and required throughput subsets against one fully solved groove bank.
A lab-instrument buyer recognizes each question from its assay uniformity,
pump and throughput acceptance sheet. Re-evaluating stored flow/scalar outputs
needs no new solve if the whole requested panel is covered and the preferred
groove demonstrably changes. New fluids, inlet chemistry or port interfaces
are optional axes that may need new flow/scalar references. Outlet pixels,
flow probes and solver seeds are not fresh questions by themselves.

**Size recommendation, not a selected law:** catalogue eight distinct
condition/requirement questions for a development scoping pilot on a
reference-covered bank. `HUMAN_INPUT`: eligible requirements and panels,
`P_job`, protected `Q_job`, weights, answer diversity, shared-assay clustering,
exposure and power-justified hidden `n`. The complete 3 × 3 panel stays
mandatory for any question that claims that service envelope.

## 4. Case contract

Bind CAD, grooves, fluid/transport law, inlet profiles, units and outlet plane.
Reject intersecting grooves, invalid inlets/mesh, backflow incompatible with
the specified scalar outlet and nonpositive flow/diffusivity (zero-D is an
explicit numerical control outside P). Own-seed public identities never bind
or reveal later protected draws. Missing velocity evidence blocks transport use.

## 5. Reference policy

OpenFOAM steady laminar flow plus passive scalar transport; pin build/image/
license, groove mesher, pressure/velocity convergence and scalar discretization
before dispatch. [The official scalar transport implementation](https://api.openfoam.com/2506/scalarTransportFoam_8C.html)
states the equation; [boundedness guidance](https://doc.openfoam.com/2306/tools/post-processing/function-objects/solvers/scalarTransport/)
motivates checking numerics. The [original grooved-channel study](https://pubmed.ncbi.nlm.nih.gov/11809963/)
supports geometry motivation, not the selected synthetic parameters or adequacy.

Controls: smooth rectangular channel with analytical pressure/diffusion and a
zero-D numerical-smearing case. Mass/solute balance≤0.5%; pointwise concentration
in[−0.001,1.001]; independent mesh refinement ΔM≤0.02 and Δpressure≤5%.
Require a resolved scalar boundary-layer/refinement witness at maximum Pe;
boundedness alone cannot establish low artificial diffusion. Keep raw c and
variance; no clipping/renormalizing to pass. 40 launches/8 node-hours/$25 caps
include velocity and scalar jobs separately: nine primary pairs consume18,
leaving22 for controls/refinements. Failure/exhaustion leaves unresolved evidence.

### Reference credibility target

**Buyer tool:** COMSOL Microfluidics Module is the assumed cartridge designer's
laminar-flow/passive-transport workflow, not verified market share. **Carbon
reference:** proposed OpenFOAM flow plus scalar transport, **not the same
tool**. Cooling's OpenFOAM build alone is not this groove/transport reference.
Tier 1 requires the buyer's exact tool, fluid, geometry, inlet and observer settings.

**Target tier:** Tier 2 for offline cartridge design against simulator outputs.
Tier 3 calibrated dye/fluorescence and hydraulic measurements would be needed
before claiming real-cartridge mixing; no chemistry/clinical validation is
implied. **Credibility evidence: NOT_DEMONSTRATED** for this task.

**Benchmark cases:** COMSOL's published
[Split and Recombine Mixer Benchmark](https://doc.comsol.com/6.3/doc/com.comsol.help.models.mfl.split_recombine_mixer/split_recombine_mixer.html)
and [Micromixer](https://doc.comsol.com/6.3/doc/com.comsol.help.models.mph.micromixer/micromixer.html),
with their exact geometry/inlets/transport law reproduced in both tools.
Their mixing measures/geometry are not automatically this packet's groove
law or positive axial-flux weighted M. Add matched smooth-channel controls
and grooved maximum-Péclet/flow-extreme witnesses; compute the **same** outlet
mean/variance/M from both raw fields and check artificial diffusion independently.
Never compare an area-weighted tutorial score directly to the flux-weighted buyer score.

**Acceptance tolerance: HUMAN_INPUT.** Recommend absolute outlet M difference
≤0.02, pressure-drop difference ≤5% at declared nonzero flow, and mean hydraulic
residence difference ≤5% using identical fluid volume/flow definitions. Absolute
near-zero pressure floors remain HUMAN_INPUT. Retain concentration/flux/balance
checks and refinement above; bounded concentrations or coincidentally similar
M can both conceal numerical smoothing. These are simulator-agreement targets,
not reaction yield or laboratory fluid-property evidence.

**Claim boundary:** [common credibility contract](reference-credibility.md).
After accepted evidence, “matches the reference simulator” for the specified
laminar passive transport, not “matches reality”, reagent performance or assay quality.

## 6. Output and measurement contract

At x=10 mm, positive axial-flux weighted c mean/variance; inlet variance0.25.
M=1−sqrt(variance_out/0.25), without clamping; negative M is a visible failure,
not a favorable score. Report solute/volume flux, pressure drop and concentration
field. Mean hydraulic residence=fluid volume /total volume flow, including
grooves; this is not an arrival-time distribution. Backflow invalidates that
outlet measurement unless separately specified. All nine conditions must meet
constraints; missing reference evidence cannot be imputed as success.

## 7. Construction contract

Prepared Level-0 target: deterministic declarative transport ROM/surrogate using
public permitted TRAIN; exact vocabulary, training limits and data grants await
their ticket/budget study. No arbitrary code, solver-grade authority or hidden
state in a model's reconstruction/prediction environment.

## 8. Research kit

Own-seed generator/reference, diffusion-scaling/smooth-channel/network/transport
ROM baselines, outlet/flux docs and incomplete public practice. Reuse OpenFOAM
and evidence packaging patterns from Cooling, not its fluid/steady truth or
metrics. Protected cases, labels and seeds stay operator-side.

## 9. Evidence plan

Control numerical smoothing before broad learning. Preregister whole-geometry
holdouts, common outlet sampling and equal charged flow+scalar budgets. Show
whether cheap mechanistic models already make the same decisions; do not
reshape the task to manufacture learned advantage. Fresh confirmation, dye/
fluorescence observation calibration, rights and training-budget study are later
contracts, not this reference-feasibility allowance.

## 10. Readiness and claim record

**Before any new hidden bank:** the owner-selected [four-check value prerequisite](../question-laws/value-check-v1.md)
requires per-stratum discrimination and meaningful buyer-unit spread, one
complete feasible action, and changing best/equivalent answers. Numeric
thresholds remain HUMAN_INPUT recommendations; receipt **NOT_DEMONSTRATED**.
For this buyer, report flux-weighted M, pressure and residence margins on the complete flow/diffusivity
panel; artificial scalar smoothing cannot supply value.
No favorable redraw, exposure reset, solver grant or qualification follows.


Selected requirements and smooth-channel dimensional screens only. Groove flow/
transport and reference adequacy NOT_DEMONSTRATED. Next: exact CAD/inlets/
extractor and analytical/numerical-diffusion controls under stage permission.
No cartridge experiment, assay quality, clinical use, qualification or launch.
