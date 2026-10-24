# OWNER-SCORE-SCALE-MEANING-01: what 1.0 means, and the headroom target

- **Received by:** the Lead session (local_b7032708-92d1-4a7c-a1d3-9ad008ba9cae), directly from the owner in chat, 2026-10-24.
- **Owner's words:** "I feel like T3 at most. 1.0 should be a model that revolutionizes that design space completely. Never wrong. Can use it on any remotely similar problem and it nails everything. 1.0 should make nation headlines."
- **Target (Lead's reading, for the owner to confirm):** T3 is the LEAST strict acceptable, and stricter is fine. On the sealed exam, Carbon's good reference model must score at most 0.80 (H ≥ 0.20). The default must score at least max(0.10, 5 × the KOTH margin) below the good model.
- **Meaning of the scale:** 1.0 is reserved for a model that is never wrong on the target task AND nails remotely similar problems (nearby variants and out-of-distribution designs). Today's good models should sit well below that. Scores near 1.0 must be nearly unreachable.
- **Consequence for design:** generalization to nearby and unusual problems must be part of the score (the robustness/OOD lever, including the A_gen-style held-out variants). Accuracy on in-distribution cases alone cannot reach 1.0. This fits the end goal: value on the target task plus nearby variants.
- **Process:** this binds OWNER-SCORE-HEADROOM-REQUIRED-01. The Validator designs the scales and slices to meet it on all 4 Challenges. The owner approves the final values from the curves. Changes ship as new exam versions.
