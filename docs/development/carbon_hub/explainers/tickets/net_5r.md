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

NET-5R repairs Carbon's unsupported 64-block shield override, fails closed on SDK/runtime drift, and retains public-safe key/nonce/era diagnostics. Canonical run 34465977413 proved one complete registration and isolated the next failure to authenticated unshielding in the pinned v445 fast-localnet proposer/keystore path.

## Maturity ceiling

Disposable C0/G2 compatibility engineering only; actual runtime effects are required before LOCALNET_READY.

## Repository detail

- [Repo ticket](https://github.com/carbonphysicsai/Carbon/blob/e45be8ae28e20c471983b7f96165eb45dcc03b9e/.agent/tickets/NET-5R_shielded_registration_compatibility.md)
- [Stable evidence](https://github.com/carbonphysicsai/Carbon/blob/e45be8ae28e20c471983b7f96165eb45dcc03b9e/.agent/evidence/wave_c/net-5r.md)
- [Runtime integration contract](https://github.com/carbonphysicsai/Carbon/blob/e45be8ae28e20c471983b7f96165eb45dcc03b9e/docs/development/LOCALNET_INTEGRATION.md)
- [Pinned runtime manifest](https://github.com/carbonphysicsai/Carbon/blob/e45be8ae28e20c471983b7f96165eb45dcc03b9e/scripts/dev/localnet-runtime.json)
- [Wave C board](https://github.com/carbonphysicsai/Carbon/blob/e45be8ae28e20c471983b7f96165eb45dcc03b9e/.agent/WAVE_C.md)

> The retained Stale receipt alone was not treated as a cause; exact SDK/runtime source established mortality, and changed debug evidence isolated the remaining pinned-runtime unshield branch.
