# Cooling — an accelerator-module customer's DEVELOPMENT packet

**Role-play:** a hypothetical cooling architect, not a real accelerator
vendor specification. **Authority:**
[OWNER-FIRST-THREE-CUSTOMER-ROUND-01](../../../../.agent/decisions/2026-10-07-OWNER-FIRST-THREE-CUSTOMER-ROUND-01.md).
Ten-section F1 format; numeric companion:
[first-three-requirements.json](first-three-requirements.json). Buyer limits
are prospective and do not replace the present periodic-cell exam.

## 1. Engineering job

“I must choose a copper cold plate **including its inlet/outlet manifolds**
and an operating flow for one accelerator module. Keep the hottest die
location below my thermal allocation while minimizing full-assembly pump
burden. A beautifully cooled periodic channel that starves a real channel
does not solve my problem.” Geometry/flow are actions; inlet temperature and
heat-map/load are conditions. This is foundation-plan Challenge 1's bounded
manifold extension, not f02's transient burst-power task.

| Buyer-owned requirement | Why it matters |
| --- | --- |
| Maximum die temperature ≤85 °C across the declared service scenarios | Keep headroom for my hypothetical module's thermal-management policy; this is not a sourced vendor maximum |
| Full cold-plate/manifold inlet-to-outlet Δp ≤50,000 Pa | Preserve the allocated loop head; include header/entrance/distribution losses |
| Full-assembly hydraulic power ≤2.5 W at ≤3 L/min | Prevent a low-temperature design from consuming excessive pumping allocation |
| Verified performance at 45-°C inlet and 1,500-W load, with the specified hotspots | Normal operation cannot be claimed only at a cool uniform nominal case |

At 3 L/min, Q=0.00005 m³/s, so 50 kPa means 2.5 W hydraulic. A **mock**
50%-efficient pump would allocate 5 W electrical; actual efficiency is a
separate pump/loop measurement. Hydraulic and electrical watts are not
interchangeable. Channel/head allocation for initial design is 30/20 kPa;
this bookkeeping split is not measured manifold pressure loss. Both the
total head and total-power limits apply at every selected flow.

The warm/high-load budget is `(85-45)/1500 = 0.02667 K/W` overall for a
uniform source. The existing 5e-6 m²·K/W TIM over 30×30 mm would contribute
0.00556 K/W, or 8.33 °C at 1,500 W **only for uniform flux**. Evaluate local
TIM temperature increments on a hotspot map; that mean-area calculation is
not a hotspot acceptance test. The old 100 °C / 0.25 W synthetic examples
are neither my requirements nor full-manifold measurements.

**Wrong decision:** a mock replacement plate prototype of $4,000 plus
24 engineering hours at $150/h costs **$7,600/revision**. A two-hour thermal
interruption of eight accelerators at an assumed $3 per accelerator-hour
costs **$48/event** in lost use, excluding contractual knock-on loss. These
are assumptions, not current cloud prices. Saving eight engineering hours
is **$1,200 gross per design revision** before all Carbon/verification costs.
Even a measured 2-W pump-electric saving at $0.15/kWh, 8,760 h/year is only
**$2.63/unit-year**; do not make energy savings the headline without scale.

## 2. Physical system

KEEP the present [domain](../../../../carbon/cold_plate/domain.py): 30×30-mm
heated footprint, C11000 copper, 1-mm base, 0.5-mm lid, PG25 coolant and stated
TIM convention. Existing channel/fin widths 0.2–0.5 mm, depth 1–3 mm; total
flow `flow_lpm_per_kw * heat_load_w/1000`, coefficient 1.25–2.0 L/min/kW;
inlet 30–45 °C; heat 500–1,500 W. Its heat map is a streamwise Gaussian band
on a normalized floor, ratio 1–3, center 3–27 mm, width 1.5–3.5 mm.

