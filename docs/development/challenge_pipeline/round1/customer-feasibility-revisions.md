# Customer feasibility follow-up: Motor, Cooling and Battery

**Basis:** owner's revised Test Lead follow-ups, 2026-10-07, under
CUSTOMER-FEASIBILITY-02. Companion to the [first-three packets at #752's
authored head](https://github.com/carbonphysicsai/Carbon/tree/8f12c8c377bd0eb5190d98bafffcc0a8b16ab72d/docs/development/challenge_pipeline/round1).
These are prospective mock-customer DEVELOPMENT proposals, not new runtime
limits, a promise that a feasible solution exists, or scientific qualification.
The reported solved-point counts and temperatures are supplied by Test Lead
through the owner; this ticket has not recomputed their retained references.
Earlier packets/results retain their meaning. New design spaces need versioned
domain contracts and demonstrated reference adequacy before reliance.

## Motor: preserve the precision joint, change the magnetic design actions

The buyer still needs 6 N·m holding, energized peak-to-peak ripple ≤5% **and**
≤0.30 N·m at the holding command, and unpowered cogging ≤0.05 N·m peak-to-peak.
12 N·m short-peak service remains a separate demand, not a continuous thermal
rating inferred from a static curve. Test Lead reports no pass in 246 solved
public points, best ripple 8%, and cogging 0.4–2.8 N·m. That establishes no
observed pass, not mathematical infeasibility of every possible geometry.
Do not substitute the old TRAIN medians or a looser precision buyer.

First proposed grammar, still using the present 92-mm stator diameter and
35-mm active stack as packaging controls:

| Action | Proposed first range | Reason and required check |
| --- | --- | --- |
| Topology/winding | Retain 8p/24s control; add **10p/12s, three-phase double-layer tooth winding** | q=0.4 rather than q=1; explicit tooth/phase/sign/turn table and winding-factor check required, not merely changing two integers |
| Stack skew | Three equal-length slices; total span 0°, 2° or 4°; offsets −span/2, 0, +span/2 | 10p/12s ideal cogging order lcm(10,12)=60 gives a 6° period; offsets −2°,0,+2° target that fundamental |
| Magnet coverage | 0.65–0.95 of mechanical pole pitch | Give cogging/harmonic shaping a design action; magnetic saturation and mean torque remain constraints |
| Magnet thickness / gap | Retain 1.5–4.0 mm / 0.3–1.0 mm as initial bounds | Isolate topology effects before buying a larger joint envelope |
| Tooth/slot geometry | Tooth width 0.20–0.40 of local bore slot pitch; slot-opening 0.03–0.12 of pitch | New normalized variables, not the old 24-slot tooth widths blindly copied into 12 slots; require positive slot/yoke/clearance and manufacturable winding area |
| Edge shaping, second tier | Magnet-edge chamfer 0/5/10% of magnet thickness; alternatively one symmetric tooth-tip notch family | Only after the winding/skew baseline; freeze exact CAD notch/chamfer grammar before solving, not an unrestricted topology search |

Control the package envelope, material law, allowed copper current-density
bound and slot-fill limit. Measure/report or separately constrain copper loss,
end-turn copper and magnet volume; equal current density/fill does not make
those quantities equal across topologies. An iso-loss sensitivity comparison
is a separate declared comparison, not an implied equality. Recalculate
coil area/turns/current per topology; do not inherit 104 turns and treat
identical current as identical thermal or copper use. Slot fill, end turns,
insulation, yoke bridges and magnet-retention details require a prospective
manufacturing contract. A 2D pass is only a magnetic shortlist.

For **loaded** multi-slice torque, all slices share the same physical phase
currents and global rotor command. Do not independently retime each slice's
commutation angle to manufacture cancellation. For this proposed reuse route,
each 2D slice returns **full-35-mm-stack-equivalent torque** (the current deck's
length normalization), then average the three torque curves with weights 1/3.
If a future deck instead solves actual 35/3-mm slices, sum their torques
unweighted; never apply 1/3 twice. Retain each slice and the combined curve;
compute ripple from that curve, not averaged ripple scalars. Sample the complete
rotation first and prove winding/load periodicity before reducing it. The old
15°/60-angle assumption cannot be carried over to a new topology. Refine angle,
air gap and mesh until cogging and energized maxima meet the packet's numerical
criteria. End leakage, skew edges and axial effects need selected 3D witnesses.

Verification order: old control → unskewed 10p/12s → three skew spans → selected
magnet coverage/shaping → independently refined zero-current and loaded curves.
Reject if mean torque is sacrificed or the absolute ripple/cogging limits fail.
If no resolved pass remains, report NO_VERIFIED_FEASIBLE_DESIGN and ask whether
the buyer buys a larger motor or a different joint architecture; do not quietly
relax precision. The [IET primary study](https://ietresearch.onlinelibrary.wiley.com/doi/full/10.1049/elp2.12367)
supports investigating 10p/12s segmented skew and warns that edge effects
disturb ideal cancellation; its larger motor is not evidence that ours passes.

## Cooling: improve the ideal cell before composing a full plate

Keep ≤85 °C **local die-side TIM-interface estimate**, ≤50 kPa across the
full plate and bounded inlet/outlet manifolds, and ≤2.5 W hydraulic power at
≤3 L/min. These are the buyer's warm-inlet/high-load constraints, not the old
periodic-cell examples. A manifold model cannot repair an already-too-hot
ideal cell merely by assigning perfect flow again.

At the reported 45 °C inlet, 89→85 °C needs a 44→40-K rise reduction:
**9.1% less total thermal resistance** at fixed 1500 W. Reported hot spots
97–115 °C imply approximately **23–43%** less local temperature rise at that
same inlet, so a nominal-only improvement is insufficient. These are algebra
on reported temperatures, not new solves. Reconfirm that the 89/97–115 values
use the packet's local-flux/TIM observer before comparing them directly.

First proposed straight-channel grammar: width 0.2–1.0 mm, fin thickness
0.2–0.5 mm, depth **3–6 mm**, base **0.5–1.0 mm**, retained 0.5-mm lid and
30×30-mm heated footprint. The largest channel/base/lid combination is
7.5 mm thick: explicitly a new mock package allowance. Increase wetted area
and test smaller pitch; do not assume narrower is always better. Retain PG25
material validity and examine Reynolds/entrance/regime support anew for each
case rather than silently applying the old qualified geometry range.

Thinning the copper base is an action, not a guaranteed hot-spot fix. A uniform
1D cross-plane estimate with k=391 W/(m·K) says 1→0.5 mm saves only
1500×0.0005/(391×0.03²)=**2.13 °C**. It also reduces lateral heat spreading;
hot-spot cases can worsen. Compare thickness/depth jointly and retain a
solid-temperature field. Local TIM jump uses local heat flux, not mean flux.

If that grammar has no resolved pass, second tier: staggered pin fins with
diameter 0.3/0.5/0.8 mm, pitch/diameter 1.5/2/3, height 3/4.5/6 mm and minimum
clear gap 0.2 mm; reject invalid combinations. This needs its own periodic-cell
grammar/reference, not a relabelled straight-channel result. Other escalation
is split-feed/parallel zones to shorten flow paths and target hot spots, under
a newly frozen manifold/network geometry. No extra pump flow or free pressure.
The [MIT Lincoln Laboratory primary work](https://archive.ll.mit.edu/publications/journal/pdf/vol01_no1/1.1.3.microchannelheatsinks.pdf)
motivates coupled channel/base/spreading design, not any predicted pass here.

**Option A is acceptable in principle to this buyer** if Carbon owns the
manifold flow network **and** thermal coupling: distribution, inlet/outlet
losses, full 1500-W heat balance, edge area, nonuniform loads and lateral solid
spreading. A bank of isolated perfect-flow cells is insufficient. Integer
channel layout and residual edge area must be explicit; do not drop heat on
the unused edge remainder of a floored periodic tiling.

Proposed end-to-end DEVELOPMENT composition error budgets against full-plate
truth: ≤1 °C local peak TIM estimate; ≤5% relative total Δp and hydraulic power
at nonzero flow. These are aggregate budgets, not 1 °C independently allowed
for every component. Include discretization/observer uncertainty. With a
demonstrated conservative absolute temperature error ≤1 °C and relative pressure/
power error measured against truth ≤5%, provisional shortlist guards are
84 °C, 47.5 kPa and 2.375 W; they do not certify safety. Eight references can
test this small development panel, not bound error over the whole design law.
Include nominal/high load, inlet-temperature extremes, central and displaced
hot spots, reduced supply/maldistribution, and pressure-boundary designs.
Freeze exact cases before reference access; keep them public DEVELOPMENT only.

## Battery: keep the complete-programme ceiling; add cooling as an action

**(a) Yes, under this packet:** its 45-°C requirement explicitly applies to
the complete declared 30-cycle programme, including discharge/rest. Keep it
in this round. Removing a hot discharge after observing it would change the
tested claim, not demonstrate that the prior demand was met. The driver buys
a 10–80% session; a standardized 1-C laboratory discharge is a different
measurement context. Report both, rather than confusing a discharge maximum
with a charging maximum. A future charge-session-only buyer contract is
possible, but would need an explicit separately bounded discharge/ageing
policy and cannot rescore the present packet or EV5.

Require per-cycle/phase extrema (charge, CV, rest, discharge), overall extrema
and their phase/cycle/time identity, all-charge local plating minima, capacity
checkpoints and first-session 80%-SOC crossing including the 120-s rest.
Save or stream all 30 cycles' reductions; checkpoint-only saved traces cannot
establish whole-programme extrema. Record NOT_REACHED rather than clipping
the SOC clock. Retain/reproduce the reported 35.6-min best using the new explicit
10–80% observer; a voltage-termination time alone would not establish that SOC
interval. This is an observer requirement, not a claim that Test Lead used the
wrong interval.

**(b) 30 min at 35 °C is a thermally managed target, not a promise for the
present fixed-cooling cell.** Keep 45 °C, model plating ≥0 V, voltage ≤4.2 V
and Q30/Q1≥0.99. First new action is effective cooling conductance: multiplier
**1, 2 or 4** of the pinned reference h, with the same fixed cell area/volume
and environment at the declared ambient (25 or 35 °C for the speed goal).
Use that same cooling action throughout charge/rest/discharge so the bench
cannot receive hidden extra cooling. These multipliers are synthetic
sensitivity/prototype choices, not measured cooling hardware capability.
Report the resulting hA, cooling heat-removal peak/energy and phase maxima.

The current code varies ambient/initial temperature, not h. Therefore add this
under a new action/version; no existing input silently changes meaning. The
[official PyBaMM thermal model](https://docs.pybamm.org/en/pybamm-v26.9.0.0/source/examples/notebooks/models/thermal-models.html)
shows the hA(T−T_environment) cooling term. Documentation supports the model
mechanism, not this pinned simulated cell's thermal adequacy or a real EV pack.
No free subambient bath, unlimited chiller, preconditioning or heat-removal
actuator is introduced. Mapping hA to cooler mass, power and hardware limits
is NOT_DEMONSTRATED; a cooled-cell screening result must not claim those costs.

Keep c1≤2 C and the original c2 range first. Freeze a small prospective set
covering the old fastest/safe controls and near misses at 25/35 °C, then cross
the same set with the three cooling actions. Recheck cold/hot service strata
before recommending one protocol. If cooled cases still miss time, next tier
is c2=0.5–2 C with c2≤c1 and switch voltage 4.00/4.05/4.10/4.15 V under the
same 4.2-V ceiling. This is another versioned design action, not extra current
hidden in the old protocol. Revalidate every mandatory condition; plating and
ageing may bind in the expanded space even if they did not bind previously.

For the explicitly assumed equal SOC/rate-capacity basis, 0.7/2 hours +2-min
rest is a **23-min lower bound**, so 30 min is not excluded by that simple
current-time arithmetic. Taper, voltage, thermal and ageing constraints can
still make it infeasible. A 35.6-min observed best is honest evidence of the
current space, not grounds for a feasible-solution guarantee. If neither
bounded cooling nor staged-current extensions produce a resolved pass, retain
NO_VERIFIED_FEASIBLE_PROTOCOL; a slower warm-temperature service promise is a
new explicit buyer scope, never a silently relaxed test.

## Engineering handoff and cost evidence

These proposals preserve the customer problem; Test Lead/Carbon Validator
own versioned gates/observations. Domain engineering owns the new geometry,
winding, thermal actions and reference controls. No hidden batch, scorer,
validator registry or capacity machinery is duplicated here. Battery EV5,
sealed journal sequence 14 and live contract remain unchanged.

The [30-case cost-panel guide](feasibility-panels.md) and offline generator
provide the requested f02/f08/f13 definitions. Costs remain NOT_RUN/null.
No paid or counted/fresh campaign ran, no deployment queue moved, and no
feasible yield, production safety or customer savings have been established.
