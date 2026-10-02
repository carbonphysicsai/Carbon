# GRAPHITE-01: Carbon's in-house research and testing agent

**Owner decisions:** OWNER-GRAPHITE-01 and OWNER-GRAPHITE-02
(`.agent/DECISIONS.md`, 2026-10-02).
**Plan:** `docs/development/GRAPHITE_TESTING_AGENT_PLAN.md`.
**Status:**
- Phase 1 is merged.
- Phase 2 is built (conditional closeout: it takes effect when its PR passes
  automated acceptance and merges, per `.agent/DELIVERY_PROTOCOL.md`). Its
  live backfill runs under the completed USD 9 grant (account
  `Carbon-Account`, expiry 2026-12-31) in a session that has `ENGY_API_KEY`;
  the 50 hand-checked cards wait for the owner's checkers.
- Later phases are planned, and each needs an owner spending grant.

## Scope of phase 1

- A `GraphiteProvider` behind the #475 campaign controller. It drives the
  existing research loop (`carbon/development_session/research_loop.py`),
  with inference through `model_provider.py` (Engy first).
- Four roles (Planner, Constructor, Attacker, Optimizer researcher), plus
  the Reader and Writer roles for literature and delivery. Each role has:
  - its own prompt, recorded by digest;
  - a tool manifest;
  - a starting rung on the owner's ladder.
- Session records: provider, model, settings, prompt digest, tool manifest,
  literature snapshot, checkout commit, and the reservation and settlement
  of every call.
- A scripted fake model for tests. No live inference in phase 1.

## Definition of done (phase 1)

- Fake-model tests for:
  - the lifecycle, including crash recovery at each boundary;
  - caps and cancellation;
  - injection-as-data;
  - refusal of confirmation material;
  - the escalation rule (one rung, only on a recorded failure).
- Mutation tests show each protection is load-bearing.
- The quality ratchet, diff hygiene and Hub checks pass.

## Out of scope

- Live inference and any spend.
- The Chutes adapter (it belongs to C-MLP-03 §2).
- Confidential compute.
- Any change to the exam rule, EV4 or the frozen verifier.

## Phase 1 delivery (2026-10-02)

**Built.**

- The `carbon/agent_campaign/graphite/` package:
  - `provider.py`: `GraphiteProvider`, a provider for the #475 controller.
  - `roles.py`: the six roles.
  - `ladder.py`: the escalation rule.
  - `literature.py`: `lit.search` and `lit.card` over a synthetic fixture
    index.
  - `tools.py`: each role's closed toolbox.
  - `model.py`: `ScriptedModel`, and a `LiveModel` that requires a grant.
- A small repair to `research_loop.run_epoch`: an optional role
  `instructions` and closed `tools` list. With neither argument, historical
  campaigns run exactly as before.
- Phase 1 sends no live inference, reads no key and spends nothing.

**Tests.** All use the scripted model:

- `tests/cpu/test_graphite_harness.py`:
  - lifecycle behind the controller;
  - crash recovery at every checkpoint, with no resend;
  - a call in flight at a crash keeps its reservation and is reconciled,
    never resent;
  - controller and provider crash points;
  - the per-run money cap, the call cap, the elapsed limit and the grant
    ceiling;
  - cancellation mid-run, before the run starts, and at the runtime limit;
  - typed provider rejections;
  - deterministic session records;
  - refusal to resume a tampered session record or brief, and refusal to
    open a brief registered against another prompt or manifest.
- `tests/cpu/test_graphite_boundaries.py`:
  - roles;
  - injection-as-data, from a literature card and from a miner tool result;
  - typed refusal of confirmation and official material;
  - withholding a result that carries a canary;
  - a canary reaching the controller as a finding;
  - a live model refusing to run without a grant.
- `tests/cpu/test_graphite_ladder.py`:
  - escalation by one rung, only on a recorded failure;
  - no escalation on success or on an infrastructure failure;
  - each failure consumed once;
  - no skipped rung;
  - the top rung is a ceiling.
