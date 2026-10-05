## 2026-10-05 — OPERATOR-USABILITY-01: say when a campaign settled, how to stop it, when to re-run reconcile, and refuse phase-4 errors by name

**Authority.** An owner request via the Graphite Test executor, 2026-10-05:
the Launchpad and Graphite should be "user application level friendly for
humans and agents". The executor's findings (B2, B3, B8, B10, C1) were
assigned to this PR by the Test Engineer. Engineering decisions within that
request, recorded by the executor of this PR. No scientific value,
threshold, gate, tolerance or economic parameter changes. Nothing here
grants authority, changes a score or reaches the chain.

**Found.** Graphite live runs at `f7c27d97` and `6f289599` (lessons entry
`2026-10-05-operator-usability`).

### D1. The owner report says how and when the campaign settled (B2)

**Observed.** `completed_unix` in `agent-report.json` is written only from
`campaign-complete.json`, the end of a finite campaign. A campaign that
settled READY (waiting for its miner), PAUSED or STOPPED never writes it, and
the run writes its report as it closes, before the dispatch settles. An
operator waited 25 minutes for a field that could not appear while the agent
was already READY. `carbon_observe`'s `state` already was the controller's
observed state (`projection.project`).

**Decision.**

1. `CampaignControl.settled` records the generation, the settled state and
   the ledger clock in a new one-row ledger table, `launchpad_settlement`
   (created if absent; a ledger settled before 2026-10-05 has no row).
2. The owner report (`research_report.render_status`, schema
   `carbon.autoresearch.owner-status.v1`) gains one additive field,
   `control`: `{state, desired, generation, settled, settled_unix}`, read
   without changing the ledger (`research_control.read_settlement`).
   `settled` is true for READY, PAUSED, STOPPED, COMPLETED, INTERRUPTED and
   RECONCILIATION_REQUIRED. `settled_unix` is the recorded time only when it
   belongs to the current generation and state, otherwise None. `None` for a
   ledger no controller ran. The HTML report shows one Controller line.
3. `completed_unix` keeps its meaning: a finite campaign's end. A campaign
   waiting for its miner is settled, not complete.
4. Settling rewrites the report once the transaction commits, for a frozen
   campaign only. The report is a derived view: a failure to write it (its
   storage bound, say) leaves the settlement in the ledger for the next one.

### D2. Stop and pause over MCP are `carbon_halt`, the page's own operation (B3)

**Observed.** `carbon_halt` (`action` stop, pause or reconcile) and
`carbon_resume` already exist at the MCP door, generated from the shared
operations table. The Control Center's Stop, Pause and Reconcile call the
same `perform("halt", ...)` (`RunnerAdapter.control`), through the same
gates: request, profile (`owner()`, no registration needed to withdraw) and
campaign (`owned_campaign`, the principal's own campaign only). Stop is
idempotent (`CampaignControl.request` returns for a STOPPED or COMPLETED
campaign), cancels outstanding operations and deletes nothing. The finding
came from the tool's name: an agent looking for "stop" did not find it.

**Decision.**

1. No `carbon_stop` or `carbon_pause` alias. Two names for one operation
   would be a second door onto the same authority, outside the table both
   doors are generated from (`mcp_operations`: "This module defines no
   operation and no gate"). No tool is added, so the tool list needs no new
   version.
2. The halt operation's summary, which both doors publish, now leads with
   "Stop or pause your campaign (action=stop or action=pause)", says the
   Control Center's buttons run the same operation, and that stop is final
   and idempotent and nothing is deleted. `carbon/miner_mcp/README.md` says
   the same.

### D3. A reconcile that cannot settle yet says when it can (B8)

**Observed.** After an ambiguous pod create, `ComputeService.recover` keeps
the intent uncertain until `not_found_grace_s` (600 s) has passed since the
intent was made. Until then `phase3 reconcile` exits 4 with `terminated:
null` and no hint.

**Decision.**

1. `RunPodPods.recover_settles(intent_id)` (optional on the pods protocol;
   reads only) returns the intent's age, the grace and the time it settles.
   `Experiment.reconcile` adds them to each `terminated: null` row; a backend
   without it adds nothing, and a failure to read it never fails a
   reconcile.
2. `phase3 reconcile` keeps its stdout report and its exit codes (0 settled,
   4 not). On exit 4 it prints one typed line to stderr:
   `{"status": "REFUSED", "reason_code": "reconcile_pods_not_settled",
   "unsettled": [...], "rerun_at_utc": ...}`. Each uncertain intent carries
   `intent_age_s`, `not_found_grace_s`, `rerun_at_utc` and
   `next_step: "settles after 600 s; re-run at or after HH:MM UTC"`, the
   settle time rounded up to the whole minute. An unverified termination
   says to re-run now.

### D4. Phase 4's typed errors end as phase 3's typed refusals (B10)

**Decision.** `phase4.main` only - the command functions are unchanged
(open PRs edit them). A command that ends in `ControllerError`,
`KnowledgeError` (the engine's, or one a test injects through
`attack_modules`), `BudgetRefused`, `ScoringUnavailable` or `GrantError`
prints `{"status": "REFUSED", "reason_code": <code>}` and exits 2, as
`RunnerRefused` does. The code is the error's closed code, never its text: a
knowledge refusal is `attack_knowledge_<code>` as `replay_guard` names it, a
grant refusal is `grant_refused`. Any other exception - a pod or provider
failure, a bug - keeps its traceback: it is not a refusal.

### D5. A short-lived MCP launch left QUEUED: root cause not established (C1)

**Observed.** The design already makes a launch independent of its client
(LP-PROD-C): an MCP door is a CLIENT that records the launch, queues it and
starts a detached supervisor in its own session; a supervisor that takes the
lock re-queues a launch left QUEUED with nothing queued
(`_redispatch_stranded`); a client start and every `carbon_observe` of a
QUEUED item with no supervisor start one. Ruled out here: (a) a child in its
own session dying with its `wsl.exe` client - probed on this host, it
survives both a normal exit and a forced kill of `wsl.exe`; (b) the MCP
SDK's stdio teardown (`killpg` of the server's process group, which the
supervisor is not in); (c) an INLINE host on any MCP path (every door
constructs a CLIENT). Still possible, and not distinguishable without the
session-1 records: the client killing the server between recording the
launch and starting the supervisor, or a detached supervisor exiting at
start (it exits 2 silently on an unusable profile).

**Decision.** No change to launch or supervision without the evidence. The
launch tool's door note now says the supervisor, not the session, carries
the campaign out, and what to do when `in_flight` stays QUEUED with
`supervisor_running` false: observe again (which starts a supervisor), then
open the Control Center. The smallest evidence to settle it: for the
stranded campaign, its `launchpad_dispatch` rows, `last_refusal`,
`interruptions.jsonl`, and whether a `scripts.dev.miner_launchpad.supervisor`
process started after the launch.

### Public interfaces

- `agent-report.json` / `research-report.json`: additive `control` field;
  schema id unchanged (additive, nothing reads a closed key set).
- Campaign ledger: new table `launchpad_settlement`, prospective.
- `carbon_halt` and `carbon_launch` descriptions (text only; no tool added,
  removed or renamed; schemas unchanged).
- `phase3 reconcile`: added row fields and one stderr line on exit 4.
- `phase4`: the listed errors exit 2 with a typed refusal instead of a
  traceback.
