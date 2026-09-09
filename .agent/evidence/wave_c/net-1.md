# NET-1 evidence — bounded read-only ChainAdapter

**Status:** selected; implementation not yet delivered
**Starting implementation base:** the merged Wave-C transition, to be resolved
from current `main` before code changes
**Primary Hub map_ref:** `WAVE-C/NET-1`

## Implementation candidate (OWNER-C0-REWARD-01)

Starting main was fetched and verified as
`9578a5042f85c4a2cbeab8259eba94c0ec462dcc`, PR #119. The original checkout
and unrelated worktrees were preserved; implementation uses
`agent/net-1-sdk-boundary`. KEEP the canonical chain package and all science;
WRAP the installed SDK's public read interfaces. No archive code reused.

Candidate: Carbon-owned frozen contexts/participants/snapshots, provider failure
codes, bounded observation capture, strict raw metagraph translation and lazy
Bittensor 11.1 reader. Context includes expected/observed genesis, endpoint,
provider, network, netuid, finalized block/hash/time and registration identity.
Snapshot comparison rejects stale or reassigned identities. Finality is reported
by the provider, not independently proven by this adapter. No write interface.

The official PyPI stable-release check found 11.1.0, with wheel SHA-256
`d84e33169249c56c41b4b43f6b2f4ed80bc2fd98afcb69a3d5844720a4d72b58`.
Source inspection verifies public Client/at/Snapshot/read registry and backend
injection contracts. Both SDK declarations are now exact; uv 0.12.7 resolved
144 packages for Carbon Python 3.11.16. Existing resolved SDK/core versions
were already 11.1.0/0.1.3; only root requirements needed lock reconciliation.
Runtime v445 is independently source-pinned at
`d3f40e44bda9019c606aeb0c907bb52ba7fe386c`; no built image, observed genesis,
burn semantics or localnet maturity is claimed. See CHAIN_ADAPTER.md.

Native diagnostic commands (Python 3.12.14, Windows; NOT canonical evidence):

```text
python -m pytest -q tests/cpu/test_net1_chain_adapter.py tests/invariants/test_net1_chain_boundary.py
35 passed, 2 skipped
python -m ruff check carbon/chain tests/cpu/test_net1_chain_adapter.py tests/invariants/test_net1_chain_boundary.py
python -m black --workers 1 --check carbon/chain tests/cpu/test_net1_chain_adapter.py tests/invariants/test_net1_chain_boundary.py
```

The two skipped tests require the actual installed SDK. Linux CI explicitly
installs the locked chain group and requires these contracts to execute. No
native skip substitutes for that acceptance. Ready-revision acceptance and
merge are still pending in this candidate; dynamic results belong in the PR.

Local environment diagnostic: Docker 25.0.3 client is present, but
`docker version` cannot open `//./pipe/docker_engine`. Starting Docker Desktop
did not leave a running backend. WSL reports default version 2 but no installed
distro. Git Bash's canonical wrapper additionally rejects the Windows-path
repository-root comparison before invoking Docker. These are infrastructure
failures, not test passes. Do not repeat an unchanged environment attempt.
Use a working Docker/WSL Linux checkout and
`CARBON_UV_GROUPS=chain CARBON_REQUIRE_CHAIN_SDK=1 ./scripts/dev/canonical.sh --focused tests/cpu/test_net1_chain_adapter.py`
for local canonical execution; repository CI supplies acceptance meanwhile.

The supplied Carbon_Wave_C_Reward_Prototype_v1.zip was inspected as synthetic
analytical reference. Its Q12 floor/remainder and immutable decay-anchor
contract are retained for the later C-REWARD ticket, not counted as NET-1 tests.

## Authority and prerequisite disposition

`.agent/WAVE_C.md` §2 records the exact NET-0 boundary disposition. Carbon/
chain ownership and read-only SDK containment are settled for local adapter
development. Authentication, replay, signing, publication, reward policy,
sink identity/custody, quorum/stake, production topology, deployment, and
security acceptance remain unavailable in their later owning operations.

## Evidence to complete

- exact official SDK package/API verification and compatible pin;
- immutable Carbon-owned interface, snapshot, identity, and failure types;
- SDK-backed read-only translation with injected deterministic substitutes;
- focused and invariant test mapping for every Definition-of-Done criterion;
- managed lock and installed-package evidence;
- applicable ready-revision CI and `Merge gate` result;
- explicit statement that live-chain integration remains unverified.

## Maturity ceiling

The transition earns no NET-1 implementation or test maturity. The implementation
may earn bounded `SPECIFIED`, `IMPLEMENTED`, and `TESTED` only. Every scientific,
security, network, commercial, production, LIVE, launch, testnet, mainnet,
transaction, weight, custody, emission, and settlement state remains unearned.

## Broad regression and focused repair

Run 34402066830 on 253403f: canonical CPU 4,865 passed / 2 failed
(bootstrap tests inherited CARBON_UV_GROUPS=chain); all 169 invariants passed.
Installed Bittensor contract tests passed. Clean image: 4,862 CPU passed /
5 expected skips; 169 invariants, 86 package checks, 17 code-authority tests
passed. The canonical job remains failed evidence. The repair parameterizes
both dev-only and dev-plus-chain environments. No SDK/application source
changed. Native selector/network/invariant diagnostics: 87 passed, 2 optional
SDK skips. Final repaired Linux acceptance and merge remain pending.

OWNER-C0-VALIDATION-01 authorizes focused acceptance for this repair. The
selector verifies the exact constraint-only migration; the locked package
resolution is unchanged. Full regression remains for unknown paths, scientific
code and changed resolved dependencies. No failure is suppressed.

## Accepted delivery

PR #120 merged 6dad22db26e4b8babadf73c4de2527a17485a2b1 on 2026-09-09.
Exact head 528213a passed run 34405478897: 169 invariants, 352 network/tooling,
86 package, 17 authority checks, clean image, Hub and Merge gate. Merge tree
1bef01d3a202c6a1868f5c16be8d963aff726efe matches the tested head.
NET-1 is done in bounded read-only engineering scope. NET-2 is next.
No localnet or scientific/security/production qualification.
