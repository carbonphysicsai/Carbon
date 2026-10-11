# Bolted joint: representative brief-to-product rehearsal

Status: DEVELOPMENT engineering preparation, **REPRESENTATIVE**, never a
customer result. No solver executed, no spend, no accepted reference, no adopted
Challenge. Keep #1020's full **3D eccentric load / assembly-preload / frictional
contact / retained lock / service history** job. A tied-contact model, beam-only
joint or force-maintained service bolt would be a different question.

## Customer inputs and replacements

[inputs.json](inputs.json) maps B01–B06 to the activation kit's I01–I17 fields,
with sources, applicability tests and exactly what the customer replaces.
Geometry and load magnitudes are ASSUMPTION sensitivity exercises; P and w are
unset. Q is an endpoint sensitivity proposal, not a registered population.
Bossard's January 2025 VDI-derived guide distinguishes tightening scatter
`alpha_A = F_Mmax/F_Mmin` from static dry steel–steel faying friction. Its ranges
are representative only, not a measured customer's distribution. NIST's generic
elastic steel is not a bolt grade, yield curve or safety allowable. Limits and
objective remain HUMAN_INPUT. Rights, actual cadence, customer hardware and
commercial acceptance remain unsupplied.

## Preparation command and exact identities

`python -m carbon.challenge_pipeline.bolted_rehearsal actions` (or `conditions`)
prints the deterministic 81-action / four-condition proposal. The other commands
`panel`, `train`, `deck`, `observe`, `compare` take `--input <representative.json>`
and emit JSON to stdout only. They cannot dispatch or write a solver deck to an
operator store. Inputs are explicitly REPRESENTATIVE and bounded to 4 MiB.

`panel(designs, rungs=[1,2], completed=[], scheduled=[])` makes exact
action × condition × mesh-rung × pin tuples, reuses completed/scheduled **exact**
identities, deduplicates repeated tuples and rejects conflicting inventories.
It is `PROPOSED_NOT_REGISTERED`; actual retained/scheduled inventories and mesh
hashes must be supplied before registration. TRAIN holds out **whole physical
actions**, across all service siblings, rungs and solver pins. `kit_domain`
checks actions, conditions, observer, all quantities and assembly/lock/service
coverage; it does not invent a trained kit or TRAIN registration.

## Draft deck and observer contract

Reuse the f08 CalculiX 2.23 source/image lock, serial OMP/OpenBLAS execution,
not f08's modal adequacy. `deck` emits model and assembly fragments, plus a
deliberately **non-runnable service template**. Data Collection supplies and
pins original 3D solid mesh, faying/bearing contacts, preload section cuts,
distributed load pads and probes. Normal penalty and elastic stick slope are
explicit caller values, not hidden solver defaults or accepted material laws.

Assembly loads each solid bolt's pretension control node. The service bridge
must remove those force commands, hold each **solved section extension** and
retain assembly state through lock. It is HUMAN_INPUT until verified by the
two-spring and same-history/restart checks. Never independently start service
from a stress-free model. Mesh, contact and retained-state gaps prevent a
working-container claim.

`observe` requires ordered assembly/lock/service sections, each raw-source hash
and **every declared nonlinear increment**, not just three endpoints. It
reduces aligned signed normal gaps, tangential relative slip, compressive
contact resultants, two bolt loads, volume-weighted integration-point stress,
and probe displacement. All increments remain in the report. It also reports
signed global force/moment residual norms about one common origin. Normal
contact sign must be compressive-positive; negative contact or nonconvergence
is `REFERENCE_FINDING`, never a candidate failure. The extraction/mapping is
still unverified; hashes and increment counts alone do not prove adequacy.
Stress averaging, singularity exclusion, thermal/plastic applicability, global
balance floors and decision tolerances require Test Lead acceptance. In CCX,
RF includes applied nodal forces: the producer must map true support reactions
without double-counting. Buyer verdict always remains UNRESOLVED here.

