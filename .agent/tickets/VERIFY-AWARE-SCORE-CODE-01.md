# VERIFY-AWARE-SCORE-CODE-01 — prospective verified-search score

**Owner assignment:** 2026-10-11. **Starting base:** `origin/main` at
`eda5e5f55c1c3fae315e295ea8ed94f91d6d0fce`; reconcile to exact main
before PR. **Research:** #1073,
VERIFY-AWARE-SCORE-01. **Primary map ref:** WAVE-C/VERIFY-AWARE-SCORE-CODE-01.
The Development Hub is retired under OWNER-WORKFLOW-SPEED-01.

## Working contract and decision

Add a DEVELOPMENT-only, pure prospective VERIFY-R leg under
`carbon.design_search`. A rule must register the action-list cap, complete-panel
attempt cap, wall/core caps, objective direction and unit, positive regret
normalisation in that unit, selector version, reference policy and P/Q/w
identities. Commit a unique ordered in-family list before reference access.
The independent verifier's cost/reference receipts supply overhead and complete
attempts; model predictions never supply a verdict. Charge every attempted
panel, including rejected or band-unresolved panels, and stop before one whose
independent planning bound cannot fit. Return the best verified feasible
design, with a full service loss when nothing can be returned. Missing or failed
reference evidence and missing model output withhold the numeric leg.
An already-incurred startup/search overrun is reported at its actual cost even
when it prevents every verification attempt; no overhead becomes free because
it exceeded the registered cap.

Register a candidate separately from registry v5, which remains unchanged.
The new `v` leg may be passed to the existing proof code as a prospective
score map; the product value target is a separate input. No v5 `q` alias,
historical rescore, owner gate choice, production k/budget/normalisation,
LIVE integration or hidden exporter is authorized.

**Engineering choice:** reuse the common `BudgetCap`/`BudgetLedger` and the
existing score-proof score-map interface; add a closed VERIFY-R input contract
and typed results. This is reversible and avoids changing the frozen v5 parser.
The alternative of adding `v` to v5 was rejected because it changes the
meaning of a frozen Q3 score. A later registry v6 adopter can bind this leg
after owner selection and confirmation. #1073 remains research evidence, not
an adopted rule.

## Acceptance

Toy fixtures cover digest binding, ordered-list uniqueness and family,
budget truncation, all attempt statuses and costs, best-of-verified, no-return
loss, missing-reference withholding, missing-output withholding, separate
P/Q/w identities, and score invariance to prediction changes that preserve the
committed list. Focused tests and canonical CI; no solver runs, spend,
hidden/AX42 data or LIVE changes. One PR to main; exact-head handoff to PR
Lead when green. Owner retains k, caps, normalisation, gates and adoption.
