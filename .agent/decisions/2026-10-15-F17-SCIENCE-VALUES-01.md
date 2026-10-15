## 2026-10-15 — F17-SCIENCE-VALUES-01: f17 micromixer reference-path and bank values (DEVELOPMENT)

**Authority.** OWNER-SOLVER-READINESS-SCIENCE-DELEGATION-01 (2026-10-15). These
are DEVELOPMENT values for the f17 OpenFOAM v2506 flow + passive-scalar
reference path (package F17-OPENFOAM-PACKAGE-01) and its public development
panel. They grant no qualification, Tier 2/3 claim, LIVE status, reward or
spend. Hidden and sealed material is untouched; the bank freeze path takes its
seed from the operator and none is recorded here. The owner may change any
value by a later record. Values are prospective.

**Buyer and what flips the decision** (packet `round1/f17-passive-micromixer.md`
§1, §3, §5, §6; `reference-routes.md` f17). A lab-cartridge engineer picks a
staggered-herringbone groove geometry that maximises the worst of nine
flow × diffusivity conditions' positive-axial-flux weighted outlet uniformity
M, subject to M ≥ 0.8, Δp ≤ 250 Pa and volume/flow ≤ 20 s on all nine. The
decision flips when numerical diffusion inflates M across the floor, when
groove coarsening changes the recessed volume (residence) or pressure, or when
a reused velocity contaminates the scalar. The packet's own M decision band is
0.02 (mesh ΔM and cross-tool ΔM), so every numerical tolerance below keeps
its error at or under that band, and controls sit at half of it or tighter.

**Order.** This file is committed before the controls, the cache proof, the
two-mesh comparison and the maximum-Pe witnesses it judges; the commit order
on `claude/solver-ready-f17` is the record. One exploratory engineering run
preceded it (deep-dense, h = 10 µm, Q = 5 µL/min, D = 0.5e-10, used to make the
iterative solve converge at all); the "Observed first?" column says what it
showed. No value was set or loosened to pass a result.

### G. Geometry convention (`scripts/dev/reference_packages/openfoam/f17_geometry.py`; `micromixer_readiness.geometry_recipe`)

