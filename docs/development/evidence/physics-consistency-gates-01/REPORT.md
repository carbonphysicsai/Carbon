# PHYSICS-CONSISTENCY-GATES-01 — research recommendation

**RES-06 · 2026-10-12 · DEVELOPMENT PUBLIC EVIDENCE · NOT QUALIFIED**

## Owner summary

Physics checks can cheaply reject impossible or internally inconsistent
predictions between reference cases. They complement reference accuracy and
screen-then-verify decision evidence. A model can obey a law while predicting
the wrong feasible frontier, so compliance cannot certify design safety or
replace independent verification.

For battery, first test **temperature causality during the shared initial rest**: at the
same initial SOC and ambient temperature, predictions before charging starts
must not depend on future charging rates. This uses today's voltage/temperature
outputs and needs no new solver call. Preserve the existing inventory,
initial-state, controller and repeat checks. Do **not** hard-gate signed plating
margin, generic temperature-above-ambient, monotone capacity fade or heat versus
current across whole protocols.

Charge balance is only partly observable from a CC protocol. Known current
allows an external charge integral on an interval known to remain CC, but the
current outputs contain no cumulative-charge or SOC/inventory trace to compare
with it. Four per-cycle discharge capacities are different measurements. The
CV current and stage times are not supplied. Thermal and electrochemical energy
balance also lack independently predicted terms. Genuine balance gates require
a prospectively versioned output contract.

For motor, investigate zero-current **mean cogging work**, without mistaking
loaded torque for a conservative zero-work curve. For cooling, retain peak/
profile, passive-temperature and pressure checks; derived outlet temperature
does not independently verify conservation. For f02, use source-order checks and
convexity of a peak under power interpolation; a peak is **not linear** even
when the temperature field is.

**Measured:** all 100 real EV4 CPU rebuilds violate rest-voltage invariance by
65–397 mV at their worst public development condition (median 208 mV). Its
association with decision loss is weak (tau-b 0.040 on six common resolved
questions). Do not adopt it immediately as a launch hard gate: it would reject
the entire existing real cohort. At the declared research temperature-prefix
floor, all 100 pass while the boundary-optimist control fails. The localized
plating sign-error control passes both prefix checks and makes four unsafe
development choices. A constructed repair makes the boundary optimist pass the
prefix and below-ambient diagnostics while preserving all eight unsafe choices.
These are descriptive measurements, not production thresholds.

Recommendation: prioritize a public causality/structure panel, keep conditional
properties diagnostic until proved for the exact model, and specify new balance
outputs only if their incremental decision value merits the cost. All new gate
tolerances, sample allocations and adoption are **HUMAN_INPUT**. This PR changes
no runtime gate, score, Challenge packet or scientific claim.

## 1. Meaning of a physics check

Use [SOURCES.md](SOURCES.md) for pinned repository links R01–R31 and primary
sources S01–S18. Exact historical constants and measured counts have
low=base=high; this records their provenance, **not** a confidence band. Proposed
numbers are labelled ASSUMPTION with ranges. Unknown bounds stay HUMAN_INPUT.

There are four distinct conclusions:

1. **Observable law:** an identity/inequality follows from the registered model
   and can be evaluated from its current predictions plus declared inputs.
2. **Conditional property:** a proof also needs a sign, coefficient, domain,
   boundary or controller assumption not yet established for the entire family.
3. **Contract consistency:** an arithmetic reduction, schema or determinism
   check is useful but is not independent physical validation.
4. **Not observable:** a law exists, but the output interface cannot identify its
   residual. A value derived from the same prediction cannot supply its missing
   independent side.

The correct prediction of an infeasible design is evidence of model usefulness,
not a violation: negative plating margin, high temperature and insufficient
torque are admissible predictions. Candidate fault, reference failure,
applicability failure and unsupported measurement remain separate (R01/R02/R11/
R25). The exam must itself be qualified before it qualifies models. This report
does not change R09's **NOT_MEASURABLE** physics score.

## 2. Battery: laws, observability and solver-free tests

