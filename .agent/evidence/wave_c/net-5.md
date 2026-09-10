# NET-5 stable integration evidence

Status: selected; canonical acceptance and merge pending.
Starting main: 0e6b5e001302b349135785756c633530853684c2 (PR #125).
Ticket: `.agent/tickets/NET-5_disposable_localnet.md`.
Primary map_ref: WAVE-C/NET-5. Decision: NET-5-D1.

## Candidate diagnostics

Local Windows Docker 25.0.3 has no reachable docker_engine named pipe; Docker
Desktop did not remain running and WSL has no distribution. The unchanged
local environment will not be retried. Existing GitHub Ubuntu Docker runners
are available for a pinned disposable localnet attempt. No runtime execution,
burn or G2 success is claimed yet.

## Expected manifest and acceptance

Localnet image/runtime manifest, isolated harness/setup, fixture integration and
regression tests, operator evidence contract and canonical Hub/board transition.
KEEP chain/auth/candidate/reward/A7/A8/A6 owners; repair actual integration defects
under this ticket. Required tests must pass. Actual head/run/merge facts remain
in the completion comment, not invented prospective evidence.

NET-3 already uniquely binds an immutable challenge/version to one evaluation
context in candidate_context_v1. The attempted second-context regression is
rejected there before reward registration. KEEP that owner guard; no duplicate
reward guard or alternative acceptance system is needed.

Development run 34422914580 passed 16 setup contracts and failed the new
three-exam integration before starting Docker: A8's defensive owned-profile
copy still reconstructed the default profile. Preserve defensive copying while
selecting the already validated finite fixture identity. No threshold, score,
qualification or acceptance flag changed. Native A3-dependent tests remain
unavailable on Windows; secure descriptor-relative access is not weakened.

Development run 34423046410 passed all 17 setup contracts and pulled the exact
runtime image digest. Container startup was followed immediately by rejected
loopback binding inspection, before any chain connection or signing. Retain
Docker network diagnostics and bound startup polling; an unchanged missing
binding will remain a failure rather than a public-network fallback.

Run 34423594657 resolves the binding failure: Docker 28.0.4 retained an internal
network with no gateway and empty actual Ports despite requested loopback
publication. This is not a startup timing race. Preserve that isolation; the
harness now owns two loopback TCP relays to the verified container address and
fixed RPC ports, with no caller endpoint file or external container route.
Container identity/network must still match the in-process relay capability.

Run 34423854559 reached pinned node genesis initialization, then all three
litep2p authorities exited with `SelectNextSome polled after terminated` in
sc_network_sync. No RPC identity/signing or burn success was claimed. The pinned
node service.rs and pinned polkadot-sdk cacb431 network CLI explicitly support
libp2p. A fixed startup shim verifies the upstream script SHA-256 and adds only
that public backend option to the three authorities. The immutable image and
runtime binary remain unchanged; Docker inspection binds the exact startup
command. If this configuration also fails, preserve the concrete failure rather
than repeatedly retrying unchanged nodes.

Run 34424399809 verified genesis
0x25ce33ee6a48d7a8fa1b485359a4e8f120b92321846e962bdf1e0dae9922e007
and runtime 445, then finalized root timing settings, subnet creation and plain
weights. Burn configuration was rejected. The pinned setter enforces the admin
freeze window even for root. Register development window 0 through the existing
root-only SDK call before local subnet setup; retain typed chain error name/code
in subsequent setup receipts. This is an explicit disposable development timing
value, not a production policy change or an unchecked extrinsic bypass.

Run 34424676154 finalized Burn configuration, activation and validator stake.
Required shielded miner registration returned failure after an included carrier;
its typed SDK code was unknown. Preserve carrier/inner identities and classify
the SDK's specific expired-inner observation without publishing raw messages.
Use the public submit_shielded API with a DEVELOPMENT 64-block mortal era,
preserving its policy/encryption and adding the pre-sign guard to the public
inner-sign path. Baselines use the registered publisher identity with zero
opening credit so the all-burn observation is independent of miner registration.
No failed/ambiguous setup operation is blindly retried on the same chain.

Run 34425042109 accepted and registered all three fixed synthetic baselines,
rejected a mismatched genesis and dispatched the all-burn transaction. Runtime
reconciliation exposed a NET-4B integration defect: resolve_extrinsic belongs to
the SDK's raw transport, while RpcSubstrate publicly exposes find_extrinsic.
Use that public method and add installed-SDK found/missing transaction contract
tests. Preserve the failed run; dispatch alone is not finalized row/burn proof.

Run 34425292251 proved the three-challenge no-winner complete vector: transaction
0x79eb701466c7b2f17deeb21f07bdf660f1f41bc338c0e2063f95d6bbe702cbda
was included/finalized with row [(0,65535)] at block 191. Finalized block 234,
epoch 12, reported MinerBurned bits=4294967296 (1.0) under Burn mode and the
verified owner sink. Owner cut/dividends remain distinct. Shielded registration
then reported Stale/expired; do not infer a recipient exists or blindly resend.
Journal the exact inner hash before encryption and reconcile inner/carrier
hashes over a bounded finalized range. Exercise all-burn restart/replay/outage
recovery before that dependent miner operation so its failure cannot hide
independent operational evidence.

Run 34425822745 additionally proved all-burn journal restart, exact dispatch replay
without resend, actual container pause/outage, reconnect and corrective publication.
Required shielded registration still returned Stale/expired. The exact inner and
carrier hashes were journaled before encryption/wire and neither appeared in the
bounded finalized scan through block 250. There is no successful registration
receipt. Stop repeated attempts with this unchanged SDK/runtime configuration;
never bypass required shielding with legacy calls or storage injection.

Current disposition: all-burn local integration and recovery OBSERVED; shared
winner/copy/recycled UID runtime path UNOBSERVED due to registration compatibility.
The complete remaining harness stays executable and fails when its requirements
are unmet. Canonical offline three-exam integration reuses actual A7/A8/A5
acceptance and tests shared-winner complete vectors, copy/restart/UID isolation
with clearly labeled chain/auth doubles. This is not substituted runtime proof.
G2 remains NOT_READY. NET-6 completes independent operator artifacts and the exact
blocked-operation handoff. The runtime workflow is now explicitly dispatched,
preventing unchanged registration failures from rerunning on documentation pushes.

## NET-5-D2 — Exact fixture migration acceptance scope

Under OWNER-C0-VALIDATION-01, use the complete focused network suite (including
all existing A7/A8, scoring and new NET-5 setup/three-exam tests), all invariants,
quality, package, Hub and required image/Merge checks. The selector recognizes
only the exact before/after bytes of the two A8 fixture-owner files and two new
fixed fixture packs. Any other evaluator, pack, threshold, dependency or unknown
path change retains full regression. This is a finite synthetic identity
extension with unchanged scoring contracts, not a general science exemption.

Broader run 34427443255 was stopped after review found a test-only batch-ID
collision across challenges. It is not a successful full-regression receipt.
The repaired test uses challenge-specific IDs just like the actual runtime
harness; conflicting replay remains rejected. A prior invariant-marker omission
also remains recorded as a failed run. No assertion is removed or weakened.
This scope avoids repeating unrelated long CPU tests for that test repair.
Alternatives: another full suite adds unrelated coverage; globally exempting A8
would lose the science fallback and is rejected. To supersede, change the exact
migration predicate in scripts/dev/select_cpu_profile.py and its regression tests.
No reserved scientific/security decision is selected. G2 remains NOT_READY.

Run 34428706438 passed all 183 invariants and 1,882 focused tests, with two
failures: the new offline clock exceeded the existing 32 requests/second limit,
and the original scoring inventory expected one fixture. Pace only the explicit
chain double; retain the rate assertion. Update inventory to exactly the three
registered synthetic packs and assert each remains fixture_origin, with no extra
file/YAML twin admitted. The narrow migration predicate also pins this exact
inventory-test change. No scoring or authentication requirement is weakened.
