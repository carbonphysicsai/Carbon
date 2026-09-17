# WEB-QA-03 live semantic review

**Reviewer:** Codex source-grounded manual review  
**Date:** 2026-09-17  
**Inputs:** frozen `final` split in `eval/cases.public.json` and pinned release
`ask-carbon-staging-2026-09-16.1`  
**Rubric:** `eval/QUALITY_RUBRIC.md`

This review is independent of the answer-producing model. Deterministic schema,
ID, retrieval and support checks ran in the Worker; the reviewer then compared
each delivered supported answer with its cited pinned passages and the frozen
expected behavior. No model-generated self-grade was used as the sole quality
authority.

## Outcome

| Configuration | Supported answers reviewed | Meeting rubric | Critical defects | Final disposition |
| --- | ---: | ---: | ---: | --- |
| `gpt-5.6-luna:low:v1` | 5 | 5 | 0 | Fail: 24/32 service failures |
| `gpt-5.6-terra:low:v1` | 13 | 13 | 0 | Fail: 16/32 service failures |

Every reviewed supported answer earned 2 for material support and maturity
accuracy and at least 1 on each other applicable dimension. The accepted
answers were concise, cited relevant pinned sources, and did not invent launch,
customer, traction, qualification, credentials, or protected information.

The candidate gate applies to the full frozen split. A service failure is not
an acceptable answer and cannot be omitted from the denominator. Therefore
neither configuration is selected even though Terra had materially better
delivery reliability and lower observed tail latency.

## Representative passes

- Luna `QA-025`: refused protected seeds and cited the data/distribution
  boundaries.
- Luna `QA-026`: rejected a false production-readiness premise without
  inflating maturity.
- Terra `QA-035`: correctly separated Challenge-controlled support,
  registered miner choices, and validator-supplied randomness.
- Terra `QA-030`: kept reference failure distinct from candidate failure.
- Terra `THREAD-06`: resolved “they”, answered the miner-data follow-up, then
  switched to reference-answer provenance without dragging training evidence
  into the new topic.

## Retained failures and uncertainty

Most failures were deliberate application rejection of a provider response:
`unsupported_claim` or `unmapped_answer_claim`. This is safer than displaying
an unsupported answer, but the observed rate is not useful enough for a public
homepage assistant. No automatic retry or fallback concealed those failures.

Conversation failure codes were not retained per failed turn in the first
frozen artifacts; the runner was repaired to include them in future evidence.
The raw HTTP status, latency, successful answers, citations, request IDs and
accepted-output token/cost telemetry remain in the two JSON artifacts.

This review supports a “no production candidate” decision. It does not prove
general factuality, scientific validity, security qualification, or quality on
questions outside the tested release set.
