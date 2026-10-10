## 2026-10-10 — OWNER-MOTOR-TRAIN-GRANT-01 (PROPOSED): a public 10p/12s motor TRAIN set on CCX63

**Status.** PROPOSED by the Data Collection session at the Test Lead's request, inside the owner's EUR 500 bank budget. Binding only after the owner's explicit approval and merge through the PR Head.

**Why.** The motor panel is the MOTOR-FEASIBILITY-02 10p/12s double-layer family. Carbon's current motor kit is the GRUCAD 8p/24s machine and cannot serve it, so no Carbon model can be trained for the panel without a public TRAIN set for this family.

**Proposal.**

| Field | Value |
|---|---|
| Set | 256 public TRAIN geometries: seeded Latin hypercube over the registered six-coordinate grammar, geometric validity enforced, rejecting any point within normalised distance 0.10 of the 43 panel/study designs (24 public panel + 19 study; the closest existing pair is 0.200) |
| Solves per geometry | the panel's bundle: J 0; J 10 and J 15 at gamma -10/-5/0/+5/+10 (three-slice step skew 0/2/4 deg reconstructed exactly as the panel) = 11 |
| Total | 2,816 standard-resolution solves with the pinned motor reference image (sha256:599521e7...), flux observers on |
| Measured cost basis | standard solve p50 1.16 / p95 1.85 allocated CPU-h (wall x 2 CPUs on the loaded operator host; an upper bound) |
| Platform | Hetzner Cloud CCX63 (48 dedicated vCPU), hourly, owner-created, deleted when done |
| **Monetary cap** | **EUR 150 all-in** (about 70 server-hours at p50, about 108 at p95, at EUR 1.37/h) |
| Node-hours cap | 110 |
| Smaller option | 128 geometries (1,408 solves): about EUR 50-75 |
| Local alternative | about 14 days at the 10-thread operator cap; no spend |

**Material.** Public development geometry only; no hidden, AX42 or panel-held-out material. DEVELOPMENT; no qualification or LIVE authority.
