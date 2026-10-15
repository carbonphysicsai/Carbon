# PLT19-REPLY-AUTHORITY-01

Ticket PLT-19; selected reversible engineering decision under delegated authority.
Problem: retained protocol receipt and later owned task view appear as peers,
with no payload authority declaration; silently adding keys breaks exact adapters.

KEEP the canonical nominal research protocol and original receipt. Add a separate
campaign-frozen reply rule carbon.autoresearch.research-reply.v2; no rule preserves
the historical six-field projection. New plans freeze the new rule. A compact
current_task projection states the governing view, state and revision and the
protocol task's retained/replayed revision. No state implies accounting settled.
Check same identity/challenge/created time/immutable bindings and nondecreasing
revision; reject same-revision disagreement and backwards observations. Only
already-disclosed task fields may enter the compact summary. Unknown rules fail
before dispatch. Adapter requires the selected schema and validates summary.

Alternatives rejected: rewrite the immutable start receipt (breaks evidence and
idempotency); silently alter every old reply (breaks public contract); put the
answer only in prose (does not fix ambiguity); infer settlement from terminal
state (loses existing reconciliation semantics); change nominal v2 service
(unnecessary authority/consumer churn). Nonterminal async observations stay valid.

Locations: development_session/research_reply.py and research_tools.py; standard.py;
two provider-plan writers, focused controls and migration doc. Revert the new
plan default prospectively if superseded, retain support for already frozen v2
wrappers; old plans/receipts need no migration. No reserved owner input needed.
Root receives the complete candidate/decision under existing authorized review
handoff; no intermediate approval or independent review quota. No disclosure,
execution, budget, qualification, deployment or settlement authority expands.


CI-discovered consumer controls: assert the prospective reply-rule field in
the three remaining agent-less plan tests rather than omit the new contract or
change historical expectations. Replace test-local dynamic module selection
with statically imported plan functions; do not add code-authority exceptions.
This repairs test/inventory integration only; selected reply schemas, original
receipt bytes and authority checks remain the candidate's original runtime.
