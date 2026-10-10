# Motor round 2 — the buyer question before the bank

**CHALLENGE-MOTOR-QUESTION-LAW-01 / DEVELOPMENT / SPECIFIED.** Owner-approval
draft, not a runtime law, bank draw, rental, score rule or qualification.
New values are **HUMAN_INPUT with recommendations**. Existing owner policy
and public observations are labelled separately in [the arithmetic sheet](motor-round2.json).

Buyer: a precision robot-joint integrator selecting a smooth magnetic
design and precommitted holding/peak commands, not a purchaser of a certified
robot or two-second thermal rating. KEEP the
[v2 packet](../round1/motor-precision-joint-v2.md), [#776 law](proposals.json),
[quiz content](motor-cooling-quiz.md), [optimizer](../optimizers/motor-precision-joint.md)
and [strong cheap baseline](../cheap-baselines/motor.md). This supplement
does not amend those historical versions or another lane's runtime work.

## 1. Evidence and exactly what is supported

Public Data Collection records, immutable rather than current branch names:

- [registry](https://github.com/carbonphysicsai/Carbon/blob/5f373b199be8f8fc12c7c3e29d345e35d1c7832a/docs/development/evidence/motor-feasibility-02/registry.json),
  [value-checks](https://github.com/carbonphysicsai/Carbon/blob/5f373b199be8f8fc12c7c3e29d345e35d1c7832a/docs/development/evidence/motor-feasibility-02/value-checks.json)
  and s3.json at the same head;
- [panel-export note](https://github.com/carbonphysicsai/Carbon/blob/112759b9c1b267cd8aef34ad6ac2dc3e4ba82216/docs/development/evidence/motor-feasibility-02/panel-export.json):
  44 geometry/skew candidates from 24 public geometries, one frozen holding
  condition, 20 unregistered requirement questions;
- [#917](https://github.com/carbonphysicsai/Carbon/pull/917): current export
  lacks physical geometry coordinates/full signed curves needed for honest
  Kriging/RBF fitting. Re-export and comparator rerun belong to that lane.

All 20 exported questions are **UNRESOLVED under inspected main**. Only
the explicitly simulated rule A+B produces 16 FEASIBLE_EXISTS / 4
NONE_FEASIBLE, with winners d21-skew4 (12) and d09-skew4 (4).
Those are neither an adopted answer key nor P probabilities. The
producer's zero unresolved rate on its holding study is a different basis.
No new host data was read for this draft.

## 2. Action set and boundary-design registration

Recommend the registered feasibility grammar's six **continuous geometry
coordinates**, subject to its validity predicates:

| Coordinate | Proposed support | Unit |
| --- | --- | --- |
| magnet thickness | 1.5–4.0 | mm |
| pole coverage | 0.65–0.95 | fraction |
| air gap | 0.3–1.0 | mm |
| tooth fraction | 0.20–0.40 | fraction |
| opening fraction | 0.03–0.12 | fraction |
| slot bottom | 34–42 | mm |

Freeze 10p/12s double-layer winding and current mapping; 92-mm stator OD,
25.6-mm rotor radius, 35-mm stack, Br=1.2 T, generic Brauer iron, tip/wedge
0.60/0.34 mm. Geometric validity includes slot per-layer width ≥1 mm,
opening clearance 0.2 mm, slot depth ≥1 mm and yoke ≥1 mm. Manufacturing,
material calibration and end-effect adequacy are not thereby proved.

Skew is **discrete {0,2,4} mechanical degrees**, not a continuous coordinate
yet. Three full-stack-equivalent curves at offsets {-s/2,0,+s/2} average
once with 1/3 weights. Hold the physical phase currents fixed using the
registered gamma−5d convention; calculate ripple from the combined signed
curve. Zero-current cogging has no relative-to-mean denominator. Legacy
8p/24s is a separate control, not a smooth coordinate or selectable answer
in this grammar. Chamfers/notches are excluded until frozen and covered.

Data Collection's **prospective boundary-design registration** must name:
physical coordinates/topology/skew, canonical action identity, parent public
panel identity, target requirement/active boundary, fixed command/signed
observer, deterministic interpolation/bracket rule, candidate order,
allowed attempts/refinement rungs, job pins and terminal/refusal handling.
Register before reference outcomes; retain both sides and failed attempts.
Use deterministic geometry bracketing to add **distinct** designs near the
frontier, not extra skew copies counted as independent geometries. Direction,
step/rounding, bracket budget, stopping rule and the exact ordered finite
bank remain HUMAN_INPUT. Do not use ordinal IDs as geometry coordinates.

A continuous search requires a registered discretization/query budget and
covered returned action. The truth comparator is the settled finite bank,
not a global optimum. An off-bank suggestion needs independent truth or is
UNRESOLVED; nearest-neighbour labels do not certify it.

## 3. One question, P(x), Q(x), w(x)

**One full buyer Q3 question** draws a requirement vector, then asks for
one geometry/skew action passing its complete fixed command panel, with the
lowest holding ripple fraction (secondary lower holding current, then frozen
bank order). The current pilot fixes J=10 A/mm², gamma=0 holding; J=15,
gamma=0 peak; J=0 cogging. Holding/slow tracking reuse is one observation,
not two independent service strata. Other current/phase commands are
diagnostics, not post-truth action substitution. Require positive signed
loaded mean and both absolute/fractional ripple limits at both roles.

Recommend continuous **stricter-or-equal** draws inside #776's proposal:

| Buyer requirement | Recommended P interval | Original anchor |
| --- | --- | --- |
| holding mean floor | U[6,7] N·m | ≥6 N·m |
| peak mean floor | U[12,14] N·m | ≥12 N·m |
| energized ripple fraction cap | U[0.04,0.05] | ≤0.05 |
| holding ripple peak-to-peak cap | U[0.24,0.30] N·m | ≤0.30 N·m |
| zero-current cogging peak-to-peak cap | U[0.03,0.05] N·m | ≤0.05 N·m |

Peak absolute ripple cap is twice the drawn holding cap. These mock density
and dependence choices remain HUMAN_INPUT, not observed customer demand.
The narrower subset does **not** adopt #776's easier 5/10-N m floors or
0.06 fraction / 0.36 / 0.07 caps. An owner may select a different, sourced
buyer brief prospectively; this draft never makes a failed motor pass by
relaxing the anchor. No new continuous physical service envelope is claimed.

- **P_job:** product-uniform requirements as a transparent developmental
  hypothesis, with the complete fixed role panel. Correlation/customer-mix
  alternatives need separate owner registration; unsupported regions remain
  HOLD, not silently truncated according to feasibility.
- **P_case (pool):** separate proposal, uniform geometry coordinates on the
  valid grammar, equal skew masses, fixed declared command role. Exact role
  masses/density, validity-conditioned generation and coverage remain
  HUMAN_INPUT. Geometry is an action in P_job, not a buyer service nuisance.
- **Q:** keep a faithful Q3 lane Q_job=P_job. Separately register diagnostic
  Q2 torque/ripple/cogging boundary enrichment and frontier bracketing. Never
  select P questions according to the submitted model's errors or redraw
  NONE_FEASIBLE. Q2 eligibility shortages are reported.
- **w:** recommend unit question weights for that uniform P_job pilot;
  report enriched Q separately. No implicit importance weights or treating
  Q2 counts as buyer frequency. Inner `tasks.py` condition p/q/w do not
  secretly register the outer law. Hard constraints apply in every role;
  weighted mean torque cannot rescue a peak or cogging breach.

Continuous is the recommended primary proposal. Keep the old 243-cell grid
as a **historical audit baseline**, including its different requirement
support; never mix its distribution into the proposed primary law. An
anchor diagnostic is not an undeclared P atom. Exact draws, support,
dependence, objective and variant are adopted only by the owner.

## 4. k, diversity and NONE_FEASIBLE

Recommend **k=12 complete questions per batch**, carrying #776's Motor
pilot, not a powered or adopted number. Test Lead selects k/alpha/control
severity after clustered cross-window power checks. A question is not one
angle, command or independently scored constraint. Q2 field cases have
their own n and bank role.

Recommend **valid forward NONE_FEASIBLE**: the buyer needs to know when no
catalogue design meets the requested joint envelope, rather than choose the
least unsafe motor. Retain the draw and reward correct abstention only under
the future registered score. FEASIBLE_EXISTS needs a covered passing action;
NONE_FEASIBLE needs every eligible bank action proven infeasible;
missing or band-overlapping truth yields UNRESOLVED unless an independent
breach already proves that action infeasible. No false-feasible utility or
made-up money penalty is adopted here. All-none batches cannot establish
the ability to choose a feasible motor; diagnose them, do not redraw them.

Report per P and Q: distinct/equivalent winners, maximum answer share,
FEASIBLE_EXISTS/NONE_FEASIBLE/UNRESOLVED counts, active constraints,
close-call/refinement rate and independent geometry count. Under independent
P draws the occupancy expectation is Σj[1−(1−p_j)^k], excluding abstention
from design winners; p_j must come from a covered law/bank audit. For a
finite bank sampled without replacement use its hypergeometric counterpart,
not that iid formula. Current P/Q expected diversity is **NOT_DEMONSTRATED**.
The public simulated 20-question panel has just two winners, not 20 answers.
Threshold decimals cost no new standard solves only when existing truth
supports the changed limits; they create neither fresh exposure nor
independent scientific evidence. Refined edges may cost extra work.

## 5. T2(a): two bands, each family, no widening

**Test Lead working value (2026-10-08):** ≥5 distinct resolved feasible and
≥5 distinct resolved infeasible designs **within two refinement bands** of
the relevant boundary, for each required question family/stratum. Report
the all-design pass fraction but do not gate on 20–80%. Report feasible-side
proximity too; a distant feasible design cannot certify a contested edge.
One geometry repeated at several skew spans does not fill the independent
frontier-design quota. Exact equivalence/independence policy is HUMAN_INPUT.

Use quantity-specific distances. The public study uses 0.10-N m mean and
0.02-N m absolute ripple/cogging rung-change bands, with maximum normalized
overshoot across its limits. Those are **working refinement diagnostics,
not calibrated truth confidence intervals**. Relative ripple requires its
own registered uncertainty/distance, not arbitrary division by mean. A
multi-constraint boundary needs the other hard limits covered before its
near-feasible count has buyer meaning.

| Family / evidence scope | Current finding | Readiness |
| --- | --- | --- |
| Holding + cogging anchor, 24 public geometries | 5 feasible, 19 infeasible; only 4 infeasible within two bands (d01,d02,d10,d17); next d23 is 4.8 bands | T2(a) **fails even the reported weaker count**; near-feasible-side breakdown also needed |
| Holding floor / fractional ripple / absolute ripple / cogging separately | Joint aggregate does not show ≥5/≥5 at every individual boundary | NOT_DEMONSTRATED per family |
| Peak at frozen J15,gamma0 | Reported S3 designs 7.9–9.9 N·m, below 12; peak not part of the holding feasibility question | No demonstrated full-buyer feasible answer; missing other designs remain unresolved |
| Full holding + peak + cogging question | No complete settled public panel/drawn-law counts | HOLD before bank |

Add frontier resolution, **never enlarge the band** to make d23 count.
Register/refine boundary designs independently of a candidate. Retain the
original question even when its answer is none; diagnostic Q supplies power.
No T3/power acceptance follows from counts or this document.

## 6. Refined-edge truth and reference findings

KEEP signed full curves and standard/rung identities. Registry's standard
mesh/angle settings are 1440 gap / h_max=1 / 0.25°; refinement rungs
2880 / 0.5 / 0.125° and 5760 / 0.5 / 0.0625°. Loaded 12° periodicity and
zero-current cogging coverage are different proof obligations. Refinement
of unchanged physics does not reset E. Refine all potential deciding actions
before a submitted pick can influence the comparator; retain failures.
Intersecting limit/objective intervals refine within a frozen cap or stay
UNRESOLVED. Final uncertainty and allowable residual rate are HUMAN_INPUT.

The public T5 summary calls ≤0.021 N·m a cogging change while saying its
0.02-N m bound was met. **Raw S3 resolves the apparent convergence conflict:**
its eight span rows have maximum cogging change 0.002510 N·m; the maximum
absolute refined cogging value is 0.020507 N·m. Flag the summary's terminology
for acquisition correction, not a numerical failure. No raw S3 span exceeds
the stated cogging-change bound. These cross-checks still do not resolve
missing 3D end/skew effects. Independent buyer-tool witnesses follow
[reference credibility](../round1/reference-credibility.md): separate public
draws or retired published cases, pointwise **and** decision agreement.
Tool disagreement is a reference finding, not candidate failure; revision
is prospective and never silently re-scores sealed historical material.

## 7. B, E and startup cost: keep the units visible

[OWNER-BANK-ARCHITECTURE-01](../../../../.agent/decisions/2026-10-07-OWNER-BANK-ARCHITECTURE-01.md)
approves Motor-class DEVELOPMENT **B=10n, E=10**. n is the registered number
of cases of that bank served per window; it is not a geometry count or a
universal alias for k. Battery pool E=2 does not transfer. Apply only in a
new rule; this document changes no deployed bank.

Under `design_bank` one bank case is a **complete question**. Recommend
prospectively n_Q3=k=12 and B_Q3=120 questions *if* adopted; action menu size
M and unique physical-job count U are different. Pool/Q2 n is HUMAN_INPUT.
The runtime has a reference-feasible live-only path: valid forward
NONE_FEASIBLE requires an explicit future Motor terminal-status/score
integration, not this prose or a silent widening of the Battery path.
The validator owner owns that seam; no runtime edit here.

Charge every question appearance, including later-voided windows, to its
registered E. Shared physical truth also retains underlying case/bank
exposure links: a new threshold/question ID must not renew the same hidden
action's E. Exact cross-question exposure enforcement is a validator-owned
adoption dependency, not assumed present. Retired cases auto-publish only
after required windows end/reveal and are journaled; never return to hidden
use. No hidden seed/ID/manifest is present in this draft.

User's prospective planning C1: **1.2 allocated CPU-h standard; 8 rung-2**.
Public shared-host allocation p50/p95 is respectively 1.157/1.847 and
8.055/15.694 CPU-h (wall×2 CPUs, upper bound). These are not measured
CCX63 process CPU use or billable durations. Rung-3, failures, witnesses,
retained verification and setup are additional, unmeasured costs.

The public note calls J0 + J10 + four skew variants **five** standard
solves; the enumerated components total **six**. Show both; recommend six
until a deduplicated acquisition manifest resolves it. A complete peak
panel across these spans may add five loaded-curve solves per geometry;
that is a **manifest hypothesis**, not a measured full-task C1. Its table
does not budget extra peak-role refinement; those jobs must be added to a
complete acquisition manifest. One boundary
geometry adds the reported four rung-2 solves, not one 8-hour allowance.

For unique geometry bundles U and refined bundles R:
`H = 1.2 × s × U + 8 × 4 × R`, with s=5 (reported) / 6 (conservative holding)
or 11 (holding+peak hypothesis). U is the union of actually needed jobs,
not B×M automatically. A common 44-action bank reused for 120 threshold
questions has U=44, whereas 120 independent 44-action panels have U=5280.
They have very different scientific dependence/exposure as well as cost.

At the requested **€1.37 per CCX63 node-hour**, illustrative **serial
allocated-CPU-hour = node-hour** costs (not measured quotes/throughput):

| Inventory scenario | Allocated CPU-h | Bare-node cost |
| --- | ---: | ---: |
| 44 shared holding bundles, reported s=5, no refine | 264.0 | €361.68 |
| 44 shared holding bundles, conservative s=6, no refine | 316.8 | €434.02 |
| Same, 9 frontier bundles ×4 rung-2 (rough 20% scenario, not measured rate) | 604.8 | €828.58 |
| 44 full-panel bundles, s=11, plus same 9 refined bundles | 868.8 | €1,190.26 |
| 120 independent 44-action holding panels, s=6, no refine | 38,016.0 | €52,081.92 |

No divide-by-advertised-vCPU shortcut establishes a bill. Let a measured
CCX63 workload throughput be g allocated CPU-h per billable node-hour:
bare cost = 1.37H/g. Actual price, tax, concurrency, RAM, failures, artifacts
and parallel efficiency must be quoted/measured. With an illustrative 19%
VAT and €10 non-node reserve, €100 leaves 55.20 node-hours: the 604.8-hour
holding example needs g≥10.96. **NOT_DEMONSTRATED**, not permission to spend.
Its serial p95 sensitivity (standard 1.8467, rung2 15.6944) is about
1,052.52 allocated CPU-h before extra costs. This is sizing arithmetic,
not an assertion that the €100 guardrail fails on a parallel CCX63.

E=10 amortizes turnover, not startup. For an adopted B_Q3=120/k=12, 100
windows is only an appearances upper bound B×E/k without top-ups; uneven
sampling/retirement/active-window disjointness can stop earlier. Repeated
threshold questions sharing an action bank must cluster power by that bank,
not manufacture 100 independent experiments. Startup and turnover require
their own exact paid/free execution authorization; this draft grants neither.

## 8. Required return, freeze and smallest decisions

Data Collection returns public supported coordinates/full signed curves,
unique geometry and command manifest, each family's near-side counts under
two bands, full-role feasible/none/unresolved states, refinement failures
and corrected cost/T5 discrepancies. Optimizer Codex supplies registered-law
clustered power/diversity/close-call reports. No solver or power run here.

Before a bank draw: owner adopts law/support/dependence/objective and the
role scope, k/n/B/E/rule version; Test Lead supplies bands, T2/T3/score and
unresolved policy; acquisition supplies adequate complete truth and an exact
deduplicated manifest; validator owner resolves NONE/exposure/task seams;
operator supplies pins, CPU/RAM/spend enforcement, quote and authority.

**Recommendation:** freeze this as a proposed full-buyer law, but HOLD its
bank rental until peak feasibility and every contested boundary are covered.
If the owner instead wants a holding-only product, explicitly approve a
separate buyer-valued scope: this is not an implicit reframe or a delivered
12-N m robot joint. No additional packet numbers are needed to keep drafting.
Motor's original requirements, other seven laws, Battery EV5/journal14/live
contract and all sealed evidence remain unchanged. No earned reference tier,
hidden-bank readiness or scientific/security/production qualification.
