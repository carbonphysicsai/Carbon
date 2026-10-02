# GRAPHITE-01: Carbon's in-house research and testing agent

**Owner decision:** OWNER-GRAPHITE-01 (`.agent/DECISIONS.md`, 2026-10-02).
**Plan:** `docs/development/GRAPHITE_TESTING_AGENT_PLAN.md`.
**Status:** phase 1 implemented (conditional closeout: it takes effect when
the phase-1 PR passes its automated acceptance and merges, per
`.agent/DELIVERY_PROTOCOL.md`). Later phases are planned, and each needs an
owner spending grant.

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

**Open owner decisions** (each blocks only its own later phase):

- the per-phase spending grants, for phase 2 onward;
- the registered number of attempts after which a Constructor's builds count
  as stalled (plan §3);
- the Chutes adapter (C-MLP-03 §2).
