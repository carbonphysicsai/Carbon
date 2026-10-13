# Statistical and economic analysis

## Authority and scheduler scope

[OWNER-BANK-ARCHITECTURE-01](https://github.com/carbonphysicsai/Carbon/blob/eda5e5f55c1c3fae315e295ea8ed94f91d6d0fce/.agent/decisions/2026-10-07-OWNER-BANK-ARCHITECTURE-01.md)
sets historical development B/E=(20n,5), (10n,10), (5n,20), retirement by
appearances, active-window disjointness and separate pool/Q2/Q3 banks.
[VALIDATOR-23](https://github.com/carbonphysicsai/Carbon/blob/eda5e5f55c1c3fae315e295ea8ed94f91d6d0fce/.agent/tickets/VALIDATOR-23_bank_architecture.md)
subsequently separates Q2 accuracy/safety from Q3 design-question banks.
Its current public [bank.py](https://github.com/carbonphysicsai/Carbon/blob/eda5e5f55c1c3fae315e295ea8ed94f91d6d0fce/carbon/challenge_validator/bank.py)
draw_window uses seeded random sampling of eligible live cases, excludes
active holders, counts exposure, and retires at E. It does not implement a
consecutive-repeat schedule. The user's requested schedule is analyzed
prospectively, not described as deployed behavior.

[E2 authority](https://github.com/carbonphysicsai/Carbon/blob/eda5e5f55c1c3fae315e295ea8ed94f91d6d0fce/.agent/decisions/2026-10-08-OWNER-BANK-EXPOSURE-E2-01.md)
reduced battery pool exposure to 2, without changing design-bank E. The newer
[E1 testnet authority](https://github.com/carbonphysicsai/Carbon/blob/eda5e5f55c1c3fae315e295ea8ed94f91d6d0fce/.agent/decisions/2026-10-10-OWNER-BANK-EXPOSURE-E1-TESTNET-01.md)
selects E=1, B=4000, rotation 360 blocks, three active rotations, and separate
operator refill for battery testnet. Mainnet E/cadence/budget remain owner
decisions. This research neither accesses those banks nor operates a host.
Seam: **NO_CONFLICT** for analyzing historical/proposed options; treating the
old E=5 as current battery testnet authority would be DOCUMENTATION_LAG.
Implementing scheduled draws or heterogeneous E needs its own prospective
version and Validator-owned contract; not granted by this research.

## Reuse changes the information unit

For a frozen model and rule, let Y_i be the loss on independent physical
question i and m_i its appearances. Repeated deterministic evaluation returns
the same Y_i. The occurrence-weighted mean has variance
sigma² × sum(m_i²)/(sum m_i)². Thus effective independent cases are

`N_eff = (sum m_i)^2 / sum(m_i^2)`.

If every case repeats E times, N=nT appearances and N_eff=N/E, exactly.
Uneven reuse is worse for that occurrence-weighted estimator: e.g.
m=(1,9) has effective n=100/82≈1.22, while (5,5) has 2 (ASSUMPTION toy
counts). Deduplicating gives the actual unique-question estimator; it must
preserve registered population/stratum weights rather than silently change
the official score. Hidden duplicates inserted for determinism never add
independent case count either.

For stochastic repeat measurement, a stand-in model Y_it=mu+u_i+eps_it with
case variance sigma_c² and independent residual sigma_e² gives
rho=sigma_c²/(sigma_c²+sigma_e²) and

`N_eff = N^2 / [rho sum(m_i^2) + (1-rho) N]`;
balanced repeats have design effect `D=1+(E-1)rho`, hence N_eff=N/D.
ASSUMPTION rho low/base/high 0.25/0.75/1 produces [results.json](results.json).
These values are illustrative, not measured dependence estimates. Frozen
deterministic per-case value has rho=1; numerical nondeterminism is not a
reason to inflate physical information. Changed recipes across windows
introduce model effects and adaptation, not independent replicate eps.
Do not fit this random-effects shortcut blindly to a changing leader series.

For a scalar stationary window statistic with variance gamma0 and
autocorrelation rho_l, the algebraic finite-T identity is

`Var(mean) = gamma0/T [1 + 2 sum_{l=1}^{T-1} (1-l/T) rho_l]`.

This supports a window ESS only with that estimand and stationarity. The
[Stan reference manual, effective sample size](https://mc-stan.org/docs/reference-manual/analysis.html)
explains autocorrelation-based ESS for means. It does not certify an exam
or turn a nonlinear rank statistic into independent windows. Report actual
overlap matrices and case/recipe clusters for tau, gates and top-k regret.
For crossed recipe/question evidence, resample recipe families with their
seeds and unique questions with all repeat records, not each appearance;
[Owen's pigeonhole bootstrap](https://arxiv.org/abs/0712.1111) is the relevant
crossed-effects source, alongside #1045/#1055's public planning design.
Add time blocks only for the stated drifting-model estimand. Never publish
protected case identities to make these internal diagnostics convenient.

Consecutive identical cohort batches give identical window scores for a
frozen deterministic member (correlation 1 until replacement), even though
the reference need be solved only once. Interleaving active-disjoint cohorts
moves that covariance to later lags; it does not remove it. On a fixed bank,
independent random draws can have little conditional autocorrelation while
sharing the same bank-to-population uncertainty. A small time-series
autocorrelation alone therefore cannot establish fresh P coverage.

For nonconcurrent random draws from an unchanging bank, ignoring active
exclusion and retirement, expected overlap is n²/B and the unconditional
case-effect correlation contribution is n/B (derived stand-in). Adjacent
active draws are disjoint under Carbon's invariant, so that approximation
does not apply to them. Use the real *internal* incidence matrix to measure
covariance; research has accessed none.

At zero observed false accepts among R independent reference-infeasible
cases, a one-sided 95% binomial upper bound is `1-0.05^(1/R)` (confidence
choice ASSUMPTION; iid within stated stratum). If 1000 such appearances
represent only 200/100/50 cases for E=5/10/20, upper bounds are about
1.49%/2.95%/5.82%, rather than 0.30% from a false 1000-independent claim.
These are mathematical planning bounds, **not observed bank outcomes** or
assurance for unrepresented strata. Cluster inference, finite P sampling,
and adaptive selection may further limit the claim. Repeat sign-test
observations for a single question must stay one shared-question cluster.

## Consecutive schedules, sealing and release lag

Literal reuse in every adjacent window conflicts with active disjointness
if those windows overlap. Let A be a window's active duration in rotation
units and g the interval between this cohort's eligible appearances. Need
g>=A for E>1, or disjoint interleaved cohorts serving concurrent lanes. In
the ideal synchronous cohort schedule, from first draw to release eligibility:

`L_release = (E-1) g + A + reveal/publish/feed delays`.

With A=g=3 (ASSUMPTION schedule illustration; three active rotations are
sourced for battery), E=5/10/20 gives 15/30/60 rotation units before timers.
At an illustrative 360-block, 72-min cadence (battery owner working estimate,
not a universal chain-time guarantee), that would be 18/36/72 h. This
schedule is not deployed; concurrent screen/final roles require enough
disjoint cohorts and their own accounting. Case references publish only
after the **last** window using them ends and is revealed. Window-score
release can additionally wait for every selected case to publish. Different
E within one window makes its largest dependency determine lag.

Random reuse has long tails. For E=2, approximate each of n=98 target cases'
next selection by independent Bernoulli p=98/2000. Then
`Pr(all repeated by t) ≈ [1-(1-p)^t]^98`.
Derived median/95th/99th waiting times are 99/151/183 windows; independence,
constant p, no active exclusion and no turnover are **ASSUMPTION**, not
actual schedule percentiles. The owner E1 record independently documents
the earlier ~105-window (~16-day) E2 release estimate. B*E/n≈100 windows
for each historical class is a *single-case draw-lifetime mean* in this
simple random model, not the score-release maximum. Scheduling can bound
this tail but creates predictable reuse timing; no secrecy guarantee follows.

[OWNER-AUTO-PUBLISH-RETIRED-01](https://github.com/carbonphysicsai/Carbon/blob/eda5e5f55c1c3fae315e295ea8ed94f91d6d0fce/.agent/decisions/2026-10-07-OWNER-AUTO-PUBLISH-RETIRED-01.md)
requires retirement, every drawing window ended/revealed, signed provenance,
and exclusion of tuning/confirmation/study/EV custody. E1 authority explicitly
forbids any producer on that bank drawing a published case. Retain these
rules; never publish early just to shorten score lag. Cases or close
reconstructable descendants reused after publication would defeat sealing.
Apply the benchmark/novelty policy to new draws as well as exact identity.

Merkle commitments and shared packages establish integrity and validator
agreement; they do not prevent learning through repeated aggregate scores.
A score can leak membership, boundary patterns or useful gradients before
answers publish. After release, detailed answers plus past scores can
support reconstruction of remaining mixed-window components; all dependency
windows must be dead before release. Adaptive submissions and Sybils can
increase queries per case: E counts windows, not total model queries. Record
both exposure and permitted feedback/query budgets; thresholds and identity
policy are owner/security decisions. A sealed, unreported fresh canary can
test generalization, but reused or adaptive canaries lose that assurance too.
Maintain independent confirmation; do not call canary pass qualification.

[Dwork et al.](https://arxiv.org/abs/1506.02629) establish holdout-reuse methods
with specified adaptive-data safeguards. [Blum and Hardt](https://proceedings.mlr.press/v37/blum15.html)
analyze a leaderboard release mechanism. Neither proves Carbon's current
sealing/lag policy prevents overfitting. Delayed/coarsened disclosure,
submission query budgets and independently refreshed canaries are proposals
to evaluate, not silently installed statistical or economic policy.

## Refill cost: cases and questions are different units

For bank/stratum s, define distinct reference-bearing draw count n_s per
window, windows/day d_s, mean CPU-h per **offered** item c_s (including
lattice/refinement/retries), valid-live yield y_s, exposure E_s, capacity B_s.
At steady balanced retirement:

`new_live_s/day = d_s n_s / E_s`

`C_refill/day = sum_s d_s n_s c_s/(E_s y_s) + C_canary + C_overhead`.

Startup is `sum_s B_s c_s/y_s`; if c_s is measured per ready-live item,
do not divide by yield again. E changes steady refill, **not initial B**.
Finite horizons have integer/burst effects and startup leftovers. Per-solve
CPU-h = wall_s × actual occupied cores / 3600 summed over jobs, not elapsed
batch wall time. Queue/parallelization affect latency and utilization, not
this accounting identity. GPU work and per-container overhead are separate.
Failed-reference cost stays in c/y and typed failure counts; not candidate
failure and not permission to conceal population exclusions.

At a common illustrative n=100, y=1 (ASSUMPTION reference-ready comparison):

| Class | c per case CPU-h low/base/high | Startup at B low/base/high | Refill/window low/base/high |
| --- | --- | --- | --- |
| Battery, B=20n,E=5 | 0.02083 / 0.02528 / 0.03333 | 41.67 / 50.56 / 66.67 | 0.417 / 0.506 / 0.667 |
| Motor-like, B=10n,E=10 | 0.6 / 0.8 / 1 | 600 / 800 / 1000 | 6 / 8 / 10 |
| CFD, B=5n,E=20 | 2 / 6 / 20 | 1000 / 3000 / 10000 | 10 / 30 / 100 |

Battery base 91 CPU-s is public VALIDATOR-23 planning, with 75/120 CPU-s
ASSUMPTION endpoints. Motor endpoints are owner's approximate 0.6–1
core-h class description; 0.8 is an assumed midpoint. All CFD costs are
ASSUMPTION illustrations, not estimates measured for f17 or cooling. Actual
per-Challenge c_s/y_s requires a public rights-clear timing receipt.
Battery's actual historical pool draw is 98 distinct cases plus two hidden
duplicates; use 98 in refill, not 100. Current E1 authority's two 98-case
draws per rotation and 20 rotations/day give 3920 new cases/day; at 91
CPU-s this is 99.09 CPU-h/day (derived), absent yield/overhead/failure costs.
This is sourced planning arithmetic, not an operator utilization audit.

Q3 costs a whole question, not one reference solve. Public VALIDATOR-23
planning uses roughly 125 lattice/refinement solves at 91 CPU-s: 3.160
CPU-h/offered question, and describes 160 live questions needing roughly
700–800 CPU-h. That latter startup estimate includes unresolved planning
details not specified by the simple 125×91 calculation; preserve the source
estimate rather than silently reconcile it. [#1062](https://github.com/carbonphysicsai/Carbon/pull/1062)
uses owner-planning 0.73 CPU-h/offered question, with ASSUMPTION low/base/high
0.66/0.73/0.80. They are different question/lattice routes; do not present
either as measured current v3 cost or mix them to make a favorable quote.

For an explicit stand-in only, use valid-live yield low/base/high
0.5/0.5625/0.7 (ASSUMPTION). The base echoes public numeric resolution
27/48, **not measured bank admission**: settled NONE_FEASIBLE can resolve
but may not be bank-live under that question contract. Combining the
0.66/0.73/0.80 cost with favorable/base/adverse yield gives 160-live startup
150.86/207.64/256 CPU-h and 8-draw E5 refill 1.509/2.076/2.560 CPU-h/window.
Use the legacy route or actual staged costs separately if that law is used.
Reference cost on unresolved offered questions can differ from resolved
cost; record the joint cost/yield distribution and stratum coverage.

## Recommend per-Challenge E, with possible within-class variation

For owner refill budget R_s CPU-h/day after other banks/overhead and stable
draw rate d_s, lower exposure bound is
`E_cost = ceil(d_s n_s c_s/(y_s R_s))`.
For a required fresh unique-case rate J_s/day in the deterministic limit,
upper bound is `E_information <= floor(d_s n_s/J_s)`.
For maximum release lag L_s rotation units (after timers), compatible cohort
spacing g_s and active duration A_s:
`E_release <= 1 + floor((L_s-A_s)/g_s)`.
Require an integer E>=1 satisfying all bounds; thresholds, risk tolerances,
information targets, cadence and budgets are **HUMAN_INPUT**. If infeasible,
change cadence/budget/reserve or hold the Challenge; do not loosen hard
science limits. Full low/base/high input vectors propagate to cost/lag;
owner chooses a conservative cost/yield bound, not a fitted precision claim.

Let B_s cover simultaneous active draws plus reserve for measured high-end
refill lead time. A conservative planning inequality is
`B_s >= n_s active_windows_s + d_s n_s lead_days_s/E_s`, plus owner burst
reserve, where turnover is assumed balanced and occupancy bound may double-
count retired holders deliberately. Record solved-but-held versus drawable
inventory explicitly. Startup and reserve cannot be inferred solely from E.

Recommend varying E **by registered bank or predeclared stratum**, not by
which model just failed: expensive bulk references may tolerate more reuse;
high-value near-limit/rare regimes, fresh canaries, confirmation and fast
feedback need lower reuse or stricter query limits. CPU class alone cannot
choose E. Within-window mixtures complicate release lag and exposure-weight
bias. Prefer separate synchronized cohorts with fixed quotas and named
prospective rules. Unweighted repeated records overrepresent high-E strata;
keep P, sampling Q and evidence w separate and account for actual inclusion
probabilities. Do not opportunistically redraw difficult/unsafe questions or
choose E after viewing miner-specific score gains.

Measure public stand-in incidence/variance first on **frozen** models, then
separately track learning and fresh-canary drift. Report unique questions,
appearance multiplicities, invalid-reference exclusions, per-stratum coverage,
cluster CIs, feedback count, refill CPU-h/ready question and tail lag. No
public output may reveal protected IDs. The recommended statistical receipt
and parameter fields are in [cost-rule.json](cost-rule.json); it is not code
for deployment or an alteration of VALIDATOR-23's implementation.
