# NET-1 — Read-only Bittensor chain adapter and identity snapshots

**Wave:** C0 network foundation
**Status:** `done`
**Depends on:** B-GATE
**Plan:** `.agent/plans/NET-1_chain_adapter.md`
**Evidence:** `.agent/evidence/wave_c/net-1.md`
**Primary Hub map_ref:** `WAVE-C/NET-1`

## Goal

Implement the smallest usable, SDK-backed, read-only Carbon chain boundary for
network/metagraph snapshots and wallet/hotkey-to-UID associations without
loading private keys, contacting a live chain in tests, or exposing signing,
publication, or SDK objects outside `carbon.chain`.

## NET-0 boundary prerequisite

The exact dispositions live in `.agent/WAVE_C.md` §2. The Carbon/chain
ownership, SDK containment, and read-only local topology are sufficient for
this ticket. Broader threat-model acceptance, authenticated transport, replay,
custody, reward-window, sink, quorum/stake, production topology, deployment,
and economic choices remain unresolved in their later owning operations and do
not block the independently testable read-only subset.

## Definition of Done

- [x] Define a narrow Carbon-owned `ChainAdapter` interface whose public
      operations are read-only and return only Carbon-owned immutable types.
- [x] Represent explicit network, endpoint/provider, netuid, observed chain,
      and snapshot context sufficient to prevent timeless/cross-network
      interpretation of hotkey, wallet, or UID associations.
- [x] Map SDK metagraph responses into a bounded read-only snapshot including
      wallet/hotkey identity and UID associations; represent UID absence and
      reassignment by comparison of exact snapshots rather than mutation or a
      timeless registry.
- [x] Classify provider unavailable, timeout/transport, malformed,
      incomplete, identity-mismatch, and unsupported responses without
      fabricated state, partial success, exception leakage, or silent defaults.
- [x] Implement the adapter against an exact compatible Bittensor SDK pin
      verified from official package metadata and documentation. SDK imports,
      clients, responses, and exceptions remain inside `carbon.chain`.
- [x] Prove import and construction perform no network call, wallet/key load,
      background refresh, authentication, signing, transaction, publication,
      or chain mutation.
- [x] Add deterministic fake-backed tests for translation, exact
      network/snapshot/identity consistency, UID absence/reassignment,
      malformed/incomplete/unavailable responses, failure classification, SDK
      containment, and the absence of write behavior.
- [x] Update the managed dependency lock, CODE_AUTHORITY if needed, stable
      evidence, maturity ledger, Wave C board, and Development Hub; run focused
      tests and one applicable ready-revision acceptance, then normally merge
      the tested expected head under OWNER-DX-03.

## Must not

Do not implement NET-2 transport, NET-3 candidate commitments, NET-4 intents or
weights, NET-5 localnet, NET-6 deployment; contact a live chain; load private
keys; sign or submit transactions; publish weights; accept raw scientific
results or score dictionaries; expose SDK objects as Carbon science; or claim
scientific, security, network, production, LIVE, testnet, or mainnet
qualification.

## Completion handoff

If every criterion passes and the exact tested head merges normally, mark
NET-1 `done` in bounded local read-only engineering scope and identify NET-2 as
the next dependency-ready ticket and continue under OWNER-C0-REWARD-01. Live integration stays
explicitly unverified.
