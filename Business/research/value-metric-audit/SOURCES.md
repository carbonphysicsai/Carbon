# RES-07 source and interpretation register

Research pin: Carbon main `1238dd3471f73d3fc0df375de1d63c4663e380b3`. Public development evidence only. A link to a committed file below means that version at the pin, even if main later changes. Input counts, hashes and computed panel statistics are **MEASURED** (low = base = high); numerical research scenarios are **ASSUMPTION**. Unknown buyer prices, production policies and missing measurements are **HUMAN_INPUT**.

## Carbon evidence

Source-publication follow-up: [RES-07 executable](res07-analyze.py.txt), [source pin](source-pin.json) and [both-study replay instructions](REPLAY.md). The source's SHA-256 is `e91f89f9cae53cd7b5e1f252910f197f8a0334adbf47e2bb492d7601dffa91ff`; its exact 39,511 bytes are preserved. This resolves the Validator's request in #1218 without changing recorded measurements.

| Source at the pin | Git blob / identity | Use and limits |
| --- | --- | --- |
| [EV4 registered results](../../../docs/development/evidence/ev4-2026-10-01/results.json) | `67ca13b966a2f6fb4b2e68b084e2909657e7ba7f` | Historical A40-era selections; preserve original outcomes and eligible cohort. |
| [EV5 registered results](../../../docs/development/evidence/ev5-2026-10-03/results.json) | `7d6ccf75a47c2df56c66d0b223300e5fd9398512` | Historical selections on another public grid; no EV5 model execution. |
| [EV4 contract](../../../carbon/battery/value/contracts/ev4-charge-protocol-selection.v1.json) | `3961b89a98c8877190bc010579852497057d3518` | Action grid, conditions, objective, reference bands, default and loss. |
| [EV5 contract](../../../carbon/battery/value/contracts/ev5-charge-protocol-selection.v1.json) | `7cb89a3787a172427ae7024922a6e1641172eb91` | Corresponding EV5 historical meanings. |
| [Decision helpers](../../../carbon/battery/value/decision.py) | `b1d899d116317bd190ad6812f0aae5d3e8a16c0c` | Pure measurement, reference assessment, selection and outcome arithmetic; imported as an isolated local helper, without importing Carbon, any solver or model. |
| [Refined EV4 records](../../../docs/development/evidence/ev4-dev-refined-v1/records.jsonl.gz), [policy/readme](../../../docs/development/evidence/ev4-dev-refined-v1/README.md) | records `c2840676909bae6585e92402a3bc7b86d6b59c27`; readme `24fa05f6941f50fd3cc7540a70c584b07d9a349a` | Secondary fresh-array sensitivity only. Overlay the 22 OK records; retain the five failed references and unchanged bands. No historical rescore. |
| [RES-06 measurements](../../../docs/development/evidence/physics-consistency-gates-01/measurements.json), [report](../../../docs/development/evidence/physics-consistency-gates-01/REPORT.md) | measurements `e1bcbec357000494e420d546d698e609dc517e6c` | Development-only rest/bound residuals on the exact same CPU bundle digests. Not a full conservation or calibration test. |
| [VERIFY-aware design](../verify-aware-score/DESIGN.md) | `242b0dde399a82dc4320947558abcd29be59c4db` | Frozen shortlist, complete-panel verification, bounded budgets and reference-relative claims. |
| [VALUE-BAR-V1](../../../docs/development/challenge_pipeline/value-bar-v1.json), [evaluator evidence contract](../../../docs/development/challenge_pipeline/value-bar-evaluator.md) | rule `b47f59fd00a460a86652478c2f0828179ff2d05f`; evaluator `5e2182fc90395648b40890b6902c5bc55da93ab3` | Requires strongest cheap and solver-alone arms, matched admissibility, registered held-out folds and measured complete-query costs. This audit does not establish a pass. |
| [Business canon](../../Business_Canon.md), [scientific canon](../../../docs/context/SCIENTIFIC_REFERENCE_CANON_V4_MASTER.md) | At the research pin | Buyer utility never overrides scientific failure; P, Q and w are distinct; reference-relative evidence is not physical qualification. |

The owner supplied a **read-only public** Windows copy in `codex-queue/inputs/ev4-public-proof/`: `experiment-predictions/`, `proof-predictions/`, `attack-predictions/` and `ev4-decision-references.jsonl`. It is not committed. The derived [results](results.json) bind each used bundle's SHA-256, folder, byte count and duplicate receipt, plus reference SHA-256 `72ea300b42fe1ca4e54b9c6131cb126ca7217ebddd5f1dddca8044a7bcef2dbf`. Only the allow-listed 840 EV4 development/verification keys contribute to measurements. No other output, model artifact or case is analyzed. Raw predictions and references are absent from this PR.

The owner explicitly confirmed on 2026-10-12 that B1–B10 has no public copy and no beyond-envelope reference set has been solved. Both are gaps. Unmerged Platform work and protected material were not inspected. The queue's reported postmortem tau 0.953 is context supplied by the owner, not a statistic reproduced by this audit's different cohort/masks.

## Primary literature

| Source | What it supports | What it does not establish here |
| --- | --- | --- |
| [Wilder, Dilkina and Tambe, AAAI 2019](https://ojs.aaai.org/index.php/AAAI/article/view/3982) | Prediction accuracy can misalign with the downstream decision objective; evaluate the decision pipeline. | Battery prices, failure costs, reuse demand or qualification. |
| [Mandi et al., ICML 2022](https://proceedings.mlr.press/v162/mandi22a.html) | Ranking feasible solutions is a decision-focused objective; solution subsets affect runtime/regret. | That Carbon beats a cached map or an industrial search policy. |
| [Owen and Eckles, Annals of Applied Statistics 2012](https://arxiv.org/abs/1106.2125v3) | Crossed factors require dependence-aware uncertainty; independently reweight factors rather than treating every seed/question as independent. | Guaranteed coverage for tau-b on this small panel. Their main results concern variance of means. Our bootstrap is an exploratory sensitivity. |
| [Gulrajani and Lopez-Paz, ICLR 2021](https://arxiv.org/abs/2007.01434) | Out-of-domain evaluation and model selection must be stated separately; many tuned public tests cannot certify unseen-domain generalization. | That EV4 verification is a new physical domain or independent of earlier public studies. |

Retrieved 2026-10-12. Literature motivates the measurement design; none supplies a universal economic coefficient or a production gate threshold.
