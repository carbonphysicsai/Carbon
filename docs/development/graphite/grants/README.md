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

**State.** Complete: the grant validates and the runner accepts it. No live
session has run.

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
reservation stay within 4.91. A Constructor session makes at most 150 model
calls (`roles.CONSTRUCTOR_SESSION_TURNS`, passed to the research loop as its
`max_provider_calls`; the shared `research_agent_policy.MAX_PROVIDER_CALLS`
of 48 is unchanged for every other epoch). At `DEFAULT_SETTINGS` (65,536
input and 2,048 output tokens) one call reserves:

- `deepseek-v4-flash-0731` (the Constructor's start): 65,536 × 45 + 2,048 × 90
  = 3,133,440 nanodollars, so 150 calls reserve
  150 × 3,133,440 = 470,016,000 nanodollars, USD 0.47, within the 1.95
  token share;
- `glm-5.2`: 65,536 × 680 + 2,048 × 1,500 = 47,636,480 nanodollars, so the
  1.95 cap still stops a run after 40 calls, before the 150-call cap.

So whichever rung the Constructor reaches, a run cannot spend more than 1.95
on tokens. The plan estimates about USD 0.10 a session on
`deepseek-v4-flash-0731` and about USD 2 on `glm-5.2` (§7).

**Runtime.** Every model call and every pod, one after another:

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
  recorded context compaction.
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
- **Time.** `max_runtime_s` (39,600 s) is still the run's elapsed limit. Its
  value was derived from 150 calls and 12 pods. It is now a time bound, not a
  call count.

**How many calls fit.** Money, not a count, decides. At the Constructor's
starting rung, settled at its full reservation, the token share holds
⌊1.95 / 0.00313344⌋ = 622 calls. At reported charges far below the
reservation, the token share holds more, and the runtime binds first. On
`glm-5.2` the token share still stops a run after 40 calls.

**How a capped session ends.** A session the agent does not end stops when its
next model call would pass the money cap or cannot finish within the runtime.
It ends `failed` with `run_cap_reached` and the dimension, as a capped run
always has. Under the v2 rule the session's work is still closed:
- on a money stop, the best improvement is bundled, and its ablation pods are
  admitted against the same run cap;
- on any stop, the stall rule's escalation applies;
- on a runtime stop, no new pod launches, so nothing is bundled.

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
