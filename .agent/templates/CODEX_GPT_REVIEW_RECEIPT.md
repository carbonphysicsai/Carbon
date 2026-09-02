# Codex/GPT Review Receipt

Place the block below, with every placeholder resolved, in one GitHub
`APPROVED` pull-request review submitted by a human who is not the pull-request
author. The review must target the unchanged exact head. Additional prose may
appear before or after the block; the field order and values are closed.

```text
CARBON_CODEX_GPT_REVIEW_RECEIPT: 1
REVIEWED_HEAD: <lowercase 40-character commit SHA>
REVIEWED_TREE: <lowercase 40-character tree SHA>
REVIEW_MODEL: <model identity, 1-120 safe characters>
REVIEW_CONTEXT: FRESH_READ_ONLY
REVIEW_SCOPE: COMPLETE_PR_DIFF
FINDINGS_TOTAL: <canonical non-negative integer>
VALID_FINDINGS_REPAIRED: <canonical non-negative integer>
INVALID_FINDINGS_DISPOSITIONED: <canonical non-negative integer>
UNRESOLVED_FINDINGS: 0
OUTCOME: PASS
```

`FINDINGS_TOTAL` must equal `VALID_FINDINGS_REPAIRED` plus
`INVALID_FINDINGS_DISPOSITIONED`. A repair changes the Git tree and therefore
requires a new exact-head review and human approval. The receipt is engineering
review evidence only; it grants no scientific, security, operational,
commercial, production, deployment, or LIVE authority.
