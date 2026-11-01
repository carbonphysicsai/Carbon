# Exam Qualification System: how Carbon makes any Challenge's exam good, and better every version

Owner, 1 Nov 2026:
- "just design an optimal system for this work"
- "needs to generalize to any challenge. We need to get really good at making these exams really good and learn from data to improve them."

Also: "we want a learning model not a formula"; "optimal evaluation > value > product"; "Don't waste tokens time or compute on anything we can check first."

**Status:** ADOPTED by the owner (OWNER-EXAM-QUALIFICATION-SYSTEM-ADOPT-01) at rev 2 (sha acaf4530…). Rev 2.1 adds case mining to S4 at the owner's direction; it needs the Validator's re-receipt. **Rev 2.2 (1 Nov, Exam Quality):** adds the REQUIRED S4a separation read (OWNER-SEPARATION-READ-ADOPT-01, lead-records 6c24fbb5) and the S5 TRAIN-kernel report row. Rev 2.1 sha 42ad91c9b4e308900e6f39ba5e54c6c4bc2aedae0a079afc06e55ccf115d2dfe; rev 2.2 sha 12a36ebc851d5516fc7c0098e0e12d64ead9279b7c07c5e695ac766ca250665c. **Rev 2.3 (1 Nov, Exam Quality):** adds the design-value rule (§3b, OWNER-DESIGN-VALUE-ENGINEER-BASELINE-01, lead-records 5328e97cb74d390df087c7c86666e6011980932c; owner: "Yes. I accept that change. Make sure we do not lose it."). Rev 2.3 sha 86892454b853b44ff3b48d5d3501fd67cba8afcbdd7b29d7dfc47f888c6b30b1 (Validator-receipted). **Rev 2.4 (1 Nov, Exam Quality):** adds the accuracy rule (§3c, OWNER-ACCURACY-OOD-MIN-01, lead-records 497b5817c5e2c24e45239b066aaf7b7732a9f1e3). Rev 2.4 sha d06cc15313d015dcdcd6184a9a5982c35ce6cff3314c137236b7835ce05fdbf0 (Validator-receipted). **Rev 2.5 (1 Nov, Exam Quality):** the owner's amendment to §3c (OWNER-ACCURACY-OOD-MIN-01 amendment, lead-records c1f57f0ac0e8792c35131ad5c9eb80c69dffedb4): `min` applies only after S4a shows a clear out-of-range win of a trained operator over the TRAIN-kernel. Rev 2.5 sha 3507a5dc63685197a878b7f48f3bca8c9beb4b3d91650208fba752e0e7538a2d (Validator-receipted). **Rev 2.6 (1 Nov, Exam Quality):** the fit-check with the earlier rows (Validator-confirmed): the stale S4 out-of-range-weight text is replaced (Q3 informs content, not a weight); N is split into accuracy-case N and D-target N; K-vs-O disagreement rows are added; one combined S2 run per version. Rev 2.6 sha e51d2f4c6dbcfa4e3565c0ea50fa2f52af001be927c391b8ff2d098a2e0b541a (Validator-receipted). **Rev 2.7 (1 Nov, Exam Quality):** cites the Validator's "clearly" definition in §3c so the document stands alone (no rule change). Rev 2.7 sha 468429e46b58a9837fceebeb502de65d7dadfdf59c31404b21d1f48f6dea8296 (sent for receipt). **Rev 2.8 (1 Nov, Exam Quality; owner: "lock all these new updates into something solid and make sure they're incorporated into the new exams"):** adds the rules register and the HARD conformance step (§3d). Rev 2.8 supersedes 2.7 for receipt and needs the Validator's receipt.
- Every pass value it names is an existing owner-signed value or an explicit owner pick. Values marked PROPOSED are review flags only until the owner adopts them.
- The Validator rules each step and receipts each artifact.
- Nothing graded is ever rescored; every change ships as a new exam version.

---

## 1. What "a good exam" means (the objective)
**An exam is good when the model that wins it is the model a client would most want for that task and its nearby variants.**

Every check below tests one of six properties:

