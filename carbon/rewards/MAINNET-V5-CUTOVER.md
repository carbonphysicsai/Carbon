# Mainnet SN116 Cutover Guide: `mainnet-winner-v4` -> `mainnet-winner-v5` (Stage 5B Hold Bonus)

> **Scope:** Offline policy registration & operator runbook only. Nothing in this repository mutates live state or submits weights without explicit live-ops execution under owner standing authorization.

## 1. Pinned Policy Digests (`carbon/rewards/weight_policies/registry.json`)

| Field | Previous (`mainnet-winner-v4`) | Stage 5B Target (`mainnet-winner-v5`) |
| :--- | :--- | :--- |
| **Version** | `mainnet-winner-v4` | `mainnet-winner-v5` |
| **`policy_digest`** | `sha256:4c51a1a49d147c2ae126f583ec351e0429e464fdaa515e764d2ccc352ce3b8e6` | `sha256:6e0c72a46f4bc8f7d3dcee359ba053e4ad469345d4c7da30a442d19dc0892836` |
| **Authority** | `OWNER-WEIGHTS-AUTHORITY-01` | `OWNER-WEIGHTS-AUTHORITY-01` |
| **Network / Netuid** | `finney` / `116` (`burn_uid: 0`, `cadence_blocks: 360`) | `finney` / `116` (`burn_uid: 0`, `cadence_blocks: 360`) |
| **Route** | `DIRECT_WINNER_PLUS_BURN` | `WATERFALL_KING_BONUS_TREASURY_BURN` |
| **Challenges** | `["electric-motor-magnetics"]` (pack `ee2348b1...`, `full_reset`) | `["electric-motor-magnetics"]` (pack `ee2348b1...`, `full_reset`) |

## 2. Waterfall Parameters in `mainnet-winner-v5`

- **Rung 1 — Active Challenge King:** `100%` share for 24h from promotion (`clock_ms` preserved verbatim across `v4 -> v5` cutover and `1.8 -> 1.9` `Handover`), halving every 24h thereafter, with `enforce_king_u16_floor = false` so unbeaten Kings decay naturally to `0` after ~16 halvings (matching `mainnet-winner-v4`).
- **Empty / Excluded Challenge Slots Burn Directly to `UID 0`:** Any Challenge slot (`Q12 // N`) with no payable King (`winner is None`, missing from snapshot, or excluded hotkey/coldkey) sends its entire `share` directly to Rung 4 (`UID 0` burn) and **never** funds Rung 2 Hold Bonus or Rung 3 Treasury. Only `decayed_from_active_kings_q12` funds Rungs 2 and 3.
- **Rung 2 — Miner Hold Bonus (`+50%` / 600 Epochs, `40%` Cap):**
  - `hold_window_epochs = 600` (~30 days at 360 blocks/epoch)
  - `window_bonus_rate_bps = 5000` (`+50%` over 600 epochs at `0%` sold)
  - `zero_bonus_sold_bps = 5000` (linear taper to `0%` bonus at `>= 50%` sold)
  - `hold_cap_q12 = 400000000000` (`40%` max epoch allocation to Hold Bonus, strictly bounded by `min(hold_cap_q12, decayed_from_active_kings_q12)`)
  - **Anti-Dump & Anti-Masking (`external_stake_rao`) on `360`-Block Snapshots:**
    - `HoldBonusLedger` tracks `external_stake_rao` and `last_observed_stake_rao` per coldkey so pre-existing, bought, or transferred-in Alpha never masks selling mined rewards (`retained_mined_rao = max(0, B_C(e) - external_stake_rao)`).
    - Point-in-time sold ratio `S_c` is evaluated against total protocol-issued `Crown + Bonus` (`I = C + H`) using `retained_mined_rao`, with non-compounding eligible principal `(C * min(retained_mined_rao, I)) // I`.
    - Stake is intentionally sampled once per `360`-block epoch at the finalized snapshot block: any intra-epoch sell-and-rebuy within 360 blocks requires buying back into the `SN116` AMM pool before the epoch snapshot, paying round-trip AMM swap fees and slippage while restoring pool Alpha liquidity.
  - **Strict Exclusions (Enforced Across BOTH Rung 1 King Pay & Rung 2 Hold Bonus):**
    - `excluded_coldkeys = ["5D5RwyMPFaKLwChEcfb5yPA6VENHxJBagcHkP5aztfg8Ynj9", "5HVHGgWc1RvFFCkS678oB4DBjR8ZumAiAFsVXDf3aJCNbY8T"]` (Carbon `SN116` owner/validator coldkey + precomputed Mainnet `CarbonTreasuryVault` coldkey), runtime `owner_coldkey` on `finney`, `owner_hotkeys`, `publisher_hotkey`, `treasury_sinks`, and canary hotkeys.
- **Rung 3 — Community Treasury Sinks (Disabled in `v5`):**
  - `treasury_sinks = []`, `treasury_stake_cap_rao = 0` during the initial 24–48h Council Holder Opt-In window on `council.carbonphysics.ai` (to be pinned in `mainnet-winner-v6` once `CarbonTreasuryVault` sinks are registered on `SN116`).
