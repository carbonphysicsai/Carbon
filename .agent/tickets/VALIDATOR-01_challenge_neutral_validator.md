# VALIDATOR-01 — One challenge-neutral validator, battery as the first adapter

**Status:** slice 1 merged in bounded DEVELOPMENT scope (#559, `de4bf912`).
Slice 2 implemented in bounded DEVELOPMENT scope, awaiting review.
**Authority:**
- OWNER-GRAPHITE-TEST-WAVE-01 §3: "validator build needs to start soon and
  shouldn't be hard";
- OWNER-GRAPHITE-TEST-WAVE-02 §3 (#564): the pod worker-timeout rule;
- the Launchpad production work list, item 7 (a real submission and
  validation endpoint);
- the Test Lead's brief and its reviews of slices 1 and 2, 2026-10-04.

**Executor:** the Carbon Validator session.
- Slice 1: branch `claude/validator-core`, from main `5d963845`.
- Slice 2: branch `claude/validator-scoring`, from main `f49ac6d9f` (after
  the Attacker, #563).

## Outcome

One validator scores any registered Challenge's submissions against that
Challenge's frozen rule. Each Challenge plugs in one `ChallengeAdapter` per
registered construction contract. Battery is the first adapter; Codex writes
the cooling and motor adapters against the interface below.

Scores are DEVELOPMENT only: no weights, rewards or chain action (OD-4b).
Nothing here is scientific, security, network or production qualification.

## Interface v1 (frozen for slice 1; for the cooling and motor adapters)

Package: `carbon/challenge_validator/`.

### Submission (`interface.Submission`)

A frozen dataclass, built only by a transport that has authenticated the
signer:

| Field | Type | Meaning |
| --- | --- | --- |
| `hotkey` | str, 1–128 printable | the identity the transport verified, never a typed field |
| `receipt` | dict, ≤ 16 keys; values int, str ≤ 128 or None | transport receipt: `sequence`, `digest`, `block` |
| `challenge_id` | str | the Challenge token (`ChallengeContract.token`) |
| `challenge_version` | str | the contract version |
| `strategy_json` | str or bytes | the strategy exactly as received |
| `contract_digest` | str | `sha256:` + 64 lowercase hex |

### What the validator does before any adapter sees a submission

`dispatch.Validator.evaluate(submission)` does the following, in order. Every
refusal is typed, recorded in the operator ledger, never scored, and touches
no adapter state.

| Check | Refusal code |
| --- | --- |
| A `Submission` with well-formed transport fields | `malformed_submission` |
| A digest matching `sha256:[0-9a-f]{64}` exactly: no case folding, no whitespace | `contract_digest_malformed` |
| A digest some registered adapter serves | `contract_not_served` |
| `challenge_id` and `challenge_version` equal to the adapter's | `challenge_mismatch` |
| The strategy is at most the adapter's `max_strategy_bytes` (UTF-8 bytes) | `oversized_submission` |
| Strict UTF-8, with no lone surrogates | `strategy_not_utf8` |
| No byte-order mark | `strategy_bom` |
| Containers nest at most 32 deep | `strategy_nesting_too_deep` |
| No `NaN` / `Infinity` tokens, and no float overflowing to infinity | `non_finite_value` |
| No duplicate keys, at any depth | `duplicate_key` |
| Integers fit a signed 64-bit value | `integer_out_of_range` |
| Valid JSON | `strategy_not_json` |
| A JSON object | `strategy_not_object` |
| The strategy's `challenge_id` equal to the adapter's | `challenge_mismatch` |

A refusal carries only its code. It never echoes submitted content.

### ChallengeAdapter (`interface.ChallengeAdapter`, an ABC)

One instance serves exactly one contract digest.

Class or instance attributes:
- `challenge_id`, `challenge_version`: the registered contract's token and version.
- `contract_digest`: that contract's digest. At registration it must equal
  `capability_registry.contract(challenge_id).digest`, and the contract's
  version must match. An adapter cannot invent a contract.
- `max_strategy_bytes`: an engineering admission limit.
- `disclosure_fields`: the miner-outcome keys allowed beyond the required ones.

Methods:

| Method | Side | Contract |
| --- | --- | --- |
| `identities()` | both | Pinned material identities. Must include `contract_digest`, `rule_digest` and `implementation_digest`, each a `sha256:` digest. Never a private value. |
| `pinned()` | both | Provided by the base class: the three digests above plus `identities_digest`, a digest of the whole document. |
| `disclosure_budget()` | operator | The budget the Challenge's rule declares, or None. The validator never invents one. |
| `evaluate(admitted)` | miner | Admit and advance one `Admitted` submission (the parsed strategy, plus the transport fields); return the miner outcome. May raise `Unavailable(code, retry=...)` for refusals that are not recorded against the miner. A refused construction is an outcome (`INVALID_CONSTRUCTION`), not an exception. |
| `outcome(submission_id)` | miner | The allow-listed miner outcome. |
| `owner(submission_id)` | miner | The submitting hotkey, or None. The validator answers an outcome only to its owner. |
| `advance()` | operator | Advance queued work; return how much moved. |
| `score_record(submission_id)` | operator | Per-case predictions, errors and gate verdicts, and the rule and identity digests. Never miner-facing. |
| `sealed_roles()` | operator | Seed roles already committed for a batch outside the pool. |
| `prepare_batch(role, kind=..., **options)` | operator | Provided by the base class. Refuses `RESERVED_SEED_ROLES` and `sealed_roles()` with `ReservedRole`, then calls `_prepare_batch`. |
| `reference_jobs`, `ingest_references`, `open_pool`, `status` | operator | Batch references, pool opening, counts and identities. |

### The miner outcome contract (`interface.check_outcome`)

Checked on every adapter return:
- **Required:** `schema`, `submission_id`, `challenge` (`{id, version}`, the
  adapter's), `state`, `evidence` (starts with `DEVELOPMENT`),
  `qualification: false`, `reward: false`.
- **States:** `ADMITTED`, `RECONSTRUCTED`, `SCORED`, `INVALID_CONSTRUCTION`,
  `RECONSTRUCTION_FAILED`, `FAILED_INFRA`, `FAILED_INFRA_EXHAUSTED`.
- **Optional:** `failure` (`{code, issues}` only), plus the adapter's
  `disclosure_fields`.
- **Finite JSON only.**

An outcome that breaks any of these is never returned. The result is
`FAILED_INFRA` / `outcome_contract_violation`. Any other adapter exception is
`FAILED_INFRA` / `adapter_failure`, and its text is never echoed.

### The result envelope (`carbon.challenge-validator.result.v1`)

`{schema, kind, code, pinned, outcome, evidence: "DEVELOPMENT",
qualification: false, reward: false}`, plus `retry` when `kind` is
`UNAVAILABLE`.
- `kind` is one of `OUTCOME`, `REFUSED`, `UNAVAILABLE` or `FAILED_INFRA`.
- `pinned` is the adapter's `pinned()`, present once a submission has
  resolved to an adapter.
- `outcome` is the adapter's outcome, unchanged.

### Surfaces

- `dispatch.Validator` is miner-facing. Its only public methods are
  `evaluate`, `outcome(contract_digest, submission_id, hotkey)` and `served`.
- `dispatch.Operator` is operator-only. It holds `score_record`,
  `prepare_batch`, references, `advance`, `status`, `attempt_counts` and the
  ledger. It is never handed to a transport.

### Ledger (`ledger.AttemptLedger`)

An owner-only SQLite file (owner-only directory and file, refused otherwise).
Every attempt is recorded, refusals included:
- kind, code and time;
- hotkey and digest presented (over-long values by digest only);
- receipt (a malformed one by digest only);
- a hash over every received field;
- submission id and state.

The ledger never stores the strategy. Operator refusals, such as a reserved
seed role, are recorded too. `attempt_counts(hotkey)` gives totals by kind
and by contract (Track A family 8).

### Reserved seed roles

`RESERVED_SEED_ROLES` is `ev5-confirmation` (EV5's sealed batch, journal
sequence 14) and `graphite-confirmation-v1`. Cooling's and motor's
confirmation roles join it by record. Separately, any role an adapter reports
as sealed outside the pool is refused.

### What a cooling or motor adapter must supply

- A registered construction contract in `capability_registry.CONTRACTS`. Today
  only Burgers and battery are registered, so cooling and motor first need
  their own contract registration (Codex's tickets).
- A frozen exam rule with a `rule_digest`, and an implementation digest.
- A reconstruction backend, reference ingestion and a batch store.
- An allow-listed miner outcome and an operator score record.
- Its sealed-role report.

## Working decisions (delegated engineering scope)

- **VAL-D1 — package name.** `carbon/challenge_validator/`, not
  `carbon/validator/`. `carbon.validator` / `carbon/validator` are retired
  legacy paths (`.agent/CODE_AUTHORITY.toml`, B-01E). The Test Lead accepted
  this.
- **VAL-D2 — battery stays byte-identical (KEEP + WRAP).** No battery file
  changes. The adapter calls `deployment.evaluate` and
  `BatteryValidator.outcome` as they are. Its operator methods take the
  deployment's writer lock.
- **VAL-D3 — battery's intake, worker, `operate.py` and the validator service
  stay on battery's path in slice 1.** Moving them onto `Validator` changes one
  observable: a stale or unknown digest gets `contract_not_served` in the
  ledger, where today it is recorded `INVALID_CONSTRUCTION` /
  `contract_refused`. The ledger exists now, so the later switch changes where
  that refusal is recorded, not whether. A test records the difference.
- **VAL-D4 — the battery strategy limit is the transport's `MAX_BODY`
  (65,536 bytes).** A battery strategy arrives inside one transport body, so
  no strategy battery accepts today is larger.
- **VAL-D5 — the parsing limits are engineering limits, not scientific
  values:** depth 32, signed 64-bit integers, 128-character identity fields,
  16 receipt keys.
- **VAL-D6 — the battery score record re-derives, then checks.**
  `BatteryAdapter.score_record` recomputes the per-case rows from the stored
  predictions with `exam.evaluate`. It refuses (`ScoreReplayMismatch`) unless
  they reproduce the stored aggregate exactly.
- **VAL-D7 — battery's sealed roles come from the public seed journal:** a
  journal batch commitment whose fingerprint is not in the pool store. Only
  the journal's public metadata (role and fingerprint) is read, never a
  batch's plaintext. One consequence: if `prepare_batch` crashes between its
  journal commit and its store record, that role reads as sealed afterwards.
  This fails closed, and the operator re-prepares under a new role.
- **VAL-D8 — outcome reads need the owner's hotkey.** Another hotkey's
  submission and a missing one get the same `unknown_submission`, so the read
  is no oracle for which submissions exist.

### Slice 2

- **VAL-D9 — no silent Challenge default in shared code.** A caller that names
  no scoring gets the only registered one. Once a second is registered, every
  unnamed call is refused (`challenge_scoring_must_be_named`). This keeps the
  Attacker's existing calls (`experiment.admit(strategy, seed)`,
  `recorded_contract()`, `FrozenRule(root)`, `pod_phase.built_record`)
  working unchanged without a battery literal in Graphite.
- **VAL-D10 — battery's bytes are unchanged.** These stay exactly as before:
  - the build record, data paths, worker deadline, frozen rule and baseline;
  - the brief's challenge and objective text;
  - every refusal code battery returned
    (`not_the_battery_development_challenge` is battery's own
    `wrong_challenge_code`).

  Two shared-code codes became neutral: `phase3_challenge_not_served` (was
  `phase3_serves_battery_development_only`) and
  `miner_campaign_is_not_the_sessions_challenge` (was
  `miner_campaign_is_not_battery_development`). `miner_path` and the
  observation check keep their id-and-version comparison.
  `check_battery_development` is renamed `check_challenge`.
- **VAL-D11 — what the pinned pod image allows: no separation.** The EV4 study
  image (`pod_control.IMAGE`) runs the bootstrap, the supervisor (`pod_phase`)
  and the program as one non-root user. Bootstrap notes that only `/tmp` is
  writable, and the reconstruction-worker family runs as `USER 65532`. So the
  supervisor cannot drop the program to another uid, and the program can
  reach `failure.json`, the `/status` server and the supervisor itself. Every
  pod-side signal is evidence only.
  - Host authority is Carbon's own poll times of the phase: `HostTiming`'s
    lower and upper bounds, plus the pod lifecycle.
  - A supervisor report is admissible only for an image listed in
    `pod_outcome.SEPARATED_IMAGES`, a host-side record. That list is empty,
    and the pod's own claim never adds to it.
  - The admissible path is implemented and tested so that Levels 4-5 (where
    participant code runs) need only a verified image record.
- **VAL-D12 — how the host confirms a timeout.**
  - **Confirmed:** the host's lower bound on the phase's duration (last
    running poll minus first) is at least the declared worker seconds. That
    span includes Carbon's own compile and pin check, which run before the
    program, so the bound can over-credit by that pre-run time and never
    under-credit.
  - **Contradicted:** the upper bound (the end poll minus the last poll
    before running) is below the declared seconds. That is FAILED_INFRA, no
    retry, and an `OTHER_SIGNAL` finding (`POD_TIMING_DISAGREEMENT`) bound to
    the claim's digest and the host readings.
  - **Unconfirmed:** anything else. On a first attempt it still earns the
    retry, because the retry blames no one. On the second it is FAILED_INFRA.
- **VAL-D13 — program-failure attribution depends on the construction level**
  (the Test Lead's ruling, 2026-10-04, refining a first draft that made every
  pod program claim unattributed).
  - **The level's source.** It comes from the run's recorded permission
    profile: `phase3.recorded_level`, which uses the profile's level only when
    the run's recorded profile digest matches. It is never taken from the
    submission. Unknown or malformed means untrusted.
  - **Levels 0-3.** No participant code runs in the pod, and only Carbon's own
    trainer writes the claim. So it is admissible.
    - A program failure stays `CANDIDATE_FAILED` / `program`, as before.
      Otherwise a recipe that crashes the trainer would get infrastructure
      semantics (no penalty, retry or refund), which is the Track A selective
      crash/retry family.
    - A pod compile failure stays `FAILED_INFRA` / `compile`, also as before.
      The pod compiled after Carbon's host compiled the same recipe, so the
      failure points at the pod's environment.
  - **Levels 4-5, or an unknown level.** Participant code may run, and the
    claim is evidence only unless the image is in `SEPARATED_IMAGES`. A
    program or compile claim is `FAILED_INFRA` /
    `candidate_failure_unattributed`.
  - **Timeouts** follow the retry rule at every level, because host
    contention can cause one whoever wrote the claim.
- **VAL-D14 — the retry is an ordinary pod.** It gets its own intent
  (`<intent>-r1`), is admitted against the run's pod count and money cap
  before launch, and has its reservation, launch, terminate and settlement
  ledgered. Both attempts are typed in the ledger (`pod_attempt_typed`) and in
  the proposal record (`attempts`). A restart after any attempt closes the
  proposal `interrupted_not_rerun`, as before.

## Slices

1. **The neutral validator and the battery adapter** (this PR):
   `carbon/challenge_validator/{interface, strict_json, dispatch, ledger,
   battery}.py`, `tests/cpu/test_challenge_validator_contract.py`,
   `tests/cpu/test_challenge_validator_battery.py`, this ticket and a lessons
   entry.
2. **A neutral ChallengeScoring layer for Graphite, and the pod worker-timeout
   rule** (#559's successor, from main `f49ac6d9f`).
   - `carbon/challenge_validator/scoring.py`: `ChallengeScoring` and its
     registry, the neutral `admit`, `rebuild_differences`, `FORBIDDEN_DATA`.
   - `carbon/challenge_validator/battery_scoring.py`: `BatteryScoring`, with
     battery's build, frozen PRACTICE rule, data paths and baseline moved
     unchanged out of the Graphite modules.
   - Graphite delegates to the session's scoring: `graphite/experiment.py`
     (`recorded_contract`, `admit`, `FrozenRule`), `pods.py` (data paths, the
     worker deadline, `ship_list`), `pod_phase.built_record`, `phase3.py`
     (`check_observation`, `session_brief`, the provider) and `miner_path.py`
     (`check_challenge`). `FORBIDDEN_DATA` and `tools.protected` are kept.
   - `graphite/pod_outcome.py`: the timeout rule's order of authority, wired
     into `Experiment.run` with one retry.
   - Tests: `tests/cpu/test_challenge_validator_scoring.py` and
     `tests/cpu/test_graphite_pod_timeout.py`.
3. **Follow-up:** battery's intake, worker and validator service onto the
   neutral `Validator` (VAL-D3).

## Validation

- `tests/cpu/test_challenge_validator_contract.py`: 90 tests over a fake
  adapter on Burgers' registered digest. They cover:
  - strict parsing (24 hostile forms);
  - malformed, unserved and mismatched digests;
  - malformed transport fields;
  - non-echoing refusals;
  - the outcome contract;
  - infrastructure typing;
  - owner-only outcome reads;
  - the miner surface's method set;
  - pinned identities;
  - registration rules;
  - reserved and sealed roles;
  - per-hotkey attempt counts;
  - an owner-only ledger.
- `tests/cpu/test_challenge_validator_battery.py`: 10 tests on real
  exam-design references with `DirectBackend`. They cover:
  - byte-identical replay against `deployment.evaluate` on twin validators
    sharing one private root, through a first incumbent, two challengers, a
    rotation, finalist comparisons, a duplicate and two refused constructions,
    with stored submissions, scores, finals, predictions, models, batches,
    pool and incumbent equal row for row;
  - the stale-digest difference;
  - hostile strategies never reaching battery;
  - the score record reproducing the stored score, and refusing a tampered
    prediction;
  - no hidden case id, batch fingerprint or root commitment on any
    miner-facing result;
  - the rule changing the pinned identities;
  - reserved and sealed roles refused without a journal write;
  - `Unavailable` recording nothing in battery;
  - infrastructure exhaustion and a retried infrastructure failure.
- Battery's own suites run unchanged.
- `scripts/check_quality.py --base origin/main`: passed.
- Canonical, slice 1 (`CARBON_UV_GROUPS="chain archive science-jax science-torch mcp"
  ./scripts/dev/canonical.sh --focused` over both new suites and battery's
  validator daemon, deployment, intake, validator service, rule v2, carry-over,
  remote submission and intake end-to-end suites): 276 passed, pytest exit 0.

### Slice 2

- `tests/cpu/test_challenge_validator_scoring.py` (8 tests):
  - the registry, and refusal of unnamed calls once a second scoring registers;
  - battery unchanged through the port: data paths, worker deadline, recorded
    contract, the build by every route, refusal codes, the frozen rule and
    the brief;
  - protected data paths refused before any ship;
  - the challenge checks in `phase3` and `miner_path`.
- `tests/cpu/test_graphite_pod_timeout.py` (28 tests). They cover:
  - timeout then success: FAILED_INFRA, then scored once;
  - two confirmed timeouts: CANDIDATE_RESOURCE_EXCEEDED, never scored;
  - unconfirmed or missing host timing: never blamed;
  - a forged failure.json contradicted by host timing: FAILED_INFRA, no retry,
    and an OTHER_SIGNAL finding;
  - program and compile claims: unattributed;
  - an unseparated supervisor report stays evidence; a separated image's report
    is admissible;
  - the pod's own deadline, a launch failure, a retry refused by budget, and a
    restart;
  - the order-of-authority table;
  - the host-timing bounds;
  - `RunPodPods.wait` taking its readings from its own clock.
- Existing tests updated only where they pinned a renamed seam:
  - the two neutral refusal codes;
  - `pods.data_paths()`;
  - `check_challenge`;
  - the mutation tests that patch `check_observation`, `check_challenge`,
    `admit`, and the scoring port's `REBUILT_FIELDS`.
- `scripts/check_quality.py --base origin/main`: passed.
- Canonical, slice 2 at `d55563f43` (same groups). The run covers both new
  suites, slice 1's validator suites, the lessons log, every Graphite and
  Attacker suite and the Graphite miner-path service suite. **873 passed, 1
  failed.** The failure,
  `test_attack_battery_adapter.py::test_each_disabled_boundary_turns_its_guard_red[protected_marker_removed]`,
  fails identically on main `f49ac6d9f` (checked on a detached main checkout)
  and is fixed by #569.

## Invariants exercised

1 (no seed leakage), 3 (pinned evaluation), 4 (disclosure allow-list),
7 (infrastructure ≠ science), 8 (deterministic replay), 10 (no silent
rescore: battery's records are untouched), 21 (a score is bound to its
contract digest and is never compared across Challenges) and 24 (miners
submit declarative strategies; the validator holds the grade). Slice 2 adds
these:
- 7 for pod runs: a worker timeout is never a scientific failure, and a
  candidate is never blamed on ambiguous evidence;
- 6: the evidence rule is designed to hold where participant code runs;
- 2 and 1: protected data never ships to a pod.

## Maturity

SPECIFIED, IMPLEMENTED, TESTED (DEVELOPMENT). Not SECURITY_QUALIFIED. **This
work needs a dedicated security review before any production or public
exposure** (AGENTS.md §13). For slice 1 that covers the strict parser, the
ledger's custody, the operator/miner surface split and the adapter
registration. For slice 2 it covers:
- the pod evidence-authority rule;
- the host-timing bounds;
- the `SEPARATED_IMAGES` record;
- the forbidden-data guard;
- the bootstrap holding `RUNPOD_API_KEY` under the program's own uid. That
  is outside this ticket, but it matters at Levels 4-5.

The tests are not an audit. Not NETWORK_QUALIFIED. No LIVE, weights or
reward.

## Human input required

- Before any Level 4-5 pod work, two security-review items:
  - a verified `SEPARATED_IMAGES` record, or an image that separates the
    supervisor from participant code;
  - resolving the bootstrap's `RUNPOD_API_KEY`, which sits under the
    program's uid. The Test Lead raised this with the owner on 2026-10-04.
- Deploying the service on the dedicated server waits on the owner ordering
  it (work list item 7), outside this ticket.
