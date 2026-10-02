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
