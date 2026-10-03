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
