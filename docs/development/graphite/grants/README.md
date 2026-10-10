# Graphite spending grants

## GRAPHITE-GRANT-PHASE2 (GRAPHITE-01 phase 2, literature backfill)

**Authority.** OWNER-GRAPHITE-02 (`.agent/DECISIONS.md`). The owner said
"Start Graphite phase 2 with full Engy balance". Later on 2026-10-02 the owner
replaced that with "grant is $9".

**State.** Complete. On 2026-10-02 the owner supplied the last two fields
("Expiry 12/31/2026 and “Carbon Account”"), so the grant validates
and the runner accepts it:

- `account`: `Carbon-Account`, the owner's label “Carbon Account” for the
  paying Engy account (a label, not a credential), written with a hyphen
  because the grant format allows no spaces;
- `expires_at`: `2026-12-31T23:59:59Z`.

| Field | Value | Basis |
|---|---|---|
| `account` | `Carbon-Account` | The owner: “Carbon Account” (2026-10-02); hyphenated for the format |
| `expires_at` | `2026-12-31T23:59:59Z` | The owner: "Expiry 12/31/2026" (2026-10-02) |
| `monetary_ceiling` | `9.00` USD | The owner: "grant is $9" (2026-10-02) |
| `provider` | `graphite` | The provider a Graphite grant binds (`graphite.provider.PROVIDER`) |
| `granted_by` | `owner` | OWNER-GRAPHITE-02 |
| `worst_case_run_cost` | `2.49` USD | Derived (below) |
| `cleanup_allowance` | `0.00` USD | Derived: phase 2 launches no pods or workers, so nothing needs cleanup. A call in flight at a crash keeps its full reservation in the run's ledger, and the grant gate counts it |
| `permitted_runs` | `40` | The owner: "Raise runs, add resume fix (Recommended)" (2026-10-02, amendment below). Was `3`, derived (below) |
| `max_concurrency` | `1` | The runner runs one backfill at a time |
| `max_runtime_s` | `360000` | Derived: 3,000 calls × the 120 s provider timeout |
| `max_submissions` | `1` | Phase 2 submits nothing. 1 is the smallest value the format accepts, and nothing reads it |

### Arithmetic

This is engineering arithmetic from listed prices, not a new price.

**One call's reservation.** It is
`ModelSelection.reservation_nano`: the maximum input tokens times the input
price, plus the maximum output tokens times the output price. The triage
settings are `triage.TRIAGE_SETTINGS`: 16,384 input tokens and 1,024 output
tokens. The Reader starts on `deepseek-v4-flash-0731`. Its listed prices
(Engy, observed 2026-09-26) are 45 and 90 nanodollars a token.

    16,384 × 45 + 1,024 × 90 = 737,280 + 92,160 = 829,440 nanodollars
                             = USD 0.00082944 per call

**One run's worst case.** A run makes at most `triage.MAX_CALLS_PER_RUN` =
3,000 calls (rate-limit retries count):

    3,000 × USD 0.00082944 = USD 2.48832  →  USD 2.49 (rounded up to the cent)

Each run's ledger is frozen with this as its money cap, so a run stops before
a reservation would pass it, whatever rung the Reader is on. If the Reader
were escalated to a dearer rung, a run would stop on this cap after fewer
calls; it would not spend more.

**Runs.** A new run opens only while settled and reserved spend, plus the
next run's worst case, plus cleanup, stays within the ceiling. The original
run count was the number of worst-case runs that fit:

    ⌊ (9.00 − 0.00) / 2.49 ⌋ = 3 runs    (3 × 2.49 = 7.47 ≤ 9.00)

Since the amendment the grant permits 40 runs. That gate is unchanged, so the
ceiling, not the run count, bounds money: a run of about 300 calls books at
most 300 × USD 0.00082944 ≈ USD 0.25, and a new run still needs USD 2.49 of
headroom under USD 9.00.

**Expected spend.** Each call is settled from Engy's reported charge, not
from the reservation. An abstract request is about 1,500 input tokens, and a
card is a few hundred output tokens. At the listed prices that is roughly
USD 0.0001 per abstract, or under USD 1 for a few thousand abstracts. The
plan's estimate is "under USD 5" (plan §7). The first live run measures the
real figure and replaces these numbers.

### Amendment (2026-10-02): 40 runs

**Authority.** OWNER-GRAPHITE-02 amendment (`.agent/DECISIONS.md`). The owner
chose "Raise runs, add resume fix (Recommended)": raise the phase-2 grant to
40 runs, keeping the USD 9 ceiling; run in chunks of about 300 calls so each
restart costs at most one call; and fix the code so a crashed run writes off
its one unresolved call and continues.

**Why.** The cloud container restarted and killed the live triage mid-call
repeatedly. Each time one call was left with an unknown outcome (ledger
state `RESERVED`) and the run stopped `RECONCILIATION_REQUIRED`, which used up
all three runs:

- `smoke-1`: 5 calls;
- `full-1`: 59 calls, 1 unresolved;
- `full-2`: 41 calls, 1 unresolved.

Together: 101 cards and 1 rejection. Booked spend is USD 0.086. Estimated
actual spend is about USD 0.007, because Engy does not report
`x_engy.charged_micro`, so each call keeps its full reservation.

**What changed.** Only `permitted_runs`, from 3 to 40. The resume fix is
GRAPHITE-D17 (`.agent/tickets/GRAPHITE-01_in_house_testing_agent.md`). An
unresolved call is written off at the next start and never resent, and its
full reservation stays booked in its run's ledger, where the gate above still
counts it.

## GRAPHITE-GRANT-PHASE3 (GRAPHITE-01 phase 3, Constructor Level 0)

**Authority.** OWNER-GRAPHITE-03 (`.agent/DECISIONS.md`). On 2026-10-02 the
owner was asked for the phase-3 grant amount (USD 15 suggested) and whether
RunPod pod time is inside it or separate. The owner answered "$15 runpod
included", then "Start phase 3 build in parallel".

**Amendment (2026-10-02).** A Constructor session was capped at 48 model
calls, the shared `research_agent_policy.MAX_PROVIDER_CALLS`, where the plan
expects about 150 turns. The owner answered: "up the plan to 150". A
Constructor session now has its own cap of 150 calls
(`roles.CONSTRUCTOR_SESSION_TURNS`, GRAPHITE-D26), and the shared 48 is
unchanged. Only `max_runtime_s` changes; the ceiling, `worst_case_run_cost`
and the pod budget do not.

**Amendment (2026-10-03): no call cap.** OWNER-GRAPHITE-MINER-01 §6. Asked
about per-epoch call and trial caps, the owner said: "Yes generous and tunable
limits. I don't like that internal graphite has limits like that honestly". A
Constructor session opened from 2026-10-03 has no session-turn cap and no
per-role call cap. The run's money cap and its runtime bind. No grant value
changes. See "Since 2026-10-03" below.

**Amendment (2026-10-04): the Constructor's whole context.** GRAPHITE-D34.
The owner: "max it out". A session opened from 2026-10-04 has a larger input
window, a 600 s timeout and runs on `engy-chat`. No grant value changes. See
"Since 2026-10-04" below.

**State.** Complete: the grant validates and the runner accepts it. Live
sessions 1 and 2 have run (GRAPHITE-D33, GRAPHITE-D34).

One grant covers both kinds of spend. Each run is reserved at
`worst_case_run_cost` by the campaign controller, and inside the run every
model call is reserved before dispatch and every pod before launch, against
that same run cap. Each settles from the provider's reported charge (Engy's
`x_engy.charged_micro`; RunPod's billing record). A pod whose charge RunPod
does not report keeps its full reservation.

