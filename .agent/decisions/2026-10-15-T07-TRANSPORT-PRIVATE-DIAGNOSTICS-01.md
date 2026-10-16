# T07-TRANSPORT-PRIVATE-DIAGNOSTICS-01-D1

Problem: generic TRANSPORT_MALFORMED erased the first rejecting ingress branch.
Decision: KEEP protocol/response/authentication/limits and annotate existing
exceptions with a closed internal enum; WRAP existing private intake.log with
a bounded best-effort once-per-branch recorder. Header count saturates at 17;
budget is a boolean or null when not examined. No request content is emitted.

Authority: direct Ryan team coordination/fix ownership; Root's bounded source
assignment of 2026-10-15; NET-2 and intake's existing private logging contract.
Classification: IMPLEMENTATION_LAG in operational observability, no protocol
or scientific conflict. Original c41 body-shape reconstruction does not prove
original wire validity or a Cloudflare cause.

Rejected: relaxing header limits, stripping headers, raw request/exception logs,
new public fields, unbounded per-request logging and automatic resubmission.
Implementation: transport models/gateway/store and battery intake; focused
synthetic tests. Root retains runtime/tests/deployment/merge authority.
Reversible: remove private enum tags and recorder; wire/history needs no migration.
No human-reserved value is chosen. Dedicated security review is required;
source tests do not qualify security or prove the original failure cause.
Hub remains frozen under OWNER-WORKFLOW-SPEED-01. Root receives this decision
directly; changing the listed files and this decision prospectively supersedes it.
