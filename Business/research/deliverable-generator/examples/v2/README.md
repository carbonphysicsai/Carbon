# PRD-01 development samples

Generation order: [battery](battery-nasa/sample.md), [f02](f02-nasa/sample.md),
[motor](motor-nasa/sample.md), [cooling-cell](cooling-cell-nasa/sample.md).
Source and framework revision: `c47e95349ae5ba862d8a873a2ec9b42932eb9fa0`.
The main generator is extended in place; its source-policy content digest is
in each manifest. Samples are not scientific experiments or customer packages.
Prior sample directories retain their historical revisions and bytes.

Every sample remains DEVELOPMENT_SAMPLE, eligible tier UNESTABLISHED and null
qualification. There is no guessed artifact, calibration, physical evidence or
acceptance. Missing PLT-01/model-card/trust-map/decision projections are explicit
GAPs. Existing MMS observations and separate owner acceptance links are copied,
not rejudged. Cooling's verification specification is not a measured MMS run.
f02 keeps the older time observations and the distinct t_end=0.375 diagnostic.
EV5 failures and other prior adverse findings retain their original scope.

Regenerate into a fresh directory with the current generator and this exact
public source revision, e.g.:

```text
python -m scripts.dev.customer_deliverable battery-fastcharge-ageing-development-v1 --ref c47e95349ae5ba862d8a873a2ec9b42932eb9fa0 --framework-ref c47e95349ae5ba862d8a873a2ec9b42932eb9fa0 --standard nasa-std-7009b --output-dir <fresh-directory>
```

No hidden/official material, model inference, reference solve, training, paid
compute, gate adoption or standards-compliance assessment is involved.
