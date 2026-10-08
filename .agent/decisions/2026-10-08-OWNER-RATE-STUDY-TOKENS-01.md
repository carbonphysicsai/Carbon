## 2026-10-08 — OWNER-RATE-STUDY-TOKENS-01: a tokens-only grant for SUBMISSION-RATE-STUDY-01's Graphite adversary arm

**Authority.** The owner, 2026-10-08: "approve rate-study tokens $30", relayed by
the Test Lead (not given to this session directly). This record takes effect only
when it is merged to main. Merging is the owner's confirmation through the PR Head.

**Context.** `docs/development/graphite/SUBMISSION_RATE_STUDY_01.md` section 9
proposed this grant for arm G-sealed (the Graphite probing adversary). Its D1 is
OWNER-RATE-STUDY-D1-01. The grant file is
`docs/development/graphite/grants/GRAPHITE-GRANT-RATE-STUDY-TOKENS.json`.

**Decision.**

| Field | Value | Basis |
|---|---|---|
| `grant_id` | `GRAPHITE-GRANT-RATE-STUDY-TOKENS` | this record |
| Provider | `graphite`, tokens only, no pods | plan section 9 |
| `permitted_runs` | 6, one at a time (`max_concurrency` 1) | 3 rates x 2 replicates |
| `worst_case_run_cost` | 4.91 USD | the same figure as GRAPHITE-GRANT-PHASE3-R3 (same role ladder) |
| `cleanup_allowance` | 0.25 USD | as the existing Constructor grants |
| `monetary_ceiling` | 30.00 USD | 6 x 4.91 + 0.25 = 29.71, rounded up |
| `max_runtime_s` | 39,600 | as the existing grants |
| `max_submissions` | 144 in the file; **set at the freeze** | see below |
| `account`, `expires_at` | `Carbon-Account` (a label), `2026-12-31T23:59:59Z` | as the existing grants |

**`max_submissions` is a ceiling now, not a decision.** The owner's approval
leaves the submission maximum to the freeze. The file carries 144, the largest
arm cap (m = 4: 36 tempos x 4), only because the grant format needs a value; a run's
real cap is the arm's scored-submission cap recorded in the frozen
`freeze-manifest.json` and may never exceed this file's value. If the freeze needs a
different number, a new grant version replaces the file (grants are never edited
in place after use).

**When the grant binds spend.** Only when all of these hold:
1. this record and the grant file are on main;
2. SUBMISSION-RATE-STUDY-01's `freeze-manifest.json` is on main, its
   `measures-v1.json` is `status: FROZEN`, and its digest is recorded in the
   Test Lead's freeze decision file (`RATE-STUDY-FREEZE-01`);
3. the runner binds this grant to the study's route (a code change by the Carbon
   Validator or Test Engineer: `grant_binding` registers phase-3/phase-4 grants by
   Challenge and does not know this one; the grant file alone spends nothing).

No G-sealed run starts before all three. Arms H and the scripted probers need no
grant. If the freeze finds the adversary needs an LLM call per scored submission,
the worst case per run changes and this grant is re-priced before any run.

**Not granted here.** Stage 0 compute (a separate owner approval), any pod, any
other arm, any production rate.

**Supplements** OWNER-RATE-STUDY-D1-01 and the grant records
OWNER-GRAPHITE-PHASE3-R3-01 and the cooling CPU-lane grant.
