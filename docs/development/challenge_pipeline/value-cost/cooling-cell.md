# Cooling cell — case-plane thermal/hydraulic shortlist scorecard

DEVELOPMENT / SPECIFIED. [Current Cooling v3](../round1/cooling-cell-v3.md).
Cell-only; full cold plate/manifold is OUT OF SCOPE. Recommendation: await
running Set A T1/T2, no additional customer reframe. KEEP NOT_DEMONSTRATED.

## Part V — buyer value

Proposed numeric adoption and adequacy acceptance remain HUMAN_INPUT; existing
owner-selected DEVELOPMENT limits are preserved, not reopened by this analysis.

### V1 — real decision

Buyer role: cold-plate OEM thermal engineer screens channel/fin unit geometry
for a specified lid-side interface map and coolant service, before assembly
validation. [Boyd cold plates for AI](https://www.boydcorp.com/thermal/liquid-cooling-systems/liquid-cold-plates/cold-plates-for-ai-server-cooling.html)
and independent [CoolIT design workflow](https://www.coolitsystems.com/coldplate-technology/)
describe thermal/hydraulic co-design and simulation/prototyping. They support
this early component-design decision, not autonomous whole-plate procurement
or the exact periodic-cell's accepted representativeness.

### V2 — low/base/high in buyer units

ASSUMPTION feasible cell-choice thermal headroom improvement **1 / 3 / 5 °C**
or pressure-drop improvement **2.5 / 5 / 10 kPa** at fixed supported flux/flow;
these are alternatives, not simultaneous achieved savings. Avoided screening
rework ASSUMPTION **1 / 3 / 8 h** × **$100 / $150 / $200/h** = gross
**$100 / $450 / $1,600 per revision**. No whole-plate pump electricity, GPU
uptime or full prototype saving claimed from a cell. Verification/integration
cost missing: net benefit NOT_DEMONSTRATED. Reconcile pressure vs hydraulic
power objective with owning contract before using either as the winner.

### V3 — cell-shortlist revisions, not server shipments

Independent [Boyd AI-platform coldplate designs](https://www.boydcorp.com/thermal/liquid-cooling-systems/liquid-cold-plates/cold-plates-for-ai-server-cooling.html)
and [CoolIT processor coldplate applications](https://www.coolitsystems.com/coldplate-technology/)
establish repeated integration work. They do not count cell-only projects,
annual SKU introductions or unique CFD teams. No full-plate/manifold work is
valued here.

All factors **ASSUMPTIONS**: 5/15/40 eligible supplier/OEM teams ×2/6/12
cell geometry/flow revisions/team/year = **10/90/480 decisions/year**;
V2 gives **$1,000/$40,500/$768,000 conditional annual gross**.
Empirical lower bound zero. Count shared supplier/OEM projects once; obtain
new-vs-carried-over SKU, NPI, cell-library and actual CFD logs before V3 PASS.
Units shipped and changing a threshold over the same bank do not create
fresh engineering decisions or reference calls.

### V4 — compare to CFD + response surface, not brute-force fiction

[Mat et al.'s microchannel study](https://www.tj.kyushu-u.ac.jp/evergreen/contents/EG2024-11_2_content/p1426-1434.html)
searches **2,500 response-surface points**, not 2,500 CFD jobs. Its exact
acquisition count is not established by the abstract. **N=30/100/1,000
new cell-condition solves** is a sensitivity assumption; the high case
requires genuinely novel supported geometries/conditions, not repeated lookups.

Owner-reported C1 **0.45 CPU-h/cell case**. At base N=100, acquiring the
legacy 1,000-case bank and fitting over only 10 served revisions costs
more than direct solves: **−1.90 serial wall-h / −$0.19 compute saved**,
end-to-end leverage **0.96×**. Break-even reuse is **over 10.43 revisions**
under these assumptions; reused published training may improve it but is
not automatically free acquisition. A cold-start model is not justified by
an instantaneous inference ratio.

Enabled case: 10,000 cell geometry/flow/tolerance queries in a review window,
with a retained refined shortlist. Compare the cited DOE/response surface,
thermal-resistance library and interpolated lookup at the same case-plane
quantity. No full cold plate saving. V4 PASS NOT_DEMONSTRATED;
[low/base/high, build and reuse](volume-leverage.json).

### V5 — credibility

Assumed buyer tool Ansys Fluent/Icepak; Carbon OpenFOAM cell + specified
vapour-chamber pre-solve is not the buyer's exact tool/assembly. Tier 2 target
ONLY for matched cell/interface shortlisting; earned NOT_DEMONSTRATED.
Use #767 conjugate-flow/pressure/interface-temperature and near-limit witness
verdict/pick/°C or Pa regret. No assembled-plate, die-junction or actual vapour
chamber claim. Tier 3 and separate scope needed for physical procurement.

## Part T — Set A has priority

### T1 — feasibility

85 °C applies at **lid-side TIM2 case plane**, not die temperature. Buyer
vapour-chamber input selected, final warm inlet/lid settings owner-pending.
Earlier uniform cell81.2 °C and raw hotspot≥117 °C do not qualify the new map.
Public [value search at96983b03](https://github.com/carbonphysicsai/Carbon/blob/96983b03b1b7fb06749e7584b16f0bb7be2dcc01/docs/development/evidence/cooling-feasibility-02/value-search.json)
reports candidates, but no final Set A refined receipt at inspected head.
All old53 logical CFD jobs remain held absent the required value/pre-solve
and separate stage/execution authority.

### T2 — contested boundary

The search's 20–80% failure is HISTORICAL, not the new gate's conclusion.
Its 95–100% typical pass fractions cannot alone reject a buyer question.
Need ≥5 feasible AND ≥5 one-band-near infeasible cell actions per condition,
supported margins and equivalence-aware answer changes. Old outlet spread
3.5–4.1 K reflects only 10 resolved designs; unsupported rows are not failures
or passes. Do not synthesize five near-fails via unverified inlet/power scaling,
cut the design menu, move85 °C or declare effective-k a physical lid law.

### T3 — power

NOT_DEMONSTRATED. Optimizer adapter must retain complete heat-condition panel,
case-plane/output identity and reference intervals, then report four controls,
k/windows/E power. A smooth/mean-temperature prediction must not hide a local peak.

### T4 — close calls

NOT_DEMONSTRATED for current questions. Refine map/cell coupling and field
peaks; propagate spreading/TIM uncertainty to case-plane verdict/pick. PG25
out-of-support rows stay UNRESOLVED. 25–<30 °C remains unsupported by the
present profile absent prospective property/package validation.

### T5 — reference

Pre-solve conduction/spreading conservation and verified cell map applicability
required; vapour-chamber effective conductivity is not a measured material law.
No full cold plate witness requested here. Retain existing adequacy and cell
hydraulic limits (≤50 kPa, ≤2.5 W, ≤3 L/min as applicable buyer envelope),
temperature plane and accepted dimension/flow scaling conventions.

## Part C — cell costs only

### C1 — per-case cost

UNMEASURED at the new map/settings; need pinned cell+pre-solve p50/p95/RSS
and failures. Historical simple periodic-cell timing cannot certify this route.

### C2 — startup

NOT_DEMONSTRATED. Legacy 1,000-cell proposal leaves3.50 serial wall-min/case
under the shared illustrative overhead reserve; include map generation,
refinement, controls and property-support work. Actual billable node ledger
decides €100 fit, not the absence of full-plate jobs.

### C3 — ongoing

NOT_DEMONSTRATED: measured complete bank refresh under registered E/windows
and ≤15% AX42-equivalent. Cell-only scope removes full-plate ongoing truth
from this analysis; it does not authorize a larger bank or new spend.

### C4 — validator

NOT_DEMONSTRATED current buyer task vs #727. Existing Cooling ChallengeAdapter
is engineering reuse, not current-task cost or qualification. Reference and
lid solvers stay outside validator rebuild/inference.

## Reframe hold

Original/current V2 vs this analysis is unchanged; no benefit is earned by
changing a ruler. Wait for Set A contested-boundary results. If refined T1/T2
fails, propose one sourced buyer-level choice and explicit sacrifice; final
inlet/lid settings remain owner-owned. No full-plate return or safety relaxation.