- `tests/cpu/test_graphite_mutations.py`: ten protections are switched off
  one at a time, and each switch fails its guarding test.

**Engineering decisions** (delegated, recorded here under
`.agent/DELEGATED_DECISION_PROTOCOL.md`; a lead may supersede any of them by
editing the named file):

- **GRAPHITE-D1, package location.** The package is
  `carbon/agent_campaign/graphite/`.
  - It is a provider behind the campaign controller, beside `fake` and
    `mira`.
  - The research-checkout denylist already excludes `carbon/agent_campaign/`,
    so no session can read its own harness.
  - Alternative rejected: a top-level `carbon/graphite/`. It would need a
    second denylist entry.
- **GRAPHITE-D2, loop repair.** `run_epoch` takes `instructions` and `tools`.
  - They are accepted only together, and only under the legacy policy with
    no Challenge.
  - Both are recorded in the epoch plan.
  - The loop runs its own selection or stop tool only when the role's list
    offers it. Any other call goes to the role's toolbox.
  - Alternative rejected: rewriting requests inside the transport. The plan
    file would then record the wrong prompt.
  - File: `carbon/development_session/research_loop.py`.
- **GRAPHITE-D3, tool names.** Provider function names allow only
  `[A-Za-z0-9_-]`. So `lit.search` and `lit.card` are sent as `lit_search`
  and `lit_card`. File: `graphite/literature.py`.
- **GRAPHITE-D4, role manifests.** Each role gets the least authority its
  job needs:
  - only the Constructor has the selection tool;
  - the Reader has only the literature tools;
  - no role has `get_prior` or `inspect_prior_alignment`.

  Starting rungs are the plan's §3 guesses. File: `graphite/roles.py`.
- **GRAPHITE-D5, protected material.** The toolbox refuses three things,
  each with a typed refusal:
  - a tool outside the manifest;
  - any argument string, including JSON inside `*_json` strings, that names
    protected material. This reuses `boundaries._denied` and adds Graphite's
    markers for seeds, draw ids, protected exams, verification references,
    private validator state and canaries;
  - any result that carries such material.

  The check may over-refuse an innocent mention; it never passes a named
  one. Briefs and literature cards are checked the same way when they are
  built. File: `graphite/tools.py`.
- **GRAPHITE-D6, escalation.**
  - Carbon records a typed research-failure observation, with an evidence
    digest, for the role's own failure kinds (the plan's "escalates when"
    column).
  - One escalation consumes one observation and moves exactly one rung.
  - Infrastructure outcomes are not failure kinds, so they never escalate.
  - Phase 1 does not decide automatically that an outcome is a research
    failure.
  - An escalation applies to the role's next session; a running session
    keeps its model.
  - File: `graphite/ladder.py`.
- **GRAPHITE-D7, run caps.**
  - A run's ledger is frozen with the grant's `worst_case_run_cost` as its
    nanodollar ceiling. That is the controller's reservation for the run.
  - Only USD grants are accepted.
  - Numerical work, final replicas and reference calls are capped at zero
    in phase 1.
  - An optional operator call cap narrows a run further.
  - The elapsed limit is the task's `max_runtime_s`.
  - File: `graphite/provider.py`.
- **GRAPHITE-D8, lifecycle.**
  - A task's `instructions_digest` names a brief that Carbon registered
    beforehand. The brief binds the role's prompt and manifest digests, and
    `start` refuses it if either has changed since.
  - `start` opens the session record.
  - `run` is the worker; an operator calls it.
  - `cancel` is observed at the loop's next ledger checkpoint, which comes
    before every reservation. A call already in flight completes and is
    journalled.
  - Before resuming, `run` re-verifies the session record against the
    role, the model selection, the literature snapshot, the brief, the grant
    and the caps. Any difference refuses the run.
  - Usage is read from the run's ledger. A reservation whose outcome is
    unknown is reported as pending, at its full amount.
  - File: `graphite/provider.py`.
