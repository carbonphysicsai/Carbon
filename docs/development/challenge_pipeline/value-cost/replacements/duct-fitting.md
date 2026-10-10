# Space-constrained duct turning-vane design — Cooling-slot candidate 2

**Strongest cheap baseline first:** ASHRAE fitting-loss database plus network
pressure calculation, manufacturer data and a geometry/Reynolds response
surface. A standard catalogue elbow is already a lookup problem. DEVELOPMENT /
SPECIFIED; [common rules](README.md), no full cold plate or HVAC certification.

## V1 — exact buyer decision, two sources

Buyer role: HVAC/mechanical-services design engineer choosing an elbow/turning-
vane layout in a fixed clearance to meet design airflow within available fan
total-pressure head. Reduce loss without inventing a new fan or shrinking
required airflow. Scope is one compact fitting, not an entire building CFD job.

[ASHRAE's database](https://www.ashrae.org/technical-resources/bookstore/duct-fitting-database)
turns fitting geometry and airflow into pressure loss with over 200 fitting
types; that is both workflow evidence and the incumbent. Independently,
[Moujaes and Aekula (2009)](https://doi.org/10.1061/%28ASCE%290733-9402%282009%29135%3A4%28119%29)
compare CFD/experiment for elbows with/without turning vanes. This supports
investigating geometry-sensitive losses, not claiming standard tables fail on
Carbon's proposed fittings or that OpenFOAM has matched those experiments.

## V2 / V3 — modest, explicit buyer-unit scenarios

ASSUMPTION effort 1 / 3 / 8 engineer-h at 60 / 90 / 120 EUR/h:
**60 / 270 / 960 EUR per layout revision** gross effort at stake.
ASSUMPTION 5 / 20 / 50 teams × 4 / 12 / 30 qualifying layout revisions/year:
**20 / 240 / 1,500 decisions/year**. Not every fitting installed or shipped.
Sources establish the workflow, not annual custom-fitting counts. Request
project logs proving how often a nonstandard fitting actually requires CFD.
Actual incremental benefit may be zero; avoid turning a whole HVAC TAM into V3.

Separate energy illustration, **not added** to effort value: assumed flow
0.3 / 1 / 2 m3/s, avoided loss 10 / 30 / 60 Pa, total fan efficiency
0.65 / 0.60 / 0.55 and operation 2,000 / 4,000 / 6,000 h/year gives about
**9.2 / 200 / 1,309 kWh/year** per affected airpath via Q × delta-p / eta.
That saving is neither demonstrated nor solely Carbon-attributable; the cheap
database optimizer may already obtain it. Do not monetize occupant comfort,
fire safety or regulatory acceptance from this local calculation.

## Task, open route and fidelity

Propose a supported family of shortened elbows with vane position/curvature/
spacing actions over three stated airflow/inlet-profile conditions. Observe
total-pressure loss, outlet flow distribution and mass balance using registered
planes. Pressure/airflow requirements and material/roughness/turbulence support,
P/Q/w remain HUMAN_INPUT; no requirement is relaxed for feasibility. Exclude
acoustics, building controls, smoke/explosion ventilation and unsteady fan stall.

Open route: [OpenFOAM Foundation](https://openfoam.org/download/) GPL steady
incompressible RANS with explicit inlet turbulence, wall treatment and bounded
mesh. Acquisition owner must pin fork/release/source/image/mesher/deck/planes.
Match a buyer Fluent/STAR-CCM+ deck and public elbow benchmark separately;
mesh convergence alone does not fix turbulence-model error. Tier 2 target
only; Tier 3 laboratory claim not earned.

## C1 / C2 and rejection

Complete case = one geometry/flow/profile solve with meshing, convergence and
pressure-plane extraction. Hypothesis CPU-h 0.05 / 0.15 / 0.33 (3 / 9 / 19.8
CPU-min), RAM 1 / 4 / 12 GiB. 24 × 3 = 72 primary, 24 twice-cost refined,
15 failures, 8 two-tool witness pairs => 151 equivalents. C2
**28.83 / 53.45 / 97.76 EUR**, [conditional](scenarios.json), barely within
high-scenario cap; failed convergence/witness pricing could overturn it.

Plausible utility is a real shortened/nonstandard layout whose separation or
inlet profile changes the pick; give calibrated correlations/RBF the same data.
Reject if standard tables already decide it, if many geometries require URANS,
or if Tier 2/refinement cannot fit the bill. Second overall for Cooling's slot;
first if the owner requires a fluid/thermal replacement rather than solenoid.
