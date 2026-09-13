# D-04 — Independent conservative numerical witness

**Wave:** D scientific qualification
**Status:** `future_reserved`; unselected and unstarted
**Depends on:** C-04

## Definition of Done

- [ ] Implement an independently owned conservative witness with spatial/time refinement and explicit scheme/tolerance identities.
- [ ] Retain conservation diagnostics, convergence histories, uncertainty, applicability, and case-level discrepancy records.
- [ ] Disclose material shared dependencies with the primary reference and reject false independence claims.
- [ ] Typed disagreement, nonconvergence, numerical failure, and infrastructure failure remain non-candidate and cannot silently settle.

The witness supplies corroborating evidence only after separate human qualification.

## C-04 prerequisite brought forward

`OWNER-C1-BURGERS-ALPHA-01` prospectively permits only the prerequisite harness
needed to assess C-04. The candidate witness is a periodic conservative
finite-volume Rusanov/SSPRK3 implementation, distinct from the Cole–Hopf/Fourier
discretization. The harness retains spatial refinement, mean drift, primary/
witness discrepancy and all shared dependencies without a tolerance or
agreement decision. Shared governing equations, case authoring, NumPy runtime
and repository are disclosed; independent human review is unavailable. This
does not select, activate or complete D-04.
