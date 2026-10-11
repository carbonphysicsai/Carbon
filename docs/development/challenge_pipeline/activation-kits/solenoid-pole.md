# Solenoid pole activation kit — complete supported force/loss envelope

**DRAFT / DEVELOPMENT / SPECIFIED / HOLD_CUSTOMER_INPUT.** Read the
[shared I01–I17 checklist, Carbon supply, timeline, cost and dossier](README.md).
Buyer: actuator magnetics engineer choosing pole/air-gap profile of a **non-PM**
axisymmetric pot-yoke/armature with the actual winding, full force-stroke/current
envelope and stated-temperature resistive loss. Not a planar electromagnet
tutorial or an unpriced transient/duty-cycle guarantee.

Basis: [full packet](../discovery/dossiers/solenoid-pole.md),
[first-panel contract](../magnetics-first-panels/solenoid-pole.md),
[#1001 input audit](../../../../Business/research/open-data-check/ASSESSMENT.md).

## Exact customer files and readiness tests

| Required extension / common IDs | Customer role and supply | Recommended readiness test / missing-data hold | Dossier |
| --- | --- | --- | --- |
| S01, I02/I05 | Actuator designer: dimensioned pole/yoke/armature/winding drawing, gaps/fillets, tolerance dependencies and permitted profile actions | Axisymmetry/connectivity/units and valid moving gaps; same full supported package for all actions. Different TEAM geometry is not a substitute | D01/D03/D04 |
| S02, I06/I04 | Magnetic materials owner: steel grade/process and monotone B–H(T) curves through nominal/hot/gap strata, domain and uncertainty | Matched grade/state over every approved temperature; interpolation/saturation and no unsupported extrapolation. Generic tutorial B–H alone fails full job | D04/D06 |
| S03, I06/I07 | Winding engineer: turns, conductor area/fill, mean turn length/leads, resistance vs temperature and current/stroke schedules | Ampere-turns, resistance and I²R internally consistent at stated conditions; ampere-turns alone cannot imply unique copper loss | D03/D04/D05 |
| S04, I03/I10 | Systems owner: complete force lower/upper envelope, current/power and packaging limits, objective among compliant profiles | Every stroke/current/condition measured with signed force/units and authority; unmet duty-cycle/thermal requirement requires adequate coupling or scope rejection | D02/D05 |
| S05, I08/I09 | Simulation/V&V owner: buyer FE decks, matched witnesses and force/flux/coenergy observers | Mesh ladder plus virtual-work/Maxwell-stress consistency; matched tool force envelope and feasibility/pick agreement, tolerance HUMAN_INPUT | D04/D05/D11 |
| S06, I11/I15 | Workflow owner: nonlinear circuit/fringing fit, manufacturer force-map cache, FE-calibrated RBF/Kriging and direct optimization costs | Whole supported-profile holdouts and same winding/constraints; lookup wins if all complete permitted outputs are already cached | D01/D05/D10 |

Permanent-magnet recoil/demagnetization data are not applicable to the non-PM
job. A PM or dynamic/eddy-current/overheating claim needs a new supported scope,
not a silent omission or added capability. #1001 found no complete matched
open nominal/hot/winding family; customer inputs can close that hold, subject
to rights/science review.

## Carbon work, next gate and output

Reuse motor GetDP build infrastructure where applicable; implement and verify
axisymmetric moving-gap force/flux/coenergy and winding-loss observers rather
than pretending motor torque extraction transfers. Data Collection owns the
package/panel; science accepts reference; buyer approves unchanged envelope.
First next action: S01–S04 matched geometry/material/winding/limit receipt from
the actuator team. Shared S0–S4 timeline is conditional; missing B–H(T) or
loss data leaves the full completion time UNKNOWN.

Deliver D01–D11 with full force-stroke/current curves and I²R at each condition,
admissibility-before-choice, uncertainty/refinement, exact reference/model
identities, strongest-baseline regret and fallback. Target Tier 2, earned
NOT_DEMONSTRATED; no real overheating, actuator reliability or supplier-product
qualification claim from magnetostatics.

## Conditional cost

[#1001's inherited bank component](../../../../Business/research/open-data-check/ASSESSMENT.md):
**ASSUMPTION EUR low/base/high 18.98 / 26.37 / 46.06**. Complete-case CPU,
packaging/force verification and customer license costs are not measured for
this matched job. These are not customer quotes or grants. Full consumed
cost/price low/base/high **null/null/null / NOT_QUOTABLE**; use #984's full
decomposition after the input and scope receipts.
