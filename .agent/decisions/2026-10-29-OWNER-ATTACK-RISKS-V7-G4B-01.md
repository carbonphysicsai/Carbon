# OWNER-ATTACK-RISKS-V7-G4B-01: the control rebuild separates an unstable model from a machine fault; the allowance stays per hotkey

- **Received by:** the Lead session (local_b7032708-92d1-4a7c-a1d3-9ad008ba9cae), directly from the owner in chat, 2026-10-29.
- **Owner's words:** "yes and keep". This answers the Lead's two questions from the M8 attack-suite risk rows:
  - (1) "Unstable models ... Recommend yes";
  - (2) "Many identities: keep the daily allowance per hotkey for now ... Recommend keep".
- **Decided:**
  1. **V7, amends the implementation of OWNER-GPU-ONLY-REPEAT-TOLERANCE-01.** When a crown-changing repeat grade falls beyond the registered tolerance, a Carbon control rebuild runs beside it on the same host.
     - If the control reproduces within tolerance, the outcome is candidate_not_reproducible: no crown change, the attempt is counted, and there is no host alert.
     - Only when the control also misses is it FAILED_INFRA (refunded, typed alert, host re-check).
  2. **G4b.** The daily allowance stays per hotkey for launch. Testnet week watches multi-hotkey behaviour (attempts per coldkey or funded identity, and feedback-probing patterns), and the owner decides for mainnet from that data.
- **Bounds:** no score term is added, KOTH stays frozen, and the control model and tolerance are the registered ones.