- **Rung 4 — `UID 0` Burn:** Receives `100%` of empty/excluded Challenge slots, `Q12 % N`, post-bonus unused decay, and integer dust.

## 3. Live-Ops `StandingAuthorization` (`standing.json`) Update

Update the owner-only (`chmod 0600`, non-symlink) standing authorization JSON on the `SN116` validator host so `policy_digest` matches `mainnet-winner-v5`:

```json
{
  "authority": "OWNER-WEIGHTS-AUTHORITY-01",
  "authority_record": "<owner-authority-record-filename.md>",
  "policy_digest": "sha256:6e0c72a46f4bc8f7d3dcee359ba053e4ad469345d4c7da30a442d19dc0892836",
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
    policy_digest="sha256:6e0c72a46f4bc8f7d3dcee359ba053e4ad469345d4c7da30a442d19dc0892836",
    context=finney_116_context,
    publisher_hotkey="<sn116-validator-publisher-hotkey-ss58>",
    expected_runtime_spec=<live_spec_version>,
    valid_from_block=<start_block>,
    valid_through_block=<end_block>,
    authority="OWNER-WEIGHTS-AUTHORITY-01",
)
```

## 4. Persistent Hold-Bonus State File (`hold_bonus_ledger.jsonl`) & CLI Wiring

When `policy.waterfall` is active (such as `mainnet-winner-v5`), `testnet_winner_publication._issuer(...)` (shared by `python -m carbon.validator_setup weights {preview,run}` and `python -m carbon.rewards.testnet_winner_publication {preview,run}`) automatically wires both `HoldBonusLedger` and `waterfall_observer`:

- **Default State Path:** `<parent-of---ledger>/hold_bonus_ledger.jsonl` (right alongside `winners.jsonl` and `publication.sqlite3` in the operator state directory; overridable via `--hold-ledger <path>` on direct CLI calls).
- **Atomic `0600` Persistence & Preview Safety:**
  - `HoldBonusLedger(".../hold_bonus_ledger.jsonl")` loads existing canonical JSONL records (`crown_credit.v1`, `bonus_credit.v1`, `stake_sample.v1`, `epoch_emission.v1`) into an in-memory engine at startup and refuses symlinks (`HOLD_LEDGER_SYMLINK_REFUSED`) or tampered lines (`HOLD_LEDGER_CORRUPTED`).
  - `weights preview`, `RECONCILE_PENDING` cycles, and refused cycles **never create or touch `hold_bonus_ledger.jsonl` on disk**.
  - Only a proceeding `issuer.issue(snapshot)` cycle (`observe_waterfall=True`), after `compute_waterfall_targets` succeeds, atomically writes `hold_bonus_ledger.jsonl` (`0600` temp file + `fsync` + `os.replace`).
- **Settled Receipt Replay & Live Subtensor Observation:**
  - Reads prior `ROW_VERIFIED` intents in `[prev_recorded_epoch, current_epoch)` from `publication.sqlite3` (read-only) so historical `mainnet-winner-v4` winners and each newly verified `v5` epoch are credited **exactly once** (zero double-crediting across previews, retries, or skipped epochs).
  - Performs a single genesis- and block-hash-pinned Subtensor read (`carbon.chain.sdk_weights.read_waterfall_chain_state`) for `alpha_out_emission` / `SubnetOwnerCut` (`epoch_miner_emission_rao`), `StakeInfoRuntimeApi.get_stake_info_for_coldkeys` (`staked_by_coldkey` on `netuid 116`), and `SubnetOwner` / `OwnedHotkeys`. Fails closed with `WATERFALL_CHAIN_OBSERVATION_UNAVAILABLE` if the chain read is unavailable.

## 5. Safe Cutover Checklist (`SN116` Live-Ops)

1. **Settle Pending Commit-Reveal First:** Ensure no prior `mainnet-winner-v4` dispatch is in `REVEAL_PENDING` (`settle_pending` must clear before switching policy digests in the same epoch).
2. **Point Operator Profile / CLI to `mainnet-winner-v5`:**
   - In operator unit profile JSON: set `"weights": { ..., "policy_version": "mainnet-winner-v5" }`.
   - On CLI invocations: pass `--policy-version mainnet-winner-v5` (no operator unit schema changes required; `hold_bonus_ledger.jsonl` is resolved automatically beside `--ledger`).
3. **Dry-Run Preview Before Live Run (Writes Nothing, Opens No Wallet):**
   - Execute `weights preview ... --standing <standing.json> --policy-version mainnet-winner-v5`.
   - Verify output reports `"policy": "mainnet-winner-v5"`, `"signed": false`, `targets["treasury"] == []`, `"5D5RwyMPFaKLwChEcfb5yPA6VENHxJBagcHkP5aztfg8Ynj9"` absent from `targets["hold_bonus"]`, `sum(winners) + sum(hold_bonus) + burn == 1000000000000`, and confirm `hold_bonus_ledger.jsonl` was **not** created or modified by `preview`.
4. **Activate Under Receipted Owner Go:** Run / unpause the `weights run` timer for the next `360`-block `SN116` epoch and verify `hold_bonus_ledger.jsonl` is created (`0600`) after the first proceeding `issue()`.
