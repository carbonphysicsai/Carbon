# Research Concierge, Demand, and Correction Contract

**Version:** 0.1 future implementation contract
**Status:** `SPECIFIED`; not implemented, authenticated, security-qualified, launched, or LIVE
**Decision:** `OWNER-EVIDENCE-RESEARCH-01`
**Tickets:** `C-DC1` through `C-DC4`, `E-D12`, `E-EB1`, `E-EA6`, `E-EA7`

This companion details the launch communication surface and its later demand/release extensions. The exact Wave-B research service protocol remains authoritative for its current namespace. Dialogue is a separately versioned capability and cannot gain official submission, evaluation, or result authority.

## 1. Launch pipeline and deterministic authority

Launch uses one replaceable reasoning component behind narrow application interfaces. A multi-agent hierarchy is optional later work, not a launch dependency.

```text
authenticate
-> validate and bound
-> durably accept
-> authorize thread and requester context
-> classify
-> retrieve approved sources
-> reason
-> check claims and requested actions
-> recheck source availability/permission
-> persist response and lineage
-> deliver
-> project permission-filtered demand observation
```

Acknowledgement follows durable acceptance. Every step records its preconditions, terminal/ retryable failure, policy identity, and idempotency key. Duplicate delivery cannot duplicate requests, charges, notifications, subscriptions, or demand counts.

Deterministic code owns identity, authorization, quotas, tool capabilities, source eligibility, persistence, tenant isolation, disclosure, and spend boundaries. Model output cannot grant permission. A second model may assist quality review but is not a security guarantee.

## 2. Supported and prohibited behavior

Launch supports questions and follow-ups; approved evidence comparisons; failure explanations; public-practice suggestions; hypotheses; research/experiment requests; paid-interest signals; feedback; subscriptions; and a requester-private update inbox. Request acceptance is not funding, scheduling, spending permission, or an SLA. Subscription is not execution permission.

The exact vocabulary belongs to C-DC1, but the v0.3 design cases must remain representable: evidence search, what-to-try, failure diagnosis, intervention comparison, transfer, resource trade-off, experiment design, method discovery, hypothesis/gap submission, experiment/quote interest, feedback, subscription, and product help; with grounded/resource/practice answers, clarification, explicit gap/recorded request, unavailable, and policy-restricted outcomes.

Responses distinguish sourced evidence, requester-reported context, proposed inference/hypothesis, uncertainty, unsupported scope, and unavailable service. An unsupported scientific question yields a scoped `ResearchGap`. Retrieval failure says retrieval is unavailable; it never claims that no evidence exists and never reveals whether Carbon holds a private result, unreleased study, or another tenant's question.

Launch sources are approved public contracts/catalogues, public scaffolds/practice resources, currently authorized PriorPacks, approved public-science resources, and requester-authorized context. Learned official-derived `EvidenceBrief`s require Wave E approval. Paid non-exam sources require separate rights and entitlement.

The service forbids request-time access to the private archive or Landscape; official score, rank, gate-margin, or champion reconstruction prediction; grading or Challenge mutation; autonomous research commissioning or spending; official submission; arbitrary URL fetching; arbitrary SQL; and arbitrary agent code over protected data.

## 3. Context, providers, failures, and audit

Thread context, retrieved documents, tool calls, model calls, output size, elapsed time, and spend are bounded. Timeout, provider failure, stale/withdrawn source, policy denial, and kill-switch activation terminate truthfully. There is no canned unsupported answer after inference failure. Human triage follows the same disclosure and source rules.

Prompts, documents, agent feedback, and tool outputs are untrusted. Tenant prompts, summaries, caches, embeddings, and provider requests remain isolated. External provider use follows approved retention/training/data-location policy; no permission is assumed.

Prompt bodies and optional proprietary context use separately encrypted, expirable payloads under the approved policy. Immutable operational checkpoints must not contain raw prompts, email addresses, user-controlled URLs, or globally searchable prompt hashes. After approved deletion, retain only permitted non-content audit metadata.

Substantive response lineage includes request/thread identity, source IDs and exact versions, claim-support summaries, requester-context references, model/prompt/tool/policy identities, uncertainty/gaps, permitted action traces, availability recheck, and correction state. Private chain-of-thought is neither required nor treated as an audit artifact.

## 4. Durable private threads and updates

Threads, messages, responses, preferences, feedback, subscriptions, and update-entitlement records are append-only/versioned and requester-private. Derived summaries never replace source history. Launch delivery uses private inbox/polling unless the transport owner explicitly approves another mechanism; no silent callback/webhook contract is created.

An operational owner must operate a bounded queue for unresolved requests, public-resource improvements, approved corrections, and human replies. Kill switches can disable reasoning, retrieval classes, updates, or the whole dialogue plane without changing official evaluation.

## 5. Purpose-separated permissions and D12

