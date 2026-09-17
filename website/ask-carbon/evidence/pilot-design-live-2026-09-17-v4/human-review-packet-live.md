# Ask Carbon private synthetic pilot-design review

Run: `gw08b-private-live-2026-09-17-v4`
Model: `gpt-5.6-luna:low:v1`
Knowledge: `ask-carbon-staging-2026-09-16.1`
Human quality status: `NAMED_PENDING_CONFIRMATION_AND_REVIEW`
Customer sessions: `0` (public/synthetic scenarios only)

Ryan reviews engineering relevance and pilot-design quality. Nick reviews clarity, friction, and prospective-client usefulness. Each reviewer should mark the packet ACCEPT, CHANGE with a named defect, or REJECT with a reason. No response is recorded by this file.

## existing-model-evaluation

Workbench: UNASSESSED -> USE_EXISTING_CAPABILITY; handoff PREPARED.

### Turn 1

Client: We already have a model and want faster comparisons. What should we define first?

Assistant: Define the decision and comparison boundary first: what design decision the loop must support, which inputs and outputs are in scope, the operating envelope, and how the current model’s turnaround and fidelity will be measured. Carbon’s bounded Evidence Audit approach independently tests an existing model against a qualified, problem-specific exam; the exam’s population, sampling, reference process, measurements, and evidence scope require separate review before official use. [business-canon-405a820b; distribution-405a820b]

Next question: What specific design decision should the faster comparison loop support, and what turnaround boundary would make it useful?

Proposals: intended_decision = Decide whether our existing model can support a faster design comparison loop for a specified design decision. | current_baseline = An existing numerical model; baseline turnaround, fidelity measures, and evaluation procedure remain to be documented. | pilot.candidate_inputs = Candidate design inputs and operating conditions within a yet-to-be-defined operating envelope. | pilot.candidate_outputs = Current-model outputs and comparison metrics to be specified for the design decision.

Client actions: ACCEPT=EXPECTED_PROPOSAL_ABSENT

Latency: 12353.83 ms

Final brief summary:

Decision: Decide whether our existing model can support a faster design comparison loop.
Requested result: Compare our current model outputs across candidate designs.
Current baseline: An existing numerical model.
Reported limitation: Turnaround is too slow; the actual timing boundary is not yet specified.
Changing conditions: Unknown
Exclusions: Unknown
Consequential error: Unknown
Comparison evidence (claimed): Unknown
Access/use limitations: Unknown
Preparation time: unknown
Recurring prediction latency: unknown
Reference-query time: unknown
Workload frequency: unknown
Requested accuracy: unknown (unreviewed client intent)

Unresolved: The target turnaround boundary is unspecified. | The design decision, operating envelope, reference process, measurements, and acceptable error or fidelity criteria are unspecified. | It is unknown whether the existing model can be independently evaluated with permitted inputs and outputs.

Ryan disposition: PENDING. Nick disposition: PENDING. Authority/sensitive-data check: PENDING.

## thermal-fluid-cold-plate

Workbench: UNASSESSED -> DEVELOP_NEW_CAPABILITY; handoff PREPARED.

### Turn 1

Client: We want to predict cold-plate temperatures faster. What might a pilot answer?

Assistant: A bounded pilot could test whether a faster temperature-prediction approach preserves decision-relevant accuracy against an agreed baseline across specified heat-load and flow ranges. It should not yet promise a speedup, ranking reliability, or reference adequacy. Any reference result must be authorized for the exact cases, method, version, provenance, uncertainty, applicability, and failure state. [reference-contract-405a820b]

Next question: What existing simulation or test method should serve as the baseline, and what temperature error would be consequential for choosing a design?

Proposals: pilot.candidate_inputs = Cold-plate design descriptions, heat-load conditions, flow conditions, material and boundary-condition data, and any permitted validation cases. | pilot.candidate_outputs = Predicted temperature fields or agreed temperature summaries, hotspot locations or values where applicable, runtime measurements, and design-comparison outputs. | pilot.operating_envelope = An explicitly agreed range of heat loads, flow conditions, designs, and boundary conditions; currently unspecified. | pilot.evaluation_questions = Does the candidate method reduce evaluation time relative to the baseline while meeting the agreed temperature and hotspot criteria across the operating envelope? Does it preserve the design ranking where ranking is decision-relevant?

Client actions: ACCEPT=ACCEPTED_CLIENT_REVIEW, ACCEPT=EXPECTED_PROPOSAL_ABSENT

Latency: 6885.198 ms

Final brief summary:

Decision: Choose a cold-plate design using predicted temperatures.
Requested result: Cold-plate temperatures, hotspots and design ranking.
Current baseline: Unknown
Reported limitation: Unknown
Changing conditions: Heat load and flow vary; the ranges are not yet agreed.
Exclusions: Unknown
Consequential error: Unknown
Comparison evidence (claimed): The team reports existing simulation or test results, but access and adequacy are unreviewed.
Access/use limitations: Unknown
Preparation time: unknown
Recurring prediction latency: unknown
Reference-query time: unknown
Workload frequency: unknown
Requested accuracy: unknown (unreviewed client intent)

