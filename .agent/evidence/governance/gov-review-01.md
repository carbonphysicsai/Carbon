# GOV-REVIEW-01 stable evidence — manual Codex/GPT review governance

**Evidence class:** stable tracked governance evidence
**Exact base commit:** `938f94d3cf0ae8ff092b52659c39f0952ec352da`
**Exact base tree:** `ca050935b1b4881931d438e47a7a69a98bd5fcfa`
**Branch:** `agent/gov-review-01-gpt-review`
**Primary Hub map_ref:** `SYSTEM/DEVELOPMENT-SEQUENCING`

## Stable findings

- The required Greptile service became unavailable because the repository was
  bound to a workspace no longer controlled by the active executor.
- The human-selected replacement is manual Codex/GPT review plus distinct human
  approval, not an automated OpenAI API integration.
- Live ruleset `22029359` was changed before repository authority: it retained
  strict `Merge gate`, normal merge only, thread resolution, deletion and non-
  fast-forward protection, and no bypass actors, but had zero required human
  approvals and no GPT review check. This is `MIGRATION_REQUIRED`.
- Historical Greptile checks remain evidence for already delivered trees. They
  are not active or prospective dependencies after this migration.

## Stable acceptance contract

The exact review receipt schema is `.agent/templates/CODEX_GPT_REVIEW_RECEIPT.md`.
The protected validator requires an open non-draft PR to main, the live head and
tree, an `APPROVED` review by a non-author, fresh read-only complete-diff scope,
canonical non-negative finding counts, complete dispositions, zero unresolved
findings, and `PASS`. The ruleset separately dismisses approvals on push,
requires last-push approval and resolved review threads, and retains no bypass.

## Dynamic evidence boundary

Final candidate head/tree, CI jobs, GPT review check/review identity, reviewer,
finding dispositions, merge topology, exact-main checks, live ruleset update,
notification, and completion receipt remain external dynamic evidence. Do not
create a commit solely to record those future facts.

## Maturity ceiling

```text
DELIVERY_GOVERNANCE_SPECIFIED: YES after merge
GPT_REVIEW_GATE_IMPLEMENTED: YES after merge and live ruleset convergence
B-04_IMPLEMENTED_BY_THIS_TICKET: NO
SCIENTIFICALLY_QUALIFIED: NO
SECURITY_QUALIFIED: NO
NETWORK_QUALIFIED: NO
PRODUCTION_QUALIFIED: NO
LIVE: NO
```
