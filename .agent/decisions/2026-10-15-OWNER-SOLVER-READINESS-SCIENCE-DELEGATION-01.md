# OWNER-SOLVER-READINESS-SCIENCE-DELEGATION-01: agents set DEVELOPMENT solver-readiness check values

Date: 2026-10-15. Recorded on 2026-10-21, because no record file was written at the time.
Status: APPROVED by the owner. The owner confirmed it directly in the Carbon Validator's session on 2026-10-21 ("Yes, record it").

## Decided

- **The agents may set the DEVELOPMENT values that solver-readiness checks use:**
  - rebuild acceptance;
  - per-rung convergence and conservation bands;
  - cross-tool tolerances;
  - value-check thresholds.
- **Each value is registered before the runs it judges.**
- **The owner may change any value at any time.** A change is a new version, and it is never applied retroactively.

## Limits

- **DEVELOPMENT only.** No qualification, LIVE, payment or spend effect.
- **It does not replace owner acceptances,** for example code-verification acceptance (OWNER-CODE-VERIFICATION-ACCEPT-01, which needs a new acceptance on a rebuild).

## Records issued under it

- `2026-10-15-F02-SCIENCE-VALUES-01.md`, with `docs/development/evidence/reference-packages-01/f02-readiness/bands.json` (commit `358b30ffb668d934c06a10b0669f3c75b2537443`).
- `F08-SCIENCE-VALUES-01`, cited in `docs/development/challenge_pipeline/structures-readiness/registration.json`.