| Value | Chosen | Basis | Observed first? |
|---|---|---|---|
| G1 groove shape | chevron of two 50-µm arms (width normal to the arm), centrelines ±45°, apex at y = 100 µm (half-cycle 0) or 200 µm (mirror), apex upstream, arms run downstream to y = 10 / 290 µm and are cut parallel to the wall; recess z ∈ [−depth, 0] | packet §2 (50 µm, 45°, corner at 1/3 width, 10 µm wall stop); normal width is the conventional groove width | no |
| G2 stations and reversal | first tip x = 250 µm; apex spacing p in a half-cycle and p + 100 µm across a reversal; grooves while the footprint ends ≤ 9750 µm | with spacing p across a reversal, the continuing arm family is collinear at p = 100 µm (overlapping grooves for p < 170.7 µm); p + 100 (the apex jump) keeps that family at its in-cycle normal spacing p/√2, so the whole packet support is valid; 250-µm smooth leads at both ends keep the outlet plane off the last groove | no (geometric analysis) |
| G3 half-cycle | groove i in half-cycle (i // reversal) mod 2 | packet "reverse every 6–10 grooves" | no |
| G4 validity | every groove pair web ≥ 20 µm and no overlap; sidewall clearance exact | in-cycle web at p = 100 is 100/√2 − 50 = 20.7 µm; a smaller web is a convention defect | no |
| G5 fluid volume | 300 × 100 × 10000 µm³ + depth × Σ groove areas; supported range 18.83–22.04 s volume/flow at 1 µL/min | analytic, includes recesses (packet §6) | no |
| G6 inlets | inlet0 y < 150 µm c = 0, inlet1 y > 150 µm c = 1, uniform equal normal velocity on both (plug), outlet p = 0, no-slip walls, zero solute wall flux | packet §2 "prescribed equal inlet flux" | no |

### N. Numerical settings (`f17_deck.py`)

| Value | Slot | Chosen | Basis | Observed first? |
|---|---|---|---|---|
| N1 mesh rungs | `f17_deck.counts`, `snappy` | primary h = 10 µm (≈ 3.1–3.7×10⁵ cells), refined h = 10/√2 = 7.071 µm (≈ 1.0×10⁶); background faces at z = 0 and z = −depth, ≥ 2 cells across the recess; snappyHexMesh level 0, explicit feature snapping; `checkMesh` must report "Mesh OK" | spec ~200k–600k primary; √2 is the smallest ratio that separates second-order error from noise; aligning the floor and recess bottom with faces leaves only the 45° walls to snap | the deep-dense h = 10 mesh was generated (Mesh OK, max non-orthogonality 40°) |
| N2 flow solve | flow `fvSolution`/`fvSchemes` | simpleFoam laminar, SIMPLEC (`consistent yes`), p relaxation 1, U 0.9, 1 non-orthogonal corrector, Gauss linear corrected; converged when initial residuals p ≤ 1e-6 and U ≤ 1e-7 AND (post hoc) area-mean inlet p changes ≤ 1e-5 relative over the last 10 iterations; ceiling 4000 iterations, else the flow is UNRESOLVED | Re ≤ 0.4, so the flow is Stokes-like; 1e-5 on Δp is 1/5000 of the 5 % band | the exploratory Q = 5 flow converged in 115 iterations |
| N3 scalar scheme | `f17_deck.PRIMARY_SCHEME` | `bounded Gauss linearUpwind grad(T)` (second-order upwind, unlimited gradient), steady, no relaxation; raw c is never clipped, so boundedness stays a real check (B3) | cell Péclet reaches ~560, ruling out central differencing; the TVD limiters do not converge as a steady Picard iteration here (limitedLinear01: outlet M 0.964 → 0.954 → 0.947 at 3/100/200 iterations, still drifting; vanLeer01 the same), while linearUpwind's deferred correction is a linear fixed point and converged geometrically (factor ≈ 0.57 per iteration) | yes: the convergence behaviour above, not any judged value, chose the scheme |
| N4 scalar linear solve | scalar `fvSolution` | PBiCGStab/DILU, tolerance 1e-13, relTol 1e-3 per outer iteration, 0 non-orthogonal correctors (the lagged correction converges with the outer iteration) | the uniform 0.5 start makes the first iterate the exact first-order upwind solution, so no unconverged "front" survives | yes (the uniform-start/limiter front was the exploratory failure) |
| N5 scalar stop | `SCALAR_STEADY_TOL`, `SCALAR_WINDOW` | stop when the outlet flux-weighted mean of c² differs from its 10-iteration window mean by ≤ 1e-7; ceiling 300 iterations → NOT_CONVERGED (UNRESOLVED) | near M = 0.9 a change of 1e-7 in ⟨c²⟩ is ~2e-6 in M, far under 1e-3 (1/20 of the band) | no |
| N6 observers | `f17_extract.py`, `micromixer_readiness.outlet_observer/balances` | M from raw outlet face c and face flux phi (zero-gradient outlet: face c = owner cell c), positive flux only, no clamping; Δp = ρ × (area-weighted mean kinematic p over both inlets − 0); residence = mesh fluid volume / prescribed Q; mass and solute balances integrated host-side from the raw boundary fields (solute = advective phi·c + diffusive −D·snGrad(c)·|S| with OpenFOAM's boundary deltaCoeffs) | packet §6 and spec §3; host-side integration is the independent extraction the spec asks for | no |

### B. Balances, bounds and applicability

| Value | Slot | Chosen | Basis | Observed first? |
|---|---|---|---|---|
| B1 mass balance | observer | \|Σ boundary phi\| / inflow ≤ 0.5 % | packet §5, adopted | no |
| B2 solute balance and floor | `micromixer_readiness.balances`, `SOLUTE_FLOOR_FRACTION` | \|Σ (advective + diffusive) over all patches\| / incoming solute ≤ 0.5 %; when incoming solute < 1e-6 × Q (zero-solute control) the denominator is the floor 1e-6 × Q × 1 (concentration units) | packet §5 adopted; spec §3 recommendation (normalise by incoming solute, never by a tiny net) adopted with an explicit floor | no |
| B3 bounds | observer | every cell and outlet face c ∈ [−0.001, 1.001]; a breach is a finding for that condition (UNRESOLVED), never clipped | packet §5 | no |
| B4 backflow | observer | any outlet face with phi < 0 makes M inapplicable (UNRESOLVED) | packet §6 | no |
| B5 mesh volume | mesh stage | \|V_mesh / V_analytic − 1\| ≤ 0.5 % | 1/10 of the 5 % residence band | deep-dense h = 10: −6e-5 (exploratory mesh) |

### C. Controls and code verification

| Value | Slot | Chosen | Basis | Observed first? |
|---|---|---|---|---|
| C1 Poiseuille duct | `f17-feature-proof.json:controls.poiseuille` | smooth 300 × 100 µm × 10 mm duct, Q = 5 µL/min: developed pressure gradient (least-squares over cells with 2 mm < x < 8 mm) vs the exact series: relative error ≤ 3.0 % at h = 10 µm and ≤ 1.5 % at 7.071 µm, observed order in [1.5, 2.5] | an independent 2D cell-centred FV model of the same cross-section predicts +2.29 % / +1.17 % flow error (order 1.94); the band is that prediction plus margin, inside the 5 % pressure band (the pressure cap has a ~6× margin, so this error cannot flip a verdict). **Replaces** the `micromixer-readiness/verification.json` recommendation of ≤ 1 % on a 10/5/2.5 µm ladder: on the registered 10 µm rung that figure is below the scheme's own truncation error, so it would fail by construction; the flow-MMS and scalar-MMS rows there stay unimplemented gaps (Poiseuille + C5 cover flow pressure and scalar transport order) | no |
| C2 uniform tracer | `controls.uniform` | both inlets c = 1, D = 1e-10, Q = 5: max \|c − 1\| over every cell ≤ 1e-6 and B2 | exact solution c ≡ 1 | no |
| C3 split tracer | `controls.split` | c = 0/1, h = 10 µm: \|M_OpenFOAM − M_ref\| ≤ 0.01 at (Q 1, D 2e-10) and (Q 5, D 0.5e-10), M_ref from the independent developed-flow marching solution (`f17_controls.marching_mixing`) whose own refinement changes M by ≤ 1e-3; outlet mean c within 1e-3 of 0.5 | half the M band; the marching reference is exact up to its converged discretisation and the neglected entrance/axial diffusion | the reference values (0.4420, 0.0814) were computed before OpenFOAM ran; no OpenFOAM result |
| C4 smooth zero-D | `controls.zeroD` | D = 0, Q = 5, split inlet: outlet M ≤ 1e-3 | straight developed flow has no transverse velocity across y = 150, so the exact M is 0 | no |
| C5 periodic scalar code check | `scripts/dev/code_verification/openfoam_periodic.py` | observed L2 order in [1.7, 2.3] over N = 16/32/64 | code-verification README recommendation, adopted | no |

### D. Convergence, high-Péclet adequacy and reuse (witnesses deep-dense 40/100/6 and deep-sparse 40/250/10)

| Value | Slot | Chosen | Basis | Observed first? |
|---|---|---|---|---|
| D1 two-mesh | `f17-feature-proof.json:convergence` | h 10 vs 7.071 µm at the maximum-Pe condition (Q 5, D 0.5e-10): \|ΔM\| ≤ 0.02, \|Δp\|/Δp ≤ 5 %, volumes each within B5 | packet §5 (ΔM ≤ 0.02, Δp ≤ 5 %), adopted. The full refined nine-condition panel is a bulk-pilot item (lead directive, cost) | no |
| D2 high-Pe adequacy (zero-D witness) | `convergence.high_pe` | on each witness and rung, on the same Q = 5 flow: M(D = 0.5e-10) − M(D = 0) ≥ 0.02. If it fails on the primary rung but holds on the refined rung, the refined rung is required for the bank; if it fails on both, maximum-Pe M is HIGH_PE_UNRESOLVED and every design whose worst-M lies within 0.04 of a floor is UNRESOLVED | true D = 0 transport gives M = 0, so M(D = 0) is pure numerical mixing; requiring the physical minimum diffusivity to add at least one decision band of mixing above it means numerics do not decide the floor (if numerical diffusivity equalled D_min, the log-Pe mixing law of herringbone mixers gives a difference of only ~s·ln 2 ≈ 0.015 for the observed slope) | no |
| D3 scheme diagnostic | `convergence.scheme` | limitedLinear01 run to its iteration ceiling at the maximum-Pe condition, reported with its drift; DIAGNOSTIC only (N3: it is not iteratively converged) | spec "meshes/schemes"; an unconverged comparison cannot accept or reject | partially (N3) |
| D4 one-way coupling | `cache.one_way` | simpleFoam never reads c; the scalar run leaves phi's data hash unchanged; the scalar is read only from `0/phi` copied from the hashed flow receipt | spec §2: D may leave the cache key only after this | no |
| D5 reuse parity | `cache.parity` | a fresh flow + scalar pair against the cached flow + reused scalar for (Q 5, D 0.5e-10) on deep-dense: phi data hashes equal and \|ΔM\| ≤ 1e-9, \|Δp\| ≤ 1e-9 relative; if not bitwise, ≤ 1e-4 passes flagged NONDETERMINISTIC | identical inputs and binary should reproduce exactly; 1e-4 is the iterative-convergence level | no |
| D6 refusal | `cache.refusal` | the scalar refuses before the solver starts when the flow receipt key belongs to another Q, another mesh, or the retained phi is missing/altered | spec §2 fail-closed loader | no |
| D7 flow-reuse acceptance | `micromixer_readiness.FLOW_REUSE` | reuse (3 flow + 9 scalar per design) is accepted for the bank when D4, D5 and D6 pass | spec §2 | no |

### F. Question law and bank (`question-laws/remaining/f17.md`)

| Value | Chosen | Basis | Observed first? |
|---|---|---|---|
| F1 P | independent uniform requirement vector: mixing floor U[0.80, 0.85]; residence cap U[19, 20] s; pressure cap fixed 250 Pa; one service context (the full nine-condition panel, mandatory) | draft law adopted for M. Residence: the analytic volume puts every supported design at 18.83–22.04 s at 1 µL/min, so the draft's [15, 20] s makes every cap below 18.83 s NONE_FEASIBLE by geometry alone; [19, 20] keeps the cap binding inside the 20-s anchor. Pressure: the analytic smooth duct is 42 Pa at 5 µL/min and grooves lower it, so a [200, 250] cap never changes an answer; it stays a hard check, not a sampled axis | the 42 Pa is analytic; the exploratory deep-dense flow gave 36 Pa |
| F2 Q | Q3 = P for scoring; Q2 enrichment (near-floor worst-M, residence-cap edges, maximum-Pe, comparator disagreement) is diagnostic only | shared rules | no |
| F3 w | outer unit weight; inner: worst-condition M objective, all nine conditions are hard gates, no averaging | packet §3 | no |
| F4 answer and tie rule | admissible: worst-M ≥ floor, max Δp ≤ 250 Pa, residence at 1 µL/min ≤ cap. Best: max worst-M. Value-equivalent set: admissible designs with worst-M within 0.02 of the best. Reported pick: lower max Δp, then lower residence, then fixed bank order | a worst-M difference inside the M band is unresolved; lower pump burden then lower hold-up are the buyer's secondary preferences (packet §1) | no |
| F5 verdict and NONE_FEASIBLE | PASS a floor only if every computed rung has worst-M ≥ floor; resolved FAIL only if every rung is below; else UNRESOLVED; a design whose primary worst-M is within 0.04 (two bands) of a floor needs the refined rung or stays UNRESOLVED; D2 can force UNRESOLVED. Residence verdicts use the mesh volume (band 0.1 s = B5 at 20 s). NONE_FEASIBLE is retained forward (no redraw) only when every eligible design is resolved FAIL; UNRESOLVED blocks it | shared two-band rule; f13 pattern | no |
| F6 k, n, B, E | k = 8 questions per window (base; 4/12 sensitivity), n = 8, B = 10n = 80, E = 10 | #776 base k = 8; OWNER-BANK-ARCHITECTURE-01 design-bank B = 10n, E = 10; requirement variants share solves and never renew E | no |
| F7 design bank M | tranche 1: 45 designs (the inherited M) drawn with the operator's producer seed from the packet action law (depth U[20, 40] µm, pitch U[100, 250] µm, reversal uniform on 6–10), refuse invalid G4 rather than clip; tranche 2: up to 15 frontier designs until F8 holds; M ≤ 60. Every design runs the full nine-condition primary panel; designs within 0.04 of a floor get the refined rung | inherited M = 45; frontier tranche planned rather than assumed | no |
| F8 T2(a) | stratum = mixing floor; band δ = 0.02; near = \|worst-M − floor\| ≤ 0.04; ≥ 5 distinct feasible and ≥ 5 distinct infeasible near designs at floors 0.80 and 0.85; residence cap near = within 0.2 s of a cap in [19, 20] s with the same 5 + 5 rule | shared two-band rule | no |
| F9 value checks B and D | B: worst-M spread ≥ 0.05 between best and worst admissible design per floor; D: expected distinct winners per k-window ≥ 3 under P and the best set changes with the residence cap for at least one floor | value-check-v1 pattern (as f13) | no |
| F10 Tier 2 cross-tool (future) | \|ΔM\| ≤ 0.02, Δp ≤ 5 % with absolute floor 0.5 Pa, residence ≤ 5 % with floor 0.1 s, same flux-weighted observer in both tools, zero resolved feasibility flips, same value-equivalent set | packet §5 recommendation adopted; 0.5 Pa cannot move a 250-Pa verdict; 0.1 s = B5 | no |

**HUMAN_INPUT left:** money (any bulk-run host, grant or spend), the producer
seed and hidden-bank custody, Tier 2 buyer-tool runs (COMSOL licence and
benchmark decks), and qualification.
