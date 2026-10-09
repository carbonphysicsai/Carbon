# Battery v3 — precomputed charge maps before a learned predictor

**DEVELOPMENT / SPECIFIED; performance NOT_MEASURED; acceptance HUMAN_INPUT.**
Use the [shared comparison](README.md) and [return checklist](data-collection-return.md).
Buyer contract: [five-band packet](../round1/battery-ambient-map-v3.md),
[continuous law](../question-laws/battery-ambient-indexed-v3.md) and
[indexed optimizer](../optimizers/battery-ambient-map-v3.md). No live BMS control.

## Buyer decision and incumbent

Choose `(c1,c2,switch_voltage,cooling_level)` independently at 5/15/25/35/40 C.
Minimize session-start-SOC-to80 minutes, aggregated by the buyer ambient mix.
Every band retains charging T<=45 C, plating>=0 V on every charge, programme
voltage<=4.2 V and Q30/Q1>=0.99. Discharge temperature is diagnostic, not a new
charging gate. Changing mix changes map value, not independent positive-weight
band argmins. About 0.5 min equivalence remains HUMAN_INPUT, not safety slack.

First comparator: **exact precomputed output/decision map** for the complete
covered action banks and supported SOC. Reapply drawn thermal/plating margins
to stored phase-correct extrema/intervals, then pick per band. Store feasible
sets, not only one recipe per temperature. This avoids enumerating the product
of five action menus. If that already makes the right decisions, faster neural
inference alone does not establish buyer value.

NEW_SUPPORTED comparator: conservative ordinary local interpolation of full
decision observables across covered protocol/service coordinates, followed by
the same exhaustive per-band search. Do not interpolate recipe parameters and
declare the resulting recipe safe. Partition discrete cooling/switch actions;
no unqualified temperature, aged-state or SOC extrapolation. The 10/20/30% SOC
law needs actual coverage; current planning anchors are not continuous support.

## Method basis and reuse

[Attia et al., Nature 2020](https://web.mit.edu/braatzgroup/Attia_Nature_2020.pdf)
demonstrates bounded multistep charging-protocol selection. Its LFP chemistry,
ten-minute task and experimental learning are **not** v3 safety evidence or
an already implemented safe interpolation baseline. Cache/interpolation here
is a comparator recommendation based on the registered finite-menu decision.
[Romeo Power's battery-model account](https://www.mathworks.com/company/technical-articles/modeling-and-simulating-battery-performance-for-design-optimization.html)
describes temperature-, SOC- and age-indexed lookup tables used to explore
charging methods in an industrial design workflow. It supports the incumbent
method class, not v3 plating, lifetime or five-band admissibility.
KEEP existing public feasibility outputs and charge-integral observers only at
their own pins; no 30-s voltage-probe proxy for session time.

Reference anchor in the packet: PyBaMM **26.8.0.0**, DFN/OKane2022, lumped
thermal and 30-cycle programme. Data Collection must supply exact environment,
parameter/deck/observer hashes and prospective action grammar; current runtime
`BatteryCase` does not cover all study switches/cooling/c2 actions. Package and
baseline executable pins remain HUMAN_INPUT until supplied. No EV5 replay.

## Witness and decision checks

Separate non-hidden whole-programme witnesses from fit rows. Cover every band,
supported SOC, each cooling action and safety-edge/near-best rivals. Cold-band
~2-mV plating needs refinement, not a margin chosen to hide a breach. Evaluate
all charge cycles and phase labels, session crossings and Q30/Q1. Preserve
four bands' historically unresolved best ordering; a feasible complete map
does not establish five exact optima. Report band verdicts/equivalent sets,
complete-map admissibility, weighted minutes/regret and unresolved coverage.

## Cost, stop condition and credibility

Count one whole 30-cycle action evaluation, not a timestep or charging session.
Owner-reported **91 CPU-s** is historical C1 context, not current map/observer
p50/p95 or cheap-method cost. Measure bank acquisition, lookup/interpolation
fit, all five searches and retained edge verification, cold and reused.
Fleet sessions are buyer-volume units, not repeated reference solves.
Stop the affected verdict for missing support/refinement; no unsafe nearest
recipe. If an exact covered map already meets latency/quality, report no
demonstrated V4 advantage and test any claimed better decision separately.
Tier 2 is an interim simulator-screening target; Tier 3 remains required for
EV reliance. Neither tier is earned by this specification.
