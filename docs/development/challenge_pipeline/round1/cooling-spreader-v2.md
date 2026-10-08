# Cooling v2 spreader proposal and feasibility panel

> **Panel hold after the 2026-10-08 budget review:** read the
> [thermal budget](cooling-thermal-budget-v2.md) before any of the 53 jobs.
> The existing 85-C limit is at TIM2, not the die junction. Temperature-plane
> confirmation and a reviewed budget showing possible feasibility with an
> uncertainty allowance are required; no release is recorded.

**Mock buyer / DEVELOPMENT / SPECIFIED; owner approval pending.** Supplement
to [Cooling cell v2](cooling-cell-v2.md), not a new full-plate task or a claim
of hotspot feasibility. All stack choices, ranges and numerical acceptance
below are **HUMAN_INPUT recommendations**. The [panel sheet](cooling-spreader-panel-v2.json)
has no accepted pins or execution authority.

## 1. Buyer input stack

I want an interior cooling-cell shortlist for a stated accelerator lid and
mounting stack. I supply the package inputs before Carbon searches channels.
The cell design may not choose a thinner TIM, colder inlet or different die
map to obtain a pass. The85-C criterion remains the **lid-side TIM2 interface**,
not die junction. Die-side temperature is a diagnostic that prevents hiding
a large upstream drop, not a newly adopted junction limit.

| Input | Recommended first set | Range for separately identified sensitivities | Buyer reason |
| --- | --- | --- | --- |
| Lid | C11000 copper, isotropic constant k=391 W/(m K) | Copper k=380–400 W/(m K); no unsupported anisotropic default | Spread local heat without assuming an isothermal lid |
| Lid thickness | 1.5 mm | 1.5–3.2 mm | Trade package height against spreading; not a guaranteed monotone improvement |
| Heated/lid footprint | 30×30 mm, registered axial band source | 30×30 mm in this cell panel; 31–40-mm package footprints are future geometry, excluded here | Match the current heated footprint, not silently gain unmodelled area |
| TIM1, die-to-lid | Pure indium foil class, nominal100 um; effective joint R1''=5.14e-6 m2 K/W | Thickness100–150 um; R1''=4e-6–8e-6, each a separate joint hypothesis | Include die-side contact resistance and mount sensitivity |
| TIM2, lid-to-cell | PTM7950-class phase-change material; supplied0.2 mm, conditioned effective bond line25 um; R2''=6e-6 m2 K/W | Supplied0.2–0.5 mm; conditioned25–50 um; R2''=4e-6–8e-6 | State the actual heat-transfer joint rather than treating a thick supplied pad as its final bond line |

The conditioned bond line and R'' are **paired input hypotheses**, not
independently uniform ranges. The minimum bulk t/k contribution must not
exceed the proposed total joint resistance. For example,50 um at8.5 W/(m K)
already contributes5.88e-6 m2 K/W: it cannot be paired with a4e-6 total joint.
R'' includes both contacts and bulk. A zero-thickness effective-contact model
uses R'' once; an explicit TIM mesh uses t/k plus only the residual contacts.
Do not add both the full R'' and t/k. Nickel/coating/roughness effects are
included in a characterized joint or explicitly pinned, never assumed free.

Published examples, **not modern accelerator specification claims**:

