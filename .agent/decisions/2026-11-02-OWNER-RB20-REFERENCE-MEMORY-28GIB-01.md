# OWNER-RB20-REFERENCE-MEMORY-28GIB-01: Ribbed Bracket 2.0 per-case reference memory limit up to 28 GiB

Date: 2026-11-02 (CST)
Status: DECIDED by the owner, directly in the Lead session (local_87151681-c66e-4949-a26c-23c4641b5722).
Owner's words: "Yes: Ribbed Bracket 2.0 per-case reference memory limit up to 28 GiB."

## Context
- This follows OWNER-RB20-SOLVER-REPIN-PASTIX-01 (4b232794): bring the measured memory figure before raising the per-case limit.
- Measurement: once, on the v2 LDLT PaStiX image (4263868e, solvers 6a44808e), at 1 s sampling, on an uncapped pod.
  - Heaviest case 0000 (547,756 nodes): peak 21.9 GiB (23,503,925,248 B runner-sampled group RSS, the quantity the runner cap stops on), 2,012 s, 0 static pivots.
  - Case 0033: 12.7 GiB.
- Exam Quality recommended 28 GiB (~1.25×) and the Validator reviewed the ask (board 01:10 CST, 2 Nov).

## Decided
- The F08 2.0 per-case reference solve memory limit is up to 28 GiB, in place of the 9 GiB limit, for F08 2.0 reference solves on the v2 PaStiX image only.
- F08 1.7 and its SPOOLES history are unchanged and never rescored.
- A case that exceeds 28 GiB stops as a typed resource refusal. It never silently passes and is never retried uncapped.