The current input is `(c1,c2,t_amb_c,soc0)`; outputs are voltage and volume-average
temperature over the first hour, cycle-one minimum plating overpotential, and
discharge capacity at cycles 1/10/20/30 (R03/R04). Current and total heating are
held by the reference during extraction but are **not model outputs**. No
mechanical stress is predicted.

| ID / property | Why and exact scope | Cheap test; current observability |
|---|---|---|
| B1 — initial condition | At the declared equilibrium initial state, voltage matches the parameter-set OCV and temperature matches initial ambient (R04/R05/R07). | Query any valid input, including interior inputs; check first trace entries with the existing calibrated allowances. **Observable now; already gated.** This checks initial state, not charge conservation. |
| B2 — discharge-capacity bounds | A positive discharge-step integral cannot exceed the declared electrode/lithium inventory (R04/R05; S02/S06). | Check each checkpoint against zero and the existing parameter-set bound. **Observable now; already gated.** Existing exam uses strict `Q>0`; do not generalize that to arbitrary cells or empty discharge steps. |
| B3 — cycler voltage limits | The specified CC-to-CV/discharge controller imposes its voltage envelope (R04/R05). | Trace min/max against existing numerical allowances. **Observable now; already gated.** These are controller consistency limits, not cell safety qualification. |
| B4 — causality / inactive future command | Identical initial state and identical forcing give identical prefix histories. The first 120 s is rest regardless of c1/c2 (R04; inference from the deterministic initial-value problem in S02/S04). | For fixed ambient/SOC, vary either charging rate and compare V/T at 0/30/60/90 s. Exclude the switch endpoint. **Observable now; proposed gate.** Also test off-grid protocol pairs when ready public model artifacts are available. |
| B5 — net external charge integration | Under PyBaMM's discharge-positive convention `dQ_net,Ah/dt = I/3600` (S06). A CC rate fixes `I=±C_rate×Q_nominal`; the pinned nominal capacity is 5 Ah (S03). | For an independently known CC interval integrate its commanded current. There is **nothing comparable in today's outputs**: capacity_ah is a later discharge-step increment. New cumulative charge and stage-time outputs are needed; CV additionally needs I(t). |
| B6 — internal charge/lithium conservation | DFN current continuity and species balances include spatial fields, main/side currents and lithium trapped in degradation products (S02). | Integrate concentrations/inventories plus side-reaction accounting, or evaluate finite-volume boundary/current residuals from predicted fields. **New output contract required.** Initial SOC plus CC current is not a proof of later lithium distribution or side-reaction balance. |
| B7 — thermal energy balance | For the pinned lumped route: effective heat capacity times dT/dt equals total heat, contact heat and cooling (S04/S05). | Prefer integral `stored_thermal_change - integral(heat+contact-cooling)` to a noisy derivative. **New independent heat output/parameter-state contract required.** Defining heat from T makes this residual identically zero by construction. |
| B8 — full electrochemical energy | Terminal electrical work, chemical stored energy and distributed losses must close consistently (S07). | Integrate declared electrical work and compare chemical/thermal/loss inventories. **New outputs required;** even I(t), V(t) and T(t) alone do not expose all terms. Label a lumped thermal residual narrowly. |
| B9 — temperature lower bound | With nonnegative total source, positive heat capacity, passive cooling and initial T equal to constant ambient, the lumped ODE preserves T≥ambient (derivation from S04). General batteries can have signed reversible heat (S01). The pinned S03 entropic coefficients are zero, but S05 contains other terms. | Count below-ambient predictions as a **conditional diagnostic now**. Before a hard gate, prove the total-source sign for all included terms/options and all declared states; do not infer it from a finite reference sample. Absolute-zero bound is a separate trivial check in declared units. |
| B10 — monotonic heat/current, fade and rate | `I²R` increases with |I| only at fixed nonnegative R; total electrochemical heat also depends on state, signed terms and controller timing. Reversible plating and later dischargeability can defeat monotone measured fade (R08; S03/S05). | Pair rates at fixed state only if that state is represented. Whole-protocol temperature/fade inequalities are **diagnostics, not universal gates**. Report reference counterexamples rather than relaxing a gate. |
| B11 — symmetries / units | Battery electrodes and CC stages are ordered and asymmetric. Exchanging c1/c2, SOC with 1−SOC, or charge/discharge sign is not an invariance. Units follow the declared interface and SI (R03; S13). | Check adapter units, signs and dimensions; known rest-prefix equivalence is a valid invariance. Celsius/Kelvin conversion belongs to the adapter; passing Kelvin into a degC field is a malformed input, not a physics test. |
| B12 — reproducibility / interpolation | Same model/input should reproduce under the registered execution; no physical law says a nonlinear DFN output is linear in inputs (R05/R02). | Repeat/order probes and valid midpoints test robustness. **Current fields suffice, new evaluations needed.** Do not score a straight-line interpolant of two stored predictions as the actual model response. |

