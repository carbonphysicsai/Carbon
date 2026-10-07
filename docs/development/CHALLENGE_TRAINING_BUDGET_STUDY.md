# Challenge training budget study: testnet test spec

**Authority.** The owner adopted this spec on 2026-09-29 as
OWNER-TRAINING-BUDGET-STUDY-01 (`.agent/DECISIONS.md`). The source is the
owner's "Challenge Training Budget Study: Testnet Test Spec" of 2026-09-28.

**The requirement.** It is a **standing launch requirement.** Every Carbon
Challenge completes this study, with its own sheet:
- before its training limit is set;
- before it pays rewards.

The readiness records enforce it. Each record carries a required
`training_budget_study` block, and the validator refuses a launch approval
unless that study is `COMPLETE`, with a result and an owner decision
(`carbon/challenge_readiness/record.py`).

**Extended 2026-10-06 (OWNER-TRAINING-BUDGET-STUDY-02).** The study also
decides each Challenge's **TRAIN data size** and the **validator capacity**
its submission cadence needs. It adds questions 8-10, Phases G and H and rules
R9-R11 (`training_budget_study/DECISION_RULES_R9_R11.md`). R1-R8 are
unchanged. See [Extension: data size, screening and cadence](#extension-data-size-screening-and-cadence).

**One study for every Challenge (OWNER-COMPUTE-BUDGET-01).** Every
Challenge runs this same study with the same Challenge-neutral code. A
Challenge supplies only its sheet and its adapter
(`training_budget_study/SHEET_TEMPLATE.md`); battery is the first instance,
never the design. The intended outcome for each Challenge is **one compute
budget**, the same for every recipe and spent in any ratio, adopted once R5
passes for that Challenge. The build is ticket TRAINING-BUDGET-01.

**Order.** Battery runs it first, on testnet, with the values in its Battery
sheet. New Challenges start from the New Challenge sheet. **Neither sheet is
in the repository yet.** The Battery sheet's values stay open until it is
supplied, and nothing that needs them runs before then.

## Purpose and the decision it informs

The study decides how Carbon limits training on a Challenge. There are three
options:
- keep its step caps;
- raise them;
- replace them with a compute-cost limit calculated from each recipe.

Each run happens off-chain, on a testnet GPU pod, using the validator's pinned
image. It ends in a recommended limit backed by measured evidence.

Each run delivers:
- **a recommended training limit:** its level, and its unit (separate caps,
  or one compute budget);
- **a cost formula,** calibrated against measured rebuild time;
- **evidence that the chosen limit does not change which recipe wins,** or a
  clear statement that it does.

Three principles are fixed going in:
- **A limit is calculated from the recipe and checked at submission.**
  Training never stops on a clock, because validators on different hardware
  would then build different models.
- **Every recipe gets the same budget.**
- **The limit sits above the point where scores stop improving,** so it
  protects validators without limiting miners.

## Questions the study answers

Each question is tied to a decision rule:
1. **Plateau.** At what training budget do the best recipes stop improving,
   measured against the exam's own resolution?
2. **Cost.** How does rebuild time grow with each setting the Challenge
   allows, and which formula predicts it?
3. **Trade-off.** At equal compute, does a bigger model trained for fewer
   steps beat a smaller model trained longer?
4. **Ranking stability.** Does the best recipe at the proposed limit stay
   best at four times that budget?
5. **Determinism.** Do same-seed rebuilds stay bit-identical at the largest
   settings, and when two rebuilds share one GPU?
6. **Load.** How many rebuilds per hour can one validator GPU carry at the
   proposed limit?
7. **Gaming.** Can a recipe cost far more to rebuild than the formula
   predicts?

8. **Data size.** How large must the TRAIN set be before more data stops
   improving the best recipes? (R9)
9. **Screening.** How small a rebuild budget still orders submissions well
   enough that no finalist is screened out? (R10)
10. **Cadence capacity.** How many GPUs does one validator need to rebuild
    every submission at the Challenge's cadence? (R11)

## Scope and approvals

Each run is off-chain development evidence for one Challenge. It needs owner
approval before any pod time, and the Challenge's sheet holds the values.

**In scope:**
- one registered Challenge version;
- the validator's rebuild worker, on the sheet's GPU and pinned image;
- the Challenge's fixed TRAIN set;
- new, study-only evaluation cases.

**Out of scope:**
- the live hidden batches;
- the Challenge's exam rule;
- chain transactions;
- miner submissions and payouts.

**What needs approval:**

| Item | Who | Why |
|---|---|---|
| The spend ceiling | Owner | Pod time comes out of the Challenge's track budget |
| A study-only contract with raised ranges | Owner, with tech-lead review | Registry ranges are owner decisions. This variant is never registered live. |
| A new study seed root | Owner | It keeps study cases apart from the live root and its hidden batches |
| The decision rules, frozen before the first run | Owner | It stops the result being tuned after the fact |

**Non-claims.** The results are development evidence for one Challenge on one
GPU type. They do not qualify hardware or set production values. They do not
change the live exam, rewards or any miner's score.

## Environment and test data

Every rebuild runs through the validator's own isolated worker, on the sheet's
GPU and pinned image. Every model is scored on study-only cases that share
nothing with the live hidden batches.

- **Rebuilds.** The Challenge's validator worker, which has:
  - no network;
  - a read-only root;
  - bounded memory;
  - the pinned image and deterministic XLA settings;
  - the sheet's study-only time limit.

  Every run records the GPU model, driver and CUDA version.
- **Scoring.** The Challenge's unchanged exam code: gates, case error and
  key-region score.
- **Records.** Every run goes through the validator's work ledger, so a
  restart never repeats or loses a run.
- **Three data sets:**
  - the Challenge's fixed TRAIN set, the same for every recipe;
  - a study evaluation set, for Phases A, B, C and F;
  - a confirmation set, sealed on creation and used once, in Phase D, after
    the limit is frozen.

**Rules for the data:**
- **Seeds.** The study seed root is separate from the live root. Each study
  set's fingerprint goes in a study journal before first use. Seeds come
  from the study root and are never chosen by hand.
- **Overlap.** Before use, both study sets are checked against every
  published case and, on the validator host, against the live pool. **Any
  overlap stops the study.**
- **References** come from the Challenge's own truth service. A failed
  reference is withdrawn for every model, as in the exam.
- **Coverage.** Every result reports how many key-region cases it covered,
  against the minimum the exam's comparison rule needs.

## Experimental design

Six phases run in order. Each Challenge's sheet sets the values and the number
of rebuilds. Two gates keep the evidence honest:
- **after Phase A, the determinism gate.** A failed determinism check ends
  the study before any sweep.
- **before Phase D, a frozen limit.** The confirmation set stays sealed until
  the owner freezes L.

| Phase | What varies | Answers |
|---|---|---|
| A. Setup and determinism gate | Each study recipe at defaults, twice with the same seed; the largest recipe allowed today, twice; two rebuilds sharing one GPU | Q5, measured times |
| B. One-factor sweeps | Each cost-driving setting in turn, from below its default to well above today's cap | Q1, Q2 |
| C. Equal-cost trade-offs | At 1, 4 and 16 times a default recipe's cost: longer training, a wider model, a deeper model, an ensemble | Q3, Q2 |
| D. Ranking stability | The top 4 configurations at the proposed limit L and at 4L, scored once on the sealed confirmation set | Q4 |
| E. Validator load | The costliest recipe allowed at L back to back, then 2 and 4 at once on one GPU | Q6, Q5 |
| F. Formula stress | Recipes built to be slow for their calculated cost, one per suspect setting | Q7 |

Phase B changes one setting at a time from each recipe's defaults. Phase C
holds calculated cost fixed and changes how it is spent.

## Measurements and cost formulas

Every rebuild records its identity, its cost and its score, so one set of
records answers every question.

| Group | Recorded per rebuild |
|---|---|
| Identity | Recipe digest, every setting, seed, image digest, backend, GPU model, driver and CUDA version |
| Time | Compile time, training time, total wall time |
| Resources | Peak GPU memory, steps completed |
| Training | Final training loss |
| Score | Exam score, key-region score, each gate's pass or fail, each error component, key-region case count |
| Determinism | Weight digest and prediction digest |
| Calculated cost | The value under each of F0 to F4 |

**The candidate cost formulas.** Parameters are counted from the compiled
model, not estimated from settings.

| Formula | Calculated as | Role |
|---|---|---|
| F0 | Training steps | Today's cap, the baseline |
| F1 | Parameters × cases per update × steps | The simplest compute measure; fits small networks |
| F2 | F1 with an optimizer factor, polish steps weighted separately, summed over ensemble members | Adds known extra costs, such as SAM's second pass per step |
| F3 | F2 converted to seconds on the sheet's GPU: fixed setup time plus a fitted rate per model family | The unit miners would see: reference seconds |
| F4 | XLA's FLOP estimate for one compiled training step × steps, summed over members, converted to seconds the same way | Works for any architecture; the expected choice for neural operators |

cost_F2 = Σ over members of (k_opt · P · B · S_main + k_polish · P · B · S_polish)

- P is parameters per member, B is cases per update, S is steps, and each k
  is a measured factor.
- **F3 and F4 are fitted on Phase A and B timings only.** Their accuracy is
  judged on Phases C and F, which the fits never see.
- **F4 needs no hand-written formula per architecture.** The same compile
  gives a peak-memory estimate to check against the sheet's memory ceiling at
  submission.

## Decision rules

The rules are frozen, as written, in
`docs/development/training_budget_study/DECISION_RULES.md`. Its digest is
recorded in `.agent/DECISIONS.md`, and a test checks it.

R9-R11 are frozen in
`docs/development/training_budget_study/DECISION_RULES_R9_R11.md`. Its digest
is recorded in `.agent/decisions/2026-10-06-OWNER-TRAINING-BUDGET-STUDY-02.md`,
and a test checks it.

## Runbook

Twelve steps, owned by the roles the testnet tracks already use: the owner,
the host session on the authorized pod, and a Claude session for code and
analysis.
1. **Owner:** approve the open decisions here and in the Challenge's sheet,
   and freeze the decision rules. Record the rules' digest.
2. **Claude session:** build the study harness on the exam-design campaign
   code: the study-only contract, a sweep driver, the record schema and
   formulas F0 to F3. Its tests pass on CPU with the DirectBackend before any
   pod time.
3. **Tech lead:** review the study contract and harness.
4. **Host session:**
   - create the study seed root and commit both study sets;
   - run the overlap checks, and compute the references the sheet calls for;
   - seal the confirmation set.
5. **Host session:** run Phase A and apply R1. Stop here if it fails.
6. **Claude session:** update the time and budget estimate from Phase A's
   measured times. Stop if it now exceeds the sheet's ceiling.
7. **Host session:** run Phases B, C and F, checking spend after each.
8. **Claude session:** fit F3 and F4, apply R2, R3, R5 and R6, and propose L.
9. **Owner and tech lead:** freeze L.
10. **Host session:** unseal the confirmation set and run Phases D and E.
11. **Claude session:** apply R4, R7 and R8, write the report, and draft the
    registry or compute-limit change.
12. **Owner:** record the decision in `.agent/DECISIONS.md`, and add the
    result to the Challenge's readiness record and programme state.

## Stop rules

| Condition | Action |
|---|---|
| Spend reaches 80 % of the sheet's ceiling | Pause and report before continuing |
| R1 fails | Stop. No limit is chosen. |
| A study case overlaps a published or live case | Stop and rebuild the study sets |
| Infrastructure failures exceed 10 % of a phase's rebuilds | Pause and fix before continuing |
| Any step would touch the live hidden batches, the Challenge's exam rule or chain state | Stop. It is out of scope. |

## Deliverables and acceptance

The study is done when the owner can decide the limit from one report, and
every number in it traces to a retained record.

| Deliverable | Where |
|---|---|
| Results report: the recommended limit, its unit, and the evidence for each rule | `docs/development/<CHALLENGE>_TRAINING_BUDGET_STUDY_RESULT.md` |
| Raw records and analysis | `docs/development/evidence/<challenge>-training-budget/` (`records.jsonl`, `analysis.json`) |
| Charts: score against budget per recipe, measured against predicted time, winners at L and 4L | In the report |
| The change itself: new registry ranges or the compute-cost limit, with tests | A pull request, opened only after the owner's decision |
| The decision record | `.agent/DECISIONS.md` |
| The training-limit entry | The Challenge's readiness record (`training_budget_study`) and programme state |

**Acceptance criteria:**
- [ ] The decision rules were frozen, with their digest recorded, before the
  first rebuild.
- [ ] R1 passed, or the study stopped and says so.
- [ ] Every rebuild has a complete record, including digests and calculated
  costs.
- [ ] The confirmation set was used once, after L was frozen.
- [ ] Spend stayed within the ceiling, with the ledger attached.
- [ ] The report states L, its unit, the plateau evidence, the R4 outcome,
  the formula accuracy and the load at L.
- [ ] The report repeats the non-claims under Scope.

## Risks

The two biggest risks are leaking live test cases and tuning the limit to the
study's own data. Both have hard stops.

| Risk | Effect | Mitigation |
|---|---|---|
| Study cases overlap the live hidden cases | Part of the live exam leaks | A separate seed root, overlap checks before use, a stop on any overlap |
| The limit is tuned to the evaluation set | An optimistic limit | A sealed confirmation set, used once after L is frozen |
| GPU non-determinism at large settings | Validators can't verify rebuilds | R1 stops the study before any limit is chosen |
| The formula misses a costly setting | A recipe that looks cheap ties up validators | Phase F stress recipes, per-setting factors, the time safety net |
| Seed noise hides small effects | A wrong plateau | 3 seeds per setting, 5 in Phase D, thresholds tied to the exam's margin |
| Raised study ranges leak into the live contract | Uncapped recipes go live | A study-only contract id, never registered live, enforced by a test |
| One Challenge's results are reused for another | Wrong limits elsewhere | Every Challenge runs its own study, per the standing requirement |
| Spend overrun | It eats the testnet track's budget | The sheet's ceiling, with a pause at 80 % |

## Extension: data size, screening and cadence

**Authority.** OWNER-TRAINING-BUDGET-STUDY-02 (owner, 2026-10-06). The
extension answers questions 8-10. It runs inside the same study, under the
same sheet, spend ceiling, stop rules and non-claims.

**Why.** The original study holds the TRAIN set fixed, so it finds where
compute stops helping but not whether data is the real limit. Battery, the
first instance, shows the gap: its contract trains full-batch on 400 TRAIN cases with up to 20,000
steps, so a default recipe passes over each case thousands of times. Data is
generated once and shared by every submission, while rebuild compute is paid
for every submission, so data is often the cheaper way to raise scores. The
study also measures one GPU's load (R8) but not how many GPUs the cadence
needs.

### Added phases

| Phase | What varies | Answers |
|---|---|---|
| G. Data size | The three best recipes at L, on nested study TRAIN sets of 1/4, 1/2, 1, 2, 4 and 8 times the current TRAIN size, within the generation ceiling | Q8 |
| H. Screening fidelity | The study panel at 1/64, 1/32, 1/16, 1/8 and 1/4 of L and at L | Q9 |

- **Phase G runs after Phase C and before L is frozen** (runbook step 8). If
  R9 moves the TRAIN size, Phase B is repeated for the three best recipes at
  the new size before L is proposed.
- **Study TRAIN sets** come from the Challenge's public generator and truth
  service under the study seed root. They are nested: each smaller set is a
  prefix of the next, so a difference between sizes is the size, not the
  draw. They pass the same overlap checks as the study sets, and their
  generation counts against the spend ceiling.
- **The study panel** for Phase H is every distinct configuration from Phases
  B and C plus the Challenge's legitimate admission panel, at least the
  number the sheet sets, spanning every rebuildable family. Phase H uses 3
  seeds per configuration.
- **Phase H runs after L is frozen**, with Phases D and E (runbook step 10),
  on the study evaluation set. The confirmation set stays reserved for D.

### Cadence capacity

R11 sizes one validator's GPUs from measured times:

G = (N · (t_s + t_e) + k · (t_L + t_e)) / (τ · u)

| Symbol | Meaning | Source |
|---|---|---|
| N | Submissions per tempo | Owner worst case: 256, every registered miner once per tempo; and the sheet's expected participation |
| τ | Tempo | 72 minutes |
| u | Target utilization, headroom so a queue never builds | Sheet |
| s, k | Screening budget and survivors | R10 |
| t_s, t_L | Rebuild time at s and at L, alone on one GPU | Phase E |
| t_e | Grading time per submission | Phase E |

Identical recipe digests are rebuilt once; the report states that G assumes
no duplicates.

### Added deliverables

The results report also states:
- **D**, the recommended TRAIN size, with its data-plateau curves and whether
  data binds;
- **passes per TRAIN case** at L and D (reported, not a threshold);
- **s and k**, or that no screen is safe;
- **G** at the worst case and at expected participation, against the
  sheet's GPU ceiling.

The readiness record's `training_budget_study` result carries D, L, s, k and
G. A change to the Challenge's TRAIN size, like a change to its registry
ranges, is a pull request opened only after the owner's decision.

### Added approvals

| Item | Who | Why |
|---|---|---|
| The generation ceiling for study TRAIN sets | Owner | Solver time comes out of the Challenge's track budget |
| The sheet's target utilization, GPU ceiling, expected participation and minimum panel size | Owner | They set R11's inputs and Phase H's population |

## Owner decisions on the spec's open items (2026-09-29)

- [x] **Adopted as a standing launch requirement.** It is recorded in the
  readiness records and the launch path.
- [x] **R1-R8 frozen as written.**
- [x] **Miners see each result:** the curves and the rule are published. The
  study cases are separate from the live exam, and publishing shows that
  every recipe gets the same budget. This was the spec's recommendation, and
  the owner approved it.
- [x] **The Battery sheet's decisions are approved by the owner.** The sheet
  itself is not yet in the repository, so its values are not applied until it
  is supplied.
