# 2026-10-05 — OWNER-MOTOR-COUNTED-ADOPT-01: motor study V2 adopts the counted V1 GetDP campaign

**Authority.** The owner, in the Data Collection session on 2026-10-05, chose option A of two:

> 1. A

The two options were:
- **Option A:** fix the importer in a new study version and reuse the existing 48 counted runs, provided the new version's proposals equal those sealed before dispatch.
- **Option B:** fix the importer and rerun all 48 cases.

**Ticket:** `.agent/tickets/CHALLENGE-MOTOR-04_counted_adoption.md`.

## What happened

The counted CHALLENGE-MOTOR-03 campaign (OWNER-DATA-MOTOR-01) ran on 2026-10-05 from 00:18Z on the operator host.
- **Run:** pinned GHCR image, Docker, 2 CPUs per case, 6 concurrent, 3,600 s timeout.
- **Result:** 48/48 cases OK with no retries.

Every case exited 0 and converged, retained all 61 torque files, and matched its mesh record.

The registered V1 importer still refused every case as `REFERENCE_PROVENANCE_INVALID`:
- It required `log.mesh` and `log.getdp` to be non-empty.
- The pinned GetDP and Gmsh write nothing to those logs on success. All 48 counted cases and all 12 earlier calibration cases had 0-byte logs.
- #562 was fixture-tested only, and no test had ever exercised the counted importer, so its runner and importer had never been checked against each other.

No evidence was edited. The raw attempt directory was hashed (`SHA256SUMS.attempt-1`, 9,185 files) and made read-only before any fix.

## Decision

1. **Importer rule.** A successful case must still have:
   - exit 0 and a convergence check of 0;
   - non-empty `params.json`, `machine.pro`, `mesh.py` and `mesh.json`;
   - all `ANGLE_STEPS + 1` torque files, each non-empty;
   - a mesh record matching `mesh.json`.

   The solver logs must exist but may be empty.

   Changing `carbon/motor/decision_study.py` changes the study's frozen code. The change therefore ships as **study V2** (`MOTOR_SYNTHETIC_DECISION_V2.json`), which differs from V1 only in `study_id`.
   - V1, its fixture and its freeze stay the historical record (invariant 10).
   - V1's fixture is now checked for internal consistency only.

2. **Adoption, not rerun.** `adopt_counted_campaign`:
   - validates the V1 campaign against V1's own plan, ledger and artifacts;
   - binds the evidence to V2's construction only after `adoption_check` proves that V2's four arms decided exactly what V1's sealed commitments decided: arm, model, method, budget, query counts, selections, selection and every predicted condition.

   Construction reads no reference. The V1 plan binds V1's construction identity, which digests every commitment, and the ledger reserved that plan before any solver ran. Identical decisions therefore show the reference results could not have influenced V2's proposals.

## Result (descriptive DEVELOPMENT pilot over the registered finite set)

- **Comparator:** complete. 4 designs are reference-feasible and 4 infeasible. The best is d04, with a worst-condition ripple fraction of 0.2451.
- **Analytical model** (fixed grid, and screen-then-confirm): selected d07, which the reference shows infeasible. This is a false-feasible decision; the model predicts zero ripple.
- **KRR model** (both methods): selected d06. It is feasible, with exact finite-set regret of 0.0192 in ripple fraction.
- **Search method** made no difference to any selection.
- **Cost:** 48 solver executions; 59,599 s summed solver wall; 33.1 allocated core-hours on the operator host.

Evidence: `docs/development/evidence/motor-decision-counted-v2/`.

## Unchanged

- The motor exam and its pools, including the private pool.
- The §6 synthetic values.
- Every scoring rule, gate and tolerance.
- The V1 fixture.

This record makes no scientific, customer, population-reliability or production claim, and grants no LIVE authority.
