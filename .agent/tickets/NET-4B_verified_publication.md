# NET-4B — Verified complete-vector publication and recovery

**Wave:** C0 network foundation
**Status:** `done`
**Depends on:** NET-4A
**Primary Hub map_ref:** `WAVE-C/NET-4B`
**Evidence:** `.agent/evidence/wave_c/net-4b.md`
**Starting main:** ba88aa8bb6360fc101ec4bc3afc5c0f4408ccd5f (PR #124).
**Authority:** OWNER-C0-REWARD-01; launch v1.0.6; NET-1/4A and C-REWARD;
Build Out/overlay; OWNER-DX-03 and OWNER-C0-VALIDATION-01.

## Working contract and plan

KEEP read-only ChainAdapter, nominal localnet intents and existing SQLite journal.
Add publication capability/complete-vector compiler, an isolated Bittensor 11.1.0
execution shim and durable publisher/reconciliation/heartbeat in carbon.chain.
SDK objects, signing and raw provider errors stay in that boundary. No public
network is enabled. The pinned v445 runtime owner-associated miner incentive burn
path is the only supported sink; arbitrary recipients or zero vectors are rejected.

1. Bind runtime capabilities and recipient identities to fresh finalized snapshots;
   compile complete targets and prove quantization tolerance without loser shares.
2. Validate final SDK integer vectors during each build before encryption/signing;
   retain SDK policy/execute path and test actual installed 11.1.0 rebuilding.
3. Journal intent/plan before dispatch and transaction identity before wire submit.
   Separate inclusion/finality, timelock reveal, stored row and settlement receipts;
   reconcile ambiguous dispatch before any new publication.
4. Add decay/no-winner heartbeat, stale exposure and recovery; test deterministic
   failures, races, restart/replay and installed-SDK plain/timelock contracts.
5. Focused canonical acceptance, Hub reconciliation and guarded merge. NET-5 owns
   actual disposable runtime execution/epoch evidence and is next after delivery.

## Definition of Done

- [x] Runtime pin/genesis, Burn mode, owner sink identity, mechanism count and
      min/max/version/rate/permit constraints are explicit and checked. Owners'
      miner incentives burn; owner cut and validator dividends remain distinct.
- [x] Complete challenge targets aggregate shared holders before UID conversion.
      Missing/recycled or owner-associated payable identities fail publication;
      the next fresh projection burns unusable winners. No loser floor, arbitrary
      sink, earned-subset normalization or cross-challenge redistribution.
- [x] Quantization tolerance is explicit and tested for dust, singleton winner plus
      burn, all-burn, zero recipients, max clipping, min counts and shared winners.
      Unsupported configurations fail with concrete capability reasons.
- [x] Installed SDK build/execute final integers are checked before encryption or
      signing, including execution rebuilding and changed UID/runtime state. A
      narrow version-specific shim is isolated and contract-tested; no global patch,
      broad SDK fork, policy bypass or arbitrary unchecked extrinsic.
- [x] Durable intent/dispatch/transaction identity precedes effects. Exact replay
      is idempotent. Interrupted/ambiguous outcomes block blind resend; bounded
      finalized-block backfill reconciles observed transactions and rows.
- [x] Plain and SDK timelock paths retain distinct reveal state. Inclusion,
      finality, reveal, stored row and settlement are never conflated. Actual
      localnet mode/epoch claims remain NET-5 evidence requirements.
- [x] Heartbeat publishes fresh decay and explicit all-burn updates, handles
      outages/reconnect/restart, and exposes stale stored-weight risk. Local expiry
      or process shutdown never reports zero ongoing payout without chain evidence.
- [x] Focused tests, installed-SDK contracts, invariants and applicable automated
      acceptance pass. No real science, security qualification, public operation,
      treasury deployment, G2 or LIVE claim.

## NET-4B-D1

Use v445 mechanism 0 and a complete challenge ledger; the runtime defaults to one
mechanism and permits at most two, so mechanisms are not challenge purses. Verify
RecycleOrBurn=Burn and the registered SubnetOwnerHotkey/owner-owned hotkeys at the
observed snapshot. MinerBurned alone cannot prove burn because it includes recycle.
Require a supported configuration (development min count 1, max limit 65535 is the
reference); fail configurations that distort targets beyond quantization tolerance.

Subclass the SDK's public SetWeights extension, narrowly mirroring its version-pinned
build to insert the final integer guard before `_build_timelocked` or composition.
Keep Client.execute policy validation. A version-specific RpcSubstrate reporting
hook records the signed transaction hash before submission. Ambiguous dispatch
without sufficient evidence remains blocked, with a concrete reconciliation state;
it is not silently reset. SDK/runtime upgrades must rerun these contracts.

Hub impact: map_structural; WAVE-C/NET-4B primary, NET-4A, chain/reward and CI affected.
Dedicated security qualification remains future human-owned; local tests are not
that acceptance. Notification is asynchronous under standing authorization.

## Accepted delivery

PR #125 passed run 34421219713 (1,848 focused CPU, 180 invariants, package,
quality, Hub and Merge gate), normally merged as 0e6b5e001302b349135785756c633530853684c2.
Completion: https://github.com/carbonphysicsai/Carbon/pull/125#issuecomment-5610763822.
Bounded implementation/test maturity; actual localnet evidence belongs to NET-5.
