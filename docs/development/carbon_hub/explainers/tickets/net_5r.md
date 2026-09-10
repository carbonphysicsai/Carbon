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

NET-5R preserves the merged eight-block repair and adds an exact, isolated standard-runtime profile. Canonical runs 34473145103 and 34473508494 bound that profile and proved one registration; full run 34474220953 proved both registrations and the shared-winner epoch, then failed before recycled-UID evidence on a source-backed SDK nonce-cache transition.

## Maturity ceiling

Disposable C0/G2 compatibility engineering only; actual runtime effects are required before LOCALNET_READY.

## Repository detail

- [Repo ticket](https://github.com/carbonphysicsai/Carbon/blob/6af2d20809efe5ba3c613004ad04f5b49df82013/.agent/tickets/NET-5R_shielded_registration_compatibility.md)
- [Stable evidence](https://github.com/carbonphysicsai/Carbon/blob/6af2d20809efe5ba3c613004ad04f5b49df82013/.agent/evidence/wave_c/net-5r.md)
- [Runtime integration contract](https://github.com/carbonphysicsai/Carbon/blob/6af2d20809efe5ba3c613004ad04f5b49df82013/docs/development/LOCALNET_INTEGRATION.md)
- [Pinned runtime manifest](https://github.com/carbonphysicsai/Carbon/blob/6af2d20809efe5ba3c613004ad04f5b49df82013/scripts/dev/localnet-runtime.json)
- [Wave C board](https://github.com/carbonphysicsai/Carbon/blob/6af2d20809efe5ba3c613004ad04f5b49df82013/.agent/WAVE_C.md)

> Standard versus fast is retained only as a compatibility comparison. Exact SDK source supports a nonce-cache transition hypothesis after the shield pair; no timing or keystore root cause is claimed, and no retry, unchecked extrinsic or public-network action is permitted.
