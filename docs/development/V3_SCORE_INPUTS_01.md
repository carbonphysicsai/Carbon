# V3-SCORE-INPUTS-01 — DEVELOPMENT collector and run-5 gap

**Status:** implementation for development evidence; no v3 run-5 score is
available. This is the prospective v3 rule in
`.agent/tickets/VALIDATOR-26_battery_rule_v3.md`, not an alteration of the
historical v2 practice result or an official validator run.

## Output definition

`python -m scripts.dev.battery.v3_score_inputs run` reconstructs one confirmed
recipe at its registered seed on CPU. It predicts a public development
screening set and every design in each registered Q3 scenario, then returns:

| Field | Exact calculation | Required source |
| --- | --- | --- |
| `a` | `1/(1+E)`, where `E` is `scoring.components`/`exam.evaluate` normalized screening error | the active development screening batches and their solved references |
| `q3_regret` and `q` | `quiz.q3_judge`/`q3_measures` after `quiz.q3_settle`; `q=1/(1+mean regret)` | eight Q3 scenarios per screening batch, complete 117-point standard lattices and terminal near-band refinements |
| `g_feas` | `score_tuning.false_feasible_rate` on the same screening set, against banded reference calls | screening references including at least one reference-infeasible case |
| `raw_score`, `eligible` | registered `G-FEAS/A-Q@0.05` candidate via `score_tuning.score_member`/`gate_verdict` | all three terms; the fixed score-tuning v4 registry |

The score combines `a` and `q` with weights 0.5 each as the registered
geometric mean. A G-FEAS breach or screening gate failure is ineligible;
missing/non-finite or malformed candidate predictions are candidate-caused.
Missing/failed references, a Q3 candidate that could change the reference
best, or an empty G-FEAS denominator are `FAILED_INFRA`/unmeasured, never a
candidate penalty. The full Q3 lattice and required refinement attempts must
be present. Refined OK records replace standard records using the existing
`quiz.q3_settle`; a failed refined attempt keeps its standard backstop.

The report binds the member recipe and seed, confirmation receipt, prediction
bundle, contract, rule registry, quiz registry, panel registration, screening
references, standard Q3 references, and refined Q3 references by SHA-256.
The panel registration must be committed and clean before the run. Every file
it names is restricted to its own directory below
`docs/development/evidence/v3-score-inputs/`. The confirmed-recipe input and
receipt must be below `docs/development/evidence/`. This structural boundary
does not establish that a mislabelled file is public; Data Collection must
verify provenance when registering a panel. Never put hidden, AX42, official
bank, or private-role references there.

## Registration and usage

Create a committed JSON panel under
`docs/development/evidence/v3-score-inputs/<panel>/panel.json`:

```json
{
  "schema": "carbon.battery.v3-score-input-panel.v1",
  "scope": "PUBLIC_SYNTHETIC_DEVELOPMENT",
  "job": "battery-q3-v8",
  "contract": {"path": "contract.json", "sha256": "sha256:<exact file digest>"},
  "rule_registry": "sha256:<score-tuning registry-v4 file digest>",
  "quiz_registry": "sha256:<quiz-registry-v8 file digest>",
  "settlement_rule": "carbon.battery.quiz.q3_settle.v8",
  "screening": {
    "batch_ids": ["<development screening batch>"],
    "case_ids": ["<all screening case IDs in that batch>"],
    "references": {"path": "screening.jsonl.gz", "sha256": "sha256:<exact file digest>"}
  },
  "q3": {
    "scenarios": [
      {"id": "<opaque scenario ID>", "batch_id": "<same screening batch>",
       "t_amb_c": "<registered numeric draw>", "soc0": "<registered numeric draw>"}
    ],
    "standard": {"path": "q3-standard.jsonl.gz", "sha256": "sha256:<exact file digest>"},
    "refined": {"path": "q3-refined.jsonl.gz", "sha256": "sha256:<exact file digest>"}
  }
}
```

The example shows one scenario for readability; the script requires **eight
per batch**. The reference files contain the usual battery truth records,
including each `case_id`, `inputs`, `status`, and `outputs`. The refined file
contains one terminal attempted record for every point returned by
`quiz.q3_refine_points`. An empty refined file is allowed only when no point
requires refinement.

Stage A supplies one JSON input per confirmed recipe:

