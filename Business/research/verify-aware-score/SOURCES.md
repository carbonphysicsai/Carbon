# Source and reproduction manifest

All Carbon sources are pinned to public main commit
`7b8e89c34ca78711883b7157a3cd8225c618aa29`. The public EV5 README explicitly
classifies its committed results as synthetic DEVELOPMENT and excludes its
sealed confirmation report and host prediction bundles. EV4's engineering
value document section 12 classifies its results as public synthetic
DEVELOPMENT. No owner sheet, sealed confirmation, AX42, host-only bundle,
operator ledger, solver run or private data is used. Reading a published
digest is not a grant to fetch the bundle it describes.

## Numerical inputs

The analyzer reads only these exact files and refuses a byte mismatch. Inputs
are cached in ignored `inputs/`; caches are not duplicated into the PR. Its
`results.json.sources` records path, Git blob, SHA-256, byte count and commit.

| Alias | Public source | Required Git blob |
| --- | --- | --- |
| ev4.json | [EV4 outcomes](https://github.com/carbonphysicsai/Carbon/blob/7b8e89c34ca78711883b7157a3cd8225c618aa29/docs/development/evidence/ev4-2026-10-01/results.json) | `67ca13b966a2f6fb4b2e68b084e2909657e7ba7f` |
| ev5.json | [EV5 outcomes](https://github.com/carbonphysicsai/Carbon/blob/7b8e89c34ca78711883b7157a3cd8225c618aa29/docs/development/evidence/ev5-2026-10-03/results.json) | `7d6ccf75a47c2df56c66d0b223300e5fd9398512` |
| ev4-contract.json | [EV4 contract](https://github.com/carbonphysicsai/Carbon/blob/7b8e89c34ca78711883b7157a3cd8225c618aa29/carbon/battery/value/contracts/ev4-charge-protocol-selection.v1.json) | `3961b89a98c8877190bc010579852497057d3518` |
| ev5-contract.json | [EV5 contract](https://github.com/carbonphysicsai/Carbon/blob/7b8e89c34ca78711883b7157a3cd8225c618aa29/carbon/battery/value/contracts/ev5-charge-protocol-selection.v1.json) | `7cb89a3787a172427ae7024922a6e1641172eb91` |
| analysis.json | [EV5 H3 near-constraint measurements](https://github.com/carbonphysicsai/Carbon/blob/7b8e89c34ca78711883b7157a3cd8225c618aa29/docs/development/evidence/ev5-2026-10-03/analysis.json) | `c2131424a3d979b71b2881a114507c2b9dcd9bf6` |
| gate.json | [Historical gate provenance](https://github.com/carbonphysicsai/Carbon/blob/7b8e89c34ca78711883b7157a3cd8225c618aa29/docs/development/evidence/ev5-2026-10-03/gate.json) | `df128cb7c30bfa679d85f537cfe3651fc9873463` |

`gate.json` and the two contracts are identity/interpretation receipts; they
are not new quantitative gate evidence. The numerical paths are
`summary.members`, `components.E`, `decisions[member][question].outcome`,
`decisions[member][question].agreement`, `references[question].status_counts`,
and `analysis.value.H3.report.members[member].measurement.constraints`.

## Contracts and interpretation

- [EV5 public scope README](https://github.com/carbonphysicsai/Carbon/blob/7b8e89c34ca78711883b7157a3cd8225c618aa29/docs/development/evidence/ev5-2026-10-03/README.md), blob `5f9eddf85b0708e44aaeba7e4c057930aae346bd`: public results versus excluded host/private confirmation.
- [EV4 engineering-value record](https://github.com/carbonphysicsai/Carbon/blob/7b8e89c34ca78711883b7157a3cd8225c618aa29/docs/development/BATTERY_ENGINEERING_VALUE_EV4.md), blob `7fb86e7aa5539e0ba51dd32a07c6d68c007816bc`, sections 7 and 12: scope, one-condition decisions, reference-relative limitations.
- [Decision implementation](https://github.com/carbonphysicsai/Carbon/blob/7b8e89c34ca78711883b7157a3cd8225c618aa29/carbon/battery/value/decision.py), blob `b1d899d116317bd190ad6812f0aae5d3e8a16c0c`: select, assess_reference, outcome, classification and finite-bank comparator. It is read, not imported/executed.
- [Score tuning](https://github.com/carbonphysicsai/Carbon/blob/7b8e89c34ca78711883b7157a3cd8225c618aa29/carbon/battery/value/score_tuning.py), blob `49d2b0917d3a396ee8f3a528efcafeb12b66780d`: scoring-set joint false-feasible denominator and one-gate parser. Public per-constraint counts cannot substitute for it.
- [Registry v5](https://github.com/carbonphysicsai/Carbon/blob/7b8e89c34ca78711883b7157a3cd8225c618aa29/docs/development/evidence/battery-score-tuning/registry-v5.json), blob `d325fa62a18750ef53aa484b7050ed4c2de0c176`: A-Q geometric weights, cutoffs and comparators.
- [Owner rule](https://github.com/carbonphysicsai/Carbon/blob/7b8e89c34ca78711883b7157a3cd8225c618aa29/.agent/decisions/2026-10-08-OWNER-BATTERY-SCORE-RULE-01.md), blob `ba4079956281f489f7fd2e61f06ba109f6b41c91`: current prospective q semantics, G-FEAS strict >0.05, owner adoption boundary. Published aggregate historical receipts are not rereun here.
- [SCORE-PROOF-01 record](https://github.com/carbonphysicsai/Carbon/blob/7b8e89c34ca78711883b7157a3cd8225c618aa29/.agent/decisions/2026-10-10-SCORE-PROOF-01.md), blob `0098dbbe575850e2547842ff796a876634e264a8`: missing-leg withholding, roles and prospective test interface. No owner sheet is opened.
- [EV4 search selection](https://github.com/carbonphysicsai/Carbon/blob/7b8e89c34ca78711883b7157a3cd8225c618aa29/docs/development/evidence/ev4-2026-10-01/optimizer/selection.json), blob `89017ce0de5bfeee286a98bbda9eb645366c3be5`, and [EV5 search selection](https://github.com/carbonphysicsai/Carbon/blob/7b8e89c34ca78711883b7157a3cd8225c618aa29/docs/development/evidence/ev5-2026-10-03/optimizer/selection.json), blob `abfeaf5726e5a6b4d5bfb559324ff768298b9627`: single Mode-D choices and margin-ordered Mode-X probes are not a buyer top-k list.
- [VALUE-BAR-V1 evaluator](https://github.com/carbonphysicsai/Carbon/blob/7b8e89c34ca78711883b7157a3cd8225c618aa29/docs/development/challenge_pipeline/value-bar-evaluator.md), blob `5e2182fc90395648b40890b6902c5bc55da93ab3`, and [rule](https://github.com/carbonphysicsai/Carbon/blob/7b8e89c34ca78711883b7157a3cd8225c618aa29/docs/development/challenge_pipeline/value-bar-v1.json), blob `b47f59fd00a460a86652478c2f0828179ff2d05f`: item 2 NONE_FEASIBLE treatment; item 5 complete paired verified values and budget registration.
- [Equal-budget design](https://github.com/carbonphysicsai/Carbon/blob/7b8e89c34ca78711883b7157a3cd8225c618aa29/docs/development/challenge_pipeline/equal-budget-design.md), blob `ffc2adffd25356827ad91b6d8999b51d61fc76b6`, and [registration](https://github.com/carbonphysicsai/Carbon/blob/7b8e89c34ca78711883b7157a3cd8225c618aa29/docs/development/challenge_pipeline/equal-budget-registration.md), blob `0539b5214114ba49780f08588bb0e8f8a848d30b`: full condition panels, three resource caps, charged overhead and ASSUMPTION half/base/double budgets.
- Earlier public research: [#1055 planning audit](https://github.com/carbonphysicsai/Carbon/pull/1055), [#1059 gate design](https://github.com/carbonphysicsai/Carbon/pull/1059), [#1062 question resolution](https://github.com/carbonphysicsai/Carbon/pull/1062). Their conclusions motivate this ticket; no private input or aggregate-to-raw inversion is performed.

## External primary sources

- [Carpentier and Locatelli, fixed-budget best-arm identification](https://proceedings.mlr.press/v49/carpentier16.html), PMLR, 2016: terminal recommendation and fixed-budget reasoning. No transfer of bandit sample bounds to Carbon is claimed.
- [Hong and Zhang, Surrogate-Based Simulation Optimization](https://arxiv.org/abs/2105.03893): expensive simulation under computational budgets. Motivation, not a measured Carbon advantage.
- [Elmachtoub and Grigas, Smart Predict, then Optimize](https://arxiv.org/abs/1710.08005): decision-aware loss rather than prediction error. No inherited guarantee for the proposed verifier/search.
- [Gneiting and Raftery, Strictly Proper Scoring Rules](https://sites.stat.washington.edu/people/raftery/Research/PDF/Gneiting2007jasa.pdf): distinction between probabilistic truthfulness and a policy-value score.
- [Owen, The Pigeonhole Bootstrap](https://arxiv.org/abs/0712.1111): crossed dependence and separate row/column resampling. This motivates sensitivity; it does not establish exact nonlinear tau coverage on this small public panel.

## Reproduce without running physics

Fetch only the six exact public blobs above into `inputs/` with the stated
alias names. The analyzer independently checks their bytes before loading
JSON. A source hash mismatch is a stop, never a reason to silently repin.

```text
python Business/research/verify-aware-score/analyze.py --bootstrap-replicates 2000
python -m unittest discover -s Business/research/verify-aware-score -p test_analyze.py -v
```

The observed diagnostic environment was bundled Python 3.12.14 and NumPy
2.3.5. No dependency installation was performed. `analyze.py` imports only
standard-library modules and NumPy; no Carbon module, solver, cloud client or
network code. It writes LF UTF-8 deterministic JSON. Synthetic verifier tests
are structurally separate from any Carbon scientific or LIVE authority.
Native Windows tests are diagnostics; applicable repository CI supplies its
own acceptance. Nothing here claims scientific qualification.
