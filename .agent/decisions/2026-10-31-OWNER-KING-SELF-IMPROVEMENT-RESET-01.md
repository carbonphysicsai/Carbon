# OWNER-KING-SELF-IMPROVEMENT-RESET-01: a crown holder who beats its own score by the margin gets a full decay-clock reset

Date: 2026-10-31 (CST)
Status: DECIDED by the owner, directly in the Lead session (local_b7032708-92d1-4a7c-a1d3-9ad008ba9cae).
Owner's words: "Yes". He was answering the Lead's question: "should a crown holder who beats their own score by the margin get their clock reset… I'd say yes, with a full reset when they beat their own score by the margin."

## Context

Under testnet-winner-v4-launch, a Challenge's winner gets its full 1/N for 24 h from the first weights run after the crown, then the share halves every 24 h, with the remainder burned to UID 0. Only a takeover by a different miner (a different hotkey and a different coldkey) restarts the clock (KOTH-TAKEOVER-RULE-01 §2, "same_miner_no_reset"). self_improvement_factor is null, so self-improvement earns no reset.

## Decided

- When the current crown holder (the same hotkey or coldkey) submits a new model whose official, repeat-confirmed grade beats its OWN current crown score by at least the registered margin, its decay clock fully restarts: the full 1/N for 24 h again, then halving.
- The margin is the same registered crown margin that a takeover needs (OWNER-CROWN-MARGIN-2SD-01), so small re-tweaks cannot reset the clock.
- Implemented as a new weights-policy version (the self-improvement factor = full reset), built and tested in week 1 and activated prospectively. Past epochs are never recomputed.

## Bounds

- Testnet first. The mainnet policy carries it only with the owner's mainnet approval.
- Sets no other economics: N, the burn UID, the decay constants and the margin are unchanged.
