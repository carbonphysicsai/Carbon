# What point-count evidence says, and what it does not

Source numbers below are **fixed low = base = high experiment constants** unless
a row explicitly presents a coupled low/base/high budget sweep. They are not
statistical intervals, a meta-analysis or universal extraction thresholds.
Accuracy relative to a reference truth, victim-prediction fidelity and exact
weight/source recovery are different outcomes.

| Evidence | Points / query budget | Published outcome and conditions | Transfer to Carbon |
|---|---|---|---|
| Tramèr et al., USENIX Security 2016, Table 1 | Amazon logistic models: 650 queries (Digits), 1,485 (Adult). BigML trees: 1,150 (German Credit), 4,013 (Steak Survey) | Authors extracted equivalent models in those service experiments; informative confidence/output access and model-class structure matter | Hundreds/thousands can suffice for simple models. These API attacks are not a proof that Carbon's fixed panel extracts an arbitrary neural operator |
| Tramèr et al., sections 4 and 7 | Binary logistic regression needs d+1 independent exact probability equations in the stated model; rounding tested at 2–5 decimals | Non-adaptive equation solving is possible; modest rounding was not a general defence, and label-only learning remained possible | A fixed downloadable batch can be enough when the function class is identifiable. Decimal count alone cannot certify protection |
| Jagielski et al., USENIX Security 2020, Table 3 | Coupled published query sweep low/base/high **250 / 1,000 / 4,000** | MixMatch extraction with task-specific unlabeled data: SVHN accuracy 95.82/96.87/97.07%, fidelity 96.38/97.45/97.61%; CIFAR-10 accuracy 87.98/90.63/93.29%, fidelity 88.79/91.39/93.99% | Useful behaviour can transfer from a small label set plus strong public data. This is classification, not an estimated physics-surrogate leakage curve |
| Orekondy et al., CVPR 2019, Table 2 | Fixed 60,000 queried images | Random open-world transfer sets recovered 0.81–0.96 times victim test accuracy across the stated tasks; the range is across tasks, with no pooled “base” invented | A copier need not know the original training distribution or use the same architecture. Large vision budgets do not give a safe lower bound for low-dimensional physics |
| Truong et al., CVPR 2021, abstract | Fixed 2,000,000 queries (SVHN), 20,000,000 (CIFAR-10) | Data-free extraction reached 0.99 and 0.92 times victim accuracy respectively | Lack of auxiliary data raises cost in these experiments. Carbon's open solver/data/physics knowledge changes that assumption |

Primary sources: [Tramèr paper](https://www.usenix.org/system/files/conference/usenixsecurity16/sec16_paper_tramer.pdf),
[Jagielski paper](https://www.usenix.org/system/files/sec20-jagielski.pdf),
[Knockoff Nets paper, Table 2](https://arxiv.org/pdf/1812.02766),
[Data-Free Model Extraction](https://openaccess.thecvf.com/content/CVPR2021/html/Truong_Data-Free_Model_Extraction_CVPR_2021_paper.html).
The original Jagielski Table 3 and Knockoff Table 2 were checked rather than
converting an abstract's qualitative claim into a query count.

## There are several copying goals

**Finite demo replay.** Once each point and its prediction is public, exact
lookup reproduces that finite table. It needs no weight recovery, query adaptation
or extrapolation. Carbon's showcase is a finite registered design family, so
this is the lowest bar and is source-countable today.

**Useful surrogate.** An attacker trains a different predictor using released
labels, public reference solves, correlations and priors. It may approximate the
incumbent or even correct its errors. How well it handles new designs depends on
smoothness, effective dimension, coverage and boundary behaviour. A method that
uses public information and actually improves verified design value is not
automatically a prohibited copy under Carbon's rights policy.

**High-fidelity extraction.** Matching an incumbent off distribution or
recovering its weights requires stronger access/structural conditions. Carbon's
fixed scalar projection does not provide adaptive arbitrary-input probes,
gradients or every raw time-series/field output. Do not claim that publishing
the demo proves complete model recovery. Conversely, a copier does not need
complete recovery to contest a score or replicate a customer-visible workflow.

**Training/private-data inference.** Model extraction and training-data privacy
are separate risks. Public inputs do not mean model outputs carry no proprietary
function information; neither do these studies prove Carbon leaks sealed inputs.
No hidden-data extraction experiment is authorized here.

## Public subnet analogue

Historical SN120 published king weights and rich per-turn duel data. Its guide
documents re-sharded duplicate weights passing a file-level check and a later
copy-related crown revocation. That is an identity/selection incident, not an
empirical count of points needed to distill a physics model. Its openly downloadable
king weights represent stronger access than Carbon's demonstration projection.
[Dated operator record](https://github.com/AffineFoundation/affine/blob/dd0d03d8ffae2ed944e1d3c22d2a8af03b80414c/affine/website/llms.txt#L517).

No public experiment was found that maps Carbon's exact projection, decision
family, construction constraints and takeover rule to a safe publication count.
Reported literature budgets are evidence of possibility under stated assumptions;
transporting them into a production cap would invent a security threshold.
