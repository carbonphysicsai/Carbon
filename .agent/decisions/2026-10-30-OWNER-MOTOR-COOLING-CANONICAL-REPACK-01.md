# OWNER-MOTOR-COOLING-CANONICAL-REPACK-01: real canonical repack of Motor and Cooling sealed exam packs, transfer and signing on custody hosts

Date: 2026-10-30 (CST)
Status: APPROVED by the owner, directly in the Lead session (local_b7032708-92d1-4a7c-a1d3-9ad008ba9cae).
Owner's words: "Yes to repack"

## What is approved

For Motor and Cooling, by the route the Validator ruled (M4_CANON receipt; Cooling canonical test a0059016a700311c874874e5587403986f4f2127):
1. Run the real canonical repack on the primary custody host. It writes new canonical and unsigned output beside the existing packs; existing sealed packs are not modified or deleted.
2. Transfer the result to the second custody host with a one-time key created on the receiving host for this transfer and removed right after; never routed through the operator PC. sha256 checked at both ends, entry in the custody ledger.
3. Sign on the second custody host (`MODE=sign`) with the producer key used by file path only; the key is never read, printed, copied or moved.

## Bounds

- Motor and Cooling only. Cooling proceeds only if its DRY run passes.
- Custody host addresses and paths stay in operator-private custody notes, not in this record.
- This record sets no score, threshold, tolerance, population law or economics.
