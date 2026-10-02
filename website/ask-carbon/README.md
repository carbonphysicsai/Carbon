# Ask Carbon

Ask Carbon is the public Q&A component for Carbon's website. Visitors can explore reviewed explanations of the project and inspect the source material behind each answer. A separate, optional Pilot Designer mode helps structure a proposed engineering project.

The general Q&A provider selects from reviewed answer cards. The Worker returns the selected passages and their pinned sources; the provider cannot supply new factual prose. Unknown, withdrawn, or unsupported selections are refused. Pilot Designer suggestions use a separate proposal schema and require the visitor to accept each change.

## Content and release status

The repository contains 27 reviewed answer cards backed by nine public repository sources. The owner approved the content under `WEB-QA-07-D1` and its dated progress refresh under `WEB-QA-07-D2`. The knowledge identifier remains `ask-carbon-release-candidate-2026-09-18.2`.

On 28 September 2026, three source references were reconciled with the revised GitHub documentation. All answer cards, passages, maturity labels, and expiry dates are unchanged. See the [source review](evidence/PUBLIC_DOCS_SOURCE_REVIEW_2026_09_28.md). The assistant's dated progress answer is therefore still a September 22 snapshot; [Project status](../../docs/publications/PROJECT_STATUS.md) is the newer repository overview.

Content approval and deployment are separate. The recorded website candidate `2026-09-26.1` uses Chutes and was approved under `WEB-QA-09-D1`; its exact approved digests remain in [PUBLIC_RELEASE_CANDIDATE.json](PUBLIC_RELEASE_CANDIDATE.json). The September 28 source refresh changes the knowledge manifest and requires a new deployment decision before inclusion in a website or Worker release. This documentation update does not deploy either.

Read the running Worker's `/api/ask-carbon/health` endpoint to establish deployed state. Repository files alone do not prove which version is live. The committed candidate configuration keeps activation disabled; the separately controlled active configuration enables it only when the content, provider, privacy, and budget checks pass. Without a valid public release, the component shows an unavailable state.

Historical private evaluations remain under `evidence/`, with their original model, knowledge, and source identities. They demonstrate the bounded behavior recorded in each run and do not establish customer usability or production qualification.

## Components

- `public/ask-carbon.js` and `ask-carbon.css`: accessible custom element, saved
  explanations, source inspection and bounded live client;
- `public/release-contract.js`: the single release rule used by UI, build and
  Worker activation;
- `knowledge/public-knowledge.v1.json`: public-only, revision-pinned knowledge;
- `worker/index.mjs`: exact `/api/ask-carbon` Worker path;
- `worker/budget-authority.mjs` and `ledger.mjs`: one non-public Durable Object
  authority shared by evaluation, staging and production;
- `eval/`: all supplied cases, a frozen rubric and Worker-only live runner;
- `tools/integrate-static.mjs`: deterministic injection into an existing static
  homepage without changing its routes or content;
- `PRIVACY_AND_RETENTION.md` and `OPERATIONS.md`: processing and release maps.
- `PILOT_DESIGN_REVIEW.md`: preview notice, shared-budget behavior, evaluation
  state and remaining pilot-mode activation inputs.
- `PUBLIC_RELEASE_DECISION_PACKET.md`: exact proposed notice, data handling,
  combined budget controls, production integration, rollback, and the bounded
  owner decisions required before inactive publication or public activation.

## Local verification

```sh
cd website/ask-carbon
npm test
npm run validate
npm run eval:contract
npm run eval:pilot:plan
npm run eval:pilot:mock
npm run eval:pilot:evidence
```

`eval:contract` measures deterministic retrieval behavior only. It never claims
factuality, citation support or live model usefulness.

The pilot commands retain the original nine scenario descriptions and execute
an adjacent frozen set of literal turns and client review actions. `plan`
enumerates the finite request and shared-budget exposure without network work;
`mock` traverses the real `PILOT_DESIGN` Worker validation, shared ledger,
reviewed-package and Workbench import paths with a test-owned provider. Neither
is live-model or customer-usability evidence. The live mode is bound only to
the authenticated private staging Worker and its shared budget authority. It
requires explicit endpoint, origin, Basic access token and operator snapshot
secret environment variables; it has no direct-provider fallback. Retained
private synthetic observations are under `evidence/pilot-design-live-*`.

## Guided pilot mode

The same adapter now exposes a distinct `PILOT_DESIGN` mode for the local
Carbon pilot designer. It accepts only a bounded schema-derived draft context
and returns proposed edits that the client must accept. General Q&A remains
available. Both modes share one ledger and one owner ceiling of $50 per UTC
month; pilot guidance does not create a second allowance. The local form works
without AI and preserves the draft when guidance is unavailable.

