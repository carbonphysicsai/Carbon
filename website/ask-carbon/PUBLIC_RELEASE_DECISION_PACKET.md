# Ask Carbon concrete public-release decision packet

## Pending: WEB-QA-09-D1, candidate 2026-09-26.1 (proposed, not approved)

**Asked of:** a named production incident owner under `WEB-QA-05-D2`.

**Approve publication of `ask-carbon-public-release-2026-09-26.1`:**

1. `ask-carbon-public` answers through Chutes (`gemma-4-31b-turbo-tee:v1`,
   `google/gemma-4-31B-turbo-TEE`, confidential compute) instead of OpenAI
   (`gpt-5.6-luna:low:v1`);
2. the visitor notice becomes version `ask-carbon-notice-v2-2026-09-26`
   (exact text in `PRIVACY_AND_RETENTION.md`, SHA-256 `92ee9254…`);
3. live answers default **on** in the Q&A panel only; Pilot Designer guidance
   stays opt-in.

Nothing else changes: knowledge (`d937e9ca…`, already approved under
WEB-QA-07-D1/D2), budget and ceilings, activation, inquiry collection
(disabled).

| Identity | Value |
| --- | --- |
| Bundle identity | `2d575c0acaca498307b2e5c709dc27b5a8bbbfad4d498d6133256857f43988d1` |
| Changed static path | `ask-carbon/ask-carbon.js` → `62ba26ce…` (101/102 identical to live on both hostnames, 2026-09-26T16:39Z) |
| Integrated homepage | `b1e8e7cd…` (unchanged) |
| Worker inputs | `PUBLIC_RELEASE_CANDIDATE.json` → `worker.source_sha256` |
| Rollback targets | `carbonwebsite` `b694b20f…` (content-identity inference); `ask-carbon-public`: capture at deploy |

**What is not verified.** The Chutes adapter is unit-tested against a
constructed fixture only; the first live request through the Worker will be
its first real exercise. It fails closed (typed error, cost settled or held
unresolved) on any response shape it does not expect. The provider's privacy
and confidential-compute properties are Chutes' own statements.

**Blocking before deploy, owned by the client-intake lane:** the Pilot
Designer page still names OpenAI in its AI disclosure and export record. The
exact paths are in `PUBLIC_RELEASE_CANDIDATE.json`. After that lane's change
the bundle is rebuilt, its identity changes, and approval must attach to the
rebuilt identity.

**To record on approval:** approval basis
`OWNER_PUBLICATION_APPROVAL_2026_09_26_WEB_QA_09_D1` on the release record and
a `.agent/DECISIONS.md` entry in the WEB-QA-08-D1 form. The knowledge
record's `approval_basis` does not change.

---

**Decision ID:** `ASK-CARBON-PUBLIC-RELEASE-DECISION-01`

**Candidate:** `ask-carbon-public-release-2026-09-18.2`

**Status:** owner-approved for inactive publication; activation disabled in
this candidate; both required operator roles are named, so the operator gate
is satisfied. Public activation of this exact accepted release is separately
authorized by `WEB-QA-05-D2` and is owned by the successor activation ticket,
not by this candidate.

## Proposed first release

Approve these four capabilities together:

1. public Carbon Q&A from reviewed, pinned public sources;
2. guided pilot drafting after affirmative AI enablement;
3. form-only pilot drafting without AI; and
4. explicit local download of a reviewed draft.

Inquiry collection is disabled and remains issue #139. Download is not
submission, receipt or a promise of staff follow-up. The release does not add
private/customer data, scientific execution, qualification or testnet action.

## Exact package

- Manifest: `PUBLIC_RELEASE_CANDIDATE.json`.
- Knowledge: `ask-carbon-release-candidate-2026-09-18.2`, SHA-256
  `3f22f87a7eee903e74ce58b4c944cbfadab40a62020ea6299610ee1cc4ef671c`;
  27 reviewed cards, nine pinned sources, expiry 2026-12-15, withdrawal epoch
  1, `APPROVED_PUBLIC` under WEB-QA-07-D1 (2026-09-22).
  The card and source content is unchanged from the staging-reviewed set; only
  the release approval block changed, which is why the version identifier is
  the same and the digest is not. The prior digest
  `899c9b9947df498ad3e933fecc060ac21871d7d76d8880f3ee5cfe9ee76ed51e` remains
  correct in `evidence/WEB-QA-04.md` and `evidence/WEB-QA-05.md`, which record
  what was true when those checks ran and are not restated here.
- Model: `gpt-5.6-luna:low:v1`, pricing identity
  `openai-standard-2026-09-16:gpt-5.6-luna`, no automatic retry or fallback.
- Privacy: the bounded visitor posture in `PRIVACY_AND_RETENTION.md`, already
  owner-approved. `store:false` is not described as Zero Data Retention.
- Static candidate: dependency-free component and pilot designer integrated
  into the observed homepage bytes without changing homepage routing.
- Production configuration: `ask-carbon-public`, exact two
  `/api/ask-carbon*` routes, `ASK_CARBON_ACTIVATION=disabled`, production Basic
  auth rejected, and the existing shared Durable Object authority.

