# Carbon Challenge Profiler framework v0.1

**Status:** development decision framework. It does not select production thresholds, solver tolerances, Challenge populations, security acceptance, LIVE activation, or validator requirements.

## Purpose

Given a proposed physical-modeling Challenge, determine:

1. whether Carbon can credibly qualify the exam at all;
2. what recurring live-operation resources one validator would need;
3. which reference, training-data, reconstruction, search-breadth and promotion-evidence profile is best supported by experiments;
4. the expected range of complete comparisons and feedback cadence under that profile;
5. the dominant limiting factor and cheapest decision-changing next test.

Upfront qualification expenditure/risk and recurring live-operation economics are separate records.

## A. Qualification feasibility record

Before optimizing cadence, record:

- physical job and causal inputs;
- target population/envelope and exclusions;
- candidate output contract;
- reference candidates and evidence roles;
- measurement candidates and intended engineering quantities;
- data/solver rights, privacy and access constraints;
- unresolved scientific/security/implementation risks;
- estimated one-time integration, convergence, validation and Dossier effort.

Outcome: `SUPPORTED_FOR_FEASIBILITY`, `UNKNOWN`, or `BLOCKED_FOR_SCOPE`, with named evidence and a next test. No weighted score can compensate for a blocked mandatory requirement.

## B. Reference accuracy-cost frontier

For each legitimate reference configuration:

- measure recurring wall/active compute and failure rate by relevant stratum;
- measure convergence/discrepancy against stronger same-method evidence and independent witness evidence where required;
- compare mean, tail and subgroup discrepancy with candidate differences Carbon intends to resolve;
- run a reference-bias adversarial control where feasible;
- record direct-method deployment latency/cost as a client baseline.

Output: a set of reference configurations that remain scientifically plausible for a registered role. Science/Dossier review, not the profiler, determines adequacy.

## C. Reference-cost crossover

For each scientifically plausible routine reference, compute:

`reference compute / candidate reconstruction compute`.

Test whether bounded committed-cohort reuse would materially increase useful candidate breadth under the same one-validator compute envelope. Include cohort-fill/feedback delay and reuse/security qualification burden. A cache/batch only enters an operating profile after separate authorization.

## D. Training-data frontier

Vary fresh construction-data volume while holding reconstruction compute policy explicit. Measure:

- reference-label generation cost;
- candidate quality and physical diagnostics;
- whether added unique data still improves outcomes;
- reuse/epoch effects when optimizer steps remain fixed.

Training-data count and optimizer updates are different variables.

## E. Validator reconstruction frontier

With training-data policy fixed, vary validator reconstruction effort. Record:

- active compute and memory;
- candidate quality;
- reconstruction variation;
- failure/censoring;
- cold/warm compilation/startup overhead.

Locate the measured knee where additional per-candidate compute buys little compared with evaluating another strategy. Do not infer beyond the measured range.

## F. Proposal-breadth frontier

Under fixed reconstruction profiles, measure selected-candidate quality as the number of distinct useful proposals increases. Preserve proposal identity and correlation. Repeated seeds are reconstruction evidence, not new ideas.

Locate the measured region where additional evaluated proposals show diminishing returns. Proposal arrival/diversity later becomes a live system input.

## G. Promotion-resolution frontier

For close incumbent/challenger pairs, vary fresh common reconstruction/evaluation evidence and measure decision instability. This studies the cost of resolving a frontier decision; it does not authorize candidate-specific weakening of the lean exam.

If additional replications do not reduce uncertainty monotonically, retain `INDETERMINATE` as a valid future policy outcome rather than forcing a winner.

## H. Fixed-validator allocation study

One validator is the planning unit. Validator count is not an optimization variable.

Given a total active-compute envelope, compare allocations among:

- more distinct proposals;
- deeper reconstruction per proposal;
- training-data generation;
- recurring reference work;
- reserved promotion evidence.

Primary research outcome: independently checked scientific progress under equal validator resources. Supporting outcomes include complete comparisons, feedback latency, failure rates and resource utilization.

The target is **verified scientific progress per validator-compute-day**, not raw exams/day by itself.

## I. Operating profile result

Produce a compact record:

- qualification burden and unresolved risks;
- qualified/plausible routine reference options and recurring cost;
- one-validator hardware/resource profile;
- training-data policy;
- reconstruction budget;
- observed useful proposal-breadth region;
- promotion-evidence policy under study/qualified policy when later authorized;
- expected complete comparison range per validator-compute-day;
- expected feedback/cycle time;
- expected discovery productivity or time-to-target under a declared research budget;
- reference/reconstruction/proposal/evidence limiting factor;
- direct solver/reference baseline for the client;
- next decision-changing experiment.

Every numeric output must carry its evidence origin: measured, modeled from measured traces, customer-reported, or unresolved.

## J. Rerun after Wave C

Repeat the same study with the actual Carbon execution path and preserve both versions.

Compare:

- cold/warm startup and compilation;
- real reference adapter and failure behavior;
- real reconstruction/resource receipts;
- candidate inference and measurement execution;
- evidence/receipt signing and orchestration;
- queue/preemption/retry behavior;
- actual admitted backbone catalog;
- real proposal supply;
- actual protected cases and qualified measurements when authorized.

Do not reinterpret the pre-Wave-C fixture as qualified science. Use it to measure model error in the profiler itself: predicted versus observed costs, bottlenecks and preferred operating regions.

## Current development findings

These are fixture-specific evidence, not production settings:

- proposal breadth had strong early value and diminishing returns around the measured 100-step search horizon;
- a medium reconstruction profile was near the cost/quality knee in the tested fixture;
- extra promotion reconstructions did not help in the fixed-incumbent map, while a separate close-strategy study showed that single-rebuild decisions can be noisy;
- the easy Cole–Hopf reference was too cheap for caching to matter operationally;
- reference reuse begins to matter when reference compute becomes a material fraction of reconstruction compute;
- same-method reference resolution far beyond the 128-point output grid added large recurring cost without observable improvement on the easy smooth population;
- very coarse reference configurations entered the same scale as candidate differences and therefore require decision-resolution/adversarial scrutiny even when one observed candidate ranking remains unchanged.

These findings validate the profiling method, not any universal Carbon operating number.
