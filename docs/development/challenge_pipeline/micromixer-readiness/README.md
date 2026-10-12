# f17 finite micromixer readiness build

**DEVELOPMENT / preparation implemented, empirical reference NOT_DEMONSTRATED.**
No builds, physical solver runs, spend, hidden/AX42 data or runtime IDs. KEEP
[packet](../round1/f17-passive-micromixer.md), [question-law draft](../question-laws/remaining/f17.md),
[strong baseline](../cheap-baselines/f17.md), [optimizer](../optimizers/f17-passive-micromixer.md)
and [package specification](../solver-package-specs/f17-openfoam.md).

## Buyer decision and invariant envelope

The mock cartridge engineer chooses a full 10-mm passive herringbone channel
that maximizes worst-condition outlet mixing. Every one of flow 1/3/5 µL/min
× diffusivity 0.5/1/2×10⁻¹⁰ m²/s must meet mixing M≥0.8, pressure≤250 Pa and
fluid-volume/flow residence≤20 s. These are the packet's selected synthetic
DEVELOPMENT anchors, **not newly adopted production or clinical limits**.
No chemistry, reagent compatibility, assay yield or experimental performance
is implied. A good easy condition cannot offset failure at high Pe.

Actions remain depth 20–40 µm, pitch 100–250 µm, integer half-cycle 6–10;
base section 300×100 µm, groove width 50 µm, angle 45°, asymmetry corner
at one-third width, 10-µm wall clearance. `geometry_recipe` emits exact axial
stations and half-cycle labels for a **CAD draft**, not a validated watertight
recess model. DC must freeze the corner/orientation/endpoint convention,
Boolean recesses and patch names, check actual groove intersections and
clearances, compute fluid volume including grooves and retain mesh proof.
No unresolved drawing convention is silently adopted as valid reference CAD.
This preserves the finite scalar history, not a periodic remixed-cell surrogate.

## Preparation commands and physical accounting

```text
python -m carbon.challenge_pipeline.micromixer_readiness panel
python -m carbon.challenge_pipeline.micromixer_readiness decks
python -m carbon.challenge_pipeline.micromixer_readiness train
python -m carbon.challenge_pipeline.micromixer_readiness pilot
python -m carbon.challenge_pipeline.micromixer_readiness compare --public-export PUBLIC.json
python -m carbon.challenge_pipeline.onboarding readiness --challenge f17
```

All preparation commands print; none dispatches. Five diagnostic actions ×
nine conditions × two proposed rungs gives **90 scalar-case tuples**.
Unproved reuse: 90 flow + 90 scalar =180 starts. Proved passive flow reuse:
5 geometries×3 Q×2 meshes=30 flow starts +90 scalar=120, before controls,
setup, repeats, refinements and failures. Nine correlated conditions are one
geometry panel, not nine independent design questions. The 10/5-µm meshing
rungs are hypotheses, not demonstrated sufficient scalar resolution.

P_dev service mass and w_dev are separately recorded at 1/9; diagnostic Q
is extremes, nominal and refinement, not the future adopted P/Q/w question
law. Forward NONE_FEASIBLE is a valid buyer answer only from resolved full
bank truth; missing or inadequate references stay UNRESOLVED, without redraw.
T2(a) requires ≥5 feasible and ≥5 infeasible within **two accepted refinement
bands** per condition, plus a complete-all-condition feasible design, buyer-
unit spread and changing best answers. Five seed designs cannot establish
that. Do not reuse convergence targets as accepted uncertainty/near bands.

The two TRAIN actions ×nine conditions are physically different from this
panel regardless of rung/label. Registration, solved public TRAIN and complete
retained **and scheduled** reuse inventory are absent; no false zero reuse
discount. `kit_domain_check` requires all physical tuples, three observables,
finite scalar history and raw flux/concentration coverage. Passing the hook
does not register training or qualify the model/reference.

## Reference drafts and diffusion protection