**CC loophole resolved.** A model-predicted 4.0-V crossing can suggest a stage
boundary, but using that same prediction to decide how much charge “should” have
flowed is circular. Use an independently declared interval that remains CC,
or require explicit stage times and current with a controller-consistency
contract. At rest, the known external integral is zero; this says nothing about
internal diffusion or SEI. At discharge, the existing checkpoint capacity could
be compared with a reported discharge duration under the fixed 1C command, but
that duration is currently missing. No new physical truth is obtained by merely
defining duration from predicted capacity.

## 3. What was measured on public development arrays

The owner supplied **148 distinct rebuilt-model bundles**, with 21 byte-identical
copies across the three folders removed. Cohorts are 100 original-EV4-label CPU
rebuilds, 27 Graphite-run-5 rebuilds, 11 additional proof members and 10 adversarial
rebuilds. Five synthetic controls are recreated separately. This is **not the
original EV4 A40 result**, nor a sealed/tuning-fold run (R15/R16).

Only **420 original public development decision inputs** (12 conditions × 35
protocols) are used. **415** have OK references; five unavailable references are
withheld from law calibration. Every real member supplies all 420 predictions.
Decisions preserve unavailable and unresolved truth. No additional model queries
or solver calls were made. The reference's maximum rest span is exactly zero
for both V and T on this mask; minimum recorded total heating is
`2.5707594987299012e-11 W`. Positive sample heating does not prove a universal
source sign.

For the 100-member EV4 CPU-rebuild cohort:

| Observable check / diagnostic | Members flagged | What it says |
|---|---:|---|
| Initial voltage / initial temperature | 0 / 100 for each | Existing gates pass on these public inputs. |
| Voltage floor / capacity bound / finite shapes | 0 / 100 for each | Existing checks pass; not full charge/energy balance. |
| Voltage ceiling | 1 / 100; 241 failing cases for that member | Existing gate catches one of the 81 members with an observed unsafe development pick. |
| Rest-voltage causality, numerical research floor | 100 / 100 | Worst spans min/median/max = 0.064906 / 0.207978 / 0.397335 V; rejects all 81 unsafe-picking members and all 19 without an observed unsafe pick. |
| Rest-temperature causality, numerical research floor | 0 / 100 | Worst spans min/median/max = 1.071e-6 / 2.469e-6 / 5.544e-6 degC; all below the research allowance. |
| Below ambient, conditional diagnostic | 93 / 100 | Worst undershoot min/median/max = 0 / 1.059744 / 3.854485 degC. Flags 76 of 81 unsafe-picking members and 17 of 19 without an observed unsafe pick. No universal hard verdict assigned. |
| Positive capacity checkpoint increment, zero cutoff diagnostic | 4 / 100 | No reference case has a positive increment on this subset. The deliberately omitted monotone-fade gate is not reinstated. |
| Below absolute zero in declared units | 0 / 100 | Trivial physical bound, little discrimination here. |
| Charge / lithium / energy / unit truth | NOT_MEASURABLE | Required independent terms or semantic evidence absent. |

