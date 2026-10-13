# PRD-04 public development samples

Fresh renderings from committed public evidence and framework at
`7f9d7a2fc99205b67d6e03393c68e1f85e716e58`. No historical examples were overwritten.
The generator's updated source-policy digest is recorded in each manifest.
These examples demonstrate document assembly, not an accepted product or risk
assessment. Every qualification record remains null and eligibility UNESTABLISHED.

| Sample | View | What remains open |
| --- | --- | --- |
| [Battery](battery-asme40/sample.md) | ASME V&V 40 topic crosswalk, matrix and risk-informed plan | Licensed clauses, applicability, actual product/context/risk and physical evidence |
| [f02](f02-nasa/sample.md) | NASA capability/results, conditional MMS decision beside both runs | t_end 0.375 is an MMS test-design condition, not physical validity or full reference adequacy |
| [Motor](motor-nasa/sample.md) | NASA verification and retained evidence gaps | Linear magnetostatic MMS does not qualify torque/skew/material or customer use |
| [Cooling](cooling-cell-dod/sample.md) | Defense VV&A evidence/questions and customer actions | Verification plan is not a measured MMS result; program tailoring/independence/accreditation stay HUMAN_INPUT |

Each directory has the same four outputs: sample Markdown, PROPOSAL_V1 JSON,
exact framework-schema copy and generation manifest. The manifest's versioned
credibility annex retains typed source outcomes, missing evidence and adverse
links. Coverage is not acceptance; reference-relative results are not physical
validation. Actual package projections and risk/context declarations are absent
in this source revision, so candidate identity and risk fields remain explicit
gaps. Positive adapter cases exist only as synthetic tests, not these examples.

Reproduce from the PR implementation with the pinned source revision above:

```text
python -m scripts.dev.customer_deliverable battery-fastcharge-ageing-development-v1 --ref 7f9d7a2fc99205b67d6e03393c68e1f85e716e58 --standard asme-vv40 --output-dir <fresh-battery-dir>
python -m scripts.dev.customer_deliverable f02 --ref 7f9d7a2fc99205b67d6e03393c68e1f85e716e58 --standard nasa-std-7009b --output-dir <fresh-f02-dir>
python -m scripts.dev.customer_deliverable motor --ref 7f9d7a2fc99205b67d6e03393c68e1f85e716e58 --standard nasa-std-7009b --output-dir <fresh-motor-dir>
python -m scripts.dev.customer_deliverable cooling-cell --ref 7f9d7a2fc99205b67d6e03393c68e1f85e716e58 --standard dod-vva --output-dir <fresh-cooling-dir>
```

No solver/model run, risk threshold, customer requirement criterion, standards
compliance, qualification, accreditation, licence, price or export clearance
is supplied by these samples. Carbon Validator and Data Collection review the
source/evidence joins; PR Head/owner handles engineering review and merge.
