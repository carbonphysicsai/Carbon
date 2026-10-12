## 2026-10-12 — MMS-ACCEPTANCE-LINKS-01: preserve verdicts and bind later owner acceptance

PLT-07, Platform3; reviewer: Carbon Validator. Classification: DOCUMENTATION_LAG.
Authority: the owner queue assignment and merged OWNER-CODE-VERIFICATION-ACCEPT-01.
Starting base: 3025f3cef (main). One PR to main; PR Head owns review and merge.

KEEP all measured MMS records, historical criteria and the owner decision unchanged.
WRAP them with three declarative acceptance links, binding exact image and criteria
identities, the decision bytes and measured evidence bytes. Elmer's accepted time
condition is t_end = 0.375; its earlier t_end = 0.5 observation stays adverse evidence.
No threshold, solver run, acceptance or reference adequacy is invented here.

The offline trust-map reader and committed-source deliverable generator share the
same acceptance validator. Missing links, changed criteria/images/decision/evidence
or unmet conditions fail closed. Trust-map v2 prospectively carries criteria and
acceptance provenance; v1 remains historical evidence and cannot grant acceptance.
Public/released projections remain operator assertions, not independently attested
reference results. Acceptance covers code verification only, never qualification.

Alternatives rejected: rewriting HUMAN_INPUT verdicts loses history; searching owner
prose for an image does not bind criteria or conditions; a caller PASS flag is not
owner authority. Reversible by removing links/readers; supersede this record and the
link files for future changes, rather than modifying original evidence.

Validation: focused trust-map, deliverable and acceptance tests; MMS regressions;
invariant suite; pinned Black/Ruff; applicable CI and Merge gate on the PR head.
Canonical wrapper currently refuses this Windows-managed worktree; local results
are diagnostics only. Queue DONE means delivered PR, not merged/qualified work.
Primary map_ref: WAVE-B/B-04. Reference-acceptance detail remains within the mapped
reference evidence boundary. Hub history remains accurate and frozen under current
OWNER-WORKFLOW-SPEED-01; no structural status, dependency or maturity change.
No reserved owner decision remains for this bounded linkage repair.
