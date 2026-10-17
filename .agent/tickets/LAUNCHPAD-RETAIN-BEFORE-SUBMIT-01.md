# Launch-bound retain before submit

Status: working contract; direct Root assignment, 2026-10-16.
Base: 5cb889da0ce8a4b7414e8bac1b2b2115b436d600.
Primary map_ref: WAVE-C/NET-2; Hub retired by OWNER-WORKFLOW-SPEED-01.

KEEP the normal Graphite FULL/BUILD research, practice, selection, artifact,
ledger and supervisor lifecycle. Add optional submission_policy=retain_only_v1
at launch. Omission preserves historical request/block bytes and edition digest.
Only this versioned literal is valid; explicit null, unknown or malformed values
are refused. The choice joins the request identity and frozen Graphite block;
resume cannot introduce, remove or replace it. No new mode, role or budget rule.

The restricted campaign may perform normal public practice and local research
authentication. A genuinely selected artifact stays retained and READY, with
final epochs unconsumed and no fabricated feedback or completion. Neither
normal automatic selection, manual/queued commit/submit, nor direct Battery
evaluation may read a commitment, request confirmation, sign/post a validator
submission, evaluate locally, or discover an intake under this policy. Skip
construction of the chain commitment gate too. Preserve all historical defaults.

Plan: contract/decision local commit; closed launch/schema plumbing; shared
frozen-policy validation and actual effect guards; retained/resume behavior;
regressions; pinned static checks; Root canonical execution/publication/merge.
Expected paths: this ticket and decision; graphite/miner edition.py and driver.py;
development_session research_campaign.py and new submission_policy.py;
battery/campaign.py and multi_intake.py; miner_mcp/mcp_operations.py;
miner_launchpad operations.py, supervisor.py, runner.py, projection.py and
research_view.js (both-door truthful retained status);
focused regression tests and narrowly required launch-contract test updates.
One author; Platform independently reviews read-only. Disjoint from EVAL396,
ScoreLab frozen scientific files, existing T07 and frozen f080 evidence.

Browser-door amendment, 2026-10-16: expose an optional Graphite retain choice
in the existing launch wizard for FULL/BUILD and send the exact versioned field
only when selected. Show the choice in review, preserve it in templates and
block when an older controller does not declare the field. The unchanged
default omits the field. RESEARCH has no selected candidate: hide the choice,
omit the policy and use research-only review text in that mode, while retaining
the checked wizard state if the miner returns to FULL or BUILD. Bound this
repair to `app.js` and the existing
`control_center_page_check.cjs` request-level scenario; Root owns canonical
execution and publication of the combined candidate.

DoD: authentic practiced selection remains retained even with its digest already
on chain; zero commitment/intake/validator effects; repeat resume makes no new
Constructor call; malformed/downgraded frozen records fail closed; historical
FULL still submits; manual and queued effects refuse before chain access.
Root canonical targets: ./scripts/dev/canonical.sh pytest -q
 tests/cpu/test_launchpad_retain_before_submit.py
 tests/cpu/test_graphite_miner_driver.py tests/cpu/test_launchpad_graphite.py
 tests/cpu/test_launchpad_commitment.py tests/cpu/test_battery_intake.py
then applicable changed-path acceptance. Author runs static tools only: no
application imports/tests, runtime/provider/model/host/spend, push or PR.

Maturity ceiling: implemented/tested restrictive engineering control only.
No scientific/security qualification, deployment authority, T07 admission or
verdict is earned by source. Root owns canonical tests, push, PR and merge.
Conditional closeout: required validation and normal merge of final candidate.

Boundary: this control governs the normal Launchpad/campaign execution graph,
including the directly callable campaign evaluation and commitment entrypoints.
The generic raw submit_through_intake transport is not a campaign admission API;
its normal campaign callers are guarded before discovery/signing. This ticket
does not claim arbitrary Python callers cannot use independent transport APIs.
The miner sandbox's separate process/import isolation remains unchanged.
