# Ask Carbon public homepage component

This directory is an integration candidate for the existing dependency-free
Carbon homepage. It is deliberately not a second application and is not proof
of the production deployment source.

## What it contains

- `public/ask-carbon.js` — accessible custom element, saved explanations, and
  the bounded live API client;
- `public/ask-carbon.css` — component styles aligned with the supplied mobile
  design and current homepage palette;
- `knowledge/public-knowledge.v1.json` — draft public-only knowledge manifest;
- `worker/` — Cloudflare Worker and Durable Object implementation;
- `tools/integrate-static.mjs` — deterministic injection into an existing
  static `index.html` without replacing its content or route;
- `eval/` — evaluation contract and a mock-only harness;
- `tests/` — dependency-free unit and integration tests.

## Fail-closed status

The knowledge release is `DRAFT_NOT_APPROVED`. The referenced 31-card package
and live evaluation cases were not supplied. The Worker also requires explicit
activation, a reviewed unexpired release, approved origins and model, explicit
token prices, global budgets, a per-client hourly ceiling, a provider key, a
signing secret, and a Durable Object binding. Missing any gate returns an
inactive health result and blocks provider calls.

No secret belongs in this repository or browser bundle. Do not send a secret
through chat. Production operators should provision Worker secrets through
their approved Cloudflare release process.

## Local preview integration

```sh
node website/ask-carbon/tools/integrate-static.mjs \
  --input /path/to/current/index.html \
  --output /tmp/ask-carbon-stage/index.html \
  --asset-prefix ./ask-carbon
```

The integration tool copies the three static assets into the output's
`ask-carbon/` directory. Serve the staging directory and open
`/?ask-carbon=open`. The generated page is staging evidence only. By default,
the tool refuses a homepage whose SHA-256 differs from the inspected live
snapshot; `--allow-changed-source` requires a fresh human review of that input.

`node tools/csp-report.mjs /path/to/integrated/index.html` generates a strict
hash-based CSP for the inspected static document. It refuses inline event
handlers and does not use `unsafe-inline`. The current live response did not
include a CSP when inspected on 2026-09-16; adopting generated headers belongs
in the actual deployment repository and release process, which is not
established here.

## Cloudflare bindings

`wrangler.example.toml` documents the intended route and Durable Object
binding without registering or deploying either. Replace every
`OWNER_DECISION_REQUIRED` value in the real private deployment configuration;
never deploy the example as-is.
