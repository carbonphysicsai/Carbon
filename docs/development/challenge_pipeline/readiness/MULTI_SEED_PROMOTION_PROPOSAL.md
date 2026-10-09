# READINESS-GAPS-01 V3: draft multi-seed promotion policy

**Status:** Test Lead working values (2026-10-09), for development waves only. Owner adoption into a frozen rule is still required. This document is not a registered promotion rule, does not pass readiness item V3, and grants no LIVE or qualification authority.

## Proposed evidence contract

Before claiming that a construction improves the incumbent, record a prospective policy version binding the Challenge, rule digest, member recipe digests, evaluation panel, seed generation and pairing, admissibility gates, decision-value metric, noise source, and the rule for missing reference or infrastructure outcomes. The same registered conditions and comparison budget apply to candidate and incumbent. No seed is chosen after its result is seen.

Rebuild each recipe at **at least five independently registered seeds per arm**, matched one-to-one between candidate and incumbent. Report the per-seed score and buyer decision outcome, the across-seed summary, the fraction passing every mandatory gate, and the uncertainty band from the declared resampling unit. A mandatory gate failure on **any seed in either arm** blocks promotion, regardless of the mean score. Reference and infrastructure failures remain typed and are excluded symmetrically, with the common resolved mask stated; they do not become gate failures.

For the working comparison, define each matched seed's improvement as incumbent exam error minus candidate exam error, so positive means the candidate improves. Bootstrap the **matched seed pairs together**, rather than resampling the two arms independently. For each bootstrap replicate, divide its mean paired improvement by its mean incumbent exam error; require the **95% lower bound of this relative improvement to be strictly above** `carbon.battery.exam.DEVELOPMENT_RULE["equivalence_margin_rel"]`. This uses the existing exam margin in its relative units; it does not change the frozen single-run `final_compare` rule or substitute a newly chosen margin. A zero or otherwise unusable incumbent denominator cannot establish this relative claim and remains inconclusive. An inconclusive band yields **NO_PROMOTION / MORE_EVIDENCE**, not a claimed improvement. Historical single-seed and v2 records retain their original interpretation.

## Working values and decisions still required before registration

| Input | Working recommendation | Authority state |
| --- | --- | --- |
| Minimum seeds and pairing | At least five seeds per arm, matched one-to-one. | Test Lead working value, development only |
| Claim and uncertainty | Bootstrap paired seed-matched improvement; its 95% lower bound must clear the exam's relative margin. | Test Lead working value, development only |
| Equivalence margin | Use `DEVELOPMENT_RULE["equivalence_margin_rel"]` in relative exam-error units. | Existing exam value; frozen-rule adoption remains owner-reserved |
| Gate verdict across seeds | Any mandatory gate failure in either arm blocks promotion. | Test Lead working value, development only |
| Bootstrap implementation and evidence identity | Register the seed-pair draw, resample count, resolved-mask rule, and exact exam rule identity before observing candidates. | `HUMAN_INPUT` |
| Required fresh confirmation evidence | State which protected role, exposure limit and common resolved mask support promotion. | `HUMAN_INPUT` |

The readiness runner must keep V3 at `REVIEW_REQUIRED` until the owner adopts a frozen policy and the required evidence is recorded. These working values alone are not that adoption or evidence.
