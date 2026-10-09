# Motor — ordinary full-curve response surfaces, not a weak torque average

**DEVELOPMENT / SPECIFIED; performance NOT_MEASURED; acceptance HUMAN_INPUT.**
[Shared comparison](README.md); [return checklist](data-collection-return.md).
Buyer: [precision-joint v2](../round1/motor-precision-joint-v2.md).

## Buyer decision and incumbent

Choose geometry and precommitted precision/peak commands: holding mean>=6 N m,
peak mean>=12 N m, energized ripple<=5% **and** <=0.30/0.60 N m respectively,
zero-current cogging<=0.05 N m peak-to-peak. Retain the packet's holding-ripple,
current-density and frozen-order ranking. Magnetic results do not certify
burst thermal duty, robot stiffness or tracking dynamics.

CLOSED_BANK: exact curve/command lookup with the same geometry inventory,
command choice and decision reductions. NEW_SUPPORTED: ordinary response
surface, Kriging and RBF candidates fitted to complete torque curves or signed
Fourier coefficients, then the identical budgeted geometry/command search.
Choose method/order on fit/calibration data, not witnesses. An analytical
magnetic circuit can be a sanity control, not the sole strongest incumbent
when an ordinary fitted FEM response surface is available.

## Method basis and reuse

[Ren et al., 2020](https://pdfs.semanticscholar.org/8117/28aba09d970a1bd7a289f42119dce7867c60.pdf)
uses Kriging/RBF surrogate-assisted electrical-machine optimization including
cogging. This supports the inexpensive method class, not parity at Carbon's
robot-joint limits.
[Ansys Maxwell Optimetrics](https://ansyshelp.ansys.com/public/views/secured/electronics/v242/en/subsystems/maxwell/content/Optimetrics.htm)
documents a commercial electromagnetic design-of-experiments and response-
surface workflow. Tool availability does not establish adoption by this buyer
or agreement on the registered joint decision. KEEP public curve extraction and
[existing baseline inventory](../../../../scripts/dev/motor/reference/baselines.py)
as reusable engineering assets; old-space results are not revised-space truth.

Separate legacy 8p/24s from prospective 10p/12s double-layer / three-slice skew
study identities. Never interpolate across pole/slot/winding topology as if
those were continuous coordinates. Exact GetDP/Gmsh, material, current-density
to phase-current mapping, skew slices, geometry grammar, mesh, angle period
and extraction pins must come from the accepted acquisition manifest.
New baseline environment/coefficient/truncation pins remain HUMAN_INPUT;
this ticket does not register the revised grammar or package.

## Witness and decision checks

Hold out whole geometries and all their commands/angles together. Independently
covered public/retired witnesses include zero-current cogging, saturation/high
current, valid geometry edges, torque/ripple boundaries and competing picks.
Retain signed curves; reconstruct between-angle extrema under the reference
policy. Check mean, absolute peak-to-peak and relative ripple separately;
near-zero cogging has no mean-divided percentage. Reduced harmonics cannot
smooth away the 0.05-N m breach. Refine deciding extrema and skew/mesh error.

Report per-command/geometry feasible sets, selected-command violations,
reference best/equivalent picks, ripple-fraction regret plus absolute N m
diagnostics under the frozen objective. No missing reference becomes a pass.
Legacy all-NONE_FEASIBLE is not a failure of the revised study or a reason to
lower torque/ripple requirements. Thermal/dynamic unsupported claims abstain.

## Cost, stop condition and credibility

The unit is a geometry's complete required command/angle/skew panel; retain
individual solves and launches separately. Current complete-panel C1 and
baseline cost are NOT_MEASURED here. Charge FEM training acquisition, harmonic
extraction, ordinary-model fitting, search and final verification including
no-load cogging. Equal physics/query allowance for Carbon and incumbent.
If ordinary surfaces/cache make equivalent decisions within buyer latency,
report no demonstrated V4 advantage. Tier 2 remains a target against the
packet's assumed buyer magnetic workflow, not an earned physical motor claim.