- **GRAPHITE-D9, models.**
  - The adapter is Engy: `engy-anthropic` by default, or `engy-chat`.
  - The settings are `model_provider.DEFAULT_SETTINGS`.
  - Prices come only from `ENGY_MODELS`. A live model needs an exact
    `SpendingGrant` for provider `graphite`, so a `HUMAN_INPUT` template is
    refused, and it reads its key file only when it sends a request.
  - File: `graphite/model.py`.

**Limitations.**

- The worker runs in the provider's process. Worker liveness is tracked in
  memory per provider instance.
- Phase 1 connects no miner SDK, so miner tools answer `UNAVAILABLE`. It
  builds no sandbox image and does not materialize the allowlisted checkout;
  the brief records only the checkout's commit and manifest digest.
- A turn with several tool calls stops the session under the historical
  loop rule.
- Brief registration is not authenticated.
- The literature index is a synthetic fixture.
- None of this is scientific, security or production qualification.

**Open owner decisions** (each blocks only its own later phase). These were
open at phase 1; OWNER-GRAPHITE-02 has since decided the last two:

- the per-phase spending grants, for phase 2 onward. Phase 2 has USD 9, and
  its account and expiry are still open;
- the registered number of attempts after which a Constructor's builds count
  as stalled (plan §3). **Decided:** 5;
- the Chutes adapter (C-MLP-03 §2). **Decided:** approved.

## The reconstruction rule (OWNER-GRAPHITE-02, binding on every later phase)

- Every Graphite phase that widens what an agent may construct ships, in the
  same phase, Carbon's reconstruction capability for the widened surface,
  with tests that Carbon rebuilds it.
- A construction Carbon cannot rebuild is refused fail-closed with a typed
  refusal and recorded as a finding. It is never scored.
- Each later phase's Definition of Done includes its reconstruction path
  (plan §7).
- Phase 2 (literature) widens no construction surface.
- Phase 3 constructs only within the existing recorded construction
  contract: the `carbon/reconstruction` expansion records, and
  `tests/cpu/test_battery_construction_contract.py::test_every_surface_changes_what_carbon_rebuilds`.

## Phase 2: literature layer

**Scope** (plan §4; §7 phase 2):

- fetch;
- triage;
- method cards;
- a snapshot index;
- hand-check support;
- a runner.

Exit evidence: an index snapshot and 50 hand-checked method cards. Grant:
GRAPHITE-GRANT-PHASE2, USD 9.

**Definition of done (build).** Fixture and scripted-model tests for:

- fetch parsing, the rate limit, retries and the record cap;
- content addressing;
- triage into cards;
- injection inside an abstract treated as data;
- the grant refusals;
- the spend cap stopping a run mid-backfill;
- crash and resume without paying twice;
- snapshot determinism and loading into `LiteratureIndex`;
- no agent path marking a card human-checked.

Mutation checks show each protection is load-bearing. The quality ratchet,
diff hygiene and Hub checks pass.

**Definition of done (exit, later).** Both wait for the owner:

- a live backfill under the completed grant, and its index snapshot;
- 50 cards checked by people with `phase2 check`.

### Phase 2 delivery (2026-10-02)

**Built**, in `carbon/agent_campaign/graphite/`:

- `literature_fetch.py`:
  - a registered query set, `graphite-phase2-queries.v1`, of ten arXiv
    searches over neural operators, DeepONet, FNO, physics-informed and
    operator-learning training, battery surrogates, reduced-order
    electrochemistry, fast-charge optimization, surrogate adversarial
    robustness and surrogate benchmarks;
  - `ArxivClient`: at least 3 s between requests including retries, and
    bounded retries that honour Retry-After;
  - a typed `FetchFailed` (`FAILED_INFRA`) when they run out;
  - `RawStore`: content-addressed pages and records, and a retrieval journal
    with the query, page offset and time;
  - a hard cap of 5,000 records;
  - resume without refetching.
