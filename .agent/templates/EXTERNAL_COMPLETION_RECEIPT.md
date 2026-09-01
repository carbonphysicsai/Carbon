# External completion receipt

Copy this template into the pull-request body, one normalized pull-request
completion comment, the applicable issue comment, or a retained GitHub Actions
artifact. Do not commit a filled copy merely to store dynamic identities.

```text
TICKET:
DELIVERY_MODE: SINGLE_TICKET_PR | SEPARATE_CONTRACT_PR
SEPARATE_CONTRACT_PR_REASON: NOT_APPLICABLE

STARTING_BASE:
STARTING_BASE_TREE:
FINAL_REVIEWED_HEAD:
FINAL_REVIEWED_TREE:

CHANGE_SCOPE:
CI_RUN:
REQUIRED_CHECKS_AND_JOBS:
MERGE_GATE_HEAD_CHECK:
GREPTILE_CHECK:
GREPTILE_SUMMARY:
GREPTILE_FINDINGS_DISPOSITION:
UNRESOLVED_GREPTILE_THREADS: 0
BLOCKING_DIRECTION: NONE | <resolved direction and evidence>

MERGE_METHOD: NORMAL_MERGE_COMMIT
EXPECTED_HEAD_GUARD:
MERGE_COMMIT:
ORDERED_PARENTS:
MERGE_TREE:
REVIEWED_TREE_PRESERVED: YES | NO
REVIEWED_HEAD_ANCESTRAL_TO_MAIN: YES | NO
ORIGIN_MAIN:

EXACT_MAIN_RUN:
EXACT_MAIN_REQUIRED_CHECKS:
EXACT_MAIN_MERGE_GATE:

RULESET_ARTIFACT: .github/rulesets/main.v1.json
RULESET_LIVE_STATE: APPLIED_AND_VERIFIED | UNAPPLIED
RULESET_MANUAL_OWNER_ACTION: NONE | <smallest exact action>

LEAD_NOTIFICATION: NOT_REQUIRED | <issue/comment identity>
OWNER_DEFERRAL: NONE | <issue #41 identity>
COMPLETION_RECEIPT_LOCATION:

FINAL_MATURITY:
REMAINING_HUMAN_RESERVED_AUTHORITY:
NEXT_SELECTED_TICKET:
NEXT_TICKET_STARTING_MAIN:
NEXT_TICKET_STARTING_TREE:
```

For `SEPARATE_CONTRACT_PR`, replace `NOT_APPLICABLE` with exactly
`CONTRACT_ONLY_TICKET`, `CONCURRENT_DOWNSTREAM_IMMUTABLE_CONTRACT`,
`CROSS_DOMAIN_PUBLIC_INTERFACE_FREEZE`, or
`AUTHORITATIVE_SEQUENCING | AUTHORITY: <normalized repo-relative current sequencing authority path> | DETAILS: <specific reason of at least four words equal to a complete SEPARATE_CONTRACT_PR_EXCEPTION marker value in that file at candidate HEAD>`.
Ticket size is categorically invalid.

Every SHA, tree, run, check, job, comment, and thread-count field must be read
from the live system after it exists. Use `PENDING` before completion and never
replace unavailable evidence with an inference.
