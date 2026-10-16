# SCORELAB-GUARDED419-T128-WORKER-01: separate source-bound partition runner

Ticket: `SCORELAB-GUARDED419-T128-WORKER-01`. Classification:
`IMPLEMENTATION_LAG`: the frozen T128 adapter registers inputs and validates
raw deliveries but exposes no file spec, CLI or pool route.

Working engineering decision: add a separate closed T128 runner. Reuse its
existing 60/59 partitions, T9/CAL prerequisite validators, T128 raw-delivery
validator and the existing collector pool. Bind the new runner module hash
and new execution commit separately from the existing 13-file T128
scientific source inventory. A Git checkout verifies HEAD and committed blobs;
the existing gitless `pod_jobs` bootstrap path instead requires its inherited
`CODE_REF` to match the binding and independently checks all shipped local
bytes. The basis is recorded in the receipt. `CODE_REF` is transport metadata,
not an in-process attestation; Root's bootstrap/provider receipt establishes
the external execution claim. This preserves the original `fc01` raw source
proofs while honestly assigning new T128 rows to the new commit. Only Root
dispatches a partition and enforces external resource limits.

Reject modifying the `fc01` worker/guard/CAL source, pretending the new CLI
existed in `fc01`, rerunning T9 anchors, bypassing CAL with a caller PASS,
adding a third partition or redraw, launching all119 automatically, and
classifying absent/infra rows as scientific failures. The file-spec/schema
is prospective engineering provenance and grants no scientific rule change.

Implementation location: `scripts/dev/score_lab/guarded419_t128_worker.py`
and exclusive tests on `codex/scorelab-guarded419-t128-worker`. A new runner
spec is reversible without changing the already registered T128 validator or
old evidence. Supersede this record and ticket to change the route. No
human-reserved scientific value is selected. Root owns canonical tests,
provider limits, stage dispatch, publication and merge.
