# Fixed-validator compute allocator

**Status:** development research synthesis only. No LIVE runtime, reconstruction count, reference policy, promotion policy, or scientific threshold is selected.

## Purpose

For one validator with a fixed compute envelope, estimate how to divide recurring compute between:

- proposal breadth: how many submitted strategies can be reconstructed and screened;
- reconstruction effort: how much training/rebuild compute each strategy receives; and
- promotion reserve: compute held back for a later incumbent-versus-challenger comparison.

This is an operating-resource analysis. One-time exam qualification cost, integration burden, solver verification, rights/security work, and activation risk remain separate Carbon Fit records.

## Evidence inputs

This v0.1 synthesis combines two already executed evidence sets rather than claiming a new monolithic experiment:

1. Operating-point v0.2 confirmation campaigns measured proposal throughput and independently held-out selected-model error at 100, 400, and 1600 optimizer steps under 4, 8, and 12 second search horizons.
2. Fresh rebuilds from the same confirmation program measured the compute cost of reconstructing a selected strategy. Median fresh rebuild time is used only to reserve compute for an incumbent/challenger comparison.

The separate single-validator replication and operating-map studies remain the evidence about close-decision instability. A reserved rebuild count is not evidence that the promotion decision is scientifically resolved.

## Development result

The best-tested allocation changed with the validator compute envelope.

At an approximately 12 second total envelope:

- 100-step reconstruction with one promotion-pair reserve supported the measured 8 second search horizon;
- about 14 to 15 candidates completed in the confirmation traces;
- mean selected holdout error was 0.460%;
- 400-step reconstruction could only support the 4 second search horizon and about 1 to 2 candidates, with 1.105% mean selected error.

At an approximately 24 second total envelope:

- 400-step reconstruction with one promotion-pair reserve supported the measured 12 second search horizon;
- about 5 candidates completed;
- mean selected holdout error was 0.258%;
- 100-step reconstruction supported about 22 candidates but selected models averaged 0.454% error;
- 1600-step reconstruction generally completed only one candidate and averaged 0.917% error.

The transferable conclusion is not the fixture seconds. It is the policy shift: a tight validator budget favored breadth, while a larger budget favored fewer, better-reconstructed candidates.

## Promotion reserve

Median fresh rebuild times in the confirmation evidence were approximately:

- 100-step strategy: 0.598 s;
- 400-step strategy: 2.326 s;
- 1600-step strategy: 7.267 s.

The development allocator assumes a 400-step incumbent for reserve accounting. One promotion reserve therefore allocates one fresh incumbent rebuild plus one fresh challenger rebuild. Two reserves double that amount.

This does not ratify one or two rebuilds as a promotion rule. The earlier close-pair replication study showed that a single rebuild can be unstable when strategies are close. Future official use needs a prospectively registered symmetric resolution and indeterminate policy.

## Proposed allocator behavior

A Challenge profiler should consume measured, Challenge-specific evidence for:

- validator hardware and active-compute allowance;
- training-data generation cost;
- reconstruction learning curves;
- miner/agent proposal supply and diversity;
- lean mandatory-exam cost;
- recurring reference work;
- promotion-resolution cost; and
- service and feedback constraints.

For each measured profile it should report:

- complete unique candidates per validator-compute period;
- independently checked selected quality;
- compute reserved for frontier resolution;
- unused or stranded capacity;
- current limiting factor; and
- the next experiment that could move the operating recommendation.

Do not extrapolate beyond measured horizons. If a requested compute envelope exceeds available evidence, return `UNKNOWN / MORE PROFILING NEEDED` rather than assuming the same performance curve continues.

## Reference cost

Recurring reference cost enters the operating envelope separately from one-time exam qualification cost. A cheap Burgers reference barely changes these development allocations. An industrial CFD, experiment, or third-party truth service may dominate the result and must be measured for the proposed Challenge.

## Wave C rerun

After Wave C provides the real execution path, rerun the same allocator with actual:

- validator hardware and concurrency;
- fresh construction data;
- reconstruction and inference;
- protected references and measurements;
- orchestration and isolation;
- receipts, retries, failures and censoring; and
- real proposal arrival and duplication.

Compare the pre-Wave-C prediction with measured Carbon behavior. Preserve changes in hardware, physics, candidate catalog, timing boundary, and evidence policy instead of folding them into an apparent speedup.

## Non-claims

This development synthesis does not establish an optimal number of exams per day, a production reconstruction budget, an allowed training-data count, a sufficient promotion repetition count, or a qualified physical model. Its purpose is to turn those questions into measurable resource-allocation experiments.