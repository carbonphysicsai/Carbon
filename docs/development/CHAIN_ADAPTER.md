# Chain adapter and SDK upgrades

NET-1 owns read-only provider observations. Construct `ChainContext` with an
explicit endpoint, provider label, network, expected genesis and netuid, then
inject `BittensorReader` into `ReadOnlyChainAdapter`. Construction and package
import open no connection or wallet. Only `observe(minimum_finalized_block=...)`
performs reads. Never use a zero watermark as proof that a snapshot is current.
Applications persist their accepted watermark and apply their own registered
freshness policy; downstream privileged operations recheck at execution.

The adapter uses Bittensor **11.1.0**, whose official PyPI wheel SHA-256 is
`d84e33169249c56c41b4b43f6b2f4ed80bc2fd98afcb69a3d5844720a4d72b58`.
The 2026-09-09 stable-release check found no newer stable package. PyPI points
to the RaoFoundation/subtensor monorepo; the old opentensor/bittensor release
feed is not the v11 release authority. `uv.lock` resolves the core and all
transitive dependencies; both optional-extra and dependency-group declarations
pin the same version. Bittensor core 0.1.3 provides Linux/macOS wheels, no
Windows wheel. Native-host tests cannot establish installed-SDK compatibility.

Source inspection used the hash-verified official wheel. Required Linux CI
installs the chain group and exercises the actual installed Client, Snapshot,
read registry and generated descriptors against a backend with only read
methods. It verifies `blocks(finalized=True)`, `at(block)`, `read("metagraph")`,
`Timestamp.Now`, genesis mismatch rejection, cleanup and exact block hash
arguments. The release's typed metagraph convenience method pads missing
columns; Carbon instead checks the raw registry response and rejects incomplete
identity columns. SDK objects and exceptions stay inside `carbon.chain`.

The provider reports finality. This adapter is not an independent consensus
verifier or a provider quorum. Contradictory before/after hashes fail closed;
a consistently dishonest provider can still lie. Snapshot identities bind the
complete Carbon identity projection including registration block, context,
time and hash. UID, coldkey and registration changes invalidate old bindings.
No observation grants scientific or settlement authority.

Runtime source is pinned independently in `scripts/dev/localnet-runtime.json`.
The v445 source pin is a build input, not an observed runtime/image/burn result.
NET-5 must record the built image digest and observed genesis, and verify
capabilities before using them. Null observation fields prohibit privileged
operation until the owning harness resolves them from its disposable node.

## Upgrade workflow

Run from Carbon's canonical interactive development environment:

```bash
# Choose and record one stable release after official metadata/API inspection.
# Edit BOTH bittensor declarations in pyproject.toml and SDK_VERSION in
# carbon/chain/sdk.py; update installed-SDK assertions and evidence.
uv lock --upgrade-package bittensor --upgrade-package bittensor-core
CARBON_UV_GROUPS=chain ./scripts/dev/bootstrap.sh
CARBON_UV_GROUPS=chain CARBON_REQUIRE_CHAIN_SDK=1 \
  ./scripts/dev/canonical.sh --focused tests/cpu/test_net1_chain_adapter.py
```

Submit a reviewable ticket PR with exact dependency/lock changes, package hash,
API/capability differences, focused regression results and required acceptance.
Re-run later NET-4B compiler/execution and NET-5 runtime contracts when those
interfaces exist. Runtime upgrades need their own pin and capability evidence;
an SDK update cannot stand in for that evidence. No automated production
upgrade, floating requirement, signing or public-network operation is included.

Official references: [package metadata](https://pypi.org/pypi/bittensor/11.1.0/json),
[metagraph registry API](https://www.bittensor.com/docs/query/metagraph),
[runtime v445](https://github.com/RaoFoundation/subtensor/releases/tag/v445).
