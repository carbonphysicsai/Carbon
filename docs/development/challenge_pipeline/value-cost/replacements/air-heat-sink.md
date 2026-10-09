# Compact forced-air heat-sink/duct-clearance design — Cooling-slot candidate 3

**Strongest cheap baseline first:** manufacturer thermal-resistance/fan maps,
fin correlations, polynomial-chaos/RBF CFD surrogate, and complete-output
lookup. Ordinary surrogates are already industry/research practice, not an
unfairly weak control. DEVELOPMENT / SPECIFIED; [common contract](README.md).

## V1 — recognizable thermal buyer

Buyer role: power-electronics thermal engineer selecting fin spacing/height
and a compact duct/bypass clearance at the fan operating point, to remain
within component-case limits with minimal volume/fan power. This is a small
forced-air module, **not a full liquid cold plate**, vapour-chamber challenge
or a relabelled existing Cooling cell.

[SimScale's heat-sink workflow](https://www.simscale.com/simulations/heat-sink-simulation/)
describes fin/fan/duct/bypass design sweeps. Independently,
[Loukrezis and De Gersem (2022)](https://arxiv.org/abs/2205.08746)
optimize a power-module heat sink using CFD-trained polynomial-chaos ensembles.
Their strong existing surrogate is evidence **against assuming** Carbon speed
advantage. The exact compact fan/clearance support still needs buyer validation;
their model and timing are not transplanted as Carbon reference measurements.

## V2 / V3 — explicit assumptions

Low/base/high effort at stake 1 / 4 / 10 engineer-h, rates
60 / 90 / 120 EUR/h => **60 / 360 / 1,200 EUR per module-layout revision**.
ASSUMPTION cohort 5 / 20 / 50 teams × 6 / 24 / 60 revisions/team/year =>
**30 / 480 / 3,000 decisions/year**. Sources establish repeated configuration
study, not actual cadence or number of addressable teams. Do not count each
electronic product shipped, watt dissipated or CFD iteration as a buyer revision.
Ask for thermal-review logs and comparisons with existing maps. Realized floor
zero; gross effort is not an avoided overtemperature/recall claim or forecast
Carbon savings.

## Bounded task and reference

Geometry actions: plate-fin dimensions and duct clearance; three stated load/
ambient/fan conditions. Solve fan-curve/pressure-loss balance, maximum component
case temperature, contact-conduction field and fan power; not fixed airflow
that ignores a new fin geometry's pressure cost. Temperature/pressure/power
limits, TIM, materials, P/Q/w and equivalent design margins are HUMAN_INPUT.
Preserve manufacturer safety requirements; do not lower the thermal load or
raise allowable temperature just to make designs pass. Exclude full rack,
liquid loops, dust ageing, acoustics and chip-internal thermal qualification.

Open route: [OpenFOAM Foundation](https://openfoam.org/download/) bounded steady
conjugate heat transfer with full local duct/bypass and a stated fan curve.
Pin exact release/fork, source/build/image, solid/fluid mesh, contact law and
observable extraction through acquisition owner; an available Cooling image
does not qualify the new deck. Match buyer Icepak/Fluent/SimScale witness
settings for Tier 2 target; no Tier 3 physical claim. Radiation or unsteady
effects cannot be silently dropped if they change the supported decision.

## C1 / C2 and the likely failure mode

Complete case includes coupled thermal/flow solve, fan operating-point
iteration, meshing and extraction for one geometry/service condition.
CPU-h hypothesis 0.06 / 0.18 / 0.38 (3.6 / 10.8 / 22.8 CPU-min), RAM
2 / 6 / 16 GiB. Illustrative 20 designs × 3 = 60 primary; 20 twice-cost refined;
12 failures; 8 two-tool witness pairs => 128 equivalents. C2
**29.04 / 54.08 / 95.82 EUR** under [the common assumptions](scenarios.json).
Do not treat a modest panel size as adequate T2/power or its high estimate as
a measured p95. More frontier resolution may require repricing/rejection.

Plausible advantage is whole-geometry inference near bypass/fan-operating-point
pick changes. Compare strong polynomial ensembles with retained verification
and equal data; no solver-only victory. Reject if they already settle the
decision, if the buyer uses catalogue maps, or if coupled CFD witness/refinement
tails exceed budget. Third: it preserves an accessible thermal story, but risks
repeating Cooling's V4 issue rather than curing it. Owner decides, not Codex.
