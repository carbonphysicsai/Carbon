# #787 reference-route triage on the grant host (f02, f13)

The grant is OWNER-REFERENCE-ROUTE-TRIAGE-GRANT-01 (#801). The host was an hourly cloud server with 8 dedicated vCPUs (AMD EPYC-Milan) and 30 GiB RAM, running Ubuntu 24.04. The image is `sha256:8bcd864d…` (config id); this Docker store runs it by its OCI manifest `sha256:fdb4d838…`. The decks are frozen in `triage-decks-manifest.json`, and the runner is `scripts/dev/reference_packages/triage_run.py`. Public recipe panels only; the host address is not recorded here.

**Ledger** (`ledger.jsonl`): one row per launch, with wall time, process-tree CPU, cgroup memory peak and outcome.
- f02 used its 2 node-hour ceiling over 26 launches:
  - completed: the 8 primaries, 4 controls, 1 of 2 steady baselines and all 8 time-halving refinements;
  - mesh refinement: 3 of 8 finished before the cap, and a 4th was cut off (CENSORED_FAMILY_CAP).
- f13 used its 4 node-hour ceiling over 4 launches:
  - small-coaxial and nominal completed;
  - large-offset hit the 2 h case limit at 78 of 201 frequencies;
  - clearance-boundary was cut by the family cap at 150 of 201.
- One case was stopped mid-run to reorder the queue (primaries first); its row is reconstructed from the container's own accounting and marked as such.
- Failure: steady-40C-1500-0.8 FAILED. CG hit its iteration limit, because a steady solve has no mass term. It was not retried, and later freezes use the direct solver for steady decks.

**Measured cost against #787's hypotheses:**

| Case type | Measured | #787 hypothesis |
|---|---|---|
| f02 primary | 2.0–3.2 CPU-min, about 20 MB | p50 0.1 CPU-h, 1 GiB |
| f02 dt/2 | 3.9–6.2 CPU-min | — |
| f02 mesh × 2 | 18–20 CPU-min, 124 MB | — |
| f13 dense 201-frequency curve, 13.6 k nodes | 7.6 CPU-min, 258 MB | p50 0.5 CPU-h, 3 GiB |
| f13 dense 201-frequency curve, 29 k nodes | 81 CPU-min, 924 MB | p50 0.5 CPU-h, 3 GiB |
| f13 dense curve, 50 k nodes | > 2 h, censored | p50 0.5 CPU-h, 3 GiB |

UMFPACK ran single-threaded; the 8-thread OpenBLAS setting gave no speed-up.

**Numerical results** (`f02-observed.json`, recomputed from the returned outputs):
- **f02:** time-halving moved peaks by under 0.001 °C. Mesh × 2 moved them by 0.005–0.009 °C and the first 95 °C crossing by ≤ 0.003 s (tolerance 0.5 °C, 0.5 s). The controls reproduced on this host.
- **f13 straight duct and coaxial cases:** the power residual is ≤ 0.34 %.
- **f13 offset-neck nominal geometry:** the residual reaches 4.7 % at some frequencies (tolerance 1 %). Plane-wave extraction at the 10 mm port stubs is not valid where the offset neck excites non-planar content. Those frequencies are REFERENCE_UNRESOLVED.
  - This is a reference finding: longer stubs or modal port extraction are needed. It is not a candidate failure.
