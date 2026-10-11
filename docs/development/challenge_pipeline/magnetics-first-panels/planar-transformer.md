# Planar transformer — magnetic layout screen, not converter certification

**PROPOSAL / HUMAN_INPUT bindings / not approved.** Buyer: converter magnetics
engineer choosing layer order/separation and gap placement to meet a fixed
inductance/leakage/flux window. Such equivalent-circuit extraction is an
industry design step, but capacitance and conductive loss require separate
physics. [COMSOL's transformer extraction example](https://www.comsol.com/blogs/computing-transformer-equivalent-circuit-parameters).
Planar geometry sensitivity is independently studied in
[the #928 planar FE source](https://www.mdpi.com/2673-4591/150/1/86).
Neither establishes Carbon's actual customer's limits or savings.

## Grammar and ten proposed actions

One approved rectangular E/E ferrite core pair, mirrored windings in its two
windows, fixed four physical copper layers, fixed primary/secondary turns and
copper thickness/trace fill. Coordinates for the fixed core/CAD template,
depth D, window width/height H, leg sections, winding span, insulation/creepage,
fillets, manufacturing tolerances and ferrite B-H(T) data are HUMAN_INPUT.
A winding layer's cross-sections in the two windows carry opposite source
signs for its closed turn. Np/Ns and layer turns/polarity are pinned; no
integer turns or current factor is inferred from motor's winding table.

Proposed action order: layer_order; equivalent_gap_over_H (0.005–0.020);
center_gap_fraction (0–1); adjacent_layer_pitch_over_H (0.12–0.20);
stack_offset_over_H (-0.10–0.10). Orders are PPSS, PSSP, PSPS; two P/two S
layers preserve winding count, not three different circuits. Uniform layer
center pitch is p*H; whole stack translates by offset*H. Copper/insulator
thicknesses are fixed. Reject a stack exceeding the approved window/clearance;
never compress its insulation to fit.

For the fixed symmetric core with total return-leg area equal to the center
leg area, use central physical gap eta*g and **each** return-leg gap (1-eta)*g,
where g=gap_coordinate*H. This preserves the linear unfringed equivalent
reluctance, not actual fringing/saturation equivalence. If areas differ, pin
a derived area-weighted mapping before runs; do not use this formula blindly.
At eta0/1 a zero gap on that leg is a valid joined interface, not an unmeshed
positive gap. Finite-gap branches must have explicit mesh resolution.

[panels.json](panels.json) lists T01–T10 with unique coordinates. These are
proposal registrations only; the absolute anchor/deck is still unregistered.
Reject self-intersecting/disconnected core, winding overlap, clearance/insulation
breaches or material extrapolation. No topology or customer limit is changed.

## Conditions, excitation and outputs

Three proposed strata: nominal approved material/temperature and bias vector;
upper allowed bias/current with corresponding approved material condition;
worst permitted gap/layer-position tolerance. Full bias vectors (Ip,Is),
thermal conditions, gap/layer errors and their correlations are HUMAN_INPUT.
Do not assume (Ip,0) represents the customer's loaded converter. A customer's
AC/thermal/isolation requirement cannot be satisfied by this DC magnetic screen.

New planar A_z formulation with independently sourced winding current regions,
flux linkage and nonlinear coenergy. The motor binary supports the language,
not this finished deck. Every design/stratum case comprises the base bias
state I0 and perturbations I0±deltaIp and I0±deltaIs: **five nonlinear field
states**, not one matrix solve. delta currents are HUMAN_INPUT. Extract
Ldiff_ij=d(psi_i)/dI_j by central differences; never assume psi/I is differential
inductance in nonlinear ferrite. [COMSOL differential-inductance workflow](https://www.comsol.com/blogs/using-differential-inductance-and-coils-in-comsol-multiphysics/).

Return the signed2x2 Ldiff matrix (H), both flux linkages (Wb-turn), B at the
base and every perturbation, energy/coenergy, Newton diagnostics, conditioning
and extraction conventions. Report winding current and terminal-polarity
conventions, not absolute off-diagonal values. Small-signal primary leakage is
the Schur complement L11-L12*L21/L22 under the registered shorted-secondary
magnetic definition; invalid L22/indefinite matrices are reference findings.
This is not measured operating-frequency short-circuit impedance or AC loss.
Use nonlinear energy integrals, not 0.5 I^T Ldiff I at a biased nonlinear state.

Six refined cases (T01/T04 in all strata) repeat the five states with finer
mesh **and** half delta; the proposed2x complete-case cost is a hypothesis
for that repetition, not an omitted second sweep. Compare it with the coarse
delta result but report that mesh and delta changes are coupled. If a difference
cannot be attributed, freeze an additional same-mesh delta-halving comparison
and request budget; it is not silently free. Refine leakage specifically:
small differences of large matrix terms can flip a narrow leakage verdict.

## Controls, independent witnesses and adequacy gap

Four complete-control allocations: linear-material reciprocity/energy;
signed current reversal at permitted bias; exterior-domain enlargement;
gap/layer mesh-resolution comparison. Positive semidefinite incremental L,
L12/L21 consistency, terminal/energy extraction and winding sign are checked.
No force/torque observer is reused. Full peak B near corners requires pinned
physical fillets and convergence; a percentile cannot hide a saturation hotspot.

Matched witness pairs T01 nominal and T04 tolerance: two GetDP2D cases and
two independently held buyer-tool **same 2D slice** cases (four complete-case
allocations). This can support a Tier2 target for that slice only. Suggested
pointwise matrix tolerance max(1% declared self-L scale,3% entry magnitude),
leakage difference max(approved absolute leakage floor,3% target leakage),
and bias B difference2%, all HUMAN_INPUT. Near-limit uncertainty must be
smaller than the approved decision band; no noisy Schur complement is accepted
by symmetry alone. Claim only agreement with the reference simulator's slice.

**The slice is not the actual finite PCB.** Its force-free A_z field assumes
translation along depth D; end turns, terminals, lateral fringing and core
edge fields can move leakage and peak B. Multiplying by D does not prove them
negligible. Before declaring a complete layout feasible or buying a bank,
acquisition must package a 3D magnetic coil/edge-element/extraction route or
an independently accepted end correction, and compare at least the separated
and interleaved layouts at nominal and worst tolerances against the same
physical CAD. Return pointwise and feasibility/pick/regret agreement. These
**four 3D witness jobs are outside the EUR20 slice estimate**, have UNMEASURED
cost and require a separately approved capped manifest. Motor's existing deck
does not implement them. No request for this extra spend is made here.

AC skin/proximity loss, core hysteresis/dynamic loss, capacitance, dielectric
strength/creepage validation, heat rise and switched-waveform effects are not
available from motor magnetostatics. They are mandatory whenever the real
buyer needs a finished transformer, in which case this panel cannot give that
decision. Retain their flags as NOT_CHECKED; never waive a safety condition.

## Decision/baseline screen and cost

Customer target self/leakage intervals, B limit by ferrite/T, package/current
limits, insulation rules, objective among admissible layouts and buyer-unit
regret are HUMAN_INPUT. No new B cap or inductance target is invented to make
five pass. Report T1/T2 initially as SLICE_ONLY/UNRESOLVED until physical
applicability is established. Ten seeds do not prove five-plus-five or changing
answers; if needed propose new frontier actions under a separately priced
manifest, not a looser band.

Strong baseline: analytical layer leakage/reluctance, circuit optimization and
cached nonlinear FE interpolation. Hold out whole layouts; include acquisition,
calibration/search and retained verification. A cheap adequate circuit/map
ends the V4 hypothesis; do not add novelty merely to beat it.

30 complete primary cases,6 refined at2x cost,4 complete controls,4 complete
matched slice witnesses and4 failed-case allocations: U=54. Maximum **240 field
systems** before any extra mesh/delta separation or3D stage (5 each across48
attempted complete cases; refinement multiplier is cost, not double-counted
physical systems). C1=0.03/0.08/0.20 CPU-h per complete five-state case,
RAM1/4/12GiB, all UNMEASURED #928 hypotheses. Cash estimate EUR10.90/15.30/25.87
under [the budget](README.md). A EUR20 cap does **not** promise completion of
the high scenario. Measure a fixed three-nominal-design prefix, charge it
once, re-estimate, then stop incomplete or request owner repricing. No grant,
package feature proof, actual feasible transformer or qualified bank exists.
