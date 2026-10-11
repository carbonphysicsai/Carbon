# Cooling mock customer v2 — cell performance with a stated spreader input

**Role-play / DEVELOPMENT / SPECIFIED.** Prospective 2026-10-08 owner revision
under [OWNER-BATTERY-COOLING-PACKETS-02](../../../../.agent/decisions/2026-10-08-OWNER-BATTERY-COOLING-PACKETS-02.md).
The [v1 full-assembly packet](cooling-accelerator-manifold.md) and
[earlier feasibility proposals](customer-feasibility-revisions.md) remain
history/deferred assembly scope. This is **cell-only**, not a full cold plate
or manifold/composition task. The [v2 sheet](first-three-requirements-v2.json)
does not grant runtime registration or a solve.

## 1. Engineering job

I am the hypothetical accelerator-module thermal architect choosing channel
geometry and a supported flow action for an interior cooling cell. My heat
map describes heat **arriving at the cold-plate interface after a die-side
spreader or lid**, not raw die-source hotspots transplanted onto the plate.
I supply that spreader/lid definition; Carbon must not secretly buy thermal
headroom by changing my TIM, hotspot ratio or coolant inlet temperature.

| Buyer requirement / report | Why it matters |
| --- | --- |
| Peak spreader-side TIM-interface estimate <=85 C in the declared cell panel | Keep the selected thermal headroom at a precisely named interface, not an unmodelled die junction |
| Post-spreader interface heat map, total heat and stated spreader properties | Prevent an impossible raw-source assumption or arbitrary smoothing from becoming my input |
| Report TIM, post-spreader ratio and inlet alternatives without selecting them | Let the buyer see what hardware/operating change would buy margin |
| Separate cell pressure/flow/hydraulic quantities from full-assembly limits | Cell truth cannot certify headers, distribution, pump allocation or a full plate |

The v1 hypothetical $7,600 prototype/engineering redo and $48 lost-use event
explain why a false-cool prediction matters; they are **module-context
assumptions**, not measured cell savings. Report minutes/hours and cost per
verified cell shortlist; net dollar value remains HUMAN_INPUT until the
replacement workflow and actual costs are measured. Do not sell a cell pass
as a qualified accelerator or full-assembly design.

## 2. Physical system

KEEP the periodic conjugate cooling-cell scope and material/coolant
applicability boundaries in [cold_plate](../../../../carbon/cold_plate/domain.py).
Improved geometry proposals/evidence have their own versions; v2 does not
change their CAD or prove every design feasible. Cell inlet/outlet and
transverse-periodic conventions remain explicit. No full-plate edges,
manifolds, cross-channel maldistribution, turbulent/boiling/fouling or die-
junction model is introduced.

Buyer inputs must state spreader/lid geometry/thickness, material conductivity
(including anisotropy/temperature law where used), contacts/interfaces, raw
source layout/load, the post-spreader heat-map plane, flux normalization and
the characterization/model provenance linking them. Missing properties are
**HUMAN_INPUT**, not guessed copper, an ideal isothermal lid or free spreading.
Accept a separately characterized interface map only within its stated scope;
this packet neither builds a spreader solver nor infers one from a ratio.

## 3. Population P, Q and w

Customer-recognizable planning contexts remain cold uniform, typical load,
warm uniform, warm central hotspot and warm outlet-side hotspot. In v2 every
nonuniform map is specified **at the post-spreader cold-plate interface**;
the source/lid definition and resulting flux map are buyer inputs, not design
actions secretly optimized by the model. Do not choose ratio, TIM or inlet
from alternatives after seeing which one passes. Freeze each scenario first.

The complete panel, supported maps and P_job/Q_job/w_job registration remain
HUMAN_INPUT in [question-law v2](../question-laws/proposals-v2.json). Preserve
separate population, near-limit diagnostic enrichment and diagnostic weights.
Report each stratum; a uniform pass cannot average away a hotspot breach.
Unsupported reduced-supply flow stays excluded/unresolved, never clamped.
Service/input alternatives are separate clearly labelled sensitivity results,
not additional equivalent questions or fresh bank exposure.

## 4. Case contract

Bind geometry/flow, coolant/material laws, interface plane, spreader properties/
source/map provenance, total heat, normalized local flux, TIM areal resistance,
inlet, mesh/solver/observer and dimensional scaling. Validate map integral and
units; source and post-spreader maps are not interchangeable identifiers.
Include each alternative's actual inputs, do not retain the original case ID.
No hidden EVAL/STRESS/quiz/tuning cases are exposed by a map revision.

Missing spreader or supported interface-map identity makes the affected case
UNRESOLVED; it is not a false prediction attributed to a candidate. A changed
spreader/heat map or material law needs prospective reference work; threshold-
only reuse is allowed only for identical covered physical observables.

