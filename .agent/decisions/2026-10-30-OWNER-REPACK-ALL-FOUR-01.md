# OWNER-REPACK-ALL-FOUR-01: the repack hold is lifted for all four launch Challenges

Date: 2026-10-30 (CST)
Status: DECIDED by the owner, directly in the Validator session (local_9d14c86b-b50e-4cf2-a2ef-5c69ad1ed1e0); written here by PR Head from the Validator's report (GPUYARD_GPU4_REPEAT_EVIDENCE_RULING_20261030.md).
Owner's words: "Approved". Asked what it covers, he chose "Repack, all four".

## The question asked

Motor and Cooling now; Ribbed Bracket and Burst Thermal once their exam data is identified; issuing exam copies still needs his separate OK per pack.

## Decided

- The repack hold is lifted for Motor 1.5, Cooling 1.6, Ribbed Bracket 1.7 and Burst Thermal 2.5.
- Each repack runs by the receipted unsigned route: a DRY run first; the repack on the AX42 without a key; a direct stream to custody2 with sha at both ends, logged in the custody ledger; then MODE=sign on custody2.
- Motor 1.5 and Cooling 1.6 run first, on the receipted canonical scripts (M4_CANON, 9bceb963…) with the picked batches.
- Ribbed Bracket 1.7 and Burst Thermal 2.5 run once the Test Lead's custody reads are in and the Validator has picked the batches. If the canonical run script has no Ribbed Bracket or Burst Thermal path, that is a new revision and needs the Validator's receipt.

- Burst Thermal 2.5 needed no repack: its plain batch 4322b8ac… was already canonical with a signed record (a trial pool build proved the mapping).

## Bounds

- Not covered: copy issuance. That stays per pack, with the owner's OK (see OWNER-COPY-ISSUE-MOTOR-COOLING-01 and OWNER-COPY-REISSUE-UID0-01).
- Sets no score, threshold or margin value.
