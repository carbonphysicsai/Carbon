# Native Julia Burgers DEVELOPMENT instrument

This fixed worker instrument computes periodic viscous Burgers point estimates
with a conservative Rusanov flux, centered diffusion and SSPRK3, at two spatial
resolutions. It reports internal-grid mean drift, the discrepancy between the
two resolutions, step counts, requested-horizon coverage, elapsed solve time
and Julia cumulative allocated bytes. Allocated bytes are not peak memory.
Refinement discrepancy is not a certified error estimate or qualification.

The initial field uses the current public Burgers representation: a mean plus
twelve cosine and twelve sine modes on a uniform periodic domain. The caller
must explicitly declare dimensionless variables. Physical units are never
guessed or converted. Outputs are sampled-state point estimates, not exact
finite-volume cell averages. Complex values and other precisions are unsupported.

`protocol.execute_in_worker` starts only the fixed executable
`/opt/carbon-julia/bin/julia` and this reviewed source. It belongs inside an
already-admitted Linux worker; it supplies deadline/process-group supervision,
not worker isolation or resource authorization. Existing Carbon controllers
must bind the role, principal, case, grant, image/environment and operation;
reserve/account for compilation, execution and cleanup; and enforce OS resource,
network, filesystem and disclosure boundaries. No new controller or ledger is
provided here. The old C-04 method identities and accepted route are unchanged.

The exact language pin is Julia **1.13.0**, reported as the current stable
release dated September 9, 2026 by the official
[manual downloads page](https://julialang.org/downloads/manual-downloads/).
Its [release checksums](https://julialang-s3.julialang.org/bin/checksums/julia-1.13.0.sha256)
must be verified by the worker image build, which owns the binary and image pin.
`Project.toml` and `Manifest.toml` describe a Base-only environment with no
third-party packages, package artifacts or request-time installation. The
bridge hashes both files and the Julia source into the request identity.
Startup/history hooks and mutable package caches are disabled using documented
[Julia command-line switches](https://docs.julialang.org/en/v1/manual/command-line-interface/)
and a closed child environment. This package does not download Julia.

Python protocol tests run without Julia. The separately skipped-when-unavailable
native numerical controls require the exact executable and release; passing
protocol fixtures is not evidence of native execution. No scientific,
protected-processing, security or production qualification is conferred.