New buyer scope: a finite bank of parallel straight channels with two opposed
edge headers and one inlet/outlet port, conjugate single-phase laminar flow.
Before a manifold comparison, the adapter ticket must fix channel count/end
margins, header cross-section and port positions/diameters, wetted topology
and machining rules in the canonical geometry. Those are needed deck pins,
not hidden customer requirements or a permission to run an unspecified CAD.
Do not vary topology silently or replace header loss with a guessed constant.

Today’s reference is the periodic interior: no headers, plate edges or
cross-channel heat variation. Its PG25 fit supports 30–99 °C and its declared
laminar applicability bound is Re≤2,000. Check every local channel/header
regime; low channel Re alone does not certify header applicability. An
unsupported manifold regime is unresolved reference scope, not a candidate
physics failure. Exclude boiling, fouling, turbulent extrapolation, seals,
pressure-vessel safety and rack-level cooling performance.

## 3. Population P, Q and w

Use six customer-recognizable synthetic service strata, pairing each proposed
geometry with **all six**. The table fixes heat-map conditions; it does not
claim their frequencies in a datacenter. The action is one shared flow
coefficient a∈{1.25,1.5,2.0} L/min/kW for the normal envelope; the final
flow-loss probe uses a 0.625 multiplier on the selected a.

| Stratum | Inlet °C / heat W | Hotspot ratio / center mm / width mm | Flow factor |
| --- | --- | --- | --- |
| Cold uniform start | 30 / 500 | 1 / 15 / 2.5 | 1 |
| Typical loaded module | 40 / 1,000 | 1.5 / 15 / 2.5 | 1 |
| Warm uniform full load | 45 / 1,500 | 1 / 15 / 2.5 | 1 |
| Warm central hotspot | 45 / 1,500 | 3 / 15 / 2.5 | 1 |
| Warm outlet-side hotspot | 45 / 1,500 | 3 / 25 / 2.5 | 1 |
| Reduced supply flow at that hotspot | 45 / 1,500 | 3 / 25 / 2.5 | 0.625 |

The reduced-flow case stays in the **current** coefficient range only at
a=2.0 (1.25 after reduction). At lower a it is deliberately outside today's
reference support. Do not clamp it back into support or count it as passed:
the manifold contract must prospectively authorize/verify that extension or
the design has unresolved service coverage. Cross-channel imbalance is an
additional mandatory manifold control, not a case the periodic model resolves.

`P_dev` gives the six named service conditions equal synthetic mass; geometry
and flow proposals remain actions, not draws from P. Pair every action with
the complete condition panel. This equal mass is **not a reliability
claim**. Diagnostic `Q` is the complete panel plus declared boundary/imbalance
controls, not protected sampling. Report results by stratum with `w=1` per
geometry/stratum for descriptive summaries; mandatory limits apply to each
scenario without averaging. Geometry is the independent selection unit;
segments and channels are correlated. Deployment P, reference-missingness
analysis and any official score weighting remain HUMAN_INPUT.

## 4. Case contract

Bind finite geometry, material/PG25/TIM definitions, complete heat-map
normalization, exogenous condition, selected flow action, pressure stations,
mesh and extraction pins. Reject self-intersecting/unmanufacturable geometry,
nonfinite inputs and out-of-contract reference regimes explicitly. Whole-plate
and periodic-cell artifacts have different identities and output semantics;
no cache substitution between them. Public documentation and own-seed
research are separate from protected EVAL/STRESS identities and labels.

## 5. Reference policy

KEEP pinned OpenFOAM conjugate reference/custody patterns. The prospective
full-manifold adapter must demonstrate conservation and distribution, not
just complete a solve. Selected DEVELOPMENT numerical criteria: successive
mesh refinements change peak die temperature by ≤1.0 °C and full-assembly
pressure/power by ≤5%; mass and heat balance close within 1% on retained
controls. Require at least three spatial resolutions on named difficult cases
and tighter solver convergence to separate iteration error from mesh error.