| Property | Question | Measured by |
|---|---|---|
| **Needs learning** | Can a formula or the client's cheap method get near the crown? Can a tuned learned model? | DOWN gate (S1) and UP gate (S5) |
| **Separates** | Does it rank good models clearly above weak ones, beyond noise? | crown − baseline gap vs margin_N; rank stability across rebuild seeds |
| **Covers** | Does it test every region a client will use, including just outside the training range, every extended side, and the regime-change zones? | coverage map: ≥ N hidden targets per region class; fill distance |
| **Measures honestly** | Can the reference tell pass from fail where it matters? | U per output per region (pinned record); near-limit counts; MMS / controls |
| **Resists gaming** | Does any bias, shortcut or leak pay? | paired gaming rule; leak attack; plateau/tie flag |
| **Fair** | Can a model as good as the baseline clear the minimums, measured the way miners are graded? | baseline graded through the miners' path (`measure_pool`) |

**Cost rule:** a solver run is justified only when it fixes a measured gap in one of these six properties. Everything that can be decided from existing data is decided first, at $0.

---

## 2. The Challenge profile (the only Challenge-specific input)
The system is the same for every Challenge. A new Challenge supplies one profile per version, digest-bound and Validator-receipted:

| Field | Example |
|---|---|
| Inputs, the signed TRAIN box, the signed extended region (held sides marked) | F02 3.0: 9 inputs, box ≤ 420 K |
| Interface + output ENCODING (what miners predict, and in what form) | Cooling: law-safe encoding |
| Outputs, limits, objectives, and the list of signed thresholds | Motor: torque ≥ 4.0, ripple ≤ 0.30 |
| Property/material tables with source + signature, and the APPLICABILITY window (property range, runaway behaviour) | F02 3.0: handbook k(T), c_p(T); leakage runaway bounds the box |
| Reference solver, solver image digests, mesh/rung ladder, U method, the pinned U record ids, per-case cost and peak memory | F08: CalculiX, h 3/2.25/1.7, ~9–11 GiB |
| Checked host classes, including the GPU driver | Lium overlay2 (F02 passed); driver pinned per class |
| Rebuild limits + recipe allowlist | v8; rebuild_wall_seconds per version |
| Baseline definition + where its minimums are measured | learned KRR, graded via `measure_pool` |
| Registered scoring constants (A scales, a_multiplier, the s_h rule, pick rule, d_aggregate) | top-3, balanced regions, s_h = 0.25 × baseline median e |
| Physics that could make it formula-shaped (linear? separable? few inputs?) | F02 2.5: linear, 2 inputs |
| Known regime-change features (mode crossings, saturation, applicability limits) | F08: a mode crossing the 600 Hz band edge |
| The strongest structured cheap model the physics allows, plus "the client's way" | F02: modal/Duhamel superposition |
| Catalog contenders by family (UP gate) | FNO, operator #2, MLP, graph, transformer |
| Nearby tasks (shifted loads, limits, bands), with sizes the owner picks | F08: a shifted band |

Everything else (stages, metrics, rules, tools) is shared.

---

## 3. The pipeline: nine stages, in check-before-spend order
Each stage has a pass rule, an owner and an output artifact. A stage that fails STOPS the version, and the Validator classifies the failure: physics, scoring, coverage, reference, catalog, fairness or disclosure.

