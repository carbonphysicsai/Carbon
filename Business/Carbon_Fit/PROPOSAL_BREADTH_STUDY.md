# Proposal-breadth study

**Status:** development research only. No miner-supply assumption, production catalog, exam cadence, or scientific threshold is selected.

## Question

Holding per-candidate reconstruction depth fixed, how much value did Carbon's research fixture obtain from evaluating additional distinct candidate strategies before choosing one?

This is different from reconstruction effort. A larger proposal count means Carbon evaluates more submitted strategies; it does not give any one strategy more optimizer updates or more training data.

## Evidence source

The study reuses the operating-point v0.2 confirmation traces. Those traces contain completed candidates from a 32-configuration research catalog spanning compact FNO-inspired and periodic CNN implementations. For each confirmation block and reconstruction depth, candidates are ordered by measured completion time. For a prefix of the first `k` completed candidates, the strategy with the lowest common-screen error is selected and its independently held-out outer error is reported.

The outer holdout never chooses the strategy. Four confirmation blocks support each displayed point. Candidate order, family mix, and catalog contents are fixed development evidence rather than a model of future miner supply.

## Result

At 100 optimizer steps per candidate, mean held-out error of the selected strategy changed as proposal breadth increased:

| Completed candidate strategies available | Mean selected holdout error |
|---:|---:|
| 1 | 5.311% |
| 2 | 1.616% |
| 4 | 0.739% |
| 5 | 0.655% |
| 8 | 0.492% |
| 12 | 0.460% |
| 16 | 0.460% |
| 20 | 0.454% |

The largest gains occurred in the first several additional proposals. Improvement flattened materially around 8 to 12 completed candidates in this trace.

At 400 optimizer steps per candidate:

| Completed candidate strategies available | Mean selected holdout error |
|---:|---:|
| 1 | 1.404% |
| 2 | 0.393% |
| 3 | 0.360% |
| 4 | 0.290% |
| 5 | 0.276% |

The measured 400-step trace still improved through five proposals, so this study does not locate its proposal-breadth knee. Longer confirmation campaigns would be required.

## Interpretation

The result supports a separate Challenge Profiler axis for **proposal breadth**:

- very few submitted strategies can leave substantial discovery value on the table;
- additional proposals can show diminishing returns once the currently useful region of a fixed catalog has been sampled; and
- the breadth knee depends on reconstruction depth, proposal quality, candidate diversity, physical regime and search guidance.

The first candidate in these research traces was often a CNN configuration and was usually displaced by an FNO configuration after more candidates completed. That observation is catalog-specific and must not be generalized into family authority.

## Relationship to the fixed-validator allocator

The fixed-validator compute allocator combines three separable questions:

1. proposal breadth: how many distinct submitted strategies can the validator examine;
2. reconstruction effort: how much compute each strategy receives; and
3. promotion reserve: how much compute is held back for a separate incumbent-versus-challenger decision.

A tight validator envelope may favor shallower reconstruction because it buys more proposals. A larger envelope can move the best-tested allocation toward deeper reconstruction. The correct operating profile is therefore an empirical resource-allocation question, not a universal exam-count target.

## Wave C rerun

Repeat the breadth curve after Wave C with actual submitted-strategy arrivals and the real reconstruction path. Preserve duplicates and near-duplicates rather than counting them as independent ideas. Report proposal source, family/catalog coverage, completion/failure state, screen evidence, independent holdout evidence and validator compute.

The eventual Carbon Fit output should distinguish capacity for candidate evaluations from actual useful proposal supply.