OpenCFD **v2506**, commit `615aae61d7e95e110ca842ca105c799d10f59178`, is confirmed
by the [upstream release tag](https://gitlab.com/openfoam/core/openfoam/-/tags/OpenFOAM-v2506).
This is not Foundation OpenFOAM 13. Archive/dependency/base/image/store pins
are still missing. Source pages for some dictionary details were unavailable
at this preparation read; the existing package specification is the contract,
not proof that these drafts parsed or ran on v2506.

`deck_draft` emits transport, U/p/T, flow/scalar control and discretization
drafts. `T` means dimensionless concentration, DT is diffusivity, p is kinematic
pressure and nu=mu/rho. Equal inlets each carry half the total flow over half
the channel area. The quoted steadyState/scalar configuration, laminar dictionary
name, numerical tolerances and 1000-iteration ceiling are **DRAFT**: DC must
prove compatibility and stopping criteria on the frozen build. They are not
accepted numerical science. No CAD/mesh means HOLD even if dictionary text exists.

`flow_key` binds normalized geometry, Q, constant rho/mu, mesh, BC, image,
schemes, observer and a one-way-coupling proof. `require_flow_cache` demands
retained U, p and **phi**, plus the converged-flow receipt. Missing phi must
fail before stock `createPhi` could reconstruct it. Do not scale a solved
flow to another Q, change mesh or let c affect density/viscosity/forcing.
Matching metadata is not independent adequacy or permission. Compare reused
scalar to a fresh pair once before crediting saved starts.

`outlet_observer` reports raw positive axial-flux-weighted mean/variance and
M=1−sqrt(var/0.25), **unclipped**; a negative M stays visible. Backflow,
nonfinite c/phi or zero flux makes the observer inapplicable, never a failed
candidate by default. Convert Δp to Pa using pinned rho=998 kg/m³. Residence
is actual fluid volume/Q, not a residence-time distribution. Separate raw-c
bounds from model quality; no clipping to [-0.001,1.001].

`balances` integrates outward volume flux and **advective plus diffusive**
solute flux on all boundary faces, with storage if needed. Normalize by
nonzero incoming volume/solute, not net residual; zero-solute controls need
an approved absolute floor. The inherited ≤0.5% balances, ΔM≤0.02 and Δp≤5%
are DEVELOPMENT checks, not earned uncertainty. Boundedness cannot prove
absence of numerical diffusion. The distinct D=0 diagnostic is outside P;
mesh/scheme sensitivity at maximum Pe must show artificial mixing is below
an accepted band before judging M≈0.8. Retain raw fields and adverse findings.

[verification.json](verification.json) has fully developed duct, uniform scalar,
flow/scalar MMS, high-Pe/zero-D and cache-reuse specifications. The pure Python
manufactured-field functions and observer controls are headless and toy-tested;
DC implements and runs source injection/extraction **inside its pinned image**.
No installed OpenFOAM test or accepted MMS receipt is claimed here.

## Strong ordinary comparator, decisions and costs

The [published herringbone optimization study by Cortes-Quiroz and Zangeneh](https://bura.brunel.ac.uk/bitstream/2438/6877/1/MNF2009.pdf)
uses CFD, design-of-experiments/function approximation and multiobjective
optimization on mixing/pressure. It also discusses radial-basis methods.
It supports an ordinary response-surface competitor, not our selected
synthetic parameters, flux metric, calibration or clinical claim. The existing
cheap-baseline sheet's attribution of this particular URL is imprecise; retain
the method, use the paper's actual authors here.

`measure` implements a fixed linear-RBF profile on geometry/flow/diffusivity,
with **whole-geometry held-out folds (all nine conditions)**. Hyperparameters
are fixed before evaluation; no held-out label tuning. Exact closed-bank lookup
is the incumbent when all actions are already solved; it is not held-out
prediction. Out-of-fit coordinate ranges or insufficient resolved fit abstain.
No predicted concentration clipping, no favorable removal of hard strata.
Additional ordinary RBF profiles may be selected with nested fit-only validation;
this reproducible profile is not a declaration of the best possible surrogate.

Input format: closed `{challenge:'f17', scope:'PUBLIC_DEVELOPMENT' or
'SYNTHETIC_FIXTURE', rows, acquisition_cost}`; every row has normalized action,
condition, `{mixing,pressure_pa,residence_s}` and reference_status RESOLVED or
UNRESOLVED. At least five complete nine-condition geometries, no duplicates.
Producer reference status must come from accepted raw-field adequacy; this
comparator cannot repair or grant it. Acquisition cost must retain full
meshing/flow/scalar/refinement/failed-attempt ledger; absent facts stay unknown.

Reports include pointwise MAE in M/Pa/s, holdout identities, prediction and
reference coverage, abstentions, candidate screening order, separate fit and
query native CPU/wall timing and supplied acquisition cost. Retained verification,
memory and full measured € remain NOT_MEASURED, not zero. The candidate order
is a screen, not a feasibility verdict. `decision_report(report, registered)`
uses the **existing neutral tasks** commit/judge: all nine conditions, worst-M,
all three supplied hard requirements and explicit accepted bands, geometry-
digest candidate IDs and condition-digest IDs. It reports feasibility and exact
pick agreement, M regret, abstentions and unresolved coverage. Missing truth
does not become NONE_FEASIBLE; any missing fold prediction can abstain. It
refuses looser-than-packet requirements. No bands or truth are invented.

`micromixer_budget.proposal()` is additive #1047 half/base/double accounting,
2/4/8 **complete nine-condition design evaluations**, 2/4/8 wall-h and
32/64/128 CPU-h **ASSUMPTION** capacity. `equal_budget.compare` accepts its
own new identity, not historical EQUAL-BUDGET-V1. Every arm charges fit/setup,
screening and all flow/scalar, failed/refined/verification attempts. Per-start
acquisition ledger is still needed; one complete evaluation is not one launch.
No budget adopts a sampling law, qualification, campaign or grant.

## Conditional ≤€10 pilot and seven-item status

`pilot_plan` registers proposed exact control/nominal Q/D/rung tuples: developed
smooth duct; full grooved Q=5/D=0.5e-10 and 2e-10 on one flow; a fresh same-input
pair; 5-µm high-Pe refinement; D=0 control outside P. Six scalar starts and
four fresh flows =ten starts before MMS controls/repeats/setup/failures. No
reuse discount before proof. Complete nine-condition C1 remains UNMEASURED.

Carry prior p50/p95 **hypotheses** 0.75/4 CPU-h and 4/16 GiB, not measurements.
Pilot node-hour low/base/high ASSUMPTION 1/4/8 =>€1.37/5.48/10.96 at €1.37/h.
**High does not fit €10**, before extra charges. DC/owner must freeze an actual
quote, exact jobs/pins and all-in reserve/stop enforcement before any launch;
no auto-retry, no incomplete case claimed as a full C1. No grant exists here.
Return CPU, wall, peak RSS, allocated hours, starts, all mesh/extraction/setup,
repeat/refinement/failure costs and raw observer/reuse/verification receipts.

Items 1–5 remain PLANNED until actual main registration, current image/store,
accepted convergence/conservation/code verification, full kit and solved
disjoint TRAIN exist. Items 6–7 are implemented comparison preparation, and
may become YES only on inspected merged main; empirical V4 remains unmeasured.
No 7/7 or launch claim. Next action: **Data Collection** freezes/builds the
full finite reference package/CAD and runs the approved verification route
before requesting a bounded pilot. Owner/science retain requirements, law,
near bands, spend and acceptance. Infrastructure/reference failure never becomes
candidate scientific failure.
