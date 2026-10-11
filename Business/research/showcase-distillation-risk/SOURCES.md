# Source register, numerical status and gaps

Access date 2026-10-11. Primary papers and pinned public Carbon source. No live
showcase or model API was queried and no model was trained/extracted. Local
arithmetic uses public coordinate counts only.

| ID | Source | Exact use / limit |
|---|---|---|
| C1 | [score_feed.py](https://github.com/carbonphysicsai/Carbon/blob/43f664319e1c2f977908186d7a017f2eb0771251/carbon/challenge_validator/score_feed.py) | Registered EV4 development showcase, whole prediction map, separate aggregate-score rounding, retained artifact identity |
| C2 | [showcase.py](https://github.com/carbonphysicsai/Carbon/blob/43f664319e1c2f977908186d7a017f2eb0771251/carbon/dashboard/showcase.py) | Browser/replay consumer and public reference route; static inspection only |
| C3 | [EV4 public synthetic contract](https://github.com/carbonphysicsai/Carbon/blob/43f664319e1c2f977908186d7a017f2eb0771251/carbon/battery/value/contracts/ev4-charge-protocol-selection.v1.json) | Development grid 7 x 5 x 4 x 3; no sealed conditions used; maximum, not observed live cardinality |
| C4 | [battery_q3_v8.py projection](https://github.com/carbonphysicsai/Carbon/blob/43f664319e1c2f977908186d7a017f2eb0771251/carbon/design_search/battery_q3_v8.py#L149) | Three continuous quantities plus reach class; unreachable-time mask |
| P1 | [Tramèr et al., Stealing Machine Learning Models via Prediction APIs, USENIX Security 2016](https://www.usenix.org/system/files/conference/usenixsecurity16/sec16_paper_tramer.pdf) | Table 1 service counts; section 4 equation solving; section 7 rounding/label-only limits. Exact model-class/access assumptions are essential |
| P2 | [Jagielski et al., High Accuracy and High Fidelity Extraction, USENIX Security 2020](https://www.usenix.org/system/files/sec20-jagielski.pdf) | Table 3 label-budget sweep with auxiliary unlabeled data; accuracy and fidelity differ. Not a physics-surrogate risk estimate |
| P3 | [Orekondy et al., Knockoff Nets, CVPR 2019](https://arxiv.org/pdf/1812.02766), [proceedings entry](https://openaccess.thecvf.com/content_CVPR_2019/html/Orekondy_Knockoff_Nets_Stealing_Functionality_of_Black-Box_Models_CVPR_2019_paper.html) | Table 2 at 60k budget, random open-world performance range; different distribution/architecture can still transfer functionality |
| P4 | [Truong et al., Data-Free Model Extraction, CVPR 2021](https://openaccess.thecvf.com/content/CVPR2021/html/Truong_Data-Free_Model_Extraction_CVPR_2021_paper.html) | Sourced 2M/20M query experiments and normalized accuracy; different auxiliary-data assumptions |
| A1 | [Historical SN120 incident/guide](https://github.com/AffineFoundation/affine/blob/dd0d03d8ffae2ed944e1d3c22d2a8af03b80414c/affine/website/llms.txt#L517) | Operator-reported re-sharded copy incident and richer public model/data access; not a distillation sample-count experiment |

Published point/query counts and experiment outcomes are fixed low/base/high at
their stated value. Jagielski's 250/1,000/4,000 is a coupled budget scenario, not
an uncertainty interval. Knockoff's cross-task range has no scientifically
meaningful base; no midpoint is invented. All Carbon transport examples,
polynomial hypotheses, publication delays, point-count sensitivity and
quantization scenarios are ASSUMPTION. Actual leakage, customer-demo utility
and policy thresholds remain HUMAN_INPUT.

Gaps: no matched Carbon extraction experiment; no live emitted-count receipt;
no empirical cross-lineage leakage curve; no evidence that rounding/error-only
publication preserves near-frontier decisions; no measured customer conversion
or willingness to pay; no validated functional-copy detector. The literature
does not establish confidentiality, scientific qualification or an IP violation.
This dossier proposes how to collect those missing public diagnostics without
accessing sealed material. VALIDATOR-31 source reconciliation is still needed.
