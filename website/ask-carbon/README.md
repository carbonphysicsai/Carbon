# Ask Carbon public homepage component

Ask Carbon is a dependency-free component for the existing Carbon homepage. It
is not a second application, an iframe, the authenticated Research Concierge,
or proof of a production deployment.

## Current release state

- Repository knowledge version: `ask-carbon-release-candidate-2026-09-18.2` (server-owned reviewed-answer selection successor; not production deployed)
- Source release date: 2026-09-18
- Private staging target: `carbon-ask-private-staging`, version `2cacdb3e-f499-4513-8bf3-f03c92743409`
- Retained homepage live-evaluation source basis: `ask-carbon-staging-2026-09-16.1`
- Release record: `APPROVED_PUBLIC` with `public_activation_allowed: true`, on
  owner approval basis `OWNER_PUBLIC_CONTENT_APPROVAL_2026_09_22_WEB_QA_07_D1`
- Public activation: a separate third gate, `ASK_CARBON_ACTIVATION`, which this
  repository does not assert either way. **Deployed state is read from
  `/health`, not from any file here**
- Live provider calls: bounded WEB-QA-03 and WEB-QA-04 private evaluations only; no production calls
- Private synthetic provider calls: observed through the authenticated staging Worker
- Homepage source-grounded answer review: complete for delivered supported answers
- Owner human-quality disposition for the retained private pilot packet:
  approved in the owner conversation; no separate Nick-authored disposition or
  customer-usability evidence is inferred
- Production homepage change: none

The production release contract deliberately rejects this manifest. The
explicit `staging-preview` attribute is required to display its saved answers.
Without a valid public release, the default component shows an unavailable
state rather than draft content.

The live general-answer provider no longer authors public factual prose. It
selects up to three retrieved reviewed-card IDs and at most one exact reviewed
follow-up. The Worker renders the selected cards' exact reviewed passage text,
pinned source destinations and maturity notes. Unknown, duplicate,
non-retrieved or withdrawn selections fail closed. The guided-pilot mode keeps
its separate proposal schema and does not gain public-answer authority.

The recovered `Carbon_Ask_v1.zip` matched SHA-256
`ca1e23c3a77ec813c384d893358fe1fe1959edd5989068a5711b04e2821120cb`.
Its 31 cards and 40 single-turn/five-conversation evaluation plan were treated
as draft input and reconciled against current sources, not copied as authority
or retained as a count gate. The current repository collection contains 27
useful reviewed units backed by nine exact source revisions. The retained
live-evaluation artifacts remain pinned to the preceding `2026-09-16.1`
snapshot so their answers and source basis stay inspectable. The candidate
private staging surface is prepared for
`ask-carbon-release-candidate-2026-09-18.2`; its changed cases were evaluated
through both registered model candidates and its exact pilot surface was run
through Luna. Prior artifacts remain pinned to their original identities.

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

The candidate registry pins exact application configurations rather than
accepting caller-provided prices:

- `gpt-5.6-luna:low:v1`: USD 0.20/M input, 0.02/M cached input,
  1.20/M output;
- `gpt-5.6-terra:low:v1`: USD 2.00/M input, 0.20/M cached input,
  12.00/M output.

Prices were rechecked in official OpenAI model documentation on 2026-09-18.
The code includes output reasoning tokens in billed output, rejects missing or
negative usage, and rejects an unexpected returned model identity. Both
configurations passed the repaired source-grounded release set through the real
staging Workers and shared ledger. Luna is the selected release candidate
because it was materially cheaper and had no material quality or latency
disadvantage in the retained measurements. This remains a candidate, not public
activation authority. Direct unmetered provider evaluation remains prohibited.

The separate guided-pilot evaluation used Luna through the authenticated
private Worker. The owner approved the retained packet and its visible
limitations; the `.2` successor reran all nine scenarios / eleven turns and
reproduced the same three missing-field limitations. This does not approve the
newer knowledge release, establish customer usability, or qualify Workbench
output.

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
