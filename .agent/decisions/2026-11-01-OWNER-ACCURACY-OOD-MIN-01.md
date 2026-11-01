# OWNER-ACCURACY-OOD-MIN-01: accuracy = the worse of in-range and out-of-range, scored per region class (new versions)

Date: 2026-11-01 (CST)
Status: DECIDED by the owner, directly in the Lead session (local_87151681-c66e-4949-a26c-23c4641b5722).
Owner's words: "Adopt the accuracy-side change for new versions: accuracy = the worse of in-range and out-of-range (scored per region class), more cases where the fit loses, per-class floors reported for now; fall back to the milder version if the dry run shows it's too noisy."
Basis:
- `codex-queue/reports/ACCURACY_OOD_OWNER_CHOICE_DRAFT_20261101.md` (Exam Quality, Validator-accepted; sha256 0f0fcb88691127dca96f186d832459ba533ba20cc4e1f2129da19448a8d1d1aa as reported by Exam Quality).
- The direction record OWNER-OOD-GENERALIZATION-DIRECTION-01 (03f4c68f).

## Decided (next versions only; nothing graded is rescored; ships only as new versions)
1. Out-of-range accuracy is scored per region class and averaged across classes. Classes with fewer than N cases pool into "other OOD"; N is set in the version plan, not invented here.
2. A = min(in-range, out-of-range).
3. More accuracy cases in the classes where the fit loses (off-step, shell edge, regime change, neighbour task). They are drawn class-level from the sampler only, and the adopted caps are unchanged.
4. Per-class floors are REPORTED against the TRAIN-kernel. A hard "not crowned" floor is a later owner pick, made from data.

## Conditions
- Fallback, per version: "min" applies only if the dry run shows class-mean noise below margin_N. In that case margin_N is recalibrated, and a tuned learner must still clear the moved minimum. Otherwise that version uses the milder form: items 1 and 3 with the current averaging.
- The rule is disclosed to miners.
- No gate change. The physics gates already run on every out-of-range answer (OWNER-GATES-ON-POOL-3A-01).
- The change never delays a version.

## Amendment (same day, owner, Lead session)
Owner's words: "Amend the accuracy-side change: the min rule applies to a version only if its separation read shows a trained learned model clearly beats the fit out of range; if nothing beats the fit there, fix the training coverage or physics levers first."
Context: the Lead raised concerns before this amendment. Learned operators may also extrapolate badly; the outer shell is the worst-covered part of TRAIN (TL fill-distance read, 1 Nov); and min() adds noise on small classes.
- Precondition for item 2 (A = min): that version's S4a separation read shows a trained learned operator clearly beats the TRAIN-kernel out of range. "Clearly" is defined by the Validator from the read's own uncertainty; no value is invented here.
- If nothing beats the fit out of range, the min rule is not applied. The fix goes first to the exam's inputs: TRAIN coverage near the edges, and/or the physics levers given to miners. That fix ships as a new version.
- Items 1, 3 and 4 and the noise fallback are unchanged.
