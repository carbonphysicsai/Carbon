# SUBMISSION-RATE-STUDY-01: Stage 0 run sheet (owner's sheet)

**Status:** DRAFT for the owner's run. Parts A and E are the Graphite Testing
Manager's. Parts B, C and D are placeholders for the Carbon Validator and Data
Collection to fill in this file (normal commits to the PR that carries it).
**Plan:** `SUBMISSION_RATE_STUDY_01.md` (sections 6, 7, 12).
**Approval:** Stage 0 operator compute (about 3,200 reference solves, about 72
CPU-hours at the 82 CPU-s prior, no provider spend) is approved for the AX42
queue by the Test Lead. The token grant for Stage 1 is separate and is not needed
here.

## Preconditions: do not start until all three hold

1. The battery pool fill has sealed.
2. The move to producer-code-r5 is done.
3. The 24-question design tranche has run.

The owner runs this sheet, held like the live producer: the study uses its own
root, journal, deployment and bank, and touches nothing the live producer, the
testnet deployment, EV5 (journal sequence 14), `graphite-confirmation-v1` or the
tuning set uses. No hidden case, seed or batch identity appears in any file below.

## A. Measures, layout, and what Stage 0 outputs (Graphite Testing Manager)

### A.1 What Stage 0 is

Arm H only (the honest control: a fixed, randomly ordered library of candidate
recipes, never conditioned on any hidden result), at the three rates m = 1, 2, 4,
on the study bank, over `W0` windows with `R0` replicates. Provisional Stage 0
sizes, to be confirmed by the Carbon Validator's deployment limits:
`W0 = 12` rotation windows, `R0 = 4` replicates per rate (see section C for the solve count this implies). These sizes are for the
noise estimate only; the Stage 1 sizes are set from its output (A.4).

### A.2 Files the run writes (operator side; committed afterwards)

All under `docs/development/evidence/submission-rate-study-01/stage0/`:

| File | Content |
|---|---|
| `records/<rate>/<replicate>.jsonl` | one line per scored submission: `{t, rate, replicate, window, probes_batch, probes_case_max, d_index, s_current, s_fresh, state, wall_s}`. No case, seed, fingerprint or prediction |
| `noise.json` | per rate and pooled: the bootstrap band of arm H's mean D at matched cumulative probe count (settings: `n_boot` 4000, `alpha` 0.05, reused from battery's `comparison`), the replicate count, and a `rate_effect` test (does D differ by rate in arm H) |
| `throughput.json` | wall time per scored submission (median, p95), counts of `UNAVAILABLE` and `WINDOW_USED`, per rate |
| `solve_cost.json` | measured CPU-s per reference solve (median, p95), solves per window |
| `manifest.json` | digests of every file above, the analysis script digest, the bank tranche roots, `git` sha of the code that ran |

