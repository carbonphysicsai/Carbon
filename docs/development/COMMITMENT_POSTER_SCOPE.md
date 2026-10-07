> Committed with `.agent/tickets/COMMITMENT-POSTER-01_miner_commitment.md`.
> The owner's answers to §6 are OWNER-COMMITMENT-POSTER-01
> (`.agent/decisions/2026-10-06-OWNER-COMMITMENT-POSTER-01.md`); where they
> differ from this draft (S-offline, one per tempo, no per-post approval),
> the record governs. Kept as drafted below.

# COMMITMENT-POSTER: scope for miner on-chain commitment posting (OD-7(a))

Status: **SCOPE ONLY. Blocked on an owner decision record before any build.**
Prepared read-only against `origin/main` @ `30876180e` (fetched 2026-10-06).
All `file:line` citations are to that commit. No code, commit, chain or network
access beyond `git fetch` was used.

Seam classification: **NEW_OWNER_DECISION_REQUIRED**. The requested design (the
miner's Carbon signer signs and posts an extrinsic) contradicts a recorded
design property of that signer (see 0.1). That property, the bounds, and the
mainnet network all need owner values before an engineer can start.

---

## 0. What the repo already says

### 0.1 Facts that constrain this change

| Fact | Where |
|---|---|
| OD-7(a) is approved for **netuid 567 (testnet) only**. It says the Launchpad's miner hotkey "may post recipe-hash commitment transactions", bounded in count per day and in window. | `.agent/DECISIONS.md:15361` |
| Transactions are limited to the exact OD-4a and OD-7 records. Missing counts, windows, fee caps and expiry are "prepared for approval, never inferred". | `.agent/DECISIONS.md:15685-15686` |
| Commitment posting is not implemented. The count per day, window, fee cap and expiry must be recorded as their own write scope. | `docs/development/BATTERY_TESTNET_HOST_HANDOFF.md:377-382`; `docs/development/BATTERY_TESTNET_PROGRAMME_STATE.md:38` (row 9) |
| **"The signer will not sign extrinsics, by design."** On-chain hotkey transactions are "done by the miner with their own Bittensor tooling, the same as registration". | `docs/development/MINER_EXTERNAL_SIGNER_SECURITY_REVIEW.md:232-236` |
| The signer signs only `btauth/1` payloads: 8 ASCII lines, `POST /carbon/v1/mcp`, sender == hotkey, a fresh nonce and an allow-listed receiver. Anything else is refused. | `carbon_miner_signer/signer.py:3-14`, `:74-109`, `:218-249` |
| Carbon's client sends the payload as ASCII (`payload.decode("ascii")`), so binary SCALE signing payloads cannot travel over the existing `sign` op. | `carbon/chain/external_signer.py:190-206` |
| The signer loads the key with `Keyfile(...).get_keypair()`. It does **not** check the key file's mode, owner or symlink status. | `carbon_miner_signer/signer.py:283-307` |
| Registration precedent: Carbon prepares a `btcli subnet register` command template. The miner runs it in their own terminal, and Carbon "runs nothing, signs nothing and reads no cost". The agent tool returns `human_action_required` / `sign_registration`. | `carbon/development_session/chain_onboarding.py:88-138`; `scripts/dev/miner_launchpad/setup_operations.py:284-296` |
| The OD-4a pattern for the only chain write that exists today: a request with a bound digest, owner approval of that exact digest, `max_dispatches: 1`, `max_fee_tao: 0` / `max_spend_tao: 0` fixed in code, reconcile but never resend. | `docs/development/BATTERY_TESTNET_HOST_HANDOFF.md:335-375` |
| `bittensor==11.1.0` is pinned. | `pyproject.toml:23`, `:67`; `carbon/chain/sdk.py:16` |
| Network constants: `CARBON_NETWORK = "testnet"`, `CARBON_NETUID = 567`. There is "no mainnet netuid yet". | `carbon/chain/models.py:11-25` |
| Testnet genesis and endpoint are pinned. | `carbon/development_testnet/operator.py:38-39` |

### 0.2 Documentation lag (not a blocker)

`BATTERY_TESTNET_HOST_HANDOFF.md:379` and `BATTERY_VALIDATOR_SERVICE_RUNBOOK.md:330`
still say the chain reader is missing. It exists on main
(`carbon/chain/commitments.py`, VALIDATOR-14). Classification: `DOCUMENTATION_LAG`.

The brief says "rule v2 checks" the commitment. In code, the check depends only on
`require_commitment` (`daemon.py:580`) and is independent of `rule` (v1/v2,
`deployment.py:21-24`). Rule v2 only supplies the block clock
(`daemon.py:187-190`).

---

## 1. Pallet, extrinsic and payload form

### 1.1 What the validator reads (pinned in the repo)

- **Read call:** `view.read("commitment", netuid=context.netuid, hotkey_ss58=hotkey)`
  at the **finalized** head, after a genesis check. It returns an object whose
  `.data` and `.block` are used. See `carbon/chain/commitments.py:78-100`,
  specifically `:94` (genesis), `:96-98` (finalized block) and `:99-100` (read).
- **Accepted value:** `data` must be a Python `str` that fully matches
  `sha256:[0-9a-f]{64}` (`commitments.py:33`, `:73-74`).
  - Anything else reads as "no commitment" and is refused as
    `commitment_required`.
  - `block` must be a non-negative `int`, or the read raises
    `CommitmentUnavailable` (`:71-72`).
- **Admission:** `daemon.py:574-590`:
  - `expected = commitment_digest(strategy["challenge_id"], admitted.contract_digest, recipe.strategy_hash)`;
  - `observed = commitments.read(submission.hotkey)`;
  - it refuses `CommitmentRequired` unless `observed["digest"] == expected`;
  - it records `{"digest", "block"}` in the binding (`:610`).
  - No freshness or window check is applied to `block`.
- **Digest:** `daemon.py:146-155` with `_digest` at `:103-105` and `canonical` at
  `carbon/battery/pool_store.py:130-131`:

  ```
  digest = "sha256:" + sha256(
      json.dumps(
          {"challenge": <challenge_id>, "contract_digest": <contract_digest>,
           "schema": "carbon.battery.commitment.v1", "strategy_hash": <strategy_hash>},
          sort_keys=True, separators=(",", ":"), allow_nan=False   # ensure_ascii default True
      ).encode()
  ).hexdigest()
  ```

  - The posted value is the 71-character ASCII string `sha256:` + 64 lowercase hex.
  - `strategy_hash` comes from `compile_recipe` (`carbon/battery/compile.py:180`).
  - `contract_digest` is `admitted.contract_digest` from `compile_submission`
    (`carbon/reconstruction/challenge_contracts.py:185`).
  - All three inputs can be computed from public Carbon code on the miner's side.
    The digest carries no hotkey, no submission id and no time window
    (`docs/development/BATTERY_MINER_SUBMISSION_PATHS.md:200-209`).
- **One current value per hotkey per netuid.** The reader reads "the hotkey's
  current commitment" (`commitments.py:7-8`). Posting a new digest replaces the
  previous one as far as admission is concerned.

### 1.2 What the repo does not pin (UNKNOWN)

| Item | Status |
|---|---|
| Pallet name and extrinsic, e.g. `Commitments.set_commitment(netuid, info)` | **UNKNOWN.** No file on main composes or names it. The grep for `set_commitment` / `Commitments` hits only the reader's SDK abstraction (`"commitment"`). The SDK 11.1 pattern for composing a call is `bittensor._generated.calls.<Pallet>.<method>(...)` plus `substrate.compose(...)` inside an `Intent` subclass (`carbon/chain/localnet.py:543-563`). That gives the mechanism, not this call. |
| Storage item the SDK reads for `"commitment"` | **UNKNOWN** (inside SDK 11.1). |
| The on-chain `info` encoding (for example a single `Raw<N>` data field holding the 71 ASCII bytes) and how SDK 11.1 decodes it into `found.data: str` | **UNKNOWN.** The only repo fact is the reader's contract: `data` must decode to exactly the 71-character string. Tests inject `(DIGEST, block)` tuples (`tests/cpu/test_chain_commitments.py:49-50`), so the round trip through the real pallet is unproven. |
| Whether the call charges a transaction fee, reserves a deposit, or is rate-limited per block or per tempo; whether the **hotkey** account (not the coldkey) pays | **UNKNOWN.** If the hotkey pays, a zero-balance hotkey cannot post. Funding a hotkey is a coldkey action, which is human. |
| Whether SDK 11.1 can compose that call offline (no live metadata) | **UNKNOWN.** |
| Whether the runtime probe covers the call | **No.** `carbon/chain/runtime_probe.py:40-66` lists `SubtensorModule` calls and storage only, with no Commitments entries. |
| Whether the call needs MEV-shield submission | **UNKNOWN.** `localnet.py:870-893` routes only `intent.mev_shield_required` intents through `submit_shielded`. |

**First engineering step (no chain needed):** read the installed
`bittensor==11.1.0` source for `_generated.calls` and the `"commitment"` read
registry to pin the pallet, call, argument types and decoder. Then prove the round
trip on the disposable localnet (`carbon/chain/localnet.py`): post, then
`ChainCommitmentReader.read` returns the same 71-character string. Until both are
done, every row above stays UNKNOWN, and the build cannot claim it matches the
reader.

---

## 2. Bounds the signer must enforce

Every bound fails closed. Any value marked `HUMAN_INPUT` is `None` in code until the
owner records it, and a `None` bound refuses **every** commit request (no default).

| # | Bound | Rule | Value |
|---|---|---|---|
| B1 | One extrinsic | The outer call must be exactly the pinned commitment call (pallet and call index pinned from SDK 11.1 metadata and checked by the runtime probe). Everything else is refused, including `SubtensorModule.*`, `Balances.*`, `System.remark*`, `Sudo.*` and every other pallet. | pallet/call: UNKNOWN (pin per 1.2) |
| B2 | Netuid | `netuid == configured netuid`. The configured netuid is fixed when the signer starts, not per request, and equals `carbon.chain.models.CARBON_NETUID` (`models.py:25`). | testnet: 567. Mainnet: **HUMAN_INPUT** (`models.py:12-16`: none chosen) |
| B3 | Network | The genesis hash in the signing payload equals the pinned genesis (`development_testnet/operator.py:39` for testnet). | mainnet genesis: **HUMAN_INPUT** |
| B4 | Fee ceiling | The estimated fee (plus any deposit) for the exact extrinsic must be ≤ the ceiling. It is re-estimated immediately before broadcast. Unknown fee means refuse. Tip must be exactly 0. | **HUMAN_INPUT.** The OD-4a code fixes `max_spend_tao` at 0 (`HOST_HANDOFF.md:374-375`), so a positive ceiling needs an owner value and a code path of its own. |
| B5 | Payload form | `info` holds exactly one field, of the one pinned data variant, whose bytes are exactly the ASCII of `sha256:` + 64 `[0-9a-f]`, which is 71 bytes. Uppercase, a missing prefix, any other length, two fields, an empty field or any other variant is refused. Use the same regex as the reader (`commitments.py:33`). | 71 bytes, fixed |
| B6 | Refuse other calls | A new closed refusal, `NOT_A_COMMITMENT`. The existing `sign` op keeps its `btauth/1`-only rule (`signer.py:74-109`) and is never usable for extrinsic bytes. | — |
| B7 | No wrapping | No `Utility.batch` / `batch_all` / `force_batch` / `as_derivative`, `Proxy.proxy` / `proxy_announced`, `Multisig.*`, `Sudo.*`, MEV-shield carrier or any nested call. The signed call bytes are the commitment call itself, at the top level. | — |
| B8 | Mortality and nonce | Mortal era with period ≤ max. The nonce is the hotkey's finalized account nonce, read just before signing. An immortal era is refused. | era max: **HUMAN_INPUT** |
| B9 | Count and window | At most N commit posts per hotkey per UTC day, and only inside the approved window. Enforced by an append-only local commit ledger beside the signer socket. | N, window, expiry: **HUMAN_INPUT** (OD-7: "bounded in count per day and in window") |
| B10 | One in flight | One commit per hotkey at a time. An ambiguous outcome (sent, no finality seen) is reconciled by reading the chain and **never resent** (the OD-4a rule). | — |
| B11 | Closed request | The `commit` op request is exactly `{protocol, op:"commit", netuid, digest}`. Fee, era, nonce and confirmation are never accepted from the socket. A request carrying `confirmed`, `fee`, `call` or raw bytes is `MALFORMED_REQUEST`. | — |
| B12 | Key file hygiene | When the signer starts, it refuses a key file that is group- or world-readable, a symlink, or not owned by the running uid. This mirrors the deployment loader's rule (`deployment.py:51-52`). | Changes signer start for btauth too: owner decision D8 |

---

## 3. How the signer prompts and limits it

### 3.1 Design (recommended working shape, pending D1/D2)

1. **New op `commit`** on the existing socket protocol (`carbon.miner-signer.v1`,
   or bumped to v2), with closed fields (B11). The signer, **not Carbon**, builds
   the call bytes from `(netuid, digest)`, or decodes Carbon-supplied unsigned call
   bytes and checks that they re-encode to exactly B1/B5/B7. Carbon never sends
   opaque bytes for the signer to sign blind.
2. **Confirmation on the signer's own terminal**, where the miner already typed
   their key password when starting it (`signer.py:286-288`, `:355-361`). The
   signer prints:

   ```
   Carbon asks to post an on-chain commitment with hotkey <ss58>
     network   testnet (genesis 0x8f9c…3105)
     netuid    567
     digest    sha256:<64 hex>
     fee       <estimate> TAO (ceiling <HUMAN_INPUT value>)   tip 0
     valid for <era> blocks; today: <k> of <N> commitments used
   Type the last 8 characters of the digest to post, anything else to refuse:
   ```

   Only typed TTY input confirms. Nothing on the socket can confirm. If no answer
   arrives within a bound, the request is `CONFIRMATION_TIMEOUT` and nothing is
   signed.
3. **Keys by path only.** The signer still loads the hotkey from `--key-file` or
   `--wallet/--hotkey` (`signer.py:318-345`). The Launchpad, the agent and the MCP
   door never see a key, a password or a key path. They know only the public
   hotkey (`external_signer.py:229-235`).
4. **Agents never sign.** An agent (Carbon's or the miner's own MCP client) may
   *request* a commit through the status loop. The request result is closed:
   `{"result": "human_action_required", "action": "confirm_commitment", "digest": …}`.
   The agent learns the outcome only by re-reading status, which reads the chain.
   This is the same shape as `sign_registration`
   (`setup_operations.py:284-296`).

### 3.2 Fit with "signer start and registration signing stay human"

- **Signer start** stays human and unchanged, apart from B12.
- **Commit signing** joins registration signing as a third human-only act. The
  difference from registration: registration is signed in the miner's own wallet
  tooling with the **coldkey**. A commitment is signed by the **hotkey** in Carbon's
  signer, with a human confirmation on each post.
- This is a **reversal** of `MINER_EXTERNAL_SIGNER_SECURITY_REVIEW.md:232-236`
  ("will not sign extrinsics, by design"). That reversal is owner decision D1, and
  the security review needs its own amendment.
- **Alternative that needs no reversal (Option R, registration-shaped):** the
  Launchpad shows the digest and a template command or unsigned call for the
  miner's own Bittensor tooling, then confirms by reading the chain. Whether any
  standard tool exposes this call is **UNKNOWN** (it must be checked the same way
  `chain_onboarding.py:134-138` marks btcli `UNVERIFIED`). Option R keeps the
  signer extrinsic-free but gives no Carbon-enforced bounds (B1-B12 become advice).

### 3.3 Where the signer talks to the chain (D2)

- **Option S-online.** The signer reads the nonce, fee and genesis, broadcasts,
  and waits for finality. This is the strongest fee and genesis check (B3/B4), but
  for the first time the key-holding process gets network egress.
- **Option S-offline (recommended to evaluate first).** The Launchpad reads the
  nonce, era block, fee estimate and genesis, and passes them alongside the closed
  request. The signer checks genesis against its pinned constant, tip 0 and era ≤
  max, shows the fee as "Carbon's estimate", builds or verifies the call, and
  returns the signed extrinsic. The Launchpad re-estimates the fee and refuses to
  broadcast above the ceiling. The signature still exists, so it is counted in
  `issued` (`external_signer.py:178-181`), and the mortal era bounds its life.

---

## 4. Launchpad flow (after a frozen submission)

Precondition: the epoch has a frozen candidate (`carbon/battery/campaign.py`,
"freeze and submit", `:13`). Submission goes through `submit_through_intake`
(`campaign.py:1010`).

| Step | Action | Result codes |
|---|---|---|
| L1 | Compute the digest locally: `compile_submission(strategy, contract_digest=…)` (`challenge_contracts.py:185`), then `commitment_digest(strategy["challenge_id"], admitted.contract_digest, recipe.strategy_hash)` (`daemon.py:146`). It must import the daemon's function, never re-implement it. | — |
| L2 | **Show the digest**, its three inputs, the netuid and the network. Warn that a new commitment replaces the hotkey's current one, so a queued submission for another recipe will then fail `commitment_required` (§1.1). | — |
| L3 | Read the current commitment with `ChainCommitmentReader` (read-only, finalized). If it already equals the digest, skip to L7 (idempotent, no spend). | `commitment_reader_unavailable` → stop, retry later |
| L4 | Check B2/B3/B9 locally and estimate the fee (B4). | `commitment_fee_over_ceiling`, `commitment_bound_unset`, `commitment_daily_limit` |
| L5 | **Post:** send the `commit` request to the signer. The UI and agent see `human_action_required: confirm_commitment` until the signer answers. | `signer_refused:<reason>`, `signer_not_running`, `CONFIRMATION_TIMEOUT` |
| L6 | **Wait for finality:** inclusion, then finalization, within a wall bound (engineering, as in `localnet.py:915-921`). Then read back through `ChainCommitmentReader` at the finalized head, which must equal the digest. A timeout after broadcast is `AMBIGUOUS`: reconcile by reading, never resend (B10). | `commitment_ambiguous`, `commitment_not_observed` |
| L7 | **Submit** through the existing intake. If a validator's finalized head lags, it answers `commitment_required`. That code is in `RECEIVED_AGAIN` (`carbon/battery/intake.py:577-588`), so resending later is safe. The supervisor text at `scripts/dev/miner_launchpad/supervisor.py:457-461` changes from "in your own wallet tooling" to the Launchpad step. | existing intake codes |

The MCP door exposes L1-L4 and L6-L7 as tools from the same table as the browser
(agent-first). Only L5's confirmation is human.

---

## 5. Threats and the tests that prove each bound

Signer unit tests go in a new `tests/cpu/test_miner_signer_commit.py`. They use
fakes only: no chain, no real key (a generated `Keypair` in a tmp dir).

| Threat | Bound | Test(s) |
|---|---|---|
| **Replay of a signed extrinsic** | B8, B10 | `test_commit_extrinsic_is_mortal_with_era_at_most_max`; `test_commit_refuses_immortal_era`; `test_commit_uses_finalized_nonce_from_request_context`. On localnet: `test_localnet_resubmitting_the_same_signed_extrinsic_is_rejected_by_chain`. |
| **Replay of a commit request** (double spend) | B9, B10, L3 | `test_second_commit_while_one_in_flight_is_refused`; `test_commit_already_on_chain_is_not_reposted` (L3 reader fake returns the same digest, so the signer is never called and `signatures_obtained()` is unchanged); `test_daily_count_is_enforced_from_the_ledger_across_restarts`. |
| **Stale commitment reused across windows** | (validator side, D6) | `test_admission_records_commitment_block` (exists in shape, `test_chain_commitments.py:120-143`). A freshness test is **blocked on D6**: today `daemon.py:586-590` admits any block. |
| **Wrong netuid** | B2 | `test_commit_refuses_netuid_other_than_configured` (566, 0, 65535, `"567"` as str, bool `True`); `test_signer_start_binds_netuid_and_request_cannot_change_it`. |
| **Wrong network** | B3 | `test_commit_refuses_genesis_mismatch`. |
| **Digest mismatch** | B5, L1 | `test_launchpad_digest_equals_daemon_expected` (same strategy and contract: the Launchpad's L1 value equals the daemon's `expected` at `daemon.py:575`); `test_commit_refuses_malformed_digest` (uppercase, 63/65 hex, missing `sha256:`, trailing newline, unicode digit, 72 bytes); `test_prompt_shows_exactly_the_digest_in_the_call_bytes`; `test_validator_refuses_mismatched_commitment` (reader fake returns another digest → `CommitmentRequired`). |
| **Other call / wrapping / blind signing** | B1, B6, B7, B11 | `test_commit_refuses_any_other_call` (parametrized: registration, transfer, remark, weights, sudo); `test_commit_refuses_batch_or_proxy_wrapped_commitment`; `test_commit_request_with_extra_fields_is_malformed` (`confirmed`, `fee`, `call`, `payload`); `test_sign_op_still_refuses_non_btauth_bytes` (the existing `refusal_for` keeps returning `NOT_A_CARBON_REQUEST` for SCALE bytes). |
| **Fee spike** | B4 | `test_commit_refuses_fee_over_ceiling`; `test_commit_refuses_unknown_fee`; `test_commit_refuses_nonzero_tip`; `test_fee_is_re_estimated_after_confirmation_and_refuses_if_risen` (the fake fee rises between prompt and broadcast, so nothing is broadcast); `test_unset_ceiling_refuses_every_commit` (HUMAN_INPUT `None`). |
| **Agent self-confirmation** | §3.1(2,4) | `test_socket_cannot_confirm` (no TTY input → refused or timed out, never signed); `test_wrong_typed_suffix_refuses`; `test_mcp_commit_tool_returns_human_action_required`. |
| **Key-file exposure** | B12 | `test_signer_refuses_group_readable_key_file` (0640), `…world_readable` (0644), `…symlinked_key_file`, `…key_file_owned_by_other_uid` (skip off Linux); `test_signer_accepts_0600_owned_key_file`; `test_no_key_path_or_password_reaches_launchpad_state_or_logs`. |
| **Overwrite race** | L2 | `test_launchpad_warns_when_a_queued_submission_has_a_different_digest`. |
| **Reader round trip** (closes the UNKNOWNs) | §1.2 | `test_localnet_posted_commitment_reads_back_as_the_71_char_digest` (disposable localnet only); `test_runtime_probe_covers_commitment_call_and_storage` (extends `runtime_probe.py:40-66`). |

A live testnet-567 post is **not** a test. Each one is a chain write from a miner key
under OD-7, and it needs the owner's per-transaction approval (D7).

---

## 6. Owner decisions needed (exact)

- **D1. Signer scope.** Do you reverse `MINER_EXTERNAL_SIGNER_SECURITY_REVIEW.md:236` ("The signer will not sign extrinsics, by design") so that `carbon-miner-signer` gains exactly one extrinsic op, the commitment, with TTY confirmation? If not, Option R applies: the miner posts with their own tooling and Carbon shows the digest and confirms by reading the chain.
- **D2. Chain access from the key-holding process.** If D1 is yes: S-online (the signer broadcasts) or S-offline (the signer signs, the Launchpad broadcasts)?
- **D3. Fee ceiling** per commitment, in TAO, including any deposit, and acceptance that it is a positive spend (OD-4a fixes spend at 0 in code). Also: who funds the hotkey if the hotkey pays (UNKNOWN until 1.2 is pinned)?
- **D4. Count per day, window and expiry** for OD-7(a) commitments, per hotkey. OD-7 requires them, and none is recorded (`HOST_HANDOFF.md:379-382`).
- **D5. Mainnet scope.** OD-7(a) covers netuid 567 only (`DECISIONS.md:15361`). For the mainnet launch: the mainnet netuid and genesis (`models.py:12-25`), and a new approval for miner commitment writes on mainnet. Under testnet = mainnet parity, the same code path serves both, with values set by the owner.
- **D6. Freshness rule.** Must a validator require the commitment block to fall inside a window, for example the submission's tempo or after the previous admission? Today any historical match is admitted (`daemon.py:586-590`), and the gap is listed in `BATTERY_MINER_SUBMISSION_PATHS.md` ("a freshness and window check").
- **D7. Approval sequence.** Is OD-7(a) plus the signer's TTY confirmation the whole authority for each post, or does each post (or each testnet trial) need an OD-4a-style numbered request digest approved by the owner?
- **D8. Key-file hygiene at signer start (B12).** Apply it to every signer start, including btauth-only use? Existing miners with 0644 key files would be refused at start.
- **D9. Maximum mortality era** (blocks) for a signed commitment.
- **D10. Agent initiation.** May an agent (Carbon's, or the miner's MCP client) *request* the commit, with the human confirming only on the signer TTY? Or must the request come from the miner in the browser?

Engineering decisions this scope leaves to the implementer, recorded as working
decisions: the op name and protocol version bump, the ledger location, the wall
bound for finality, refusal code names, and the S-offline wire fields.

## Addendum (2026-10-06): Carbon Validator confirmations
- **btcli cannot post it.** The installed btcli 9.23.2 has no general
  commitment command. Its "commit" is weights commit-reveal only, and
  `subnets` has only set-identity and set-symbol. Option R (miner's own
  tooling) therefore needs SDK code, not btcli, and a signer-mediated poster
  is required either way.
- **SDK path:** the Commitments pallet's `set_commitment`, for netuid 567. The
  exact call composition and fee still have to be pinned from the installed
  SDK source and checked by a localnet round trip.
- **Format:** the reader `chain.commitments.ChainCommitmentReader` reads
  `view.read("commitment", netuid, hotkey_ss58)` at the finalized head. It
  accepts exactly the ASCII `sha256:<64 lowercase hex>`.
- **Value:** `carbon.battery.daemon.commitment_digest(challenge_id,
  contract_digest, strategy_hash)`. The intake's refusal names it ("commit
  <digest> on chain before submitting").
- **Order:** commit, wait for finality, then submit. The daemon compares the
  digest at admission.
