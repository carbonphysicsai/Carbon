# NET-5R — Shielded registration compatibility repair

**Wave:** C0/G2 evidence follow-up
**Status:** `in_progress`

PR #132 merged the eight-block shield-era repair as
`675427ec8852579aa9d336bbec94e28be7b62810`. The exact standard-runtime
comparison has since passed both shielded registrations and the shared-winner
stage, but the canonical full scenario stopped at a source-backed plain-nonce
transition defect before the recycled-UID effect. G2 remains `NOT_READY`.
**Depends on:** NET-5, pinned SDK 11.1.0, v445 disposable localnet runtime
**Decisions:** `NET-5R-D1`, `NET-5R-D2`, `NET-5R-D3`, `NET-5R-D4`
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

## NET-5R-D3 — Register the exact standard-runtime compatibility profile

Pinned upstream `Dockerfile-localnet` builds and copies both release binaries
and WASM artifacts. Pinned `scripts/localnet.sh` selects
`/target/non-fast-runtime/release/node-subtensor` with `False`; its Cargo
features are `pow-faucet metadata-hash`, while the fast build additionally
enables `fast-runtime`. Run 34473145103 verified that both installed artifacts
are executable and distinct before any network or key was created, then bound
the standard binary/WASM hashes and genesis. The node CLI does not expose
`--version` and returns exit 2; isolated RPC subsequently verified runtime v445
and 12-second blocks. This is a compatibility comparison, not a timing or
keystore-cause claim. The original fast profile and its evidence remain intact.

Run 34473508494 performed exactly one authenticated shielded `BurnedRegister`
with retry budget zero. Its carrier and inner finalized in block 17, exact key
query and exclusive expiry were recorded, and registration was read back at
block 19. G2 remained `NOT_READY` pending the full scenario.

## NET-5R-D4 — Refresh the public SDK transport after a successful shield pair

Canonical full run 34474220953 passed both shielded registrations, shared-winner
publication, readback and an observed shared-winner epoch. It then submitted the
plain `SwapHotkey` through `Client.execute(..., retries=0)` and received
`Stale/expired` with no inclusion, so the recycled-UID effect was not observed.

Exact Bittensor 11.1.0 source provides a testable nonce-transition hypothesis.
`submit_shielded` signs the inner at `nonce+1`, and then submits the carrier with
explicit `nonce`. `SubstrateConnection.create_signed_extrinsic` pins each
explicit nonce into its per-transport cache, so the later carrier pin replaces
the higher inner pin. After both extrinsics finalize, a later plain execute on
that transport can increment the retained carrier nonce to the already-consumed
inner nonce. This explains the observed Stale result without attributing it to
runtime speed or proposer keystore behavior.

The smallest supported Carbon candidate verifies the finalized public account
next nonce is exactly `inner_nonce+1`, then retires and recreates the public SDK
`Client`/`RpcSubstrate` under the same endpoint, genesis, runtime and policy
checks. It never accesses the private cache, injects a nonce, retries, submits a
raw/unchecked call or changes network. A local upstream issue draft is retained;
no maintainer was contacted. The changed full scenario has not been rerun.
Notification:
https://github.com/carbonphysicsai/Carbon/issues/42#issuecomment-5618878650.

## Bounded delivery disposition

The source-backed mortality repair, exact standard profile, one-shot diagnostic
and focused contracts pass. The full standard run observed both registrations
and the shared-winner effect, but not the recycled-UID effect, so the full-
scenario Definition-of-Done checkbox remains intentionally open. NET-5R stays
`in_progress` on the changed public-transport-refresh candidate above; G2 stays
`NOT_READY`. No later ticket is selected, and C-EA1's unresolved operating
decisions remain scoped to C-EA1.