- `method_cards.py`:
  - the Reader extraction prompt, recorded by digest;
  - a closed request with no tools, where the paper is a JSON data message;
  - a closed reply shape: any other field, or any tool call, rejects the
    extraction with a typed code and makes no card;
  - cards carry the arXiv link, the abstract and record digests, and the
    model, selection, prompt, request and response digests. They are always
    written `UNCHECKED`;
  - human checks are append-only and bound to the card's digest. They need
    the card id typed back and a checker name that names no agent or model;
  - deterministic snapshots. A card naming protected material is withheld,
    and a card a person rejected is excluded. Snapshots load into the
    phase-1 `LiteratureIndex`, so `lit_search` and `lit_card` serve real
    cards.
- `triage.py`, the `Backfill`:
  - the Reader's ladder rung, on the cheapest rung by default;
  - every call through `research_agent.request_model` on a `CampaignLedger`,
    capped per run at the grant's `worst_case_run_cost` and a call cap;
  - the controller's grant arithmetic for opening a run;
  - typed stops (`COMPLETED`, `STOPPED_CAP`, `RECONCILIATION_REQUIRED`,
    `PROVIDER_REJECTED`, `STOPPED_INFRA`).
- `phase2.py`, the runner (see "Running phase 2 live").
- The Constructor stall limit, `roles.CONSTRUCTOR_STALL_ATTEMPTS = 5`.
  `ladder.record_failure` refuses a stall observation that states fewer
  attempts.
- `docs/development/graphite/grants/GRAPHITE-GRANT-PHASE2.json`, with its
  derivation in `docs/development/graphite/grants/README.md`.

**Live validation of parsing (no spend).** On 2026-10-02 `phase2 fetch` read
one 20-record page of each of the ten queries from the public arXiv API. That
gave 158 unique abstracts in 14 requests. Four of the requests were
retries, and the retries recovered. The fetched records stayed in a scratch directory,
outside the repository.

A dry run then:

- carded all 158 abstracts with the scripted model;
- produced the same snapshot digest twice;
- withheld no card as protected material.

Nothing from that sample is committed.

**Tests.**

- `tests/cpu/test_graphite_literature_fetch.py`
- `tests/cpu/test_graphite_method_cards.py`
- `tests/cpu/test_graphite_phase2_runner.py`
- `tests/cpu/test_graphite_phase2_mutations.py`: nine protections.
- The stall-limit test in `tests/cpu/test_graphite_ladder.py`.

**Engineering decisions** (delegated, recorded under
`.agent/DELEGATED_DECISION_PROTOCOL.md`; a lead may supersede any):

- **GRAPHITE-D10, one call per abstract.** The Reader triages (`relevant`)
  and extracts in a single call, which halves the calls the plan's two steps
  would make. Both steps stay on the cheapest rung. File:
  `graphite/method_cards.py`.
- **GRAPHITE-D11, query set.** `graphite-phase2-queries.v1` lists search
  terms, not claims. A change is a new version, and each record keeps the
  query it came from. File: `graphite/literature_fetch.py`.
- **GRAPHITE-D12, injection.**
  - The request is fixed by Carbon: prompt, no tools, model and bounds.
  - The paper travels only as a JSON data message.
  - The reply must be exactly the card fields. Rejecting a wider reply,
    rather than dropping the extra fields, makes an obeyed injection visible
    as a typed rejection.
  - File: `graphite/method_cards.py`.
- **GRAPHITE-D13, triage settings.** 16,384 input tokens (the smallest the
  selection accepts) and 1,024 output tokens, so a call reserves USD
  0.00082944 on `deepseek-v4-flash-0731`. Phase 1's research loop keeps
  `DEFAULT_SETTINGS`. A request too large for the window is rejected before
  dispatch. File: `graphite/triage.py`.
- **GRAPHITE-D14, human checks.**
  - The check needs the card id typed back on an interactive terminal.
  - The checker name may not name an agent, role or model.
  - The agent path has no tool or code path that writes a check, and cards
    are stored only `UNCHECKED`.
  - This is a guard, not authentication.
  - File: `graphite/method_cards.py`, `graphite/phase2.py`.