Service delivery, demand aggregation, internal research, model training, and cross-customer reuse are separate purposes. The system preserves original terms and unknown permission. Service access cannot depend on consent to model training or broad commercial reuse.

`DemandObservation` is a coarse, permission-eligible projection from a private interaction, not the interaction itself. Wave C captures it from launch; Wave E `E-D12` adds aggregation, clustering, manipulation controls, planning, and lineage. Deletion/withdrawal applies to summaries, embeddings, clusters, exports, and backup restoration.

D12 keeps distinct: query volume, threads/campaigns, observed independent organizations, repeat demand, declared budgets, quote requests, issued quotes, accepted quotes, paid campaigns, and repeat purchases. Payment facts come only from the commercial ledger. Account count is not proof of independence or Sybil resistance. Self-reported outcomes never become source-owned measurements.

`ResearchGap` lifecycle:

```text
RECORDED -> TRIAGED -> PROPOSAL_CANDIDATE -> GOVERNANCE_REVIEW
         -> APPROVED_STUDY | RESOURCE_UPDATE | DEFERRED | DECLINED
         -> EVIDENCE_LINKED -> RELEASE_CANDIDATE -> CLOSED_OR_REOPENED
```

Only authorized links may cross records; there is no cross-tenant reference resolution or causal claim based on timing. Popularity cannot create scientific truth, funding, Challenge changes, scoring, or emissions.

## 6. EvidenceBrief and release objects

| Object | Identity/version and lifecycle | Required content and limits |
|---|---|---|
| `KnowledgeClaim` | immutable claim version with source/dependency graph; corrected or invalidated by appended state | scope, epistemic status, support/counterevidence, uncertainty, permission, owner |
| `EvidenceBrief` | immutable approved release version; draft/review/approved/withdrawn/superseded | applicability, comparator/intervention, outcome/estimand, evidence origin, support, uncertainty, counterevidence, resource context, transfer limits, falsification options, release refs |
| `ResearchQuery` / `ResearchResponse` | requester/thread-bound immutable versions | permissions, sources, claim support, policy/model identities, status, update entitlement |
| `ResearchGap` / `DemandObservation` | stable private source identity plus purpose-specific derived versions | no private-source existence leakage; coarse projection only |
| `OutcomeFeedback` | reporter-bound version, explicitly self-reported unless linked to authorized measurement | use/context, uncertainty, permissions; never silently upgraded |
| subscription/update record | requester/topic or response dependency + entitlement/policy version | private delivery target, correction type, delivery/idempotency state |

Offline private analysis, exact-artifact release approval, and external serving are separate gates. The existing cumulative-disclosure mechanism applies across free and paid answers, versions, models, exports, errors, prices, timing, and updates. A new endpoint or customer gets no fresh information budget. Fresh experiments or seeds do not declassify selection knowledge.

Acceptance attacks include raw case/seed extraction, champion reconstruction, per-case margin/membership inference, small-cell isolation, release differencing, model extraction, poisoning, source/rights laundering, cache/hash and price/quote/queue side channels, and official-ordering prediction beyond genuine physics improvement. Coarsening, lag, per-account limits, `no-store`, and revocation are useful controls but are not by themselves privacy, Sybil, or uncopyability guarantees.

Official-derived scientific content and release timing are equal for free and paid miners. Paid service may add permitted analysis, requester context, workflow, and eligible non-exam evidence. Raw archive export is forbidden; assume recipients retain every response. Public PriorPack history is not revoked merely to create recurrence.

## 7. Correction and withdrawal

Dependency tracking is `source -> claim -> brief/prior -> response/model -> deliverable`. A factual correction appends corrected content and may invalidate named uses. Withdrawal changes availability; permission revocation changes permitted use; a prospective policy change governs future use. None silently rescored historical official results.

Impact assessment finds affected briefs, priors, responses, models, reports, recipients, and pending updates. Minimal source-version, response-dependency, availability recheck, and linked-update controls ship in C. Wave E adds transitive archive-to-model-to-customer propagation. Notifications reveal only the recipient's permitted artifact and never a private source's existence.

## 8. Evaluation and launch separation

Concierge release acceptance is an engineering contract. Focused deterministic
tests and bounded integration checks cover approved-source retrieval and source
references, groundedness, abstention, counterevidence, stale/unavailable
sources, failure honesty, suggestion-versus-official-result separation,
authentication, tenant/session isolation, protected-data boundaries, quotas,
cost/latency limits, feedback capture, monitoring, and kill switches. Human
security, privacy, and operations owners retain deployment acceptance for the
exact surface.

A paid benchmark campaign, statistically significant utility improvement,
independent research qualification, or new certification framework is not a
launch prerequisite. Empirical effectiveness is `UNMEASURED` until ordinary
operational feedback or separately budgeted research supplies evidence.
Dialogue readiness is independent of Challenge scientific qualification, and
the Concierge does not gate the core network path: Carbon may release it
disabled and enable it later after its engineering checks pass.
