# GOAL-WORKBENCH-12: startable private Workbench service and deployment-ready receiver

Programme: #139 (private receiver, access, retention and deployment acceptance)
and #209 (core platform integration). Owner authority: the owner-forwarded
Workbench completion handoff of 2026-09-20, Workstream 2 of 2. Status:
bounded engineering delivery. No scientific qualification, security acceptance,
deployment authority or live customer collection is claimed or authorized.

Primary Development Hub map_ref: `SYSTEM/BUSINESS-AUTHORITY`; impact
`map_structural`. Affects `SYSTEM/AGENT-EXECUTION` through the shared research
campaign attachment.

## Problem

The Workbench's connected workflow existed but could not be started as a
product. The only composition of `ResearchToolAdapter`, `WorkbenchScience`,
`create_workbench_app` and the private build was
`tests/service/workbench_native_host.py` — a pytest fixture that monkeypatches
the message signer, resolves drafts from an in-memory dictionary and treats any
loopback client as the campaign principal. An operator following
`SCIENTIFIC_STUDIES_OPERATOR.md` had to assemble those objects by hand, and
there was no supported start, check, stop or recovery sequence.

The private team receiver claimed durability and provenance it did not have. It
acknowledged a receipt from an unflushed write, and `update()` replaced the
team assessment in place, so a correction erased what an engineer previously
recorded. Its transactional outbox had no reachable surface at all, and the
receiver had no HTTP-level test of its own role checks or idempotency.

## Working contract

KEEP the accepted application, physical-definition checks, public-source Julia
studies, source-bound evidence, team assessment, private persistence and
handoff machinery. KEEP the fixed
`/api/scientific-studies/{capabilities,start,status,cancel,result}` contract and
every `WorkbenchScience` check. WRAP the existing admitted-campaign attachment
rather than writing a second one. REPAIR the receiver defects above. REPLACE
nothing.

No second scheduler, evaluator, solver, ledger, accounting authority, identity
provider, database platform, cloud vendor or JavaScript framework is added.

### Definition of Done

1. One supported launcher composes the existing objects and serves the reviewed
   private build. It verifies required local configuration without opening
   secrets in diagnostics; opens the existing private stores and task/controller
   state; resolves authenticated principals and draft ownership; mounts the
   fixed scientific routes before the static build; preserves controller and
   task ownership across browser disconnects; exposes health/readiness,
   shutdown and recovery behaviour without initializing unavailable accelerators
   merely for discovery; and prints exactly which capabilities are enabled,
   configured but unavailable, fixture-only or unsupported.
2. Campaign ownership, generation, reconciliation and cleanup have exactly one
   implementation, shared with the existing research MCP command.
3. A registered draft is a durable operator installation bound to the exact
   granted public physical definition. A browser cannot register, choose a
   principal or grant rights. A newer revision leaves earlier revisions stale
   but still cancellable, and a revocation takes effect without a restart.
4. The receiver's durable save reaches the disk before its acknowledgement; a
   storage failure returns no receipt; team assessment is append-only with a
   versioned migration that invents no history it never retained.
5. The outbox is observable and retryable, carries only the permitted minimal
   summary and an authenticated record path, and never reports an undelivered
   notification as a delivery.
6. Acceptance runs through the real composed routes, the real registry and the
   real `WorkbenchScience` checks — not around them.
7. A documented start/check/stop/recover sequence exists for a fresh supported
   Linux checkout, with the remaining live-activation items stated explicitly.

## Boundaries

The launcher creates no campaign, grant, allowance, listener authority or
scientific result. Named staff tokens record who opened a session; the
scientific routes still act as the single admitted campaign principal, and a
token grants no scientific, rights or economic authority to a person.

A configured notification destination records where a notification would go. It
is not a mailbox credential, a sender, or permission to contact anyone. The
receiver opens no outbound connection.

GPU and authored research stay `UNSUPPORTED` for the Workbench: no Workbench
solver is invented, no backend is substituted for another, and no customer task
is relabelled to reach a service it has no rights to.

W-C deployment acceptance is out of scope and remains blocked on external
authority. This ticket delivers W-A and the engineering half of W-B.
