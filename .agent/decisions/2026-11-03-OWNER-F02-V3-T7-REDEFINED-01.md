# OWNER-F02-V3-T7-REDEFINED-01: Burst Thermal 3.0 T7 redefined at a new threshold (value in custody)

Date: 2026-11-03 (CST, ~12:16)
Status: DECIDED by the owner, directly in the Lead session (local_87151681-c66e-4949-a26c-23c4641b5722).
Owner's words: "Yes: Burst Thermal 3.0 T7 redefined at [the new threshold] (time above it and recovery measured at it); recompute their uncertainty at it from the existing runs before registration." The threshold value is not in the published F02 spec yet, so it is held in custody (Validator ruling 19:56, 3 Nov) and its publication is decided at registration.

## Evidence at the decision
- The pooled design counts and the share of T7-feasible designs scoring exactly 0 s at each candidate threshold are pool statistics: held in custody by sha, not repeated here.
- The chosen threshold is a choice among candidate thresholds, not a measured optimum. Its effect on how well T7 separates models is not yet measured.

## Decided
- **T7's threshold:** "time above" and the recovery threshold are measured at the new threshold (value in custody) instead of the old one.
- **Unchanged:** the peak, the first-95 °C crossing, the second-pulse peak, the extra energy, the 95 °C limit (T1), and the T3/T4 limit shifts.
- **Before registration,** the reference uncertainty U for time_above and recovery is recomputed at the new threshold from the existing U-panel runs (read-only; Evidence/TL). The kept case dirs allow this with no new solves.
- **BT 3.0 is a new version,** so nothing graded is rescored.
