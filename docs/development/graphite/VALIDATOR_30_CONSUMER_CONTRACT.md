# VALIDATOR-30: the rate study's consumer contract

**Status:** DRAFT for the Carbon Validator to build to. **Author:** Graphite Testing
Manager. **Consumer:** SUBMISSION-RATE-STUDY-01 (`SUBMISSION_RATE_STUDY_01.md`, run
sheet and arm sheets). Starting point: run sheet section B, which the Validator wrote;
nothing here contradicts it. This file is what the study calls, so the Validator builds
the harness to it rather than guessing. It changes no `carbon/challenge_validator` code;
the acceptance tests (`tests/cpu/test_rate_study_consumer_contract.py`) are `xfail`
until VALIDATOR-30 lands.

## 1. Module and commands

```
python -m carbon.challenge_validator.rate_study <command> ...
```

| Command | Purpose | Consumer |
|---|---|---|
| `check --config PATH [--arm ARM]` | read-only preflight; exit 0 or a typed refusal | owner, before any run |
| `run --config PATH --arm {H,S-sealed,S-revealed} --rate {1,2,4} --replicate R` | one run: arm, rate, replicate | owner (Stage 0: arm H only) |
| `fresh --config PATH --submission ID --set ID` | non-consuming operator-side fresh-set scoring (section B.4) | `run`, and the owner for repair |

Arm G-sealed does not use `run`: it starts through the phase-3/4 runner with
`--study SUBMISSION-RATE-STUDY-01` (arm sheets, run sheet F). Scripted arms
S-sealed and S-revealed call a prober (Test Engineer, run sheet D.2) given as
`--prober MODULE:OBJECT`; its interface is `propose(feedback) -> strategy_json`, where
`feedback` is the allow-list for S-sealed and the batch score for S-revealed. S-revealed is
refused unless the bank is the sacrificial one (section 4).

The Python surface the tests call: `rate_study.main(argv) -> int` (the CLI) and
`rate_study.run(config, arm, rate, replicate) -> int`, `rate_study.fresh(...)`,
`rate_study.check(config, arm) -> None | RefusalCode`.

## 2. Config (`etc/rate-study.json`; schema `carbon.rate-study.config.v1`)

| Key | Content |
|---|---|
| `fixture` | `true` selects an in-memory fixture bank and a synthetic scorer (section 6); never `true` with a real root |
| `roots` | the run sheet B.1 paths: `producer`, `battery`, `bank`, `fresh`, `runs` (all under `/var/lib/carbon-producer/rate-study/`) |
| `rules` | `{"1": "v2-bank-rate-1", "2": "v2-bank-rate-2", "4": "v2-bank-rate-4"}` |
| `library` | `{path, digest}` of the arm-H library (current: `library-v2.json`); `run` refuses a mismatch |
| `order_seed` | the library's public order seed string |
| `windows` | `W0` (12 at Stage 0) |
| `clock` | `{"mode": "simulated", "start_block": N}`; no chain read (run sheet B.3) |
| `hotkey` | one development identity per run |
| `bank` | `{"name": "study", "cases": 3000, "sacrificial": true, "top_up": "off", "tranche_roots": [...]}` |
| `fresh` | `{"name": "fresh", "windows": 12, "cases_per_window": 98, "roots": {...}}` |
| `records_dir` | where `records/<arm>/<rate>/<replicate>.jsonl` is written |
| `freeze_manifest` | path to `freeze-manifest.json`; required for Stage 1 arms, absent for Stage 0 arm H |

## 3. Rules `v2-bank-rate-1/2/4`

