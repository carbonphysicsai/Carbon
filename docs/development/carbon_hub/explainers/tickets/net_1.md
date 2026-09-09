# NET-1: Read-only Bittensor chain adapter and identity snapshots

**Wave:** C

**Map ref:** `WAVE-C/NET-1`

**Status:** IN_PROGRESS

**Target phase:** C0

## What and why

Add a pinned, SDK-backed read-only ChainAdapter for network/metagraph snapshots and wallet/hotkey-to-UID associations with exact network and snapshot context.

Carbon needs network discovery and identity without letting SDK objects, mutable UID assignments, provider failures, keys, or write operations enter scientific authority.

## What it adds

A narrow Carbon-owned interface, immutable snapshot/identity types, classified provider failures, an exact compatible SDK pin, and deterministic fake-backed translation tests.

## Placement and handoff

- **Depends on:** B-GATE
- **Feeds:** No downstream ticket captured.
- **Driver:** Codex + network/protocol engineering
- **Review route:** Network/protocol + security
- **Master questions:** MQ-054, MQ-056

## Explicit non-goals

NET-1 does not authenticate requests, bind candidates, sign or publish transactions or weights, run localnet, deploy nodes, load keys, contact a live chain in tests, or earn scientific, security, network, production, LIVE, testnet, or mainnet qualification.

## Current stage

NET-1 is the sole selected C0 ticket. It will add a pinned, SDK-contained, read-only ChainAdapter with explicit network/snapshot identity, metagraph hotkey/UID associations, and classified provider failures. No live-chain, key, signing, publication, or deployment action is authorized.

## Maturity ceiling

The transition earns specification/selection only. NET-1 may later earn bounded local read-only implementation and test maturity; scientific, security, network, commercial, production, LIVE, launch, testnet, mainnet, weight, transaction, custody, emission, frontier, treasury, and settlement authority remain unearned.

## Repository detail

- [Repo ticket](https://github.com/carbonphysicsai/Carbon/blob/29d6a6d35918ebf796c76c12e930c99d45f80d91/.agent/tickets/NET-1_chain_adapter.md)
- [Wave C controlling board](https://github.com/carbonphysicsai/Carbon/blob/29d6a6d35918ebf796c76c12e930c99d45f80d91/.agent/WAVE_C.md)
- [Implementation plan](https://github.com/carbonphysicsai/Carbon/blob/29d6a6d35918ebf796c76c12e930c99d45f80d91/.agent/plans/NET-1_chain_adapter.md)
- [Stable evidence](https://github.com/carbonphysicsai/Carbon/blob/29d6a6d35918ebf796c76c12e930c99d45f80d91/.agent/evidence/wave_c/net-1.md)
- [Current launch roadmap](https://github.com/carbonphysicsai/Carbon/blob/29d6a6d35918ebf796c76c12e930c99d45f80d91/launch/Carbon_Testnet_to_Mainnet_Launch_Path_v1.0.5.md)

> Read-only local adapter work proceeds without keys or live-chain access. UID meaning is snapshot- and network-bound; missing or malformed provider state fails closed rather than fabricating identity.
