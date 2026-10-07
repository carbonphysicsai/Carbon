# Motor — a precision robot-joint customer's DEVELOPMENT packet

**Role-play:** a hypothetical direct-drive robot integrator, not an actual
customer or certified motor requirement. **Authority:**
[OWNER-FIRST-THREE-CUSTOMER-ROUND-01](../../../../.agent/decisions/2026-10-07-OWNER-FIRST-THREE-CUSTOMER-ROUND-01.md),
extending the owner's round-1 customer delegation. Ten-section F1 format;
numeric companion: [first-three-requirements.json](first-three-requirements.json).
This is prospective buyer input to the Test Lead, not a change to today's exam.

## 1. Engineering job

“I integrate a direct-drive elbow joint for slow precision assembly. Choose
one motor cross-section satisfying the declared geometry-validity grammar
and two selected static current-command points
that can hold my load smoothly. I need a verified shortlist, not just a
low-error torque predictor.” Geometry is the design action; current density
and phase angle are chosen commands, not random environmental disturbances.

My mock load is a 1.5-kg payload at a 0.20-m lever, plus 2 N·m from the tool
and link. At g=9.81 m/s², `(1.5*9.81*0.20 + 2)*1.20 = 5.9316 N·m`.
Round up to **6 N·m holding torque**. Demand **12 N·m for a 2-s acceleration
burst** as a separate eventual product requirement, not a 2D thermal rating.

| Buyer-owned requirement | Why it matters |
| --- | --- |
| Holding mean ≥6 N·m at a selected precision command | Avoid drift or a stalled placement; TRAIN's 4 N·m median is not my load |
| Energized peak-to-peak ripple ≤5% of absolute mean **and** ≤0.30 N·m in holding, ≤0.60 N·m at the 12-N·m peak command | Limit motion disturbance; absolute and relative constraints both apply |
| Zero-current cogging peak-to-peak ≤0.05 N·m | Smooth backdriving/hand positioning; do not divide by a near-zero mean |
| Product-context tip disturbance ≤10 µm peak-to-peak at the declared 0.20-m lever | A customer-recognizable precision allocation, needing mechanical/controller verification |

The ripple allocation assumes joint torsional stiffness 10,000 N·m/rad:
0.30 N·m gives 30 µrad or 6 µm at the tip. This is a dimensional allocation,
not a closed-loop motion prediction. The acceleration stratum has a different
motion budget; a 12-N·m magnetic result does not demonstrate its 2-s duty.

**Wrong decision:** a mock commissioning stop of 2 h at $120/h plus $400
scrapped parts costs **$640/event**; a geometry redo of 16 engineering hours
at $150/h plus a $1,200 prototype costs **$3,600/revision**. These assumed
rates exclude safety consequences and are not observed losses. Buyer value
per shortlist revision is six engineering hours, **$900 gross**, if actually
saved against the best existing workflow; subtract full Carbon costs.
Machining/material/assembly feasibility still needs a separate review.
Not a safety-rated actuator, full robot, efficiency map or commercial order.

## 2. Physical system

KEEP [domain.py](../../../../carbon/motor/domain.py): 8-pole/24-slot
surface-PM cross-section, 92-mm stator outer diameter, 35-mm model stack
length and 104 turns. Six geometry variables remain within their existing
validity grammar: magnet thickness 1.5–4 mm, embrace 0.55–0.95, air gap
0.3–1 mm, slot opening 1–6°, tooth width 2.5–5 mm, slot bottom radius 34–42 mm.
The 60 torque samples are at 0:0.25:14.75° over one 15° mechanical period.

Reference commands use current density J=0–15 A/mm² and phase angle 0–60°.
J is **not phase amperes**: the existing winding/slot-area calculation maps
J to current separately for each geometry. State that mapping in the manifest.
The current generic magnetic material laws remain generic and version-pinned.
No material-batch claim is created by this buyer brief.

Slow motion at 1–60°/s, link stiffness, inverter/bus voltage, resistance,
heating, bearing/end effects, 3D skew, tolerances and control dynamics are
deployment context, **absent causal inputs** in today's magnetostatic model.
Do not infer continuous duty, peak duration or tip error from that model.

## 3. Population P, Q and w

Customer-recognizable strata: unpowered positioning; settled loaded holding;
slow loaded tracking; and short acceleration. For the first synthetic
DEVELOPMENT diagnostic panel, holding/tracking use J in {8,10} A/mm² and
phase angle in {0,15}°; acceleration probes use J in {12,15} and angles
{0,15}°; unpowered uses J=0 and angle=0. These are candidate command options,
not an assertion that every low-current command must deliver 6 N·m.

For each geometry choose a precision command and a peak command **before
verification**. The chosen precision command must meet 6 N·m/holding ripple;
the chosen peak command must meet 12 N·m/peak ripple. Unchosen commands remain
reported diagnostics, not retrospectively deleted successes or failures.
Holding and tracking share the same static cases; they are not two independent
observations. Dynamic tracking adequacy remains unresolved.

