# CHALLENGE-REFERENCE-ROUTES-01 — cost-bounded reference-route proposals

**Selection:** owner's direct task, 2026-10-07. **State:** in_progress.
**Scope/maturity:** DEVELOPMENT / SPECIFIED only; one branch and one PR.
**Starting base:** `df26107c265dd9148be25ea5659ec2007785e0f2`.
**Branch:** `codex/challenge-reference-routes-01`; PR Lead owns delivery after handoff.

## Working contract

Propose cost-ranked routes for f02, f06, f08, f13 and f17 that retain the
mock buyer's existing problem. Specify decision-flip checks, Tier 2 witness
requirements, eight public measurement cases per family, unmeasured CPU/RSS
hypotheses, acquisition-package dependencies and an unapproved capped grant.
Cooling is excluded. This is not a solver implementation, reference adoption,
measurement execution or replenishment of the earlier feasibility grants.

Authority: CONSTITUTION, INVARIANTS, current DELIVERY_PROTOCOL (OWNER-DX-03),
DELEGATED_DECISION_PROTOCOL, OWNER-LAUNCH-PORTFOLIO-02,
OWNER-PORTFOLIO-DEV-ROUND-01, Eight_Challenge_Foundation_Plan §§3–7,
Business_Canon, the five round-one packets/requirements, #767 credibility
contract, merged #776 question laws and #784 foundation quiz. No archive reuse.
The historical WAVE selector is not permission to execute a future family.

KEEP packet limits, P/Q/w, no-redraw/exposure semantics and historical reference
identities. WRAP the existing credibility and cost-panel patterns. No changes
to runtime tasks, optimizers, registries, validator/data lifecycle, scoring,
weights, protocol stages, queues or other lanes' solver packages. Exact task
package pins are acquisition-owner dependencies, not fabricated installed builds.

Primary placement: `docs/development/challenge_pipeline/round1/`.
Hub impact: none; the current delivery protocol retires Hub maintenance.
Former map context is challenge-pipeline foundation; no Hub source/generated edits.

## Plan and acceptance

1. Audit current main, open ownership, packets, credibility and package status;
   run the bounded static baseline before edits and notify #643/#42.
2. Record the route decision and write one proposal document plus panel sheet.
3. Test the specification's scope, unapproved permissions/pins, panel counts,
   grant arithmetic, solve-versus-launch accounting and preserved buyer anchors.
4. Run focused static regressions and quality/diff checks; record lessons.
5. Submit one ready PR with exact-head evidence and the handoff declaration.

Expected manifest: this ticket; one decision; `round1/reference-routes.md`;
`round1/reference-route-panels.json`; one static CPU test; four execution lessons
under `carbon/challenge_pipeline/lessons/`. Regenerate/check the existing
`docs/development/CHALLENGE_PIPELINE.md` view; RECORDED lessons leave it unchanged.
Pipeline lesson rendering is separate from the retired Development Hub.
Canonical command: `./scripts/dev/canonical.sh python -m pytest -q
tests/cpu/test_reference_route_proposals.py tests/cpu/test_foundation_quiz_content.py
tests/cpu/test_customer_reference_credibility.py tests/cpu/test_customer_feasibility_panels.py`.
Native host output is diagnostic only; scope-required pinned CI remains required.

## Candidate validation and integration

- Baseline: 50 static packet/credibility/quiz tests passed in 10.73s.
- Proposal plus those regressions: 64 passed in 2.81s.
- Final proposal/pipeline integration: 42 passed in 19.40s with
  `py -3.11 -X utf8 -m pytest -q tests/cpu/test_reference_route_proposals.py
  tests/cpu/test_challenge_pipeline.py`. The initial same invocation without
  UTF-8 failed one existing roadmap decode under cp1252 (41 passed); that failed
  run remains recorded, not canonical acceptance.
- New test lint: `py -3.11 -m ruff check tests/cpu/test_reference_route_proposals.py`
  passed. Host formatting is mechanical, not the pinned CI quality receipt.
- All results above are native Windows/Anaconda Python 3.11.4 diagnostics. The
  local canonical host is unavailable (known missing shell utilities); use the
  applicable pinned GitHub acceptance once on the ready candidate. No solver or
  model was run and no empirical route adequacy/cost was earned.
- Current main advanced to `ae6ee7ca2779a5e775fca886a1ac53b78105280c` during work
  (#778/#747). Its changed paths are Launchpad/training-budget work, not these
  packets, lesson schema, delivery authority or proposals. No unrelated base
  refresh, handed-off branch edit or Battery study/grant change.

## Boundaries and conditional completion

All measured costs and earned credibility remain UNMEASURED/NOT_DEMONSTRATED.
Reduction acceptance, disagreement/regret limits, exact packages and execution
grant stay HUMAN_INPUT with recommendations. No solver/model runs, installation,
provider dispatch, paid spend, hidden witnesses or counted/fresh campaigns.
Battery EV5, journal sequence 14 and live contract remain untouched; 45/30/25
is not adopted. Reference errors never become candidate penalties; future
revisions do not silently rescore sealed results.

Prepared specification is delivered only after applicable exact-head acceptance
and normal merge under the current protocol; PR Lead owns those final actions.
Engineering delivery confers neither reference adequacy nor an execution grant.
