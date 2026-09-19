# WEB-QA-05 — Ask Carbon inactive production publication

**Status:** IN PROGRESS — exact static package prepared and reconciled against
current main; both required operator roles are now named, so the operator gate
is satisfied; the production mutation itself has not been executed because no
Cloudflare deployment credential is reachable from the executing environment

**Owner authorization:** approve `ask-carbon-public-release-2026-09-18.2` for
inactive production publication against the reconciled uploaded website source;
the enable step remains separate

**Depends on:** merged WEB-QA-04 / PR #216 and the owner-supplied
`Carbon_Automotive_Cloudflare.zip`

**Primary map ref:** `SYSTEM/PUBLICATION-AUTHORITY`

## Goal

Reconcile the owner's uploaded homepage source with the current Cloudflare
homepage, build the exact dependency-free Ask Carbon bundle, publish it and the
production-disabled API Worker only after the required incident roles are
named, verify both hostnames and rollback state, and leave public activation
disabled.

## Boundaries

- Preserve the existing homepage, Workbench links, routes and unrelated assets.
- Bind only the two reviewed `/api/ask-carbon*` routes.
- Keep `ASK_CARBON_ACTIVATION=disabled`; do not perform the separate enable step.
- Keep issue #139 inquiry collection disabled.
- Preserve the shared USD 50 UTC-month ledger and its nested USD 5 evaluation
  scope; deployment does not reset or replace financial history.
- Do not change scientific execution, shared core interfaces, testnet behavior,
  DNS, paid Cloudflare plan, private data access or qualification state.

## Acceptance

1. Validate the ZIP and reconcile its sole `index.html` to current production
   using a deterministic, hash-pinned Workbench delta.
2. Build and hash the inactive static bundle; distinguish production and
   staging-preview artifacts.
3. Run Ask Carbon tests, production knowledge validation where applicable,
   local browser/static checks and one repository automated acceptance.
4. Before production mutation, record the named incident owner and named
   disable/rollback operator.
5. Publish the static bundle and inactive API route without changing DNS or
   activating provider calls; verify both hostnames, Workbench, CSP/assets,
   inactive health, ledger preservation and rollback.
6. Deliver through one PR under the current expected-head merge protocol.

## Core-programme boundary

This ticket touches only the Ask Carbon website publication surface and its
existing application-specific provider ledger binding. It does not change the
issue #209 shared execution, scientific-task, capability, checkpoint, grant,
artifact, accounting or job-lifecycle interfaces, so no core implementation
coordination is required for this bounded work.

## Named production operators (2026-09-19)

Recorded by the owner as `WEB-QA-05-D2` in `.agent/DECISIONS.md`:

- production incident owners: Ryan Bequette, Nick Fitzpatrick;
- authorized disable/rollback operators: Ryan Bequette, Nick Fitzpatrick.

Either named operator may act independently. Acceptance item 4 is satisfied.

## Reconciliation and current execution state (2026-09-19)

The candidate was reconciled against main `48ed47fc`, which includes the
complete C-CORE-01..14 core programme and Launchpad #235. Every Hub conflict
was resolved by preserving main's reconciled records and reapplying only the
WEB-QA-05 entries; no historical event was rewritten.

Re-verified owner source authority, unchanged since the original
reconciliation:

- owner archive `Carbon_Automotive_Cloudflare.zip` SHA-256
  `d85cfc5cf79d8d6fffa403975dd768ebe69d9874b65d11e511e78b7f2606f125`;
- live `https://carbonphysics.ai/` and `https://www.carbonphysics.ai/` both
  SHA-256 `5ebb43e859e9837f74bbc93b5748b2db95a6700821afbfcecb407e75702e2020`,
  exactly the pinned `observed_live_input_sha256`.

Observed production baseline before any mutation:

- homepage 200 on both hostnames at the pinned hash;
- `/workbench/` 200 and unchanged;
- `/api/ask-carbon/health` 404 — the route is not bound;
- `/ask-carbon/ask-carbon.js` and `.css` 404 — not published.

Acceptance item 5 (publish and verify in production) is **not executed**. No
Cloudflare credential, `wrangler`, `npm` or `node` is available to the
executing environment, so the approved mutation cannot be performed here. This
is an access blocker, not a repository defect; the prepared bundle, hashes,
rollback target and named operators are all resolved and unchanged.
