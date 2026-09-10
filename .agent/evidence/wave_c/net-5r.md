# NET-5R shielded registration compatibility evidence

**Status:** selected candidate; source-confirmed hypothesis and smallest repair
implemented; canonical full disposable-localnet execution pending.

**Starting main:** `a3ca8cd111689329832131eac1460d579c7828b3`
(PR #131).

**Ticket:** `.agent/tickets/NET-5R_shielded_registration_compatibility.md`.

**Primary Hub map_ref:** `WAVE-C/NET-5R`.

**Decision:** `NET-5R-D1`.

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