| Field | Value | Basis |
|---|---|---|
| `monetary_ceiling` | `15.00` USD | The owner: "$15 runpod included" (2026-10-02). Tokens and pods together |
| `account` | `Carbon-Account` | The same as the phase-2 grant; the owner set it for phase 2 ("Carbon Account", 2026-10-02) |
| `expires_at` | `2026-12-31T23:59:59Z` | The same as the phase-2 grant; the owner set it for phase 2 ("Expiry 12/31/2026") |
| `provider` | `graphite` | The provider a Graphite grant binds |
| `granted_by` | `owner` | OWNER-GRAPHITE-03 |
| `permitted_runs` | `3` | The plan's first block of 3 sessions (plan §7) |
| `cleanup_allowance` | `0.25` USD | pod_control's `CLEANUP_RESERVE_USD` (below) |
| `worst_case_run_cost` | `4.91` USD | Derived (below) |
| `max_runtime_s` | `39600` | Derived (below); 27,360 before the 150-call amendment |
| `max_concurrency` | `1` | One session at a time; each session runs one pod at a time |
| `max_submissions` | `3` | One session export per permitted run; the controller counts exports across the grant |

### Arithmetic

This is engineering arithmetic from recorded prices, not a new price.

**The pod price.** It is the EV4 pod tooling's
(`scripts/dev/exam_design/runpod/pod_control.py`), read by
`graphite.pods.prices()` and never restated in code:

- `MAX_RATE` = USD 0.49 an hour for one A40 Secure pod. The EV4 ledger
  (`docs/development/evidence/ev4-2026-10-01/accounting/ledger.jsonl`)
  records RunPod's `costPerHr` 0.49 on each pod it created.
- Container disk: `DISK_GB` 20 at `DISK_USD_PER_GB_MONTH` 0.10, over 730
  hours a month: 20 × 0.10 / 730 = USD 0.002739726 an hour.

      0.49 + 0.002739726 = USD 0.492739726 an hour

The rate is a ceiling: the runner refuses a pod RunPod offers above it.

**One proposal's pod.** Its lifetime is three allowances, each from an
existing record (GRAPHITE-D20):

- start-up: 15 min, the rented runner's `RentedCompute.startup_seconds` (900 s);
- the job: 10 min, the battery construction contract's
  `envelope.worker_deadline_seconds` (600 s);
- export: 5 min, pod_control's default `--export-minutes 5`.

      30 min × 0.492739726 / 60 = USD 0.246369864 per pod (rounded up to the nanodollar)

The pod's own watchdog terminates it at that deadline (`bootstrap.py`).

**One session's pods.** The plan estimates "about USD 1-3 of pod time" per
session (§7). At the upper end, 3.00 / 0.492739726 × 60 = 365.3 min, which
holds 12 whole 30-minute pods (`experiment.SESSION_POD_MINUTES` = 360). The
baseline takes the first; the rest are proposals and ablations.

      12 × 0.246369864 = 2.956438368  →  USD 2.96 (rounded up to the cent)

**Cleanup.** `cleanup_allowance` is pod_control's `CLEANUP_RESERVE_USD`,
USD 0.25. Every pod is reserved to its full deadline, so a pod that outlives
its job is already paid for. The allowance covers terminating it beyond that:
the verified-termination loop (6 tries 10 s apart, about USD 0.008 of A40
time) and up to about 30 more minutes of one A40 (0.25 / 0.492739726 × 60 =
30.4 min) if termination needs a later reconcile. Only one pod runs at a time.

**One run's worst case.** The ceiling less cleanup, shared evenly by the 3
permitted runs, rounded down to the cent:

      ⌊ (15.00 − 0.25) / 3 ⌋ = ⌊ 4.9166… ⌋ = USD 4.91
      3 × 4.91 + 0.25 = 14.98 ≤ 15.00        ⌊ (15.00 − 0.25) / 4.91 ⌋ = 3 runs

**The run's split.** Pods take 2.96, and tokens take the rest:

      4.91 − 2.96 = USD 1.95 of tokens per run

The run's research ledger is frozen with 1.95 as its money cap, and a pod is
admitted only while tokens committed, plus pods committed, plus the new pod's
reservation stay within 4.91. A Constructor session opened before 2026-10-03
makes at most 150 model calls (`roles.CONSTRUCTOR_SESSION_TURNS`, passed to
the research loop as its `max_provider_calls`; the shared
`research_agent_policy.MAX_PROVIDER_CALLS` of 48 is unchanged for every other
epoch). A session opened from 2026-10-03 has no call cap; see "Since
2026-10-03" below. At `DEFAULT_SETTINGS` (65,536 input and 2,048 output
tokens), the settings of every session opened before 2026-10-04, one call
reserves (for later sessions see "Since 2026-10-04" below):

- `deepseek-v4-flash-0731` (the Constructor's start): 65,536 × 45 + 2,048 × 90
  = 3,133,440 nanodollars, so 150 calls reserve
  150 × 3,133,440 = 470,016,000 nanodollars, USD 0.47, within the 1.95
  token share;
- `glm-5.2`: 65,536 × 680 + 2,048 × 1,500 = 47,636,480 nanodollars, so the
  1.95 cap still stops a run after 40 calls, before the 150-call cap.

So whichever rung the Constructor reaches, a run cannot spend more than 1.95
on tokens. The plan estimates about USD 0.10 a session on
`deepseek-v4-flash-0731` and about USD 2 on `glm-5.2` (§7).

**Runtime.** Every model call and every pod, one after another, for a session
opened before 2026-10-03 (150 calls):

      150 × 120 s (the provider timeout) + 12 × 1,800 s = 18,000 + 21,600 = 39,600 s

**Expected spend.** Each call and each pod settles from the provider's
reported charge, not from its reservation. The plan's estimate is about
USD 0.10 of tokens and USD 1-3 of pod time per session. The first live
session measures the real figures and replaces these numbers.

### Since 2026-10-03: money and time bind, not call counts

**Authority.** OWNER-GRAPHITE-MINER-01 §6 (quoted in the amendment above).
The engineering choices are recorded in GRAPHITE-MINER-S6
(`.agent/decisions/2026-10-03-GRAPHITE-MINER-S6.md`).

**What changed.** Only the rule a new session runs under, not the grant.
- A session opened from 2026-10-03 records the v2 session-limits rule
  (`provider.SESSION_LIMITS_V2`) in its session record, under
  `session_limits`. It has no session-turn cap and no per-role call cap. The
  research loop runs it with the engine's count-free limits and its
  recorded context compaction. Its model is offered the role's closed
  manifest plus the engine's compaction tool, which the loop answers itself
  and which reaches no role tool; the record names it (`engine_tools`).
- The 150 calls of `roles.CONSTRUCTOR_SESSION_TURNS` are historical. A session
  recorded under them, every session opened before 2026-10-03, resumes under
  them and replays byte-identically.
- Stall detection and its one-rung escalation are unchanged.

**What bounds a run now.** The same two limits as before, now the only ones:
- **Money.** The controller reserves `worst_case_run_cost` (USD 4.91) for each
  run. Inside the run, every model call and every pod is admitted against
  that same cap. Model calls are also held to the token share (USD 1.95).
  The session record states both caps (`money_cap_nanodollars`,
  `model_spend_cap_nanodollars`). The controller's launch gate (settled and
  reserved spend, plus the next run's worst case, plus cleanup, within the
  ceiling) uses money alone, so the arithmetic above is unchanged:
  3 × 4.91 + 0.25 = 14.98 ≤ 15.00.
