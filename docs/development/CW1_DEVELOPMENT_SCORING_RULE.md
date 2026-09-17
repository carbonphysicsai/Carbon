# Burgers DEVELOPMENT balanced rule v2

**Decision:** OWNER-C-W1-D3-DELEGATION-01. Final candidate iteration 2, frozen before V2 verification.
V1 is retained at commit ac4ce290 and in its signed derived report. Executable data: `carbon.scoring.development.RULE`; its
canonical SHA-256 binds every report. New measurements:
`carbon.c05.burgers-development-derived.v3`. No historical C-05 contract changes.

## One recommended objective

Preserve the initial condition, mean, maximum principle and viscous energy
trajectory on every sampled case and reconstruction. Among admissible methods,
reward accurate trajectories, accurate fluctuation-energy evolution and the
worst case. No soft gain buys relief from a mandatory failure.

Challenge burgers-dynamics-v1/1.0 and executable supervised-development.v2:
12 TRAIN / 12 EVAL / 12 STRESS, three replicas, 64 spatial points, 13 times.
This is the seen reduced development subset, not prospective population
confirmation. TRAIN labels only enter construction. EVAL/STRESS labels remain
evaluator-only. Original generator, cohort, reference method/settings, image,
resource/profile and signed source identities must match exactly. No change
to the all-burn publisher, official ScorePack or qualification boundary.

## Operators, units and blind spots

Binary64 evaluation of retained float32 predictions; equal-space periodic
quadrature and trapezoidal time integration on the actual nonuniform times.
Field error is sqrt(time-average spatial MSE) divided by the prescribed initial
fluctuation RMS, not a candidate-selected scale. Energy is L/2 times spatial
mean squared fluctuation. Energy-path error is RMS time error divided by the
prescribed initial energy. Both are dimensionless. Equal times are not assumed.

For smooth unforced periodic Burgers, multiply the equation by u minus its
conserved mean and integrate by parts: dE/dt = -nu integral(u_x squared) dx.
New integrated balance is max over sampled prefixes of abs(E(t)-E(0)+integral
dissipation dt), divided by prescribed initial energy. Trapezoid time error
and unresolved spatial modes remain; reference balance is a discretization
indicator, not a proven uncertainty bound. This underresolved diagnostic does not
determine v2 admissibility. The mandatory energy-path maximum compares sampled
energy against reference energy, with no numerical time derivative/integral. The periodic Fourier gradient
inherits the sampled representation and cannot detect subgrid error.

Historical `energy_dissipation_balance` is positive sampled energy increment:
zero establishes only no increase at sampled times. Historical `periodicity`
is closure of the same Fourier interpolant: numerical zero establishes an
identity of the representation, not correct dynamics. Neither earns quality
credit. Historical `weak_local_pde` is a midpoint sampled differential residual,
not a test-function weak formulation. New four-mode sine/cosine weak residual
integrates spatial derivatives by parts and time by trapezoid; diagnostic only,
since an error orthogonal to those tests can pass. Zero on any finite operator
establishes that sampled identity only, not a PDE solution or physical validity.

Compression/peak dissipation remain historical diagnostics; shared t=0 may
dominate extrema. New diagnostic time indices and energy trajectories explain
that mechanism. Half-time now explicitly reports observed/left/right-censored;
no crossing is not an event at the horizon. It is diagnostic, never a score
input, so missing a crossing cannot earn timing credit. Historical reports
remain readable under their original horizon-clipped contract.

## Provisional values and their bases

| Choice | Value / basis |
|---|---|
| Initial-condition maximum error / amplitude | Strictly below 32 float32 eps = 3.814697265625e-6. Representation-conversion allowance, deliberately distinct from physical tolerance; verify with controls. |
| Maximum mean drift and overshoot / amplitude | Each strictly below 0.01 in every case/replica. Provisional product choice: permit at most 1% of the physical amplitude budget for these conservation/envelope defects; not fitted to FNO observations or an industrial standard. |
| Maximum energy-trajectory error / initial energy | Strictly below 0.05 in every case/replica, including measured reference sensitivity. Provisional product budget: no sampled energy value may deviate by 5% of initial energy. Full integral balance is diagnostic because the retained reference time quadrature itself reaches 2.93% error; its former 2.5% gate-resolution requirement was rejected in iteration 2. |
| Reference field/energy sensitivity maxima | Each at most 0.0025, one quarter of the per-case noninferiority budget. Empirical resolution budget, not qualified uncertainty. Missing indicators withhold acceptance. |
| Practical score improvement | Strict gain above 0.005 after the uncertainty envelope: half a percentage point of the fixed score range. Provisional minimum useful development change, not a p-value or measurement floor. |
| Per-case noninferiority | At most 0.01 normalized field AND energy increase for every EVAL/STRESS case across all replica pairs, including reference sensitivity. Product protection against hidden subgroup losses. |
| Equivalence | Entire score-difference envelope within +/-0.005 AND mutual per-case noninferiority AND both admissible. Otherwise failure to resolve is not a tie. |
| Arithmetic floor | 128 binary64 eps, a defensive arithmetic guard, not physical/reference uncertainty. |

These values express a provisional engineering utility, openly authorized by
Ryan. Round product budgets are not represented as scientific derivations.
Calibration tests whether they detect declared failures; it does not establish
industrial adequacy. Values never depend on FNO-40/FNO-48 relative performance.

## Score and comparison

