# Carbon Development Hub v2.1

Carbon's static-first, non-repository orientation and navigation layer.

When browsing on GitHub, start with **`orientation/START_HERE.md`**. It is the primary repository-readable orientation entry.

**`index.html`** is the complete local or hosted static Hub build after cloning or through a configured static host. GitHub's file view is not a hosted Hub application. The page has no script element or automatic remote resource and works through `file://` or a basic static server. `interactive.html` is optional.

## Inventory

- 14 waves (A-N)
- 69 captured tickets across Wave A, Wave B, and Wave C
- 7 protocol-change routes
- 122 map-level change events
- 8 independent maturity states

## Captured current position

Wave **C**; current ticket: **C-10**. Last completed: **C-08** (`done`). Next selected: **none selected**. C-EA1 private-alpha preparation is the latest accepted continuation after PR #168 accepted exact head ea51a947bbf21908144f93ffb04b5e9cc46de519 in run 34830155526 and normally merged as 0ee4c9b8db8339740521e2afc72624c97d8e177a; its broader ticket remains in progress. C-10 alone is selected for a linked fresh public DEVELOPMENT execution and disagreement/quarantine journal over C-01/C-06/C-07. Exact bytes can support only an engineering reproducibility observation; different or unavailable evidence remains unresolved and quarantined. No later ticket is selected in the canonical position; owner direction authorizes a concrete C-EA1 deployment-package continuation only after C-10 merges. No provider provisioning, real archive acknowledgement, C-EA2, protected execution, independent security/scientific acceptance, public network or LIVE authority exists. D6 run 34518806217 remains historical LOCALNET_READY evidence for its exact disposable standard-profile localnet.

## Maintain

Read `orientation/AGENT_MAINTENANCE_CONTRACT.md`. Semantic map updates use
`data/hub_data_v2.json` and `data/change_events.json`; the event template,
renderer, and interactive template are maintained sources for their respective
schema or presentation behavior. Never hand-edit generated outputs. Then run:

```bash
python docs/development/carbon_hub/tools/render_hub.py
python docs/development/carbon_hub/tools/render_hub.py --check
python docs/development/carbon_hub/tools/test_newcomer.py
python docs/development/carbon_hub/tools/validate_hub.py --repo-root .
node docs/development/carbon_hub/tools/test_routes.js
python docs/development/carbon_hub/tools/browser_smoke_test.py
```

The hub explains and routes; repository authority controls implementation and evidence. Manual Pages publication is available to authorized maintainers, but the workflow does not itself enforce owner approval. A required reviewer on the `github-pages` environment, if desired, is a separate human-controlled repository setting. Pages is public when enabled; this integration does not enable it or change settings.