| Stage | What | Cost | Pass rule (owner-signed values or owner picks) | Owner |
|---|---|---|---|---|
| **S0 Evidence intake** | Read everything already known: king per-target regrades, legs audit, catalog sweep, coverage map of the current version, the lessons checklist, the rules-vs-evidence audit (each limit vs its pinned U, each gate vs its evidence) | $0 | Every lessons-checklist item ticked or a reason recorded | Val + EQ |
| **S1 Physics adequacy** | Step-1 sizing: is the response nonlinear / non-separable enough? Plus the DOWN adversary on minimal data | small | Nonlinearity above the owner-signed bar; the bar-to-U ratio is REPORTED (a minimum ratio, if wanted, is an owner pick); the cheap method not within margin_N of the oracle (owner-signed) | Val; DC runs |
| **S2 Scoring dry run** | The proposed scoring rules (pick rule, region balance, honesty scale, A scale), applied as a scratch what-if to existing regrades or the S1 data | $0 | The crown − baseline gap widens or holds; paired gaming holds; the bootstrap class-mean spread with N targets < margin_N sets N. N may only be RAISED from the owner-delegated minimum (N = 3, record 3c87c2cd), never lowered | TE writes, TL runs, Val |
| **S3 Reference qualification** | Edge check (it produces the SIGNED extended region), U panel per output per region (3 rungs, pinned record), MMS / controls | small | Controls pass; the near-limit count at ±U and ±3U is REPORTED per limit; decisions within ±U are flagged; any rule beyond reporting is an owner pick; a region with no U gets no targets | DC / LP run; Val |
| **S4 Case mining → pool-mix design → FREEZE** | Mine candidate cases from seven sources first (audit gaps, coverage maps, king-audit gaps, disagreement, near-gate, regime/nearby tasks, design-skill targets; CASE_MINING_PLAN). N per class is a FLOOR, not a cap. Region classes from the signed region: in-train, inner band, outer shell, each empty extended side, regime zones (profile + disagreement), nearby tasks; N per class from S2; how in-range and out-of-range accuracy combine per §3c (`min` only after a clear S4a win and a passing ACC-NOISE run, else `mean`; no weighted rule), and the rank-correlation (Q3) read informs which out-of-range cases to add (C3), not a weight; N per class is split: accuracy-case N and D-target N, each with the N = 3 floor, raise-only, and the ≤ 1/3 mined cap applied to each separately; disagreement rows may include TRAIN-kernel-vs-operator disagreement (K + ≥ 2 O families, the receipted X rule of 3U or a limit-side flip, selected by disagreement only, accuracy rows only, custody only, the ≤ 24 cap SHARED with miner-king disagreement); disagreement-chosen cases ≤ 1/3, accuracy-only; distance rules vs practice and published cases <br>**S4a Separation read (REQUIRED, OWNER-SEPARATION-READ-ADOPT-01, lead-records 6c24fbb5; card SEP-READ-01):** before the big solves, score a TRAIN-kernel fit (tuned prior_krr, TRAIN only) against the best tuned catalog operator, per region class, on cases already solved outside TRAIN (ext-U panels, practice/coverage probes, the STAGE2 gate probe). Report the nearest-TRAIN distances. Two-phase harness: no probe inputs on pods. Mining ranks first the CLASSES where the fit loses by > margin_N, the operator beats it, and n ≥ 6. Cases within a class come only from the registered sampler, never chosen by which ones the operator wins. Caps unchanged (mined ≤ 1/3; N floor). The read never delays the calendar freeze: if it is late, the freeze proceeds and that is recorded | $0 (the S4a training sits inside the S5 cap) | HARD: the version's conformance column (§3d) is Validator-receipted first. The Validator receipts the frozen mix digest, which cites the region digest, the U digests, the S4a read digest (or "S4a late, recorded") and the receipted conformance column. **No large solve before this freeze** | Val; DC drafts; S4a: LP/TL train, TL custody score, Val ranks |
| **S5 Learning necessity** | The UP gate: tuned catalog contenders (TRAIN only, within the version's own rebuild limits, a fixed digested grid) vs the best DOWN model | ≤ $5 | Best tuned learner beats the best cheap method by > margin_N (owner pick A). Hard or report-only per the owner's pick for that version; a date conflict goes to the owner. REQUIRED report row: the "TRAIN-kernel interpolation reference" (Validator Q11 ruling). If the best UP model is a TRAIN-kernel that no other learner beats by > margin_N on a hard-gate version, the Validator raises ONE owner question at GO/NO-GO; nothing waits on it | Graphite tool; LP; TL |
| **S6 Solve at scale** | Only the frozen mix. Opaque shards, wide parallel rented pods (sealed: single-tenant, inputs only), unique container names per parallel run; heaviest case alone first; 6-case probe per family | the big spend, capped | Probe ≥ 5/6 OK; ≥ 2 feasible per target (one top-up, else drop and report) | LP / TL / DC |
| **S7 Post-solve QA + disclosure** | Coverage map of the FINAL pool (≥ N per class); U-per-region; minimums via the miners' path; the catalog sweep for the Option-B floor; proof grid; paired gaming; 10-seed margin recal on a rebuild host class with matching GPU driver (class pinned per driver); leak scan. **Disclosure:** practice-bank draw + difficulty check + full exclusion rerun before publishing; the per-part feedback leak attack before that feedback serves; the public-safe miner note | GPU day (custody) | All pass, or STOP | Val + TL; DC (practice) |
| **S8 Register → land → owner sheet → cutover → watch** | Overlay entry (digest-bound, add-only); graders land by push + zero-downtime re-prepare; image moves only for worker-image inputs. One owner sheet (scales, baseline, margins, intended use). Zero-downtime cutover. The live watch (§4) feeds S0 of the next version | — | Owner picks; push on the owner's go | PR Head; TL; Lead → owner |

### 3b. Design value against the engineer's shortcut (REQUIRED for every new version; OWNER-DESIGN-VALUE-ENGINEER-BASELINE-01, lead-records 5328e97cb74d390df087c7c86666e6011980932c; adopted text: DESIGN_VALUE_OWNER_CHOICE_DRAFT_20261101.md sha256 8eb0aa23df557035c51b58ddb565f0f0022d68ba96ef0be9efdc7f1619677c34, incl. the Validator review)
- **L2, the D zero point:** per target, s_low = the objective of the version's REGISTERED cheap method run as screen-then-verify at budget B. It replaces the pool median. The cheap method is the one the owner-signed DOWN gate already uses, registered by digest in the version record before the freeze. No new method is ever defined for this.
- **L3, design targets where grid-fitting fails:** off-step and shell-edge design-target classes, drawn by the registered sampler at class level, inside the adopted caps (N floor; mined ≤ 1/3). Kept only where S4a shows the TRAIN-kernel loses by > margin_N AND the operator beats it.
- **The weight of D vs A is unchanged.**
- **Stages:**
  - **S2** runs the dry-run curve of D (kings, baseline, TRAIN-kernel, shortcut) under the median anchor vs the shortcut anchor at each candidate B. **B = HUMAN_INPUT**: the owner picks it from that curve, per version. If every B gives D ≈ 0 for both the baseline and the crown, report it and do not adopt L2 for that version.
  - **S3:** the runner retains the shortcut's per-design objective for every pool design (a registration item).
  - **S4:** degenerate targets (shortcut = optimum) are dropped or redrawn ONLY by the sampler, keeping ≥ N per class.
  - **S7:** the "how you are tested" record discloses the new D zero point, and the disclosure check covers it.
  - **S8:** B goes on the owner sheet.
- **Never delays a version:** if the L2 grader change isn't ready by a version's freeze, that version ships L3 only and L2 starts at the next version. Nothing graded is rescored.

| Version | Registered shortcut (Validator ruling) | B | L3 classes |
|---|---|---|---|
| Ribbed Bracket 2.0 (first) | coarse h = 3 mm rung of the same deck | HUMAN_INPUT (curve; draft candidates 4 / 8 / 16 from F08-DEVELOPMENT-PROPOSED-V1, basis ASSUMPTION) | shell-edge (length, relief length, rib thickness) + off-step IF the 2.0 domain/region is signed "geometry continuous" (decided with the region signature; if "lattice only", shell-edge only) |
| Burst Thermal 3.0 | the modal-sum cheap method (= the DOWN adversary) | HUMAN_INPUT (curve) | per its S4a read |
| Motor 1.7 | its registered cheap adversary model (its ladder has no rung below L0) | HUMAN_INPUT (curve) | per its S4a read |
| Cooling 1.8 | the coarsest r of the graded-hotspot ladder if per-design objectives exist there, else COOL-ADV-01's structured model | HUMAN_INPUT (curve) | per its S4a read |

### 3c. Accuracy: the worse of in-range and out-of-range, per region class (REQUIRED for every new version; OWNER-ACCURACY-OOD-MIN-01, lead-records 497b5817c5e2c24e45239b066aaf7b7732a9f1e3; adopted text: ACCURACY_OOD_OWNER_CHOICE_DRAFT_20261101.md sha256 0f0fcb88691127dca96f186d832459ba533ba20cc4e1f2129da19448a8d1d1aa, incl. the Validator review)
Owner: "Adopt the accuracy-side change for new versions: accuracy = the worse of in-range and out-of-range (scored per region class), more cases where the fit loses, per-class floors reported for now; fall back to the milder version if the dry run shows it's too noisy."
- **C2, balanced per-class A_gen:** A_gen = the mean over the out-of-range region classes of the class-mean accuracy (inner band, side_*, outer shell, off-step, `regime:*`, neighbour task). A class with n < N joins a pooled "other OOD" class.
- **C1:** A = min(A_in, A_gen), via the existing `combine_a {"kind": "min"}`.
- **C3:** more accuracy cases in the classes where S4a shows the TRAIN-kernel loses by > margin_N and the operator beats it. Class-level, registered sampler only, adopted caps unchanged.
- **C4:** each OOD class's accuracy is REPORTED against the TRAIN-kernel reference. A hard per-class floor is a later owner pick, from data.
- **C5:** already in force. Physics gates run on every pool answer, A_gen included (OWNER-GATES-ON-POOL-3A-01).
- **Stages:**
  - **One combined S2 scratch run per version** (ACC-NOISE-01 + DV-CURVE-01 on the FULL new rule set: A scale, `min`, the new classes, the shortcut anchor, top-3, s_h). It reports each decision's statistic SEPARATELY (the ACC-NOISE spread, D per B, the S4a "clearly" bound), plus a Q10 too-hard check (the crown and a tuned learner clear the minimums; D not ≈ 0). The ACC-NOISE part:
  - **S2 noise dry run** (card ACC-NOISE-01, $0, per version): `min` is used only if the bootstrap spread of the balanced A_gen < margin_N. Otherwise raise N per class, or fall back to C3 + C2 with `mean` (the milder version) and report it.
  - **S7:** margin_N is recalibrated under the adopted rule. S5 must show a tuned learner clears the moved baseline minimum. The "how you are tested" record discloses the A rule.
- **AMENDMENT (owner, lead-records c1f57f0ac0e8792c35131ad5c9eb80c69dffedb4):** "Amend the accuracy-side change: the min rule applies to a version only if its separation read shows a trained learned model clearly beats the fit out of range; if nothing beats the fit there, fix the training coverage or physics levers first."
  - **C1 gate:** A = min(A_in, A_gen) applies to a version ONLY if its S4a read shows a trained catalog operator CLEARLY beats the TRAIN-kernel on the out-of-range classes. "Clearly" (Validator definition, OVERNIGHT_20261101.md, no new constant) means all of: O is a trained catalog operator and K the tuned TRAIN-kernel, both from the same harness and rules; the statistic is the paired O − K in the registered A_gen atom, balanced over the OOD classes with n ≥ 6 (at least one such class, else no clear win); and its paired bootstrap 95 % LOWER bound (within-class resampling, 2000 draws, seed recorded) > margin_N. S4a is therefore the deciding step for C1, and each version's S4a is scheduled as early as its probe cases exist.
  - **No clear win:** that version keeps `mean` (C2 + C3 still apply), and a card opens for the NEXT version (TRAIN-COVER-<version>): improve TRAIN coverage near the edges (the fill read shows the outer shell is also the worst-covered region of TRAIN) and/or the physics levers given to miners. That card is a new version, never a change to a graded one.
- **Never delays a version:** if the C2 grader code isn't ready by a freeze, that version ships C3 + C1 on the pooled slice (or C3 + mean, if the dry run fails) and C2 starts at the next version. Nothing graded is rescored.

### 3d. Rules register and the HARD conformance step (REQUIRED for every new version)
- **The register:** `EXAM_DESIGN_RULES_REGISTER.md` is the one numbered list of every ADOPTED exam-design rule. Each rule gives its owner record id + commit, the stage it binds, and the check that proves it. A new owner record adds its row in the same step, under the Validator's receipt.
- **The conformance table:** `EXAM_RULES_CONFORMANCE.md` gives, per version, every rule as applied / N/A-with-reason / pending.
- **HARD STEP before the S4 mix FREEZE:** the version's conformance column must be Validator-receipted.
  - Every rule binding S0–S4a is applied or N/A-with-reason.
  - Rules binding S5–S8 name an owner and a date.
- **HARD STEP before the S6 big solves:** the column is re-receipted with the S5 row applied or N/A.
- **A pending freeze-binding rule blocks the freeze.** Under the owner's never-delay rule, the version may instead ship that rule's registered fallback, recorded as N/A-with-reason and receipted. A rule is never skipped silently.
- The frozen-mix digest cites the receipted conformance column.

**Why this order:**
- Everything that decides WHAT to solve (S0–S2, S4) costs $0.
- The small reference work (S3) comes before the freeze, because coverage classes need the signed region and every region needs its U.
- S5 catches a formula-shaped exam cheaply.
- S6 spends only on the frozen, justified mix.

---

## 4. The learning loop: getting better at exams from data
Each version is also an experiment about exam design.

1. **Exam Quality Record per version** (one file, aggregates only, written at S7 and updated in week 1 live):
   - the six properties' measured values: separation gap, rank stability, coverage per class, worst limit/U ratio and near-limit counts, gaming result, baseline-vs-minimum;
   - the UP/DOWN scores;
   - the cost and time per stage;
   - the count of "fails its own test" findings (it should trend down version over version).
2. **Live signals** (automated after week 1, read-only, aggregates):
   - out-of-range vs in-range rank correlation and crown flips;
   - saturation (PROPOSED trigger values for the owner to adopt: A ≥ 0.98 or D ≥ 0.9; review flags only until then);
   - plateau/tie (≥ 2 entries sharing a floored top total for ≥ 2 epochs);
   - practice-vs-official rank correlation;
   - near-gate margins;
   - king-audit mismatches (passes the exam, fails the client test);
   - time-to-first-king and the number of distinct winning approaches.
3. **What a signal triggers:**
   - saturation or a plateau → S1 for the next version (harder physics or more inputs);
   - out-of-range rank duplicating in-range → resample toward regime zones (S4);
   - a king-audit mismatch → a new region class or a scoring change (S2/S4);
   - a near-limit flag → a reference fix (S3);
   - practice not predicting → practice refresh (S7 disclosure);
   - a rules-vs-evidence finding (a gate the evidence can't support) → S0 of the next version;
   - a probe or cheap-method STOP → S1.
4. **Design lessons → defaults.** Every finding becomes a row in `MAINNET_EXAM_DESIGN_LESSONS.md` (Challenge, finding, evidence, rule). Rules the owner adopts become DEFAULTS in the profile template and the stage pass rules, so the next Challenge starts from everything learned. Learned so far (proposed until adopted):
   - linear in ≤ 3 inputs = too easy;
   - U must match its region;
   - minimums are measured the miners' way;
   - regime-change zones are the highest-value hidden cases;
   - cite PINNED records only (not working copies);
   - thermal runaway / applicability windows bound the box;
   - GPU host classes are per driver;
   - container names must be unique in parallel runs.
5. **Cross-Challenge calibration** (weekly): compare the six properties across all live Challenges. One Challenge far worse on a property means a targeted fix there. All Challenges worse means a system rule changes, and the owner adopts it.

**How we know we're getting better:** per new version, track:
- the stage pass rate on the first try;
- the solver dollars per qualified target;
- the days from design to cutover;
- the count of "fails its own test" findings;
- the six-property scores vs the previous version.

The weekly review reports the trend.

---

## 5. Shared tools (the "qualification kit": build once, reuse on every Challenge)
| Tool | Stage | Exists? |
|---|---|---|
| Coverage map + coverage-plan draw (region classes, distance rules, side gate) | S0, S4, S7 | yes (COVERAGE_MAP_REV2, coverage_plan rev 3); make it Challenge-generic from the profile |
| Rules-vs-evidence audit (each limit vs pinned U; near-limit counts) | S0, S3 | done by hand 1 Nov; script it (reads U_RECORDS + limits) |
| Adversary gate (structured cheap model + "10 runs + fit") | S1 | per Challenge today; template it |
| Scoring dry run (new rules on existing regrades; bootstrap N) | S2 | being written (SCORE-DRYRUN-01) |
| U panel / edge payloads | S3 | per Challenge (Motor / Cooling ext-U); template |
| Learning-necessity harness | S5 | built (claude/ln-harness) |
| Wide-parallel dispatch (job cards, rent recipes, caps, ledger) | S6 | yes (COMPUTE_DISPATCH, JOB_QUEUE) |
| Proof grid, recal, minimums-via-miner-path, catalog sweep, leak scan, practice draw + exclusion rerun, per-part leak attack | S7 | yes |
| Overlay registration + zero-downtime re-prepare | S8 | yes |
| Exam Quality Record writer + live-signal jobs | §4 | to build after week 1 (scheduled, read-only) |

---

## 6. Roles
- **Exam Quality:** owns this system, the board, the per-version Quality Records, the learning loop and the weekly trend; finds and assigns gaps.
- **Validator:** rules every stage and receipts every artifact; final word on the method. Owner-reserved values stay the owner's.
- **DC:** profiles, payloads, draws, practice. **TE / Graphite:** tools and version code. **TL / Launchpad:** runs (custody vs rented). **Runner:** gates. **PR Head:** landing. **Lead:** the owner interface and one-choice picks.

---

## 7. Where each live Challenge stands (1 Nov)
| Version | Stage | Waiting on |
|---|---|---|
| Burst Thermal 3.0 | S1 (box cut → re-run step 1 with leakage feedback) | owner box signature; the S2 dry run and Q3 read before the S4 freeze |
| Ribbed Bracket 2.0 | S1/S3 prep (deck + controls; U/edge payload receipted) | TE harness → smoke; S2 before S4 |
| Motor 1.6 / 1.7 | 1.6: S3 (shell U) + code restructure; 1.7: S4 draft (coverage + disagreement) | ext-U run; S2 result (N) |
| Cooling 1.7 / 1.8 | 1.7: S7/S8 (image move); 1.8: S3 (shell U payload) → S4 (plan receipted, outer shell after the ext-U result) | ext-U receipt and run; S5 report on 1.7 |

The detailed tracker is `EXAM_QUALITY_BOARD.md`; the job cards are in `JOB_QUEUE.md`.