Per role and replica: A=1/(1+mean field error), P=1/(1+mean energy-path error),
R=1/(1+maximum case field error). Use existing A5 binary64 weighted geometric
arithmetic: S=P^0.25 R^0.25 A^0.5. Half the logarithmic sensitivity is allocated
to average accuracy, the other half equally to dynamics fidelity and worst-case
protection: provisional product composition, not learned coefficients. These
are new DEVELOPMENT scalar inputs, not fixture-origin A5 ScoreInputs.
Per-replica score is min(S_EVAL,S_STRESS); reported rank is the mean of three.
Range [0,1]. Finite bad predictions cannot exploit denominator choice. Failure
of a mandatory gate retains descriptive rank but is explicitly inadmissible.

Comparison envelope: [min challenger - max baseline, max challenger - min
baseline], expanded by twice (0.75 field sensitivity + 0.25 energy sensitivity)
and the arithmetic guard. Reciprocal/log transforms bound these sensitivities.
Cases are matched; replica indices are not presumed paired random seeds. All
cross-replica comparisons avoid fictitious case-by-replica independent samples.
No confidence level or population claim follows from three replicas. The range
does not bound unseen reconstruction variability. Admission is conditional on
this finite-cohort development robustness rule only.

Accept only if the lower difference bound exceeds the practical margin, every
case is noninferior, both sources pass mandatory conditions and empirical
reference resolution is adequate. C-04 primary quadrature refinement at
1024/2048/4096 points supplies per-case empirical field and energy sensitivity.
It shares method/implementation and is not an independent witness or rigorous
error bound; the acceptance claim is conditional on this development recipe. Symmetric robust loss is regression. Resolved
aggregate gains/losses with opposing cases are trade-offs. Unresolved envelopes
are indeterminate. Exact input equality can satisfy the explicit equivalence
rule; copying is never improvement or new reward credit.

Complete 72-observation rectangles are required. Missing, failed, nonfinite,
altered, incompatible, revoked, quarantined or superseded sources yield typed
input/eligibility failure, never a scientific zero. Censored timing remains an
explicit diagnostic and cannot masquerade as zero timing error. All versions,
source receipts, strategy/reconstruction, artifacts and cohort are bound.

Matched resource ceilings mean the same v2 2-CPU/4-GiB/no-swap, per-worker and
session limits and 32..64 training steps; actual step counts may differ within
that declared ceiling. No accuracy-per-dollar bonus or hidden normalization.
Report actual resources. A future efficiency contest needs its own rule.

## Prospective use, disclosure and reward

Retained FNO results are calibration/ranking only. Acceptance requires a frozen
rule/cohort/trust registration before BOTH new construction starts, a new source
association, and active C-06/C-10 state at use. New derived evidence links exact
signed input digests without rewriting them. Real observations remain real.

The C-07 disclosure owner exposes the rule, coefficients, limits, aggregate
EVAL/STRESS observations, score, admissibility and disposition. No case IDs,
labels, per-case results, coordinates, paths, seed commitments or credentials.
Fixed-cohort adaptive feedback is explicitly not hidden-exam qualification.

Only an eligible accepted report can enter non-paying simulation, with exact
rule/comparison, source holder, opening baseline, range [S0,1], one challenge
allocation and explicit simulation clock. Reuse C-REWARD's existing 24-hour
decay, gain, self-improvement and takeover arithmetic. Copy/replay cannot
refresh credit. Real and synthetic simulations have distinct provenance.
No chain writer, official eligibility, payment or settlement is introduced.

## References and remaining qualification

The energy identity above is an algebraic consequence under smooth periodic
assumptions; the implementation samples it. Cole-Hopf derivation context:
https://www.math.toronto.edu/ivrii/APM-textbook/Chapter9/L9.1.html .
Verification versus physical validation follows the distinction discussed by
NIST: https://doi.org/10.6028/NIST.IR.8298 . These references do not qualify Carbon.
Recommend Harshdeep review these provisional scientific/product choices.


## Trusted operator commands

The scoring operator uses the existing private source/configuration mechanism.
It creates C-06 signatures itself; the operator never edits a receipt or signature.
For the retained review, run in the Ubuntu checkout:

```bash
PRIVATE_CARBON_ROOT="$HOME/.local/share/carbon-testnet"
SCORING_ROOT="$PRIVATE_CARBON_ROOT/development-scoring-20260916/iteration-2"
uv run --locked --group chain python -m carbon.development_comparison.scoring_operator status --root "$SCORING_ROOT"
uv run --locked --group chain python -m carbon.development_comparison.scoring_operator report --root "$SCORING_ROOT"
```

Open `owner-scoring-report.html` or `.md` in that directory. Status rechecks
source lifecycle, quarantine, artifact associations, signatures and rule identity.
The signed derived report is `development-acceptance.json`; original source
receipts remain in their historical session directories.

For a separately authorized future experiment, prepare its authenticated session
and trusted keys first, then `freeze --root <new-private-root> --config <private-config>`
before either fresh construction starts. The configuration names `template_source`,
`quarantine_journal`, `reference_root`, and the `sessions` map of session roots to
trusted service configuration paths. After reconstruction, use `derive --root
<new-private-root> --baseline <signed-source> --challenger <signed-source>
--image-manifest <accepted-image-manifest>`. This invokes only the bounded derived
measurement carrier. Use `--resume-completed` only for reconciliation of a retained,
matching completed output; it does not authorize duplicate numerical dispatch.
`feedback` projects the allow-listed miner view. No command invokes a provider,
trains a model, registers an identity or writes the public chain.
