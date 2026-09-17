# Ask Carbon public-release decision packet

**Decision ID:** `ASK-CARBON-PUBLIC-RELEASE-DECISION-01`

**Status:** concrete candidate in engineering acceptance; owner release approval
required; public activation disabled

**Scope:** public Ask Carbon explanation and guided pilot drafting only

**Not in scope:** inquiry receipt/persistence, customer-data processing,
scientific execution, qualification, protected access, or launch authority

## Decision summary

The bounded private synthetic evaluation is implemented, accepted, and merged
through PR #203. The owner subsequently approved the retained human-quality
packet in the owner conversation. That approval accepts the observed bounded
guidance quality and its three retained missing-field limitations; it does not
prove customer usability or approve public data processing, production
security, publication, routing, or collection.

The release candidate contains knowledge
`ask-carbon-release-candidate-2026-09-18.1`. It is `STAGING_REVIEWED`, expires
on 2026-12-15, and explicitly has `public_activation_allowed: false`. The live
pilot evidence remains bound to `ask-carbon-staging-2026-09-16.1` and
`gpt-5.6-luna:low:v1`. A newer repository manifest does not retroactively
change that evidence.

Recommended release sequence:

1. Complete the exact candidate evaluation, static integration, abuse-policy,
   incident-owner and production-route record. The owner has approved the
   prepared visitor privacy posture.
2. If approved, publish the static component and production Worker **inactive**
   and test the exact homepage integration and rollback.
3. Explicitly enable public general Q&A and guided drafting only after those
   inactive checks pass.
4. Keep inquiry submission unavailable. Visitors may use the form without AI
   and explicitly download their reviewed draft. Do not display a submission
   receipt or contact promise.
5. Implement live inquiry collection later under issue #139 after the private
   receiver, store, access roles, retention/deletion, staff notification, and
   incident controls are accepted and tested.

This split provides the reviewed educational and scoping experience without
pretending the local export is a received customer inquiry.

## Verified production surface

Read-only inspection on 2026-09-18 established:

- `https://carbonphysics.ai/` and `https://www.carbonphysics.ai/` return
  Cloudflare-served HTML with HTTP 200;
- the repository runbook identifies the production static-assets Worker as
  `carbonwebsite`, created by manual Dashboard upload;
- the live homepage is separate from the private Ask Carbon Worker and was not
  changed by the private evaluation;
- the exact immutable homepage source artifact and repeatable upload command
  are not repository-owned inputs yet.

The last point blocks a safe production-page mutation. Before publication,
Engineering needs the exact current homepage HTML/source artifact or a
repository-owned equivalent, the chosen production Worker/route, and the
specific prior deployment used for rollback. Do not use a newly downloaded
homepage as an editable source without reconciling it to the owner's upload
workflow.

## Exact proposed visitor notice

The following copy is the owner-approved visitor posture for this bounded
candidate and is shown before the first AI request. It does not authorize
inquiry collection or confidential/customer-data processing:

> **Before you enable Ask Carbon**
>
> Ask Carbon uses reviewed public Carbon sources to explain Carbon and help
> you draft a possible pilot. If you enable AI guidance, Carbon sends your
> current question and the disclosed high-level draft context to OpenAI through
> Carbon's server. Pilot guidance may include the current brief, proposed
> pilot, unresolved assumptions, and up to ten conversation turns. Contact
> details and the optional conversation-export choice are not sent to the AI.
>
> Do not include confidential engineering, customer, personal, credential,
> solver, model, export-controlled, or protected-evaluation information. The
> current provider project uses `store:false`, but Carbon has not established
> Zero Data Retention or Modified Abuse Monitoring; prompts and responses may
> be retained by the provider for up to 30 days under its default abuse-
> monitoring controls. Clearing this browser view does not delete provider
> records.
>
> You can continue with the form without enabling AI. Nothing is submitted as
> an inquiry by this preview. Downloading a draft saves an unencrypted local
> file that you choose how to share. Ask Carbon does not qualify a model,
> approve a Challenge, promise performance, or authorize scientific work.

Required controls around the notice:

- AI is off until the visitor affirmatively selects **Enable AI guidance**;
- the exact outbound context is previewed before the first request;
- form-only drafting sends no question or draft content;
- conversation export remains unchecked by default;
- clearing local history states that provider records are unaffected;
- optional future reuse permission remains separate from inquiry-response
  permission;
- submission controls remain absent until the receiver is implemented.

## Data handling selected for review

| Action | Leaves browser | Retained by this implementation | Authority |
| --- | --- | --- | --- |
| Use form only | No | Page memory until navigation/clear | Local drafting only |
| Enable general Q&A | Current question plus retrieved public passages | Provider processing may retain prompt/response up to 30 days; Carbon ledger excludes text | Public explanation only |
| Enable pilot guidance | Disclosed brief/context and up to ten turns | Same provider limitation; abandoned raw conversation is not intentionally stored by Carbon | Draft suggestions only |
| Accept/reject/undo suggestion | No additional provider authority | Accepted changes retain client/AI provenance in the local brief | Client brief editing only |
| Download reviewed brief | No automatic transmission | Unencrypted file controlled by visitor | Not an inquiry receipt |
| Submit inquiry | **Unavailable** | No receiver exists | Blocked under issue #139 |

