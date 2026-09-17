# Private Workbench scientific studies

This is the existing Workbench's C-CORE-04 public-source DEVELOPMENT consumer.
It provides local physical-definition checks and a granted Julia Burgers
reference-feasibility study. The operating-envelope action, modified numerical
inputs and private customer calculations remain unavailable. Results remain
`NOT_QUALIFIED`; challenge preparation remains request-only and `UNASSESSED`.
A public template result does not validate an unbound customer design.

## Build separate artifacts

From a canonical checkout with its locked development environment:

```bash
.venv/bin/python Business/Carbon_Fit/workbench/tools/build.py \
  --output-directory .carbon-local/workbench-offline
.venv/bin/python Business/Carbon_Fit/workbench/tools/build.py \
  --private-science --output-directory .carbon-local/workbench-private
```

Open the offline `Carbon_Opportunity_Workbench.html` for local authoring. Its
scientific-service connection is disabled by CSP. The private build permits
only same-origin service requests and must be served by the operator's existing
private host. It embeds neither tokens nor Julia and creates no server or grant.
Do not overwrite the tracked generated HTML or publish the private artifact.

## Compose with the existing private service

The host supplies these existing Python boundaries:

1. `ResearchToolAdapter` over its authenticated research service and trusted
   principal, with the registered public Julia material and valid task grant.
2. `WorkbenchScience(adapter, draft_resolver=...)`. The operator resolver returns
   an exact `RegisteredWorkbenchDraft` for the stored job, design and revision,
   including current revision, permitted scope, physical definition and rights.
   The browser cannot register a draft, choose a principal or grant rights.
3. `create_workbench_app(service, authorize=..., allowed_origin=...)` from
   `carbon.scientific_tasks.workbench_http`. Mount its fixed
   `/api/scientific-studies/{capabilities,start,status,cancel,result}` routes
   before the private static mount. The host's reviewed authentication resolver
   returns the session principal; this factory creates no authentication scheme,
   listener, deployment or persistent controller owner.

Use one exact HTTPS origin (loopback HTTP is allowed for local fixtures).
Preserve the controller and ledger across browser disconnects and HTTP process
restarts; reconcile admitted workers and allocations before shutdown. Existing
research admission, operation identity, budgets and cancellation still govern
every numerical request. Do not use the deterministic fixture host's identity
resolver for production authentication.

In the existing design view, connect to the service and explicitly adopt its
allowed public source definition before checking or running. Start, status,
cancel and results use the same operation and bound draft fingerprint. A cancel
request is pending until worker cleanup is observed. Unknown budgets display as
unknown. Save/reopen uses a separate versioned study bundle; an imported result
is unverified until reread from the service. Relevant physical edits invalidate
association and reject late results. Display edits do not dispatch another run.
Retain source/rights lineage; no automatic public-training handoff is supplied.

The controller's exact public source adapter seam is
`carbon/scientific_tasks/workbench.py` importing only `DOMAIN_LENGTH` and
`requested_times` from `carbon.generators.burgers_dynamics`. Its corresponding
prospective C-CORE-04 invariant allowance must remain exact; this does not grant
worker, miner or browser access to generator internals or protected cases.

## Required checks and bounded evidence

```bash
./scripts/dev/canonical.sh bash scripts/dev/workbench_science_checks.sh
```

The required lane uses Node.js **24.19.0** and the locked development Python
environment. It executes all existing `test_*.cjs` tests, Python source and
authoring tests, and the scientific-service contract/HTTP tests. Source tests
regenerate schemas and release artifacts, so the script makes a disposable
byte-preserving source copy and builds offline/private artifacts into separate
directories under `.carbon-local`. It prints the retained diagnostic path.
It never changes fixture hashes to accommodate host newline conversion.

The development-only `python-docx==1.2.0` pin supports the existing authoring
source tests; it is not a research worker dependency. The pin is verified against
[the official release](https://pypi.org/project/python-docx/1.2.0/) and
[its tagged upstream source](https://github.com/python-openxml/python-docx/tree/v1.2.0).

The separate `browser_scientific_studies_smoke.cjs` exercises desktop/mobile
interaction with deterministic responses; `browser_scientific_studies_native.cjs`
can exercise an explicitly prepared loopback Julia fixture. Neither is a
production authentication or scientific qualification test. The latter requires
an operator-installed exact draft and an existing admitted worker image; running
the checks above creates neither a numerical campaign nor new external spending.
