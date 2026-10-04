# VALIDATOR-01 — One challenge-neutral validator, battery as the first adapter

**Status:** slice 1 implemented in bounded DEVELOPMENT scope, awaiting review.
Slice 2 waits for the Graphite Attacker PR (`claude/graphite-attack-engine`).
**Authority:**
- OWNER-GRAPHITE-TEST-WAVE-01 §3: "validator build needs to start soon and
  shouldn't be hard";
- the Launchpad production work list, item 7 (a real submission and
  validation endpoint);
- the Test Lead's brief and slice-1 review, 2026-10-04.

**Executor:** the Carbon Validator session. Branch `claude/validator-core`,
from main `5d963845`.

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

## Slices

1. **The neutral validator and the battery adapter** (this PR):
   `carbon/challenge_validator/{interface, strict_json, dispatch, ledger,
   battery}.py`, `tests/cpu/test_challenge_validator_contract.py`,
   `tests/cpu/test_challenge_validator_battery.py`, this ticket and a lessons
   entry.
2. **A neutral ChallengeScoring layer for Graphite** (after the Attacker PR
   merges, from the new main). It removes the battery-only scoring from:
   - `graphite/phase3.py` (608–614, 679–695);
   - `design_search/experiment.py` (152–201 admit, 226–262 FrozenRule);
   - `pod_phase.py` (47–52);
   - `pods.py` (52–102);
   - `miner_path.py` (115–136).

   `FORBIDDEN_DATA` and `tools.protected` are kept. Coordinate with the Test
   Engineer, whose Attacker scores through `experiment.admit` today. Line
   numbers are as of `5d963845`; re-verify them on the new main.
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
- `scripts/check_quality.py --base origin/main`.

## Invariants exercised

1 (no seed leakage), 3 (pinned evaluation), 4 (disclosure allow-list),
7 (infrastructure ≠ science), 8 (deterministic replay), 10 (no silent
rescore: battery's records are untouched), 21 (a score is bound to its
contract digest and is never compared across Challenges) and 24 (miners
submit declarative strategies; the validator holds the grade).

## Maturity

SPECIFIED, IMPLEMENTED, TESTED (DEVELOPMENT). Not SECURITY_QUALIFIED. **This
work needs a dedicated security review before any production or public
exposure** (AGENTS.md §13): the strict parser, the ledger's custody, the
operator/miner surface split and the adapter registration. The tests are not
an audit. Not NETWORK_QUALIFIED. No LIVE, weights or reward.

## Human input required

None for slice 1. Deploying the service on the dedicated server waits on the
owner ordering it (work list item 7), outside this ticket.
