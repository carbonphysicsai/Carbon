# NET-5R shielded registration compatibility evidence

**Status:** NET-5R `done` in bounded standard-profile disposable-localnet scope.
PR #132's repair and PR #133's standard-profile/D4 checkpoint are merged. D6
run 34518806217 passed the complete auditable predicate. G2 is
`LOCALNET_READY` for this exact standard profile only.

**Starting main:** `675427ec8852579aa9d336bbec94e28be7b62810`
(PR #132). PR #131's merged specification checkpoint remains
`a3ca8cd111689329832131eac1460d579c7828b3`.

**Ticket:** `.agent/tickets/NET-5R_shielded_registration_compatibility.md`.

**Primary Hub map_ref:** `WAVE-C/NET-5R`.

**Decisions:** `NET-5R-D1`, `NET-5R-D2`, `NET-5R-D3`, `NET-5R-D4`,
`NET-5R-D5`, `NET-5R-D6`, `NET-5R-D7`.

**Lead notification:**
https://github.com/carbonphysicsai/Carbon/issues/42#issuecomment-5618878650.

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

## Standard-runtime profile discovery

Pinned upstream commit `d3f40e44bda9019c606aeb0c907bb52ba7fe386c`
documents `False` as the standard 12-second runtime. Its exact
`Dockerfile-localnet` and `scripts/localnet.sh` hashes are recorded in
`scripts/dev/localnet-runtime.json`. They build/copy separate fast and non-fast
release binaries plus WASM; only the fast build enables `fast-runtime`.

Run 34472892985 is preserved as a pre-key instrumentation failure: both node
binaries reject `--version` with exit 2, and the original `set -e` probe stopped
before it could report artifact identities. It created no network and performed
no signing. Changed run 34473145103 captured that unsupported command outcome,
verified both artifacts were executable and distinct, and bound the standard
binary, WASM and genesis hashes. Isolated RPC verified spec version 445 and
12-second blocks. This establishes an exact supported profile, not a claim that
runtime speed or keystore behavior caused the fast-profile failure.

## One-shot standard registration diagnostic

Run 34473508494 used the standard profile, a 1,200-second wall ceiling, 5 GiB,
3 CPUs, 1,024 PIDs, one registration attempt and zero retries. The queried
1,184-byte key digest was
`sha256:b2be6c535a2bcde3b70e9f7c22849363ef674f0268eb963febcbaf281ac2bd88`
at block 15 / hash
`0x1f24a53ee38444b8ce2e2e721ebd61f35abd89abcadd843e572e9f6b927ce4c5`,
with exclusive expiry block 18 and author
`0x9026941b7aa2328a8c5ea4e25bb747a2bf92a066fae0cc3722faf58cf44d3502`.
Carrier
`0xa20e0826b48837ca9c980665fd593679da875bdb0557c15d8887f54429d486ff`
and inner
`0x59edd5f12d3c732311aee3569343a590b94d5540edc03e12a4ff8dcc2cd2867b`
both finalized successfully at block 17. The queried key was `CurrentKey` at
that carrier block, and the registration association was read back at block 19.
No secret key or decrypted payload is retained. G2 remained `NOT_READY` pending
the complete scenario.

## Standard full attempt 34474220953

The one full attempt ran at exact head
`7701a1d11f0d80ae90ab942a0fd726482a054699` under the declared 5,400-second
wall, 5 GiB, 3 CPU and 1,024-PID budget with zero registration or extrinsic
retries. Both authenticated shielded registrations succeeded:

- miner key query block 77, exclusive expiry 80, author
  `0x9026941b7aa2328a8c5ea4e25bb747a2bf92a066fae0cc3722faf58cf44d3502`;
  carrier `0x8550b3e0d889362cbd2149a7975d6ea2144398d23a077d90fb6fdcb3eab08229`
  and inner `0x7180b60d4d2619237dcd316a1b9874eb7ddd98d9420d226ca427d870a8f7c170`
  finalized at block 79;
- challenger key query block 81, exclusive expiry 84, author
  `0xac859f8a216eeb1b320b4c76d118da3d7407fa523484d0a980126d3b4d0d220a`;
  carrier `0x3b64a215158671426d651c7b9c4bd87ce76b7e18c424dc9b43a6abb5ea306c99`
  and inner `0xcb2bec65243db7d8071ddf8001ad4ac87dca77ff406ebf7203b337dcc0c18949`
  finalized at block 83.

The run then observed the complete three-challenge shared-winner vector,
verified its stored row, and sampled the shared-winner epoch. It also observed
copy-without-new-credit plus restart/replay and provider recovery. The later
plain `SwapHotkey` transaction
`0x391e2b0c99adf161abc20aaa1133a1cef797df624a9e76b9a9defe35141a7429`
was rejected `Stale/expired` before inclusion. Therefore no replacement was
manufactured and the recycled-UID effect remains unobserved.

Exact SDK source establishes the new testable hypothesis recorded in NET-5R-D4:
successful shield signing pins inner nonce 1 and then regresses the same
transport cache by explicitly pinning carrier nonce 0; the subsequent plain
execute can therefore reuse consumed nonce 1. The candidate verifies the
finalized account next nonce and reopens the supported public SDK transport
under unchanged identity/policy checks. It does not manipulate the private
cache, inject a nonce, retry or bypass the SDK. The complete scenario has not
been rerun, so G2 remains `NOT_READY` until recycled-UID evidence also passes.

The exact public-safe files and hashes are retained in
`.agent/evidence/wave_c/net-5r-runtime/34474220953/manifest.json`. Decrypted
inner bytes are redacted from the retained node log; hashes and outcome lines
remain. The workflow is
https://github.com/carbonphysicsai/Carbon/actions/runs/34474220953. A local-only
upstream issue draft is in
`.agent/evidence/wave_c/net-5r-upstream-issue-draft.md`; no maintainer contact
occurred.

## Exact D4 candidate full run 34489505489

The canonical workflow was explicitly dispatched with `mode=full` and
`profile=standard` at exact unchanged post-PR-133 main
`faf99d20356a42ca53e9c1c9a5884d3de4620459`; it did not rely on the workflow's
fast default. Ubuntu 24.04 amd64 setup and pinned SDK contracts passed, then the
full scenario passed in 1,834.56 seconds within the existing 5,400-second,
5-GiB, 3-CPU and 1,024-PID limits with zero retries.

The miner account
`5FHneW46xGXgs5mUiveU4sbTyGBzmstUspZC92UhjJM694ty` finalized carrier
`0x8ec82790ea087f54b6aeac7ac36b40ea254b1a022c9bb41cfb99a3e37de990b6`
and inner
`0x974c5a271252ed7eaf885a02dd63d5439895a515d30bfa5f8806ff1db7d52a50`
at block 78 / hash
`0x5839bbf50dd9cfecc0a293d03a39fb68888d6e004540fbce8da9af32f94b696e`;
the finalized next nonce was 2. The challenger account
`5FLSigC9HGRKVhB9FiEo4Y3koPsNmBmLJbpXg2mp1hXcS59Y` finalized carrier
`0xdedd884abfe19940d546cd1c081969164d9ac49c1db45e1c866f410416b83931`
and inner
`0x8905be1ad21b102e38b85d618117ffc000a4c8e00be4f8878cdd61d353a5e958`
at block 82 / hash
`0x56d0c817afc655e59b4482f574ff12186e0ea0ed298ad0d7f28af6063036a85b`;
its finalized next nonce was also 2.

The complete shared-winner vector and epoch were observed. `SwapHotkey`
transaction
`0xad3e92a05b8590fa51b8b5ef3f95db10f92d7c118d704727186ef16164840837`
then finalized at block 117 / hash
`0xab98a7889a58c32dbf014f30af395510baa69ac868841a2e3fc76c4422d28033`,
with takeover readback and recycled-UID non-inheritance verified. The final
identity-replacement all-burn epoch was observed at block 151 / hash
`0x74c5f85f49b16d01cbeb54cad74d285c2285d4ec8a6b2986944c28c83979fd5f`.

This proves D4's complete behavioral predicate. The retained v1 setup artifact
does not expose the clarified transport generations/closure or ordinary
SDK-selected nonce, so G2 remains `NOT_READY` pending one D5 evidence run. Exact
public-safe artifacts and hashes are in
`.agent/evidence/wave_c/net-5r-runtime/34489505489/manifest.json`; no decrypted
private payload or secret key is retained. Workflow:
https://github.com/carbonphysicsai/Carbon/actions/runs/34489505489.

## D5 source-backed evidence candidate

Pinned Bittensor 11.1.0 source exposes public, pool-aware
`RpcSubstrate.account_next_index(address)` and uses it when ordinary signed
extrinsic creation receives no nonce. Carbon's candidate records that value as
the SDK-selected nonce without supplying or changing it, then verifies the
finalized account increment. The session serializes each account's submission
sequence across finalized nonce verification and handover. A replacement may
connect and pass endpoint, genesis, runtime and standard-profile checks first,
but the prior transport must close before the replacement becomes active or any
subsequent signing/dispatch. Outstanding ambiguity requires reconciliation and
cannot trigger reset. Focused installed-SDK and invariant tests pass; one changed
full standard run remains before closeout.
Notification:
https://github.com/carbonphysicsai/Carbon/issues/42#issuecomment-5621253748.

## D5 changed full run 34497456242 and D6 diagnosis

The sole changed full/standard successor ran at exact head
`9b7b70f745062a100ff2d6c85d9f647ddad4e588`. Canonical Ubuntu 24.04 amd64
setup and the pinned SDK contracts passed. The run then stopped at the first
`start_delay` configuration submission after its 144-second operation ceiling.
Setup retained disposable Alice account
`5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY`, transport generation one,
public next index zero, omitted Carbon nonce argument and transaction
`0x7037e152ffc318bf20e55bf94b9525dea49adeeab6e8ed6256642a76512b735f`.
The transaction was not observed before timeout, state is
`AMBIGUOUS_OR_UNAVAILABLE`, and the transport closed at session end. No shield
registration or `SwapHotkey` occurred.

Exact Bittensor 11.1.0 source makes the cause deterministic:
`RpcSubstrate.account_next_index` delegates to the transport's
`get_account_next_index(address)`, whose `use_cache=True` default advances its
nonce cache. D5's evidence read returned zero and advanced that signing cache;
the following omitted-nonce SDK execution advanced it again and selected future
nonce one. Concurrent drand HTTP warnings cannot cause this pre-shield nonce
path. No standard/fast timing, key rotation, ciphertext, unshielding or keystore
claim follows.

D6 instead reads finalized `System.Account` at the exact pre-sign block, never
calls stateful next-index on the signing transport, keeps nonce omitted and
retains the SDK-selected nonce only after an exclusive successful submission's
finalized account increment proves it. Focused installed-SDK and invariant tests
pass. Exact public-safe artifacts and hashes are in
`.agent/evidence/wave_c/net-5r-runtime/34497456242/manifest.json`; no secret key
or private payload is retained. The authorized run budget is exhausted, so G2
remains `NOT_READY` on the missing D6 runtime demonstration and no further run
was dispatched. Workflow:
https://github.com/carbonphysicsai/Carbon/actions/runs/34497456242. Notification:
https://github.com/carbonphysicsai/Carbon/issues/42#issuecomment-5621535023.

## D6 canonical full/standard success — run 34518806217

The owner-authorized first D6 execution ran on canonical Linux amd64 Docker at
exact candidate `97a2405776a3f520076e03a89ea8b7b4086d9ad2`, explicitly with
`mode=full` and `profile=standard`. Its head and inputs matched. Setup passed 86
focused contracts and the full scenario passed in 1,828.88 seconds. Runtime
identity was v445 at source `d3f40e44bda9019c606aeb0c907bb52ba7fe386c`,
image digest
`sha256:bb762bf7a88502e0e21f76a1e6615ad4c00316f6b0e988dba2e59035c015aa86`,
standard selector `False`, genesis
`0x8244412784e980f8001b2d87a528a4e24487e33e3ce96d137f0fdf491752966e`,
SDK `bittensor==11.1.0`, eight-block shield era, nominal 12-second blocks and
zero transaction retries.

| Predicate | Finalized observation |
|---|---|
| Miner registration | Bob; generation 1; carrier `0x47138cdcc7d97f7b54562de20f681edbcd69c39fcc2313acf74c5eeb6cc29f1e`, inner `0x68d0e04ca2d007106af2a017c00f90bec407141f8e61d307438ec9d4139e8101`; block 78 / `0x8429e8a6112f241a4090252f50b8b3ad616920c5b75f5a569fe77d9af17a8a2c`; account 1→2 |
| Challenger registration | Charlie; generation 2; carrier `0xf99c5ea2286f349764801452e0679e92057070fb211498831073262f0143dd8c`, inner `0x84de64bb4d6cdb2decdfc3a83fb7d9198a6c00814581b7fa173b2c39573209d8`; block 82 / `0x62f4f3e2ef9565d7d14d0796286ca8662db793c41690632d21d30af1bea50bcb`; account 2→3 |
| Shared winner | Complete vector and stored row; epoch block 111 / `0xfa0bda0ba0ba44e7ff60c7ff288733d2536de847262d8cc6b62404740056beaa`; `MinerBurned=3974620244` |
| Copy/recovery | Copy without new credit, restart/exact replay and provider recovery passed |
| `SwapHotkey` | Checked SDK; Bob generation 3; tx `0xc5ab188768de19550da2fe5e23775b7fa51ae7b522ca66d80d1a9cf686253e18`; block 117 / `0x995592e836990fb3ff77b5febc7c385212050316d6207f75b6a459ce488eddb8`; account 2→3, inferred selected nonce 2 |
| Takeover/recycled UID | UID 1 changed from Bob hotkey to Dave with Bob coldkey; takeover matched and the prior winner target was not inherited |
| Replacement all-burn | Stored row contained only UID 0 at 65535; epoch block 151 / `0x31b39a93e0b72cf984c58362126c7698a38dd8724b6ed4baf085f03755540525`; burn Q32 `4294967296` |

The ordinary selected nonce is an inference from the exclusive sequence and
exact finalized `System.Account` increment; it was not decoded from captured
signed-extrinsic bytes. Generations 1, 2 and 3 each verified replacement
endpoint, genesis, runtime and profile identity, closed the prior transport, and
only then made the replacement active. No ambiguous dispatch remained. Account,
transaction, finalized-block and generation associations stayed exact.

Target weights, stored rows and epochs remain distinct from wallet receipts. No
settlement or wallet payment was observed, and `MinerBurned` does not prove that
owner cuts or validator dividends burned. No secret, decrypted private payload,
public-network credential or persistent value is retained.

The manifest and exact public-safe bytes are under
`.agent/evidence/wave_c/net-5r-runtime/34518806217/`; workflow:
https://github.com/carbonphysicsai/Carbon/actions/runs/34518806217. One authorized
full scenario was consumed. Because the first passed, the conditional second
run is unavailable. D5 remains byte-for-byte unchanged and its selected-nonce
interpretation remains invalid for the source-backed cache-mutation reason.

NET-5R is done in bounded engineering scope. Together with retained NET-1
through NET-6 evidence, G2 is `LOCALNET_READY` for this exact standard-profile
disposable v445 localnet. The global capability flag remains false: fast-profile
failures, public networks, production, settlement, science, security and LIVE
qualification remain outside the claim.
