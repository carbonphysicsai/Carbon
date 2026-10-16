# Private closed failure records for fixed public practice

Decision: FIXED-PRACTICE-FAILURE-DIAGNOSTICS-01-D1; working implementation.
Ticket: FIXED-PRACTICE-FAILURE-DIAGNOSTICS-01.

Root reserved this repair after consuming actual c41 worker projection
eda683f91972e6c4c2bef6be391bd72a6430a13141ba61d1a090b4fcd0739a30.
The retained evidence does not identify the original worker failure. Preserve
that uncertainty; do not silently reinterpret the reconciled FAILED_INFRA task.

Use the existing owner-only atomic write_once for separate fixed-name stage
failure records outside the snapshot. Persist only closed stage/category,
validated WorkerCode and markers selected from a constant finite vocabulary.
Inspect at most 64 KiB of WorkerFailure.private_diagnostic; never persist its
bytes or any exception string. Unknown exception types collapse to Exception.
Each stage catches and re-raises the same exception. Catch recorder failures
separately so ENOSPC or immutable-file conflicts cannot replace it. No ledger,
result, program, image, cleanup, authority or dispatch policy is changed.

Rejected alternatives: raw stderr/trace retention risks secrets and wider
disclosure; preserving failed stdout changes existing behavior; generic retries
lose failure attribution; inferring pre-execution from missing files is unsound.

Implement in research_carrier.py and the ticket's new focused test file. Test
actual stage failures, cleanup and unchanged exception/reservation behavior,
including hostile message/class names and recorder write failures. Existing
worker/research redaction tests remain controlling. Author static checks only;
Root owns actual canonical tests and GPU reproduction, independently of signer.

Reversible by removing stage contexts/recorder and their focused tests. Records
are diagnostic engineering evidence, not runtime or scientific acceptance.
No human-reserved value is selected. Supersede this file and the ticket if Root
changes scope; no Hub update or frozen decision-history edit is needed.
