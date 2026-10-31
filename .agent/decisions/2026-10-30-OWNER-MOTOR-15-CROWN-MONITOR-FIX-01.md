# OWNER-MOTOR-15-CROWN-MONITOR-FIX-01: Motor 1.5 crowns open on testnet under watch; fix the exam definition during testnet week

Date: 2026-10-30 (CST)
Status: DECIDED by the owner, directly in the Lead session (local_b7032708-92d1-4a7c-a1d3-9ad008ba9cae).
Owner's words: "Since it's not an actual attack vector I would say we monitor testnet week and spend the week trying to fix it."

Context: the Motor 1.5 proof grid at its registered point fails (0/768). The gaming controls are built from the hidden true answers, and the "wrong near the optimum" control totals 0.720 against the honest KRR's 0.262. The oracle's accuracy leg is only about 0.81, and honest models earn design value D of about 0, so the proxy leg minimums do not block the controls. The Lead recommended practice-only. The owner chose otherwise, judging that it is not a practical attack vector, since a miner would need near-perfect accuracy without the hidden answers.

## Decided

- On testnet, Motor 1.5 crowns open under its current constants, once its leg minimums, recal and margin exist, with the Validator's private watch extended to the control patterns: high design value with a limit-optimistic or optimum-biased pattern.
- During testnet week, the team works on a fixed Motor exam definition: the oracle must reach a full accuracy leg, and honest models must earn design value. It ships as a new version under the usual proof grid, recal and e2e.

## Bounds

- Testnet only. Mainnet uses its own versions.
- Cooling 1.6's decision is separate and still open.
- Sets no score, threshold or economics.
