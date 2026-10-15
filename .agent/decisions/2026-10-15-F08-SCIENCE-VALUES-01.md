# 2026-10-15 — F08-SCIENCE-VALUES-01: DEVELOPMENT science values for the f08 reference path

**Authority.** OWNER-SOLVER-READINESS-SCIENCE-DELEGATION-01 (2026-10-15). Set by
the f08 solver-readiness track before the triage checks they judge were run
(written and committed before any f08 triage launch; the only results already
observed are the package smoke, the oscillator/plate feature proof and its
local re-run, marked below). DEVELOPMENT values only: no qualification, Tier
claim, LIVE, reward or spend. Exposure E, hidden `n`, protected `Q_job`, money
and the Tier 2 buyer-tool run stay with the owner.

**Customer problem (packet `round1/f08-resonance-structure.md`).** A precision
stage designer picks the lightest ribbed cantilever support that keeps, under a
1 N tip-pad force, mass ≤ 0.45 kg, static tip compliance ≤ 0.03 mm/N and the
worst tip dynamic compliance over 80–600 Hz ≤ 0.15 mm/N at every modal damping
ratio 0.005/0.01/0.02. The decision flips when a reference error moves a design
across one of those limits or reorders two designs' worst-band tip motion. A
missed or under-resolved narrow peak is the dominant hazard: at ζ = 0.005 the
half-power bandwidth is 1 % of the mode frequency, and an isolated peak scales
as (modal static compliance)/(2ζ), so a 1 % frequency (stiffness) error moves
the peak about 2 %.

**Error budget used to derive the bands.** The packet's 5 % peak band is the
total numerical budget for the decision quantity. It is split into mode
truncation ≤ 1 %, frequency sampling ≤ 0.5 % (a Lorentzian sampled at one
twentieth of its bandwidth off the crest loses 0.5 %; the observer then refines
the crest), and the rest to the mesh. A 1 % eigenfrequency band is consistent
with that (≈ 2 % peak). These are reference-numerics bands, not joint-damping
or physical uncertainty.

## Values