Unresolved: The baseline simulation or test method is not identified. | Temperature-error and hotspot tolerances are not defined. | Heat-load and flow ranges are not defined. | The adequacy and accessibility of comparison evidence are unreviewed. | The permitted design and validation cases are not defined.

Ryan disposition: PENDING. Nick disposition: PENDING. Authority/sensitive-data check: PENDING.

## unfamiliar-coupled-physics

Workbench: UNASSESSED -> DEVELOP_NEW_CAPABILITY; handoff PREPARED.

### Turn 1

Client: Can Carbon solve our coupled electro-thermal-structural problem?

Assistant: Carbon cannot currently be confirmed as able to solve this coupled multiphysics problem. The reviewed profile covers a bounded search over neural-operator training strategies; broader model-construction methods remain future architecture, and no production qualification is established. A bounded evidence audit may be more appropriate than requesting a new solver. [constitution-405a820b] [business-canon-405a820b]

Next question: Do you already have an existing model and a finite, shareable evaluation case set whose outputs could be independently compared?

Proposals: pilot.bounded_first_pilot = Assess an existing coupled electro-thermal-structural model through a bounded Evidence Audit, rather than ask Carbon to construct or deploy a new solver. | pilot.missing_evidence = Establish whether the problem, reference process, finite sampling plan, measurements, and output interfaces are sufficiently defined before claiming pilot feasibility.

Client actions: ACCEPT=ACCEPTED_CLIENT_REVIEW, ACCEPT=ACCEPTED_CLIENT_REVIEW

Latency: 17355.953 ms

Final brief summary:

Decision: Assess whether a coupled multiphysics design question warrants a pilot.
Requested result: Coupled response outputs that are not in the reviewed public capability profile.
Current baseline: Unknown.
Reported limitation: Unknown
Changing conditions: Multiple coupled fields; exact interfaces remain unknown.
Exclusions: Unknown
Consequential error: Unknown
Comparison evidence (claimed): Unknown
Access/use limitations: Unknown
Preparation time: unknown
Recurring prediction latency: unknown
Reference-query time: unknown
Workload frequency: unknown
Requested accuracy: unknown (unreviewed client intent)

Unresolved: Whether an existing model is available. | Whether suitable reference results and evaluation cases exist. | Whether the coupled outputs and interfaces can be specified without expanding scope. | Whether protected execution or qualification would be required.

Ryan disposition: PENDING. Nick disposition: PENDING. Authority/sensitive-data check: PENDING.

## sparse-information

Workbench: UNASSESSED -> DEVELOP_NEW_CAPABILITY; handoff PREPARED.

### Turn 1

Client: We need better predictions.

Assistant: “Better predictions” needs a specific engineering decision and prediction target before a bounded pilot can be drafted. Please identify what you predict, what baseline it is compared against, and how the prediction informs a decision.

Next question: What engineering decision should the pilot support, and what quantity or outcome must be predicted to make that decision?

Proposals: none

Client actions: ACCEPT=EXPECTED_PROPOSAL_ABSENT, SKIP=UNKNOWN_RETAINED

Latency: 9401.933 ms

### Turn 2

Client: We cannot answer that yet. What should remain open?

Assistant: Keep the decision, prediction target, baseline, operating conditions, error consequences, evidence, access limits, and pilot scope open until specified. No pilot target or outcome should be assumed yet.

Next question: What specific engineering decision should the pilot support, and what prediction would inform it?

Proposals: intended_decision = Unspecified pending identification of the engineering decision. | requested_result = Unspecified pending definition of the prediction target and decision use. | current_baseline = Unspecified pending identification of the comparator. | pilot.bounded_first_pilot = Remain open until the decision, prediction target, baseline, operating envelope, and evaluation evidence are defined.

Client actions: SKIP=UNKNOWN_RETAINED

Latency: 12210.225 ms

Final brief summary:

Decision: Improve an engineering decision that has not yet been specified.
Requested result: Unknown
Current baseline: Unknown
Reported limitation: Unknown
Changing conditions: Unknown
Exclusions: Unknown
Consequential error: Unknown
Comparison evidence (claimed): Unknown
Access/use limitations: Unknown
Preparation time: unknown
Recurring prediction latency: unknown
Reference-query time: unknown
Workload frequency: unknown
Requested accuracy: unknown (unreviewed client intent)

Unresolved: The prediction target is unspecified. | The baseline comparator is unspecified. | The operating conditions and exclusions are unspecified. | The consequences of prediction error are unspecified. | Available evidence and access limitations are unspecified.

Ryan disposition: PENDING. Nick disposition: PENDING. Authority/sensitive-data check: PENDING.

## Authority ceiling

These are private synthetic live-model observations. They are not customer usability evidence, qualified Carbon evidence, scientific acceptance, rights authorization, execution approval, or public-release approval.
