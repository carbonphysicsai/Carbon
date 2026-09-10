# NET-5R: Shielded registration compatibility repair

**Wave:** C

**Map ref:** `WAVE-C/NET-5R`

**Status:** IN_PROGRESS

**Target phase:** C0/G2

## What and why

Replace Carbon's unsupported 64-block shield era with the pinned eight-block setting and retain key, nonce, era, inner/carrier hash and finalized-readback diagnostics.

The v445 runtime rejects submit_encrypted mortality above eight as Stale, so the old override prevented the required registration from reaching a block.

## What it adds

A fail-closed SDK/runtime compatibility check, public-safe shield diagnostics and one changed full disposable-localnet hypothesis test.

## Placement and handoff

- **Depends on:** NET-5
- **Feeds:** No downstream ticket captured.
- **Driver:** Codex + network/protocol engineering
- **Review route:** Network/protocol + security
- **Master questions:** MQ-054, MQ-056

## Explicit non-goals

No unchecked extrinsic, blind retry, public endpoint, production key, persistent value, archive decision, scientific qualification or LIVE authority.

## Current stage

NET-5R replaces Carbon's unsupported 64-block shield override with the pinned SDK/runtime eight-block period, fails closed on drift, and adds public-safe key/nonce/era diagnostics. Canonical full-localnet execution remains pending.

## Maturity ceiling

Disposable C0/G2 compatibility engineering only; actual runtime effects are required before LOCALNET_READY.

## Repository detail

- [Repo ticket](https://github.com/carbonphysicsai/Carbon/blob/46846def752586b1188cbdfc442300c4e0fac3ec/.agent/tickets/NET-5R_shielded_registration_compatibility.md)
- [Stable evidence](https://github.com/carbonphysicsai/Carbon/blob/46846def752586b1188cbdfc442300c4e0fac3ec/.agent/evidence/wave_c/net-5r.md)
- [Runtime integration contract](https://github.com/carbonphysicsai/Carbon/blob/46846def752586b1188cbdfc442300c4e0fac3ec/docs/development/LOCALNET_INTEGRATION.md)
- [Pinned runtime manifest](https://github.com/carbonphysicsai/Carbon/blob/46846def752586b1188cbdfc442300c4e0fac3ec/scripts/dev/localnet-runtime.json)
- [Wave C board](https://github.com/carbonphysicsai/Carbon/blob/46846def752586b1188cbdfc442300c4e0fac3ec/.agent/WAVE_C.md)

> The retained Stale receipt alone was not treated as a cause; exact SDK and runtime source establish the changed mortality hypothesis.
