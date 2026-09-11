# Carbon reference accuracy-cost frontier study v0.1

**Date:** 11 September 2026

**Status:** public development research only. No production reference configuration, tolerance, uncertainty floor, decision threshold, or scientific qualification is selected.

## Question

For a proposed Challenge, what is the cheapest reference configuration that is still accurate enough to support the candidate distinctions Carbon wants to make?

This is separate from upfront exam-qualification cost. The convergence campaign is qualification evidence; once a reference configuration is approved, its recurring cost enters live-operation economics.

## Physical fixture

Same easy periodic viscous Burgers development fixture used by the Carbon Fit studies: `nu=0.005`, final time `0.25`, 128-point candidate output grid, smooth four-mode initial conditions. The reference family is the same periodic Cole–Hopf implementation at different internal work-grid sizes. An 8,192-point run is used as a stronger same-method anchor. This is convergence evidence, not methodologically independent reference qualification.

Four actual 400-step compact-FNO reconstructions were also evaluated against each reference configuration. Their anchor ordering was `C1 > C2 > C3 > I`, where `>` means lower mean relative-L2 error.

## Accuracy-cost frontier

For 256 evaluation cases:

| Internal reference grid | Median compute | Mean discrepancy vs 8192 anchor | 95th percentile | Maximum |
|---:|---:|---:|---:|---:|
| 16 | ~2.0 ms | 0.211% | 0.849% | 1.467% |
| 24 | ~2.8 ms | 0.00672% | 0.0381% | 0.113% |
| 32 | ~1.9 ms | 0.000438% | 0.00268% | 0.0109% |
| 48 | ~2.0 ms | 0.00000222% | 0.0000116% | 0.0000998% |
| 64 | ~2.2 ms | 0.0000000129% | 0.0000000564% | 0.000000890% |
| 128 | 1.22 ms in the primary timing run | approximately machine precision | approximately machine precision | approximately machine precision |
| 1024 | 35.1 ms | approximately machine precision | approximately machine precision | approximately machine precision |
| 8192 | 158.5 ms | anchor | anchor | anchor |

The 128-point configuration was about **130x faster** than the 8,192-point anchor in the primary repeated timing run and agreed at roughly machine precision on this smooth population. Increasing internal resolution beyond the candidate/output grid bought no observable answer improvement here.

This does not imply that 128 points is adequate for another Burgers population, lower viscosity, different horizon, another PDE, another observable, or a product claim. It shows why reference convergence and cost should be profiled rather than treating maximum fidelity as the routine operating choice.

## Decision resolution

The mean-error gap between the two best reconstructed candidates under the anchor was about **0.00514 percentage points**.

- Grid 16 reference discrepancy was much larger than that gap.
- Grid 24 mean discrepancy was also larger than that gap, and its tail discrepancy was much larger.
- Grid 32 mean and 95th-percentile discrepancies were smaller than that gap, while its maximum case discrepancy was still larger.
- Grid 48 and above were far below the observed candidate gap on this fixture.

All four actual reconstructed candidates retained the same mean-error ranking under every tested reference configuration, including the coarse ones. That stability is useful but is **not sufficient reference qualification**: one observed candidate set can fail to expose a reference-specific bias.

## Generator/reference-bias adversarial control

For each weak reference, the study constructed two diagnostic fields:

- Candidate A: closer to the 8,192-point anchor, placed one-quarter of the way from the anchor toward the weak reference.
- Candidate B: exactly matches the weak reference.

The strong anchor prefers A. The weak reference necessarily prefers B. This creates an explicit ranking reversal whenever the weak-reference discrepancy is nonzero.

The test is deliberately adversarial. It demonstrates the constitutional point that a self-consistent weak-reference oracle can reward its own bias. It does not mean an arbitrarily tiny floating-point discrepancy is scientifically material. Materiality must be judged against the Challenge's qualified decision resolution, measurement uncertainty and physical requirements.

## Carbon Fit rule

A proposed reference configuration should be evaluated on an **accuracy-cost frontier**, not cost alone:

1. measure recurring cost and failure behavior across relevant strata;
2. establish convergence/verification evidence and a stronger anchor or witness where applicable;
3. compare reference uncertainty/discrepancy with the candidate differences Carbon intends to resolve;
4. run a reference-bias adversarial control where feasible;
5. retain tail and subgroup discrepancies, not only mean agreement;
6. choose a routine reference role only after the registered Dossier determines that remaining error cannot plausibly reverse decisions Carbon intends to make;
7. keep stronger/slower reference roles available as witnesses or qualification anchors when useful.

The operating profiler can then feed the approved routine reference cost into the single-validator allocation model. Upfront convergence/qualification expenditure remains a separate Carbon Fit metric.

## Wave C rerun

After the real C1 reference path and candidate reconstruction path exist, repeat this study with:

- the actual proposed reference configurations and environment identities;
- real case strata and failure regions;
- exact measurements used by the proposed Challenge;
- close real candidate pairs and repeated reconstructions;
- full reference failures/timeouts and censoring;
- methodologically independent witness evidence where the policy requires it;
- real validator resource receipts.

Compare the measured accuracy-cost frontier with this development baseline. Do not copy the fixture's grid sizes or tolerances into production.