```json
{
  "schema": "carbon.battery.confirmed-recipe-input.v1",
  "status": "CONFIRMED",
  "member": "<stable member ID>",
  "strategy": {"<pinned battery TrainingStrategy>": "..."},
  "seed": "<integer seed>",
  "recipe_digest": "sha256:<compiled recipe digest>",
  "confirmation": {"path": "<receipt.json>", "sha256": "sha256:<receipt digest>"}
}
```

The confirmation receipt must itself contain `status: CONFIRMED`, the same
`recipe_digest`, and the same `seed`. The collector checks those fields and
the compiled strategy digest. It does not make a scientific confirmation
decision. The operator retains both registration and receipts as DEVELOPMENT
evidence. Run one command per confirmed member:

```bash
python -m scripts.dev.battery.v3_score_inputs run \
  --panel docs/development/evidence/v3-score-inputs/<panel>/panel.json \
  --member docs/development/evidence/<confirmation>/<member>.json \
  --out <development-output>/<member>-v3.json
```

Once all eight run-5 first-seed recipes have complete measured reports on the
**same panel identity**, calculate the matched correlations. A G-FEAS gate
failure with all three measured terms remains in the comparison, ranked below
passers by the registered `candidate_scores` rule; a missing reference or
candidate prediction failure leaves the comparison unmeasured:

```bash
python -m scripts.dev.battery.v3_score_inputs compare-run5 \
  --report <development-output>/<member-1>-v3.json \
  --report <development-output>/<member-2>-v3.json
# Repeat --report for the other six members.
```

The comparison refuses a partial v3 conclusion and preserves the recorded
v2 one-seed τ/ρ as a separate line. The run-5 recipes are historical
diagnostic members, **not** confirmed Stage A recipes; confirmation status
must be established before using this collector on them.

## Main inventory and exact missing work (2026-10-09)

Main contains the eight distinct run-5 strategies/seeds and a v2 Q1 report,
but only SHA manifests for its large CPU prediction bundles. It also contains
EV4's **35-point** development decision grids, not the current **117-point**
Q3 lattice over eight registered scenarios; two public stand-in refined
scenarios are not that batch. The retained `refs-b` scoring set is a
**private-role** set and is prohibited here. There is no registered matched
development screening-set reference file plus settled eight-scenario Q3
panel for these members. Therefore v3 `a`, `q`, and scoring-set `g_feas`
cannot be computed on main for the eight members. The script's
`compare-run5` currently reports the recorded v2 one-seed Kendall τ-b
**−0.472805** and Spearman ρ **−0.538932**, with v3 **UNMEASURED**.

To obtain v3 on this panel, Data Collection/executor must:

1. Register development screening batch IDs/case IDs and public-development
   solved references for all cases, including reference-infeasible cases for
   G-FEAS; reuse only if the exact input/contract/reference identity matches.
2. Register eight Q3 scenarios per screening batch from the approved
   development draw law and solve their 117 lattice points. Run the existing
   `q3_refine_points` selection and terminal refined solves, then register
   the exact standard/refined files and digests. The script settles them.
3. Confirm the eight distinct run-5 recipes if those historical diagnostic
   members are to be used in Stage A, or use the Stage A confirmed set
   instead. Reconstruct each confirmed recipe and infer on the registered
   screening and Q3 inputs using this same command. Do not use pod weights.

**CPU estimate, not a run authorization:** one Q3 batch is 8 × 117 = **936
standard truth solves**. The registered public stand-in measured a median
81.8904 CPU-s/solve, so an all-new batch is approximately **21.3 CPU-hours**
of standard solves (wall time depends on available workers). Reused exact
development solves reduce that count. Let `R` be the count selected by
`q3_refine_points`; refined-solve cost is **R × measured refined CPU time**.
The run-5 follow-up measured 15 tighter solves at roughly 1–3 core-hours,
which suggests **4–12 core-minutes per refinement** as a planning range,
not a guarantee. If `N` screening references are absent, add **N standard
solves** (roughly 66–82 CPU-s each in the cited development runs); `N` is
not known until the screening registration is fixed. The prior 27 run-5 CPU
rebuilds with EV4 inference took about **25 minutes**; the eight-member v3
rebuild+117-point inference time is unmeasured and the script records its
reconstruction/inference seconds. This ticket ran **zero solves** and spent
nothing.
