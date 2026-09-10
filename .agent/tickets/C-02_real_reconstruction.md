# C-02 — Real declarative reconstruction

**Wave:** C1 real scientific execution foundations
**Status:** `future_reserved`; unselected and unstarted
**Depends on:** B-02B, B-03, B-E1, C-01

**Required external interface input:** the authorized JAX implementation
repository URL, one immutable revision, its reproducible dependency/build
identity, and the actual training/inference entry points, signatures, array
shapes/dtypes, state/artifact format and error semantics exposed at that revision.
Until those source/interface facts are supplied, C-02 remains fail-closed and
unselected.

## Goal

Implement the real declarative JAX reconstruction backend without broadening the accepted Strategy language or exposing official cases.

Carbon owns the adapter around the supplied interface. The upstream JAX
implementation is not required to rename or wrap its functions as
`fit_train_arrays`, `freeze_artifact` or `infer_requested_points`; those are
Carbon-side semantic capabilities, not mandatory upstream symbol names.

## Definition of Done

- [ ] Reconstruct only an exact compiled Strategy under a pinned backend profile and registered CPU/GPU, memory, time, process, output, and environment limits.
- [ ] Bind every reconstruction receipt to the Strategy, resolved plan, candidate artifact, implementation/environment, registered resources, and repeated-build identities.
- [ ] When policy requests repeats, retain per-repeat outcomes and dispersion evidence under the same Strategy and resource policy.
- [ ] Reject identity, environment, artifact, or resource mismatches before result association; typed resource and infrastructure failures are not scientific failures.
- [ ] Deterministic and bounded integration tests prove reconstruction/result association and prove protected official case material is absent from public receipts.

## Authority ceiling

Engineering implementation only. No scientific qualification, official score, LIVE, network, settlement, or production authority.
