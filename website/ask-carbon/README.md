# Ask Carbon public homepage component

Ask Carbon is a dependency-free component for the existing Carbon homepage. It
is not a second application, an iframe, the authenticated Research Concierge,
or proof of a production deployment.

## Current release state

- Knowledge version: `ask-carbon-staging-2026-09-16.1`
- Source release date: 2026-09-16
- Release: `STAGING_REVIEWED`
- Public activation: disabled
- Live provider calls made for this release: zero
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

## Local verification

```sh
cd website/ask-carbon
npm test
npm run validate
npm run eval:contract
```

`eval:contract` measures deterministic retrieval behavior only. It never claims
factuality, citation support or live model usefulness.

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
configured candidates, not live-tested winners. A direct provider evaluation
is prohibited; live evaluation must traverse the staging Worker and shared
ledger.

## Deployment boundary

The example Cloudflare configurations create no deployment or route. One
central, non-public budget authority is required so separate app environments
cannot each receive USD 50. Creating that Durable Object may incur Cloudflare
charges and needs an exact target and authorization. Credentials belong only in
the approved secret store. Never put them in Git, browser assets, chat, issues
or evaluation output.