- **Time.** `max_runtime_s` (39,600 s) is still the run's elapsed limit,
  counted from the run ledger's first reservation. Its value was derived from
  150 calls and 12 pods. It is now a time bound, not a call count, and it
  bounds pods as well as model calls:
  - a model call is admitted only when its 120 s timeout fits the time left
    (600 s for a session opened from 2026-10-04);
  - a pod is admitted only when its full 1,800 s lifetime fits the time left.
    A proposal also counts the baseline's pod when the baseline has not run,
    and is otherwise refused before anything starts
    (`proposal_cannot_fit_remaining_time`). An ablation that cannot fit is
    recorded `NOT_RUN_NO_TIME` in the bundle.

  Under the old rule the bound held by construction (the sum above). Without
  a call cap, model calls could otherwise take the whole runtime and a pod
  could still start just before its end, so the pod admission check is what
  keeps the run inside 39,600 s. The controller cancels a run past the limit
  only after the runner returns, so it is not relied on.

**How many calls fit.** Money, not a count, decides. For a session opened
before 2026-10-04 (65,536 input tokens), at the Constructor's starting rung,
settled at its full reservation, the token share holds
⌊1.95 / 0.00313344⌋ = 622 calls. At reported charges far below the
reservation, the token share holds more, and the runtime binds first. On
`glm-5.2` the token share still stops a run after 40 calls. A session opened
from 2026-10-04 reserves more per call; see below.

**How a capped session ends.** A session the agent does not end stops when its
next model call would pass the money cap or cannot finish within the runtime.
It ends `failed` with `run_cap_reached` and the dimension, as a capped run
always has. An operator's own call cap, when one is set, stops it the same
way. Under the v2 rule the session's work is still closed:
- on any stop, the best improvement is bundled. Its ablation pods are
  admitted against the same run cap and the time left, so on a runtime stop
  the bundle records every ablation as `NOT_RUN_NO_TIME` and no pod starts;
- on any stop, the stall rule's escalation applies.

### Since 2026-10-04: the Constructor's whole context, a 600 s timeout, `engy-chat`

**Authority.** GRAPHITE-D34 (`.agent/decisions/2026-10-04-GRAPHITE-D34.md`).
The owner, 2026-10-04: "yeah we need to allow for as much context as
possible. whatever that value is, max it out". Of the executor's
recommendation on the timeout and the reported charge: "perfect. I approve
what comes back".

**Why.**
- Live session 2 stopped after 2 model calls at the context admission
  ceiling of `DEFAULT_SETTINGS`: 65,536 − 4,096 = 61,440 tokens.
- Every call of live sessions 1 and 2 kept its full reservation. They ran on
  `engy-anthropic`, and Engy's Messages endpoint returns no
  `x_engy.charged_micro`.

**What changed, for a session opened from 2026-10-04.**
- The Constructor's `max_input_tokens` is its model's whole context, as
  Engy's public list gives it, up to 1,048,576 (the most `select` accepts).
  Output stays 2,048 tokens and reasoning `low`.
- Its provider timeout is 600 s, up from 120 s.
- Phase 3 opens its sessions on `engy-chat`, which reports each call's
  charge, so each call settles at that charge.
- A session opened before keeps its recorded selection when it resumes
  (`engy-anthropic`, 65,536 tokens, 120 s).

**What did not change.** No grant value. The ceiling, `worst_case_run_cost`,
the 1.95 token share, the pod budget and `max_runtime_s` are as above, and
3 × 4.91 + 0.25 = 14.98 ≤ 15.00 still holds.

**One call's reservation.** This is engineering arithmetic from the listed
prices (Engy, observed 2026-09-26), not a new price. A call reserves
`max_input_tokens` × the input price plus 2,048 × the output price. The last
two columns count the calls the 1.95 token share holds when every call
settles at its full reservation, as on `engy-anthropic`:

| Rung | Model | `max_input_tokens` | Reservation (nanodollars) | Calls at full reservation | Before (65,536 input) |
|---|---|---|---|---|---|
| 0 | `deepseek-v4-flash-0731` | 1,048,576 | 1,048,576 × 45 + 2,048 × 90 = 47,370,240 | ⌊1.95 / 0.04737024⌋ = 41 | 622 |
| 1 | `qwen3.8-27b` | 1,001,536 | 1,001,536 × 45 + 2,048 × 320 = 45,724,480 | ⌊1.95 / 0.04572448⌋ = 42 | 540 |
| 2 | `glm-5.3-flash` | 262,144 | 262,144 × 135 + 2,048 × 450 = 36,311,040 | ⌊1.95 / 0.03631104⌋ = 53 | 199 |
| 3 | `glm-5.2` | 262,144 | 262,144 × 680 + 2,048 × 1,500 = 181,329,920 | ⌊1.95 / 0.18132992⌋ = 10 | 40 |
| 4 | `kimi-k3` | 1,048,576 | 1,048,576 × 1,950 + 2,048 × 9,750 = 2,064,691,200 | none: one call, USD 2.0647, exceeds 1.95 | 13 |

**The trade-off, plainly.**
- At full reservation far fewer calls fit: 41 instead of 622 on the first
  rung, 10 instead of 40 on `glm-5.2`.
- On `kimi-k3` no call can be admitted at all, so a session on that rung
  stops, typed (`run_cap_reached`, `provider_nanodollars`), before its first
  call. The Constructor moves one rung per stalled session, so this grant's
  3 runs reach at most the third rung (`glm-5.3-flash`).
- On `engy-chat` a call settles at Engy's reported charge, so the token share
  holds as many calls as those charges allow. A call is still admitted only
  while the spend so far plus its full reservation stays within 1.95.
- Raising the token share would be a grant change, and that is the owner's.

**Time.**
- `max_runtime_s` stays 39,600, counted from the run ledger's first
  reservation.
- A model call is admitted only when its 600 s timeout fits the time left
  (120 s before), so no call starts in the run's last ten minutes.
- A call that hangs is abandoned at its 610 s hard deadline with an unknown
  outcome, which stops the session `RECONCILIATION_REQUIRED`.
- Time limits the number of calls only when calls are slow. If every call ran
  its full 600 s beside 12 full pods (21,600 s), the remaining 18,000 s would
  hold 30 calls, where 120 s calls would hold 150.
- Pods are admitted exactly as before.

## GRAPHITE-GRANT-PHASE3-R2 (GRAPHITE-01 phase 3, refund of sessions 2 and 3)

**Authority.** OWNER-GRAPHITE-PHASE3-REFUND-01
(`.agent/decisions/2026-10-04-OWNER-GRAPHITE-PHASE3-REFUND-01.md`). Asked
whether session 2 counts as one of GRAPHITE-GRANT-PHASE3's runs, the owner said
"no". Asked to approve this grant, which also refunds session 3, the owner said
"approve R2". Both sessions failed on Carbon harness defects, not Graphite
attempts:

- session 2 stopped on `context_ceiling` (GRAPHITE-D34);
- session 3 hit the pod store's cross-thread `sqlite3.ProgrammingError`.

**Why a second grant.** The controller counts every run row against
`permitted_runs` and binds its store to the exact grant document it first
opened. GRAPHITE-GRANT-PHASE3 therefore stays unchanged, at 3 of 3 runs used,
and can never launch again. This grant runs in a fresh controller root.

| Field | Value | Basis |
|---|---|---|
| `monetary_ceiling` | `10.07` USD | 2 × `worst_case_run_cost` + `cleanup_allowance` (below) |
| `permitted_runs` | `2` | Sessions 2 and 3 refunded |
| `max_submissions` | `2` | One per run, as GRAPHITE-GRANT-PHASE3 |
| `worst_case_run_cost` | `4.91` USD | Unchanged from GRAPHITE-GRANT-PHASE3 |
| `cleanup_allowance` | `0.25` USD | Unchanged |
| `max_runtime_s`, `max_concurrency`, `provider`, `account`, `expires_at`, `granted_by` | as GRAPHITE-GRANT-PHASE3 | Unchanged |

