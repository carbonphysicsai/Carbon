# Part-feedback leak attack: custody payload

Proof, before a Challenge serves the v4 per-part feedback, that the extra numbers do not let a miner climb the sealed exam
(PART_FEEDBACK_GRANULARITY_20261029 §3; POOL_GRADER_AND_PROOF_SUITE_SPEC §3 item 5). Until a passed run is registered in
`part_feedback_attacks.json` the Challenge serves v3.

## What it does
Simulated miners hill-climb a model by perturbation, accepting only what the feedback they are SHOWN says improved
(the real `grade_feedback` functions: the Ladder rule for the total, the part hysteresis for each part, gates pass/fail):

| attacker | climbs on |
|---|---|
| `total` | the Ladder total alone |
| `A`, `D`, and every registered component | that one shown part alone |
| `joint` | the total, or any part rising with none falling and every gate passing |

For each attacker, `--seeds` independent runs of `--rounds` graded submissions each. The leak measure is the final model's
gain on the SEALED set beyond its gain on a FRESH QA-passed draw from the same region. Per attacker, one of:
- **PASS:** mean gap ≤ `--margin` + 2 SE **and** the run resolves the margin (2 SE ≤ margin);
- **FAIL:** mean gap > margin + 2 SE, or a final model scored on the sealed exam but NOT on the fresh draw (reason `fresh_unscored_while_sealed_scores`: the strongest overfit signal, never hidden);
- **INCONCLUSIVE (`add_seeds`):** 2 SE > margin, so the SE could hide any leak. Never a pass.
`all_pass` needs every attacker to PASS. The count of each unscored case is reported per attacker.
Output is aggregates only (per attacker: gains, gap, SE, bound, pass) plus the run digest; no model, no case, no seed of the exam.

## Run (Test Lead, AX42, custody)
```bash
python3 attack.py selftest                 # fake data first; must print "ok": true
python3 attack.py sums                     # compare with SHA256SUMS
python3 attack.py run --binding MODULE:FUNCTION --rounds N --seeds S --margin M --margin-source registered|provisional_sheet --out result.json
```
- `--binding` is the Challenge's custody binding (a factory returning an object with `dim`, `parts_registry()`, `gate_names()` and
  `grade(theta, which)` for `which` in `sealed` / `fresh`; theta = zeros is the unperturbed model). Motor 1.5 first; Cooling 1.7 once served.
- `--rounds` is the registered cadence over the 90-day rotation maximum (`a = R / (M·Σt)` graded submissions per miner per day,
  floor 1 a day, ceiling 1 per epoch; OWNER-CADENCE-AND-ROTATION-02). The Test Lead passes the registered figure; this tool has no default.
- `--margin` is the version's REGISTERED KOTH margin (`margin_N` from the recal), `--margin-source registered`; only if none is registered,
  the sheet's M = 0.01 with `--margin-source provisional_sheet`. The output records which was used.
- The custody binding is the Test Lead's; the Validator receipts it by digest before the run. `theta = 0` must reproduce the live king-free baseline grade.
- `--rebuild-noise` is the Challenge's registered rebuild noise (the Ladder step is `max(0.02, noise)`; the part step `max(0.05, 2·step)`).
- The proposal scale, shrink and patience are numerical settings recorded in the output and never tuned to reach a pass.

## If an attacker fails
Make that part coarser rather than hiding it, and re-run (the owner's rule): first `--part-step 0.10`, then `--bands`
(three-word band: low < 1/3 ≤ mid < 2/3 ≤ high). A part that fails even as a band goes to the owner with its attack numbers; this
tool never decides that. A step finer than the registered one is refused.

## Return
`result.json` and its `run_digest`, plus the exact command line and the binding's id. Evidence goes in EXAM_READINESS_GATE for the Challenge's launch version.
