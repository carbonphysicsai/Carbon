# VALIDATOR-23: hidden batches drawn from pre-solved banks

**Status:** design, then slices. Security-sensitive (AGENTS.md §13): it
changes how hidden cases are committed, drawn and imported. It needs a
dedicated review.

**Authority:**
- **OWNER-BANK-ARCHITECTURE-01** ("approve bank plan", 2026-10-07);
- Data Collection's bank policy registry (`claude/quiz-load-memo` @ 4aca2186,
  `docs/development/evidence/quiz-bank-policy-v1/registry.json`; basis: the
  quiz-load memo §3);
- OWNER-SHARED-ANSWER-KEY-01.

**Builds on:** VALIDATOR-19 (producer, answer key, rotation) and VALIDATOR-21
(the shared hidden store and the second Challenge).

**Executor:** the Carbon Validator session.

## Why

Today every rotation solves a fresh batch and its quiz. At the approved
cadences that is about 1.7 AX42s for battery, motor and the cooling cell
alone. With a bank, a rotation costs about zero solves. Compute goes into
topping up the bank at n/E cases per batch, about E times cheaper.

B and E are also chosen so that the cheapest way to score well is to learn
the population, not the bank (memo §3: at B ≥ 10n, fitting the bank pays at
most about 3 % false-feasible).

## Design

1. **The bank ledger** (`challenge_validator/bank.py`, Challenge-neutral,
   producer-only).
   - **Banks.** Each Challenge has named banks:
     - `pool`, a faithful draw from P;
     - `q2`, the near-limit stratum;
     - `q3:<stratum>`, one bank per registered condition stratum.
   - **Tranches.** A tranche is drawn by the Challenge's source from the
     producer root under a tranche role (`bank-<bank>-T<k>`). It is committed
     to the producer's journal before use, then solved, then **sealed**:
     - the Merkle root over `H(canonical {case_id, inputs, reference})`, in
       case-id order;
     - the references digest and the case count.

     The tranche commitment is public.
   - **Live set.** Sealed tranche cases with an `OK` reference, not retired.
     A case whose reference failed never enters the live set; it is counted.
   - **Window draw.** It is seeded by `HMAC(bank key, "window/<bank>/<slot>")`
     and draws n live cases uniformly, without replacement. It never repeats
     a case of another window of the same bank still active at that slot.
     - Stratified banks draw their per-stratum quotas, each uniformly within
       its stratum.
     - The draw is stored once per window; a redraw differently is refused.
   - **Exposure.** Each window draw adds one exposure per case. At E the
     case retires: it leaves the live set and enters the release queue.
   - **Automatic publication** (OWNER-AUTO-PUBLISH-RETIRED-01): once every
     window that drew a retired case has ended and is revealed
     (`window_revealed` journals its case ids, which digest to its
     selection digest), the case publishes into the Challenge's public
     training pool. It goes out as a training file signed with the producer
     key, each case with its tranche root and Merkle proof, served
     read-only by the distribution host (`training_pool`).
     - An unretired case is refused (`bank_case_not_retired`), as is an
       unrevealed window (`bank_window_not_revealed`).
     - Only `pool`, `q2`, `q3:<stratum>` and `canary` are bankable, so
       tuning, confirmation, study and EV material can never publish.
   - **Top-up.** When the live set falls below B, a new tranche of the
     deficit is drawn from the same stratum. While it is unsealed, draws use
     what is live. A bank with fewer than n live cases cannot fill a window,
     and the slot is recorded unfilled, as today.
2. **The v2 window commitment.** The commitment gains
   `bank: {"bank_rule", "tranches": [{tranche, root, cases, sealed_sequence}], "selection_digest"}`.
   The package payload carries the Merkle proof of every drawn case.
3. **Validator import.** Before anything is stored, every drawn case's
   `(case_id, inputs, reference)` must prove into a committed tranche root.
   - The tranche must have been sealed before the window's activation: a
     sealed sequence earlier than the window's journal sequence.
   - Duplicates and refusals behave as today.

   Fairness holds: every validator imports the identical signed package.
4. **Battery, first** (cheap class: B = 20n, E = 5).
   - **Pool bank:** n = 100, the rule's screening size, so B = 2,000.
     Tranches are drawn with `seeds.make_batch`, with their duplicate
     dropped, and solved in the pinned truth image.
   - **The window batch** is a `PrivateBatch` of n − 2 drawn cases plus 2
     hidden duplicates (opaque ids from the window seed), so battery's
     import, journal and scoring are unchanged.
   - **Quiz:** `q2` (n = 80, B = 1,600) and `q3:<stratum>` (k = 8 scenarios
     per window, B = 160, stratified). Each Q3 scenario is solved with its
     lattice and refine and settled once, at tranche seal.
   - **A new battery rule version** (`v2-bank`) carries B, E and the bank
     names. Battery's current deployment stays on v2.
5. **Diagnostics,** all public counts:
   - per-stratum P coverage after every retirement;
   - per-case exposure histogram;
   - turnover;
   - the fit-versus-learn ceiling's inputs (B/n, E, live size).
6. **The canary** (CFD class, with cooling or motor): a disjoint near-limit
   canary scored, unreported, beside the quiz, and a one-sided Fisher flag.
   Its alpha is HUMAN_INPUT, null until set.

