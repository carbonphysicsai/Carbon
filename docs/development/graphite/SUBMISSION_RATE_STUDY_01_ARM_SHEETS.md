# SUBMISSION-RATE-STUDY-01: per-arm run sheets

Companion to `SUBMISSION_RATE_STUDY_01_RUN_SHEET.md` (Stage 0, owner-run) and the
plan. Each column lists inputs, the command, outputs and validity. Commands marked
**(VALIDATOR-30)** do not exist until that item merges. Nothing here runs before the
freeze (plan section 12); Stage 0 is arm H only. Every record is written to
`records/<arm>/<rate>/<replicate>.jsonl` in the schema `analyze.FIELDS` (no case, seed,
fingerprint or prediction).

Analysis (exists, fixture-tested): `python scripts/dev/rate_study/analyze.py stage0|report`.
Dry runs use synthetic FIXTURE records only (`scripts/dev/rate_study/fixtures.py`,
`tests/cpu/test_rate_study_analysis.py`); a FIXTURE report is refused for the evidence
tree. The study bank is specified in
`docs/development/evidence/submission-rate-study-01/bank-spec-v1.json`.

| | Arm H (honest) | S-sealed | S-revealed | G-sealed |
|---|---|---|---|---|
| Stage | 0 (and 1 as control) | 1 | 1 | 1 |
| Input | `library-v2.json` in its frozen order (at least 144 recipes) | scripted prober (Test Engineer, section D) | same prober, revealed score | adversary brief and probe tool (section D) |
| Feedback to the agent | allow-list only | allow-list only | hidden-batch score on the **sacrificial** bank only | allow-list only |
| Rate | m in 1, 2, 4: 36 / 72 / 144 submissions per run | same | same | same, 2 runs per rate |
| Command | `rate_study run --arm H ...` **(VALIDATOR-30)** | `rate_study run --arm S-sealed ...` **(VALIDATOR-30)** | `rate_study run --arm S-revealed ...` **(VALIDATOR-30)** | the phase-3/4 runner with `--study SUBMISSION-RATE-STUDY-01` **(Test Engineer binding, pending)** |
| Needs | study bank, fresh bank, rate variants, simulated clock **(VALIDATOR-30)** | same, plus the prober | same, plus the prober | same, plus the token grant bound and one controller root per run |
| Output | `records/H/...` | `records/S-sealed/...` | `records/S-revealed/...` | `records/G-sealed/...` |
| Valid when | every window produced records; `UNAVAILABLE`, `WINDOW_USED`, `REPEATED` excluded and counted | same | same, and the bank is the sacrificial one | same, and the per-run submission cap is the frozen manifest's |

**Order (bank draw-down):** interleaved by rate and replicate, as run sheet C.1
(m1 r1, m2 r1, m4 r1, m1 r2, ...). **After all arms:** `analyze.py report` writes the
safe rate, `P*` and the bank and E table; the sacrificial bank is then retired or
published (OWNER-RATE-STUDY-D1-01).

**Blocked on VALIDATOR-30:** the `rate_study run` command, the rate variants
`v2-bank-rate-1/2/4`, the `fresh` bank and non-consuming fresh-set scorer, top-up off,
the simulated clock. **Blocked on the Test Engineer:** the prober and brief (section
D.2/D.3) and the `STUDY_GRANTS` binding. **Blocked on the freeze:** all of Stage 1.
