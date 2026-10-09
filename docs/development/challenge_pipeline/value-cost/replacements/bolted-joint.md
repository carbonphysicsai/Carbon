# Bolted-joint preload and contact load transfer — f08 candidate 1

**Strongest cheap baseline first:** VDI 2230/compliance calculation, a
contact-aware fitted response surface, and exact complete-output lookup for
closed menus. A linear beam-bolt screen is not the strongest comparator if the
buyer already calibrates prying/contact. DEVELOPMENT / SPECIFIED;
[common boundaries and costing](README.md) apply. Replacement not adopted.

## V1 — whose decision, and evidence

Buyer role: industrial-machine mechanical design engineer selecting bolt
preload and a compact bracket's local flange thickness/bolt spacing before
detailed verification. They need enough clamping to avoid opening/slip without
overloading bolt or parent material under an eccentric service load.

[Ansys's bolt-pretension course](https://learninghub.ansys.com/learn/course/external/view/elearning/36/ansys-mechanical-bolt-pretension)
explicitly connects assembly simulation to bolt size, number and preload
selection. [NASA's Fastener Design Manual](https://ntrs.nasa.gov/api/citations/19900009424/downloads/19900009424.pdf)
independently documents fastener selection, joint loading and preload. These
support a real workflow, not Carbon credibility, exact annual volume or a
fictional paid customer. The proposed commercial step is a **local shortlist**,
not fastener certification, fatigue life or flight/pressure-vessel acceptance.

## V2 / V3 — explicit low, base, high scenarios

All transferred counts, hours and rates below are ASSUMPTION, not source data.

| Buyer unit | Low | Base | High |
| --- | ---: | ---: | ---: |
| Engineer-hours at stake per joint revision | 3 | 8 | 20 |
| Gross effort value, EUR/revision | 180 | 720 | 2,400 |
| Eligible design teams in a conditional cohort | 5 | 20 | 50 |
| Joint revisions/team/year | 6 | 24 | 60 |
| Exact decisions/year in that cohort | 30 | 480 | 3,000 |

Repeated decision is a changed joint/load/tolerance design, not each shipped
machine or bolt. Sources establish why sizing/preload is revisited, **not the
cadence**. Ask buyers for revision logs and current calculation/verification
effort. Wrong picks cause another design/verification iteration; no accident,
downtime, recall or liability value is monetized. Realized benefit floor zero.

## Proposed supported task and reference

Finite two-bolt bracket with geometry/preload actions; mandatory load direction,
friction and assembly scatter as stated inputs, not hidden nuisance. Outputs:
bolt-force histories, interface opening/slip, reaction balance and appropriate
stress/strain observables. Avoid mesh-singular peak stress as the sole criterion.
Numeric material laws, load/strength/slip limits and P/Q/w are HUMAN_INPUT.
No safety limit is relaxed. Creep/fatigue/loosening and full machine dynamics
are outside this first step; buyer still retains detailed verification.

Open route: [CalculiX](https://www.dhondt.de/) local 3D nonlinear contact with
pretension/assembly step followed by combined loading; select the acquisition
owner's exact supported release and immutable Linux image, material/deck and
extractor pins before any work. Solver/image pins are pending, not a built
package. Verify preload locking, contact opening, friction/load balance and
mesh refinement against matched Ansys/Abaqus decks; **Tier 2 target only**.

## C1 / C2 — hypotheses, not measured percentiles

One case is an entire assembly-preload + service-loading history for one
geometry/condition, including mesh/extraction. CPU-h hypothesis
0.03 / 0.08 / 0.24 (1.8 / 4.8 / 14.4 CPU-min); RAM 1 / 4 / 12 GiB.
Illustrative 24 designs × 4 strata = 96 cases, 32 twice-cost refinement cases,
20 charged failed attempts and 8 two-tool witness pairs: 196 case-equivalents.
[Sheet](scenarios.json): C2 **26.11 / 42.08 / 93.21 EUR** under common serial,
tax and overhead assumptions. C1/p95/C2 PASS are NOT_DEMONSTRATED.

## Why Carbon might win — and the kill test

Hypothesis: geometry-dependent contact opening redistributes loads nonlinearly;
cached linear modes/compliance can miss the feasibility/pick switch. Whole-
geometry holdouts near opening/slip compare against the calibrated ordinary
surface, not just hand formulas. Carbon must save quality-matched search/
verification time or reduce false-feasible decisions without more fallback.
Reject if those baselines already settle buyer decisions, if calibrated
contact/material uncertainty dominates, or if refinement consumes the budget.
Rank first for f08 because the nonlinearity addresses the linear-library risk
without adding a full machine, crash or certification problem. Not a V4 PASS.
