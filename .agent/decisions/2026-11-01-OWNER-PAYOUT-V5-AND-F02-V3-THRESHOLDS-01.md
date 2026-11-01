# OWNER-PAYOUT-V5-AND-F02-V3-THRESHOLDS-01: activate payout policy v5; F02 3.0 thresholds; crown-average switch-on order

Date: 2026-11-01 (CST)
Status: DECIDED by the owner, directly, twice:
- In the Validator session (local_9d14c86b-b50e-4cf2-a2ef-5c69ad1ed1e0): "I approve all 3" (verified in that transcript by the Lead).
- In the Lead session, answering A/B/C on the multi-account finding: "A".

Context: the Chain Auditor found UIDs 34/35/36 funded by one address minutes before each registered (one operator, three coldkeys). Crowns are valid; no probing evidence. Under v4 a "different miner" takeover restarts the full-pay clock, so swapping crowns between one operator's accounts reset it.

## Decided

1. ACTIVATE payout policy v5, `testnet-winner-v5-launch` (self-improvement reset; already on main; registry digest sha256:2990d644b6d65b855dde87c757a3a7ddefcd930a7073a3c3030213b95f5ee317).
   - Binding: a NEW owner-only standing.json naming the v5 policy digest (same procedure as 62897f2c), created or confirmed by the owner in the Test Lead session; the weights loop then runs with `--policy-version testnet-winner-v5-launch`.
   - Past ledger records unchanged; prospective only.
2. F02 3.0 thresholds, owner-signed: nonlinearity too weak if under 0.5 °C; STOP if a cheap method comes within margin_N of the oracle.
3. Crown-average switch-on after the ordering fix (push-1) is live: K_crown created with the owner in the TL session → per-receiver config at a zero-downtime re-prepare → kings re-measured (OWNER-CROWN-AVERAGE-GO-LIVE-01 terms).

Not chosen: B (common-funder accounts treated as one miner) and C (defer). Testnet only.