## 5. Reference policy

KEEP pinned OpenFOAM conjugate-cell reference and applicable conservation/
refinement controls. Demonstrate local thermal and cell-pressure convergence
on the improved geometry and post-spreader map. Numerical agreement is not
physical adequacy or a granted solve. Reference failure/FAILED_INFRA never
becomes candidate failure.

Target **Tier2** matching of the assumed buyer Ansys Fluent/Icepak cell
workflow, not Tier1 (same tool/settings) or earned laboratory credibility.
Keep v1 published conjugate-transfer benchmark candidates as verification
rungs, then compare matched periodic-cell uniform/nonuniform/warm cases with
identical post-spreader maps/TIM conventions. Acceptance remains HUMAN_INPUT
with the existing recommendations (1-C thermal difference, 5% nonzero cell
pressure/power difference, separately accepted absolute near-zero floors).
Report pointwise and feasibility/best-pick agreement/regret together under
the [common credibility contract](reference-credibility.md), using separate
non-hidden draws or verified retired published cases. NOT_DEMONSTRATED;
“matches the reference simulator” only after accepted evidence, never reality.

## 6. Output and measurement contract

The thermal quantity is
`max_x [T_cold_plate_heated_face(x) + R_TIM(x) * q_interface(x)]`.
Use local **post-spreader** q in W/m2 and areal R in m2*K/W at the same
interface coordinates; the increment is K. This estimates the **spreader-
side TIM interface**, not die-junction temperature. Do not add a second lid
temperature drop if the supplied map/temperature convention already includes
it, or combine a mean flux jump with an unrelated plate maximum. Retain maps,
local fields, extrema coordinates, total-power/heat-balance checks and scope.

Report cell pressure drop in Pa at pinned stations, flow in its declared
cell/physical scaling, and hydraulic power only with that consistent scaling.
The v1 full-assembly 50 kPa / 2.5 W / 3 L/min values are context, **not adopted cell
limits**. #776's 20/25/30-kPa cell allocations/objective remain HUMAN_INPUT
recommendations. Freeze cell constraints/objective/ties before a future task.
No full-cold-plate solve or composition witness is part of this ticket.

For each TIM/ratio/inlet alternative retain its own input identity, peaks,
thermal margin, flow/pressure burden and unresolved coverage. **No alternative
is selected.** A complete settled bank with no hard-limit pass yields
NONE_FEASIBLE; missing map/reference support yields UNRESOLVED instead.

## 7. Construction contract

KEEP reconstruction, permitted TRAIN provenance and existing Interface-v1
adapter. Prospective post-spreader conditioning/observer projection needs an
owning versioned implementation; no extra runtime input or new geometry
permission is installed here. Commit proposed geometry/flow before truth;
the candidate does not choose the heat map that makes it look admissible.

## 8. Research kit

Reuse public cell generator/reference packaging and analytical controls.
Publish the interface convention, buyer-input requirements and alternatives
reporting rules. Own-seed research receives no protected maps/seeds/labels.
Offline models replace first-pass **cell** sweeps, not coupled full-plate
verification or a datacenter controller. V1 assembly throughput figures are
not cell measurements; cell end-to-end cost and speed remain UNMEASURED.

## 9. Evidence plan

Owner-reported source `3ab30becb6dcee0a2ec43272883c2800fb32a64a`,
`cooling-feasibility-02/`, 128 solves: uniform best 81.2 C is feasible in that
stratum, while every reported hotspot is >=117 C. At ratio 3 the stated
`R_TIM*q_local` jump is about 25 K; `85-45-25=15 K` available plate rise is below
about 28 K best plate rise. These approximate components explain pressure to
revisit the **interface input**, not a calculation reproducing 117 C or proof
of any feasible post-spreader hotspot. Codex did not rerun these cases.

Forward [Q2/Q3 impacts](../question-laws/quiz-impact-v2.md) require new map/
observer identities and complete supported truth. Keep edge-optimist,
over-cautious, local sign-error and optimizer/lattice-aware controls with
phase/coordinate-correct quantities. Near-limit refinement is producer-owned
under separate authority; no validator reference solves. Report false-feasible
and missed designs, cell-pressure regret and thermal margin by stratum.

## 10. Readiness and claim record

KEEP cell assets, v1 history and six unaffected question laws. NEW selected
heat-map plane and explicit buyer-input contract. GAPS: characterized spreader
properties/post-interface maps, their supported distributions, numerical/
model-form reference adequacy, v2 task/quiz integration and cell allocations.
These are SPECIFIED requirements; document tests do not establish hotspot
feasibility, whole-panel acceptance, Tier2 or a physical cooling claim.
Test Lead/Carbon Validator/PR Lead coordinate on #643, science on #42. Full
cold plate is out of scope; Battery EV5/journal14/live contract are untouched.
