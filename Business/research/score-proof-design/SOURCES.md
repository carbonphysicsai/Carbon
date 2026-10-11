# Sources and source limits

Checked 2026-10-10. Primary literature, official statistical documentation and committed public Carbon sources only. Linked works are summarized; no full article is copied. Numeric planning is recorded in [planning.json](planning.json), with assumptions and formulas.

## Carbon source snapshot

Main commit `fb47eb5725338a7733f6074650e58271c355006b`; these paths were read as source text. No runtime state or predictions were read.

| File | Blob SHA | Use |
| --- | --- | --- |
| [scripts/dev/battery/tuning_rescore.py](https://github.com/carbonphysicsai/Carbon/blob/fb47eb5725338a7733f6074650e58271c355006b/scripts/dev/battery/tuning_rescore.py) | `d0ee0167aba188a4010f749bab66cb7f62ec03c0` | Route, rule inventory, metric implementation or historical contract; not proof of results |
| [docs/development/evidence/battery-score-tuning/registry-v4.json](https://github.com/carbonphysicsai/Carbon/blob/fb47eb5725338a7733f6074650e58271c355006b/docs/development/evidence/battery-score-tuning/registry-v4.json) | `f08811e9e4e97a38b22f6915d31e906f602093b6` | Route, rule inventory, metric implementation or historical contract; not proof of results |
| [carbon/battery/value/score_tuning.py](https://github.com/carbonphysicsai/Carbon/blob/fb47eb5725338a7733f6074650e58271c355006b/carbon/battery/value/score_tuning.py) | `49d2b0917d3a396ee8f3a528efcafeb12b66780d` | Route, rule inventory, metric implementation or historical contract; not proof of results |
| [carbon/battery/value/score_candidates_b1.py](https://github.com/carbonphysicsai/Carbon/blob/fb47eb5725338a7733f6074650e58271c355006b/carbon/battery/value/score_candidates_b1.py) | `9771a06874683b8695c78ee2e6b6c464a8a720fb` | Route, rule inventory, metric implementation or historical contract; not proof of results |
| [carbon/design_search/score_value.py](https://github.com/carbonphysicsai/Carbon/blob/fb47eb5725338a7733f6074650e58271c355006b/carbon/design_search/score_value.py) | `57ab94540a6cd72abc2cd3524aca73ed0cc90151` | Route, rule inventory, metric implementation or historical contract; not proof of results |
| [carbon/battery/value/contracts/ev4-charge-protocol-selection.v1.json](https://github.com/carbonphysicsai/Carbon/blob/fb47eb5725338a7733f6074650e58271c355006b/carbon/battery/value/contracts/ev4-charge-protocol-selection.v1.json) | `3961b89a98c8877190bc010579852497057d3518` | Route, rule inventory, metric implementation or historical contract; not proof of results |

## Statistical sources

| Source | Supports | Limit for Carbon |
| --- | --- | --- |
| [Kendall (1938), A New Measure of Rank Correlation](https://doi.org/10.1093/biomet/30.1-2.81); [SciPy tau-b definition](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.kendalltau.html) | Ordinal rank agreement and tie-aware convention | Does not certify decision utility or safety |
| [SciPy Kendall tutorial](https://docs.scipy.org/doc/scipy/tutorial/stats/hypothesis_kendalltau.html), untied independence-null variance | Exact planning check leading to 175 independent recipes under the stated null | Not general variance at positive tau, with ties or clusters |
| [Efron and Tibshirani (1986)](https://doi.org/10.1214/ss/1177013815) | Bootstrap estimates of statistical uncertainty | Dependence structure and statistic regularity still matter |
| [Owen (2007), The Pigeonhole Bootstrap](https://arxiv.org/abs/0712.1111); [Owen and Eckles (2012), Bootstrapping Data Arrays of Arbitrary Order](https://arxiv.org/abs/1106.2125) | Separate resampling of crossed factors; naive IID resampling can misstate uncertainty | Mean-statistic results do not guarantee gated tau-b/argmin coverage |
| [Holm (1979), A Simple Sequentially Rejective Multiple Test Procedure](https://www.ime.usp.br/~abe/lista/pdf4R8xPVzCnX.pdf) | Strong FWER control using valid marginal tests without independence of tests | Does not repair invalid p-values or adaptive reuse of confirmation |
| [Cawley and Talbot (2010)](https://www.jmlr.org/papers/v11/cawley10a.html) | Selection overfits a noisy evaluation criterion; separate selection and evaluation | Grouped split and new-family transfer are Carbon-specific proposals |
| [NIST confidence intervals for a binomial proportion](https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm) | Exact binomial inversion; small failure counts need appropriate limits | The one-sided zero-miss formula here is a derivation requiring IID unsafe trials |

## Decision-theory sources

| Source | Supports | Limit for Carbon |
| --- | --- | --- |
| [Gneiting and Raftery (2007)](https://sites.stat.washington.edu/people/raftery/Research/PDF/Gneiting2007jasa.pdf) | Proper probabilistic forecasts and point-forecast distinctions | Does not make a geometric mixture decision-proper |
| [Blackwell (1953), Equivalent Comparisons of Experiments](https://doi.org/10.1214/aoms/1177729032) | Comparing information through attainable decision risks | No universal dominance from one scalar empirical score |
| [Donti, Amos and Kolter (2017)](https://proceedings.neurips.cc/paper/2017/file/3fc2c60b5782f641f76bcefc39fb2392-Paper.pdf) | Predictive accuracy and downstream task value can differ | Experiments in other tasks are not Carbon validation |

All thresholds for adopting a score remain HUMAN_INPUT. Published dates, source versions, counts and mathematical constants are identifiers/facts with low=base=high; no market value, buyer frequency or hardware-validity claim is inferred.

## Open Test Engineer integration snapshot

PR [#1044](https://github.com/carbonphysicsai/Carbon/pull/1044), inspected at head `83b03b7c8f883ee73403ee33f2fbf04f9bc84e93`; not merged at inspection. Only source and public PR metadata were read. No execution or owner-run sheet was accessed.

| Public source | Blob SHA | Use |
| --- | --- | --- |
| [docs/development/evidence/battery-score-tuning/registry-v5.json](https://github.com/carbonphysicsai/Carbon/blob/83b03b7c8f883ee73403ee33f2fbf04f9bc84e93/docs/development/evidence/battery-score-tuning/registry-v5.json) | `d325fa62a18750ef53aa484b7050ed4c2de0c176` | Integration proposal, not merged evidence or validated results |
| [docs/development/evidence/battery-score-tuning/proof-members-v1.json](https://github.com/carbonphysicsai/Carbon/blob/83b03b7c8f883ee73403ee33f2fbf04f9bc84e93/docs/development/evidence/battery-score-tuning/proof-members-v1.json) | `8ef84727bba4b20021201ca33ffa1c2ef358edf5` | Integration proposal, not merged evidence or validated results |
| [carbon/battery/value/score_proof.py](https://github.com/carbonphysicsai/Carbon/blob/83b03b7c8f883ee73403ee33f2fbf04f9bc84e93/carbon/battery/value/score_proof.py) | `b561615285a5f3affda5fce51aad474cbdd7a6cc` | Integration proposal, not merged evidence or validated results |
