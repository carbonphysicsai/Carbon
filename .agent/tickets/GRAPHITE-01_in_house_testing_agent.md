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
- `tests/cpu/test_graphite_phase2_mutations.py`: ten protections (the tenth,
  the GRAPHITE-D17 write-off, added by the 2026-10-02 amendment).
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
- **GRAPHITE-D17, writing off a call with an unknown outcome** (2026-10-02,
  under the OWNER-GRAPHITE-02 amendment "Raise runs, add resume fix
  (Recommended)").
  - The problem. A container restart kills the process mid-call. The call
    stays `RESERVED` in its run's ledger with its full reservation, because
    the provider may have received and charged it. Before this change, every
    later start of that run stopped `RECONCILIATION_REQUIRED` again, because
    `request_model` refuses to resend that call. So a run could not continue,
    and a new run would have sent the same record again under a new ledger.
  - The fix. At the start of every run, new or resumed,
    `Backfill.write_off_unknown` scans the ledgers of all runs for operations
    in state `RESERVED`. It maps each one back to its raw record: the id is
    `card-` plus `address[7:47]`, with `-rlN` on a rate-limit retry. It
    writes a typed rejection for that record through
    `CardStore.put_rejection`: code `provider_outcome_unknown`, with the run
    id, the operation id and the reservation. `pending()` then skips the
    record, so no run resends it.
  - Money. The ledger is not touched. The operation stays `RESERVED` with
    its full reservation, so the run's money cap, `committed_nano()` and the
    grant gate keep counting it. Nothing is settled, refunded or deleted.
  - The ledger allows it. A backfill ledger is frozen with the development
    CLI's own manifest schema (`research_ledger.VERSION`), which is not a
    controlled campaign. The "unknown provider metering; reconcile before
    dispatch" refusal applies only to controlled campaigns, so the ledger
    admits new operations beside a `RESERVED` one, and its cap arithmetic
    includes the `RESERVED` reservation. Only a resend of the same id is
    refused ("provider outcome uncertain"). The write-off makes sure that
    resend never happens.
  - Idempotent. A record that already has a card or a rejection is left as
    it is. For example, a record stuck in one run may already have been
    carded by a later run. Rejections are written once, with no timestamp.
  - Fail closed. A `RESERVED` operation that maps to no record in the raw
    store refuses the run (`unresolved_operation_unmapped`) before anything
    is written or sent.
  - The stop is still visible. A call that ends with an unknown outcome
    during a run still stops that run `RECONCILIATION_REQUIRED`: a crash, a
    transient server error, or any other failure whose outcome is unknown. The
    write-off happens only at the next start. Calls written off at the start
    do not turn a later typed stop (for example `PROVIDER_REJECTED`) into
    `RECONCILIATION_REQUIRED`.
  - The run summary carries `written_off_unknown`: the number of records
    written off at this start.
  - Tests: `tests/cpu/test_graphite_method_cards.py`. The mutation case
    `unknown_call_write_off` in `tests/cpu/test_graphite_phase2_mutations.py`
    shows that without the scan a new run resends the call.
  - File: `graphite/triage.py`.
- **GRAPHITE-D27, a hard deadline on every provider call** (2026-10-02,
  owner order "Do it now"; numbered D27 because D18-D26 are taken on other
  branches).
  - The problem. Twice on 2026-10-02 a live triage call sat with no response
    for 26 minutes or more, its operation still `RESERVED` (created 19:28:18
    and 20:00:12 UTC). `model_provider._post` passed `timeout_seconds` (120)
    to urllib, which applies it to each socket operation separately:
    connect, proxy CONNECT, TLS handshake and every `recv`. Nothing bounded
    the whole call. Headers or a body that arrive in pieces, each piece
    inside 120 s, keep the read alive until the 2 MiB response bound, and DNS
    resolution has no timeout at all. The rate-limit retry loop is bounded
    (two resends, at most 30 s apart) and is not the cause. Which of these
    the live calls hit is not known from the code alone.
  - The fix. `_post` runs the exchange in a daemon worker thread and joins it
    for `call_deadline_seconds(settings)`: `timeout_seconds` plus
    `DEADLINE_MARGIN_SECONDS` (10), so 130 s for triage. The margin admits
    the connect, handshake and send before the reply wait, so a call that
    completed within its per-read timeout before still completes. Past the
    deadline the call's sockets (TCP, and TLS before its handshake) are shut,
    which unblocks the worker, and `ProviderDeadlineExceeded` is raised. A
    daemon thread never holds up process exit; a stall inside DNS cannot be
    shut and ends when the resolver returns.
  - The outcome. `ProviderDeadlineExceeded` is not an HTTP rejection, so
    `classify` makes it UNKNOWN: the full reservation stays, nothing is
    settled and nothing is resent. Triage stops `RECONCILIATION_REQUIRED`
    and the GRAPHITE-D17 write-off handles the call at the next start.
  - Every adapter shares `_post`, so the deadline applies to engy-anthropic,
    engy-chat, chutes, anthropic, openai-responses and both
    openai-compatible adapters. Per-read timeouts and all replies inside the
    deadline are unchanged.
  - Not changed. The elapsed-envelope check still asks that
    `timeout_seconds` fit the remaining campaign time, so a call can overrun
    it by at most the 10 s margin. `fetch_models` (an operator check with no
    reservation) keeps its per-read timeout only.
  - Tests: `tests/cpu/test_provider_call_deadline.py`. A local HTTPS server
    stalls before headers, trickles the body a byte at a time, or accepts and
    never speaks; each call ends within a 0.5 s injected deadline plus 2 s
    as UNKNOWN, keeps its reservation, is refused on replay and is sent once,
    and its worker exits. A fast reply is unchanged. The mutation case
    removes the deadline and shows the stall outliving the bound.
  - File: `carbon/development_session/model_provider.py`.

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

**Running in chunks** (OWNER-GRAPHITE-02 amendment, 2026-10-02). The grant
permits 40 runs. Triage in chunks of about 300 calls, one run id per chunk:

```
python -m carbon.agent_campaign.graphite.phase2 triage --root "$ROOT" \
    --grant docs/development/graphite/grants/GRAPHITE-GRANT-PHASE2.json \
    --credential-env ENGY_API_KEY --run-id chunk-NN --max-calls 300
```

If the container restarts mid-call, rerun the same command with the same
`--run-id` and `--max-calls`. A different `--max-calls` changes the run record
and is refused (`run_record_mismatch`). The rerun writes off the one call with
an unknown outcome (GRAPHITE-D17), reports it in `written_off_unknown`, and
continues with the remaining records. A chunk that ends `STOPPED_CAP` on
`provider_attempts` has used its 300 calls; the next chunk takes a new run id.

**Limitations.**

- Live triage has run (`smoke-1`, `full-1`, `full-2`: 101 cards and 1
  rejection; see the OWNER-GRAPHITE-02 amendment). Engy reports no
  `x_engy.charged_micro`, so every call keeps its full reservation as
  booked spend (USD 0.086 booked against about USD 0.007 estimated).
- A call written off under GRAPHITE-D17 is never retried, so its record has
  no card. Retrying those records would need a new owner decision.
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
- `provider.py`: the GRAPHITE-D18 repair (below).
- `docs/development/graphite/grants/GRAPHITE-GRANT-PHASE3.json`, with its
  arithmetic in the grants README.

**Tests.**

- `tests/cpu/test_graphite_phase3.py`: 44 tests covering every DoD item.
  Also covered:
  - the pod phase's local CPU run, and its refusal of a different build;
  - pod_control's code-manifest equality;
  - the live RunPod backend against an in-memory RunPod;
  - the miner adapter translation;
  - the runner's refusals and its dry run.
- `tests/cpu/test_graphite_phase3_mutations.py`: 14 protections, each
  switched off in turn.
- `tests/service/test_graphite_miner_path.py`: a Constructor session whose
  miner tools reach the battery composition through the standard
  `ResearchToolAdapter` (signed gateway, research adapter, campaign ledger),
  added to `scripts/dev/ci.sh`'s MCP lane.

**Engineering decisions** (delegated, recorded under
`.agent/DELEGATED_DECISION_PROTOCOL.md`; a lead may supersede any):

- **GRAPHITE-D18, provider hooks.** `GraphiteProvider.run` now calls
  `_epoch` (one research epoch) and `_unresolved` (whether a reservation's
  outcome is unknown). Phase 3 overrides both; phase 1 behaves exactly as
  before. File: `graphite/provider.py`.
- **GRAPHITE-D19, the miner path.**
  - The real path is the standard miner MCP attachment, not a second
    composition. It holds the campaign lock, checks the owner, and composes
    the Challenge's own research service.
  - Graphite's operation ids are `graphite-<run>-<tool>`, so sessions never
    collide in one miner campaign.
  - File: `graphite/miner_path.py`.
- **GRAPHITE-D20, pods and the session's shape.**
  - One proposal is one pod of 30 minutes: start-up 15 (the rented runner's
    900 s), job 10 (the contract's `worker_deadline_seconds`) and export 5
    (pod_control's default).
  - A session has 12 pods (360 minutes, the plan's upper estimate of USD 3).
  - The pods use EV4's pinned image, A40 Secure, the 0.49 rate ceiling and
    disk price and the 0.25 cleanup reserve, all read from `pod_control`. The
    account balance floor is the operator's private configuration
    (`~/.runpod/campaigns.json`, `balance_floor_usd`, POD-LEDGER-PRIVATE-01),
    read only at launch and never recorded; without it a launch refuses
    before any provider call.
  - Lifecycle, ownership tags, lost-create recovery and verified termination
    come from the operator RunPod layer (GRAPHITE-D32; it was `carbon.compute`
    until OWNER-MINER-COMPUTE-LINK-ONLY-01 removed that).
  - Only JAX recipes are served, as in the GPU practice lane. A PyTorch recipe
    is refused, typed, and is not a finding.
  - Files: `graphite/pods.py`, `graphite/experiment.py`.
- **GRAPHITE-D21, the proposal tool and the rebuild check.**
  - The Constructor's `graphite_run_proposal` carries data only.
  - Carbon compares nine fields of what the pod built with its own
    computation (`experiment.REBUILT_FIELDS`). Any difference is a
    `REBUILD_MISMATCH` finding (`OTHER_SIGNAL`), and the proposal is not
    scored.
  - A proposal refused by the gate is an `UNREBUILDABLE` finding.
  - Findings reach the controller (`phase3.sync_findings`), where they block
    any later expansion.
  - Files: `graphite/roles.py`, `graphite/experiment.py`, `graphite/phase3.py`.
- **GRAPHITE-D22, the baseline and the frozen rule on development material.**
  - Each session runs a baseline once, on its first pod. By default this is
    the battery scaffold, the unexecuted template every miner starts from.
  - Each proposal is scored and compared with it by the frozen gates and
    score and rule v2's paired comparison, on public PRACTICE only.
  - The baseline is a provisional engineering default, not the B1 study
    population, which stays science-reserved (plan §9).
  - File: `graphite/phase3.py` (`session_brief`).
- **GRAPHITE-D23, the stall rule's automation.**
  - A stall is 5 consecutive scored proposals since the last `IMPROVEMENT`
    that are not an `IMPROVEMENT`.
  - At the limit Carbon records one `BUILD_STALLED_AGAINST_BASELINE`
    observation per run.
  - At the session's end the provider consumes it and moves the Constructor
    up one rung for its next session.
  - Compile failures are not escalated automatically.
  - Files: `graphite/experiment.py`, `graphite/phase3.py`.
- **GRAPHITE-D24, delivery.**
  - Carbon's rule picks the proposal to bundle: the eligible `IMPROVEMENT`
    with the lowest score. The agent's own selection is recorded beside it.
  - Ablations remove each change from the baseline one at a time, while pods
    remain.
  - The write-up is generated from the records; no Writer model runs in
    phase 3.
  - The clean rebuild checks digests. Numerical reproduction is
    `NOT_JUDGED` with tolerance `HUMAN_INPUT`.
  - File: `graphite/delivery.py`.
- **GRAPHITE-D25, keys, cancellation and crashes.**
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
- **GRAPHITE-D26, the Constructor's 150-call session** (OWNER-GRAPHITE-03
  amendment, 2026-10-02: "up the plan to 150").
  - A Constructor session (one research epoch) may make up to 150 model
    calls, `roles.CONSTRUCTOR_SESSION_TURNS`. It was capped at the shared
    48, while the plan expects about 150 turns.
  - Mechanism: `research_loop.run_epoch` takes an optional
    `max_provider_calls`, accepted only with a role's `instructions` and
    `tools` (as the GRAPHITE-D18 repair is) and recorded in the epoch plan.
    Omitted, the shared `research_agent_policy.MAX_PROVIDER_CALLS` (48)
    stands and the plan is byte-identical, so frozen studies such as the
    battery agent-campaign pre-registrations are unchanged.
  - `Phase3Provider` passes 150 to `run_epoch` and uses it as the run
    ledger's `provider_attempts` cap. `GraphiteProvider` itself is
    unchanged: phase-1 and phase-2 sessions keep their recorded shape.
  - The grant's `max_runtime_s` becomes 150 × 120 s + 12 × 1,800 s =
    39,600. The ceiling, `worst_case_run_cost` and pod budget are unchanged.
    The 1.95 token share still binds first on an expensive rung (40 calls on
    the fourth rung).
  - Files: `graphite/roles.py`, `graphite/phase3.py`,
    `development_session/research_loop.py`, the phase-3 grant and its README.
- **GRAPHITE-D32, phase 3's pods after the link-only decision**
  (OWNER-GRAPHITE-04, 2026-10-03).
  - OWNER-MINER-COMPUTE-LINK-ONLY-01 (#511) removed the RunPod provisioning
    layer from `carbon.compute`, which phase 3's `RunPodPods` was built on.
    Its LINKONLY-D1 keeps operator scripts on Carbon's own RunPod account.
    Asked how phase 3 should get GPUs, the owner chose "Carbon's own RunPod".
  - The layer phase 3 uses (adapter, provisioning service, store, accounting
    bound, reconciler and its CLI) is restored unchanged in behaviour under
    `scripts/dev/exam_design/runpod/operator_compute/`, beside `pod_control`.
    It is operator-side only: nothing under `carbon/` names a provider API
    (the #511 scan test still passes), and only phase 3's runner imports it,
    as it already imports `pod_control`.
  - Pods run on Carbon's account with Carbon's key under the phase-3 grant,
    never a miner's key. Nothing on the miner path changes.
  - The independent reconciler is now
    `python -m scripts.dev.exam_design.runpod.operator_compute reconcile
    --root "$ROOT/pods/compute" --runpod-key-file FILE`.
  - Tests: the retired layer's tests, restored against the new path
    (`test_graphite_operator_runpod.py`), and phase 3's live-backend test.
  - Files: `scripts/dev/exam_design/runpod/operator_compute/`,
    `graphite/pods.py`, `graphite/phase3.py`.
- **GRAPHITE-D33, the Constructor's parallel-call rule** (owner approval,
  2026-10-03; recorded in `.agent/decisions/2026-10-03-GRAPHITE-D33.md`).
  - Live session 1 (`graphite-913bf1889a6db2d1`) ended `harness_error` on
    turn 1: the model returned three tool calls despite
    `parallel_tool_calls: false`, and Graphite ran the loop under the
    historical rule.
  - The Constructor now runs under the loop's existing `PARALLEL_CALLS`
    (`roles.PARALLEL_RULES`, passed by `GraphiteProvider._epoch` and
    `Phase3Provider._epoch`). The first call runs, the rest are refused and
    journalled, and three such turns in a row stop the session `STOPPED`.
    Other roles keep the historical rule.
  - The Constructor's prompt states the rule
    (`research_agent_policy.one_call_per_turn`), and the dry run opens with
    live session 1's three-call turn.
  - `operation_id` needed no change: the miner path supplies it, and `{}` is
    the exact argument set of the three tools.
  - Files: `graphite/roles.py`, `graphite/provider.py`, `graphite/phase3.py`,
    `development_session/research_agent_policy.py`.
- **GRAPHITE-D34, the Constructor's whole context window, a 600 s timeout,
  and phase 3 on `engy-chat`** (owner, 2026-10-04: "max it out"; recorded in
  `.agent/decisions/2026-10-04-GRAPHITE-D34.md`).
  - Live session 2 (`graphite-d90a8ccfd603cf6a`) stopped `context_ceiling`
    after 2 calls: every Graphite session ran at `DEFAULT_SETTINGS`, whose
    admission ceiling is 61,440 tokens, and turn 1's five results (about
    69 KB) after a reported 10,607-token turn passed it.
  - The Constructor now opens with its model's whole published context, up
    to `select`'s 1,048,576 (`roles.MODEL_SETTINGS`, from
    `roles.ENGY_CONTEXT_TOKENS`, Engy's list read 2026-10-04), and a 600 s
    timeout. Output stays 2,048 tokens and reasoning `low`. A model with no
    recorded context is refused before anything opens. Other roles keep
    `DEFAULT_SETTINGS`.
  - Phase 3 opens its sessions on `engy-chat` (`phase3.ADAPTER`): Engy's
    Messages endpoint reports no `x_engy.charged_micro`, so every call on
    `engy-anthropic` kept its full reservation.
  - Prospective: a recorded session resumes with the selection its record
    froze, so a session opened before this change replays byte-identically.
  - At full reservation the 1.95 token share holds 41 calls on the first
    rung and 10 on `glm-5.2`; a `kimi-k3` call (USD 2.0647) cannot be
    admitted. On `engy-chat` calls settle at their reported charge. See the
    grants README.
  - Files: `graphite/roles.py`, `graphite/provider.py`, `graphite/phase3.py`,
    the phase-3 grant README.
- **GRAPHITE-D35, the phase-4 Attacker's whole context window** (owner,
  2026-10-05, relayed by the Test Lead: "yes for attacker budget"; recorded
  in `.agent/decisions/2026-10-05-GRAPHITE-D35.md`).
  - D34's mechanism, reused: `roles.WHOLE_CONTEXT_ROLES` names the
    Constructor and the Attacker, and both get the same per-model table in
    `roles.MODEL_SETTINGS`. On `glm-5.2` an Attacker session opens with
    262,144 input tokens and a 600 s timeout on `engy-chat`. Other roles keep
    `DEFAULT_SETTINGS`; a recorded session resumes with its recorded
    selection.
  - The grant is unchanged: at full reservation the Attacker's 1.93 token
    allowance holds 10 `glm-5.2` calls (40 before); a `kimi-k3` call (USD
    2.0647) cannot be admitted.
  - `phase4 run --dry-run` and `phase4 prelive` print the `attacker_model`
    block.
  - Files: `graphite/roles.py`, `graphite/provider.py`, `graphite/phase4.py`,
    `graphite/phase4_prelive.py`.

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
- Running the same command again resumes a session that has not ended (a
  process that died mid-session). A session that ended (`succeeded`,
  `failed` or `cancelled`) is terminal: the same command only prints its
  recorded end again. A `failed` session with code `reconciliation_required`
  is never resumed: run `reconcile` (it terminates and settles every pod the
  session may have left and exits 0 when none is live), read `status` (each
  pod's booked amount and basis in `pod_charges`), and make any further
  attempt a new `--session N` within the grant's permitted runs. `run` and
  `status` print this as `next_step` (GRAPHITE-RUNNER-USABILITY-01).
- `run` exits 4 on any end other than `succeeded`.
- Keys go by file path: `--credential-file PATH` (owner-only, as phase 4) and
  `--runpod-key-file PATH`; the `--credential-env` and `--runpod-key-env`
  forms remain for older launchers. `python -m carbon.agent_campaign.graphite
  run-checked --phase 3 ...` runs the gates, the launch and the post-run
  `reconcile` and `status` in order, with key files only.

**Limitations.**

- No live session has run. Token, pod and time figures are planning
  estimates until the first one.
- A Constructor session makes at most 150 model calls (GRAPHITE-D26), the
  plan's "about 150 turns". On a dear rung the run's 1.95 token share stops
  it sooner (about 40 calls on the fourth rung).
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

### Phase 3 literature follow-up (2026-10-02)

**Owner approval.** The owner answered "Yes" to the proposed follow-up: phase-3
sessions read the real phase-2 method cards, offered checked cards by default,
and the Planner records next-level proposals that widen nothing.

**The gap it closes.** `GraphiteProvider` defaulted to `FIXTURE_INDEX`, the
three synthetic phase-1 cards, so phase-3 sessions never saw a phase-2 card.

**Built** (conditional closeout: it takes effect when its PR passes automated
acceptance and merges, after #504). No live model was called, no pod was
started, no key was read and nothing was spent.

- `phase3 run --literature-snapshot PATH` loads a frozen phase-2 snapshot.
  - The session record's `literature` block pins the snapshot file's digest
    (its address), the snapshot's index digest and label, the offer policy,
    the number of offered cards, any unchecked card offered, and the digest
    of the offered set.
  - A resume whose snapshot or policy differs is refused before anything is
    touched (`phase3.check_resume`, reason
    `literature_snapshot_changed_since_the_session_opened`). The provider
    also refuses it on its own: the run ends `session_record_mismatch` /
    `literature_snapshot_changed` before any model call.
  - Without the flag, a live run is refused
    (`live_run_needs_a_literature_snapshot`). The dry run keeps the phase-1
    fixture, and its record says so (`source.kind:
    PHASE1_SYNTHETIC_FIXTURE`).
- **Checked cards by default.**
  - Snapshots are now `carbon.graphite.literature-snapshot.v2`. Each records
    `card_status`, every indexed card's check status at snapshot time, which
    must agree with the card's own provenance text.
  - A session is offered only cards whose latest check of that exact card is
    `CORRECT` (`HUMAN_CHECKED_CORRECT`).
  - `--allow-unchecked-cards` also offers `UNCHECKED` cards. `lit_search` and
    `lit_card` then mark each result's `check_status`, an unchecked card
    carries an `UNCHECKED` note, and the session record lists the unchecked
    cards offered.
  - A card a person rejected never entered the snapshot. A card naming
    protected material is withheld from the snapshot, and the index refuses
    one.
  - With no checked card, the index is empty. Every literature result says
    `index_empty`, and the session record and `phase3 status` carry
    `empty: true` and a note. Nothing falls back to the fixture.
  - A v1 snapshot still loads; its cards count as `UNCHECKED`.
- **Next-level proposals.**
  - New module `graphite/next_level.py`, and a new closed tool
    `graphite_propose_next_level`. The Planner and the Constructor are the
    only roles that hold it.
  - The arguments are checked:
    - the capability (1 to 300 characters);
    - 1 to 8 source card ids, each offered to this session;
    - a contract dimension from `capability_registry.Dimension`;
    - the contract's capability id, which must exist in that dimension and
      must not be `rebuildable_development`, or an empty string when the
      contract does not name the capability;
    - why it is outside the contract;
    - what Carbon would need to reconstruct it.
  - The record carries the recorded battery contract (`challenge`,
    `contract_digest`, `record_sequence`), the cited entry's status, the
    source cards with their check status, and the literature digest.
  - Its status is `PROPOSED`. It is written once under
    `runs/<run>/next-level/`, at most 8 per run, and carries an authority
    block saying it widens nothing.
  - `phase3 proposals --root DIR` lists them. A run's bundle
    (`carbon.graphite.phase3.pr-bundle.v2`) carries the run's proposals in
    `next-level-proposals.json`, and the clean rebuild ignores them.
  - A proposal never widens the construction surface, never calls
    `record_expansion`, never writes an expansion record, and never changes
    a permission profile, a role's tools or a score.
- **The Constructor's brief** lists the offered cards (id, title, check
  status), at most 100. The Constructor holds `lit_card` only, so the brief is
  how it learns which ids exist. Phase 3 refuses a brief whose literature is
  not the session's own.

**Tests.**

- `tests/cpu/test_graphite_phase3_literature.py`: 21 tests:
  - snapshot status recording, and `phase2 snapshot` naming the file and its
    count of CORRECT cards;
  - checked-only filtering;
  - v1 snapshots;
  - a forged status;
  - protected cards withheld;
  - the policy invariant;
  - snapshot pinning in the session record;
  - unchecked opt-in marking;
  - the empty index in the record and in `status`;
  - the fixture recorded for a dry run;
  - a stale brief refused;
  - the resume refusal at the runner and in the provider;
  - the runner's literature refusals;
  - a dry run with a snapshot;
  - proposal validation, writing and listing;
  - the Planner-only tool;
  - a proposal never changing the contract, permissions or score (bundle
    included);
  - the Constructor refused the tool;
  - injected card text triggering no proposal and no tool change.
- `tests/cpu/test_graphite_phase3_literature_mutations.py`: 7 protections,
  each switched off in turn:
  - the checked-only filter;
  - unchecked marking;
  - digest pinning in the provider;
  - digest pinning in the runner;
  - a cited capability outside the contract;
  - a planted widening when a proposal is written;
  - the Planner-only manifest.
- `tests/cpu/test_graphite_phase3.py`: the runner-refusal test now passes a
  snapshot.

**Engineering decisions** (delegated, recorded under
`.agent/DELEGATED_DECISION_PROTOCOL.md`; a lead may supersede any):

- **GRAPHITE-D28, snapshot pinning and no live fixture.**
  - Of the two approved options, a live `phase3 run` without
    `--literature-snapshot` is refused, and the dry run keeps the fixture.
  - Why: a paid session on three synthetic cards spends the grant on a
    literature layer that is not there. That is the gap this follow-up
    closes, and a silent default would reopen it. The dry run spends
    nothing, so it keeps the fixture and records it.
  - The pin is the snapshot file's own digest (its content address) plus the
    offer policy and the offered set. So a re-made snapshot, a later check or
    a changed flag is a different literature, refused on resume.
  - File: `graphite/phase3.py`, `graphite/provider.py`,
    `graphite/literature.py`.
- **GRAPHITE-D29, check status in the snapshot.**
  - The snapshot records each card's status when it is made, so a session
    pins checks as well as cards, and the snapshot file stays the one thing
    copied to the run host.
  - A check made after the snapshot reaches a session only through a new
    snapshot.
  - The recorded status must agree with the card's provenance text, which
    the index digest already covers.
  - Only `CORRECT` counts as checked. `EXTRACTION_ERROR` and `NOT_RELEVANT`
    cards never enter a snapshot.
  - Files: `graphite/method_cards.py`, `graphite/literature.py`,
    `graphite/tools.py`.
- **GRAPHITE-D30, next-level proposals.**
  - The contract a proposal is checked against is the recorded battery
    construction contract (Level 0's), from `experiment.recorded_contract`.
  - The Planner and the Constructor hold the tool. The Planner's came with
    the approved design. The Constructor's was added on 2026-10-02 on the
    owner's instruction ("Yes add it"). Phase 3 runs the Constructor, so a
    phase-3 session can now write proposals itself. Every other role is
    refused at the manifest.
  - A Constructor's proposal follows the same rules as the Planner's: it is
    validated, write-once and `PROPOSED`, and it widens nothing. The record
    carries `role: constructor`.
  - Files: `graphite/next_level.py`, `graphite/roles.py`, `graphite/tools.py`,
    `graphite/provider.py`, `graphite/delivery.py`, `graphite/phase3.py`.
- **GRAPHITE-D31, the Constructor's catalogue.** The brief lists up to 100
  offered cards. The rest stay readable by id, and the count not listed is
  stated. File: `graphite/phase3.py`.

**Running phase 3 live with the literature** (replaces the `run` line above):

```
# Where the phase-2 root is ($P2ROOT): a person checks cards, then snapshots.
python -m carbon.agent_campaign.graphite.phase2 cards --root "$P2ROOT" --unchecked
python -m carbon.agent_campaign.graphite.phase2 check --root "$P2ROOT" \
    --card arxiv-XXXX.XXXXXvN --checker NAME --verdict CORRECT
python -m carbon.agent_campaign.graphite.phase2 snapshot --root "$P2ROOT"
# -> {"snapshot": "sha256:<HEX>", ...}; the file is
#    $P2ROOT/backfill/cards/snapshots/<HEX>.json. Copy it unrenamed: its name
#    is its digest, and phase 3 refuses a file whose name does not match.
python -m carbon.agent_campaign.graphite.phase3 run --root "$ROOT" \
    --grant docs/development/graphite/grants/GRAPHITE-GRANT-PHASE3.json \
    --credential-env ENGY_API_KEY --runpod-key-env RUNPOD_API_KEY \
    --miner-profile PROFILE.json --miner-campaign CAMPAIGN_ID \
    --code-ref "$REF" --session 1 \
    --literature-snapshot "$SNAPSHOTS/<HEX>.json"     # [--allow-unchecked-cards]
python -m carbon.agent_campaign.graphite.phase3 proposals --root "$ROOT"
```

Sessions 2 and 3 resume or open with the same snapshot and policy. A
different one is refused for a session that has already opened.

**Owner decision, 2026-10-02: the first live sessions run on unchecked cards.**
Asked whether to check cards on the WSL host first or to run with unchecked
cards, the owner answered "B". So the first live phase-3 sessions run with
`--allow-unchecked-cards`, on a snapshot taken after the live phase-2 triage
finishes. Each unchecked card is marked `UNCHECKED` in every tool result and
in the session record. Because sessions 2 and 3 must keep the policy session
1 opened with, all three sessions of this grant use it. A proposal citing
unchecked cards records that status on each source card. People still check
cards (`phase2 check`); a later grant can run checked-only.

**Limitations.**

- No live session has run, and no snapshot from a live backfill has been
  checked by people yet. Until one is, the default run is offered an empty
  index.
- Keyword search only; no embeddings.
- The human check is a guard, not authentication (GRAPHITE-D14).
- None of this is scientific, security or production qualification.

**Open owner decisions** (none blocks the build):

- acting on any proposal: widening a level is the owner's decision under the
  reconstruction rule, and ships with Carbon's reconstruction of the widened
  surface.

## Phase 4: the Attacker, the general attack engine (build)

**Owner decision:** OWNER-GRAPHITE-ATTACKER-01 (2026-10-04;
`.agent/decisions/2026-10-04-OWNER-GRAPHITE-ATTACKER-01.md`), recorded again as
OWNER-GRAPHITE-TEST-WAVE-01 §2 (carbonphysicsai/Carbon#556). A general,
challenge-neutral attack engine, driven by Graphite's Attacker role, with its
first adapter at battery Level 0, under the live grant GRAPHITE-GRANT-PHASE4.

**Scope of this slice (AT-E): the session driver, the grant and the records.**
The challenge-neutral engine (the neutral core, the per-Challenge adapters,
analysis, verify, the knowledge store, report and benchmark) is built by the
other slices in `carbon.agent_campaign.attack`. This slice is the phase-4
session driver (`carbon/agent_campaign/graphite/phase4.py`) and its grant.

- `AttackerProvider(Phase3Provider)` inherits the v2 session-limits rule (no
  call cap; the grant's money cap and elapsed limit bind), compaction and the
  parallel-call rule, and drives the Attacker role through `AttackerTools`
  (the code-run wall allowance, from the adapter, enforced before dispatch).
  Its brief comes from the adapter alone (refused typed when a session
  surface member is missing; `start` refuses a brief that is not its
  adapter's). An Attacker proposes no construction: no baseline, no pod, no
  delivery, bundle or stall escalation, and its frozen session record says so.
- Carbon's side runs through the engine's published interfaces:
  `analysis.attempts` → `map_to_families` → `verify.verify` → for a BREACHED
  verdict `verify.record` → `controller.record_finding` (stops expansion) →
  `knowledge.AttackStore` (each verdict with its own outcome) →
  `report.family_report` from the session's verdicts and `benchmark.b2`
  against the adapter's deterministic runs, under the store snapshot pinned
  before the session.
- Carbon's verify-pod rebuild is a declared NOT_RUN seam in phase 4: no pod
  is launched; the grant keeps the pods' share reserved.
- `run --dry-run` produces the coverage report and B2 with a scripted model
  and `ScriptedPods`, zero spend. The live run path requires
  GRAPHITE-GRANT-PHASE4; it is implemented and tested with fakes but **not
  executed** (OWNER-GRAPHITE-ATTACKER-01 §5).
- `GRAPHITE-GRANT-PHASE4`: ceiling USD 10.50, cleanup 0.25, worst-case run cost
  3.41 (six verify pods ≈ 1.48, the token share 1.93 ≈ 40 glm-5.2 calls),
  three runs, one concurrency, 15,600 s runtime, expiring 2026-12-31.
  Derivation in `docs/development/graphite/grants/README.md`.

**Mutations shown load-bearing:** a reintroduced call cap (in the dry run or
the loop arguments); a grant ceiling that no longer covers three runs and
cleanup; a code run over the adapter's wall allowance; a brief naming
protected material; a real Verdict read as no finding; infrastructure stored
as a hold or a near miss; battery's identity substituted for a missing
adapter surface; a brief not checked against its adapter; B2 recorded without
the pinned snapshot; the Constructor's stall rule frozen into the Attacker's
record. Expansion after a finding is refused through the controller (the
breach test).

**Not in this slice:** the engine modules, the battery Level 0 adapter, the
synthetic second Challenge, and any live run. See
`docs/development/graphite/PHASE4_ATTACKER.md`.

**Integration round 1 (phase 4).** The coverage report now names every Track A
check. `coverage.checks` (schema `carbon.graphite.attacker-coverage.v3`) lists
all eight checks, each with the run families and NOT_RUN seams the adapter
declares for it. A check covered only by seams, such as battery's
`fresh_attack_confirmation`, is therefore still named. Rows that lost their
check are listed, and a row whose check contradicts the adapter is refused.
The engine report's seam rows still carry `check: None` until AT-C's report
repair lands; the engine-path tests fail on that until then.
