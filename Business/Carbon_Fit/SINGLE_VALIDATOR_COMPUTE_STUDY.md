# Single-validator compute and replication study

**Status:** development research evidence and Engineering handoff. No LIVE exam, validator requirement, reconstruction count, hardware profile, or production capacity is selected.

## Owner direction

Treat one validator as the planning execution authority. Do not optimize or assume validator count. The controllable variable is the compute profile Carbon requires from that validator for each submitted strategy. Additional validators may later increase aggregate capacity, but the Challenge should remain analyzable under the one-validator profile.

The profile should eventually bind hardware class/count, active compute entitlement, memory/storage/network ceilings, permitted concurrency, cold/warm compilation and worker-lifetime policy, required lean reconstruction count, and separate frontier-promotion evidence where applicable. Reuse existing resource-policy owners rather than inventing another runtime authority.

## Research question

How should Carbon trade construction depth against repeated independent reconstruction of the same submitted strategy when one validator supplies all compute?

The development study reuses the public CPU Burgers/JAX fixture from the operating-point pilot. It is not Carbon's canonical runtime and does not use a qualified Challenge. Two strong compact-FNO strategy configurations were reconstructed independently eight times at 100 and 400 training steps. A fixed 256-case screening set and separate fixed 256-case holdout were used.

The first standalone execution attempt failed before candidate work because the fixture protocol file had not been copied into the bundle. That setup failure is retained in the research log. Process restarts also exposed substantial JAX cold-compilation overhead relative to these short CPU rebuilds. Production profiling therefore must account for worker lifetime and compilation/cache policy rather than treating printed training time as complete validator cost.

## Measured reconstruction behavior

| Training depth | Strategy | Mean holdout relative-L2 | Reconstruction SD | Median measured rebuild time |
|---|---|---:|---:|---:|
| 100 | A | 0.799% | 0.138% | 0.777 s |
| 100 | B | 0.554% | 0.064% | 0.759 s |
| 400 | A | 0.244% | 0.018% | 3.233 s |
| 400 | B | 0.227% | 0.086% | 3.060 s |

Strategy B had the lower mean holdout error at both depths. The 400-step pair is much closer while Strategy B also shows materially more reconstruction variation.

## What fixed replication bought

The diagnostic below compares the two strategies using the mean screening error across `r` independent reconstructions of each. It reports how often combinations from the finite eight-run empirical set disagree with the ordering implied by the eight-reconstruction mean holdout error. This is not a production false-selection probability.

| Training steps | Reconstructions per strategy | Diagnostic disagreement | Median measured compute per strategy |
|---:|---:|---:|---:|
| 100 | 1 | 1.6% | 0.769 s |
| 100 | 2 | 0.0% | 1.537 s |
| 100 | 3 | 0.0% | 2.306 s |
| 400 | 1 | 18.8% | 3.077 s |
| 400 | 2 | 25.9% | 6.155 s |
| 400 | 3 | 36.7% | 9.232 s |

For the clearly separated 100-step pair, one reconstruction was usually sufficient in this finite diagnostic, and two or three removed the observed disagreement. For the close 400-step pair, one reconstruction was noisy and two or three did not show monotonic improvement in the small empirical sample. The result is a warning against setting a universal reconstruction count from one Challenge. More replication can average random reconstruction noise; it cannot repair inadequate decision resolution, systematic evaluation mismatch, or very small separation between contenders.

A same-index diagnostic found screening and holdout ordering agreed for all eight 100-step reconstruction pairs. At 400 steps, two of eight holdout pairs favored Strategy A and one of eight pairs had a screening-versus-holdout ordering mismatch.

## Capacity semantics

Use validator compute, not validator count, as the planning denominator:

```text
complete candidate exams/day
<=
available validator compute/day
/
validator compute consumed per complete candidate exam
```

Apply separate capacity bounds for reference work, queues, candidate supply, retries and mandatory evidence. Hardware identity and concurrency must accompany any compute quantity. Warm CPU fixture seconds cannot be converted to production GPU capacity by a multiplier.

A single submitted strategy reconstructed three times consumes about three times the measured reconstruction work before other exam stages. Those replicas strengthen evidence about one strategy; they are not three distinct research proposals.

## Architecture implication

Do not infer that every lean exam should run three reconstructions. A useful future design to qualify is:

1. keep the mandatory lean reconstruction policy prospective and identical for every eligible candidate within the Challenge;
2. use lean evidence for screening/ranking;
3. when a contender is separately nominated for frontier promotion, compare contender and incumbent using the same registered fresh promotion evidence and the reconstruction replication required by the `LeaderReplacementPolicy`.

This preserves the prohibition on candidate-specific hidden official depth while allowing a separate promotion decision to purchase stronger common evidence. Exact reconstruction counts remain human/scientific inputs that require qualification.

## Next experiments

1. Repeat on the real Wave-C execution path with one validator and explicit target hardware.
2. Vary the validator compute profile through hardware/concurrency and active compute entitlement, not validator count; measure cold/warm compilation, active device time, memory, full wall time and typed failures.
3. Expand construction depth around the current operating region and include deliberately close and clearly separated strategy pairs.
4. Preregister a replication-resolution study using a decision-relevant superiority margin and observed reconstruction/evaluation variance.
5. Compare fixed lean reconstruction with a separate common fresh frontier-promotion experiment.
6. Refit the Challenge operating point using supported progress per validator-compute-day and time-to-supported-frontier-advance, while keeping one-time exam qualification cost and risk separate.

## Claim boundary

This study provides development evidence that reconstruction depth and reconstruction variance interact with decision reliability. It does not select one, two or three reconstructions for Carbon, establish GPU scaling, qualify Burgers, or authorize adaptive official evaluation.
