# NET-5: Reproducible disposable localnet integration

**Wave:** C

**Map ref:** `WAVE-C/NET-5`

**Status:** IN_PROGRESS

**Target phase:** C0

## What and why

Reproduce the complete fixture-to-chain path and collect actual runtime identity, rows, epochs and recovery evidence.

Unit contracts and source pins cannot prove chain effects, burn behavior or local operation.

## What it adds

An isolated pinned-image runner, guarded local setup, three fixed synthetic exam identities and actual SDK/chain integration tests.

## Placement and handoff

- **Depends on:** NET-4B
- **Feeds:** No downstream ticket captured.
- **Driver:** Codex + network/protocol engineering
- **Review route:** Network/protocol + security
- **Master questions:** MQ-054, MQ-056

## Explicit non-goals

No C1 scientific evidence, public network, treasury, security qualification or automatic G2 readiness.

## Current stage

NET-5 observed three-challenge all-burn finality/rows/epoch burn and restart/outage recovery. Shielded miner registration is unresolved; shared-winner runtime integration and G2 remain unearned. Canonical engineering acceptance is pending.

## Maturity ceiling

Disposable C0 fixture integration only; G2 depends on actual runtime evidence and NET-6 operations.

## Repository detail

- [Repo ticket](https://github.com/carbonphysicsai/Carbon/blob/7bcf1b7fe1b7c545ac41ca42ad7e19c3b6f01b60/.agent/tickets/NET-5_disposable_localnet.md)
- [Stable evidence](https://github.com/carbonphysicsai/Carbon/blob/7bcf1b7fe1b7c545ac41ca42ad7e19c3b6f01b60/.agent/evidence/wave_c/net-5.md)
- [Operator contract](https://github.com/carbonphysicsai/Carbon/blob/7bcf1b7fe1b7c545ac41ca42ad7e19c3b6f01b60/docs/development/LOCALNET_INTEGRATION.md)
- [Wave C board](https://github.com/carbonphysicsai/Carbon/blob/7bcf1b7fe1b7c545ac41ca42ad7e19c3b6f01b60/.agent/WAVE_C.md)

> Targets, stored weights, Yuma outcomes and settled receipts remain separate evidence states.
