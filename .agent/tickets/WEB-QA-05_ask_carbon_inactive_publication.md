# WEB-QA-05 — Ask Carbon inactive production publication

**Status:** IN PROGRESS — exact static package prepared; production mutation
blocked only on the two required named operator roles

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
