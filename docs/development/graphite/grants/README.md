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

## GRAPHITE-GRANT-STEP4 (Challenge Roadmap Phase 1 step 4: Graphite phases 3 and 4)

**Authority.** OWNER-CHALLENGE-ROADMAP-02 (`.agent/DECISIONS.md`): "$5 Engy"
for step 4, with the phase 2 grant's account and expiry reused. Ticket:
`.agent/tickets/CHALLENGE-PROTOCOL-04.md`. One grant and one controller store
serve both phases: the Constructor block and the Attacker block.

| Field | Value | Basis |
|---|---|---|
| `account` | `Carbon-Account` | The owner, reusing phase 2's (2026-10-02) |
| `expires_at` | `2026-12-31T23:59:59Z` | The owner, reusing phase 2's (2026-10-02) |
| `monetary_ceiling` | `5.00` USD | The owner: "$5 Engy" (2026-10-02) |
| `provider` | `graphite` | `graphite.provider.PROVIDER` |
| `granted_by` | `owner` | OWNER-CHALLENGE-ROADMAP-02 |
| `worst_case_run_cost` | `0.77` USD | Derived (below) |
| `cleanup_allowance` | `0.00` USD | No pods: reconstructions and practice run on the owner's host at no marginal spend |
| `permitted_runs` | `6` | Derived (below): the plan's block of 3 Constructor and 3 Attacker sessions |
| `max_concurrency` | `1` | One session at a time |
| `max_runtime_s` | `10560` | Derived: 48 calls × the 120 s provider timeout, plus 8 trials × the battery contract envelope's 600 s |
| `max_submissions` | `6` | Each session exports one record, so this equals `permitted_runs` |

### Arithmetic

This is engineering arithmetic from listed prices, not a new price.

**One call's reservation.** It is `ModelSelection.reservation_nano` at
`DEFAULT_SETTINGS`: 65,536 input tokens and 2,048 output tokens.
- **Constructor** on `deepseek-v4-flash-0731`, at 45 and 90 nanodollars per
  token (Engy, observed 2026-09-26):

      65,536 × 45 + 2,048 × 90 = 3,133,440 nanodollars = USD 0.00313

- **Attacker** on `glm-5.2`, at 680 and 1,500 nanodollars per token:

      65,536 × 680 + 2,048 × 1,500 = 47,636,480 nanodollars = USD 0.04764

**One run's worst case.**
- A Constructor epoch makes at most `MAX_PROVIDER_CALLS` = 48 calls:
  48 × 0.00313 = USD 0.150.
- An Attacker session is capped at 16 calls (CHALLENGE-PROTOCOL-04 slice 2,
  a per-role call cap): 16 × 0.04764 = USD 0.762.
- The worst case is the larger of the two, rounded up to the cent:
  **USD 0.77**.
- Each run's ledger is frozen with this as its money cap. So an escalated
  Constructor up to `glm-5.3-flash` (USD 0.47 worst case) still fits. A
  dearer rung stops on the cap, typed `run_cap_reached`, and never spends
  more.

**Runs.**

    ⌊ (5.00 − 0.00) / 0.77 ⌋ = 6 runs    (6 × 0.77 = 4.62 ≤ 5.00)

**Expected spend.** The plan's §7 figures, scaled to these call caps:
- about USD 0.03 for a Constructor session on deepseek;
- about USD 0.21 for an Attacker session on glm-5.2.

The block of 3 and 3 is about USD 0.73 expected, and USD 2.76 at worst. The
first live sessions measure the real figures and replace these.

**Campaign ceilings.** Both campaigns (constructor, attacker) have a USD 5.00
ceiling, the owner's choice of 2026-10-02. So only the grant binds.
