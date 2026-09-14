# D-05 — Measurement qualification and calibration

**Wave:** D scientific qualification
**Status:** `future_reserved`; unselected and unstarted
**Depends on:** C-05, D-02, D-03, D-04

**Prospective prerequisite harness:** C-05's selected bounded slice implements
the exact 3-replica-by-12-public-case variance separation and paired
rank-stability calculations authorized by `OWNER-C1-BURGERS-ALPHA-01`. This
does not select Wave D, set the decision-resolution target, qualify floors or
complete any checkbox below.

## Definition of Done

- [ ] Implement reproducible calibration scripts for applicability, numerical/reference floors, uncertainty, sensitivity, and rank stability.
- [ ] Retain inputs, exclusions, dependence, failures, candidate sets, and output intervals under exact policy identities.
- [ ] Prevent post-result threshold tuning and keep numerical floors distinct from human scientific acceptance thresholds.
- [ ] Emit evidence for the first Score Pack and human measurement qualification; indeterminate evidence remains indeterminate.

No measurement, gate, weight, or score threshold is ratified by the scripts alone.
