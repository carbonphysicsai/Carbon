# Carbon: screen, final, artifact and reward are separate

Source snapshot `43f664319e1c2f977908186d7a017f2eb0771251`. All source constants
are fixed low/base/high triples. Inspection is read-only; no evaluation data or
operator state was accessed.

| Surface | What the pinned source does | Recommendation / gap |
|---|---|---|
| Screening | `exam.nominate` requires eligibility, same pool version, same device class, score `< incumbent*(1-margin)` and an important-region check | It compares aggregates without a paired uncertainty test. This is the owner's “unpaired screen” shorthand; the source already requires the same pool, so do not claim disjoint case sets |
| Margin | `equivalence_margin_rel = 0.056993107446249414`, displayed approximately 5.70% | Same setting feeds nomination and the frozen final. Split screen-cost policy, practical gain and inference confidence prospectively |
| Final test | Paired case differences, 4,000 percentile draws, alpha 0.05 (two-sided quantiles); n_min 30, important_min 10 | Minimum counts are availability checks, not power guarantees. Case-IID bootstrap does not cover bank/source dependence or rebuild uncertainty by itself |
| Final improvement | Interval excludes zero **and** point gain exceeds practical margin | Current rule does not require the whole interval beyond that margin. Proposed `LCB > delta_useful` is a different, stricter estimand and must be explicit |
| Regional rule | Significant practical important-region regression blocks; too few important cases blocks | Failure to detect regression is not affirmative noninferiority. A required no-harm bound and its tolerances remain science/owner input |
| Artifact | `process_final` reconstructs both recipes under the frozen matched training seed and retains final-specific models | VALIDATOR-32's stored-both proposal would test actual deployed artifacts; it would not prove recipe repeatability |
| Changed incumbent | Final is withdrawn if the frozen incumbent has changed | Keep. A stale duel cannot automatically depose a different artifact |
| Copy identity | `daemon` records priority for identical recipe digests across hotkeys | Digest duplicate handling is useful but not a functional-distillation detector; rights and independence are separate questions |
| Validator parity | Shared batches, references, reconstruction seed and device identities are checked | Keep identical evidence/rule pins. Statistical uncertainty is not a license for validator disagreement |
| Weight eligibility | Decided promotion and first-incumbent paths are distinct from screen scores; same-party reset is separately controlled | Do not change payout, decay or rights when changing scientific comparison |

Primary sources: [nomination](https://github.com/carbonphysicsai/Carbon/blob/43f664319e1c2f977908186d7a017f2eb0771251/carbon/battery/exam.py#L897),
[paired comparison](https://github.com/carbonphysicsai/Carbon/blob/43f664319e1c2f977908186d7a017f2eb0771251/carbon/battery/exam.py#L761),
[frozen recipe and matched rebuilds](https://github.com/carbonphysicsai/Carbon/blob/43f664319e1c2f977908186d7a017f2eb0771251/carbon/battery/daemon.py#L1408),
[shared-key parity](https://github.com/carbonphysicsai/Carbon/blob/43f664319e1c2f977908186d7a017f2eb0771251/carbon/challenge_validator/acceptance.py),
[eligibility contract](https://github.com/carbonphysicsai/Carbon/blob/43f664319e1c2f977908186d7a017f2eb0771251/.agent/tickets/VALIDATOR-14_testnet_winner_weights.md).

## A small gain cannot currently pass even without noise

For lower-is-better score S, define gain `g=(S_inc-S_chal)/S_inc` only where the
denominator is positive. Under identical hypothetical records, gains below the
registered margin fail nomination; in the final they also cannot be “better”
under its point-margin condition. More cases shrink uncertainty but cannot
remove this deterministic barrier. Relative score gain is not automatically
equal-budget design gain or customer value.

Illustration **ASSUMPTION**: normalized incumbent score low/base/high = 1/1/1;
true relative gain low/base/high = 0.005/0.01/0.02 (0.5%/1%/2%). All are below
the sourced margin; all fail the ideal noise-free screen and final. This is an
algebraic example, not observed Carbon performance. Near a zero denominator,
use a registered absolute/decision-unit contrast rather than unstable ratios.

The existing [incentive simulation](https://github.com/carbonphysicsai/Carbon/blob/43f664319e1c2f977908186d7a017f2eb0771251/docs/development/incentive-mechanism-sim/README.md#L44)
already gives a conditional path-dependence counterexample: repeated admission
opportunities seat an intermediate model, after which the best model's smaller
gain falls below the bar. Its normal-noise assumptions and public rebuild proxy
are not measured live takeovers. This report uses the mechanism, not its
conditional target shares as a forecast.

## VALIDATOR-32 draft boundary

The owner's prompt says “stored rebuilds on both sides and a looser screen.”
No corresponding public ticket/file or open PR was present in the checked main
tree/open list. That is **OWNER_CONTEXT / DRAFT_NOT_VERIFIED**, not a code review
of VALIDATOR-32. Reconcile the final draft against this crosswalk before adoption.

Stored-artifact comparison is appropriate if the purchased product is the exact
trained model. Keep independent repeatability evidence for the submitted recipe
as a separate product/readiness condition; do not quietly require a different
training draw to win the artifact duel. If the owner instead wants a comparison
of construction methods, integrate independent rebuild seeds and case blocks in
the estimand, evidence budget and hierarchy of resampling. Neither interpretation
is earned by merely changing a model-loading call.
