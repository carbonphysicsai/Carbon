# OWNER-IMAGE-MOVE-RESEAL-D-01: re-seal the 4 live packs on the M3 image (route D)

Date: 2026-11-02 (CST)
Status: DECIDED by the owner, directly in the Lead session (local_87151681-c66e-4949-a26c-23c4641b5722). Supersedes route (b) of OWNER-IMAGE-MOVE-PLATFORM-EQUIVALENCE-01 for the live packs.
Owner's words: "Yes: re-seal the 4 live packs on the M3 image (route D, existing build path, minimums proven bit-equal); kings keep crowns and clocks, Score to beat unchanged, Ladders and daily allowances start fresh (old rows kept, nothing rescored); each king is regraded on the re-sealed pack on a spare root before its door switches."

## Context
- The equivalence-record code (09db1215) would move every live pack's producer_digest.
- The config route (each door's inference on 97b1eda2) was refused at the receiver's source-revision check on all 4 doors.
- The TL's 4/4 calibration reruns showed the minimums are bit-equal on M3 582fcb9a (Validator receipt, note 6bc31c7e).
- Graphite's code read of main 594361ac, ruled by the Validator, found the miner-visible effects:
  - kings keep crowns and their crown and payout clocks;
  - Score to beat is unchanged;
  - each Ladder starts fresh;
  - daily exam allowances reset.

## Decided
- Each of the 4 live packs (F08 1.7, F02 2.5, Motor 1.5, Cooling 1.6) is re-sealed on the M3 image through the existing baseline_minimums build path. There is no new code, and the registered minimums are carried exactly, proven bit-equal.
- **Before a door switches,** the TL regrades that door's king on the re-sealed pack on a spare root. A king that can't be regraded stops that door's switch and comes back to the owner.
- **Ladders and daily allowances start fresh.** Old rows are kept and nothing is rescored.
- **Zero downtime:** each door is proven on a spare port first, switched door by door, and rolled back on failure.

## Amendment (2 Nov ~12:05 CST, owner, Lead session)
The owner chose "Wait for Tuesday" (AskUserQuestion), for the case where the TL's 30-minute read-only check finds no existing trigger that opens all owners at start on the Motor, Cooling and F02 new roots.
- Those three doors stay on today's image until Tuesday's Receiver Engineer fix (re-bind or replay on an image move).
- Miners never re-stage. F08 stays switched.
- The crown-average switch-on waits for the rest of the move.

## Update (2 Nov ~12:30 CST)
The TL's read-only check found the trigger. advance()'s first pass opens every owner with a carried submission (lean_recipe ~l.606); Motor's first pass is just slower. A replay with a settle-wait gave Motor 14 owners, 8/8 EQUAL. All 4 doors therefore proceed as F08, with no miner re-stage and without waiting for Tuesday. The owner's condition is met.
