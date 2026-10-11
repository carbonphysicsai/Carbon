# Backward-facing step — source-linked customer design packet

BENCHMARK-PACKETS-01 · DEVELOPMENT / SPECIFIED. Proposed family label, not a
runtime Challenge ID. [Research basis](../../../../Business/research/benchmark-challenge-briefs/BACKWARD_FACING_STEP.md);
[owner decisions](backward-facing-step-owner-decisions.json). All new numerical
acceptance and buyer limits are HUMAN_INPUT. No reference solve was run.

## 1. Engineering job

**Mock buyer:** an internal-flow design/CAE engineer at a duct, valve or flow-
channel supplier. Choose one manufacturable expansion/recovery contour that
minimizes total-pressure loss across a complete service brief while satisfying
separation/recovery and packaging requirements. The output is a design choice,
not a memorized NASA reattachment value.

The [Rheinmetall-authored workflow](https://www.ansys.com/content/dam/resource-center/case-study/numerical-fluid-optimization-exhaust-gas-flap-valve.pdf)
uses constrained flow-channel design, CFD, DoE/metamodels and robustness studies;
[SU2's independent tutorial](https://su2code.github.io/tutorials/Inc_Turbulent_Bend_Opt/)
optimizes pipe-bend pressure drop. These establish adjacent industrial and open
engineering workflows, not demand for this exact step family or a real Carbon
customer. Buyer role and transfer to planar recovery design are **ASSUMPTION**.

Value is avoided pumping/fan power at a required flow, fewer rejected design
revisions and faster robust geometry selection. Recommend reporting pressure-
loss regret in Pa, and illustrative power difference `volume_flow * delta_p`
in W only with a consistent incompressible flow definition; input duty cycle,
efficiency, energy price, annual decisions, revision cost and acceptable latency
are HUMAN_INPUT. No asserted euros, revenue or market volume. A wrong choice
can violate a flow/recovery requirement despite low average prediction error.
Not a full valve, thermal, combustion, noise or arbitrary 3D product design.

## 2. Physical system

Use a 2D turbulent separated-flow expansion with a recovery contour, viscous
walls and a fully specified developed inlet state. Freeze material density,
viscosity/temperature law, geometry, upstream development, turbulence inputs
and outlet/back pressure. Boundary-layer thickness alone is not a complete
inlet profile; changing Re requires a consistent profile/model setup.

The [NASA/TMR source case](https://tmbwg.github.io/turbmodels/backstep_val.html)
states Re_H approximately 36,000 (not the earlier 50,000), Re_theta 5,000,
upstream boundary-layer thickness about 1.5H, Mach 0.128 and a straight opposite
wall. Those are **anchor facts**, not approved buyer support. Re_H uses its
named U_ref near x/H = -4; Re_theta is not interchangeable. Do not scale a
geometry without maintaining the chosen nondimensional and material laws.

Research's ASSUMPTION low/base/high design hypotheses: recovery length/H
0.5/2/4, radius/H 0/0.10/0.25, expansion-ratio factor 0.95/1/1.05;
Re_H factor 0.8/1/1.2 and inlet-thickness factor 0.9/1/1.1. They require
accepted support and the actual anchor height ratio derived from source grids.
Recommend a monotone connected spline contour with fixed inlet/outlet planes;
degrees of freedom, allowed curvature, clearance and profile law remain open.
These endpoints are neither a uniform law nor registered cases.

## 3. Population P, Q and w

[Question law](backward-facing-step-law.md) separates buyer service/requirement
P, diagnostic/near-boundary Q and evidence/decision w. No P/Q/w is approved.
Define support after [anchor/copy exclusion](contamination-contract.md), within
reference applicability; audit rejection and missing-support rates. Varying
requirements on an already solved bank is legitimate, but does not renew E.
One independent observation is provisionally a complete buyer question with
its full design/scenario bundle; dependence model and statistical claims open.

## 4. Case contract

An eventual tuple binds physical contour, material law, developed inlet and
operating state, plane/observation contract, reference identity and rung.
Meshes are representations, not new designs. Reject self-intersections,
disconnected/negative-height channels and conditions outside accepted support.
Missing inputs are unsupported/UNRESOLVED, not an infeasible design.

Recommend a nondimensional wall-contour distance integrated over an approved
x/H window, with separate expansion/feature and condition distances in
log(Re_H), Mach and inlet-profile coefficients. Compare against all audited
source entries under approved coordinate/scaling equivalences. Require a
geometry component; changing Re on the published contour is not enough.
Window, normalizers, floors, group, component weights and acceptance are all
HUMAN_INPUT. No secret hashes, seeds, distances or labels are public here.

## 5. Reference policy

Research's candidate route is SU2 source
`bc15466602a687d6fb796d5df7a12ce3fde0949a` (LGPL-2.1). A source pin is not
an image: build/dependency lock, image digest, CPU/MPI policy, turbulence option
mapping, deck, mesh ladder and measurement adapter remain missing. In particular
NASA's SSTm and SU2 options must be matched explicitly, not equated by name.

Code verification (exact/MMS component tests), convergence and conservation
are distinct evidence. Recommend nested meshes, wall resolution and inlet/
outlet-length sensitivity; numerical acceptance/error budgets are HUMAN_INPUT.
Convergence cannot remove turbulence-model error. Typed FAILED_INFRA and
reference/model inadequacy cannot become candidate failure.

**Credibility target: Tier 2, NOT_DEMONSTRATED.** Mock buyer tool assumption:
Ansys Fluent, supported as an adjacent workflow, not market-share evidence.
SU2 is not that tool. Compare matched decks on the public NASA anchor and
independent non-hidden novel task witnesses, pointwise **and** verdict/pick/
regret measures. Tool/version and tolerances require buyer/science approval.
NASA's measured reattachment interval is anchor evidence for that observable,
not Tier 3 for novel contour pressure-loss decisions. No matches-reality claim.

## 6. Output and measurement contract

Report mass-flow-weighted total pressure at **fixed named planes**, loss in Pa,
and a dimensionless loss coefficient using an approved dynamic-pressure
convention. Surface Cp/Cf and velocity/turbulence profiles remain separately
located and normalized. NASA's shifted Cp cannot establish absolute loss.
Retain units, reference scales, flow direction, mass balance and uncertainty.

Determine separation and reattachment from signed wall shear with an accepted
multiple-crossing policy; no forced unique root or arbitrary clipped value.
NASA reports x/H reattachment 6.26 ± 0.10; retain the source's interval, do not
convert it into a population confidence statement. Plane definitions, limit
directions, allowed reversal and admissible uncertainty remain HUMAN_INPUT.
Mandatory constraints precede ranking; no soft metric compensates a failure.

## 7. Construction contract

No construction capability is registered for this proposed family. Recommend
reuse of current authoring/case projections and bounded TrainingStrategy
reconstruction, with only approved public TRAIN data. Backends, output tensor
layout, normalization, resources and rebuild vocabulary require their owners.
No arbitrary solver execution, official data access or LIVE rights are added.

## 8. Research kit

Provide source-attributed anchor documentation, legal-use notices, accepted
grammar/units, public generator, reference wrapper, training runtime and
incomplete practice. All but research documentation are gaps for this family.
Published anchors may be labelled public diagnostics but never exam examples.
Practice cannot reveal protected draws, novelty distances or decision labels.
Licensing the solver does not automatically license every vendor asset.

## 9. Evidence plan

[Panel plan](backward-facing-step-panel.md): verify reference components,
reproduce the non-scoring anchor, test exclusion on known equivalents, then
measure independent novel designs across complete scenarios and frontier rungs.
Precommit question/limit/refinement identities, reuse index and all attempts.
Measure contested boundaries, complete feasible answer, margin spread, changed
picks and cheap-baseline/equal-budget gain before any hidden bank.

Strong competitors: applicable published loss correlations (round-pipe fits
are not automatically planar-step models), audited anchor lookup, calibrated
response surfaces, competent coarse-to-fine RANS and direct/adjoint optimization.
Hold out whole contours and scenario bundles. Charge setup, fitting, queries,
refinement, failures and final verification; if the cheap route wins, report V4
failure rather than an artificially weak competitor. Four behavioral controls:
edge-optimist, over-cautious, sign-error and lookup/optimizer-aware. Power and
thresholds belong to Test Lead. Fresh confirmation needs its separate grant.

## 10. Readiness and claim record

Exists: source-confirmed research, historical generated drafts and these
prospective specifications. Ran: document/arithmetic checks only. Missing:
approved law/grammar/novelty rules, pinned working package, reference adequacy,
registered tuples/TRAIN, kit, observed cost and decision studies. No stage exit,
qualified tier, tested Challenge or customer acceptance is earned.

Next: owner/Test Lead settle [one decision inventory](backward-facing-step-owner-decisions.json);
Data Collection prepares an exact public manifest/package, then receives any
needed execution grant. Cost hypotheses are in the panel; high startup exceeds
EUR 100. No lowering safety or performance demands to force feasibility.
New versions only; Battery history and portfolio queue remain untouched.
