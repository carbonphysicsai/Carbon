# Immutable public sources and reproduction

Source snapshot for main: `fcab655b30f42d4e3a42786f22af8aa2b08402e2`.
Registry/split snapshot: #1161 head
`e99881523712d2a8969a003a7ffcdd99641f1d01`.
The analyzer refuses a Git-blob mismatch before reading any measurements.
Raw public inputs stay in ignored temporary storage, not in this PR.

| Input | Source | Git blob |
| --- | --- | --- |
| EV4 | [Public results](https://github.com/carbonphysicsai/Carbon/blob/fcab655b30f42d4e3a42786f22af8aa2b08402e2/docs/development/evidence/ev4-2026-10-01/results.json) | 67ca13b966a2f6fb4b2e68b084e2909657e7ba7f |
| EV5 | [Public results](https://github.com/carbonphysicsai/Carbon/blob/fcab655b30f42d4e3a42786f22af8aa2b08402e2/docs/development/evidence/ev5-2026-10-03/results.json) | 7d6ccf75a47c2df56c66d0b223300e5fd9398512 |
| EV5 interpretation | [Public analysis](https://github.com/carbonphysicsai/Carbon/blob/fcab655b30f42d4e3a42786f22af8aa2b08402e2/docs/development/evidence/ev5-2026-10-03/analysis.json) | c2131424a3d979b71b2881a114507c2b9dcd9bf6 |
| Candidate contract | [Registry v9](https://github.com/carbonphysicsai/Carbon/blob/e99881523712d2a8969a003a7ffcdd99641f1d01/docs/development/evidence/battery-score-tuning/registry-v9.json) | 698aa61873e6970039d0c8a9d76da21a4a269412 |
| Future public split | [LEG/VALUE rule](https://github.com/carbonphysicsai/Carbon/blob/e99881523712d2a8969a003a7ffcdd99641f1d01/docs/development/evidence/battery-score-tuning/public-dev-split-v1.json) | befed141a5fb6283a96722efb3862de12c29362f |

Definitions read, never executed: [score_tuning](https://github.com/carbonphysicsai/Carbon/blob/fcab655b30f42d4e3a42786f22af8aa2b08402e2/carbon/battery/value/score_tuning.py),
[ratios](https://github.com/carbonphysicsai/Carbon/blob/fcab655b30f42d4e3a42786f22af8aa2b08402e2/carbon/battery/value/ratios.py),
[proximity/envelope](https://github.com/carbonphysicsai/Carbon/blob/fcab655b30f42d4e3a42786f22af8aa2b08402e2/carbon/battery/value/score_candidates_b1.py),
[mean-optimism gate](https://github.com/carbonphysicsai/Carbon/blob/fcab655b30f42d4e3a42786f22af8aa2b08402e2/carbon/battery/value/admissibility.py),
[verification contract](https://github.com/carbonphysicsai/Carbon/blob/fcab655b30f42d4e3a42786f22af8aa2b08402e2/carbon/design_search/verify_aware.py),
[Q3 replay](https://github.com/carbonphysicsai/Carbon/blob/fcab655b30f42d4e3a42786f22af8aa2b08402e2/carbon/battery/value/verify_quiz.py).
No tuning CLI, host bundles, operator work directory or sealed question was read.

KEEP [#1082 attack study](https://github.com/carbonphysicsai/Carbon/pull/1082),
[#1073 verified-service study](https://github.com/carbonphysicsai/Carbon/pull/1073)
and [#1059 gate study](https://github.com/carbonphysicsai/Carbon/pull/1059).
Their historical verdicts are not changed. The 70/74 sign-control near-FA
source is the prior attack [public source/classification record](https://github.com/carbonphysicsai/Carbon/blob/fcab655b30f42d4e3a42786f22af8aa2b08402e2/Business/research/score-candidate-attacks/ATTACKS.md);
it cannot supply joint scoring-set G-FEAS.

Literature consulted 2026-10-12: [Hardt et al.](https://arxiv.org/abs/1506.06980),
[Dwork et al.](https://arxiv.org/abs/1506.02629),
[Tramèr et al.](https://www.usenix.org/conference/usenixsecurity16/technical-sessions/presentation/tramer).
Only their supported general results are used; Carbon-specific rates and
countermeasure effectiveness are not inferred from them.

Place the five exact files above under a local public-input directory as
ev4.json, ev5.json, analysis.json, registry-v9.json and public-dev-split-v1.json.
Then run:

```sh
python Business/research/score-candidate-attacks-v9/analyze.py --inputs PUBLIC_INPUT_DIRECTORY
python Business/research/score-candidate-attacks-v9/test_analyze.py
```

The audit imports only stdlib/NumPy, never Carbon runtime/evaluator/solver.
Native diagnostics used Python 3.12.14 and NumPy 2.5.4. Formatting checks
use pinned Black 26.5.1 and Ruff 0.16.3. CI's pinned canonical environment
owns acceptance; native diagnostics alone are not canonical qualification.
All exact measurements, sensitivity settings and provenance are in
[results.json](results.json). Fixed measured points are not invented CIs;
all toy/sample-intervention ranges are explicitly ASSUMPTION.
