# Carbon development

Carbon's supported development and ordinary evidence workflow is the canonical
Ubuntu 24.04/glibc environment documented in
[`docs/development/ENVIRONMENT.md`](development/ENVIRONMENT.md).

From an opened Carbon Dev Container:

```bash
./scripts/dev/bootstrap.sh
./scripts/dev/doctor.sh
```

Those repository-controlled commands own environment synchronization,
validation, and normal PR gates. Before a PR, return to the host shell at the
same checkout and run `./scripts/dev/canonical.sh --full`; it creates the
isolated, read-only-source validation environment. GitHub Actions resolves the
exact live candidate, runs Delivery preflight, and unlocks only the acceptance
lanes required by the classified change scope. Runtime-full changes also run
the repository-owned fast preflight before both full `./scripts/dev/ci.sh`
acceptance paths. Do not reconstruct a separate local test sequence.

Native Windows Python, historical PoC/Julia/network checks, and optional JAX,
Torch, chain, CUDA, or GPU stacks are not ordinary Carbon evidence platforms
or default gates. Use an optional group or inspect archived implementation only
when the selected ticket explicitly owns it.

The immutable legacy location and retrieval rules are recorded in
[`docs/history/LEGACY_CODE_INDEX.md`](history/LEGACY_CODE_INDEX.md). Archive
presence grants no current implementation authority.

This environment and its passing engineering gates do not qualify science,
security, network behavior, economics, `LIVE`, launch, or production.
