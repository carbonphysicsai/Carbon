# Battery mock customer v3 ambient indexed charge map

**Role-play / DEVELOPMENT / SPECIFIED.** Ryan's 2026-10-08
[ambient-map decision](../../../../.agent/decisions/2026-10-08-OWNER-BATTERY-AMBIENT-MAP-03.md)
supersedes the one-protocol decision in [v2](battery-ev-fast-charge-v2.md).
Historical evidence and frozen scoring contracts keep their own identities.
The [law](../question-laws/battery-ambient-indexed-v3.md) and
[optimizer](../optimizers/battery-ambient-map-v3.md) are prospective specs,
not installed samplers, controllers, score rules or reference packages.

## 1. Engineering job

I calibrate an EV fleet's charging map. I choose one protocol and cooling
setting for each covered ambient band, instead of making every session use
the same warm-safe recipe. My buyer value is expected charging minutes across
the fleet's stated ambient mix. A fast cold-band recipe cannot compensate for
an unsafe warm-band recipe. A wrong feasible verdict can damage cells or
force a charger calibration recall; the v1 hypothetical costs remain context,
not measured savings or commercial traction.

For band b the action is `(c1, c2, switch_voltage, cooling_level)`. Hard
charging T<=45 C, every-charge plating overpotential>=0 V, programme
voltage<=4.2 V and Q30/Q1>=0.99 apply to **each band**. Discharge and rest
temperatures are diagnostics. Minimize each band's session-start-to80 time;
aggregate minutes and value-equivalent regret with the buyer's band mix. There is no
30-minute cutoff. About 0.5 min from that band's best is a HUMAN_INPUT
recommendation for value resolution, not a safety tolerance.

## 2. Physical system

Retain the pinned PyBaMM 26.8.0.0 DFN/OKane2022 lumped electrothermal and
30-cycle ageing programme. Proposed cooling levels x1/x2/x4 multiply the
identified model's total heat-transfer coefficient **through the whole
programme**, with area and ambient unchanged, as in Data Collection's study.
They are not subambient baths, pump-power multipliers or demonstrated vehicle
hardware. Report the actual h, area, heat-removal peaks/energy and missing
electrical/packaging costs. No combined time/energy objective is adopted.

Current runtime `BatteryCase` has no switch or cooling input and keeps
c2<=1.0. The public study includes c2=1.25 and switches above 4.0 V. A pinned
prospective action grammar/reference is required; changing a packet does not
relax current input validation. Bands 5/15/25/35/40 C are supported planning
anchors, not already qualified continuous temperature intervals.

## 3. Population P diagnostic Q and weights

Port the continuous requirement variant: draw the buyer ambient mix, one
starting SOC and common thermal/plating margins for the map. Suggested mix
Dirichlet(2,3,8,5,2), SOC probabilities 50/30/20%, thermal margin U[0,2.5] K
and plating margin U[0,2] mV remain HUMAN_INPUT, not measured fleet frequencies.
The owner selects SOC support 10/20/30% and the explicit start-SOC observable.
A known buyer may supply their measured ambient mix instead.

Fresh identified initialization remains a point mass; retain ageing during
30 cycles. Initial aged-state/restart support is absent. Q enriches safety
edges and near-best alternatives without redrawing NONE_FEASIBLE. Owner
selects `w_band=buyer_mix` for within-map value aggregation; outer-question
sampling/evidence weights and diagnostic Q remain separate.

## 4. Case contract

Bind the full five-entry map, drawn margins/SOC/mix, finite action banks per
band, programme/cooling identity, solver/environment/observer, uncertainty,
query budget, band projection and exposure linkage. Commit all five picks
before producer truth access. No one-protocol cross-band constraint remains.
No band is optional because its weight is small or zero. Missing reference
support is UNRESOLVED; a fully settled band without feasible actions is
NONE_FEASIBLE and cannot be replaced with a favorable new draw.

## 5. Reference policy

