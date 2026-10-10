# Battery v3: middle-band boundary-action panel

**BATTERY-V3-MIDDLE-BANDS-PANEL-01 / DEVELOPMENT / SPECIFIED.** Proposed
registration for Data Collection, not an approved run, hidden bank, new law or
T2 pass. No solves/spend/hidden/AX42 access. The [planning sheet](battery-v3-middle-bands-panel.json)
enumerates deterministic action groups; accepted manifest and dispatch grant
are null. Keep the [round-two law](battery-v3-round2.md),
[buyer map](../round1/battery-ambient-map-v3.md) and optimizer ownership.

## 1. Buyer question and the gap

The fleet engineer chooses one safe protocol/cooling action for each of five
ambient bands, minimizing buyer-mix-weighted charging minutes. A fast model
must distinguish fast-but-unsafe actions from safe actions near each safety
frontier, not merely copy the one known feasible map. This panel resolves the
missing **15/25/35 C** frontier evidence; it does not establish the best map or
cover the expanded SOC20/30 and initial-ageing law.

Test Lead working value, 2026-10-08: T2(a) needs **at least five resolved
feasible and five resolved infeasible distinct actions within TWO refinement
bands**, on both sides of the relevant limit, per question family/condition.
The overall feasible fraction remains a report, not a gate. Fix insufficient
counts with frontier resolution, never a wider band or softer safety limit.
This prospectively records the two-band working definition; prior one-band
wording and historical acquisition counts are not silently reinterpreted.
Accepted widths/criteria remain HUMAN_INPUT. Recommend the development
registry's temperature band0.5 K and plating band0.002 V; consequently the
working near distances are1 K and4 mV. They are **not safety slack**.

At nominal requirements, retain charging T<=45 C, every-charge plating>=0 V,
programme V<=4.2 V and Q30/Q1>=0.99. Time is an objective, never a hard30-min
cap; test-discharge temperature stays diagnostic. All five bands remain
mandatory even at zero fleet weight. No change to motor or other family laws.

## 2. Evidence custody and exact reuse

