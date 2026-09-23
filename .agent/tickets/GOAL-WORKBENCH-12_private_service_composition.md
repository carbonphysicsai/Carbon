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

W-C deployment acceptance is out of scope. This ticket delivers W-A and the
engineering half of W-B.

**The blocker is not external.** An earlier revision of this line said W-C
"remains blocked on external authority", which records that a blocker exists
and gives nobody anything to act on. Named precisely, so it can be decided
rather than cited:

| What is needed | Whose it is | What changes the day it is granted |
|---|---|---|
| Money for counsel and for a security review of the deployed surface | **Ryan** | Unblocks every legal item below; nothing legal can start until this is answered |
| Storage location and jurisdiction | **Nick**, plus a jurisdiction and entity only **Ryan** can supply | §3.2 proceeds; records that matter may be written |
| Retention period, legal basis, approver (OD-25) | **Ryan and Nick with counsel** | `legal_basis` stops being `null`; deletion stops being exception-only by default |
| Notice and consent text | **Ryan and Nick with counsel** | Client-facing collection becomes possible at all |
| Sender credential and authorised sender identity | **Ryan** | Notifications may be attempted; today every attempt reports that none is configured |
| Named staff accounts and credential issuance | **Ryan** | Real identities replace the synthetic stage-1 directory |
| Incident ownership and rollback authority | **Ryan** — decided, see `CARBON-D-INCIDENT` | already granted; the operator to page is named |
| Rate limiting, lockout and escalation | engineering, gated on the security review above | The abuse controls the runbook records as absent get built |

Every row is Ryan's or Nick's. Nothing here is external to Carbon, and nothing
is waiting on a third party.

One row is already decided and was decided before this table was written:
**incident ownership is Ryan's**, recorded as `CARBON-D-INCIDENT`. The first
revision of this table assigned it to Nick, following the W-C setup decisions
document, which routed it as "conditional on Nick". That document predated the
decision and the table repeated it, so a settled question was published as an
open one against the owner's own answer. It is corrected here rather than left
to be read twice.

**What is already prepared against them.** Stage 1 runs today on loopback with
one receiver process per store file, a store ceiling that cannot write a file it
cannot read, authenticated staff identity with cross-team denial, versioned
retention with an approved-exception deletion model, and a transactional outbox
that reports what it did not do. The runbook records the start, check, stop and
recover sequence as actually run. The engineering is not what is waiting.

**What §3.1 being resolved does not mean.** A working internal host with
synthetic fixtures is one precondition of nine. The eight that remain are the
ones with a client on the other end, and a host is not a deployment, a security
qualification, or authorisation for client-facing collection.

## Successor repairs (GOAL-WORKBENCH-13)

Review of the merged implementation found three defects. Each was reproduced
from the current source before any change, and each repair keeps a regression
that fails against the merged code.

**F1 — the browser could not authenticate.** Adding a bearer requirement to the
scientific routes without giving the browser study adapter a credential left the
real browser connection returning 401 on every route. The API-level tests set the
header themselves, so the suite passed with the browser path broken. A staff
member now enters their own operator-issued token in the study panel; the adapter
sends it on every scientific route and refuses to call without one. The token is
held in memory for that browser tab only and is never embedded in the build,
stored, placed in a URL, or written into an export or saved study. The loopback
fixture host now authenticates through the same `StaffPrincipals` record instead
of trusting any loopback client, so a fixture run can no longer pass while the
real credential path is broken.

**F2 — a completing notification could erase concurrent writes.** Outbox
completion persisted a store snapshot captured before its await, so an assessment
filed, an attempt recorded or an inquiry deleted during the delivery window was
overwritten, and a deleted record could be resurrected. Completion now merges
into current state and refuses to revive an event removed while its delivery was
in flight.

**F3 — one failed write blocked the store permanently.** A write or flush failure
left the fixed PID-named temporary file behind, and every later write failed
`EEXIST` against the exclusive create. The temporary name is now unique per
attempt and is removed on every failure path.

