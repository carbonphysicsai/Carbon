# OWNER-CROWN-AVG-UNSTABLE-KING-01: an unstable king keeps its crown, flagged

Date: 2026-11-02 (CST), ~14:50
Status: DECIDED by the owner, directly in the Lead session (local_87151681-c66e-4949-a26c-23c4641b5722), via AskUserQuestion.
Owner's choice: "King keeps it, flagged (Recommended)". Option text: "The king keeps the crown, and challengers are compared to its single registered score. It's flagged as unstable on the board, and the next recalibration re-measures it. The race keeps running and nobody is unseated over what may be an infra fault."

## Context
- Crown-average switch-on (the owner's K_crown + N=10): when the incumbent is re-measured over N rebuilds and some rebuilds fail, the record has no mean.
- Today's code then raises KING_UNMEASURED and pauses that Challenge's crowns indefinitely (crown_average.py:276-278; pool_store.py:1660-1676). The Validator ruled this a miner-facing policy, not an operator one.

## Decided
- A KING_UNSTABLE incumbent keeps its crown. Challengers are compared to its single registered total (with the registered margin), not to a missing mean.
- The board shows the king as unstable. The next registered recalibration re-measures it, and a stable mean then replaces the single total prospectively.
- Nothing graded is rescored.
- **Implementation:** the TE changes the screening path from 'pause' to 'single registered total + flag' for KING_UNSTABLE only, with tests (unstable king vs a challenger above/below its single total; stable kings unchanged). Tier 2, Validator receipt, then main on the owner's words before switch-on.
