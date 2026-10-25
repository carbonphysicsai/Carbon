# OWNER-SEVEN-LIMITS-APPROVED-01: the Validator's 7 kept miner limits, approved at the widest value their reason supports

- **Received by:** the Lead session, directly from the owner in chat, 2026-10-25.
- **Owner's words:** "approve as long as those limits are as high as they should be for their reasoning".
- **Under:** OWNER-LIMITS-NEED-OWNER-APPROVAL-01. Source: the Validator's list, MAILBOX/LEAD.md 2026-10-25 19:28Z.
- **Approved (each KEEPS only at the widest value its protection needs):**
  1. Compile deadline: 120 s interim, then 4x the measured compile time of a 64 MiB document (sandbox protection from a compile hang).
  2. An op that is not bit-identical on GPU under the pinned flags runs CPU-only for official rebuilds (grading reproducibility).
  3. Nested-call jit metadata stays default (containment and determinism).
  4. Static shapes only (the graph is bounded before it runs).
  5. Intake 64 MiB document / 192 MiB submission / parse 120 s + 4 GiB / call depth 256 (containment; testnet acceptance 10-21).
  6. No pretrained initial_state; RNG only from Carbon's key (from-scratch grading, exam reproducibility).
  7. Structural recipe validity: batch <= TRAIN rows, steps >= 1, lr > 0.
- **Condition:** the approval covers each limit only at the highest value its stated reason justifies. The Validator confirms, per limit, that the value is no tighter than that reason needs (interim values carry their measurement and are raised when measured). A limit that is tighter than its reason needs is NOT approved at that value and must be widened.
- Everything else on the graph-ops audit list is REMOVED (Validator, 19:28Z).
