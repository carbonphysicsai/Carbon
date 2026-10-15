# SOLVER-JUDGE-LIFETIME-01

Owner-directed execution and crash recovery, 2026-10-15; starting head c65d0e14f.
The current recovery scope collects the existing pods and verifies cleanup.
It grants no duplicate solve, new budget or automatic retry.

Finding: pod_phase deletes step scratch after exporting its keep set. The
f02 and f17 plans placed judges in later steps and referenced the deleted
sibling scratch. All 36 f02 and 13 f17 solves completed, but those judges
had no input coverage. f17's keep set also omits polyMesh/raw fields; a
post-collection judge observed 0/13 and cannot choose a mesh. f02's keep set
omits final VTU required by B5. These are orchestration/evidence-retention
failures, not physical pass/fail results. Preserve original receipts.

KEEP bounded scratch cleanup, frozen decks, numerical bands, public-only
material and the no-retry policy. REPAIR future plans to use bulk.observe
while raw scratch still exists, and make later lineage steps consume served
judgement JSON. Reject parent traversal from {work} in launch preflight and
pod loading; consumers must use {bulk} within observe or persisted {out}.

DoD: concrete lifetime regression, future f02/f17 plan repair, affected
canonical tests and static checks. Save all existing collection/failure
receipts; claim no recovered acceptance where raw data was discarded.
Do not launch repaired plans under this ticket or reinterpret the old run.
Primary historical map_ref C19; Hub frozen. Qualification and LIVE unchanged.
