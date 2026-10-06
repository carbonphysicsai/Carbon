# COMMITMENT-POSTER-01: the miner's on-chain strategy commitment

**Status:** implemented and tested offline. The signer's commit op stays
**off** until the localnet round trip pins the call index, the `Raw71` tag,
the signed-extension order and the fee. Security-sensitive (AGENTS.md §13):
it needs a dedicated security review, and security acceptance is the owner's.
Tests are not an audit.

**Authority:** OWNER-COMMITMENT-POSTER-01 (PR #712,
`.agent/decisions/2026-10-06-OWNER-COMMITMENT-POSTER-01.md`), D1 to D10,
answered under the owner's "bittensor standard and easiest and best for all
parties". OD-7(a) for netuid 567.

**Scope document:** `docs/development/COMMITMENT_POSTER_SCOPE.md` (the Test
Engineer's scope, bounds B1-B12, threats and tests; committed here as drafted).

**Executor:** a Test Engineer subagent. Branch `claude/commitment-poster`,
built on #712's branch (`60b5991c9`, one record commit over main `0fb850833`)
because #712 was not merged at the start.

**Primary hub map_ref:** none changed. The miner signer's purpose changes
(one extrinsic), which the hub owner reconciles when the hub is next
regenerated; this ticket edits no hub output.

## What the SDK pins (bittensor 11.1.0, `site-packages/bittensor/`)

| Fact | Where |
|---|---|
| Call `Commitments.set_commitment(netuid: NetUid, info: CommitmentInfo)` | `_generated/calls.py:862-868` |
| Pallet index 18 | `_generated/errors.py:243` (`(18, n)` are Commitments errors) |
| Data variant `Raw<len>`, read back by concatenating `Raw*` fields as UTF-8 | `reads/identity.py:69-77`, `:90-101` |
| Storage `Commitments.CommitmentOf`; deposits `InitialDeposit`, `FieldDeposit` | `_generated/storage.py:353-354`; `_generated/constants.py:138-141` |
| Fee query: `estimate_fee` -> `partial_fee` via `TransactionPaymentApi_query_info` | `_substrate.py:538-542`; `_transport/interface.py:694-711` |
| Fee payer: the hotkey's owning coldkey, not the hotkey | `fee_filters.py:30` |
| Default era 128 | `settings.py:22` |
| Out-of-process signing: `prepare` / `submit_signature`; payload = call ++ extra ++ additional, blake2b-256 over 256 bytes | `_substrate.py:635-686`; `_transport/extrinsics.py:135-199` |
| Per-epoch space quota (`SpaceLimitExceeded`, at least 100 bytes per call) | `error_descriptions/commitments.py:11-15` |

Not in the SDK source (runtime metadata only): the call index, the `Raw71`
tag byte, the signed-extension order. They are `null` in
`carbon_miner_signer/commitment_record.json` until measured.

## Working decisions (delegated engineering)

1. **S-offline wire shape (D2).** The commit request is closed:
   `{protocol, op: "commit", netuid, digest, unsigned, fee}`. `unsigned` is the
   SDK's `UnsignedExtrinsic.to_dict()` parts (call bytes, era, nonce, tip,
   genesis, era block hash, spec and transaction versions, metadata hash,
   extension bytes); `fee` is the Launchpad's estimate. The scope's B11 said
   nonce and era are never accepted from the socket; under S-offline the
   signer has no other source, so they are accepted as observations and
   checked, never trusted: the signer rebuilds every byte and signs only its
   own reconstruction.
2. **Pins live in a record file** (`commitment_record.json`), loaded once at
   signer start. Any null pin refuses every commit (`COMMITMENT_NOT_PINNED`);
   an inconsistent record (ceiling not 2x the measurement, era cap not a power
   of two within one tempo, an unknown extension) stops the load.
3. **Tempo for D4** is rule v2's 360-block window aligned to multiples of 360
   (`carbon/battery/exam.py:81`). The era cap is min(128, 360) = 128.
4. **The Launchpad trusts the signer's ceiling** (`fee_ceiling_rao` in its
   answer) for the post-confirmation fee re-check, so there is one source.
5. **Launchpad flow as a module** (`carbon/chain/commitment_poster.py`) with a
   human CLI (`python -m carbon.chain.commitment_poster`). Wiring into the
   browser and MCP doors is a follow-up (below).
