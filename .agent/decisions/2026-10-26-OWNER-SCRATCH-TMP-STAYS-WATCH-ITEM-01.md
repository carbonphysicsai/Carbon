# OWNER-SCRATCH-TMP-STAYS-WATCH-ITEM-01: /scratch/tmp stays a watch item after its recurrence, with one automatic retry

- **Received by:** the Lead session, directly from the owner in chat, 2026-10-26 ~11:00Z.
- **Owner's word:** "approve" (to the Validator's recommendation, MAILBOX/LEAD.md 08:29Z).
- **Context:** /scratch/tmp FileExistsError recurred 2/221 on valV3 (FAILED_INFRA before training; both passed on retry); the OWNER-SCRATCH-TMP-WATCH-ITEM-01 trigger fired.
- **Decided:** it stays a WATCH ITEM, not a launch blocker (typed infra, ~1 %, no science effect). Plus: (a) the host retries that specific pre-training entrypoint failure once, automatically, so miners never see it (Launchpad, small; Validator receipt); (b) the watcher stays on launch hosts to catch the cause. 8e4914101 stays out.