## Slices (one PR per slice, each to main)

1. **This contract, the decision record, and the bank core**: ledger,
   tranches, Merkle, window draws, exposure and retirement, top-up,
   coverage. Tests on a synthetic source.
2. **The battery pool bank and the v2 commitment and import.**
3. **Design-question banks** (amended 2026-10-08, the Test Lead's slice 3
   decisions D1–D3; see "Slice 3" below).
4. **Motor** (motor-like class), once its design space is revised.
5. **The canary,** with the first CFD-class Challenge.

## Slice 2, as built (battery's pool bank)

- **Rule `v2-bank`** (`exam.DEVELOPMENT_RULE_V2_BANK`): v2, unchanged, plus
  `bank.pool`:
  - `window_cases` 98, with v2's 2 hidden duplicates added;
  - `size` 2,000: 20n, with n = 100 cases per window. The screening and
    finalist windows share the one bank.
  - `retire_at` 5.

  Battery's current v2 deployments are unaffected. A deployment moves onto
  the bank only by naming the rule.
- **`battery_bank.BankedBatterySource`** (producer-only), selected by the
  producer config's new optional `bank` key.
  - **Tranches** are drawn with `seeds.make_batch` from the producer
    deployment's own root (duplicate dropped, published cases refused),
    solved in the pinned truth image and sealed.
  - **Windows:** each slot role (`pscreen-S<n>`, `pfinal-S<n>`) draws from
    the bank, disjoint from every window of the slots still active. The
    hidden duplicates are root-derived. The window becomes a `PrivateBatch`
    imported into the producer deployment, with its references from the
    bank, so seal, export and check are battery's own.
  - **Top-up:** when a window finds the bank short, the deficit is drawn,
    solved and sealed first. `battery_bank fill` does the first fill.
- **The v2 commitment** adds `bank` (`{bank, rule, tranches, selection_digest}`),
  and the package adds `bank.proofs`.
- **The validator** (`BatteryAdapter._checked_bank`) refuses unless:
  - the bank values are its rule's;
  - the selection digest is the drawn ids';
  - every drawn case's id, inputs and reference prove into a committed
    tranche root.

  It also refuses a bank package under a rule without a bank. The codes are
  `answer_key_bank_{missing,mismatch,proof}`.
- **Not yet:** the tick reveals ended windows and auto-publishes retired
  cases once #760 merges (slice 2b).

## Tests (slice 1)

- Tranche seal: Merkle roots and proofs verify, and a changed case,
  reference or order fails.
- Window draws:
  - deterministic per slot;
  - without replacement;
  - disjoint from other active windows of the bank;
  - stratum quotas respected.
- Exposure:
  - exactly one per draw;
  - retirement at E into the release queue;
  - the live set returns to B by top-up.
- Failed references never go live.
- An unfillable window is recorded, never filled late.
- Diagnostics are public counts only.

## Out of scope

- The canary's alpha.
- LIVE values.
- Cooling (on hold, #752).

## Maturity ceiling

IMPLEMENTED and TESTED. Not SECURITY_QUALIFIED or SCIENTIFICALLY_QUALIFIED.
No LIVE authority.

## Slice 3: design-question banks (amended 2026-10-08)

**The Test Lead's decisions** (within the quiz-design remit):
- **D1: Q2 is out of the design banks.** Q2's near-limit cases are accuracy
  and safety cases: they go through the case bank and pool path, as
  near-limit strata. Design banks hold design questions only: Q3 now, and
  indexed charge maps later.
- **D2: k = 8, B = 160, E = 5,** registered as development working values
  (`design_bank.DESIGN_BANKS`).
  - k is a registered parameter, not a constant. The sealed v8 quiz's power
    report shows that 8 questions can't separate a bad control within one
    batch.
  - So per-miner evidence accumulates across batches. That is a first-class
    field of slice 3c's outcome records.
- **D3: the Test Lead registers battery Q3's score rule:** OWNER-BATTERY-SCORE-
  RULE-01's q leg, through #827's bridge.

**Design.**
- A design bank is a `BankLedger` bank `design:<id>`. One case is one
  question:
  - `inputs` are `{task, task_digest, draw}`, a frozen plain or indexed
    task;
  - `reference` is the bridge's `{status: OK, panel | per_index}`, or a
    terminal non-live status.
- A Challenge supplies one `QuestionLaw`: `draw`, staged `next_stage`, and
  `references`. The bank core is unchanged apart from the bank name.
- **E counts every question draw:** +1 per window that serves the question,
  including a window later voided.

**Slices:**
- **3a (this PR):**
  - `design_bank`: `QuestionLaw`, `DesignBankSource`, `DesignBank` (staged
    and resumable fill) and the CLI;
  - the battery Q3 law (`battery_q3_bank`): v8's neutral task; lattice, then
    refine, then settle; live only when reference-feasible with every
    candidate's truth defined.
- **3b:** producer windows draw design questions. This brings:
  - a commitment `design` field;
  - questions with proofs in the package;
  - validator import verification;
  - per-stratum reporting.
- **3c:** bridge scoring under the registered rule (report-only), with
  cross-batch per-miner evidence.
- **3d:** the indexed law for battery v3, after the owner approves its
  question law.
