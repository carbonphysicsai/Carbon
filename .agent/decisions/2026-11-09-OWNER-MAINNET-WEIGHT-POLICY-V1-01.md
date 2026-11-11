# OWNER-MAINNET-WEIGHT-POLICY-V1-01: the mainnet weight policy mainnet-winner-v1

Date: 2026-11-09 (CST)
Status: DECIDED by the owner, typed directly in the Test Lead-B session (local_53eacf8f-8011-499a-adde-22a96cf78124).
Owner's words: "Test Lead-B: mainnet-winner-v1 = Motor and Cooling, full_reset, baselines null."
He was answering Test Lead-B's W1 question (the three values the policy loader leaves to the owner).

## Decided

- `carbon/rewards/weight_policies/mainnet-winner-v1.json`: finney, netuid 116, authority OWNER-WEIGHTS-AUTHORITY-01.
- Challenges: Motor (`electric-motor-magnetics`) and Cooling (`chip-cold-plate`), each 1/2 of an epoch.
- `self_improvement_factor`: `full_reset` (OWNER-KING-SELF-IMPROVEMENT-RESET-01 carried to mainnet, as its Bounds required).
- Baselines: null for both (the first-incumbent rule, as testnet-winner-v5-launch).
- Decay (1 day full, halving each further day), cadence 360 blocks and burn UID 0 are the loader's fixed values, unchanged.

## Bounds

- Registered, not the registry's `current` policy. Mainnet weights use it only through a finney standing authorization that names its digest, on the owner's launch-day go.
- Adding Burst Thermal or Ribbed Bracket is a new policy version with its own owner words, gate and review.
- Applies going forward only; no ledger record is recomputed.