- **GRAPHITE-D15, backfill runs under the grant.**
  - The backfill is not a #475 controller provider. Each run has its own
    research ledger.
  - A new run opens under the controller's arithmetic: the run count, and
    settled plus reserved spend, plus the next worst case, plus cleanup,
    within the ceiling.
  - A resume is not a new run.
  - File: `graphite/triage.py`.
- **GRAPHITE-D16, credentials.**
  - The runner takes `--credential-file` or `--credential-env ENGY_API_KEY`.
  - From the environment, it writes a 0600 file in a fresh 0700 temporary
    directory, passes the path as the credential reference and deletes it
    on exit. The key is never printed or logged.
  - `CHUTES_API_KEY` is recognised and refused until Graphite wires the
    Chutes adapter.
  - File: `graphite/phase2.py`.

**Running phase 2 live** (the grant is complete as of 2026-10-02):

```
export ENGY_API_KEY=...             # already in the owner's environment
ROOT=/path/outside/the/repository   # a private directory
python -m carbon.agent_campaign.graphite.phase2 fetch --root "$ROOT" --max-records 3000
python -m carbon.agent_campaign.graphite.phase2 triage --root "$ROOT" \
    --grant docs/development/graphite/grants/GRAPHITE-GRANT-PHASE2.json \
    --credential-env ENGY_API_KEY
python -m carbon.agent_campaign.graphite.phase2 snapshot --root "$ROOT"
python -m carbon.agent_campaign.graphite.phase2 cards --root "$ROOT" --unchecked
python -m carbon.agent_campaign.graphite.phase2 check --root "$ROOT" \
    --card arxiv-XXXX.XXXXXvN --checker NAME --verdict CORRECT   # a person, at a terminal
```

`triage` exits 4 on a typed stop other than `COMPLETED`. Running it again
resumes the same run, and a different `--run-id` opens a new one under the
grant.

**Limitations.**

- No live inference has run, so token use and cost are estimates.
- `lit_search` is keyword search; there are no embeddings.
- The backfill runs on demand, not nightly.
- The Chutes adapter is not wired into Graphite.
- Human checks are not authenticated.
- None of this is scientific, security or production qualification.

## Phase 3: Constructor, Level 0

**Owner decision:** OWNER-GRAPHITE-03 (2026-10-02): "$15 runpod included",
then "Start phase 3 build in parallel". One USD 15 grant,
GRAPHITE-GRANT-PHASE3, covers Engy tokens and RunPod pod time together.

**Scope** (plan §5 and §7, phase 3): the Constructor proposes declarative
battery `TrainingStrategy` objects through the real miner path. Carbon then:

1. runs each proposal on a RunPod pod;
2. scores it by the frozen rule;
3. bundles the best improvement as a PR-ready directory;
4. rebuilds that bundle from the bundle alone.

Level 0 widens nothing: every construction stays inside the recorded battery
construction contract (the reconstruction rule).

**Definition of done (build).** Scripted-model, scripted-pod tests for:

- an end-to-end session: proposal → pod run → frozen-rule score → rebuild
  match → bundle → clean rebuild;
- a rebuild mismatch becoming a finding;
- an unrebuildable proposal refused and never scored;
- the combined token and pod cap;
- pod termination on cancellation and after a crash;
- crash and resume without paying twice;
- injection as data;
- refusal of confirmation material;
- the stall limit producing the ladder observation.

Mutation checks show each protection is load-bearing. The graphite and
agent_campaign suites, the quality ratchet, diff hygiene and Hub checks pass.

**Definition of done (exit, later).** The first block of 3 live sessions
under the grant, giving the plan's first end-to-end proposal → run →
frozen-rule score → PR → clean rebuild.

### Phase 3 delivery (2026-10-02)

