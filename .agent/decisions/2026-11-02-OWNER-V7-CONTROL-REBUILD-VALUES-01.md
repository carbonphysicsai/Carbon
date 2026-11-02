# OWNER-V7-CONTROL-REBUILD-VALUES-01: V7 control rebuild values V1–V5

Date: 2026-11-02 (CST)
Status: DECIDED by the owner, directly in the Lead session (local_87151681-c66e-4949-a26c-23c4641b5722).
Owner's words: "Yes: V7 control rebuild values: V1 = 3 repeat misses per hotkey per Challenge per day, V2 = one day, V3 = operator alert only (no auto-pause), V4 = register the controls in the one recal on the M3 image after the move, V5 = 10 bit-identical rebuilds."
Spec: codex-queue/reports/V7_CONTROL_REBUILD_RESTORE_SPEC_20261102.md. Head: V7 port 594361ac29fcd69d239765a496df8d1c5fd0bba9, Validator FINAL, Runner tier-2 2,801/0.

## Decided
| Value | Setting |
|---|---|
| V1, watch threshold | 3 repeat misses per hotkey per Challenge per day |
| V2, window | one day |
| V3, alert action | operator alert only; no automatic pause of any hotkey |
| V4, when controls register | in the one registered recalibration on the M3 image after the move |
| V5, bit-identical rebuild count | 10 |

- Until V4 registers the controls, outcomes stay FAILED_INFRA, as today.
- The push to main still needs the owner's push words in the PR Head session.
