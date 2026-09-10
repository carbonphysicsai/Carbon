# NET-5R — Shielded registration compatibility repair

**Wave:** C0/G2 evidence follow-up
**Status:** `in_progress`

The smallest supported Carbon repair is a bounded delivery candidate, but the
canonical full scenario did not pass and G2 remains `NOT_READY`.
**Depends on:** NET-5, pinned SDK 11.1.0, v445 disposable localnet runtime
**Decisions:** `NET-5R-D1`, `NET-5R-D2`
**Primary Hub map_ref:** `WAVE-C/NET-5R`

## Goal

Determine and narrowly repair the observed shielded `BurnedRegister`
`Stale/expired` compatibility failure without bypassing SDK policy or weakening
the signed-extrinsic checks. Preserve exact inner and carrier hashes, era, nonce,
inclusion, finalized readback, replacement-UID observations and the existing full
localnet scenario.

## Definition of Done

- [x] Reproduce only under a stated new hypothesis and capture enough public-safe
      evidence to distinguish timing, key rotation, nonce, era and runtime causes.
- [x] Make the smallest compatible repair without unchecked extrinsics, public
      endpoints, persistent value, or production keys.
- [ ] Pass focused compatibility tests and the existing disposable full scenario
      on canonical Linux amd64 Docker.
- [x] Observe the required shared-winner and recycled-UID effects, or retain G2
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

## First changed-run result and refined hypothesis

Canonical run 34464255826 accepted and finalized the eight-block carrier at
block 258, with the expected key length and inner/carrier nonce and era values,
but did not observe the decrypted inner hash. This falsifies continued
pool-level mortality rejection. Pinned proposer/runtime source narrows the
remaining branch to decapsulation-key availability, ML-KEM/XChaCha unshielding,
or inner-extrinsic push validity; drand is not part of this shield decryptor.
Enable only the pinned proposer/shield debug targets for one changed diagnostic
run. Do not alter the intent, nonce, era, runtime, extrinsic or isolation path.

## NET-5R-D2 — Retain the authenticated unshield blocker

Canonical Linux run 34465977413 at exact head
`b2ff8e607dfd0bf2b116944bd89a130c2b8eb944` ran the full disposable scenario
with the refined debug configuration. The miner carrier
`0x4bbc97f657865be6a9bb74957ae7b88e0aa52b5e0f888410d3cca02cb41cc25b`
and inner
`0xdc0a70d67441a3665e001a27fdea0ae15971f6ba0029b0af82ea8fb6d5a6670b`
both finalized at block 255. The challenger carrier
`0x4c9b0b0721b75c057cf9437a4cc019a561f9b4157de2c8b8770e0691b5268082`
finalized at block 263, but proposer and runtime debug targets both reported
`Failed to unshield transaction`; the exact challenger inner hash
`0x559cabb65387597d99ce7e07f070f8f39ebe37dfdbf98a9bb84e5d1b91c0f87b`
was absent through finalized block 266.

This changed run distinguishes the retained failure from mortality, nonce,
carrier policy, drand and inner-dispatch rejection. The remaining failure is an
intermittent authenticated unshield mismatch in the pinned v445 fast-localnet
proposer/keystore path. Carbon has no supported retry, unchecked-extrinsic,
legacy-registration or runtime-bypass repair. The next interface input must be a
supported upstream repair for that v445 path, or an explicitly authorized new
compatible SDK/runtime pin. Notification:
https://github.com/carbonphysicsai/Carbon/issues/42#issuecomment-5617251068.

## Bounded delivery disposition

The source-backed mortality repair and its focused contracts pass, and both
changed canonical hypotheses were executed once. The full scenario did not pass,
so its Definition-of-Done checkbox remains intentionally open and neither
shared-winner nor recycled-UID evidence is claimed. The smallest supported Carbon
repair is ready to ship, but NET-5R remains `in_progress` on the exact upstream
interface blocker above. G2 remains `NOT_READY`. No later ticket is selected,
and C-EA1's unresolved operating decisions remain scoped to C-EA1.
