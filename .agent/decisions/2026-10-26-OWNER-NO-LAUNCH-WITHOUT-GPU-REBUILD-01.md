# OWNER-NO-LAUNCH-WITHOUT-GPU-REBUILD-01: CPU training is not an acceptable launch state

- **Received by:** the Lead session, directly from the owner in chat, 2026-10-26 ~20:15Z.
- **Owner's words:** "Yeah CPU training is unacceptable. I'm upset we ever thought this was an acceptable launch state" (after the CPU vs GPU rebuild comparison; the choice offered was CPU-rebuild testnet now with a later switch, or hold).
- **Decided:** the testnet launch is GATED on GPU rebuilds. No launch with CPU rebuilds. The validator rebuild trains on the GPU; grading runs on the same machine's CPU (OWNER-GPU-REBUILD-RENTED-4090-01). The owner rents a DEDICATED 4090 today (rebuild + grade on one machine; option (b) of GPU_REBUILD_RULINGS); the marketplace 4090 is for development only and never holds sealed exams.
- **Consequences:** the serving stack (LAUNCH_SERVING_STACK steps 1-9) moves to the dedicated 4090 when it arrives (valV3 work becomes the rehearsal); the registered recalibration runs on the 4090 class, not ccx33; the rebuild wall, the noise registry and the crown margin are measured there.
- **Root cause recorded:** OWNER-GPU-FOR-EVERY-CHALLENGE (10-22, a launch must) was silently narrowed when the 4090 moved to after testnet and testnet grading moved to CPU hosts; nobody re-checked the must-have against the new plan.
