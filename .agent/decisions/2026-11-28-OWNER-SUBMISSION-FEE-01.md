# OWNER-SUBMISSION-FEE-01: official miner submission fee via atomic Subtensor `add_stake_burn`

Date: 2026-11-28 (AWST 16:51:23+08:00 / 2026-11-28T08:51:23Z)
Status: DECIDED by the owner (Nick Fitzpatrick), directly in the session via `ask_question` (four single-select confirmations `A1`–`A4` at `2026-11-28T08:51:23Z`, following earlier Option A rollout confirmation in session).

## Context
Carbon requires a protocol-native anti-spam and anti-Sybil submission fee on official validator doors that buys and burns Subnet Alpha without Carbon ever holding miner funds, operating a buyback keeper, or sending cash/TAO refunds, while preserving `AGENTS.md` §6.7 (Carbon infrastructure failure never costs the miner) and `AGENTS.md` §6.11 (fee is never score).

## Owner's Verbatim Confirmations

Earlier rollout direction in session (2026-11-28):
- Owner question: `"Ok, so we can get this thing all built and live on mainnet and then flip the fee on when we want to easily?"`
- Owner confirmation: `"Yep, lets go with option A and go for it"`

Post-re-audit `ask_question` prompts and verbatim owner selections (`2026-11-28T16:51:23+08:00` / `2026-11-28T08:51:23Z`):

1. **Question 1 (`A1` — Sequencing):** `"How would you like to sequence the remaining fixes from this re-audit?"`
   - Selected (verbatim): `"(Recommended) Fix everything in PR #1437 now (Merge Blockers 1-2 + L1-L2 + C1-C7 + M1-M4 + B8 sha pin + H3/H4/H13/H16 + docs/nits) so #1437 is GO for both dark merge and 116 enablement"`
   - Not selected: `"Two-step: fix only Merge Blockers 1-2 now to dark-merge #1437 immediately, then put L1-M4 + docs in a follow-up PR before enabling 116"`

2. **Question 2 (`A2` — Price, Consume Rules, Terms v1 SHA-256 Pin, & Per-Burn Caps):** `"Confirm the owner-reserved fee parameters, caps, and Terms v1 SHA-256 pin for OWNER-SUBMISSION-FEE-01:"`
   - Selected (verbatim): `"(Recommended) Confirm 0.025 TAO launch fee (legal signed off), WITHDRAWN_BY_MINER & DUPLICATE consume burn, pin carbon-submission-terms-v1 sha256 321100f9b4342f36a13bd9cf5c0bfbefbca99a44543e4e8da99c4760315ff1a5, hard cap 1.0 TAO (door & signer) + miner --max-single-fee-tao default 0.10 TAO"`
   - Not selected: `"Confirm same launch fee, consume rules, and terms v1 sha256 pin, but keep door/signer hard cap at 10.0 TAO and miner --max-single-fee-tao default at 0.25 TAO"`

3. **Question 3 (`A3` — Infrastructure Retry-Credit Boundary):** `"Confirm the infrastructure retry-credit boundary (Owner Items 4, 5, 6):"`
   - Selected (verbatim): `"(Recommended) Credit proven CARBON_CLASSES builds + repo-verified Carbon grade failure codes ONLY (exclude carbon_unclassified to prevent 16x rerun farming); credits and owed-list reruns are mutually exclusive (credit only once retries settle with no pending/owed rebuild)"`
   - Not selected: `"Also issue retry credits on carbon_unclassified build failures after retries settle"`

4. **Question 4 (`A4` — Validator Host Topology & R89 Preflight Bucket):** `"Confirm validator host topology and R89 preflight bucket behavior (Owner Items 7, 8):"`
   - Selected (verbatim): `"(Recommended) One validator host per receiver hotkey + require explicit/fixed host-wide state dir (/var/lib/carbon/submission-fee-netuid-<N> or submission_fee_state_dir); exempt verified construction_preflight from R89 group token spend (still rate-limited by R89 guard on auth failure and per-hotkey preflight limiter)"`
   - Not selected: `"One validator host per receiver hotkey + fixed host-wide state dir, but keep R89 group token spend on construction_preflight (rely on live burst >= 2)"`