The retained Luna/Terra comparison and `.2` affected rerun found both
configurations acceptable on the source-grounded release cases. Luna is
selected because its observed cost was materially lower with no material
quality or latency advantage for Terra. The exact `.2` pilot run returned all
11 public/synthetic turns and preserved the three previously accepted
missing-field limitations. Full evidence is in `evidence/WEB-QA-04.md`.

## Visitor notice

> Ask Carbon uses reviewed public Carbon sources to explain Carbon and help you
> draft a possible pilot. Saved explanations and form-only drafting send no
> question or draft content to the AI provider. If you affirmatively enable AI,
> Carbon sends your current question or the disclosed high-level draft context
> to the OpenAI API through Carbon's server. Pilot guidance may include the
> current brief, proposed pilot, unresolved assumptions and up to ten
> conversation turns. Contact details and the optional conversation-export
> choice are not sent to the AI.
>
> Do not include confidential engineering, customer, personal, credential,
> solver, model, export-controlled or protected-evaluation information.
> Requests use `store:false`, but Carbon has not established Zero Data Retention
> or Modified Abuse Monitoring; prompts and responses may be retained by the
> provider for up to 30 days. Clearing this browser view does not delete
> provider records.
>
> You can draft with the form without AI. Downloading saves an unencrypted local
> file; it does not submit an inquiry, promise staff follow-up, qualify a model,
> approve a Challenge or authorize scientific work.

AI stays off until affirmative action. Accept, reject, undo, direct edit,
reset, missing-information display and download remain client-side controls.
Raw abandoned conversations are not intentionally stored for sales/research.

## Hosting, rollback and cost

Production is the manually uploaded Cloudflare static-assets Worker
`carbonwebsite` in account `7462053c6992b9c9fd889952a7ae0496`, serving both
`carbonphysics.ai` and `www.carbonphysics.ai`. The current production version is
`5a44ab03-ce7c-4100-ae42-71843b07246a`; immediate observed rollback is
`b99c37f0-c2d2-432b-842a-00b9fb518d96`. The private staging and Durable Object
run on the observed Free plan; no new monetary commitment was created.

September application exposure is 453,479 micro-USD, leaving 4,546,521
micro-USD in the nested evaluation allowance and 49,546,521 micro-USD in the
monthly application allowance. Unresolved exposure remains charged. A deploy,
environment or model change does not reset either ceiling. Cloudflare and
out-of-path provider charges remain outside this application counter.

Rollback is fail closed: deploy the committed disabled Worker, remove only the
two API routes if necessary, restore the recorded prior `carbonwebsite`
version, purge affected static assets, and verify both hostnames and Workbench.
Do not delete or roll back Durable Object financial state. Exact commands and
checks are in `OPERATIONS.md`.

## Source reconciliation and remaining production inputs

The owner supplied `Carbon_Automotive_Cloudflare.zip`, SHA-256
`d85cfc5cf79d8d6fffa403975dd768ebe69d9874b65d11e511e78b7f2606f125`.
Its sole regular file is `index.html`, SHA-256
`546fb89d7df7de98f191ae9585d9952db773eedff4bf33c069f9c6b29f6efb7b`.
The current production homepage is exactly that source plus the previously
deployed Workbench navigation delta: one tablet wrapping rule and one
Workbench link in each navigation. The deterministic reconciliation produces
the observed production SHA-256
`5ebb43e859e9837f74bbc93b5748b2db95a6700821afbfcecb407e75702e2020`.

Both previously required names were recorded by the owner on 2026-09-19 as
`WEB-QA-05-D2` in `.agent/DECISIONS.md`:

1. production incident owners: Ryan Bequette and Nick Fitzpatrick;
2. authorized disable/rollback operators: Ryan Bequette and Nick Fitzpatrick.

Either named operator may act independently; joint action is not required.
No production source input remains outstanding. On 2026-09-19 both production
hostnames still served exactly the pinned reconciled source
`5ebb43e859e9837f74bbc93b5748b2db95a6700821afbfcecb407e75702e2020`, so the
recorded reconciliation remains current and no hash was repinned.

## Recorded owner decision

On 18 September 2026 the owner approved this exact package as follows:

> Approve `ask-carbon-public-release-2026-09-18.2` for inactive production
> publication against the reconciled uploaded website source, followed by the
> documented checks and a separately recorded enable step limited to public
> Q&A, guided pilot drafting, form-only drafting and local download, using
> `gpt-5.6-luna:low:v1`, the approved visitor notice and the existing shared
> ceilings. Keep inquiry collection disabled under issue #139.

This authorizes inactive publication only after the two required operator roles
are named. It does not authorize the separately recorded enable step. Until
those roles are supplied, no production homepage or route may change.

```text
PRIVATE_STAGING: ACTIVE_AUTHENTICATED
PUBLIC_KNOWLEDGE_RELEASE: OWNER_APPROVED_FOR_INACTIVE_PUBLICATION
PUBLIC_MODEL_CANDIDATE: GPT_5_6_LUNA_LOW_V1_SELECTED_FOR_REVIEW
PUBLIC_PRIVACY_POSTURE: OWNER_APPROVED_BOUNDED_SCOPE
INACTIVE_PRODUCTION_PUBLICATION: AUTHORIZED_PENDING_NAMED_OPERATORS
PUBLIC_ACTIVATION: DISABLED
INQUIRY_COLLECTION: DISABLED_ISSUE_139
SCIENTIFIC_OR_LAUNCH_AUTHORITY: NONE
```
