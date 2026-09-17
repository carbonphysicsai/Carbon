# Carbon miner launchpad: implementation handoff

Date: 2026-09-17.
Starting main: `49449ce8406e5d02aad0d7eb6d8c42f6ad11b10f`.
Branch: `agent/miner-launchpad-dev-foundation`.
Ticket: `.agent/tickets/C-MLP-01_development_launchpad.md`.

Continuation: C-MLP-01 merged in PR #205 after successful canonical acceptance
and Merge gate (run 35218321344). Actual browser/server checks and canonical
Python 3.11 Launchpad regressions passed. C-MLP-02 is in progress; its partial
verified-source bridge and remaining real-campaign dependency are described in
`MINER_LAUNCHPAD_RESEARCH_BRIDGE.md`. Older pending-acceptance notes below record
the original handoff, not the current delivery status.

## Product target

Let a visitor choose a challenge, connect or launch an agent, choose a reasoning
provider and experiment compute, approve a budget, then conduct a real research
campaign. Returning users should be able to launch or resume from saved settings.
Practice should not require purchasing a new miner registration. Reuse an existing
miner identity where appropriate; a new worker is not automatically a new miner.

The owner authorized building and iterating before Carbon launches. Complete
ordinary engineering without repeated approval ceremonies. This does not grant
new spending, public exposure, protected access, production eligibility or chain
transaction authority. Existing bounded grants remain scoped to their own tasks.

## Current executable slice

The draft contains a zero-network controller rehearsal, not the completed mining
product. Only `controller-rehearsal-v1 / fixture / none / local` is accepted.
Specifying Hermes, Lium or another unsupported profile fails closed. Rehearsal
steps are counters, not physics experiments. Scientific results and submission
receipts remain null. External spend is zero because no provider is called, not
because this version implements a monetary spending limiter.

From the repository root on Linux, macOS or Windows:

```sh
python scripts/dev/miner_launchpad/controller.py
```

Use the loopback address printed by the command and paste its generated local
session token into the page. Keep the server running. Closing a browser tab does
not stop the controller; stopping the server interrupts its in-process fixture
work. The next server startup retains the database and marks queued/running work
INTERRUPTED. Resume is explicit and cannot extend the original deadline.

The default state directory is `~/.carbon/development-launchpad`. The OS lock
prevents a second controller from owning that directory. At most four active runs
and 1,000 retained runs are admitted; the UI lists the 50 most recent. Credentials
are not accepted as request fields. No shell command or external endpoint can be
supplied through the API.

On Windows use a private, user-owned state directory: POSIX mode bits do not
establish a Windows ACL. OS file locking prevents concurrent controller ownership
on each supported host and releases ownership when the process exits.
An unconfirmed browser launch retains only its request key and closed rehearsal
specification in tab session storage across reloads. Credentials remain in memory.
If retry storage is unavailable, launch fails closed before dispatch. Closing the
tab loses that pending request; reconnect and inspect retained runs before starting
another. Server history persists independently of browser storage.

Do not upload these files to the public marketing site and expect a working hosted
service. Do not expose this Python HTTP server through a public tunnel. The mobile
layout is preparatory; real phone access needs a separately reviewed authenticated
host or proxy. This build binds only to 127.0.0.1.

Native diagnostics:

```sh
python -m pytest tests/cpu/test_miner_launchpad.py -q
node --check scripts/dev/miner_launchpad/app.js
python scripts/dev/miner_launchpad/browser_smoke.py
```

The recorded 56 passing tests ran on Python 3.13.5 outside Carbon's pinned
environment. Repeat acceptance in canonical Python 3.11. The continuation repaired
reload-safe retries, stale connection controls, fresh export, bounded HTTP admission
and Windows ownership locking. Its 63 Python 3.12 Windows diagnostics passed.
Actual local Chromium/server smoke passed launch, lost-response/reload retry,
pause/resume/stop, export, storage failure, reopened SQLite/server recovery,
expiry and 1440/390px layouts. This replaces the prior browser environment blocker;
it does not replace canonical Python acceptance. Local Docker/WSL was unavailable.

## Continue in the Carbon Codex environment

1. Inspect the worktree, current main, this branch and current PRs. Preserve other
   agents' work. Follow AGENTS.md and its mandatory authority reads, including
   DELIVERY_PROTOCOL and the Hub maintenance contract. The main WAVE selector may
   lag merged PRs; reconcile exact evidence without erasing concurrent work.
2. Finish C-MLP-01 acceptance and repair work. No special human review ceremony is
   required. Keep current canonical tests and the required Merge gate intact.
3. Continue into C-MLP-02 with a separate coherent ticket/PR. Reuse the real research
   campaign being developed after PR #202 rather than cloning it into this tool.
4. Keep future integrations unavailable until their contract tests and real bounded
   smoke have passed. Do not let a provider selection silently run the fixture.
5. Stop only the affected paid/deployment/chain behavior when its authority is
   absent. Continue implementing and testing everything that does not need it.

## C-MLP-02: first real research path

Wrap Carbon's current public/synthetic DEVELOPMENT campaign runner with a durable
launcher job. Discover the actual callable and contracts on current main; do not
invent an endpoint from an architecture document. Keep launcher states separate
from Carbon's authoritative submission and scientific result types.

