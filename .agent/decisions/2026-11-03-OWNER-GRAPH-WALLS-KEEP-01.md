# OWNER-GRAPH-WALLS-KEEP-01: keep the graph build and task time limits as registered for now

Date: 2026-11-03 (CST, ~10:34)
Status: DECIDED by the owner, directly in the Lead session (local_87151681-c66e-4949-a26c-23c4641b5722).
Owner's words: "Yes: keep the graph build and task time limits as they are for now; revisit after the scan-graph GPU fix and the validator-host confirm run."
Input: codex-queue/reports/GRAPH_PHASE_TIME_RESULT_20261103.md (Evidence; Launchpad's audit #5 table, Validator-receipted method).

## Decided
- **The walls stay as registered:** 648 s build, 947 s task. A Motor-sized graph used 1.3–5.9 % of them in the measured route.
- **They are revisited after both of these:**
  - (a) the scan-graph GPU fix: scan graphs train differently on JAX GPU vs CPU, and loops stay on CPU until a registered parity test exists;
  - (b) a short confirm run on the validator host itself.
- **No wall value changes** without a new owner decision.
