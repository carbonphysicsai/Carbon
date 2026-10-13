# Bolted joint — conditional public winnability pilot

**SPECIFIED / PROPOSED ASSUMPTION / not authorized.** No execution in this ticket.
Current end-to-end runnable: **NO**. Reviewer Carbon Validator; Data Collection
packages/acquires, Optimizer fits/compares, Model Kits supplies the covered kit.
Common [preflight, cost enforcement and exact report readers](README.md) apply.
[Auditable count/ranking sheet](plans.json): `bolted-joint`, rank5.

## Buyer decision and public/representative support

Joint-design engineer chooses a full3D eccentric two-bolt assembly/preload/contact design through assembly-lock-service. REPRESENTATIVE rehearsal, never a customer result.

Existing representative action ranges: bolt diameter[8,12] mm, spacing[40,70] mm, support thickness[8,16] mm, preload_max[8000,16000] N. Use all four existing bolted_rehearsal.conditions(), not three easier ones. Source inputs give fayingmu[0.1,0.3], alpha_A[1.4,2.0], opening load[1000,4000] N, shear[500,2000] N; these bounds do not authorize arbitrary independent redraws. Elastic E197000 MPa/nu0.29 is not a bolt grade. Yield/contact laws and all safety allowables remain HUMAN_INPUT.

Hard safety limits never relax for feasibility. Missing buyer ranges/materials,
objective or P/Q/w stay HUMAN_INPUT; no official population/bank is created.

## Solver/image and native applicability

CalculiX 2.23 source-locked modal build, NEW nonlinear contact/pretension history. Historical environment candidate:
`sha256:d9ef68d016226a945c7eefcb6b2261c60a11249ee0f93458ae6c3aca956fd6f8`.
Current presence **UNKNOWN**; exact task/deck/extractor/transport receipt required.
MMS status: **CONTACT_HISTORY_ACCEPTANCE_NOT_DEMONSTRATED**. Existing owner acceptance is discretisation only,
not full reference adequacy or new family/observer acceptance. No Tier2 is earned.

## Register data, k and attempts before truth

16 registered geometries x all four service histories =64 TRAIN records;12 distinct held-out geometries x four histories =48. Group all increments/load/friction/preload/rungs by physical geometry. Include complete assembly/lock/service states; do not use a tied or force-maintained bolt model to make training cheap.

Proposed k=8 complete buyer questions/batch, independently frozen within
the supported requirement law; not48 correlated cases or
12 actions disguised as independent questions.
P is the buyer request law (HUMAN_INPUT); Q is the tagged diagnostic/frontier
proposal; w is independently approved evidence use, not Q's frequencies.
Whole-geometry internal calibration folds use onlyTRAIN. Refine deciding edges
under the adopted uncertainty policy (otherwise HUMAN_INPUT); intervals crossing
a hard limit stay UNRESOLVED. No redraw of NONE_FEASIBLE or widening two bands.

112 complete primary histories +4 controls +12 refined histories +4 failure slots =132 attempts; at2x refinement cost144 coarse-case equivalents. C1 low/base/high0.03/0.08/0.24 CPU-h is UNMEASURED discovery hypothesis. +8 CPU-h fit/check reserve yields12.32/19.52/42.56. A full nonlinear history, not one increment, is the case cost. Native contact/lock verification precedes bulk acquisition.

Controls / observer coverage: Elastic affine patch; applicable smooth elasticity/force-moment closure; two-spring pretension/lock and same-state restart; Coulomb contact transition. Four control allocations must cover their complete declared ladders or HOLD/reprice. Rung refinement never substitutes for unverified service-state retention.
Attempt caps include failures, probe, refinements and every required excitation.
Solver version or successful controls do not prove buyer-tool Tier2 agreement.

## Three arms and exact value evidence

**Cheap:** VDI-style member/bolt compliance and eccentric group plus the strongest calibrated contact-aware cached FE/response surface. Hand calculation alone cannot predict opening/slip/stress; its missing fields must abstain.

