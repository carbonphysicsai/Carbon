# NET-5: Reproducible disposable localnet integration

**Wave:** C

**Map ref:** `WAVE-C/NET-5`

**Status:** DONE

**Target phase:** C0

## What and why

Reproduce the complete fixture-to-chain path and collect actual runtime identity, rows, epochs and recovery evidence.

Unit contracts and source pins cannot prove chain effects, burn behavior or local operation.

## What it adds

An isolated pinned-image runner, guarded local setup, three fixed synthetic exam identities and actual SDK/chain integration tests.

## Placement and handoff

- **Depends on:** NET-4B
- **Feeds:** NET-6, NET-5R
- **Driver:** Codex + network/protocol engineering
- **Review route:** Network/protocol + security
- **Master questions:** MQ-054, MQ-056

## Explicit non-goals

No C1 scientific evidence, public network, treasury, security qualification or automatic G2 readiness.

## Current stage

NET-5 merged in PR #126 with canonical tests and actual all-burn finality, rows, epochs and restart/outage recovery. Shielded miner registration and shared-winner runtime evidence remain unresolved; G2 is NOT_READY.

## Maturity ceiling

Disposable C0 fixture integration only; G2 depends on actual runtime evidence and NET-6 operations.

## Repository detail

- [Repo ticket](https://github.com/carbonphysicsai/Carbon/blob/d958a2ec694f3d937b642b4d8524f2fc166f8273/.agent/tickets/NET-5_disposable_localnet.md)
- [Stable evidence](https://github.com/carbonphysicsai/Carbon/blob/d958a2ec694f3d937b642b4d8524f2fc166f8273/.agent/evidence/wave_c/net-5.md)
- [Operator contract](https://github.com/carbonphysicsai/Carbon/blob/d958a2ec694f3d937b642b4d8524f2fc166f8273/docs/development/LOCALNET_INTEGRATION.md)
- [Wave C board](https://github.com/carbonphysicsai/Carbon/blob/d958a2ec694f3d937b642b4d8524f2fc166f8273/.agent/WAVE_C.md)

> Targets, stored weights, Yuma outcomes and settled receipts remain separate evidence states.
