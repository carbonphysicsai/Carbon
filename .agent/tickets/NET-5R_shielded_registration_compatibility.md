# NET-5R — Shielded registration compatibility repair

**Wave:** C0/G2 evidence follow-up
**Status:** `in_progress`; selected under the existing C0 authorization
**Depends on:** NET-5, pinned SDK 11.1.0, v445 disposable localnet runtime
**Decision:** `NET-5R-D1`
**Primary Hub map_ref:** `WAVE-C/NET-5R`

## Goal

Determine and narrowly repair the observed shielded `BurnedRegister`
`Stale/expired` compatibility failure without bypassing SDK policy or weakening
the signed-extrinsic checks. Preserve exact inner and carrier hashes, era, nonce,
inclusion, finalized readback, replacement-UID observations and the existing full
localnet scenario.

## Definition of Done

- [ ] Reproduce only under a stated new hypothesis and capture enough public-safe
      evidence to distinguish timing, key rotation, nonce, era and runtime causes.
- [ ] Make the smallest compatible repair without unchecked extrinsics, public
      endpoints, persistent value, or production keys.
- [ ] Pass focused compatibility tests and the existing disposable full scenario
      on canonical Linux amd64 Docker.
- [ ] Observe the required shared-winner and recycled-UID effects, or retain G2
      NOT_READY with the exact remaining blocker.

## Boundaries

The previous all-burn and operator evidence remains valid. Do not rerun the
unchanged failing command, infer a cause from `Stale/expired`, relabel unit tests
as runtime evidence, or perform a public-network transaction. Treasury remains
optional and irrelevant to this repair.

## NET-5R-D1 — Source-confirmed mortality hypothesis

The retained operation signed both inner and carrier with a 64-block mortal era.
The exact SDK 11.1.0 wheel instead defines `MEV_SHIELD_ERA_PERIOD = 8`. At the
independently pinned v445 source commit, `runtime/src/check_mortality.rs` defines
`MAX_SHIELD_ERA_PERIOD = 8` and rejects `submit_encrypted` periods above that
ceiling immediately as `InvalidTransaction::Stale`. The retained `Stale/expired`
receipt and absence of both hashes in finalized blocks are therefore predicted
by the unsupported Carbon override, without assuming a key-rotation failure.

Use the SDK's exact eight-block setting and fail closed if that installed value
drifts. Journal a digest and length of the public ephemeral key plus exact inner
and carrier nonce/era values before signing/submission. Keep the existing SDK
intent, encryption, policy, identity guards, exact hashes and finalized lookup.
This changes no runtime, key, nonce algorithm, retry policy or public endpoint.
Only a fresh disposable chain with this changed configuration may test the
hypothesis.
