# V8_8-VALIDATOR-SETUP-01: portable validator operator setup

Root's direct Ryan mandate,2026-10-14: Product/Launchpad owns the proposed
literal v8.8 validator setup end-to-end. One complete engineering candidate;
Platform2 packages the operator packet, Validator reviews the complete focused
candidate once, Root polls CI/merges and performs privileged execution.
Starting merged main91d4a13d3 (exact SHA recorded in local source bindings).
Current1348 repair has a known external PLT29 CI dependency owned by Platform;
do not duplicate that repair or change the reviewed910 weights branch.

## Working contract

Deliver a portable, bound operator source bundle and complete validator-service
OCI build recipe, with executable install/verify/update/rollback preparation
and entry points for existing intake+daemon supervision, answer-key sync and
checked weights. The image is a distinct operator artifact from a reconstruction
worker. No image publication, privileged installation, listener exposure,
wallet/signing, protected import, rented compute or production acceptance occurs
in builder tests. An unpublished build recipe is not installed-image evidence.

KEEP current service/supervisor/backup, intake/authentication, validator daemon,
shared answer-key verifier, pool rotation, issuer/shared publisher and source
eligibility/decay. WRAP them behind a portable operator route with explicit
repository/config/state paths and immutable source/image/lock bindings. REPAIR
fresh answer-key initialization and partial-import completeness where existing
public counterexamples show skipped salt/design recovery. Do not draw/solve on
ordinary remote validators, rewrite journals or reset clocks. No miner credential
or miner-controlled request can configure or invoke trusted operator tools.

Introduce an additive network-neutral weights operator configuration/entry
point rather than weakening the bounded development-testnet loader. Registry,
standing authority, context/genesis/netuid/runtime, recipient and integer/no-resend
checks remain mandatory. Mainnet registration/economics/coldkey custody and
exposure remain unresolved owner matters; absent policy fails before wallet or
private-source access. Keep SDK11.1.0; consume Data Collector's actual public
finney/testnet runtime receipt without treating a release-page or SDK match as
proof of equal chain behavior. No new scientific/economic/fee/security value.

Source distribution excludes state, wallets, secrets, private/official materials,
untracked files, commercial documents and legacy executables. Bind an explicit
public runtime payload to its exact source revision/tree and per-file digests;
verify actual bytes before using it. Worker Docker host paths and container paths
must be explicit and compatible, never silently inherited from Ryan's host.
Update/rollback switch only an inactive immutable code release; persistent state
stays outside it and is never restored/downgraded/deleted as a release action.

## Bounded implementation and controls

1. Inspect current source/authority and focused baseline; record durable choices.
2. Source bundle/manifest, closed verifier and release-directory lifecycle with
   traversal/symlink/mutation/nonempty-target/refused-update contrasts.
3. Portable service image/entry points and actual source/package/config wiring;
   preserve existing service refusal/restart and writer-lock semantics.
4. Import-only fresh initialization: init/open/sync/status and real finalized
   window observation; interrupted import must not become HELD while required
   salt/design is absent. Synthetic public fixtures only.
5. Neutral weights configuration and wrapper over existing checked publication;
   missing mainnet policy/context/standing refuses before signing. Genuine drift,
   owner exclusions and epoch/journal/reconciliation remain controlling.
6. Reuse existing HTTP/signature/TLS/proxy fixtures, add missing exact operator
   route controls, and record separate NOT_RUN cells for actual fresh external
   identities/HTTPS/discovery/durable202-admit-score-own-status and actual weight
   commit/reveal/inclusion/finalized readback. Do not count fixtures as these cells.
7. Canonical focused regression/style/hygiene; one main-based complete PR and
   one candidate checkpoint with support files for Platform2 and Validator.

## Authority and seams

Current constitution/invariants/WAVE, OWNER-DX-03 delivery/delegated decisions,
BuildOut/constitutional overlay/master compatibility, code authority and legacy
index; VALIDATOR18/19/15/27, deployment/submission/answer-key operations and
current OWNER-VALIDATOR-MAINNET-PARITY/SHARED-ANSWER-KEY/WEIGHTS records control.
Earlier setup prose is DOCUMENTATION_LAG where current code already implements
intake/signing/commitment. Reconstruction-image versus full validator artifact,
import completeness and testnet-only CLI are IMPLEMENTATION_LAG. Missing mainnet
policy/custody/activation is NEW_OWNER_DECISION_REQUIRED, explicitly fail closed.
No Wave scientific successor or later-wave execution freedom is selected.

Hub retired by current owner direction; no source/derived Hub maintenance.
Maturity ceiling: DEVELOPMENT engineering implementation and public fixture
testing, exact packaging evidence only when actually executed. Real installed
artifact, external HTTPS, GPU, live chain/publication/payment, security/science/
mainnet qualification retain their independent owner receipts. Proposed tag
word and final release SHA remain Root/owner decisions. Bug fixes alone do not
make v8.8 ready.

Canonical evidence at implementation slice: existing service/proxy/answer-key
baseline99 PASS. New interrupted-salt/missing-design controls2 RED on original
source, then repaired first slice24 PASS; image/lifecycle/entry slice19 PASS.
Complete focused source/config/image/lease/entry/runtime/units plus answer-key/
design-window/installed-SDK regressions125 PASS/56.14s. Canonical Black/Ruff17
changed Python paths PASS after formatting actual source. Actual image build,
fresh-machine and real HTTPS/chain receipts remain separate NOT_RUN cells.
