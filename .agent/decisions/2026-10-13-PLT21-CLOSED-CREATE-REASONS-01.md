# PLT21-D1: disclose closed cause evidence on ambiguous creation

The provider response is not a safe logging schema. Regex-redacting long token
shapes cannot remove a short account identifier or request echo reliably.
For ambiguous creates, accept only exact recognized code/reason/message values
at the top level or under the error object, and emit a Carbon-authored code.
Unknown, unavailable or contradictory reasons remain explicit; HTTP status
does not prove capacity, quota, non-creation or retry safety.

KEEP definitive refusals and pre-dispatch budget/headroom names unchanged.
KEEP ownership tags, execution uncertainty, reconciliation, pending reservation
and resend rules. Shared pod-job receipts already retain HTTP status on main;
repair Graphite's ambiguous launch wrapper so it also retains status or explicit
unavailability. Add no new provider or credential access.

The reason vocabulary is a bounded engineering classification, not a complete
RunPod error schema or security acceptance. Future exact provider codes may be
added deliberately with fixture controls; never replace unknown with a guess.
Hub is retired. Primary map reference WAVE-C/GRAPHITE-OPERATOR.

A real-receipt negative control failed because reconciliation erased the first
create diagnostic. Preserve each create's status and validated closed cause
through that wrapper. Even a definitive second failure must not release the
first ambiguous create's hold. No reconciliation timing or resend rule changes.
