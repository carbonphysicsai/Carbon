# F06-SCIENCE-VALUES-01 — f06 grating-coupler reference values (DEVELOPMENT)

**Authority.** OWNER-SOLVER-READINESS-SCIENCE-DELEGATION-01 (2026-10-15).
DEVELOPMENT values only: no qualification, Tier claim, LIVE, reward or spend.
Money figures, hidden/sealed material and any paid run stay with the owner.

**Order.** Every acceptance value in §A–§D was written into this file and
into `scripts/dev/reference_packages/meep/f06_controls.py:ACCEPT` before any
f06 Meep control ran (the f06 image did not exist yet). §E (bank size) was
set afterwards from measured cost, which is an input, not a judged result.
No value was changed after a result was seen; failures stay findings.

## Derivation from the buyer decision

The buyer picks one mask; every one of 45 rows (9 correlated vectors × 5
wavelengths) must have coupling C ≥ 0.30 and TE0 reflection R ≤ 0.10, and the
objective is the fifth-ordered coupling (nearest-rank p10). A numerical error
flips the decision when it moves a row across 0.30/0.10 or swaps two masks'
p10 order. The Tier-2 target is agreement with Lumerical to ≤0.01 absolute
coupling/reflection; our own numerical error must therefore sit inside that.
One coupling point (0.01) is 0.14 dB at 0.30 — below the 0.2–0.5 dB scale on
which grating designs are compared, so a total row error e_C = 0.01 keeps
designs that differ by a meaningful margin distinguishable. Reflection is
judged against a 0.10 cap and usually sits at 0.01–0.08, where the R-error
should be half the C-error: e_R = 0.005. These are the repo's existing
proposals (f06-resolution-cost README); the derivation confirms them.

The total budget is split into independent worst-case components that sum to
e (linear, not RSS, because the components can share sign):
grid 0.005/0.0025, PML 0.002/0.001, padding 0.002/0.001, duration
0.001/0.0005 (coupling/reflection). The packet's looser recommendations
(adjacent rung ≤0.02/0.01, PML/time ≤0.01, residual ≤0.03) cannot deliver a
0.01 total and are tightened, not relaxed.

## A. Numerical adequacy and grid

| Value | Slot | Chosen | Basis | Result seen first? |
| --- | --- | --- | --- | --- |
| Row error bound e_C | package-specs.json `packages.f06.registered_values.e_C` | 0.010 | buyer limit / Tier-2 0.01 (above) | no |
| Row error bound e_R | same `.e_R` | 0.005 | half e_C; cap 0.10 with typical R 0.01–0.08 | no |
| Grid budget | `.grid_budget` | ΔC ≤ 0.005, ΔR ≤ 0.0025 | half of e, largest single component | no |
| Grid estimator (2D ladder 40/30/20/15/10 nm, 8 public designs, nominal geometry, dx −1/0/+1, 5 λ) | `.grid_rule` | E_h = max\|Q(h)−Q(10)\| + 2·max\|Q(15)−Q(10)\| over rows | 10 nm as near-truth; factor 2 bounds the 10-nm residual for ≥1st-order convergence (corners), no assumed Richardson order | no |
| Reference grid | `.reference_grid_nm` | coarsest of {40, 30, 20} nm with E_h within the grid budget for C and R on every row; none → UNRESOLVED finding | coarsest affordable that preserves the decision | no |
| 3D grid confirmation | `.grid_3d_confirmation` | registered refinement witnesses nominal-narrow and nominal-wide, all 45 rows, at h_ref and next finer rung (30→20, 20→15): \|ΔC\| ≤ e_C, \|ΔR\| ≤ e_R and identical resolved verdicts at 0.30/0.10, before bank dispatch | 2D captures the etch/period discretisation; 3D adds lateral/taper edges | no |
| Spatial rungs | `.spatial_rungs_nm` | 2D 40/30/20/15/10; 3D h_ref + one finer rung on witnesses; no 10-nm 3D (forecast ≫ available memory) | memory forecast | no |
| Slab TE0 n_eff error | `.slab_neff_abs` | ≤ 0.003 at h_ref (220/150/90 nm Si) | n_eff error δ shifts the peak by Λ·δ; 2-nm Tier-2 peak budget / 0.63 µm | no |
| Code-verification order band (vacuum Bloch mode, h 0.05/0.025/0.0125) | code-verification criteria `status`/`order_band` for `meep-bloch-mode` | ACCEPTED_DEVELOPMENT, [1.7, 2.3] (spec recommendation) | Yee scheme is second order in vacuum | no |
| Courant | `.courant` | 0.5 (Meep default) | stable in 3D (< 1/√3) | no |
| Subpixel averaging | `.subpixel` | on, tol 1e-4, maxeval 1e5 (Meep defaults), analytic geometry | f06-resolution-cost README | no |

