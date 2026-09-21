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

The normal operator journey no longer assembles these objects by hand. One
supported launcher composes them and serves the private build:

```bash
.venv/bin/python -m carbon.scientific_tasks.workbench_host check \
  --configuration /private/carbon-workbench/runner-profile.json \
  --draft-registry /private/carbon-workbench/drafts.json
.venv/bin/python -m carbon.scientific_tasks.workbench_host serve \
  --configuration /private/carbon-workbench/runner-profile.json \
  --draft-registry /private/carbon-workbench/drafts.json \
  --principals /private/carbon-workbench/staff.json \
  --static /path/to/workbench-private \
  --origin http://127.0.0.1:8770 --port 8770
```

It reuses the same admitted campaign attachment the research MCP command uses,
so campaign ownership, generation, reconciliation and cleanup have exactly one
implementation. `check` starts no container and probes no accelerator; it
reports each capability as `ENABLED`, `CONFIGURED_UNAVAILABLE`, `FIXTURE_ONLY`
or `UNSUPPORTED`. A reviewed draft is installed with `register-draft` into a
private registry that binds it to the exact granted physical definition; a
browser still cannot register a draft, choose a principal or grant rights.
`/api/workbench-host/health` and `/api/workbench-host/capabilities` report
composition state only and carry no physical definition or result.

See `PRIVATE_SERVICE_RUNBOOK.md` for the start/check/stop/recover sequence from
a fresh checkout, including the named staff token file and the recovery table.

The launcher composes these existing Python boundaries, which remain the
supported interface for any other reviewed host:

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

In the existing design view, enter your own staff access token, connect to the
service, and explicitly adopt its allowed public source definition before
checking or running. The browser sends that token as the bearer credential on
every scientific route and holds it in memory for the tab only; it is never
embedded in the build, stored, put in a URL, or written into an export or saved
study. Without a credential the panel states the next action and sends nothing. Start, status,
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

## Prospective two-case operating-envelope composition

C-CORE-08 adds `julia_burgers_envelope_v2`: baseline plus the second exact record
in an already frozen public TRAIN cohort. The capability describes both physical
definitions, their ordered case digests and the full scope digest. These two
observations do not establish a population, scientific qualification, or validity
of customer design text. Arbitrary parameter edits and private inputs remain
unavailable; neither output becomes public training data automatically.

For an operator-approved combined grant, the exact `runtime.scientific_tasks`
value must be `[julia_burgers_scope(image, role_root),
julia_envelope_scope(image, role_root)]`. Construct `PublicJuliaStudy(data,
envelope_scope=the_exact_second_scope)`, then wrap the existing
`JuliaPublicMaterial(PublicMaterial(data), study)` with `JuliaEnvelopeMaterial`.
Pass that material to the same research service and `WorkbenchScience` factories.
Factories recompute and verify the full ordered scope; constructing expected
grant bytes does not grant resources. Old single-case grants and constructors
keep their original behavior and cannot authorize the envelope action.

In the current draft, **Explore operating envelope** selects the v2 operation.
**Assess reference feasibility** selects the existing v1 operation. Both remain
available under the combined grant, retain separate immutable artifacts and can
be saved/reopened independently. Status/cancel/results apply to the displayed
operation. Each case plot uses its own requested time coordinates. A completed
first child remains visible when the second is held, cancelled or unresolved.

The existing CampaignLedger atomically reserves both 720,000 ms worker limits
plus their existing trajectory, invocation and retained-byte vectors, while
preserving final-phase headroom. The parent consumes no additional allowance.
`HELD` means reserved capacity with no dispatched worker; one transaction claims
each child, checking grant, principal and current controller generation. The
second child additionally requires the first child's observed C-04 cleanup
journal. Cancellation after expiry can release only never-claimed capacity;
claimed unknown consumption remains charged. Reconnects never create another
allowance or infer cleanup from a missing worker journal.

`scripts/dev/julia_worker_service.sh` includes the actual two-case, expiry and
running-cancellation fixtures. For the existing loopback browser fixture only,
`tests/service/workbench_native_host.py --envelope` installs the explicit synthetic
combined scope before serving. Set `CARBON_ENVELOPE=1` for
`browser_scientific_studies_native.cjs`, and `CARBON_MOBILE=1` for its mobile
viewport. These fixtures are local engineering controls, not production session
authentication or new research campaign authority.
