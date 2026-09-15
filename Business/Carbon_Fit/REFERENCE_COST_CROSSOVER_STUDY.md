# Carbon reference-cost crossover study v0.1

**Date:** 11 September 2026

**Status:** development analysis. No cache/reuse policy, production runtime, scientific/security qualification, sample count, or cohort size is selected.

## Question

When does reference computation become expensive enough that Carbon should change how one validator allocates compute, including sharing one protected reference batch across a committed cohort?

This study keeps upfront exam-qualification expenditure separate. It studies recurring live-operation compute after an exam exists.

## Inputs

This is a cross-study replay using previously measured public-fixture evidence rather than new model training:

- confirmation proposal-breadth curves for 100- and 400-step reconstructions;
- measured fresh-rebuild median time of **0.598 s** for the 100-step profile and **2.326 s** for the 400-step profile;
- prior measured median of **14.46 ms** to compute the 384-case screening/holdout reference batch in the easy Burgers fixture;
- one-validator **12 s active-compute envelope** for the trace-supported replay.

The measured fixture reference/reconstruction ratios are therefore about **2.4%** for the 100-step profile and **0.62%** for the 400-step profile. This is why reference caching did not materially improve the earlier easy-Burgers throughput result.

## General crossover rule

If one reference batch costs `R`, one candidate reconstruction costs `C`, and the exact same qualified reference batch may legitimately serve a committed cohort of `B` candidates, the idealized per-candidate active-compute saving relative to recomputing the reference per candidate is:

`R * (1 - 1/B) / (C + R)`.

This is a compute identity, not a reuse authorization. It omits cohort-fill delay, storage/security work, cache creation, adaptive feedback, qualification and incident risk.

Useful thresholds:

| Committed cohort | Reference cost / reconstruction cost needed for 10% saving | for 25% saving | for 50% saving |
|---:|---:|---:|---:|
| 2 | 0.25x | 1.00x | impossible; pair sharing caps at 50% asymptotically |
| 4 | 0.154x | 0.50x | 2.00x |
| 8 | **0.129x** | **0.40x** | **1.33x** |
| 16 | 0.119x | 0.364x | 1.14x |

For the measured 400-step reconstruction cost, an eight-candidate committed cohort would require a reference batch around **0.30 s** before the idealized active-compute saving reaches 10%, about **0.93 s** for 25%, and about **3.10 s** for 50%. The measured fixture reference batch was 0.01446 s, far below those values.

## Fixed-budget trace replay

The replay sweeps a hypothetical common reference-batch cost while retaining only measured proposal-breadth points. It does not interpolate model quality or extrapolate past measured search breadth.

At the measured **14.46 ms** reference cost, the best trace-supported 12 s profile remains five 400-step candidates without reference sharing, with mean selected holdout error of **0.276%**.

For the 400-step profile:

| Common reference batch cost | No-sharing capacity / observed error | Best trace-supported sharing result | Illustrative fill wait at 100 proposals/day |
|---:|---|---|---:|
| 0.014 s measured | 5 candidates / 0.276% | no sharing needed | 0 h |
| 0.25 s | 4 candidates / 0.290% | 5 candidates with cohort 8 / 0.276% | 0.84 h |
| 1.0 s | 3 candidates / 0.360% | 4 candidates with cohort 2 / 0.290% | 0.12 h |
| 2.0 s | 2 candidates / 0.393% | 4 candidates with cohort 4 / 0.290% | 0.36 h |
| 5.0 s | 1 candidate / 1.404% | 3 candidates with cohort 4 / 0.360% | 0.36 h |

The fill waits use **100 proposals/day only as a sensitivity example**. They are not a Carbon arrival-rate assumption.

Within this narrow 12 s trace replay, the preferred measured search depth remains 400 steps until the hypothetical common reference-batch cost becomes several times the 400-step reconstruction cost. Around **7.35 s** in the discrete replay, the best trace-supported allocation switches to the shallower 100-step profile because the reference has consumed enough of the budget that breadth becomes more valuable. That crossover is specific to this measured candidate pool and 12 s envelope; it is not a universal Carbon threshold.

## Decision rule for Carbon Fit

Classify the recurring reference burden by the ratio `reference compute / candidate reconstruction compute`, while separately recording accuracy, applicability and qualification status:

- **Reference-light:** reuse is unlikely to change throughput materially; focus on reconstruction/search/evaluation overhead.
- **Reference-material:** reuse can change how many useful candidates fit in the validator budget; test bounded committed cohorts and feedback delay.
- **Reference-dominant:** reference work can determine the search-depth optimum; compare shared cohorts, protected reservoirs where separately qualified, cheaper qualified reference roles, and the direct reference method as a deployable baseline.

Do not assign universal numeric class boundaries from this fixture. Use the analytic saving curves and Challenge-specific resource/value requirements to select what counts as material.

## What to measure on a proposed Challenge

1. Fresh reference compute per complete protected pack, including failures and difficult strata.
2. Validator reconstruction compute for each candidate profile.
3. Candidate inference/measurement/receipt compute.
4. Exact permitted reuse scope and committed-cohort semantics.
5. Proposal arrival and diversity, because batching can add feedback delay.
6. Reference uncertainty and whether a faster direct/reference method is already a sufficient client solution.
7. Search breadth curve under fixed validator compute, so saved reference work can be translated into actual discovery value rather than raw capacity alone.

## Next experiment

The next high-value study is **reference accuracy-cost frontier mapping**. For a real proposed Challenge, run multiple legitimate reference configurations/fidelities and measure:

- wall/active compute;
- convergence/uncertainty and failure regions;
- whether reference uncertainty can reverse candidate ordering;
- cost per fresh protected pack;
- direct-method deployment latency/cost;
- effect of any qualified accelerated reference on the operating map.

This is the bridge between 'reference is expensive' and 'which reference configuration is adequate and economically sensible.' It must be Challenge-specific and cannot invent solver tolerances or production adequacy thresholds.
