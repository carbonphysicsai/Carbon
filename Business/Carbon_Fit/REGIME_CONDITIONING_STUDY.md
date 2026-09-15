# Regime-conditioned Challenge profiling

**Status:** working research evidence; no LIVE Challenge, scientific threshold, production reference fidelity, runtime, or deployment claim is selected.

## Question

Does one Carbon operating profile remain adequate as the physics becomes harder, or do reference fidelity and validator reconstruction requirements change across the Challenge envelope?

## Development study

A public CPU research fixture keeps the candidate family, optimizer hyperparameters, 256 fresh training trajectories per reconstruction, model I/O grid, and validator execution path fixed. Only the synthetic Burgers regime changes:

| Regime | Viscosity | Horizon | IC modes | Amplitude range | Spectral decay |
|---|---:|---:|---:|---:|---:|
| easy | 0.005 | 0.25 | 4 | 0.1–0.3 | k^-2 |
| moderate | 0.0025 | 0.35 | 6 | 0.15–0.4 | k^-1.75 |
| hard | 0.0015 | 0.50 | 8 | 0.2–0.5 | k^-1.5 |

These are development strata, not a ratified Carbon population or operating envelope.

The reconstruction diagnostic uses the same compact FNO-inspired research model at 100 and 400 optimizer updates. The reference diagnostic compares the same periodic Cole–Hopf implementation across internal grids against a 4096-point anchor. Same implementation lineage means this is convergence evidence, not independent reference qualification.

## Main findings

Physics difficulty increased strongly: mean maximum absolute gradient increased from about 1.05 (easy) to 2.03 (moderate) to 4.43 (hard); p95 increased from about 2.07 to 4.25 to 10.91.

Deeper reconstruction improved field error in all three regimes:

| Regime | 100-step holdout error | 400-step holdout error | Relative reduction | Approx. compute multiplier |
|---|---:|---:|---:|---:|
| easy | 0.538% | 0.350% | 34.9% | 2.73x |
| moderate | 1.069% | 0.517% | 51.7% | 4.05x |
| hard | 3.801% | 2.258% | 40.6% | 4.13x |

The hard 400-step reconstruction still showed a nonzero extrema-violation diagnostic (~0.0128). No production physical gate is inferred from that value.

Reference fidelity was regime-dependent:

- Easy: every tested internal grid down to 32 remained numerically valid; the 32-point p95 discrepancy from the 4096-point anchor was about 0.000784%.
- Moderate: 32 remained valid but p95 discrepancy increased to about 0.246%; 48 reduced that to about 0.0105%; 64 to about 0.000617%.
- Hard: the 32- and 48-point reference configurations failed numerically. The first tested valid grid was 64, with about 0.266% p95 discrepancy; 96 reduced that to about 0.0199%; 128 dropped below about 0.000035%.

A development-only diagnostic requiring reference p95 discrepancy below 1% of the observed 400-step model error would first be met at grid 32 for easy, 64 for moderate, and 96 for hard. That ratio is an analysis aid, not a Carbon qualification threshold.

## Carbon interpretation

This supports a new Challenge Profiler requirement: **condition operational feasibility on regime/stratum rather than assuming one easy-regime profile applies across the whole envelope.**

This must not become candidate-specific exam depth. Regime evidence should inform the prospective Challenge design. Options include stronger common reconstruction/reference resources, a registered stratified SamplingPlan/reference-fidelity allocation, a narrower envelope, or a new Challenge version. Mandatory scientific requirements and evidence use remain prospective and common to eligible candidates under the owning contracts.

Reference failures and censoring stay visible by stratum. A failed low-resolution hard case cannot be silently removed just to keep the exam fast.

## Expensive CFD, experimental, or customer-hosted references

Bounded batching/reuse can make expensive real-solver references economically practical when one prospectively committed reference batch can legitimately serve multiple committed candidates. Reuse lowers recurring reference expenditure; it does not make the source scientifically adequate by itself.

For a real solver reference, Carbon still needs a registered role/envelope, verification or convergence and uncertainty evidence, failure/disagreement policy, exact case/configuration identity, rights/custody, and protection from adaptive answer-bank leakage. Persistent reservoirs require separate reuse and retirement qualification. Customer-hosted solver services can keep proprietary truth infrastructure customer-side while Carbon sends authorized cases and receives controlled reference outputs, subject to the same scientific evidence requirements.

## Challenge Profiler update

Add a **Regime Conditioning** stage:

1. Define scientifically meaningful development strata before inspecting candidate results.
2. Measure reference convergence/failure and candidate reconstruction curves within each stratum.
3. Test whether the proposed common operating profile supports the intended decision resolution across all required strata.
4. If it does not, change the prospective Challenge design rather than weakening evidence for the hard stratum.
5. Preserve generator/reference/infrastructure censoring by stratum.
6. Re-run on the real Wave C path and compare predicted versus observed limiting strata and operating cost.

## Limits

This is one candidate recipe and one fresh block per regime. It does not identify a stable reconstruction optimum, ratify Burgers strata, qualify Cole–Hopf as production authority, select a validator requirement, or establish a production runtime. The next useful experiment is a stratum-allocation study under a fixed validator-compute envelope, with target population, proposal sampling, and evidence weighting kept explicit and prospective.
