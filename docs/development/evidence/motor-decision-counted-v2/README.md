# Motor decision study: counted GetDP evidence (study V2, adopted campaign)

**Authority:**
- OWNER-DATA-MOTOR-01;
- OWNER-MOTOR-COUNTED-ADOPT-01 (`.agent/decisions/2026-10-05-OWNER-MOTOR-COUNTED-ADOPT-01.md`).

**Ticket:** CHALLENGE-MOTOR-04.

This directory holds:
- `completion.json`, the manifest: identities, hashes, counts, archive locations and the decision result;
- `adoption.json`, the digest-sealed adoption record;
- `construction/`, V2's construction (its commitments and freeze);
- `evaluation/`, the counted result and report.

The raw campaign stays outside Git:
- on the operator host at `~carbon/shared/evidence/motor-decision-counted-v1/`, read-only, listed in `SHA256SUMS.attempt-1` (9,185 files);
- off-machine in the owner's Drive folder, as `motor-decision-counted-v1-archive.tar.gz` with its manifest.

## Run

| Field | Value |
| --- | --- |
| Campaign | `sha256:a414f6b1…` (study V1 plan; construction `sha256:81e76d39…`) |
| Code | `992d046b`, a detached worktree whose 16 frozen files matched the V1 freeze |
| Image | `ghcr.io/carbonphysicsai/carbon-motor-reference@sha256:599521e7…c1c05` |
| Host | operator host, Intel i7-12700H, 20 threads; Docker, 2 CPUs per case, 6 concurrent, 3,600 s timeout, retain all |
| Outcome | 48/48 OK, 0 retries, campaign wall 9,974 s |
| Per-case wall (min / median / max) | 767 / 1,366 / 1,886 s |
| Allocated core-hours | 33.1 |

Another session's test suite shared the host for part of the run. The wall times include that contention.

## Why V2

The V1 importer required non-empty solver logs, and the pinned solver leaves them empty on success, so every case was refused. V2 fixes that rule and changes nothing else.

V2's construction (`sha256:959fb6ba…`) made exactly the decisions V1 sealed before dispatch, so it adopts the V1 campaign (`adoption.json`).

## Result

The comparator covers the complete finite set: 4 designs are reference-feasible and 4 infeasible. The best design is **d04**, with a worst-condition ripple fraction of 0.2451.

| Arm | Selection | Reference outcome | Exact regret (ripple fraction) |
| --- | --- | --- | --- |
| analytic-v1, fixed grid | d07 | infeasible (false-feasible) | n/a |
| analytic-v1, screen then confirm | d07 | infeasible (false-feasible) | n/a |
| learned-krr-v1, fixed grid | d06 | feasible | 0.0192 |
| learned-krr-v1, screen then confirm | d06 | feasible | 0.0192 |

- The analytical baseline predicts zero ripple. That misleads it into an unsafe design.
- The learned baseline picks a feasible design, but not the best one.
- The search method made no difference to any selection.

This is a descriptive fixed pilot. Arms share one decision problem and reuse evidence, so there is no population-reliability claim.
