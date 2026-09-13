# C-02 — Real declarative reconstruction

**Wave:** C1 real scientific execution foundations
**Status:** `in_progress`; bounded JAX DEVELOPMENT adapter selected
**Depends on:** B-02B, B-03, B-E1, C-01
**Selection authority:** owner-supplied C-02 JAX integration bundle and explicit
implementation request after C-EP3 merged in PR #145
**Primary Hub map_ref:** `WAVE-C/C-02`

**Required external interface input:** the authorized JAX permission-cleared
source and immutable revision/build identity are satisfied for this bounded
DEVELOPMENT slice by the supplied `carbon_jax_lab` 0.1.0 wheel, exact digest
`sha256:3941af49fb7441b9ee37408db2b759bdc65088f0bda089f2a774adc3506935db`,
its extracted source, reproducible dependency/build record, notices, tests, and
actual training/inference signatures. The interface description binds
parameter/state structures, input/output shapes and dtypes, batching/layout
rules, PRNG/RNG ownership and handling, checkpoint/artifact format, JIT/sharding
expectations and failure/error semantics.
Production source selection, scientific qualification and protected execution
remain absent and cannot be inferred from this DEVELOPMENT source.

## Goal

Implement the real declarative JAX reconstruction backend without broadening the accepted Strategy language or exposing official cases.

Carbon owns the adapter around the supplied interface. The upstream JAX
implementation is not required to rename or wrap its functions as
`fit_train_arrays`, `freeze_artifact` or `infer_requested_points`; those are
Carbon-side semantic capabilities, not mandatory upstream symbol names.

## Definition of Done

- [ ] Reconstruct only an exact compiled Strategy under a pinned backend profile
      and registered CPU/GPU, memory, time, process, output, and environment
      limits. Exact plan/profile mapping is implemented; C-03 still owns the
      unavailable hostile-worker resource envelope.
- [x] Bind every development reconstruction receipt to the Strategy identity,
      resolved plan, candidate artifact, implementation/environment, public
      TRAIN archive, normalization, full-width randomness digest, checkpoint,
      and execution-attempt identity.
- [ ] When policy requests repeats, retain per-repeat outcomes and dispersion evidence under the same Strategy and resource policy.
- [x] Reject identity, environment, data, artifact, or seed mismatches before
      result association; cancellation, nonfinite and reconciliation outcomes
      do not become scientific failures.
- [x] Deterministic bounded tests prove reconstruction/result association and
      prove protected official case material is absent from public receipts.

The complete ticket remains open because repeated-build policy and C-03's
registered isolated-worker limits are still absent. This change earns only the
bounded DEVELOPMENT adapter slice.

## Authority ceiling

Engineering implementation only. No scientific qualification, official score, LIVE, network, settlement, or production authority.
