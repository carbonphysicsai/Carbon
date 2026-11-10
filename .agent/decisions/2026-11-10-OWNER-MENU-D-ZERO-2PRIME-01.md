## 2026-11-10 — OWNER-MENU-D-ZERO-2PRIME-01: rule 2' for a menu-D version reads the menu's zero

Date: 2026-11-10 (CST)
Status: DECIDED by the owner, directly in the mc-exam-B session (local_a8a7a49e), Tue 10 Nov ~06:21 CST: he approved the text in AskUserQuestion and then typed it.
This record holds his words and their plain meaning only. It contains no hidden values: no thresholds, seeds, region bounds or case inputs.

## The owner's words (typed, verbatim)
"For a version graded by menu D (Motor 1.8, Cooling 1.8, and any later version registered with a menu), requirement 2' is met by the best-of-three zero sealed in each menu record, registered in that version’s fit_breaker block; the grader’s own d_zero stays unset for those versions."

## What it rests on
- The text is Validator-2B's engineering ruling, TEAM_BOARD Tue 10 Nov 05:45 CST ("PATH (ii)"): for a version with a registered menu block, `pool_exam` replaces every target d with min(menu D, C), so `optimizer.d_zero` grades nothing.
- Carbon Validator-B's science ruling, `codex-queue/reports/D_ZERO_MENU_2PRIME_RULING_20261110.md` (sha256 908e8fe2214ba1bae244c2b97dc4faf4a5a2ac64649ac651304e1746fb65576a): the menu zero meets the intent of 2' (OWNER-EXAM-DESIGN-DECISIONS-BATCH-01) under its conditions (a)-(f).

## Plain meaning
- For Motor 1.8, Cooling 1.8 and any later version that registers a `menu` block, the fit-breaker rule 2' (D's zero is the best of the fit's pick, TRAIN's best design, and the engineer shortcut where screened) is met by the zero sealed in each menu record.
- That zero is registered in the version's `fit_breaker.d_zero` block: kind best_of, its components, source menu_records, the hardness proof sha, the fit-panel (arms) sha and one zero-record sha per menu task.
- The grader's own `optimizer.d_zero` stays unset for those versions (one zero only).
- `tests/cpu/test_fit_breaker_conformance.py` (amendment 2) checks this registration and needs this record in the tree. Conditions (a)-(c), that each record's arms hold the fit panel and its s_zero equals its zero record, are a custody check in the version Validator's receipt. `carbon/scoring/menu_score.py` refuses a record with no arms.
- A version without a menu block (RB 2.0, BT 3.2 today) is unchanged: it still needs the best-of zero in the grader, or its own owner record for no D.
- It changes no threshold, value or live grade: no version on main registers a menu block.
