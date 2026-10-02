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
