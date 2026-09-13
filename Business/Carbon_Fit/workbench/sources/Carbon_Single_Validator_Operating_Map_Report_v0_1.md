# Carbon single-validator operating-map study v0.1

**Status:** development research only. No production runtime, LIVE Challenge, physical qualification, validator requirement, frontier policy, training-data budget, or reconstruction count is selected.

## Plain-language result

This study treats one validator as fixed. It varies two things Carbon could require from that validator:

1. **construction depth**: how many optimizer updates each reconstruction receives; and
2. **promotion resolution**: how many fresh reconstructions of the incumbent and nominated challenger are used in the separate promotion comparison.

The main study holds fresh training data at **256 generated training trajectories per reconstruction**. “Training longer” therefore means more optimizer updates over batches drawn from the same 256-case training set. It does **not** mean that Carbon generated a larger training dataset. A separate sensitivity experiment varies training-data count while holding optimizer steps fixed.

With a fixed 400-step incumbent, the best-tested trade-off in this small fixture sits around **400 construction steps with one promotion reconstruction per strategy**. The 800-step profile produced a slightly lower independently audited error, but it used much more validator compute for a small incremental gain. Additional promotion reconstructions did not change any of the nine tested promotion decisions, so they only increased cost in this particular study.

This is a knee in one research fixture, not a production optimum.

## Main operating map

The search side evaluated three fixed challenger recipes. One lean reconstruction per challenger selected a nominee on common screening cases. Promotion then compared that nominee with a **fixed 400-step incumbent** on one, two, or three fresh reconstructions per strategy. Promotion cases were common across the pair. A separate outer audit set never selected the nominee or promotion result.

A three-reconstruction audit pool defines the finite diagnostic comparison target. Agreement with that pool is not a production false-promotion guarantee.

| Challenger construction | Promotion reconstructions per strategy | Mean validator compute / cycle | Mean audited selected error | Promotions across 3 blocks | Agreement with 3-rebuild audit |
|---|---:|---:|---:|---:|---:|
| 100 steps | 1 | 6.38 s | 0.2566% | 0/3 | 100% |
| 100 steps | 2 | 9.87 s | 0.2566% | 0/3 | 100% |
| 100 steps | 3 | 13.75 s | 0.2566% | 0/3 | 100% |
| 400 steps | 1 | 15.23 s | 0.2454% | 1/3 | 100% |
| 400 steps | 2 | 21.31 s | 0.2454% | 1/3 | 100% |
| 400 steps | 3 | 27.60 s | 0.2454% | 1/3 | 100% |
| 800 steps | 1 | 28.19 s | 0.2434% | 1/3 | 100% |
| 800 steps | 2 | 36.74 s | 0.2434% | 1/3 | 100% |
| 800 steps | 3 | 45.60 s | 0.2434% | 1/3 | 100% |


### The construction knee

Using one promotion reconstruction per strategy:

- **100 steps:** 6.38 s mean validator compute per cycle; 0.2566% mean audited selected error. The challengers never displaced the fixed incumbent in the three blocks.
- **400 steps:** 15.23 s; 0.2454%. One challenger displaced the incumbent in one of three blocks.
- **800 steps:** 28.19 s; 0.2434%. One challenger displaced the incumbent in one of three blocks.

Going from 400 to 800 steps increased measured validator compute by **85.1%** while lowering the mean selected error by only **0.79% relative** in this fixed-incumbent comparison. That makes 400 steps the stronger current knee if Carbon values throughput as well as the final error. This conclusion could move with a different physical regime, candidate pool, hardware, incumbent, or evidence policy.

### Promotion replication

Within every construction-depth row, increasing promotion reconstruction from one to two or three did not change the selected strategy or the audited result in any of the three fresh blocks. For example, the 400-step profile increased from 15.23 s at one rebuild to 27.60 s at three rebuilds with the same mean selected error.

