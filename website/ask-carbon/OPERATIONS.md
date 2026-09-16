# WEB-QA-01 activation and withdrawal runbook

This runbook defines the intended release seam. It does not authorize a
deployment and is not a substitute for the actual website repository's release
instructions.

## Source update and knowledge approval

1. Resolve the actual website repository, production branch, static output and
   Cloudflare project/route owner. Re-check the served homepage SHA-256.
2. Import and review the missing 31 candidate cards and supplied live cases.
   Every card must be paraphrased, publicly releasable, linked only to an
   allow-listed source ID and checked against current governing sources.
3. Record reviewer/owner approval outside the public bundle. Update the
   manifest to `APPROVED_PUBLIC`, set an exact `source_release_date`, and set a
   prospective `expires_at`. Never infer approval from a merge to `main`.
4. Run `node tools/validate-knowledge.mjs --production`. A source update,
   unknown source, incomplete 31-card review, absent approval, missing date or
   expiry must fail the release.
5. Regenerate the static integration only from the reviewed homepage input.
   A changed source hash requires a fresh review; do not use
   `--allow-changed-source` as an automated release bypass.

## Privacy, security and provider activation

Before live answers, the owner must accept the visitor-facing privacy notice,
retention posture and provider data handling. Security review must cover the
Worker, Durable Object, Cloudflare account/route and abuse controls. Provision
the provider key and HMAC secret as Worker secrets—not repository variables,
browser code, logs, PR text or chat.

Set all explicit operational values in the private deployment configuration:

- approved origins and model allowlist plus selected model;
- current input/output price in USD per million tokens;
- daily request and micro-USD ceilings;
- global concurrency and per-client hourly ceilings;
- maximum input/output tokens and provider timeout;
- Durable Object binding and migration.

Run the supplied live cases against every owner-approved candidate and record
support, citation relevance, maturity accuracy, context handling, usefulness,
latency and measured token cost. A second-model check is evidence only; it is
not an authority or an automatic launch choice.

## Routing and activation order

1. Deploy the Worker without a route and with `ASK_CARBON_ACTIVATION=disabled`.
2. Exercise Worker tests in the real Cloudflare runtime, including concurrent
   reservations, restart/recovery, expiry, settlement failure and price math.
   Confirm provider timeouts and malformed responses consume their conservative
   reserved maximum rather than releasing unmeasured spend.
3. Bind only the exact `/api/ask-carbon*` route. Confirm the homepage and
   `/workbench/` remain served by their existing origin.
4. Publish the approved static assets with the generated hash-based CSP and
   confirm cache behavior, desktop/mobile layout, Mobile Safari, keyboard and
   assistive-technology behavior.
5. Verify `/api/ask-carbon/health` is still inactive, then set the explicit
   activation variable only under deployment authorization. Re-check ceilings
   and observe the first bounded requests.

## Rollback and static withdrawal

Rollback order is fail closed:

1. set `ASK_CARBON_ACTIVATION=disabled` and confirm health returns inactive;
2. remove the Worker route while retaining its ledger records for the approved
   operational retention period;
3. remove the one stylesheet tag, `<ask-carbon>` element and module-script tag
   from the static homepage, then publish and purge only the affected assets;
4. verify the homepage and Workbench routes, response headers and absence of
   provider requests;
5. preserve the released manifest, evidence and incident/withdrawal reason as
   historical records rather than rewriting them.

An expired or withdrawn knowledge release disables live serving. It does not
auto-publish a replacement from a later `main` revision.
