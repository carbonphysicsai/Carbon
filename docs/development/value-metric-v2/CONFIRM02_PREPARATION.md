# CONFIRM-02 and Track A preparation on sealed plating v2

**Scope:** development preparation only. This page does not launch a pod, draw a sealed question, run a solver, authorize spend, select a score rule, or declare a final-check result. The `battery-plating-ref-v2` public label digest is `cac1e23001c227d9221653b2a90cee4755f62ca06fec58305d11cb9cba510069`. Its 103 pending and 108 solved-but-UNRESOLVED labels remain unresolved; the 1.0 mV band governs until a prospective owner decision changes it.

## Copied operator-sheet correction

The owner-provided copy `codex-queue/inputs/operator/SCORE_PROOF_CONFIRM02_RUNPOD_SHEET.md` was locally corrected. It is **outside the tracked repository** and is not a change to the living original on the owner's machine. Before host execution, the owner must sync the correction to that original and re-check every gate there. The required C0 substitutions are:

| Old | Corrected |
|---|---|
| `producer-code-r8.4`, `/opt/carbon-r84`, `R84` | `producer-code-r8.6`, `/opt/carbon-r86`, `R86` |
| Clone revision printed but not asserted | `test "$(git -C /opt/carbon-r86 rev-parse HEAD)" = e9a28008b3975c3aaa93b710b6f623221241c2eb` before any downstream step |

The r8.6 annotated tag object is `d590f44938b110191f7e0c532716faf4a8ec812d`; its target commit is the exact C0 guard above. The watchdog source SHA256 remains `eba55521a397574560e75ee50be6ad2b625f737a11d44568d00436c093bc90e8`. The corrected copy has no r8.4/r8.5 path or tag references. `python -m scripts.dev.battery.confirm02_sheet_preflight --sheet <copy>` checks seven static invariants and refuses stale release pins, a missing exact-commit assertion, a missing public dry question or a missing final-look command. It **never runs** a command from the sheet.

## Stand-in rehearsal and limits

The public fixture stand-in ran 61 tests covering the new release-preflight and bank-cost negative controls plus existing public score-proof draw/refinement, sharded transfer/merge, watchdog and score-proof paths. No reference solver, sealed draw, pod or AX42 step ran. This is a local plumbing rehearsal, not the full host dry pass in sheet step 5, throughput measurement or custody acceptance. The owner-side host-key, pod, throughput, teardown and final-look gates remain mandatory and unrun.

## Track A sizing input

`python -m scripts.dev.battery.plating_v2_bank_cost --pdd-total 8390 --action-condition-solves N` accepts the actual prospective count `N = |Q| × |A| × c`. It verifies the exact committed public D3 v2 label and cost-record digests, requires `rule ∈ V2_RULES`, recomputes labels and counts by `source`, never by ID prefix. The **full** PDD v2 window is 695/8,390 = **8.28 %**: 611 solved plus 84 pending. The earlier 7.28 % (611/8,390) omitted pending cases, and 3.30 % covered a still narrower interval. The denominator 8,390 is owner-supplied in the work queue; it is an explicit CLI input because the label file alone does not register the denominator.

Public D3 means are 288.52 CPU-s at mesh160 (669 solves), 52.09 at mesh80 (67) and 16.33 at mesh40 (67). The v2 10 % convergence trigger needs **both** mesh40 and mesh80 to measure order. For an illustrative `N=1,000`, the **incremental** plating work is 6.80 CPU-h at the public share, or 82.05 CPU-h if every action-condition lies in-window. These are arithmetic sensitivity results, not a future-bank estimate or an approved figure. The base reference solve, actual bank-window mix, refinement failure/retry allowance, host wall time and price must be supplied by Data Collection before the owner sees a spend figure. A bank concentrated near the limit can approach the all-in-window case. No sealed bank sizing or host work was performed here.

Track A step 5 remains an owner-run sealed final-check. The preparation does not change its score or look policy.
