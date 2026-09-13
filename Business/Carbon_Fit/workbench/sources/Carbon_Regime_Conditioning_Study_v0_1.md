# Carbon Regime-Conditioning Study v0.1

**Status:** public development research only; not Challenge qualification, production runtime evidence, or scientific threshold selection.

## Question

Does one Carbon operating profile remain adequate as the physics becomes harder, or do reference fidelity and validator reconstruction requirements change across the Challenge envelope?

## Controlled setup

The study keeps the candidate family, optimizer hyperparameters, 256 fresh training trajectories per reconstruction, model I/O grid, and validator execution path fixed. Only the physical regime changes.

| Regime | Viscosity | Horizon | IC modes | Amplitude range | Spectral decay |
|---|---:|---:|---:|---:|---:|
| easy | 0.005 | 0.25 | 4 | 0.1–0.3 | k^-2 |
| moderate | 0.0025 | 0.35 | 6 | 0.15–0.4 | k^-1.75 |
| hard | 0.0015 | 0.50 | 8 | 0.2–0.5 | k^-1.5 |

These regimes are synthetic development strata, not a ratified Carbon population or operating envelope.

Candidate diagnostic: compact FNO-inspired research model, lr 0.008, weight decay 1e-4, batch 32, float32, one fresh block per regime. Reconstruction depth is 100 versus 400 optimizer updates. Reference diagnostic: periodic Cole–Hopf implementation compared with a 4096-point anchor over a grid sweep. Same implementation lineage means this is convergence evidence, not an independent reference qualification.

## Results

### Physics difficulty increased

| Regime | Mean max |grad u| | p95 max |grad u| |
|---|---:|---:|
| easy | 1.05 | 2.07 |
| moderate | 2.03 | 4.25 |
| hard | 4.43 | 10.91 |

### More reconstruction compute helped every regime, but did not erase regime difficulty

| Regime | 100-step error | 400-step error | Error reduction | Compute multiplier |
|---|---:|---:|---:|---:|
| easy | 0.538% | 0.350% | 34.9% | 2.73x |
| moderate | 1.069% | 0.517% | 51.7% | 4.05x |
| hard | 3.801% | 2.258% | 40.6% | 4.13x |

The hard 400-step reconstruction still showed a maximum extrema violation of about 0.0128 in this development metric; easy and moderate runs did not. No production physical gate was selected.

### Reference fidelity became regime-dependent

- Easy: every tested grid down to 32 remained numerically valid. The 32-point p95 discrepancy from the 4096-point anchor was about 0.000784%.
- Moderate: 32 points remained valid but p95 discrepancy increased to about 0.246%; 48 points reduced that to about 0.0105%; 64 points to about 0.000617%.
- Hard: the 32- and 48-point reference configurations failed numerically. The first tested valid grid was 64, with about 0.266% p95 discrepancy. At 96 points the p95 discrepancy was about 0.0199%; at 128 points it dropped below 0.000035%.

A diagnostic criterion of reference p95 discrepancy below 1% of the observed 400-step model error would first be met at grid 32 for easy, 64 for moderate, and 96 for hard. That 1% ratio is an analysis aid only. It is not a Carbon qualification threshold.

## Interpretation

This study supports three Carbon hypotheses:

1. **One Challenge can contain strata with different operational burdens.** The hard stratum required stronger reference resolution and remained substantially harder for the candidate at the same reconstruction budget.
2. **Hard-regime reference failures must remain visible.** Dropping the failed low-resolution hard cases would make the realized evidence population easier than the intended one.
3. **The profiler should condition operating recommendations on regime/stratum.** It should not automatically run different official evidence for different candidates. Instead, regime evidence informs the prospective Challenge design: common mandatory profile, stratified evidence allocation, stronger reference policy, or a narrower envelope/version.

This does not authorize candidate-specific reference fidelity, different gates, or dynamic exam depth after observing a submission.

## Expensive CFD / real-solver references

Bounded batching/reuse can make expensive CFD, experimental, or customer-hosted solver references economically practical when the same prospectively committed reference evidence can legitimately serve multiple committed candidates. It changes recurring reference cost; it does not make the source scientifically adequate by itself.

For a real solver reference, Carbon still needs a registered role and envelope, convergence/verification and uncertainty evidence, failure policy, exact case/configuration identity, rights/custody, and protection from adaptive answer-bank leakage. Persistent reservoirs require a separate reuse/retirement qualification. A customer-hosted solver service can keep proprietary truth infrastructure customer-side while Carbon receives controlled reference outputs, subject to those same scientific requirements.

## Challenge Profiler update

Add a **Regime Conditioning** stage after the initial reference and reconstruction sweeps:

1. Define scientifically meaningful development strata before looking at candidate results.
2. Measure reference convergence/failure and candidate reconstruction curves within each stratum.
3. Check whether the proposed common profile can support the intended decision resolution across all required strata.
4. If not, choose prospectively among stronger common resources, registered stratified sampling/reference allocation, narrower envelope, or a new Challenge version.
5. Preserve reference/generator/infrastructure censoring by stratum.
6. Re-run on the real Wave C path and compare the predicted versus observed limiting stratum and cost.

## Limitations

- One candidate recipe and one fresh block per regime; no claim of a stable construction optimum.
- Synthetic regime ladder; no claim that these are the right Burgers strata for a LIVE Challenge.
- Same Cole–Hopf implementation lineage across resolutions; no independent reference authority.
- CPU research fixture; no production validator/hardware inference.
- No fresh proposal-breadth campaign by regime yet. That should follow only if the regime-conditioned reconstruction curves show enough value to justify the cost.

## Next experiment

Use the regime-conditioned data to design a **stratum allocation study**: under one fixed validator-compute envelope, vary how finite evidence is allocated across easy/moderate/hard strata while preserving a prospectively declared target estimand. Compare uniform sampling with registered oversampling/importance-weighting proposals. This addresses whether hard-regime coverage, rather than model training, becomes the next throughput/decision-resolution bottleneck.
