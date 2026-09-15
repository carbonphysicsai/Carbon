# Carbon Development Hub v2.1

Carbon's static-first, non-repository orientation and navigation layer.

When browsing on GitHub, start with **`orientation/START_HERE.md`**. It is the primary repository-readable orientation entry.

**`index.html`** is the complete local or hosted static Hub build after cloning or through a configured static host. GitHub's file view is not a hosted Hub application. The page has no script element or automatic remote resource and works through `file://` or a basic static server. `interactive.html` is optional.

## Inventory

- 14 waves (A-N)
- 69 captured tickets across Wave A, Wave B, and Wave C
- 7 protocol-change routes
- 125 map-level change events
- 8 independent maturity states

## Captured current position

Wave **C**; current ticket: **C-W1**. Last completed: **C-10** (`done`). Next selected: **none selected**. PR #180 accepted exact C-EA1-D4 head a4395a3b3f7707fc9e2793e333cc5d101ea01c64 in run 34915666663 and normally merged as 1f9ead70c886f9d04804533eab3579083c4e358d. AWS deployment and spending are deferred; Hippius is the preferred but unverified future provider. C-W1-D1 now selects a separate public/synthetic DEVELOPMENT profile with exact C-08/C-06 source association, bounded same-host retention, an all-burn checked intent and secret-free preflight. Read-only public-testnet observation found the endpoint/genesis/runtime but no registration on scanned netuids for the available public hotkey; the current Darwin arm64 host lacks Docker. No chain write, token spend, real archive acknowledgement, protected/official eligibility, science/security qualification or LIVE authority exists. No later ticket is selected. D6 run 34518806217 remains historical LOCALNET_READY evidence for its exact disposable standard-profile localnet.

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