The named service roles define intended applicability, not four independent
equal-mass observations: there is **no aggregate P estimate** from this finite
static panel. Tracking remains unobserved dynamic context; reused holding
curves may not be counted again as tracking evidence. This is separate from
the existing eight-input DEVELOPMENT model-case generator. Geometry/current proposals are
actions, not draws from a customer's operating population. Freeze the finite
geometry proposal list and command-selection rule before reference access.
Diagnostic `Q` is the complete nine-command panel applied to those actions,
plus separately declared boundary/low-torque controls; it is not IID deployment
sampling. `w=1` per geometry for descriptive magnetic-selection counts; each mandatory
stratum is checked separately. No weighted
mean can erase failed torque/cogging. Real deployment P and evidence weights
for a registered exam remain HUMAN_INPUT. Geometry is the independent unit;
angle probes and command curves on that geometry are correlated.

## 4. Case contract

Bind geometry, current mapping, selected commands, angle convention, materials,
mesh, solver build and extraction version to a canonical prospective case.
Refuse nonfinite/out-of-range inputs, impossible tooth/slot clearances and
unsupported dimensions before solving. No silent clamps or replacement draws.
Six static geometry parameters cannot be used to encode stiffness or speed.
The present 60-vector representation is reusable; the new command-selection
and cogging policy requires its own versioned decision binding.

These public scenario recipes contain no protected cases or labels. Public
research uses the researcher's own draws. Protected evaluation identities,
seeds and confirmation material stay operator-side, never in research pods.

## 5. Reference policy

KEEP current Gmsh/GetDP deck/mesh/reference custody and their immutable pins;
WRAP for the buyer decision only in a later authorized ticket. Reference
adequacy for 6/12 N·m and 5% ripple is **NOT_DEMONSTRATED**. Require retained
air-gap and mesh refinement, torque orientation/periodicity checks, and
Maxwell-stress versus virtual-work/energy comparison on the same cases.

Selected DEVELOPMENT numerical acceptance: successive resolved refinements
change mean torque by ≤0.10 N·m and peak-to-peak by ≤0.02 N·m; the two torque
methods agree within those absolute bounds on the diagnostic controls.
Check zero-current, low-torque, tight-gap and high-J/saturation cases. Refine
angle sampling 60→120→240 with compatible exact-rotation gap meshes. Today's
1,440 gap nodes support only 60 steps per 15° period; 120/240 require at
least 2,880/5,760 gap nodes, or a separately verified rotation method.
Distinguish angle and spatial sensitivities using compatible pinned meshes
(for example all three angle rungs on the finest gap mesh); missed extrema
must not hide under a good mean. A case meeting convergence but straddling a
buyer limit remains unresolved. These limits are acceptance demands to test,
not measured solver error bounds or permission to rescore old evidence.

Keep invalid inputs, reference nonconvergence and infrastructure failure
separate from candidate failure. No solver/spend grant is added. Exact
refinement campaigns require their own pins, controls, custody and approval.

### Reference credibility target

