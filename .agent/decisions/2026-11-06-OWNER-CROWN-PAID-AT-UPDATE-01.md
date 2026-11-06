# OWNER-CROWN-PAID-AT-UPDATE-01: weights follow whoever holds the crown at each weight update

Date: 2026-11-06 (CST, about 09:1x)
Status: DECIDED by the owner, directly in the Lead session (AskUserQuestion).

Context: on 6 Nov two Ribbed Bracket crowns landed inside one weights cycle, and the ledger skipped one, so the publisher refused (fail-closed). The Carbon Validator ruled the replay/bridge rule: every crown since the last record is replayed in signed koth-journal order, and a gap is bridged only by a signed journal event. He asked the owner for the general payout rule.

Question: "If a different miner wins a crown and loses it again between two weight updates, should they be paid for those minutes?"
Owner's selection (verbatim option): "A: No, pay crown at each update (Recommended)". The option read: "Weights follow whoever holds the crown at each update. Today's behaviour, no new code; very short crowns earn nothing."

## Decided
- Testnet and mainnet: weights follow the crown holder at each weight update. No time-weighted settlement.
- The replay of intermediate crowns is for record integrity only. It does not create a payout for a crown held only between updates.

## Replayed-crown clock (6 Nov, about 09:3x, AskUserQuestion in the Lead session)
Question: "When the weights loop misses a crown and replays it later, when should that king's 24-hour full-pay window start?"
Owner's selection (verbatim option): "When it actually won (Recommended)". The option read: "Same pay as if our loop had never failed; an outage on our side can't give a king extra hours of full share."
- A replayed crown uses the door's event time. Live cycles keep observation time. A replay with no timestamp is refused.
