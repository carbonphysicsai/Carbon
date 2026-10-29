# OWNER-MAINNET-CLEAN-START-AND-PUBLISHED-TOLERANCES-01: mainnet starts clean; the miner guide publishes the validator GPU and per-Challenge repeat tolerances; btcli gets a pinned known-good version

- **Received by:** the Lead session (local_b7032708-92d1-4a7c-a1d3-9ad008ba9cae), directly from the owner in chat, 2026-10-29, answering a miner's three questions.
- **Owner's words:** "Yes to all 3" (to the Lead's three recommendations below).
- **Decided:**
  1. **Mainnet starts clean.** No testnet crown, score, KOTH entry, leaderboard standing or ranking carries over to mainnet. Testnet results are rehearsal evidence only and never become mainnet entitlement.
  2. **The miner guide (`docs/MINING.md`) publishes:**
     - the validator GPU model (RTX 4090);
     - each Challenge's repeat (rebuild-noise) tolerance.
     The tolerances are published only after they are measured and registered at the production validator's one registered recalibration, never before. No tolerance value is chosen by this record.
  3. **btcli:** the team tests btcli versions against testnet, pins a known-good version in the miner guide, and announces it before launch. A miner reported that btcli 9.23.2 fails on testnet `subnet show` and `metagraph` with "storage function SubtensorModule.RootClaimType not found".
- **Bounds:**
  - This record sets no tolerance value, no threshold and no economics.
  - Publishing the GPU model and tolerances is consistent with the public-repo rule: no balances, account ids or credentials.
