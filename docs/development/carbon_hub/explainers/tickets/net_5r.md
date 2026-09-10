# NET-5R: Shielded registration compatibility repair

**Wave:** C

**Map ref:** `WAVE-C/NET-5R`

**Status:** IN_PROGRESS

**Target phase:** C0/G2

## What and why

Preserve PR #132's eight-block repair, bind the distinct upstream standard runtime without weakening the fast identity, retain public-safe key/author/expiry/hash outcomes, and verify/reopen the public SDK transport after finalized shield pairs.

The standard profile removes the prior authenticated-unshield blocker, while exact SDK source explains why the same transport can later reuse the consumed inner nonce and receive Stale on the first plain submission.

## What it adds

An isolated standard-runtime identity, bounded one-shot registration diagnostic, retained partial full-scenario evidence, minimal reproducer and focused-tested public-transport refresh candidate.

## Placement and handoff

- **Depends on:** NET-5
- **Feeds:** No downstream ticket captured.
- **Driver:** Codex + network/protocol engineering
- **Review route:** Network/protocol + security
- **Master questions:** MQ-054, MQ-056

## Explicit non-goals

No second full run without the changed hypothesis, unchecked extrinsic, private nonce-cache access, timing/keystore cause claim, public endpoint, production key, persistent value, archive decision, scientific qualification or LIVE authority.

## Current stage

PR #133 preserves NET-5R's eight-block repair and exact standard profile. D4 full/standard run 34489505489 passed both registrations, shared-winner, takeover and recycled-UID behavior; the focused-tested D5 successor retains clarified exclusive handover and passive SDK-nonce evidence before G2 can change.

## Maturity ceiling

Disposable C0/G2 compatibility engineering only; actual runtime effects are required before LOCALNET_READY.

## Repository detail

- [Repo ticket](https://github.com/carbonphysicsai/Carbon/blob/d079c7b9686205e80ac74b511031f90ec5fceaba/.agent/tickets/NET-5R_shielded_registration_compatibility.md)
- [Stable evidence](https://github.com/carbonphysicsai/Carbon/blob/d079c7b9686205e80ac74b511031f90ec5fceaba/.agent/evidence/wave_c/net-5r.md)
- [Runtime integration contract](https://github.com/carbonphysicsai/Carbon/blob/d079c7b9686205e80ac74b511031f90ec5fceaba/docs/development/LOCALNET_INTEGRATION.md)
- [Pinned runtime manifest](https://github.com/carbonphysicsai/Carbon/blob/d079c7b9686205e80ac74b511031f90ec5fceaba/scripts/dev/localnet-runtime.json)
- [Wave C board](https://github.com/carbonphysicsai/Carbon/blob/d079c7b9686205e80ac74b511031f90ec5fceaba/.agent/WAVE_C.md)

> Standard versus fast is retained only as a compatibility comparison. Exact SDK source supports the shield-pair nonce transition and public pool-aware nonce readback. D5 permits replacement connection/verification before old closure but requires old closure before activation or later signing/dispatch; ambiguity requires reconciliation. No timing or keystore root cause, retry, nonce injection, unchecked extrinsic or public-network action is permitted.