The **81** unsafe-picking members collectively make **129** reference-infeasible
choices across the development conditions. "No observed unsafe choice" is **not**
a safe-model label: unresolved choices and missed opportunities remain. On six
conditions resolved for every member, tau-b of maximum residual versus mean
loss is **0.04027** for rest voltage, **−0.01231** for rest temperature and
**0.08656** for below-ambient undershoot. Shared cases/repeated recipes and a small
common mask prevent an independent or causal inference. This supplies no
convincing evidence that these magnitudes rank real models by buyer value.

The sensitivity floors are `0.000016021728515625 V` and
`0.000152587890625 degC`, transferred from the historical numerical convention
as **ASSUMPTION**, with adoption **HUMAN_INPUT**. Multipliers 1/10/100/1000 leave
the real-cohort voltage check at 100 flagged and temperature check at zero.
The full observed-residual curves are retained in measurements.json; examples
below are **descriptive breakpoints, not acceptable physical tolerances**:

| Voltage span cutoff (V) | All flagged | Unsafe-picking flagged / 81 | No-observed-unsafe flagged / 19 |
|---:|---:|---:|---:|
| 0.06490599 | 99 | 81 | 18 |
| 0.16519898 | 74 | 63 | 11 |
| 0.20783497 | 50 | 40 | 10 |
| 0.23471818 | 25 | 20 | 5 |
| 0.39733510 | 0 | 0 | 0 |

Counts use strict residual `>` cutoff and full-precision values in JSON; displayed
cutoffs are rounded. Large cutoffs in this table illustrate weak separation,
not a recommendation to excuse 0.2-V violations.

| Separate cohort | Members | Unsafe-picking members | Existing-gate flags | Voltage-prefix flags at floor | Temperature-prefix flags at floor | Below-ambient diagnostic flags at floor |
|---|---:|---:|---:|---:|---:|---:|
| Graphite run 5 | 27 | 24 | 0 | 27 | 0 | 27 |
| Additional public proof | 11 | 9 | 0 | 11 | 0 | 5 |
| Adversarial rebuild | 10 | 9 | 1 | 10 | 1 | 10 |

One adversarial rebuild also predicts below absolute zero and fails the old
capacity/voltage-floor gates. These are unambiguously different from a model
correctly predicting that a design overheats. Separate cohorts are not pooled
as independent evidence.

| Synthetic control, recreated on the public development references | Existing-gate failure | Worst V-prefix span | Worst T-prefix span | Unsafe development choices |
|---|---|---:|---:|---:|
| Oracle | None | 0 V | 0 degC | 0 / 12 |
| Conservative | None | 0 V | 0 degC | 0 / 12 |
| Rank-preserving delay | None | 0 V | 0 degC | 0 / 12 |
| Boundary optimist | None | 0 V | 3.5 degC | 8 / 12 |
| Localized plating sign error | None | 0 V | 0 degC | 4 / 12 |

**A cheap bypass is measured, not hypothetical:** take the boundary optimist,
clamp predicted temperatures to ambient and set its four pre-charge samples to
ambient; leave voltage, plating and capacity unchanged. It then has zero prefix
span and zero below-ambient undershoot and passes all existing gates. **Every
one of its 12 decision outcomes is unchanged**, including all eight unsafe
choices. This post-hoc research control is not a real miner or a pre-registered
proof result. It demonstrates that the proposed visible-output checks can be
repaired without raising decision value.

Historical context is kept separate: R13's original A40 verification summaries
had 56 eligible real members with an unsafe choice and one rejected unsafe
member. R14's original EV5 summaries had nine of ten adversarial members passing
old gates while making an unsafe verification choice. Do not attach those
losses/verdicts to these new CPU artifact identities.


The detailed [measurement protocol](MEASUREMENT_PROTOCOL.md) publishes the masks,
control transformations, residuals, cutoffs and selection/loss definition.
[measurements.json](measurements.json) contains cohort summaries, every public
member's descriptive residuals/outcomes and byte provenance, without raw traces.
This analysis uses original unrefined decision references. It does not import
the tuning fold's later settled-reference policy. A changed mask/settling policy
can change the associations and must be reported as a new analysis.