### Arithmetic

    validator:   cleanup + worst case          = 0.25 + 4.91        = 5.16  ≤ 10.07
    run 1 gate:  0 + 4.91 + 0.25               = 5.16               ≤ 10.07
    run 2 gate:  run 1 (at most 4.91) + 4.91 + 0.25 = 10.07         ≤ 10.07

Run 2 can always launch, even if run 1 is held at its full reservation.

**Phase-3 total.** Sessions 1–3 spent about USD 0.015 (USD 0.0031, 0.0063 and
0.0055) and created no pods. With this grant, phase 3's worst case is about
USD 10.09, inside the original USD 15.00. GRAPHITE-GRANT-PHASE3's unused
headroom cannot be spent, because that grant cannot launch.

**Entry conditions for each run.** These apply in addition to the phase-3
handoff:

- the pod-thread fix has merged;
- the real-path no-spend pre-live check passes at the run's REF;
- the owner confirms the REF;
- the operator host is agreed with Data Collection.

## GRAPHITE-GRANT-PHASE3-R3 (GRAPHITE-01 phase 3, a third battery grant)

**Authority.** OWNER-GRAPHITE-PHASE3-R3-01
(`.agent/decisions/2026-10-05-OWNER-GRAPHITE-PHASE3-R3-01.md`). The owner said
"approve new grant" on 2026-10-05, after GRAPHITE-GRANT-PHASE3 (3 of 3 runs)
and GRAPHITE-GRANT-PHASE3-R2 (2 of 2 runs) were used up.

| Field | Value | Basis |
|---|---|---|
| `monetary_ceiling` | `15.00` USD | the proposal the owner approved; at least 3 × 4.91 + 0.25 = 14.98 |
| `permitted_runs` | `3` | the proposal |
| `max_submissions` | `3` | one per run |
| everything else | as GRAPHITE-GRANT-PHASE3-R2 | unchanged |

### Arithmetic

    validator:   cleanup + worst case          = 0.25 + 4.91         = 5.16   ≤ 15.00
    run 3 gate:  runs 1-2 (≤ 2 × 4.91) + 4.91 + 0.25                 = 14.98  ≤ 15.00

Measured runs cost about USD 3. Run 5 spent USD 0.018 in tokens and booked
USD 2.96 for 12 pods at USD 0.246 each, because RunPod reports no charge.

**Runs** in a fresh controller root, under the OWNER-GRAPHITE-TEST-WAVE-05 §3
checklist, with pod-attribution-v2 on main.

## GRAPHITE-GRANT-PHASE3-R4 (GRAPHITE-01 phase 3, battery Level 1+ on the top rung)

**Authority.** OWNER-GRAPHITE-PHASE3-R4-01
(`.agent/decisions/2026-10-05-OWNER-GRAPHITE-PHASE3-R4-01.md`). The owner,
2026-10-05: "Level 0 probably not needed. But 1 and up I want to see
creativity. So I approve." and "For 1 and up." USD 10 per run for model calls
plus USD 5 per run for compute, USD 45 over 3 runs.

| Field | Value | Basis |
|---|---|---|
| `monetary_ceiling` | `45.00` USD | the approval; at least 3 × 14.91 + 0.25 = 44.98 |
| `worst_case_run_cost` | `14.91` USD | R3's compute-inclusive 4.91 plus 10.00 for the model |
| `permitted_runs` | `3` | the approval |
| `max_submissions` | `3` | one per run |
| everything else | as GRAPHITE-GRANT-PHASE3-R3 | unchanged |

**Run conditions** (`grant_binding.PHASE3_GRANTS`; recorded in each new
session's `run_conditions`):

- construction Level 1 and above only: a Level 0 run under it is refused
  `grant_requires_construction_level_1_or_above`, at the CLI and again before a
  session opens;
- the Constructor (and the Planner, when used) starts on `kimi-k3`, the top
  Engy rung; a session that would open below it is refused
  `start_model_below_the_grants_start_rung`. The escalation rule is unchanged;
  a stall at the top records `ladder_top`;
- the run's token share is fixed at USD 11.93 (the Test Lead's figure, 14.91
  less 2.98 of compute); its pods get the remaining 2.98, which covers the 12
  pods' 2.96 at today's rate ceiling, or the budget is refused
  `grant_token_share_leaves_too_little_for_pods`. Without the fixed share the
  split would follow the rate ceiling (today 11.95);
- bound to battery and to main's committed blob.

### Arithmetic

    validator:   cleanup + worst case                 = 0.25 + 14.91  = 15.16  ≤ 45.00
    run 3 gate:  runs 1-2 (≤ 2 × 14.91) + 14.91 + 0.25                = 44.98  ≤ 45.00
    split:       14.91 = 11.93 tokens + 2.98 pods     (12 pods need 12 × 0.246369864 → 2.96)

kimi-k3's per-call reservation at the Constructor's settings
(`roles.MODEL_SETTINGS`: 1,048,576 input tokens, 2,048 output tokens; Engy list
USD 1.95 / 9.75 per million):

    1,048,576 × 0.00000195 + 2,048 × 0.00000975 = 2.044723200 + 0.019968000 = USD 2.0646912
    ⌊ 11.93 / 2.0646912 ⌋ = 5 full reservations   (5 × 2.0646912 = 10.323456 ≤ 11.93)
    ⌊ 10.00 / 2.0646912 ⌋ = 4 within the approved USD 10 model allowance

