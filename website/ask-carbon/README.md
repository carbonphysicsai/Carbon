# Ask Carbon public homepage component

Ask Carbon is a dependency-free component for the existing Carbon homepage. It
is not a second application, an iframe, the authenticated Research Concierge,
or proof of a production deployment.

## Current release state

- Knowledge version: `ask-carbon-staging-2026-09-16.1`
- Source release date: 2026-09-16
- Release: `STAGING_REVIEWED`
- Public activation: disabled
- Live provider calls: bounded WEB-QA-03 evaluation only; no production calls
- Production homepage change: none

The production release contract deliberately rejects this manifest. The
explicit `staging-preview` attribute is required to display its saved answers.
Without a valid public release, the default component shows an unavailable
state rather than draft content.

The recovered `Carbon_Ask_v1.zip` matched SHA-256
`ca1e23c3a77ec813c384d893358fe1fe1959edd5989068a5711b04e2821120cb`.
Its 31 cards and 40 single-turn/five-conversation evaluation plan were treated
as draft input and reconciled against current sources, not copied as authority
or retained as a count gate. The current collection contains 26 useful reviewed
units backed by nine exact source revisions.

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

## Local verification

```sh
cd website/ask-carbon
npm test
npm run validate
npm run eval:contract
```

`eval:contract` measures deterministic retrieval behavior only. It never claims
factuality, citation support or live model usefulness.

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

## Provider configurations

The candidate registry pins exact application configurations rather than
accepting caller-provided prices:

- `gpt-5.6-luna:low:v1`: USD 0.20/M input, 0.02/M cached input,
  1.20/M output;
- `gpt-5.6-terra:low:v1`: USD 2.00/M input, 0.20/M cached input,
  12.00/M output.

Prices were rechecked in official OpenAI model documentation on 2026-09-17.
The code includes output reasoning tokens in billed output, rejects missing or
negative usage, and rejects an unexpected returned model identity. These are
configured candidates, not production winners. WEB-QA-03 evaluated both
through the real staging Worker and shared ledger. Terra was more reliable, but
neither cleared the frozen final quality gate, so no production candidate was
selected. Direct unmetered provider evaluation remains prohibited.

## Deployment boundary

WEB-QA-03 deployed one route-less, non-public budget authority and two private
evaluation Workers on the owning account's existing Free plan. They create no
production route or DNS change. Separate environments bind the same authority
so they cannot each receive USD 50. Credentials belong only in Cloudflare
secrets. Never put them in Git, browser assets, chat, issues or evaluation
output.