[verification.json](verification.json) specifies 3D affine/smooth elasticity,
pretension/lock and Coulomb analytic controls, independent mesh/penalty/time-step
ladders, full-history conservation and matched public buyer-tool witnesses.
MMS order/pass bands are recommendations, not accepted results. Image presence,
code verification, reference convergence and contact/history adequacy are
different receipts. No native fixture earns Tier 2.

## Strong cheap baseline, without invented safety

`hand_calculation` uses **independently calibrated** bolt/member stiffness,
`phi=kb/(kb+km)`, eccentric two-bolt load sharing, residual clamp and friction
reserve. It is a VDI-style calculation, not complete licensed VDI compliance.
It refuses its closed-contact domain after separation. It cannot manufacture
opening, slip, stress or displacement by returning zeros.

`compare` accepts a digest-bound REPRESENTATIVE panel, matched runnable neutral
tasks/actions/observer, independent stiffness rows and the five-field retained
cost inventory. It reports supported pointwise errors, canonical decision
agreement/regret/abstention, timing and candidate ranking for equal-budget replay.
Decisions requiring an unsupported quantity **abstain**. Query cost is measured
for this calculation; there is no fit, so formula fit cost is zero. Unmeasured
acquisition/refinement/retained verification/memory/money are null, not zero.
This is an independent analytic comparator, not a fitted held-out response
surface; every witness design is excluded from calibration. Matched customer
stiffness and calibration evidence are not yet available. The strongest
contact-aware cached FE/response surface remains `HOLD_NOT_SUPPLIED`; beating
the hand arm alone cannot pass V4.

`bolted_budget.proposal()` is an isolated digest-bound #1047-form
`BOLTED-JOINT-REPRESENTATIVE-PROPOSED-V1` ladder: half/base/double 4/8/16 complete
joint decisions, 1/2/4 host-hours and 2/4/8 core-hours, all ASSUMPTION. One
evaluation completes every assembly/lock/service condition, not one cheap
increment. Shared replay charges fit/screening/failures and verification equally
and reports REPRESENTATIVE scope. Historical four-family EQUAL-BUDGET-V1 is
unchanged and still rejects this family. No run or spend grant is created.

## Question/value/pilot/readiness handoff

A question is a full joint design under buyer-supplied opening/slip/stress and
displacement limits and objective, not one torque/preload row. Provisional
k=4/8/12 are ASSUMPTION sensitivity options; P/Q/w, E, B, thresholds and power
must be frozen before any scored bank. Retain NONE_FEASIBLE without redraw.
Use the current **two** refinement-band rule: each condition needs at least
five feasible and five infeasible near its limits, meaningful buyer-unit margin
spread, one complete feasible design and changing best answers. This prospectively
aligns the rehearsal with the current Test Lead rule; the discovery dossier's
historical one-band text is not authority for this new panel. A four-job pilot
cannot demonstrate those checks or a p95 solve cost.

[measurement-pilot.json](measurement-pilot.json): four proposed analytic/joint
jobs, including rung 2, low/base/high elapsed compute 0.65/1.4/3.2 hours and
EUR0.89/1.92/4.38 at the owner's EUR1.37/h basis, **hypotheses**, not measured or
all-in quotes. Free CPU first; if paid later, an exact all-in quote within EUR10,
pins, resource enforcement, ledger and owner execution authority are required.
No retry/spend permission is implied. [delivery-measurement.json](delivery-measurement.json)
retains actual timestamps, human effort, failed attempts, compute and dossier
D1–D11 receipts, all null until measured: no invented SLA or delivery time saved.

[readiness-binding.json](readiness-binding.json) gives seven explicit owners and
real pointers. All remain PLANNED pending registration/store/verification/kit/
TRAIN/matched comparison/complete decision receipts. Central integration waits
for #1039 on main; preparation is not 7/7 readiness. Data Collection's next
bounded action: build the original 3D contact mesh and independently verify the
pretension lock transition on free CPU, then return exact pins, all increments,
raw observer maps, errors and full costs. Customer/Test Lead supply limits and
acceptance; owner supplies grants and commercial decisions.
