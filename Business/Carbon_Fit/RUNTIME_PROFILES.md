# Challenge runtime and resource profiles

**Working design requirements; no production values selected.** See [status](README.md) and [Research Resource Policy Contract](../../Design_Specs/Research_Resource_Policy_Contract.md). This document does not add a second resource-policy engine or an alternate official result taxonomy.

## 1. Recommendation

Adopt finite per-profile limits before real execution or a binding service promise. Do not choose one universal maximum for every Carbon Challenge. A host-level emergency safety cap can coexist with longer programs implemented as bounded scheduled stages. Such a cap does not define scientific feasibility or permit unfinished evidence to pass.

Separate three clocks: client onboarding/qualification; candidate discovery/comparison; and deployed query latency. Different Challenges may use different resource classes and cadence. A changed resource regime that changes the comparison needs prospective identity and review. Do not extend only a favored candidate after seeing outcomes.

## 2. Required profile decisions

| Decision | Bound and timing semantics | Accountable owner |
|---|---|---|
| Construction | Hard wall/active-compute ceilings, accelerator/CPU class and count, peak memory, storage, solver/query allowance; start/stop and pause semantics | Engineering/Operations, with scientific comparability review |
| Candidate exam execution | Per-case and whole-pack resource limits for inference and required measurements, with immutable evidence obligations | Engineering/Operations and Science |
| Reference work | Per-attempt and campaign spending/work limits, qualified method, uncertainty, failure and replacement rules | Reference/Science and Operations |
| Queue/service | Admission capacity, queue expiry, service target, final completion deadline, cancellation and escalation | Operations and commercial owner |
| Replication/retry | Required reconstruction/evaluation replicas, infrastructure retry and resume semantics, total attempt envelope | Existing lifecycle/evidence owners |
| Disclosure | Status vocabulary and timing/precision policy that cannot expose protected cases or detailed failures | Security and disclosure owner |

Profile identity must bind the owning Challenge, execution environment and policy references. These rows are review inputs, not new serialized types. Reuse the existing `ResearchResourcePolicy`, `ResourceClass`, assembly and evidence contracts wherever their current semantics apply; route extensions through their owners.

A customer-entered desired deadline is a request, not admission or a quote. Missing required production limits block that execution profile, not harmless offline analysis.

## 3. Define what the stopwatch measures

Account for startup, compilation, permitted training-data readiness, reconstruction, reference readiness, data transfer, inference, measurement and evidence finalization. Decide how preemption, outages, retries and queueing count. Infrastructure queue time must not silently consume a candidate's active compute entitlement. Charge useful work and overhead according to one prospectively disclosed profile.

Report cold and warm timing separately. A qualified compiled-kernel cache can remove repeat compilation but cannot justify reusing a trained candidate checkpoint where fresh reconstruction is required. For JAX, synchronize device work before reading elapsed time; record compilation, transfers, precision and hardware. See [official JAX benchmarking guidance](https://docs.jax.dev/en/latest/benchmarking.html).

Elapsed turnaround is the completion time of the authorized dependency/resource graph. Parallel reference generation and construction reduce wall time only when their dependencies, secrecy and reserved capacity permit it. GPU-hours and wall time remain different quantities. Adding stage p95 values does not produce an end-to-end p95. Use measured end-to-end trials or an evidence-supported scheduling model, including queues and failures.

## 4. Timeout attribution

An enforcement timeout is not a physical residual measurement.

- Candidate-attributable exhaustion: retain the resource receipt and apply the existing resource/lifecycle policy. It may make the attempt ineligible under the registered resource requirement; do not invent an official physics-failure state or report a physical law violation.
- Reference non-convergence/exhaustion: preserve reference failure/uncertainty. No candidate scientific zero. Do not replace hard cases with easy cases outside the registered SamplingPlan.
- Infrastructure outage, preemption or ambiguous attribution: retain operational evidence; use the owning retry/cancellation policy. Do not grant arbitrary unlimited retries or treat ambiguity as candidate misconduct.
- Service deadline missed: communicate an operational incomplete/delayed outcome. No partial or shallow evidence produces an accepted positive official result.

Budget exhaustion cannot lower reference fidelity, mandatory coverage or physical requirements. Qualified stopping rules, including a conclusive mandatory failure, remain owned by the scientific contract.

## 5. Select real numbers from a calibration program

1. Name the physical job, finite evidence requirement and candidate construction class without inspecting protected official results.
2. Profile development/qualification cases across relevant easy, boundary and difficult strata. Retain failures and censoring.
3. Measure cold/warm construction, solver convergence, peak memory, full mandatory-pack execution, variance and repeated reconstruction where required.
4. Estimate arrival rate, worker resources, queue behavior, retry/replication and fresh-reference production. Test the resulting schedule under representative load.
5. Compare complete costs and delay against client workload value and deployment needs. Choose explicit failure/recovery behavior and operational reserve from evidence, not a universal multiplier.
6. Responsible owners approve the exact profile, limits, uncertainty and review triggers before offering it. Freeze the applicable limits for a comparison cohort.

No numeric runtime, sample count, retry quota, safety factor or service percentile is ratified by this proposal. Revisit a profile prospectively when the workload, hardware, method, cache policy or required evidence changes.

## 6. Test requirements

Engineering should test boundary equality, overshoot and process cancellation, child processes, memory/disk exhaustion, monotonic timing, missing/mismatched profiles, preemption, duplicate/resumed work, evidence persistence and failure attribution. Science should test whether resource censoring changes the realized population or prevents the intended decision resolution. Security should inspect progress/log/timeout side channels.

A successful enforcement test establishes bounded software behavior. It does not establish that the selected budget is scientifically adequate or that a service target is achievable in production.
