# Source and reproduction record

Inputs are bound in analyze.py/results.json to Git blobs at public commit
`07d414638f1ede517d59cca2a30554360d934716`:

- [EV4 results](https://github.com/carbonphysicsai/Carbon/blob/07d414638f1ede517d59cca2a30554360d934716/docs/development/evidence/ev4-2026-10-01/results.json): summary.members, components.E, decisions, references.
- [EV5 results](https://github.com/carbonphysicsai/Carbon/blob/07d414638f1ede517d59cca2a30554360d934716/docs/development/evidence/ev5-2026-10-03/results.json): same fields, including constructed attacks.
- [EV5 analysis](https://github.com/carbonphysicsai/Carbon/blob/07d414638f1ede517d59cca2a30554360d934716/docs/development/evidence/ev5-2026-10-03/analysis.json): value.H3.report.members.*.measurement.constraints; sign-error control's 70/74 is stated in the [public classification and verdict record](https://github.com/carbonphysicsai/Carbon/blob/07d414638f1ede517d59cca2a30554360d934716/docs/development/evidence/ev5-2026-10-03/README.md). Its owner-only confirmation is excluded.
- [Registry v5](https://github.com/carbonphysicsai/Carbon/blob/07d414638f1ede517d59cca2a30554360d934716/docs/development/evidence/battery-score-tuning/registry-v5.json): candidate definitions, GF scored-case denominator, strict owner comparison.
- [#1059 feasibility-gate research](https://github.com/carbonphysicsai/Carbon/pull/1059), [#1073 verification-aware research](https://github.com/carbonphysicsai/Carbon/pull/1073), [#1045 statistics](https://github.com/carbonphysicsai/Carbon/pull/1045), [#1055 public planning audit](https://github.com/carbonphysicsai/Carbon/pull/1055): prior descriptive sweeps and prospective design. Current historical results are not rewritten.

Place only the three named public files into ignored inputs/ as ev4.json,
ev5.json and analysis.json. The audit refuses a blob mismatch. Run:

```text
python Business/research/score-candidate-attacks/analyze.py
python -m unittest discover -s Business/research/score-candidate-attacks -p test_analyze.py -v
python -m black --check Business/research/score-candidate-attacks/analyze.py
python -m black --check Business/research/score-candidate-attacks/test_analyze.py
python -m ruff check Business/research/score-candidate-attacks
```

Pinned tooling: Black 26.5.1, Ruff 0.16.3, repo pyproject.toml. Native
research calculations are diagnostics, not canonical scientific qualification.
No Carbon runtime, solver, model or protected pack is imported. Numeric
counts and tau are measured finite-panel diagnostics. Tied rank intervals
and gate allowances are exact calculations, not uncertainty bounds.
ASSUMPTION sensitivities and missing fields are explicitly separate.
