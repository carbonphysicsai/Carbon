# OWNER-EXAM-CAP-ROTATION-01: C = 20 with daily exam rotation (revisable)

Date: 2026-10-19
Status: APPROVED by the owner "for now", so **revisable**. Confirmed in the Test Lead's session and relayed to the Carbon Validator, who records it.
Implementation:
- **The counter is built** in `carbon/challenge_validator/exam_cap.py`, landing with `claude/step1-motor` at `7c8d85e8a` (it carries `afb02a0ba` and `6c37f071a`):
  - C = 20 for all five Challenges, keyed per (hotkey, Challenge, sealed-exam pack digest);
  - one graded submission per 360-block window, from the signed receipt;
  - build refusals, FAILED_INFRA and indeterminate outcomes don't count;
  - a crash-held slot is released as FAILED_INFRA at start-up, and start-up fails closed without the deadline policy.
- **Daily rotation is operational, not code.** A rotation restarts the receiver with the next QA-passed pack. The pack-digest key starts new counts automatically.
- **Not yet built:** regrading the king on the new pack after a rotation (route A, in progress). Until it lands, a comparison after a rotation is UNAVAILABLE.
Proposal: `codex-queue/reports/PRIVATE_EXAM_CAP_PROPOSAL_20261019.md`.
Supersedes the C value in `OWNER-GRADE-FEEDBACK-LADDER-01` (which was C = 10), prospectively. The Ladder rule and η = 0.02 are unchanged.

## Decided

- **Per-miner cap C = 20** graded submissions per sealed exam version, for every Challenge.
- **Plus at most one graded submission per miner per epoch** (360 blocks).
- **Each Challenge's sealed exam rotates daily** from the AX42 backlog. The wear trigger (the king's exam score measurably above his fresh-exam score) can rotate one earlier.
- **Fallback if AX42 time is short:** Battery at C = 10 with 12 h rotation. The others are unchanged.

**Basis:** daily fresh exams for all five take about 130 CPU-h a day, about 45% of one AX42 (an optimistic SMT figure).

**To re-measure:** the AX42's real throughput under load, and Battery's solves per exam (set by the bank spec).
