# Solenoid pole — complete force-stroke decision

**PROPOSAL / HUMAN_INPUT bindings / not approved.** Buyer: proportional-actuator
magnetics engineer choosing a pole profile that follows an unchanged force
envelope across stroke and current, inside a fixed package/coil. Not a promise
about switching speed, hysteresis, thermal duty, friction or valve dynamics.
Pole shaping and force extraction are real engineering questions, supported
by [Vogel/Ulm's force-stroke study](https://www.comsol.com/paper/download/83443/vogel_paper.pdf)
and [Magnet-Schultz's actuator technical explanation](https://www.magnet-schultz.com/fileadmin/Daten/Vertrieb/PR1/TechnErl/GXX_e.pdf).
No actual customer force target is inferred from either source.

## Grammar and binding

Fixed axisymmetric, non-PM pot yoke and coaxial translating armature, one
annular homogenized copper coil. Meridional (r,z) polygons revolve about r=0.
Coil topology/turns, armature radius Ra, outer yoke/package, coil window,
return-path dimensions, stroke S, minimum positive gap g0, mechanical clearances,
fillets, drawing tolerance and material B-H(T) table are **HUMAN_INPUT**.
There is no arbitrary copy of the motor's grade, radius or length.

Proposed action coordinates, in this order:

| Coordinate | Proposal support | Exact geometric role |
| --- | --- | --- |
| tip_radius_over_Ra | 0.60–1.00 | pole-face radius Rt = coordinate * Ra |
| nose_length_over_S | 0–0.50 | axial taper length Lt = coordinate * S |
| shoulder_radius_over_Ra | 1.00–1.40 | taper rear radius Rs = coordinate * Ra |
| yoke_web_over_Ra | 0.35–0.75 | return-yoke radial web thickness |

Taper profile is a straight segment from (Rt,zface) to (Rs,zface-Lt), joined
to the fixed rear pole/yoke; use the pinned buyer fillet at joins. At Lt=0
this is a flat shoulder, not division by zero. The translating armature face
is zface+g(s), with g(s)=g0+s. Coil/window topology never moves with a design.
Validate clearances, polygon self-intersections, nonnegative radii, positive
gap at every stroke/probe, no overlap with coil or package, fixed fillets and
all assembly extremes. Reject a row; never clip a coordinate or redraw it.
Supports are diagnostic geometric proposals, not adopted manufacture limits.

[panels.json](panels.json) registers ten uniquely named **proposal** rows
S01–S10 (two flats, tapers and yoke extremes). Absolute realizations are not
registered until the anchor is approved and hashed. Fixed refine/witness IDs
avoid choosing only an attractive observed design; a failure remains in the
return. A later boundary expansion requires a new manifest, not silent edits.

## Conditions, output and force convention

Three mandatory *proposed* strata: nominal approved material/temperature;
hot approved B-H(T)/copper resistance; worst permitted axial assembly-gap
offset. Nominal/hot temperatures, current limit Imax, offset sign/magnitude
and actual worst combination are HUMAN_INPUT. If temperature-dependent B-H
is absent, do not invent it: that material stratum remains unresolved. Gap
tolerance is not transverse eccentricity; eccentricity requires a 3D route.

Each design/stratum case is **nine** strokes s/S=0,1/8,...,1 and **three**
current fractions I/Imax=0.25,0.60,1: **27 nonlinear field states**. These are
Q, not customer prevalence. Source J_phi=NI/Acoil in the meridional coil
cross-section; verify ampere-turns, copper fill and resistance independently.
No extra 2*pi or motor turns/current/RMS factor is applied to J_phi.

New axisymmetric A_phi formulation: Br=-dA_phi/dz, Bz=(1/r)d(r A_phi)/dr;
regularity at the axis and a converged exterior air boundary. GetDP's
VolAxi is a route ingredient, **not proof** that motor's A_z basis/curl has
these semantics. Prove the overall 2*pi*r volume/surface normalization once
with an analytic control; never multiply twice or substitute motor stack L.

Return signed axial force from a closed Maxwell-stress surface entirely in
air around the armature; separately report positive closing force. With s
increasing the gap, Fclosing=-dWco/ds at fixed current. Nonlinear
Wmag=integral_0^B H(b)db and Wco=B*H-Wmag; do not use 0.5*B*H for nonlinear
iron. Also return flux linkage (Wb-turn), secant inductance where I>0,
peak material B, magnetic/coenergy and stated-temperature DC I²R. These
are magnetic/resistive screens, not a solved hot winding or thermal safety.

For six refined cases (S01/S04 in all three strata), repeat all27 at the
finer mesh. At interior s/S=0.25/0.50/0.75 and I=Imax, add displacements
±epsilon and ±epsilon/2: **12 more field states per refined case**, for
virtual-work and displacement-step consistency. epsilon is HUMAN_INPUT;
recommend min(g0,S)/100 as a starting probe, not an accepted tolerance.
All probe geometries must remain valid; no one-sided derivative disguised
as the symmetric check. Remaining24 force points are not independently
virtual-work verified by this subset. Return coverage explicitly.

## Controls, witnesses and acceptance proposals

Four additional complete-control allocations (27 field-state equivalents
each): zero current across strokes; linear-material weak-field I² force/
current-reversal invariance; exterior-domain growth; and air-contour invariance
on a permitted strong-excitation case. Duplicate zero values need not be
resolved repeatedly, but accounting never exceeds/omits the frozen allocation.
If an allocation needs more states, stop and reprice. Test force sign, 2*pi,
stored units, mesh/gap resolution and actual region areas before volume.

Two independent matched witness pairs: S01 nominal and S04 assembly, each
one GetDP case and one independently held COMSOL/buyer-EM case, **four complete
27-point cases** in the conservative budget (reuse is credited only once).
Tier2 target; current earned credibility NOT_DEMONSTRATED. Recommend mesh
force change ≤2% of rated force scale, stress/virtual-work agreement ≤3% and
independent-tool difference ≤max(1% rated scale,3% local force), all HUMAN_INPUT.
An absolute near-zero floor must be approved before zero-current acceptance.
No motor torque tolerance is reused. Near-limit refinement uncertainty must
be tighter than the decision band; Test Lead/science sets the final criterion.

T1 needs a refined force-envelope/current/package/material witness across
all three strata. T2 needs at least five feasible and five near-infeasible
actions per stratum plus buyer-unit force-margin spread and different picks;
the ten seeds may not deliver it. No force target/objective/weight is invented.
Customer upper/lower force-vs-stroke/current tables, preference among passing
designs and acceptable regret in N or envelope units are HUMAN_INPUT.

Baseline first: nonlinear reluctance circuit plus gap/pole-fringing calibration,
manufacturer-map interpolation and cached FE response surface. Hold out whole
geometries; count their setup/data/verification. If these already preserve
force-envelope choices, say V4 fails rather than making the job artificially
more nonlinear. Qualification and dynamic/thermal extensions need new scope.

## Cost and scope of the first panel

30 primary cases +6 refined cases at2x cost +4 controls +4 witness cases
+4 failed-case allocations, plus72 virtual-displacement states at the refined
mesh. Raw maximum **1368 field systems** if every allocation is used, including
buyer-tool states and failed-state equivalents; not1368 independent jobs or
necessarily1368 processes. Cost equivalent U=30+2*6*(27+12)/27+4+4+4=59.3333
coarse complete cases. C1 ranges are the unmeasured #928 hypothesis for a
complete27-point case:0.01/0.04/0.12 CPU-h; no measured p50/p95. RAM0.5/2/6GiB
is likewise a hypothesis, not capacity evidence. The high bill is EUR19.87
under the [conditional budget](README.md); very little tail/overhead headroom.
No witness licence, extra states or missed output is silently free.

First solve controls and S01 nominal, then fixed remaining cases only under a
separately approved ledger/reservation/timeout policy. If the package lacks
axisymmetric force, valid B-H/coenergy or actual customer limits, the panel
does not start. There is no granted EUR20, feasible design or full bank today.
