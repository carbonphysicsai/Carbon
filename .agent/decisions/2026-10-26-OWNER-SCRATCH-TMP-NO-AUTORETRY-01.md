# OWNER-SCRATCH-TMP-NO-AUTORETRY-01: /scratch/tmp stays a watch item WITHOUT the automatic retry

- **Received by:** the Lead session, directly from the owner in chat, 2026-10-26 ~12:05Z.
- **Owner's word:** "A" (choice: (a) watch item without the automatic retry, ~1 % of runs show the miner a refundable typed infra error; (b) build the retry anyway).
- **Why it came back:** OWNER-SCRATCH-TMP-STAYS-WATCH-ITEM-01 approved the retry only as a SMALL change; the Validator ruled it is not small (container lifecycle), so that condition is not met.
- **Decided:** watch item; no automatic retry in the launch build; the failure stays typed FAILED_INFRA (refundable, resubmittable); the watcher stays on launch hosts; 8e4914101 stays out. Amends OWNER-SCRATCH-TMP-STAYS-WATCH-ITEM-01 (a).
