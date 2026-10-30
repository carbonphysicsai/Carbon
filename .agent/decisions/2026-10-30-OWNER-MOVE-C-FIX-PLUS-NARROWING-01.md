# OWNER-MOVE-C-FIX-PLUS-NARROWING-01: one more validator image move (Move C) carries the official GPU catalog re-expansion fix and the image-input narrowing

Date: 2026-10-30 (CST)
Status: DECIDED by the owner, directly in the Validator session (local_9d14c86b-b50e-4cf2-a2ef-5c69ad1ed1e0); relayed by the Validator to the Lead, who records it here.
Owner's words: "Fix + narrowing (Recommended)"

## Context

On the Move B install (public main 418ce0de6), all three reference-model baselines (Motor 1.5, Ribbed Bracket 1.7, Burst Thermal 2.5) were admitted and rebuilt on GPU. Then official auto-grade failed at retention with `catalog_reexpansion_differs`. Retention re-expanded the catalog submission with the CPU expansion (`expand()`), while the official grade used the GPU twin (`expand_official`). No test covered an official GPU catalog grade through retention. As shipped, no catalog submission could be officially graded on GPU. The Validator confirmed this from the box run and the Test Engineer's code check.

## Decided

- Move C = public main 418ce0de6, plus exactly:
  - the Test Engineer's `check_reexpansion` fix (carbon/backbone_catalog/served.py, its two call sites, and tests): when the CPU expansion differs, it re-expands with the twin the catalog pins for the retained runtime; tampering still refuses;
  - the image-input narrowing (week-1 update item 1, aed49de2 line), rebased on the fix, under the Validator's conditions: a canonical run, a build-time import smoke, a box trace for every job kind, a shell-equals-Python digest test, and an installed-commit record;
  - the already-receipted scripts and tests batch: 84de5ef24 door tests, ed5e194bb pack-set fixture, 878c67ef4 receiver GPU-twin staging.
- Nothing else. The other week-1 items stay in week-1.
- Everything bound to the Move B image on the box is void after the move: calibration packs, baseline grades and the Cooling recalibration. Box work holds until Move C is installed.
- Narrowing moving into launch supersedes its week-1 timing under OWNER-NARROW-IMAGE-INPUTS-FIRST-01.

## Bounds

- Sets no score, threshold, margin or economics. Recalibration values are measured as before (OWNER-RECAL-FEWER-REPEATS-01 applies).
- Every exam pack is rebuilt on the Move C image, and the owner's copy OKs are asked again.
- The push to public main needs the owner's word in the PR Head session.
