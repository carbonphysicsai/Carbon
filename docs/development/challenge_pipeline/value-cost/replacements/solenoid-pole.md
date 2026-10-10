# Axisymmetric solenoid force-stroke design — Cooling-slot candidate 1

**Strongest cheap baseline first:** analytical reluctance circuit, manufacturer
force-stroke catalogue, nonlinear FEM-calibrated RBF/Kriging response surface,
and exact curve lookup. This is not Motor's rotating-machine ticket or a new
cold-plate scope. DEVELOPMENT / SPECIFIED; [common conditions](README.md).

## V1 — buyer's actual question

Buyer role: industrial valve/automation actuator engineer choosing pole shape,
air gap and coil geometry to meet a prescribed force envelope throughout a
stroke without exceeding winding current/power constraints. Objective: least
copper loss among feasible profiles, not maximum force at one convenient gap.

[Magnet-Schultz](https://www.magnet-schultz.com/en/products) describes its
application-specific electromagnetic development with simulation/calculation.
[Vogel and Ulm (2011), Heilbronn University](https://www.comsol.de/paper/theory-of-proportional-solenoids-and-magnetic-force-calculation-using-comsol-multiphysics-11391)
independently compare pole-geometry force-stroke shaping using reluctance and
COMSOL FE models. These sources establish the exact design step and a strong
mechanistic comparator, not Carbon's demand, adequacy or commercial savings.

## V2 / V3 — transparent sensitivity

ASSUMPTION low/base/high: 3 / 8 / 20 engineer-h per actuator revision at
60 / 90 / 120 EUR/h = **180 / 720 / 2,400 EUR** gross effort. Conditional cohort
5 / 20 / 50 teams × 6 / 24 / 60 revised profiles/team/year =
**30 / 480 / 3,000 exact decisions/year**. Manufacturer customization and the
design study support repeatability, not a sourced annual cadence. Count a
changed force-stroke/application brief, not every valve built or commanded.
Buyer logs must confirm frequency and useful time saved. Wrong choices consume
another design/verification iteration; no catastrophic valve failure value is
invented. Realized benefit floor zero.

## Bounded reference and what is given up

Propose an axisymmetric DC force-curve family with pole taper/gap/coil actions,
under three explicitly supplied material/winding-temperature conditions.
Keep full current/stroke force and flux/saturation outputs. Buyer force floor,
power/temperature/current limits, B-H laws and P/Q/w remain HUMAN_INPUT; winding
temperature is a stated operating input, not a thermal limit magically proven
by a magnetic solve. Resistance/loss calculation must use the stated temperature.
No safety constraint is relaxed. Dynamics, eddy currents, hysteresis/remanence,
3D leakage, spring/valve dynamics and field lifetime are excluded. Buyer still
performs final coupled qualification; applicability may be too narrow for them.

Open route: [GetDP](https://www.getdp.info/) nonlinear axisymmetric magnetostatics
with Gmsh, virtual-work force versus an independently checked stress-tensor
observer. Official source supports axisymmetry and GPL distribution; exact
image/source/mesher/B-H/deck pins are pending acquisition-owner approval, not
an inherited Motor reference. Match COMSOL/Maxwell buyer-tool decks; target
Tier 2 in this DC step only, earned tier NOT_DEMONSTRATED.

## C1 / C2 hypothesis

One complete case = one geometry/condition's **9 stroke × 3 current** magnetostatic
systems, meshing and force/loss extraction. 27 systems are not 27 buyer decisions;
do not quote a single-system timing as curve C1. Hypothesis CPU-h
0.01 / 0.04 / 0.12 (0.6 / 2.4 / 7.2 CPU-min), RAM 0.5 / 2 / 6 GiB.
24 × 3 = 72 primary curves, 24 twice-cost refined curves, 15 failed attempts,
8 two-tool witness pairs: 151 equivalents. C2 **18.98 / 26.37 / 46.06 EUR**
in [the sheet](scenarios.json), not measured p50/p95 or permission to dispatch.

## Why first — and why it may still fail

Hypothesis: fringing/saturation changes the force envelope and least-loss pick
as pole geometry changes, beyond an uncalibrated circuit. Carbon must also beat
the **calibrated** ordinary response surface on whole-geometry witnesses.
Reject if that baseline already meets quality/latency, if actual applications
need 3D/hysteretic dynamics, or if material uncertainty dominates. Ranked first
for the vacant slot for bounded 2D cost and a full-curve decision, not because
it has demonstrated V4. Owner must explicitly accept the physics change.
