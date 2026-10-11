# Sources, custody and reproducibility

Source snapshot: main `d426cf8b3f86a20c27e4dd82593b5935d99ada1f`. Public-read classification precedes data access. Research date: 2026-10-10 owner-local date; GitHub/UTC work crosses into 2026-10-11. Numbers in this record are identifiers or measured source facts, with low=base=high unless an explicit statistical interval or sensitivity range is given.

## Explicit public permission and limits

- [EV4 engineering-value record, section 12](https://github.com/carbonphysicsai/Carbon/blob/d426cf8b3f86a20c27e4dd82593b5935d99ada1f/docs/development/BATTERY_ENGINEERING_VALUE_EV4.md) calls the committed result files public synthetic DEVELOPMENT and separates the private financial ledger. The audit reads only results, not ledger, operator-host predictions or reference bundles.
- [EV5 evidence README](https://github.com/carbonphysicsai/Carbon/blob/d426cf8b3f86a20c27e4dd82593b5935d99ada1f/docs/development/evidence/ev5-2026-10-03/README.md) classifies the directory as public synthetic DEVELOPMENT, identifies results and gate artifacts, and explicitly says the owner-only confirmation report is not published there. No confirmation route is followed.
- [Public score/value alignment reporter](https://github.com/carbonphysicsai/Carbon/blob/d426cf8b3f86a20c27e4dd82593b5935d99ada1f/scripts/dev/battery/score_value_alignment_report.py) documents why committed EV4/EV5 value cannot be relabelled v3 Q3/G-FEAS. This audit preserves that boundary.

## Analyzer input allow-list

The analyzer opens exactly these three files in an explicitly supplied input directory, verifies Git blob identities before parsing, and also verifies that the EV5 gate's `results_sha256` binds the EV5 input. Full SHA-256 digests are in [results.json, `provenance`](results.json). It does not discover inputs by walking the repository or inspect host work directories. The large input copies are ignored locally and are not duplicated in the PR.

| Local name | Pinned source | Git blob |
| --- | --- | --- |
| ev4.json | [EV4 results](https://github.com/carbonphysicsai/Carbon/blob/d426cf8b3f86a20c27e4dd82593b5935d99ada1f/docs/development/evidence/ev4-2026-10-01/results.json) | `67ca13b966a2f6fb4b2e68b084e2909657e7ba7f` |
| ev5.json | [EV5 results](https://github.com/carbonphysicsai/Carbon/blob/d426cf8b3f86a20c27e4dd82593b5935d99ada1f/docs/development/evidence/ev5-2026-10-03/results.json) | `7d6ccf75a47c2df56c66d0b223300e5fd9398512` |
| gate.json | [EV5 historical near-optimism gate](https://github.com/carbonphysicsai/Carbon/blob/d426cf8b3f86a20c27e4dd82593b5935d99ada1f/docs/development/evidence/ev5-2026-10-03/gate.json) | `df128cb7c30bfa679d85f537cfe3651fc9873463` |

Two additional public SR2/SR3 aggregate result blobs were inspected during source discovery. They lack matched question-level scoring inputs, so they are not inputs to the analyzer or the counts. No Q1 aggregate is treated as a question matrix; Q1 cannot supply its missing question variance.

## #1044 integration source, read-only

The open PR was inspected at `fd3308af4041c32b8609cfccc5f5d5987b4a4a0f`:

- [score_proof.py](https://github.com/carbonphysicsai/Carbon/blob/fd3308af4041c32b8609cfccc5f5d5987b4a4a0f/carbon/battery/value/score_proof.py), blob `41d705618243c2251842fcf749e076513afc9ffd`: crossed recipe/question bootstrap, scoring cases fixed; purposive controls excluded from primary tau; incomplete legs withheld; known-bad member top-half and unsafe recall screens.
- [proof-members-v1.json](https://github.com/carbonphysicsai/Carbon/blob/fd3308af4041c32b8609cfccc5f5d5987b4a4a0f/docs/development/evidence/battery-score-tuning/proof-members-v1.json), blob `764a53fe2205ed956254315d44cbd4bb9767ab24`: EV4 recipe families are Level 0; controls are level-agnostic anchors; the missing higher levels are explicit. Its owner-side fill instructions are not execution authorization for this researcher.
- [score_tuning.py](https://github.com/carbonphysicsai/Carbon/blob/fd3308af4041c32b8609cfccc5f5d5987b4a4a0f/carbon/battery/value/score_tuning.py), blob `49d2b0917d3a396ee8f3a528efcafeb12b66780d`: current G-FEAS uses scoring-case feasibility calls, disjoint from the decision-side unsafe labels used here. The historical near gate is not G-FEAS.

## Statistical sources and claim limits

| Primary source | Use here | Limit |
| --- | --- | --- |
| [Owen (2007), The pigeonhole bootstrap](https://arxiv.org/abs/0712.1111) | Separately resample crossed row and column clusters. | Its mean-statistic consistency result does not establish percentile tau-b coverage for this gated, purposive panel. |
| [Owen and Eckles (2012), Bootstrapping data arrays of arbitrary order](https://arxiv.org/abs/1106.2125) | Product weights preserve the crossed array and avoid false row/case independence. | This implementation uses multinomial recipe and question/block resampling; it does not claim all guarantees of other reweighting schemes. |
| [NIST, Exact Binomial](https://www.itl.nist.gov/div898/software/dataplot/refman2/auxillar/exacbino.htm) | Invert binomial tails for small-sample, equal-tail exact proportion intervals. | The interval interpretation requires independent Bernoulli recipe trials; hyperparameter relatives and shared question effects can violate that model. |
| [Howard et al. (2021), Time-uniform confidence sequences](https://arxiv.org/abs/1810.08240) | Explain why a fixed-sample CI cannot authorize arbitrary optional stopping at an interim look. | No confidence sequence for crossed gated tau-b is implemented or claimed here. |
| [#1045 statistical design](../score-proof-design/STATISTICAL_DESIGN.md) | Original analytic assumptions, frozen scoring-set distinction and multiple-comparison discipline. | This audit replaces selected variance assumptions with public measurements; it does not overwrite the earlier NOT_RUN historical record. |

## Reproduce without a solver or protected route

Acquire only the allow-listed public GitHub blobs. For each row above, `gh api repos/carbonphysicsai/Carbon/git/blobs/<git-blob> --jq .content` returns base64; decode to its listed local name under an input directory. Do not substitute a local host run directory or a newer unpinned evidence file. Then, with Python and NumPy available:

```text
python Business/research/score-proof-planning-audit/audit.py --self-check
python Business/research/score-proof-planning-audit/audit.py --input-dir Business/research/score-proof-planning-audit/inputs --output Business/research/score-proof-planning-audit/results.json
```

The fixed public research RNG seed is unrelated to any official/derived exam seed. All data-dependent outputs carry full precision in JSON; Markdown tables round for readability. `runtime` identifies the actual interpreter and NumPy. The analyzer imports no Carbon module and has no network call, solver call, training call or hidden-material adapter.

The local Docker daemon was unavailable. Native numerical runs are research diagnostics, **not canonical runtime or scientific qualification**. Repository acceptance is separately reported by PR CI. Self-checks cover monotone/reversed/undefined tau, repeated-cluster ties including gate floors, an exact binomial tail, exact zero-success limit and screen-count edge cases. They do not establish interval coverage for future physics data.
