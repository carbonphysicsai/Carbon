# NET-5R shielded registration compatibility evidence

**Status:** bounded NET-5R engineering complete; smallest supported repair and
two changed canonical full-scenario executions retained; G2 `NOT_READY`.

**Starting main:** `a3ca8cd111689329832131eac1460d579c7828b3`
(PR #131).

**Ticket:** `.agent/tickets/NET-5R_shielded_registration_compatibility.md`.

**Primary Hub map_ref:** `WAVE-C/NET-5R`.

**Decisions:** `NET-5R-D1`, `NET-5R-D2`.

**Lead notification:**
https://github.com/carbonphysicsai/Carbon/issues/42#issuecomment-5616806419.

## Retained failure and testable hypothesis

Run 34425822745 signed the `BurnedRegister` inner and `MevShield` carrier with
Carbon's explicit 64-block era. It returned typed `Stale/expired`; the journaled
inner hash `0xc8a7effbf498374941364256c421e8f092614b35d62997c1631f504b7974fb6f`
and carrier hash `0xbbb441b9d20a3c6110f6508011e1dd7a9ced2d8454264a8f096de277ad5f0df6`
were both absent from the finalized scan through block 250.

The exact `bittensor==11.1.0` wheel locked by `uv.lock` has SHA-256
`d84e33169249c56c41b4b43f6b2f4ed80bc2fd98afcb69a3d5844720a4d72b58`
and defines `MEV_SHIELD_ERA_PERIOD = 8`. Independently, pinned runtime commit
`d3f40e44bda9019c606aeb0c907bb52ba7fe386c` defines
`MAX_SHIELD_ERA_PERIOD = 8` in `runtime/src/check_mortality.rs`; its validation
returns `InvalidTransaction::Stale` for longer `submit_encrypted` eras. This
predicts the retained pool-level rejection and empty finalized scan directly.

## Candidate repair and evidence boundary

Carbon now uses the exact installed SDK value and fails closed if it differs
from eight or if the signed inner/carrier period changes. Before submission the
existing journal additionally records the public ephemeral-key digest and
length, exact inner/carrier nonce and era, and the pre-existing inner/carrier
hashes. No unchecked call, legacy registration, storage injection, retry,
runtime change, persistent key, public endpoint or production token is added.

Focused installed-SDK contracts and the canonical Linux full scenario remain
required. Until successful registration, shared-winner publication and recycled
UID isolation have all been observed on that disposable runtime, G2 remains
NOT_READY.

## Changed canonical run 34464255826

The first eight-block candidate ran at exact head
`dcd8dc773c825400b2cf6636c22bb704758b5218` on Ubuntu 24.04 amd64. Setup and
installed Bittensor 11.1.0 contracts passed. The `register-miner` carrier
`0x1f1c63e85547a917f93a260a569e1d4b4261bc44c5bee977c432662cc6995b1d`
was accepted and finalized at block 258, proving that the 64-to-8 repair moved
the operation past the retained pool-level `Stale` rejection. Its public-safe
diagnostics recorded a 1184-byte key, inner nonce 1, carrier nonce 0 and era 8.
The inner hash
`0xde3bb6ce5f1e9fef831e0dd956a1ade13cbacc957192e7302ecd8f8344ddb55c`
did not appear before its era, so the shared-winner and recycled-UID stages did
not run and G2 remains `NOT_READY`.

Pinned source excludes the concurrent drand HTTP errors as the cause of this
ML-KEM path: the shield proposer decrypts with its in-memory per-author
decapsulation key and the runtime performs ML-KEM/XChaCha unshielding. Because
the wrapper was included, the proposer had already accepted its key hash. The
remaining bounded alternatives are unavailable local decapsulation key,
failed unshielding, or rejection while pushing the decrypted inner extrinsic.
The retained info-level log cannot distinguish them. The next changed run
therefore enables only pinned proposer/shield debug targets; it changes the
diagnostic configuration and tests this exact three-way hypothesis without
changing, bypassing or retrying the registration operation.

## Refined changed run 34465977413

The refined canonical Ubuntu 24.04 amd64 run executed at exact head
`b2ff8e607dfd0bf2b116944bd89a130c2b8eb944`. Setup and the installed
Bittensor 11.1.0 contracts passed. The miner carrier
`0x4bbc97f657865be6a9bb74957ae7b88e0aa52b5e0f888410d3cca02cb41cc25b`
and exact inner
`0xdc0a70d67441a3665e001a27fdea0ae15971f6ba0029b0af82ea8fb6d5a6670b`
both finalized at block 255. Debug evidence records `Unshielded inner
transaction` and `Pushed unshielded transaction to the block` for that carrier.

The challenger used a distinct 1184-byte public key digest, inner nonce 1,
carrier nonce 0 and era 8. Its carrier
`0x4c9b0b0721b75c057cf9437a4cc019a561f9b4157de2c8b8770e0691b5268082`
finalized successfully at block 263, while both `mev-shield` and
`basic-authorship` reported `Failed to unshield transaction`. The exact inner
`0x559cabb65387597d99ce7e07f070f8f39ebe37dfdbf98a9bb84e5d1b91c0f87b`
was absent through finalized block 266. This excludes a continued mortality or
pool rejection, nonce mismatch, drand dependency and post-decrypt inner push
failure for the unsuccessful operation.

The exact retained artifact set and hashes are in
`.agent/evidence/wave_c/net-5r-runtime/34465977413/manifest.json`; the workflow
is https://github.com/carbonphysicsai/Carbon/actions/runs/34465977413. The full
scenario failed at `register-challenger`, so shared-winner and recycled-UID
effects remain unobserved. G2 remains `NOT_READY` on an intermittent
authenticated unshield mismatch in the pinned v445 fast-localnet
proposer/keystore path. A supported upstream repair for that path, or an
explicitly authorized compatible SDK/runtime pin, is required; Carbon adds no
blind retry, unchecked extrinsic, legacy registration or public-network action.
