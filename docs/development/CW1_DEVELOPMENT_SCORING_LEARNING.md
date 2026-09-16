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
