## 2026-10-05 — RESEARCH-BUDGET-REFUSAL-TYPING-01: a ledger limit refusal is typed by whose limit it is

**Authority.** The Test Lead approved this on 2026-10-05 as an engineering
correctness fix; no owner approval is needed. It changes no score, reward,
weight, settlement, scientific value, threshold or gate, and no budget policy:
every limit binds exactly where it bound before. What changes is how a refusal
is typed and what it says. Invariant 7's principle holds: an infrastructure
failure and a non-infrastructure outcome stay distinct. The owner's direction,
relayed by the Test Lead the same day, applies: "a miner should only ever run
out of a budget they set themselves."

**Why it is needed.** On 2026-10-05, campaign e78349d4 had `research_trials`
3 of 3 used. Its next two practice tasks ended FAILED_INFRA / INTERNAL in
about 0.5 s with no operation row and no reason, which reads exactly like a
worker crash. The ledger's `_reserve` refused them with
`ValueError("miner budget: research_trials")`, and
`carbon/research/durable.py` `_NoRetry.execute` turned every exception into
INTERNAL.

**Decisions.**

1. **One typed refusal, raised by the ledger.**
   `research_ledger.LedgerRefusal` subclasses ValueError and keeps each
   historical message exactly, so every `except ValueError` and every text
   match reads what it always read. It carries `code`, `dimension`, `basis`,
   `used`, `requested` (including any final reserve the campaign asked to
   hold back), `ceiling` and `refused_at` (`reservation`, or
   `storage_check`). These are this campaign's own budget and use, which
   `status` already reports to its owner. No hidden or official value and no
   other owner's state.
   - Code `miner_ceiling_reached`, reused because it already means exactly
     "the campaign's own ceiling or its time bound". `research_loop`,
     Graphite's miner edition (`miner/budget.py`) and `RunLedger` stop with
     it. No new code is added.
   - Carbon's service capacity is `carbon_service_capacity`: Carbon's limit,
     never reported as the miner's.
   - `basis` names whose limit it is: `miner_launch_budget` (product),
     `development_grant`, `development_campaign` or `carbon_service`.
2. **Every refusal site covered.**
   - `CampaignLedger._reserve`, every capped dimension, money included:
     `miner budget: <dimension>`.
   - `CampaignLedger._reserve`, time: elapsed or grant time spent, a
     provider timeout that cannot fit, and a worker that cannot fit.
   - `CampaignLedger._reserve`: `carbon service capacity: <dimension>`.
   - `check_storage`: `miner budget: retained_bytes`.
   - `research_sequences`: `miner budget, sequence aggregate: <dimension>`,
     service capacity, and the three sequence and child time refusals.
   - `CampaignControl.checkpoint`: `original campaign deadline reached`.
     A controlled campaign meets its time here before `_reserve`. It is now
     `research_control.CampaignDeadlineReached`, still a DispatchStopped with
     that text, carrying the same record as `refusal`.
   - A clock that ran backwards is not a limit. It stays the plain
     ValueError with its historical text.
   - These stay plain ValueErrors because they are not limits: the
     concurrency guards (one numerical worker, unknown provider metering),
     replay and identity checks, and Carbon's own per-worker ceiling on
     non-research phases.
3. **Readers that checked the exact type accept the typed refusal beside
   ValueError** (`research_ledger.PLAIN_REFUSALS`). Every other subclass
   stays excluded, as before. The readers are:
   - `research_loop.miner_ceiling`;
   - `graphite/miner/budget.reserve_limit`;
   - the standard MCP door's `_pre_dispatch_stop`.

   Internal Graphite's `provider.limit_dimension` and its run-finish branch
   are unchanged. Its `RunLedger._reserve` already turns every ledger
   refusal it reads into `RunCapReached` by text, so the typed refusal never
   reaches those exact-type checks.
4. **The durable provider types it; everything else stays INTERNAL.**
   `_NoRetry` first asks the executor to type the exception
   (`refusal_outcome`); a missing hook, a declined or failing hook, or a reply
   of any other type keeps FAILED_INFRA / INTERNAL exactly as before.
   - `PublicResearchExecutor.refusal_outcome` handles the campaign's own
     ceiling. The task completes SUCCEEDED with outcome
     `MINER_CEILING_REACHED`, stored as its public result like
     `REQUEST_REFUSED` and `MINER_PROGRAM_FAILED` (LP-PROD-D).
   - That result holds the record and a `correction`: Carbon-written text
     over the record's own values.
   - Carbon's service capacity stays FAILED_INFRA, now typed
     `RESOURCE_LIMIT` rather than INTERNAL.
   - The B-07 wire enums and receipt fields are unchanged. No tool text,
     tools rule or role digest changes: the outcome is new information in a
     result, as `program_output` was (LP-PROD-D decision 2). The research
     tools, the MCP door and the Graphite miner path forward the public
     result unchanged.