Acceptance scopes are reported separately: `workbench_science_checks.sh` is not
the read-only release-freshness gate and neither is a product-browser journey.
The browser suites were not executed in this session; the development host has no
usable Chromium.

## Handoff §10 acceptance, re-audited 2026-09-23

The Workbench completion handoff's §10 lists fourteen required cases. The table
marking each one was only ever written in a session transcript. It was re-marked
there on 2026-09-21, and that update was then lost when the conversation was
compacted, so later reports kept saying "four partials" after two had closed.
The four rows below are recorded here so that cannot happen again. All four now close. The other ten
were marked covered on 2026-09-21 and are not re-audited here.

| Case | Status | Evidence |
|---|---|---|
| 7. Real composition reaches `WorkbenchScience` and the registered task; single-case, two-case, partial completion, expiry and cancellation | **Covered** | `tests/service/test_julia_workbench.py` (single case through the HTTP routes, saved replay, stale draft, cancellation after grant expiry) and `tests/service/test_julia_envelope_worker.py` (two cases, partial completion, held capacity after expiry, cancellation of a running envelope), on a real Julia worker in the isolated service job. Re-run on 2026-09-23 against a worker rebuilt from the current tree: 6 of 6. |
| 8. Stop, reconnect and controller restart observe task-owned cleanup and conservative charges, with no new grant or duplicate numerical work | **Covered** | `tests/service/test_mcp_tasks_native_julia.py`: three server processes, each one a controller restart, replay with no duplicate trial, a double cancel, cleanup on stdio EOF, nothing left `RESERVED`. `tests/service/test_workbench_host_process.py` does the same for the Workbench launcher: `SIGTERM` reconciles to `INTERRUPTED`, and a restart or `SIGKILL` recovery replays the study with unchanged usage. |
| 11. One desktop and narrow-mobile team journey saves and reopens the same inquiry, study and assessment | **Covered** | `tests/service/workbench_team_journey.py` drives `Business/Carbon_Fit/workbench/tests/browser_team_journey_launcher.cjs` through one browser session against `workbench_host serve` and the stage-1 receiver. The client downloads a package from the preview the launcher serves, and an operator relays it into the receiver, which stores the same bytes. The team imports what the receiver stored, records an assessment on that job, and runs a real-worker study on its design after `register-draft`. The page then saves, is reloaded, reopens the saved bytes, and finds the inquiry's words, the assessment and the study, which the service rereads. 14 of 14 checks at 1440 px and at 390 px on 2026-09-23, with nothing off-origin and no page errors. Operator-run, like the other Workbench browser journeys: CI installs no browser. |
| 12. Fresh checkout, bootstrap, build, startup, shutdown and recovery work on supported Linux | **Covered** | `tests/service/test_workbench_host_process.py` runs the private build, `check`, `register-draft` and `serve` as the operator runs them, as separate processes, then stops with `SIGTERM`, restarts, crashes with `SIGKILL` and restarts again. The campaign is test-owned and synthetic under handoff §G. Only the external hotkey and testnet runtime is substituted. |

**The stated precondition was the wrong one.** Cases 7, 8 and 12 were held on
"an admitted campaign with its grant". Handoff §G permits a test-owned synthetic
grant in a temporary root, so that was never required. #282 did not remove the
grant from this path either: `load_profile` still requires it. What actually
kept case 12 open was that no test ran the launcher as a process. The first run
that did found two defects, each of which made the supported host unusable. Both
are fixed on the branch that records this:

- **`serve` never reconciled on the documented stop.** uvicorn raises SIGTERM
  again once it has shut down, and the default action ended the process inside
  the campaign attachment, before worker cleanup, controller settlement and
  task-store close. It now exits `0` with the campaign `INTERRUPTED`. The
  process test fails with `-15` against the old code.
- **`register-draft` wrote a registry that `serve` could never read.** The
  operator commands keyed the registry on the profile's `principal`, the operator
  named in the grant, while `serve` keys it on the authenticated campaign owner.
  With any real profile, every study was refused as `DRAFT_BINDING_DENIED`. The
  in-process tests hid this by setting the two identities equal. They now differ
  as they do in a real profile, and the operator test fails against the old code.