**Interpreting a flagged member.** A zero/tiny prefix tolerance may reject nearly
every learned model, including useful ones. That would enforce an exact
structural property but provide little separation by decision value. Conversely,
the plating-only sign control can be internally consistent in all visible
voltage/temperature/capacity fields while selecting unsafe actions. Do not
choose a tolerance just because it excludes one disliked member. A hard-gate
decision needs an independently justified numerical allowance and prospective
decision-value evidence.

**Unavailable rates:** no charge/energy residual, independent uncertainty
calibration, new-input interpolation response, repeated/batch-order response or
motor/cooling/f02 member violation rate is invented. The supplied arrays enable
fixed-grid battery measurements. Ready public models/extra observables are
required for the other measurements.

## 4. Motor: bind the right family before testing

The launch-oriented 10p/12s kit predicts 48 signed samples over a 12-degree
window for a 2D slice, then correctly combines shifted loaded/cogging curves for
the skewed stack (R17). Legacy `carbon.motor` is an 8p/24s, 60-sample family
(R18/R19). Transfer no period, zero, tolerance or sign convention between them
without a prospective contract. Mechanical stress is not a torque output.

| Property | Solver-free probe and boundary |
|---|---|
| Conservative zero-current cogging work | At J=0 and fixed conservative magnet/material state, torque is the angular derivative of periodic magnetic energy; its integral over a full physical period is zero (S08; inference for this declared magnetostatic family). Average/integrate the predicted **unloaded** curve on its own angular grid. **Current curve sufficient** once the full period, quadrature and hysteresis exclusions are established. Numerical allowance HUMAN_INPUT from reference angular convergence. |
| No arbitrary zero-torque rule | PM cogging can be nonzero instantaneously at J=0. Do not require each sample to vanish. Loaded synchronous currents change as the rotor turns, so the loaded mean need not be zero. |
| Zero-current command-angle invariance | J=0 makes the current-angle command inactive. At fixed geometry, vary gamma within admitted bounds and compare cogging curves. **Observable from current outputs; extra queries needed.** Ensure coordinate phase is identical. |
| Periodicity / rotational symmetry | Predict at equivalent angular origins or transform geometry/current phases consistently. **Only when that input or an equivalent transformation exists.** Neither the first and last sample on a half-open grid nor a cyclic roll by itself is an independent repeated endpoint. A new angular-origin input would version the interface. |
| Motoring mean sign | R18's nonnegative-mean check is tied to its specific motoring quadrant and surface-PM frame. Verify the 10p/12s current conventions and permitted gamma first. **Conditional, not automatically inherited.** Negative ripple samples are allowed. |
| Virtual work versus Maxwell stress / flux balance | Coenergy and flux/field predictions would allow an independent cross-check (S08/S09). **New model outputs required.** Reference-side coenergy/B diagnostics are not miner predictions. Differentiate coenergy holding currents fixed; `dW'(theta,I(theta))/dtheta` includes an extra current term and is not torque alone. |
| Torque/ripple reductions and skew | Recompute mean, pk-pk, cogging and ripple from the signed curve. Apply R17's loaded angle shifts to gamma as well as theta. **Contract arithmetic now**, not new physical validation. A ripple fraction at near-zero mean is undefined and must abstain rather than divide by zero. |
| Current monotonicity and units | Do not enforce exact torque proportionality/oddness for nonlinear saturating steel and PM cogging. Limit any linear relation to an explicitly linear tier and subtract the appropriate unloaded component. Check N·m and radians in work integration; degree/radian conversion errors multiply an energy residual. |

## 5. Cooling: distinguish full cell physics from the composed reference

The cold-plate model predicts `peak_c`, a 30-segment face-temperature profile and
pressure drop. Mean and outlet are derived (R20). The current AI-chip point B/C
composition adds a presolved lid, thermal interface and cached cell-map response
(R24); it is a distinct reference route. Agreement with that composition does
not establish full nonlinear package CFD or vapour-chamber phase-change physics.

