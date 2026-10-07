# Three 30-case full-task cost panels — definitions, not measured timings

**Ticket:** CHALLENGE-CUSTOMER-FEASIBILITY-02. **Status:** recipes prepared;
all 90 result slots NOT_RUN/null. Elmer/CalculiX domain decks, build/image,
mesher, extractor, hardware and launch-accounting pins are absent. No solver
was installed or dispatched and no paid cost or capacity measurement occurred.
The [Foundation Plan §3](../../../../Design_Specs/Eight_Challenge_Foundation_Plan.md)
requests geometry-aware reference verification and full-task p50/p95 costs.
An analytical screen or a sparse-frequency solve cannot supply those timings.

## Reproduce the definitions

From the repository root, the stdout-only generator takes a Challenge planning
label. These are public DEVELOPMENT recipes, never operator hidden draws:

```text
python scripts/dev/customer_feasibility_panels.py f02
python scripts/dev/customer_feasibility_panels.py f08
python scripts/dev/customer_feasibility_panels.py f13
```

Each output contains the numeric sheet digest, common material/geometry/range
and allowance facts, per-case inputs/digest, a panel-definition digest, null
required solver pins and measured-cost slots. The digest is a public recipe
identity, not an official reference pin, custody proof or execution grant.
This guide and each source packet complete the CAD/load/observer definition;
the output is **not** a solver-ready deck. Freeze generator version, source
sheet, guide/packet blobs and emitted panel before reference access.

| Challenge | Exactly 30 complete tasks | Required output, not a cheaper proxy |
| --- | --- | --- |
| f02 burst thermal | 24 strata at 110 W/10 s + six warm boundary probes | Full 120-s spatial transient, event/peak/crossing search and temperature grid |
| f08 structures | Ten whole valid geometries × three damping conditions | Static, eigen and complete adaptive 80–600-Hz complex harmonic curves |
| f13 silencers | 27 fixed stratified geometries + three low/nominal/high boundary recipes | Complete 500–2500-Hz complex transfer/TL curve per geometry, initially 201 frequencies then refinement |

These are diagnostic Q panels, not a random deployment-P sample or official
confirmation. f08 has **ten** independent geometry units, not thirty; damping
conditions are repeated within a geometry. f13 frequencies are one response
task, not hundreds of independent cases. Describe these units when reporting
cost summaries; do not claim population uncertainty from this small panel.

## f02: retain the already specified 30-case panel

Use the [burst packet](f02-burst-thermal.md) and [numeric sheet](requirements.json):
centered 20×20×0.5-mm silicon, 20×20×0.2-mm TIM, 30×30×2-mm copper, synthetic
material laws, two 8×8-mm top patches centered x=−5/+5 mm/y=0, insulated exposed
surfaces and full-underside Robin cooling. The emitted cooling/T0/source split
and waveform rows fully specify this diagnostic task. Larger power share is
on the left patch. Linear ramp and half-duration/gap pulse events are retained.
Each segment is [start s,end s,power at start W,power at end W]; discontinuities
use the next segment's value after the event, without interpolating across it.

The 24 rows cover both atomic cooling pairs, both initial temperatures, both
power splits and three waveform families. Six extra rows use warm cooling,
55 °C, 80:20 split: low 80 W/5 s and the existing preregistered RC-selected
probe for each waveform. The RC probe selections are not reference labels.
Observers: 0:0.5:120-s grid plus all events, patch centers, top-die spatial peak,
internal temporal peak/crossing search and recovery to the 20-W steady baseline.
Record four shared steady-baseline costs explicitly and report amortized and
unamortized case costs; failed baselines leave recovery unresolved.

Current allowance: 30 primary +4 controls +12 independent boundary refinements
+4 steady baselines =50 launches, ≤6 node-hours, ≤$20, 16 vCPU/24 GiB, no retry.
Keep the packet's equilibrium/slab/energy controls and mesh/time refinement.
Whole-programme accounting, not only primary solve time, must fit those caps.

## f08: thirty whole response tasks, not the old six diagnostics

Use the [structure packet](f08-resonance-structure.md) for the clamped ribbed
plate, 3-mm rounded centered relief, force pad, synthetic material, probe
coordinates and exp(+iωt) output convention. The generator fixes ten geometry
tuples (length,width,plate thickness,rib height,rib thickness,relief length),
all in mm. Each appears at damping 0.005,0.01,0.02. Minimum sampled width is
70 mm; the 60-mm lower bound would leave less than a 6-mm ligament between
the centered relief and these ribs, so it is not silently repaired/clipped.
Geometry identity is independent of damping; shared factors are valid only
with exact same CAD/material/clamp/mesh identity and recorded reuse.