6. **D6 is the validator's** (the Carbon Validator's own PR). Contract
   documented here: the validator reads only the 71-character `sha256:`
   string and the pallet's own block; a commitment older than the hotkey's
   previous admission is refused `commitment_stale`. The Launchpad answers
   that refusal with an offer to recommit (`commit_then_submit(...,
   recommit=True)`), which still needs the miner's confirmation and a new
   tempo.

## Bounds implemented (all fail closed)

| Bound | Code | Tests |
|---|---|---|
| B1/B6 one call | `commitment.check_request` (call bytes == own build) | `test_any_other_call_is_refused` |
| B7 no wrapping | same | `test_a_wrapped_or_doubled_commitment_is_refused` |
| B2 netuid fixed at start | `CommitPolicy.netuid` from the record | `test_only_the_netuid_fixed_at_start_is_accepted`, `test_signer_start_fixes_the_commit_policy_from_the_record` |
| B3 genesis | pinned testnet genesis | `test_another_networks_genesis_is_refused` |
| B4 fee ceiling, tip 0 | HUMAN_INPUT ceiling; re-check before broadcast | `test_the_fee_ceiling_holds_and_an_unknown_fee_refuses`, `test_a_tip_is_refused`, `test_a_tip_hidden_in_the_extension_bytes_is_refused`, `test_a_fee_that_rose_after_confirmation_is_not_broadcast`, `test_committed_record_is_unpinned_so_every_commit_is_refused` |
| B5 71-byte digest | `is_digest` | `test_a_malformed_digest_is_refused` |
| B8 mortal era <= cap | `check_request`, `mortal_era` | `test_the_era_is_mortal_and_at_most_one_capped_period`, `test_scale_encodings_match_substrate_vectors` |
| B9/D4 one per tempo | `CommitLedger` | `test_one_commitment_per_tempo_survives_a_restart`, `test_a_recommit_in_the_same_tempo_is_refused_by_the_signer` |
| B10 one in flight, never resent | signer lock; poster state file and `_reconcile` | `test_a_second_commit_while_one_is_being_asked_is_refused`, `test_an_unknown_outcome_is_reconciled_by_reading_and_never_resent`, `test_an_expired_unknown_outcome_allows_a_new_request` |
| B11 closed request | exact key sets at every level | `test_a_request_with_any_other_field_is_malformed` |
| B12/D8 key file | `key_file_problem` at start, before opening | `test_a_key_file_others_can_read_is_refused_with_the_fix`, symlink, other uid, `test_signer_start_refuses_before_opening_the_key` |
| D10 only the terminal confirms | `tty_confirm` reads `/dev/tty` only | `test_an_agent_cannot_confirm_its_own_request`, `test_only_the_typed_suffix_confirms_on_the_terminal` (pty), `test_without_a_terminal_nothing_can_confirm`, `test_an_agent_can_request_but_only_the_terminal_confirms` |
| L1 digest | `expected_digest` imports the daemon's function | `test_the_launchpad_digest_is_the_daemons_expected_digest` |
| L3 skip | `post` | `test_a_digest_already_on_chain_is_not_reposted` |
| L6 verify before broadcast | `post` | `test_a_returned_call_other_than_the_prepared_one_is_not_broadcast`, `test_a_signature_over_anything_else_is_not_broadcast` |
| D6 stale | `commit_then_submit` | `test_a_stale_commitment_is_offered_a_recommit_and_recommitted` |

## HUMAN_INPUT and unmeasured

- `fee.measured_fee_rao`, `fee.measured_deposit_rao`, `fee.ceiling_rao` (D3:
  ceiling = 2 x measured fee + deposit) — HUMAN_INPUT until the localnet
  measurement is recorded.
- `call.call_index`, `call.data_tag`, `extensions`, `zero_sized_extensions` —
  unmeasured; the localnet round trip prints them.
- Mainnet netuid and genesis (D5) — deferred to the mainnet launch record.
- Security acceptance of the signer change.

## Localnet round trip (executor; agents never start a chain)

On a host where the executor may run Docker, from this branch's worktree with
the locked `.venv`:

