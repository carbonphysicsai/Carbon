# OWNER-SCRATCH-TMP-WATCH-ITEM-01: /scratch/tmp becomes a watch item if the 1.4 export run is clean

- **Received by:** the Lead session, directly from the owner in chat, 2026-10-25 ~20:00Z.
- **Owner's word:** "accept" (to the Validator's recommendation, MAILBOX/LEAD.md 19:56Z).
- **Decided (conditional):** if the 1.4 EXPORT path run on the clean 32 GB host shows no /scratch/tmp FileExistsError, the /scratch/tmp crash is DOWNGRADED from launch blocker to a watch item, and the watcher stays on the launch hosts. If that run reproduces it, it stays a launch blocker.
- 8e4914101 (tolerant entrypoint) stays OUT either way unless the crash reproduces with a cause (Validator).
- Evidence so far: NOT reproduced 20/20 on rc41 (DO Ubuntu 24.04, Docker 29.9.2 + 29.1.3, a real practice), results/scratch-tmp-repro/README.md; the failures were rc26-era pair runs.
