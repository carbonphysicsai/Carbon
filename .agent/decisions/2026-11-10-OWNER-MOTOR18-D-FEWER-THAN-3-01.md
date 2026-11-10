## 2026-11-10 — OWNER-MOTOR18-D-FEWER-THAN-3-01: Motor 1.8 design value may seal on fewer than 3 menu tasks

Date: 2026-11-10 (CST)
Status: DECIDED by the owner. Both sets of words below were typed by him in the session named, and both are carried in codex-queue/reports/DECISION_LEDGER_20261105.md (the entries cited).
This record holds his words and their plain meaning only. It contains no hidden values: no thresholds, seeds, region bounds, case inputs or design values.

## The owner's words (typed, verbatim)
1. Mon 9 Nov 2026 ~06:1x CST, typed in the Lead session (ledger entry "2026-11-09 06:1x CST | Motor 1.8 design value"; option (c) of Carbon Validator-Motor's block MOTOR18_D_OWNER_BLOCK_20261109.md, sha256 prefix 935227b7):
   "Motor 1.8 design value: run tasks 3 and 4 under the fewer-than-3 exception as in (a); also apply Cooling’s option A to Motor tasks 2, 5 and 6 (same 75-then-50 order, hardness check only), launched before 09:00 Mon, and add any that pass every check by Tue 12:00; drop the exception label if Motor reaches 3 tasks."
2. Tue 10 Nov 2026, typed in the mc-exam-B session (ledger entry "2026-11-10 06:4x CST | Motor 1.8 D4 best-known + menu-D 2'", item (1)):
   "Motor 1.8 design value: task D4 may use its best-known optimum (BEST_KNOWN, not CONVERGED), labelled ‘best-known optimum’ in the seal record; Motor D seals on the tasks that pass every check by Tue 12:00, under my fewer-than-3 exception."

"The fewer-than-3 exception as in (a)" names option (a) of that block: Motor D on the tasks that pass, with every one used every epoch, under the label "D on fewer than 3 tasks: weaker against tuning".

## Plain meaning
- Motor 1.8's design value (menu D) may seal on fewer than the 3 menu tasks `carbon.scoring.pool_menu.MIN_TASKS` requires: on the tasks that pass every check by Tue 10 Nov 12:00 CST.
- While it has fewer than 3 tasks, it carries the label "D on fewer than 3 tasks: weaker against tuning". If Motor reaches 3 tasks, the label is dropped and this exception is not needed.
- Task D4 may use its best-known optimum (status BEST_KNOWN, not CONVERGED), labelled "best-known optimum" in its seal record.
- If no task passes, there is no Motor D (option (a)'s rule): this record does not let D seal on zero tasks.
- This is the id that Motor 1.8's registered `menu.min_tasks_exception` names (`scripts/validator_host_classes/pool_constants.json`), only when it seals on fewer than 3 tasks.
- It applies to Motor 1.8 only. Cooling 1.8 needs its own record.