Controls: uniform no-hotspot limit, channel/network relation, zero-load
temperature limit, near-thermal-boundary map, header flow imbalance and low
supply flow. Refine hotspots locally; a good span-mean profile cannot resolve
the hottest local cell. Reference interval overlap with 85 °C or head/power
limits yields UNRESOLVED. Model-form/material adequacy is separate from
these numerical checks and remains NOT_DEMONSTRATED for the new job.
Invalid inputs/reference failures/FAILED_INFRA never become poor candidate
scores. Retain attempts, logs and cost; no dispatch grant is created here.

### Reference credibility target

**Buyer tool:** Ansys Fluent, often through an Icepak electronics-thermal
workflow, is the mock architect's assumed tool, not a market-share finding.
[Icepak's vendor description](https://www.ansys.com/products/electronics/ansys-icepak)
identifies its Fluent basis. **Carbon reference:** current pinned OpenFOAM
periodic-cell conjugate heat transfer, **not the same tool**. Tier 1 would
require the buyer's actual tool and exact settings, which are absent.

**Target tier:** Tier 2 for **cell-level** simulator matching. Under the owner's
latest “ignore the full cold plate” instruction, full-plate packaging, cost
testing and composition witnesses are outside current work. Ongoing hidden
truth stays cell-level; this target does not satisfy the older full-assembly
85-°C/head/power demand. Tier 3 measured thermal/hydraulic cell evidence would
be needed for a physical cell-performance claim. **Credibility evidence:
NOT_DEMONSTRATED** for this buyer decision.

**Benchmark cases:** published COMSOL
[Thermal Modeling of a Microchannel Heat Sink](https://doc.comsol.com/6.3/doc/com.comsol.help.models.heat.microchannel_heat_sink/microchannel_heat_sink.html)
is a candidate conjugate-transfer verification case, not a full-cold-plate
task grant or a published OpenFOAM/Fluent agreement result. Its air/aluminum
setup differs from PG25/copper. Reproduce its exact inputs in both tools only
in a separately authorized benchmark stage, then use matched **periodic-cell**
uniform-load, hotspot, low-flow and warm-inlet cases. Preserve transverse
periodicity versus streamwise inlet/outlet definitions; do not substitute
streamwise fully developed flow for the existing cell physics.

**Acceptance tolerance: HUMAN_INPUT.** Recommend maximum cell die-side TIM
proxy/profile difference ≤1.0 °C and cell pressure-drop/hydraulic-power
differences ≤5% at declared nonzero flow/head. Match local heat flux and TIM
convention, dimensional scaling, pressure stations and all extrema; absolute
near-zero head/power floors remain HUMAN_INPUT. These are cell comparison
bounds, not an allowance for unmeasured manifold error or assembly acceptance.

**Claim boundary:** [common credibility contract](reference-credibility.md).
After accepted evidence, say “matches the reference simulator” **for this
cell scope**. No “matches reality”, plate-level thermal certification,
distribution claim or qualified accelerator follows from cell parity.

## 6. Output and measurement contract

Present outputs: peak/profile/pressure and derived mean/outlet quantities,
with a 30-segment streamwise profile. Pin the prospective thermal observation
as `max[T_heated_face(x,y) + R_TIM*q(x,y)]` over the full heated footprint:
a locally mapped **die-side TIM-interface estimate**, not an explicit die
solid or a mean-flux increment added to the plate maximum. Retain coordinates
of the maximum and the normalized local heat map. This is the declared
synthetic 85-°C measurement; real die geometry/material/contact adequacy is
an additional gap before product reliance. The legacy 30-segment periodic
TIM proxy is not this full-domain observer.

New manifold decision also needs per-channel flow/temperature, total inlet
and outlet flow, and full-assembly Δp. Select flow-weighted total pressure
`integral[(p + rho*|u|²/2)*u_n dA]/Q` at the declared inlet/outlet port planes
with the same datum, inlet flow into the domain and outlet flow out of it
taken positive. Require resolved port planes with no pointwise backflow;
backflow makes this observer UNRESOLVED until a prospective signed-flux
contract is supplied, not a candidate physics failure. Bind station locations,
material density and averaging to the case before a solve; this is not the
old cell's static-pressure observation. Define the hydraulic allocation
`P_hyd=Δp*Q_in` in Pa and m³/s, using **inlet volumetric flow** explicitly.
Record Q_in, Q_out and mass balance separately if temperature-dependent
density changes the two volume flows; this declared allocation metric is
not an assertion that Δp times an unspecified flow is exact viscous dissipation.
Do not multiply an unscaled periodic-cell pressure by an arbitrary total flow.

**Acceptance of a mock shortlist:** independent coupled-reference verification
of all service scenarios and manifold controls, then choose the feasible
geometry/flow with minimum worst-scenario hydraulic power; tie on lower worst
die temperature, then frozen proposal order. If none meets all limits, return
NO_VERIFIED_FEASIBLE_DESIGN. Missing manifold output or unsupported service
coverage is UNRESOLVED, not a promise of cooling success. These are buyer
decision measurements, not adopted score gates or soft-physics residuals.

## 7. Construction contract

KEEP current reconstruction and permitted TRAIN provenance. Reuse the cold
plate representation only where it describes the same physical scope. New
manifold inputs/output dimensions require a prospective contract/adapter,
never silently appended channels to the old public API. Candidate-proposed
designs/flows are committed before independent verification; the construction
model does not certify its own thermal or flow result.

## 8. Research kit

Reuse public cold-plate kit, analytic thermal/hydraulic controls and existing
practice/reference packaging. Publish buyer units and scope differences.
Public research may not receive protected exam scenarios or seeds. A uniform
flow assumption is a baseline to challenge, not ground truth for manifolds.

**Deployment:** an offline accelerator-module design workstation. Target
warm-model p95 ≤0.25 s per full service case on a pinned CPU profile; 200
designs ×6 cases ≤300 s inference and a shortlist within 15 min including
overhead. These are unmeasured speed goals. Replace first-pass coupled CFD
sweeps, not final reference confirmation, pressure/flow/thermal rig testing
or the live datacenter controller. Report training, meshing, verification,
unresolved cases and best cheap-network/cached baseline cost in net value.

## 9. Evidence plan

Use equal search budgets and common resolved-case rules for network/closed-form,
reduced-order and learned models. Test falsely cool hotspots, biased Δp,
missing/starved channels, and an attractive design that fails one service
stratum. Precommit proposals/flow/rules before reference access. Report
false-feasibility, verified hydraulic regret in watts, temperature margins
with reference uncertainty, unresolved coverage and **net time/cost per
verified plate revision**. Better average temperature cannot rescue a breach.

Real instrumented plate data, new reference campaigns, actual rights,
deployment frequencies, training limits and sealed confirmation require
their own evidence/authority. No counted/fresh campaign here; no final
confirmation tuning. Keep family queue and f02's separate budgets unchanged.

## 10. Readiness and claim record

KEEP: periodic cold-plate domain/reference, historical
[Cooling design packet](../../AI_ACCELERATOR_COOLING_DESIGN_PACKET.md),
Graphite public practice/control work and existing Interface-v1 adapter.
NEW: full-manifold buyer limits, named scenarios and value assumptions.
GAPS: pinned finite-manifold geometry/ports, local TIM-interface/total-pressure
observers, actual die representation if needed, multi-channel coupled outputs,
flow-loss support, numerical/model-form adequacy, actual hardware acceptance.
Requirements are SPECIFIED; dimensional checks are not cooling evidence.
No qualified accelerator, datacenter or LIVE claim is made. Next engineering
gate is the bounded manifold case/reference/measurement contract, coordinated
with Test Lead and Carbon Validator on #643; scientific visibility on #42.

Primary context: [OCP cold-plate requirements](https://www.opencompute.org/documents/ocp-acs-liquid-cooling-cold-plate-requirements-pdf)
separate cooling-component thermal and pressure/flow requirements. This
motivates assembly-level observables; it does not supply or certify this
mock buyer's 85-°C, 50-kPa, 2.5-W or monetary allocations.
