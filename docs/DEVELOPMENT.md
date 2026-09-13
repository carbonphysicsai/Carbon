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

For the selected C-02 ticket, the source-controlled Apple-silicon CPU
diagnostic profile is reproducible with:

```bash
./scripts/dev/refresh_jax_macos_lock.sh
./scripts/dev/setup_jax_macos.sh
.venv-jax-macos/bin/python scripts/dev/jax_macos_diagnostic.py doctor
PYTHONPATH=tests/cpu .venv-jax-macos/bin/python -m pytest tests/science -q
```

The refresh command uses repository-required `uv==0.12.7`; the setup command
syncs only the hash-locked CPU dependencies into `.venv-jax-macos`. It installs
no CUDA or other accelerator packages. Native results remain diagnostics;
GitHub's Linux x86-64 `science-jax` lane is canonical acceptance.

The immutable legacy location and retrieval rules are recorded in
[`docs/history/LEGACY_CODE_INDEX.md`](history/LEGACY_CODE_INDEX.md). Archive
presence grants no current implementation authority.

This environment and its passing engineering gates do not qualify science,
security, network behavior, economics, `LIVE`, launch, or production.