**Built** (conditional closeout: it takes effect when its PR passes automated
acceptance and merges, per `.agent/DELIVERY_PROTOCOL.md`). The live sessions
are pending. Nothing was sent to a live model, no pod was started, no key was
read and nothing was spent.

New modules in `carbon/agent_campaign/graphite/`:

- `miner_path.py`: the real miner path, which phase 1 left unconnected.
  - `attach` opens the standard miner MCP door
    (`standard_cli.load_profile` and `attached_profile`) on a battery
    DEVELOPMENT campaign, and refuses any other Challenge.
  - `MinerPathTools` sends each raw tool call to the public
    `ResearchToolAdapter.call`, exactly as an external MCP client does.
  - An adapter failure that may have dispatched stops the loop for
    reconciliation.
- `experiment.py`: Carbon's runner.
  - **The reconstruction gate.** A proposal must compile under the live
    battery contract, and that contract must be the one its newest expansion
    record pins. Anything else is refused as `REFUSED_UNREBUILDABLE`,
    recorded as a finding and never run or scored.
  - **Pinned build.** Carbon computes what it would build before any pod:
    the recipe, the staged files and the program, by digest.
  - **Pod reservation.** Each pod is reserved against the run's combined
    token and pod cap. Each model call is held to the same cap
    (`phase3.Phase3Ledger`).
  - **Lost creates.** A create whose answer is lost is never sent again. The
    pod it made is adopted by its ownership tag, and when none exists its
    reservation is released.
  - **Independent rebuild check.** The pod's `built.json` is compared with
    Carbon's own record. A mismatch is a finding, and the proposal is not
    scored.
  - **Frozen-rule score.** `practice.score_practice` on the 200 public
    PRACTICE cases, then `exam.final_compare` (rule v2) against the
    session's baseline.
  - **Stall rule.** It applies after 5 non-improving attempts.
  - **Pod ledger.** An EV4-style append-only JSONL ledger per run.
- `pods.py`: the pods.
  - `RunPodPods`, on the compute layer's `ComputeService` and
    `RunPodAdapter`, with EV4's pinned study image, `bootstrap.py` and a
    hash-pinned code ship at a pushed commit.
  - Verified termination, and the provider's own charge.
  - `ScriptedPods`, a scripted lifecycle with rates, charges, failures and
    process deaths.
  - Prices are read from `pod_control`.
- `pod_phase.py`: the `graphite_practice` pod phase, added to
  `scripts/dev/exam_design/runner.py`.
  - It compiles the proposal and builds the practice trial's staged files.
  - It refuses to run unless they match Carbon's pinned digests.
  - It then runs the fixed GPU practice program.
- `delivery.py`: the PR-ready bundle (`strategy.json`, `recipe.json`,
  `score.json`, `rows.json`, `baseline.json`, `ablations.json`,
  `run-log.jsonl`, `WRITEUP.md`, `REBUILD.md`, `manifest.json`) and
  `clean_rebuild`, which reads the bundle alone.
- `phase3.py`: `Phase3Provider` (a `GraphiteProvider`) and the runner
  (`run`, `cancel`, `reconcile`, `status`, `rebuild`, and `run --dry-run`).

Other changes:

- `roles.py`: the Constructor's manifest gains `graphite_run_proposal`, and
  its prompt names it. No other role has it.
- `provider.py`: the GRAPHITE-D17 repair (below).
- `docs/development/graphite/grants/GRAPHITE-GRANT-PHASE3.json`, with its
  arithmetic in the grants README.

**Tests.**

- `tests/cpu/test_graphite_phase3.py`: 41 tests covering every DoD item.
  Also covered:
  - the pod phase's local CPU run, and its refusal of a different build;
  - pod_control's code-manifest equality;
  - the live RunPod backend against an in-memory RunPod;
  - the miner adapter translation;
  - the runner's refusals and its dry run.
- `tests/cpu/test_graphite_phase3_mutations.py`: 12 protections, each
  switched off in turn.