| Property | Solver-free probe and boundary |
|---|---|
| Passive temperature lower bound | Positive heating, inlet-fed steady flow, passive solid conduction and no colder sink imply face temperature at least inlet for the declared cell. R21 currently uses strict `>`; a new allowance remains HUMAN_INPUT. Check peak/profile at interior geometries/flows. The claim excludes refrigeration, transients with colder initial solids and unmodelled boundary sinks. |
| Peak dominates profile | The face maximum is at least every segment/span mean, and the arithmetic mean lies between min/max profile. **Observable now, already partly gated;** segment means do not bound an unresolved local maximum from above. |
| Passive hydraulic dissipation | In the declared equal-area straight duct with positive flow, no pump/gravity work inside the cell, a viscous pressure loss is positive. **Observable now, already gated.** Do not transfer a static-pressure sign rule to expanding manifolds or reverse flow without total-pressure accounting. |
| Energy and mass balances | Steady absorbed heat equals independent outlet-minus-inlet enthalpy flux plus registered kinetic/conductive terms; inflow and outflow mass agree (R22; S12). **Current reduced model outputs cannot check these independently.** R20's outlet is computed from absorbed heat and input flow/cp, so plugging it back gives an arithmetic identity. Add independently predicted fluxes/fields to test a real residual. |
| Power/flow normalization | Use periodic-cell absorbed power, not full-chip nameplate power, when the geometric period does not tile the footprint (R20). Compute flow from heat×L/min/kW. A fixed coefficient is **not fixed flow**. Therefore “higher heat must give a particular larger temperature” is not a universal gate in this controlled family. |
| Symmetry | Declared transverse symmetry planes permit symmetry-consistent fields if exposed. An upstream hot spot and its downstream mirror are not equivalent: convection fixes direction. Do not reflect the axial profile without transforming inlet/outlet and the physical problem. Current scalar/profile interface has no full symmetry-field test. |
| Superposition/thermal-property assumptions | Exact linear heat-map identities apply only to the declared cached linear composition, not variable-property CFD (R23/R24). Test intermediate weights within that composition, naming the result **composed-reference consistency**. Do not hide the cheap response-map baseline. |
| Units/applicability | Pressure in Pa, thermal flux in W/m², flow conversions and solid/coolant temperature domains must be explicit. R24 now defaults to full validity, preserving older no-check/99-only results as history. Missing/exceeded reference validity is UNRESOLVED, not a failed model. Actual allowed ranges belong to the validity owner, not this gate proposal. |

## 6. f02: exploit the linear field without claiming a linear peak

R26's current model predicts only `peak_top_c` and `extra_energy_j`; R28's planned
packet traces are not present in that model interface. The deck uses
constant-property layered solid conduction with Robin cooling and prescribed
waveforms (R27). Heat-equation linearity has explicit coefficient/boundary
conditions (S10); comparison principles inform the following stated derivations
(S11).

| Property | Solver-free probe and boundary |
|---|---|
| Source integral | Recompute extra energy above the 20-W baseline from the exact waveform/event knots, not `peak×duration`. **Observable now; arithmetic consistency.** If the objective is fully determined by inputs, derive it instead of rewarding a model for reproducing it. |
| Initial/max lower bounds | A time-and-space maximum including t=0 is at least the initial uniform temperature. With nonnegative sources and passive constant-coolant boundaries, no field value falls below `min(initial,coolant)`. **Peak lower bound observable now.** Full pointwise lower-bound check needs predicted traces/fields. |
| Source-order monotonicity | With identical coefficients, initial state and cooling, a pointwise larger nonnegative source cannot produce lower temperature/peak. Vary peak power at fixed duration/waveform/split. Rectangular longer duration preserves source order; ramp and separated-pulse duration changes need not. **Peak check observable now**, extra queries needed. |
| Convexity under interpolated power | At fixed duration/waveform/context, the temperature field is affine in power. Its maximum over the same space/time domain is convex: `peak(alpha*p1+(1-alpha)*p2) <= alpha*peak(p1)+(1-alpha)*peak(p2)`. **Peak-only necessary condition now.** Neither equality nor exact proportionality is implied. |
| Field superposition | For the same operator, subtract the common baseline response and add source/initial-state perturbations. **New trace/field output contract needed** for an equality check; the two scalar peaks cannot reconstruct which point/time maximizes temperature. |
| Thermal energy | `input_energy = stored_energy_change + integrated_boundary_outflow` under the registered conduction model. **New independent predicted storage/flux outputs required.** Peak and useful source joules do not determine spatial average energy. Reference-side balance remains reference evidence. |
| Spatial mirror | A symmetric stack/cooling with left/right sources exchanged swaps patch-center traces and preserves the top maximum. Current discrete split set `{0.5,0.8}` excludes the complementary 0.2 for an off-center test (R26). **Do not query an undeclared split as an admissible gate.** Version/population change needed for that pair. |
| Temperature offset and stress/load | Common temperature-offset equivariance needs unchanged coefficients, initial/coolant shifted together and unchanged h. R26 ties coolant to discrete h pairs; those are different operators. Mechanical stress is **NOT_APPLICABLE**, no structural output. Linear-elastic load proportionality would require a separate structural Challenge's assumptions. |