## B. Domain, absorber, stopping, source

| Value | Slot | Chosen | Basis | Result seen first? |
| --- | --- | --- | --- | --- |
| PML | `.pml_um` | 1.0 µm all faces, Meep default profile | ≥ 0.6 λ in air | no |
| PML adequacy band | `.pml_band` | doubling to 2.0 µm: ΔC ≤ 0.002, ΔR ≤ 0.001 | budget split | no |
| Padding | `.padding_um` | flux box: 0.5 above Si top, 0.2 into substrate below BOX, 1.0 beyond grating edge laterally and after last period; 0.3 µm gap to PML | evanescent decay of the slab mode in air ≈ 0.1 µm | no |
| Padding band | `.padding_band` | doubling all pads: ΔC ≤ 0.002, ΔR ≤ 0.001 | budget split | no |
| Stopping rule | `.stopping` | Meep `stop_when_dft_decayed(tol=1e-6)` from t_min = source end (100) + 4.5·box length + 50 to t_min + 2000; hitting the maximum = UNRESOLVED, never accepted | decay criterion fixed before running, not "finish when efficiency appears" | no |
| Duration band | `.duration_band` | tol 1e-8 rerun: ΔC ≤ 0.001, ΔR ≤ 0.0005 | budget split | no |
| Source | `.source` | TE0 eigenmode (band 1, ODD_Y 3D / ODD_Z 2D), Gaussian pulse at the mean of the five exact frequencies, fwidth 0.1 | covers 1.53–1.57 µm with margin | no |
| Broadband parity band | `.broadband_band` | 5 single-frequency runs (own normalization each) vs broadband: ΔC ≤ 0.002, ΔR ≤ 0.001 on nominal and short-narrow in 2D; repeated on one 3D witness before the bank; without 3D parity every wavelength is charged | numerical-procedure equivalence ≪ e | no |
| Mirror symmetry | `.mirror_symmetry` | Mirror(Y, −1) allowed: geometry, TE0 source and fields are y-symmetric, offsets enter only the analytic target; requires mirror vs full 3D ΔC, ΔR ≤ 0.001 incl. dy = ±1 targets | spec §2 allows symmetry that preserves geometry/source/offsets/observables when independently checked | no |

## C. Observer and controls

| Value | Slot | Chosen | Basis | Result seen first? |
| --- | --- | --- | --- | --- |
| Fibre convention | deck `fibre` | y-polarised, axis tilted 10° from +z towards +x (propagation direction), waist 2 µm above Si top centred on the nominal (mask-intended) grating centre + (dx, dy); overlap on the top flux face | standard forward-tilted coupler (avoids second-order Bragg); packet leaves sign/centre to the deck | no |
| Flux parity (straight guide) | `.flux_parity_rel` | \|flux/\|α+\|² − 1\| ≤ 0.002 | e/5 | no |
| Straight-guide TE0 reflection / transmission | `.straight` | R ≤ 1e-4, \|T − 1\| ≤ 0.002 | e/5 | no |
| Repeat | `.repeat` | bitwise identical (serial, same image/deck) | determinism | no |
| Gaussian overlap control | `.gaussian_overlap_rel` | Meep Gaussian beam vs analytic target: \|P_c/flux − 1\| ≤ 0.005 | 0.5 % relative = 0.0015 absolute at C = 0.3 | no |
| Field-integral vs Meep top flux | `.top_fields_vs_flux_abs` | ≤ 0.002 | validates overlap weights/positions | no |
| Incident drift | `.incident_drift_rel` | device vs normalization α+ ≤ 0.005 relative | cache key correctness | no |
| Power residual | `.residual_abs` | \|1 − R_flux − outward\| ≤ 0.010 per row | packet ≤0.03 tightened: a closure gap above e_C hides decision-scale power | no |
| Memory headroom | `.memory_headroom` | forecast (measured bytes/cell × cells + DFT planes) × 1.25 ≤ enforced limit; local 3D ≤ 10 GiB forecast | measured scatter + Python/export peak | no |
| 2D role | `.two_dimensional_role` | SCREENING_ONLY: numerical-procedure studies and research-kit proxy; never a reference value, bank answer or 2D→3D correction | spec §2 | — |
| 3D audit cadence | `.audit_cadence` | every bank design is full 3D at h_ref; finer-rung audit on 1 in 16 bank designs (seeded uniform, operator side) plus the two registered witnesses; any audit outside e → affected questions UNRESOLVED and grid escalation | bounds undetected grid drift | no |

