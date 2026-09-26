# Miner Control Center programme record

The single record for the miner Control Center: what exists, what is decided,
who is doing what, and in which order. It is an orientation and tracking
document. It grants no authority, and it does not mark anything qualified.
Repository code and tests remain the authority for what is implemented.

- **Goal.** A miner can use the browser to register (existing registration),
  select a Challenge, choose an agent and model provider or work manually,
  connect compute, set optional limits, launch, watch, control, freeze, submit,
  and read the receipt and permitted feedback. They do this without editing
  configuration files or using a terminal during the normal journey.
- **First release.** One complete battery campaign on testnet 567. It has one
  cloud-compute path (RunPod), a working autonomous-agent path with the
  miner's chosen provider, manual research, and an external MCP (stdio)
  connection.
- **Audit basis.** `origin/main` at `a32dcd70a` (26 September 2026), plus the
  Launchpad stack still in review (`agent/miner-no-limits`,
  `agent/challenge-campaign-adapter`).

## Evidence levels

Each capability is graded separately on five levels. A level is held only with
cited code or a recorded run. It is never inferred from markup, a fixture, a
schema or a document.

1. **UI exists.**
2. **Backend exists.**
3. **Browser reaches backend:** a route is wired, not just markup.
4. **Real execution passed:** a real run, not a fixture. Where the only run is
   fixture-grade, the matrix says so.
5. **Deployment available:** on this host.

## Capability matrix (audit, 26 September 2026)

| Capability | Current implementation | Evidence | Levels | Remaining integration | Lane |
|---|---|---|---|---|---|
| Navigation and shell | Seven sections: Connect, Register, Rehearsal, Research, Validator exam, Evidence, Integrations. No per-campaign tabs or deep links. Rehearsal fixtures sit in the primary flow. | `scripts/dev/miner_launchpad/index.html`, `app.js`; `browser_smoke.py` | 1, 3 | The target navigation (Overview, Campaigns, Challenges, Agents, Compute, Connections, Wallet & Identity, Settings); campaign tabs; a Development area | UI |
| Capability-driven interface | `/api/v1/capabilities` still uses the rehearsal-era schema with a stale Burgers entry. `options` is versioned and registry-driven. Much of the UI is hard-coded. | `controller.py`, `runner.py` | mixed | A versioned capability contract for the whole wizard | UI |
| Shared browser/MCP operations | `launch`, `options`, `observe`, `practice`, `halt`, `resume`, `freeze_candidate`, `submit`. The gates are ordered and genuinely shared with MCP. | `operations.py`; `carbon/miner_mcp/mcp_operations.py`; `test_miner_operations_doors`, `test_journey_one_definition` | 1–3 | Idempotency beyond launch (next row) | — |
| Idempotency | Only launch has it: a replay gate plus a digest conflict. `practice`, `freeze_candidate` and `submit` have none, so a retried submit can double-submit. **This is a correctness defect.** | `runner.py` replay gate | 2–3 (launch only) | Idempotency keys for all three, durable across restart | Lane 0 |
| Challenge selection | The backend resolves `challenge`/`challenge_version` exactly. The browser never sends one. | `runner._challenge`; `carbon/challenge_registry` | 2 | Battery-first selection in the wizard | UI |
| Challenge-specific behaviour | `ChallengeCampaign` adapters are resolved only through the registry. The shared workflow names no Challenge. | `carbon/challenge_registry/campaigns.py`; `test_challenge_campaigns.py` | 2 | Retire Burgers from the path (launch must name a Challenge) | Lane 0 |
| Battery description | Built from executable registrations: objective, inputs and outputs, public material, reference method, rebuildable families, exam gates and feedback. There is no research-versus-validator hardware field. | `carbon/challenge_registry/battery.py` | 2 | Browser view; hardware split | UI |
| Battery practice | Real JAX training scored by the exam's own gates. Tested only in a non-isolated subprocess runner. | `carbon/battery/research.py`, `practice.py`; `tests/service/test_battery_mcp_research.py` | 2, 4 (fixture-grade) | A run through the Docker carrier | H |
| Freeze and submit to validator | Freeze needs a completed practice. Submit is a signed `battery_submit` to the validator daemon; without a deployment it is refused as `evaluation_unavailable` and the candidate is retained. | `carbon/battery/campaign.py`, `daemon.py`, `deployment.py` | 2, 4 (in-process backend) | Deployment on this host; browser path | H, UI |
| Validator reconstruction | The daemon rebuilds with Carbon's seed. It handles restarts, retries and stale-final withdrawal. | `tests/cpu/test_battery_validator_daemon.py` | 2, 4 (in-process, published cases) | Deploy on this host; commitment gate | H |
| Identity and registration | Describes the transaction and re-reads status against a finalized snapshot. Signing is external by design. No fee read and no registration submission journal. Every test uses a stub reader. | `carbon/development_session/chain_onboarding.py`; `test_launchpad_onboarding_door.py` | 1–3 (stub) | One real read of the registered UID; expose observation time | UI |
| Agent (autonomous) | Challenge-neutral for battery. Provider and model are hard-wired to one vendor and model. No rate-limit handling. Battery has only scripted-agent evidence. | `research_loop.py`, `research_agent.py`, `agent.py` | Burgers 1–4; battery 2 | Miner-chosen provider and model; rate limits; remove shared Burgers assumptions | Agent |
| Manual research | Practice, freeze and development submit from the browser | `app.js`; journey fixture | 1–3 (fixture) | Battery manual path | UI |
| External MCP (stdio) | Open tier, operations and attach modes; protocol tests use a real MCP client driven by a script | `standard_cli.py`; `test_standard_mcp_stdio.py` | 2, 4 (protocol) | In-UI connection instructions and a connection test | Agent |
| Remote MCP | Authentication code exists; no listener | `access_auth.py`, `standard_http.py` | 2 | Needs the §4 security review for reachability beyond this host. Stdio covers the first release. | — |
| Compute: local worker | Isolated Docker carrier with intent recorded before create, exact removal and a watchdog | `research_carrier.py`, `docker_runtime.py` | 2, 4 (service tests) | Selectable in the wizard; a liveness reaper for unbounded miner runs | UI, G |
| Compute: cloud provider | No provider layer in `carbon/`. RunPod exists only as an untested operator script with estimated charges and a report-only reconcile. | `scripts/dev/exam_design/runpod/pod_control.py` | 2 (script) | Provider interface and RunPod adapter; off-host reconciler | Compute |
| Budgets | Per-dimension ceilings, elapsed time and a final reserve, with transactional reservation. Blank means no limit. No total-money or concurrency dimension. No change after launch. | `research_ledger.py`, `product_campaign.py` | 1–3 | Budget amendment; money and concurrency vocabulary | F/G |
| Experiments, journal, artifacts, logs | A training-loss curve and a JSON dump. No artifact, log or journal views. | `app.js` | partial | Views driven by the capability contract | F |
| Recovery and cleanup | Separate desired and observed control states; generation fencing; settlement after verified cleanup | `research_control.py`, `runner.py` | 2–4 (unit) | Battery campaign tested under a restart; the reaper | G |

