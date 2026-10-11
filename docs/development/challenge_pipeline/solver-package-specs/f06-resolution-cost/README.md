# f06: resolution, decision preservation and startup cost

`F06-RESOLUTION-AND-COST-01`; DEVELOPMENT **SPECIFIED**. Research and arithmetic
only. **COARSEST_ADEQUATE_GRID_NOT_DEMONSTRATED; C1/C2 UNMEASURED.** No solver,
build, spend, hidden data, bank draw, adopted reframe or qualification. Reuse
the [package spec](../f06-meep.md), [packet](../../round1/f06-grating-coupler.md)
and [inactive 2D reframe](../../value-cost/reframes/f06.md); existing authority
and historical results are unchanged. [Sources](sources.md) and the
[non-executable assumptions](analysis.json) distinguish evidence from inference.

## Buyer decision and what cannot be traded away

The original task selects a finite-width silicon grating for a Gaussian fibre,
not upward radiated power alone. Every design has **45 observations**: nine
correlated geometry/alignment conditions at five exact wavelengths. The packet
floor is coupling 0.30 and reflection cap 0.10 on every row; the objective is
the fifth sorted coupling (nearest-rank p10). A complete 3D witness includes
all 45, plus normalization and required numerical controls. One wavelength
is not a witness. Requirement variation over the same bank spends its existing
exposure, not a fresh bank. No safety or buyer limit is relaxed here.

The existing 30/20/10 nm ladder remains the selected DEVELOPMENT proposal.
**Recommendation, HUMAN_INPUT: science/DC:** first test 30 nm with proper
subpixel averaging, then optionally insert a 40 nm cost probe. Treat 50 nm as
a screening experiment only. Do not declare 40 nm adequate before the checks
below. This is a numerical-route investigation, not a second customer reframe.

## Published evidence: promising, not transferable certification

