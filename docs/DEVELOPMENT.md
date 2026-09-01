# Carbon development

Carbon's supported development and ordinary evidence workflow is the canonical
Ubuntu 24.04/glibc environment documented in
[`docs/development/ENVIRONMENT.md`](development/ENVIRONMENT.md).

From an opened Carbon Dev Container:

```bash
./scripts/dev/bootstrap.sh
./scripts/dev/doctor.sh
./scripts/dev/ci.sh
```

Those repository-controlled commands own environment synchronization,
validation, and normal PR gates. GitHub Actions first invokes
`./scripts/dev/preflight.sh` as a cheap upstream dependency, then both full
jobs execute the same repository-owned `./scripts/dev/ci.sh` acceptance
semantics. The direct local pre-PR command remains `./scripts/dev/ci.sh`; do
not reconstruct a separate local test sequence.

Native Windows Python, historical PoC/Julia/network checks, and optional JAX,
Torch, chain, CUDA, or GPU stacks are not ordinary Carbon evidence platforms
or default gates. Use an optional group or inspect archived implementation only
when the selected ticket explicitly owns it.

The immutable legacy location and retrieval rules are recorded in
[`docs/history/LEGACY_CODE_INDEX.md`](history/LEGACY_CODE_INDEX.md). Archive
presence grants no current implementation authority.

This environment and its passing engineering gates do not qualify science,
security, network behavior, economics, `LIVE`, launch, or production.
