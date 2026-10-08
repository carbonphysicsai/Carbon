# SUBMISSION-RATE-STUDY-01: plan (no runs, no spend, no grant)

**Status:** PLAN for Test Lead review; D1 approved by the owner (OWNER-RATE-STUDY-D1-01). **Author:** Graphite Testing Manager.
**Authority:** the owner's study request, 2026-10-08, relayed by the Test Lead.
This plan dispatches nothing. A run needs the pre-registration below to be
frozen, the owner's approval of the grant proposal in section 9, and the
development deployment in section 4. Every score here is DEVELOPMENT evidence;
nothing is qualification, LIVE, reward or a production rate.

## 1. The question

The owner asks whether faster (GPU) validators could raise the submission rate.
Validator speed is not the binding limit. Every scored submission is a probe of
the hidden batch it is scored on, so the binding limit is **adaptive
overfitting**: a hotkey that scores `k` times on one batch can fit that batch.
The study finds the largest per-hotkey submission rate at which that fitting is
indistinguishable from noise, and prices what rate beyond it would need (bank
size B and exposure E, in reference solves).

Verified on main (9d011aba3):
- **Rate today:** battery rule v2 allows one scored submission per hotkey per
  360-block tempo (`exam.DEVELOPMENT_RULE_V2["per_hotkey"]`); a screening batch
  is replaced every 1080 blocks (3 tempos), so one hotkey probes one batch 3
  times. Hidden results are sealed from miners (the miner sees the allow-list).
- **Bank rule `v2-bank`** (OWNER-BANK-ARCHITECTURE-01): 98 window cases plus 2
  hidden duplicates per window, drawn without replacement from a live bank of
  B = 20n = 2000 cases, each case retired after E = 5 draws.
- **Graphite's hidden route** (VALIDATOR-13, `graphite/hidden_score.py`): the
  same admitted recipe is submitted to a separate operator battery deployment
  through `deployment.evaluate`; the agent sees only the allow-list; one
  development identity per run, one hidden score per tempo. The receipt block
  comes from a caller-supplied clock.
