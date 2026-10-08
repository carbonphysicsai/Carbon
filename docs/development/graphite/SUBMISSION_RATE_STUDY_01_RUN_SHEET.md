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
`W0 = 12` rotation windows, `R0 = 4` replicates per rate. These sizes are for the
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

## B. Study deployment and rule variants (Carbon Validator to fill)

- The study deployment's root, journal, work and bank paths (operator-owned;
  distinct from the live producer's and the testnet's).
- The three development-only rule variants on `v2-bank` with
  `per_hotkey.window_blocks` 360 / 180 / 90, and their names and digests.
- Whether the deployment runs on a simulated block clock for a whole run, and how.
- The operator-side fresh-set scoring command (scores a retained model on a
  producer fresh set, once, output to the private root only).
- The exact command that runs arm H for one rate, one replicate, and its exit codes.

## C. Study bank and fresh sets (Data Collection to fill)

- The sacrificial study bank: tranche draws from the producer root, committed to the
  journal before use, solved on the AX42 queue, sealed; the tranche roots.
- The fresh sets: 12 windows x 98 cases (shared among models at the same simulated
  time), disjointness record against every live, retired and published case, TRAIN,
  PRACTICE, EV5, `graphite-confirmation-v1` and the tuning set.
- The host window and queue position relative to the three preconditions, and the
  measured solves/CPU-s the run actually used (feeds `solve_cost.json`).
- After the study: the retire-or-publish step for the sacrificial bank
  (OWNER-RATE-STUDY-D1-01).

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
