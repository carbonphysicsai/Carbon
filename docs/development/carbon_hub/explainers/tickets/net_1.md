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

NET-1 implements the Bittensor 11.1.0 read-only adapter candidate, immutable finalized provider snapshots and UID registration checks. Native diagnostics pass; required installed-SDK Linux acceptance and normal merge are pending.

## Maturity ceiling

B-GATE retains bounded closure. NET-1 has implementation and native diagnostic evidence; canonical installed-SDK acceptance and merge remain pending. No localnet, scientific, security, production or LIVE qualification.

## Repository detail

- [Repo ticket](https://github.com/carbonphysicsai/Carbon/blob/34b0607565f67d43685831fb2941b74ef7afa420/.agent/tickets/NET-1_chain_adapter.md)
- [Wave C controlling board](https://github.com/carbonphysicsai/Carbon/blob/34b0607565f67d43685831fb2941b74ef7afa420/.agent/WAVE_C.md)
- [Implementation plan](https://github.com/carbonphysicsai/Carbon/blob/34b0607565f67d43685831fb2941b74ef7afa420/.agent/plans/NET-1_chain_adapter.md)
- [Stable evidence](https://github.com/carbonphysicsai/Carbon/blob/34b0607565f67d43685831fb2941b74ef7afa420/.agent/evidence/wave_c/net-1.md)
- [Current launch roadmap](https://github.com/carbonphysicsai/Carbon/blob/34b0607565f67d43685831fb2941b74ef7afa420/launch/Carbon_Testnet_to_Mainnet_Launch_Path_v1.0.6.md)
- [C0 reward execution contract](https://github.com/carbonphysicsai/Carbon/blob/34b0607565f67d43685831fb2941b74ef7afa420/.agent/plans/C0_score_reward_program.md)
- [SDK adapter and upgrades](https://github.com/carbonphysicsai/Carbon/blob/34b0607565f67d43685831fb2941b74ef7afa420/docs/development/CHAIN_ADAPTER.md)

> Read-only local adapter work proceeds without keys or live-chain access. UID meaning is snapshot- and network-bound; missing or malformed provider state fails closed rather than fabricating identity.
