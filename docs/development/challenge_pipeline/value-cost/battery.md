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

### V3 — fleet-session volume, not map revisions

Two independent scale anchors: [TfL's July 2025 report](https://content.tfl.gov.uk/tfl-commissioners-report-22-july-2025-acc.pdf)
records its 2,000th zero-emission bus; [Uber's October 2025 release](https://www.uber.com/us/en/newsroom/uber-electric/)
reports over 200,000 EV drivers. Neither is a matching-chemistry buyer receipt:
zero-emission includes other technologies, and independent drivers are not one
controllable fleet. Neither source measures eligible fast-charge sessions.

Conditional low/base/high cohort, **every factor ASSUMPTION**:
100/1,000/10,000 vehicles ×0.3/0.7/1 **packet-eligible, time-bottleneck**
sessions per operating day ×250/300/330 days = **7,500/210,000/3,300,000
sessions/year**. The daily rate includes eligibility, not all charging.
V2 gives **$1,500/$315,000/$19.8m annual gross** only if the stated per-session
improvement actually occurs. Empirical lower bound **zero**; not TAM, revenue,
observed savings or deployment authority. Physical fleet use needs Tier 3.
Obtain chemistry, charging/SOC/ambient/queue logs and cooling energy costs.
Map-building events (assumed 2/6/12 revisions per BMS team/year) are separate;
never multiply map-search CPU savings by every session.

### V4 — map-building leverage, not a solve every charge

[Attia et al.](https://web.mit.edu/braatzgroup/Attia_Nature_2020.pdf) search a
224-protocol menu; 117 candidates were never tested. Different chemistry and
limits: menu size is an analogue, not 224 full reference calls. For a new
five-band map, **N=224/1,120/11,200 complete programme evaluations is an
ASSUMPTION** (base 224 ×5; extra SOC/age/tolerance exploration in high).
Owner reports **91 CPU-s/programme**; applicability to v3/refined cold-band
programmes needs the matched C1 ledger. The public TRAIN timing is a
400-query batch, not single-query latency; see [timing discipline](analysis.md#workflow-leverage-with-build-cost).

Using the shared illustrative build/reuse assumptions, base saves **25.89
serial wall-h / $2.59 compute per map**, end-to-end leverage **11.69×**.
Not V2 session savings, not labour saved, not a measured speedup. Potential:
a 10,000-point SOC/ambient/cooling sensitivity search between calibration
reviews, retaining per-band truth/refinement. Cached verified maps already
serve live sessions cheaply; Carbon must beat cached/interpolated/POD maps
at matched admissibility, not claim real-time BMS necessity. V4 PASS remains
NOT_DEMONSTRATED. [All sensitivities](volume-leverage.json).

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
