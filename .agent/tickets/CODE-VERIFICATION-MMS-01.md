# CODE-VERIFICATION-MMS-01 — reusable, image-bound verification

Owner's ordered 2026-10-10 batch, after EVIDENCE-READINESS-CHECK-01. Independent
main-based PR, never stacked. Reuse pending #1030 Elmer heat MMS and #1019's
reference-stage exit policy; do not duplicate package builds or change them.

Specify manufactured/analytic fields, source terms, BC/IC, ladders and expected
orders for Elmer heat, GetDP magnetostatics, PyBaMM particle diffusion/lumped
heat, Elmer acoustics, OpenFOAM flow/scalar, Meep modes and CalculiX elasticity.
Implement a common headless CPU result checker and native tests where package
APIs exist. Explicit gaps remain blocked, rather than relabelling generic
Poisson tests as verification of every production feature.

No solver runs, builds, spend, hidden bodies, AX42, EV5, sealed journal or live
contract edits. Data Collection runs every native solver test. Synthetic tests
exercise symbolic derivation, norms, order calculation, failure/identity
semantics and deck/adapter structure only. Pass bands are DEVELOPMENT
recommendations awaiting science/owner acceptance, not production tolerances.
Repin/rebuild requires fresh verification at the new identity. Code verification
is necessary, not solution adequacy, Tier-2 validation or qualification.

DoD: seven-family specifications, pinned source pointers and explicit missing
image/feature gaps; runnable basic native arms for GetDP, PyBaMM, Elmer acoustics,
OpenFOAM scalar transport, Meep propagation and CalculiX modal frequencies,
reusing #1030 Elmer heat; common image-bound field/frequency checker; no false PASS
on an absent rung/field, wrong image, constant/zero error or missing criteria;
Data Collection handoff with exact commands and remaining work; applicable CI.
