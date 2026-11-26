# Mainnet SN116 Cutover Guide: `mainnet-winner-v4` -> `mainnet-winner-v5` (Stage 5B Hold Bonus)

> **Scope:** Offline policy registration & operator runbook only. Nothing in this repository mutates live state or submits weights without explicit live-ops execution under owner standing authorization.

## 1. Pinned Policy Digests (`carbon/rewards/weight_policies/registry.json`)

| Field | Previous (`mainnet-winner-v4`) | Stage 5B Target (`mainnet-winner-v5`) |
| :--- | :--- | :--- |
| **Version** | `mainnet-winner-v4` | `mainnet-winner-v5` |
| **`policy_digest`** | `sha256:4c51a1a49d147c2ae126f583ec351e0429e464fdaa515e764d2ccc352ce3b8e6` | `sha256:691b882f5afa22cb30fc9cf439555e481793c95d4310084284f29de5701a9724` |
| **Authority** | `OWNER-WEIGHTS-AUTHORITY-01` | `OWNER-WEIGHTS-AUTHORITY-01` |
| **Network / Netuid** | `finney` / `116` (`burn_uid: 0`, `cadence_blocks: 360`) | `finney` / `116` (`burn_uid: 0`, `cadence_blocks: 360`) |
| **Route** | `DIRECT_WINNER_PLUS_BURN` | `WATERFALL_KING_BONUS_TREASURY_BURN` |
| **Challenges** | `["electric-motor-magnetics"]` (pack `ee2348b1...`, `full_reset`) | `["electric-motor-magnetics"]` (pack `ee2348b1...`, `full_reset`) |

## 2. Waterfall Parameters in `mainnet-winner-v5`

- **Rung 1 — Active Challenge King:** `100%` share for 24h from promotion, halving every 24h, with `enforce_king_u16_floor = true` (`MIN_POSITIVE_U16_Q12 = 7,629,511`, guaranteeing compiled `u16 >= 1` while positive).
- **Rung 2 — Miner Hold Bonus (`+50%` / 600 Epochs, `40%` Cap):**
  - `hold_window_epochs = 600` (~30 days at 360 blocks/epoch)
  - `window_bonus_rate_bps = 5000` (`+50%` over 600 epochs at `0%` sold)
  - `zero_bonus_sold_bps = 5000` (linear taper to `0%` bonus at `>= 50%` sold)
  - `hold_cap_q12 = 400000000000` (`40%` max epoch allocation to Hold Bonus, strictly carved from decayed weight `Q12 - king_total_q12`)
  - **Anti-Dump Basis:** Point-in-time sold ratio `S_c` evaluated against total protocol-issued `Crown + Bonus` (`C + H`), with non-compounding eligible principal `(C * min(B, C + H)) // (C + H)`.
  - **Strict Exclusions:** `excluded_coldkeys = ["5D5RwyMPFaKLwChEcfb5yPA6VENHxJBagcHkP5aztfg8Ynj9"]`, runtime `owner_coldkey`, `owner_hotkeys`, `publisher_hotkey`, and canary hotkeys.
- **Rung 3 — Community Treasury Sinks (Disabled in `v5`):**
  - `treasury_sinks = []`, `treasury_stake_cap_rao = 0` during the initial 24–48h Council Holder Opt-In window on `council.carbonphysics.ai` (to be pinned in `mainnet-winner-v6` once `CarbonTreasuryVault` sinks are registered on `SN116`).
- **Rung 4 — `UID 0` Burn:** Receives `100%` of post-bonus decayed weight, unpaid slots, and integer dust.

## 3. Live-Ops `StandingAuthorization` (`standing.json`) Update

Update the owner-only (`chmod 0600`, non-symlink) standing authorization JSON on the `SN116` validator host so `policy_digest` matches `mainnet-winner-v5`:

```json
{
  "authority": "OWNER-WEIGHTS-AUTHORITY-01",
  "authority_record": "<owner-authority-record-filename.md>",
  "policy_digest": "sha256:691b882f5afa22cb30fc9cf439555e481793c95d4310084284f29de5701a9724",
  "publisher_hotkey": "<sn116-validator-publisher-hotkey-ss58>",
  "expected_runtime_spec": 495,
  "valid_from_block": <start_block>,
  "valid_through_block": <end_block>
}
```

*(Keep `<owner-authority-record-filename.md>`, `publisher_hotkey`, `expected_runtime_spec`, and valid block window aligned with the live `SN116` operator state; verify `chmod 0600 standing.json` so `load_standing` does not refuse with `STANDING_AUTHORIZATION_NOT_OWNER_ONLY`.)*

If constructing `StandingAuthorization` programmatically in Python:

```python
StandingAuthorization(
    authority_record_digest="<64-hex-sha256-of-owner-record>",
    policy_digest="sha256:691b882f5afa22cb30fc9cf439555e481793c95d4310084284f29de5701a9724",
    context=finney_116_context,
    publisher_hotkey="<sn116-validator-publisher-hotkey-ss58>",
    expected_runtime_spec=<live_spec_version>,
    valid_from_block=<start_block>,
    valid_through_block=<end_block>,
    authority="OWNER-WEIGHTS-AUTHORITY-01",
)
```

## 4. Safe Cutover Checklist (`SN116` Live-Ops)

1. **Settle Pending Commit-Reveal First:** Ensure no prior `mainnet-winner-v4` dispatch is in `REVEAL_PENDING` (`settle_pending` must clear before switching policy digests in the same epoch).
2. **Point Operator Profile / CLI to `mainnet-winner-v5`:**
   - In operator unit profile JSON: set `"weights": { ..., "policy_version": "mainnet-winner-v5" }`.
   - On CLI invocations: pass `--policy-version mainnet-winner-v5`.
3. **Dry-Run Preview Before Live Run (Writes Nothing, Opens No Wallet):**
   - Execute `weights preview ... --standing <standing.json> --policy-version mainnet-winner-v5`.
   - Verify output reports `"policy": "mainnet-winner-v5"`, `"signed": false`, `targets["treasury"] == []`, `"5D5RwyMPFaKLwChEcfb5yPA6VENHxJBagcHkP5aztfg8Ynj9"` absent from `targets["hold_bonus"]`, and `sum(winners) + sum(hold_bonus) + burn == 1000000000000`.
4. **Activate Under Receipted Owner Go:** Run / unpause the `weights run` timer for the next `360`-block `SN116` epoch.
