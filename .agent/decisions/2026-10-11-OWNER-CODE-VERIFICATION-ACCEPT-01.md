## 2026-10-11 — OWNER-CODE-VERIFICATION-ACCEPT-01: code verification (MMS) accepted for GetDP (motor), PyBaMM (battery) and Elmer (f02)

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

**Elmer (f02), accepted with a condition.** The owner, verbatim in the Test Lead session on 2026-10-11, said "accept f02". This covers Elmer 26.2.1 (f02), image `sha256:6fab746f31257236da9e91b5be681bfbd2d25bd69f5dcd9a2e350394e8bcb675`, on transient heat with hex808 and BDF2, where the manufactured T = 1 + sin(pi x) sin(pi y) sin(pi z) cos(2 pi t) is expected to give order 2 against the band [1.7, 2.3]:

- Space, N 16 -> 32: 1.995 max, 1.930 RMS.
- Time at the first end time t_end 0.5: 2.49. This is outside the band on the fast side, and it is kept on record. At t = 0.5 the sin(2 pi t) factors of BDF2's leading error vanish, so that time point understates the error. The cause is the test design, not the solver.
- Time at t_end 0.375: 1.78, then 2.11, then 2.07 (dt 1/8 -> 1/64). This is within the band.

The condition, recommended by the Test Lead and accepted by the owner: the MMS specification's registered end time is t_end = 0.375, which is not a symmetry point of the manufactured solution. `scripts/dev/reference_packages/elmer/mms_heat.py` is amended here so future re-runs use it. #1046's `specs.json` (elmer-heat, t 0.5) needs the same amendment by its owner.

**Scope.** This is code verification of the discretisation only. It is not
reference adequacy, physical validity or qualification. A rebuild or re-pin
needs a new run and a new acceptance.
