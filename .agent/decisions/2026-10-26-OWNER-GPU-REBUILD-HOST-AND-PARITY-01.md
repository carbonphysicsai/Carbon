# OWNER-GPU-REBUILD-HOST-AND-PARITY-01: marketplace 4090 for rebuilds now; CPU-GPU parity tolerance 0.01

- **Received by:** the Lead session, directly from the owner in chat, 2026-10-26 ~20:05Z.
- **Owner's words:** "A and 2" (to: 1 = (a) a marketplace 4090 now, rebuilds only, grading stays on valV3; or (b) a dedicated bare-metal 4090 only. 2 = the CPU-GPU parity tolerance, recommended 0.01).
- **Lead's reading, stated back to the owner:** 1 = (a); 2 = the recommended 0.01.
- **Decided:**
  - Rebuilds run on a rented MARKETPLACE 4090 (Lium first) now: rebuilds only; the trained model moves to valV3, which keeps sealed grading on its CPU. Sealed exams never go to the marketplace host (null-consensus custody rule).
  - Moving to (b), a dedicated bare-metal 4090 (rebuild + grade on one machine), stays open; it needs an owner-held provider account.
  - CPU-GPU parity tolerance = 0.01 (half the 0.02 Ladder step): a tested entry over it is labelled "GPU and CPU results differ" in practice and is never compared across devices. Not a grading input.
- Fixed by the Validator's rulings (GPU_REBUILD_RULINGS_20261026): bit-identical second GPU rebuild; crown margin = max(5 sigma, seed spread) re-measured on the class; wall = 2x the slowest served build on the class; a containment test with the GPU attached + the owner's own acceptance.
