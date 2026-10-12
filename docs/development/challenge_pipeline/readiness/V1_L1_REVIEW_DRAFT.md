# V1 at Level 1: review DRAFT (not signed; the reviewer is the Test Lead)

Status: **DRAFT by the Graphite Testing Manager, 2026-10-12. This is not a review record.** It is deliberately not
`reviews/V1.json`: until the Test Lead rules and signs a review that names level 1, gate item V1 at Level 1 reads
REVIEW_REQUIRED (the automated half passes; the existing `V1.json` names level 0 only).

## What the report is

`carbon/challenge_pipeline/readiness/battery-fastcharge-ageing-development-v1/q1_report.L1.json`, built by the executor
(sha256 `5b3ba57430ba2a0087626b249ab9afbd576edebed2706187654d5786103dacf7`, byte-identical to the executor's file).
Reference provenance `EV4_REFERENCE` (the committed EV4 decision references, digest `ff10f9ae...436cb`), decision study
`ev4-dev-proof-l1-v1`, resolved on 7 of 12 development scenarios, 20 of 20 members eligible, all RECONSTRUCTED.

| Measure | Value |
|---|---|
| Kendall tau-b | 0.467 (band 0.0: one seed per recipe, a single panel) |
| Spearman rho | 0.659 |
| Top-1 overlap (by score vs by value) | 0 |
| SCORE_VALUE_DIVERGENCE conditions | 16 of 20 members (value noise band null, so any gap fires) |

Level 0 for comparison: tau-b -0.473, rho -0.539, 8 members. V1 is a measurement, not a threshold: a within-noise or
negative tau is recorded, not a blocker.

## The mixed scoring basis (the decision the review must make)

The 20 members do not share one score basis:

- 14 members carry the **Graphite frozen-rule pod score**: nine `l1-D-913bf188-p-*` proposals and five `stage-a-*` bundles.
- 6 members carry a **Launchpad rehearsal practice-feedback v3 aggregate under an unnamed rule**: `minerH-bsub-8df17aba-s0`,
  `minerH-bsub-9a658866-s0`, `minerH-bsub-b1d1f99f-s0`, `minerI-bsub-925d55a1-s0`, `minerI-bsub-e8efce9a-s0`,
  `minerI-bsub-ed8a517f-s0`.

tau and rho rank all 20 scores together, so a difference between the two rules enters the correlation. The six Launchpad
members sit far below the rest in score (-0.17 to -0.54, against -0.045 to -0.068), so they drive much of the rank order.
Five of the 16 divergences are Launchpad members.

The review must either:

- (a) **accept the basis**, stating that the V1 claim is a measurement over a mixed panel and naming the six as a different
  rule; or
- (b) **require a same-rule recompute** of the six anchors under the frozen rule before the level-1 report counts.

Nothing here chooses between them. If the Test Lead rules (b), the executor recomputes the six and the report is rebuilt
with `readiness.q1 build --level 1`; V1 stays REVIEW_REQUIRED until then.

## Draft text for the review notes (for the Test Lead to keep, change or reject)

> Level 1, PASS-or-FAIL pending ruling on the mixed basis. Measurement over 20 reconstructed members on the EV4 references
> (7 of 12 scenarios): tau-b 0.467, rho 0.659 (one seed per recipe, band 0.0), top-1 overlap 0, 16 divergences. Fourteen
> members are scored by the Graphite frozen rule and six by an unnamed Launchpad practice-feedback v3 aggregate. Level 1
> remains an alignment measurement, not improvement hunting.

Fields a signed `reviews/V1.json` for level 1 would need (`level: [1]`, `item: V1`, `decision`, `reviewer`, `date`,
`evidence` with this report's file digest) are the Test Lead's to fill; none is filled here.
