# PRACTICE-QUIZ-01: the exam's quiz, practised on public items in the Launchpad

**Status:** READY. The Test Lead approved it with the rulings below on
2026-10-06, and it was committed after #686 merged. Slice 0 is
security-adjacent (it moves exam-side code into a shared module): the Carbon
Validator session reviews it.

**Authority:**
- The owner's direction, relayed by the Test Lead on 2026-10-06: miners
  practise on the same quiz they are graded on, using public questions.
  - The practice quiz uses B4's public design tasks (PRACTICE-SAFETY-01's B4
    on practice decision set v2, #682 and #689) and a public near-limit case
    set drawn from TRAIN/PRACTICE material.
  - It scores both with the same quiz code and fixed optimizer the validator
    uses (Q2 and Q3, #686 and #685), so local practice reproduces the exam's
    mechanics.
  - It adds retired hidden batches' quiz items to the practice pool once they
    are published.
  - Invariant 12 holds throughout: practice is never the official exam, and
    hidden quiz items never appear before retirement.
- The owner, 2026-10-06 (through VALIDATOR-19 slice Q): "Yes make the quiz
  questions maximally effective."
- OWNER-BATTERY-3B-AND-EXPOSURE-01: a miner sees a hidden batch only after
  Carbon retires it and commits it to the training data pool
  (`CARBON_COMMIT_TO_TRAINING_POOL`). Retirement by rotation alone releases
  nothing.
- OWNER-VALIDATOR-MAINNET-PARITY-01 item 5: retired batches are published into
  the training data. That release path does not exist yet.
- PRACTICE-SAFETY-01's hard rules 1–5 apply unchanged to every practice-quiz
  measure.

**Executor:** the Test Engineer session. The Carbon Validator session reviews
slice 0 and owns every change on the exam side.

**Primary `map_ref`:** to be confirmed at ticket start against the hub source.
This draft does not invent one.

**Depends on:**
- #686 (merged): `score_tuning.near_limit`, `false_infeasible_rate`,
  registries v3–v6 and the disagreement panel v1;
- #689 (merged): B4 on set v2, `practice-inputs.v2` staging and practice
  feedback v3;
- VALIDATOR-19 slice Q (design merged in #685, not built), for the exam-side
  caller of the shared quiz code;
- VALIDATOR-19 S3 (not built), for the release queue;
- the `CARBON_COMMIT_TO_TRAINING_POOL` release path, which does not exist yet.

## What Q2 and Q3 are (read from #686 and #685)

- **Q2, per-case near-limit quiz** (quiz-registry-v3, `panel_disagreement`).
  - The pool is the cases whose reference lies within a margin of the plating
    or peak-temperature limit, on either side (`score_tuning.near_limit`, in
    contract bands).
  - From the pool, it keeps the cases where the versioned public panel
    (`disagreement-panel-v1.json`, 80 EV4 first-seed recipes) splits most
    evenly between feasible and infeasible.
  - **Measures:** G-FEAS (`score_tuning.false_feasible_rate`), G-PLATE
    (`score_tuning._plating_fa`, via `false_acceptance.component`), and
    false-infeasible (`score_tuning.false_infeasible_rate`).
- **Q3, decision-scenario quiz** (quiz-registry-v4, `decision_scenarios`).
  - Each scenario is a pre-solved 35-candidate grid at one condition.
  - The candidate model, inside the fixed registered optimizer (EV4's decision
    rules: grid, constraints, tie rule, abstention), picks one protocol.
    `value.decision.assess_predicted` and `select` make the pick.
  - The pick is checked against the reference grid (`assess_reference`,
    `outcome`). The validator solves nothing.
  - **Gate measure:** decision false-feasible, the share of SELECTED_INFEASIBLE
    picks. Regret (mean `decision_loss`) and over-caution (the
    MISSED_OPPORTUNITY share) are reported beside it.
  - All-infeasible scenarios are excluded (quiz-registry-v5).
  - Score-tuning registry v3 adds leg `q = 1/(1 + mean Q3 regret)`.
- **The agreed exam quiz** (VALIDATOR-19 slice Q): both types on every hidden
  batch and on `graphite-tuning-v2`. Its sizes come from the public stand-in
  and are not adopted. The margin, the thresholds, the quiz share and rule v3
  stay HUMAN_INPUT. Until rule v3 is adopted, the exam quiz gates nothing.

## Scope

1. **One shared quiz module**, used by both the validator's quiz (VALIDATOR-19
   slice Q) and practice. It holds Q2's selector and measures and Q3's judge,
   with no dependency between the two callers (see *Shared-code boundary*).
2. **The practice quiz pool**, versioned and digest-pinned:
   - **Q3 items:** the 6 B4 conditions of practice decision set v2, each a
     35-candidate reference grid, already staged to the worker as
     `practice-inputs.v2`;
   - **Q2 items:** a public near-limit case set, selected by Q2's own rule from
     TRAIN/PRACTICE material only;
   - **released items:** retired hidden batches' quiz items, once retired and
     published (see *Retirement and publication rule*).
3. **Practice-quiz feedback:** a new, allow-listed `quiz` block in battery
   practice feedback, computed by the shared module, feedback only.
4. **The Launchpad** renders the block in the practice result, labelled as
   practice, with no gate verdict.

**Not in scope:**
- any change to the practice score, rules v1 and v2, the exam's gates, B1–B4's
  definitions, or the EV studies;
- building VALIDATOR-19 slice Q, S3, or the release path;
- choosing the quiz margin, thresholds, sizes or quiz share;
- cooling and motor (battery first; another Challenge needs its own Q2/Q3
  registration).

## Reused versus new

| Item | Class | Notes |
|---|---|---|
| `carbon/battery/value/decision.py` (`measure`, `check`, `assess_predicted`, `select`, `assess_reference`, `outcome`) | KEEP | The fixed optimizer. It imports only `math`, so it is already a safe leaf. |
| `score_tuning.near_limit`, `false_feasible_rate`, `false_infeasible_rate`, `_plating_fa`; `margins._margins`; `false_acceptance.component` | WRAP | Their bodies move into the shared module unchanged. The originals delegate, keeping their signatures (slice 0). |
| Q3 judging in `scripts/dev/battery/quiz_q3.py` | WRAP | Its per-scenario outcome becomes a library function in the shared module. The script then calls it. |
| `practice_safety.DECISION_RULES` and `CANDIDATES` (copies of EV4's contract, test-bound) | KEEP | They become the shared module's pinned rules object, extended with EV4's `mistake_costs` and `minimum_useful_improvement_s`, copied and test-bound the same way. No value is new. |
| Practice decision set v2 and its pin (`DecisionSet`, `load_decision_set`) | KEEP | These are the Q3 items. |
| `practice-inputs.v2` staging (#689) | KEEP | The worker already predicts the 210 grid inputs. |
| `disagreement-panel-v1.json` | KEEP | Q2's panel version, recorded with the public set. |
| `seeds.verify_reveal` | WRAP | Moves to a public-journal leaf that `seeds.py` re-exports, so practice can verify reveals without importing the seed journal. |
| `pool_store.releasable`, `mark_released`, `BATCH_STATES` | KEEP | They are read only by the release path (operator side), never by practice. |
| `carbon/practice_safety_feedback.py` allow-list machinery | KEEP | The quiz block uses the same `allowed=` refusal mechanism. |
| Launchpad `renderChallengePractice` (`scripts/dev/miner_launchpad/app.js`) | REPAIR | It gains a quiz section. |
| The public near-limit set, the practice-quiz pool manifest, the release-bundle consumer, the quiz feedback block | NEW | |

## Shared-code boundary (practice and exam mechanics identical; the exam never depends on practice)

**The module.** `carbon/battery/value/quiz.py` (the name is the working
decision).
- **Its imports are limited to** the standard library and
  `carbon.battery.value.decision`. A test enforces that list.
- **It holds:**
  - `QuizRules`: EV4's decision rules, candidate grid, bands and mistake costs,
    each copied from `ev4-charge-protocol-selection.v1.json` and bound to it by
    a test, plus `rules_digest()`;
  - `margins(rules, outputs)` and `near_limit(rules, outputs, margin)`. The
    margin is a required argument with no default;
  - `q2_measures(rules, predictions, case_ids, refs)`, which returns G-FEAS,
    G-PLATE and false-infeasible;
  - `q3_outcome(rules, scenario, grid_predictions, grid_references)`, which
    returns the pick, the outcome kind and the decision loss;
  - `q3_measures(outcomes)`, which returns decision false-feasible, regret and
    over-caution, with the registry-v5 exclusion of all-infeasible scenarios.
- **It holds no item selection by membership, no margin value, no threshold
  and no verdict.** Thresholds and verdicts belong to rule v3, which is
  exam-side and HUMAN_INPUT.

**Who imports it:**
- **Exam side:** `score_tuning` (delegating, unchanged signatures),
  `margins`/`false_acceptance` (delegating), and VALIDATOR-19 slice Q's
  validator quiz;
- **Practice side:** a new `carbon/battery/practice_quiz.py`, called from
  `BatteryPractice` beside `practice_safety.safety`.

**Import-graph rules, each enforced by a test:**
1. `value/quiz.py` imports nothing in `carbon/battery` except
   `value/decision.py`.
2. **No exam module imports a practice module.** No module in the validator
   path (`daemon`, `pool_store`, `exam`, `seeds`, `deployment`, `intake`,
   `value/*`, `carbon/challenge_validator/*`) imports `practice`,
   `practice_safety`, `practice_quiz`, `research`, or anything under
   `scripts/dev/miner_launchpad`.
3. **No practice module imports exam state.** `practice_quiz` imports no
   scoring-set, pool-store, seed-journal, daemon or study-campaign module
   (PRACTICE-SAFETY-01's import-graph check, extended).
4. **One copy only.** No second implementation of Q2's measures or Q3's judge
   exists on either side. A test greps for re-definitions of the shared
   function names outside `value/quiz.py`.

**Rule binding.** Every practice-quiz result and every exam quiz report
records `rules_digest`. A test asserts that the practice rules digest equals
the exam's for the same contract version. A future rule change is a new
`QuizRules` version on both sides, never on one.

**Exam behaviour unchanged.** Slice 0 is a pure move. Golden tests reproduce
these committed outputs byte for byte from the delegating `score_tuning`:
- `comparison-v5-public-standin.json`;
- `q3-v5-public-standin.json`;
- `value-v6-public-standin.json`;
- `test_battery_score_tuning.py`.

## The public near-limit set (Q2 items)

- **Source:** TRAIN v1 and PRACTICE material only (`practice.TRAIN_V1_PATH`
  and `PRACTICE_SOURCE_PATH`, both pinned).
  - **Never** the public scoring set (the 1588-case stand-in #686 used),
    which PRACTICE-SAFETY-01 rule 2 forbids, and never EV conditions or
    protected grids.
- **Selection:** Q2's own rule, through the shared module. The pool is cases
  within the margin, on both sides. The kept cases are those where panel
  version N splits most evenly.
  - The set records the panel version, the margin and the source digests.
  - It is selected and committed before any miner sees it, like B4's set.
- **Margin:** the exam's margin is HUMAN_INPUT. Until the owner adopts one,
  the set is built at quiz-registry-v3's registered development value
  (`pool_margin_bands`) and labelled DEVELOPMENT. It is reselected as a new
  version when the owner adopts a margin.
- **Panel predictions** on these public cases need the 80 panel recipes
  trained and run. That is new compute: a grant is proposed with platform,
  budget and runs, and the owner approves it before any run.
- **The in-sample problem** (open, see HUMAN_INPUT 3). A TRAIN-drawn item is
  in the miner's own training data, so it measures recall, not the exam's
  generalisation. The default is PRACTICE-drawn items only.
- **Disjointness:** the same test as `test_practice_safety_disjoint.py`, at
  4 dp, against EV1/2/4/5 conditions, EV4's protected grids and EV5's
  optimizer grids.

## Retirement and publication rule (released items)

A hidden batch's quiz items enter the practice pool **only** when every one of
these holds. Each is checked against the pool store's and the journal's own
states, never inferred.

1. **Retired in the pool store.** The batch's `pool_store` state is `RETIRED`
   or `CONSUMED` (rotation's `UPDATE ... state='RETIRED'`). It is not held by
   a `FROZEN` final, so it appears in `PoolStore.releasable()`.
2. **Retired and revealed in the journal.** The public seed journal holds a
   `retire` entry, then a `reveal` entry for the fingerprint.
   `seeds.reveal` refuses before retirement (`RevealRefused`), and
   `verify_reveal` confirms the revealed document's digest equals the
   fingerprint committed earlier (commit sequence < retire < reveal).
3. **Released in the pool store.** `mark_released(fingerprint)` has moved the
   batch to `RELEASED`. It refuses with `release_before_retirement`
   otherwise.
4. **Published by the owner's release path.** The batch was committed to the
   training data pool by `CARBON_COMMIT_TO_TRAINING_POOL`, under an owner
   release decision (VALIDATOR-19 §3: release is never automatic). The
   release bundle carries that record's id and digest.

**Who checks what:**
- **The operator-side release path** (VALIDATOR-19 S3; not this ticket)
  checks 1 and 3 against `pool_store`, and emits a public release bundle.
  The bundle holds the revealed batch document, the quiz membership from
  inside it, the batch's reference records with their digest, the rule and
  contract digests, and the release record id plus digest.
- **The practice consumer** (`practice_quiz.load_released`) reads only public
  bytes:
  - the public journal (`seeds.public()` form) and the release bundle;
  - it re-verifies 2 with the shared public-journal verifier;
  - it checks the bundle's reference digest against the batch's committed
    references digest, and checks the release record field (4).
- **The consumer never opens validator state.** A typed refusal applies to
  each case: no reveal, a reveal before retire, a digest mismatch, a missing
  release record, an unknown schema, or a references digest mismatch. Nothing
  is added on a refusal.

**Pool versions.** The practice-quiz pool is an append-only manifest:
- v1 is B4 set v2 plus the public near-limit set;
- each release appends one bundle, by fingerprint and digest.

Every practice result records the pool version it used. Old results keep
their meaning (invariant 10).

**Until the release path exists,** the released-items stratum is empty and
reports `"BLOCKED: no release path (CARBON_COMMIT_TO_TRAINING_POOL)"`. Its
tests run on synthetic, structurally non-production bundles, which a
`fixture: true` marker keeps out of every real manifest.

## Disclosure allow-list (the `quiz` block)

The block follows PRACTICE-SAFETY-01 rule 4.

**Allowed:**
- per stratum (`q2_public`, `q3_public`, `released`): `items`, `measured`,
  `unmeasured` and `unresolved` counts;
- Q2: G-FEAS, G-PLATE and false-infeasible, each as a rate with its numerator
  and denominator counts;
- Q3: decision false-feasible, mean regret, over-caution, `chosen`,
  `abstained`, `excluded_all_infeasible`;
- `rules_digest`, `pool_version`, the panel version, and the material
  `{path, sha256}` pins;
- released bundle fingerprints (public in the journal after reveal);
- `"feedback_only": true` and `"official": false` on every computed field;
- a literal stating that this is the practice quiz on public items, not the
  exam, and that it gates nothing.

**Refused, by the allow-list's typed refusal:**
- per-case ids, values or PASS/FAIL;
- per-condition picks or verdicts;
- per-scenario outcomes;
- any gate verdict, threshold, cutoff or margin-relative pass statement (rule
  v3 is not adopted; see B2's rule);
- any field about a non-released batch: fingerprint, pool version, quiz share,
  membership, counts;
- seeds, roots, draw ids;
- exam scores or ranks.

**Launchpad:** it renders only the allow-listed fields, under the heading
"Practice quiz (public items, not the exam)". It shows no verdict colour and
no pass or fail wording.

## Invariant tests

**No hidden item before retirement** (`tests/cpu/test_practice_quiz_release.py`):
- On a synthetic `PoolStore` plus journal:
  - ACTIVE, PREPARED, FINALIST, and RETIRED-but-not-RELEASED batches are each
    refused by the release path;
  - a RETIRED batch held by a FROZEN final is not in `releasable()`;
  - only a RELEASED, revealed batch with a release record produces a bundle.
- **The consumer refuses:**
  - a bundle without a journal reveal;
  - a reveal whose sequence precedes its retire entry;
  - a tampered document (digest mismatch);
  - a missing or forged release record;
  - a references digest mismatch.
- A mutant that skips the reveal check must fail the suite.
- The import-graph check: `practice_quiz` imports no `pool_store`, `seeds`,
  `daemon` or scoring-set module.
- The staged worker files contain no item from a non-released bundle. The
  test seeds a sentinel case in an ACTIVE batch and greps the staging.

**Practice never official** (`tests/cpu/test_practice_quiz_isolation.py`):
- Every computed field carries `feedback_only: true` and `official: false`.
- **Provenance:** practice results keep `BATTERY_PUBLIC_PRACTICE`. The
  validator's intake and daemon refuse any input carrying a practice
  provenance or a practice-quiz schema.
- **No exam path reads practice:** an import-graph check over the exam
  modules listed under *Shared-code boundary*.
- Practice-quiz measures enter no score leg, gate, rank, nomination, frontier
  event or settlement. Grep-level and call-graph tests cover `score_tuning`
  legs and `daemon` scoring.
- **Invariant 12:** the practice pool never contains an item of a still-hidden
  batch, the sealed tuning set (`graphite-tuning-v2`), or a confirmation set.
  The release path checks this operator-side, and the consumer checks that a
  bundle's role is `screening` or `finalist`, never a producer-only role.

**Identical scoring on the same input** (`tests/cpu/test_practice_quiz_parity.py`):
- **Same function and same bytes:** for fixed predictions, references and
  items, the practice entry point and the exam entry point (slice 0:
  `score_tuning` delegates; later: VALIDATOR-19 slice Q's validator quiz)
  return canonical-JSON-identical Q2 and Q3 measures.
- The practice and exam `rules_digest` are equal. A mutant tie rule or a
  mutant band on either side breaks the equality test.
- **Golden reproduction:** on the committed public stand-in, the shared module
  reproduces #686's `comparison-v5`, `q3-v5` and `value-v6` per-member
  numbers exactly.
- **B4 and Q3 are distinct definitions.** B4's `rate = feasible_choice/chosen`
  (#689's engineering decision) and Q3's decision false-feasible use
  different denominators. A test pins both on the same predictions, so
  neither is silently redefined as the other.

## The Test Lead's rulings (2026-10-06)

1. **Abstentions.** Practice's Q3 uses the exam's definition through the
   shared module, so practice equals the exam. B4's rate keeps its own
   definition, but reports name it `b4_feasible_choice_rate`, so it is never
   read as the Q3 number.
2. **Rule 2 wording.** Accepted as `DOCUMENTATION_LAG`: released batches are
   public. PRACTICE-SAFETY-01's rule 2 is amended in the same commit as this
   ticket.
3. **TRAIN-drawn items are allowed** in the public near-limit set. They are
   already public, so they add no exposure, and invariant 12 holds because
   the scored quiz stays hidden. This is the Test Lead's ruling, not
   HUMAN_INPUT.
4. **The quiz margin and the set sizes** come from the tuning-set curves, and
   the owner picks them. They stay HUMAN_INPUT.

## Delegated working decisions (confirmed by the Test Lead)

1. **The shared module lives on the exam side** (`carbon/battery/value/`).
   Exam modules keep their signatures and delegate to it. Practice imports it.
   The Carbon Validator owns changes to it.
2. **Practice reads only published bytes.** It reads the public journal and
   release bundles, never validator or producer state.
3. **B4 stays as v3 defines it.** The Q3 measures on the same 6 conditions are
   reported in the new `quiz` block beside it.
4. **A new feedback schema version** (`carbon.battery.practice-feedback.v4`)
   adds the `quiz` block. v3 results keep their meaning.
5. **Seam classification.** A released batch is neither hidden nor sealed, so
   adding it under PRACTICE-SAFETY-01 rule 2 is `NO_CONFLICT`. Rule 2's text
   ("never read hidden or private pools, sealed batches") is amended to allow
   a released batch. That made it `DOCUMENTATION_LAG`, which the Test Lead
   accepted (ruling 2).

## HUMAN_INPUT, fail closed

1. **The quiz margin** (owner; swept). Until it is adopted, the public
   near-limit set uses the registry-v3 development value and is labelled
   DEVELOPMENT.
2. **The practice set sizes** (Q2 item count; Q3 uses B4's 6, fixed by its
   ruling). These are owner or Data Collection values: none is chosen here.
3. ~~TRAIN-drawn items~~: settled by the Test Lead's ruling 3 (allowed).
4. **The release decision** for each retired batch, and the release path
   itself (`CARBON_COMMIT_TO_TRAINING_POOL`) (owner; VALIDATOR-19 §3). Until
   both exist, the released stratum is BLOCKED.
5. **Whether release bundles publish reference records** with the revealed
   document (owner, under OWNER-BATTERY-3B-AND-EXPOSURE-01). Without
   references, no released item can be scored, and the stratum stays BLOCKED.
6. **In-sample labelling for released items** (Test Lead). Released batches
   enter the training data pool, so they are in-sample for models trained on
   a later TRAIN version. The proposal is to report them as their own stratum,
   labelled with the TRAIN version that contains them.
7. **Panel compute** for Q2 selection on public cases (owner; a grant
   proposal).
8. **Any per-item disclosure** beyond aggregates (Test Lead or owner). The
   default is none, per PRACTICE-SAFETY-01 rule 4.
9. **Showing a gate verdict in practice** after rule v3 is adopted (owner).
   The default is never.

## Slice plan

- **S0: the shared quiz module (pure move, exam-reviewed).**
  - `value/quiz.py`, with `QuizRules` bound to EV4's contract;
  - `score_tuning`, `margins` and `false_acceptance` delegate;
  - `quiz_q3.py` calls the library;
  - the public-journal verifier leaf, re-exported by `seeds.py`;
  - golden byte-identity tests and import-graph rules 1–4.
  - **Needs:** #686 merged. The Carbon Validator reviews it.
- **S1: the Q3 practice stratum.**
  - `practice_quiz.py`, which scores B4 set v2's 6 grids through `q3_outcome`
    and `q3_measures` from the already-staged `practice-inputs.v2`
    predictions;
  - feedback v4's `quiz.q3_public`;
  - the allow-list and the parity tests.
  - **Needs:** #689 merged.
- **S2: the public near-limit set (Q2 items).**
  - The selection script, which commits the set, its `SHA256SUMS`, the panel
    version and the margin label;
  - the disjointness test;
  - staging of the set's inputs (`practice-inputs.v3`);
  - `quiz.q2_public`.
  - **Needs:** the panel-compute grant (HUMAN_INPUT 7) and the owner's margin
    and set sizes (HUMAN_INPUT 1 and 2).
- **S3: the released-items consumer.**
  - `load_released`, the pool manifest, typed refusals and synthetic-fixture
    tests;
  - the stratum reports BLOCKED until a real bundle exists.
  - **Needs:** VALIDATOR-19 S3's bundle schema (proposed to it by this ticket,
    not frozen here).
- **S4: the Launchpad.**
  - The quiz section in `renderChallengePractice` and the allow-listed fields
    only;
  - `test_miner_launchpad*.py` and browser-smoke coverage.
- **S5: closeout.**
  - The lessons entry (`carbon/challenge_pipeline/lessons/`);
  - the hub event.

**Validation (each slice):** the targeted tests above, plus
`test_practice_safety_*`, `test_battery_score_tuning.py`,
`test_battery_practice_material.py` and `test_miner_launchpad*.py`, run
through `./scripts/dev/canonical.sh`. CI runs the full suite.

## Maturity ceiling

At most IMPLEMENTED and TESTED (DEVELOPMENT), feedback only.
- **Not SCIENTIFICALLY_QUALIFIED:** the quiz sizes come from a public
  stand-in, no design met the registered bar without the v5 known-bad set,
  and rule v3 is unadopted.
- **Not SECURITY_QUALIFIED:** the release-path isolation is VALIDATOR-19's,
  and it needs a dedicated review.
- **No authority:** no score, gate, rank, frontier, settlement or LIVE
  authority.
- **The released stratum's ceiling is SPECIFIED** until a real release bundle
  exists.