`d_index` is `s_fresh`-relative: `D = S(model; current) - S(model; fresh)`, signed so
positive means better on the scored batch (battery's score is lower-is-better).
`s_fresh` is produced by the operator-side fresh-set scoring, never by an agent.

### A.3 Analysis (after the run)

`scripts/dev/rate_study/analyze.py` (to be merged before the run; digest-pinned)
reads `records/` and writes `noise.json`, `throughput.json`, `solve_cost.json`.
It prints no hidden-derived value except the aggregates above. Its self-test runs
on synthetic records.

### A.4 From Stage 0 to the freeze (plan section 12)

1. Commit `stage0/*` (the run's operator-side outputs; aggregates and per-submission
   D only).
2. Set Stage 1's `W` and `R` from `noise.json`: enough replicates that the honest
   band's width is estimable; recorded in `measures-v1.json`.
3. Set `measures-v1.json` `status: FROZEN`, fill `noise`, `sizes`.
4. Write `freeze-manifest.json` and have the Test Lead record its digest in a
   decision file (`RATE-STUDY-FREEZE-01`). Stage 1 may then be planned.

### A.5 Pass/fail for Stage 0 itself

Stage 0 is valid when: every window of every replicate produced its records;
`UNAVAILABLE` submissions are excluded and counted (never a drift observation);
the fresh sets were each scored by operator code only; and `noise.json` has at
least the replicate count A.1 states for every rate. A failed Stage 0 changes
nothing frozen (nothing is frozen yet) and is rerun.

## B. Study deployment and rule variants (Carbon Validator)

**State (2026-10-08):** O2 is answered from the code. O1, the fresh-set
scorer and the arm-H runner are **to build**, as VALIDATOR-30 (rate-study
harness, below). Commands marked *(VALIDATOR-30)* do not exist until it
merges and the AX42 runs a tag that carries it. Fill-in values in `<…>` are
recorded when that PR merges.

### B.1 Paths (operator-owned; distinct from the live producer's and the testnet's)

All under `/var/lib/carbon-producer/rate-study/` (owner-only 0700, account
`carbon-producer`):
- `producer/`: the study producer's directory (journal, outbox, its own lock).
- `battery/`: the study producer deployment's root, journal, state and work
  (`etc/rate-study-producer.json`).
- `bank/`: the study bank. Data Collection's section C fills it.
- `fresh/`: the sealed fresh sets (section C).
- `runs/m<m>-r<r>/validator/`: each run's own import-only validator
  deployment (root, journal, state, work, retained models), fresh per run.
- `runs/m<m>-r<r>/records.jsonl`: written to A.2's `records/<rate>/<replicate>.jsonl`.

### B.2 The rule variants (O1, to build in VALIDATOR-30)

Three development-only rules, each `v2-bank` unchanged plus
`per_hotkey.window_blocks` and `study: "SUBMISSION-RATE-STUDY-01"`. That
gives each its own digest, so a study package never imports into a `v2-bank`
validator and the reverse.

| Rate m | Rule name | `window_blocks` | Digest |
|---|---|---|---|
| 1 | `v2-bank-rate-1` | 360 | `<recorded at merge>` |
| 2 | `v2-bank-rate-2` | 180 | `<recorded at merge>` |
| 4 | `v2-bank-rate-4` | 90 | `<recorded at merge>` |

Each is prospective and changes no production rule or deployment
(invariant 10). Authority: OWNER-RATE-STUDY-D1-01.

### B.3 The simulated block clock (O2): yes, without a chain read

- **Submissions:** the hidden route (`graphite/hidden_score.py`, VALIDATOR-13)
  builds the authenticated submission with a **caller-supplied block**
  (`clock()`) and calls `deployment.evaluate`. That receipt block is what the
  per-hotkey window (`exam.hotkey_window`) and the windowed pool's clock
  read.
- **Windows:** the study producer ticks at a simulated block
  (`producer tick --block B`). Its packages carry `[slot × 1080, (slot + 3) × 1080)`,
  imported by `answer_key import`, never fetched.
- **No chain:** the study deployments set `require_commitment: false` and name
  **no** `commitment_reader`. Since r4 (#841), a windowed pool's clock is the
  newer of the receipts and an *observed* chain head. With no reader, nothing
  observes a head, so the simulated receipts alone drive rotation.

### B.4 Fresh-set scoring (operator-side, to build in VALIDATOR-30)

`fresh_rerun` exists but **consumes** a batch per rerun. Section 5 shares one
fresh set among models at the same simulated time, scored once per model. So
VALIDATOR-30 adds a non-consuming scorer:

```bash
P carbon.challenge_validator.rate_study fresh --config <run config> --submission <id> --set <fresh set id>    # (VALIDATOR-30)
```

- It scores the retained model once on a sealed fresh set. A repeat returns
  the stored result.
- The output goes to the run's private state only. The record line carries
  `s_fresh` and nothing hidden.

### B.5 Arm H, one rate and one replicate (to build in VALIDATOR-30)

```bash
P carbon.challenge_validator.rate_study run --config /var/lib/carbon-producer/etc/rate-study.json --arm H --rate <1|2|4> --replicate <r>    # (VALIDATOR-30)
```

Per window `w` = 1 … `W0`:
1. tick the study producer at the window's simulated block;
2. import its packages;
3. submit the next `m` × 3 library candidates at `window_blocks` spacing, as one
   development hotkey;
4. score each on the fresh set of that simulated time;
5. append one A.2 line per scored submission.

**Exit codes:**
- `0` when every window produced its records;
- `2` for a refused configuration (typed code printed);
- `1` for infrastructure, which is resumable: rerun the same command.

`UNAVAILABLE` and `WINDOW_USED` are counted, never drift (A.5).

### B.6 Limits that bear on A.1's sizes (W0 = 12, R0 = 4)

- One run draws `W0 × 98` = 1,176 window cases. 12 runs is 14,112 draws, against
  a bank's `2,000 × E` = 10,000 draws at E = 5.
- **Section C must size the study bank** (or give each rate its own bank) so
  that Stage 0's runs never short it. A short bank tops up (more solves) and
  would mix tranche ages across runs.

## C. Study bank and fresh sets (Data Collection)

**Sizing (Test Lead decision, 2026-10-08).** One **single shared sacrificial study
bank** for all rates, sized to the draws, not to the production B rule. Each run
draws 12 windows x 98 cases, and replicates draw different batches (they must, to
measure noise): 3 rates x 4 replicates x 12 x 98 = 14,112 draws. At E = 5 that needs
at least 14,112 / 5 = 2,823 cases, so the bank is **3,000 cases**. One bank for all
rates keeps the rates on the same case population, so drift is not confounded by
bank differences; exposure is counted per draw.

**Reconciliation with the earlier approval.** Stage 0 was approved at about 3,200
reference solves, about 72 CPU-hours (2,000 study cases plus 1,176 fresh cases, at
the 82 CPU-s prior). With the bank sized to the draws:

| Term | Cases | CPU-h at 91 CPU-s |
|---|---|---|
| Study bank | 3,000 | about 76 |
| Fresh sets (12 x 98, shared among models at the same simulated time) | 1,176 | about 30 |
| **Stage 0 total** | **4,176** | **about 106** |

That is about 1,000 solves and about 34 CPU-hours above the approved figure (about
3,200 / 72 CPU-h at 82 CPU-s). The 3,000-case bank alone is in line with the original
estimate; the difference is the fresh sets, which the original 3,200 counted against
the 2,000-case bank. **Ruling (Test Lead, 2026-10-08; a Test Lead scheduling ruling under the owner's
approved study, not a new owner approval):** option (a). The full design stands
(`R0` unchanged). About 4,176 reference solves, about 106 CPU-hours, are approved as
operator compute on the AX42, no provider spend. The token grant is unchanged. Queue
position is unchanged: after the pool fill, the move to producer-code-r5 and the
24-question design tranche. (The reduced-R0 options, R0 = 3 with a bank of about 750
or R0 = 2 with about 500, are not taken.)

**State (2026-10-08):** specified. The bank fill uses existing commands. The
fresh-set draw and the disjointness check are **to build**; they are marked
*(to build)* below. Values in `<…>` are recorded when the step runs. No case,
seed, input, reference or score appears in this file.

### C.1 The sacrificial study bank (3,000 cases, Test Lead sizing above)

- **Source.** Battery's pool population law (Q = P), drawn by the study
  producer deployment (B.1 `battery/`) from **its own root**. That root is
  distinct from the live producer's, so seed derivation alone keeps the study
  cases apart from every production draw. C.3 still records content
  disjointness, because seed separation does not prove it (constitution 7.2).
  `battery_bank` already refuses published campaign cases.
- **Fill**, on the AX42, under the study producer's own lock and directory:

  ```bash
  P carbon.challenge_validator.battery_bank fill --config /var/lib/carbon-producer/etc/rate-study-producer.json --workers 7
  P carbon.challenge_validator.battery_bank status --config /var/lib/carbon-producer/etc/rate-study-producer.json
  ```

  `fill` draws each tranche, commits it to the study journal **before** any
  solve, solves it in the pinned truth image and seals it. Tranche roots:
  `<recorded at seal: tranche id, case count, Merkle root>`.
- **No top-up during the study (dependency on VALIDATOR-30).** `v2-bank`
  refills the bank to its `size` before each window. Left on, every retired
  case would be replaced, and the study would solve about 2,800 more cases than
  sized. The study rule variants therefore need the bank `size` set to 3,000
  and top-up off, so that the windows draw down the sealed bank. The Validator
  records this in B.2's rule variants. If that is not possible, the bank is
  filled once and the variant sets the top-up threshold to 0.
- **Run order.** 14,112 draws against 3,000 × E = 15,000 exposures leaves
  888 spare exposures, so the last runs draw from a nearly exhausted bank.
  Run the 12 runs **interleaved by rate**:
  (m1 r1, m2 r1, m4 r1, m1 r2, …). Then no rate systematically draws the tail,
  and the order is recorded in `manifest.json`. A window that cannot draw 98
  live disjoint cases is `UNAVAILABLE`. It is counted, and it is never drift
  and never topped up (A.5).
- **For the record (the reduced-R0 options were not taken).** With one
  shared bank the draws scale with all three rates, so R0 = 3 would have
  needed about 2,117 cases and R0 = 2 about 1,412, not about 750 / 500.

### C.2 Fresh sets (12 × 98 = 1,176 cases)

- One fresh set per window index `w` = 1…12. It is shared by every model
  scored at window `w` in every run, and each model scores it once (B.4). The
  sets are drawn, journal-committed, solved and sealed **before run 1**, so no
  fresh case is drawn after any study result exists.
- **They cannot come from `producer draw`.** Under `v2-bank`, battery's draw
  takes a window *from the bank*, so a fresh set drawn that way would be bank
  cases. The fresh sets are therefore a **separate bank** (`fresh`) in the
  study ledger, as 12 tranches of 98 under roles `fresh-w01` … `fresh-w12`.
  That bank is never drawable by a window and is read only by B.4's scorer.
  *(To build, VALIDATOR-30: a `fresh` draw/solve/seal command over
  `BankLedger.draw_tranche`, plus B.4's non-consuming scorer reading it.)*
  Roots: `<recorded at seal, per w>`.

### C.3 Disjointness record (operator-side; the H2 overlap check is NOT_BUILT)

- **By construction.** The study root is distinct from the live producer's
  root and from every campaign root. The study bank and the `fresh` bank are
  distinct tranches of one ledger, so a case belongs to exactly one tranche.
- **By content** *(to build; Data Collection can write it, and the operator
  runs it)*. Each study and fresh case gets a canonical case-input digest,
  computed from the case's physical inputs and ignoring ids and seeds. That
  digest set is checked for exact matches against the live, retired and
  published pool cases and against TRAIN, PRACTICE, EV5 (journal sequence 14),
  `graphite-confirmation-v1` and the tuning set. The check runs under the
  producer account. It writes only per-set **counts** of matches (expected 0),
  the digest of the study digest set and the digest of the script; no case or
  digest list leaves the host. A near-duplicate tolerance would be a
  scientific choice and stays `HUMAN_INPUT`. Until it is set, only exact
  matches are checked, and the record says so. Record:
  `<recorded: per set, matches = 0, script digest, date>`.

### C.4 Host window, queue and measured cost

- **Queue.** The fill and the fresh sets are the next AX42 job after the three
  preconditions hold. They run before any Stage 0 run and never overlap a live
  producer tranche solve; check `producer status` first. Estimated time:
  4,176 solves × 91 CPU-s, about 106 CPU-h, or about 15 h wall at 7 workers.
  That is the figure approved by the Test Lead's option (a) ruling above.
- **Measured cost (feeds `solve_cost.json`).** CPU-s per solve, median and
  p95, read from the bank's solve records for both banks, plus solves per
  window. FAILED_INFRA retries are counted separately. Record:
  `<recorded after fill: solves, median, p95, failed-infra retries>`.

### C.5 After the study: retire or publish (OWNER-RATE-STUDY-D1-01)

- The study bank never serves a real window. Its release queue lives in the
  study ledger only and never enters the live producer's.
- Recommendation for the owner: **publish** the study bank and the fresh sets
  as one study dataset **after Stage 1's last arm finishes**. Until then the
  fresh sets must stay unseen. The S-revealed arm will already have exposed
  scores on study cases, so publishing reveals nothing new about production.
  Once published, the set joins the published exclusion list that future draws
  are checked against.
- The alternative is to retire the banks to the operator's archive unpublished.
  Either way it is the owner's step, and it is never automatic.

## D. Candidate library for arm H (Test Engineer or Data Collection to fill)

- The frozen, ordered library of candidate recipes (EV4's 100 recipes and Graphite's
  run-5 constructions): the file, its digest, and the random order's seed (study-only,
  not a hidden seed).

## F. Stage 1 entry point (for later; not part of Stage 0)

The G-sealed arms start through the existing Graphite phase-3/4 runner with
`--study SUBMISSION-RATE-STUDY-01`. The runner's grant check for that flag is
`grant_binding.STUDY_GRANTS` / `check_study_grant`: it must enforce the 30.00 USD
ceiling, the per-run cap, 6 runs, 39,600 s per run, and a submission cap of at
most 144 read from the frozen `freeze-manifest.json`. **Status: pending (Test
Engineer); not on main** at the time of writing (verified). Until it is on
main the grant (OWNER-RATE-STUDY-TOKENS-01) binds nothing, and no G-sealed run may
start.

## E. Checklist the owner runs

1. Confirm the three preconditions hold.
2. Confirm B, C and D are filled and their digests recorded.
3. Run arm H for each rate and replicate with the section B command; check each exits 0.
4. Run `analyze.py`; confirm A.5.
5. Commit `stage0/*` through PR Head; tell the Test Lead.
6. Do nothing for Stage 1: the freeze (A.4) and the owner's grant come first.
