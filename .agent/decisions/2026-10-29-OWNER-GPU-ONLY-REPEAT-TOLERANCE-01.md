# OWNER-GPU-ONLY-REPEAT-TOLERANCE-01: nothing trains on a CPU; the crown repeat grade must match within the registered rebuild wobble

- **Received by:** the Lead session (local_b7032708-92d1-4a7c-a1d3-9ad008ba9cae), directly from the owner in chat, 2026-10-29.
- **Owner's words:**
  - "I don't want anything training on a CPU".
  - Then "A", answering the Lead's options: "A ... the re-check allows the measured wobble ... B ... make those models give exactly the same result on the GPU". The owner chose A and did not ask for B.
- **Decided:**
  1. **GPU only:** validator rebuilds train on the GPU for every served entry. CPU-lane training is not used. This reaffirms the owner's 10-26 rule that GPU rebuild is a launch must. The CPU lanes are reverted: cno1d-cpu-lane 773f78541 is reverted, and cpu-lane-parity 5261c2653 is not folded.
  2. **Crown repeat (amends OWNER-CROWN-GRADE-REPEAT-01's implementation):**
     - The second, independent grade must agree with the first within the registered rebuild-noise tolerance for that Challenge on the registered class. Exact bit-identity is not required.
     - A disagreement beyond the tolerance is FAILED_INFRA: no crown change, a typed alert, a host re-check, and never the miner's fault.
     - Until the tolerance is registered at the one recalibration, crown changes are UNAVAILABLE.
- **Bounds:**
  - The tolerance value comes only from the registered recalibration measurement; no agent chooses it.
  - KOTH stays frozen and no score term is added.
  - Owner-visible follow-up: whether any GPU-vs-CPU gate disagreement found in the parity run affects what miners see in practice.
