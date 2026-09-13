# D-03 — Cole–Hopf qualification harness

**Wave:** D scientific qualification
**Status:** `future_reserved`; unselected and unstarted
**Depends on:** C-04

## Definition of Done

- [ ] Implement IC recovery, periodicity, precision, quadrature/transform sensitivity, conditioning, invariant, limiting-case, and failure-mapping checks.
- [ ] Bind every result to the exact Burgers regime, implementation, environment, policy, case, and numerical settings.
- [ ] Retain convergence and uncertainty evidence and fail closed on unsupported applicability or numerical instability.
- [ ] Produce evidence for human primary-reference qualification without generalizing beyond the tested Burgers envelope.

Passing harness code is not itself truth admission or scientific qualification.

## C-04 prerequisite brought forward

`OWNER-C1-BURGERS-ALPHA-01` prospectively permits only the prerequisite harness
needed to assess C-04. `carbon.reference_runtime.qualification_candidate`
records public-case initial recovery, periodic closure, stabilized-phi
conditioning and 1024→2048 quadrature sensitivity with exact request/method/
environment identities. It defines no pass threshold and does not select,
activate or complete D-03. Applicability, conditioning limits, uncertainty and
primary qualification remain for the scientific owner.
