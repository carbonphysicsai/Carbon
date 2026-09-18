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

## Current blocker

Repository operations require the production incident owner and the authorized
disable/rollback operator to be named before any production mutation. Neither
identity is inferred from repository or account access. All other source and
package inputs are resolved.