- **Detector:** `challenge_validator/leak_detection.py` (#737): per submission,
  `advantage` = median score on non-current batches (fresh, retired,
  published) minus median on current batches, with seed-band and batch-spread
  bands; descriptive, gates nothing.
- **Fresh-case rerun:** `fresh_rerun` rescored a winner once on a fresh batch
  that is then consumed (`test_a_winner_is_rescored_once_on_a_fresh_batch...`).
- **Not on main:** `CAPACITY_MODEL_8_CHALLENGES.md` is referenced by
  PRODUCER-STARTUP-HOST-01 but is not committed. Section 8 therefore prices in
  reference solves with its own stated terms; the capacity model's terms are
  to be reconciled when it lands (open item O4).

## 2. Arms

All arms submit to the same development deployment (section 4) under the same
bank, rule version, tempo and clock. Rate multiplier `m` scales the per-hotkey
cap: m = 1 is one scored submission per 360 blocks, m = 2 per 180, m = 4 per 90.
Probes of one batch by one hotkey are `k = 3m` (3, 6, 12); probes of one case
before retirement are `P = E x k` (15, 30, 60 at E = 5).

| Arm | Behaviour | Feedback the agent gets | Purpose |
|---|---|---|---|
| **H** honest control | Submits a fixed, randomly ordered sequence of candidate recipes drawn from a frozen library (EV4's 100 recipes and Graphite's run-5 constructions). Never conditions on any hidden result | allow-list only (sealed) | Noise: what drift looks like with no adaptation |
| **S-sealed** scripted prober | Deterministic adaptive search (coordinate-wise hill climbing over recipe parameters) that conditions on whatever the route returns | allow-list only (sealed): the real mainnet view | Does the sealed channel leak enough to be fitted? |
| **S-revealed** scripted prober | Same search, conditioned on the batch score itself | the hidden-batch score, on a **sacrificial study bank only** (section 5) | Worst-case bound: how fast drift grows when the channel is wide open |
| **G-sealed** Graphite probing adversary | A Graphite Constructor session whose brief is to maximise the route's outcomes using only what it returns, with the scripted prober's probe tool available | allow-list only | The realistic adversary; token-cost arm, run fewer replicates |

The scripted prober exists because it is deterministic, cheap and
replicable at 4x (144 submissions per run), and it bounds what an LLM adversary
could extract. G-sealed checks that bound with the real adversary at small R.
Each of H, S-sealed, S-revealed, G-sealed runs at m in {1, 2, 4}.

## 3. What is measured

All measures are computed by the operator side from the validator's own state
and are registered before any adversary run (section 6). Nothing below reaches
an agent.

1. **Overfitting index `D`.** For each scored submission `t` of a run, with the
   retained model `M_t`: `D_t = S(M_t; current batches) - S(M_t; fresh cases)`,
   sign-adjusted so positive means better on the batch it was scored on
   (battery's score is lower-is-better, as `leak_detection` handles). The
   fresh score uses a producer-drawn **fresh set** the model could not have seen
   (section 5), the same size as a window batch, scored once per `t` through
   the validator's fresh-case path.
2. **Drift growth.** `D` against cumulative probes of the batch `k_cum` and of
   the case `P_cum`, per arm and rate: the regression slope with a bootstrap
   interval over runs, and `D` at the matched final probe count.
3. **Sealed versus revealed.** The ratio of S-revealed to S-sealed drift at the
   same `m` and probe count.
4. **Exposure and retirement.** `D` of submissions scored when their batch's
   cases are at exposure 1, 3 and E (the fresh and retired profiles, reusing
   `leak_detection`'s `fresh`, `retired` and `published` classes), and the
   advantage on cases that retire during the run.
5. **Detector behaviour.** Per submission, `leak_detection` `advantage` and both
   bands, as a curve over its registered sweep. This asks whether the existing
   detector flags the adversary before drift becomes large, and its
   false-flag rate on arm H. The detector's alpha stays HUMAN_INPUT; the study
   only reports the curve.
6. **Throughput.** Wall time per scored submission (validator rebuild plus
   score) and the rate of `UNAVAILABLE` / `WINDOW_USED`. This is the only
   place validator speed enters: it bounds how fast a real campaign could reach
   `m`, and it says what a GPU validator would buy.
7. **Selection effect check.** Arm H's best-of-sequence `D` (the maximum the
   honest library reaches at each probe count), so selection among many
   candidates is not mistaken for adaptation.

## 4. Deployment and clock

- A **separate development deployment** of battery's pool machinery, its own
  `private_root`, journal and bank, as VALIDATOR-13 already requires. It never
  touches the testnet deployment, EV5's sealed batch (journal sequence 14),
  `graphite-confirmation-v1`, or the tuning set.
- It runs the `v2-bank` rule with `per_hotkey.window_blocks` set to 360, 180 and
  90 for the three rates. Those are **development-only rule variants** (new
  rule versions, prospective; invariant 10): the Carbon Validator builds them.
  They change no production rule and no battery deployment.
- The route accepts a caller-supplied clock. The study uses a **simulated block
  clock**, so a run's rate is set by blocks, not wall time: m = 4 does not need
  4x the real hours, and total wall time is bounded by Graphite and validator
  throughput (measure 6). Whether the deployment accepts a simulated clock
  without a chain read is to be confirmed with the Carbon Validator (O2).
- Pool windows: a run lasts `W` rotation windows (1080 blocks each).

## 5. Fresh cases and the sacrificial bank

- **Fresh cases come from the producer, never from agents.** Each fresh set is a
  producer tranche drawn from the producer root, committed to its journal before
  use, solved, sealed (OWNER-BANK-ARCHITECTURE-01), and scored by the operator
  side only, once per model (a set may be shared by models of different arms at the
  same simulated time, never by one model twice, and is never visible to any agent). It is disjoint from every live, retired and
  published case, from TRAIN, PRACTICE, EV5, `graphite-confirmation-v1` and the
  tuning set (the H2 overlap check, which is still NOT_BUILT; until it exists
  the producer checks disjointness at draw time and records it).
- **Study bank.** All study cases come from a bank created for this study. Its
  cases are drawn from the same population law as battery's pool (Q = P) so the
  measures transfer, but they are **study-only**: never reused for a
  production batch, retirement into the release queue, or training. This is
  what makes the S-revealed arm safe: revealing scores of study-only cases
  reveals no production hidden material. S-revealed on any production pool is
  not permitted (OWNER-RATE-STUDY-D1-01). After the study the bank is retired or
  published; it never serves a real window.
- Sealed arms (H, S-sealed, G-sealed) show agents the mainnet allow-list only.
  No hidden score, case, seed, fingerprint, prediction or batch identity is in
  any agent-visible output. The operator record stays under the run's private
  root.

## 6. Pre-registration (freeze before any adversary run)

A measures registration file is committed **before the first adversary run**:
`docs/development/evidence/submission-rate-study-01/measures-v1.json` (draft
beside this plan). Pattern: the existing freeze manifests
(`graphite-run5-q1/freeze-manifest.json`, EV5): a content-addressed document
whose canonical digest is recorded in a Test Lead decision file, and the
analysis script's digest with it. Freezing records:

1. the measure definitions of section 3 and the exact analysis code (digest);
2. the arms, rates, windows `W`, replicates `R` per arm, and the library of
   candidate recipes and probe-tool settings;
3. the **noise definition** (section 7), computed from arm H only;
4. the decision rule for the safe rate (section 7);
5. the study bank's tranche roots (committed before use), and the sacrificial
   designation.

Order of work, so the noise estimate cannot be chosen after seeing adversary
data:
- **Stage 0, honest pilot** (arm H only, all three rates): measures the noise
  estimate, validator throughput and per-solve cost.
- **Freeze** with Stage 0's numbers. Sizes `W` and `R` are set here from
  Stage 0's noise (enough replicates that the honest interval is estimable),
  not guessed now; the proposals in section 9 are provisional and adjustable
  at the freeze.
- **Stage 1, adversary arms** (S-sealed, S-revealed, G-sealed), unchanged
  after freeze. Any deviation is a recorded amendment, never a silent edit.

## 7. The output: the safe rate, B and E

**Noise (defined, not guessed).** From arm H's replicates at each `m`, the
empirical distribution of `D` at matched cumulative probe count `P_cum`. Its
noise band is the bootstrap interval of the honest mean `D` with the repository's
existing comparison settings (battery `comparison`: `n_boot` 4000, `alpha`
0.05, reused, not chosen), pooled over rates because arm H does not adapt, so
`m` should not change it (checked as a result, not assumed).

**Within noise.** At rate `m` and probe count `P_cum`, an adversary arm is within
noise iff the upper bound of its bootstrap interval of mean `D` does not exceed
the upper bound of arm H's band. Otherwise it is **distinguishable**.

**Safe rate.** The largest tested `m` at which every adversary arm
(S-sealed and G-sealed, which are the realistic ones) stays within noise at
the final `P_cum`, plus the `P_cum` at which drift first becomes
distinguishable at the next rate. S-revealed is reported as the bound, not
used for the rate unless the sealed channel is found open (measure 3).

**What B and E would be needed.** Let `P*` be the largest per-case probe count
within noise (from the drift curves). For a target per-hotkey rate `m` with `H`
colluding hotkeys: `E <= P* / (3 m H)`. Reference-solve cost then follows from the
bank's steady state: each window consumes `n = 98` case-exposures, and each case
supplies `E`, so

- new reference solves per window = `n / E`,
- per day (a 3.6 h window at 12 s blocks gives 6.67 windows) = `6.67 x 98 / E`,
- the one-time fill = `B`, with `B >= n x E`-fold coverage so no batch shares a
  case with a simultaneously active one (the bank rule).

At E = 5, B = 2000: about 131 solves per day plus 2000 to fill. A lower E
(forced by a higher rate) raises the daily solves in proportion. The study
reports the table `m x H -> E, B, solves/day` priced with the measured
per-solve cost (median 82 CPU-s per reference solve in the B4 host solves,
`battery-quiz-designs`; re-measured in Stage 0 because VALIDATOR-13 requires
the measurement before any run). The 8-challenge capacity model's other terms
are reconciled when it lands (O4).

If no tested rate is within noise, the result is stated as such: the safe rate is
below m = 1 at the current E, and the table gives the E (and the solve cost) that
would make m = 1 safe.

## 8. Cost (no account figures; counts and hours only)

Reference solves (producer, CPU), with `W` windows per run and `n = 98`:
- Study bank fill: `B_study` cases, sized at freeze to cover the largest
  arm's draws without reuse beyond E; Stage 0 sets the number. Provisional
  `B_study` is 2000 plus the fresh sets.
- Fresh sets: one set of 98 per scored submission of the largest arm unless
  reused across arms is shown disjoint; this dominates solves at m = 4.
  Provisional bound: (total scored submissions) x 98 / (submissions sharing a fresh
  set). To keep this affordable, the plan scores the fresh set once per
  submission but **shares one fresh set among all arms' submissions at the same
  simulated time** (the model differs, the set is the same, each model sees it
  once). That makes fresh solves proportional to windows, not submissions:
  roughly `W x 98` per rate in play, a few thousand solves in total. The
  freeze records the reuse rule.
- Wall cost at 82 CPU-s per solve: 1000 solves are about 23 CPU-hours, on
  the operator host's CPUs, scheduled with Data Collection.

Agent compute: arms H and S need no LLM tokens; they cost validator rebuild and
score time per submission (measure 6). Only G-sealed uses tokens (proposals at the
probe cadence). Pods: none. A scored submission rebuilds on the carrier
backend on the operator host; no hidden material goes to rented compute.

## 9. Grant PROPOSAL (not authored; the owner approves, the grant file binds spend)

Platform: the Graphite provider route, tokens only, for arm G-sealed. Everything
else is operator-host CPU and the validator's own time, with no provider spend and
no pods.

| Field | Proposal | Basis |
|---|---|---|
| Runs | 6, one at a time (3 rates x 2 replicates) | section 2 |
| Worst case per run | 4.91 USD | the same figure as GRAPHITE-GRANT-PHASE3-R3 (Constructor, same role ladder); the adversary makes a few dozen LLM turns that drive the scripted probe tool, not one LLM call per scored submission |
| Cleanup allowance | 0.25 USD | as the existing Constructor grants |
| Ceiling | 30.00 USD | 6 x 4.91 + 0.25 = 29.71, rounded up |
| Max runtime per run | 39600 s | as the existing grants |
| Max submissions per run | set at the freeze to the arm's scored-submission cap (36, 72, 144) | the existing grants cap at 3, which does not fit this arm |

If the freeze finds the adversary needs an LLM call per scored submission, the
worst case per run changes and the proposal is re-priced before any run. Arms H
and the scripted probers need no grant (Stage 0 needs only the operator-compute
approval in section 12). The grant file is authored by the owner's process; this
plan only proposes it.

## 10. Safeguards (invariants)

- No hidden material in any agent-visible output; sealed arms see exactly the
  mainnet allow-list; S-revealed only on the study-only bank (decision D1).
- The study never writes to, reads from, or rotates the testnet deployment,
  EV5, `graphite-confirmation-v1` or the tuning set.
- Fresh cases from the producer only; agents never draw, choose or see them.
- No invented threshold: the noise is arm H's; the interval settings are the
  repository's existing ones; detector alpha stays HUMAN_INPUT.
- Infrastructure failure (`UNAVAILABLE`, validator down) is never a drift
  observation; those submissions are excluded and counted.
- A result is a measurement for a rate decision, not a rate. Setting a
  production rate, E or B is the owner's decision.

## 11. Open items and decisions

- **D1 (DECIDED, owner, 2026-10-08, OWNER-RATE-STUDY-D1-01):** the S-revealed arm is in
  scope, only on a study-only sacrificial bank that never serves a real window and
  is retired or published after the study. Its result sets the leak bound for the
  owner's later decision on live per-section scores (VALIDATOR-29 item 1).
- **O1 (Carbon Validator):** development-only rule variants with `window_blocks`
  360 / 180 / 90 on `v2-bank`; a deployment with its own study bank.
- **O2 (Carbon Validator):** whether the deployment accepts a simulated block
  clock for the whole run.
- **O3 (Data Collection):** the study bank's tranches and the fresh sets;
  per-solve cost measurement in Stage 0.
- **O4:** reconcile with `CAPACITY_MODEL_8_CHALLENGES.md` when it is committed.
- **O5 (Test Engineer):** the scripted prober and the G-sealed brief (adversary
  tooling), built as development tooling with no access to operator records.
- **O6:** the H2 overlap check is not built; until it is, disjointness is
  recorded at draw time by the producer.

## 12. The freeze: procedure, file layout, and what must exist first

The freeze happens after Stage 0 and before Stage 1 (section 6). Nothing in this
section runs without the approvals in 12.4.

### 12.1 Layout (all under `docs/development/evidence/submission-rate-study-01/`)

| Path | Content | Written |
|---|---|---|
| `measures-v1.json` | the registration; `status` becomes `FROZEN`; `sizes` and `noise` filled from Stage 0 | at the freeze |
| `stage0/noise.json` | arm H's bootstrap band per rate and pooled, with the replicate records it was computed from | Stage 0 |
| `stage0/throughput.json` | wall time per scored submission, `UNAVAILABLE` and `WINDOW_USED` counts | Stage 0 |
| `stage0/solve_cost.json` | measured CPU-s per reference solve (median, p95) | Stage 0 |
| `analysis/analyze.py` | the analysis code (a new file under `scripts/dev/`, digest-pinned; it reads operator records only) | before the freeze |
| `freeze-manifest.json` | `{schema, study, measures_digest, analysis_digest, stage0_digest, bank_tranche_roots, library_digest, arms, rates, windows, replicates, decision_ref, frozen_unix}` | at the freeze |

### 12.2 Steps

1. Build and merge the analysis script; run its self-test on synthetic records.
2. Run Stage 0 (arm H, three rates) on the study bank; write `stage0/*`.
3. Compute `noise.json`, set `W` and `R` from its interval width, fill
   `measures-v1.json` and set `status: FROZEN`.
4. Compute the canonical digests, write `freeze-manifest.json`.
5. The Test Lead records the manifest digest in a decision file
   (`RATE-STUDY-FREEZE-01`); the files merge through PR Head.
6. Stage 1 may start only when the decision file and the files are on main.
   A change afterwards is a recorded amendment, never an edit.

### 12.3 Guard

A test refuses Stage 1 when `measures-v1.json` is not `FROZEN` or its digest
differs from the manifest's (added with the analysis script).

### 12.4 Needed before the freeze can happen

- **Stage 0 operator-compute approval** (no provider spend): about 3200 reference
  solves (2000 for the study bank plus 12 windows x 98 fresh cases), about 72
  CPU-hours at the 82 CPU-s prior, in a host window agreed with Data Collection.
- **Carbon Validator:** the development rule variants and the study deployment
  (O1), and the simulated-clock answer (O2).
- **Data Collection:** the study bank tranches committed and solved (O3).
- Not needed for Stage 0: the grant in section 9, the prober or the adversary
  brief (those gate Stage 1).