This does **not** justify a universal one-rebuild promotion policy. The prior replication study found a close pair where one-rebuild decisions were unstable. Together, the studies support a sharper hypothesis: promotion effort should be qualified against the decision resolution required for the registered comparison, rather than hard-coded as “always three.” Any sequential or margin-triggered policy would need a prospective symmetric rule and scientific qualification before official use.

## Training longer versus generating more training data

The main map fixed training data at 256 fresh trajectories per reconstruction. A separate 400-step sensitivity used the same strategy and varied only the number of freshly generated training trajectories:

| Fresh training trajectories | Mean outer error | SD across 3 blocks | Mean live compute | Mean training-reference generation |
|---:|---:|---:|---:|---:|
| 64 | 0.2763% | 0.0617% | 2.794 s | 0.0035 s |
| 256 | 0.3969% | 0.1051% | 2.657 s | 0.0102 s |
| 1024 | 0.3728% | 0.1834% | 2.848 s | 0.1688 s |


The small study showed **no monotonic improvement from adding more generated training cases** at fixed optimizer steps. Sixty-four cases happened to have the lowest mean error in these three blocks. That is not evidence that 64 is optimal. With fixed optimizer steps, a smaller dataset receives more repeated exposure, while a larger dataset increases information diversity but each example receives less reuse. The correct data-volume policy needs its own curve.

Reference-label generation rose sharply with data volume in relative terms, but the absolute cost stayed small in this analytic Burgers fixture. An industrial reference could reverse that economics. Carbon Fit should therefore keep **training-data generation budget** separate from **optimizer/training compute**.

## What this adds to the Challenge Profiler

The proposed profiler now needs at least four separable operating axes:

- training-data generation allowance;
- construction compute per reconstruction;
- lean reconstruction/evaluation policy;
- separate frontier-promotion resolution policy.

For one validator, Carbon can measure a cost/error/Pareto surface instead of selecting an exam count by intuition. The operating output should report a supported region, throughput per declared validator-compute budget, decision uncertainty, and the limiting factor. One-time exam qualification cost and risk remain a separate record.

## Experimental regime and limitations

The study reuses the public smooth periodic viscous Burgers/JAX research fixture. It is an easy development regime, not a qualified Carbon Challenge. One CPU process used two logical CPUs, JAX 0.9.0.1, a compact FNO-inspired implementation, and development-selected strategy configurations from earlier research evidence. Three fresh blocks supplied screening, promotion, and outer audit cases.

JAX kernels compiled once before measured reconstruction work. Every reconstruction created fresh model weights, optimizer state, and training cases. The measured policy compute includes training-reference generation, state/batch preparation, training, and screen or promotion prediction/diagnostics. Outer audit prediction and initial kernel compilation remain outside the policy compute. These boundaries do not match a production Carbon exam.

The first launch stopped before candidate execution because the standalone reference helper expected `protocol.json` at import. A second attempt exposed a metric-key mismatch before a completed candidate record. A third restart exposed an incomplete bootstrap protocol on import. Those setup failures remain in the execution history. The final run completed all planned numerical work in {json.load(open(root/'environment.json'))['total_process_wall_s']:.2f} s process wall time.

The nine main profile cells are supported by only three fresh blocks. The finite three-rebuild audit is not scientific truth. No mandatory physical gate was selected. No GPU scaling, candidate-supply model, queue behavior, Carbon orchestration, signature/receipt path, protected-reference security, or client value was tested.

## Wave C rerun

After Wave C supplies the real execution path, rerun the same logical study with:

1. one validator and an explicitly named hardware/compute profile;
2. fixed training-data budget and a separate data-volume sweep;
3. measured construction depth profiles;
4. one or more prospectively specified promotion-resolution policies;
5. common fresh evidence for incumbent/challenger comparisons;
6. independent holdout/audit evidence that does not select the operating profile; and
7. full orchestration, isolation, reference, measurement, receipt, retry and failure costs included in the declared clock.

Compare predicted versus measured compute, throughput, promotion stability, error, failures and censoring. Changed hardware or physical regimes must remain visible rather than folded into an apparent software speedup.