## Decided (testnet 567 and mainnet 116)
1. **Atomic non-custodial payment (`0.025 TAO` initial launch rate, `1.0 TAO` hard cap, `0.10 TAO` miner single-burn default):** Paid doors require finalized `Utility.batch_all([SubtensorModule.add_stake_burn(hotkey, netuid, amount, limit), System.remark_with_event(remark)])` on the Challenge's Bittensor subnet or one unspent `RETRY_CREDIT` owed to that hotkey. Initial Mainnet launch size is `0.025 TAO` (`25,000,000 RAO`), hot-dialable in validator host state without restarting the receiver. Both the validator door (`MAX_SUBMISSION_BURN_RAO`) and `carbon-miner-signer` (`max_single_burn_rao`) enforce a `1.0 TAO` (`1,000,000,000 RAO`) hard ceiling, and `carbon-miner-signer --max-single-fee-tao` defaults to `0.10 TAO` (`100,000,000 RAO`) per submission unless raised by the miner.
2. **Receiver-bound v2 remark, one host per receiver hotkey, and fixed host-wide state directory:** The canonical remark is `carbon.fee.v2|<netuid>|<challenge_id>|<receiver_ss58>|<miner_hotkey_ss58>` (Challenge-version-free so unspent burns carry across version flips on the same validator, while binding `receiver_ss58` so burns cannot be replayed across different validator boxes). Operational topology is strictly **one validator host per receiver hotkey**, with one shared SQLite fee ledger (`submission_fees_<netuid>.sqlite3`) and live policy file (`submission_fee_policy.json`) per `(host, netuid)` at `/var/lib/carbon/submission-fee-netuid-<netuid>` (or explicit `submission_fee_state_dir` / `CARBON_SUBMISSION_FEE_STATE_DIR` outside the git checkout).
3. **Pinned `carbon-submission-terms-v1` SHA-256 gate and per-version Mainnet activation:** `docs/terms/carbon-submission-terms-v1.md` (containing Section 9) is pinned at SHA-256 `321100f9b4342f36a13bd9cf5c0bfbefbca99a44543e4e8da99c4760315ff1a5` in both `submission_terms.PINNED_SHA256` and `submission_fee.FEE_BEARING_TERMS_SHA256`. Mainnet `116` forbids `116:*` wildcard enablement (requiring explicit `116:<challenge_id> <version>` rows) and fails closed (`503 fee_policy_unavailable`) unless `carbon-submission-terms-v1` is served and verified against that exact SHA-256. Deployment lands dark by default (Option A: absent host policy file = dark, zero worker build-inputs hash movement).
4. **Consumption and mutually-exclusive `RETRY_CREDIT` boundary:** Pre-admission refusals never spend a burn or credit. Once admitted to build, candidate outcomes (`GRADED`, `CANDIDATE_FAILED`, `RECONSTRUCTION_FAILED`), post-admission graded duplicates (`DUPLICATE`), and miner-initiated withdrawals (`WITHDRAWN_BY_MINER`) consume the burn or credit. Build-layer credits issue only for proven `infra_diagnosis.CARBON_CLASSES` (excluding `carbon_unclassified`), and grade-layer credits issue only for repo-verified Carbon infrastructure failure codes. Credits and owed-list/operator reruns are mutually exclusive: a credit is minted only after automatic retries settle with no pending rebuild or unapplied owed-list rerun, or when queued ungraded submissions are closed by `version_close` (`VERSION_CLOSED`).
5. **Verified `construction_preflight` R89 exemption and `carbon/fees` boundary:** Authenticated `construction_preflight` calls do not spend the R89 group's `construction_submit` token (invalid/unverified calls still charge the R89 guard, and verified preflight calls have their own bounded per-group preflight bucket). Wave-A `carbon/fees` remains a fixture-only process-local `Strategy` package (`carbon/fees/__init__.py`); live `DirectRecipeIntake` burn verification and credit accounting live in `carbon.chain.fee_burns`, `carbon.chain.fee_poster`, `carbon_miner_signer.fee_burn`, and `carbon.challenge_validator.submission_fee`, with zero path into scoring, KOTH, Crown, bank, or weights.