| # | Value | Slot (file:field) | Chosen value | Derivation basis | Result already observed? |
|---|---|---|---|---|---|
| V1 | Mesh eigen band | `structures-readiness/verification.json:task_adequacy_separate_from_MMS.registered.eigen_change_percent` | ≤ 1.0 % for every mode ≤ the first mode above 600 Hz, h = 3 vs h = 1.7 mm | Packet recommendation adopted; ≈ 2 % peak via ω² | No |
| V2 | Mesh peak band | same `.peak_change_percent` | ≤ 5 % worst-band tip peak per ζ, h = 3 vs 1.7 | Packet adopted; equals total decision budget | No |
| V3 | Peak location band | same `.peak_location` | ≤ min(2 Hz, 1 % of peak f) | Packet adopted; = one ζ = 0.005 bandwidth | No |
| V4 | Peak phase band | same `.phase_deg` | ≤ 5° wrapped, each rung at its own resolved peak, only where \|u\| ≥ 0.015 mm/N | Packet 5° adopted; floor = 10 % of the 0.15 cap (phase is meaningless near zero response) | No |
| V5 | Absolute floor away from peaks (packet HUMAN_INPUT) | same `.curve_floor` | \|Δu\| ≤ 0.05·\|u_ref\| + 0.0015 mm/N on the reference grid, away from peaks: outside f_j·(1 ± 3·2ζ) of every in-band mode of either rung (inside those windows V2–V4 govern; a 1 % frequency shift legitimately moves a ζ = 0.005 curve by far more than 5 % at fixed frequency) | 0.0015 = 1 % of the dynamic cap: below any decision-relevant motion | No |
| V6 | Static mesh band | same `.static_change_percent` | ≤ 2 % | Packet's static cross-tool 2 % adopted as the mesh band | No |
| V7 | Mass band | same `.mass_change_percent` | mesh vs CAD volume ≤ 0.5 % | Packet adopted (0.5 % of 0.45 kg = 2.25 g) | No |
| V8 | Asymptotic check | same `.asymptotic` | \|Δ(2.25→1.7)\| ≤ \|Δ(3→2.25)\| for f1 and each ζ peak, else NOT_ASYMPTOTIC → UNRESOLVED (finding, no band change) | Three-rung practice; a non-monotone ladder cannot bound error | No |
| V9 | Bank mesh choice | same `.bank_mesh_rule` | the coarsest rung of {3, 2.25} whose V1–V7 pass against h = 1.7 on all three witness geometries at all ζ; if none, h = 1.7 with the gap reported | Cheapest adequate deck, chosen before the witnesses run | No |
| V10 | Registered numerical uncertainty for verdicts | same `.verdict_uncertainty` | u = band value (dyn 5 %, static 2 %, mass 0.5 % of the case value) unless a case-specific h = 1.7 refinement gives 1.25 × its observed difference (Roache 3-grid safety factor), floored at 1 % (dyn) | Verdict = FEASIBLE if every margin > u, INFEASIBLE if any margin < −u, else UNRESOLVED | No |
| F1 | Frequency-resolution rule | same `.frequency_rule` | grid ≤ 0.1 half-power bandwidth (2ζf_j) within ±5 bandwidths of each mode near the band, ≤ 0.5 Hz elsewhere; every local crest then refined by golden section to 1e-6 relative frequency | Packet ≤ 0.1-bandwidth rule adopted; refinement removes the sampling loss | No |
| F2 | Sampling-loss bound | same `.sampling_loss_percent` | refined crest − grid crest ≤ 0.5 % | Error budget (Lorentzian at bw/20) | No |
| F3 | ccx-native vs projection | `f08_proof.CHECKS.projection_over_peak` | ≤ 1e-4 of peak (unchanged package check) | Print precision; not a science band | Yes (proof) |
| M1 | Retained modes for the bank | same `.modes` | N = 48 per launch, truncations 12/24 reported | Packet ladder 12/24/48 | No |
| M2 | Mode-ladder adequacy | same `.mode_ladder_rule` | all of: f_N ≥ 900 Hz (1.5 × band top); truncation bound R/(1 − (600/f_N)²)/u_peak ≤ 1 % at every ζ, R = \|static − modal static\| at the tip (collocated residual-flexibility bound); 24→48 worst-band tip peak change ≤ 1 % and location ≤ min(2 Hz, 1 %). Fail → UNRESOLVED_MODES, a new registered launch with more modes | Truncation share of the budget; bound valid because residual modes above ω are stiffness-like | No |
| C1 | Oscillator control | `verification.json:tests[uncoupled…].registered` | ≤ 1e-6 relative complex error, phase ≤ 0.01° where \|u\| ≥ 1 % of peak, unretained ≤ 1e-12 | Repo recommendation 1e-6 adopted (ccx prints 7 significant digits, so this is the print floor) | **Yes**: 4.9e-7 in the recorded and local proof |
| C2 | Slender-beam control | `verification.json:tests[unribbed…].registered` | static ≤ 2 %, f1 ≤ 1 %, second z-bending ≤ 1 %, mode-1 FRF crest ≤ 3 % and location ≤ min(2 Hz, 1 %) vs Euler–Bernoulli at the pad centroid | Packet 2 %/1 % adopted; crest ∝ φ²/ω² tracks static (2 %) plus mode-shape share; shear/rotary corrections for 220×20×6 mm are < 0.2 % | No |
| C3 | 3D MMS orders | `verification.json:tests[3D cubic…].registered` | observed order on the last two rungs L2 ∈ [2.5, 3.5], H1 ∈ [1.5, 2.5]; reaction + body-force balance ≤ 1e-5 relative | Repo recommendation adopted (quadratic C3D10, cubic field) | No |
| C4 | Closed-form rod benchmark (NAFEMS substitute) | `verification.json:tests[closed-form rod…].registered` | ν = 0 fixed-free rod, lateral DOF fixed: first three axial f ≤ 0.2 %; tip FRF crest ≤ 1 %, location ≤ min(2 Hz, 1 %), phase ≤ 5° at each ζ vs the exact modal series | Exact 3D elasticity solution; band ≪ 1 % reference band so it tests the code, not the decision | No |
| D1 | Cross-tool agreement (future Tier 2 vs Mechanical) | `reference-route-panels.json:families.f08.agreement` | eigen/peak f ≤ 1 %, static ≤ 2 %, mass ≤ 0.5 %, location ≤ min(2 Hz, 1 %), peak ≤ 5 %, phase ≤ 5° above 0.015 mm/N | Packet recommendation adopted unchanged | No |
| D2 | Reduced vs full decision agreement | same `.decision_agreement` | zero resolved feasibility flips on the witness panel; pick agreement or regret ≤ 0.0075 mm/N | 0.0075 = 5 % of the cap = reference's own peak band; designs closer cannot be ordered | No |
| D3 | Tie rule | `question-laws/proposals.json:f08.objective.registered` | feasible set; candidates within 0.0075 mm/N of the minimum worst-band tip compliance; least mass; masses within 0.00225 kg equivalent; then frozen bank order | Objective order from the packet; tie widths = V2 and V7 bands | No |
| Q1 | P (geometry, design actions) | `proposals.json:f08.P_geometry.registered` | independent uniform on the lattice L 180:5:260, W 60:5:100, t 4:0.5:8, h_r 8:1:16, t_r 3:0.5:5, l_r 20:5:60 mm, conditioned on `structures_readiness.action` validity | Packet grammar; steps are the stock/drawing resolution a buyer distinguishes | No |
| Q2 | Q and w (geometry) | same `.Q_geometry` / `.w_geometry` | Q = P, w = 1 for bank v1 | Frontier position unknown before solving; a screen-based enrichment would rely on an unverified ROM. A T2a shortfall gets a second registered enrichment bank, never a redraw | No |
| Q3 | Damping law | same `.damping` | every geometry solved at all three ζ (mandatory); P_dev = Q = 1/3 each, w = 1, for population-mean diagnostics only | Packet | No |
| Q4 | P_job | `proposals.json:f08.requirement_axes[*].registered` | uniform over the 27-cell grid: dynamic {0.10, 0.15, 0.20} mm/N × static {0.02, 0.03, 0.04} mm/N × mass {0.35, 0.45, 0.55} kg; grid variant | Repo recommendation adopted; grid kept as the audit baseline (continuous variant not selected) | No |
| Q5 | Q_job | `proposals.json:f08.Q_job.registered` | 0.5 P_job + 0.5 uniform over near-limit cells (reference best answer's binding margin within 2 u of a limit, or pick changes under u); none → P_job, reported | Common recommendation adopted; 2 u = T2a's two refinement bands | No |
| Q6 | w_job | same `.w_job` | P_job/Q_job, population-mean diagnostics only, never a score weight | Common recommendation adopted | No |
| Q7 | B | `proposals.json:f08.bank_candidates.registered` | 256 geometries | Repo recommendation adopted: ≈ 9.5 designs per question cell; cost measured in the sizing note | No |
| Q8 | n | `proposals.json:f08.questions_per_batch.registered` | 8 | Packet's eight-question pilot | No |
| Q9 | k | same `.k` | 8 (iid draws in the expected-distinct-winners benchmark = n); minimum 2 distinct resolved picks per batch | Common recommendation adopted | No |
| Q10 | NONE_FEASIBLE | same `.none_feasible` | a question whose bank is fully settled with no FEASIBLE design is VALID_FORWARD_NO_REDRAW with answer NONE_FEASIBLE; if any design is UNRESOLVED, refine it (h = 1.7, then more modes) within the bank's refinement allowance, else the question stays UNRESOLVED, is excluded from scoring and counted in the residual-unresolved rate; no redraw, no quota | Common recommendation; refinement converts most unresolved cases | No |
| Q11 | Near-limit bands | same `.near_limit_bands` | UNRESOLVED zone = ±u; near-limit region = ±2u (dyn 10 %, static 4 %, mass 1 % of the limit) | V10 and T2a | No |
| Q12 | Value-check spread | `question-laws/value-check-v1.json:challenges[resonance-structure].registered_spread` | 0.03 mm/N | Value-cost V2 base gain (30 µm at 1 N) adopted | No |
| Q13 | Bank refinement allowance | `proposals.json:f08.refinement.registered` | every bank geometry that is a candidate answer for some cell and lies within ±2u of a limit gets an h = 1.7 refinement; plus 13 (5 %) random audit refinements | Covers the decision-relevant cases; audits estimate the h = 3 error on the population | No |

## Not decided here

Exposure E, hidden `n`, protected `Q_job`, any money or paid host, Tier 2
Mechanical execution and the NAFEMS P18/R0016 benchmark decks (not available
offline; C4 and C2 are closed-form substitutes and are labelled so).

**Reversibility.** Each value is prospective and versioned; a later decision may
change it. A failing result stays a finding; bands are not loosened.
