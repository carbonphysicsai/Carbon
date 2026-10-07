# f17 — Carbon-owned passive micromixer design optimizer (proposal)

**Status:** DEVELOPMENT design specification; no registered optimizer, solved
design bank, qualified reference, score, customer deployment or clinical
claim. The [round-one packet](../round1/f17-passive-micromixer.md),
[numeric sheet](../round1/requirements.json) and
[common packet](../COMMON_DESIGN_PACKET_V1.md) own the selected requirements.
New proposals are marked **HUMAN_INPUT (recommended)**. Test Lead owns
verification, attacks, sizing, and score adoption; Carbon must freeze the
optimizer before protected observations.

## Buyer decision and domain

The hypothetical cartridge engineer chooses bottom staggered-herringbone
groove **depth** `20–40 µm` and **pitch** `100–250 µm` (continuous), plus
**grooves per half-cycle** `6–10` (integer). Groove width is fixed at 50 µm,
angle 45°, asymmetry corner 1/3 width and wall-end clearance 10 µm in a
300 × 100 µm, 10 mm base channel. The three total flows `1,3,5 µL/min` and
three diffusivities `0.5,1,2 × 10⁻¹⁰ m²/s` are **exogenous conditions**, not
optimizer controls. They form the packet's nine equally weighted synthetic
`P_dev` combinations; do not choose an easier flow or filter high Péclet cases.
This is one robust geometry decision across all nine conditions, not nine
independent buyer scenarios.

Maximize `min_{nine conditions} M`, dimensionless outlet mixing uniformity,
where the packet defines `M = 1 − sqrt(variance_out/0.25)` at x = 10 mm using
positive axial-flux weighting. The buyer success limit is `M ≥ 0.8` at **all**
nine conditions. At every condition, pressure drop must be ≤ 250 Pa and mean
hydraulic residence, including grooves, ≤ 20 s. Reject intersecting/invalid
geometry, backflow incompatible with the specified outlet measurement and
invalid inputs; missing velocity evidence blocks scalar use. Hard conditions
and validated mass/solute/concentration checks precede soft ranking. A high
mean M cannot compensate for the worst condition or pump burden. Secondary
trade-off is **HUMAN_INPUT (recommended): report a Pareto diagnostic of
worst-M versus worst pressure and residence, without a new weight or changing
the primary decision**. Equal worst-M picks use canonical `(depth,pitch,
grooves_per_half_cycle)` order after units are fixed. `NONE_FEASIBLE`/abstain
is the correct answer when the complete verified bank has no design meeting
all nine constraints; missing truth produces `UNRESOLVED`, not an assertion
that none is feasible.

## Fixed search and decision budget

**Class (a), exhaustive finite lattice, is proposed** for the first
scoreable decision contract: only two continuous variables and one small
integer axis. **HUMAN_INPUT (recommended): depth `{20,30,40} µm` × pitch
`{100,175,250} µm` × all packet integers `{6,7,8,9,10}` = 45 geometries.**
The finite bank must be validated for actual groove intersections and frozen
before testing; rejected CAD points are excluded by a preregistered rule.
This deliberately claims an optimum **within the bank**, not over continuous
fabricable geometry. The packet's continuous bounds remain available for
future prospective bank refinement. Gradient search is not justified by the
prepared Level-0 surrogate contract, and local search saves little model work
on 45 points while opening path attacks. Query all nine conditions for every
valid bank geometry: **HUMAN_INPUT (recommended): at most 405
geometry-condition model evaluations per task**, inclusive of failed calls.
Carbon fixes the canonical order and may permute it with a producer-owned
hidden seed; no miner-selected seed, dynamic stopping or post-observation
optimizer change. The count is provisional until inference latency and
validator cadence are measured. If the bank cannot be queried within its
fixed budget, emit `UNRESOLVED_BUDGET` rather than rank a convenient subset.

## Truth verification and cost

For every selected geometry, compare to independent, pinned OpenFOAM laminar
velocity and passive-scalar truth at all nine conditions, including mass/
solute balance, bounded raw concentration, independent mesh refinement and a
resolved maximum-Péclet scalar boundary-layer witness. The packet charges
velocity and scalar as separate jobs: **18 primary solver launches per design**
for nine condition pairs, before controls/refinement. The proposed 45-bank
therefore has an **810-launch lower bound** before failures and refinement;
the existing 40-launch/8-node-hour/$25 grant can perform the stated nominal
preflight and controls only. Sharing a flow solve across diffusivities may be
an engineering optimization after exact case/provenance and numerics are
qualified; do not credit that saving before a measured, pinned implementation.
**Reference CPU-hours and dollars per design, complete-bank producer cost,
and per-task cadence are NOT_DEMONSTRATED.** The producer-cost formula is
`45 × measured nine-condition design cost + controls + refinements + failures
+ setup`; only the lower-bound launch count is currently sourced. A new
bank/confirmation allowance, quote, pinned image/deck, retained ledger and
reference adequacy are prerequisites to reference-judged tasks.

