# Cooling cell readiness build — launch #4 preparation

DEVELOPMENT / SPECIFIED, with toy-tested preparation code. No solver execution,
spend, hidden/AX42 data, full cold plate, earned Tier 2 or new runtime identity.

The buyer still chooses an **interior cell geometry and supported flow** under
**frozen buyer service maps**. Temperature means **lid-side TIM2 case plane**,
`max_x(T_plate_face(x) + R_TIM2*q_interface(x)) <=85 C`, not die/TIM1 or a mean
TIM rise added to an unrelated field maximum. See [cell v3](../round1/cooling-cell-v3.md)
and [baseline](../cheap-baselines/cooling-cell.md).

## Inputs and owners

The Test Lead's owner-relayed selection is now **point B** from
[#1084](https://github.com/carbonphysicsai/Carbon/pull/1084): actual cell inlet
40 °C, interface heat 1000 W, total footprint flow 1.50 L/min, and 25 kPa cell
allocation. These are DECIDED_DEVELOPMENT **REPRESENTATIVE** settings, not
vendor-qualified GPU conditions. Every value and its basis is in #1084's
`operating-points.json`, point B. `bind_operating_point` freezes these in a
complete supplied registration and fixes the flow action to 1.5 L/min/kW;
the remaining geometry coordinates stay actions. P/Q/w and the objective
are not silently selected.
The supplied map/material registration must already cover the selected inlet
and heat; the binder refuses to relabel an old-condition map as point-B truth.

Point C from the same [source](https://github.com/carbonphysicsai/Carbon/pull/1084)
(45 °C, 1400 W, 2.80 L/min, 30 kPa) is **optional stress only**, off by default.
It needs Data Collection's retained public NEEDS_OPTIONAL_STRESS_C value-check
finding and source digest. It is a separate panel with flow 2 L/min/kW, never
a hidden addition to B's population or sampling law. A documentary finding
does not grant execution or scientific acceptance.

The buyer lid is **REPRESENTATIVE vapor-chamber**: #1084 SOURCE_REVIEW.md,
Boyd datasheet p.2 gives thickness 1–10 mm, typically 3–4 mm. #1084's
2000/5000/10000 W/m/K sensitivity is **ASSUMPTION**, not a characterized law.
No scalar conductivity is installed into the cell renderer. Supply actual
coolant applicability,
characterized vapour-chamber identity, normalized **post-spreader** interface
map and uncertainty, TIM2 resistance, and cell-scale hydraulic allocations and
objective. The old 3 L/min / 50 kPa / 2.5 W assembly constraints are **not** cell
constraints. Inlet/heat/flow/cell allocation are decided; matched lid
characterization, post-spreader map and uncertainty remain HOLD.

[Registration template](registration-template.json) deliberately contains null
HUMAN_INPUT fields and cannot pass the generator. Test Lead/Data Collection
populate and seal it using `cooling_readiness.seal`; fixture numbers live only
in tests. P, Q and w are separate explicit service masses, not inferred from
one another. Requirement changes do not renew physical bank exposure.

## Reuse and supported scope

KEEP [domain](../../../../carbon/cold_plate/domain.py),
[deck renderer](../../../../carbon/cold_plate/openfoam.py) and reference checks
in [analysis](../../../../carbon/cold_plate/analysis.py). The source pin is
`opencfd/openfoam-default@sha256:33fb575aa9980d2bc42fd58c75ae698c489293ba30c991380fe3f899c622f319`.
This is **not** a present-image receipt or a new-case verification result.

The existing route supports the 30-mm half-channel/half-fin cell, current
width/fin/depth/flow ranges, PG25 inlet 30–45 C and fluid 30–99 C, laminar
Re<=2000, and transverse-uniform axial Gaussian-on-floor maps. Supported
subranges are caller-registered; action lattice steps are not new science.
No improved geometry, water, inlet below 30 C, 2D hotspot or lid material law
is smuggled in. A sourced candidate outside this support needs a new pinned
route and verification before a physical deck can be rendered.

The 0.5-mm solid top cover in the existing **cold-plate** geometry is not the
buyer's vapour-chamber lid. The supplied post-spreader map already represents
that buyer input; no second lid resistance or free spreading is added.

## Offline tools

`carbon.challenge_pipeline.cooling_readiness` exposes:

- `validate`, `actions`, `conditions`: bounded public-seed draws. Service P
  and diagnostic Q are chosen explicitly; w remains the supplied evidence mix.
- `case`, `panel`: exact action/service/rung/pin tuples, deduplication and
  explicit completed/scheduled reuse. Output is PROPOSED_NOT_REGISTERED, not an
  authority claim or run release.
- `deck`: actual supported OpenFOAM inputs rendered **in memory**. No image
  builds, host writes or subprocess calls. UNVERIFIED_DECK_DRAFT.
- `observe`: co-located face q/T/TIM2, patch coverage, retained hydraulic
  scaling and applicability. Numerical + map uncertainty produces an interval;
  crossing 85 C is UNRESOLVED. Report sampled heat vs analytic map integral;
  mesh quadrature/conservation acceptance is still producer/science-owned.
- `train_plan`: excludes the panel's same physical cases regardless of rung,
  renamed service or requirement values. Solver/material/observer changes
  prevent reference reuse; they do not make a test case fresh for TRAIN.
- `kit_domain`: compares exact map identity, plane, coordinates and outputs;
  empty comparisons cannot pass. This hook is not a new training kit.
- `compare`: wraps the existing strongest same-context, held-geometry response
  map, requiring the new case-plane observer and all geometry/flow coordinates.
  Output includes pointwise errors, decision agreement/regret, abstention,
  costs and equal-budget screening cost/rank. Data Collection must supply the
  complete matched public export and companion materials, not legacy scalar
  heated-face peak values relabelled as TIM2 truth.

Use the functions with an explicitly scoped, sealed public registration. No
hidden store, public seed service, paid runner or runtime adapter is activated.

## Verification and cost

[Verification spec](verification.json) separates code verification, convergence
and conservation. Exact Poiseuille/conduction and manufactured heat-source
fields are available; solver source injection, actual runs and acceptance are
still required. Old rungs are useful evidence within their original contracts,
not proof for new maps/TIM2 observables.

`carbon.design_search.cooling_budget.proposal()` returns the digest-bound
#1047-form ASSUMPTION cap (half/base/double), validated by its own additive
family validator. `equal_budget.compare(..., registration=proposal)` uses the
same accounting for direct/model/cheap arms. Historical EQUAL-BUDGET-V1 remains
closed to its original four families. Counting a solver evaluation means a
**complete service panel for an action**, not one cheap condition while omitting
the others. Screening, fits, failed attempts and final retained verification
all consume the same cap. This proposal is not an accepted buyer budget.

[Pilot proposal](measurement-pilot.json): <=EUR10 all-in, sequential two-core
CPU; four standard tuples and two paired refinement tuples if they fit. These
are hypotheses, not measured cost or a grant. Actual quote, overhead, package
presence, pins, frozen map/limits, registration, MMS and stage permission still
precede any attempt. A truncated panel is reported, never redrawn as success.
It measures timing/memory/numerical closure; six cases cannot establish T2(a).

## Seven-item return

| Item | Preparation here | What still earns YES | Owner |
| --- | --- | --- | --- |
| 1 Panel | exact tuple/dedup/reuse generator | main registration plus complete retained/scheduled receipts and final pins | Data Collection/Test Lead |
| 2 Package | existing source-pinned OpenFOAM deck | current same-image operator-store observation | Data Collection/operator |
| 3 Reference | analytic/MMS spec and old-rung reuse map | new matched image/family code, convergence and conservation results with acceptance | Data Collection/science |
| 4 Kit | domain-coverage hook | real kit covers frozen geometry/flow/map/observer panel | Model Kits |
| 5 TRAIN | disjoint proposal generator | public registered solved TRAIN inventory | Data Collection |
| 6 Comparator | response maps and TIM2 wrapper | implementation on main; complete matched materials still needed for V4 | Packets/Data Collection |
| 7 Equal budget | additive validator and replay dispatch | implementation on main; measured comparison still pending | Optimizer/Data Collection |

Onboarding counts are inspected main evidence, not this table or green fixture
tests. No seven-of-seven claim. Reserved inlet/lid/limit selections remain
closed while independent engineering preparation proceeds.
