# OWNER-VALIDATOR-GPU-CLASS-02: keep the RTX 4090

Date: 2026-10-22
Status: APPROVED by the owner, directly in the Carbon Validator's session: "Keep the RTX 4090". The owner was answering the Validator's request to confirm "Keep the RTX 4090; drop the L40S / RTX 6000 Ada backup". The owner had said the same earlier in the Test Lead's session.
Amends: OWNER-VALIDATOR-GPU-CLASS-01, which stays unchanged as the record of that decision.

## Why

The two-host RTX 4090 check (evidence: `codex-queue/claude-ops/results/gpu4090-class/cross_host/summary.json`) found:
- trained parameters byte-identical across the two hosts in 6/6 cases;
- an A/B repeat byte-identical within each host in 12/12;
- predictions not byte-identical across hosts (max abs 2.8e-8 to 3.6e-6).

The build predicts on the CPU (`model.cpu().eval()`), and the two hosts' CPUs had different instruction sets: AVX512 on one, AVX2 on the other.

The -01 fallback ("L40S / RTX 6000 Ada, where byte-identical evidence already exists") rested on same-host evidence only (U58). So it would not have removed a CPU-side cause.

## Decided

1. **The mainnet validator machine class stays the NVIDIA RTX 4090 (24 GB).** The rest of -01 item 1 is unchanged.
2. **The L40S / RTX 6000 Ada fallback of -01 item 2 no longer applies.**
3. **The class is registered only after the fix and a repeat of the two-host check.** That check must show byte-identical official predictions and scorer outputs on two RTX 4090s on different hosts with different CPUs.
4. **The fix is an engineering change, not a science value:**
   - Official predictions move off the CPU, to the GPU, with the image's CPU math path still pinned for every CPU-side step (the scorer).
   - The exact change is the Test Engineer's, under Validator review.
   - A producer-digest move before the image is published is expected.

Not decided here: any tolerance in place of byte identity. If the repeated check is not byte-identical, it comes back to the owner.
