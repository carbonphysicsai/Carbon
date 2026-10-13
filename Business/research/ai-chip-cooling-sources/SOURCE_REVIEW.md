# Public source review and operating recommendations

## What each source supports

Ranges below are source envelopes or explicit engineering assumptions, not
statistical confidence intervals. A sourced single specification is an
endpoint, not a probability distribution; missing bounds stay HUMAN_INPUT.
Midpoints calculated for planning are labelled ASSUMPTION. Public technical
facts are paraphrased; no vendor document or figure is redistributed.

| Quantity | Low / base / high | Source, locator and interpretation |
| --- | --- | --- |
| ASHRAE W32 maximum | 32 / 32 / 32°C | [ASHRAE AI framework, introduction Fig.2](https://www.ashrae.org/technical-resources/topics-and-initiatives/ai-data-center/introduction-and-purpose); W32 replaces W3 |
| W40 maximum | 40 / 40 / 40°C | Same source; added class |
| W45 maximum | 45 / 45 / 45°C | Same source; W45 replaces W4 |
| Entire W-class lower endpoint | 2 / 2 / 2°C | Same source; W17, W27, W32, W40, W45 and W+ share it. W+ is beyond 45°C; no finite upper endpoint sourced |
| OCP warm secondary supply | 30 / 33.5 / 37°C | [OAI liquid-cooling guidelines, §1.4 p.8](https://www.opencompute.org/documents/oai-system-liquid-cooling-guidelines-in-ocp-template-mar-3-2023-update-pdf); midpoint ASSUMPTION, not prevalence |
| OCP hotter secondary supply | 40 / 42.5 / 45°C | Same §1.4; midpoint ASSUMPTION |
| Lenovo warm facility / technology loop | FWS 27–32°C; TCS 32–37°C | [LP2018, table 1](https://lenovopress.lenovo.com/lp2018-lenovo-neptune-direct-water-cooling-standards); separate source intervals, midpoints 29.5/34.5°C ASSUMPTION |
| Lenovo hot facility / technology loop | FWS 40–45°C; TCS 45–50°C | Same table; midpoints 42.5/47.5°C ASSUMPTION. Its Solution 1 explicitly uses 45°C DLC water with H200; not an approval for all GPUs |
| OAM cold-plate flow/device | 1 / 1.5 / 2 L/min | OCP §1.3 p.7; endpoints sourced, midpoint ASSUMPTION |
| PG25 flow per removed heat | 1.25 / 1.5 / 2 L/min/kW | OCP §1.3 p.7; base is source's typical target; associated bulk temperature rise 7.5–12°C, target 10°C |
| High-power vendor test flow | 4.28 / HUMAN_INPUT / 6.06 L/min at about 4 kW | [CoolIT technical brief R1, 2025-03-13, table 1](https://www.coolitsystems.com/wp-content/uploads/2025/03/4000W-coldplate-Technical-Brief.pdf), indexed primary table; no typical base claimed. Its [primary announcement](https://www.coolitsystems.com/resources/news/coolits-4000w-coldplate-establishes-single-phase-direct-liquid-cooling-technology-leadership/) states 6 L/min and >97% capture |
| Loop pressure example, 8 parallel OAMs | 7 / 7 / 7 psi at 10 L/min system | OCP §6.1 p.23; about 48.3 kPa. Branch/device flow is 1.25 L/min if evenly distributed (derived), not 10/device |
| Loop pressure example, 4 parallel pairs | 10 / 10 / 10 psi at 10 L/min system | OCP §6.1 p.23; about 68.9 kPa. Each series plate sees 2.5 L/min if uniform (derived), not 10/device |
| Vendor test full-loop drop | 8 / 8 / 8 psi | CoolIT announcement; about 55.2 kPa, includes fittings and QDs. Not an interior-cell drop |
| Vapor-chamber effective k | >5000; base and upper bound HUMAN_INPUT | [Boyd vapor-chamber datasheet, p.2](https://info.boydcorp.com/hubfs/Thermal/Two-Phase-Cooling/Boyd-Vapor-Chamber-Datasheet.pdf), ©2020. Product performance claim, not a constant material property |
| Boyd advertised VC thickness | 1 / 3–4 typical / 10 mm | Same p.2; no 0.5-mm Carbon lid calibration follows |
| Boyd advertised maximum heat flux | 350 / 350 / 350 W/cm² | Same p.2; product-family capability endpoint, not guaranteed across orientations/geometries; no uncertainty band sourced |
| NVIDIA Blackwell Ultra maximum TDP | HGX B300 1100 W; GB300 1400 W | [Official datasheet, technical specifications p.3](https://resources.nvidia.com/en-us-gpu-resources/blackwell-ultra-datasheet?xs=443990), indexed primary text: configurable maxima, no minimum/base duty load or lid partition given |
| AMD MI350X / MI355X | 1000 / HUMAN_INPUT / 1400 W across two products | [CDNA4 whitepaper p.15](https://www.amd.com/content/dam/amd/en/documents/instinct-tech-docs/white-papers/amd-cdna-4-architecture-whitepaper.pdf), [MI355X requirements](https://www.amd.com/en/products/accelerators/instinct/mi350/mi355x.html), [MI350X requirements](https://www.amd.com/en/products/accelerators/instinct/mi350/mi350x.html). Typical board powers; not all main-die or lid heat |
| Published heater flux example | 1000 W / 9 cm² = 111.11 W/cm² | OCP §6.2.2 p.25; thin-foil TTV, 30×30 mm, copper sandwich. Main-chip guidance §2.1 separately estimates 60–80 W/cm² for 70–80% of a 1000-W module; midpoint 70 W/cm² is ASSUMPTION, not a current vendor measurement |
| Current vendor lid power/area/local flux | HUMAN_INPUT / HUMAN_INPUT / HUMAN_INPUT | None of the cited current product specifications supplies a transferable interface-resolved map |

Unit conversions are mathematical, not measured new data: 1 psi≈6.894757 kPa;
1 W/cm²=10000 W/m²; 1 L/min=1/60000 m³/s. Psi conversion follows
[NIST SP811 appendix B.9](https://www.nist.gov/pml/special-publication-811/nist-guide-si-appendix-b-conversion-factors/nist-guide-si-appendix-b9).
This review found useful operating guidance and product/test anchors, not a
universal pressure budget. Choose and register a cell allocation only after
reserving head for headers, distribution, hoses and QDs. Static operating or
proof-test pressure is a different quantity from pump differential pressure.

## Warm water without a scope mistake

ASHRAE's named upper endpoint describes the applicable equipment environment;
class capability spans its range. It is not a mandate to run at that endpoint.
Facility water may pass through a CDU heat exchanger before reaching the
technology loop. State FWS, CDU approach and **actual cell inlet** separately.
Lenovo's FWS/TCS tables explicitly demonstrate why W32 facility supply can
coexist with a hotter device inlet. A 45°C cell point needs that stated inlet;
it cannot be inferred from a W45 label alone.

Current practice is SKU-specific: Lenovo's public hot-water examples establish
that a warm-water hypothesis is commercially recognizable. They do not
validate Carbon's assumed TIM, periodic cell, homogenized lid or 85°C proxy.
The 2023 OCP source is dated design guidance with non-universal examples,
not a 2026 survey of shipped GPU installations.

## Effective lid conductivity and local heat flux

The fixed 0.5-mm lid and copper k=391 W/m/K in Carbon's current
[domain.py](https://github.com/carbonphysicsai/Carbon/blob/07d414638f1ede517d59cca2a30554360d934716/carbon/cold_plate/domain.py)
are development choices. The [v3 packet](https://github.com/carbonphysicsai/Carbon/blob/07d414638f1ede517d59cca2a30554360d934716/docs/development/challenge_pipeline/round1/cooling-cell-v3.md)
requires a buyer vapor-chamber input and pending characterization. Swapping
in Boyd's >5000 scalar does not upgrade this model. Separate in-plane
spreading, through-plane resistance and contacts. Record heat-load/map,
orientation, working temperature and transport/dryout envelope. A nonlinear
two-phase limit can invalidate a linear effective-k approximation at high
local flux, even if mean temperature is low.

For screening only, k low/base/high 2000/5000/10000 W/m/K is ASSUMPTION,
motivated by the scale of commercial two-phase claims; all three lack a
matched calibration for Carbon. Characterized lid thickness, tensor k,
interface transfer operator and validity bounds stay HUMAN_INPUT. Boyd's
thickness range makes blindly preserving Carbon's 0.5-mm lid particularly
unsupported. A source-provenance post-spreader map would also work within
its stated envelope, but this research supplies no such map.

Heat flux must name the plane and area. Current TBP/TDP includes power beyond
the main heater. A separate illustrative cross-product of power 750/1000/1400 W,
lid area 9/16/36 cm² and heat fraction 0.7/0.85/1 (all ASSUMPTION) yields
mean-flux extrema/base 14.58/53.13/155.56 W/cm². These are planning
sensitivities, not sourced GPU lid ranges. Carbon's fixed 9-cm² *heated model
footprint* at these powers instead yields 83.33/111.11/155.56 W/cm² when all
heat is assigned there. A peak/mean ratio must come from the characterized
post-spreader map, not a raw die hotspot transplanted onto this interface.

## Recommended candidate points; Test Lead selects

Use points A/B/C in [operating-points.json](operating-points.json) as three
separate, explicitly hypothetical interface-input panels. Central candidate B
has the strongest match to the existing 1000-W public heater example and
Carbon's domain. A tests lower heat and W32-context supply; C tests the
modern 1400-W envelope and warmest currently supported inlet. No point has
a demonstrated feasible or contested design family.

Every point freezes the same 85°C lid-side TIM2 proxy (owner development
selection), areal TIM 5e-6 m²K/W (current source), PG25 model validity
30–99°C, and a single characterized post-spreader map before comparison.
None optimizes inlet, TIM or lid conductivity secretly. Ratio base 1.5,
low/high 1/2 are ASSUMPTION options to characterize, not a sourced map or
new sampling law. Cell pressure allocations low/base/high A=15/20/25,
B=20/25/30, C=25/30/35 kPa are ASSUMPTION, not industry hard limits.

At each base heat and ratio 1.5, TIM-only local increments are mathematically
6.25/8.33/11.67 K for A/B/C. Maximum remaining plate-rise budgets at the same
location are 46.75/36.67/28.33 K = 85−Tin−local TIM increment. These are
necessary thermal budgets, not predicted maxima, feasibility proofs, or
reconstructions of the historical >=117°C results. Spatial maxima and q must
share a location in an actual measurement. Do not double-count lid loss.

Before a future bank: Test Lead freezes the intended plane/map/lid and inputs;
Data Collection verifies all strata without relaxing safety limits, tests the
contested frontier and strongest cached/response-map baseline at equal budget,
and measures cell hydraulic scaling plus end-to-end reference costs. If
lid characterization or feasible frontier remains absent, hold the Challenge.
No new solvers or data partner activity is authorized here.
