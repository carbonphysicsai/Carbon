# F02 cold pack evidence: TRAIN40-v2 and the eight accepted cold actions (2026-10-20)

**What this set is.** The judged outputs behind F02 evaluation version 2.0
(OWNER-F02-TRAIN40-V2-01). Everything is in the fixed cold context
c30-i40-s0.5-rectangular (coolant 30 °C, h 2500 W/m²K, initial 40 °C, left-source fraction 0.5,
rectangular pulse).

- **Exam references:** `rr04-judgement.json`, RR-PACKS-04.
  - It is the frozen plan's own rejudge under F02-SCIENCE-VALUES-01 (code `67dafcf3`).
  - Verdict: **B10 `ACCEPTED_FOR_DEVELOPMENT_BANK`**. All 12 primaries pass B1–B5 at both the
    mesh2 and dt0.5 rungs, and all 12 B6/B7 baselines pass.
  - The pack's exam is the 8 cold primaries named in the scoring producer's `_F02_ACTIONS`.
  - At the 95 °C limit they are **3 safe and 5 unsafe**. The closest is 86 W / 5 s at
    95.206 °C, a margin of 0.21 °C. The largest rung shift among the 8 is 0.011 °C.
  - No action's rungs straddle the limit.
- **Solver build:** the RR-04 Elmer binary was native. It matched the RR-PACKS-05 MMS-verified
  build output for output (`rr05-mms-evidence.json`).
- **TRAIN40-v2:** `train40v2.jsonl` (`b6875185…`), RR-PACKS-08.
  - It was exported by `export_train40v2.py.txt`, which checks every deck against the freeze
    ledger written before any solve.
  - `rr08-ledger-check.json` records pin = ledger = step record with zero refused decks.
  - The build's own MMS passed (`rr08-mms-evidence.json`).
  - Strata: **S1** has 24 rows, 12 at or below 95 °C and 12 above. **S2** has 16 rows, all
    above.
  - The 4-case S1 convergence spot-check passed (`rr08-spot-summary.json`).
  - `carbon/challenge_kit/f02_train.py` re-derives `f02-dev-train40-v2.npz` from this file
    byte for byte.
- **TRAIN spread:** `train_peak_std_c` = **6.701 °C**, as decided in the owner record's
  revision.
  - It is the population std (ddof 0) of the 24 S1 peaks, recomputed from the pinned rows
    (6.7012…), which must round to 6.701.
  - The full-TRAIN figure, 16.704, was not picked.
  - v1 (TRAIN40) keeps 13.633, is history, and is not served.

**What it does not support:**
- **Not an independent population.** The 8 actions are the registered set, and TRAIN is
  deliberately placed near the limit.
- **Not scoreable on its own.** The accuracy definition and F02's Design policy and scales are
  scoring authority, so they stay HUMAN_INPUT in the pack. The Test Engineer's F02 adapter
  supplies them, under the Validator's review.
- **Not a qualification, a model result or a LIVE claim.**

**Files:**
- `rr04-judgement.json` and `rr04-judgement.provenance.json`.
- `train40v2.jsonl`, `train40v2.diagnostics.jsonl` and `train40v2.summary.json`.
- `export_train40v2.py.txt`, kept as text so the formatters never rewrite it.
- `rr08-freeze-ledger.json`, `rr08-ledger-check.json`, `rr08-mms-evidence.json`,
  `rr08-pod-environment.json`, `rr08-pod-phase.json`, `rr08-spot-summary.json` and
  `rr08-spot-deck-verification.json`.
- `rr05-mms-evidence.json`.
