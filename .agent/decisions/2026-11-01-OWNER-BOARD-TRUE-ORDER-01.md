# OWNER-BOARD-TRUE-ORDER-01: public boards show the true rank order (exact totals), with rounded scores, and the king on top

Date: 2026-11-01 (CST)
Status: DECIDED by the owner, directly in the Lead session (local_b7032708-92d1-4a7c-a1d3-9ad008ba9cae).
Owner's words: "We need to show who is actually ahead and behind and the true king needs to be on top", then, after the Lead and the Validator explained the within-step ordering concern: "it's not a leak tho it just shows the true order the rounding still protects us. 1"

## Decided
- The signed launch board carries each hotkey's TRUE rank by exact best total. The displayed total stays floored to the Ladder step, and exact totals are never published.
- The current king is always listed first (the crown holder, even when a challenger's exact total is higher but within the margin); everyone else follows in exact-total order.
- The board drops "=1" display ties; equal exact totals keep a shared rank.

## Record of the concern (not adopted)
The Validator recommended against within-step ordering (it reveals relative order inside the noise band and could help a multi-hotkey miner bisect an exact total). The owner judged the rounding protection sufficient. Revisit if the Chain Auditor or the gaming watch sees probing patterns (many near-identical submits across hotkeys of one operator).

## Bounds
- Display/disclosure only. Scoring, crowns and payouts are unchanged.
- Rides the next producer push (board v2 with to_beat v2 and crown_changes). Testnet.
