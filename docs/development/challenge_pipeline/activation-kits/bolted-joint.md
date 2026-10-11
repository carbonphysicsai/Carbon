# Bolted joint activation kit — assembly then nonlinear service loading

**DRAFT / DEVELOPMENT / SPECIFIED / HOLD_CUSTOMER_INPUT.** Read the
[shared I01–I17 checklist, Carbon supply, timeline, cost and dossier](README.md).
Buyer: joint-design engineer choosing bolt pattern/size, preload and local
support geometry for the actual eccentric load envelope. Preserve separation,
slip and applicable bolt/member loading; a linear modal or unrelated vibration
benchmark is not this decision.

Basis: [full packet](../discovery/dossiers/bolted-joint.md),
[#1001 input audit](../../../../Business/research/open-data-check/ASSESSMENT.md).

## Exact customer files and readiness tests

| Required extension / common IDs | Customer role and supply | Recommended readiness test / missing-data hold | Dossier |
| --- | --- | --- | --- |
| B01, I02/I05 | Joint designer: bracket/bolt/member CAD, thread-model convention, interfaces, load frames and tolerance/action catalog | Units/connectivity and compatible assembly; no overlap/invalid bolt pattern; preserve eccentric lever/load path and permitted actions | D01/D03/D04 |
| B02, I06 | Materials engineer: same-grade/process bolt/member elastic/plastic curves, strength/strain allowables and temperature domains | Supported constitutive/load domain and limit authority; grade names alone do not define yielding/strength | D02/D04/D06 |
| B03, I06/I07 | Assembly engineer: force preload/distribution, tightening/locking/assembly order and scatter; torque conversion if used | Measured or approved preload bridge; distinguish thread/under-head tightening friction from service faying friction | D03/D04 |
| B04, I06/I04 | Contact owner: faying friction vs pressure/surface/finish/lubricant/temperature, uncertainty and tolerance correlations | Same interface/condition law, not generic steel-on-steel default or another rig's tightening data; missing law holds slip judgment | D04/D06 |
| B05, I03/I07/I10 | Systems lead: full assembly/service loads and opening/slip/stress/displacement acceptances, objective | All load steps and material limits sourced; regularized stress/resultant definition prevents singular-node criteria; missing sequence holds complete decision | D02/D05 |
| B06, I08/I09/I11 | Simulation/workflow owner: contact/pretension decks, force-balance/convergence witnesses, VDI/compliance worksheet and strongest contact-aware FE surface | Full-history state transfer, clamp/load balances and mesh/contact/load-step sensitivity; matched whole-design choices/costs | D04/D05/D11 |

#1001's TRC CAD is a licensed ingredient for a different assembly, not a
source-confirmed eccentric bracket/faying/friction family. Do not infer
licenses for contributed decks from the CalculiX solver license. No missing
friction scatter or safety requirement is narrowed to make the task pass.

## Carbon work, next gate and output

Carbon freezes the joint/output contract and strongest-baseline comparison;
Data Collection packages nonlinear contact/pretension with assembly followed
by service history. f08 linear modal plumbing does not supply these missing
capabilities. First next action: buyer joint/assembly/contact owners provide
B01–B05 coherent files. Science/reference acceptance precedes any panel.
Shared S0–S4 preparation scenarios apply only after those receipts; full
completion time is UNKNOWN while missing data/verification remain.

Deliver D01–D11 with stepwise opening/slip/clamp/stress/displacement and
per-stratum constraints, force/contact diagnostics, unresolved/failed
reference handling, matched-baseline decisions and exact state lineage.
Target Tier 2, earned NOT_DEMONSTRATED. No fatigue/fracture/flight or physical
joint reliability certification is inferred from this bounded model.

## Conditional cost

[#1001's inherited bank component](../../../../Business/research/open-data-check/ASSESSMENT.md):
**ASSUMPTION EUR low/base/high 26.11 / 42.08 / 93.21**. Matched contact-case
cost, material integration, buyer licenses and independent confirmation are
UNMEASURED. Full consumed cost/price low/base/high
**null/null/null / NOT_QUOTABLE**. Owner prices full #984 scope, not only the
cheap bank hypothesis; no grant or automatic affordability decision follows.