Reuse the public feasibility study as **existence evidence at its own inputs**,
not a complete v3 law bank. Refine cold-band plating near 2 mV and all drawn
thermal/plating boundaries, SOC crossings and time orderings. Retain all
30-cycle charge phases, spatial plating extrema, phase/cycle labels and
voltage/capacity reductions. Reference/infra failures never penalize candidates.
Tier2 buyer-tool credibility remains a target, not earned lab agreement;
the producer's `tier3` run label denotes its acquisition stage, not Tier3
experimental credibility.

## 6. Outputs and measurements

Report five actions, phase-correct admissibility intervals, session minutes,
per-band reference-best/equivalent sets, raw regret and value-equivalent regret.
For consistency with the proposed indexed-task contract in #820, recommend
zero regret inside the registered value band and the full minute difference
outside it. Report minutes beyond the band as a separate diagnostic, not an
alternative silently installed score rule. At SOC 10% the
observer is the v2 10-80 anchor, including the 120-s initial rest. At 20/30%
it is explicitly session-start SOC-to80, using the pinned charge integral and
capacity basis. No voltage proxy or first-hour censoring substitutes for it.
Variable-SOC reference coverage is NOT_DEMONSTRATED. The full map's weighted
minutes is defined only when its mandatory bands are eligible and feasible.

## 7. Construction contract

KEEP reconstruction and permitted TRAIN provenance. Candidate predictions
drive a frozen per-band search under one declared query budget; no reference
access while choosing. The indexed-task proposal is already owned by #820 at
`e1d0fdbec3a77f464e936d2750b55a78dfb5d2a8`; observer/map-report integration
stays with Validator/Test Lead, not installed by this packet. EV5, journal14,
the live contract, sealed Q3 v8 and #815 score-rule identity remain unchanged.

## 8. Research kit and deployment

Publish action/observer/band conventions and public own-seed/retired-case
provisions under existing authority. A model helps an engineer shortlist the
five calibrations; independent simulator verification follows before any
vehicle calibration. It does not replace a BMS safety controller. Band edges,
temperature measurement error, transitions, cooling hardware and control
deployment need separate qualification. End-to-end decision latency and
cooling hardware/electricity costs remain UNMEASURED.

## 9. Evidence plan

Inspected public [ambient-indexed evidence](https://github.com/carbonphysicsai/Carbon/blob/f79e7a61da10f1005e7438362ffc8baf6bf80d61/docs/development/evidence/battery-feasibility-02/ambient-indexed.json)
at `f79e7a61da10f1005e7438362ffc8baf6bf80d61`:

| Ambient C | Best reported minutes | Selected cooling | Best-pick ordering flag |
| --- | ---: | --- | --- |
| 5 | 77.2 | x1 | unresolved |
| 15 | 46.7 | x1 | unresolved |
| 25 | 32.9 | x1 | unresolved |
| 35 | 33.6 | x4 | unresolved |
| 40 | 38.6 | x4 | resolved under the study rule |

A complete feasible map exists in the with-cooling lane; the protocol-only
lane has no feasible 35/40-C choices. Some 35-C x2 actions are feasible; the
reported 40-C feasible set uses x4, so a complete map needs x4 allowed.
Feasible existence is not five settled optima. Historical flags use the
study's near-rival rule; adopting a 0.5-min value band does not retroactively
relabel them. Cold reported best plating is about 1.906 mV: it cannot be
assumed feasible for every new margin up to 2 mV. Refine and retain abstentions.

At the suggested mean mix, the reported picks average about **40.1 min**.
That is arithmetic on those observations, not a resolved fleet optimum or
measured deployment value. Initial SOC alternatives, full comparator coverage,
intervals, timing/memory/failure ledgers and cluster-aware power still need
their own evidence. No new solves occur here.

## 10. Readiness and next gate

The ambient map and buyer-mix value are owner-selected DEVELOPMENT semantics.
Numeric law, action bank, value resolution, reference adequacy, score-use,
power and executable map/observer integration are not adopted by a green
document test. Motor and the five-family laws remain unchanged. No LIVE,
product/security qualification, permit activation or spend follows. PR Lead
receives one PR; science and Validator coordinate via #42/#643.