5. **The correction says whose ceiling it is and how to raise it.**
   - For a product campaign it says the ceiling is the miner's own, set at
     launch in `budget.ceilings.<dimension>` (or `budget.elapsed_seconds`)
     on the `launch` operation, and that Carbon sets no ceiling of its own.
     A launched campaign's budget is frozen with it (`freeze` refuses any
     change), so the way to raise it is a new campaign with a larger value,
     or none.
   - A development campaign's correction names its development budget.
6. **Historical records keep their meaning.** Nothing is rewritten. Tasks and
   results retained before this read back unchanged, and a task that ended
   FAILED_INFRA / INTERNAL stays so.

**Where the 3-trial cap came from (e78349d4).** No Carbon-side code injected
it. The product launch path builds the budget only from the launch request:
- `runner.py` uses `miner_budget(request.get("budget"))`, which validates and
  never supplements.
- `ProductLaunch.__post_init__` refuses any budget that is not exactly what
  `miner_budget` returns.
- `manifest_fields` spreads only that budget.
- `research_campaign.py:678` deletes the development ceilings and deadline
  from every product manifest before adding the launch fields.

So `research_trials: 3` in that manifest is the value its launch request
set. This matches the executor's account. The test
`test_a_launch_records_only_the_budget_the_miner_set` holds the path.

**Audit: where a cap could reach a miner campaign the miner did not set.**
- `research_ledger.py:123` `DEVELOPMENT_CEILINGS` (`research_trials: 16`):
  Carbon's own development only.
  - Read by `research_admission` (the grant).
  - Read by `research_profile`.
  - Read by `research_campaign.py:655` for the development CLI's own
    VERSION campaign; it is removed for a product campaign at line 678.
  - It never reaches a product campaign.
- `battery/campaign.py:104` and `challenge_registry/agent_plan.py:46`
  (`max_research_trials_per_epoch: 8`) do not bind a miner's budget.
  - Both are in `provider_plan`'s legacy `autonomous` plan, which no new
    launch selects. No code reads the field.
  - The research loop's own `MAX_RESEARCH_TRIALS` (8,
    `research_agent_policy.py:65`) paces Carbon's legacy autonomous agent
    per epoch, only for a plan frozen without a limits rule. It moves the
    agent to selection; it is not a ledger refusal.
  - Graphite plans freeze `limits` with `trials_per_epoch` null unless the
    miner sets it.
- `graphite/provider.py` `caps` and `graphite/triage.py` `ceilings`
  (`research_trials: 0`): Graphite's internal run ledgers on Carbon's own
  grant, never a miner campaign.
- **Flagged to the Test Lead, policy unchanged:**
  - `SERVICE_LIMITS`, `research_ledger.py:100`, applied in `_reserve` and
    `research_sequences.py`: Carbon's shared reference service capacity,
    512 `reference_trajectories` and 2048 `reference_invocations` per
    campaign. It applies to every campaign, the miner's included, though
    no miner sets it. It is reported as Carbon's capacity, never as the
    miner's budget, and now types as FAILED_INFRA / RESOURCE_LIMIT.
  - `research_ledger.py:723`: the 720000 ms per-worker ceiling on
    non-research phases (final, selection, report), Carbon's own
    evaluation work.

**Tests.** `tests/cpu/test_research_budget_refusal_typing.py` (new):
- typed refusals and counts for trials, money, provider attempts and epochs;
- retained bytes and service capacity typed apart;
- time typed, but a regressed clock not;
- campaign control's deadline carrying the same record;
- the loop's and Graphite's readers reading the typed refusal;
- every unset dimension never refusing, whether absent, null or no budget;
- the launch recording only the miner's budget;
- the durable path for trials, money, elapsed time and service capacity;
- genuine exceptions, the ledger's text without its type, and a failing
  hook all staying INTERNAL;
- retained tasks and results reading back unchanged.
