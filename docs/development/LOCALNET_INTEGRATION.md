# Disposable C0 runtime integration

NET-5 owns this fixture-only harness. NET-6 owns the complete operator lifecycle.
Run from the exact repository revision in Carbon's locked Ubuntu 24.04 amd64,
Python 3.11.16 / uv 0.12.7 development environment with a working Docker daemon:

```bash
CARBON_UV_GROUPS=chain ./scripts/dev/bootstrap.sh
CARBON_UV_GROUPS=chain ./scripts/dev/localnet.sh .carbon-artifacts/localnet
```

The existing `Disposable localnet evidence` workflow executes these commands on
an ephemeral Ubuntu runner. Its runtime result is separate from CPU acceptance.
No mock, skipped integration test, image download or source inspection is a
successful runtime proof. A failed runtime command retains diagnostics and leaves
G2 not ready; independent engineering acceptance can still be completed.

## Pins and topology

Bittensor 11.1.0 and core 0.1.3 remain locked by uv.lock. Runtime v445 / source
d3f40e44bda9019c606aeb0c907bb52ba7fe386c is independently pinned to the amd64
image digest in `scripts/dev/localnet-runtime.json`. The upstream localnet image
runs three development authorities at nominal 0.25-second slots. An internal
Docker network contains only this container with no published ports or gateway.
The harness process owns two dynamically chosen 127.0.0.1 TCP listeners, relaying
only to the inspected container address and fixed RPC ports 9944/9945. The relay
capability stays in memory and rejects a replaced container or changed network. No volume, privileged container, external peer or valuable
network is admitted. A fixed, hash-checked upstream startup script selects the supported libp2p
backend after the default litep2p backend panicked in the recorded runner. The
runtime binary is unchanged and inspection binds the exact startup command.
The probe inspects actual Docker state, observes genesis,
and verifies runtime version before setup constructs any key.

The familiar Substrate development accounts are disposable, publicly known and
valueless here. Owner, publisher, miner and challenger roles are separately
recorded by public address; seed/private-key bytes are not evidence fields. The
SDK's policy and generated calls remain in control. Root setup is a finite list
of pinned local development settings, not a generic raw-call interface. Min
weight count 1, rate 0, admin freeze window 0, mechanism 0, Burn and plain weights are DEVELOPMENT
settings, not production SLOs or accepted public economics. Runtime max weight
65535 and other capabilities must be observed; incompatible constraints fail.

Registration uses the real SDK BurnedRegister including its required ML-KEM
shielding. NET-5R removes Carbon's unsupported 64-block override and requires
the pinned SDK's eight-block era, which equals v445's maximum for
`submit_encrypted`. Drift fails before disposable key construction. A digest and
length of the public ephemeral key, exact inner/carrier nonce and era, and exact
inner/carrier hashes are journaled and reconciled independently. Missing local validator keys or decryption are not bypassed through
legacy register/raw calls. Weight timelock encryption has installed-SDK contract
tests; actual isolated runtime operation uses plain weights. A future timelock
configuration needs actual beacon, reveal and stale-exposure evidence.

Run 34464255826 proved the eight-block carrier is accepted and finalized rather
than rejected `Stale`, but its inner hash was not observed before expiry. Pinned
source shows ML-KEM shield decryption uses the selected author's in-memory key,
not drand. The harness enables the pinned proposer/shield debug targets so a
changed diagnostic run can distinguish key availability, unshielding and inner
push validity without changing the registration operation or isolation.

Refined run 34465977413 observed the miner carrier and decrypted inner both
finalize at block 255, then observed the challenger carrier finalize at block
263 while pinned `mev-shield` and `basic-authorship` debug targets both reported
`Failed to unshield transaction`; its exact inner remained absent. This
distinguishes the remaining blocker from mortality, nonce, drand, carrier policy
and post-decrypt inner push rejection. The exact blocker is intermittent
authenticated unshielding in the pinned v445 fast-localnet proposer/keystore
path. A supported upstream fix or an explicitly authorized compatible pin is
required before another changed run; no blind retry or unchecked fallback is
supported.

## Fixture ownership and evidence

A8's existing evaluator gets only two additional finite synthetic profiles:
a5_fixture_net5_b and a5_fixture_net5_c, both fixture-1.0. Their exact ScorePack
digests are fixed. Every field other than challenge identity equals the existing
A5 fixture pack: same hard gates, geometric composition and coefficients.
Unknown profile names fail. There is no generic mode or second evaluator. A7
submission/admission, A8 execution, A5 scoring and A6 publication still create
each accepted fixture. Real challenge, C1 and LIVE authority remain unavailable.

The harness makes a bounded deterministic fixture search: at most 20 baseline
attempts per challenge, then 40 improvement attempts for each of challenges A and C.
Failed mandatory gates stay failed; no threshold is changed. The middle challenge
has no reward winner. Each accepted baseline starts with zero credit. Allocation
is explicitly synthetic, one third per challenge with Q12 remainder burned.
Authenticated messages use actual SDK signatures and a single server-observed
finalized snapshot per in-process ingress exchange; this does not claim a public
HTTP service or WAN availability SLO. Candidate ownership prevents duplicate
challenge/version contexts and artifact/wallet resets creating new credit.

`isolation.json` records the observed chain/container identity. `setup.json`
records local setup operations and transaction hashes before wire dispatch.
`integration.json` separates application targets, submitted integers, inclusion,
finality, applicable reveal, stored rows and epoch observations. `node.log`
contains runtime diagnostics. The workflow archives these for 14 days as
development evidence, not the later C-EA durable scientific archive contract.
Retain a reviewed evidence summary in the repository before artifact expiry.

Actual epoch samples include MinerBurned, Burn mode, owner identity, incentives,
dividends, emission and alpha state. MinerBurned alone includes recycle and is
insufficient. The pinned runtime routes owner-associated miner incentives to
burn_subnet_alpha in Burn mode. Owner cut, validator dividends, collateral and
Yuma/stake effects remain separate. Native weights express consensus targets;
they are not per-challenge purses or guarantees of exact wallet receipts.

Restart and duplicate publication must resolve the existing dispatch. A real
container pause exercises outage and reconnect. A signed hotkey replacement
reuses its UID but receives no inherited target; a fresh projection publishes
all-burn. Stopping a publisher leaves stored weights potentially effective.
No treasury is created or needed. Economic adversarial tests retain withholding,
drip-feeding, copying, coordinated timing and plateau limitations; these are
development observations, not strategy-proofness or participation evidence.

Immutable partial runtime observations are retained under
`.agent/evidence/wave_c/net-5-runtime/`. Run 34425292251 proves the three-challenge
no-winner vector, finality/readback and full miner-incentive burn in an observed
epoch. The overall run failed at shielded miner registration; it does not prove
shared-winner, recovery or G2 readiness. The manifest distinguishes those states.

Run 34425822745 also observed all-burn restart, exact replay, actual
provider outage and publication recovery. Shielded miner registration remains
unresolved: the SDK reports Stale/expired and no exact inner/carrier receipt was
found through the then-finalized block. No winner or replacement is manufactured.
The workflow is manual (`workflow_dispatch`); normal CI still runs all setup and
offline fixture contracts. Do not repeatedly rerun the unchanged registration
configuration. Exact SDK/runtime source inspection identifies the 64-block
override as incompatible: v445 returns `Stale` above its eight-block shield
mortality ceiling. The eight-block repair was executed twice with changed
hypotheses on canonical Linux; the refined run failed at the second shielded
registration as recorded above. G2 cannot become LOCALNET_READY until a
supported upstream or pin change permits the shared-winner/identity scenarios to
pass.
