## OWNER-VALV3-GRANT-01: valV3's test-window rental, capped at USD 0.80 an hour and USD 25 in total

**Authority.** The owner, 2026-10-08, relayed by the Test Lead: "approve valV3
grant". It approves the Carbon Validator session's proposal in
`REHEARSAL_3B_VALV3.md` (the grant proposal section).

**Grants:**
- **Hourly ceiling: USD 0.80** for one verified-datacenter, VM-type
  NVIDIA A40 rental (Vast.ai Secure Cloud or RunPod SECURE), disk and IPv4
  included. Any offer above it is refused.
- **Total: USD 25** for the first rehearsal windows: 3 windows of 8 h, plus
  1 h of setup each.
- **Owner-run in the owner's account.** No agent rents, stops or bills
  anything.

**Binds only with** OWNER-VALV3-GPU-VALIDATOR-01:
- datacenter-only custody;
- every window ends with the rental destroyed.

**Spends nothing before both gates:**
- VALIDATOR-27, the battery validator's GPU scoring, merged and released;
- the A40 acceptance passes.

This record holds no booked spend, and none is ever committed. A change
needs a new owner record.
