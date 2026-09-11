# Client Carbon Fit explorer

**Status:** implementation-ready product/science requirements, pending Engineering selection and live-collection approvals.  
**Handoff:** [FIT-WEB-01, issue #139](https://github.com/carbonphysicsai/Carbon/issues/139).  
**Authority:** [Commercial Operating Model](../Commercial_Operating_Model.md) governs rights, access and engagement. The [fit method](DECISION_METHOD.md) supplies planning calculations, not scientific certification.

## 1. User experience

Provide a short plain-language path with optional technical detail. Do not require a model-family choice, equation or exact number from a nontechnical visitor. Offer `I do not know` at technical questions and collect ranges with units where available.

| Screen | Ask |
|---|---|
| Physical job | What decision/output do you need, and what physical system does it concern? |
| Current approach | What method do you use, how long does it take, and what are its known limitations? |
| Evidence access | Do you have simulations, measurements or a solver? Who may use them? Broad categories only. |
| Workload and need | How often will you query it, what turnaround/deployment constraints matter, and what accuracy can you explain? |
| Review | Show inputs, assumptions, unresolved items and preliminary arithmetic; let the visitor correct them. |
| Optional submission | Show the exact payload and ask whether to send it with contact details to Carbon. |

Initial results may state: a gap needs expert review; supplied numbers conflict with a requested limit; evidence is insufficient; or the current baseline may already meet the need. Clearly label calculations as based on supplied information. The public tool cannot set `SUPPORTED_FOR_THIS_STAGE` as an expert finding from an unchecked assertion. It cannot say qualified, approved, guaranteed savings, guaranteed speedup or an official score/rank forecast. It cannot issue a binding quote or admit a network job.

## 2. Anonymous mode and collection boundary

Compute scenarios locally in the browser by default. Do not transmit entered answers before an explicit submission through analytics, session replay, crash reports, autosave, URLs or third-party AI. Disclose unavoidable hosting/security request metadata rather than promise absolute anonymity. Keep initial answer state in memory; explicit local saving/export can be a separately explained feature.

MVP accepts high-level structured information and limited free text, not CAD/mesh files, solver outputs, proprietary datasets, model weights, credentials or executable code. Warn against confidential detail. Do not auto-fetch user-entered URLs. Use synthetic fixtures during development. Do not put actual submissions in this public repository, GitHub issues, Pages, public analytics or an unqualified third-party AI service.

## 3. Submission and delivery

Proposed flow:

```text
client reviews preliminary summary
  -> explicit send action with approved notice/permissions
  -> bounded authenticated-as-appropriate intake API
  -> server validates, normalizes permitted units and recomputes calculations
  -> durable private intake + delivery event
  -> receipt after successful persistence
  -> retryable staff notification with minimal summary and authenticated link
  -> staff triage and evidence-linked follow-up
```

An anonymous visitor may submit without an account if the deployed abuse model permits; staff reads require authentication and authorization. Browser-calculated results and user-supplied status/rights assertions are untrusted. Pin input schema, calculator, rule and notice versions. Retain original assertions and transformed values as distinct provenance under the approved retention policy.

Engineering should use a transactional outbox or equivalent durable delivery design. Submission idempotency binds the request and payload: retry returns the same receipt; reuse of the key with conflicting bytes rejects. Notification retry must not duplicate intakes or lose a persisted inquiry. The UI distinguishes accepted for storage, notification pending and complete failure; never claim Carbon received data before durable acceptance. A receipt ID is not a public bearer credential for reading the record.

Staff notifications contain an inquiry reference and minimal non-sensitive summary, not reference assets, detailed customer data or secrets. The approved destination, private dashboard/store and sender must be configured and tested; the design does not assume an existing email address or CRM. Keep intake credentials separate from scientific execution/reference credentials.

## 4. Information model

Conceptual records, not a new runtime schema mandate:

- Inquiry: id, creation time, schema/rule versions, high-level job, requested claim, baseline, inputs/units/ranges and unknowns, requested resource profile, contact when submitted, notice/permission receipt.
- Preliminary analysis: reproducible calculated terms, input/source refs, assumptions, uncertainty semantics, limit conflicts and next evidence needed. No official result type.
- Review: reviewer, timestamp, evidence refs, six check states, limitations, disposition, next-test scope/budget and stop conditions.
- Outcome: measured construction/reference/program resources and later engagement outcome, each with source, scope and rights. Do not overwrite the customer's original estimate with a measured value.

Use existing engagement/evidence objects through explicit adapters once the opportunity advances. A client assertion, model inference, measured development result and qualified scientific result require different evidence labels. Database storage must not silently upgrade one into another.

## 5. Learn with purpose and permission

Processing and contacting a person about the submitted inquiry is one purpose. Optional use of eligible, minimized information for aggregate service improvement is another. Record approved purposes and policy versions. Do not preselect optional research/aggregate-learning permission or infer rights to train models, publish examples, share cross-customer detail or create priors from submission alone. Rights/legal owners approve the actual notice, basis, retention, deletion, recipients and reuse controls before collection.

First learn from missing inputs, common reference bottlenecks, estimate-versus-actual cost and reasons a reviewed opportunity progressed or stopped. Use only rights-eligible data. Separate contact identity from analysis where possible; de-identification does not guarantee anonymity. Apply approved aggregation/disclosure and deletion policies, including handling derived records and backup lifetimes. Do not export rare-client detail as an aggregate.

Retain the selection context: website inquiries are self-selected, reviewers investigate a subset, and negative/deferred/unmeasured outcomes matter. Sales conversion is not evidence that a model was physically correct. A learned fit predictor, Pareto view or graph requires a prospective utility and leakage study before stronger claims. Intake data cannot change official sampling, truth, gates, weights or exam depth.

## 6. Security and implementation acceptance

Engineering tests exact numerical comparators, units, ranges, zero/negative limits, missing values, overflow, invalid input, server/client parity and version migration. Scenario intervals are not confidence intervals without evidence.

Test persistence failures, duplicate/conflicting retries, outbox recovery, staff access, cross-record access denial, export authorization, text rendering/XSS, injection, CSRF where applicable, abuse/rate limits, record enumeration, log redaction, retention/deletion and secure secret handling. No arbitrary user URL or file processing. Keep intake independent of protected evidence endpoints. Use [OWASP authorization](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html) and [logging](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html) guidance as review inputs.

Product tests keyboard/mobile usability, clear unknowns, nontechnical wording, an accurate review payload, a useful no-submit result and no fabricated badge/price/speedup. Science tests that uncertain/inadequate reference evidence cannot produce an expert-qualified conclusion through favorable economics.

## 7. Activation checklist

Before live collection, name and approve: actual website/repository/host; private store and staff access; notification destination/delivery; security controls and incident owner; notice and purposes; retention/deletion and reuse policy; tested calculator versions and claim wording; and responsible launch approval. No values or vendors are chosen here. The existing site should be discovered and reused where appropriate.

A local prototype can ship through a selected Engineering ticket with sending disabled. Live submission requires the end-to-end receiving path and approvals; a static form or screenshot alone is not a data-collection capability. Website work remains non-blocking for the scientific mainnet path.
