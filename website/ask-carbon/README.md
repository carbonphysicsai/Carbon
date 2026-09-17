# Ask Carbon public homepage component

Ask Carbon is a dependency-free component for the existing Carbon homepage. It
is not a second application, an iframe, the authenticated Research Concierge,
or proof of a production deployment.

## Current release state

- Repository knowledge version: `ask-carbon-staging-2026-09-17.1`
- Source release date: 2026-09-17
- Private live-evaluation deployment: `ask-carbon-staging-2026-09-16.1`
- Release: `STAGING_REVIEWED`
- Public activation: disabled
- Private synthetic provider calls: observed through the authenticated staging Worker
- Human quality review: pending
- Production homepage change: none

The production release contract deliberately rejects this manifest. The
explicit `staging-preview` attribute is required to display its saved answers.
Without a valid public release, the default component shows an unavailable
state rather than draft content.

The recovered `Carbon_Ask_v1.zip` matched SHA-256
`ca1e23c3a77ec813c384d893358fe1fe1959edd5989068a5711b04e2821120cb`.
Its 31 cards and 40 single-turn/five-conversation evaluation plan were treated
as draft input and reconciled against current sources, not copied as authority
or retained as a count gate. The current repository collection contains 26
useful reviewed units backed by nine exact source revisions. The private live
evaluation remains pinned to the preceding `2026-09-16.1` snapshot so its
answers and source basis stay inspectable; the `2026-09-17.1` repository
snapshot passed local validation but was not deployed or live-model tested in
that run.

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

Prices were observed in official OpenAI model documentation on 2026-09-16.
The code includes output reasoning tokens in billed output, rejects missing or
negative usage, and rejects an unexpected returned model identity. These are
configured candidates, not a general model comparison. The private synthetic
run used `gpt-5.6-luna:low:v1` through the staging Worker; human quality review
is still pending. A direct provider evaluation is prohibited; live evaluation
must traverse the staging Worker and shared ledger.

## Deployment boundary

The private evaluation deployment uses `carbon-ask-private-staging` with no
production homepage route and the route-less `carbon-ask-budget-authority`
Durable Object script. It remains a staging aid, not a public release. One
central authority prevents separate app environments from each receiving USD
50. Cloudflare charges are separate and were not measured by the provider
ledger. Credentials belong only in the approved secret store. Never put them
in Git, browser assets, chat, issues or evaluation output.