## 7. Cheap interpolation, repeat and out-of-domain panel

For a ready public model, supplement cached-grid measurements with matched
probe families. **ASSUMPTION low/base/high: 12/48/192 anchor groups per family,
2/3/5 evaluations per group**, hence 24/144/960 model evaluations, no new solver
calls. These are planning ranges, not an adequate sample-size or CPU-time claim.
Gate sample allocation, numerical allowances and allowed failing rate are
HUMAN_INPUT. Inference throughput is unmeasured here; do not quote milliseconds.

Use paired legal interior points, valid faces/corners, source-order pairs and
shared-history pairs. For continuous axes take genuine model evaluations at
off-grid convex-combination inputs; keep categorical physics, discrete context
and geometry validity fixed. For motor, check buildability and J=0; for cooling,
avoid channel-count jumps when interpreting smoothness; for f02, keep waveform
and initial/cooling context fixed for power convexity. Units tests use explicit
adapter conversions. Repeat and permutation tests re-evaluate the same model,
not just permute an existing array.

`P` is the owner-defined job population. `Q_probe` intentionally targets laws,
edges and interpolation holes; it is a diagnostic design, not P. Report
per-family/per-stratum results with declared weights `w_probe`; do not mix its
adversarial concentration into a population safety-rate estimate. Different
probe strata can overlap; do not add their denominators blindly.

Outside the admitted input domain, a model should refuse or flag unsupported
use according to its contract. Unknown/outside reference-property validity
produces unresolved truth (R25). Extrapolation probes can measure failure modes
as diagnostics, but cannot change P, make out-of-domain requests admissible or
extend physical validation. Passing finite probes does not establish laws at
every point between them; a constrained architecture can enforce a particular
identity, while still predicting the wrong answers.

## 8. Uncertainty and calibration

Today these outputs are point predictions. Neither a physics residual nor
ensemble disagreement is a calibrated error probability. Reference numerical
bands, model approximation error and physical/model-form discrepancy are
different uncertainties. An empirical reference-relative residual band can be
added without pretending that the model emitted uncertainty, but an explicitly
predicted interval/distribution requires a versioned measurement/output contract.

Propose a separate public calibration set and untouched evaluation set, split by
case/operating condition and artifact/recipe as appropriate. Calibrate one-sided
error bands for feasibility margins and simultaneous bands for a whole trace or
question, not just marginal per-time coverage. Report coverage **and width**,
abstention, false-feasible frequency, decision regret and worst-stratum behaviour.
Use binomial intervals only when the independent unit is justified; otherwise
cluster by case/question and recipe and report the dependence limitation.
Coverage levels, tolerated false-feasible rate and widths are HUMAN_INPUT.

