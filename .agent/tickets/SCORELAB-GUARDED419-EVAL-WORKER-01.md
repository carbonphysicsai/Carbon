# SCORELAB-GUARDED419-EVAL-WORKER-01

Status: IN_PROGRESS. Root delegated one source-only guarded419 EVAL worker repair on
2026-10-16 from normally merged main `5cb889da0ce8a4b7414e8bac1b2b2115b436d600`.
The 14 original fc01 CAL scientific blobs and existing EVAL adapter,
feasibility02 solver, question law, and values remain frozen.

## Working contract

KEEP `guarded419_eval` registration, CAL nominal constructor, pretruth roster,
and `feasibility02._timed`/`_guarded_job_context`. WRAP them with one separate
`scripts/dev/score_lab/guarded419_eval_worker.py` file-based entry. The new
worker admits only `PUBLIC_DEVELOPMENT`, a closed independently pinned
stage binding, the exact original acquisition plan and registered N1 context,
all 18 pretruth member commitments and their independently pinned original
files, and actual nominal full compatible CAL15 before any output creation or
worker submission. The worker passes the exact stage binding and digest to
`_timed`, so the existing solver's admission remains authoritative.

The closed file spec identifies the stage binding, nested original CAL
`FILE_SPEC`, pretruth raw receipt, all 18 members' fit receipt, predictions,
commitments, and commitment receipt bytes, an ordered nonempty subset of
registered EVAL job IDs, and this runner's source hash. The subset is an
operational dispatch bound, not a changed question law or completed EVAL
claim. Base 120 offers retain their original order and optional refinement
IDs remain explicit in the stage binding. No stage is auto-chained.

Record every returned reference outcome and typed missing/infra state in an
atomic native receipt and original raw JSONL. No fake success, hidden data,
qualification, security attestation, or custody chronology claim. Root owns
the external pretruth chronology/custody proof, exact provider limits,
dispatch eligibility, canonical tests, CI, review, push and merge.

Owned paths: this ticket, one new worker module, exclusive focused tests, and
one durable handoff. No frozen14 source or existing worker/adapter edits.
Hub impact: no change to the retired Development Hub's purpose, placement,
status, dependencies, boundaries, maturity, or links under OWNER-DX-03 and
OWNER-WORKFLOW-SPEED-01; historical map_ref `SYSTEM/AGENT-EXECUTION`.

Author validation is source/AST/Black/Ruff/Git only. Root performs runtime and
canonical validation. This ticket is DEVELOPMENT engineering only; no actual
EVAL evidence, scientific qualification, LIVE or production authority.

## EVAL-WORKER-D1 — separate file-based transport

Problem: the existing feasibility02 worker admits a closed EVAL stage binding,
but its CLI/solve path cannot transport that binding to child processes.
Recommended reversible implementation: use a separate file-pinned module,
operationally selected ordered EVAL subset, and `ProcessPoolExecutor` calls to
the existing `_timed` with its stage binding/digest. Validate the full nominal
CAL, registered source/plan/context, all 18 pretruth member file bytes, and
source closure first. Retain a typed original-row receipt. This module is not
an alternate solver or scientific reducer. Alternatives rejected: extending
the frozen feasibility02 CLI (would alter source14); invoking unbound `solve`
(it rejects guarded jobs); fabricating full CAL or pretruth success (invalid
authority); and treating file hashes as chronology proof (insufficient).

Interfaces affected: new internal `FILE_SPEC` and CLI only. Existing public
scientific adapter, worker job schema, producer, CAL, T128 and reference
semantics remain unchanged. The materializer and Root provider plan depend on
the new closed spec; the eventual EVAL consumer still validates original raw
chunks independently. To supersede D1, change this ticket, the new worker and
exclusive tests, then review the complete diff. No human-reserved value is
selected here; actual custody chronology, dispatch and qualification remain
Root/human-owned and fail closed. Working source branch/head and tests are
reported in the external handoff; no maturity change is asserted by this
source-only authoring step.

## Review repair R1 — member-file alias refusal

Product's exact-head engineering review found that two different raw path
strings could resolve to one uploaded file through `.` or an in-root symlink.
The original no-alias contract therefore needed a path-identity guard. Member
keys now require canonical relative spelling and case-fold-distinct identity;
the CLI public loader rejects dot segments and symlinked components even when
their target remains inside the public root. Focused negative tests cover both
spelling and symlink aliases. No FILE_SPEC field, scientific input, source14
blob, provider route, or worker admission semantics changed. The successor
head requires fresh canonical checks and review; the first head is superseded.
