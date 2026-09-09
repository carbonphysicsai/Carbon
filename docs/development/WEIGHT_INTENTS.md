# NET-4A publication authority

`LocalnetIntentIssuer(FixtureRewardLedger)` issues a
`StructuralLocalnetWeightIntent(identity, digest)` backed by the existing private
SQLite journal. A nominal reference is not self-authenticating. NET-4B must resolve
it through that issuer with a fresh finalized snapshot before publication.

Issuance resolves the complete C-REWARD projection: network, endpoint/provider,
observed genesis, netuid, finalized snapshot/block/time, immutable challenge state
hashes, accepted provenance and DIRECT_WINNER_PLUS_BURN targets. Its stage is
DISPOSABLE_LOCALNET and maturity SYNTHETIC_ONLY. Raw score dictionaries, stage
flags and copied nominal references cannot create authority.

The intent lasts at most 60 finalized-chain seconds (a DEVELOPMENT setting), ending
earlier at the next opening, allocation step or funding boundary. Exact request
replay returns the same reference without changing age or reactivating an old
intent. New issuance supersedes the previous complete-vector intent for this chain
context. Changed accepted state or a winner quarantine invalidates old targets.
Hash mismatch, unknown reference, stale/conflicting snapshot, expired validity,
wrong context and nominal-type confusion fail with distinct reasons.

An all-burn/no-winner intent is explicit and non-paying for participant miners.
Treasury state and credentials are entirely absent. Intent expiry does not erase
stored chain weights or establish zero payout. NET-4B owns execution-time fresh
identity/runtime checks, complete-vector compilation, the last integer-vector
check before encryption/signing, durable dispatch and readback. NET-5 supplies
actual runtime burn and settlement evidence. Short intent validity cannot cure
an unavailable or compromised publisher by itself.

`TestnetWinnerWeightIntent` is a distinct reserved family whose issuer fails with
C2_REAL_ELIGIBILITY_ISSUER_UNAVAILABLE. Its future C2 issuer must resolve real
TestnetWeightEligibilityEvent provenance, challenge/version, scientific receipt
and archive, exact network/subnet/identity, policy and validity. Its ceiling remains
TESTNET_ONLY, NON_LIVE, NON_SETTLING, NOT_FRONTIER_QUALIFIED and
NOT_MAINNET_ELIGIBLE. There is no fixture conversion path and no public transaction
authorization in NET-4A.

`TreasuryRoutingWeightIntent` is another distinct reserved family whose issuer
fails with OPTIONAL_TREASURY_ISSUER_UNAVAILABLE. C-TREASURY owns future verified
destination health/custody and settled plus pending/dispatched/committed/unrevealed
liability admission. It cannot reuse local fixture or testnet winner authority.
Unknown treasury state burns new unearned allocation under the direct policy;
existing liabilities are not erased. Neither reserved family is fabricated as
implemented public-network or custody capability.

Restart tests exercise immutable references, active supersession and provenance;
negative cases include fabricated/subclass references, modified journal bytes,
public-stage construction, context mismatch, expired/funding-end targets and
post-acceptance quarantine. Existing C-REWARD/A7/A8/A6 acceptance remains unchanged.
