# OWNER-INFO-BUDGET-DATA-CHANNELS-01: the 32 KiB recipe-information budget counts only data-like channels

Date: 2026-11-02 (CST), ~12:10
Status: DECIDED by the owner, directly in the Lead session (local_87151681-c66e-4949-a26c-23c4641b5722).
Owner's words: "Yes: the 32 KiB recipe-information budget counts only data-like channels (constants + static integers), not graph topology, for the new versions; the from-scratch rule stays."

## Context
- Graph audit #6 (codex-queue/reports/GRAPH_LIMITS_AUDIT_20261101.md): under accounting v6 the budget is the zlib-9 size of the WHOLE canonical recipe, topology included (carbon/level4/allowlist.py:257 V6_CONSTANT_BYTES; validate.py:252, :375 fitted_info_over_budget). Physics graphs carry structure (time stepping, solvers, schedules) with no fitted information, so topology alone uses most of the budget. A miner confirmed this on the board (2 Nov).

## Decided
- **For the new versions** (RB 2.0, BT 3.0, Motor 1.7, Cooling 1.8, and later versions on the new allowlist), the 32 KiB budget counts only data-like channels: constants and static integers. Graph topology (nodes, wiring, op choices) is not counted.
- **The from-scratch rule stays:** no pretrained weights may be smuggled in. Constants and static integers remain counted, so it still binds.
- **Published versions are unchanged.** This is a prospective accounting version, and nothing graded is rescored.
- **Implementation:** a new accounting version (Receiver Engineer / TE), with tests showing a large-topology graph with small constants passes, a large-constant graph is refused fitted_info_over_budget, and published versions keep v6. Validator receipt, then main on the owner's words.
