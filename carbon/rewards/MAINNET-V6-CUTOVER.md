# Mainnet SN116 Stage B Cutover Guide: `mainnet-winner-v5` -> `mainnet-winner-v6` (Community Treasury Activation)

> **Scope:** Offline policy registration, operator cutover, and rollback runbook only. Nothing in this repository mutates live state or submits weights without explicit live-ops execution under owner standing authorization.

## 1. Pinned Policy Digests (`carbon/rewards/weight_policies/registry.json`)

| Field | Previous (`mainnet-winner-v5`, Stage 5B) | Stage B Target (`mainnet-winner-v6`, Stage 5C) |
| :--- | :--- | :--- |
| **Version** | `mainnet-winner-v5` | `mainnet-winner-v6` |
| **`policy_digest`** | `sha256:6e0c72a46f4bc8f7d3dcee359ba053e4ad469345d4c7da30a442d19dc0892836` | `sha256:e98a48db7be3be36136ed6ae3e9fe862695a1b8b3bb76efdce90c6411811592f` |
| **Authority** | `OWNER-WEIGHTS-AUTHORITY-01` | `OWNER-WEIGHTS-AUTHORITY-01` |
| **Network / Netuid** | `finney` / `116` (`burn_uid: 0`, `cadence_blocks: 360`) | `finney` / `116` (`burn_uid: 0`, `cadence_blocks: 360`) |
| **Route** | `WATERFALL_KING_BONUS_TREASURY_BURN` | `WATERFALL_KING_BONUS_TREASURY_BURN` |
| **Challenges** | `["electric-motor-magnetics"]` (pack `ee2348b1...`, `full_reset`) | `["electric-motor-magnetics"]` (pack `ee2348b1...`, `full_reset`) |
| **Rung 3 Treasury** | Disabled (`treasury_sinks: []`, `treasury_stake_cap_rao: 0`) | Active (`UID 498` & `UID 499`, `treasury_stake_cap_rao: 50000000000000`) |

## 2. Live Finney (`964`) / `SN116` Stage B Treasury Deployment & Sink Pins

- **`CarbonCouncil` (`964`):** `0x9FE8274Af58DB23FC7c699A8d41C28Deb94BA46b` (block `9597255`, tx `0x38a1ec8a333fc48459e049e37692d071770cbab09ca45d187fb9d15ef66e44cc`)
- **`CarbonTreasuryVault` (`964`):** `0xA1347f50E6b8942Ff08E7725a10500eBC3c7F945`
- **Vault Coldkey (`0x080C`):** `5HVHGgWc1RvFFCkS678oB4DBjR8ZumAiAFsVXDf3aJCNbY8T` (`0xefeb89e154895fdab5ad3e04dbc451d18afd9dc0ba301bcc82ef22181663cc68`)
- **Vault Parking Hotkey (`UID`-less):** `0x54dcc44a83df1529590e6850f3ea70b09782a1a687d016e066b5902f62c27334`
- **Sink 0 (`UID 498`):**
  - `hotkey`: `5EJntfeBXpuJB8Jgss89uFyp468Z3xuBRLppgMPf42EwbgoJ` (`0x6336d99cb612977581e256ab46190f461be71c761d210c68dbf95034bbf4bb64`)
  - `coldkey`: `5HVHGgWc1RvFFCkS678oB4DBjR8ZumAiAFsVXDf3aJCNbY8T`
  - `registered_at` (`BlockAtRegistration`): `9597339` (tx `0x90c7013eb1dbe7bce11cbdc18bf807e45c624a43a9fd53e9efbaf12069bd903a`)
- **Sink 1 (`UID 499`):**
  - `hotkey`: `5CtoE4XJ9g9NHXY6Fb8DZy1uxGj5DdLPqkRksMMH5TqGVTwb` (`0x24adda4013380d6625c1c396e732ff305d5cae1a14df8ee6b354a1e5cc4abaa9`)
  - `coldkey`: `5HVHGgWc1RvFFCkS678oB4DBjR8ZumAiAFsVXDf3aJCNbY8T`
  - `registered_at` (`BlockAtRegistration`): `9597340` (tx `0x47b19866acd89da75d5a99e4ab7a7f6f559e22a2c5e21242b97d0a02804a0fb6`)
- **Owner-Approved Stage B Stake Cap:** `treasury_stake_cap_rao = 50000000000000` (`50,000 α`).

## 3. Exact Inheritance & Rung 3 Treasury Routing Semantics

