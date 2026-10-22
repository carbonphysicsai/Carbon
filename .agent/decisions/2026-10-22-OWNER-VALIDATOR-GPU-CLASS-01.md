# OWNER-VALIDATOR-GPU-CLASS-01: mainnet validators run the RTX 4090, after an identity check

Date: 2026-10-22
Status: APPROVED by the owner, directly in the Carbon Validator's session. The owner chose "RTX 4090, with a check first" from the option sheet `codex-queue/reports/VALIDATOR_HARDWARE_OPTIONS_20261022.md`.

Context: OWNER direction 2026-10-22, confirmed to the Lead: all validators run identical GPU machines, and the exam reproduces GPU-vs-GPU. CPU-vs-GPU parity is not required.

## Decided

1. **The mainnet validator machine class is the NVIDIA RTX 4090 (24 GB).** Every validator runs the same GPU model, driver and CUDA, with an x86-64 CPU and at least 30 GiB of RAM. The image pins the CPU math-library (BLAS) kernel path and thread count.
2. **The check first:** a GPU-vs-GPU identity test on **two rented RTX 4090s on different hosts**, the same test as U58 on the RTX 6000 Ada.
   - **If the results are byte-identical,** the 4090 class is registered.
   - **If they aren't,** the class falls back to the **L40S / RTX 6000 Ada**, where byte-identical evidence already exists.
   - The check is a small spend inside the standing weekly test grant.
3. **Then, once on the chosen class:**
   - the machine-class record;
   - a rebuild-noise and rebuild-wall measurement;
   - the one registered recalibration, on the published image.

**Not decided here:** whether testnet also moves to the GPU class before the recalibration. The Validator recommends yes, so there is one recalibration, not two. That is a separate owner question.
