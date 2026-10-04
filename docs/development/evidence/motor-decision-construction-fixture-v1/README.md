# Motor decision construction and evaluation fixture v1

**Status:** deterministic DEVELOPMENT construction plus analytical-fixture
evaluation; no GetDP evidence was accessed or claimed.

This directory is the inspectable output of:

```text
python -m scripts.dev.motor.decision_study construct \
  --out docs/development/evidence/motor-decision-construction-fixture-v1/construction
python -m scripts.dev.motor.decision_study evaluate-fixture \
  --construction docs/development/evidence/motor-decision-construction-fixture-v1/construction \
  --out docs/development/evidence/motor-decision-construction-fixture-v1/evaluation
```

It binds the exact `MOTOR_SYNTHETIC_DECISION_V1.json` scenario, the registered
analytical and learned-model identities, the two search methods, their budgets,
the analysis policy and all four persisted proposal commitments. The exact
construction identity is
`sha256:921a19d5368c001a52f230999999fc3b31761d207acb7f43d133d5c49e641cab`;
the freeze digest is
`sha256:b55510b3cc8200d502f36d9c9b5701850b57bf0cb8cb19601e7d2c7f5ecf3903`.

## Construction outcome

| Model | Search | Selection | Attempted queries |
|---|---|---|---:|
| Analytical | Fixed grid | `d07` | 48 |
| Analytical | Screen then confirm | `d07` | 48 |
| Learned KRR | Fixed grid | `d06` | 48 |
| Learned KRR | Screen then confirm | `d06` | 43 |

The analytical model predicts zero ripple and selects `d07`. The reconstructed
learned KRR predicts a worst-condition ripple fraction of about 0.2347 and a
worst-condition mean of about 4.569 N m for `d06`. This is model output, not
reference truth. The model disagreement is a reason to run the preregistered
finite comparator after compute approval; it is not a learned-model advantage.

Screening preserved each model's selection. It saved five learned-model query
attempts and no analytical attempts in this one construction. Query count is a
diagnostic view. The deciding search-method comparison must use measured
computational cost, including reconstruction and inference, as registered by
`OWNER-GRAPHITE-TEST-WAVE-01` section 3.

The learned reconstruction used all 150 retained public TRAIN records at the
already selected length 4.0 and ridge 0.0001. This fixture recorded 0.1918 s
wall time and 2.7188 CPU seconds for reconstruction on the Windows development
host. Historical training-data generation and tuning cost remains unavailable
and is not treated as zero.

## Analytical-fixture evaluation

All four proposals are feasible under the analytical fixture, and the
analytical finite comparator is complete. Both selected geometries have zero
fixture regret because the analytical model emits flat torque curves. That is
a lifecycle/reporting smoke result, not independent validation. The 24 arm
condition uses reduce to 12 unique selected design-condition cases (8
representative and 4 boundary-stress), with 12 evidence reuses. The report
contains descriptive counts only and makes no population reliability claim.

## Integrity anchors

- `construction/construction.json`: `sha256:2de656fd7fe284d58ba3190c00862f4bb56bc8e9a095f184388bced848045cd6`
- `construction/freeze.json`: `sha256:e73ad230f30fd22d5e75276f61da0f87a997a3a67ae9c0039cf636dea3f072bd`
- `construction/reconstruction.json`: `sha256:65aeecc9bd158b04b0bbb1df170f84b2e67c2b147e219686bae2f75ca4d2220a`
- `evaluation/result.json`: `sha256:85955d165d1f1de3d24f7457b08b9e30032fdf6bfbee2cf95547fb7e6412fbab`
- `evaluation/report.md`: `sha256:a9db0a42b44eddc26d31cd91c21401cfce88ee4079bbbfa27afb2f9736e7d1e6`

Each commitment's path, commitment digest and file digest are bound in
`construction.json`.

## Claim ceiling and next step

This fixture establishes that Carbon can reconstruct the two registered models,
run both methods and persist all proposals before reference access. It does not
establish reference feasibility, regret, model value, customer relevance,
scientific qualification, production qualification or Launchpad readiness.

Strict GetDP provenance, restart-safe campaign accounting, full finite-set
evaluation and report generation are implemented. The next step is to build
and pin the Docker image, generate the exact image-bound plan and obtain
compute/spend approval. The 48-case reference campaign must not start before
that approval.