- **Inherited Unchanged from `mainnet-winner-v5`:** Rung 1 Challenge King decay (`100%` for 24h, halving every 24h, `enforce_king_u16_floor = false`), empty/excluded slot direct burn to `UID 0`, Rung 2 Miner Hold Bonus (`+50%` over `600` epochs tapering linearly to `0%` at `50%` sold, `hold_cap_q12 = 400000000000`), and `excluded_coldkeys = ["5D5RwyMPFaKLwChEcfb5yPA6VENHxJBagcHkP5aztfg8Ynj9", "5HVHGgWc1RvFFCkS678oB4DBjR8ZumAiAFsVXDf3aJCNbY8T"]` across both Rung 1 and Rung 2.
- **Rung 3 Community Treasury Routing:** While observed `SN116` stake for `5HVHGgWc1RvFFCkS678oB4DBjR8ZumAiAFsVXDf3aJCNbY8T` is strictly `< 50_000_000_000_000` rao (`50,000 α`), `residual_after_bonus_q12` (unused active-King decay) splits evenly across all active identity-pinned `(hotkey, coldkey, registered_at)` sinks matching the finalized metagraph (`UID 498` and `UID 499`).
  - If `UID 498` deregisters or is recycled at a different `registered_at`/`coldkey`, `100%` of Rung 3 automatically fails over to `UID 499` (and vice versa).
  - Once observed vault stake reaches `>= 50_000 α` (or if stake observation fails or both sinks fail pin verification), `100%` of post-bonus residual burns to `UID 0`.
- **Prospective Only:** Existing `winners.jsonl` (`promoted_at_ms`), `publication.sqlite3`, and `hold_bonus_ledger.jsonl` remain untouched across cutover and are never recomputed.

## 4. Safe Operator Cutover (`v5 -> v6`)

1. **Settle Pending Commit-Reveal First:** Allow `settle_pending` to clear any open `mainnet-winner-v5` `REVEAL_PENDING` dispatch before switching `policy_digest` in the same epoch.
2. **Update `standing.json` (`chmod 0600`, non-symlink):**
   - Set `"policy_digest": "sha256:e98a48db7be3be36136ed6ae3e9fe862695a1b8b3bb76efdce90c6411811592f"`.
   - Keep `authority` (`OWNER-WEIGHTS-AUTHORITY-01`), `authority_record`, `publisher_hotkey`, `expected_runtime_spec`, and block window aligned with live `SN116`.
3. **Switch Policy Flag / Profile:** Update `--policy-version mainnet-winner-v6` (or operator unit config `"policy_version": "mainnet-winner-v6"`), keeping existing `--journal`, `--ledger`, and `--hold-ledger` paths unchanged.
4. **Dry-Run Preview First (Read-Only, No Wallet):**
   ```bash
   python -m carbon.validator_setup weights preview \
     --config <operator-weights.json> \
     --standing <standing.json> \
     --journal <publication.sqlite3> \
     --ledger <winners.jsonl> \
     --lean-pool electric-motor-magnetics=<motor-pool.sqlite3> \
     --policy-version mainnet-winner-v6
   ```
   Confirm `"signed": false`, `"policy": "mainnet-winner-v6"`, `targets["treasury"]` resolves pinned `UID 498` / `UID 499` (when active-King decay exceeds Rung 2 Hold Bonus and vault stake `< 50,000 α`), `sum(winners) + sum(hold_bonus) + sum(treasury) + burn == 1000000000000`, and `hold_bonus_ledger.jsonl` is unmodified.
5. **Activate Under Receipted Owner Go:** Enable/run `weights run` for the next `360`-block `SN116` epoch.

## 5. Emergency Rollback (`v6 -> v5`)

1. **Clear Pending Dispatch:** If a `mainnet-winner-v6` commit is `REVEAL_PENDING`, either pause new submissions (`weights_paused`) while `reconcile_during_pause` settles the pending reveal, or wait for `settle_pending` to clear cleanly.
2. **Revert `standing.json` & Policy Flag to `mainnet-winner-v5`:**
   - Set `"policy_digest": "sha256:6e0c72a46f4bc8f7d3dcee359ba053e4ad469345d4c7da30a442d19dc0892836"`.
   - Switch `--policy-version mainnet-winner-v5` (retaining existing `publication.sqlite3`, `winners.jsonl`, and `hold_bonus_ledger.jsonl` without editing or resetting state).
3. **Verify via `weights preview`:** Confirm `"policy": "mainnet-winner-v5"`, `targets["treasury"] == []`, and all residual weight burns to `UID 0`.