**Buyer tool:** Ansys Maxwell 2D/3D for the mock integrator's magnetic design
workflow; this is a role-play assumption, not measured adoption. Maxwell's
[official capability description](https://www.ansys.com/products/electronics/ansys-maxwell)
supports the workflow, not Carbon agreement. **Carbon reference:** current
Gmsh/GetDP, **not the same tool**. Neither a shared formulation nor a future
Maxwell run establishes Tier 1 without the buyer's exact model/settings.

**Target tier:** Tier 2 for magnetic design shortlisting. Tier 3 torque-angle/
current bench evidence would be required before relying on physical cogging
or robot-joint performance; thermal, end effects and controller response need
their own scope. **Credibility evidence: NOT_DEMONSTRATED** for this buyer job.

**Benchmark cases:** COMSOL's published
[Permanent Magnet Motor in 2D](https://doc.comsol.com/6.4/doc/com.comsol.help.models.acdc.pm_motor_2d_introduction/pm_motor_2d_introduction.html)
and [Permanent Magnet Motor in Steady State](https://doc.comsol.com/6.4/doc/com.comsol.help.models.acdc.pmm_steady_state/pmm_steady_state.html),
recreated with identical published inputs in GetDP and the chosen buyer tool.
The first example is 10-pole/12-slot, not today's 8-pole/24-slot deck; neither
is a published cross-tool pass for Carbon. Add matched buyer-grammar zero-current,
holding, peak-current and saturation witnesses, including any prospectively
adopted skew slices with the same stack/torque normalization. No topology or
solver change is implemented by this subsection.

**Acceptance tolerance: HUMAN_INPUT.** Recommended initial cross-tool limits:
mean torque difference ≤1% at nonzero holding/peak commands; maximum absolute
torque-curve difference ≤0.03 N·m; energized peak-to-peak difference ≤0.015 N·m;
zero-current cogging peak-to-peak difference ≤0.005 N·m. These allocate a small
part of the buyer's ripple/cogging budget; resolve angle extrema and refinement
before comparison, with no relative cogging error about a zero mean. The older
numerical criteria above are not silently tightened by this recommendation.

**Claim boundary:** [the common credibility contract](reference-credibility.md)
applies. After accepted Tier 2 evidence, say “matches the reference simulator”
for the stated magnetic cases/bounds, not “matches reality” or qualified joint
precision. Target selection itself earns no agreement or Tier 3 evidence.

## 6. Output and measurement contract

Report the signed torque curve in N·m, its mechanical-angle coordinates,
`mean(T)`, `T_pp=max(T)-min(T)` and energized `r_pp=T_pp/abs(mean(T))`.
Refinement resolves between-probe extrema. Positive drive orientation is
fixed; negative/zero mean cannot meet a positive torque floor. Unpowered
cogging uses T_pp alone and reports signed extrema, never a percentage score.

**Acceptance of a mock shortlist:** independently verify the preselected
commands, mean floors and both ripple limits; verify zero-current cogging;
return the best verified feasible geometry or **NO_VERIFIED_FEASIBLE_DESIGN**.
Rank feasible magnetic designs by lowest holding ripple fraction, then lower
holding current density, then a frozen design-order tie break. No magnetic
ranking certifies heat or controller performance. Boundary uncertainty or
missing references yields UNRESOLVED, not a favorable zero.

Today's [customer_decision.py](../../../../carbon/motor/customer_decision.py)
uses a common floor/ripple policy across its conditions. It cannot express
this per-role command selection plus zero-current absolute-cogging contract
without prospective changes. This packet supplies requirements, **not those
changes or a new Score Pack**. Frozen 4.0-N·m/0.30 studies keep their meaning.

## 7. Construction contract

KEEP existing Level-0 representation, registered reconstruction capabilities
and TRAIN-only provenance. A model may propose commands using permitted
public data, but is not the verifier of its own chosen design. Deterministic
geometry/command proposals must be frozen before independent evaluation.
Any new output, current schedule or construction capability needs the owning
versioned contract. No participant code receives grader authority.

## 8. Research kit

Reuse public motor geometry/curve documentation, generator and available
analytic/interpolation/learned baselines; publish the mock load and limits
with their derivations. Do not promise a torque-field residual from a
torque-only output. Current physical reference, practice score and Interface
v1 adapter are different components, none makes this new buyer task ready.

**Deployment:** an engineer's offline design workstation, not the live servo
loop. Target warm-model p95 ≤0.10 s for a complete 60-angle curve on a pinned
CPU profile; 200 designs ×9 declared command queries should use ≤180 s
inference and deliver a shortlist within 10 min including overhead. This
throughput target is unmeasured and excludes training/reference verification.
Carbon replaces repeated first-pass magnetostatic sweeps, not independent
final FEA, bench torque measurement or control commissioning. Report all those
costs and the strongest cached/interpolated baseline, not only cold FEA time.

## 9. Evidence plan

Test Lead owns future design-task integration; Carbon Validator owns grade
bindings. Compare analytical harmonics, interpolation/reduced models and
learned models with equal search opportunities and the same resolved cases.
Controls must catch flat/mean-only torque, phase-shifted curves, hidden narrow
peaks and a false feasible near-limit design. Precommit limits/commands and
record every attempted case before observing verification outputs.

Measure false-feasible decisions, unresolved references, feasible yield,
selection regret in ripple units, and **net hours/dollars per verified design
revision**. Never trade a torque failure for customer value or a soft score.
Fresh independent confirmation, deployment law, actual material/bench data,
training budget, spend and production acceptance remain HUMAN_INPUT.
No counted or fresh campaign runs in this ticket. Final confirmation cannot
be used to tune either the buyer brief or the model.

## 10. Readiness and claim record

KEEP: domain, full-curve reference, historical decision/control studies,
[existing packet](../../MOTOR_DECISION_DESIGN_PACKET.md) and Interface-v1
adapter merged in #706. NEW: independently selected buyer job, limits,
scenario roles, value assumptions and prospective verification demands.
GAPS: command-role/cogging measurement integration, adequacy at these limits,
3D/material/thermal/dynamic evidence and actual customer acceptance.

Requirements are SPECIFIED; documentation tests are not magnetic evidence.
No robot-joint qualification or LIVE state follows. Next owner action is
Test Lead's versioned decision-contract integration, not another request for
the already delegated mock numbers. Science #42; coordination #643.

Primary context: [maxon's cogging/ripple explanation](https://support.maxongroup.com/hc/en-us/articles/6726327972252-Meaning-and-impact-of-Cogging-torque-and-Ripple-torque)
distinguishes unpowered cogging and energized ripple and their low-speed
effects; [Kollmorgen's frameless motor applications](https://www.kollmorgen.com/en-us/products/motors/frameless-motors)
motivate the joint integration context. Neither source certifies these
selected torque, precision, speed or cost requirements.
