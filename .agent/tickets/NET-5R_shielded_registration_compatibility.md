# NET-5R — Shielded registration compatibility repair

**Wave:** C0/G2 evidence follow-up
**Status:** `future_reserved`; unselected and blocked on a new testable hypothesis
**Depends on:** NET-5, pinned SDK 11.1.0, v445 disposable localnet runtime

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