A real run must load the public challenge and legal strategy catalog, generate
allowed training/practice material, propose and run multiple experiments, preserve
unsuccessful trials, freeze a selected strategy, reconstruct through the independent
DEVELOPMENT path, and return that path's actual receipt and disposition. Display
UNRESOLVED, infrastructure failure, trade-off and regression without manufacturing
a winner. Preserve the fixed registered grader during each comparison.

Use the existing owner report/experiment records for detailed research reporting.
The launchpad displays run controls, status and links to those records. It must not
expose protected realizations, reference outputs or private validator data.

The first agent may use the already-supported local/provider path while the
Hermes adapter is built. Avoid making three new vendors a prerequisite to a real
end-to-end Carbon test. No new paid campaign may start without a matching approved
resource envelope. Record unsupported requested capabilities with the intended
intervention, expected benefit, blocking boundary and empirical evidence if any.

Acceptance: launch from the browser; conduct at least two real research iterations
within the approved envelope; retain experiment identities and measured usage;
produce an actual independently reconstructed DEVELOPMENT result; survive browser
reconnect; stop all owned work; and distinguish every fixture test from real runs.
A completed campaign is not necessarily an improved model.

## C-MLP-03: Hermes, Chutes and Lium

Build separate agent, inference and experiment-worker adapters. Prefer the first
hosted combination Hermes + Chutes inference + Lium numerical worker, while
keeping an adapter for personal agents. Version the Carbon research skill and
record the exact runtime/model/skill/reconstruction identities for each campaign.

Verify provider contracts again at implementation time. References checked on
2026-09-17:

- Hermes programmatic interfaces:
  https://hermes-agent.nousresearch.com/docs/developer-guide/programmatic-integration
  Documents /v1/runs, status/events, stop and capabilities. Capability discovery is
  not durable orchestration or hard budget enforcement. Do not invent pause or
  durable resume semantics from a stop endpoint. Pin and test the actual request
  schemas, authorization, failure and recovery behavior.
- Lium agent integration:
  https://docs.lium.io/developers/agents
  Documents CLI/SDK access, a live OpenAPI source and explicit pod TTL. Its docs
  MCP is documentation access, not an execution/account-management endpoint.
- Chutes delegated authorization:
  https://chutes.ai/docs/sign-in-with-chutes/overview
  Validate supported scopes, user billing and revocation during implementation.

Before a paid launch, require an operator-approved grant binding principal,
challenge, permitted provider/account, run(s), expiry, total monetary cap, inference
call/token limits, GPU rate/quantity/time limits and concurrent-job limit. Reserve
worst-case in-flight spend transactionally before dispatch, share a grant across
its jobs, and reconcile actual charges. Unknown metering must stop new dispatch;
a prompt instruction is not enforcement. Show estimated versus settled charges
and any provider-billing lag. Do not promise an absolute invoice cap without a
provider-enforced cap or a justified worst-case bound including teardown latency.

Use durable intents and provider identifiers. Reconcile ambiguous timeouts before
retrying create/start; request idempotency alone cannot guarantee exactly-once
provider creation. Put expiry/TTL and independent cleanup outside the agent.
Stop must cancel agent work, terminate owned jobs/pods, verify teardown and retain
unresolved cleanup as an actionable state. Never report "stopped" solely because
a browser stream or Hermes turn ended. Test server crashes during each boundary.

Keep coldkeys out of the service. Do not place hotkeys or broad provider secrets on
rented workers. Run the trusted controller/signing boundary separately, scope
worker access to one job, and protect miner-to-miner workspace separation. No
claims of a secure arbitrary-code sandbox follow from containers or this draft.

## C-MLP-04: private hosted pilot and registration

Add authenticated owner accounts, authorization per run, revocable credentials,
request limits, audit events, reviewed secret storage, isolation and a deployment
runbook. Add the launch route to the existing site instead of replacing the site.
Use private staging first; do not borrow another website feature's deployment grant.

Add read-only testnet identity/registration preflight before transaction support.
Query current chain state and costs; show the exact network, subnet, hotkey, fee
and permitted transaction. Require wallet approval and exact transaction authority.
Persist finality/reconciliation evidence. No automatic repeat registration on
retry or agent restart. Keep mainnet and reward/payment claims unavailable until
their separate gates pass.

## C-MLP-05: optimize and expand

Compare agents using matched resource envelopes and fresh evaluator-held cases.
Measure first valid run, valid/reconstructable submissions, measured improvement
per unit cost, failed/wasted compute, invalid actions, recovery and cleanup latency,
and human interventions. Do not rank agents by transcript length or fixture wins.

After the baseline works, add Engy inference and additional compatible agent/worker
adapters. Keep Mira unavailable until deployment/API, external tools/compute,
export/reconstruction, stop/recovery and budget controls are verified. Record
improvement requests outside current bounds without silently expanding submission
freedom or protected access.

## Current blockers, not extra approval ceremonies

C-MLP-01 needs canonical acceptance, actual browser E2E and Hub reconciliation.
Paid research/provisioning needs the smallest concrete provider-account and budget
grant after the implementation preflight identifies it. Hosted pilot and chain
transactions need their own explicit authority. No agent or deployment has been
started by preparing this branch or handoff.
