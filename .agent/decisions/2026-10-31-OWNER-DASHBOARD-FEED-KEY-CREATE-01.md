# OWNER-DASHBOARD-FEED-KEY-CREATE-01: create the validator's feed signing key on GPUYard for the public launch board

Date: 2026-10-31 (CST)
Status: DECIDED by the owner, directly in the Lead session (local_b7032708-92d1-4a7c-a1d3-9ad008ba9cae).
Owner's words: "Yes, create the feed key"

## Context

The live dashboard (OWNER-DASHBOARD-LIVE-SWITCH-01) needs each receiver's signed launch board. The board is signed with the validator's feed key (score_feed.FeedKey). The Validator has no record of a feed key on GPUYard, and no receiver config names one.

## Decided

- If a read-only name search on GPUYard finds no existing feed key, the Test Lead creates one with score_feed's key-create command.
- The private key file stays on GPUYard, readable only by the validator account (mode 600), and is never printed, copied off the box or committed.
- Only the public key (64 hex) goes into each receiver's `launch_board_key`, the dashboard's pinned key, and public records.
- The key signs only the public launch board (scores, kings, counts). It never signs weights, money or wallet actions.

## Bounds

- Testnet. A mainnet feed key is a separate owner decision.