Read-only source: acquisition head
[`66ea509888e4ef0f5ac08750554db744b56b92bf`](https://github.com/carbonphysicsai/Carbon/tree/66ea509888e4ef0f5ac08750554db744b56b92bf/docs/development/evidence/battery-feasibility-02).
`registry.json`, `summary.json`, `tier3-summary.json`, `v2-rescore.json`,
`tier4-boundary-registry.json`, `tier4-boundary.json` and `v3-panel-export.json`
are development records, not hidden data or a new qualification receipt.
No operator-host export was opened for this ticket.

The v3 provenance note registers **115 refined programmes**, including
**8 at15 C,40 at25 C and45 at35 C**. That is93 middle-band refinements already
on DC's plan, not93 new jobs here. The note does not prove their completion.
Its file SHA256 is
`5ea5df8f83880e75d35df8b1361e948b6e09ea66bdbc538dc29f9b82e5098f48`,
logical digest `sha256:4594c73236f609556ec59f1dc68c4af9dd422f243a6f07b4c96a133165f3d7e5`.
The different inventory measured in the round-two law remains versioned
history; do not replace one export's counts/digest with another's.

Before any later authorized start, DC joins the proposed tuples against
completed **and scheduled** standard/refined/third-rung records by the complete
physical identity: model/parameter/dependency/image, initial state/SOC,
ambient, c1/c2/switch/CV/cutoff, cooling h/area, programme/rest/discharge,
observer and numerical rung. Identical coordinates alone are insufficient.
Reuse verified matching artifacts, retain their original identity, and return
the intersection and missing/failed/in-flight rows. A new label is not a new
solve. Never subtract all93 from this panel without that intersection.

Keep off-lattice and x3/x6 historical rows visible as excluded history; no
rounding or interpolation manufactures truth for an approved-menu tuple.
Public development rows never become hidden rows. Neither this panel nor a
new requirement resets exposure E. No protected material is requested.

## 3. Fixed diagnostic slice and required pins

Recommend the already observed slice: initial SOC0.10, identified fresh state,
30 cycles, switch4.00 V, CV4.2 V to C/20, same registered rest/discharge
programme and session-start-SOC integral observer (nominal5 Ah). Cooling is
x1/x2/x4 multiplying the registered **h0=10 W/m2K**, area0.00531 m2, unchanged
through charge/CV/rest/discharge. This repeats source definitions, not a claim
about a real fleet cell or a production cooling system.

Freeze the complete programme/deck and charge-phase masks before execution;
report cycle/phase/time of every extremum and first session reach of80% SOC,
including the120-s session rest. The early voltage-probe time estimate is not
reused. The source says PyBaMM26.8.0.0 overlay but truncates its lock hash
(`6267e033...`); a prefix is **not an execution pin**. DC must supply full
source/dependency/image/parameter/observer/deck digests and exact standard-rung
settings. Keep the recorded refined mesh40/rtol1e-6/atol1e-8 and conditional
third rung mesh80/rtol1e-7/atol1e-9 only after package-owner verification.

The producer's numerical4.200001-V convention is not adopted here. The buyer
cap stays4.2 V. Reference-owner settlement/roundoff treatment, voltage and
retention bands, numerical support and legal physical action bounds remain
HUMAN_INPUT. Missing accepted values HOLD affected verdicts/dispatch, not
turn them into favorable defaults. This diagnostic menu does not freeze the
whole action space, switch menu, P, Q, w, E or k.

## 4. Anchors: choose the frontier, not the desired outcome

These are **source point estimates**, not accepted interval counts. v2 rows
use IDs `c1=...,c2=...,sv=4:h...@T...`; refined rows retain their source ID.
Small differences between coarse and refined records are a reason to refine,
not evidence of interchangeable truth.

| Band / source action | Charging T, C | Plating minimum, mV | Why it informs the panel |
| --- | ---: | ---: | --- |
| 15 /1.25,0.70,x1 (v2) |33.264|+2.122|Plating-safe side, already near the proposed4-mV distance |
| 15 /1.25,1.00,x1 (v2) |33.263|-2.995|Opposite plating side; no thermal relaxation needed |
| 15 /1.25,0.40,x2 (v2) |26.140|+5.450|Brackets x2 plating with c2=0.70 (-4.240 mV) |
| 15 /1.25,0.40,x4 (v2) |21.420|-4.410|x4 lower-c1 probes needed; no proved safe bracket yet |
| 25 /1.50,1.25,x1 (refined summary) |44.720|+4.295|Known near-thermal feasible-side lead; not settled optimum |
| 25 /1.50,1.50,x1 (v2) |45.908|+2.014|Nearby thermal fail, motivates c1/c2 frontier resolution |
| 25 /2.00,1.00,x2 (refined summary) |42.975|-0.484|Refined plating boundary remains a close call |
| 25 /1.75,0.70,x4 (v2) |34.098|+0.419|c1-driven plating frontier, with thermal headroom |
| 35 /1.25,0.70,x2 (v2) |42.969|+22.307|Below thermal frontier |
| 35 /1.50,0.70,x2 (v2) |45.523|+22.170|Just above thermal frontier |
| 35 /2.00,1.25,x4 (v2) |44.533|+1.859|Near plating-safe lead with thermal headroom |
| 35 /2.00,1.50,x4 (v2) |44.533|-5.679|Brackets x4 plating, but this endpoint is outside4 mV |

T15's practical first frontier is plating. At c1=2/x1, thermal is near45 C
but plating is about-9.67 mV, so it is **not a near-feasible thermal witness**.
Report that missing per-limit coverage; do not count it as thermal success.
The low-current x4/T15 and x1/T35 probes below are deliberately uncertain
bracket-finding probes, not asserted feasible actions. None of the anchors
guarantees the proposed lattice provides five distinct points on each side.

## 5. Proposed registration A: exact finite action groups

Inclusive endpoints; every range has **0.01-C** step. Fixed lists are exactly
those shown. Cartesian products are within a row only; never cross rows or
ambient bands. c2<=c1 for every tuple. Identity template:
`bmid1:T{ambient}:h{multiplier}:c1={two decimals}:c2={two decimals}:sv=4.00:SOC=.10`
plus the immutable physical/rung manifest. This is a proposed diagnostic ID,
not a runtime case/Challenge registration. The sheet is the machine-readable
group specification; DC expands, sorts and hashes the final accepted manifest.

| Group | Ambient | Cooling | c1, C | c2, C | Rows | Frontier / role |
| --- | ---: | ---: | --- | --- | ---: | --- |
|15-p1|15|x1|1.00,1.25,1.50,1.75|0.75--0.95|84|Plating crossing across four c1 slices |
|15-p2a|15|x2|1.25|0.50--0.60|11|Plating crossing in c2 |
|15-p2b|15|x2|1.40--1.50|0.40|11|Plating crossing in c1 |
|15-p4-probe|15|x4|0.75,1.00,1.10,1.20,1.25|0.40|5|Find a bracket; do not assume monotonicity |
|25-t1|25|x1|1.48--1.55|0.70,1.00,1.25|24|Thermal frontier with plating audit |
|25-p2|25|x2|1.25,1.50,1.75,2.00|0.90--1.05|64|Plating crossing across c1 |
|25-p4|25|x4|1.70--1.85|0.70|16|c1-driven plating boundary |
|35-t1-probe|35|x1|0.95--1.10|0.40|16|Find thermal bracket; no proved endpoints |
|35-t2|35|x2|1.42--1.51|0.70,1.00,1.25|30|Thermal frontier, plating/retention check |
|35-p4|35|x4|1.50,1.75,2.00|1.24--1.36|39|Plating boundary with thermal audit |

Total **300 proposed tuples:111/104/85** in T15/T25/T35. This counts physical
action/context rows, not questions, accepted designs, solver starts or newly
earned near witnesses. DC must validate all newly proposed tuples against
the pinned model/action support. Bounds/order are panel recommendations, not
global grammar adoption. All solved results, including failed probes, stay
in the return; no selection on success or omission of inconvenient rows.

Do A only after the accepted reuse/in-flight inventory; prioritize the
already-authorized93 refinement plan where it intersects. In this ticket
all run permissions are false. No new script/deck or acquisition lane is built.

## 6. Proposed registration B: bounded frontier fill

If A lacks5+5, a later accepted plan may add **at most20 tuples per band (60
total)**, without widening any near band or safety requirement. This is a
predeclared adaptive Q diagnostic, not P or an iid population estimate.

1. Sort by band, group ID, fixed-coordinate values and varied C rate. Form
   adjacent solved-point pairs along one axis, with all other inputs identical.
   Use actual returned values/intervals, not a surrogate's predicted truth.
2. Seek brackets of plating targets-3/+3 mV or temperature44.25/45.75 C
   (1.5 working bands either side). Linear interpolation proposes a location
   only; it is not a reference result or a monotonicity assumption. Quantize
   to0.01 C (nearest, exact half ties downward); consider adjacent lattice
   neighbors only to avoid a duplicate. Verify c2<=c1.
3. Keep within that group's existing varying-axis min/max and all its fixed
   coordinates. For probe groups, refine only **observed** brackets; if none
   exists, report no bracket rather than extrapolate. The x4/T15 probe c1
   envelope is0.75--1.25; x1/T35 is0.95--1.10. No new cooling/switch/SOC is added.
4. Freeze the ranked tuples and hashes before each later permitted stage;
   exact reuse/in-flight check again. Keep all outcomes. Stop at the cap or
   enough accepted distinct witnesses, reporting incomplete coverage honestly.

If the existing0.01-C lattice cannot supply5+5 at a frontier, or the bracket
is absent, return **NOT_DEMONSTRATED** and the smallest model/action-support
or law decision to Test Lead. Do not change lattice, E, safety, population or
near distance to manufacture a pass. This panel does not grant a retry loop.

## 7. Refinement, count definition and required return

Refine every used row whose accepted uncertainty or coarse/refined difference
can change verdict, near membership or potentially winning pick. Also target
both sides within two working bands, not only violations or the fastest five.
First reuse matching refinement. Proposed rung2 is the registered mesh40
recipe; a third rung is only for straddles or differences>=the relevant band,
under DC/reference-owner acceptance. At most one new standard and one rung2
per tuple; proposed third-rung ceilings **60 for A,12 for B**. Unsettled rows
at a cap remain UNRESOLVED. No automatic retries; infrastructure/reference
failure is distinct from physical infeasibility. A repeat needs its own cap.

Count per **drawn requirement**, not only nominal45 C/0 V. Publish nominal and
the four-combination audit baseline separately; the continuous law needs
coverage/diversity across its registered draws, not a nominal-only T2 claim.
At every limit l define the safe-signed margin (cap minus value, or value minus
floor). Recommend counting near-feasible for l only when all hard limits are
settled feasible and the **accepted reference interval** for its margin lies
entirely in[0,2b_l]. Count near-infeasible for l only when that limit is a
settled violation with its margin interval entirely in[-2b_l,0); other
violations are reported separately. Crossing an edge of these intervals makes
membership unresolved, not eligible. Accepted uncertainty/settlement, not an
invented interval from two point estimates, must support this classification.
Equality follows the accepted reference contract; without it, report unresolved.

For each question family/band return union-distinct near-feasible and
near-infeasible counts, plus **separate per-limit** counts and overlap IDs.
Never add one action several times because multiple limits are near. Five
different C-rate tuples can be near correlated versions of one protocol:
report effective frontier slices and clustering, not independent power.
T15 plating-only coverage cannot stand in for demonstrated thermal-family
coverage. Test Lead decides applicable families and thresholds.

Required DC return, on development/public or retired published data only:

- Accepted proposed/expanded manifests, provenance/rights, artifact/rung hashes,
  reuse/scheduled/excluded/new counts; source export identity and coverage.
- Raw cycle/phase/time extrema, charge integrals/session minutes, charging and
  discharge temperatures, every-charge plating, V, Q30/Q1, cooling heat/energy.
- Standard/refined/third values, accepted intervals/settlement, statuses and
  per-limit reasons; refinement/unresolved rates with all-row denominators.
- Nominal and supported requirement-draw T2 counts, pass fraction, meaningful
  minutes/margin spread, complete-five-band feasibility and per-band winner/
  value-equivalent-set diversity. Do not declare T1/T2/best picks from anchors.
- Summed process-tree CPU seconds, full wall time, process/cgroup peak memory,
  helper/setup/failure/retry costs, resource shape, in-flight artifacts and
  actual stop reason. Preserve all attempts in the ledger.

Optimizer Codex owns score-value/power/cluster accumulation and readiness.
This ticket neither measures them nor expands their authority.

## 8. CPU budget: an estimate, not a rental or execution grant

Supplied working C1: **91 CPU-s per standard programme**; its transfer to
new boundary actions is an assumption. The export note's refined p50 is
**378 wall-s**, not measured summed CPU-s. Use378 CPU-s only as a labelled
single-thread planning proxy; it is not a p95 or universal C1. Third-rung
CPU/memory is **NOT_MEASURED**. Recommend900 CPU-s per third rung as a planning
allowance/stop trigger, not a claim that it finishes. Per-case resource/stop
rules require DC/owner acceptance; total cap never permits an overlong case.

| Scenario (ASSUMPTION, before setup/helpers) | New standard / rung2 / rung3 | Planning CPU-h |
| --- | --- | ---: |
| Low, heavy exact reuse |60 /30 /0|4.6667|
| Base, A with40% new rung2 and12 third rungs |300 /120 /12|23.1833|
| A maximum, all new/rung2 plus60 third rungs |300 /300 /60|54.0833|
| A+B maximum, all new/rung2 plus72 third rungs |360 /360 /72|64.9000|

The low reuse and base refinement shares are not measured or guaranteed.
Costs add completed **failed attempts**, meshing/observer/helpers and setup;
stop at the accepted all-in cap even if coverage remains missing. In-flight
prior grants have separate ledgers; intersection avoids duplicate new starts,
but does not erase the total resource those other jobs consumed.

At the user-supplied CCX63 rate **EUR1.37 per billed node-hour**, define measured
effective throughput S=aggregate process CPU-h/billed node-h. Rental arithmetic
is `1.37 * CPU_h / S` plus fixed charges; **48 vCPUs is not S=48**. At S=1,
the A+B proxy isEUR88.913 before overhead; at a hypothetical S=8 it is
EUR11.114125. Neither demonstrates<=EUR100 all-in or authorizes rental. Free
CPU consumes the same resources even with zero incremental invoice. Capacity,
memory, exact pins and an accepted ledger/stop plan precede any later run.

## 9. Handoff ceiling

**SPECIFIED** with tested static arithmetic/guardrails, not IMPLEMENTED
acquisition, measured middle-band coverage, qualified reference, settled
optimum or hidden-bank readiness. Only the inherited safety/action menu is
owner-selected. Panel tuples, applicable families, bands/settlement, full
package/support pins and any execution/cap are HUMAN_INPUT/DC acceptance.
DC can prepare the exact reuse/manifest return independently; no paid dispatch
or new solve is authorized here. Battery EV5, journal14 and live contract stay
untouched. Codex is done; PR Lead may take over.