```bash
image="$(.venv/bin/python -c 'import json;p=json.load(open("scripts/dev/localnet-runtime.json"));print(p["image"]+"@"+p["image_digest"])')"
startup="$(.venv/bin/python -c 'from carbon.chain.localnet import startup_for;print(startup_for("fast"),end="")')"
docker run --detach --rm --name carbon-commitment-localnet --platform linux/amd64 \
  -p 127.0.0.1:9944:9944 --entrypoint /bin/bash "$image" -c "$startup"
# wait until the node produces blocks (docker logs -f carbon-commitment-localnet)
CARBON_COMMITMENT_LOCALNET=1 .venv/bin/python scripts/dev/commitment_localnet_roundtrip.py \
  --endpoint ws://127.0.0.1:9944 --setup --out .carbon-artifacts/commitment
docker stop carbon-commitment-localnet
```

- `--setup` creates netuid 2 with `//Alice` and registers `//Bob` on it, as
  the disposable harness does. Drop it on a chain already set up that way.
- The signer prompts **on this terminal**. Check the digest and fee, type the
  last 8 characters. If it asks a second time (a different digest, only when
  the first post crossed a tempo boundary), press Enter to refuse.
- Success is exit 0 and `.carbon-artifacts/commitment/commitment-roundtrip.json`
  with `read_back_is_digest`, `replay_rejected` and
  `second_refused_by_ledger` all true. Its `record` is the pinned record:
  call index, `Raw71` tag, extension order, and the fee measured as the fee
  actually paid (else the estimate) plus the pallet deposit, with the ceiling
  at 2x.
- **Recording D3:** copy `record.call.call_index`, `record.call.data_tag`,
  `record.extensions`, `record.zero_sized_extensions` and `record.fee` into
  `carbon_miner_signer/commitment_record.json` in a normal commit, with the
  evidence file's digest in the commit message. The owner's acceptance of the
  ceiling number is that commit's review. Until then every commit is refused.
- If 9944 is not reachable from the host (the image's RPC binding), stop and
  report; the fallback is a new opt-in step inside the disposable harness's
  own process relay (`carbon/chain/localnet.py`), which this ticket did not
  change.

## Testnet 567 trial (the human only; no agent signs or broadcasts)

After the pinned record is merged:

1. The miner's rehearsal hotkey is registered on 567; its key file is mode
   600 and owned by the miner (`chmod 600 <file>` otherwise; the signer says
   so and refuses to start).
2. Start `carbon-miner-signer --wallet <W> --hotkey <H>` in its own terminal.
   It prints "On-chain commitments: testnet netuid 567". Its coldkey pays the
   fee (testnet TAO).
3. Get the digest for a frozen candidate (`expected_digest(strategy,
   contract_digest)`), then in a second terminal:
   `python -m carbon.chain.commitment_poster --hotkey <ss58> --digest <sha256:...> --plan`
   and, if `needed` is true, the same without `--plan`.
4. In the signer's terminal, check network, netuid, digest and fee, then type
   the digest's last 8 characters.
5. The poster prints `commitment_committed` with the block. Submit through the
   intake. A validator answering `commitment_stale` gets `--recommit` in a
   later tempo.

## Validation

- `pytest tests/cpu/test_miner_signer_commit.py tests/cpu/test_commitment_poster.py tests/cpu/test_external_signer.py tests/cpu/test_chain_commitments.py tests/invariants/test_product_process_holds_no_key.py tests/invariants/test_attack_store_unreachable.py`
- `QUALITY_BASE_SHA=$(git rev-parse origin/main) CARBON_CANDIDATE_SHA=$(git rev-parse HEAD) ./scripts/dev/ci_preflight.sh`
- `python scripts/check_quality.py --base origin/main`
- `python -m carbon.challenge_pipeline validate`

## Maturity ceiling

SPECIFIED, IMPLEMENTED, TESTED (offline, fakes and a real signer socket).
Not run on any chain. Not SECURITY_QUALIFIED. Nothing here is LIVE.

## Follow-ups

- Wire `CommitmentPoster.plan/start/status` into the Launchpad's browser
  route and MCP tool table (`scripts/dev/miner_launchpad/`), and the
  frozen-candidate submit path (`campaign.submit_through_intake`) through
  `commit_then_submit`.
- Extend `carbon/chain/runtime_probe.py` `SURFACE` with
  `Commitments.set_commitment` and `CommitmentOf`.
- The dedicated security review of the signer amendment
  (`MINER_EXTERNAL_SIGNER_SECURITY_REVIEW.md` §9).
