## 2026-10-11 — OWNER-CODE-VERIFICATION-ACCEPT-01: code verification (MMS) accepted for GetDP (motor) and PyBaMM (battery)

**Authority.** The owner, verbatim in the Test Lead session on 2026-10-11:
"I accept MMS results". The Test Lead relayed it to Data Collection. Code
verification is a science acceptance reserved to the owner. This record
takes effect when merged through the PR Head, which confirms it with the
owner.

**Accepted.** These are the results reported before the quote. Both ran
natively in the pinned images, under CODE-VERIFICATION-MMS-01 (#1046)
workers, with the evidence in #1050.

| Solver | Image | Manufactured test | Expected order | Measured order (finest pair) | Pass band |
|---|---|---|---|---|---|
| GetDP 3.5.0 (motor) | `sha256:599521e79786ee0326a0754ba0545f51ee9665adff73c3515c8d4b8ba24c1c05` | 2D magnetostatic A = sin(pi x) sin(pi y), Form1P / P1 | A: 2; B: 1 | A L2 1.987, Linf 1.990; B L2 0.992 | A [1.7, 2.3]; B [0.7, 1.3] |
| PyBaMM 26.8.0.0 (battery) | `sha256:2d19b261e722fe67f20bee02e115f2277a799c448b90d54d2872361b341bd940` | spherical-particle FV diffusion; lumped heat theta' = 1 - theta | particle: 2 | particle L2 2.000, Linf 1.999; lumped heat error tracks tolerance (1.6e-6 / 1.6e-7 / 4.9e-9 at rtol 1e-4 / 1e-6 / 1e-8) | [1.7, 2.3] |

**Not covered.** Elmer (f02, image `sha256:6fab746f...`) was not reported
before the quote, so it needs its own owner decision. Its evidence is in this
PR: space order 1.995 / 1.930; time order 2.49 at t_end 0.5 (outside the band,
from a test-design degeneracy); a diagnostic rerun at t_end 0.375 gives 2.07.

**Scope.** This is code verification of the discretisation only. It is not
reference adequacy, physical validity or qualification. A rebuild or re-pin
needs a new run and a new acceptance.