- Gwinn and Webb's primary paper describes a **31-mm-square,1.5-mm copper
  IHS** on the Pentium4 and nonuniform heat flux despite spreading.
  [Performance and testing of thermal interface materials](https://www.sciencedirect.com/science/article/pii/S002626920200191X).
- A primary heat-spreader study varies copper thickness **1.6–3.2 mm** and
  chip side10–30 mm. That is an immersion-cooling study, not this PG25 cell.
  [Thermal performance and stress analysis of heat spreaders](https://www.sciencedirect.com/science/article/pii/S1359431120334669).
- Indium's brochure distinguishes TIM1/TIM2 and lists pure indium k=86 W/(m K),
  **0.0514 cm2 K/W at0.004 inch and100 psi** (101.6 um, about0.69 MPa).
  This converts to5.14e-6 m2 K/W; it is a supplier test joint, not a validated
  silicon-to-lid joint or a prescribed chip clamping load.
  [Indium thermal-interface brochure, p3](https://www.indium.com/wp-content/uploads/2025/08/TIMs-Brochure-99342-A4-R4.pdf).
- Honeywell's AI/HPC note lists PTM7950 k=8.5 W/(m K), no-shim impedance
  **0.04–0.08 cm2 K/W**, supplied0.2–0.5 mm and typical25-um bond line at
 30 psi/60 C. Its table also has a distinct38-um best-performance column;
  these are test conventions, not a universal compression law. The6e-6
  recommendation is the impedance interval midpoint. Cold/unconditioned
  joints are not covered by conditioned numbers automatically.
  [Optimizing AI Systems, p7](https://prod-edam.honeywell.com/content/dam/honeywell-edam/pmt/oneam/en-us/electronic-materials/thermal-interface-materials/documents/hon-ess-adm-optimizing-ai-systems-tim-pcm.pdf).

Copper k=391 reuses Carbon's stated C11000 fixture, not a newly measured lid
law. No proof of adequate mounting pressure, contact aging, void fraction,
flatness or die mechanical safety is supplied. Those properties need buyer
and reference-owner approval/characterization. The proposed lid is **additional
to**, not a renaming of, the cell's existing0.5-mm channel cover. Larger lids,
transverse die islands, heat loss into a package/substrate and full-plate edges
remain outside this first cell panel.

## 2. Produce the post-spreader map without guessing a ratio

Pin a steady conduction pre-solve of `div(k grad T)=0` in the lid. First route:
axial2D (flow x, thickness z), with a raw Gaussian band plus uniform floor,
uniform across channels. Side ends are adiabatic. Normalize the raw map's
integral to the declared footprint power **before** solving. There is no
volumetric heat generation or unreported lateral/substrate heat loss.
TIM1 lies between the prescribed source and lid; it gives the die-side jump
and does not independently smooth a prescribed flux. A finite die/source-
temperature problem would be a different, coupled source contract.

At the bottom use the candidate's span-mean heated-face temperature and
TIM2 contact law:
`q_interface(x) = [T_lid_bottom(x) - T_cell_face(x)] / R2''`.
Start with a pinned preliminary cell-face estimate, solve conduction, transfer
the resulting flux conservatively to the cell and recompute the cell. Iterate
under a fixed, pinned algorithm until both map and interface temperatures
meet the registered coupling criteria. Recommendation: under-relaxation0.5,
maximum20 iterations; exhaustion is REFERENCE_UNRESOLVED, not a candidate
failure. Record every pre-solve/cell invocation and cost. **No fixed isothermal
bottom or single geometry-independent map is accepted as truth.**

The axial reduction discards transverse surface variation. Verify it against
a **3D lid coupled to one repeating cooling cell**, with identical source,
contacts and symmetry/periodic boundaries. This witness is not a full plate.
If decision agreement fails or transverse effects exceed accepted uncertainty,
use the repeating-cell coupled route or declare the affected cases unresolved;
do not flatten the witness to make the cheap route pass.

Current `carbon/cold_plate/domain.py` accepts only a normalized axial Gaussian
via ratio/centre/width. A conduction solution generally is **not** that family.
Data Collection must package a prospective, versioned tabulated-flux boundary
and extraction route before execution. Do not fit a Gaussian, lower its peak,
or clip reverse flux as an undocumented map replacement. Unsupported signed
flux or temperatures outside PG25's30–99-C validity stay unresolved.

Pins required in a producer-owned manifest: source-map version/content hash;
stack/contact/material law and units; geometry/area/periodic scaling; conduction
source/build/image/linear-solver identity; mesh and refinement; coupling code,
initialization/tolerances/iteration cap; map coordinates/interpolation/area
weights and hashes; cell geometry/flow/reference/observer identities; retained
lid and cell fields, timings, memory and typed failures. **Accepted pins null.**
Recommend reusing the acquisition lane's Elmer26.2.1 target for solid conduction
and the owning OpenFOAM cell package; neither a version string nor f02's package
alone is an accepted map/coupling feature receipt.

The post-spreader map is bound to its source, stack **and cell design/boundary**.
It is not a buyer-selected favorable map. A future common-map approximation
would need a registered witness and conservative error budget first. Publish
the public generator/stack/transfer contract for research, never realized
protected maps or labels. Q2/Q3 need prospective map and observer identities;
the Cooling question thresholds, P/Q/w proposals and optimizer remain unchanged.

## 3. Verification and uncertainty

Before the panel, verify: zero-power constant-temperature control; uniform
1D stack (each jump qR'' and copper qt/k); a cosine/Fourier conduction control
with the same boundary law; interface orientation/contact signs; conservation
under fine-to-coarse and coarse-to-fine map transfer. A solver completing is
not verification. Retain power at each interface and absolute error near zero.

HUMAN_INPUT numerical recommendations: energy discrepancy<=0.1% of nonzero
load (zero-load absolute floor1e-6 W **per modeled periodic cell**); uniform
control temperature error<=0.05 K; mesh/map refinement and coupling each
<=0.1 K in the final TIM2 peak, coupling flux change<=0.1% in registered L1
norm. Use three rungs with axial near-hotspot spacing0.25/0.125/0.0625 mm and
8/16/32 through-lid cells, plus independently refined cell meshes. They are
verification targets, **not certified error bounds**; check observed order
and further refine if the ladder is not asymptotic.

Carry source-map uncertainty, conductivity/contact variations, numerical
conduction/map/cell errors, coupling residual and axial-reduction discrepancy
**jointly** through the composed quantity
`max_x(T_cell_face(x) + R2'' q_interface(x))`.
Retain pointwise correlated fields and coupled sensitivity evaluations; do not
add independent p95 errors or maximize T and q at unrelated coordinates.
Owner selects admissible parameter uncertainty/support, not these literature
ranges as probabilistic confidence intervals. If no defensible composed
interval exists, the feasibility verdict is UNRESOLVED. Entire interval<=85 C
is verified feasible for this thermal criterion; entirely above85 C is
infeasible; an intersecting interval needs refinement or stays UNRESOLVED.
Any other adopted cell constraint must also be settled before a design pass.

Against the buyer Fluent/Icepak route, report pointwise differences **and**
feasibility agreement, best-in-bank pick agreement and bidirectional regret in
cell pressure Pa/thermal K under identical requirements. Recommendation for
the total composed thermal discrepancy remains<=1 K, not1 K per component;
decision-agreement thresholds stay HUMAN_INPUT. Use separate non-hidden draws
or retired published cases outside the producer's custody, never hidden
EVAL/STRESS/quiz/tuning. Reference disagreements trigger future versioned
reference revision, not candidate penalties or silent historical rescoring.
[Common credibility contract](reference-credibility.md). Tier2 is a target,
not earned; no reality claim.

## 4. Data Collection feasibility panel

Freeze the sheet's **six geometry actions × five source/service contexts =30
base cases** only after owner stack approval and package/support entry checks.
Use the improved straight-channel proposal from #758: widths0.2/0.3/0.5 mm,
fin0.3 mm, depth3 or6 mm, base0.5 mm; existing channel cover0.5 mm. All are
new proposed grammar values, not legacy-reference defaults. Pair each design
with all five contexts:30-C/500-W uniform,40-C/1000-W uniform,45-C/1500-W
uniform, and45-C/1500-W ratio3 central/outlet axial bands (centre15/24 mm,
width2.5 mm). The ratio3 describes **raw source**, never the solved interface.
Flow is2 L/min/kW (1/2/3 L/min scaled context totals); retain per-cell actual
area/absorbed heat and exact tiling factor. No manifolds/edge-heat claim.

Add **five verification controls**, **six declared difficult base cases at
two extra refinement rungs (12 jobs)**, and **six repeating-cell coupled
witnesses**. That is53 logical case/control jobs, **not53 solver launches**:
coupling, mesh, refinement and witnesses can each require multiple invocations.
No automatic retries or failed-case replacement. Refinement/witness choices
are frozen by the sheet before outcomes; these sensitivity contexts are Q,
not a measured deployment P. Stack sensitivities outside this base recipe
need separately recorded panels/grants; no TIM/ratio/inlet alternative is
adopted here. A complete settled all-fail panel says NONE_FEASIBLE, not redraw.

Return exact approved inputs/pins and case manifest; raw and post maps with
integrals/peak ratios, fields and coordinates; both TIM jumps and diagnostic
die-side peaks; thermal intervals and cell pressure/flow/regime checks;
feasible/none/unresolved per design/context; numerical and coupled-witness
discrepancies including decision effects; setup/mesh/each solve/transfer/
extraction CPU and wall time, peak RSS, all failures and charged attempts.
**No runs or spend are authorized by this sheet.** Acquisition/Data Collection
provide immutable packages and a bounded execution request first. No hidden
material, full cold plate, prototype purchase or qualification is included.
