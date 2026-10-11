# Daily championship: good structure, incomplete error contract

**Independent DEVELOPMENT research review, 2026-10-11.** Recommend the shared
fresh batch and stored-artifact pairing, but **do not treat MARGIN-SIZING-04 as
validation of the combined Holm/carry-forward/alpha-investing championship**.
Its code implements a power formula and one known-normal carry process, not
that complete rule. No solver, spend or protected material was used.

The supplied null result reproduces exactly: **36/6,000 = 0.600%** over
**14 rounds at N=2,000**, with a **95% Monte Carlo Wilson interval
0.434–0.829%**. This is one fixed artifact/incumbent pair at alpha 0.05,
independent Gaussian increments and known SD. It is not the N=3,000
multi-contender championship's false-promotion rate.

Independent **ASSUMPTION stress scenarios**, 40,000 paths each, show the limit
of transferring that result. At N=3,000, the same proxy boundary crosses under
the null **8.31%** when actual SD is 1.5 times the proxy, **6.88%** with
Gaussian round correlation phi=0.5, and **8.53%** with rare positively skewed
batch shocks having the same marginal mean/variance. These are hypothetical
counterexamples, not measured Carbon distribution estimates. The raw public
case rows were requested; supplied SD summaries cannot establish tail or
dependence behavior. [Measured diagnostics and limits](REVIEW.md).

Required repairs/decisions:

- **One error budget.** Holm controls a fixed family's round only with valid
  p-values. Combining ordinary daily Holm, carry-forward and a fast lane needs
  an explicit joint budget. Daily 5% is not 5% over a campaign.
- **A genuine anytime contract.** The mixture needs a valid conditional variance
  proxy or a registered bounded-loss process. A sample SD alone is insufficient.
  Fix the artifact/incumbent pair, measurement, population and weights; a new
  incumbent creates a new hypothesis and consumes fresh budget.
- **Artifact identity is dedup, not a Sybil cure.** Many distinct near-copies
  still consume tests. Ordinary alpha-investing targets mFDR under its
  assumptions; it is not strong family-wise protection
  against any false crown, and no wealth ledger appears in m04.py.
- **Retire all scored cases after the round.** Lower-bound disclosure conveys
  more than a binary result; the proposed reuse allowance has no supporting
  leakage experiment. Gate/important-region evidence and costs are absent.

For a first implementation, recommend fixed-round Holm with a declared campaign
budget, or a single fixed-cohort anytime-Holm procedure after its per-pair
process is validated. Do not run both as separate routes at the full same alpha.
The detailed alternative and dynamic-entry ledger are in
[STATISTICAL_CONTRACT](STATISTICAL_CONTRACT.md).

**Useful gain:** recommend owner consideration of epsilon=0 for a
reference-relative DEVELOPMENT accuracy comparison, preserving hard gates,
until a positive value/resolution floor is evidenced. Sensitivity
**0/0.1/0.5%** is ASSUMPTION, not adoption. Detectable improvement is not epsilon;
accuracy gain still needs score-proof evidence to imply design value.

All production alpha, horizon, epsilon, no-harm limits and rollout remain
HUMAN_INPUT. The proposal is promising; the combined guarantee is unproved.
