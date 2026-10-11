# Carbon: screen, final, artifact and reward are separate

Initial source snapshot `43f664319e1c2f977908186d7a017f2eb0771251`, reconciled
with `0e5eb8403fdc043e9d4e6c1f39a8897710c08f30` before handoff. The latter adds
the owner-decided v3 registered score and gate; it preserves the relative
margin, paired accuracy final and fresh recipe rebuilds. All source constants
are fixed low/base/high triples. Inspection is read-only; no protected
evaluation data or operator state was accessed. This is source behavior, not a
claim that a particular rule is deployed or scientifically qualified.

| Surface | What the pinned source does | Recommendation / gap |
|---|---|---|
| Screening | v2 `exam.nominate` uses lower-is-better accuracy loss; new v3 `nominate_registered` uses registered higher-is-better A-Q `> incumbent*(1+margin)`, its gate and the v2 important-region guard; both require the same pool version and device class | Aggregate nomination lacks a paired uncertainty test. This is the owner's “unpaired screen” shorthand; do not claim disjoint case sets. A-Q includes Q3 only here |
| Margin | `equivalence_margin_rel = 0.056993107446249414`, displayed approximately 5.70% | Same setting feeds nomination and the frozen final. Split screen-cost policy, practical gain and inference confidence prospectively |
| Final test | Paired case differences, 4,000 percentile draws, alpha 0.05 (two-sided quantiles); n_min 30, important_min 10 | Minimum counts are availability checks, not power guarantees. Case-IID bootstrap does not cover bank/source dependence or rebuild uncertainty by itself |
| Final improvement | Interval excludes zero **and** point gain exceeds practical margin | Current rule does not require the whole interval beyond that margin. Proposed `LCB > delta_useful` is a different, stricter estimand and must be explicit |
| v3 final gate / quantity | OWNER-BATTERY-V3-FINALS-01 keeps the v2 paired accuracy final and adds the challenger's registered candidate gate on that fresh batch; Q3 is not evaluated there | Respect the adopted development contract. Decision-value finals would need separately authorized measurement/producer changes; this survey proposes no runtime override |
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

Reconciliation sources: [owner's v3 finals decision](https://github.com/carbonphysicsai/Carbon/blob/0e5eb8403fdc043e9d4e6c1f39a8897710c08f30/.agent/decisions/2026-10-11-OWNER-BATTERY-V3-FINALS-01.md),
[registered nomination and v3 rule](https://github.com/carbonphysicsai/Carbon/blob/0e5eb8403fdc043e9d4e6c1f39a8897710c08f30/carbon/battery/exam.py),
[registered screening and final gate](https://github.com/carbonphysicsai/Carbon/blob/0e5eb8403fdc043e9d4e6c1f39a8897710c08f30/carbon/battery/daemon.py).
The registered candidate is deployment-bound. The owner decision specifies
`G-FEAS/A-Q>@0.05`: exactly 0.05 passes; these are fixed sourced low/base/high
0.05/0.05/0.05, not new research choices. The feasibility gate does not remove
either improvement margin and does not independently prove physical safety.

## A small gain cannot currently pass even without noise

For v2 lower-is-better loss S, define gain `g=(S_inc-S_chal)/S_inc` only where
the denominator is positive. For v3 higher-is-better registered score R,
nomination instead uses `g_R=(R_chal-R_inc)/R_inc`. Gains below the margin fail
their respective screens. Independently, the final accuracy gain below its
point-margin cannot be “better.” There is no assumed identity between A-Q gain
and accuracy gain. More cases shrink uncertainty but cannot remove these
deterministic barriers. Neither relative gain is automatically equal-budget
design gain or customer value.

Illustration **ASSUMPTION**: normalized incumbent score low/base/high = 1/1/1;
true relative gain low/base/high = 0.005/0.01/0.02 (0.5%/1%/2%). Consider the
screen-score and final-accuracy scenarios separately: each is below its sourced
margin and fails even without noise. This algebra does not assert that one
model has equal improvements in both quantities, and is not observed Carbon
performance. Near a zero denominator, use a registered absolute/decision-unit
contrast rather than unstable ratios.

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
