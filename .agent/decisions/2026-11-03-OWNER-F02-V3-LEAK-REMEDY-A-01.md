# OWNER-F02-V3-LEAK-REMEDY-A-01: Burst Thermal 3.0 leak remedy = option A (fresh custody extension) + T8 re-pick

Date: 2026-11-03 (CST, ~15:39)
Status: DECIDED by the owner, directly in the Lead session (local_87151681-c66e-4949-a26c-23c4641b5722).
Owner's words: held in custody (they contain hidden values). The TL's custody record names them by sha.

## Kind of decision (no values; per the Validator's 3 Nov rule: tracked owner records carry the kind + digest only)
- **What happened:** two decision records pushed to public main on 3 Nov exposed BT 3.0's extended-region shape and the T8 corner. They are forward-redacted (PR Head 0a34acac); history is not rewritten.
- **Option A, chosen:**
  - a fresh hidden extension is drawn in custody under a new custody key, for the sides that extend, inside the owner's range and minimum distance;
  - a failing side is re-drawn once lower, then held;
  - the held sides stay held;
  - spend is capped by the owner's figure;
  - the edge/U jobs and the coverage side designs are redone on it, while TRAIN, the U panel, the gate probe and the inner band are unaffected.
- **T8:** the hot corner is re-picked in custody, at a new custody-random position of the same size. The TRAIN corner exclusion is recomputed.
- The old region and corner are retired as history. Nothing graded is rescored.