## Owner decisions (26 September 2026)

1. **Hosting.** The owner's development host. The battery validator has no listener
   and deploys here. W-C needs no public endpoint under Path A. Reachability
   beyond this host is gated by the owner's §4 security review, and nothing
   else gates it.
2. **RunPod.** Approved, capped at the existing account balance. The balance is
   read and reported before the first dispatch. The key is scoped to pod
   lifecycle. The independent reconciler runs off the host it reconciles.
3. **Model provider.** The miner's choice. The miner selects the provider and
   model and supplies their own credential. Carbon keeps the provider/model
   split and does not hard-code a vendor.
4. **Registration.** Reuse the existing registered UID (confirmed at block
   8,065,348). No new hotkey.
5. **Wallet.** Signing stays external. The absence of a signing capability
   remains provable.
6. **Portfolio.** Battery is the first Challenge (OWNER-LAUNCH-PORTFOLIO-01,
   #354). The statement in #341 that battery is outside the launch portfolio
   is superseded.

## Lanes and dependency order

| Lane | Scope | Branch | Depends on |
|---|---|---|---|
| 0 | Land #339 (Julia for every product campaign); the `miner-no-limits` stack; the Challenge campaign adapter; **idempotency for practice, freeze and submit**; retiring Burgers from the path | `agent/julia-without-grant`, `agent/miner-no-limits`, `agent/challenge-campaign-adapter`, `agent/cc-idempotency`, `agent/retire-burgers-path` | — |
| UI (B + C) | Capability contract, navigation shell, battery-first launch wizard | `agent/cc-shell-wizard` | Adapter |
| Compute (D) | Provider interface and RunPod adapter; off-host reconciler | `agent/cc-compute-provider` | Adapter |
| Agent (E) | Provider/model split; rate limits; shared Burgers assumptions removed; MCP connection instructions and test | `agent/cc-agent-provider` | Adapter |
| Reliability (G) | Controller-liveness reaper for unbounded miner runs | `agent/cc-reliability` | Idempotency |
| F | Experiments, metrics, journal, artifacts, submission and logs views | — | UI contract |
| H | Live battery journey on this host: validator deployment, RunPod dispatch, a real agent run with the miner's provider, reconnect, stop and reconcile | — | All of the above |

## Adjacent work and ownership

- **Battery validator deployment on this host** belongs to the testnet session:
  operate init, truth materialization and verification, private batches,
  opening the pool, and the carrier doctor. The Control Center consumes that
  deployment and never writes to its state. Status on 26 September:
  - The deployment is configured and the truth overlay verifies.
  - It does **not yet accept submissions**. Three things come first: #357 must
    merge, the private screening batches must be prepared, solved and
    ingested, and `operate open` must run.
  - It runs with `require_commitment: false` deliberately, because no chain
    commitment reader exists. Admissions record `commitment: null`.
- **#356 CL-SHARED-01** adds a readiness record per launch-portfolio Challenge,
  keyed on the Challenge registry. It is adjacent to this programme and has no
  file overlap.
- **#352 BATTERY-EV1** is exam-method research. It is not a Control Center
  dependency.

## Readiness vocabulary

Specified, implemented, tested and empirically exercised stay separate from
scientific, security and production qualification. A working Control Center
is not a qualified one. The milestone is complete only when the owner has run
the battery journey through the interface and the evidence is retained: which
source and runtime executed, which services were real, what the agent and
workers did, what the validator observed, what it cost, and which resources
remain. UI screenshots, fixtures or merged backend work alone do not complete
it.
