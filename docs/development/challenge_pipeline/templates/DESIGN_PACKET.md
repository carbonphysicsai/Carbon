# Design packet: <family id> <challenge name> v<version>

**Template, DRAFT until protocol lock** (Challenge Roadmap §02 Stage 2 and
§06). Each section cites the committed artifact that holds it: a file, a
commit or an evidence directory.
- A section with no artifact says `GAP`. No value is invented to fill it.
- Values that the roadmap or Carbon's authority reserves to people stay
  `HUMAN_INPUT` until they are set.

| Field | Value |
| --- | --- |
| Accepted brief | path, and the `scope` gate's decision |
| Readiness record | `carbon/challenge_readiness/records/<id>.v<N>.json` |
| Protocol version | |

## 1. Engineering decision

The user, the design and control variables, the objective, the constraints
and the consequence of error.

## 2. Scope and data

- Geometry topology, numeric bounds and units.
- Material provenance.
- Boundary and initial conditions.
- Output locations, and time or frequency grids.
- The registered dimensionless regimes.

## 3. Reference

- Exact solver build and image digest, discretization, tolerances and
  deterministic settings.
- Analytical or manufactured controls.
- Refinement evidence.
- The failed-case policy: failed solves are counted by rule, never dropped.
- Credibility level reached (§06): 1 numerical correctness, 2 model
  adequacy, 3 decision reliance.

## 4. Feasibility panel and timing

- The 30-case stratified panel, with its outcomes.
- Timing on the reference hardware:
  - setup, solve, post-processing and failures, timed separately;
  - warm and cold runs;
  - peak memory;
  - p50 and p95.
- These are the pipeline record's `p50s`, `p95s`, `cases` and `hw`, and its
  `evidence.timing`.

## 5. Generator and splits

- The case generator and its sampling law.
- The splits, by whole geometry, trajectory or regime: public practice,
  permitted construction data, development holdout, rotating exam batches,
  anchor set and sealed pool.
- Interpolation, boundary and out-of-envelope panels.
- The rotation cadence and selection rule, and the disclosure budget
  (`HUMAN_INPUT` until set).
- The sealed pool: its size (`HUMAN_INPUT`), and its root commitment under
  an operator-held root. The root and cases never enter the repository or
  rented compute.

## 6. Construction

- The construction contract:
  - JAX-runnable recipe;
  - permitted declarations and methods;
  - authorized data;
  - build resources, seeds and dependencies.
- Reconstruction and artifact identity.
- The training budget study (OWNER-TRAINING-BUDGET-STUDY-01).
- The Launchpad reference build, identical to the validator pin, with its
  licence check.

## 7. Evidence design

- Physical gates: a mandatory failure disqualifies, whatever the accuracy.
- Normalized errors, critical regions and uncertainty treatment.
- Decision tests.

## 8. Baselines

Run at matched budgets, with their scores on the development holdout:
- the direct solver with caching or factorization reuse;
- interpolation;
- a reduced-order model, where one exists.

## 9. Deployment record

Supported inputs and outputs, the latency budget, version pinning and
requalification triggers.

## Design sign-off

Left blank by the drafter. The science owner's signature is recorded in the
pipeline record's `design` gate: `{by, on, ref}`.