The application has no right to use inquiry submission as consent for
marketing, model training, cross-customer reuse, or scientific evidence.

## Model, knowledge, and budget

Human-quality approval covers the exact private pilot packet generated with
`gpt-5.6-luna:low:v1` and knowledge
`ask-carbon-staging-2026-09-16.1`. It does not select a general-Q&A production
model or approve the newer knowledge release.

The existing implementation enforces one provider budget authority:
`ask-carbon-provider-budget-v2`. General Q&A and `PILOT_DESIGN` share the same
50,000,000 micro-USD (USD 50) UTC-month ceiling. The 5,000,000 micro-USD
evaluation allowance is nested inside that ceiling and is not renewed by this
decision. The repository runbook currently records 295,165 micro-USD of
September application exposure after combining historical ledgers, leaving
4,704,835 micro-USD inside the evaluation allowance before any later ledger
activity. That is a repository-recorded snapshot, not an account invoice.

Production must preserve:

- the same Durable Object authority and legacy exposure offset;
- exact model/configuration and price registry checks;
- pre-dispatch worst-case reservation and conservative unresolved exposure;
- no retries, hedges, direct-provider bypass, or per-environment allowance;
- daily, per-client, per-session, and global concurrency controls;
- form fallback whenever release, privacy, provider, auth, network, or budget
  admission fails.

Cloudflare cost is separate from this provider ledger. No new paid plan or
incremental Cloudflare charge is authorized by this packet.

## Proposed production change

Recommended architecture:

- preserve `carbonwebsite` and its `/` homepage behavior;
- add the reviewed CSS, custom element, module, and release manifest through
  the existing static integration tool;
- deploy one production Ask Carbon Worker bound to the existing shared budget
  authority;
- route only `/api/ask-carbon*` to that Worker;
- use `https://carbonphysics.ai` and `https://www.carbonphysics.ai` as the only
  approved browser origins unless the owner explicitly adds another;
- keep `ASK_CARBON_ACTIVATION=disabled` during publication and inactive checks;
- production must reject the private-staging Basic-auth mode;
- do not expose the ledger, operator route, provider credential, Workbench,
  private evidence, or source-assessment trust roots;
- do not add an inquiry receiver as part of this activation.

Before activation, verify the exact static source hash, CSP, both hostnames,
inactive health, origin rejection, body bounds, edge abuse policy, budget
snapshot, release expiry/withdrawal, cache purge, and rollback. A route or UI
option is not evidence that the production service is active or safe.

Rollback remains:

1. disable `ASK_CARBON_ACTIVATION` and verify inactive health;
2. remove only `/api/ask-carbon*` while retaining financial history;
3. restore the prior `carbonwebsite` deployment and purge affected assets;
4. verify both homepages, CSP, absence of provider calls, and disabled pilot
   guidance;
5. retain the release/withdrawal/incident record and unresolved exposure.

## Decisions required before inactive production publication

The owner should answer these exact questions together:

1. **Notice and processing:** Accept, change, or reject the proposed visitor
   notice and processing description, including potential provider retention
   up to 30 days and synthetic-only evidence to date.
2. **Public knowledge:** Approve the exact candidate as a new
   `APPROVED_PUBLIC` release, or name the required source changes.
3. **Model configuration:** Select the exact production configuration for
   general Q&A and pilot guidance, or keep either mode unavailable. Pilot
   quality approval alone does not select general Q&A.
4. **Abuse and incident ownership:** Name the accepted Cloudflare edge policy,
   incident owner, and disable/rollback operator. Origin checks are not auth or
   abuse control.
5. **Deployment target:** Confirm the production Worker/route and provide the
   exact current homepage source/upload and rollback deployment identities.
6. **Activation scope:** Authorize either inactive publication only, or a later
   explicit bounded activation after the inactive checklist passes.

Issue #139 separately still needs the private receiver/store, staff roles and
destination, persistence-before-receipt, idempotency, notification recovery,
retention/deletion, inquiry notice/permissions, abuse controls, and incident
handling. Those inputs block inquiry collection, not this decision packet.

## Current disposition

```text
PRIVATE_SYNTHETIC_ENGINEERING: ACCEPTED_AND_MERGED
OWNER_HUMAN_QUALITY_DISPOSITION: APPROVED_BOUNDED_PACKET
PUBLIC_KNOWLEDGE_RELEASE: NOT_APPROVED
PUBLIC_MODEL_SELECTION: NOT_SELECTED
PUBLIC_PRIVACY_AND_SECURITY: NOT_ACCEPTED
INACTIVE_PRODUCTION_PUBLICATION: NOT_AUTHORIZED
PUBLIC_ACTIVATION: DISABLED
INQUIRY_COLLECTION: NOT_IMPLEMENTED
CUSTOMER_SESSIONS: 0
SCIENTIFIC_OR_LAUNCH_AUTHORITY: NONE
```