- `tests/service/test_graphite_miner_path.py`: a Constructor session whose
  miner tools reach the battery composition through the standard
  `ResearchToolAdapter` (signed gateway, research adapter, campaign ledger),
  added to `scripts/dev/ci.sh`'s MCP lane.

**Engineering decisions** (delegated, recorded under
`.agent/DELEGATED_DECISION_PROTOCOL.md`; a lead may supersede any):

- **GRAPHITE-D17, provider hooks.** `GraphiteProvider.run` now calls
  `_epoch` (one research epoch) and `_unresolved` (whether a reservation's
  outcome is unknown). Phase 3 overrides both; phase 1 behaves exactly as
  before. File: `graphite/provider.py`.
- **GRAPHITE-D18, the miner path.**
  - The real path is the standard miner MCP attachment, not a second
    composition. It holds the campaign lock, checks the owner, and composes
    the Challenge's own research service.
  - Graphite's operation ids are `graphite-<run>-<tool>`, so sessions never
    collide in one miner campaign.
  - File: `graphite/miner_path.py`.
- **GRAPHITE-D19, pods and the session's shape.**
  - One proposal is one pod of 30 minutes: start-up 15 (the rented runner's
    900 s), job 10 (the contract's `worker_deadline_seconds`) and export 5
    (pod_control's default).
  - A session has 12 pods (360 minutes, the plan's upper estimate of USD 3).
  - The pods use EV4's pinned image, A40 Secure, the 0.49 rate ceiling and
    disk price, the 0.25 cleanup reserve and the 2.00 balance floor, all
    read from `pod_control`.
  - Lifecycle, ownership tags, lost-create recovery and verified termination
    come from `carbon.compute`.
  - Only JAX recipes are served, as in the GPU practice lane. A PyTorch recipe
    is refused, typed, and is not a finding.
  - Files: `graphite/pods.py`, `graphite/experiment.py`.
- **GRAPHITE-D20, the proposal tool and the rebuild check.**
  - The Constructor's `graphite_run_proposal` carries data only.
  - Carbon compares nine fields of what the pod built with its own
    computation (`experiment.REBUILT_FIELDS`). Any difference is a
    `REBUILD_MISMATCH` finding (`OTHER_SIGNAL`), and the proposal is not
    scored.
  - A proposal refused by the gate is an `UNREBUILDABLE` finding.
  - Findings reach the controller (`phase3.sync_findings`), where they block
    any later expansion.
  - Files: `graphite/roles.py`, `graphite/experiment.py`, `graphite/phase3.py`.
- **GRAPHITE-D21, the baseline and the frozen rule on development material.**
  - Each session runs a baseline once, on its first pod. By default this is
    the battery scaffold, the unexecuted template every miner starts from.
  - Each proposal is scored and compared with it by the frozen gates and
    score and rule v2's paired comparison, on public PRACTICE only.
  - The baseline is a provisional engineering default, not the B1 study
    population, which stays science-reserved (plan §9).
  - File: `graphite/phase3.py` (`session_brief`).
- **GRAPHITE-D22, the stall rule's automation.**
  - A stall is 5 consecutive scored proposals since the last `IMPROVEMENT`
    that are not an `IMPROVEMENT`.
  - At the limit Carbon records one `BUILD_STALLED_AGAINST_BASELINE`
    observation per run.
  - At the session's end the provider consumes it and moves the Constructor
    up one rung for its next session.
  - Compile failures are not escalated automatically.
  - Files: `graphite/experiment.py`, `graphite/phase3.py`.
- **GRAPHITE-D23, delivery.**
  - Carbon's rule picks the proposal to bundle: the eligible `IMPROVEMENT`
    with the lowest score. The agent's own selection is recorded beside it.
  - Ablations remove each change from the baseline one at a time, while pods
    remain.
  - The write-up is generated from the records; no Writer model runs in
    phase 3.
  - The clean rebuild checks digests. Numerical reproduction is
    `NOT_JUDGED` with tolerance `HUMAN_INPUT`.
  - File: `graphite/delivery.py`.
- **GRAPHITE-D24, keys, cancellation and crashes.**
  - **Keys.** The RunPod key is an owner-only file (pod_control's
    `~/.runpod/api_key`), or `RUNPOD_API_KEY` copied into a 0600 file in a
    fresh 0700 directory and removed on exit.
  - **Cancellation.** `phase3 cancel`, SIGINT or SIGTERM sets the run's
    cancel flag. The worker terminates its pod, verifies it is gone and
    finishes cancelled.
  - **Crashes.** A resume first terminates every pod the run may have
    created and settles it. It never launches one again. An interrupted
    proposal stays open, and the run ends `reconciliation_required`.
  - **Settlement.** A pod's spend settles from RunPod's billing record. An
    unreported charge keeps the full reservation.
  - File: `graphite/phase3.py`.

**Running phase 3 live** (the later session; the grant expires 2026-12-31):

```
export ENGY_API_KEY=... RUNPOD_API_KEY=...       # in the owner's environment
ROOT=/path/outside/the/repository                 # a private directory
REF=<the checked-out commit>                       # pushed, and clean under carbon/ and scripts/dev/exam_design/
python -m carbon.agent_campaign.graphite.phase3 run --root "$ROOT" \
    --grant docs/development/graphite/grants/GRAPHITE-GRANT-PHASE3.json \
    --credential-env ENGY_API_KEY --runpod-key-env RUNPOD_API_KEY \
    --miner-profile PROFILE.json --miner-campaign CAMPAIGN_ID \
    --code-ref "$REF" --session 1
python -m carbon.agent_campaign.graphite.phase3 status --root "$ROOT"
python -m carbon.agent_campaign.graphite.phase3 cancel --root "$ROOT" --session 1
python -m carbon.agent_campaign.graphite.phase3 reconcile --root "$ROOT" \
    --grant docs/development/graphite/grants/GRAPHITE-GRANT-PHASE3.json \
    --runpod-key-env RUNPOD_API_KEY --code-ref "$REF"
python -m carbon.agent_campaign.graphite.phase3 rebuild --bundle "$ROOT/graphite/runs/RUN/delivery"
python -m carbon.agent_campaign.graphite.phase3 run --root "$ROOT" --dry-run   # no spend
```

What each argument is:

- `PROFILE.json` and `CAMPAIGN_ID` name a battery DEVELOPMENT miner campaign
  that a miner has launched with the Launchpad, on a registered testnet
  hotkey. Graphite attaches to it as any MCP client does.
- Sessions 2 and 3 use `--session 2` and `--session 3`.
- Running the same command again resumes a session.
- `run` exits 4 on any end other than `succeeded`.

**Limitations.**

- No live session has run. Token, pod and time figures are planning
  estimates until the first one.
- RunPod's billing read (`RunPodAdapter.provider_charge`) has not been
  exercised live. Until it is, a pod may stay at its full reservation, which
  leaves fewer proposals per session but never more spend.
- **The pod phase is unexercised on RunPod.** It is exercised locally on the
  CPU. Its first run on EV4's study image, with JAX on CUDA, is the live
  check.
- `miner_path.attach` needs that launched campaign and its accepted host
  images. The service test drives the same adapter class through fixture
  signing, not `attach` itself.
- The scores are development feedback on adaptively seen public PRACTICE
  cases, chosen as the best of a session's proposals. They carry selection
  bias and are not held-out evidence.
- The worker runs in the runner's process. A cancellation from another
  process is a flag the worker reads at its next checkpoint or pod poll.
- None of this is scientific, security or production qualification.

**Open owner decisions** (none blocks the build):

- the live sessions themselves, which need the keys and a launched battery
  miner campaign;
- science-reserved, unchanged (plan §9): the reconstruction tolerances,
  which would let a clean rebuild judge a retrained model's numbers, and the
  Level-0 study population and held-out confirmation for B1.