Each is `v2-bank` unchanged plus `per_hotkey.window_blocks` of 360, 180, 90 and
`study: "SUBMISSION-RATE-STUDY-01"` (run sheet B.2). They live in `exam.RULES` (or the
rate-study module's registry the deployment reads) with their own digests, so a study
package never imports into a `v2-bank` validator or the reverse. The bank `size` is 3,000
and **top-up is off**, so windows draw down the sealed bank. The `fresh` bank is **not**
drawable by any window (it is read only by the fresh scorer).

## 4. Typed refusals (exit 2, one line `refused: <code>` on stdout)

Closed set; the tests assert exactly these:

`config_unreadable`, `config_schema_mismatch`, `rule_unknown`, `rule_not_study_variant`,
`rule_window_blocks_mismatch`, `library_digest_mismatch`, `study_bank_not_sealed`,
`study_bank_wrong_size`, `study_bank_not_sacrificial`, `topup_not_off`,
`fresh_bank_missing`, `fresh_bank_drawable_by_a_window`, `clock_not_simulated`,
`production_root_refused`, `revealed_on_non_sacrificial_bank`,
`freeze_manifest_required`, `freeze_manifest_mismatch`, `replicate_already_complete`,
`run_dir_not_fresh`, `fixture_with_real_root`.

`production_root_refused` covers any root that is the live producer's, the testnet
deployment's, EV5's, `graphite-confirmation-v1`'s or the tuning set's.

## 5. Exit codes and resumption

- `0`: every window produced its records.
- `1`: infrastructure; resumable: **rerun the same command** and it appends only the
  missing submissions (no duplicates, same `t`). Infrastructure is never a drift record.
- `2`: refused (typed code, section 4); nothing was written.

No other codes. (Run sheet B.5 states 0, 1 and 2; this keeps them.)

## 6. Output: one line per submission (`records_dir`)

Exactly the fields of `analyze.FIELDS` (`scripts/dev/rate_study/analyze.py`):
`arm, rate, replicate, window, t, probes_batch, probes_case_max, d_index, s_current,
s_fresh, state, wall_s, provenance`. Nothing else: no case, seed, fingerprint,
prediction or batch identity (the analysis refuses a record with another field).

- `t`: 1, 2, 3, ... in submission order within the run, stable across a resume.
- `state`: `SCORED`, `UNAVAILABLE`, `WINDOW_USED` or `REPEATED`. A `REPEATED` outcome
  (the route returned a stored outcome for an identical submission) is its own line and
  is **never** a scored submission; the runner counts it separately. A library of at least
  144 distinct recipes (library-v2) means a clean run has none.
- `d_index = s_fresh - s_current`, for a lower-is-better score; positive means better on
  the batch it was scored on. For non-`SCORED` lines the numeric fields are `null`.
- `probes_batch`: how many times this hotkey has now probed this window's batch;
  `probes_case_max`: the largest exposure count among the batch's cases at this
  submission. Both from the validator's own state.
- `wall_s`: validator rebuild plus score seconds for the submission.
- `provenance`: `"STUDY"` for a real run; `"FIXTURE"` when `fixture` is true.

A run also writes `records_dir/<arm>/<rate>/<replicate>.manifest.json`: `{rule,
rule_digest, library_digest, bank_tranche_roots, fresh_roots, clock_start_block,
counts: {scored, unavailable, window_used, repeated}, git_sha, config_digest}`.

## 7. The fresh-set scorer (`fresh`)

- Scores the retained model once on a sealed fresh set, writes the result to the run's
  private state, prints one JSON line `{"state": ..., "s_fresh": ...}` and nothing else.
- **Non-consuming:** a repeat for the same `(submission, set)` returns the stored result;
  a different model on the same set scores normally; the set is never marked consumed.
- Refuses a set that is drawable by a window (`fresh_bank_drawable_by_a_window`).

## 8. Fixture mode (for acceptance, never evidence)

`fixture: true` selects an in-memory bank and a synthetic scorer with a public string
seed. It refuses any non-temporary root (`fixture_with_real_root`), stamps every record
and manifest `provenance: "FIXTURE"`, and its output is refused by the analysis for the
committed evidence tree. It exists so `check`, `run` and `fresh` can be exercised end to
end by tests without a bank, a pool or a host.

## 9. Not in this contract

The prober and adversary brief (Test Engineer), the study-grant binding
(`STUDY_GRANTS`, Test Engineer), the bank fill and fresh-set draw (`battery_bank`,
Data Collection), and the freeze. Hidden-material rules, the REPEATED semantics and the
closed refusal list above are the parts the study cannot work without.