Begin a 2-Hz grid over 80–600 Hz, bracket each in-band mode and refine to ≤one
tenth of half-power bandwidth before a peak claim. Retain static displacement,
mass, eigenfrequencies, both complex response probes, full adaptive frequency
grid and band maximum/location. Repeat 12/24/48-mode and mesh/grid comparisons
on packet controls; a primary coarse case is not an adequacy receipt.

The **existing** grant is only 36 launches/12 node-hours/$30 for six diagnostics
with controls/refinement. Under its separately launched static/eigen/harmonic
strategy, thirty unshared primary tasks use 90 launches; sharing static/eigen
once per geometry still uses 10+10+30=50, before controls/refinement. A verified
combined/batched deck could change that accounting, but is NOT_IMPLEMENTED.
Do not claim 36 funds this new complete panel or transfer another family's
allowance. First implement and measure a pinned full-task control; price the
remaining panel using actual launch topology and resource enforcement.

## f13: thirty complete band curves, not ninety sparse points

Use the [silencer packet](f13-compressor-silencer.md): rigid 3D two chambers,
50-mm-ID coaxial inlet/outlet, radius-20-mm inter-chamber neck and its lateral
offset, two fixed 10-mm port stubs, air rho=1.2 kg/m³/c=343 m/s, unit incident
plane-wave power and matched outlet. Grammar validation requires ≤300-mm total
length, ≤140-mm diameter and neck radius+offset+10-mm clearance ≤both chamber
radii. The 27 midpoint-stratified geometry rows use fixed coprime permutations
in each coordinate, followed by lower/mid/upper diagonal rows. No clipping,
hidden random seed or outcome-dependent geometry selection.

Each task includes 201 initial frequencies (500:10:2500 Hz), adaptive resonance
and quadrature refinement, complex R/T, incident/reflected/transmitted power,
energy residual and the interval-weighted p10/mean/minimum TL. Grid refinement
cannot overweight a resonance by counting nodes equally. A curve must satisfy
mesh and quadrature checks; report failure/unresolved evidence rather than
favorable p10 from a few points.

The **existing** grant is sparse preflight:40 launches/8 node-hours/$25. With
one process per frequency, thirty primary curves alone require **6,030 launches**
before controls/refinement. A verified multi-frequency Elmer deck could reduce
process count, but its full internal work and charged failures still count.
No such pinned deck or measured timing is present. The old grant cannot be
relabelled as a funded 30-curve measurement programme.

## Cost ledger and capacity interpretation

Use the existing neutral capacity/compute owners, not another framework.
For every attempted case retain phase timings (CAD/mesh/setup/reference/
extraction), exit/failure type, process CPU user+system including descendants,
allocation start/stop, peak memory, actual thread count, charged launches,
image/deck/mesh/extractor/hardware pins and artifact identities. Keep cold
startup and shared-factorization time separate and report their allocation.
Retain failed/OOM/timed-out attempts and their costs; don't drop expensive
failures or relabel infrastructure failure as scientific infeasibility.

- **Consumed CPU-hours:** sum actual user+system CPU seconds over the complete
  task/process tree /3600. This is not the wall clock multiplied by a guessed
  thread count.
- **Allocated vCPU-hours:** allocated vCPU count ×actual charged allocation
  wall-hours, including startup/idle/failed work. A 16-vCPU node occupies
  16 allocated vCPU-hours per node-hour even if solver parallelism is poor.
- **End-to-end latency:** setup/mesh/solve/extraction wall time, plus explicitly
  reported startup/shared overhead. Solver-only time is insufficient for sizing.

Report full-panel p50/p95, max, success/unresolved/failure counts and aggregate
charged costs **after** execution. Include empirical-quantile convention and
sample count; failure timings stay in a separate retained ledger and total
cost, not silently excluded. No numeric CPU-hour estimate is reported here.
Sizing all eight concurrently also needs arrival rate, latency/queue objective,
memory peaks and measured thread scaling; eight concurrent cases is not eight
reserved 16-vCPU nodes by assumption.

Existing five-family total remains $160/46 node-hours/736 allocated vCPU-hours/
202 charged launches, non-transferable, one 16-vCPU allocation and one solver
process at a time, no GPU/automatic retries. These are feasibility ceilings,
not a ready runner or counted/fresh grant. Require exact pins, retained ledger,
quote/capacity and resource/spend enforcement within those caps, plus existing
stage authority before paid dispatch. New full-panel requirements do not expand
the caps. Battery-led protocol remains DEFINING; no runtime ID/queue transition.
