# First magnetics panels — buyer decision before bank size

**MAGNETICS-FIRST-PANELS-01 / DEVELOPMENT / SPECIFIED / NOT_APPROVED.**
Prepares the [solenoid pole](solenoid-pole.md) and [planar transformer](planar-transformer.md)
from [#928](https://github.com/carbonphysicsai/Carbon/pull/928) at
536a2716bd24a41751a1d382fca40038ff1384ae. These are conditional candidate
customers, not adopted replacement Challenges. [Proposed schedules/budget](panels.json)
are not a runner manifest. No solver, container build, paid execution, real
panel measurement or hidden/AX42-data access occurred.

## What motor actually supplies

Audit at main 432d22b786a7341de788bc8b1206526849f3a31f:

| Asset | Disposition / precise boundary |
| --- | --- |
| `scripts/dev/motor/reference/Dockerfile` | KEEP binaries: GetDP3.5.0, Gmsh4.15.2, source SHA checks, Ubuntu snapshot. Existing published image below; verify run identity, not a mutable tag. |
| `carbon/motor/getdp.py` | WRAP source-current and nonlinear iteration patterns; planar 2D A_z formulation. New constitutive tables, energy and inductance/force observers need proof. |
| `carbon/motor/mesh.py` | KEEP Gmsh API/version and tagged-region pattern, not circular rotor/stator geometry, moving-band nodes or periodic angles. New grammar/CAD/mesh and area checks. |
| `scripts/dev/motor/reference/run_batch.py` | KEEP isolation/resource/failure/ledger concepts; motor input and torque reader cannot accept these new jobs unchanged. New domain adapter later, owned by acquisition. |
| Motor material/output acceptance | NOT reusable scientific authority: generic Brauer iron is neither the buyer's solenoid steel nor transformer ferrite. Torque is not axial force or an inductance matrix. |

Published environment candidate, recorded by the
[acquisition deck](https://github.com/carbonphysicsai/Carbon/blob/0f12834226f65cdb317e7407e1e83e68c135801b/scripts/dev/reference_packages/elmer/f13_deck.py)
as its motor mesher image:
`ghcr.io/carbonphysicsai/carbon-motor-reference@sha256:599521e79786ee0326a0754ba0545f51ee9665adff73c3515c8d4b8ba24c1c05`.
This is the acquisition source's mesher/reference environment candidate, not
proof that the new deck works. GetDP archive SHA256
`bca39450cc6f33feac27bff1c8c3e47bb200f44679b0f03d85820def84ef1444`;
Gmsh archive SHA256
`2dbd68d033f99b05789554bf4db6d47f4108dd36b0b36d4a50935df0ceb9e772`.
Reviewed Git blobs: Dockerfile `fdc429d87cb12196a4258f53ae7e4a8d3133c28f`,
getdp.py `8e25254333ea539fff3ae3bc15e9b0eb3028e211`, mesh.py
`fdbfba29db5ebd3f9ac44ca1dbf00ed168c03576`. Material, geometry, deck,
extractor, resource enforcer and independent-tool pins remain HUMAN_INPUT.

GetDP supports axisymmetric Jacobians, but selecting one does not automatically
turn motor's Cartesian formulation into an actuator. Verify basis/axis
regularity and 2*pi normalization in the exact build. [GetDP 3.5 manual](https://getdp.info/doc/texinfo/getdp.html#Types-for-Jacobian).

## Approval and stage gates

1. **Zero-spend binding:** owner/customer approves anchor drawing, winding,
   material tables/rights, duty/temperature applicability, hard limits and
   objective. Every unresolved input in the family specs blocks that output
   or verdict. The earlier round-1 delegation does not adopt these new families.
2. **Package feature proof:** acquisition freezes image/source/CAD/mesh/deck/
   extractor hashes and demonstrates the named controls in an approved
   environment. Authoring/rights labour and any extra build cost are not
   hidden inside a solve-time estimate; add them to the proposal if charged.
3. **Grant proposal:** EUR20 **each** (EUR40 if both selected), not a shared
   transferrable allowance and not owner-approved today. Actual quote, tax,
   witness-tool access, startup cost, enforcement and retained ledger must fit.
4. **Sequential triage:** controls and a nominal design first; then the fixed
   ten-design/three-stratum screen. Stop on reference inadequacy or cap. Return
   partial coverage explicitly, never a feasible bank from a favorable subset.
5. **Admission remains separate:** refined feasible witness; contested boundary
   counts per stratum; changing answers; adequate reference; baseline advantage;
   qualified question/power/cost contract. This small panel cannot earn them all.

P is actual customer-job prevalence (HUMAN_INPUT); these fixed cases are Q,
with no inferred population weights. w/score use is HUMAN_INPUT. Controls and
witnesses are separate non-hidden public diagnostics, not official exam draws.
The one-band framework count is primary; report the Test Lead's two-band
working sensitivity separately. Do not widen a band or loosen a safety limit
to reach five-plus-five. Ten designs are only the theoretical minimum; they
do not guarantee five on either side or broad answer diversity.

## EUR20 arithmetic — scenarios, not measured C1 or a live quote

Use the owner's planning rate EUR1.37/node-hour, **no core-count division**.
Assume one serial solve/one worker thread; elapsed/CPU ratio1; tax multiplier
1.19; two allocated node-hours for startup/idle/meshing/baseline fit/benchmark
overhead; EUR5 noncompute reserve. These are **ASSUMPTION**, not tax advice,
a vendor quote or an implemented spend guard. Smaller overhead than #928's
four hours/EUR10 assumes its existing image and prepared package can be reused;
if not, reprice. Human labour and a new paid buyer-tool licence are unpriced;
the zero incremental licence assumption must be confirmed or the panel stops.

`cash = 1.37 * 1.19 * (2 + U * C1) + 5 EUR`, with complete-case-equivalent U
derived in each spec. C1 includes all excitation points/field states and
extraction, not one matrix solve or one stroke. The overhead covers additional
mesh/fit work; any measured excess is charged. Refinement costs are separate.

| Proposed screen | U | C1 CPU-h low/base/high (UNMEASURED) | Cash low/base/high EUR | EUR20 conclusion |
| --- | ---: | --- | --- | --- |
| Solenoid | 59.3333 | 0.01 / 0.04 / 0.12 per 27-point case | 9.23 / 12.13 / 19.87 | All hypotheses fit narrowly; no tail/feature proof yet |
| Planar 2D magnetic slice | 54 | 0.03 / 0.08 / 0.20 per five-field case | 10.90 / 15.30 / 25.87 | Base fits, high does not; cannot promise a complete panel at EUR20 |

The reserve leaves at most `(20-5)/(1.37*1.19) = 9.20076` node-hours total,
including the two-hour overhead; variable allowance is 7.20076 hours. Hypotheses
are inherited C1 ranges from #928, expanded for solenoid virtual-work probes.
No measured p50/p95 exists. Proposed total wall cap **9.15 node-hours** makes
the stressed compute+reserve bill EUR19.9172; storage/licence/reserve overruns
still stop before dispatch. One worker, two allocated vCPUs/one solver thread,
no GPU, RAM ceiling16 GiB, initial complete-case timeout45 min; verify capacity
before approval. All failed attempts count; no automatic retries. A case is
not dispatched unless its worst-case reservation fits the remaining cap.
These are proposed enforcement settings, not an enforcement implementation.

For planar, run the first three nominal cases as a *prefix* of the fixed panel,
not extra uncounted pilots. Re-estimate the full bill from measured cost;
if above EUR20, return an incomplete screen or request a new cap. Do not drop
hot/tolerance strata, point states, end effects or witnesses to force a green.
Full 3D/end-turn proof is a separately priced stage and is **not included** in
the 2D EUR20 estimate. The owner can choose solenoid first; no panel is started.

## Data Collection return

Return frozen bindings and every scheduled action/stratum, complete force
curves or signed inductance matrices, material/flux applicability, refinement
bands, all mandatory margins and NOT_CHECKED outputs. Give T1 all-strata
witness, T2 near-feasible/near-infeasible counts, buyer-unit spread and changing
picks, NONE_FEASIBLE vs UNRESOLVED, and close-call/refinement rates. No binary
verdict with an unapproved hard limit or missing coupled safety output.

For each invocation/field state: source/image/deck/mesh/material/extractor
identity; node/element counts; solver iterations/residuals; CPU user+system
sum including children, wall, RSS and resource enforcement; failures, startup,
idle, fit/query/retained-verification and billed cost. CPU-h is not allocated
vCPU-h. Record exact completed vs censored work, not a p95 from a tiny success
sample. Compare strongest cheap baseline under identical limits/information
using held-out designs and retained verification, reporting feasibility/pick
agreement, false-feasible rate, buyer-unit regret and abstention. If the circuit/
catalogue/interpolated map already makes the right decisions, report V4 failure.

Tier2 is a target: independent buyer-tool witness custody, same explicit
geometry/material/excitation/output definitions, pointwise and decision agreement.
No hidden cases; source differences are reference findings, never candidate
failures. Historical references/results remain versioned. T3/power, qualification,
adoption, replacement and any official bank are separate owner/Test Lead work.
