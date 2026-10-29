# OWNER-RECAL-VALUES-TESTNET-NOW-01: use the measured calibration values on testnet now; the owner's formal approval comes during the pre-mainnet week

- **Received by:** the Lead session (local_b7032708-92d1-4a7c-a1d3-9ad008ba9cae), directly from the owner in chat, 2026-10-29.
- **Owner's words:**
  - "Honestly. I will be submitting a delegated approval for those numbers to your team anyway. We should be pressing forward with whatever we get. If there's a problem we will fix it later."
  - Then "During the pre mainnet week."
  - Then "Yes" to the Lead's restatement: "Now, for testnet: we use the calibration numbers exactly as measured, straight away. No waiting for anyone's approval, and we press forward. During the pre-mainnet week: you give the formal delegated approval of those numbers, or adjust them, based on how they hold up with real miners. Problems found along the way get fixed as we go."
- **Decided:**
  - **Testnet, now:** the values from the one registered recalibration on the final M9 install are used on testnet exactly as measured, without waiting for an approval. These are the rebuild noise, the crown margin and floor, the crown-repeat tolerance, the speed baselines and the measured lane limits.
  - **Pre-mainnet week:** the owner gives the formal delegated approval of these values, or adjusts them, in light of real-miner testnet results.
  - Problems found along the way are fixed through the hotfix runbook, or for scoring, through new versions.
- **Bounds:**
  - Values come only from the registered measurement method; no agent picks or tunes a number.
  - A measurement that fails its own checks is reported, not used.
  - Mainnet use needs the owner's approval.
  - The validator signing key, security acceptances and money stay with the owner.
