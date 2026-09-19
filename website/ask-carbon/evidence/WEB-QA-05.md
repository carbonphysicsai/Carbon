# WEB-QA-05 inactive-publication evidence

## Source reconciliation

- Owner upload: `Carbon_Automotive_Cloudflare.zip`
- Archive SHA-256: `d85cfc5cf79d8d6fffa403975dd768ebe69d9874b65d11e511e78b7f2606f125`
- Archive structure: one regular, non-executable file named `index.html`; no
  absolute path, traversal component or symlink
- Uploaded `index.html` SHA-256:
  `546fb89d7df7de98f191ae9585d9952db773eedff4bf33c069f9c6b29f6efb7b`
- Observed production homepage SHA-256:
  `5ebb43e859e9837f74bbc93b5748b2db95a6700821afbfcecb407e75702e2020`

The only semantic delta from the uploaded source to the current production
bytes is the previously deployed Workbench navigation change: one tablet-width
wrapping rule and two `/workbench/` navigation links. The hash-pinned
`--reconcile-owner-upload` path reproduces the observed production bytes
exactly before injecting Ask Carbon.

## Prepared inactive artifact

- Reconciled integration input:
  `5ebb43e859e9837f74bbc93b5748b2db95a6700821afbfcecb407e75702e2020`
- Production-gated integrated `index.html`:
  `d897118ebd16a602994f3498ae8084f4a9ba908cee4aa6a7b8ef1650cc25da55`
- Staging-preview `index.html` retained for comparison:
  `6c6bdcffb82487202d05ba8cbea63305fe0fdacde1516a4cdca6beb50d430017`
- Component CSS:
  `fa02c7eac7d8aa6166dd51c3c651c3776431c4cd21f2a4c5f5981f44dcc97f58`
- Component JavaScript:
  `6a098c0ab3c22bc347519bab0c54183828f1de3ed3646130817f9f3ef307fa0d`
- Pilot designer:
  `57ef27d9e219479ff382a9612ad438910febad6ad8053106c1de3a45973d1c10`
- Release contract:
  `3b91dca55ad7dc787902d307930f8ed018cce42821fdd2fdae42278531ce2329`
- Knowledge:
  `899c9b9947df498ad3e933fecc060ac21871d7d76d8880f3ee5cfe9ee76ed51e`

The production-gated artifact deliberately omits `staging-preview`. The
knowledge remains `STAGING_REVIEWED`, `public_activation_allowed:false`, and
the production Worker remains configured `ASK_CARBON_ACTIVATION=disabled`.
Publishing this artifact therefore does not perform the separately required
enable step.

## Named production operators (2026-09-19)

The owner recorded both required identities as `WEB-QA-05-D2` in
`.agent/DECISIONS.md`:

- production incident owners: Ryan Bequette, Nick Fitzpatrick;
- authorized disable/rollback operators: Ryan Bequette, Nick Fitzpatrick.

Either named operator may act independently; joint action is not required.
The operator gate that previously blocked production mutation is satisfied.

## Source re-verification (2026-09-19)

Re-checked before reconciling the candidate against main `48ed47fc`:

- owner archive `Carbon_Automotive_Cloudflare.zip` recomputed SHA-256
  `d85cfc5cf79d8d6fffa403975dd768ebe69d9874b65d11e511e78b7f2606f125`,
  matching the recorded identity;
- `https://carbonphysics.ai/` and `https://www.carbonphysics.ai/` each
  returned HTTP 200 and SHA-256
  `5ebb43e859e9837f74bbc93b5748b2db95a6700821afbfcecb407e75702e2020`,
  exactly the recorded `observed_live_input_sha256`.

Production has therefore not changed since the original reconciliation, and
no expected hash was repinned.

## Observed pre-mutation production baseline (2026-09-19)

| Probe | Observation |
| --- | --- |
| `https://carbonphysics.ai/` | 200, pinned reconciled hash |
| `https://www.carbonphysics.ai/` | 200, same pinned hash |
| `/workbench/` | 200, present and unchanged |
| `/api/ask-carbon/health` | 404 — route not bound |
| `/ask-carbon/ask-carbon.js` | 404 — not published |
| `/ask-carbon/ask-carbon.css` | 404 — not published |

This is the recovery reference for the inactive publication: Ask Carbon is
currently absent from production, and the rollback target is the recorded
prior `carbonwebsite` deployment.

## Current blocker

Production mutation has **not** been performed. The executing environment has
no reachable Cloudflare credential and no `node`, `npm` or `wrangler`
installation, so the approved static upload, route binding and inactive
health verification could not be executed. Every repository-side input —
source authority, reconciliation, bundle hashes, rollback target, named
operators — is resolved.

Nothing about this blocker is a repository defect, and it does not weaken any
release gate: the candidate still carries `public_activation_allowed:false`
and `ASK_CARBON_ACTIVATION=disabled`.

## Defect found and repaired during reconciliation (2026-09-19)

**Destructive static publication.** The recorded production sequence built the
upload directory with `integrate-static.mjs`, which writes only `index.html`
and the `ask-carbon/` assets, and then deployed that directory to the
`carbonwebsite` static-assets Worker. Because such a deployment replaces the
entire asset set, running the recorded command would have withdrawn every
other live path.

Enumerated from the live site on 2026-09-19, all returning HTTP 200 and all
absent from the tool's output directory:

- `assets/carbon-66e3549179d4.png`, `assets/carbon-f7ea9506b7b9.png`
- `workbench/index.html`, `workbench/app.js`, `workbench/assist-contract.js`,
  `workbench/assist-ui.js`, `workbench/atlas.js`, `workbench/cooling-v02.js`,
  `workbench/engine.js`, `workbench/styles.css`

This directly contradicts the ticket boundary "preserve the existing homepage,
Workbench links, routes and unrelated assets".

**Repair.** `tools/integrate-static.mjs` now pins the required production path
set, accepts `--existing-site DIR` to fold a complete current-site copy into
the bundle, reports `deployable_to_carbonwebsite` plus
`missing_production_paths`, warns on an incomplete bundle, and fails closed
under `--require-complete-bundle`. `OPERATIONS.md` records the corrected
sequence and a post-deploy re-verification of `/workbench/` and `/assets/*`.
Three regression tests in `tests/integration.test.mjs` cover the required path
set, the incomplete Ask-Carbon-only bundle, and the complete bundle.

No prepared artifact hash changed; this repair constrains how the bundle is
assembled and deployed, not what the integrated homepage contains.

## Local verification note

The Windows working tree checks out CRLF, so `validate-knowledge` reports
`source_changed` for all nine pinned sources when run against it. The
committed LF bytes match the pinned digests exactly — for example
`CONSTITUTION.md` hashes to
`7e088fa32805768453900102446c6691198ad46721469594c5992506357feab5` as
recorded. No pinned source hash was repinned. Canonical Linux CI is the
authoritative run.