No secret belongs in this repository or browser bundle. Do not send a secret
through chat. Production operators should provision Worker secrets through
their approved Cloudflare release process.

WEB-QA-03 staging additionally requires
`ASK_CARBON_STAGING_AUTH_USER` and `ASK_CARBON_STAGING_AUTH_PASSWORD` as
Cloudflare secrets. The Worker authenticates every staging asset and API
request before serving it. This bounded Basic-auth mode is for private owner
review only and activation rejects it in production.

Evaluation Workers also require a distinct
`ASK_CARBON_EVALUATION_ACCESS_SECRET`. It authorizes only staging
`/api/ask-carbon*` requests while evaluation telemetry is enabled; it cannot
fetch staging assets, is rejected as a production bypass, and does not replace
the separate operator-read secret. The live runner reads it from the operator
environment and never writes it to evidence.

`Business/Carbon_Fit/workbench/Carbon_Client_Pilot_Designer_Preview.html` is
the maintained local preview. It edits the same `carbon.client-intake.draft.v1`
core in conversation and form mode, exports a closed
`carbon.client-intake.reviewed.v1` package, and never submits it. Conversation
inclusion is off by default.

The release does not read that preview. It ships the committed snapshot
`release/pilot-designer.html` (ASK-CARBON-PILOT-SNAPSHOT-01). Refreshing the
snapshot is a release step: see "Shipping a newer Pilot Designer" in
`OPERATIONS.md`.

## Local preview integration

To make a private local staging artifact from the reviewed homepage bytes:

```sh
node website/ask-carbon/tools/integrate-static.mjs \
  --input /path/to/current/index.html \
  --output /tmp/ask-carbon-stage/index.html \
  --asset-prefix ./ask-carbon \
  --staging-preview
```

The tool copies CSS, UI module, shared release contract and knowledge manifest.
It refuses a homepage whose SHA differs from the inspected source unless an
operator explicitly uses `--allow-changed-source` after reviewing the change.
Omitting `--staging-preview` preserves the production release gate.

The 18 September owner upload predates the already-deployed Workbench
navigation links. Reproduce the reviewed production input and inactive bundle
directly from its extracted `index.html` with:

```sh
node website/ask-carbon/tools/integrate-static.mjs \
  --input /path/to/extracted/index.html \
  --output /tmp/ask-carbon-production/index.html \
  --asset-prefix ./ask-carbon \
  --reconcile-owner-upload
```

That flag accepts only the pinned owner-upload SHA, applies only the exact
Workbench navigation delta, and then requires the reconciled bytes to equal the
reviewed live-source SHA before integration. It does not enable Ask Carbon.

## Provider configurations

Each model profile in `worker/models.mjs` names its provider adapter
(`worker/providers.mjs`), the Cloudflare secret that adapter requires, and the
production privacy mode it is disclosed under. Activation fails closed unless
the configured secret and privacy mode belong to the selected profile.

- `gemma-4-31b-turbo-tee:v1` (**production candidate 2026-09-26.1**): Chutes
  `https://llm.chutes.ai/v1/chat/completions`, model
  `google/gemma-4-31B-turbo-TEE`, USD 0.12/M input, 0.012/M cached input,
  0.37/M output, 131,072-token context, `confidential_compute: true`; secret
  `ASK_CARBON_CHUTES_API_KEY`; privacy mode
  `approved_public_privacy_v2_chutes_confidential`. Model id, prices and limits
  read from `GET /v1/models` on 2026-09-26. The adapter is unit-tested against
  a constructed (not recorded) response fixture; it has not been exercised live
  through the Worker.
- `gpt-5.6-luna:low:v1` and `gpt-5.6-terra:low:v1`: OpenAI Responses API,
  retained for the historical evaluation evidence and the private staging
  configuration. Luna served production until candidate 2026-09-26.1.

The code includes reasoning tokens in billed output, rejects missing or
negative usage, and rejects an unexpected returned model identity. Direct
unmetered provider evaluation remains prohibited.

The Q&A panel defaults live answers **on** when the Worker reports active
health; the visitor can switch to saved explanations. Pilot Designer AI
guidance stays **opt-in**: it receives the visitor's own engineering problem,
not a public question about Carbon.

## Deployment boundary

WEB-QA-03 deployed one route-less, non-public budget authority and two private
evaluation Workers on the owning account's existing Free plan. They create no
production route or DNS change. Separate environments bind the same authority
so they cannot each receive USD 50. Credentials belong only in Cloudflare
secrets. Never put them in Git, browser assets, chat, issues or evaluation
output.

The guided-pilot review surface at `carbon-ask-private-staging` is likewise
private and has no production route. Its concurrent ledger is historical only;
the integrated configuration binds all continuing staging callers to
`ask-carbon-budget-authority`. Cloudflare charges remain outside the provider
ledger and were not measured by it.