Define exact finite-bank regret in physical units as
`best_verified_worst_M − selected_verified_worst_M` (dimensionless M), only
when all potentially better bank members are resolved and the selected design
is feasible at all nine conditions. Report pressure violation in Pa, residence
violation in s, and M shortfall separately by condition; do not bury them in
an arbitrary scalar penalty. If a feasible pick is missing but a verified one
exists, expose false `NONE_FEASIBLE`. If any potentially superior member or the
selected design is reference-unresolved, report best-observed difference and
`UNRESOLVED`, not exact regret. Independent pressure truth may be reused
across diffusivities only with exact versioned provenance.

The packet's mass/solute residual ≤ 0.5%, concentration in
`[−0.001,1.001]`, ΔM ≤ 0.02 and Δpressure ≤ 5% under independent mesh
refinement are selected checks, not a qualified error distribution. Near
`M = 0.8`, `Δp = 250 Pa` or residence `20 s`, refine until an interval verdict
is defensible. **HUMAN_INPUT (recommended): flag `|M−0.8| ≤ 0.02` and
`|Δp−250 Pa| ≤ 5% of 250 Pa` for mandatory refinement**, using the packet's
refinement scales only as provisional triggers. A residence review band is
**HUMAN_INPUT** until CAD-volume and numerical uncertainty are established.
Residual `UNRESOLVED` gets Test Lead's preregistered conservative scoring
backstop; reference failure is never imputed as a failed mixer.

## Gaming, power and buyer use

The Test Lead-owned attack set should include (1) an edge-optimist that makes
a truly failing M/pressure/residence boundary look passing, (2) an
over-cautious model that suppresses a better feasible mixer, (3) sign errors
in pressure gradient or concentration-variance-to-M conversion, and (4) an
optimizer-aware model accurate on public bank points but wrong on hidden
whole-geometry or condition probes. Compare against diffusion-scaling,
smooth-channel/network and transport-ROM baselines under the same complete
flow-plus-scalar charges. A second, differently ordered or local registered
optimizer with Carbon-owned hidden starts can diagnose path-specific gaming;
agreement is evidence to study, not a substitute for reference truth. The
exhaustive registered choice itself cannot be changed after seeing models.
Physical-unit regret and false `NONE_FEASIBLE` expose over-caution; hard-limit
violations expose optimism. Do not count nine correlated conditions as nine
independent tasks.

**Hidden-batch task count is HUMAN_INPUT, NOT_DEMONSTRATED.** The packet now
sketches [fluid/assay/cartridge job variation](../round1/f17-passive-micromixer.md)
and an eight-brief scoping inventory; the current reference still defines one
nine-condition buyer job and no adopted `P_job`/protected `Q_job`. Test Lead
must approve eligible whole-job contexts, reference support and behavior-
defined good/bad controls, then size the batch by resampling distinct jobs
with shared assay/platform clusters retained. Report each bad subtype, false
feasible, false `NONE_FEASIBLE`, and worst-M regret, including maximum-Péclet
coverage. **HUMAN_INPUT (recommended): pilot eight eligible jobs only after
the law and reference budget exist**; this is neither a powered nor approved
hidden batch. The fixed 3 × 3 panel stays complete within every supported job.

The buyer-facing tool would take the pinned channel/inlet/fluid/flow/
diffusivity contract and approved groove bank, and return groove parameters,
worst and per-condition M, pressure drop in Pa, residence in s, raw-measurement
provenance, margins and `NONE_FEASIBLE`/unresolved state. It could replace
manual enumeration within this synthetic passive-scalar decision, not cartridge
experiments, chemistry or assay qualification. **HUMAN_INPUT (recommended):
five-minute interactive design latency**; the packet has no deployment-time
requirement and this must be checked against 405 model queries and the actual
customer workflow. The same frozen Carbon-owned optimizer and tie rule should
serve both grading and the delivered tool; protected reference labels remain
operator-side.

## Open gates

Test Lead/owner must approve the finite lattice, inference budget, scenario
law and strata, reference-cost quote, near-limit uncertainty, power target and
latency before testing. The `carbon/design_search/tasks.py` named in the
request was absent in this checkout; adapting the current Challenge-neutral
design-search interfaces is later implementation work. No grader, hidden
pool, validator, live contract or miner surface is changed here. Groove flow/
transport and reference adequacy remain **NOT_DEMONSTRATED**.
