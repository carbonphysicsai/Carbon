# Battery v3 — ambient-indexed charging-map scorecard

DEVELOPMENT / SPECIFIED. Current scope: [Battery v3](../round1/battery-ambient-map-v3.md).
Working recommendation: retain the owner-approved question; no new customer
reframe selected. Overall KEEP: NOT_DEMONSTRATED. [Interpretation](analysis.md).

## Part V — buyer value

Proposed numeric adoption and adequacy acceptance remain HUMAN_INPUT; existing
owner-selected DEVELOPMENT limits are preserved, not reopened by this analysis.

### V1 — real decision

Buyer role: EV cell/BMS calibration engineer selects one charge/cooling recipe
per ambient band, offline, before independent cell/pack validation.
[NREL multi-scale battery modelling](https://www.nrel.gov/transportation/multi-scale-battery-physics-modeling.html)
describes model-guided charge protocols and thermal strategies; the independent
[integrated fast-charge/thermal-control study](https://arxiv.org/abs/2404.04358)
optimizes charging with active thermal management across ambient conditions.
These support the decision class, not an actual Carbon buyer, market share,
our five chosen bands, cooling coefficients or a physical performance promise.

### V2 — low/base/high in buyer units

ASSUMPTION scenario, not observed improvement: a better admissible map saves
**1 / 3 / 6 minutes per charging session** relative to the buyer's current
verified map. Buyer waiting-time value ASSUMPTION **$0.20 / $0.50 / $1 per
minute** gives gross **$0.20 / $1.50 / $6 per session**. Incremental cooling
electricity/hardware and verification costs are NOT_DEMONSTRATED, so net
benefit is not claimed. Fleet mix w is the buyer's ambient frequencies,
not uniform by convenience; mean time is sum(w_band × time_band).
The public band times 77.2/46.7/32.9/33.6/38.6 min are reported feasible
selections, NOT five settled optima or proof of that saving. Never promise a
30-minute session. A violation of plating/thermal/voltage/retention is not
compensated by saved minutes. Cold-band equivalence requires refinement.

### V3 — frequency

ASSUMPTION per BMS team: **2 / 6 / 12 map revisions/year**, **100 / 500 / 2,000
sessions/day** affected after deployment. These are elicitation ranges, not
fleet sales or demand. Annual gross session value is explicitly conditional
on actual sessions and Tier 3/deployment evidence; not multiplied into V2 as
present commercial value. Ask buyer for revision and temperature-frequency logs.

### V4 — fast-model leverage

Existing #776 proposal: 100 actions ×5 conditions =500 complete programmes
plus refinements, not the five final choices. Public sources above establish
optimization but do not establish a buyer's evaluation count; **workflow
evaluation count UNSOURCED**. Do not pass V4. Historical 91 CPU-s ×500 =
12.64 CPU-h is a sensitivity calculation ONLY; v3 per-band cooling/SOC/30-cycle
programmes need matched measured C1. Retain charge-integral observers and
final reference verification; compare strongest cached/interpolated control.

### V5 — credibility

Buyer tool assumption: COMSOL electrochemical/thermal or the buyer's validated
PyBaMM model. Carbon PyBaMM is not automatically the same parameter set,
thermal boundary or measurement. Target Tier 2 per #767, **earned tier
NOT_DEMONSTRATED** for v3. Require matched ambient/SOC/cooling and near-plating
benchmarks, curve/limit and per-band pick/minute-regret agreement. Physical
charging safety/lifetime requires Tier 3 and separate deployment acceptance.

## Part T — Data Collection/Test Lead receipt

### T1 — complete feasible answer

OBSERVED_PUBLIC at [96983b03b1b7fb06749e7584b16f0bb7be2dcc01](https://github.com/carbonphysicsai/Carbon/blob/96983b03b1b7fb06749e7584b16f0bb7be2dcc01/docs/development/evidence/battery-feasibility-02/ambient-indexed.json):
complete feasible indexed map reported at studied inputs with cooling allowed.
T35 includes some ×2 feasible actions; selected warm best and T40 feasible
actions use ×4. These are heat-transfer coefficients, not four-times pump
energy. Hard limits per band: charging ≤45 °C, plating ≥0 V over EVERY charge,
4.2 V, Q30/Q1≥0.99. Discharge temperature diagnostic. Variable start-SOC and
extra buyer margins are not covered by map existence alone.

### T2 — contested decisions

Published feasible/resolved counts by 5/15/25/35/40 °C:
**3/41, 11/39, 16/131, 15/132, 3/36**. Overall fractions 7.3/28.2/12.2/11.4/8.3%
are diagnostic, not gates. Current T5/T40 panels FAIL the five-feasible count;
near-limit infeasible counts and equivalent-set diversity are missing for
every band. Add buyer-plausible protocols within existing permissions and
refine near-boundary ones; do not prune aggressive recipes, change 45 °C/0 V,
or fabricate variants as independently informative actions. Mix-only draws
change aggregate value but NOT independent per-band argmins.

### T3 — power

NOT_DEMONSTRATED for indexed v3. Historical eight-question one-batch failure
does not prove failure after allowed cross-batch accumulation. Optimizer
owns indexed panel adapter, four controls, moderate severity and k/windows/E
receipt; bands and same-bank windows are correlated. No new E is chosen here.

### T4 — close calls

NOT_DEMONSTRATED at v3 question level after refinement. Historical battery
v8's 87.5% is a different question/reference identity, not a v3 rate.
Nominal best ordering unresolved except reported T40; cold ~1.906-mV
plating requires refined truth or UNRESOLVED. Do not count probe uncertainty
as model failure or discard close draws.

### T5 — reference

Require complete charge-integral session time, extrema over all charging
legs, matched cooling law and mesh/time/cycle checks at safety boundaries.
Reported 35.6-min voltage-probe value was superseded by 63.3-min integral
observation; 32.9-min admissible study selection is a separate fact. Historical
EV5/journal14/live contract unchanged. v3 accepted reference receipt pending.

## Part C — no spending authority

### C1 — per-case cost

OWNER_REPORTED historical 91 CPU-s; v3 pinned complete-programme p50/p95,
peak memory and failure ledger NOT_DEMONSTRATED. Not a five-band map timing.

### C2 — startup

UNMEASURED v3. Legacy 500 ×91 s yields12.64 CPU-h before overhead; historical
2,684-solve quiz yields67.85 CPU-h. Neither is a bill: at serial CPU=wall and
€1.37/h the latter is €92.95 before overhead, so it can exceed €100.
Use measured throughput/host bill and actual refined programme manifest.

### C3 — ongoing

NOT_DEMONSTRATED: registered windows/week, remaining E and refreshed map-bank
cost required. Never count mix/threshold draws as fresh physical banks; compare
complete refresh demand to ≤15% measured AX42-equivalent capacity.

### C4 — validator

NOT_DEMONSTRATED for indexed v3 rebuild+inference+optimizer vs #727 envelope.
Validators never run battery reference programmes. Current generic adapters
do not prove a five-band/SOC-specific capacity profile.

## Next decision and preserved value

No second rewrite of the already approved v3 job is justified by low pass
fractions. Close T2 boundary coverage and T3/T4 first. All V2 values above
are unchanged before/after this analysis; no benefit gain claimed from changing
the ruler. If even an adopted single reframe cannot establish contested
safe choices and powered affordable evidence, owner chooses replacement.
