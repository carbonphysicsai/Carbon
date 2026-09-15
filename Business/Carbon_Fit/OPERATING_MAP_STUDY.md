# Carbon single-validator operating map

**Status:** working development research; not LIVE authority, production runtime, scientific qualification, validator requirement, frontier policy, or selected reconstruction count.

## Question

With one validator treated as fixed, how should Carbon allocate that validator's compute between:

1. construction effort per candidate reconstruction; and
2. extra fresh reconstruction effort used for the separate frontier-promotion decision?

The study keeps the main training-data budget fixed at 256 freshly generated trajectories per reconstruction. In this study, “train longer” means more optimizer updates over batches sampled from those same 256 trajectories. It does not mean generating a larger training dataset.

A separate sensitivity varies training-data count at fixed optimizer steps.

## Development experiment

The public CPU Burgers/JAX fixture from the earlier Carbon Fit studies was used. The physical problem remains smooth periodic viscous Burgers with the same development-only reference and model implementation. No mandatory physical threshold was selected.

The main map used three fresh blocks. Each block had:

- one fixed incumbent recipe reconstructed at 400 optimizer steps for the promotion comparison;
- three fixed challenger recipes;
- challenger construction depths of 100, 400, and 800 optimizer steps;
- one lean reconstruction per challenger to nominate the lowest common-screen-error challenger;
- one, two, or three fresh reconstructions per strategy for the subsequent incumbent-versus-nominee promotion comparison on common promotion cases; and
- a separate outer audit set that did not choose the nominee or promotion result.

All JAX kernels compiled once before measured reconstruction work. Each reconstruction still used fresh weights, optimizer state, and training trajectories. Measured policy compute includes fresh training-reference generation, state/batch preparation, training, and the applicable screening or promotion prediction/diagnostics. It excludes initial compilation and outer-audit prediction.

The first standalone launches exposed packaging/metrics issues before useful candidate execution; those setup failures are retained in the research bundle. The completed numerical run used the unchanged scientific plan.

## Fixed-incumbent operating map

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

### Current development interpretation

The 400-step / one-promotion-reconstruction profile is the strongest current **knee**, not a production optimum.

Moving from 400 to 800 challenger steps increased measured validator compute by about 85% while lowering mean selected error by only about 0.79% relative in this fixed-incumbent comparison. The deeper profile produced the numerically lowest mean error, but the incremental gain was small relative to its added validator work.

Increasing promotion reconstructions from one to two or three did not change any selected strategy in the nine tested profile cells. It therefore added cost without changing this study's outcomes. This does not justify a universal one-rebuild promotion rule. The earlier replication study found a close pair where one-rebuild decisions were unstable. Together the studies support qualifying promotion effort against the required decision resolution rather than hard-coding “always three.”

A future sequential or margin-triggered promotion procedure would need a prospective symmetric rule, an uncertainty model, and scientific qualification before official use.

## Training-data generation is a separate lever

At 400 optimizer steps, one fixed strategy was reconstructed on three fresh blocks while varying only the number of freshly generated training trajectories:

| Fresh training trajectories | Mean outer error | SD across 3 blocks | Mean live compute | Mean training-reference generation |
|---:|---:|---:|---:|---:|
| 64 | 0.2763% | 0.0617% | 2.794 s | 0.0035 s |
| 256 | 0.3969% | 0.1051% | 2.657 s | 0.0102 s |
| 1024 | 0.3728% | 0.1834% | 2.848 s | 0.1688 s |

The result is not monotonic and does not establish an optimal training-data count. At fixed optimizer steps, smaller datasets receive more repeated exposure while larger datasets offer more distinct examples. The reference-label cost also scales separately from optimizer compute. Carbon Fit should therefore track training-data generation and optimizer/training effort as different resource axes.

## What this adds to the Challenge Profiler

For a proposed Challenge, record and test at least:

- training-data generation allowance;
- construction compute per reconstruction;
- lean reconstruction/evaluation policy;
- separate frontier-promotion resolution policy;
- reference compute and reuse policy;
- validator hardware/compute profile;
- independent decision-resolution evidence; and
- resulting throughput and latency under that profile.

The output should be a supported operating region or Pareto set, not a universal scalar score. One-time Challenge qualification cost/risk remains a separate Carbon Fit record.

## Wave C rerun

After Wave C supplies the real execution path, rerun the same logical study with one named validator hardware profile and include full orchestration, isolation, reference, measurement, receipt, retry, failure, and queue costs in the declared clock. Keep a separate training-data-volume sweep. Use common fresh promotion evidence and an independent holdout that does not select the operating profile.

Compare predicted versus measured validator compute, throughput, promotion stability, physical outcomes, reference/reconstruction failures, and censoring. Changed hardware or changed physical regimes remain explicit context rather than an apparent software speedup.

## Claim boundary

This study used one easy public physical regime, a small fixed strategy set, three fresh blocks, a CPU worker, and a finite three-reconstruction audit. It does not qualify Burgers, select production sample/reconstruction counts, establish GPU scaling, prove a false-promotion probability, or authorize an adaptive official exam.