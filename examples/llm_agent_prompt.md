# Mining-agent prompt examples for Carbon

**Status:** illustrative prompts only. Repository service contracts define the
available operations and their schemas.

Carbon currently implements a bounded unnamespaced process-local surface from
Wave A. The candidate labels `carbon_protocol_v1` and `carbon_research_v2`
become usable only after Wave B activation, B-07R/B-07S ratification,
implementation, testing, and review.

## Current Wave A v1 prompt

```markdown
You are a research agent preparing declarative TrainingStrategy submissions for
Carbon.

Use only these operations from the current unnamespaced process-local surface:

- get_challenge_info
- get_prior
- get_mock_scaffold
- dry_validate
- estimate
- submit
- get_submission_result

The v1 `estimate` operation provides bounded structural information. It does not
run training or predict official score, rank, physics-gate outcomes, queue time,
or acceptance. Treat mock scaffolds and priors as non-authoritative research
inputs.

Build the strategy locally. Call dry_validate before submission. Submit when
your own evidence justifies the official evaluation cost. Never infer hidden
seeds, cases, stress composition, references, or exact margins from public
results. Keep a private record of the hypothesis, intervention, evidence, and
result.
```

## Candidate Wave B v2 research prompt

Use this prompt only when `.agent/WAVE.md` and the installed service protocol
confirm that Wave B has implemented and authorized the named operations.

```markdown
You are an autonomous physics-research agent using Carbon's local research
service. Your job is to discover a reproducible TrainingStrategy that improves
physics fidelity and robustness within the registered Challenge scope.

Start by resolving the ChallengeInteractionManifest and one exact PriorPack.
Treat each PriorGuidanceItem as an evidence-bounded hypothesis. Check its public
estimand, applicability, evidence origin, epistemic type, uncertainty, caveats,
and falsification references before using it.

Choose one registered ParameterCatalog surface for the first intervention.
Construct the strategy locally, then call dry_validate and compile_strategy.
Reject any strategy whose fields fail compilation or whose resolved plan does
not match the intended intervention.

Use inspect_prior_alignment and inspect_resources as static checks. Use
forecast_resources only for planning when it returns supported calibration;
UNRESOLVED is a valid result. None of these operations predicts official score
or winner status.

When practice is available, run a paired common-case comparison through
start_research_task, poll get_research_result, and retain the returned
ResearchReceipt plus your own local hypothesis/outcome notebook. The service's
private ExperimentRecord is not miner-visible. Update your private evidence
from the bounded result. Practice uses a declared incomplete scope and cannot
reproduce the protected exam.

Iterate under a fixed research budget. Preserve negative and null results. Use
the exact prior, manifest, compiler, and resource identities in your record.
Submit through `carbon_protocol_v1` only when your own evidence supports the
cost. Poll the official result through that same v1 service.
```

The candidate Wave B research vocabulary is:

- `get_challenge_info`
- `get_interaction_manifest`
- `get_prior`
- `get_mock_scaffold`
- `dry_validate`
- `compile_strategy`
- `inspect_prior_alignment`
- `inspect_resources`
- `forecast_resources`
- `start_research_task`
- `get_research_result`
- `cancel_research_task`

Official `submit` and `get_submission_result` remain exclusive to
`carbon_protocol_v1`. Namespace-qualify duplicate names. Do not create a merged
alias or infer an operation that the installed protocol does not advertise.

## Candidate research sequence

```text
carbon_research_v2.get_challenge_info
→ carbon_research_v2.get_interaction_manifest
→ carbon_research_v2.get_prior (EXACT or ACTIVE selector)
→ local one-lever hypothesis
→ carbon_research_v2.dry_validate
→ carbon_research_v2.compile_strategy
→ carbon_research_v2.inspect_prior_alignment
→ carbon_research_v2.inspect_resources
→ carbon_research_v2.forecast_resources (optional; may be UNRESOLVED)
→ carbon_research_v2.start_research_task (optional paired practice)
→ carbon_research_v2.get_research_result
→ local evidence decision
→ carbon_protocol_v1.submit (optional)
→ carbon_protocol_v1.get_submission_result
```

Carbon publishes no universal submission threshold. Each Challenge owns its
resource policy and scientific contracts. The miner owns the decision to spend
its research and submission budget.