**Plain L0:** Existing carbon_arm.TRAINER_DEFAULTS: width256, depth3, GELU, 6000 Adam/cosine steps, float64; public seeds0/1/2; CPU only; do not tune on heldout. Training labels=64, from
16 physical training geometries/schedules; all three fits
share <=4 aggregate CPU-h of the total cap. If that size/time cannot train,
report INDETERMINATE and propose a new counted dataset, not a tuned success.
Use independently predicted compact outputs required by the observer; known
action objectives such as integrated extra joules are computed identically
for all arms rather than treating arithmetic as learned privileged value.

**Solver alone:** freeze a competent direct/adaptive policy with the same
geometry/menu, hard limits and complete-case accounting. Record actual trace,
initialization, public-physics use and every failed/refined call; no hindsight
best-in-bank or deliberately bad ordering. Policies are external inputs to
OPT-12, not algorithms implemented by its replay.

Pointwise learning unit: mm (opening/slip/displacement diagnostics); objective/regret unit HUMAN_INPUT.
Read learnable/advantage/headroom through the exact [common mappings](README.md);
include raw per-stratum maxima/coverage, near-boundary counts, finite-bank picks,
regret and uncertainty. No aggregate low error can erase an unsafe pick.

## Compute, bill and expected duration

Hard proposed cumulative actual CPU cap **48 CPU-h**; one32-vCPU/64-GB
RunPod CPU pod, allocation-to-confirmed-termination **56 h** maximum.
Entire allocated capacity **1792 vCPU-h** is billed
regardless of1/2/4 used cores. Conditional worst all-in **USD67.60**,
only with current inclusive compute quote <=USD1.20/h and all extras <=USD0.40.
Probe: first complete coarse case, <=30 min lifecycle,
<=USD1.00, INCLUDED in all caps. RAM must remain<=16 GiB
working RSS under the64-GB profile; source RAM is a hypothesis, not measurement.
A larger working set needs a prospective plan/quote, not an automatic host switch.

CPU scenario L/B/H 12.32/19.52/42.56 h;
serial wall hypotheses 13.32/20.52/43.56 h.
These include a quota reserve, not measured fit/preparation times. Status:
**SERIAL_HYPOTHESIS_NOT_MEASURED_COMPLETION**. CPU/elapsed ratio and new-case p50/p95 are
UNMEASURED; only the cited historical anchors are observations. Caps limit
partial work; they never promise completion. Stop on adequacy, memory, count,
CPU/wall/cash or deletion-tail risk and retain an honest incomplete return.

## Runnability holds and next artifact

- Verified retained solved extension through lock/service, contact mesh and observers
- Matched material/strength/friction laws, rights, hard limits and objective
- Real family learner kit, strongest contact-aware FE arm and current image presence
- Existing replay route `bolted-joint`: inspect scope/registration and complete inputs; it is not an execution grant.
- L0 kit status: **NOT_IN_CARBON_ARM_KITS**.
- Independent CPU/deadline/spend enforcement, quote/capacity, exact owner grant,
  expiry/deletion proof and retained ledger: not supplied by this plan.

Existing deck emits a deliberately non-runnable service template. Never force-maintain assembly preload, tie contacts, start service stress-free or treat stress/ slip omissions as zero. The main-only readiness wiring stays0/7; existing proposed budget is not adopted or a grant.

Data Collection's next artifact is the bound tuple/pin/reuse/adequacy and
complete-case timing receipt with these holds resolved or explicitly rejected.
The owner chooses pass/park thresholds and Challenge #2 only after the results.
No hidden bank, EV5/journal14/live-contract changes or commercial claim.

## Source basis (audited main f878ed9529e85cd8d5443266661bc9419b8ee356)

- [inputs.json](../../../../../docs/development/challenge_pipeline/bolted-rehearsal/inputs.json)
- [bolted_rehearsal.py](../../../../../carbon/challenge_pipeline/bolted_rehearsal.py)
- [verification.json](../../../../../docs/development/challenge_pipeline/bolted-rehearsal/verification.json)
- [bolted-joint-wiring.md](../../../../../docs/development/challenge_pipeline/evidence-readiness/bolted-joint-wiring.md)
