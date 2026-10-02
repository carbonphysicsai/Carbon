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
| `permitted_runs` | `3` | Derived (below) |
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
next run's worst case, plus cleanup, stays within the ceiling:

    ⌊ (9.00 − 0.00) / 2.49 ⌋ = 3 runs    (3 × 2.49 = 7.47 ≤ 9.00)

**Expected spend.** Each call is settled from Engy's reported charge, not
from the reservation. An abstract request is about 1,500 input tokens, and a
card is a few hundred output tokens. At the listed prices that is roughly
USD 0.0001 per abstract, or under USD 1 for a few thousand abstracts. The
plan's estimate is "under USD 5" (plan §7). The first live run measures the
real figure and replaces these numbers.

## GRAPHITE-GRANT-PHASE3 (GRAPHITE-01 phase 3, Constructor Level 0)

**Authority.** OWNER-GRAPHITE-03 (`.agent/DECISIONS.md`). On 2026-10-02 the
owner was asked for the phase-3 grant amount (USD 15 suggested) and whether
RunPod pod time is inside it or separate. The owner answered "$15 runpod
included", then "Start phase 3 build in parallel".

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
| `max_runtime_s` | `27360` | Derived (below) |
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
existing record (GRAPHITE-D19):

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
reservation stay within 4.91. A research epoch makes at most 48 model calls
(`research_agent_policy.MAX_PROVIDER_CALLS`). At `DEFAULT_SETTINGS` (65,536
input and 2,048 output tokens) one call reserves:

- `deepseek-v4-flash-0731` (the Constructor's start): 65,536 × 45 + 2,048 × 90
  = 3,133,440 nanodollars, so 48 calls reserve USD 0.15;
- `glm-5.2`: 65,536 × 680 + 2,048 × 1,500 = 47,636,480 nanodollars, so the
  1.95 cap stops a run after 40 calls.

So whichever rung the Constructor reaches, a run cannot spend more than 1.95
on tokens. The plan estimates about USD 0.10 a session on
`deepseek-v4-flash-0731` and about USD 2 on `glm-5.2` (§7).

**Runtime.** Every model call and every pod, one after another:

      48 × 120 s (the provider timeout) + 12 × 30 min = 5,760 + 21,600 = 27,360 s

**Expected spend.** Each call and each pod settles from the provider's
reported charge, not from its reservation. The plan's estimate is about
USD 0.10 of tokens and USD 1-3 of pod time per session. The first live
session measures the real figures and replaces these numbers.
