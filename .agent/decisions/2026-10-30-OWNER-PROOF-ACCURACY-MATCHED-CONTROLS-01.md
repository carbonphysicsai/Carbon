# OWNER-PROOF-ACCURACY-MATCHED-CONTROLS-01: proof-suite gaming controls are built from the honest model's own predictions

Date: 2026-10-30 (CST)
Status: DECIDED by the owner, directly in the Lead session (local_b7032708-92d1-4a7c-a1d3-9ad008ba9cae).
Owner's words: "Yes", in reply to the Lead's question: reply "yes to the fairer test" to adopt it.

Context: the owner observed that controls built from the hidden true answers bank about 0.5 of the total through accuracy alone, so "control must lose to the honest model" mostly measured accuracy rather than whether bias is punished. Checked against the existing sheets, every control scores below the oracle on Motor 1.5, F08 1.7 and F02 2.5. The Validator confirmed that "controls must lose to good" was a proof-suite design choice (pool_proof_suite), not an owner-set science value.

## Decided

- The proof suite's gaming-control test changes to accuracy-matched controls (the Validator's option E2). Take the honest (good) model's own predictions, apply each control bias (optimistic near limits, wrong near the optimum, in-distribution only), and require each biased version to score at or below the honest model. The oracle must still reach the top, and each truth-based control must still score below the oracle.
- It is built during testnet week, in carbon/scoring after the launch packs and recal, alongside the Motor exam fix. It applies prospectively, with no rescore of past results.

## Bounds

- Sets no score threshold, constant or economics.
- How the provisional-constants guard reads the new rule is confirmed when the change lands.
