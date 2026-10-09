# Cooling cell — thermal/hydraulic response maps at the correct interface

**DEVELOPMENT / SPECIFIED; performance NOT_MEASURED; acceptance HUMAN_INPUT.**
[Shared comparison](README.md); [return checklist](data-collection-return.md).
Buyer: [cell v3](../round1/cooling-cell-v3.md). **No full cold plate.**

## Buyer decision and incumbent

Choose an interior-cell geometry/flow action under frozen buyer service maps,
with peak **lid-side TIM2 interface <=85 C**. Vapour-chamber properties and
post-spreader interface heat maps are buyer inputs, not model-selected design
actions. Final inlet/lid settings and cell hydraulic allocations/objective
remain HUMAN_INPUT pending owner selection. The old assembly 50 kPa/2.5 W/
3 L/min limits are **not adopted cell constraints**. No manifold composition,
die-temperature certificate or full-plate acceptance enters this comparison.

CLOSED_BANK: cache complete local thermal extrema/fields and cell pressure/
flow quantities, then re-evaluate supported requirements. NEW_SUPPORTED:
ordinary response-surface/local interpolation of thermal and hydraulic outputs
within a fixed material/map/service identity, with the same design search.
Retain an applicable thermal-resistance/channel relation as a physical control;
do not make it the only incumbent when a calibrated output map is available.

## Method basis and reuse

[Mat et al., 2024](https://www.tj.kyushu-u.ac.jp/evergreen/contents/EG2024-11_2_content/p1426-1434.html)
uses water-cell response-surface optimization with 2,500 **response-surface
design points**, not 2,500 separately measured CFD solves. It supports the
ordinary incumbent class, not our maps/lid/pressure allocations. KEEP
[existing cell baseline inventory](../../../../scripts/dev/cold_plate/reference/baselines.py)
and public output conventions only within their recorded applicability.

Use accepted OpenFOAM conjugate-cell environment/deck/mesh/extractor pins plus
spreader/source/interface-map/TIM identities supplied by Data Collection.
Changed lid/map/temperature support requires new evidence, not an old cache
hit. Exact new baseline/data/package pins remain HUMAN_INPUT; a cooling solver
version alone does not identify this post-spreader task.

## Witness and decision checks

Freeze witnesses independently of fitting: each mandatory uniform/hotspot/warm
stratum, thermal/pressure decision edges and alternate feasible contenders.
Compute `max_x(T_plate_face(x)+R_TIM(x)*q_interface(x))` at matched local
coordinates, not mean TIM rise plus an unrelated field maximum. Do not add
TIM1/die/lid drops to the case-plane quantity. Preserve energy and map-integral
checks and actual cell-to-physical scaling for flow/pressure/power.

Linear thermal scaling/superposition is a proposed baseline only where constant
properties and flow/map assumptions are independently supported. No automatic
translation below PG25's 30-C support, arbitrary hotspot flattening or selected
TIM/lid headroom. Refine boundary contenders; unsupported map is UNRESOLVED.
Report false-cool decisions, margins in K, hydraulic burdens and regret under
the registered cell objective once supplied; no invented hydraulic objective.

## Cost, stop condition and credibility

Owner-reported **~0.45 CPU-h** is existing cell C1 context, not new v3 complete
panel p50/p95. Count unique physical cases, fitting, searches and retained
thermal/hydraulic checks, including any separately authorized lid-model work.
Sensitivity questions on the same outputs save solves but do not renew E.
If simple maps match decisions at acceptable latency, no demonstrated V4
advantage. Missing final inputs/contested-value evidence blocks that measurement
scope; this spec does not release the held 53 jobs. Tier 2 against matched
Fluent/Icepak **cell** witnesses remains a target, never a full-assembly claim.
