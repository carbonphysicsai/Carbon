# C-W1-D3 bounded learning log

## Iteration 1 — prospective plan (before numerical execution)

Problem: monotonic energy, representation periodicity and extrema dominated by
t=0 can reward incorrect trajectories; no authorized acceptance rule existed.
Hypothesis: time-weighted field/energy trajectory errors plus every-case
physical constraints and replica-envelope comparison discriminate these failures
without rewarding Fourier closure. Falsifier: frozen controls with drift, phase,
wrong decay, suppression or localized errors pass the expected safeguards or
beat exact agreement; reference agreement fails beyond numerical tolerance.

Change: new C-05 derived operators and DEVELOPMENT-only score/acceptance adapter;
leave old signed metrics untouched. Candidate rule is frozen in the rule document
before control execution. Calibration uses a periodic Cole-Hopf solution with
nu=0.2, a=0.25, mode=1, mean=0, horizon=2, 64 spatial points and 65 time points.
Perturbations are analytic, independent of the seen FNO outcomes.

Untouched verification recipe V1 (defined now; do not execute/inspect until rule
freeze): same independently specified closed-form solution, nu=0.13, a=0.35,
mode=2, mean=0.1, horizon=1.5, 128 points and 129 times; perturbation magnitudes
0.02 and 0.08 in initial-amplitude units, phase 0.15 radians, localized Gaussian
width L/20, decay factors 0.5/1.5, frozen initial field and zero fluctuations.
Check analytic mean/energy derivative, field-error identity, nonuniform time
quadrature, explicit crossing censoring and score ordering. This is synthetic
operator verification, not real-model generalization. If rule changes after
inspection, V1 becomes calibration and V2 must be defined before new testing.

Retained FNO-40/FNO-48 is seen development evidence only, never confirmatory.
Cost/outcome and retain/reject decision will be appended after execution.

## Iteration 1 — observed result and decision

All 17 calibration and 17 untouched V1 verification checks passed, including
analytic energy identity and time-quadrature convergence. V1 verification is
now retired to development evidence because a rule revision follows.

Authentic retained data exposed a different resolution issue: the primary
reference's sampled trapezoidal balance reaches 0.0292675724 of initial energy,
above the candidate's 0.025 resolution budget. Thus exact sampled reference
agreement could not be accepted on this cohort. This is temporal quadrature
resolution, not evidence that either FNO is better. The new signed V1 report
retains this outcome. A serialization omission was repaired by recovering only
the missing reference-refinement output; completed measurements were reused.
A scalar wrapper's missing component identity was repaired without numerics.

## Iteration 2 — final prospective candidate

Hypothesis: a maximum sampled energy-trajectory deviation detects the intended
wrong-decay/suppression failure without using a temporally underresolved balance
as a pass/fail predicate. Change only the dynamics gate to max |E_candidate -
E_reference| / E_initial < 0.05, including measured reference sensitivity.
Keep full integral balance and its reference indicator visible as diagnostics.
Do not raise its tolerance or change cases/resources. Other rule values stay
fixed. New measurement v3 and balanced rule v2; old evidence stays immutable.

This is a reference-relative finite-sample fidelity condition, not proof of
continuous energy conservation. Field error still catches phase/spatial errors
with identical energy. The falsifier is a wrong-decay, frozen or suppressed
trajectory remaining within the energy envelope, or exact agreement failing it.

Untouched verification V2, defined before execution: Cole-Hopf closed form with
nu=0.17, a=0.42, mode=3, mean=-0.07, horizon=1.2, 256 spatial points, 193 times.
Use the preregistered perturbation families and explicit new energy-envelope
checks. It has not been used to tune the rule. No third iteration is authorized.
Historical remeasurement under changed v3 is new derived evidence, not a repeat
for reassurance, and still cannot yield retrospective acceptance.