## D. Agreement and question law

| Value | Slot | Chosen | Basis |
| --- | --- | --- | --- |
| Cross-tool (Tier-2) agreement | `.cross_tool` | per row \|ΔC\| ≤ 0.01, \|ΔR\| ≤ 0.01, peak λ ≤ 2 nm, identical resolved verdicts, best-pick p10 regret ≤ 0.01 | packet recommendation adopted |
| Value-equivalence / tie | proposals.json `challenges[4].tie_rule` | answer set = resolved-feasible masks with p10 ≥ best p10 − 0.01; reference pick: highest p10, then higher min C, then lower max R, then lower bank index | e_C |
| Feasibility with bounds | `.feasibility` | resolved feasible: every row C − e_C ≥ L and R + e_R ≤ U; resolved infeasible: some row C + e_C < L or R − e_R > U; else UNRESOLVED | f06-resolution-cost README |
| P (question law) | `.requirement_axes[*].continuous_interval`, `continuous_variant` | continuous: L ~ U[0.25, 0.35], U ~ U[0.05, 0.15], independent, quantised 0.001; service context fixed to the complete 45-row panel | proposal intervals adopted; context variation adds no new truth |
| Q | `.q` | 0.5 P + 0.5 P conditioned on the near-limit region (some bank mask with \|L − C_min\| ≤ 0.02 or \|U − R_max\| ≤ 0.01); Q = P if that region has zero mass | common recommendation, bands = 2e |
| w | `.w` | P/Q for population-mean diagnostics only; no score weighting | common recommendation |
| Near-limit bands | `.near_limit_bands` | ±0.02 coupling, ±0.01 reflection | 2e |
| NONE_FEASIBLE | `.none_feasible` | valid answer when every bank mask is resolved infeasible; issued, never redrawn | — |
| UNRESOLVED questions | `.unresolved` | a question whose answer set an UNRESOLVED mask could change is not issued; its P-mass is reported as residual_unresolved_rate; refinement only under separate budget | missing truth is not NONE_FEASIBLE |
| n | `.questions_per_batch` | 8 | proposal adopted |
| k | `.k` | 8 (iid winner-expectation benchmark = n) | — |
| Minimum distinct picks per batch | `.min_distinct_picks` | 2 | common recommendation |
| Bank design law | `.bank_design_law` | uniform independent: periods U{12..20}, pitch U[580, 680] nm (0.1 nm), duty U[0.35, 0.65] (1e-4), etch U[70, 130] nm (0.1 nm), width U[8, 12] µm (0.01 µm), rejection-conditioned on all nine perturbed geometries valid (line/space ≥ 180 nm, residual Si > 0); Q_design = P_design | packet §3 |
| Strata | `.strata` | width < 10 µm / ≥ 10 µm (the 3D-only axis); T2a ≥ 5 feasible and ≥ 5 near-limit infeasible per stratum checked after the bank | packet §10 |

## E. Bank size B (set after cost measurement)

See §E below the measured-cost section of
`docs/development/evidence/reference-packages-01/f06-bulk-sizing.md`.

## Alternatives rejected

Packet thresholds unchanged (cannot deliver e = 0.01); 2D as reference truth
or 2D→3D correction (spec forbids); periodic transverse unit cell (removes
finite width/taper/y-offset); 10-nm 3D rung (forecast far beyond any
enforced allocation available); Richardson extrapolation with an assumed
order at sharp corners.

**Reversibility.** Prospective DEVELOPMENT values; the owner may revise any
by a later record. No sealed evidence exists to rescore.
**HUMAN_INPUT left.** Exposure E; any spend above the existing €100 startup
framework; Tier-2 Lumerical witnesses (licence/tool outside custody).
