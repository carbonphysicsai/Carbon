# LAUNCHPAD-ACCEPT-02: the strategy commitment in the Launchpad and MCP

**Authority:**
- OWNER-COMMITMENT-POSTER-01 D1 to D10;
- OWNER-COMMITMENT-D6-TIE-01;
- LAUNCHPAD-ACCEPT-01 (the critical path, step A1).

**Status:** SPECIFIED.

## The gap

- A validator deployment with `require_commitment: true` admits a submission
  only against the hotkey's current on-chain commitment of
  `daemon.commitment_digest(challenge, contract_digest, strategy_hash)`.
  Rehearsal 3a's valV2 has that setting.
- `carbon/chain/commitment_poster.py` implements L1 to L7 (`plan`, `post`,
  `commit_then_submit`), but nothing in `scripts/dev/miner_launchpad/` or
  `carbon/miner_mcp/` calls it.
- So a Launchpad submit to such a validator can only end
  `commitment_required`. The Launchpad has a refusal-catalog entry for it
  (`supervisor.py`), and no way forward.

## Build

1. **A `commit` operation in `OPERATIONS`.**
   - It reaches both doors from the one table: browser
     `POST /api/v1/operations/commit`, MCP `carbon_commit`.
   - Its gates are the standard ones: request, profile, replay, registration
     with the signer probe, and campaign.
   - Request: `campaign_id`, and `recommit` (Boolean, default false).
   - It commits the campaign's frozen candidate; there is no free-form
     digest.
   - It runs on the supervisor dispatch queue, because the signer waits on
     its TTY. The immediate result is the plan:
     - the digest;
     - the hotkey's current on-chain commitment and its block;
     - the replacement warning (L2), including any queued submit it would
       strand.
   - The state then advances to `human_action_required: confirm_commitment`.
     `observe` and `campaign_view` show it, and then the read-back digest,
     block and extrinsic hash at finality.
   - The same digest already on chain is not posted again (L3), unless
     `recommit` is set.
2. **Commit before submit.**
   - `submit` reads the hotkey's commitment at the finalized head, read-only,
     before it sends anything.
   - If the commitment is not the frozen candidate's digest, `submit` refuses
     `commitment_required` with `next_step: carbon_commit`. Nothing is
     signed or sent, so the hotkey's tempo window is not spent.
   - A validator answer of `commitment_stale` gets
     `next_step: carbon_commit` with `recommit: true` (L7).
   - **Working decision (delegated, engineering):** require a matching
     commitment before any submit. Every rule-v2 validator Carbon runs
     requires one. The intake's public facts do not say whether it requires
     one, and changing that is the validator domain's call. On testnet 567
     the commitment is one fee-free extrinsic per tempo.
3. **The Graphite miner edition's submit** goes through the same operation,
   so Graphite requests the commitment and the miner confirms it (D10).
4. **The commitment's own refusals** reach both doors with their closed codes
   and next steps. They are the enum in `carbon_miner_signer/commitment.py`
   (`COMMITMENT_NOT_PINNED`, `PAYLOAD_MISMATCH`, `FEE_OVER_CEILING`,
   `ALREADY_COMMITTED_THIS_TEMPO`, `NOT_CONFIRMED`, and the rest) and the
   poster's chain failures.
5. **An outcome-unknown post is never resent** (B10). It is reconciled by
   reading the chain until its mortal era has passed, and `observe` shows
   `RECONCILING` meanwhile.

## Tests

- **Door parity:** browser and MCP give the same result and the same closed
  codes.
- **Submit gating:** submit refused `commitment_required` before any send;
  `commitment_stale` leads to recommit.
- **The agent cannot confirm** (D10): no MCP or browser input completes the
  confirmation.
- **No resend** of an outcome-unknown post.
- **The frozen candidate's digest** equals `daemon.commitment_digest(...)`.
- All of the above use the signer harness and a chain stand-in. That is
  engineering evidence only.
- The real acceptance is the plan's cells F10, F13 and A5.

## Boundaries

- The Launchpad still never holds a key. The signer signs; the Launchpad
  broadcasts (D2).
- Testnet only (D5).
- No change to the validator, the commitment record's pins or the fee
  ceiling.
- This touches hotkey authentication and chain writes. Surface it for the
  owner's security review; tests are not an audit.