Correct interface averaging can improve convergence; sharp corners still
complicate it. Meep's anisotropic averaging is not arbitrary blurring of the
physical design. See [Farjadpour et al.](https://opg.optica.org/ol/abstract.cfm?uri=ol-31-20-2972)
and the [official method](https://meep.readthedocs.io/en/latest/Subpixel_Smoothing/).
Those results do not set a universal resolution for our decision.

[Wan et al., Appendix A](https://congshanwan.github.io/files/Wan_2018_GARC.pdf)
used 19–35 pixels/µm and 20 pixels/µm (50 nm) for sensitivity studies of a
different 3D interlayer coupler. That supports testing a coarse ladder, not
claiming our finite-width fibre coupling, rank or near-limit verdict converges
at 50 nm. [Lee et al.](https://oak.go.kr/central/journallist/journaldetail.do?article_seq=20707)
used 20/10 nm directional mesh spacing for a silicon fibre coupler with 70 nm
etch; this is relevant practice, not Meep isotropic-grid convergence proof.

Our minimum 70 nm etch occupies only 1.4 cells at 50 nm, 1.75 at 40 nm and
2.33 at 30 nm. Even an internal-wavelength pixel heuristic cannot prove this
geometry's phase, reflection, overlap or ranking accuracy. The
[Meep FAQ](https://meep.readthedocs.io/en/latest/FAQ/) requires convergence of
the quantity actually sought; it supplies no universal adequate grid.

## Exact prospective comparison, before accepting a grid

KEEP Meep v1.32.0 at commit `95d41251ddacfb6d63b9efecd8ba2814af141e2d`;
accepted image/dependency/task hashes are still missing. Use analytic built-in
geometry and `eps_averaging=True`. Freeze `subpixel_tol`, `subpixel_maxeval`,
source, run/decay time, mesh origin, PML, padding, normalizations, fibre/mode
planes and all DFT frequencies in the manifest. Tighten integration accuracy
independently. A raster epsilon file or scalar Gaussian blur is not equivalent
to built-in anisotropic interface averaging. A half-voxel origin shift probes
aliasing without changing the physical geometry. Averaging is not evidence
that a 70 nm etch is resolved.

Proposed registration (HUMAN_INPUT, no execution grant): choose eight complete,
non-hidden designs before running: geometry corners including minimum etch,
width extremes, a central design, and distinct screen-predicted contenders
and near-floor/near-reflection designs. Record exact coordinates/selection,
never quietly choose only the coarse winner. All nine conditions and five
wavelengths remain. Compare 30→20 nm on all eight; 10 nm on the unresolved
or rank-sensitive subset and independent controls. An optional 40→30 nm
comparison follows, not replaces, this evidence. DC must quote the complete
registered work, including failed attempts, before any execution approval.

The packet recommendations remain adjacent differences ≤0.02 coupling and
≤0.01 reflection; independent PML/padding/time effects ≤0.01, power closure
≤0.03. They are numerical diagnostics, not a total error certificate. Proposed
total bounds `e_C≤0.01`, `e_R≤0.005` reserve room for the Tier-2 target but
remain **HUMAN_INPUT**, not adopted tolerances. Do not automatically infer
an error bound by assuming quadratic Richardson convergence at corners.

For approved row-wise error bounds and a drawn coupling floor L/reflection
cap U:

- **Resolved feasible:** all rows satisfy `C-e_C ≥ L` and `R+e_R ≤ U`.
- **Resolved infeasible:** at least one satisfies `C+e_C < L` or `R-e_R > U`.
- Otherwise **UNRESOLVED**: refine, or abstain. Missing truth is not
  NONE_FEASIBLE or candidate failure.

Propagate lower/upper coupling arrays through the fifth order statistic. A
rank is resolved only when one contender's lower objective exceeds the other
upper objectives, or an owner-approved value-equivalent/regret rule applies.
Continuous requirement draws inevitably encounter boundaries: report their
unresolved rate rather than claim every draw is preserved. Report pointwise
errors **and** per-design verdict agreement, best-pick agreement and regret
in absolute coupling fraction; neither substitutes for the other. Tier 2 still
requires matched Lumerical witnesses outside producer custody under the
[credibility policy](../../round1/reference-credibility.md), never protected
quiz/EVAL/STRESS/tuning material. A reference disagreement triggers a
prospective revision, never a silent sealed-result rescore.

## Memory: distinguish lower bound, scenario and measurement

The #947 bare grating volume implies 573 million–1.2 billion cells at 10 nm.
Using Meep's 96-byte real-field baseline gives the first column below; it
excludes air/substrate/PML/ports, averaging tensors, monitors and extraction.
A **scenario**, not an upper bound, uses 120 bytes/cell (three additional
double tensor entries), 2.5× bare volume and 1.5× auxiliary storage. Tensor
coverage/chunking and complex fields may change this substantially. Exact
Nx×Ny×Nz, field mode and process-tree/container peaks must be measured.

| Grid nm | Bare 96-byte GiB low/high | Larger-domain scenario GiB (high bare volume) | Complete 45-row CPU-h fast/tail hypotheses |
| --- | --- | --- | --- |
| 50 | 0.41 / 0.86 | 4.02 | 0.518 / 2.074 |
| 40 | 0.80 / 1.68 | 7.86 | 1.266 / 5.062 |
| 30 | 1.90 / 3.97 | 18.63 | 4 / 16 |
| 20 | 6.40 / 13.41 | 62.86 | 20.25 / 81 |
| 15 | 15.18 / 31.79 | 149.01 | 64 / 256 |
| 10 | 51.23 / 107.29 | 502.91 | 324 / 1,296 |

[CCX63](https://www.hetzner.com/cloud/general-purpose/) advertises 48 vCPUs and
192 **GB** (about 178.8 GiB), not 192 GiB or 48 independent physical cores.
The scenario at 10 nm does not fit it. Lower-bound fit is not RSS fit; host
reserve, MPI/DFT overhead and memory bandwidth remain unknown. No memory cap,
hardware availability or allocation is granted by this document.

## CPU and C2: conditional break-even, not measured quantiles

KEEP the earlier 30 nm complete-panel hypotheses: 4 CPU-h fast, 16 CPU-h tail.
They are not empirical p50/p95. For a fixed domain/time interval, use
`CPU(h)=CPU(30)*(30/h)^4` (cells h^-3 and timesteps h^-1) as a sensitivity
model only. Decay time, resonances, mesh/DFT/normalization changes or poor
parallelism can invalidate it. Broadband parity at all five exact wavelengths
must be established; absent parity, charge the separate frequency launches.

Use B=256 complete designs from the **unadopted** question-law proposal, not
a smaller bank chosen to make a cost gate pass. Rate €1.37/billable node-hour
is the framework's working assumption, not a new quote. Illustrative retained
overhead O=€20 covers other work only if DC can actually deliver it; tax,
storage, normalization, convergence and failures must replace this allowance
in a real quote. Define **S = measured aggregate CPU-h per billed node-h**,
including memory-limited scheduling. S is not advertised vCPU count.

`C2 = O + 1.37*(B*CPU_primary + W*CPU_witness)/S`.

| Primary fast hypothesis | S | Primary C2 incl. €20 | Additional complete 20 nm witnesses affordable | Additional complete 10 nm witnesses affordable |
| --- | --- | --- | --- | --- |
| 30 nm | 8 | €195.36 | 0 — primary fails | 0 — primary fails |
| 30 nm | 16 | €107.68 | 0 — primary fails | 0 — primary fails |
| 40 nm | 8 | €75.49 | 7 | 0 |
| 40 nm | 16 | €47.74 | 30 | 1 |

These are **separate alternatives**, not additive allowances; the counts omit
extra ladder rungs beyond the €20 assumption. Thus even the conditional
40 nm/S=16 case buys only one 10 nm complete witness, not broad proof. At the
40 nm tail hypothesis, S=8 costs €241.94 before witnesses. Break-even S is
17.536 for the 30 nm fast bank, 5.5485 for the 40 nm fast bank and 22.194 for
the 40 nm tail bank, before witnesses. An eight-design 30/20 nm ladder plus
two 10 nm witnesses would alone be 842 CPU-h in the fast scaling model
(`8*(4+20.25)+2*324`), before repeats and buyer-tool witnesses. It cannot be
hidden inside a small miscellaneous allowance.

## Recommendation and honest failure condition

**The original full-3D bank has no demonstrated affordable adequate route.**
40 nm plus proper averaging is a candidate to test, not the answer. Accept
only after decision/error evidence and measured complete startup C2≤€100,
including adequate independent witnesses. If 40 nm fails numerical adequacy,
or if a credible ladder cannot fit, report original f06 C2 failure to the
owner. Evaluate the existing, inactive **2D early-design** reframe separately
against the strongest cheap 2D optimizer; it gives up final finite-width
robust sign-off and cannot inherit Tier 2 or value automatically. Do not
silently activate it, shrink B, discard hard cases, skip convergence or
stretch credibility to rescue a ranking.

DC return: exact grid/domain/chunks and pins; raw 45-row curves and observer
integrals; decision/error/unresolved results; complete CPU, wall, peak RSS,
node allocation and retained-artifact costs with failures; achieved S at a
safe resource shape. This is the smallest evidence needed to choose the
coarsest adequate grid and keep/reframe/replace. No additional spend request
is made now.