Split conformal prediction is a candidate reference-relative calibration method
under exchangeability (S14). Covariate-shift extensions need more assumptions
(S15). Optimizer-selected points create feedback shift (S16), so random-point
coverage does not by itself bound the safety of a top-k design. Test the actual
selection-and-verification workflow, stratify envelope/edge cases and abstain
when applicability or evidence is missing. Dataset shift requires direct
uncertainty evaluation (S17); classification temperature scaling is not a remedy
for temperature-regression errors (S18). No calibration result here qualifies
hardware or guarantees individual-design safety.

## 9. Candidate hard gates and the adoption bar

All rows are **proposals, HUMAN_INPUT**. None is registered or implemented.

| Priority / gate candidate | Needs now versus new version | Evidence required before adoption |
|---|---|---|
| H1 — battery prefix-causality | Current output fields; **new prospective exam/gate version** and legal probe law. Temperature prefix is the useful first candidate; voltage prefix requires structural remediation before a hard launch gate because every present real member fails. | Analytic shared-forcing proof, numerical allowance from independent prefix/reference controls, full tolerance curve, real/control/attack discrimination and fresh value/shifted-question evidence. Do not adopt an all-model rejector merely because its recall is high. |
| H2 — cross-output/command consistency | Preserve battery initial/inventory/controller and cooling peak/profile/pressure checks; add justified motor inactive-command/zero-current-work and f02 peak-order/convexity checks only to their exact family. Existing fields often suffice; new gates still version exam semantics. | Reference qualification and quadrature/convergence evidence; prove input transformation legality. Numerical maxima/convexity are necessary conditions, not sufficient adequacy. Retain the strongest lawful cheap formula/ROM as a competing baseline. |
| H3 — independently observable balance | New predicted current/charge/stage-time or thermal storage/heat/flux fields: **new Challenge output/measurement contract**. Full lithium/electrochemical balance needs more state. | Identify every term and units, signed conventions, initial/boundary state, retained solver approximations, numerical/refinement residual, adversarial self-consistent-but-wrong controls and incremental buyer decision value. Separate reference-invalid from candidate-fail. |
| Deferred — battery above-ambient | Current T observable, but entire-source-sign proof is absent; keep diagnostic. | Zero entropic coefficients are insufficient by themselves. Prove total source and passive boundary hypotheses across registered states/options, then calibrate. No limit relaxed to obtain feasibility. |
| Rejected as general gates | Whole-protocol monotonic heat/fade, all torque samples nonnegative/zero at J=0, scalar peak linearity, safety-threshold prediction positivity. | Each is either false without restrictive assumptions or confuses a bad design with a bad predictor. |

Acceptance should fail closed when an **adopted, applicable, independently
qualified** mandatory measurement fails. It should not turn NOT_MEASURABLE,
undeclared reference validity, unavailable arrays or infrastructure failure into
a physical model failure. No soft score compensates for an adopted mandatory
failure; no hard gate creates scientific authority on its own.

## 10. Handoff and remaining evidence

Test Engineer: use the measured residual curves as **selection-fold research
candidates**, not a changed registry or official gate. Preserve both adverse
findings and controls that pass. First reproduce the common-rest measurement and its physics-repaired boundary-optimist bypass
from the public manifest; then evaluate ready public models on new legal
interpolation pairs and order/repeat tests, with no training or solver calls
required for those probes. Freeze candidate definitions before fresh confirmatory
questions. The later value-metric job can test whether compliance predicts
shifted-question value; this report does not claim that result.

Packets/Validator: reconcile the 10p/12s, composed cooling and scalar f02 output
contracts with each desired measurement. Draft new balance observables only as
prospective versions. Reference verification remains essential for feasibility.
Owner: choose whether exact causal structure is mandatory, select independently
justified allowances, decide which new outputs are worth requiring, and approve
any eventual production gate or claim. These decisions are not made by this PR.

Maturity: law/probe designs **SPECIFIED as recommendations**; public diagnostic
arithmetic checked. No runtime implementation, scientific qualification,
security acceptance, LIVE activation, commercial validation or physical safety
claim is earned. Hub is retired/frozen; existing packets and runtime remain
unchanged. Research limitations are delivered in this report, not concealed by
an aggregate physics score.
