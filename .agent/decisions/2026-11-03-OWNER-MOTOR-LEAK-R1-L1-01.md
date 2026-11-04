# OWNER-MOTOR-LEAK-R1-L1-01: Motor extended-region leak: R1 for Motor 1.7, L1 for Motor 1.6

Date: 2026-11-03 (CST, ~10:33)
Status: DECIDED by the owner, directly in the Lead session (local_87151681-c66e-4949-a26c-23c4641b5722).
Owner's words: "Yes: R1 for Motor 1.7, re-sign a fresh hidden out-of-range extension before its pack is drawn, up to USD 35 of new rented solves inside the week's USD 250; and L1 for Motor 1.6, keep it running unchanged and flagged until 1.7 replaces it."

## Background (confirmed 3 Nov ~08:06)
- **The leak:** the public repo's scripts/validator_host_classes/version_overlay.json (Motor 1.6 baseline_box, since commit dcbae3547c / 1 Nov) equals the hidden Motor extended region (canonical 248460a6, file c3e41b52) on 16/16 sides.
- **Not exposed:** sealed cases, truths and seeds.
- **The sweep:** the TE's sweep of main (LEAK_SWEEP_MAIN_20261103.md) found no other leak.

## Decided
- **R1 for Motor 1.7:** a FRESH hidden out-of-range extension is re-signed before 1.7's pack is drawn. The ext-U / edge panel and the coverage-side solves are redone on it.
  - **Spend:** up to USD 35 of new rented solves, inside the week's USD 250.
  - **Inputs-only:** rented work gets inputs only, with truths to custody.
  - **Data already solved:** the old-region MOT-EXTU and COV17 data stay as evidence and are never rescored.
- **L1 for Motor 1.6:** it keeps running unchanged and flagged until 1.7 replaces it.
  - Records since 1 Nov carry the leak flag. Nothing is rescored.
  - The 1.6 door is not re-prepared onto a main that includes P1 before 1.7 replaces it.

## Mandatory (Validator; not a choice)
- **P1:** the extents leave tracked files (te/p1-motor-box 0da8f37c, FINAL). It lands on main only after the 4 crown flips. Its push comes to the owner then.
- **The new 1.7 extension's region record** stays in custody, referenced by sha only. It never goes into a tracked file.
- **A leak-guard test** is added: no hidden extents in tracked files.

## Extent rule values (~10:37 CST): DECIDED by the owner, values HELD IN CUSTODY
- The owner typed the range and distance for the fresh per-side extension in the Lead session.
- Per the Validator's 10:35 ruling, the values are recorded ONLY in custody, next to the new K_ext root, by the TL. This public record says "chosen" and nothing more. The board carries only the custody record's sha and the draw's canonical sha.
- **The rule's shape:**
  - 16 independent per-side draws in custody under a new key K_ext, inside the owner's range and at least his minimum distance from the leaked public margin;
  - each fresh edge is checked by the existing edge/U verdict, and a failing side falls back to the registered fallback margin;
  - the inner band, practice and verify sets do not move.

## Extent rule AMENDED (~10:48 CST): owner, Lead session; values HELD IN CUSTODY
- The owner typed an amendment, after Evidence's and the Validator's points.
- **What changed:**
  - 13 sides extend, not 16; the 3 held sides stay held;
  - the inner band stays at its old edge, so the 48 COV17 inner-band designs stay valid;
  - a failing side is re-drawn once lower, then held at the TRAIN edge with no extension. There is no known-number fallback.
- The values went to the TL for the custody record only. The public record says "amended" and nothing more.
