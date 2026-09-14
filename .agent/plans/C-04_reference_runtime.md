# C-04 role-explicit Burgers reference runtime plan

**Decision:** `OWNER-C1-BURGERS-ALPHA-01`
**Status:** bounded implementation accepted in PR #154; scientific/security
qualification remains pending
**Base:** PR #151 merge `2d5872aff89ca7bef3e3f062b293aeefe17769aa`
**Accepted:** head `32fa87f0f4947b8fbae9b2b73e5fa875a73de175`, run
`34784739423`, PR #154, merge
`0cd91bfa6d30f81739ff75e46888f6f1387bd1de`
**Primary Hub map_ref:** `WAVE-C/C-04`

## Scope

Keep B-04's immutable policy/outcome vocabulary, B-E2's typed failure
separation, the public C-AUTH1 Burgers generator and C-03's Docker controls.
Add one separate `carbon.reference_runtime` implementation package. It consumes
only B-04 enum outcomes and never imports TruthAsset admission, measurement,
score, reward, archive or network authority.

The candidate operational roles are prospectively fixed as:

1. Cole–Hopf Fourier quadrature — candidate primary;
2. periodic conservative finite-volume Rusanov/SSPRK3 — independently
   discretized witness; and
3. dealiased Fourier ETDRK4 — DEVELOPMENT cross-check only.

All use exact float64 request/output semantics, the existing public Burgers
physical scales and the exact C-03 locked CPU science environment. Method
execution success cannot issue a truth asset or qualification.

## Ordered implementation

1. Define a closed, canonical request whose digest includes the Challenge,
   public case bytes, policy, nominal role, implementation, environment,
   precision, numerical settings, physical coefficients, viscosity, length,
   requested points/times and output semantics.
2. Implement the three methods without a generic callback, import path,
   command, fallback, solver vote or automatic scientific threshold.
3. Seal bounded raw little-endian float64 artifacts and validate exact bytes,
   shape, dtype, finiteness, identity and status in a separate capped process.
4. Dispatch the C-04 schema through the fixed C-03 image entry point. Reuse its
   read-only root/input, non-root user, no capabilities, seccomp,
   no-new-privileges, network-none, cgroup, scratch, output, deadline,
   termination and resource-observation controls.
5. Persist intent before container creation, use the request/image/policy
   digest as the idempotent launch key, preserve exact replay, and refuse
   uncertain/changed histories. Association occurs after container removal.
6. Bring forward only D-03/D-04 prerequisite probes: initial recovery,
   periodic closure, Cole–Hopf conditioning/quadrature sensitivity,
   conservative mean drift, spatial refinement and method discrepancies.
   Record observations without scientific pass/fail.
7. Freeze and run twelve public EVAL cases, one per registered cell, under the
   required Linux service lane. Preserve every run and limitation.

## Stop boundary

This slice cannot qualify the method hierarchy or comparison tolerance and
cannot enable protected or score-eligible use. D-03/D-04 scientific acceptance
and the commissioned independent protected-execution review remain external
gates. C-05 may consume the merged engineering outputs only as explicitly
non-official public test inputs.