Those counts bound calls in flight, not calls per run: each call is admitted
with its full reservation and settles at Engy's reported charge, which then
replaces the reservation in the research ledger (`CampaignLedger._usage`). At
a conservative USD 0.078468 per call (30,000 input tokens plus the whole
2,048-token output at kimi-k3's prices), run 5's 23 calls fit the 11.93 share
(`test_23_settled_kimi_k3_calls_are_admitted_under_the_r4_share`). Under R3's token share
(USD 1.95) not one full-window kimi-k3 call is admitted.

**Runs** in a fresh controller root, under the OWNER-GRAPHITE-TEST-WAVE-05 §3
checklist, and only once OWNER-GRAPHITE-PHASE3-R4-01's entry conditions hold.

## GRAPHITE-GRANT-PLANNER-01 (GRAPHITE-ADMISSION-01: Graphite's level planner)

**Authority: OWNER-GRAPHITE-05** (`.agent/DECISIONS.md`, 2026-10-02). It is
the first grant under the owner's process, "stop requiring grants. Just ask
for platform and budget and propose one".
- **Proposed by:** the executor, with every value below.
- **Approved by:** the owner, directly, on 2026-10-02: "Approve as proposed".

The grant format has no field for the proposer. The file therefore records
`granted_by: owner`, and this section and the decision record the proposal.
The controller still treats the file as the hard spend ceiling.

**Use.** Live level-planning sessions. Each session makes one Planner call per
construction level 0-5, for one Challenge, starting with battery. The runner
(`python -m carbon.agent_campaign.graphite.level_planner`) enforces three
things:
- it accepts only grants in `PLANNER_GRANTS`, which today is this one;
- it refuses a credential file that is not owner-only;
- it holds each session to `MAX_CALLS` (24), within this grant's cap of 43.

| Field | Value | Basis |
|---|---|---|
| `provider` | `graphite` | Engy inference only, no pods |
| `account` | `Carbon-Account` | As proposed and approved |
| `granted_by` | `owner` | OWNER-GRAPHITE-05 |
| `expires_at` | `2026-12-31T23:59:59Z` | As proposed and approved |
| `monetary_ceiling` | `5.00` USD | As proposed and approved |
| `worst_case_run_cost` | `2.50` USD | As proposed and approved; the call cap is derived from it |
| `cleanup_allowance` | `0.00` USD | No pods or workers: nothing needs cleanup |
| `permitted_runs` | `2` | Battery first, plus one retry or a second Challenge |
| `max_concurrency` | `1` | One session at a time |
| `max_runtime_s` | `12900` | 43 calls × the planner's 300 s timeout |
| `max_submissions` | `2` | One proposal set per session |

### Arithmetic

This is engineering arithmetic from listed prices, not a new price.

**One call's reservation**, at the planner's settings (`level_planner.SETTINGS`:
65,536 input tokens and 8,192 output tokens). It is priced at `glm-5.2`, 680
and 1,500 nanodollars per input and output token:

    65,536 × 680 + 8,192 × 1,500 = 56,852,480 nanodollars = USD 0.05685248

**Call cap.** The most calls one session's worst case covers:

    ⌊ 2.50 / 0.05685248 ⌋ = 43 calls    (43 × 0.05685248 = USD 2.4447)

A session needs six calls, one per level. The runner's `MAX_CALLS` of 24
leaves room for rate-limit retries. A dearer rung stops on the session's
money cap and never spends more.

**Runs.**

    ⌊ (5.00 − 0.00) / 2.50 ⌋ = 2 runs    (2 × 2.50 = 5.00 ≤ 5.00)

`tests/cpu/test_graphite_level_planner.py::test_the_planner_grant_covers_its_calls`
holds this arithmetic.

## GRAPHITE-GRANT-PLANNER-02 (Graphite's level planner, larger briefs)

**Authority: OWNER-GRAPHITE-05.** The executor proposes, the owner approves.
- **Proposed by:** the executor, on 2026-10-03, after the two runs below.
- **Approved by:** the owner, directly, on 2026-10-03. Asked "Approve
  GRAPHITE-GRANT-PLANNER-02 as proposed?", the owner answered "Okay I guess
  just fit as many relevant cards as we can", then "then approve".

**Why a second grant.** GRAPHITE-GRANT-PLANNER-01's two runs are used:
- `level-plan-1` was refused before any call. Its 24 cards made a 115 KB
  request against the 61,440-byte bound: 65,536 input tokens, less the 4,096
  reserve, at one token per byte before any usage is reported. The stop was
  mislabelled as an incomplete provider response. It spent nothing.
- `level-plan-2`, with 6 cards, made one call. The 55.7 KB request was 13,171
  tokens, about 4.2 bytes per token. The reply ran past 8,192 output tokens and
  came back incomplete. It booked $0.0569, the full reservation, because the
  provider reported no charge; at list price it was about $0.021.

**Settings** (`level_planner.SETTINGS`):

| Setting | Value |
|---|---|
| input | 196,608 tokens |
| output | 32,768 tokens |
| reasoning effort | medium |
| timeout | 600 s, the most the provider settings allow |

**What the settings cost.** One call reserves 196,608 × 680 + 32,768 × 1,500
nanodollars, or $0.18284544. The call cap is floor($1.50 / $0.18284544) = 8,
which equals `MAX_CALLS`: six levels plus two retries. The runtime cap is
8 × 600 s = 4,800 s.

**Where the settings differ from the proposal.** The proposal said 131,072
input tokens and a 900 s timeout. The owner asked to fit as many relevant cards
as we can, so the input is 196,608 tokens, about 47 cards, within the same
approved money ceilings. The provider settings allow at most 600 s, so the
runtime cap of 4,800 s is under the approved two hours.

**What the runner enforces:**
- It accepts only this grant (`PLANNER_GRANTS`). PLANNER-01 was derived for
  the earlier settings and is no longer accepted.
- It refuses a brief whose largest request exceeds the bound, before any call
  (`brief_too_large`).
- It reports an input-bound stop as `STOPPED_CAP input_tokens`.

| Field | Value | Basis |
|---|---|---|
| `provider` | `graphite` | Engy inference only, no pods |
| `account` | `Carbon-Account` | As proposed and approved |
| `granted_by` | `owner` | OWNER-GRAPHITE-05 |
| `expires_at` | `2026-12-31T23:59:59Z` | As PLANNER-01 |
| `monetary_ceiling` | `3.00` USD | As proposed and approved |
| `worst_case_run_cost` | `1.50` USD | As proposed and approved; the call cap is derived from it |
| `cleanup_allowance` | `0.00` USD | No pods or workers |
| `permitted_runs` | `2` | As proposed and approved |
| `max_concurrency` | `1` | One session at a time |
| `max_runtime_s` | `4800` | 8 calls × 600 s, under the approved two hours |
| `max_submissions` | `2` | As PLANNER-01 |

## GRAPHITE-GRANT-PHASE4 (Graphite's Attacker, the general attack engine)

**Authority.** OWNER-GRAPHITE-ATTACKER-01
(`.agent/decisions/2026-10-04-OWNER-GRAPHITE-ATTACKER-01.md`), and the Test
Lead's record OWNER-GRAPHITE-TEST-WAVE-01 §2
(carbonphysicsai/Carbon#556), which records the same approval. Asked to
approve the live grant for Graphite's Attacker, the owner answered "Approve
now". The engine is challenge-neutral; its first adapter is battery Level 0.

**State.** Approved. The grant validates and the phase-4 runner accepts it. No
live session has run: the engine's scripted dry run
(`python -m carbon.agent_campaign.graphite.phase4 run --dry-run`) spends
nothing, and a live run takes place only after the engine merges and that dry
run passes (OWNER-GRAPHITE-ATTACKER-01 §5).

One grant covers both kinds of spend, as the phase-3 grant does: the Attacker's
Engy model calls, and the RunPod pods on which Carbon would rebuild the attack
constructions it scores (the verify step; §5). In this build that pod rebuild
is a declared NOT_RUN seam (`phase4.POD_REBUILD_SEAM`): a live Attacker run
launches no pod, and the pods' share of each run stays reserved but unspent.
Each run is reserved at
`worst_case_run_cost` by the campaign controller; inside the run every model
call is reserved before dispatch and admitted against the run's token share.
**Money and time bind, never a call count** (OWNER-GRAPHITE-ATTACKER-01 §5,
following OWNER-GRAPHITE-MINER-01 §6): the Attacker session opens under the v2
session-limits rule with no session-turn cap and no per-role call cap.

| Field | Value | Basis |
|---|---|---|
| `monetary_ceiling` | `10.50` USD | The owner, as proposed. Tokens and pods together |
| `account` | `Carbon-Account` | The same paying account as the phase-2 and phase-3 grants |
| `expires_at` | `2026-12-31T23:59:59Z` | As proposed and approved |
| `provider` | `graphite` | The provider a Graphite grant binds |
| `granted_by` | `owner` | OWNER-GRAPHITE-ATTACKER-01 §5 |
| `permitted_runs` | `3` | The first block of 3 Attacker sessions |
| `cleanup_allowance` | `0.25` USD | pod_control's `CLEANUP_RESERVE_USD`, as phase 3 |
| `worst_case_run_cost` | `3.41` USD | Derived (below) |
| `max_runtime_s` | `15600` | As proposed and approved |
| `max_concurrency` | `1` | One session at a time |
| `max_submissions` | `3` | One session export per permitted run |

### Arithmetic

This is engineering arithmetic from recorded prices, not a new price. It uses
the same pod price as the phase-3 grant (`graphite.pods.prices()`, read from
the EV4 pod tooling): USD 0.246369864 per 30-minute pod.

**Pods per run.** A run's worst case rebuilds up to six attack constructions
on their own pods (the verify step, §5):

    6 × USD 0.246369864 = 1.478219184  →  USD 1.48 (rounded up to the cent)

**One run's worst case.** The owner approved USD 3.41 a run: the six pods
plus about 40 `glm-5.2` calls.

**Tokens per run.** The token share is what the run cost leaves after the
pods:

    3.41 − 1.48 = USD 1.93

The Attacker starts on `glm-5.2`. At `DEFAULT_SETTINGS` (65,536 input and 2,048
output tokens) one call reserves 65,536 × 680 + 2,048 × 1,500 = 47,636,480
nanodollars, USD 0.04763648, so the token share covers about 40 calls
(1.93 / 0.04763648 ≈ 40.5; 40 calls are USD 1.9054592). The call count only
explains the figure: money binds, not the count.

**Runs.** Three permitted runs, plus cleanup, stay under the ceiling:

    3 × 3.41 + 0.25 = 10.48 ≤ 10.50

The run's research ledger is frozen with the token share as its money cap, so
a run cannot spend more than that on model calls whatever rung the Attacker
reaches; the controller reserves the whole `worst_case_run_cost` per run, and
its launch gate (settled and reserved spend, plus the next run's worst case,
plus cleanup, within the ceiling) uses money alone. No call count bounds a
run. The grant's `max_runtime_s` is the run's elapsed limit.

**Expected spend.** Each call and each pod settles from the provider's
reported charge, not from its reservation. The first live session measures the
real figures and replaces these numbers.

## GRAPHITE-GRANT-PHASE4-COOLING (Graphite's Attacker on cooling, `chip-cold-plate`)

**Authority.** OWNER-GRAPHITE-TEST-WAVE-05 §2
(`.agent/decisions/2026-10-05-OWNER-GRAPHITE-TEST-WAVE-05.md`,
carbonphysicsai/Carbon#593). Asked to approve a phase-4 Attacker grant for
cooling with the amounts proposed in #587, identical to GRAPHITE-GRANT-PHASE4,
the owner answered "approve". The record says the grant is a new file, and
that the runner accepts a grant only when it is the committed blob on main for
the Challenge named by `--challenge`. A motor grant is proposed the same way
once motor's scorer exists; none is added here.

**State.** Approved. The grant validates. No live session has run. The
engineering choices for the per-Challenge binding are
GRAPHITE-GRANT-BINDING-01
(`.agent/decisions/2026-10-05-GRAPHITE-GRANT-BINDING-01.md`).

**Binding to the Challenge.** The grant format
(`carbon.agent-campaign.spending-grant.v1`) has an exact field set and no
Challenge field, so the binding lives in the runner:
`phase4.PHASE4_GRANTS` maps `battery-fastcharge-ageing-development-v1` to
GRAPHITE-GRANT-PHASE4 and `chip-cold-plate` to this grant.
- A live run and `phase4 prelive` accept only the grant registered for the
  Challenge `--challenge` names. Another Challenge's grant is
  `grant_is_for_another_challenge`. A Challenge with no registered grant
  (motor today) is `no_phase4_grant_for_challenge`.
- The grant must be the committed blob at a pushed HEAD and equal the blob on
  main, with the grants directory clean, exactly as for battery
  (`check_committed_grant`). Until this file is on main, the cooling checks
  refuse with `main_grant_unavailable`.
- `phase4 prelive --challenge chip-cold-plate` defaults `--grant` to this
  file, and its report names the grant id, file, digest and Challenge it
  accepted.

| Field | Value | Basis |
|---|---|---|
| `monetary_ceiling` | `10.50` USD | OWNER-GRAPHITE-TEST-WAVE-05 §2, as GRAPHITE-GRANT-PHASE4 |
| `cleanup_allowance` | `0.25` USD | OWNER-GRAPHITE-TEST-WAVE-05 §2; pod_control's `CLEANUP_RESERVE_USD`, as GRAPHITE-GRANT-PHASE4 |
| `worst_case_run_cost` | `3.41` USD | OWNER-GRAPHITE-TEST-WAVE-05 §2, as GRAPHITE-GRANT-PHASE4 (derivation below) |
| `permitted_runs` | `3` | OWNER-GRAPHITE-TEST-WAVE-05 §2 |
| `max_concurrency` | `1` | "one at a time", OWNER-GRAPHITE-TEST-WAVE-05 §2 |
| `max_runtime_s` | `15600` | OWNER-GRAPHITE-TEST-WAVE-05 §2 |
| `max_submissions` | `3` | One session export per permitted run, as GRAPHITE-GRANT-PHASE4 |
| `account` | `Carbon-Account` | The same paying account label as GRAPHITE-GRANT-PHASE4 (a label, not a credential) |
| `expires_at` | `2026-12-31T23:59:59Z` | As GRAPHITE-GRANT-PHASE4 |
| `provider` | `graphite` | The provider a Graphite grant binds |
| `granted_by` | `owner` | OWNER-GRAPHITE-TEST-WAVE-05 §2 |

### Arithmetic

This is engineering arithmetic from recorded prices, not a new price. It is
GRAPHITE-GRANT-PHASE4's, checked against cooling's own registered scoring.

**Pods per run.** Cooling's `ChallengeScoring` gives the same 30-minute verify
pod as battery (`graphite.pods.proposal_minutes`), at the same price
(`graphite.pods.prices()`, read from the EV4 pod tooling): USD 0.246369864 per
pod. `phase4.attacker_budget` reserves `ATTACKER_VERIFY_PODS` = 6 of them:

    6 × USD 0.246369864 = 1.478219184  →  USD 1.48 (rounded up to the cent)

**Tokens per run.** The token share is what the run cost leaves after the
pods:

    3.41 − 1.48 = USD 1.93

At `glm-5.2` and `DEFAULT_SETTINGS` one call reserves USD 0.04763648, so the
token share covers about 40 calls. The count only explains the figure: money
binds, not the count. The verify-pod rebuild is still the declared NOT_RUN
seam (`phase4.POD_REBUILD_SEAM`), so the pods' share stays reserved but
unspent.

**Runs.**

    3 × 3.41 + 0.25 = 10.48 ≤ 10.50        ⌊ (10.50 − 0.25) / 3.41 ⌋ = 3 runs

`tests/cpu/test_graphite_phase4_grant.py` holds this arithmetic for both
phase-4 grants.

**Expected spend.** Each call settles from the provider's reported charge, not
from its reservation. The first live cooling session measures the real
figures.

## GRAPHITE-GRANT-PHASE3-COOLING-CPU (Graphite's Constructor on cooling, CPU lane)

**Authority.** OWNER-GRAPHITE-TEST-WAVE-06 §3
(`.agent/decisions/2026-10-05-OWNER-GRAPHITE-TEST-WAVE-06.md`,
carbonphysicsai/Carbon#595). Asked to approve a cooling Constructor grant for
the CPU lane, the owner answered "approve". The approved terms:

- 3 runs, one at a time;
- a worst case of USD 1.95 per run, tokens only, because the CPU lane has no
  pods;
- a cleanup allowance of USD 0.25;
- a ceiling of USD 6.10.

The record also says the grant file is bound by the runner to
`chip-cold-plate` and to main's committed blob. A GPU-lane cooling grant
includes pod time, and is proposed with a price once the GPU lane exists.

**State.** Approved. The grant validates. No live session has run. The
engineering choices are GRAPHITE-GRANT-BINDING-01
(`.agent/decisions/2026-10-05-GRAPHITE-GRANT-BINDING-01.md`).

**Binding.** `grant_binding.PHASE3_GRANTS` registers every phase-3 grant with
its Challenge:
- GRAPHITE-GRANT-PHASE3, GRAPHITE-GRANT-PHASE3-R2 and GRAPHITE-GRANT-PHASE3-R3
  are battery's, and are accepted for battery exactly as before;
- this grant is cooling's.

`phase3 run` (`grant_binding.check_phase3_grant`) refuses:
- a registered grant named for another Challenge:
  `grant_is_for_another_challenge`;
- any grant on `chip-cold-plate` that is not registered for it:
  `grant_is_not_a_phase3_grant_for_challenge`.

It accepts this grant only as the committed blob at a pushed HEAD, equal to
the blob on main, with the grants directory clean. Those are the phase-4
checks (`grant_binding.check_committed_blob`), with phase-3 codes. Until the
file is on main, a cooling run refuses `main_grant_unavailable`.

**No paid pods.** The grant is in `phase3.TOKENS_ONLY_GRANTS` (VALIDATOR-06),
so its runs have a pod money budget of 0 (`Phase3Budget.tokens_only`):
- Its proposals run on the CPU carrier lane (`phase3 run --compute
  carrier`), which costs no provider money (rate 0).
- `phase3 run --compute runpod` refuses it
  (`grant_is_tokens_only_use_the_carrier_lane`).
- Behind that, `Experiment._admit_pod` refuses `grant_allows_no_pods` for
  every launch that would reserve pod money: the baseline's, a proposal's,
  an ablation's and a retry's on RunPod. That happens before any pod is
  reserved in the run's pod ledger and before any create request reaches
  RunPod.

| Field | Value | Basis |
|---|---|---|
| `monetary_ceiling` | `6.10` USD | OWNER-GRAPHITE-TEST-WAVE-06 §3 |
| `worst_case_run_cost` | `1.95` USD | OWNER-GRAPHITE-TEST-WAVE-06 §3, tokens only. It equals the phase-3 grants' token share (below) |
| `cleanup_allowance` | `0.25` USD | OWNER-GRAPHITE-TEST-WAVE-06 §3 |
| `permitted_runs` | `3` | OWNER-GRAPHITE-TEST-WAVE-06 §3 |
| `max_concurrency` | `1` | "one at a time", OWNER-GRAPHITE-TEST-WAVE-06 §3 |
| `max_runtime_s` | `39600` | Not stated in the approval. It is kept as GRAPHITE-GRANT-PHASE3's and R2's elapsed limit for a Constructor session. It bounds time only, never money |
| `max_submissions` | `3` | One session export per permitted run, as GRAPHITE-GRANT-PHASE3 |
| `account` | `Carbon-Account` | The same paying account label as the other Graphite grants (a label, not a credential) |
| `expires_at` | `2026-12-31T23:59:59Z` | As the other Graphite grants |
| `provider` | `graphite` | The provider a Graphite grant binds |
| `granted_by` | `owner` | OWNER-GRAPHITE-TEST-WAVE-06 §3 |

### Arithmetic

This is engineering arithmetic, not a new price.

**The run's split.** With no pod money, the pod allowance is 0 and the whole
run cost is the token share:

    pods:   USD 0.00 (the carrier costs no provider money; RunPod is refused)
    tokens: 1.95 − 0.00 = USD 1.95

The run's research ledger is frozen with USD 1.95 as its money cap. That is
the same token share each GRAPHITE-GRANT-PHASE3 run has (4.91 − 2.96), so a
Constructor session's model calls are bounded exactly as on battery. See
"Since 2026-10-04" above for how many calls each rung's reservation allows.

**Runs.**

    3 × 1.95 + 0.25 = 6.10 ≤ 6.10        ⌊ (6.10 − 0.25) / 1.95 ⌋ = 3 runs

Every launch gate passes: run 3 needs 2 × 1.95 + 1.95 + 0.25 = 6.10.

`tests/cpu/test_graphite_phase3_cooling_cpu_grant.py` holds this arithmetic.

**Expected spend.** Each call settles from Engy's reported charge, not from
its reservation. The first live cooling session measures the real figures.

## GRAPHITE-GRANT-LITERATURE-COOLING-MOTOR (literature for cooling and motor)

**State.** Approved by the owner on 2026-10-05
(OWNER-GRAPHITE-LITERATURE-GRANT-01: "approve").

It pays the method-card extraction for a Challenge with a registered
literature profile (VALIDATOR-08):

    phase2 triage --challenge chip-cold-plate --grant docs/development/graphite/grants/GRAPHITE-GRANT-LITERATURE-COOLING-MOTOR.json ...
    phase2 triage --challenge electric-motor-magnetics --grant ...

Any other grant is refused (`grant_is_not_the_literature_grant`). The arXiv
fetch costs nothing. Battery's phase-2 backfill keeps `GRAPHITE-GRANT-PHASE2`.

| Field | Value | Why |
|---|---|---|
| `monetary_ceiling` | `4.00` | Covers the expected backfill (about 1,800 booked calls) with room for the worst case below |
| `worst_case_run_cost` | `2.49` | 3,000 calls at the booked reservation (below) |
| `permitted_runs` | `3` | One run per Challenge, plus one resume or retry |
| `cleanup_allowance` | `0.10` | Headroom kept back at every run's admission |
| `max_runtime_s` | `360000` | About 100 hours, as phase 2's |
| `max_concurrency` | `1` | One run at a time |

### Arithmetic

This is engineering arithmetic from listed prices, not a new price.

**One call's reservation.** The same Reader settings and rung as phase 2:
16,384 input and 1,024 output tokens on `deepseek-v4-flash-0731`, at 45 and 90
nanodollars a token:

    16,384 × 45 + 1,024 × 90 = 829,440 nanodollars = USD 0.00082944 per call

Engy reports no charge for these calls, so every call is booked at this
reservation.

**One run's worst case.** At most 3,000 calls (`triage.MAX_CALLS_PER_RUN`):

    3,000 × USD 0.00082944 = USD 2.48832  →  USD 2.49

**The ceiling, not the run count, binds the third run.** A run opens only
while booked spend, plus the next run's worst case, plus cleanup, stays
within the ceiling:

    booked + 2.49 + 0.10 ≤ 4.00   ⇔   booked ≤ USD 1.41

So once the runs before it have booked more than USD 1.41 (about 1,700
calls), no further run opens, whatever the run count allows. With the
expected volume, one run per Challenge (cooling, then motor) both open: about
900 calls, or USD 0.75, each. A third run opens only if those two booked at
most USD 1.41 together.

**Expected volume.**
- Each Challenge has 6 queries with a quota of 3 pages of 100 records:
  at most 1,800 records, so 3,600 for both.
- Each profile's free pre-filter keeps only records naming the Challenge's
  domain, or a domain and a surrogate cue, before any paid call. About half
  are expected to pass: about 1,800 calls in total.
- That is USD 1.49 booked, about USD 0.20 actual (phase 2 measured about
  USD 0.00007 a card).
- **The worst case does not fit.** If every record passed, the first
  Challenge's run alone could book 1,800 calls (USD 1.49). That is past the
  USD 1.41 a second run's admission allows, so the other Challenge's run
  would be refused.
  - **Mitigation:** run each Challenge with `--max-calls 850`, which caps a
    run at USD 0.71 booked. Both runs then open (0.71 + 2.59 ≤ 4.00), and so
    does a third (1.41 + 2.59 ≤ 4.00).
  - A Challenge with more kept records than its run's calls finishes them in
    the third run. Past that, it needs a ceiling amendment from the owner.

The first live run measures the real figures and replaces these numbers.

## GRAPHITE-GRANT-ADMISSION-CONTROLLER-{BATTERY,COOLING,MOTOR} (zero spend)

**Authority.**
- The owner approved these grants on 2026-10-06, directly in the Test Engineer
  session: "Approve" three zero-spend admission-controller grants, one per
  Challenge.
- The Test Lead's A4 ruling uses #615's dedicated zero-spend admission
  controller for all three Challenges
  (A4-DEDICATED-ADMISSION-CONTROLLERS-01).

**What they authorize: nothing.**
- Every amount is 0.00, `permitted_runs` is 0 and `max_submissions` is 0.
- Each grant only binds one dedicated admission controller's identity, which
  is created once with `phase3 admission-controller init`.
- Campaign registration, launch, the live model and the phase-3 provider all
  refuse a zero-spend grant (`grant_is_zero_spend`) before anything is
  reserved.
- `max_concurrency` and `max_runtime_s` are 1, because the grant schema
  requires positive values. They bound nothing, since no run is permitted.

## GRAPHITE-GRANT-RATE-STUDY-TOKENS (SUBMISSION-RATE-STUDY-01, arm G-sealed)

**Authority.** OWNER-RATE-STUDY-TOKENS-01
(`.agent/decisions/2026-10-08-OWNER-RATE-STUDY-TOKENS-01.md`): the owner's
"approve rate-study tokens $30", relayed by the Test Lead.

Tokens only: 6 runs one at a time, 4.91 USD worst case per run, 0.25 cleanup, 30.00
ceiling, 39,600 s per run. `max_submissions` (144) is a ceiling; the arm cap is set
at the freeze. The grant binds spend only after the freeze manifest is on main and
the runner binds it to the study's route (see the decision record).

## GRAPHITE-GRANT-STAGE-A-{CONSTRUCTOR,ATTACKER} (the ladder wave's stage A, battery, kimi-k3)

**Authority.** OWNER-GRAPHITE-STAGE-A-01
(`.agent/decisions/2026-10-09-OWNER-GRAPHITE-STAGE-A-01.md`):
- **The figure.** The owner replied "Approve 2" to the Test Lead's exact line
  "approve Graphite stage A, $128.44".
- **The relation to R4.** The owner confirmed it directly in the Test
  Engineer's session: a new USD 128.44 for all nine stage A runs, with R4's
  unused runs still spendable on top.
- **The plan.** `GRAPHITE_LADDER_WAVE_PLAN.md` section 4 (#889).

| Grant | Runs | Worst case per run | Cleanup | Ceiling | Concurrency |
|---|---|---|---|---|---|
| STAGE-A-CONSTRUCTOR (phase 3) | 5: Level 0 x 2, Level 1 x 3 | 14.91 (R4's: 10.00 model + 4.91) | 0.12 | 74.67 | 2 |
| STAGE-A-ATTACKER (phase 4) | 4: Level 0 x 2, Level 1 x 2 | 13.41 (10.00 model + PHASE4's 3.41) | 0.13 | 53.77 | 2 |
| Stage A | 9 | | 0.25 | **128.44** | |

**Bindings** (`grant_binding.PHASE3_GRANTS`, `phase4.PHASE4_STAGE_GRANTS`):
- **Both grants:** battery, main's committed blob only, start model kimi-k3.
- **The Constructor grant** admits Level 0 and above, unlike R4. Its token
  share is 11.93, R4's.
- **The Attacker grant** starts the Attacker on kimi-k3. Its model money is
  PHASE4's plus 10.00, which holds at least four full kimi-k3 reservations.
  Phase 3 refuses it. Phase 4 accepts it with `--grant` for battery only;
  battery's default phase-4 grant is still PHASE4.

R4 (45.00, 3 runs, Level 1 and above) is unchanged and stays spendable.

## GRAPHITE-GRANT-STAGE-B-{CONSTRUCTOR,ATTACKER} (the ladder wave's stage B, battery L2-L3, kimi-k3)

**Authority.** OWNER-GRAPHITE-STAGE-B-01
(`.agent/decisions/2026-10-10-OWNER-GRAPHITE-STAGE-B-01.md`):
- **The approval.** The owner replied "approve" to the Test Lead's exact line
  "approve Graphite stage B, $143.35, up to 4 at once".
- **Direct confirmation.** The owner confirmed it directly in the Test
  Engineer's session.
- **The plan.** `GRAPHITE_LADDER_STAGE_B_PLAN.md` section 7 (#938).

| Grant | Runs | Worst case per run | Cleanup | Ceiling | Concurrency |
|---|---|---|---|---|---|
| STAGE-B-CONSTRUCTOR (phase 3) | 6: Level 2 x 3, Level 3 x 3 | 14.91 | 0.12 | 89.58 | 4 |
| STAGE-B-ATTACKER (phase 4) | 4: Level 2 x 2, Level 3 x 2 | 13.41 | 0.13 | 53.77 | 4 |
| Stage B | 10 | | 0.25 | **143.35** | |

**Bindings:** stage A's, at Levels 2 and 3 only.
- **The Constructor grant** sets `min_level` 2 and `max_level` 3.
- **The Attacker grant** sets `Phase4Grant.levels` to (2, 3).
- **A run at any other level** is refused `grant_level_outside_the_grants_levels`.

## GRAPHITE-GRANT-STAGE-C-{CONSTRUCTOR,ATTACKER} (the ladder wave's stage C, battery L4, kimi-k3)

**Authority.** OWNER-GRAPHITE-STAGE-C-01
(`.agent/decisions/2026-10-10-OWNER-GRAPHITE-STAGE-C-01.md`):
- **The approval.** The owner replied "Approve stage C" to the Test Lead's
  exact line "approve stage C, $71.80".
- **Direct confirmation.** The owner confirmed it directly in the Test
  Engineer's session.
- **The plan.** `GRAPHITE_LADDER_WAVE_PLAN.md` section 4 (#889), stage C.

| Grant | Runs | Worst case per run | Cleanup | Ceiling | Concurrency |
|---|---|---|---|---|---|
| STAGE-C-CONSTRUCTOR (phase 3) | 3 at Level 4 | 14.91 | 0.12 | 44.85 | 4 |
| STAGE-C-ATTACKER (phase 4) | 2 at Level 4 | 13.41 | 0.13 | 26.95 | 4 |
| Stage C | 5 | | 0.25 | **71.80** | |

**Bindings:** stage B's, at Level 4 only.
- **The Constructor grant** sets `min_level` = `max_level` = 4.
- **The Attacker grant** sets `levels` to (4,).
- **Whether a Level 4 live run happens** stays the owner's and the security
  owner's (plan section 1). This grant authorizes spend only.

## The optional pod rate ceiling (GRANT-POD-CEILING-01)

- **The field.** A grant may carry `pod_rate_ceiling_usd_per_hr`, the most a
  pod under it may cost an hour. Absent, the ceiling is pod_control's
  `MAX_RATE`, as before.
- **Existing grants.** Every existing grant omits it, so its document, digest
  and behaviour are unchanged.
- **What it changes.** A grant that names it prices its pods at that ceiling
  (`pods.prices`, `phase3_budget`), and the preflight checks the live offer
  against it.
- **The token share.** A raised ceiling under a fixed token share can leave
  the session's pods too little; the run is then refused
  `grant_token_share_leaves_too_little_for_pods`, and the grant's token
  share or per-run worst case needs re-setting too.

**Stages A, B and C (2026-10-10).**
- **The approval.** The owner approved a standing 0.65/h ceiling for all
  stages: "approve a standing pod ceiling for all stages", answering the
  Test Lead's USD 0.65/h proposal. The owner confirmed it directly in the
  Test Engineer's session, with the Constructor token share lowered to
  USD 10.90.
- **The change.** The six stage grant files carry
  `pod_rate_ceiling_usd_per_hr` 0.65, and the stage Constructors' token
  share is 10.90 (`grant_binding.STAGE_TOKEN_SHARE`).
- **Unchanged:** stage caps, run counts and per-run caps.
