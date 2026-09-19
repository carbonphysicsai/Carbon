# Optional Workbench MCP App

This package view reuses the existing Workbench request/response validation and
numerical plot. The service remains `WorkbenchScience`, with its registered draft
resolver, public Burgers method, campaign grant, controller and accounting. The
App contains no numerical solver and makes no direct HTTP, credential, storage,
draft-registration or model-provider calls.

The initial view displays a bound public-source study and exposes four explicit
controls: run the same request, status, load results and cancel. It accepts the
original tool input from its host; it does not author a new draft or change
physical parameters. Saved/reopened design studies remain the existing Workbench
workflow. A host reopening this view supplies the exact original input/result.
Two-case results retain ordered case identities and distinguish HELD capacity
from dispatched consumption. All results remain DEVELOPMENT / NOT_QUALIFIED.

## Trusted composition

Ordinary research CLI/server construction installs no App tool or resource.
An operator must explicitly supply both `workbench` and `authorize_workbench` to
`_create_server` or `create_http_app`. The service must be an exact
`WorkbenchScience` object whose `adapter is` the same exact `ResearchToolAdapter`
already supplied to the server. A same-name principal is insufficient.

`authorize_workbench()` is an operator-owned callable, optionally async. It must
raise on absent rights (an explicit `False` also rejects). This is **additional**
authorization: the HTTP factory still supplies its existing token/context guard.
For example, an operator can require its separately issued
`carbon:workbench:public-studies` scope in the verified current token; this name
is demonstrated only by deterministic tests and is not a newly issued grant or
production policy. Never pass a caller-selected guard or infer Workbench rights
from `carbon:research`. Registered drafts and existing grants remain mandatory.

The optional tool is `carbon_workbench_study_v1` with required `action` and
`request` fields. `capabilities` requires `request: null`; `start`, `status`,
`result`, and `cancel` require the unchanged Workbench v1/v2 request object.
The tool forwards to the same service, retains its operation identity and returns
meaningful text plus `{action, request, response, official_eligible:false}`.
Malformed JSON-string envelopes and extra caller identity fields are rejected.
Tool discovery is not an authorization check; direct tool/resource access checks
both guards, and the service checks its scope and lineage again.

The fixed resource is `ui://carbon/workbench-study-v1.html`, with
`text/html;profile=mcp-app`. Its `_meta.ui.csp` declares no external connection,
resource, frame or base domains, and it requests no browser permissions. A host
must enforce the released App sandbox contract. The asset also carries its own
hash-based CSP. Rendering and host notifications do not start work. Cancellation
acknowledgements do not establish worker release. Clients without Apps use the
same structured/text results; no accelerator workflow depends on this view.

## Rebuild and validate

The selected upstream is the stable Apps specification **2026-01-26**, with
`@modelcontextprotocol/ext-apps@2.0.0` (upstream commit
`352f6ced4d80772e92b4e7a311854481a8d65b04`), TypeScript client 2.0.0 and Python
MCP 2.2.0. The pnpm lock pins all transitive integrity. Node 20+ is required;
the existing canonical tooling uses Node 24.19.0 and pnpm 11.19.0.

From this directory:

```sh
pnpm install --frozen-lockfile --ignore-scripts
pnpm build
```

`build.mjs` bundles the SDK and existing Workbench sources, with literal script
insertion. `manifest.json` records normalized-LF source digests and exact emitted
HTML bytes. `THIRD_PARTY_LICENSES.txt` preserves LICENSE/NOTICE text and attribution
from every package actually included by esbuild, normalizing line endings and
trailing horizontal whitespace. A missing package license fails the build.
The installed Python resource checks the HTML's exact digest and size against its
manifest. The exact `.gitattributes` LF rule preserves those bytes on Windows.
Runtime loading uses installed package assets, never repository-relative sources.

From the repository root, with the normal MCP/science test environment:

```sh
python -m pytest tests/cpu/test_mcp_app_asset.py tests/service/test_standard_mcp_apps.py tests/service/test_mcp_app_composition.py tests/cpu/test_workbench_science.py -q
node --test Business/Carbon_Fit/workbench/tests/test_scientific_studies.cjs Business/Carbon_Fit/workbench/tests/test_scientific_envelope.cjs
```

The wire test writes `browser-fixture.json` under its pytest temporary directory.
It contains a deterministic worker's result through the real Workbench service,
not native Julia or paid research evidence. To exercise the actual official
App/AppBridge SDK in a browser, bundle the host from this directory:

```sh
node node_modules/esbuild/bin/esbuild ../../../tests/service/mcp_apps/bridge.mjs --bundle --format=esm --platform=browser --outfile=../../../.carbon-local/mcp-app-browser/bridge.js
```

Then, from the repository root with Playwright and a permitted local Chromium:

```sh
CARBON_BROWSER=/path/to/chromium node tests/service/mcp_apps/browser.cjs /path/to/browser-fixture.json .carbon-local/mcp-app-browser/bridge.js .carbon-local/mcp-app-browser/evidence
```

This harness routes only its synthetic loopback page, uses an actual sandboxed
iframe, sends official input/result messages, exercises four tool controls and
rejects forged qualification. It verifies CSP-blocked fetch, zero external
requests, and desktop/mobile rendering. Its bridge handler is deterministic;
the separate Python SDK test establishes forwarding to the real existing service.
Neither test is a real commercial agent-host run, paid-model usefulness result,
public deployment, security audit or scientific qualification.

Primary references: [stable specification](https://github.com/modelcontextprotocol/ext-apps/blob/352f6ced4d80772e92b4e7a311854481a8d65b04/specification/2026-01-26/apps.mdx),
[official SDK documentation](https://apps.extensions.modelcontextprotocol.io/api/),
[published exact package](https://registry.npmjs.org/@modelcontextprotocol/ext-apps/2.0.0).
